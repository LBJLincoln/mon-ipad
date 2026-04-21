#!/bin/bash
# Monitor NBA + POL + ITF live TFs — snapshot every 3 min, append JSONL + human log.
set -u
LOG_DIR="/home/termius/mon-ipad/data/ops/tf-monitor"
mkdir -p "$LOG_DIR"
JSONL="$LOG_DIR/monitor-$(date -u +%Y-%m-%d).jsonl"
HUMAN="$LOG_DIR/monitor-$(date -u +%Y-%m-%d).log"

probe() {
  local name="$1" url="$2"
  local ts body
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  body=$(curl -sS --max-time 10 "$url/api/status" 2>/dev/null || echo '{}')
  python3 - "$name" "$ts" "$body" <<'PY' 2>>"$HUMAN"
import json, sys, datetime
name, ts, body = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.loads(body) if body else {}
except Exception:
    d = {}
row = {"ts": ts, "fleet": name, "running": d.get("running"), "stopped": d.get("stopped")}
if name == "NBA":
    row["day"] = d.get("days_processed"); row["total"] = d.get("days_total")
    row["fleet_best"] = d.get("fleet_best_bankroll"); row["leader"] = d.get("fleet_leader")
    row["llm_calls"] = d.get("llm_calls"); row["fail"] = d.get("llm_failures")
    row["pacts"] = d.get("cooperation_pacts_count"); row["rogue"] = d.get("rogue_events_total")
elif name == "POL":
    row["day"] = d.get("days_processed"); row["total"] = d.get("days_total")
    row["fleet_best"] = d.get("fleet_best_bankroll"); row["leader"] = d.get("fleet_leader")
    row["llm_calls"] = d.get("llm_calls"); row["fail"] = d.get("llm_failures")
    row["pacts"] = d.get("cooperation_pacts_count")
elif name == "ITF":
    row["tick"] = d.get("tick"); row["positions"] = d.get("open_positions")
    row["cash"] = d.get("cash_total"); row["equity"] = d.get("fleet_equity")
    row["llm_calls"] = d.get("llm_calls"); row["fail"] = d.get("llm_failures")
print(json.dumps(row))
# Human-readable
compact = " ".join(f"{k}={v}" for k,v in row.items() if v is not None and k not in ("ts","fleet"))
sys.stderr.write(f"[{ts}] {name:3s} {compact}\n")
PY
}

while true; do
  {
    probe NBA https://lbjlincoln26-nba-llm-trading-floor.hf.space
    probe POL https://lbjlincoln26-political-llm-trading-floor.hf.space
    probe ITF https://lbjlincoln26-intraday-trading-floor.hf.space
  } >> "$JSONL" 2>>"$HUMAN"
  # roll JSONL/log name at UTC midnight automatically via date-suffix
  JSONL="$LOG_DIR/monitor-$(date -u +%Y-%m-%d).jsonl"
  HUMAN="$LOG_DIR/monitor-$(date -u +%Y-%m-%d).log"
  sleep 180
done
