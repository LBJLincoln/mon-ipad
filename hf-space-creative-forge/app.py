#!/usr/bin/env python3
"""
NOMOS42 CREATIVE FORGE (RGWA) — Department Dashboard (HF Space)
================================================================
Lightweight monitoring dashboard for AI Art (RGWA) departments.
NO ML on CPU -- reads data files, displays metrics, syncs results.

Departments:
  D8-Generation: Track pieces generated, quality scores, model usage
  D8-Curation: Monitor gallery pipeline, filtering, quality gates
  D8-Publishing: Track @RGWAbot posts, engagement metrics
  D8-StyleEvo: Monitor style diversity, trend tracking, evolution

Clones rgwa at startup, runs department loops every 15 min,
git syncs results back.
"""

import os
import sys
import json
import time
import threading
import subprocess
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import gradio as gr
import requests

# ── Configuration ──
REPO_URL = "https://github.com/LBJLincoln/rgwa.git"
REPO_DIR = Path("/tmp/rgwa")
DATA_DIR = REPO_DIR / "data"
LOOP_INTERVAL = 900  # 15 minutes
VERSION = "1.0.0"

# ── Art Styles Tracked ──
ART_STYLES = [
    "Abstract Expressionism",
    "Surrealism",
    "Digital Brutalism",
    "Glitch Art",
    "Vaporwave",
    "Cyberpunk",
    "Minimalism",
    "Generative Geometry",
    "AI Dreamscapes",
    "Neo-Futurism",
    "Data Visualization Art",
    "Algorithmic Nature",
]

# ── Quality Tiers ──
QUALITY_TIERS = {
    "S": {"label": "Masterpiece", "threshold": 0.95, "count": 0},
    "A": {"label": "Gallery-worthy", "threshold": 0.85, "count": 0},
    "B": {"label": "Good", "threshold": 0.70, "count": 0},
    "C": {"label": "Acceptable", "threshold": 0.50, "count": 0},
    "D": {"label": "Draft", "threshold": 0.0, "count": 0},
}

# ── State ──
forge_state = {
    "started": datetime.now(timezone.utc).isoformat(),
    "loop_count": 0,
    "last_loop": None,
    "repo_cloned": False,
    "errors": [],
    "departments": {
        "generation": {
            "name": "Generation",
            "status": "idle",
            "pieces_total": 0,
            "pieces_today": 0,
            "avg_quality_score": 0.0,
            "models_used": [],
            "last_generation": None,
            "generation_rate": 0.0,  # pieces/hour
        },
        "curation": {
            "name": "Curation",
            "status": "idle",
            "gallery_size": 0,
            "pending_review": 0,
            "accepted_rate": 0.0,
            "rejected_count": 0,
            "quality_distribution": {},
            "last_curation": None,
        },
        "publishing": {
            "name": "Publishing",
            "status": "idle",
            "posts_total": 0,
            "posts_today": 0,
            "avg_engagement": 0.0,
            "channels": ["@RGWAbot"],
            "last_post": None,
            "top_performing": [],
        },
        "style_evolution": {
            "name": "Style Evolution",
            "status": "idle",
            "styles_active": 0,
            "style_diversity": 0.0,
            "trending_styles": [],
            "style_history": [],
            "last_analysis": None,
        },
    },
}


# ── Repo Management ──
def clone_or_pull_repo():
    """Clone repo at startup or pull latest."""
    try:
        if REPO_DIR.exists() and (REPO_DIR / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(REPO_DIR), "pull", "--rebase"],
                capture_output=True, text=True, timeout=60,
            )
            return f"Pull: {result.stdout.strip()}"
        else:
            token = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
            url = REPO_URL
            if token:
                url = REPO_URL.replace("https://", f"https://{token}@")
            REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(REPO_DIR)],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                forge_state["repo_cloned"] = True
                return "Clone: success"
            return f"Clone failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Repo error: {e}"


def git_sync_results():
    """Push updated data back to repo."""
    try:
        if not (REPO_DIR / ".git").exists():
            return "No repo to sync"
        cmds = [
            ["git", "-C", str(REPO_DIR), "add", "-A"],
            ["git", "-C", str(REPO_DIR), "commit", "-m",
             f"forge: creative dept sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"],
            ["git", "-C", str(REPO_DIR), "push"],
        ]
        for cmd in cmds:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
                return f"Sync issue: {r.stderr.strip()}"
        return "Synced"
    except Exception as e:
        return f"Sync error: {e}"


