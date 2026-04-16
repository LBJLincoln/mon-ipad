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

# Nomos42 LLM gateway (20 models, auto-fallback). Councils call this first;
# the gateway handles provider selection + rate-limit routing. Per-dept model
# IDs below must exist in scripts/arena/hf-llm-gateway/app.py MODELS dict.
GATEWAY_URL = os.environ.get("GATEWAY_URL", "https://lbjlincoln26-llm-gateway.hf.space").rstrip("/")

DEPT_GATEWAY_MAP = {
    "d1": "cerebras:qwen-3-235b",     # Research — best reasoning, 235B params
    "d2": "cerebras:llama3.1-8b",     # Engineering — fast code
    "d3": "cerebras:qwen-3-235b",     # Evolution — analytical
    "d4": "mistral:medium",           # Product — ensemble, balanced
    "d5": "selfhost:gemma-4-e2b",     # Business — local CPU (Gemma-4 native JSON, Apr 2026)
    "d6": "cerebras:qwen-3-235b",     # Evaluation — best reasoning (stays cloud)
    "d7": "cerebras:llama3.1-8b",     # Infra — fast + reliable
    "d8": "selfhost:qwen3-4b",        # Finance — local CPU (Qwen3-4B reasoning, no quota)
    "d9": "selfhost:phi-4-mini",      # Cross-repo — local CPU (Phi-4-mini 128K ctx, MIT)
}

# Legacy HF-Router map kept only as fallback if the gateway is fully down.
DEPT_MODEL_MAP = {
    "d1": ("hf",         "Qwen/Qwen2.5-72B-Instruct",            "hf/qwen2.5-72b"),
    "d2": ("hf",         "Qwen/Qwen2.5-Coder-32B-Instruct",      "hf/qwen2.5-coder-32b"),
    "d3": ("hf",         "Qwen/Qwen2.5-72B-Instruct",            "hf/qwen2.5-72b"),
    "d4": ("hf",         "Qwen/Qwen2.5-Coder-32B-Instruct",      "hf/qwen2.5-coder-32b"),
    "d5": ("hf",         "meta-llama/Meta-Llama-3-8B-Instruct",   "hf/llama3-8b"),
    "d6": ("hf",         "Qwen/Qwen2.5-72B-Instruct",            "hf/qwen2.5-72b"),
    "d7": ("hf",         "meta-llama/Meta-Llama-3-8B-Instruct",   "hf/llama3-8b"),
    "d8": ("hf",         "Qwen/Qwen2.5-Coder-32B-Instruct",      "hf/qwen2.5-coder-32b"),
    "d9": ("hf",         "Qwen/Qwen2.5-72B-Instruct",            "hf/qwen2.5-72b"),
}

# HF token -- try multiple env var names (HF_TOKEN may be reserved on Spaces)
HF_TOKEN = os.environ.get("NOMOS_HF_TOKEN", "") or os.environ.get("HF_TOKEN", "") or os.environ.get("HF_TOKEN_3", "")

# Debug: log which token sources are available at startup
_token_sources = []
if os.environ.get("NOMOS_HF_TOKEN"): _token_sources.append("NOMOS_HF_TOKEN")
if os.environ.get("HF_TOKEN"): _token_sources.append("HF_TOKEN")
if os.environ.get("HF_TOKEN_3"): _token_sources.append("HF_TOKEN_3")
print(f"[COUNCIL] HF_TOKEN sources: {_token_sources}, len={len(HF_TOKEN)}")

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


def _call_gateway(prompt: str, max_tokens: int, temperature: float) -> tuple:
    """Call the Nomos42 LLM gateway (20-model proxy) with the dept-preferred model.
    Returns (content, provider_name) or (None, None) on failure."""
    model = DEPT_GATEWAY_MAP.get(DEPT_ID, "cerebras:qwen-3-235b")
    try:
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{GATEWAY_URL}/api/chat",
            data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Nomos42Council/1.0"},
        )
        # 180s timeout: selfhost CPU inference (Phi-3.5 / Qwen3-4B / Gemma-2-2B)
        # takes 20-60s per call; cloud providers respond <5s. Gateway internal
        # fallback chain kicks in after model-level timeouts, not this socket.
        with urllib.request.urlopen(req, timeout=180, context=_ssl_ctx()) as resp:
            result = json.loads(resp.read())
            content = result.get("content") or result.get("message", {}).get("content") or ""
            if content:
                return content.strip(), f"gateway/{model}"
    except Exception:
        pass
    return None, None


