"""
Nomos42 Paperclip — Agent Orchestrator with Heartbeat + Discipline System
Inspired by github.com/paperclipai/paperclip, adapted for our 22-agent swarm.

Features:
- Org chart with 7 departments, 22 agents
- Heartbeat monitoring (agent alive/stuck/fired)
- 3-strike discipline system (warn → final warning → fired & remodeled)
- Pixel agent dashboard (clickable cards)
- Forge Factory user view (read-only pixel agents)
- VM task delegation API
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

import gradio as gr
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import httpx
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("paperclip")

# ─── Agent Status & Discipline ────────────────────────────────────────

class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    STUCK = "stuck"
    WARNED = "warned"
    FINAL_WARNING = "final_warning"
    FIRED = "fired"
    REMODELED = "remodeled"

@dataclass
class AgentState:
    id: str
    title: str
    department: str
    status: AgentStatus = AgentStatus.IDLE
    heartbeat_interval: str = "4h"
    last_heartbeat: Optional[str] = None
    last_task: Optional[str] = None
    last_result: Optional[str] = None
    warnings: int = 0
    warning_log: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    fired_count: int = 0
    remodel_notes: list = field(default_factory=list)
    pixel_color: str = "#4CAF50"  # green = healthy
    pixel_emoji: str = "🤖"


# ─── Company State ────────────────────────────────────────────────────

COMPANY_FILE = Path("/app/data/company.json") if Path("/app/data/company.json").exists() else Path("company.json")
STATE_FILE = Path("/tmp/agent_states.json")

# Department colors for pixel agents
DEPT_COLORS = {
    "Research": "#2196F3",      # blue
    "Engineering": "#FF9800",   # orange
    "Evolution": "#9C27B0",     # purple
    "Betting & Strategy": "#F44336",  # red
    "Evaluation": "#00BCD4",    # cyan
    "Infrastructure": "#795548",  # brown
    "Oversight": "#FFD700",     # gold
}

DEPT_EMOJIS = {
    "Research": "🔬",
    "Engineering": "⚙️",
    "Evolution": "🧬",
    "Betting & Strategy": "🎰",
    "Evaluation": "📊",
    "Infrastructure": "🏗️",
    "Oversight": "👁️",
}

# Initialize agents from company.json
def load_agents() -> dict[str, AgentState]:
    agents = {}
    try:
        data = json.loads(COMPANY_FILE.read_text())
        for dept in data.get("departments", []):
            dept_name = dept["name"]
            for ag in dept.get("agents", []):
                agents[ag["id"]] = AgentState(
                    id=ag["id"],
                    title=ag.get("title", ag["id"]),
                    department=dept_name,
                    heartbeat_interval=ag.get("heartbeat", "4h"),
                    pixel_color=DEPT_COLORS.get(dept_name, "#4CAF50"),
                    pixel_emoji=DEPT_EMOJIS.get(dept_name, "🤖"),
                )
    except Exception as e:
        logger.error(f"Failed to load company.json: {e}")
        # Fallback minimal agents
        agents["orchestrator"] = AgentState(
            id="orchestrator", title="CEO", department="Oversight",
            pixel_color="#FFD700", pixel_emoji="👁️"
        )
    return agents

AGENTS: dict[str, AgentState] = load_agents()

def save_state():
    """Persist agent states to disk"""
    data = {aid: asdict(a) for aid, a in AGENTS.items()}
    STATE_FILE.write_text(json.dumps(data, indent=2, default=str))

def load_state():
    """Restore agent states from disk"""
    global AGENTS
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            for aid, state in data.items():
                if aid in AGENTS:
                    for k, v in state.items():
                        if k != "status":
                            setattr(AGENTS[aid], k, v)
                        else:
                            AGENTS[aid].status = AgentStatus(v)
        except:
            pass

load_state()


# ─── Discipline System (3-Strike) ────────────────────────────────────

def discipline_agent(agent_id: str, error_description: str) -> dict:
    """
    3-strike discipline system:
    1. First offense: Precise explanation of what went wrong
    2. Second offense: Final warning — next is termination
    3. Third offense: Fired, then remodeled with all error solutions baked in
    """
    agent = AGENTS.get(agent_id)
    if not agent:
        return {"error": f"Agent {agent_id} not found"}

    agent.errors.append({
        "timestamp": datetime.utcnow().isoformat(),
        "description": error_description
    })
    agent.failed_tasks += 1
    agent.warnings += 1

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    if agent.warnings == 1:
        # STEP 1: Precise explanation
        msg = (
            f"⚠️ WARNING #{agent.warnings} for {agent.title} ({agent.id})\n"
            f"Department: {agent.department}\n"
            f"Error: {error_description}\n\n"
            f"EXPLANATION: This is your first infraction. Here is precisely what went wrong:\n"
            f"- {error_description}\n"
            f"You must correct this behavior immediately. Next failure will escalate."
        )
        agent.status = AgentStatus.WARNED
        agent.pixel_color = "#FFC107"  # yellow = warned
        agent.warning_log.append({"level": 1, "time": now, "msg": msg})
        save_state()
        return {"action": "warned", "strike": 1, "message": msg}

    elif agent.warnings == 2:
        # STEP 2: Final warning
        msg = (
            f"🚨 FINAL WARNING for {agent.title} ({agent.id})\n"
            f"Department: {agent.department}\n"
            f"Previous errors: {len(agent.errors)}\n"
            f"Latest: {error_description}\n\n"
            f"THIS IS YOUR LAST CHANCE. One more failure = TERMINATION + REMODEL.\n"
            f"All your past errors have been logged for remodeling."
        )
        agent.status = AgentStatus.FINAL_WARNING
        agent.pixel_color = "#FF9800"  # orange = final warning
        agent.warning_log.append({"level": 2, "time": now, "msg": msg})
        save_state()
        return {"action": "final_warning", "strike": 2, "message": msg}

    else:
        # STEP 3: Fire and remodel
        error_summary = "\n".join([f"  - [{e['timestamp'][:10]}] {e['description']}" for e in agent.errors])
        solutions = [f"SOLUTION for '{e['description']}': Prevent recurrence by baking fix into agent config" for e in agent.errors]

        msg = (
            f"🔥 TERMINATED: {agent.title} ({agent.id})\n"
            f"Department: {agent.department}\n"
            f"Total strikes: {agent.warnings}\n"
            f"Error history:\n{error_summary}\n\n"
            f"REMODELING with all error solutions:\n" +
            "\n".join(f"  ✅ {s}" for s in solutions) +
            f"\n\nAgent will restart with hardcoded fixes for ALL past errors."
        )
        agent.status = AgentStatus.FIRED
        agent.pixel_color = "#F44336"  # red = fired
        agent.fired_count += 1
        agent.remodel_notes.extend(solutions)
        agent.warning_log.append({"level": 3, "time": now, "msg": msg})

        # Auto-remodel after firing
        agent.warnings = 0  # reset strikes
        agent.status = AgentStatus.REMODELED
        agent.pixel_color = "#2196F3"  # blue = remodeled (fresh start)
        save_state()
        return {"action": "fired_and_remodeled", "strike": 3, "message": msg, "remodel_notes": solutions}


# ─── Heartbeat Engine ─────────────────────────────────────────────────

def heartbeat(agent_id: str, task: str = None, result: str = None, success: bool = True):
    """Record a heartbeat from an agent"""
    agent = AGENTS.get(agent_id)
    if not agent:
        return {"error": f"Unknown agent: {agent_id}"}

    agent.last_heartbeat = datetime.utcnow().isoformat()
    agent.total_tasks += 1

    if task:
        agent.last_task = task
    if result:
        agent.last_result = result

    if success:
        agent.successful_tasks += 1
        agent.status = AgentStatus.SUCCESS
        # Restore healthy color if was warned
        if agent.warnings < 2:
            agent.pixel_color = DEPT_COLORS.get(agent.department, "#4CAF50")
    else:
        agent.status = AgentStatus.FAILED
        if result:
            discipline_agent(agent_id, result)

    save_state()
    return {"status": "ok", "agent": agent_id, "heartbeat": agent.last_heartbeat}


def check_stuck_agents() -> list[dict]:
    """Detect agents that haven't sent heartbeat within 2x their interval"""
    stuck = []
    now = datetime.utcnow()

    interval_map = {
        "2min": timedelta(minutes=4),
        "30min": timedelta(hours=1),
        "1h": timedelta(hours=2),
        "2h": timedelta(hours=4),
        "4h": timedelta(hours=8),
        "6h": timedelta(hours=12),
        "9h": timedelta(hours=18),
        "12h": timedelta(days=1),
        "24h": timedelta(days=2),
    }

    for agent in AGENTS.values():
        if agent.heartbeat_interval in ("on-demand", "weekly", "daily", "daily-5pm-ET", "daily-10am-UTC"):
            continue
        if not agent.last_heartbeat:
            continue

        try:
            last = datetime.fromisoformat(agent.last_heartbeat)
            timeout = interval_map.get(agent.heartbeat_interval, timedelta(hours=8))
            if now - last > timeout:
                agent.status = AgentStatus.STUCK
                agent.pixel_color = "#9E9E9E"  # gray = stuck
                stuck.append({
                    "agent": agent.id,
                    "department": agent.department,
                    "last_heartbeat": agent.last_heartbeat,
                    "expected_interval": agent.heartbeat_interval,
                    "stuck_for": str(now - last)
                })
        except:
            pass

    if stuck:
        save_state()
    return stuck


