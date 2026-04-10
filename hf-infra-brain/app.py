"""
Nomos42 Infra Brain — HF Space Delegated Compute
Always-on FastAPI server with:
- Task delegation from VM (POST /task)
- Gemini 2.5 Flash for free LLM calls (1500 req/day)
- APScheduler crons (research, health checks, data fetch)
- MCP connectors (Supabase, Neo4j)
- Health dashboard (GET /)
"""

import os
import json
import time
import hashlib
import asyncio
import httpx
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import gradio as gr
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

# ── Config ──
VM_IP = os.environ.get("VM_IP", "34.136.180.66")
VM_TOKEN = os.environ.get("VM_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
AUTH_TOKEN = os.environ.get("INFRA_AUTH_TOKEN", "")
DATA_DIR = Path("/tmp/infra-brain")
DATA_DIR.mkdir(exist_ok=True)

# ── State ──
state = {
    "started": datetime.now(timezone.utc).isoformat(),
    "tasks_received": 0,
    "tasks_completed": 0,
    "tasks_failed": 0,
    "gemini_calls": 0,
    "last_health_check": None,
    "hf_spaces": {},
    "task_log": [],
    "cron_runs": [],
}

# ══════════════════════════════════════════════════════════════
# GEMINI FREE LLM
# ══════════════════════════════════════════════════════════════

async def gemini_call(prompt: str, max_tokens: int = 4096) -> str:
    """Free Gemini 2.5 Flash call (1500 req/day, 1M tokens/min)"""
    if not GEMINI_KEY:
        return "ERROR: GEMINI_API_KEY not set"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens}
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            state["gemini_calls"] += 1
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"GEMINI_ERROR: {e}"

# ══════════════════════════════════════════════════════════════
# HF SPACES HEALTH CHECK
# ══════════════════════════════════════════════════════════════

SPACES = {
    "S10": "nomos42-nba-quant",
    "S11": "nomos42-nba-quant-2",
    "S12": "nomos42-nba-evo-3",
    "S13": "nomos42-nba-evo-4",
    "S14": "nomos42-nba-evo-5",
    "S15": "nomos42-nba-evo-6",
}

async def check_all_spaces():
    """Check health of all 6 HF evolution islands"""
    results = {}
    async with httpx.AsyncClient(timeout=10) as client:
        for sid, url in SPACES.items():
            try:
                resp = await client.get(f"https://{url}.hf.space/api/status")
                if resp.status_code == 200:
                    data = resp.json()
                    results[sid] = {
                        "status": "UP",
                        "brier": data.get("best_brier", "?"),
                        "gen": data.get("generation", "?"),
                        "model": data.get("best_model", "?"),
                    }
                else:
                    results[sid] = {"status": f"HTTP_{resp.status_code}"}
            except Exception as e:
                results[sid] = {"status": "DOWN", "error": str(e)[:100]}

    state["hf_spaces"] = results
    state["last_health_check"] = datetime.now(timezone.utc).isoformat()

    # Save to file
    (DATA_DIR / "spaces-health.json").write_text(json.dumps(results, indent=2))
    return results

# ══════════════════════════════════════════════════════════════
# VM COMMUNICATION
# ══════════════════════════════════════════════════════════════

async def vm_exec(command: str) -> dict:
    """Execute a command on the VM via terminal API"""
    if not VM_TOKEN:
        return {"error": "VM_TOKEN not set"}

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"http://{VM_IP}:8081/exec",
                json={"command": command, "token": VM_TOKEN},
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

async def vm_health() -> dict:
    """Check VM health"""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            resp = await client.get(f"http://{VM_IP}:8081/health")
            return resp.json()
        except Exception:
            return {"status": "unreachable"}

# ══════════════════════════════════════════════════════════════
# SUPABASE CONNECTOR
# ══════════════════════════════════════════════════════════════