def _call_llm(prompt: str, max_tokens: int = 500, temperature: float = 0.3) -> tuple:
    """Try gateway first, then providers in priority order.
    Returns (response_text, provider_name)."""

    # 1. Try Nomos42 gateway first (20 models, automatic fallback)
    gw_content, gw_name = _call_gateway(prompt, max_tokens, temperature)
    if gw_content:
        return gw_content, gw_name

    # Build all available providers (legacy fallback)
    all_providers = {}

    if HF_TOKEN:
        # Use dept-preferred model on HF Router if available, else fallback to Qwen3.5
        hf_model = "Qwen/Qwen3.5-27B"
        dept_pref_check = DEPT_MODEL_MAP.get(DEPT_ID)
        if dept_pref_check and dept_pref_check[0] == "hf":
            hf_model = dept_pref_check[1]
        all_providers["hf"] = _build_provider(
            f"hf/{hf_model.split('/')[-1]}",
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
        if prov_key == "hf" and HF_TOKEN:
            providers.append(_build_provider(
                display, "https://router.huggingface.co/v1/chat/completions",
                f"Bearer {HF_TOKEN}", model_id,
                prompt, max_tokens, temperature,
            ))
        elif prov_key == "cerebras" and CEREBRAS_API_KEY:
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
    if not providers:
        key_status = f"HF={len(HF_TOKEN)>0}, CEREBRAS={len(CEREBRAS_API_KEY)>0}, GROQ={len(GROQ_API_KEY)>0}, OR={len(OPENROUTER_API_KEY)>0}"
        return f"[NO PROVIDERS CONFIGURED: {key_status}]", "none"

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
    """Fetch live status from ALL running experiments: 13 NBA islands + 8 political
    islands + 2 LLM trading floors. Councils now audit every real experiment, not
    just the first 6 (was a real gap flagged 2026-04-16)."""
    endpoints = {
        # NBA evolution islands (13 total: S10–S22)
        "S10": "https://nomos42-nba-quant.hf.space/api/status",
        "S11": "https://nomos42-nba-quant-2.hf.space/api/status",
        "S12": "https://nomos42-nba-evo-3.hf.space/api/status",
        "S13": "https://nomos42-nba-evo-4.hf.space/api/status",
        "S14": "https://nomos42-nba-evo-5.hf.space/api/status",
        "S15": "https://nomos42-nba-evo-6.hf.space/api/status",
        "S16": "https://lbjlincoln26-nba-evo-s16.hf.space/api/status",
        "S17": "https://lbjlincoln26-nba-evo-s17.hf.space/api/status",
        "S18": "https://testforge42-nba-evo-s18.hf.space/api/status",
        "S19": "https://testforge42-nba-evo-s19.hf.space/api/status",
        "S20": "https://lbjlincoln26-nba-evo-s20.hf.space/api/status",
        "S21": "https://lbjlincoln26-nba-evo-s21.hf.space/api/status",
        "S22": "https://testforge42-nba-evo-s22.hf.space/api/status",
        # Political evolution islands (8 total: P1–P8)
        "P1": "https://nomos42-political-alpha.hf.space/api/status",
        "P2": "https://nomos42-political-alpha-2.hf.space/api/status",
        "P3": "https://lbjlincoln-political-alpha-3.hf.space/api/status",
        "P4": "https://lbjlincoln-political-alpha-4.hf.space/api/status",
        "P5": "https://lbjlincoln-political-alpha-5.hf.space/api/status",
        "P6": "https://lbjlincoln-political-alpha-6.hf.space/api/status",
        "P7": "https://lbjlincoln-political-alpha-7.hf.space/api/status",
        "P8": "https://lbjlincoln-political-alpha-8.hf.space/api/status",
        # LLM Trading Floors (the meta-experiments — 12 NBA / 10 political agents)
        "TF-NBA": "https://lbjlincoln26-nba-llm-trading-floor.hf.space/api/status",
        "TF-POL": "https://lbjlincoln26-political-llm-trading-floor.hf.space/api/status",
    }
    results = {}
    for name, url in endpoints.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Nomos42Council/1.0"})
            with urllib.request.urlopen(req, timeout=8, context=_ssl_ctx()) as resp:
                results[name] = json.loads(resp.read())
        except Exception as e:
            results[name] = {"error": str(e)[:100]}
    return results


# -- Live arXiv feed per department (real, not hardcoded) ---------------------

DEPT_ARXIV_QUERIES = {
    "d1": "(cat:cs.LG OR cat:stat.ML) AND (all:%22Brier+score%22 OR all:%22probability+calibration%22 OR all:%22isotonic+regression%22 OR all:%22Venn-Abers%22 OR all:TabPFN)",
    "d2": "(cat:cs.SE OR cat:cs.LG) AND (all:%22feature+engineering%22 OR all:%22tabular+learning%22 OR all:AutoML)",
    "d3": "(cat:cs.NE OR cat:cs.AI) AND (all:%22evolutionary+algorithm%22 OR all:%22genetic+algorithm%22 OR all:%22darwinian%22 OR all:%22island+model%22)",
    "d4": "(cat:cs.HC) AND (all:dashboard OR all:%22information+design%22 OR all:%22data+visualization%22 OR all:%22social+media+engagement%22)",
    "d5": "(cat:q-fin.PM OR cat:q-fin.TR OR cat:econ.GN) AND (all:%22Kelly+criterion%22 OR all:%22optimal+pricing%22 OR all:%22customer+acquisition%22 OR all:SaaS)",
    "d6": "(cat:cs.LG OR cat:stat.ME) AND (all:%22model+audit%22 OR all:%22calibration+error%22 OR all:%22backtest%22 OR all:%22combinatorial+purged%22)",
    "d7": "(cat:cs.DC OR cat:cs.SE) AND (all:%22MLOps%22 OR all:%22uptime%22 OR all:%22model+serving%22 OR all:Kubernetes)",
    "d8": "(cat:q-fin.RM OR cat:q-fin.PM) AND (all:%22risk+management%22 OR all:%22Monte+Carlo%22 OR all:%22value+at+risk%22 OR all:%22Sharpe+ratio%22)",
    "d9": "(cat:cs.SE) AND (all:%22monorepo%22 OR all:%22cross-repo%22 OR all:%22code+parity%22 OR all:%22schema+migration%22)",
}

def _fetch_dept_papers(dept_id: str, max_results: int = 5) -> list:
    """Fetch the NEWEST arXiv papers matching this dept's domain.
    Real, live, not hardcoded. Returns list of {title, summary, url, published}."""
    query = DEPT_ARXIV_QUERIES.get(dept_id, DEPT_ARXIV_QUERIES["d1"])
    url = (
        f"https://export.arxiv.org/api/query?search_query={query}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Nomos42Council/1.0"})
        with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx()) as resp:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.read())
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            out = []
            for entry in root.findall("atom:entry", ns):
                t = entry.find("atom:title", ns)
                s = entry.find("atom:summary", ns)
                p = entry.find("atom:published", ns)
                l = entry.find("atom:id", ns)
                out.append({
                    "title": (t.text or "").strip().replace("\n", " ")[:200],
                    "summary": (s.text or "").strip().replace("\n", " ")[:400],
                    "published": (p.text or "")[:10],
                    "url": (l.text or ""),
                })
            return out
    except Exception:
        return []

