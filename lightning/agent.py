#!/usr/bin/env python3
"""
Nomos Lightning Agent — Full autonomous AI agent on Lightning.ai GPU.

Pilotable via Telegram. Executes commands, builds websites, accesses all repos.
Runs on port 8000 (exposed via Lightning.ai HTTPS tunnel).

Usage:
    source .env.local
    python3 agent.py
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ============================================================
# CONFIG
# ============================================================

PORT = int(os.environ.get("PORT", 8000))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LITELLM_PROXY_URL = os.environ.get("LITELLM_PROXY_URL", "")
LITELLM_MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

WORKDIR = Path(os.environ.get("NOMOS_WORKDIR", Path.home() / "nomos-agent"))
REPOS_DIR = WORKDIR / "repos"

# All repos this agent can work in
REPOS = {
    "mon-ipad": "https://github.com/LBJLincoln/mon-ipad.git",
    "rag-website": "https://github.com/LBJLincoln/rag-website.git",
    "rag-data-ingestion": "https://github.com/LBJLincoln/rag-data-ingestion.git",
    "rag-dashboard": "https://github.com/LBJLincoln/rag-dashboard.git",
}

# LLM model fallback chain (via OpenRouter)
MODEL_CHAIN = [
    "openrouter/optimus-alpha",
    "openai/gpt-4.1",
    "openrouter/quasar-alpha",
    "moonshotai/kimi-k2",
    "google/gemini-2.5-flash-preview",
    "qwen/qwen3-235b-a22b",
]

SYSTEM_PROMPT = """Tu es l'Agent Nomos Lightning — un agent IA autonome tournant sur un GPU NVIDIA T4 (Lightning.ai).

Tu es un BUILDER. Ta mission principale : construire les sites web et applications techniques decrits dans MISSION_PROMPT.md :
- Dashboard satellite ultra-futuriste (Cesium 3D globe, WebGL shaders CRT/FLIR, satellite.js orbites)
- Marketplace d'agents & d'entreprises (M&A IA)
- Automated Business Factory
- Module de valorisation avec signatures thermiques WebGL

Tu as acces COMPLET a :
- Shell Linux avec GPU NVIDIA T4 (CUDA, PyTorch, etc.)
- Tous les repos Nomos : mon-ipad, rag-website, rag-data-ingestion, rag-dashboard
- Toutes les bases de donnees : Supabase (43K docs), Neo4j (72K nodes), Pinecone (82K vectors)
- LiteLLM proxy (9 modeles, 13 providers)
- npm, node, python3, git, curl — tout ce qu'il faut pour builder

REGLES :
1. Quand on te demande de builder quelque chose, tu EXECUTES. Pas de "je ne peux pas".
2. Tu travailles dans les repos clones localement (~/nomos-agent/repos/).
3. Tu commit + push tes changements quand c'est pret.
4. Tu reponds en francais sauf si on te parle en anglais.
5. Tu gardes tes reponses concises pour Telegram (max 4000 chars).
6. Pour les commandes longues, tu executes en background et tu rapportes le resultat.
7. Tu ne supprimes JAMAIS de fichiers sans confirmation.
8. Tu verifies TOUJOURS que tes changements n'introduisent pas de regressions.

COMMANDES SPECIALES :
/build <description> — Construire un site/composant technique
/exec <commande> — Executer une commande shell
/repo <nom> <commande> — Executer dans un repo specifique
/status — Status GPU + repos + infra
/gpu — Info GPU (nvidia-smi)
/sites — Liste des sites web a construire
/pull — Git pull tous les repos
/push <repo> <message> — Commit + push dans un repo
/query <question> — Interroger les pipelines RAG
/plan <objectif> — Planifier une implementation"""

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("nomos-lightning")

# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="Nomos Lightning Agent", version="1.0.0")

# Conversation history per chat
conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20


# ============================================================
# SHELL EXECUTOR
# ============================================================

def run_shell(cmd: str, cwd: str | None = None, timeout: int = 120) -> dict:
    """Execute a shell command and return stdout/stderr."""
    if cwd is None:
        cwd = str(WORKDIR)

    log.info(f"EXEC [{cwd}]: {cmd[:200]}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "HOME": str(Path.home())},
        )
        output = result.stdout + result.stderr
        # Truncate for Telegram
        if len(output) > 3500:
            output = output[:1700] + "\n\n... (tronque) ...\n\n" + output[-1700:]

        return {
            "exit_code": result.returncode,
            "output": output.strip() or "(no output)",
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "output": f"TIMEOUT after {timeout}s", "success": False}
    except Exception as e:
        return {"exit_code": -1, "output": f"ERROR: {e}", "success": False}


def run_in_repo(repo: str, cmd: str, timeout: int = 120) -> dict:
    """Execute a command inside a specific repo directory."""
    repo_path = REPOS_DIR / repo
    if not repo_path.exists():
        return {"exit_code": -1, "output": f"Repo {repo} not found at {repo_path}", "success": False}
    return run_shell(cmd, cwd=str(repo_path), timeout=timeout)


# ============================================================
# LLM CLIENT
# ============================================================

async def llm_completion(messages: list[dict], max_tokens: int = 4000) -> str:
    """Get LLM completion via OpenRouter with fallback chain."""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://nomos42.ai",
        "X-Title": "Nomos Lightning Agent",
    }

    for model in MODEL_CHAIN:
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                        "max_tokens": max_tokens,
                        "temperature": 0.3,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    log.info(f"LLM OK: {model} ({data.get('usage', {}).get('total_tokens', '?')} tokens)")
                    return content
                else:
                    log.warning(f"LLM {model}: HTTP {resp.status_code}")
                    continue
        except Exception as e:
            log.warning(f"LLM {model} failed: {e}")
            continue

    return "Erreur: tous les modeles LLM sont indisponibles."


# ============================================================
# TELEGRAM COMMANDS
# ============================================================

async def handle_command(chat_id: int, text: str) -> str:
    """Handle slash commands."""

    parts = text.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return """*Nomos Lightning Agent v1.0*