# ── Data Readers ──
def read_json_safe(path):
    """Read JSON file safely."""
    try:
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def scan_generation_data():
    """Scan generation output data."""
    dept = forge_state["departments"]["generation"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total = 0
    today_count = 0
    quality_scores = []
    models = set()

    # Scan gallery directories
    gallery_dir = DATA_DIR / "gallery"
    if gallery_dir.exists():
        # Check index
        index = read_json_safe(gallery_dir / "index.json")
        if isinstance(index, list):
            total += len(index)
            for item in index:
                if isinstance(item, dict):
                    if item.get("date", "").startswith(today):
                        today_count += 1
                    if "quality" in item:
                        quality_scores.append(item["quality"])
                    if "model" in item:
                        models.add(item["model"])
        elif isinstance(index, dict):
            total += index.get("total", 0)
            today_count += index.get("today", 0)

        # Count images in subdirectories
        for subdir in ["images", "video", "audio"]:
            media_dir = gallery_dir / subdir
            if media_dir.exists():
                files = list(media_dir.glob("*"))
                media_count = len([f for f in files if f.is_file() and not f.name.startswith(".")])
                total += media_count

    # Scan results directory
    results_dir = DATA_DIR / "results"
    if results_dir.exists():
        for f in results_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict):
                if "pieces" in data:
                    total += data["pieces"]
                if "quality_score" in data:
                    quality_scores.append(data["quality_score"])
                if "model" in data:
                    models.add(data["model"])

    # Scan departments/creative
    creative_dir = DATA_DIR / "departments" / "creative"
    if creative_dir.exists():
        for f in creative_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict):
                total += data.get("generated", 0)
                if "quality" in data:
                    quality_scores.append(data["quality"])

    dept["pieces_total"] = total
    dept["pieces_today"] = today_count
    dept["avg_quality_score"] = round(sum(quality_scores) / max(len(quality_scores), 1), 3)
    dept["models_used"] = list(models)[:10]
    dept["last_generation"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"

    # Estimate generation rate
    if forge_state["loop_count"] > 0:
        try:
            start = datetime.fromisoformat(forge_state["started"])
            hours = (datetime.now(timezone.utc) - start).total_seconds() / 3600
            dept["generation_rate"] = round(total / max(hours, 0.1), 1)
        except Exception:
            pass


def scan_curation_data():
    """Scan curation pipeline data."""
    dept = forge_state["departments"]["curation"]

    gallery_size = 0
    pending = 0
    accepted = 0
    rejected = 0
    quality_dist = {tier: 0 for tier in QUALITY_TIERS}

    # Gallery index
    gallery_dir = DATA_DIR / "gallery"
    if gallery_dir.exists():
        index = read_json_safe(gallery_dir / "index.json")
        if isinstance(index, list):
            gallery_size = len(index)
            for item in index:
                if isinstance(item, dict):
                    status = item.get("status", "accepted")
                    if status == "pending":
                        pending += 1
                    elif status == "accepted":
                        accepted += 1
                    elif status == "rejected":
                        rejected += 1

                    # Quality tier assignment
                    q = item.get("quality", 0.5)
                    if q >= 0.95:
                        quality_dist["S"] += 1
                    elif q >= 0.85:
                        quality_dist["A"] += 1
                    elif q >= 0.70:
                        quality_dist["B"] += 1
                    elif q >= 0.50:
                        quality_dist["C"] += 1
                    else:
                        quality_dist["D"] += 1
        elif isinstance(index, dict):
            gallery_size = index.get("total", 0)

        # Count actual media files
        for subdir in ["images", "video", "audio"]:
            media_dir = gallery_dir / subdir
            if media_dir.exists():
                gallery_size += len([f for f in media_dir.glob("*") if f.is_file() and not f.name.startswith(".")])

    total_reviewed = accepted + rejected
    dept["gallery_size"] = gallery_size
    dept["pending_review"] = pending
    dept["accepted_rate"] = round(accepted / max(total_reviewed, 1) * 100, 1)
    dept["rejected_count"] = rejected
    dept["quality_distribution"] = quality_dist
    dept["last_curation"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


def scan_publishing_data():
    """Scan publishing and engagement data."""
    dept = forge_state["departments"]["publishing"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total_posts = 0
    today_posts = 0
    engagements = []
    top_performing = []

    # Check prompts directory for post history
    prompts_dir = DATA_DIR / "prompts"
    if prompts_dir.exists():
        for f in prompts_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict):
                total_posts += 1
                if data.get("date", "").startswith(today):
                    today_posts += 1
                eng = data.get("engagement", 0)
                engagements.append(eng)
                if eng > 0:
                    top_performing.append({
                        "title": data.get("title", f.stem),
                        "engagement": eng,
                    })
            elif isinstance(data, list):
                total_posts += len(data)

    # Check departments data
    creative_dir = DATA_DIR / "departments" / "creative"
    if creative_dir.exists():
        for f in creative_dir.glob("*publish*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict):
                total_posts += data.get("posts", 0)
                today_posts += data.get("posts_today", 0)

    dept["posts_total"] = total_posts
    dept["posts_today"] = today_posts
    dept["avg_engagement"] = round(sum(engagements) / max(len(engagements), 1), 2)
    dept["top_performing"] = sorted(top_performing, key=lambda x: x.get("engagement", 0), reverse=True)[:5]
    dept["last_post"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


def scan_style_evolution():
    """Scan style diversity and evolution data."""
    dept = forge_state["departments"]["style_evolution"]

    styles_seen = set()
    style_counts = defaultdict(int)

    # Scan gallery for style tags
    gallery_dir = DATA_DIR / "gallery"
    if gallery_dir.exists():
        index = read_json_safe(gallery_dir / "index.json")
        if isinstance(index, list):
            for item in index:
                if isinstance(item, dict):
                    style = item.get("style", "Unknown")
                    styles_seen.add(style)
                    style_counts[style] += 1

    # Scan results for style data
    results_dir = DATA_DIR / "results"
    if results_dir.exists():
        for f in results_dir.glob("*.json"):
            data = read_json_safe(f)
            if isinstance(data, dict) and "style" in data:
                styles_seen.add(data["style"])
                style_counts[data["style"]] += 1

    # Include known art styles
    for style in ART_STYLES:
        styles_seen.add(style)

    total_styles = len(styles_seen)
    dept["styles_active"] = total_styles

    # Shannon diversity index for style diversity
    if style_counts:
        total = sum(style_counts.values())
        diversity = 0.0
        for count in style_counts.values():
            p = count / total
            if p > 0:
                import math
                diversity -= p * math.log(p)
        dept["style_diversity"] = round(diversity, 3)
    else:
        dept["style_diversity"] = 0.0

    # Trending: top styles by count
    trending = sorted(style_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    dept["trending_styles"] = [{"style": s, "count": c} for s, c in trending]

    # Style history (last N data points)
    dept["style_history"] = [
        {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "active": total_styles, "diversity": dept["style_diversity"]}
    ]

    dept["last_analysis"] = datetime.now(timezone.utc).isoformat()
    dept["status"] = "active"


# ── Department Loop ──
def run_department_loop():
    """Run all department scans."""
    try:
        scan_generation_data()
        scan_curation_data()
        scan_publishing_data()
        scan_style_evolution()
        forge_state["loop_count"] += 1
        forge_state["last_loop"] = datetime.now(timezone.utc).isoformat()

        # Write state to repo
        state_file = DATA_DIR / "departments" / "forge-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(forge_state, f, indent=2, default=str)

    except Exception as e:
        forge_state["errors"].append(f"{datetime.now(timezone.utc).isoformat()}: {e}")
        forge_state["errors"] = forge_state["errors"][-20:]


def background_loop():
    """Background thread: clone, then loop every 15 min."""
    print(f"[CreativeForge] Starting background loop (interval={LOOP_INTERVAL}s)")
    clone_result = clone_or_pull_repo()
    print(f"[CreativeForge] {clone_result}")

    while True:
        try:
            clone_or_pull_repo()
            run_department_loop()
            git_sync_results()
            print(f"[CreativeForge] Loop {forge_state['loop_count']} complete")
        except Exception as e:
            print(f"[CreativeForge] Loop error: {e}")
            traceback.print_exc()
        time.sleep(LOOP_INTERVAL)


# ── Gradio UI Builders ──
def build_generation_tab():
    """Generation department tab."""
    dept = forge_state["departments"]["generation"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Generation Department
**Status:** {dept['status']} | **Last Generation:** {dept.get('last_generation', 'never')} | **Refreshed:** {now}

### Generation Metrics
| Metric | Value |
|--------|-------|
| Total Pieces | {dept['pieces_total']} |
| Today | {dept['pieces_today']} |
| Avg Quality Score | {dept['avg_quality_score']:.3f} |
| Generation Rate | {dept['generation_rate']:.1f} pieces/hr |
"""

    # Models used
    model_text = "\n### Models Used\n"
    if dept["models_used"]:
        for m in dept["models_used"]:
            model_text += f"- {m}\n"
    else:
        model_text += "_Scanning for model data..._\n"

    # Generation pipeline
    pipeline = """
### Generation Pipeline
1. **Prompt Engineering** -- Style-guided prompt construction from curated templates
2. **Model Selection** -- Adaptive model routing based on style + quality targets
3. **Batch Generation** -- Parallel generation with diversity constraints
4. **Quality Scoring** -- Automatic quality assessment (aesthetic + technical + novelty)
5. **Metadata Tagging** -- Style, mood, technique, color palette extraction
"""

    return header + model_text + pipeline


def build_curation_tab():
    """Curation department tab."""
    dept = forge_state["departments"]["curation"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Curation Department
**Status:** {dept['status']} | **Last Curation:** {dept.get('last_curation', 'never')} | **Refreshed:** {now}

### Gallery Metrics
| Metric | Value |
|--------|-------|
| Gallery Size | {dept['gallery_size']} |
| Pending Review | {dept['pending_review']} |
| Acceptance Rate | {dept['accepted_rate']:.1f}% |
| Rejected | {dept['rejected_count']} |
"""

    # Quality distribution
    quality_text = "\n### Quality Distribution\n| Tier | Label | Threshold | Count |\n|------|-------|-----------|-------|\n"
    for tier, info in QUALITY_TIERS.items():
        count = dept.get("quality_distribution", {}).get(tier, 0)
        quality_text += f"| {tier} | {info['label']} | >= {info['threshold']:.2f} | {count} |\n"

    # Curation pipeline
    pipeline = """
### Curation Pipeline
1. **Auto-Filter** -- Remove duplicates, corrupted files, low-resolution outputs
2. **Quality Gate** -- Score >= 0.50 required for gallery inclusion
3. **Style Check** -- Ensure style diversity (no single style > 40% of gallery)
4. **Manual Queue** -- Borderline pieces (0.50-0.70) flagged for review
5. **Gallery Update** -- Accepted pieces indexed, metadata enriched, thumbnails generated
"""

    return header + quality_text + pipeline


def build_publishing_tab():
    """Publishing department tab."""
    dept = forge_state["departments"]["publishing"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Publishing Department
**Status:** {dept['status']} | **Last Post:** {dept.get('last_post', 'never')} | **Refreshed:** {now}

### Publishing Metrics
| Metric | Value |
|--------|-------|
| Total Posts | {dept['posts_total']} |
| Today | {dept['posts_today']} |
| Avg Engagement | {dept['avg_engagement']:.2f} |
| Active Channels | {', '.join(dept['channels'])} |
"""

    # Top performing
    top_text = "\n### Top Performing Posts\n"
    if dept.get("top_performing"):
        top_text += "| Title | Engagement |\n|-------|------------|\n"
        for post in dept["top_performing"][:5]:
            top_text += f"| {post.get('title', 'Untitled')} | {post.get('engagement', 0)} |\n"
    else:
        top_text += "_No engagement data yet..._\n"

    # Publishing strategy
    strategy = """
### Publishing Strategy
- **@RGWAbot** (Telegram): Primary channel for AI art output
- **Scheduling**: Peak engagement hours (UTC 14:00-20:00)
- **Content Mix**: 60% new generations, 20% curated highlights, 20% process/behind-the-scenes
- **Engagement Loop**: Track reactions, adjust style mix based on audience preference
- **Cross-promotion**: Share highlights to @Nomos42 channel
"""

    return header + top_text + strategy


def build_style_tab():
    """Style Evolution department tab."""
    dept = forge_state["departments"]["style_evolution"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = f"""## Style Evolution Department
**Status:** {dept['status']} | **Last Analysis:** {dept.get('last_analysis', 'never')} | **Refreshed:** {now}

### Style Metrics
| Metric | Value |
|--------|-------|
| Active Styles | {dept['styles_active']} |
| Style Diversity (Shannon) | {dept['style_diversity']:.3f} |
"""

    # Trending styles
    trend_text = "\n### Trending Styles\n"
    if dept.get("trending_styles"):
        trend_text += "| Style | Pieces |\n|-------|--------|\n"
        for t in dept["trending_styles"]:
            trend_text += f"| {t['style']} | {t['count']} |\n"
    else:
        trend_text += "_Analyzing style distribution..._\n"

    # Known styles tracking
    style_list = "\n### Style Palette\n"
    for style in ART_STYLES:
        style_list += f"- {style}\n"

    # Evolution methodology
    method = """
### Evolution Methodology
- **Diversity Pressure**: Maintain Shannon diversity > 1.5 across styles
- **Trend Detection**: Rolling 7-day style frequency analysis
- **Novelty Bonus**: New style combinations get priority in generation queue
- **Audience Signal**: Telegram engagement feeds back into style weights
- **Seasonal Rotation**: Shift palette and mood based on calendar events
"""

    return header + trend_text + style_list + method


def build_overview():
    """Main overview dashboard."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    uptime = "N/A"
    if forge_state.get("started"):
        try:
            start = datetime.fromisoformat(forge_state["started"])
            delta = datetime.now(timezone.utc) - start
            hours = delta.total_seconds() / 3600
            uptime = f"{hours:.1f}h"
        except Exception:
            pass

    gen = forge_state["departments"]["generation"]
    cur = forge_state["departments"]["curation"]
    pub = forge_state["departments"]["publishing"]
    sty = forge_state["departments"]["style_evolution"]

    overview = f"""## Creative Forge (RGWA) -- Overview
**Version:** {VERSION} | **Uptime:** {uptime} | **Loops:** {forge_state['loop_count']} | **Refreshed:** {now}

### Department Status
| Department | Status | Key Metric |
|-----------|--------|------------|
| Generation | {gen['status']} | {gen['pieces_total']} pieces ({gen['avg_quality_score']:.3f} avg quality) |
| Curation | {cur['status']} | {cur['gallery_size']} in gallery ({cur['accepted_rate']:.0f}% acceptance) |
| Publishing | {pub['status']} | {pub['posts_total']} posts ({pub['avg_engagement']:.1f} avg engagement) |
| Style Evolution | {sty['status']} | {sty['styles_active']} styles ({sty['style_diversity']:.3f} diversity) |

### System Info
| Item | Value |
|------|-------|
| Repo | rgwa |
| Repo Cloned | {forge_state['repo_cloned']} |
| Loop Interval | {LOOP_INTERVAL}s (15 min) |
| Last Loop | {forge_state.get('last_loop', 'never')} |
| Bot | @RGWAbot |
| Art Styles Tracked | {len(ART_STYLES)} |
"""

    # Recent errors
    if forge_state["errors"]:
        overview += "\n### Recent Errors\n"
        for err in forge_state["errors"][-5:]:
            overview += f"- `{err}`\n"

    return overview


def refresh_all():
    """Refresh all tabs."""
    run_department_loop()
    return (
        build_overview(),
        build_generation_tab(),
        build_curation_tab(),
        build_publishing_tab(),
        build_style_tab(),
    )


def get_status_json():
    """Return forge state as formatted JSON."""
    return json.dumps(forge_state, indent=2, default=str)


# ── Build Gradio App ──
def create_app():
    with gr.Blocks(
        title="Nomos42 Creative Forge (RGWA)",
        theme=gr.themes.Soft(),
    ) as app:
        gr.Markdown("# Nomos42 Creative Forge (RGWA)\n_Department dashboard for AI art generation, curation, publishing, and style evolution._")

        with gr.Tabs():
            with gr.Tab("Overview"):
                overview_md = gr.Markdown(build_overview())

            with gr.Tab("Generation"):
                gen_md = gr.Markdown(build_generation_tab())

            with gr.Tab("Curation"):
                cur_md = gr.Markdown(build_curation_tab())

            with gr.Tab("Publishing"):
                pub_md = gr.Markdown(build_publishing_tab())

            with gr.Tab("Style Evolution"):
                style_md = gr.Markdown(build_style_tab())

            with gr.Tab("Raw State"):
                state_json = gr.Textbox(
                    value=get_status_json(),
                    label="Forge State JSON",
                    lines=30,
                    interactive=False,
                )

        refresh_btn = gr.Button("Refresh All Departments", variant="primary")
        refresh_btn.click(
            fn=refresh_all,
            outputs=[overview_md, gen_md, cur_md, pub_md, style_md],
        )

    return app


# ── FastAPI + Gradio Mount ──
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

api = FastAPI()


@api.get("/api/status")
async def api_status():
    return JSONResponse(content={
        "space": "creative-forge",
        "version": VERSION,
        "status": "running",
        "loop_count": forge_state["loop_count"],
        "last_loop": forge_state.get("last_loop"),
        "departments": {
            k: {"status": v["status"], "name": v["name"]}
            for k, v in forge_state["departments"].items()
        },
    })


@api.get("/api/state")
async def api_state():
    return JSONResponse(content=forge_state)


# ── Launch ──
if __name__ == "__main__":
    # Start background loop
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    app = create_app()
    app = gr.mount_gradio_app(api, app, path="/")

    import uvicorn
    uvicorn.run(api, host="0.0.0.0", port=7860)
else:
    # HF Spaces import mode
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    app = create_app()
    demo = app  # HF Spaces expects `demo`
    app = gr.mount_gradio_app(api, app, path="/")
