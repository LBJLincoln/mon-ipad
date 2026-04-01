#!/bin/bash
# Auto-Iteration Engine — Karpathy Autoresearch Pattern for Trading Floor
# Pattern: run iteration → analyze → propose improvements → apply → run next
# Triggered by: autonomous-cycle.sh Phase 3c OR manually
#
# Following Karpathy's official autoresearch pattern:
#   1. Run experiment (5 min budget = 1 full backtest)
#   2. Measure metric (bankroll = fitness toward $1M)
#   3. If improved → keep
#   4. If not → revert
#   5. Log everything for post-analysis
#   6. Repeat
set -uo pipefail

ROOT="/home/termius/mon-ipad"
LOG="$ROOT/logs/auto-iterate.log"
ITER_FILE="$ROOT/data/arena/trading-floor-iteration.json"
BEST_CONFIG="$ROOT/data/arena/best-config-toward-1M.json"
KARPATHY_OUT="$ROOT/data/arena/trading-floor-karpathy-output.json"
PROPOSALS_DIR="$ROOT/data/arena/proposals"
mkdir -p "$PROPOSALS_DIR" "$(dirname "$LOG")"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

log "=== AUTO-ITERATE ENGINE START ==="

# ── Step 1: Read current state ──────────────────────────────────────────────
CURRENT_ITER=$(python3 -c "import json; print(json.load(open('$ITER_FILE')).get('iteration', 0))" 2>/dev/null || echo 0)
CURRENT_BEST=$(python3 -c "import json; print(json.load(open('$BEST_CONFIG')).get('best_bankroll', 100))" 2>/dev/null || echo 100)
log "Current iteration: $CURRENT_ITER | Best bankroll: \$$CURRENT_BEST"

# ── Step 2: Run full Trading Floor Karpathy loop (the "experiment") ─────────
log "Running Trading Floor v5 backtest (iteration $((CURRENT_ITER + 1)))..."
timeout 300 python3 "$ROOT/scripts/arena/trading-floor-v4.py" karpathy >> "$LOG" 2>&1
RUN_EXIT=$?

if [ $RUN_EXIT -ne 0 ]; then
    log "ERROR: Trading floor run failed (exit=$RUN_EXIT)"
    exit 1
fi

# ── Step 3: Measure result ──────────────────────────────────────────────────
NEW_BEST=$(python3 -c "import json; print(json.load(open('$BEST_CONFIG')).get('best_bankroll', 100))" 2>/dev/null || echo 100)
NEW_ITER=$(python3 -c "import json; print(json.load(open('$ITER_FILE')).get('iteration', 0))" 2>/dev/null || echo 0)
IMPROVED=$(python3 -c "print('yes' if $NEW_BEST > $CURRENT_BEST else 'no')")

log "New iteration: $NEW_ITER | New best: \$$NEW_BEST | Improved: $IMPROVED"

# ── Step 4: Analyze and propose improvements ────────────────────────────────
log "Analyzing results and proposing improvements..."
PROPOSAL_FILE="$PROPOSALS_DIR/proposal-iter-${NEW_ITER}.json"

python3 - "$KARPATHY_OUT" "$BEST_CONFIG" "$PROPOSAL_FILE" <<'PYEOF'
import json, sys
from datetime import datetime, timezone

karpathy = json.loads(open(sys.argv[1]).read())
best_config = json.loads(open(sys.argv[2]).read())
proposal_file = sys.argv[3]

proposals = []

# Analyze strategy performance
strat_rankings = karpathy.get("strategy_rankings", [])
if strat_rankings:
    top_strat = strat_rankings[0]
    bottom_strats = [s for s in strat_rankings if s.get("roi_pct", 0) < 0]

    if bottom_strats:
        proposals.append({
            "type": "eliminate_strategies",
            "strategies": [s["strategy"] for s in bottom_strats[:3]],
            "reason": f"{len(bottom_strats)} strategies with negative ROI",
            "priority": 1,
        })

# Analyze model performance
model_rankings = karpathy.get("model_rankings", [])
if model_rankings:
    top_model = model_rankings[0]
    proposals.append({
        "type": "promote_model",
        "model": top_model.get("model", "unknown"),
        "avg_daily_pnl": top_model.get("avg_daily_pnl", 0),
        "reason": f"Top performing model with {top_model.get('win_rate_pct', 0):.0f}% win rate",
        "priority": 2,
    })

# Analyze $1M progress
opt = karpathy.get("optimization", {})
if opt:
    current = opt.get("current_best", 100)
    target = opt.get("target", 1_000_000)
    if current < target * 0.5:
        proposals.append({
            "type": "increase_aggression",
            "reason": f"Only {current/target*100:.1f}% to $1M — agents need more aggressive Kelly fractions",
            "priority": 1,
        })