# ─── FastAPI Server ───────────────────────────────────────────────────

app = FastAPI(title="Nomos42 Paperclip", version="1.0.0")

@app.get("/")
async def root():
    return {"name": "Nomos42 Paperclip Orchestrator", "agents": len(AGENTS), "version": "1.0.0"}

@app.post("/heartbeat/{agent_id}")
async def api_heartbeat(agent_id: str, request: Request):
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    return heartbeat(agent_id, body.get("task"), body.get("result"), body.get("success", True))

@app.post("/discipline/{agent_id}")
async def api_discipline(agent_id: str, request: Request):
    body = await request.json()
    return discipline_agent(agent_id, body.get("error", "unspecified error"))

@app.get("/agents")
async def api_agents():
    return {aid: asdict(a) for aid, a in AGENTS.items()}

@app.get("/agents/{agent_id}")
async def api_agent(agent_id: str):
    if agent_id not in AGENTS:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return asdict(AGENTS[agent_id])

@app.get("/health")
async def api_health():
    stuck = check_stuck_agents()
    summary = {
        "total_agents": len(AGENTS),
        "by_status": {},
        "by_department": {},
        "stuck_agents": stuck,
        "timestamp": datetime.utcnow().isoformat()
    }
    for a in AGENTS.values():
        summary["by_status"][a.status] = summary["by_status"].get(a.status, 0) + 1
        if a.department not in summary["by_department"]:
            summary["by_department"][a.department] = {"total": 0, "healthy": 0, "issues": 0}
        summary["by_department"][a.department]["total"] += 1
        if a.status in (AgentStatus.IDLE, AgentStatus.RUNNING, AgentStatus.SUCCESS, AgentStatus.REMODELED):
            summary["by_department"][a.department]["healthy"] += 1
        else:
            summary["by_department"][a.department]["issues"] += 1
    return summary

