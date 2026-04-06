#!/usr/bin/env python3
"""
Nomos42 Department Council Space
=================================
Runs a Karpathy autoresearch loop using HF Router free LLM inference.
No GPU. No paid APIs. Pure CPU + HTTP.

Loop pattern:
  SCAN -> THINK (LLM) -> DECIDE -> ACT -> LOG -> repeat every N minutes

Parameterized by DEPT_ID, DEPT_NAME, DEPT_MISSION env vars (HF Space secrets).
"""

import os
import json
import time
import threading
import urllib.request
import urllib.error
import ssl
import random
from datetime import datetime, timezone
from pathlib import Path
import gradio as gr

# -- Configuration ------------------------------------------------------------

DEPT_ID = os.environ.get("DEPT_ID", "d0")
DEPT_NAME = os.environ.get("DEPT_NAME", "unknown")
DEPT_MISSION = os.environ.get("DEPT_MISSION", "Run a Karpathy autoresearch loop.")
LOOP_INTERVAL_MINUTES = int(os.environ.get("LOOP_INTERVAL_MINUTES", "30"))
PREFERRED_MODEL = os.environ.get("PREFERRED_MODEL", "")

# Per-department optimal model assignments
# Format: {dept_id: (provider_key, model_id, display_name)}
DEPT_MODEL_MAP = {
    "d1": ("hf",         "Qwen/Qwen3.5-397B-A17B",               "hf/qwen3.5-397b"),            # 397B MoE for deep research
    "d2": ("hf",         "Qwen/Qwen3.5-27B",                     "hf/qwen3.5-27b"),             # Code analysis
    "d3": ("hf",         "google/gemma-4-31B-it",                 "hf/gemma4-31b"),              # Evolution decisions
    "d4": ("hf",         "google/gemma-4-26B-A4B-it",             "hf/gemma4-26b-a4b"),          # Product reasoning
    "d5": ("hf",         "deepseek-ai/DeepSeek-R1",               "hf/deepseek-r1"),             # Strategic reasoning
    "d6": ("hf",         "Qwen/Qwen3.5-35B-A3B",                 "hf/qwen3.5-35b"),             # Statistical validation
    "d7": ("hf",         "meta-llama/Llama-4-Scout-17B-16E-Instruct", "hf/llama4-scout"),        # Fast infra checks
    "d8": ("hf",         "Qwen/Qwen3-235B-A22B-Instruct-2507",   "hf/qwen3-235b"),              # Financial analysis
    "d9": ("hf",         "Qwen/Qwen3.5-397B-A17B",               "hf/qwen3.5-397b"),            # Cross-repo (big context)
}

# HF token -- automatically available in HF Spaces, or set as secret
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Optional: external LLM API keys (set as HF Space secrets)
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Optional: VM endpoint to push actions to
VM_API_URL = os.environ.get("VM_API_URL", "")

# -- State ---------------------------------------------------------------------

state = {
    "dept_id": DEPT_ID,
    "dept_name": DEPT_NAME,
    "status": "STARTING",
    "iteration": 0,
    "last_run": None,
    "last_action": None,
    "last_decision": None,
    "last_llm": None,
    "metrics": {},
    "history": [],
    "errors": [],
}

_lock = threading.Lock()

# -- SSL -----------------------------------------------------------------------

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# -- LLM Inference (multi-provider with fallback) -----------------------------

def _build_provider(name, url, auth_header, model_id, prompt, max_tokens, temperature, extra_headers=None):
    """Build a provider dict for the fallback chain."""
    headers = {"Authorization": auth_header, "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    return {
        "name": name,
        "url": url,
        "headers": headers,
        "payload": {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        },
    }


