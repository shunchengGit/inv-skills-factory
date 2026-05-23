#!/usr/bin/env python3
"""
本地券商研报 PDF：按标的列目录、抽取文本（依赖 pymupdf）。

  pip install pymupdf
  # 或：python3 -m venv .venv && .venv/bin/pip install pymupdf

用法见 skills/stock-research-report-analysis/SKILL.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

DEFAULT_WITHIN_DAYS = 183
DEFAULT_MAX_PAGES = 30

DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
TICKER_PATTERNS = [
    # 带后缀的代码（优先级最高，最精确）：0700.HK / 600276.SS / 300124.SZ / 2330.TW / 005930.KS
    # 这些模式最精确，应优先匹配，避免被括号内的非代码文本（如 "(HA)"）干扰
    (re.compile(r"(?:^|[-_/])(\d{6})\.(SS|SZ)(?:[-_/]|$)"), "a_share_suffixed"),
    (re.compile(r"(?:^|[-_/])(\d{4})\.(HK)(?:[-_/]|$)"), "hk_suffixed"),
    (re.compile(r"(?:^|[-_/])([A-Z]{1,6})\.(?:US|N|O|A)(?:[-_/]|$)"), "us_suffixed"),
    (re.compile(r"(?:^|[-_/])(\d{4})\.(TW)(?:[-_/]|$)"), "tw_suffixed"),
    (re.compile(r"(?:^|[-_/])(\d{6})\.(KS|KQ)(?:[-_/]|$)"), "kr_suffixed"),
    # 中文括号：6位A股代码 （600519）
    (re.compile(r"（(\d{6})）"), "a_share"),
    # 英文括号：6位A股代码 (600519)
    (re.compile(r"\((\d{6})\)"), "a_share"),
    # 中文括号：4-5位港股代码 （00700）
    (re.compile(r"（(\d{4,5})）"), "hk"),
    # 英文括号：4-5位港股代码 (00700)
    (re.compile(r"\((\d{4,5})\)"), "hk"),
    # 中文括号：美股代码 （TSM）
    (re.compile(r"（([A-Z]{1,6}(?:\.[A-Z]{1,2})?)）"), "us"),
    # 英文括号：美股代码 (TSM)
    # 注意：此模式会误匹配文件名中的非代码缩写（如 "Fuyao Glass (HA)" 中的 HA），
    # 因此放在后缀模式之后，确保后缀模式优先匹配
    (re.compile(r"\(([A-Z]{1,6}(?:\.[A-Z]{1,2})?)\)"), "us"),
    # 无括号无后缀的纯代码（紧跟 - 或 _ 分隔符）：如 300124-汇川技术
    (re.compile(r"(?:^|[-_/])(\d{6})(?:[-_/]|$)"), "a_share_bare"),
]

DEFAULT_ROOT = Path.home() / "股票研报"
REPORT_REMOTE = "git@github.com:shunchengGit/stock-report.git"
INDEX_FILE = Path(__file__).resolve().parent.parent / "research-index.json"
TICKER_MAP_FILE = Path(__file__).resolve().parent.parent / "references" / "ticker-folder-map.json"

# 行业/策略研报分类关键词
INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "行业研究-AI": ["AI", "人工智能", "大模型", "LLM", "GPT", "AIGC"],
    "行业研究-半导体": ["半导体", "芯片", "晶圆", "封装", "半导体设备"],
    "行业研究-互联网": ["互联网", "平台经济", "电商"],
    "行业研究-新能源": ["新能源", "光伏", "风电", "储能", "碳中和"],
    "行业研究-汽车": ["汽车", "智驾", "自动驾驶", "新能源车", "智能驾驶"],
    "行业研究-计算机": ["计算机", "软件", "信创", "云计算"],
    "行业研究-光模块": ["光模块", "光通信", "CPO"],
    "行业研究-工业自动化": ["工业自动化", "机器人", "工控"],
    "行业研究-传媒": ["传媒", "游戏", "影视", "短视频"],
    "策略研究": ["策略", "宏观", "A股", "港股", "美股", "市场展望", "投资策略"],
}

# 中文公司简称正则（从文件名中提取）
CN_NAME_PATTERNS = [
    # 匹配 "券商_公司简称（代码）" 或 "券商-公司简称-代码" 格式
    re.compile(r"[-_]([^\-_/\\（(（]{2,10}?)(?:[（(（]\d|[—-]\d)"),
    # 匹配 "代码-公司简称" 格式如 "0700.HK-JPMorgan-Tencent"
    re.compile(r"\d{4,6}\.(?:HK|SS|SZ|TW|KS)-[A-Za-z\s]+-([A-Za-z\s]+?)(?:-|$)"),
]


def default_root() -> Path:
    env = os.environ.get("RESEARCH_PDF_ROOT", "").strip()
    return Path(env).expanduser() if env else DEFAULT_ROOT


def filename_date(name: str) -> str | None:
    m = DATE_PREFIX.match(name)
    return m.group(1) if m else None


def filename_date_as_date(name: str) -> date | None:
    raw = filename_date(name)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_as_of(s: str) -> date:
    if not (s or "").strip():
        return date.today()
    return date.fromisoformat(s.strip())


def timeliness_label(report_date: date | None, as_of: date | None = None) -> str:
    if report_date is None:
        return "unknown"
    ref = as_of or date.today()
    days = (ref - report_date).days
    if days <= 90:
        return "fresh"
    if days <= 183:
        return "aging"
    return "stale"


def extract_ticker_from_filename(name: str) -> str | None:
    for pattern, kind in TICKER_PATTERNS:
        m = pattern.search(name)
        if not m:
            continue
        code = m.group(1)
        if kind in ("a_share", "a_share_bare"):
            if len(code) == 6 and code.isdigit():
                if code.startswith(("6", "9")):
                    return f"{code}.SS"
                return f"{code}.SZ"
        elif kind == "a_share_suffixed":
            suffix = m.group(2)
            return f"{code}.{suffix}"
        elif kind in ("hk",):
            if code.isdigit() and 4 <= len(code) <= 5:
                return f"{code}.HK"
        elif kind == "hk_suffixed":
            return f"{code}.HK"
        elif kind == "us":
            return code
        elif kind == "us_suffixed":
            return code
        elif kind == "tw_suffixed":
            return f"{code}.TW"
        elif kind in ("kr_suffixed",):
            suffix = m.group(2)
            return f"{code}.{suffix}"
    return None


def guess_broker(name: str) -> str | None:
    m = DATE_PREFIX.match(name)
    if not m:
        return None
    rest = name[m.end() :]
    idx = rest.find("_")
    if idx <= 0:
        return None
    return rest[:idx] or None


def is_pdf_name(name: str) -> bool:
    """检查文件名是否为 PDF（含 .undefined.pdf 特殊后缀）。"""
    lower = name.lower()
    return lower.endswith(".pdf") or lower.endswith(".undefined.pdf")


def matches_filter(name: str, code: str | None, contains: str | None) -> bool:
    if not is_pdf_name(name):
        return False
    if code:
        strict = f"（{code}）" in name
        loose = code in name
        if not (strict or loose):
            return False
    if contains and contains not in name:
        return False
    if not code and not contains:
        return False
    return True


def filter_by_recency(
    entries: list[PdfEntry],
    within_days: int,
    as_of: date,
    include_undated: bool,
) -> tuple[list[PdfEntry], date | None]:
    if within_days <= 0:
        return entries, None
    cutoff = as_of - timedelta(days=within_days)
    out: list[PdfEntry] = []
    for e in entries:
        fd = filename_date_as_date(e.path.name)
        if fd is None:
            if include_undated:
                out.append(e)
            continue
        if cutoff <= fd <= as_of:
            out.append(e)
    return out, cutoff


def add_recency_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--within-days",
        type=int,
        default=DEFAULT_WITHIN_DAYS,
        help=f"只保留文件名日期在「--as-of 往前此天数」至「--as-of」之间的 PDF；默认 {DEFAULT_WITHIN_DAYS}（约半年）；0=不按文件名日期过滤",
    )
    ap.add_argument(
        "--as-of",
        default="",
        help="计算「最近半年」的基准日 YYYY-MM-DD，默认今天",
    )
    ap.add_argument(
        "--include-undated",
        action="store_true",
        help="无 YYYY-MM-DD 文件名前缀的 PDF 也纳入（默认排除，因无法判断是否在半年内）",
    )


@dataclass
class PdfEntry:
    path: Path
    sort_key: str
    ticker_guess: str | None = None

    def to_json_row(self, as_of: date | None = None) -> dict:
        n = self.path.name
        fd = filename_date_as_date(n)
        return {
            "path": str(self.path),
            "name": n,
            "date_prefix": filename_date(n),
            "broker_guess": guess_broker(n),
            "ticker_guess": self.ticker_guess or extract_ticker_from_filename(n),
            "timeliness": timeliness_label(fd, as_of),
        }


def load_ticker_map() -> dict[str, str]:
    """加载代码→文件夹名映射表。"""
    if not TICKER_MAP_FILE.exists():
        return {}
    try:
        data = json.loads(TICKER_MAP_FILE.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


def md5_file(path: Path) -> str:
    """计算文件的 MD5 哈希。"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_source_dir(source: Path) -> list[Path]:
    """扫描来源目录下所有 PDF 文件。

    macOS 沙盒限制下 pathlib 可能无法访问 ~/Downloads/，
    此时回退到 AppleScript 获取文件列表。
    """
    if source.is_dir():
        try:
            # 尝试直接 pathlib 扫描
            test = list(source.iterdir())
            return [p for p in source.iterdir() if p.is_file() and is_pdf_name(p.name)]
        except PermissionError:
            pass

    # 回退：AppleScript 获取文件名列表
    try:
        result = subprocess.run(
            [
                "osascript", "-e",
                f'tell application "Finder" to get name of every file of folder "{source.name}" of home',
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            names = [n.strip() for n in result.stdout.strip().split(",")]
            return [source / n for n in names if is_pdf_name(n)]
    except Exception:
        pass

    print(f"无法访问来源目录: {source}", file=sys.stderr)
    return []


def extract_cn_name(filename: str) -> str | None:
    """从文件名中提取中文公司简称。"""
    for pat in CN_NAME_PATTERNS:
        m = pat.search(filename)
        if m:
            return m.group(1).strip()
    return None


def identify_target_folder(
    filename: str,
    ticker_map: dict[str, str],
    existing_folders: list[str],
) -> tuple[str, str]:
    """识别研报应归档的目标子文件夹。

    返回 (目标文件夹名, 识别方式)。
    识别方式: "ticker_map" / "cn_name" / "industry" / "unclassified"
    """
    # 1. 优先从代码查映射表
    ticker = extract_ticker_from_filename(filename)
    if ticker and ticker in ticker_map:
        return ticker_map[ticker], "ticker_map"

    # 2. 从中文简称匹配已有子文件夹
    cn_name = extract_cn_name(filename)
    if cn_name:
        # 精确匹配
        for folder in existing_folders:
            if cn_name == folder:
                return folder, "cn_name"
        # 模糊匹配：简称包含在文件夹名中，或文件夹名包含简称
        for folder in existing_folders:
            if cn_name in folder or folder in cn_name:
                return folder, "cn_name"

    # 3. 代码前缀匹配（如 600276 → 搜索含 恒瑞 的子文件夹）
    if ticker:
        # 去掉后缀，只保留纯数字/字母代码
        pure_code = ticker.split(".")[0]
        for folder in existing_folders:
            if pure_code in folder:
                return folder, "cn_name"

    # 4. 行业/策略研报关键词匹配
    for folder, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in filename:
                return folder, "industry"

    # 5. 无法识别 → _未分类
    return "_未分类", "unclassified"


def collect_entries(root: Path, code: str | None, contains: str | None, *, all_pdfs: bool = False) -> list[PdfEntry]:
    entries: list[PdfEntry] = []
    if not root.is_dir():
        return entries
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if not is_pdf_name(p.name):
            continue
        if not all_pdfs and not matches_filter(p.name, code, contains):
            continue
        d = filename_date(p.name) or "0000-00-00"
        ticker = extract_ticker_from_filename(p.name)
        entries.append(PdfEntry(path=p, sort_key=d, ticker_guess=ticker))
    return entries


def prepare_entries(args: argparse.Namespace) -> list[PdfEntry]:
    root = Path(args.root).expanduser()
    folder = getattr(args, "folder", None)
    if folder:
        target = root / folder
        if not target.is_dir():
            print(f"子文件夹不存在: {target}", file=sys.stderr)
            return []
        raw = collect_entries(target, code=None, contains=None, all_pdfs=True)
    else:
        raw = collect_entries(root, args.code, args.contains)
    as_of = parse_as_of(getattr(args, "as_of", "") or "")
    filtered, cutoff = filter_by_recency(
        raw,
        getattr(args, "within_days", DEFAULT_WITHIN_DAYS),
        as_of,
        getattr(args, "include_undated", False),
    )
    if cutoff is not None and getattr(args, "within_days", 0) > 0:
        print(
            f"# 日期筛选: 文件名日期 ∈ [{cutoff.isoformat()}, {as_of.isoformat()}] "
            f"（--within-days {getattr(args, 'within_days', DEFAULT_WITHIN_DAYS)}）",
            file=sys.stderr,
        )
    entries = sort_entries(filtered, args.sort)
    if args.limit:
        entries = entries[: args.limit]
    return entries


def sort_entries(entries: list[PdfEntry], order: str) -> list[PdfEntry]:
    reverse = order == "date-desc"
    return sorted(entries, key=lambda e: (e.sort_key, e.path.name), reverse=reverse)


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser()
    if not _check_repo_ready(root):
        return 1
    as_of = parse_as_of(getattr(args, "as_of", "") or "")

    if getattr(args, "use_index", False):
        # 索引不存在时自动构建
        if not INDEX_FILE.exists():
            print("# 索引不存在，自动生成...", file=sys.stderr)
            cmd_index(args)
        indexed = query_index(args.code, args.contains, args)
        if indexed is not None:
            if not indexed:
                print("（索引中无匹配）", file=sys.stderr)
                if args.json:
                    print("[]")
                return 1
            if args.json:
                print(json.dumps(indexed, ensure_ascii=False, indent=2))
            else:
                for row in indexed:
                    print(row["path"])
            return 0

    entries = prepare_entries(args)
    if not entries:
        print(
            "（无匹配 PDF：请检查标的/路径，或放宽日期窗口如 --within-days 0）",
            file=sys.stderr,
        )
        if args.json:
            print("[]")
        return 1
    if args.json:
        print(json.dumps([e.to_json_row(as_of) for e in entries], ensure_ascii=False, indent=2))
    else:
        for e in entries:
            print(e.path)
    return 0


def page_indices(page_count: int, mode: str, first_n: int | None, max_pages: int) -> list[int]:
    if page_count <= 0:
        return []
    effective_pages = min(page_count, max_pages)
    if mode == "all":
        return list(range(effective_pages))
    if mode == "first-n":
        n = first_n or 3
        return list(range(min(n, effective_pages)))
    idxs = {0}
    if effective_pages > 1:
        idxs.add(effective_pages - 1)
    return sorted(idxs)


def _need_fitz():
    try:
        import fitz
        return fitz
    except ImportError:
        print(
            "缺少 pymupdf：pip install pymupdf\n"
            "或：python3 -m venv /tmp/research-pdf-venv && "
            "/tmp/research-pdf-venv/bin/pip install pymupdf",
            file=sys.stderr,
        )
        sys.exit(2)


def cmd_extract(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser()
    if not _check_repo_ready(root):
        return 1
    fitz = _need_fitz()
    entries = prepare_entries(args)
    if not entries:
        print(
            "（无匹配 PDF：请检查标的/路径，或放宽日期窗口如 --within-days 0）",
            file=sys.stderr,
        )
        return 1

    max_chars = args.max_chars
    max_pages = getattr(args, "max_pages", DEFAULT_MAX_PAGES)
    for e in entries:
        try:
            doc = fitz.open(e.path)
        except Exception as exc:
            print(f"# 跳过无法打开的 PDF: {e.path.name} ({exc})", file=sys.stderr)
            continue
        try:
            n_pages = doc.page_count
            idxs = page_indices(n_pages, args.pages, args.first_n, max_pages)
            fd = filename_date_as_date(e.path.name)
            tl = timeliness_label(fd)
            parts: list[str] = [f"### {e.path.name}\npages={n_pages} timeliness={tl}\n"]
            used = len(parts[0])
            for i in idxs:
                text = (doc.load_page(i).get_text() or "").strip()
                block = f"\n--- page {i + 1} ---\n{text}"
                if used + len(block) > max_chars:
                    block = block[: max(0, max_chars - used)] + "\n…(截断)"
                    parts.append(block)
                    break
                parts.append(block)
                used += len(block)
            if n_pages > max_pages:
                parts.append(f"\n…(仅解析前 {max_pages} 页，共 {n_pages} 页，用 --max-pages 调整)\n")
            sys.stdout.write("".join(parts) + "\n\n")
        finally:
            doc.close()
    return 0


def query_index(code: str | None, contains: str | None, args: argparse.Namespace) -> list[dict] | None:
    if not INDEX_FILE.exists():
        return None
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    entries = data.get("entries", [])
    as_of = parse_as_of(getattr(args, "as_of", "") or "")
    within_days = getattr(args, "within_days", DEFAULT_WITHIN_DAYS)

    results = []
    for entry in entries:
        if code:
            ticker = entry.get("ticker", "")
            if ticker != code and code not in entry.get("filename", ""):
                continue
        if contains and contains not in entry.get("filename", ""):
            continue
        if within_days > 0:
            rd = entry.get("report_date")
            if rd:
                try:
                    rd_date = date.fromisoformat(rd)
                    cutoff = as_of - timedelta(days=within_days)
                    if not (cutoff <= rd_date <= as_of):
                        continue
                except ValueError:
                    pass
        results.append(entry)
    return results


def cmd_index(args: argparse.Namespace) -> int:
    fitz = _need_fitz()
    root = Path(args.root).expanduser()
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 1

    existing: dict[str, dict] = {}
    if INDEX_FILE.exists():
        try:
            data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
            for entry in data.get("entries", []):
                existing[entry.get("filename", "")] = entry
        except Exception:
            pass

    as_of = date.today()
    entries: list[dict] = []
    scanned = 0
    skipped = 0

    for p in sorted(root.rglob("*")):
        if not p.is_file() or not is_pdf_name(p.name):
            continue
        name = p.name
        fd = filename_date_as_date(name)
        ticker = extract_ticker_from_filename(name)
        broker = guess_broker(name)
        tl = timeliness_label(fd, as_of)

        if name in existing and existing[name].get("pages") is not None:
            entry = existing[name]
            entry["timeliness"] = tl
            entries.append(entry)
            continue

        try:
            doc = fitz.open(p)
        except Exception:
            entries.append({
                "filename": name,
                "path": str(p),
                "ticker": ticker,
                "broker": broker,
                "report_date": fd.isoformat() if fd else None,
                "pages": None,
                "first_page_chars": None,
                "likely_scanned": True,
                "last_indexed": as_of.isoformat(),
                "timeliness": tl,
                "error": "cannot_open",
            })
            skipped += 1
            continue

        try:
            t0 = (doc.load_page(0).get_text() or "").strip()
            entries.append({
                "filename": name,
                "path": str(p),
                "ticker": ticker,
                "broker": broker,
                "report_date": fd.isoformat() if fd else None,
                "pages": doc.page_count,
                "first_page_chars": len(t0),
                "likely_scanned": len(t0) < 80,
                "last_indexed": as_of.isoformat(),
                "timeliness": tl,
            })
            scanned += 1
        finally:
            doc.close()

    index_data = {
        "meta": {"last_updated": as_of.isoformat(), "total": len(entries)},
        "entries": entries,
    }
    INDEX_FILE.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"索引已更新: {len(entries)} 条（新增扫描 {scanned}，跳过 {skipped}）", file=sys.stderr)
    print(f"写入: {INDEX_FILE}", file=sys.stderr)
    return 0


def cmd_organize(args: argparse.Namespace) -> int:
    """从来源目录扫描研报 PDF，归档到研报库对应子文件夹。"""
    source = Path(args.source).expanduser()
    root = Path(args.root).expanduser()
    contains = getattr(args, "contains", None)
    execute = getattr(args, "execute", False)

    if execute and not _check_repo_ready(root):
        return 1

    if not source.exists():
        print(f"来源目录不存在: {source}", file=sys.stderr)
        return 1
    if not root.is_dir():
        print(f"研报库根目录不存在: {root}", file=sys.stderr)
        return 1

    # 加载映射表和已有子文件夹
    ticker_map = load_ticker_map()
    existing_folders = [p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]

    # 扫描来源目录
    pdfs = list_source_dir(source)
    if contains:
        pdfs = [p for p in pdfs if contains in p.name]

    # 过滤空文件（0 字节）
    non_empty = []
    for p in pdfs:
        try:
            if p.stat().st_size > 0:
                non_empty.append(p)
            else:
                print(f"跳过空文件: {p.name}", file=sys.stderr)
        except Exception:
            pass
    pdfs = non_empty

    if not pdfs:
        print("来源目录中未找到 PDF 文件", file=sys.stderr)
        return 0

    # 识别并归档
    results: list[dict] = []
    for pdf_path in pdfs:
        target_folder, method = identify_target_folder(pdf_path.name, ticker_map, existing_folders)
        target_dir = root / target_folder
        target_path = target_dir / pdf_path.name
        action = "移动"
        need_create = False

        # 检查目标文件夹是否需要新建
        if not target_dir.exists():
            need_create = True

        # 检查同名文件冲突
        if target_path.exists():
            src_md5 = md5_file(pdf_path)
            dst_md5 = md5_file(target_path)
            if src_md5 == dst_md5:
                action = "跳过(重复)"
            else:
                # 同名不同内容，加后缀
                stem = pdf_path.stem
                suffix = pdf_path.suffix
                counter = 2
                while target_path.exists():
                    target_path = target_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                action = f"移动(重命名→{target_path.name})"

        results.append({
            "source": pdf_path,
            "target_dir": target_dir,
            "target_path": target_path,
            "folder": target_folder,
            "method": method,
            "action": action,
            "need_create": need_create,
        })

    # 输出预览表格
    mode_label = "执行" if execute else "预览"
    print(f"\n研报归档{mode_label}（共 {len(pdfs)} 份）\n")

    # 表格输出
    col_file = 42
    col_folder = 18
    col_action = 16
    col_method = 12

    header = f"{'文件名':<{col_file}} {'目标文件夹':<{col_folder}} {'操作':<{col_action}} {'识别方式':<{col_method}}"
    sep = "─" * (col_file + col_folder + col_action + col_method + 3)
    print(sep)
    print(header)
    print(sep)

    moved = 0
    skipped = 0
    deleted = 0
    created_dirs: set[str] = set()

    for r in results:
        fname = r["source"].name
        if len(fname) > col_file - 2:
            fname = fname[:col_file - 5] + "..."
        folder = r["folder"]
        if r["need_create"]:
            folder += "(新建)"
            created_dirs.add(r["folder"])
        if len(folder) > col_folder - 2:
            folder = folder[:col_folder - 5] + "..."
        action = r["action"]
        method = r["method"]

        print(f"{fname:<{col_file}} {folder:<{col_folder}} {action:<{col_action}} {method:<{col_method}}")

        if execute and action != "跳过(重复)":
            # 创建目标文件夹
            if r["need_create"]:
                r["target_dir"].mkdir(parents=True, exist_ok=True)
            # 移动文件
            try:
                shutil.move(str(r["source"]), str(r["target_path"]))
                moved += 1
            except Exception as exc:
                print(f"  ⚠ 移动失败: {exc}", file=sys.stderr)
        elif action == "跳过(重复)":
            skipped += 1
            if execute:
                # 已归档的重复文件，直接删除源文件
                try:
                    r["source"].unlink()
                    deleted += 1
                except Exception as exc:
                    print(f"  ⚠ 删除源文件失败: {exc}", file=sys.stderr)

    print(sep)

    # 汇总
    to_move = sum(1 for r in results if r["action"] != "跳过(重复)")
    if execute and deleted > 0:
        print(f"\n汇总: 共 {len(results)} 份 | 移动 {moved} | 重复跳过 {skipped} | 删除源文件 {deleted} | 新建文件夹 {len(created_dirs)}")
    else:
        print(f"\n汇总: 共 {len(results)} 份 | 待移动 {to_move} | 重复跳过 {skipped} | 需新建文件夹 {len(created_dirs)}")
    if created_dirs:
        print(f"新建文件夹: {', '.join(sorted(created_dirs))}")

    if not execute and to_move > 0:
        print(f"\n💡 加 --execute 参数以实际执行移动")
        return 0

    if not execute:
        return 0

    # ── execute 模式：归档后处理 ──

    # 5. 输出研报库全部文件清单（供 Agent 判断过期）
    file_list = _collect_file_list(root)
    print(f"\n── 研报库文件清单（共 {len(file_list)} 份）──")
    print(json.dumps(file_list, ensure_ascii=False))

    # 6. 重建索引
    print("\n# 重建索引...", file=sys.stderr)
    cmd_index(args)

    # 7. git 操作
    _git_commit_and_push(root)

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """初始化研报库：从远程仓库 clone 或 pull。"""
    import subprocess as sp

    root = Path(args.root).expanduser()
    remote = getattr(args, "remote", REPORT_REMOTE)

    if root.exists():
        git_dir = root / ".git"
        if not git_dir.exists():
            print(f"错误: {root} 已存在但不是 git 仓库，无法初始化", file=sys.stderr)
            return 1
        print(f"研报库已存在，执行 git pull...")
        r = sp.run(["git", "-C", str(root), "pull"], capture_output=True, text=True)
        if r.returncode != 0:
            print(f"git pull 失败: {r.stderr.strip()[:300]}", file=sys.stderr)
            return 1
        print(r.stdout.strip() or "已是最新")
        # 重建索引
        cmd_index(args)
        return 0

    # clone
    parent = root.parent
    parent.mkdir(parents=True, exist_ok=True)
    print(f"git clone {remote} → {root} ...")
    r = sp.run(["git", "clone", remote, str(root)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"git clone 失败: {r.stderr.strip()[:300]}", file=sys.stderr)
        return 1
    print(r.stderr.strip() or "clone 完成")
    # 首次 clone 后建索引
    cmd_index(args)
    return 0


def _check_repo_ready(root: Path) -> bool:
    """检查研报库是否已初始化。未初始化时提示运行 init。"""
    git_dir = root / ".git"
    if not root.exists() or not git_dir.exists():
        print(f"研报库未初始化，请先运行: research_pdf.py init", file=sys.stderr)
        return False
    return True


def _collect_file_list(root: Path) -> list[dict]:
    """收集研报库所有 PDF 文件信息，供 Agent 判断过期。"""
    files = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or not is_pdf_name(p.name):
            continue
        try:
            folder = p.parent.name if p.parent != root else ""
        except Exception:
            folder = ""
        files.append({
            "path": str(p),
            "folder": folder,
            "filename": p.name,
        })
    return files


def _git_commit_and_push(root: Path) -> None:
    """在研报库目录执行 git add -A && git commit && git push。"""
    import subprocess as sp

    git_dir = root / ".git"
    if not git_dir.exists():
        print("# 研报库不是 git 仓库，跳过提交", file=sys.stderr)
        return

    # 检查是否有变更
    result = sp.run(["git", "-C", str(root), "status", "--porcelain"],
                    capture_output=True, text=True)
    if not result.stdout.strip():
        print("# 无变更，跳过提交")
        return

    today = date.today().isoformat()
    cmds = [
        (["git", "-C", str(root), "add", "-A"], "git add"),
        (["git", "-C", str(root), "commit", "-m", f"chore: 归档研报 {today}"], "git commit"),
        (["git", "-C", str(root), "push"], "git push"),
    ]
    for cmd, label in cmds:
        r = sp.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"# ⚠ {label} 失败: {r.stderr.strip()[:200]}", file=sys.stderr)
            return
    print(f"# git commit & push 完成 ({today})")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="本地研报 PDF：列出与抽取")
    p.add_argument(
        "--root",
        default=str(default_root()),
        help=f"研报目录（也可用环境变量 RESEARCH_PDF_ROOT），默认 {DEFAULT_ROOT}",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="初始化研报库：从远程仓库 clone 或 pull")
    init.add_argument("--root", default=str(default_root()), help=f"研报库本地路径，默认 {DEFAULT_ROOT}")
    init.add_argument("--remote", default=REPORT_REMOTE, help=f"远程仓库地址")
    init.set_defaults(func=cmd_init)

    pl = sub.add_parser("list", help="列出匹配 PDF 路径（按文件名日期排序）")
    pl.add_argument("--code", help="6 位证券代码，如 000858")
    pl.add_argument("--contains", help="文件名需包含的子串，如 五粮液")
    pl.add_argument("--folder", help="直接扫描指定子文件夹（如 福耀玻璃、微软），跳过代码匹配")
    pl.add_argument("--sort", choices=("date-asc", "date-desc"), default="date-asc")
    pl.add_argument("--limit", type=int, default=0, help="最多条数，0 表示不限")
    pl.add_argument("--json", action="store_true", help="输出 JSON（含日期与券商猜测）")
    pl.add_argument("--use-index", action="store_true", help="优先从 research-index.json 查询")
    add_recency_args(pl)
    pl.set_defaults(func=cmd_list)

    pe = sub.add_parser("extract", help="抽取文本到 stdout（默认首尾页）")
    pe.add_argument("--code")
    pe.add_argument("--contains")
    pe.add_argument("--folder", help="直接提取指定子文件夹下的研报，跳过代码匹配")
    pe.add_argument("--sort", choices=("date-asc", "date-desc"), default="date-asc")
    pe.add_argument("--limit", type=int, default=0)
    pe.add_argument(
        "--pages",
        choices=("edges", "all", "first-n"),
        default="edges",
        help="edges=首页+末页；all=全文；first-n=前 N 页（见 --first-n）",
    )
    pe.add_argument("--first-n", type=int, default=3, help="与 --pages first-n 联用")
    pe.add_argument("--max-chars", type=int, default=12000, help="每个 PDF 写入 stdout 的最大字符数")
    pe.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES, help=f"单次解析最大页数，默认 {DEFAULT_MAX_PAGES}")
    add_recency_args(pe)
    pe.set_defaults(func=cmd_extract)

    org = sub.add_parser("organize", help="从指定目录扫描研报 PDF，归档到研报库对应子文件夹")
    org.add_argument("--source", default=str(Path.home() / "Downloads"), help="来源目录，默认 ~/Downloads")
    org.add_argument("--root", default=str(default_root()), help=f"研报库根目录，默认 {DEFAULT_ROOT}")
    org.add_argument("--execute", action="store_true", help="实际执行移动（默认 dry-run 预览）")
    org.add_argument("--contains", help="只处理文件名包含此子串的文件")
    org.set_defaults(func=cmd_organize)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd not in ("organize", "init") and not getattr(args, "code", None) and not getattr(args, "contains", None) and not getattr(args, "folder", None):
        print("请指定 --code 和/或 --contains", file=sys.stderr)
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