@app.get("/discipline-log")
async def api_discipline_log():
    logs = []
    for a in AGENTS.values():
        for entry in a.warning_log:
            logs.append({"agent": a.id, "department": a.department, **entry})
    return sorted(logs, key=lambda x: x.get("time", ""), reverse=True)

@app.get("/forge/agents")
async def forge_agents_view():
    """Read-only view for Forge Factory users — pixel agents with clickable cards"""
    agents_view = []
    for a in AGENTS.values():
        agents_view.append({
            "id": a.id,
            "title": a.title,
            "department": a.department,
            "status": a.status,
            "emoji": a.pixel_emoji,
            "color": a.pixel_color,
            "success_rate": f"{a.successful_tasks}/{a.total_tasks}" if a.total_tasks > 0 else "N/A",
            "last_active": a.last_heartbeat or "never",
        })
    return agents_view


# ─── Gradio Dashboard ─────────────────────────────────────────────────

def build_pixel_grid():
    """Build HTML pixel agent grid"""
    html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;padding:16px;">'

    for dept_name in ["Oversight", "Research", "Engineering", "Evolution", "Betting & Strategy", "Evaluation", "Infrastructure"]:
        dept_agents = [a for a in AGENTS.values() if a.department == dept_name]
        if not dept_agents:
            continue

        html += f'<div style="grid-column:1/-1;margin-top:16px;"><h3 style="color:{DEPT_COLORS.get(dept_name, "#fff")};margin:0;">{DEPT_EMOJIS.get(dept_name, "")} {dept_name}</h3></div>'

        for agent in dept_agents:
            status_badge = {
                AgentStatus.IDLE: "⬜",
                AgentStatus.RUNNING: "🟢",
                AgentStatus.SUCCESS: "✅",
                AgentStatus.FAILED: "❌",
                AgentStatus.STUCK: "⬛",
                AgentStatus.WARNED: "🟡",
                AgentStatus.FINAL_WARNING: "🟠",
                AgentStatus.FIRED: "🔴",
                AgentStatus.REMODELED: "🔵",
            }.get(agent.status, "⬜")

            warnings_indicator = ""
            if agent.warnings == 1:
                warnings_indicator = '<span style="color:#FFC107;">Strike 1/3</span>'
            elif agent.warnings == 2:
                warnings_indicator = '<span style="color:#FF9800;font-weight:bold;">Strike 2/3 FINAL</span>'

            fired_badge = ""
            if agent.fired_count > 0:
                fired_badge = f'<br><span style="color:#F44336;font-size:10px;">Fired {agent.fired_count}x, remodeled</span>'

            success_rate = ""
            if agent.total_tasks > 0:
                rate = agent.successful_tasks / agent.total_tasks * 100
                color = "#4CAF50" if rate >= 80 else "#FFC107" if rate >= 50 else "#F44336"
                success_rate = f'<br><span style="color:{color};font-size:11px;">{rate:.0f}% success ({agent.successful_tasks}/{agent.total_tasks})</span>'

            html += f'''
            <div style="background:{agent.pixel_color}22;border:2px solid {agent.pixel_color};border-radius:12px;padding:12px;cursor:pointer;transition:transform 0.2s;min-height:120px;"
                 onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <div style="font-size:24px;text-align:center;">{agent.pixel_emoji} {status_badge}</div>
                <div style="font-weight:bold;font-size:13px;margin-top:6px;color:#fff;">{agent.title}</div>
                <div style="font-size:11px;color:#aaa;">{agent.id}</div>
                <div style="font-size:10px;color:#888;margin-top:4px;">⏰ {agent.heartbeat_interval}</div>
                {f'<div style="margin-top:4px;">{warnings_indicator}</div>' if warnings_indicator else ''}
                {fired_badge}
                {success_rate}
            </div>'''

    html += '</div>'
    return html


