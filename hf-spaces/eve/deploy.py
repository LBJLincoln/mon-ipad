#!/usr/bin/env python3
"""Deploy Eve to lbjlincoln/nomos-eve-agent HF Space.

Uploads all files via HF Hub API and restarts the Space.

Usage:
    source .env.local
    python3 hf-spaces/eve/deploy.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from huggingface_hub import HfApi, CommitOperationAdd
from pathlib import Path

# Config
SPACE_ID = "lbjlincoln/nomos-eve-agent"
HF_TOKEN = os.environ.get("HF_TOKEN_2") or os.environ.get("HF_TOKEN")
LOCAL_DIR = Path(__file__).parent


def main():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN_2 (or HF_TOKEN) not set. Run: source .env.local")
        sys.exit(1)

    api = HfApi(token=HF_TOKEN)

    print(f"Deploying Eve to {SPACE_ID}...")

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
    api.create_commit(
        repo_id=SPACE_ID,
        repo_type="space",
        operations=operations,
        commit_message="fix: switch LLM from Gemini (dead quota) to Groq Kimi K2",
    )
    print("Files uploaded successfully!")

    # Restart the Space
    print("\nRestarting Space...")
    try:
        api.restart_space(SPACE_ID)
        print("Space restarted!")
    except Exception as e:
        print(f"Restart warning: {e}")

    print(f"\nDone! Eve available at: https://{SPACE_ID.replace('/', '-')}.hf.space")
    print(f"Dashboard: https://lbjlincoln-nomos-eve-agent.hf.space/?token=huggingclaw")


if __name__ == "__main__":
    main()
