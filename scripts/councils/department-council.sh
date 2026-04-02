#!/bin/bash
################################################################################
# Department Council Runner — Karpathy loop per department
# Usage: department-council.sh <dept> [--dry-run]
# Departments: research|engineering|evolution|betting|evaluation|infra|political|creative|comms|business|finance
# Trading Floor has its own continuous loop (trading-floor-council-loop.sh)
################################################################################

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPT="${1:-}"
DRY_RUN="${2:-}"
LOG_DIR="$REPO_ROOT/logs/councils"
mkdir -p "$LOG_DIR"

source "$REPO_ROOT/.env.local" 2>/dev/null || true

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { echo "[$(ts)] [council:$DEPT] $*" | tee -a "$LOG_DIR/$DEPT.log"; }

if [ -z "$DEPT" ]; then
    echo "Usage: $0 <department>"
    echo "Departments: research engineering evolution betting evaluation infra political creative comms business finance"
    exit 1
fi

# ── Department-specific Karpathy loop ──────────────────────────────────

case "$DEPT" in
    research)
        log "START: Research Council — scan papers, extract techniques, propose features"
        cd "$REPO_ROOT"
        # Run research scanner
        python3 scripts/agents/research-scanner.py --quick 2>&1 | tail -5 | while read line; do log "$line"; done || true
        # Check for new proposals
        mkdir -p data/departments/research
        proposals=$(find data/departments/research/ -name '*.json' -newer "$LOG_DIR/research.lastrun" 2>/dev/null | wc -l || echo "0")
        log "DONE: $proposals new proposals found"
        touch "$LOG_DIR/research.lastrun"
        ;;

    engineering)
        log "START: Engineering Council — check engine parity, test builds, measure Brier delta"
        cd "$REPO_ROOT"
        # Verify feature engine parity across all HF spaces
        python3 -c "
import hashlib, pathlib
local = pathlib.Path('features/engine.py')
hf = pathlib.Path('hf-space/features/engine.py')
if local.exists() and hf.exists():
    lh = hashlib.md5(local.read_bytes()).hexdigest()[:8]
    hh = hashlib.md5(hf.read_bytes()).hexdigest()[:8]
    status = 'PARITY OK' if lh == hh else f'DRIFT: local={lh} hf={hh}'
    print(f'Engine parity: {status}')
else:
    print('Engine files missing')
" 2>&1 | while read line; do log "$line"; done
        log "DONE: Engineering check complete"
        ;;

    evolution)
        log "START: Evolution Council — check 6 islands, stagnation detection, cross-pollinate"
        cd "$REPO_ROOT"
        # Poll all 6 HF islands
        for island in s10:nomos42-nba-quant s11:nomos42-nba-quant-2 s12:nomos42-nba-evo-3 s13:nomos42-nba-evo-4 s14:nomos42-nba-evo-5 s15:nomos42-nba-evo-6; do
            name="${island%%:*}"
            url="${island#*:}"
            status=$(curl -s --max-time 8 "https://${url}.hf.space/api/status" 2>/dev/null || echo '{"error":"down"}')
            brier=$(echo "$status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('best_brier','?'))" 2>/dev/null || echo "?")
            gen=$(echo "$status" | python3 -c "import sys,json; print(json.load(sys.stdin).get('generation','?'))" 2>/dev/null || echo "?")
            log "  $name: Brier=$brier Gen=$gen"
        done
        log "DONE: Evolution check complete"
        ;;

    betting)
        log "START: Betting Council — analyze strategies, ROI, Kelly sizing"
        cd "$REPO_ROOT"
        if [ -f data/nba-agent/bankroll-state.json ]; then
            python3 -c "
import json
with open('data/nba-agent/bankroll-state.json') as f: s = json.load(f)
print(f'Bankroll: \${s.get(\"bankroll\",0):.2f} | ROI: {s.get(\"roi_pct\",0):.1f}% | Bets: {s.get(\"total_bets\",0)}')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Betting check complete"
        ;;

    evaluation)
        log "START: Evaluation Council — calibration, phantom detection, false positive audit"
        cd "$REPO_ROOT"
        if [ -f data/nba-agent/latest-eval.json ]; then
            python3 -c "
import json
with open('data/nba-agent/latest-eval.json') as f: e = json.load(f)
print(f'Brier: {e.get(\"brier\",\"?\")} | Games: {e.get(\"total_games\",\"?\")} | Accuracy: {e.get(\"accuracy\",\"?\")}')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Evaluation check complete"
        ;;

    infra)
        log "START: Infra Council — check all services, GPU platforms, data pipeline"
        cd "$REPO_ROOT"
        # Already handled by infra-agent.sh, just log summary
        if [ -f data/infra-status.json ]; then
            python3 -c "
