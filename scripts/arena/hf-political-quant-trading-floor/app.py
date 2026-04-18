"""
Nomos42 Political QUANT Trading Floor — HF Space entry point.
Engine lives in engine.py (testable without gradio/fastapi).
This file only adds the FastAPI + Gradio layer + experiment orchestrator.
"""
import gradio as gr
import json
import os
import threading
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

print("=" * 60)
print("NOMOS42 POLITICAL QUANT TRADING FLOOR — STARTUP")
print("=" * 60)
for k in ["CEREBRAS_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_2",
          "OPENROUTER_KEY_ORCHESTRATOR", "MISTRAL_API_KEY",
          "HF_WRITE_TOKEN", "NOMOS_HF_TOKEN", "SPACE_ID"]:
    v = os.environ.get(k, "")
    print(f"  {k}: {'SET (len=' + str(len(v)) + ')' if v else 'NOT SET'}")
print("=" * 60)

# Langfuse (non-blocking)
_langfuse = None
try:
    from langfuse import Langfuse
    _pub, _sec, _host = (os.environ.get(k, "") for k in
                         ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"))
    if _pub and _sec and _host:
        _langfuse = Langfuse(public_key=_pub, secret_key=_sec, host=_host, enabled=True, timeout=5)
        print(f"  LANGFUSE: initialized → {_host}")
except Exception as e:
    print(f"  LANGFUSE: init failed ({e})")

from engine import (
    AGENTS, STARTING_BANKROLL, run_day, set_call_llm, default_call_llm
)
from session_data import load_events, all_days

# Hook langfuse into LLM calls
if _langfuse:
    def _traced_llm(agent, prompt):
        resp = default_call_llm(agent, prompt)
        try:
            _langfuse.trace(name=f"pqtf.{agent['tid']}",
                            input={"prompt_head": prompt[:400]},
                            output={"thesis": (resp or {}).get("thesis", "")[:200]},
                            metadata={"model": agent["model"],
                                      "dt": (resp or {}).get("_llm_seconds")})
        except Exception:
            pass
        return resp
    set_call_llm(_traced_llm)

# Control state
_stop_event = threading.Event()
_running = False
_state: Dict = {}
_lock = threading.Lock()
STATE_PATH = Path("/tmp/pqtf-state.json")
DECISIONS_DIR = Path("/tmp/pqtf-decisions")
DECISIONS_DIR.mkdir(exist_ok=True)

HF_REPO_ID = os.environ.get("SPACE_ID") or "LBJLincoln26/political-quant-trading-floor"
HF_TOKEN = os.environ.get("HF_WRITE_TOKEN") or os.environ.get("NOMOS_HF_TOKEN") or os.environ.get("HF_TOKEN")
try:
    from huggingface_hub import HfApi
    _hub = HfApi(token=HF_TOKEN) if HF_TOKEN else None
except Exception:
    _hub = None


def run_experiment(max_days: Optional[int] = None):
    global _running
    _running = True
    _stop_event.clear()
    try:
        events = load_events("data/political_events.json")
        days = all_days(events)
        date_list = sorted(days.keys())
        if max_days:
            date_list = date_list[:max_days]

        agents_state = {a["tid"]: {"bankroll": STARTING_BANKROLL, "wins": 0, "losses": 0}
                        for a in AGENTS}
        _state["agents"] = agents_state
        _state["started_at"] = datetime.now(timezone.utc).isoformat()
        _state["total_days"] = len(date_list)
        _state["days_done"] = 0

        for d_idx, date in enumerate(date_list):
            if _stop_event.is_set():
                print(f"[exp] stop at day {d_idx}")
                break
            day_log = run_day(agents_state, date, days[date])

            for sess in day_log["sessions"]:
                for pos in sess["positions"]:
                    st = agents_state[pos["tid"]]
                    if pos["pnl"] > 0:
                        st["wins"] += 1
                    elif pos["pnl"] < 0:
                        st["losses"] += 1

            with _lock:
                _state["days_done"] = d_idx + 1
                _state["last_date"] = date
                _state["bankroll_snapshot"] = {tid: s["bankroll"] for tid, s in agents_state.items()}
                day_path = DECISIONS_DIR / f"day-{d_idx:03d}.json"
                day_path.write_text(json.dumps(day_log, indent=2, default=str))
                STATE_PATH.write_text(json.dumps(_state, indent=2, default=str))

            if _hub and (d_idx + 1) % 5 == 0:
                try:
                    _hub.upload_file(path_or_fileobj=str(day_path),
                                     path_in_repo=f"data/decisions/day-{d_idx:03d}.json",
                                     repo_id=HF_REPO_ID, repo_type="space",
                                     commit_message=f"pqtf day-{d_idx:03d}")
                except Exception as e:
                    print(f"[hub] push failed: {e}")

            print(f"[exp] day {d_idx+1}/{len(date_list)} {date}: "
                  f"fleet=${sum(s['bankroll'] for s in agents_state.values()):,.0f} "
                  f"pos={sum(len(s['positions']) for s in day_log['sessions'])}")

        _state["completed_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        print(f"[exp] FATAL: {e}\n{traceback.format_exc()}")
        _state["error"] = str(e)
    finally:
        _running = False
        STATE_PATH.write_text(json.dumps(_state, indent=2, default=str))


# FastAPI
app = FastAPI()

@app.get("/api/status")
def api_status():
    """Pixel-world-compatible shape: `agents` dict keyed by tid with bankroll/wins/losses/total_bets."""
    with _lock:
        live = _state.get("agents") or {}
        agents_flat = {}
        for tid, s in live.items():
            w = s.get("wins", 0); l = s.get("losses", 0)
            agents_flat[tid] = {
                "bankroll": round(s.get("bankroll", STARTING_BANKROLL), 2),
                "wins": w, "losses": l,
                "total_bets": w + l,
                "llm_calls": w + l,  # placeholder — every bet = one LLM call
                "llm_ok": w + l,
            }
        return JSONResponse({
            "running": _running,
            "days_processed": _state.get("days_done", 0),
            "days_total": _state.get("total_days", 50),
            "games_processed": 0, "games_total": 0,  # N/A for quant
            "agents": agents_flat,
            "config_agents": AGENTS,
            "starting_bankroll": STARTING_BANKROLL,
            "session_structure": {"s1": "09:30-12:00", "s2": "12:00-14:30",
                                  "s3": "14:30-16:00", "s4": "16:00-20:00"},
            "cooperation_pacts_count": 0,  # tallied per-session, not surfaced here yet
            "axelrod_strategies": {},
            "sacrificial_assignments": {},
            "reputation": {},
            "langfuse_active": _langfuse is not None,
            "hub_push_active": _hub is not None,
            "last_date": _state.get("last_date", ""),
            "error": _state.get("error"),
        })

@app.post("/api/run")
async def api_run(request: Request):
    global _running
    if _running:
        return JSONResponse({"error": "already running"}, status_code=409)
    try:
        body = await request.json()
    except Exception:
        body = {}
    max_days = body.get("max_days")
    threading.Thread(target=run_experiment, kwargs={"max_days": max_days}, daemon=True).start()
    return JSONResponse({"started": True, "max_days": max_days})

@app.post("/api/stop")
def api_stop():
    _stop_event.set()
    return JSONResponse({"stopping": True})

@app.get("/api/leaderboard")
def api_leaderboard():
    with _lock:
        if "agents" not in _state:
            return JSONResponse({"agents": []})
        ranked = sorted(
            [(tid, s["bankroll"], s.get("wins", 0), s.get("losses", 0))
             for tid, s in _state["agents"].items()],
            key=lambda x: -x[1])
        return JSONResponse({"agents": [
            {"tid": t, "bankroll": round(b, 2), "wins": w, "losses": l,
             "wr": round(w / max(1, w + l), 3)}
            for t, b, w, l in ranked]})


# Gradio UI
def ui_status():
    with _lock:
        running = "🟢 running" if _running else "⚪ idle"
        if "agents" not in _state:
            return f"{running}\nNo experiment data. POST /api/run or click Start."
        ranked = sorted(_state["agents"].items(), key=lambda x: -x[1]["bankroll"])
        lines = [f"{running}  day {_state.get('days_done', 0)}/{_state.get('total_days', '?')}"]
        lines.append(f"last: {_state.get('last_date', '-')}")
        lines.append("")
        for tid, s in ranked:
            lines.append(f"  {tid:16} ${s['bankroll']:>10,.0f}   W:{s.get('wins',0)} L:{s.get('losses',0)}")
        return "\n".join(lines)


def ui_start(max_days):
    global _running
    if _running:
        return "already running"
    try:
        md = int(max_days) if max_days else None
    except Exception:
        md = None
    threading.Thread(target=run_experiment, kwargs={"max_days": md}, daemon=True).start()
    return f"started (max_days={md})"


def ui_stop():
    _stop_event.set()
    return "stop signal sent"


with gr.Blocks(title="Nomos42 Political Quant TF") as demo:
    gr.Markdown("# 🏛️ Nomos42 Political QUANT Trading Floor")
    gr.Markdown("6 LLM agents × 4 intraday sessions × options derivatives on sector ETFs")
    with gr.Row():
        max_days_in = gr.Number(label="max_days (blank=all 50)", value=None, precision=0)
        start_btn = gr.Button("▶️ Start")
        stop_btn = gr.Button("⏹ Stop")
        refresh_btn = gr.Button("🔄 Refresh")
    status_out = gr.Textbox(label="Status", lines=12, interactive=False)

    start_btn.click(ui_start, [max_days_in], [status_out])
    stop_btn.click(ui_stop, [], [status_out])
    refresh_btn.click(ui_status, [], [status_out])
    demo.load(ui_status, [], [status_out])

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