async def supabase_query(table: str, select: str = "*", limit: int = 10) -> list:
    """Query Supabase REST API"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return [{"error": "Supabase not configured"}]

    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&limit={limit}&order=created_at.desc"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(url, headers=headers)
            return resp.json()
        except Exception as e:
            return [{"error": str(e)}]

# ══════════════════════════════════════════════════════════════
# TASK DELEGATION API
# ══════════════════════════════════════════════════════════════

task_queue = asyncio.Queue()

async def process_task(task: dict) -> dict:
    """Process a delegated task"""
    task_type = task.get("type", "gemini")
    prompt = task.get("prompt", "")
    task_id = task.get("id", hashlib.md5(prompt.encode()).hexdigest()[:8])

    result = {"id": task_id, "type": task_type, "timestamp": datetime.now(timezone.utc).isoformat()}

    try:
        if task_type == "gemini":
            result["output"] = await gemini_call(prompt)
        elif task_type == "health_check":
            result["output"] = await check_all_spaces()
        elif task_type == "vm_exec":
            result["output"] = await vm_exec(prompt)
        elif task_type == "supabase":
            table = task.get("table", "experiments")
            result["output"] = await supabase_query(table, limit=task.get("limit", 10))
        elif task_type == "research":
            # Use Gemini for research with NBA context
            context = "You are an NBA quant research analyst. Our best Brier score is 0.21570 (TabICL). "
            context += "We have 6 HF Spaces running tree-based evolution. Target: Brier < 0.20, ROI > 5%.\n\n"
            result["output"] = await gemini_call(context + prompt, max_tokens=8192)
        else:
            result["output"] = f"Unknown task type: {task_type}"

        result["status"] = "completed"
        state["tasks_completed"] += 1
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        state["tasks_failed"] += 1

    # Keep last 50 tasks in log
    state["task_log"].append(result)
    state["task_log"] = state["task_log"][-50:]

    return result

# ══════════════════════════════════════════════════════════════
# SCHEDULED CRON JOBS
# ══════════════════════════════════════════════════════════════

async def cron_health_check():
    """Every 5 minutes: check all HF spaces"""
    results = await check_all_spaces()
    down = [k for k, v in results.items() if v.get("status") != "UP"]
    if down:
        # Alert via Gemini analysis
        await gemini_call(f"HF Spaces DOWN: {down}. Suggest recovery steps.")
    state["cron_runs"].append({"job": "health_check", "time": datetime.now(timezone.utc).isoformat(), "down": down})
    state["cron_runs"] = state["cron_runs"][-100:]

async def cron_research_scan():
    """Every 6 hours: scan for new research papers"""
    prompt = """Search for the latest NBA prediction research papers from 2026.
    Focus on: calibration, Brier score optimization, feature engineering, ensemble methods.
    List top 3 papers with title, authors, key insight, and applicability to NBA game prediction.
    Our current approach: tree ensemble (extra_trees, xgboost, lightgbm, catboost, random_forest)
    with 6211 features across 43 categories. Best Brier: 0.21570."""

    result = await gemini_call(prompt, max_tokens=4096)

    # Save to file
    scan_file = DATA_DIR / f"research-scan-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.json"
    scan_file.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "result": result}, indent=2))

    state["cron_runs"].append({"job": "research_scan", "time": datetime.now(timezone.utc).isoformat()})

async def cron_vm_sync():
    """Every 30 minutes: sync status with VM"""
    vm = await vm_health()
    state["vm_status"] = vm

    # Push our health data to VM
    if vm.get("status") == "ok":
        health_data = json.dumps({
            "infra_brain": {
                "status": "UP",
                "tasks": state["tasks_completed"],
                "gemini_calls": state["gemini_calls"],
                "spaces": state["hf_spaces"],
                "last_check": state["last_health_check"],
            }
        })
        await vm_exec(f"echo '{health_data}' > /home/lahargnedebartoli/mon-ipad/data/infra-brain-status.json")

    state["cron_runs"].append({"job": "vm_sync", "time": datetime.now(timezone.utc).isoformat()})

async def cron_odds_analysis():
    """Every 4 hours: analyze betting value with Gemini"""
    # Read latest odds from VM
    odds_result = await vm_exec("cat /home/lahargnedebartoli/mon-ipad/data/nba-agent/odds-latest.json 2>/dev/null | head -200")
    if "output" in odds_result:
        prompt = f"""Analyze these NBA odds for value bets. Compare lines across bookmakers.
        Focus on: ML, spreads, totals. Flag any line that differs >3% from consensus.
        Our edge is strongest on UNDER bets and H1_ATS_AWAY.

        Odds data:
        {odds_result['output'][:3000]}

        Output: JSON with {{game, bet_type, bookmaker, edge_pct, recommendation}}"""

        result = await gemini_call(prompt, max_tokens=4096)
        (DATA_DIR / "value-analysis.json").write_text(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "analysis": result
        }, indent=2))

    state["cron_runs"].append({"job": "odds_analysis", "time": datetime.now(timezone.utc).isoformat()})

# ══════════════════════════════════════════════════════════════
# FASTAPI + GRADIO
# ══════════════════════════════════════════════════════════════

app = FastAPI()

def verify_auth(request: Request):
    """Verify auth token"""
    if not AUTH_TOKEN:
        return True  # No auth configured
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    return token == AUTH_TOKEN

@app.post("/task")
async def receive_task(request: Request):
    """Receive a task from VM or external caller"""
    if not verify_auth(request):
        raise HTTPException(status_code=403, detail="Invalid token")

    task = await request.json()
    state["tasks_received"] += 1
    result = await process_task(task)
    return JSONResponse(result)

@app.get("/api/status")
async def api_status():
    """Full status for dashboard integration"""
    return JSONResponse({
        "service": "infra-brain",
        "status": "UP",
        "uptime_since": state["started"],
        "tasks": {
            "received": state["tasks_received"],
            "completed": state["tasks_completed"],
            "failed": state["tasks_failed"],
        },
        "gemini_calls": state["gemini_calls"],
        "hf_spaces": state["hf_spaces"],
        "last_health_check": state["last_health_check"],
        "vm_status": state.get("vm_status", {}),
        "recent_crons": state["cron_runs"][-10:],
        "recent_tasks": state["task_log"][-5:],
    })

@app.get("/api/spaces")
async def api_spaces():
    """Current HF spaces status"""
    return JSONResponse(state["hf_spaces"])

@app.get("/api/tasks")
async def api_tasks():
    """Recent task log"""
    return JSONResponse(state["task_log"][-20:])

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "service": "infra-brain"})

# ── Gradio Dashboard ──

def build_dashboard():
    """Build Gradio dashboard"""

    def get_status():
        spaces_md = "## HF Evolution Islands\n\n"
        spaces_md += "| Island | Status | Brier | Gen | Model |\n|--------|--------|-------|-----|-------|\n"
        for sid, info in state.get("hf_spaces", {}).items():
            if isinstance(info, dict):
                spaces_md += f"| {sid} | {info.get('status', '?')} | {info.get('brier', '?')} | {info.get('gen', '?')} | {info.get('model', '?')} |\n"

        infra_md = f"""## Infra Brain Status