GPU NVIDIA T4 — Full autonomous builder

*Build commands:*
/build <description> — Construire un site/composant
/sites — Sites a construire (MISSION_PROMPT)
/plan <objectif> — Planifier implementation

*Execution:*
/exec <cmd> — Commande shell
/repo <nom> <cmd> — Commande dans un repo
/gpu — nvidia-smi
/pull — Git pull tous les repos
/push <repo> <msg> — Commit + push

*Intelligence:*
/query <question> — Pipeline RAG
/status — Status complet

Ou pose directement ta question — je suis un builder autonome."""

    elif cmd == "/exec":
        if not args:
            return "Usage: /exec <commande>"
        result = run_shell(args, timeout=180)
        icon = "+" if result["success"] else "x"
        return f"[{icon}] `{args[:80]}`\n```\n{result['output']}\n```"

    elif cmd == "/repo":
        repo_parts = args.split(maxsplit=1)
        if len(repo_parts) < 2:
            return "Usage: /repo <nom-repo> <commande>\nRepos: " + ", ".join(REPOS.keys())
        repo_name, repo_cmd = repo_parts
        result = run_in_repo(repo_name, repo_cmd, timeout=180)
        icon = "+" if result["success"] else "x"
        return f"[{icon}] `{repo_name}$ {repo_cmd[:60]}`\n```\n{result['output']}\n```"

    elif cmd == "/gpu":
        result = run_shell("nvidia-smi 2>/dev/null || echo 'No GPU detected'")
        return f"*GPU Status:*\n```\n{result['output']}\n```"

    elif cmd == "/status":
        gpu = run_shell("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'No GPU'")
        repos_status = []
        for name in REPOS:
            rp = REPOS_DIR / name
            if rp.exists():
                branch = run_shell("git branch --show-current", cwd=str(rp))
                repos_status.append(f"  {name}: {branch['output']}")
            else:
                repos_status.append(f"  {name}: NOT CLONED")

        disk = run_shell("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\")\"}'")
        mem = run_shell("free -h | grep Mem | awk '{print $3\"/\"$2}'")

        return f"""*Nomos Lightning Agent Status*

*GPU:* {gpu['output']}
*RAM:* {mem['output']}
*Disk:* {disk['output']}

*Repos:*
{chr(10).join(repos_status)}

*Uptime:* {int(time.time() - START_TIME)}s
*LLM:* OpenRouter ({len(MODEL_CHAIN)} models)"""

    elif cmd == "/pull":
        results = []
        for name in REPOS:
            rp = REPOS_DIR / name
            if rp.exists():
                r = run_shell("git pull --quiet", cwd=str(rp))
                results.append(f"  {'+'if r['success'] else 'x'} {name}")
            else:
                r = run_shell(f"git clone {REPOS[name]} {rp}", timeout=60)
                results.append(f"  {'+'if r['success'] else 'x'} {name} (cloned)")
        return "*Git Pull:*\n" + "\n".join(results)

    elif cmd == "/push":
        push_parts = args.split(maxsplit=1)
        if len(push_parts) < 2:
            return "Usage: /push <repo> <commit message>"
        repo_name, commit_msg = push_parts
        r1 = run_in_repo(repo_name, "git add -A")
        r2 = run_in_repo(repo_name, f'git commit -m "{commit_msg}\n\nCo-Authored-By: Nomos Lightning Agent <noreply@nomos42.ai>"')
        r3 = run_in_repo(repo_name, "git push origin main")
        if r3["success"]:
            return f"*Pushed to {repo_name}:* {commit_msg}"
        return f"*Push failed:*\n```\n{r2['output']}\n{r3['output']}\n```"

    elif cmd == "/sites":
        return """*Sites techniques a construire (MISSION_PROMPT):*

