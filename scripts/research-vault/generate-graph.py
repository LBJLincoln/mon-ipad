#!/usr/bin/env python3
"""
Generate Obsidian-style graph JSON from research-vault backlinks.

Outputs:
  research-vault/graph.json — D3 force-directed graph data
  research-vault/graph.html — Standalone interactive graph viewer

The graph shows:
  - Topic nodes (large, colored by category)
  - Concept nodes (medium)
  - File nodes (small)
  - Edges between files and their topics/concepts
"""

import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
VAULT = ROOT / "research-vault"
BACKLINKS = VAULT / "backlinks.json"


def build_graph():
    data = json.loads(BACKLINKS.read_text())
    topics = data.get("topics", {})
    concepts = data.get("concepts", {})
    files = data.get("files", {})

    nodes = []
    edges = []
    node_ids = set()

    # Color palette for topics
    topic_colors = {
        "nba-prediction": "#4FC3F7",
        "evolution": "#81C784",
        "infrastructure": "#FFB74D",
        "feature-engineering": "#CE93D8",
        "calibration": "#F06292",
        "betting-strategy": "#FFD54F",
        "political-alpha": "#EF5350",
        "data-sources": "#4DB6AC",
        "karpathy-patterns": "#7986CB",
        "trading-floor": "#A1887F",
    }

    # Add topic nodes
    for tid, tdata in topics.items():
        nid = f"topic:{tid}"
        nodes.append({
            "id": nid,
            "label": tdata["name"],
            "type": "topic",
            "size": 24,
            "color": topic_colors.get(tid, "#90A4AE"),
        })
        node_ids.add(nid)

    # Add concept nodes
    for cname, cdata in concepts.items():
        nid = f"concept:{cname}"
        n_files = len(cdata.get("files", []))
        nodes.append({
            "id": nid,
            "label": cname,
            "type": "concept",
            "size": max(8, min(18, n_files // 5 + 8)),
            "color": "#B0BEC5",
            "file_count": n_files,
        })
        node_ids.add(nid)

    # Add file nodes (only files with topics or concepts)
    file_topics = defaultdict(set)
    file_concepts = defaultdict(set)

    for tid, tdata in topics.items():
        wiki_path = tdata.get("wiki_path", "")
        for fname, fdata in files.items():
            ftopics = fdata.get("topics", [])
            if tid in ftopics:
                file_topics[fname].add(tid)

    for cname, cdata in concepts.items():
        for fname in cdata.get("files", []):
            file_concepts[fname].add(cname)

    # Only include files that have at least 1 topic or concept link
    connected_files = set(file_topics.keys()) | set(file_concepts.keys())

    for fname in connected_files:
        fdata = files.get(fname, {})
        nid = f"file:{fname}"
        label = fdata.get("title", fname.split("/")[-1].replace(".md", ""))
        if len(label) > 40:
            label = label[:37] + "..."

        # Color by primary topic
        ftops = file_topics.get(fname, set())
        color = "#546E7A"
        if ftops:
            first_topic = list(ftops)[0]
            color = topic_colors.get(first_topic, "#546E7A")

        nodes.append({
            "id": nid,
            "label": label,
            "type": "file",
            "size": 4,
            "color": color,
            "path": fname,
        })
        node_ids.add(nid)

        # Edges: file -> topic
        for tid in ftops:
            tnid = f"topic:{tid}"
            if tnid in node_ids:
                edges.append({"source": nid, "target": tnid, "type": "topic"})

        # Edges: file -> concept
        for cname in file_concepts.get(fname, set()):
            cnid = f"concept:{cname}"
            if cnid in node_ids:
                edges.append({"source": nid, "target": cnid, "type": "concept"})

    graph = {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "topics": len(topics),
            "concepts": len(concepts),
            "files": len(connected_files),
            "edges": len(edges),
        },
    }
    return graph


def generate_html(graph):
    """Generate a standalone HTML graph viewer using D3.js."""
    stats = graph["stats"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Nomos42 Research Brain</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0f; color: #e0e0e0; font-family: 'JetBrains Mono', monospace; overflow: hidden; }}
  #info {{
    position: fixed; top: 12px; left: 12px; z-index: 10;
    background: rgba(10,10,15,0.9); border: 1px solid #333; border-radius: 6px;
    padding: 12px 16px; font-size: 11px; line-height: 1.6;
  }}
  #info h2 {{ color: #4FC3F7; font-size: 14px; margin-bottom: 6px; }}
  #info .stat {{ color: #888; }}
  #info .val {{ color: #81C784; }}
  #tooltip {{
    position: fixed; display: none; z-index: 20;
    background: rgba(20,20,30,0.95); border: 1px solid #555; border-radius: 4px;
    padding: 8px 12px; font-size: 11px; pointer-events: none; max-width: 300px;
  }}
  svg {{ width: 100vw; height: 100vh; }}
  .link {{ stroke-opacity: 0.15; }}
  .link-topic {{ stroke: #4FC3F7; }}
  .link-concept {{ stroke: #90A4AE; }}
</style>
</head>
<body>
<div id="info">
  <h2>NOMOS42 RESEARCH BRAIN</h2>
  <div><span class="stat">Topics:</span> <span class="val">{stats['topics']}</span></div>
  <div><span class="stat">Concepts:</span> <span class="val">{stats['concepts']}</span></div>
  <div><span class="stat">Files:</span> <span class="val">{stats['files']}</span></div>
  <div><span class="stat">Connections:</span> <span class="val">{stats['edges']}</span></div>
  <div style="margin-top:6px;color:#555;font-size:10px;">Drag to pan, scroll to zoom, hover for details</div>
</div>
<div id="tooltip"></div>
<svg></svg>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const graph = {json.dumps(graph)};

const svg = d3.select("svg");
const width = window.innerWidth;
const height = window.innerHeight;
const tooltip = d3.select("#tooltip");

const g = svg.append("g");

const zoom = d3.zoom()
  .scaleExtent([0.1, 5])
  .on("zoom", (e) => g.attr("transform", e.transform));
svg.call(zoom);

const sim = d3.forceSimulation(graph.nodes)
  .force("link", d3.forceLink(graph.edges).id(d => d.id).distance(d => d.type === "topic" ? 120 : 60).strength(0.3))
  .force("charge", d3.forceManyBody().strength(d => d.type === "topic" ? -400 : d.type === "concept" ? -150 : -30))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collision", d3.forceCollide().radius(d => d.size + 2));

const link = g.append("g").selectAll("line")
  .data(graph.edges).join("line")
  .attr("class", d => "link link-" + d.type)
  .attr("stroke-width", 0.5);

const node = g.append("g").selectAll("circle")
  .data(graph.nodes).join("circle")
  .attr("r", d => d.size)
  .attr("fill", d => d.color)
  .attr("fill-opacity", d => d.type === "topic" ? 0.9 : d.type === "concept" ? 0.7 : 0.5)
  .attr("stroke", d => d.type === "topic" ? "#fff" : "none")
  .attr("stroke-width", d => d.type === "topic" ? 1.5 : 0)
  .call(d3.drag()
    .on("start", (e, d) => {{ if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on("drag", (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
    .on("end", (e, d) => {{ if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }})
  );

const label = g.append("g").selectAll("text")
  .data(graph.nodes.filter(d => d.type !== "file")).join("text")
  .text(d => d.label)
  .attr("font-size", d => d.type === "topic" ? 12 : 9)
  .attr("fill", d => d.type === "topic" ? "#fff" : "#aaa")
  .attr("text-anchor", "middle")
  .attr("dy", d => d.size + 12);

node.on("mouseover", (e, d) => {{
  tooltip.style("display", "block")
    .html("<b>" + d.label + "</b><br>Type: " + d.type +
      (d.file_count ? "<br>Files: " + d.file_count : "") +
      (d.path ? "<br>" + d.path : ""));
}}).on("mousemove", (e) => {{
  tooltip.style("left", (e.pageX + 12) + "px").style("top", (e.pageY - 12) + "px");
}}).on("mouseout", () => tooltip.style("display", "none"));

sim.on("tick", () => {{
  link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("cx", d => d.x).attr("cy", d => d.y);
  label.attr("x", d => d.x).attr("y", d => d.y);
}});
</script>
</body>
</html>"""


def main():
    print("Building research brain graph...")
    graph = build_graph()

    # Save graph JSON
    out_json = VAULT / "graph.json"
    out_json.write_text(json.dumps(graph, indent=2))
    print(f"Graph JSON: {out_json} ({graph['stats']})")

    # Save HTML viewer
    out_html = VAULT / "graph.html"
    out_html.write_text(generate_html(graph))
    print(f"Graph HTML: {out_html}")
    print(f"Open in browser: file://{out_html}")


if __name__ == "__main__":
    main()