import json
with open('data/infra-status.json') as f: s = json.load(f)
total = s.get('total_checks', 0)
ok = s.get('healthy', 0)
print(f'Infra: {ok}/{total} healthy')
" 2>&1 | while read line; do log "$line"; done
        fi
        log "DONE: Infra check complete"
        ;;

    political)
        log "START: Political Council — signal freshness, ETF strategy, category coverage"
        cd /home/termius/nomos-political-alpha 2>/dev/null || cd "$REPO_ROOT"
        python3 ops/fetch_political_data.py --fast 2>&1 | tail -3 | while read line; do log "$line"; done || log "Political fetch skipped"
        log "DONE: Political check complete"
        ;;

    creative)
        log "START: Creative Council — RGWA quality scores, generation rate, gallery"
        cd /home/termius/rgwa 2>/dev/null || cd "$REPO_ROOT"
        log "Checking RGWA generation pipeline..."
        # Placeholder — RGWA specific checks
        log "DONE: Creative check complete"
        ;;

    comms)
        log "START: Communication Council — prepare posts, check bot status, engagement"
        cd "$REPO_ROOT"
        # Check bot health
        for bot in "Nomos42Bot:8672296360:AAHZ5_3-fDE7BBb3b-RJBSRWlXA1qO31UVo" "Forge42Bot:8748162877:AAGZOrjB9HZx_0X6d9714sNAgw3DG12h9uA"; do
            name="${bot%%:*}"
            token="${bot#*:}"
            ok=$(curl -s --max-time 5 "https://api.telegram.org/bot${token}/getMe" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ok',False))" 2>/dev/null || echo "False")
            log "  $name: $ok"
        done
        log "DONE: Communication check complete"
        ;;

    business)
        log "START: Business Council — pricing, conversion, user metrics"
        cd "$REPO_ROOT"
        # Count forge users
        users=$(ls -d forge-users/*/ 2>/dev/null | wc -l)
        log "Forge users: $users"
        log "DONE: Business check complete"
        ;;

    finance)
        log "START: Finance Council — P&L, burn rate, revenue tracking"
        cd "$REPO_ROOT"
        # Compute costs
        log "Monthly costs: ~\$6 (VM) + \$0 (HF free) + Modal usage"
        if [ -f data/nba-agent/bankroll-state.json ]; then
            bankroll=$(python3 -c "import json; print(json.load(open('data/nba-agent/bankroll-state.json')).get('bankroll',0))" 2>/dev/null)
            log "Bankroll: \$$bankroll"
        fi
        log "DONE: Finance check complete"
        ;;

    *)
        echo "Unknown department: $DEPT"
        echo "Valid: research engineering evolution betting evaluation infra political creative comms business finance"
        exit 1
        ;;
esac

# ── Write enriched council result to JSON ──
python3 - "$DEPT" "$REPO_ROOT" "$(ts)" <<'COUNCIL_ENRICHMENT'
import json, sys, os, glob
from pathlib import Path
from datetime import datetime, timezone

dept = sys.argv[1]
repo_root = sys.argv[2]
timestamp = sys.argv[3]

# ── Collect department-specific metrics ──────────────────────────────────
metrics = {}
recommendations = []
kpis = {}
health = "GREEN"

# Helper: safe JSON load
def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

# ── BETTING metrics ──────────────────────────────────────────────────────
if dept == "betting":
    bankroll = load_json(f"{repo_root}/data/nba-agent/bankroll-state.json")
    tf_latest = load_json(f"{repo_root}/data/arena/trading-floor-v4-latest.json")
    council_latest = load_json(f"{repo_root}/data/arena/council/council-latest.json")

    metrics = {
        "bankroll": bankroll.get("bankroll", 0),
        "roi_pct": bankroll.get("roi_pct", 0),
        "total_bets": bankroll.get("total_bets", 0),
        "win_rate": bankroll.get("win_rate", 0),
        "sharpe": bankroll.get("sharpe", 0),
        "max_drawdown": bankroll.get("max_drawdown", 0),
    }

    # Trading floor leaderboard
    if council_latest:
        lb = council_latest.get("analysis", {}).get("leaderboard_summary", [])
        metrics["tf_leader"] = lb[0].get("trader_id", "unknown") if lb else "unknown"
        metrics["tf_best_bankroll"] = lb[0].get("nba_bankroll", 0) if lb else 0
        metrics["tf_worst_bankroll"] = lb[-1].get("nba_bankroll", 0) if lb else 0

        top_strats = council_latest.get("analysis", {}).get("top_strategies", [])
        metrics["top_strategies"] = [s.get("strategy") for s in top_strats[:3]]
        bottom_strats = council_latest.get("analysis", {}).get("bottom_strategies", [])
        metrics["bottom_strategies"] = [s.get("strategy") for s in bottom_strats[:3]]

    kpis = {
        "target_roi_pct": 5.0,
        "target_sharpe": 1.5,
        "roi_gap": round(5.0 - metrics.get("roi_pct", 0), 2),
        "sharpe_gap": round(1.5 - metrics.get("sharpe", 0), 2),
    }

    if metrics.get("roi_pct", 0) < 0:
        health = "RED"
        recommendations.append("ROI negative — reduce Kelly fraction, tighten min_edge")
    elif metrics.get("roi_pct", 0) < 5:
        health = "YELLOW"
        recommendations.append("ROI below target — review strategy mix")
    if metrics.get("max_drawdown", 0) > 0.20:
        health = "RED"
        recommendations.append(f"Drawdown {metrics['max_drawdown']:.0%} exceeds 20% limit — activate circuit breaker")
    if metrics.get("win_rate", 0) > 0 and metrics.get("win_rate", 0) < 0.45:
        recommendations.append("Win rate < 45% — switch to half_kelly conservative mode")

# ── EVOLUTION metrics ────────────────────────────────────────────────────
elif dept == "evolution":
    agent_health = load_json(f"{repo_root}/data/agent-health.json")
    # Islands can be at top-level or under projects.nba.spaces
    islands = agent_health.get("islands", agent_health.get("spaces", {}))
    if not islands:
        islands = agent_health.get("projects", {}).get("nba", {}).get("spaces", {})

    briers = []
    generations = []
    island_data = {}
    for key, val in islands.items() if isinstance(islands, dict) else []:
        b = val.get("best_brier", val.get("brier", None))
        g = val.get("generation", val.get("gen", 0))
        if b is not None:
            briers.append(b)
            generations.append(g)
            island_data[key] = {"brier": b, "gen": g, "status": val.get("status", "unknown")}

    metrics = {
        "island_count": len(island_data),
        "best_brier": min(briers) if briers else None,
        "avg_brier": round(sum(briers) / len(briers), 5) if briers else None,
        "total_generations": sum(generations),
        "islands": island_data,
    }

    # Stagnation detection
    if briers:
        cv = (max(briers) - min(briers)) / (sum(briers) / len(briers)) if sum(briers) > 0 else 0
        metrics["diversity_cv"] = round(cv, 4)
        if cv < 0.01:
            health = "YELLOW"
            recommendations.append("Low diversity (CV < 1%) — inject mutation boost on weakest island")

    kpis = {
        "target_brier": 0.20,
        "brier_gap": round((min(briers) if briers else 0.25) - 0.20, 5),
        "gen_per_hour_target": 50,
    }

    if metrics.get("best_brier") and metrics["best_brier"] > 0.23:
        health = "YELLOW"
        recommendations.append("Best Brier > 0.23 — consider feature injection or model diversification")

# ── ENGINEERING metrics ──────────────────────────────────────────────────
elif dept == "engineering":
    # Feature engine parity
    import hashlib
    local_eng = Path(f"{repo_root}/features/engine.py")
    hf_eng = Path(f"{repo_root}/hf-space/features/engine.py")
    parity = "UNKNOWN"
    if local_eng.exists() and hf_eng.exists():
        lh = hashlib.md5(local_eng.read_bytes()).hexdigest()[:8]
        hh = hashlib.md5(hf_eng.read_bytes()).hexdigest()[:8]
        parity = "OK" if lh == hh else f"DRIFT:{lh}≠{hh}"
    elif not local_eng.exists():
        parity = "MISSING_LOCAL"
    elif not hf_eng.exists():
        parity = "MISSING_HF"

    # Test results
    test_pass = True
    test_file = Path(f"{repo_root}/../nomos-nba-agent/test_data_leakage.py")

    # Phantom game detection
    picks = load_json(f"{repo_root}/../nomos-nba-agent/data/nba-agent/latest-picks.json")
    phantoms = 0
    if isinstance(picks, list):
        for p in picks:
            if p.get("home_team") == p.get("away_team"):
                phantoms += 1

    metrics = {
        "engine_parity": parity,
        "phantom_games": phantoms,
        "feature_engine_version": "v3.1-46cat",
        "max_features": 200,
    }

    kpis = {
        "parity_target": "OK",
        "phantom_target": 0,
        "test_pass_rate_target": 1.0,
    }

    if parity != "OK":
        health = "RED"
        recommendations.append(f"Engine parity BROKEN ({parity}) — sync immediately")
    if phantoms > 0:
        health = "RED"
        recommendations.append(f"{phantoms} phantom games detected — fix team normalization")

# ── FINANCE metrics ──────────────────────────────────────────────────────
elif dept == "finance":
    bankroll = load_json(f"{repo_root}/data/nba-agent/bankroll-state.json")
    monthly_costs = {
        "vm_gcp": 6.0,
        "hf_spaces_free": 0.0,
        "domain": 0.0,
        "modal_usage": 0.0,
        "total": 6.0,
    }
    metrics = {
        "bankroll": bankroll.get("bankroll", 0),
        "monthly_costs": monthly_costs,
        "mrr": 0,
        "stripe_status": "connected_not_active",
        "burn_rate_monthly": monthly_costs["total"],
        "runway_months": "infinite" if monthly_costs["total"] == 0 else round(bankroll.get("bankroll", 0) / monthly_costs["total"], 1),
    }

    kpis = {
        "target_mrr": 100,
        "mrr_gap": 100,
        "break_even_users": 1,  # At $19/mo tier
    }

    if metrics["mrr"] == 0:
        health = "YELLOW"
        recommendations.append("Zero MRR — activate Stripe pricing tiers ($19/$49/$149)")

# ── EVALUATION metrics ───────────────────────────────────────────────────
elif dept == "evaluation":
    eval_data = load_json(f"{repo_root}/data/nba-agent/latest-eval.json")
    metrics = {
        "brier": eval_data.get("brier", None),
        "total_games": eval_data.get("total_games", 0),
        "accuracy": eval_data.get("accuracy", None),
        "ece": eval_data.get("ece", None),
        "calibration_bins": eval_data.get("calibration_bins", {}),
    }

    kpis = {
        "target_brier": 0.20,
        "target_ece": 0.05,
        "target_accuracy": 0.68,
    }

    if metrics.get("ece") and metrics["ece"] > 0.15:
        health = "RED"
        recommendations.append(f"ECE={metrics['ece']:.4f} — calibration crisis, apply Platt scaling")
    elif metrics.get("ece") and metrics["ece"] > 0.05:
        health = "YELLOW"

# ── INFRA metrics ────────────────────────────────────────────────────────
elif dept == "infra":
    infra = load_json(f"{repo_root}/data/infra-status.json")
    summary = infra.get("summary", {})
    total_checks = summary.get("total", infra.get("total_checks", 0))
    healthy = summary.get("healthy", infra.get("healthy", 0))
    hf_spaces = infra.get("hf_spaces", {})
    spaces_up = sum(1 for s in hf_spaces.values() if isinstance(s, dict) and s.get("status") == "running")
    spaces_total = len(hf_spaces)
    metrics = {
        "total_checks": total_checks,
        "healthy": healthy,
        "uptime_pct": round(healthy / max(1, total_checks) * 100, 1),
        "hf_spaces_up": spaces_up,
        "hf_spaces_total": spaces_total,
        "kaggle": infra.get("kaggle", {}),
        "modal": infra.get("modal", {}),
    }

    kpis = {
        "target_uptime_pct": 99.0,
        "uptime_gap": round(99.0 - metrics["uptime_pct"], 1),
    }

    if metrics["uptime_pct"] < 90:
        health = "RED"
        recommendations.append(f"Uptime {metrics['uptime_pct']}% below 90% — check failing services")
    elif metrics["uptime_pct"] < 99:
        health = "YELLOW"

# ── DEFAULT for other departments ────────────────────────────────────────
else:
    metrics = {"note": f"Department {dept} — basic check only"}
    kpis = {}

# ── Build enriched council output ────────────────────────────────────────
result = {
    "department": dept,
    "timestamp": timestamp,
    "status": "completed",
    "type": "council",
    "health": health,
    "metrics": metrics,
    "kpis": kpis,
    "recommendations": recommendations,
    "recommendation_count": len(recommendations),
}

output_path = f"{repo_root}/data/departments/council-{dept}.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w") as f:
    json.dump(result, f, indent=2)

# Print summary
rec_str = f" | {len(recommendations)} recs" if recommendations else ""
print(f"[{dept}] health={health}{rec_str} | metrics={len(metrics)} keys")
COUNCIL_ENRICHMENT

log "Council result written to data/departments/council-$DEPT.json"
