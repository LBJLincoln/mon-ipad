#!/bin/bash
# Department: CREATIVE (D8 / RGWA) — Karpathy Loop
# Pattern: scan gallery → measure quality → check generation pipeline → propose improvements
# Metric: quality_score, pieces_count, diversity_index, generation_rate
# Max runtime: 5 minutes
set -uo pipefail

DEPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$(dirname "$(dirname "$DEPT_DIR")")")"
RGWA_ROOT="/home/lahargnedebartoli/rgwa"

OUTPUT_DIR="$ROOT/data/departments/creative"
OUTPUT_FILE="$OUTPUT_DIR/karpathy-output.json"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
ITER_FILE="$OUTPUT_DIR/.iteration"
ITERATION=$(cat "$ITER_FILE" 2>/dev/null || echo 0)
ITERATION=$((ITERATION + 1))
echo "$ITERATION" > "$ITER_FILE"

echo "[D8-CREATIVE] Starting Karpathy loop at $TIMESTAMP (iter=$ITERATION)" >&2

# ── Check RGWA repo exists ───────────────────────────────────────────────────
RGWA_EXISTS=false
if [[ -d "$RGWA_ROOT" ]]; then
    RGWA_EXISTS=true
fi

# ── Scan gallery index ───────────────────────────────────────────────────────
GALLERY_STATS=$(python3 - "$RGWA_ROOT" <<'PYEOF'
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone

rgwa = Path(sys.argv[1])
gallery_file = rgwa / "data" / "gallery" / "index.json"

result = {
    "total_pieces": 0,
    "images": 0,
    "music": 0,
    "video": 0,
    "avg_quality": None,
    "best_piece": None,
    "latest_piece": None,
    "gallery_exists": False,
}

if not gallery_file.exists():
    print(json.dumps(result))
    sys.exit(0)

try:
    data = json.load(open(gallery_file))
    result["gallery_exists"] = True

    stats = data.get("stats", {})
    result["images"] = stats.get("images", 0)
    result["music"] = stats.get("music", 0)
    result["video"] = stats.get("video", 0)
    result["total_pieces"] = data.get("total_pieces", 0)
    result["avg_quality"] = stats.get("avg_score")
    result["best_piece"] = stats.get("best_piece")

    pieces = data.get("pieces", [])
    if pieces:
        result["total_pieces"] = max(result["total_pieces"], len(pieces))
        # Find latest
        sorted_pieces = sorted(pieces, key=lambda p: p.get("created_at", ""), reverse=True)
        if sorted_pieces:
            result["latest_piece"] = {
                "id": sorted_pieces[0].get("id"),
                "type": sorted_pieces[0].get("type"),
                "created_at": sorted_pieces[0].get("created_at"),
            }
        # Compute avg quality from pieces that have scores
        scored = [p.get("quality_score") for p in pieces if p.get("quality_score")]
        if scored:
            result["avg_quality"] = round(sum(scored) / len(scored), 2)
except Exception as e:
    result["error"] = str(e)[:200]

print(json.dumps(result))
PYEOF
)

# ── Scan prompt library ──────────────────────────────────────────────────────
PROMPT_STATS=$(python3 - "$RGWA_ROOT" <<'PYEOF'
import json, sys
from pathlib import Path

rgwa = Path(sys.argv[1])
prompt_file = rgwa / "data" / "prompts" / "starter-prompts.json"

result = {"total_prompts": 0, "categories": [], "prompt_file_exists": False}

if not prompt_file.exists():
    print(json.dumps(result))
    sys.exit(0)

try:
    data = json.load(open(prompt_file))
    result["prompt_file_exists"] = True
    if isinstance(data, list):
        result["total_prompts"] = len(data)
        cats = set()
        for p in data:
            if isinstance(p, dict) and "category" in p:
                cats.add(p["category"])
        result["categories"] = sorted(cats)
    elif isinstance(data, dict):
        prompts = data.get("prompts", [])
        result["total_prompts"] = len(prompts)
except Exception as e:
    result["error"] = str(e)[:200]

print(json.dumps(result))
PYEOF
)

# ── Check generation pipeline (scripts, bots) ───────────────────────────────
PIPELINE_STATUS=$(python3 - "$RGWA_ROOT" <<'PYEOF'
import json, sys, os
from pathlib import Path

rgwa = Path(sys.argv[1])
result = {
    "scripts_count": 0,
    "bot_script_exists": False,
    "generation_scripts": [],
    "data_dirs": [],
}

scripts_dir = rgwa / "scripts"
if scripts_dir.exists():
    scripts = list(scripts_dir.glob("*.py")) + list(scripts_dir.glob("*.sh"))
    result["scripts_count"] = len(scripts)
    result["generation_scripts"] = [s.name for s in scripts[:10]]

# Check for bot
for bot_name in ["bot.py", "telegram_bot.py", "rgwa_bot.py"]:
    if (rgwa / bot_name).exists() or (rgwa / "scripts" / bot_name).exists():
        result["bot_script_exists"] = True
        break

# Check data directories
data_dir = rgwa / "data"
if data_dir.exists():
    result["data_dirs"] = [d.name for d in data_dir.iterdir() if d.is_dir()]

print(json.dumps(result))
PYEOF
)

