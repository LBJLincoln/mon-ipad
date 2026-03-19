#!/usr/bin/env python3
"""Deploy RGWA to lbjlincoln26/nomos-rgwa HF Space.

Reuses Eve's codebase from hf-spaces/openclaw/ but with different env vars
that give RGWA its own identity, Telegram bot (@RGWAbot), and focus.

Usage:
    source .env.local
    python3 hf-spaces/rgwa/deploy.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from huggingface_hub import HfApi, CommitOperationAdd
from pathlib import Path

# Config
SPACE_ID = "LBJLincoln/nomos-rgwa"
HF_TOKEN = os.environ.get("HF_TOKEN_2")  # lbjlincoln account
# Reuse Eve's codebase — RGWA runs the same code with different env vars
LOCAL_DIR = Path(__file__).parent.parent / "openclaw"

# Secrets to configure on the Space (same infra as Eve + RGWA-specific)
SECRETS = {
    # LLM Providers
    "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY", ""),
    "OPENROUTER_KEY_STANDARD": os.environ.get("OPENROUTER_KEY_STANDARD", ""),
    "OPENROUTER_KEY_GRAPH": os.environ.get("OPENROUTER_KEY_GRAPH", ""),
    "OPENROUTER_KEY_QUANTITATIVE": os.environ.get("OPENROUTER_KEY_QUANTITATIVE", ""),
    "OPENROUTER_KEY_ORCHESTRATOR": os.environ.get("OPENROUTER_KEY_ORCHESTRATOR", ""),
    "OPENROUTER_KEY_SPARE": os.environ.get("OPENROUTER_KEY_SPARE", ""),
    "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
    "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
    # LiteLLM
    "LITELLM_PROXY_URL": os.environ.get("LITELLM_PROXY_URL", ""),
    "LITELLM_MASTER_KEY": os.environ.get("LITELLM_MASTER_KEY", ""),
    # Telegram — RGWA has its OWN bot (@RGWAbot)
    "TELEGRAM_BOT_TOKEN": os.environ.get("RGWA_TELEGRAM_BOT_TOKEN", ""),
    "ADMIN_TELEGRAM_ID": os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"),
    "TELEGRAM_CHANNEL_ID": os.environ.get("TELEGRAM_CHANNEL_ID", ""),
    # Databases (shared with Eve)
    "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
    "SUPABASE_URL": os.environ.get("SUPABASE_URL", ""),
    "SUPABASE_API_KEY": os.environ.get("SUPABASE_API_KEY", ""),
    "NEO4J_URI": os.environ.get("NEO4J_URI", ""),
    "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    "PINECONE_HOST": os.environ.get("PINECONE_HOST", ""),
    "PINECONE_API_KEY": os.environ.get("PINECONE_API_KEY", ""),
    # Embeddings & Search
    "JINA_API_KEY": os.environ.get("JINA_API_KEY", ""),
    "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
    # HF Tokens (3 accounts)
    "HF_TOKEN": os.environ.get("HF_TOKEN", ""),
    "HF_TOKEN_2": os.environ.get("HF_TOKEN_2", ""),
    "HF_TOKEN_3": os.environ.get("HF_TOKEN_3", ""),
    # GitHub
    "GH_TOKEN": os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", "")),
    "GITHUB_TOKEN": os.environ.get("GITHUB_TOKEN", os.environ.get("GH_TOKEN", "")),
    # VM SSH Access
    "SSH_PRIVATE_KEY": os.environ.get("SSH_PRIVATE_KEY", ""),
    "VM_HOST": os.environ.get("VM_HOST", "34.136.180.66"),
    "VM_USER": os.environ.get("VM_USER", "termius"),
    # Search APIs
    "BRAVE_API_KEY": os.environ.get("BRAVE_API_KEY", ""),
    "EXA_API_KEY": os.environ.get("EXA_API_KEY", ""),
    "ODDS_API_KEY": os.environ.get("ODDS_API_KEY", ""),
    # Kimi 2.5 — coding LLM
    "KIMI_API_KEY": os.environ.get("KIMI_API_KEY", ""),
    # RGWA-specific identity & peer config
    "AGENT_NAME": "RGWA",
    "AGENT_ROLE": "general",
    "EVE_URL": "https://nomos42-nomos-worker-2.hf.space",
    "PEER_AGENTS": "Eve|https://nomos42-nomos-worker-2.hf.space",
}


def main():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN_2 not set. Run: source .env.local")
        sys.exit(1)

    if not LOCAL_DIR.exists():
        print(f"ERROR: OpenClaw source directory not found at {LOCAL_DIR}")
        sys.exit(1)

    api = HfApi(token=HF_TOKEN)

    print(f"Deploying RGWA to {SPACE_ID}...")
    print(f"Source directory: {LOCAL_DIR}")

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
            commit_message="feat: RGWA — autonomous OpenClaw agent with full infra access",
        )
        print("Files uploaded successfully!")
    except Exception as e:
        # Space might not exist yet, create it
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
                commit_message="feat: RGWA — autonomous OpenClaw agent with full infra access",
            )
            print("Files uploaded successfully!")
        else:
            raise

    # Set secrets
    print("\nConfiguring secrets...")
    for key, value in SECRETS.items():
        if value:
            try:
                api.add_space_secret(SPACE_ID, key, value)
                print(f"  Set {key}")
            except Exception as e:
                print(f"  WARN: Failed to set {key}: {e}")
        else:
            print(f"  SKIP {key} (empty)")

    # Restart the Space
    print("\nRestarting Space...")
    try:
        api.restart_space(SPACE_ID)
        print("Space restarted!")
    except Exception as e:
        print(f"Restart warning: {e}")

    print(f"\nDone! RGWA will be available at:")
    print(f"  https://lbjlincoln-nomos-rgwa.hf.space")
    print(f"\nTelegram: @RGWAbot")
    print(f"\nMonitor build at:")
    print(f"  https://huggingface.co/spaces/{SPACE_ID}")


if __name__ == "__main__":
    main()