# -- Department-specific prompts -----------------------------------------------

DEPT_PROMPTS = {
    "d1": """You are the D1 RESEARCH department head for Nomos42 NBA quant AI.
Niche: probability calibration, tabular SOTA (TabPFN/TabICL), Brier < 0.20 hunting.
Mission: {mission}

Fleet status:
{context}

Latest arXiv papers in your niche (FRESH, pulled live):
{papers}

Your job: pick ONE paper above and propose applying its core technique to our 21 evolution islands.
Output ONLY valid JSON:
{{"action": "propose_feature|propose_calibration|write_proposal|scan_paper", "paper_url": "arxiv url from list above or empty", "technique": "the concrete technique to try", "target_island": "S10..S22", "expected_brier_delta": "-0.001|-0.002|-0.005", "reasoning": "2 sentences"}}""",

    "d2": """You are the D2 ENGINEERING department head for Nomos42.
Niche: features/engine.py parity, AutoML, tabular SOTA, code hygiene.
Mission: {mission}

Fleet status:
{context}

Latest arXiv papers in your niche:
{papers}

Your job: pick ONE engineering action grounded in the papers or the fleet state.
Output ONLY valid JSON:
{{"action": "add_feature|fix_bug|optimize_code|verify_parity", "target_file": "features/engine.py or specific path", "paper_url": "arxiv url or empty", "description": "1 sentence", "priority": "high|medium|low", "reasoning": "2 sentences"}}""",

    "d3": """You are the D3 EVOLUTION department head for Nomos42.
Niche: evolutionary algorithms, island-model GA, Darwinian weights, mutation/crossover theory.
Mission: {mission}

Fleet status (all 21 islands, pick the laggards):
{context}

Latest arXiv papers:
{papers}

Your job: tune GA parameters on ONE lagging island OR cross-pollinate.
Output ONLY valid JSON:
{{"action": "tune_mutation|tune_features|cross_pollinate|restart_island", "island": "S10..S22 or P1..P8", "parameter": "mut_rate|feat_count|pop_size|elite_frac", "new_value": "number", "paper_url": "arxiv url or empty", "reasoning": "2 sentences"}}""",

    "d4": """You are the D4 PRODUCT department head for Nomos42.
Niche: dashboard UX, information-density design, slide/presentation craft (Tufte + Geist + Stripe patterns), SEO, social-media-specific formatting.
Mission: {mission}

Fleet status (what products exist):
{context}

Latest arXiv papers in HCI / data viz:
{papers}

Your job: propose ONE product upgrade — could be a new dashboard widget, a slide template for @Nomos42Picks, a Twitter-card format, or a design-token cleanup.
Output ONLY valid JSON:
{{"action": "update_dashboard|slide_template|social_card|design_tokens|improve_bot|add_metric_display|fix_ui", "product": "dashboard|telegram|bloomberg|twitter|landing|slides", "description": "1 sentence", "priority": "high|medium|low", "design_ref": "Tufte|Geist|Stripe|Bloomberg|Apple|arxiv_url"}}""",

    "d5": """You are the D5 BUSINESS department head for Nomos42.
Niche: Napoleonic "sell fast" commerce, Kelly-criterion sizing, SaaS unit economics, Big 4 frameworks (McKinsey 7S, Porter 5F, BCG matrix, SWOT), customer acquisition cost, conversion funnels.
Deadline context: We must have PAYING SUBSCRIBERS by May 1 2026 or shut down (14 days from now).
Mission: {mission}

Fleet + revenue status:
{context}

Latest arXiv papers (q-fin, SaaS, pricing):
{papers}

Your job: propose ONE revenue/commerce action that can land a paying sub or raise MRR THIS WEEK. Be Napoleonic — speed beats elegance.
Output ONLY valid JSON:
{{"action": "launch_channel|adjust_pricing|write_sales_copy|cold_outreach|pivot_tier|review_bankroll|adjust_kelly|analyze_roi|report_metrics", "target_metric": "MRR|CAC|ARPU|conversion|churn|bankroll", "description": "1 sentence, action-oriented", "expected_revenue_usd": "number", "timeframe_days": "1|3|7|14", "framework": "Porter|BCG|McKinsey7S|SWOT|Kelly|Kano|JTBD|empty"}}""",

    "d6": """You are the D6 EVALUATION department head for Nomos42.
Niche: calibration audit, CPCV + purging, DSR gate, deflated Sharpe, Brier decomposition, false-positive hunting.
Mission: {mission}

Fleet + last predictions:
{context}

Latest arXiv papers (model audit, calibration, backtest methodology):
{papers}

Your job: propose ONE evaluation action — must be measurable and reversible.
Output ONLY valid JSON:
{{"action": "check_calibration|audit_predictions|verify_brier|flag_anomaly|run_cpcv|compute_dsr", "metric_to_check": "brier|logloss|ece|sharpe|dsr|roi|hit_rate", "paper_url": "arxiv url or empty", "description": "1 sentence", "priority": "high|medium|low"}}""",

    "d7": """You are the D7 INFRA department head for Nomos42.
Niche: 33 HF Spaces keepalive, cron health, VM RAM budget (969MB), Vercel deploys, MLOps, model serving.
Mission: {mission}

Fleet + Space status (red = down):
{context}

Latest arXiv papers (MLOps, uptime, serving):
{papers}

Your job: propose ONE infra action — fix a down Space, verify a cron, check VM pressure. Zero ML on VM rule still holds.
Output ONLY valid JSON:
{{"action": "restart_island|check_cron|verify_keepalive|check_vm|restart_gateway|restart_council|restart_tf", "target": "S10..S22|P1..P8|D1..D9|gateway|tf-nba|tf-pol|vm|cron", "description": "1 sentence", "urgency": "critical|high|low"}}""",

    "d8": """You are the D8 FINANCE department head for Nomos42.
Niche: risk management, Monte Carlo, VaR, Sharpe/Sortino, CFA body-of-knowledge, burn-rate projection, cash runway.
Deadline: $100/project CLI expiry May 8 2026 if no revenue. Current runway: ~23 days.
Mission: {mission}

Fleet + bankroll + Stripe MRR:
{context}

Latest arXiv papers (q-fin.RM/PM):
{papers}

Your job: propose ONE finance action — a VaR check, a burn-rate report, a Sharpe computation, a reserve-fund decision.
Output ONLY valid JSON:
{{"action": "compute_roi|track_bankroll|project_burn|report_pnl|compute_var|compute_sharpe|stress_test", "period": "daily|weekly|monthly", "metric_name": "VaR_95|Sharpe|Sortino|max_dd|burn_rate|runway_days", "description": "1 sentence", "priority": "high|medium|low"}}""",

    "d9": """You are the D9 CROSS-REPO department head for Nomos42.
Niche: monorepo parity, schema migrations, feature-engine sha256 match, cross-repo audits across mon-ipad + nomos-nba-agent + nomos-dashboard + nomos-political-alpha + rgwa.
Mission: {mission}

Fleet status:
{context}

Latest arXiv papers (software engineering, monorepo):
{papers}

Your job: propose ONE cross-repo action — parity check, feature sync, doc update, workflow audit.
Output ONLY valid JSON:
{{"action": "verify_engine_parity|sync_features|audit_crons|update_docs|schema_migration|dedupe_workflows", "repos": ["mon-ipad","nomos-nba-agent","nomos-dashboard","nomos-political-alpha","rgwa"], "description": "1 sentence", "priority": "high|medium|low"}}""",
}

def _build_prompt(scan_data: dict) -> str:
    template = DEPT_PROMPTS.get(DEPT_ID, DEPT_PROMPTS["d1"])
    context = json.dumps(scan_data, indent=2)[:2500]
    # Pull 5 freshest papers for this dept's niche (real, live arXiv call)
    papers_list = _fetch_dept_papers(DEPT_ID, max_results=5)
    if papers_list:
        papers = "\n".join(
            f"- [{p['published']}] {p['title']}\n  {p['url']}\n  {p['summary'][:200]}..."
            for p in papers_list
        )
    else:
        papers = "(arXiv fetch failed — use general reasoning)"
    return template.format(context=context, mission=DEPT_MISSION, papers=papers[:2000])

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

    refresh_btn.click(get_status_display, outputs=[status_md], api_name="get_status")
    trigger_btn.click(trigger_iteration, outputs=[trigger_output], api_name="trigger")
    history_btn.click(get_history_json, outputs=[history_json], api_name="get_history")
    status_json_btn.click(get_status_json, outputs=[status_json], api_name="get_status_json")

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