# ── Compute diversity index ──────────────────────────────────────────────────
DIVERSITY_INDEX=$(python3 - "$GALLERY_STATS" <<'PYEOF'
import json, sys
stats = json.loads(sys.argv[1])
types = [stats.get("images", 0), stats.get("music", 0), stats.get("video", 0)]
total = sum(types)
if total == 0:
    print("0.0")
    sys.exit(0)
# Shannon diversity index normalized to 0-1
import math
probs = [t / total for t in types if t > 0]
if len(probs) <= 1:
    print("0.0")
    sys.exit(0)
h = -sum(p * math.log(p) for p in probs)
h_max = math.log(len(probs))
print(f"{h / h_max:.3f}" if h_max > 0 else "0.0")
PYEOF
)

# ── Build recommendations ────────────────────────────────────────────────────
RECOMMENDATIONS=$(python3 - "$GALLERY_STATS" "$PIPELINE_STATUS" "$PROMPT_STATS" <<'PYEOF'
import json, sys

gallery = json.loads(sys.argv[1])
pipeline = json.loads(sys.argv[2])
prompts = json.loads(sys.argv[3])

recs = []

total = gallery.get("total_pieces", 0)
if total == 0:
    recs.append({
        "type": "empty_gallery",
        "priority": 1,
        "action": "generate_first_pieces",
        "reason": "Gallery is empty. Generate initial art pieces to bootstrap the pipeline.",
    })

if gallery.get("images", 0) > 0 and gallery.get("music", 0) == 0:
    recs.append({
        "type": "missing_modality",
        "priority": 2,
        "action": "add_music_generation",
        "reason": "Only images exist. Add music generation for multi-modal diversity.",
    })

if gallery.get("video", 0) == 0 and total > 5:
    recs.append({
        "type": "missing_modality",
        "priority": 3,
        "action": "add_video_generation",
        "reason": "No video content yet. Consider adding video generation pipeline.",
    })

avg_q = gallery.get("avg_quality")
if avg_q is not None and avg_q < 0.7:
    recs.append({
        "type": "low_quality",
        "priority": 1,
        "action": "improve_prompts",
        "reason": f"Average quality score {avg_q:.2f} is below 0.70 threshold. Refine prompts and curation.",
    })

if prompts.get("total_prompts", 0) < 10:
    recs.append({
        "type": "limited_prompts",
        "priority": 2,
        "action": "expand_prompt_library",
        "reason": f"Only {prompts.get('total_prompts', 0)} prompts available. Expand to 50+ for diversity.",
    })

if not pipeline.get("bot_script_exists"):
    recs.append({
        "type": "no_bot",
        "priority": 3,
        "action": "deploy_telegram_bot",
        "reason": "No Telegram bot detected. Deploy @RGWAbot for autonomous publishing.",
    })

print(json.dumps(recs))
PYEOF
)

# ── Determine overall status ─────────────────────────────────────────────────
TOTAL_PIECES=$(echo "$GALLERY_STATS" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total_pieces', 0))" 2>/dev/null || echo 0)
AVG_QUALITY=$(echo "$GALLERY_STATS" | python3 -c "import json,sys; v=json.load(sys.stdin).get('avg_quality'); print(v if v else 'null')" 2>/dev/null || echo "null")
REC_COUNT=$(echo "$RECOMMENDATIONS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

if [ "$TOTAL_PIECES" -gt 10 ] && [ "$AVG_QUALITY" != "null" ]; then
    STATUS="active"
elif [ "$RGWA_EXISTS" = "true" ]; then
    STATUS="idle"
else
    STATUS="warning"
fi

echo "[D8-CREATIVE] Gallery: $TOTAL_PIECES pieces, quality=$AVG_QUALITY, status=$STATUS" >&2

# ── Write Karpathy output ────────────────────────────────────────────────────
cat > "$OUTPUT_FILE" <<EOF
{
  "department": "creative",
  "timestamp": "$TIMESTAMP",
  "iteration": $ITERATION,
  "status": "$STATUS",
  "rgwa_repo_exists": $RGWA_EXISTS,
  "gallery": $GALLERY_STATS,
  "prompts": $PROMPT_STATS,
  "pipeline": $PIPELINE_STATUS,
  "diversity_index": $DIVERSITY_INDEX,
  "quality_score": $AVG_QUALITY,
  "pieces_today": $TOTAL_PIECES,
  "recommendations": $RECOMMENDATIONS,
  "recommendations_count": $REC_COUNT,
  "improved": false
}
EOF

echo "[D8-CREATIVE] Karpathy loop complete — $OUTPUT_FILE" >&2

# Console output for guardian orchestrator
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(json.dumps({
    "status": d["status"],
    "department": d["department"],
    "metric": "quality_score",
    "quality_score": d.get("quality_score"),
    "pieces_today": d.get("pieces_today", 0),
    "diversity_index": d.get("diversity_index", 0),
    "recommendations_count": d.get("recommendations_count", 0),
    "improved": d.get("improved", False),
}))
PYEOF
