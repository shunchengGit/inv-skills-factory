#!/usr/bin/env python3
"""知识图谱可视化：生成自包含 HTML，Cytoscape.js 力导向图。

用法:
  uv run km_visualize.py
  uv run km_visualize.py -o ~/Desktop/graph.html
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
_TYPE_PALETTE = {
    "Article": "#3b82f6", "Analysis": "#8b5cf6", "Synthesis": "#ec4899",
    "Reference": "#10b981", "Note": "#94a3b8",
}
_DEFAULT_COLOR = "#94a3b8"
_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)\)")


def _get_knowledge_dir() -> Path:
    env = os.environ.get("INV_KNOWLEDGE_ROOT", "").strip()
    return Path(env).expanduser() if env else _DEFAULT_KNOWLEDGE_DIR


KNOWLEDGE_DIR = _get_knowledge_dir()
DEFAULT_OUTPUT = KNOWLEDGE_DIR / "knowledge-graph.html"


def _parse_tags(tags_val) -> list[str]:
    if isinstance(tags_val, list):
        return [str(t) for t in tags_val]
    if isinstance(tags_val, str):
        s = tags_val.strip().strip("[]")
        return [t.strip().strip("\"'") for t in s.split(",") if t.strip()] if s else []
    return []


def _extract_links(body: str, entry_path: str, all_paths: set[str]) -> list[str]:
    out, seen = [], set()
    entry_dir = str(Path(entry_path).parent)
    if entry_dir == ".":
        entry_dir = ""
    for m in _LINK_RE.finditer(body):
        target = m.group(1)
        if "://" in target or target.startswith("#"):
            continue
        candidate = target if "/" in target else str(Path(entry_dir) / target) if entry_dir else target
        if candidate in all_paths and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def build_graph(max_nodes: int = 200) -> dict:
    entries_list, _indexed = parse_index(KNOWLEDGE_DIR)
    if not entries_list:
        return {"nodes": [], "edges": [], "types": [], "palette": _TYPE_PALETTE}

    all_paths = {e["path"] for e in entries_list}
    entries = {e["path"]: e for e in entries_list}
    if len(entries) > max_nodes:
        entries = dict(list(entries.items())[:max_nodes])

    nodes, bodies, path_to_id, node_id = [], {}, {}, 0
    for path, entry in entries.items():
        nid = f"n{node_id}"
        path_to_id[path] = nid
        node_id += 1

        file_path = KNOWLEDGE_DIR / path
        fm = _read_frontmatter(file_path) if file_path.exists() else {}
        body = ""
        try:
            body = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
            m = re.match(r"^---\s*\n.*?\n---\n", body, re.DOTALL)
            if m:
                body = body[m.end():].strip()
        except Exception:
            pass

        entry_type = fm.get("type") or entry.get("type") or "Article"
        color = _TYPE_PALETTE.get(entry_type, _DEFAULT_COLOR)
        source_type = fm.get("source_type") or ""
        icon = {"url": "", "pdf": "📄 ", "note": "📝 "}.get(source_type, "")
        label = f"{icon}{entry['title']}"

        nodes.append({"data": {
            "id": nid, "label": label, "type": entry_type, "source_type": source_type,
            "description": fm.get("description") or entry.get("description", ""),
            "resource": fm.get("resource") or entry.get("resource", ""),
            "tags": _parse_tags(fm.get("tags", "")), "color": color,
            "size": 26 + min(64, len(body) // 300), "path": path,
        }})
        bodies[nid] = body

    edges, seen_edges = [], set()
    for path in entries:
        file_path = KNOWLEDGE_DIR / path
        if not file_path.exists():
            continue
        try:
            body_text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for target in _extract_links(body_text, path, all_paths):
            if target == path:
                continue
            src_id, tgt_id = path_to_id.get(path), path_to_id.get(target)
            if not src_id or not tgt_id:
                continue
            key = (src_id, tgt_id)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({"data": {"id": f"{src_id}__{tgt_id}", "source": src_id, "target": tgt_id}})

    # 连接数统计
    conn_count = {}
    for e in edges:
        conn_count[e["data"]["source"]] = conn_count.get(e["data"]["source"], 0) + 1
        conn_count[e["data"]["target"]] = conn_count.get(e["data"]["target"], 0) + 1
    for n in nodes:
        c = conn_count.get(n["data"]["id"], 0)
        n["data"]["connections"] = c
        n["data"]["size"] = (20 if c == 0 else 32 if c >= 3 else 26) + min(40, n["data"]["size"] - 26)

    orphans = sum(1 for n in nodes if conn_count.get(n["data"]["id"], 0) == 0)
    return {
        "nodes": nodes, "edges": edges, "bodies": bodies,
        "types": sorted({n["data"]["type"] for n in nodes}),
        "palette": _TYPE_PALETTE,
        "stats": {"total_nodes": len(nodes), "total_edges": len(edges), "orphans": orphans},
    }


# ── HTML 模板（参考 knowledge-catalog 的 viz.html / viz.js） ──

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>知识图谱 — __NODES__ 节点</title>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f8fafc;--surface:#fff;--border:#e2e8f0;--text:#0f172a;--muted:#64748b;--accent:#3b82f6;--hover:#f1f5f9;--radius:8px}
body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;color:var(--text);background:var(--bg);display:flex;flex-direction:column;height:100vh}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:8px 16px;background:var(--surface);border-bottom:1px solid var(--border);flex-shrink:0}
header strong{font-size:15px}
header .muted{font-size:12px;color:var(--muted)}
.controls{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.controls input{width:180px;font-size:13px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;outline:none}
.controls input:focus{border-color:var(--accent)}
.controls button,.controls select{font-size:12px;padding:5px 10px;border:1px solid var(--border);border-radius:6px;background:var(--surface);cursor:pointer}
.controls button:hover,.controls select:hover{background:var(--hover)}
.chip-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding-top:4px}
.chip{font-size:11px;padding:3px 10px;border-radius:12px;border:1.5px solid var(--border);cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:5px}
.chip::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--c,#94a3b8)}
.chip.active{color:#fff;background:var(--c,#3b82f6);border-color:var(--c,#3b82f6)}
.chip.active::before{background:#fff}
main{display:flex;flex:1;min-height:0}
#graph{flex:1 1 55%;min-width:0;background:var(--surface);border-right:1px solid var(--border);position:relative}
#detail{flex:0 0 45%;overflow-y:auto;padding:20px 24px;background:var(--surface)}
.type-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:600;color:#fff;text-transform:uppercase;letter-spacing:.5px}
h1{font-size:18px;margin:6px 0 4px;font-weight:600;line-height:1.3}
dl.meta{display:grid;grid-template-columns:70px 1fr;gap:6px 12px;margin:10px 0 16px;font-size:13px}
dl.meta dt{color:var(--muted);font-weight:500}
dl.meta dd{word-break:break-all}
dl.meta a{color:var(--accent)}
.tag{display:inline-block;padding:1px 8px;margin:0 4px 4px 0;border-radius:4px;background:var(--hover);color:#475569;font-size:11px}
hr{border:none;border-top:1px solid var(--border);margin:16px 0}
#detail-body{font-size:13px;line-height:1.7}
#detail-body p{margin:8px 0}
#detail-body h1{font-size:17px;margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
#detail-body h2{font-size:15px;margin:16px 0 8px}
#detail-body h3{font-size:13px;margin:12px 0 6px}
#detail-body ul,#detail-body ol{padding-left:22px;margin:8px 0}
#detail-body li{margin:3px 0}
#detail-body blockquote{border-left:3px solid var(--border);margin:10px 0;padding:4px 14px;color:var(--muted)}
#detail-body a{color:var(--accent)}
#detail-body pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:var(--radius);overflow-x:auto;font-size:12px}
#detail-body code{background:var(--hover);padding:1px 5px;border-radius:3px;font-size:12px;font-family:ui-monospace,monospace}
#detail-backlinks{margin-top:20px}
#detail-backlinks h2{font-size:13px;color:var(--muted);margin-bottom:8px}
#detail-backlinks ul{padding-left:18px}
#detail-backlinks a{color:var(--accent);cursor:pointer}
.stats-bar{position:absolute;bottom:10px;left:14px;right:14px;z-index:10;display:flex;gap:16px;font-size:11px;color:var(--muted);pointer-events:none}
.stats-bar span{display:inline-flex;align-items:center;gap:4px}
.stats-dot{width:6px;height:6px;border-radius:50%}
.legend{position:absolute;top:10px;left:14px;z-index:10;display:flex;gap:12px;font-size:11px;color:var(--muted);flex-wrap:wrap}
.legend-item{display:inline-flex;align-items:center;gap:4px}
</style>
</head>
<body>
<header>
  <div><strong>知识图谱</strong> <span class="muted">__NODES__ 节点 · __EDGES__ 关联 · __ORPHANS__ 孤立</span></div>
  <div class="controls">
    <input id="search" type="search" placeholder="搜索...">
    <select id="layout">
      <option value="cose">力导向</option><option value="concentric">同心圆</option>
      <option value="breadthfirst">层级</option><option value="circle">环形</option><option value="grid">网格</option>
    </select>
    <button id="reset">↺</button>
  </div>
  <div class="chip-row" id="type-chips"><span class="chip active" data-all>全部</span></div>
</header>

<main>
  <section id="graph">
    <div class="legend" id="legend"></div>
    <div class="stats-bar"><span id="filter-count"></span></div>
  </section>
  <section id="detail">
    <div id="detail-empty" class="muted">点击节点查看详情</div>
    <article id="detail-content" hidden>
      <header><span class="type-badge" id="detail-type"></span><h1 id="detail-title"></h1></header>
      <dl class="meta">
        <dt>描述</dt><dd id="detail-description"></dd>
        <dt>来源</dt><dd id="detail-resource"></dd>
        <dt>标签</dt><dd id="detail-tags"></dd>
      </dl>
      <hr>
      <div id="detail-body"></div>
      <section id="detail-backlinks" hidden><h2>被引用</h2><ul id="backlinks-list"></ul></section>
    </article>
  </section>
</main>

<script>
window.BUNDLE = __DATA__;
</script>
<script>
(function(){
const B=window.BUNDLE;
document.title='知识图谱 — '+B.nodes.length+' 节点';

// Type chips
const p=B.palette||{};
B.types.forEach(t=>{
  const c=p[t]||'#94a3b8',ch=document.createElement('span');
  ch.className='chip';ch.textContent=t;ch.style.setProperty('--c',c);
  ch.addEventListener('click',()=>{
    const active=ch.classList.toggle('active');
    B.types.forEach(t2=>document.querySelectorAll('#type-chips .chip:not([data-all])')
      .forEach(c2=>{if(c2!==ch)c2.classList.remove('active')}));
    document.querySelector('#type-chips [data-all]').classList.toggle('active',!active);
    cy.nodes().forEach(n=>n.toggleClass('dim',active&&n.data('type')!==t));
    cy.edges().forEach(e=>e.toggleClass('dim',e.source().hasClass('dim')||e.target().hasClass('dim')));
  });
  document.getElementById('type-chips').appendChild(ch);
});
document.querySelector('#type-chips [data-all]').addEventListener('click',()=>{
  document.querySelectorAll('#type-chips .chip').forEach(c=>c.classList.remove('active'));
  document.querySelector('#type-chips [data-all]').classList.add('active');
  cy.elements().removeClass('dim');
});

// Legend
const legend=document.getElementById('legend');
B.types.forEach(t=>{
  const c=p[t]||'#94a3b8';
  legend.innerHTML+='<span class="legend-item"><span class="stats-dot" style="background:'+c+'"></span>'+t+'</span>';
});

// Indices
const nodeIdx={};B.nodes.forEach(n=>nodeIdx[n.data.id]=n.data);
const backlinks={};B.edges.forEach(e=>{(backlinks[e.data.target]||=[]).push(e.data.source)});

// Cytoscape
const cy=cytoscape({
  container:document.getElementById('graph'),
  elements:[...B.nodes,...B.edges],
  style:[
    {selector:'node',style:{
      'background-color':'data(color)','label':'data(label)','color':'#0f172a',
      'font-size':9.5,'text-valign':'bottom','text-margin-y':3,'text-wrap':'wrap','text-max-width':100,
      'width':'data(size)','height':'data(size)','border-width':1,'border-color':'data(color)',
      opacity:.92,'transition-property':'opacity','transition-duration':150
    }},
    {selector:'node:selected',style:{'border-width':3,'border-color':'#f59e0b'}},
    {selector:'edge',style:{width:1.5,'line-color':'#cbd5e1','target-arrow-color':'#cbd5e1','target-arrow-shape':'triangle','curve-style':'bezier','arrow-scale':.8}},
    {selector:'.dim',style:{opacity:.08}},
    {selector:'.hidden',style:{display:'none'}}
  ],
  layout:{name:'cose',animate:false,padding:30},
  wheelSensitivity:.2
});

cy.on('tap','node',evt=>showDetail(evt.target.id()));
cy.on('tap',evt=>{if(evt.target===cy)clearSelection()});

// Search
document.getElementById('search').addEventListener('input',e=>{
  const q=e.target.value.trim().toLowerCase();
  if(!q){cy.elements().removeClass('dim');return}
  cy.nodes().forEach(n=>{
    const d=n.data();
    const hay=(d.label||'').toLowerCase()+' '+d.id+' '+(d.tags||[]).join(' ').toLowerCase();
    n.toggleClass('dim',!hay.includes(q));
  });
  cy.edges().forEach(e=>e.toggleClass('dim',e.source().hasClass('dim')||e.target().hasClass('dim')));
});

// Layout
document.getElementById('layout').addEventListener('change',e=>{
  const name=e.target.value,opts={name,animate:false,padding:30};
  if(name==='grid')opts.rows=Math.ceil(Math.sqrt(cy.nodes(':visible').length||1));
  cy.layout(opts).run();
});
document.getElementById('reset').addEventListener('click',()=>{cy.fit(null,30);clearSelection()});

// Detail panel
function clearSelection(){
  cy.elements().unselect();
  document.getElementById('detail-empty').hidden=false;
  document.getElementById('detail-content').hidden=true;
}

function showDetail(nid){
  const d=nodeIdx[nid];if(!d)return;
  cy.elements().unselect();
  const n=cy.getElementById(nid);if(n)n.select();
  document.getElementById('detail-empty').hidden=true;
  const content=document.getElementById('detail-content');content.hidden=false;

  const badge=document.getElementById('detail-type');
  badge.textContent=d.data.type;badge.style.background=d.data.color;

  document.getElementById('detail-title').textContent=d.data.label;
  document.getElementById('detail-description').textContent=d.data.description||'—';

  const resEl=document.getElementById('detail-resource');resEl.innerHTML='';
  const resource=d.data.resource||'';
  if(/^https?:\/\//.test(resource)){
    const a=document.createElement('a');a.href=resource;a.target='_blank';a.rel='noopener';
    a.textContent=resource.length>80?resource.slice(0,77)+'...':resource;resEl.appendChild(a);
  }else{resEl.textContent=resource||'—';}

  const tagsEl=document.getElementById('detail-tags');
  tagsEl.innerHTML=d.data.tags?.length?d.data.tags.map(t=>'<span class="tag">'+t+'</span>').join(''):'—';

  // Detail body: render markdown from bundle bodies
  const body=B.bodies[nid]||'';
  const bodyEl=document.getElementById('detail-body');
  bodyEl.innerHTML=body?renderMD(body):'<p class="muted">无正文内容</p>';

  // Backlinks
  const bl=backlinks[nid]||[];
  const blEl=document.getElementById('backlinks-list');blEl.innerHTML='';
  const blSec=document.getElementById('detail-backlinks');
  if(bl.length){blSec.hidden=false;bl.forEach(s=>{
    const li=document.createElement('li'),a=document.createElement('a');
    a.textContent=nodeIdx[s]?.data?.label||s;a.addEventListener('click',()=>showDetail(s));
    li.appendChild(a);blEl.appendChild(li);
  })}else{blSec.hidden=true;}

  cy.animate({center:{eles:n},zoom:Math.max(cy.zoom(),1.0)},{duration:200});
}

// Simple markdown renderer
function renderMD(t){
  if(!t)return'';
  let h=t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  h=h.replace(/```(\w*)\n([\s\S]*?)```/g,(_,lang,code)=>'<pre><code>'+code.trim()+'</code></pre>');
  h=h.replace(/`([^`]+)`/g,'<code>$1</code>');
  h=h.replace(/^#### (.+)$/gm,'<h4>$1</h4>');
  h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  h=h.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  h=h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  h=h.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
  h=h.replace(/\*(.+?)\*/g,'<em>$1</em>');
  h=h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,'<img alt="$1" src="$2">');
  h=h.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  h=h.replace(/^---$/gm,'<hr>');
  h=h.replace(/^[\*\-] (.+)$/gm,'<li>$1</li>');
  h=h.replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>');
  h=h.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');
  h=h.replace(/\n\n+/g,'</p><p>');
  h='<p>'+h+'</p>';
  return h.replace(/<p>\s*<\/p>/g,'');
}

// Auto-init
const initial=B.nodes[0];
if(initial)showDetail(initial.data.id);
})();
</script>
</body>
</html>"""


def generate_html(graph: dict, output_path: Path) -> None:
    stats = graph.get("stats", {})
    html = (_TEMPLATE
        .replace("__DATA__", json.dumps(graph, ensure_ascii=False))
        .replace("__NODES__", str(len(graph["nodes"])))
        .replace("__EDGES__", str(len(graph["edges"])))
        .replace("__ORPHANS__", str(stats.get("orphans", 0))))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


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
