#!/usr/bin/env python3
"""Deploy RGWA v2 — Full OpenClaw Agent (SOTA March 2026).

RGWA is a full peer of Eve, not a crippled market-only agent.
Same agentic loop, same experiment pipeline, same capabilities.
Differentiated by: identity, Telegram bot, and complementary focus.

Architecture: NemoClaw-inspired (NVIDIA endorsed OpenClaw pattern)
  - Full OODA loop (observe-orient-decide-act)
  - Real experiment submission → Supabase → S11 evaluation
  - Auto-execute recommendations (Karpathy pattern)
  - Web agent (Puppeteer + Kimi vision)
  - A2A peer communication with Eve
  - GitHub read/write on all repos
  - VM SSH access for commands

Usage:
    source .env.local
    python3 hf-spaces/rgwa/deploy.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from huggingface_hub import HfApi, CommitOperationAdd
from pathlib import Path

# Config
SPACE_ID = "LBJLincoln/nomos-rgwa"
HF_TOKEN = os.environ.get("HF_TOKEN_2")  # lbjlincoln account
LOCAL_DIR = Path(__file__).parent.parent / "openclaw"

# ── ALL credentials from VM — RGWA gets full access ──
SECRETS = {
    # ══════════════════════════════════════════════════
    # LLM PROVIDERS (all keys for resilience + rotation)
    # ══════════════════════════════════════════════════
    "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
    "OPENROUTER_KEY_STANDARD": os.environ.get("OPENROUTER_KEY_STANDARD", ""),
    "OPENROUTER_KEY_GRAPH": os.environ.get("OPENROUTER_KEY_GRAPH", ""),
    "OPENROUTER_KEY_QUANTITATIVE": os.environ.get("OPENROUTER_KEY_QUANTITATIVE", ""),
    "OPENROUTER_KEY_ORCHESTRATOR": os.environ.get("OPENROUTER_KEY_ORCHESTRATOR", ""),
    "OPENROUTER_KEY_PME": os.environ.get("OPENROUTER_KEY_PME", ""),
    "OPENROUTER_KEY_SPARE": os.environ.get("OPENROUTER_KEY_SPARE", ""),
    "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
    "GROQ_API_KEY_2": os.environ.get("GROQ_API_KEY_2", ""),
    "GROQ_API_KEY_3": os.environ.get("GROQ_API_KEY_3", ""),
    "GROQ_API_KEY_4": os.environ.get("GROQ_API_KEY_4", ""),
    "GROQ_API_KEY_5": os.environ.get("GROQ_API_KEY_5", ""),
    "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
    "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
    "XAI_API_KEY": os.environ.get("XAI_API_KEY", ""),
    "KIMI_API_KEY": os.environ.get("KIMI_API_KEY", ""),
    # LiteLLM proxy
    "LITELLM_PROXY_URL": os.environ.get("LITELLM_PROXY_URL", ""),
    "LITELLM_MASTER_KEY": os.environ.get("LITELLM_MASTER_KEY", ""),

    # ══════════════════════════════════════════════════
    # DATABASES (full access — Supabase, Neo4j, Pinecone, Redis)
    # ══════════════════════════════════════════════════
    "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_API_KEY": os.environ.get("SUPABASE_API_KEY", ""),
    "SUPABASE_PASSWORD": os.environ.get("SUPABASE_PASSWORD", ""),
    "NEO4J_URI": os.environ.get("NEO4J_URI", ""),
    "NEO4J_USER": os.environ.get("NEO4J_USER", "neo4j"),
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    "PINECONE_HOST": os.environ.get("PINECONE_HOST", ""),
    "PINECONE_API_KEY": os.environ.get("PINECONE_API_KEY", ""),
    "REDIS_URL": os.environ.get("REDIS_URL", ""),
    "UPSTASH_REDIS_REST_URL": os.environ.get("UPSTASH_REDIS_REST_URL", ""),
    "UPSTASH_REDIS_REST_TOKEN": os.environ.get("UPSTASH_REDIS_REST_TOKEN", ""),

    # ══════════════════════════════════════════════════
    # TELEGRAM — RGWA's own bot (@RGWAbot)
    # ══════════════════════════════════════════════════
    "TELEGRAM_BOT_TOKEN": os.environ.get("RGWA_TELEGRAM_BOT_TOKEN", ""),
    "ADMIN_TELEGRAM_ID": os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"),
    "TELEGRAM_CHANNEL_ID": os.environ.get("TELEGRAM_CHANNEL_ID", ""),

    # ══════════════════════════════════════════════════
    # HUGGINGFACE (3 accounts for space management)
    # ══════════════════════════════════════════════════
    "HF_TOKEN": os.environ.get("HF_TOKEN", ""),
    "HF_TOKEN_2": os.environ.get("HF_TOKEN_2", ""),
    "HF_TOKEN_3": os.environ.get("HF_TOKEN_3", ""),

    # ══════════════════════════════════════════════════
    # GITHUB (full admin — all repos)
    # ══════════════════════════════════════════════════
    "GH_TOKEN": os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", "")),
    "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", "")),

    # ══════════════════════════════════════════════════
    # VM SSH ACCESS
    # ══════════════════════════════════════════════════
    "SSH_PRIVATE_KEY": os.environ.get("SSH_PRIVATE_KEY", ""),
    "VM_HOST": os.environ.get("VM_HOST", "34.136.180.66"),
    "VM_USER": os.environ.get("VM_USER", "termius"),

    # ══════════════════════════════════════════════════
    # SEARCH & WEB (internet access for forms, scraping, research)
    # ══════════════════════════════════════════════════
    "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", ""),
    "EXA_API_KEY": os.environ.get("EXA_API_KEY", ""),
    "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
    "JINA_API_KEY": os.environ.get("JINA_API_KEY", ""),
    "JINA_API_KEY_2": os.environ.get("JINA_API_KEY_2", ""),

    # ══════════════════════════════════════════════════
    # MARKET DATA (NBA odds, live betting)
    # ══════════════════════════════════════════════════
    "ODDS_API_KEY": os.environ.get("ODDS_API_KEY", ""),

    # ══════════════════════════════════════════════════
    # EMBEDDINGS & TEXT
    # ══════════════════════════════════════════════════
    "COHERE_API_KEY": os.environ.get("COHERE_API_KEY", ""),

    # ══════════════════════════════════════════════════
    # SOCIAL MEDIA (Twitter for data + sentiment)
    # ══════════════════════════════════════════════════
    "TWITTER_BEARER_TOKEN": os.environ.get("TWITTER_BEARER_TOKEN", ""),

    # ══════════════════════════════════════════════════
    # KAGGLE (GPU compute for experiments)
    # ══════════════════════════════════════════════════
    "KAGGLE_USERNAME": os.environ.get("KAGGLE_USERNAME", ""),
    "KAGGLE_KEY": os.environ.get("KAGGLE_KEY", ""),

    # ══════════════════════════════════════════════════
    # DEPLOYMENT
    # ══════════════════════════════════════════════════
    "VERCEL_TOKEN": os.environ.get("VERCEL_TOKEN", ""),
    "REMOTE_CONTROL_KEY": os.environ.get("REMOTE_CONTROL_KEY", ""),

    # ══════════════════════════════════════════════════
    # RGWA IDENTITY — Full OpenClaw peer (NOT crippled market-only)
    # ══════════════════════════════════════════════════
    "AGENT_NAME": "RGWA",
    "AGENT_ROLE": "nba-quant",  # SAME as Eve — full capabilities, proven pipeline
    "S10_URL": "https://lbjlincoln-nomos-nba-quant.hf.space",
    "S11_URL": "https://lbjlincoln-nomos-nba-quant-2.hf.space",
    "EVE_URL": "https://nomos42-nomos-worker-2.hf.space",
    "PEER_AGENTS": "Eve|https://nomos42-nomos-worker-2.hf.space",
    # Enable all capabilities
    "AUTO_EXECUTE": "true",
    "WEB_AGENT_ENABLED": "true",
}


def main():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN_2 not set. Run: source .env.local")
        sys.exit(1)

    if not LOCAL_DIR.exists():
        print(f"ERROR: OpenClaw source directory not found at {LOCAL_DIR}")
        sys.exit(1)

    api = HfApi(token=HF_TOKEN)

    print(f"Deploying RGWA v2 (Full OpenClaw) to {SPACE_ID}...")
    print(f"Source directory: {LOCAL_DIR}")
    print(f"Role: nba-quant (full peer, not market-only)")

    # Collect all files to upload (from Eve's codebase)
    operations = []
    skip_patterns = {"__pycache__", ".pyc", "node_modules", ".git", "deploy.py"}

    for file_path in LOCAL_DIR.rglob("*"):
        if file_path.is_dir():
            continue
        if any(skip in str(file_path) for skip in skip_patterns):
            continue

        rel_path = file_path.relative_to(LOCAL_DIR)
        print(f"  + {rel_path}")

        operations.append(
            CommitOperationAdd(
                path_in_repo=str(rel_path),
                path_or_fileobj=str(file_path),
            )
        )

    if not operations:
        print("ERROR: No files found to upload")
        sys.exit(1)

    # Upload all files in one commit
    print(f"\nUploading {len(operations)} files...")
    try:
        api.create_commit(
            repo_id=SPACE_ID,
            repo_type="space",
            operations=operations,
            commit_message="feat: RGWA v2 — Full OpenClaw peer (fix experiment pipeline + auto-execute)",
        )
        print("Files uploaded successfully!")
    except Exception as e:
        if "404" in str(e) or "not found" in str(e).lower():
            print(f"Space {SPACE_ID} not found, creating...")
            api.create_repo(
                repo_id=SPACE_ID,
                repo_type="space",
                space_sdk="docker",
                space_hardware="cpu-basic",
                private=False,
            )
            print("Space created! Retrying upload...")
            api.create_commit(
                repo_id=SPACE_ID,
                repo_type="space",
                operations=operations,
                commit_message="feat: RGWA v2 — Full OpenClaw peer (fix experiment pipeline + auto-execute)",
            )
            print("Files uploaded successfully!")
        else:
            raise

    # Set ALL secrets
    print(f"\nConfiguring {len(SECRETS)} secrets...")
    set_count = 0
    for key, value in SECRETS.items():
        if value:
            try:
                api.add_space_secret(SPACE_ID, key, value)
                set_count += 1
                print(f"  Set {key}")
            except Exception as e:
                print(f"  WARN: Failed to set {key}: {e}")
        else:
            print(f"  SKIP {key} (empty)")

    print(f"\n{set_count}/{len(SECRETS)} secrets configured")

    # Restart the Space
    print("\nRestarting Space...")
    try:
        api.restart_space(SPACE_ID)
        print("Space restarted!")
    except Exception as e:
        print(f"Restart warning: {e}")

    print(f"\n{'='*60}")
    print(f"RGWA v2 deployed to: https://lbjlincoln-nomos-rgwa.hf.space")
    print(f"Telegram: @RGWAbot")
    print(f"Role: nba-quant (FULL OpenClaw peer)")
    print(f"Experiment pipeline: FIXED (Supabase INSERT)")
    print(f"Auto-execute: ENABLED")
    print(f"Web agent: ENABLED")
    print(f"{'='*60}")
    print(f"\nMonitor: https://huggingface.co/spaces/{SPACE_ID}")


if __name__ == "__main__":
    main()
