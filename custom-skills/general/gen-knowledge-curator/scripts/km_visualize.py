#!/usr/bin/env python3
from __future__ import annotations

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""知识图谱可视化：解析 OKF 知识库，生成自包含交互式 HTML。

功能：
- Cytoscape.js 力导向图，节点按 type 着色，大小按正文长度
- 搜索框实时筛选、类型过滤、布局切换
- 分栏详情面板：标题、类型标签、描述、资源、标签、全文 markdown、回链
- 内部链接可点击导航图谱

用法:
  uv run km_visualize.py
  uv run km_visualize.py -o ~/Desktop/graph.html
  uv run km_visualize.py --max-nodes 100
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "lib"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, _read_frontmatter

KNOWLEDGE_DIR = Path.home() / ".knowledge"
DEFAULT_OUTPUT = KNOWLEDGE_DIR / "knowledge-graph.html"

_LINK_RE = re.compile(r"\]\(([^)]+)\)")

_TYPE_PALETTE = {
    "Article": "#3b82f6",
    "Analysis": "#8b5cf6",
    "Synthesis": "#ec4899",
    "Reference": "#10b981",
    "Metric": "#f59e0b",
    "Playbook": "#ef4444",
    "Note": "#94a3b8",
}
_DEFAULT_COLOR = "#94a3b8"


def _extract_links(body: str, entry_dir: str, all_paths: set[str]) -> list[str]:
    """从正文提取指向知识库内其他条目的链接。"""
    out: list[str] = []
    seen: set[str] = set()
    current_dir = str(Path(entry_dir))
    if current_dir == ".":
        current_dir = ""

    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target or target.startswith("#"):
            continue
        target = target.split("#")[0]
        if not target or not target.endswith(".md"):
            continue
        # 规范化路径
        resolved = str((Path(current_dir) / target).resolve())
        if resolved in all_paths:
            if resolved not in seen:
                seen.add(resolved)
                out.append(resolved)
    return out


def build_graph(max_nodes: int = 200) -> dict:
    """构建图谱数据。"""
    categories, _indexed = parse_index(KNOWLEDGE_DIR)
    if not categories:
        return {"nodes": [], "edges": [], "bodies": {}, "types": [], "palette": _TYPE_PALETTE}

    # 构建 path → entry 映射
    all_paths: set[str] = set()
    entries: dict[str, dict] = {}
    for cat, cat_entries in categories.items():
        for e in cat_entries:
            p = e["path"]
            all_paths.add(p)
            entries[p] = e

    # 限制数量
    if len(entries) > max_nodes:
        entries = dict(list(entries.items())[:max_nodes])

    # 构建节点
    nodes: list[dict] = []
    bodies: dict[str, str] = {}
    path_to_id: dict[str, str] = {}
    node_id = 0

    for path, entry in entries.items():
        nid = f"n{node_id}"
        path_to_id[path] = nid
        node_id += 1

        file_path = KNOWLEDGE_DIR / path
        fm = _read_frontmatter(file_path) if file_path.exists() else {}
        body = ""
        try:
            body = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            # 去除 frontmatter
            m = re.match(r"^---\s*\n.*?\n---\n", body, re.DOTALL)
            if m:
                body = body[m.end():].strip()
        except Exception:
            pass

        entry_type = fm.get("type") or entry.get("type") or "Article"
        color = _TYPE_PALETTE.get(entry_type, _DEFAULT_COLOR)

        nodes.append({
            "data": {
                "id": nid,
                "label": entry["title"],
                "type": entry_type,
                "description": fm.get("description") or entry.get("description", ""),
                "resource": fm.get("resource") or entry.get("url", ""),
                "tags": _parse_tags(fm.get("tags", "")),
                "color": color,
                "size": 26 + min(64, len(body) // 300),
                "path": path,
            },
        })
        bodies[nid] = body

    # 构建边
    edges: list[dict] = []
    seen_edges: set[tuple[str, str]] = set()
    for path, entry in entries.items():
        file_path = KNOWLEDGE_DIR / path
        if not file_path.exists():
            continue
        try:
            body_text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        links = _extract_links(body_text, str(Path(path).parent), all_paths)
        for target in links:
            if target == path:
                continue
            src_id = path_to_id.get(path)
            tgt_id = path_to_id.get(target)
            if not src_id or not tgt_id:
                continue
            key = (src_id, tgt_id)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "data": {
                    "id": f"{src_id}__{tgt_id}",
                    "source": src_id,
                    "target": tgt_id,
                },
            })

    types = sorted({n["data"]["type"] for n in nodes})
    return {
        "nodes": nodes,
        "edges": edges,
        "bodies": bodies,
        "types": types,
        "palette": _TYPE_PALETTE,
    }


def _parse_tags(tags_val) -> list[str]:
    """解析 tags 字段（支持字符串和列表）。"""
    if isinstance(tags_val, list):
        return [str(t) for t in tags_val]
    if isinstance(tags_val, str):
        s = tags_val.strip().strip("[]")
        if not s:
            return []
        return [t.strip().strip("\"'") for t in s.split(",") if t.strip()]
    return []


# ── HTML/CSS/JS 模板 ─────────────────────────────────────────────────────

_CSS = r"""
* { box-sizing: border-box; }
body {
  margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  font-size: 14px; color: #0f172a; background: #f8fafc;
  display: flex; flex-direction: column; height: 100vh;
}
header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; background: #fff; border-bottom: 1px solid #e2e8f0; flex-shrink: 0;
}
.title strong { font-size: 16px; margin-right: 8px; }
.muted { color: #64748b; font-size: 12px; }
.controls { display: flex; gap: 8px; align-items: center; }
.controls input, .controls select, .controls button {
  font-size: 13px; padding: 5px 10px; border: 1px solid #cbd5e1;
  border-radius: 4px; background: #fff;
}
.controls input { width: 200px; }
.controls button { cursor: pointer; background: #f1f5f9; }
.controls button:hover { background: #e2e8f0; }

main { display: flex; flex: 1; min-height: 0; }
#graph { flex: 1 1 60%; background: #fff; border-right: 1px solid #e2e8f0; min-width: 0; position: relative; }
#detail { flex: 0 0 40%; overflow-y: auto; padding: 20px 24px; background: #fff; }
#detail-empty { text-align: center; margin-top: 60px; }

.detail-header { margin-bottom: 14px; }
.detail-header h1 { font-size: 18px; margin: 6px 0 4px; font-weight: 600; }
.type-chip {
  display: inline-block; padding: 2px 10px; border-radius: 10px;
  font-size: 11px; font-weight: 600; color: #fff; text-transform: uppercase; letter-spacing: 0.5px;
}
dl.fm {
  display: grid; grid-template-columns: 80px 1fr; row-gap: 4px; column-gap: 12px;
  margin: 8px 0 14px; font-size: 13px;
}
dl.fm dt { color: #64748b; font-weight: 500; }
dl.fm dd { margin: 0; word-break: break-all; }
dl.fm a { color: #2563eb; }

.tag {
  display: inline-block; padding: 1px 8px; margin: 0 4px 4px 0;
  border-radius: 4px; background: #f1f5f9; color: #475569; font-size: 11px;
}
.legend { font-size: 12px; color: #64748b; margin-bottom: 10px; }
.legend-item { display: inline-flex; align-items: center; margin-right: 14px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }

hr { border: none; border-top: 1px solid #e2e8f0; margin: 14px 0; }

#detail-body { font-size: 13px; line-height: 1.6; }
#detail-body h1 { font-size: 16px; margin: 18px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #e2e8f0; }
#detail-body h2 { font-size: 14px; margin: 14px 0 6px; }
#detail-body h3 { font-size: 13px; margin: 12px 0 4px; }
#detail-body p { margin: 6px 0; }
#detail-body code { background: #f1f5f9; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
#detail-body pre { background: #0f172a; color: #e2e8f0; padding: 10px 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
#detail-body pre code { background: transparent; color: inherit; padding: 0; }
#detail-body ul, #detail-body ol { padding-left: 20px; margin: 6px 0; }
#detail-body table { border-collapse: collapse; margin: 8px 0; }
#detail-body th, #detail-body td { border: 1px solid #e2e8f0; padding: 4px 8px; font-size: 12px; }
#detail-body blockquote { border-left: 3px solid #e2e8f0; margin: 8px 0; padding: 2px 12px; color: #64748b; }
#detail-body img { max-width: 100%; }
#detail-body a.internal { color: #2563eb; cursor: pointer; }
#detail-body a.external { color: #2563eb; }

#detail-backlinks { margin-top: 18px; }
#detail-backlinks h2 { font-size: 13px; color: #64748b; margin-bottom: 8px; }
#detail-backlinks ul { padding-left: 18px; }
#detail-backlinks li { margin: 3px 0; }
#detail-backlinks a { color: #2563eb; cursor: pointer; }
"""