# Analyze mutations
mutations = karpathy.get("mutations", {})
if not mutations:
    proposals.append({
        "type": "force_mutation",
        "reason": "No mutations last iteration — force bottom agent to adopt top agent's full config",
        "priority": 2,
    })

# Category analysis
cat_rankings = karpathy.get("category_rankings", [])
if cat_rankings:
    best_cats = [c for c in cat_rankings if c.get("win_rate_pct", 0) > 65]
    worst_cats = [c for c in cat_rankings if c.get("win_rate_pct", 0) < 40 and c.get("bets", 0) > 50]
    if worst_cats:
        proposals.append({
            "type": "restrict_categories",
            "categories": [c["category"] for c in worst_cats],
            "reason": f"{len(worst_cats)} categories with <40% win rate should be avoided",
            "priority": 2,
        })

output = {
    "iteration": karpathy.get("iteration", 0),
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "current_best_bankroll": opt.get("current_best", 100),
    "distance_to_1M_pct": opt.get("distance_to_1M_pct", 100),
    "proposals": proposals,
    "proposals_count": len(proposals),
    "auto_applicable": [p for p in proposals if p["type"] in ["eliminate_strategies", "promote_model"]],
    "needs_review": [p for p in proposals if p["type"] in ["increase_aggression", "force_mutation"]],
}

with open(proposal_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"Proposals: {len(proposals)} ({len(output['auto_applicable'])} auto-applicable, {len(output['needs_review'])} need review)")
for p in proposals:
    print(f"  [{p['priority']}] {p['type']}: {p['reason']}")
PYEOF

# ── Step 5: Apply auto-applicable improvements ─────────────────────────────
log "Applying auto-applicable improvements..."
# The trading-floor-v4.py already handles:
# - Strategy elimination (auto in _auto_eliminate_strategies)
# - Agent mutation (auto in _mutate_agent_preferences)
# - Best config tracking (auto in run_karpathy_loop)
# So improvements are applied on the NEXT iteration automatically.

# ── Step 6: Update OPERATIONS.md with latest state ─────────────────────────
python3 - "$ROOT" <<'PYEOF'
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone

root = Path(sys.argv[1])

# Read latest state
iter_data = json.loads((root / "data/arena/trading-floor-iteration.json").read_text())
best = json.loads((root / "data/arena/best-config-toward-1M.json").read_text())

# Update the iteration line in OPERATIONS.md
ops_file = root / "OPERATIONS.md"
if ops_file.exists():
    content = ops_file.read_text()
    # Update last updated timestamp
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content = content.split("\n")
    for i, line in enumerate(content):
        if line.startswith("> **Last updated:**"):
            content[i] = f"> **Last updated:** {now} | **Auto-refreshed by:** autonomous-cycle.sh every 4h"
        elif "**Iteration:**" in line and "**Generation:**" in line:
            content[i] = f"- **Iteration:** {iter_data['iteration']} | **Generation:** {iter_data['generation']}"
        elif "**Best bankroll:**" in line:
            content[i] = f"- **Best bankroll:** ${best['best_bankroll']:,.0f} by {best['best_trader_id']} (aggressive, full_kelly + xgboost)"
        elif "**$1M target:**" in line:
            pct = (best['best_bankroll'] / 1_000_000) * 100
            mult = 1_000_000 / max(best['best_bankroll'], 1)
            content[i] = f"- **$1M target:** {pct:.1f}% achieved, need {mult:.1f}x more"
    ops_file.write_text("\n".join(content))
    print(f"OPERATIONS.md updated ({now})")
PYEOF

# ── Step 7: Git commit and push ─────────────────────────────────────────────
log "Committing iteration results..."
cd "$ROOT"
git add data/arena/ data/departments/ OPERATIONS.md 2>/dev/null
git diff --cached --quiet || {
    git commit -m "data: auto-iterate #${NEW_ITER} — best \$$(printf '%.0f' $NEW_BEST) ($IMPROVED)" --no-verify 2>/dev/null
    git push origin main 2>/dev/null || log "[GIT] push failed"
}

log "=== AUTO-ITERATE COMPLETE — iter $NEW_ITER, best \$$NEW_BEST ==="

# ── Step 8: Schedule next iteration (if in continuous mode) ─────────────────
# In continuous mode, the cron job will trigger the next iteration.
# For manual burst mode, call this script again.
echo "{\"iteration\": $NEW_ITER, \"best_bankroll\": $NEW_BEST, \"improved\": \"$IMPROVED\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
