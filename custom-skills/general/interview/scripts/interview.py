#!/usr/bin/env python3
"""面试管理脚本"""

import argparse
import re
from datetime import datetime
from pathlib import Path

RESUME_DIR = Path.home() / ".resume"


def list_candidates():
    """列出所有候选人"""
    if not RESUME_DIR.exists():
        print("面试目录不存在")
        return

    pdfs = list(RESUME_DIR.glob("*.pdf"))
    if not pdfs:
        print("暂无候选人简历")
        return

    print(f"=== 候选人列表 ({len(pdfs)}人) ===")
    for pdf in sorted(pdfs):
        name = extract_name(pdf.name)
        status = check_status(name)
        print(f"  {name:12s} [{status}]")


def extract_name(filename: str) -> str:
    """从简历文件名提取姓名"""
    # 去掉文件扩展名
    base = filename.replace(".pdf", "").strip()
    # 提取中文姓名（2-4个汉字）或英文名
    patterns = [
        r"】\s*([^】_]+?)(?:[._\s]|$)",          # 】后的人名（优先，最精确）
        r"[一-鿿]{2,4}(?=[._\s]|$)",  # 中文汉字（fallback）
        r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?",       # 英文名
    ]
    for p in patterns:
        match = re.search(p, base)
        if match:
            name = match.group(1) if p.startswith(r"】") else match.group(0)
            if name.strip():
                return name.strip()
    return base[:20]  # fallback: 取前20个字符


def _extract_job_info(filename: str) -> str:
    """从简历文件名提取岗位和年限，如 'Android开发 2年'"""
    base = filename.replace(".pdf", "").strip()
    # 去空格避免 "Andro id" 匹配失败
    compact = base.replace(" ", "")
    # 找年限
    years = ""
    ym = re.search(r"[_ ]?(\d+)\s*年", base)
    if ym:
        years = f" {ym.group(1)}年"
    # 找岗位关键词
    if "Android" in compact:
        job = "Android开发"
    elif "iOS" in compact or "IOS" in compact:
        job = "iOS开发"
    else:
        job = "开发"
    return f"{job}{years}"


def check_status(name: str) -> str:
    """检查候选人状态"""
    question_file = RESUME_DIR / f"面试题_{name}.md"
    if question_file.exists():
        content = question_file.read_text(encoding="utf-8")
        if "评分" in content or "score" in content.lower():
            return "已面试"
        return "已出题"
    return "待处理"


SENIOR_DIMS = [
    ("学习能力", 50),
    ("毅力", 50),
]

MID_DIMS = [
    ("智力", 35),
    ("学习能力", 35),
    ("毅力", 30),
]


def _dim_section(name: str, question_count: int, idx: int, start_q: int) -> str:
    """生成维度章节模板。每题只有结构没有内容，等 AI 读简历后填充。"""
    labels = ["一", "二", "三"]

    questions = []
    for i in range(question_count):
        qn = start_q + i
        q = f"""### Q{qn} 【基于简历出题】
> 引用候选人简历中的具体经历，构造开放性问题

**考察点：** 这道题看什么信号、为什么选这个维度

| 分数 | 标准 |
|------|------|
| 1 | 行为锚点：得分1的典型表现 |
| 2 | 行为锚点：得分2的典型表现 |
| 3 | 行为锚点：得分3的典型表现 |
| 4 | 行为锚点：得分4的典型表现 |
| 5 | 行为锚点：得分5的典型表现 |"""
        questions.append(q)

    return f"## {labels[idx]}、{name}（{question_count}题）\n\n" + "\n\n---\n\n".join(questions)