_JS = r"""
const bundle = window.BUNDLE;
document.title = "知识图谱 — Knowledge Graph";

// Type filter
const typeSelect = document.getElementById("filter-type");
bundle.types.forEach(t => {
  const o = document.createElement("option"); o.value = t; o.textContent = t;
  typeSelect.appendChild(o);
});

// Legend
const legend = document.getElementById("legend");
bundle.types.forEach(t => {
  const c = bundle.palette[t] || "#94a3b8";
  legend.innerHTML += `<span class="legend-item"><span class="legend-dot" style="background:${c}"></span>${t}</span>`;
});

// Backlinks index
const backlinks = {};
bundle.edges.forEach(e => {
  const {source, target} = e.data;
  (backlinks[target] ||= []).push(source);
});

// Node index
const nodeIndex = {};
bundle.nodes.forEach(n => nodeIndex[n.data.id] = n.data);

const cy = cytoscape({
  container: document.getElementById("graph"),
  elements: [...bundle.nodes, ...bundle.edges],
  style: [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        "label": "data(label)",
        "color": "#0f172a",
        "font-size": 10,
        "text-valign": "bottom",
        "text-margin-y": 4,
        "text-wrap": "wrap",
        "text-max-width": 110,
        "width": "data(size)",
        "height": "data(size)",
        "border-width": 1,
        "border-color": "#0f172a",
      },
    },
    {
      selector: "node:selected",
      style: { "border-width": 3, "border-color": "#f59e0b" },
    },
    {
      selector: "edge",
      style: {
        "width": 1.5, "line-color": "#cbd5e1",
        "target-arrow-color": "#cbd5e1", "target-arrow-shape": "triangle",
        "curve-style": "bezier", "arrow-scale": 0.9,
      },
    },
    {
      selector: ".dim",
      style: { "opacity": 0.12 },
    },
  ],
  layout: { name: "cose", animate: false, padding: 30 },
  wheelSensitivity: 0.2,
});

cy.on("tap", "node", evt => showDetail(evt.target.id()));
cy.on("tap", evt => { if (evt.target === cy) clearSelection(); });

document.getElementById("layout").addEventListener("change", e => {
  cy.layout({ name: e.target.value, animate: false, padding: 30 }).run();
});
document.getElementById("reset").addEventListener("click", () => {
  cy.fit(null, 30); clearSelection();
});

// Search
document.getElementById("search").addEventListener("input", e => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) { cy.elements().removeClass("dim"); return; }
  cy.nodes().forEach(n => {
    const d = n.data();
    const hay = (d.label||"").toLowerCase() + " " + d.id + " " + (d.tags||[]).join(" ").toLowerCase();
    n.toggleClass("dim", !hay.includes(q));
  });
  cy.edges().forEach(edge => {
    edge.toggleClass("dim", edge.source().hasClass("dim") || edge.target().hasClass("dim"));
  });
});

// Type filter
document.getElementById("filter-type").addEventListener("change", e => {
  const t = e.target.value;
  if (!t) { cy.elements().removeClass("dim"); return; }
  cy.nodes().forEach(n => n.toggleClass("dim", n.data("type") !== t));
  cy.edges().forEach(edge => {
    edge.toggleClass("dim", edge.source().hasClass("dim") || edge.target().hasClass("dim"));
  });
});

function clearSelection() {
  cy.elements().unselect();
  document.getElementById("detail-empty").hidden = false;
  document.getElementById("detail-content").hidden = true;
}

function showDetail(nid) {
  const data = nodeIndex[nid];
  if (!data) return;
  cy.elements().unselect();
  const node = cy.getElementById(nid);
  if (node) node.select();

  document.getElementById("detail-empty").hidden = true;
  document.getElementById("detail-content").hidden = false;

  const chip = document.getElementById("detail-type");
  chip.textContent = data.type;
  chip.style.background = data.color;

  document.getElementById("detail-title").textContent = data.label;
  document.getElementById("detail-description").textContent = data.description || "—";

  const resEl = document.getElementById("detail-resource");
  resEl.innerHTML = "";
  if (data.resource) {
    const a = document.createElement("a"); a.href = data.resource;
    a.textContent = data.resource; a.target = "_blank"; a.rel = "noopener";
    resEl.appendChild(a);
  } else { resEl.textContent = "—"; }

  const tagsEl = document.getElementById("detail-tags");
  tagsEl.innerHTML = "";
  if (data.tags && data.tags.length) {
    data.tags.forEach(t => {
      const s = document.createElement("span"); s.className = "tag"; s.textContent = t;
      tagsEl.appendChild(s);
    });
  } else { tagsEl.textContent = "—"; }

  const body = bundle.bodies[nid] || "";
  document.getElementById("detail-body").innerHTML = marked.parse(body, {breaks: false, gfm: true});

  const bl = backlinks[nid] || [];
  const blSec = document.getElementById("detail-backlinks");
  const blList = document.getElementById("backlinks-list");
  blList.innerHTML = "";
  if (bl.length) {
    blSec.hidden = false;
    bl.forEach(src => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.textContent = nodeIndex[src]?.label || src;
      a.addEventListener("click", () => showDetail(src));
      li.appendChild(a);
      blList.appendChild(li);
    });
  } else { blSec.hidden = true; }

  cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.0) }, { duration: 200 });
}

// Auto-show first node
if (bundle.nodes.length) showDetail(bundle.nodes[0].data.id);
"""

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>知识图谱 — Knowledge Graph</title>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="title"><strong>知识图谱</strong><span class="muted">Knowledge Graph</span></div>
  <div class="controls">
    <input id="search" type="search" placeholder="搜索标题 / 标签">
    <select id="filter-type"><option value="">全部类型</option></select>
    <select id="layout">
      <option value="cose">力导向</option>
      <option value="concentric">同心圆</option>
      <option value="breadthfirst">层级</option>
      <option value="circle">环形</option>
      <option value="grid">网格</option>
    </select>
    <button id="reset">重置视图</button>
  </div>
