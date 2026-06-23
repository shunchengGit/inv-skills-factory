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
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))

sys.path.insert(0, str(Path(__file__).resolve().parent))
from knowledge import parse_index, _read_frontmatter, ENTRIES_DIR

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".inv-knowledge"


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()
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
_SOURCE_TYPE_ICONS = {
    "url": "🔗",
    "pdf": "📄",
    "note": "📝",
}
_DEFAULT_COLOR = "#94a3b8"


def _extract_links(body: str, entry_path: str, all_paths: set[str]) -> list[str]:
    """从正文提取指向知识库内其他条目的链接。"""
    out: list[str] = []
    seen: set[str] = set()
    entry_dir = str(Path(entry_path).parent)
    if entry_dir == ".":
        entry_dir = ""

    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target or target.startswith("#"):
            continue
        target = target.split("#")[0]
        if not target or not target.endswith(".md"):
            continue
        # 如果 link 已包含目录前缀（如 investing/xxx.md），直接使用
        # 否则相对于当前条目所在目录解析
        if "/" in target:
            candidate = target
        else:
            candidate = str(Path(entry_dir) / target) if entry_dir else target
        if candidate in all_paths and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def build_graph(max_nodes: int = 200) -> dict:
    """构建图谱数据。从 entries/ 扁平目录读取所有 OKF 条目。"""
    entries_list, _indexed = parse_index(KNOWLEDGE_DIR)
    if not entries_list:
        return {"nodes": [], "edges": [], "bodies": {}, "types": [], "palette": _TYPE_PALETTE}

    # 构建 path → entry 映射
    all_paths: set[str] = set()
    entries: dict[str, dict] = {}
    for e in entries_list:
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
        source_type = fm.get("source_type") or entry.get("source_type") or ""
        color = _TYPE_PALETTE.get(entry_type, _DEFAULT_COLOR)
        icon = _SOURCE_TYPE_ICONS.get(source_type, "")

        label = entry["title"]
        if icon:
            label = f"{icon} {label}"

        nodes.append({
            "data": {
                "id": nid,
                "label": label,
                "type": entry_type,
                "source_type": source_type,
                "description": fm.get("description") or entry.get("description", ""),
                "resource": fm.get("resource") or entry.get("resource", ""),
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
    for path in entries:
        file_path = KNOWLEDGE_DIR / path
        if not file_path.exists():
            continue
        try:
            body_text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        links = _extract_links(body_text, path, all_paths)
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

    # 统计每个节点的连接数
    conn_count: dict[str, int] = {}
    for e in edges:
        conn_count[e["data"]["source"]] = conn_count.get(e["data"]["source"], 0) + 1
        conn_count[e["data"]["target"]] = conn_count.get(e["data"]["target"], 0) + 1

    orphans = sum(1 for n in nodes if conn_count.get(n["data"]["id"], 0) == 0)

    # 更新节点大小：连接越多越大
    for n in nodes:
        c = conn_count.get(n["data"]["id"], 0)
        base = 20 if c == 0 else (32 if c >= 3 else 26)
        n["data"]["size"] = base + min(40, n["data"]["size"] - 26)
        n["data"]["connections"] = c

    types = sorted({n["data"]["type"] for n in nodes})
    return {
        "nodes": nodes,
        "edges": edges,
        "bodies": bodies,
        "types": types,
        "palette": _TYPE_PALETTE,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "orphans": orphans,
        },
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
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#f8fafc;--surface:#fff;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;
  --accent:#3b82f6;--hover:#f1f5f9;--radius:8px;
  --shadow-sm:0 1px 2px rgba(0,0,0,.05);
}
body{
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
  color:var(--text);background:var(--bg);display:flex;flex-direction:column;height:100vh;
}

/* ── Header ── */
header{
  display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding:8px 16px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0;
}
.brand{display:flex;align-items:baseline;gap:8px}
.brand strong{font-size:15px}
.brand .muted{font-size:12px;color:var(--muted)}
.controls{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.controls input{width:180px;font-size:13px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;outline:none;transition:border-color .15s}
.controls input:focus{border-color:var(--accent)}
.controls button,.controls select{
  font-size:12px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;
  background:var(--surface);cursor:pointer;transition:all .15s;
}
.controls button:hover,.controls select:hover{background:var(--hover)}
.controls button.active{background:var(--accent);color:#fff;border-color:var(--accent)}

/* Chips */
.chip-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.chip{
  font-size:11px;padding:3px 10px;border-radius:12px;border:1.5px solid var(--border);
  background:var(--surface);cursor:pointer;transition:all .15s;user-select:none;
  display:inline-flex;align-items:center;gap:5px;
}
.chip::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--chip-color,#94a3b8)}
.chip:hover{background:var(--hover)}
.chip.active{color:#fff;border-color:transparent;background:var(--chip-color,#3b82f6)}
.chip.active::before{background:#fff}
.chip[data-all]::before{display:none}

/* ── Main ── */
main{display:flex;flex:1;min-height:0}
#graph-panel{flex:1 1 55%;display:flex;flex-direction:column;min-width:0;position:relative;background:var(--surface);border-right:1px solid var(--border)}
#graph{flex:1;position:relative}
#table-view{flex:1;overflow-y:auto;display:none;padding:0}
#table-view.active{display:block}
#detail{flex:0 0 45%;overflow-y:auto;padding:20px 24px;background:var(--surface)}
#detail-content{display:block!important}
#detail-content[hidden]{display:none!important}

.view-toggle{position:absolute;top:8px;right:8px;z-index:20;display:flex;gap:4px}
.view-toggle button{
  font-size:11px;padding:3px 8px;border:1px solid var(--border);border-radius:4px;
  background:var(--surface);cursor:pointer;
}
.view-toggle button.active{background:var(--accent);color:#fff;border-color:var(--accent)}

.graph-hint{
  position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);z-index:5;
  text-align:center;color:var(--muted);font-size:14px;pointer-events:none;
}
.graph-hint b{color:var(--text)}

/* ── Table ── */
.entry-table{width:100%;border-collapse:collapse;font-size:13px}
.entry-table thead{position:sticky;top:0;z-index:1;background:var(--surface)}
.entry-table th{
  text-align:left;padding:8px 12px;border-bottom:2px solid var(--border);
  color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.5px;cursor:pointer
}
.entry-table td{padding:8px 12px;border-bottom:1px solid var(--border);vertical-align:top}
.entry-table tr{cursor:pointer;transition:background .1s}
.entry-table tr:hover{background:var(--hover)}
.entry-table td.title{font-weight:500}
.entry-table td.type{font-size:11px}
.entry-table td.desc{color:var(--muted);font-size:12px;max-width:300px}

/* ── Detail ── */
#detail-empty{text-align:center;margin-top:80px}
.detail-header{margin-bottom:14px}
.detail-header h1{font-size:18px;margin:6px 0 4px;font-weight:600;line-height:1.3}
.type-badge{
  display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:10px;
  font-size:11px;font-weight:600;color:#fff;text-transform:uppercase;letter-spacing:.5px;
}
dl.meta{display:grid;grid-template-columns:70px 1fr;gap:6px 12px;margin:10px 0 16px;font-size:13px}
dl.meta dt{color:var(--muted);font-weight:500}
dl.meta dd{word-break:break-all}
dl.meta a{color:var(--accent)}
.tag{display:inline-block;padding:1px 8px;margin:0 4px 4px 0;border-radius:4px;background:var(--hover);color:#475569;font-size:11px}
hr{border:none;border-top:1px solid var(--border);margin:16px 0}

#detail-body{font-size:13px;line-height:1.7}
#detail-body h1{font-size:17px;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
#detail-body h2{font-size:15px;margin:16px 0 8px}
#detail-body h3{font-size:13px;margin:12px 0 6px}
#detail-body p{margin:8px 0}
#detail-body code{background:var(--hover);padding:1px 5px;border-radius:3px;font-size:12px;font-family:ui-monospace,monospace}
#detail-body pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:var(--radius);overflow-x:auto;font-size:12px}
#detail-body pre code{background:transparent;color:inherit;padding:0}
#detail-body ul,#detail-body ol{padding-left:22px;margin:8px 0}
#detail-body li{margin:3px 0}
#detail-body table{border-collapse:collapse;margin:10px 0;font-size:12px}
#detail-body th,#detail-body td{border:1px solid var(--border);padding:5px 10px}
#detail-body blockquote{border-left:3px solid var(--border);margin:10px 0;padding:4px 14px;color:var(--muted)}
#detail-body img{max-width:100%;border-radius:var(--radius)}
#detail-body a{color:var(--accent)}

#detail-backlinks{margin-top:20px}
#detail-backlinks h2{font-size:13px;color:var(--muted);margin-bottom:8px}
#detail-backlinks ul{padding-left:18px}
#detail-backlinks li{margin:3px 0}
#detail-backlinks a{color:var(--accent);cursor:pointer}

/* Stats bar */
.stats-bar{
  position:absolute;bottom:10px;left:14px;right:14px;z-index:10;
  display:flex;gap:16px;font-size:11px;color:var(--muted);
  pointer-events:none;
}
.stats-bar span{display:inline-flex;align-items:center;gap:4px}
.stats-dot{width:6px;height:6px;border-radius:50%}
.legend{position:absolute;top:10px;left:14px;z-index:10;display:flex;gap:12px;font-size:11px;color:var(--muted);flex-wrap:wrap}
.legend-item{display:inline-flex;align-items:center;gap:4px}

/* Connectivity badge */
.badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:4px;font-weight:600}
.badge-warn{background:#fef3c7;color:#92400e}
.badge-ok{background:#d1fae5;color:#065f46}
"""

_JS = r"""
const B = window.BUNDLE;
const connected = B.edges.length > 0;
const HAS_CYTOSCAPE = typeof cytoscape !== "undefined";
document.title = `知识图谱 — ${B.nodes.length} 节点`;

console.log('HAS_CYTOSCAPE:', HAS_CYTOSCAPE, 'nodes:', B.nodes.length, 'edges:', B.edges.length);

if (!HAS_CYTOSCAPE) {
  document.getElementById("graph").innerHTML =
    '<div class="graph-hint"><b>⚠ Cytoscape.js 未加载</b><br><span style="font-size:12px">请切换到列表视图</span></div>';
  document.querySelector('[data-view="table"]').click();
}

// ── Indexes ──
const nodeIdx = {}; B.nodes.forEach(n => nodeIdx[n.data.id] = n.data);
const backlinks = {}; B.edges.forEach(e => {(backlinks[e.data.target]||=[]).push(e.data.source)});

// ── Type chips ──
const p = B.palette;
const types = B.types;
let activeType = null;

const chipRow = document.getElementById("type-chips");
// "全部" chip
chipRow.querySelector("[data-all]").addEventListener("click", ()=>{
  activeType = null;
  chipRow.querySelectorAll(".chip").forEach(c=>c.classList.remove("active"));
  chipRow.querySelector("[data-all]").classList.add("active");
  applyFilters();
});
types.forEach(t => {
  const ch = document.createElement("span");
  ch.className = "chip"; ch.textContent = t;
  ch.style.setProperty("--chip-color", p[t]||"#94a3b8");
  ch.addEventListener("click", () => {
    if (activeType === t) {
      activeType = null;
      chipRow.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chipRow.querySelector("[data-all]").classList.add("active");
    } else {
      activeType = t;
      chipRow.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      ch.classList.add("active");
    }
    applyFilters();
  });
  chipRow.appendChild(ch);
});

// ── Layout (自适应：无边→grid，有边→cose) ──
const layoutSelect = document.getElementById("layout");
if (!connected) layoutSelect.value = "grid";

// cytoscape 不可用时提供空壳对象
const cy = HAS_CYTOSCAPE ? cytoscape({
  container: document.getElementById("graph"),
  elements: [...B.nodes, ...B.edges],
  style: [
    { selector:"node", style:{
      "background-color":"data(color)","label":"data(label)","color":"#0f172a",
      "font-size":9.5,"text-valign":"bottom","text-margin-y":3,"text-wrap":"wrap","text-max-width":100,
      "width":"data(size)","height":"data(size)","border-width":1,"border-color":"data(color)",
      "opacity":.92,"transition-property":"opacity","transition-duration":150,
    }},
    { selector:"node:selected", style:{"border-width":3,"border-color":"#f59e0b"} },
    { selector:"edge", style:{"width":1.5,"line-color":"#cbd5e1","target-arrow-color":"#cbd5e1","target-arrow-shape":"triangle","curve-style":"bezier","arrow-scale":.8} },
    { selector:".dim", style:{"opacity":.08} },
    { selector:".hidden", style:{"display":"none"} },
  ],
  layout: { name: connected?"cose":"grid", animate:true, padding:30, ...(connected?{}:{rows:Math.ceil(Math.sqrt(B.nodes.length))}) },
  wheelSensitivity: .2,
});

cy.on("tap","node",evt=>showDetail(evt.target.id()));
cy.on("tap",evt=>{if(evt.target===cy)clearSelection()});
}) : { // cytoscape 降级
  on(){}, elements(){return{unselect(){}}}, getElementById(){},
  nodes(){return{filter:()=>({length:0})}}, fit(){}, animate(){}, layout(){run(){}}, batch(fn){fn()}, zoom(){return 1}
};

// ── Search ──
let searchQ = "";
document.getElementById("search").addEventListener("input",e=>{
  searchQ = e.target.value.trim().toLowerCase();
  applyFilters();
});

// ── Layout ──
if (HAS_CYTOSCAPE) {
document.getElementById("layout").addEventListener("change",e=>{
  const name = e.target.value;
  const opts = { name, animate:true, padding:30 };
  if (name==="grid") opts.rows = Math.ceil(Math.sqrt(cy.nodes(":visible").length||1));
  cy.layout(opts).run();
});

document.getElementById("reset").addEventListener("click",()=>{cy.fit(null,30);clearSelection()});
}

// ── View toggle ──
document.querySelectorAll(".view-toggle button").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".view-toggle button").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    const isGraph = btn.dataset.view === "graph";
    document.getElementById("graph").style.display = isGraph?"":"none";
    document.getElementById("table-view").classList.toggle("active",!isGraph);
    if (isGraph) { cy.resize(); cy.fit(null,30); }
  });
});

// ── Filters ──
function applyFilters(){
  if (!HAS_CYTOSCAPE) return;
  cy.batch(()=>{
    cy.nodes().forEach(n=>{
      const d = n.data();
      let visible = true;
      if (activeType && d.type !== activeType) visible = false;
      if (searchQ) {
        const hay = (d.label||"").toLowerCase()+" "+d.id+" "+(d.tags||[]).join(" ").toLowerCase();
        if (!hay.includes(searchQ)) visible = false;
      }
      n.toggleClass("dim",!visible).toggleClass("hidden", false);
    });
    cy.edges().forEach(e=>{
      e.toggleClass("dim",e.source().hasClass("dim")||e.target().hasClass("dim"));
    });
  });
  // 更新计数
  const v = cy.nodes(":visible").filter(n=>!n.hasClass("dim")).length;
  document.getElementById("filter-count").textContent = v===B.nodes.length?"":`${v}/${B.nodes.length}`;
}

// ── Detail ──
function clearSelection(){
  cy.elements().unselect();
  document.getElementById("detail-empty").style.display = "";
  document.getElementById("detail-content").style.display = "none";
}

function showDetail(nid){
  const d = nodeIdx[nid]; if(!d) return;
  cy.elements().unselect();
  const n = cy.getElementById(nid); if(n) n.select();

  document.getElementById("detail-empty").style.display = "none";
  const content = document.getElementById("detail-content");
  content.style.display = "";
  content.scrollTop = 0;

  const badge = document.getElementById("detail-type");
  badge.textContent = d.data.type; badge.style.background = d.data.color;

  document.getElementById("detail-title").textContent = d.data.label;
  document.getElementById("detail-description").textContent = d.data.description||"—";

  const resEl = document.getElementById("detail-resource");
  resEl.innerHTML = "";
  const resource = d.data.resource||"";
  const isUrl = /^https?:\/\//.test(resource);
  if (isUrl) {
    const a = document.createElement("a");
    a.href = resource; a.target = "_blank"; a.rel = "noopener";
    a.textContent = resource.length>80?resource.slice(0,77)+"...":resource;
    resEl.appendChild(a);
  } else { resEl.textContent = resource||"—"; }

  const tagsEl = document.getElementById("detail-tags");
  tagsEl.innerHTML = d.data.tags?.length
    ? d.data.tags.map(t=>`<span class="tag">${t}</span>`).join("") : "—";

  const bodyText = B.bodies[nid]||"";
  const bodyEl = document.getElementById("detail-body");
  bodyEl.innerHTML = renderMD(bodyText);

  const bl = backlinks[nid]||[];
  const blSec = document.getElementById("detail-backlinks");
  const blList = document.getElementById("backlinks-list");
  blList.innerHTML = "";
  if (bl.length) {
    blSec.hidden = false;
    bl.forEach(s=>{
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.textContent = nodeIdx[s]?.data?.label||s;
      a.addEventListener("click",()=>showDetail(s));
      li.appendChild(a);
      blList.appendChild(li);
    });
  } else { blSec.hidden = true; }

cy.animate({center:{eles:n},zoom:Math.max(cy.zoom(),1.0)},{duration:200});
}

// ── Table view ──
if (!connected) {
  document.getElementById("graph-hint").hidden = false;
}
// ── Legend ──
types.forEach(t=>{
  const c = p[t]||"#94a3b8";
  document.getElementById("legend").innerHTML += `<span class="legend-item"><span class="stats-dot" style="background:${c}"></span>${t}</span>`;
});

// ── Table ──
const tbody = document.getElementById("table-body");
B.nodes.forEach(n=>{
  const d = n.data;
  const tr = document.createElement("tr");
  tr.innerHTML = `<td class="title"><span class="type-badge" style="background:${d.color};font-size:10px;margin-right:6px">${d.type}</span>${d.label}</td><td class="desc">${d.description||""}</td>`;
  tr.addEventListener("click",()=>{
    document.querySelectorAll(".view-toggle button").forEach(b=>b.classList.remove("active"));
    document.querySelector('[data-view="graph"]').classList.add("active");
    document.getElementById("graph").style.display="";
    document.getElementById("table-view").classList.remove("active");
    showDetail(d.id);
  });
  tbody.appendChild(tr);
});

// ── 内置 Markdown 渲染（无 CDN 依赖） ──
function renderMD(text) {
  if (!text) return "";
  let html = text
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_,lang,code)=>
    `<pre><code class="lang-${lang}">${code.trim()}</code></pre>`);
  // 行内代码
  html = html.replace(/`([^`]+)`/g,"<code>$1</code>");
  // 标题
  html = html.replace(/^#### (.+)$/gm,"<h4>$1</h4>");
  html = html.replace(/^### (.+)$/gm,"<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm,"<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm,"<h1>$1</h1>");
  // 粗体/斜体
  html = html.replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g,"<em>$1</em>");
  // 图片
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,'<img alt="$1" src="$2">');
  // 链接
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  // 水平线
  html = html.replace(/^---$/gm,"<hr>");
  // 无序列表
  html = html.replace(/^[\*\-] (.+)$/gm,"<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g,"<ul>$1</ul>");
  // 有序列表
  html = html.replace(/^\d+\. (.+)$/gm,"<li>$1</li>");
  // 引用
  html = html.replace(/^&gt; (.+)$/gm,"<blockquote>$1</blockquote>");
  // 段落（连续的纯文本行）
  html = html.replace(/\n\n+/g,"</p><p>");
  html = "<p>" + html + "</p>";
  // 清理空段落
  html = html.replace(/<p>\s*<\/p>/g,"");
  html = html.replace(/<p>(<(?:h[1-4]|ul|ol|pre|blockquote|hr|table)[\s\S]*?<\/\1>)<\/p>/g,"$1");
  return html;
}

// Auto-init: cy.ready 确保 Cytoscape 初始化完成后再显示
if (B.nodes.length) {
  cy.ready(() => {
    cy.fit(null, 30);
    showDetail(B.nodes[0].data.id);
  });
}
"""

_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>知识图谱</title>
<script>__CYTOSCAPE_JS__</script>
<style>__CSS__</style>
</head>
<body>
<header>
  <div class="brand">
    <strong>🧠 知识图谱</strong>
    <span class="muted">__NODES__ 节点 · __EDGES__ 关联</span>
    <span class="badge __BADGE_CLASS__" id="conn-badge">__CONN_LABEL__</span>
  </div>
  <div class="controls">
    <input id="search" type="search" placeholder="搜索..."><span class="muted" id="filter-count" style="width:50px"></span>
    <select id="layout">
      <option value="cose">力导向</option><option value="concentric">同心圆</option>
      <option value="breadthfirst">层级</option><option value="circle">环形</option><option value="grid">网格</option>
    </select>
    <button id="reset">↺</button>
  </div>
  <div class="chip-row" id="type-chips" style="flex-basis:100%;padding-top:4px">
    <span class="chip active" data-all style="font-weight:500">全部</span>
  </div>
</header>
<main>
  <section id="graph-panel">
    <div class="view-toggle">
      <button data-view="graph" class="active">◉ 图谱</button>
      <button data-view="table">☰ 列表</button>
    </div>
    <div id="graph">
      <div class="graph-hint" id="graph-hint" hidden>
        <b>🔗 暂无关联</b><br><span style="font-size:12px">导入时为条目添加交叉引用，图谱将显示关联连线</span>
      </div>
      <div class="legend" id="legend"></div>
    </div>
    <div id="table-view"><table class="entry-table"><thead><tr><th>条目</th><th>描述</th></tr></thead><tbody id="table-body"></tbody></table></div>
  </section>
  <section id="detail">
    <div id="detail-empty" class="muted">◀ 点击节点或列表项查看详情</div>
    <article id="detail-content">
      <header class="detail-header">
        <span class="type-badge" id="detail-type"></span>
        <h1 id="detail-title"></h1>
      </header>
      <dl class="meta">
        <dt>描述</dt><dd id="detail-description"></dd>
        <dt>来源</dt><dd id="detail-resource"></dd>
        <dt>标签</dt><dd id="detail-tags"></dd>
      </dl>
      <hr>
      <div id="detail-body"></div>
      <section id="detail-backlinks" hidden>
        <h2>↩ 被引用</h2>
        <ul id="backlinks-list"></ul>
      </section>
    </article>
  </section>
</main>
<script>window.BUNDLE = __DATA__;</script>
<script>__JS__</script>
</body>
</html>"""



_cytoscape_js_cache = None


def _get_cytoscape_js():
    """获取 Cytoscape.js（优先本地缓存，再从 CDN 下载）。"""
    global _cytoscape_js_cache
    if _cytoscape_js_cache:
        return _cytoscape_js_cache

    cache_path = Path("/tmp/cytoscape-3.28.1.min.js")
    cdn_urls = [
        "https://cdn.bootcdn.net/ajax/libs/cytoscape/3.28.1/cytoscape.min.js",
        "https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js",
    ]

    if cache_path.exists():
        _cytoscape_js_cache = cache_path.read_text(encoding="utf-8")
        return _cytoscape_js_cache

    import urllib.request
    for url in cdn_urls:
        try:
            js = urllib.request.urlopen(url, timeout=15).read().decode("utf-8")
            cache_path.write_text(js, encoding="utf-8")
            _cytoscape_js_cache = js
            print(f"# Cytoscape.js 已下载并缓存 ({len(js)} bytes)", file=sys.stderr)
            return js
        except Exception:
            continue

    return "console.warn('Cytoscape.js 加载失败，图谱不可用');var cytoscape=null;"


def generate_html(graph: dict, output_path: Path) -> None:
    """生成自包含 HTML。"""
    node_count = len(graph["nodes"])
    edge_count = len(graph["edges"])
    connected = edge_count > 0

    stats = graph.get("stats", {})
    orphans = stats.get("orphans", 0)

    cytoscape_js = _get_cytoscape_js()

    html = (
        _HTML
        .replace("__CSS__", _CSS)
        .replace("__CYTOSCAPE_JS__", cytoscape_js)
        .replace("__JS__", _JS)
        .replace("__DATA__", json.dumps(graph, ensure_ascii=False))
        .replace("__NODES__", str(node_count))
        .replace("__EDGES__", str(edge_count))
        .replace("__ORPHANS__", str(orphans))
        .replace("__BADGE_CLASS__", "badge-ok" if orphans < max(1, node_count//3) else "badge-warn")
        .replace("__CONN_LABEL__", f"{edge_count} 关联, {orphans} 孤立" if orphans > 0 else "全关联")
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