def generate_questions(name: str, level: str = "mid"):
    """生成面试题文件模板"""
    pdf_files = [f for f in RESUME_DIR.glob("*.pdf") if name in f.name]
    if not pdf_files:
        print(f"未找到 {name} 的简历")
        return

    output = RESUME_DIR / f"面试题_{name}.md"
    if output.exists():
        print(f"面试题已存在: {output}")
        return

    dims = SENIOR_DIMS if level == "senior" else MID_DIMS
    questions_per_dim = 6 if level == "senior" else 4
    dim_count = len(dims)
    summary_num = ["三", "四", "五"][dim_count - 2]  # 2维→三, 3维→四 (实际是第 dim_count+1 个章节)

    # 从简历文件名提取岗位和年限信息
    pdf_name = pdf_files[0].name
    job_info = _extract_job_info(pdf_name)

    q_counter = 1
    dim_blocks = []
    for i, (d, _) in enumerate(dims):
        dim_blocks.append(_dim_section(d, questions_per_dim, i, q_counter))
        q_counter += questions_per_dim
    dims_md = "\n".join(dim_blocks)

    # 维度加权行
    total_weight = sum(s for _, s in dims)
    weight_rows = "\n".join(
        f"| {d} | Q{i*questions_per_dim+1}-Q{(i+1)*questions_per_dim} | {s / total_weight * 60:.0f} | {s / total_weight * 100:.0f}% |"
        for i, (d, s) in enumerate(dims)
    )

    template = f"""# 面试问题列表与评分标准

## 候选人：{name} | {job_info} | 核心考察：{' + '.join(d for d, _ in dims)}

<!-- 出题规范：
  1. 每道题必须引用候选人简历中的具体经历，拒绝泛泛提问
  2. 考察点要说清「这道题看什么信号、为什么选这个维度」
  3. 评分表每级写具体行为锚点，不要「较好」「一般」等模糊词
  4. 一票否决项：如果某题得分1说明什么维度能力缺失，必须写明
  5. 红旗信号：写出每题得分≤2的隐患含义
-->

---

{dims_md}

---

## {summary_num}、评分汇总

| 维度 | 题目 | 总分 | 加权 |
|------|------|------|------|
{weight_rows}

### 综合评级

| 总分 | 评级 | 判断 |
|------|------|------|
| 45-60 | A | 强烈推荐，底层能力突出 |
| 36-44 | B | 推荐，底层能力合格 |
| 27-35 | C | 待定，需要额外验证 |
| <27 | D | 不推荐，底层能力不足 |

### 一票否决项
<!-- 列出哪些题得分1意味着某个维度能力缺失，直接否决 -->
- [ ]

### 红旗信号（不否决但需警惕）
<!-- 列出哪些题得分≤2意味着存在隐患，需要额外验证 -->
- [ ]"""

    output.write_text(template, encoding="utf-8")
    print(f"已生成面试题: {output}")
    print(f"简历: {pdf_name} ({pdf_files[0].stat().st_size // 1024}KB)")

    # 额外提示
    pdf_path = pdf_files[0]
    size_kb = pdf_path.stat().st_size // 1024
    print(f"提示: 简历 {pdf_path.name} ({size_kb}KB)，出题时请基于简历实际声明")


def feedback(name: str, score: int = None, rating: str = None):
    """记录面试反馈"""
    question_file = RESUME_DIR / f"面试题_{name}.md"
    if not question_file.exists():
        print(f"未找到 {name} 的面试题文件")
        return

    content = question_file.read_text(encoding="utf-8")

    if score:
        content = re.sub(r"总分:.*", f"总分: {score}/60", content)

    if rating:
        for r in ["A", "B", "C", "D"]:
            content = content.replace(f"□ {r}", f"{'☑' if r == rating else '□'} {r}")

    question_file.write_text(content, encoding="utf-8")
    print(f"已记录 {name} 的面试反馈")


def main():
    parser = argparse.ArgumentParser(description="面试管理")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="列出候选人")

    gen_parser = subparsers.add_parser("generate", help="生成面试题")
    gen_parser.add_argument("name", help="候选人姓名")
    gen_parser.add_argument("--level", choices=["senior", "mid"], default="mid",
                           help="候选人级别 (senior=2维度50/50, mid=3维度35/35/30)")

    fb_parser = subparsers.add_parser("feedback", help="记录面试反馈")
    fb_parser.add_argument("name", help="候选人姓名")
    fb_parser.add_argument("--score", type=int, help="总分")
    fb_parser.add_argument("--rating", choices=["A", "B", "C", "D"], help="评级")

    args = parser.parse_args()

    if args.command == "list":
        list_candidates()
    elif args.command == "generate":
        generate_questions(args.name, args.level)
    elif args.command == "feedback":
        feedback(args.name, args.score, args.rating)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