def _call_llm(prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> tuple:
    """Try providers in priority order, with dept-preferred model first.
    Returns (response_text, provider_name)."""

    # Build all available providers
    all_providers = {}

    if HF_TOKEN:
        # Use dept-preferred model on HF Router if available, else fallback to Qwen3.5
        hf_model = "Qwen/Qwen3.5-27B"
        dept_pref_check = DEPT_MODEL_MAP.get(DEPT_ID)
        if dept_pref_check and dept_pref_check[0] == "hf":
            hf_model = dept_pref_check[1]
        all_providers["hf"] = _build_provider(
            f"hf-router/{hf_model.split('/')[-1]}",
            "https://router.huggingface.co/v1/chat/completions",
            f"Bearer {HF_TOKEN}",
            hf_model,
            prompt, max_tokens, temperature,
        )

    if CEREBRAS_API_KEY:
        all_providers["cerebras"] = _build_provider(
            "cerebras/qwen3-235b",
            "https://api.cerebras.ai/v1/chat/completions",
            f"Bearer {CEREBRAS_API_KEY}",
            "qwen-3-235b-a22b-instruct-2507",
            prompt, max_tokens, temperature,
        )

    if GROQ_API_KEY:
        all_providers["groq"] = _build_provider(
            "groq/llama4-scout",
            "https://api.groq.com/openai/v1/chat/completions",
            f"Bearer {GROQ_API_KEY}",
            "meta-llama/llama-4-scout-17b-16e-instruct",
            prompt, max_tokens, temperature,
        )

    if OPENROUTER_API_KEY:
        all_providers["openrouter"] = _build_provider(
            "openrouter/auto-free",
            "https://openrouter.ai/api/v1/chat/completions",
            f"Bearer {OPENROUTER_API_KEY}",
            "openrouter/auto:free",
            prompt, max_tokens, temperature,
            extra_headers={
                "HTTP-Referer": "https://nomos42.com",
                "X-Title": f"Nomos42 Dept Council {DEPT_ID.upper()}",
            },
        )

    # Determine preferred model for this department
    dept_pref = DEPT_MODEL_MAP.get(DEPT_ID)
    if PREFERRED_MODEL and ":" in PREFERRED_MODEL:
        parts = PREFERRED_MODEL.split(":", 1)
        dept_pref = (parts[0], parts[1], PREFERRED_MODEL)

    # Build ordered provider list: preferred first, then all others as fallback
    providers = []
    preferred_key = None

    if dept_pref:
        prov_key, model_id, display = dept_pref
        preferred_key = prov_key

        # Build the preferred provider with its specific model
        if prov_key == "cerebras" and CEREBRAS_API_KEY:
            providers.append(_build_provider(
                display, "https://api.cerebras.ai/v1/chat/completions",
                f"Bearer {CEREBRAS_API_KEY}", model_id,
                prompt, max_tokens, temperature,
            ))
        elif prov_key == "groq" and GROQ_API_KEY:
            providers.append(_build_provider(
                display, "https://api.groq.com/openai/v1/chat/completions",
                f"Bearer {GROQ_API_KEY}", model_id,
                prompt, max_tokens, temperature,
            ))
        elif prov_key == "openrouter" and OPENROUTER_API_KEY:
            providers.append(_build_provider(
                display, "https://openrouter.ai/api/v1/chat/completions",
                f"Bearer {OPENROUTER_API_KEY}", model_id,
                prompt, max_tokens, temperature,
                extra_headers={
                    "HTTP-Referer": "https://nomos42.com",
                    "X-Title": f"Nomos42 Dept Council {DEPT_ID.upper()}",
                },
            ))

    # Add remaining providers as fallback (skip the preferred one to avoid duplicate)
    default_order = ["hf", "cerebras", "groq", "openrouter"]
    for key in default_order:
        if key != preferred_key and key in all_providers:
            providers.append(all_providers[key])

    # Try each provider
    errors = []
    for p in providers:
        try:
            data = json.dumps(p["payload"]).encode("utf-8")
            req = urllib.request.Request(
                p["url"], data=data, method="POST", headers=p["headers"]
            )
            with urllib.request.urlopen(req, timeout=90, context=_ssl_ctx()) as resp:
                result = json.loads(resp.read())
                choices = result.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        return content.strip(), p["name"]
        except Exception as e:
            errors.append(f"{p['name']}: {e}")
            continue

    return f"[ALL PROVIDERS FAILED: {'; '.join(errors)}]", "none"

# -- Scan: read public HF Space status ----------------------------------------

def _scan_spaces() -> dict:
    """Fetch status from the 6 NBA evolution islands (public API, no auth)."""
    islands = {
        "S10": "https://nomos42-nba-quant.hf.space/api/status",
        "S11": "https://nomos42-nba-quant-2.hf.space/api/status",
        "S12": "https://nomos42-nba-evo-3.hf.space/api/status",
        "S13": "https://nomos42-nba-evo-4.hf.space/api/status",
        "S14": "https://nomos42-nba-evo-5.hf.space/api/status",
        "S15": "https://nomos42-nba-evo-6.hf.space/api/status",
    }
    results = {}
    for name, url in islands.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42Council/1.0"})
            with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
                results[name] = json.loads(resp.read())
        except Exception as e:
            results[name] = {"error": str(e)[:100]}
    return results

# -- Department-specific prompts -----------------------------------------------

DEPT_PROMPTS = {
    "d1": """You are the RESEARCH department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE concrete research action for the next 5 minutes.
Output ONLY valid JSON (no markdown, no explanation outside the JSON):
{{"action": "string (one of: propose_feature, propose_calibration, write_proposal, scan_paper)", "description": "1 sentence max", "priority": "high|medium|low", "reasoning": "2 sentences max"}}""",

    "d2": """You are the ENGINEERING department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE concrete engineering action for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: add_feature, fix_bug, optimize_code, verify_parity)", "description": "1 sentence max", "target_file": "features/engine.py or other", "priority": "high|medium|low", "reasoning": "2 sentences max"}}""",

    "d3": """You are the EVOLUTION department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE GA parameter tweak or cross-pollination action.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: tune_mutation, tune_features, cross_pollinate, restart_island)", "island": "S10|S11|S12|S13|S14|S15", "parameter": "mut_rate|feat_count|pop_size", "new_value": "number", "reasoning": "2 sentences max"}}""",

    "d4": """You are the PRODUCT department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE product improvement for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: update_dashboard, improve_bot, add_metric_display, fix_ui)", "product": "dashboard|telegram|bloomberg", "description": "1 sentence max", "priority": "high|medium|low"}}""",

    "d5": """You are the BUSINESS department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE business/betting action for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: review_bankroll, adjust_kelly, analyze_roi, report_metrics)", "description": "1 sentence max", "priority": "high|medium|low", "expected_impact": "1 sentence"}}""",

    "d6": """You are the EVALUATION department AI for Nomos42 NBA quant AI.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE evaluation/audit action for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: check_calibration, audit_predictions, verify_brier, flag_anomaly)", "description": "1 sentence max", "priority": "high|medium|low", "metric_to_check": "brier|logloss|ece|sharpe"}}""",

    "d7": """You are the INFRA department AI for Nomos42.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE infra action for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: restart_island, check_cron, verify_keepalive, check_vm)", "target": "S10|S11|S12|S13|S14|S15|vm|cron", "description": "1 sentence max", "urgency": "critical|high|low"}}""",

    "d8": """You are the FINANCE department AI for Nomos42.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE financial tracking action for the next 5 minutes.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: compute_roi, track_bankroll, project_burn, report_pnl)", "description": "1 sentence max", "period": "daily|weekly|monthly", "priority": "high|medium|low"}}""",

    "d9": """You are the CROSS-REPO department AI for Nomos42.
Mission: {mission}
Current fleet status:
{context}

Your task: Propose ONE cross-repo sync/audit action.
Output ONLY valid JSON (no markdown):
{{"action": "string (one of: verify_engine_parity, sync_features, audit_crons, update_docs)", "repos": ["mon-ipad", "nomos-nba-agent"], "description": "1 sentence max", "priority": "high|medium|low"}}""",
}

def _build_prompt(scan_data: dict) -> str:
    template = DEPT_PROMPTS.get(DEPT_ID, DEPT_PROMPTS["d1"])
    context = json.dumps(scan_data, indent=2)[:3000]
    return template.format(context=context, mission=DEPT_MISSION)

# -- Act: execute the decided action -------------------------------------------

def _act(decision: dict) -> str:
    """Lightweight action executor. Returns status string."""
    action = decision.get("action", "")

    if VM_API_URL:
        try:
            payload = json.dumps({
                "dept": DEPT_ID,
                "action": decision,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }).encode("utf-8")
            req = urllib.request.Request(
                f"{VM_API_URL}/api/council-action",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
                result = json.loads(resp.read())
                return f"Forwarded to VM: {result.get('status', 'ok')}"
        except Exception as e:
            return f"VM forward failed: {e} -- logged locally"

    return f"Logged: {action} (VM endpoint not configured)"

# -- Main loop -----------------------------------------------------------------

def run_iteration() -> dict:
    """Run one full SCAN -> THINK -> DECIDE -> ACT -> LOG cycle."""
    ts_start = time.time()

    with _lock:
        state["status"] = "SCANNING"

    scan_data = _scan_spaces()

    with _lock:
        state["status"] = "THINKING"

    prompt = _build_prompt(scan_data)
    llm_response, provider = _call_llm(prompt)

    # Parse JSON decision
    decision = {}
    try:
        clean = llm_response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
        # Try to extract JSON from response
        if "{" in clean:
            start = clean.index("{")
            end = clean.rindex("}") + 1
            clean = clean[start:end]
        decision = json.loads(clean)
    except Exception:
        decision = {"action": "noop", "error": "LLM parse failed", "raw": llm_response[:300]}

    action_result = _act(decision)
    elapsed = round(time.time() - ts_start, 1)

    record = {
        "iteration": state["iteration"] + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scan_summary": {},
        "decision": decision,
        "action_result": action_result,
        "llm_provider": provider,
        "elapsed_seconds": elapsed,
    }

    # Build scan summary safely
    for k, v in scan_data.items():
        if isinstance(v, dict):
            record["scan_summary"][k] = v.get("best_brier") or v.get("generation") or v.get("error", "?")
        else:
            record["scan_summary"][k] = str(v)[:50]

    with _lock:
        state["iteration"] += 1
        state["status"] = "IDLE"
        state["last_run"] = record["timestamp"]
        state["last_action"] = action_result
        state["last_decision"] = decision.get("action", "?")
        state["last_llm"] = provider
        state["history"] = ([record] + state["history"])[:50]

    # Retrospective JSONL logging (ephemeral on HF, durable via VM council-api)
    _append_iteration_log(record)

    return record


COUNCIL_LOG_PATH = Path("/tmp/council-iterations.jsonl")

def _append_iteration_log(record: dict):
    """Append iteration record to JSONL for retrospective analysis."""
    log_entry = {
        "timestamp": record["timestamp"],
        "dept_id": DEPT_ID,
        "dept_name": DEPT_NAME,
        "iteration": record["iteration"],
        "model_used": record["llm_provider"],
        "decision": record.get("decision", {}).get("action", "unknown"),
        "decision_full": record.get("decision", {}),
        "action_taken": record["action_result"],
        "elapsed_seconds": record["elapsed_seconds"],
        "scan_summary": record.get("scan_summary", {}),
    }
    try:
        with open(COUNCIL_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        pass

def _loop_worker():
    """Background thread: run iterations on schedule with startup jitter."""
    # Random jitter to avoid thundering herd across 9 spaces
    jitter = random.randint(10, LOOP_INTERVAL_MINUTES * 30)
    print(f"[{DEPT_ID.upper()}] Starting loop with {jitter}s jitter...")
    time.sleep(jitter)

    while True:
        try:
            record = run_iteration()
            print(f"[{DEPT_ID.upper()}] Iteration #{record['iteration']} "
                  f"action={record['decision'].get('action', '?')} "
                  f"provider={record['llm_provider']} "
                  f"elapsed={record['elapsed_seconds']}s")
        except Exception as e:
            with _lock:
                state["status"] = "ERROR"
                state["last_action"] = f"Loop error: {e}"
                state["errors"].append({
                    "time": datetime.now(timezone.utc).isoformat(),
                    "error": str(e)[:200],
                })
                state["errors"] = state["errors"][-10:]
            print(f"[{DEPT_ID.upper()}] Loop error: {e}")
        time.sleep(LOOP_INTERVAL_MINUTES * 60)

# -- Gradio UI -----------------------------------------------------------------

def get_status_display():
    with _lock:
        s = dict(state)
    hist = s.pop("history", [])
    errs = s.pop("errors", [])

    providers_str = "HF Router (Qwen2.5-72B)"
    if CEREBRAS_API_KEY:
        providers_str += " + Cerebras"
    if GROQ_API_KEY:
        providers_str += " + Groq"
    if OPENROUTER_API_KEY:
        providers_str += " + OpenRouter"

    last_run = s.get('last_run') or 'Never'
    last_decision = s.get('last_decision') or '-'
    last_action = (s.get('last_action') or '-')[:80]
    last_llm = s.get('last_llm') or '-'

    status_text = f"""## {s['dept_id'].upper()}: {s['dept_name'].upper()} COUNCIL

| Field | Value |
|-------|-------|
| **Status** | {s['status']} |
| **Iteration** | {s['iteration']} |
| **Last Run** | {last_run} |
| **Last Decision** | {last_decision} |
| **Last Action** | {last_action} |
| **LLM Provider** | {last_llm} |
| **Loop Interval** | {LOOP_INTERVAL_MINUTES} min |
| **Available Providers** | {providers_str} |

---
### Mission
{DEPT_MISSION}

---
### Last 10 Iterations
"""
    if not hist:
        status_text += "\n*No iterations yet. First iteration will run after startup jitter.*\n"
    else:
        for rec in hist[:10]:
            decision = rec.get("decision", {})
            action = decision.get("action", "?")
            desc = (decision.get("description") or decision.get("reasoning") or "")[:60]
            elapsed = rec.get("elapsed_seconds", "?")
            status_text += (
                f"\n- **#{rec['iteration']}** `{rec['timestamp'][:19]}Z` "
                f"| `{action}` | {desc} | {rec.get('llm_provider', '?')} | {elapsed}s"
            )

    if errs:
        status_text += "\n\n---\n### Recent Errors\n"
        for e in errs[-3:]:
            status_text += f"\n- `{e['time'][:19]}Z` {e['error'][:100]}"

    return status_text

def trigger_iteration():
    try:
        record = run_iteration()
        decision = record["decision"]
        return (
            f"Iteration #{record['iteration']} complete.\n"
            f"Action: {decision.get('action', '?')}\n"
            f"Description: {decision.get('description', decision.get('reasoning', 'N/A'))}\n"
            f"Provider: {record['llm_provider']}\n"
            f"Elapsed: {record['elapsed_seconds']}s"
        )
    except Exception as e:
        return f"Error: {e}"

def get_history_json():
    with _lock:
        hist = list(state["history"])
    return json.dumps(hist, indent=2)

def get_status_json():
    """API-friendly JSON status."""
    with _lock:
        s = dict(state)
    s["history"] = s["history"][:5]  # Trim for API
    return json.dumps(s, indent=2)

# -- Build Gradio app ----------------------------------------------------------

with gr.Blocks(
    title=f"Nomos42 {DEPT_ID.upper()}: {DEPT_NAME.title()} Council",
    theme=gr.themes.Monochrome(),
) as demo:
    gr.Markdown(
        f"# Nomos42 -- {DEPT_ID.upper()}: {DEPT_NAME.upper()} Council\n"
        f"*Autonomous Karpathy autoresearch loop | Free LLM inference | CPU-only*"
    )

    with gr.Row():
        with gr.Column(scale=2):
            status_md = gr.Markdown(get_status_display())
            with gr.Row():
                refresh_btn = gr.Button("Refresh Status", size="sm")
                trigger_btn = gr.Button("Trigger Iteration Now", variant="primary", size="sm")
            trigger_output = gr.Textbox(label="Trigger Result", lines=5)

        with gr.Column(scale=1):
            gr.Markdown("### API Status (JSON)")
            status_json = gr.Code(label="Status JSON", language="json", value=get_status_json())
            status_json_btn = gr.Button("Refresh JSON", size="sm")

            gr.Markdown("### Iteration History")
            history_json = gr.Code(label="History (JSON)", language="json")
            history_btn = gr.Button("Load History", size="sm")

    refresh_btn.click(get_status_display, outputs=[status_md])
    trigger_btn.click(trigger_iteration, outputs=[trigger_output])
    history_btn.click(get_history_json, outputs=[history_json])
    status_json_btn.click(get_status_json, outputs=[status_json])

# -- Startup -------------------------------------------------------------------

if __name__ == "__main__":
    thread = threading.Thread(target=_loop_worker, daemon=True)
    thread.start()
    print(f"[{DEPT_ID.upper()}] Council space starting. Mission: {DEPT_MISSION}")
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )
