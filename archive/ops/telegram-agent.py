#!/usr/bin/env python3
"""Nomos Telegram Agent — AI assistant like Claude Code CLI.

Conversational AI agent controllable via Telegram.
Uses OpenRouter with the latest models. Can execute commands across all repos.
NO Stripe, NO products — pure AI assistant.

Usage:
    source .env.local
    python3 ops/telegram-agent.py
"""

import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"))
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 2

# Repos accessible
REPOS = {
    "mon-ipad": "/home/termius/mon-ipad",
    "rag-website": "/home/termius/rag-website",
    "rag-data-ingestion": "/home/termius/rag-data-ingestion",
    "rag-dashboard": "/home/termius/rag-dashboard",
    "autoresearch": "/home/termius/autoresearch",
}

# LiteLLM S7 (our own proxy) — primary
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"

# Fallback OpenRouter models
OPENROUTER_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen-2.5-72b-instruct:free",
]

SYSTEM_PROMPT = """Tu es l'Agent Nomos — un assistant IA expert comme Claude Code CLI, accessible via Telegram.

Tu as acces COMPLET a l'infrastructure Nomos :
- 4 repos GitHub : mon-ipad, rag-website, rag-data-ingestion, rag-dashboard
- 4 pipelines RAG (Standard, Graph, Quantitative, Orchestrator) sur 5 HF Spaces
- Bases de donnees : Supabase (43K docs), Neo4j (72K nodes), Pinecone (82K vectors)
- LiteLLM proxy (13 providers, rotation auto)
- 6 daemons continus (ingest, enrich, eval-blast, regression, improver, monitor)

Tu peux EXECUTER des commandes shell quand on te le demande.
Tu reponds de maniere concise et technique.
Quand on te demande de faire quelque chose, tu le FAIS — pas de "je ne peux pas".
Format Telegram (Markdown). Francais par defaut, anglais si demande."""

# ─── Conversation history ─────────────────────────────────────
conversations = {}
MAX_HISTORY = 30


# ─── Shell executor ───────────────────────────────────────────
def run_cmd(cmd, cwd=None, timeout=60):
    """Execute shell command and return output."""
    try:
        r = subprocess.run(
            cmd, shell=True, cwd=cwd or REPOS["mon-ipad"],
            capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout + r.stderr).strip()
        if len(out) > 3500:
            out = out[:1700] + "\n...(tronque)...\n" + out[-1700:]
        return {"ok": r.returncode == 0, "output": out or "(no output)"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"TIMEOUT ({timeout}s)"}
    except Exception as e:
        return {"ok": False, "output": str(e)}


# ─── LLM ──────────────────────────────────────────────────────
def _call_llm(url, key, model, messages, max_tokens=3000, extra_headers=None):
    """Call a single LLM endpoint. Returns content or raises."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]

def llm_chat(messages, max_tokens=3000):
    """Call LiteLLM S7 first, then OpenRouter free models as fallback."""
    # Try LiteLLM S7 (our own proxy — free, 13 providers)
    for model in ["smart", "fast", "default"]:
        try:
            content = _call_llm(LITELLM_URL, LITELLM_KEY, model, messages, max_tokens)
            print(f"  LLM OK: LiteLLM/{model}")
            return content
        except Exception as e:
            print(f"  LiteLLM/{model} failed: {e}")

    # Fallback: OpenRouter free models
    for model in OPENROUTER_MODELS:
        try:
            content = _call_llm(
                "https://openrouter.ai/api/v1/chat/completions",
                OPENROUTER_KEY, model, messages, max_tokens,
                {"HTTP-Referer": "https://nomos42.ai", "X-Title": "Nomos Agent"},
            )
            print(f"  LLM OK: {model}")
            return content
        except Exception as e:
            print(f"  LLM {model} failed: {e}")

    return "Erreur: tous les modeles LLM sont indisponibles. LiteLLM S7 et OpenRouter down."


# ─── Telegram helpers ─────────────────────────────────────────
def tg_request(method, data=None):
    """Make Telegram Bot API request."""
    url = f"{API_URL}/{method}"
    if data:
        req = urllib.request.Request(
            url, json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  TG error ({method}): {e}")
        return None


def send_msg(chat_id, text):
    """Send message, splitting if too long."""
    while text:
        chunk = text[:4000]
        text = text[4000:]
        # Try markdown first
        result = tg_request("sendMessage", {
            "chat_id": chat_id, "text": chunk, "parse_mode": "Markdown",
        })
        if not result or not result.get("ok"):
            # Fallback without markdown
            tg_request("sendMessage", {"chat_id": chat_id, "text": chunk})


# ─── Command handlers ────────────────────────────────────────
def handle_command(chat_id, text):
    """Handle slash commands. Returns response text or None."""
    parts = text.split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "/start":
        return """*Nomos Agent v2.0*
Assistant IA — comme Claude Code CLI

*Commandes :*
/exec <cmd> — Commande shell
/repo <nom> <cmd> — Commande dans un repo
/status — Sante infrastructure
/pipelines — Status pipelines RAG
/daemons — Status daemons actifs
/query <question> — Interroger RAG
/pull — Git pull tous les repos
/help — Aide complete

Ou parle-moi directement — je suis un assistant IA complet."""

    elif cmd == "/exec":
        if chat_id != ADMIN_ID:
            return "Admin only."
        if not args:
            return "Usage: /exec <commande>"
        r = run_cmd(args, timeout=120)
        icon = "+" if r["ok"] else "x"
        return f"[{icon}] `{args[:80]}`\n```\n{r['output']}\n```"

    elif cmd == "/repo":
        if chat_id != ADMIN_ID:
            return "Admin only."
        rp = args.split(maxsplit=1)
        if len(rp) < 2:
            return "Usage: /repo <nom> <cmd>\nRepos: " + ", ".join(REPOS.keys())
        name, rcmd = rp
        if name not in REPOS:
            return f"Repo inconnu: {name}\nDisponibles: {', '.join(REPOS.keys())}"
        r = run_cmd(rcmd, cwd=REPOS[name], timeout=120)
        icon = "+" if r["ok"] else "x"
        return f"[{icon}] `{name}$ {rcmd[:60]}`\n```\n{r['output']}\n```"

    elif cmd == "/status":
        lines = ["*Infrastructure Nomos*\n"]
        # Check spaces
        for name, url in [
            ("S1", "https://lbjlincoln-nomos-rag-engine.hf.space"),
            ("S3", "https://lbjlincoln-nomos-rag-engine-3.hf.space"),
            ("S5", "https://lbjlincoln-nomos-rag-engine-5.hf.space"),
            ("S7-LiteLLM", "https://lbjlincoln-nomos-rag-engine-7.hf.space"),
            ("S9-Ingest", "https://lbjlincoln-nomos-rag-engine-9.hf.space"),
            ("OpenClaw", "https://nomos42-nomos-worker-2.hf.space"),
        ]:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    lines.append(f"  + {name}: UP ({resp.status})")
            except Exception:
                lines.append(f"  x {name}: DOWN")
        return "\n".join(lines)

    elif cmd == "/daemons":
        r = run_cmd("ps aux --no-headers | grep -E 'python3.*(ops/|eval/|agents/)' | grep -v grep | awk '{print $NF}' | sort")
        return f"*Daemons actifs:*\n```\n{r['output']}\n```"

    elif cmd == "/pipelines":
        r = run_cmd("cat data/health-status.json 2>/dev/null || echo '{}'")
        try:
            h = json.loads(r["output"])
            lines = ["*Pipeline Status*\n"]
            for name, info in h.get("pipelines", {}).items():
                rate = info.get("success_rate", 0)
                total = info.get("total", 0)
                lines.append(f"  {name}: {rate}% ({total} runs)")
            return "\n".join(lines)
        except Exception:
            return f"```\n{r['output']}\n```"

    elif cmd == "/query":
        if not args:
            return "Usage: /query <question>"
        send_msg(chat_id, "Interrogation pipeline...")
        spaces = [
            "https://lbjlincoln-nomos-rag-engine.hf.space",
            "https://lbjlincoln-nomos-rag-engine-3.hf.space",
        ]
        for url in spaces:
            try:
                data = json.dumps({"question": args, "tenant_id": "finance"}).encode()
                req = urllib.request.Request(
                    f"{url}/webhook/orchestrator-v2", data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read())
                    answer = result.get("response") or result.get("answer") or result.get("output", "No answer")
                    pipeline = result.get("selected_pipeline", "?")
                    return f"*RAG ({pipeline}):*\n\n{answer[:3500]}"
            except Exception:
                continue
        return "Pipelines RAG indisponibles."

    elif cmd == "/pull":
        results = []
        for name, path in REPOS.items():
            if Path(path).exists():
                r = run_cmd("git pull --quiet", cwd=path)
                results.append(f"  {'+'if r['ok'] else 'x'} {name}")
            else:
                results.append(f"  - {name} (not cloned)")
        return "*Git Pull:*\n" + "\n".join(results)

    elif cmd == "/help":
        return """*Nomos Agent — Assistant IA Complet*

