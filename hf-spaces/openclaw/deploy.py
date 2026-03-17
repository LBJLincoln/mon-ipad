#!/usr/bin/env python3
"""Deploy OpenClaw to Nomos42/worker-2 HF Space.

Uploads all files via HF Hub API, configures secrets, and starts the Space.

Usage:
    source .env.local
    python3 hf-spaces/openclaw/deploy.py
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from huggingface_hub import HfApi, CommitOperationAdd
from pathlib import Path

# Config
SPACE_ID = "Nomos42/nomos-worker-2"
HF_TOKEN = os.environ.get("HF_TOKEN_3")
LOCAL_DIR = Path(__file__).parent

# Secrets to configure on the Space
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
    # Telegram
    "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "ADMIN_TELEGRAM_ID": os.environ.get("ADMIN_TELEGRAM_ID", "6582544948"),
    "TELEGRAM_CHANNEL_ID": os.environ.get("TELEGRAM_CHANNEL_ID", ""),
    # Databases
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
}


def main():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN_3 not set. Run: source .env.local")
        sys.exit(1)

    api = HfApi(token=HF_TOKEN)

    print(f"Deploying OpenClaw to {SPACE_ID}...")

    # Collect all files to upload
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
            commit_message="Deploy OpenClaw v2026.3.11-beta.1",
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
                commit_message="Deploy OpenClaw v2026.3.11-beta.1",
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

    print(f"\nDone! OpenClaw will be available at:")
    print(f"  https://nomos42-nomos-worker-2.hf.space")
    print(f"\nMonitor build at:")
    print(f"  https://huggingface.co/spaces/{SPACE_ID}")


if __name__ == "__main__":
    main()