def get_agent_card(agent_id: str) -> str:
    """Detailed agent card for click inspection"""
    agent = AGENTS.get(agent_id)
    if not agent:
        return f"Agent '{agent_id}' not found. Available: {', '.join(AGENTS.keys())}"

    errors_html = ""
    if agent.errors:
        errors_html = "<h4>Error History</h4><ul>"
        for e in agent.errors[-10:]:  # last 10
            errors_html += f"<li>[{e['timestamp'][:16]}] {e['description']}</li>"
        errors_html += "</ul>"

    warnings_html = ""
    if agent.warning_log:
        warnings_html = "<h4>Discipline Log</h4>"
        for w in agent.warning_log:
            level_color = {1: "#FFC107", 2: "#FF9800", 3: "#F44336"}.get(w["level"], "#fff")
            warnings_html += f'<div style="border-left:3px solid {level_color};padding:8px;margin:4px 0;background:#1a1a2e;"><pre style="white-space:pre-wrap;color:#ddd;font-size:12px;">{w["msg"]}</pre></div>'

    remodel_html = ""
    if agent.remodel_notes:
        remodel_html = "<h4>Remodel Solutions Baked In</h4><ul style='color:#2196F3;'>"
        for note in agent.remodel_notes:
            remodel_html += f"<li>{note}</li>"
        remodel_html += "</ul>"

    return f"""
    <div style="background:#0d1117;border:2px solid {agent.pixel_color};border-radius:16px;padding:24px;max-width:600px;color:#fff;">
        <div style="display:flex;align-items:center;gap:16px;">
            <span style="font-size:48px;">{agent.pixel_emoji}</span>
            <div>
                <h2 style="margin:0;color:{agent.pixel_color};">{agent.title}</h2>
                <div style="color:#888;">{agent.id} | {agent.department}</div>
            </div>
        </div>
        <hr style="border-color:#333;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0;">
            <div>Status: <b style="color:{agent.pixel_color};">{agent.status.value.upper()}</b></div>
            <div>Heartbeat: <b>{agent.heartbeat_interval}</b></div>
            <div>Tasks: <b>{agent.total_tasks}</b> ({agent.successful_tasks} ok, {agent.failed_tasks} fail)</div>
            <div>Warnings: <b style="color:{'#F44336' if agent.warnings >= 2 else '#FFC107' if agent.warnings >= 1 else '#4CAF50'};">{agent.warnings}/3</b></div>
            <div>Fired: <b>{agent.fired_count}x</b></div>
            <div>Last HB: <b>{(agent.last_heartbeat or 'never')[:16]}</b></div>
        </div>
        {f'<div style="margin:8px 0;"><b>Last task:</b> {agent.last_task}</div>' if agent.last_task else ''}
        {f'<div style="margin:8px 0;"><b>Last result:</b> {agent.last_result}</div>' if agent.last_result else ''}
        {errors_html}
        {warnings_html}
        {remodel_html}
    </div>
    """