*Shell:*
/exec <cmd> — Commande shell (admin)
/repo <nom> <cmd> — Dans un repo specifique

*Monitoring:*
/status — Sante HF Spaces
/daemons — Process actifs
/pipelines — Performance RAG

*Intelligence:*
/query <question> — Pipeline RAG
/pull — Git pull tous repos

*Conversation:*
Parle-moi directement pour :
- Analyser du code
- Debugger un probleme
- Planifier une implementation
- Executer des taches complexes

Je suis ton Claude Code CLI portable."""

    return None  # Not a command


# ─── Main loop ────────────────────────────────────────────────
def main():
    print(f"=== NOMOS TELEGRAM AGENT v2.0 ===")
    print(f"Bot: @Nomos42Bot")
    print(f"Admin: {ADMIN_ID}")
    print(f"LLM: LiteLLM S7 (smart/fast/default) + {len(OPENROUTER_MODELS)} OpenRouter fallbacks")
    print(f"Repos: {', '.join(REPOS.keys())}")
    print(f"Polling mode active...")

    # Delete any webhook
    tg_request("deleteWebhook")

    offset = 0
    while True:
        try:
            result = tg_request("getUpdates", {
                "offset": offset, "timeout": 30, "allowed_updates": ["message"],
            })
            if not result or not result.get("ok"):
                time.sleep(POLL_INTERVAL)
                continue

            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                username = msg.get("from", {}).get("username", "?")

                if not text or not chat_id:
                    continue

                print(f"[{datetime.now().strftime('%H:%M:%S')}] @{username}: {text[:80]}")

                # Try command first
                if text.startswith("/"):
                    response = handle_command(chat_id, text)
                    if response:
                        send_msg(chat_id, response)
                        continue

                # AI conversation
                if chat_id not in conversations:
                    conversations[chat_id] = []

                conversations[chat_id].append({"role": "user", "content": text})
                if len(conversations[chat_id]) > MAX_HISTORY * 2:
                    conversations[chat_id] = conversations[chat_id][-MAX_HISTORY:]

                # Check if the AI should execute commands
                response = llm_chat(conversations[chat_id])

                # Auto-execute EXEC: lines
                if "EXEC:" in response and chat_id == ADMIN_ID:
                    exec_results = []
                    for line in response.split("\n"):
                        if line.strip().startswith("EXEC:"):
                            cmd = line.strip()[5:].strip().strip("`")
                            if cmd:
                                r = run_cmd(cmd, timeout=120)
                                icon = "+" if r["ok"] else "x"
                                exec_results.append(f"[{icon}] `{cmd[:60]}`")
                                if not r["ok"]:
                                    exec_results.append(f"```\n{r['output'][:500]}\n```")
                    if exec_results:
                        response += "\n\n*Executed:*\n" + "\n".join(exec_results)

                send_msg(chat_id, response[:4000])
                conversations[chat_id].append({"role": "assistant", "content": response})

        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