- **Uptime since:** {state['started']}
- **Tasks:** {state['tasks_completed']}/{state['tasks_received']} completed ({state['tasks_failed']} failed)
- **Gemini calls:** {state['gemini_calls']}
- **Last health check:** {state.get('last_health_check', 'never')}
- **VM status:** {state.get('vm_status', {}).get('status', 'unknown')}
"""

        crons_md = "## Recent Cron Runs\n\n"
        for c in state.get("cron_runs", [])[-10:]:
            crons_md += f"- `{c.get('job')}` at {c.get('time', '?')}\n"

        return spaces_md + "\n" + infra_md + "\n" + crons_md

    async def run_task(task_type, prompt):
        task = {"type": task_type, "prompt": prompt}
        result = await process_task(task)
        return json.dumps(result, indent=2)

    def sync_run_task(task_type, prompt):
        return asyncio.get_event_loop().run_until_complete(run_task(task_type, prompt))

    with gr.Blocks(title="Nomos42 Infra Brain", theme=gr.themes.Monochrome()) as demo:
        gr.Markdown("# Nomos42 Infra Brain\n> Delegated compute hub — 16GB RAM, Gemini Flash, cron jobs")

        with gr.Tab("Dashboard"):
            status_output = gr.Markdown(get_status)
            refresh_btn = gr.Button("Refresh Status")
            refresh_btn.click(fn=get_status, outputs=status_output)

        with gr.Tab("Task Runner"):
            task_type = gr.Dropdown(
                choices=["gemini", "research", "health_check", "vm_exec", "supabase"],
                value="gemini",
                label="Task Type"
            )
            prompt_input = gr.Textbox(label="Prompt / Command", lines=3)
            run_btn = gr.Button("Execute Task")
            task_output = gr.Code(label="Result", language="json")
            run_btn.click(fn=sync_run_task, inputs=[task_type, prompt_input], outputs=task_output)

        with gr.Tab("Spaces Health"):
            async def refresh_spaces():
                results = await check_all_spaces()
                return json.dumps(results, indent=2)

            spaces_output = gr.Code(language="json")
            check_btn = gr.Button("Check All Spaces Now")
            check_btn.click(fn=lambda: asyncio.get_event_loop().run_until_complete(refresh_spaces()), outputs=spaces_output)

    return demo

# ── Startup ──

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup():
    # Schedule cron jobs
    scheduler.add_job(cron_health_check, IntervalTrigger(minutes=5), id="health_check")
    scheduler.add_job(cron_vm_sync, IntervalTrigger(minutes=30), id="vm_sync")
    scheduler.add_job(cron_research_scan, CronTrigger(hour="*/6"), id="research_scan")
    scheduler.add_job(cron_odds_analysis, CronTrigger(hour="*/4"), id="odds_analysis")
    scheduler.start()

    # Initial health check
    await check_all_spaces()
    print(f"Infra Brain started at {state['started']}")
    print(f"Crons: health(5m), vm_sync(30m), research(6h), odds(4h)")

# Mount Gradio
demo = build_dashboard()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