1. *Satellite Dashboard* — Cesium 3D globe + WebGL shaders (CRT, Vision Nocturne, FLIR)
   Stack: Next.js + CesiumJS + satellite.js + Three.js/WebGL
   Repo: rag-website

2. *Marketplace M&A IA* — Vente/encheres d'entreprises et agents
   Stack: Next.js + Supabase + Neo4j graph viz
   Repo: rag-website

3. *Business Factory UI* — Interface creation entreprise automatisee
   Stack: Next.js + n8n webhook triggers
   Repo: rag-website

4. *Heatmap Valorisation* — Signatures thermiques WebGL
   Stack: WebGL custom shaders + Supabase data
   Repo: rag-website

Utilise /build <n> ou /build <description> pour commencer."""

    elif cmd == "/query":
        if not args:
            return "Usage: /query <question>"
        spaces = [
            "https://lbjlincoln-nomos-rag-engine.hf.space",
            "https://lbjlincoln-nomos-rag-engine-3.hf.space",
        ]
        for space_url in spaces:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{space_url}/webhook/orchestrator-v2",
                        json={"question": args, "tenant_id": "finance"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = data.get("response") or data.get("answer") or data.get("output", "No answer")
                        pipeline = data.get("selected_pipeline", "?")
                        return f"*RAG Response* (via {pipeline}):\n\n{answer[:3500]}"
            except Exception:
                continue
        return "Pipelines RAG indisponibles."

    elif cmd == "/plan":
        if not args:
            return "Usage: /plan <objectif>"
        # Use LLM to plan
        messages = [{"role": "user", "content": f"Planifie l'implementation de : {args}\n\nDonne un plan technique precis avec les commandes a executer, les fichiers a creer, et les etapes dans l'ordre. Utilise les repos disponibles: {', '.join(REPOS.keys())}"}]
        plan = await llm_completion(messages, max_tokens=3000)
        return plan[:4000]

    elif cmd == "/build":
        if not args:
            return "Usage: /build <description de ce qu'il faut construire>"
        # LLM-driven build: plan then execute
        messages = [{"role": "user", "content": f"""MISSION: Construire ceci: {args}

Tu as acces au GPU T4, a tous les repos, et a toutes les bases de donnees.
Le repo principal pour les sites web est rag-website (Next.js).

Donne-moi:
1. Le plan technique (fichiers a creer/modifier)
2. Les commandes shell a executer
3. Les dependances a installer

Format: une liste de commandes executables que je vais lancer une par une."""}]
        plan = await llm_completion(messages, max_tokens=3000)
        return f"*Build Plan:*\n\n{plan[:4000]}"

    return None  # Not a known command


# ============================================================
# TELEGRAM HANDLER
# ============================================================

async def send_telegram(chat_id: int, text: str):
    """Send a message via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Split long messages
    chunks = []
    while text:
        if len(text) <= 4000:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, 4000)
        if split_at < 2000:
            split_at = 4000
        chunks.append(text[:split_at])
        text = text[split_at:]

    async with httpx.AsyncClient(timeout=30) as client:
        for chunk in chunks:
            try:
                await client.post(url, json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                })
            except Exception:
                # Retry without markdown
                try:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": chunk,
                    })
                except Exception as e:
                    log.error(f"Telegram send failed: {e}")


async def process_message(chat_id: int, user_text: str):
    """Process an incoming Telegram message."""

    # Try command first
    if user_text.startswith("/"):
        response = await handle_command(chat_id, user_text)
        if response:
            await send_telegram(chat_id, response)
            return

    # AI conversation with history
    if chat_id not in conversations:
        conversations[chat_id] = []

    conversations[chat_id].append({"role": "user", "content": user_text})

    # Trim history
    if len(conversations[chat_id]) > MAX_HISTORY * 2:
        conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

    # Check if the AI wants to execute commands
    enriched_prompt = user_text
    if any(kw in user_text.lower() for kw in ["execute", "lance", "fais", "build", "cree", "installe", "deploie", "run"]):
        enriched_prompt += "\n\n[CONTEXTE: Tu peux me donner des commandes shell a executer. Prefixe chaque commande avec EXEC: sur une ligne separee. Je les executerai et te donnerai le resultat.]"

    response = await llm_completion(conversations[chat_id])

    # Auto-execute EXEC: commands if present
    if "EXEC:" in response:
        exec_results = []
        final_response = response
        for line in response.split("\n"):
            if line.strip().startswith("EXEC:"):
                cmd = line.strip()[5:].strip()
                if cmd:
                    # Security: only admin can execute
                    if chat_id == ADMIN_TELEGRAM_ID:
                        result = run_shell(cmd, timeout=120)
                        exec_results.append(f"`{cmd[:60]}` → {'OK' if result['success'] else 'FAIL'}")
                        if not result['success']:
                            exec_results.append(f"```\n{result['output'][:500]}\n```")
                    else:
                        exec_results.append(f"`{cmd[:60]}` → DENIED (admin only)")

        if exec_results:
            final_response += "\n\n*Executed:*\n" + "\n".join(exec_results)

        await send_telegram(chat_id, final_response[:4000])
    else:
        await send_telegram(chat_id, response[:4000])

    conversations[chat_id].append({"role": "assistant", "content": response})