</header>
<main>
  <section id="graph">
    <div class="legend" id="legend" style="position:absolute;top:10px;left:14px;z-index:10;"></div>
    <div id="stats" style="position:absolute;bottom:10px;right:14px;font-size:11px;color:#94a3b8;z-index:10;">
      节点 __NODES__ · 边 __EDGES__
    </div>
  </section>
  <section id="detail">
    <div id="detail-empty" class="muted">点击节点查看详情</div>
    <article id="detail-content" hidden>
      <header class="detail-header">
        <span class="type-chip" id="detail-type"></span>
        <h1 id="detail-title"></h1>
      </header>
      <dl class="fm">
        <dt>描述</dt><dd id="detail-description"></dd>
        <dt>来源</dt><dd id="detail-resource"></dd>
        <dt>标签</dt><dd id="detail-tags"></dd>
      </dl>
      <hr>
      <div id="detail-body"></div>
      <section id="detail-backlinks" hidden>
        <h2>被引用</h2>
        <ul id="backlinks-list"></ul>
      </section>
    </article>
  </section>
</main>
<script>window.BUNDLE = __DATA__;</script>
<script>__JS__</script>
</body>
</html>"""


def generate_html(graph: dict, output_path: Path) -> None:
    """生成自包含 HTML。"""
    html = (
        _HTML
        .replace("__CSS__", _CSS)
        .replace("__JS__", _JS)
        .replace("__DATA__", json.dumps(graph, ensure_ascii=False))
        .replace("__NODES__", str(len(graph["nodes"])))
        .replace("__EDGES__", str(len(graph["edges"])))
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


# ── CLI ───────────────────────────────────────────────────────────────────

def cmd_visualize(output: str = "", max_nodes: int = 200) -> dict:
    if not KNOWLEDGE_DIR.exists():
        return {"success": False, "error": f"{KNOWLEDGE_DIR} 不存在"}

    output_path = Path(output) if output else DEFAULT_OUTPUT
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    graph = build_graph(max_nodes=max_nodes)
    generate_html(graph, output_path)

    return {
        "success": True,
        "output": str(output_path),
        "nodes": len(graph["nodes"]),
        "edges": len(graph["edges"]),
    }


def main():
    parser = argparse.ArgumentParser(description="知识图谱可视化")
    parser.add_argument("--output", "-o", default="", help="输出路径")
    parser.add_argument("--max-nodes", type=int, default=200)
    args = parser.parse_args()

    result = cmd_visualize(output=args.output, max_nodes=args.max_nodes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