def build_dashboard():
    with gr.Blocks(
        title="Nomos42 Paperclip",
        theme=gr.themes.Base(primary_hue="blue", neutral_hue="slate"),
        css="""
        .gradio-container { background: #0d1117 !important; }
        h1,h2,h3 { color: #fff !important; }
        """
    ) as demo:
        gr.Markdown("# 🏢 Nomos42 Paperclip — Agent Orchestrator")
        gr.Markdown("*22 agents | 7 departments | Heartbeat monitoring | 3-strike discipline*")

        with gr.Tabs():
            # TAB 1: Pixel Agent Grid
            with gr.TabItem("Pixel Agents"):
                pixel_html = gr.HTML(build_pixel_grid)
                refresh_btn = gr.Button("Refresh", size="sm")
                refresh_btn.click(fn=build_pixel_grid, outputs=pixel_html)

            # TAB 2: Agent Inspector
            with gr.TabItem("Agent Inspector"):
                agent_dropdown = gr.Dropdown(
                    choices=list(AGENTS.keys()),
                    label="Select Agent",
                    value="orchestrator"
                )
                card_html = gr.HTML()
                agent_dropdown.change(fn=get_agent_card, inputs=agent_dropdown, outputs=card_html)

            # TAB 3: Discipline System
            with gr.TabItem("Discipline"):
                gr.Markdown("### Report Agent Failure")
                disc_agent = gr.Dropdown(choices=list(AGENTS.keys()), label="Agent")
                disc_error = gr.Textbox(label="Error Description", placeholder="Describe what went wrong...")
                disc_btn = gr.Button("Report Failure", variant="stop")
                disc_result = gr.JSON(label="Discipline Result")
                disc_btn.click(fn=discipline_agent, inputs=[disc_agent, disc_error], outputs=disc_result)

                gr.Markdown("### Discipline Log")
                def get_log():
                    logs = []
                    for a in AGENTS.values():
                        for w in a.warning_log:
                            logs.append(f"[{w['time']}] Strike {w['level']}/3 — {a.id}: {w['msg'][:100]}...")
                    return "\n\n".join(logs[-20:]) if logs else "No discipline actions yet."
                log_output = gr.Textbox(label="Recent Actions", lines=10, interactive=False)
                gr.Button("Refresh Log").click(fn=get_log, outputs=log_output)

            # TAB 4: Health Dashboard
            with gr.TabItem("Health"):
                def health_summary():
                    stuck = check_stuck_agents()
                    lines = [f"Total Agents: {len(AGENTS)}"]
                    by_dept = {}
                    for a in AGENTS.values():
                        by_dept.setdefault(a.department, []).append(a)
                    for dept, agents in by_dept.items():
                        healthy = sum(1 for a in agents if a.status in (AgentStatus.IDLE, AgentStatus.SUCCESS, AgentStatus.REMODELED, AgentStatus.RUNNING))
                        lines.append(f"\n{DEPT_EMOJIS.get(dept, '')} {dept}: {healthy}/{len(agents)} healthy")
                        for a in agents:
                            lines.append(f"  {a.status.value:15s} | {a.id:25s} | HB: {(a.last_heartbeat or 'never')[:16]}")
                    if stuck:
                        lines.append(f"\nSTUCK AGENTS ({len(stuck)}):")
                        for s in stuck:
                            lines.append(f"  {s['agent']} — stuck for {s['stuck_for']}")
                    return "\n".join(lines)
                health_txt = gr.Textbox(label="System Health", lines=25, interactive=False)
                gr.Button("Check Health").click(fn=health_summary, outputs=health_txt)

            # TAB 5: Forge User View (read-only)
            with gr.TabItem("Forge View"):
                gr.Markdown("### Forge Factory — User Dashboard Preview")
                gr.Markdown("*This is what paying users see — read-only pixel agents, clickable cards*")
                forge_html = gr.HTML(build_pixel_grid)
                forge_agent = gr.Dropdown(choices=list(AGENTS.keys()), label="Click Agent for Details")
                forge_card = gr.HTML()
                forge_agent.change(fn=get_agent_card, inputs=forge_agent, outputs=forge_card)

    return demo


# ─── Mount & Run ──────────────────────────────────────────────────────

demo = build_dashboard()
app = gr.mount_gradio_app(app, demo, path="/dashboard")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