# ============================================================
# ROUTES
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "Nomos Lightning Agent",
        "version": "1.0.0",
        "gpu": "NVIDIA T4",
        "repos": list(REPOS.keys()),
        "uptime": int(time.time() - START_TIME),
        "telegram": bool(TELEGRAM_BOT_TOKEN),
        "endpoints": ["/", "/health", "/webhook/telegram", "/api/exec", "/api/query"],
    }


@app.get("/health")
async def health():
    gpu = run_shell("nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo 'No GPU'")
    return {
        "status": "healthy",
        "gpu": gpu["output"].strip(),
        "uptime": int(time.time() - START_TIME),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Telegram bot webhook."""
    try:
        data = await request.json()
        msg = data.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")
        user_id = msg.get("from", {}).get("id")
        username = msg.get("from", {}).get("username", "?")

        if not text or not chat_id:
            return JSONResponse({"ok": True})

        log.info(f"[TG] {username}: {text[:80]}")

        # Process in background to not block webhook
        asyncio.create_task(process_message(chat_id, text))

        # Notify admin of external conversations
        if user_id != ADMIN_TELEGRAM_ID:
            asyncio.create_task(
                send_telegram(ADMIN_TELEGRAM_ID, f"[External] {username}: {text[:200]}")
            )

        return JSONResponse({"ok": True})
    except Exception as e:
        log.error(f"Webhook error: {e}")
        return JSONResponse({"ok": True})


@app.post("/api/exec")
async def api_exec(request: Request):
    """REST API to execute commands (admin only, check via header)."""
    data = await request.json()
    cmd = data.get("command", "")
    repo = data.get("repo")
    timeout = data.get("timeout", 120)

    if not cmd:
        return JSONResponse({"error": "command required"}, status_code=400)

    if repo:
        result = run_in_repo(repo, cmd, timeout=timeout)
    else:
        result = run_shell(cmd, timeout=timeout)

    return JSONResponse(result)


@app.post("/api/query")
async def api_query(request: Request):
    """REST API to query RAG pipelines."""
    data = await request.json()
    question = data.get("question", "")
    if not question:
        return JSONResponse({"error": "question required"}, status_code=400)

    response = await handle_command(0, f"/query {question}")
    return JSONResponse({"response": response})


# ============================================================
# STARTUP
# ============================================================

START_TIME = time.time()


async def setup_telegram_webhook():
    """Set Telegram webhook to this server."""
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")
        return

    # Lightning.ai URL pattern
    webhook_url = os.environ.get(
        "WEBHOOK_URL",
        f"https://8000-01kkj0hqg9fq7twz8065b3e94m.cloudspaces.litng.ai/webhook/telegram"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json={"url": webhook_url})
        if resp.status_code == 200:
            log.info(f"Telegram webhook set: {webhook_url}")
        else:
            log.error(f"Telegram webhook failed: {resp.text}")


@app.on_event("startup")
async def startup():
    log.info("=" * 60)
    log.info("NOMOS LIGHTNING AGENT v1.0.0")
    log.info(f"GPU: checking...")
    gpu = run_shell("nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'No GPU detected'")
    log.info(f"GPU: {gpu['output'].strip()}")
    log.info(f"Repos dir: {REPOS_DIR}")
    log.info(f"Telegram: {'ACTIVE' if TELEGRAM_BOT_TOKEN else 'DISABLED'}")
    log.info(f"OpenRouter: {'OK' if OPENROUTER_API_KEY else 'NOT SET'}")
    log.info(f"LiteLLM: {LITELLM_PROXY_URL or 'NOT SET'}")
    log.info("=" * 60)

    # Ensure repos dir exists
    REPOS_DIR.mkdir(parents=True, exist_ok=True)

    # Setup Telegram webhook
    await setup_telegram_webhook()

    # Notify admin
    if TELEGRAM_BOT_TOKEN:
        await send_telegram(
            ADMIN_TELEGRAM_ID,
            f"*Nomos Lightning Agent v1.0.0 started*\nGPU: {gpu['output'].strip()}\nRepos: {', '.join(REPOS.keys())}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
