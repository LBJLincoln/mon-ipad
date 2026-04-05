#!/usr/bin/env python3
"""
Deploy all 9 department council spaces to HuggingFace.

Usage:
    source /home/termius/mon-ipad/.env.local
    python3 /home/termius/mon-ipad/council-spaces/deploy-all.py
    python3 /home/termius/mon-ipad/council-spaces/deploy-all.py --dept d1  # single dept
    python3 /home/termius/mon-ipad/council-spaces/deploy-all.py --dry-run
"""

import os
import sys
import json
import shutil
import tempfile
import argparse
from pathlib import Path

# Load .env.local
env_file = Path("/home/termius/mon-ipad/.env.local")
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))

from huggingface_hub import HfApi
from huggingface_hub.utils import RepositoryNotFoundError

# -- Department configurations -------------------------------------------------

DEPTS = [
    {
        "dept_id": "d1", "name": "research",
        "account": "LBJLincoln", "token_env": "HF_TOKEN",
        "emoji": "🔬",
        "mission": "Find techniques from academic papers to improve Brier score.",
        "color_from": "blue", "color_to": "purple",
        "preferred_model": "openrouter:qwen/qwen3.6-plus:free",
    },
    {
        "dept_id": "d2", "name": "engineering",
        "account": "LBJLincoln", "token_env": "HF_TOKEN",
        "emoji": "⚙️",
        "mission": "Implement features and code improvements to reduce Brier score below 0.20.",
        "color_from": "gray", "color_to": "blue",
        "preferred_model": "cerebras:qwen-3-235b-a22b-instruct-2507",
    },
    {
        "dept_id": "d3", "name": "evolution",
        "account": "LBJLincoln26", "token_env": "HF_TOKEN_2",
        "emoji": "🧬",
        "mission": "Optimize genetic algorithm parameters across 6 NBA evolution islands.",
        "color_from": "green", "color_to": "yellow",
        "preferred_model": "cerebras:qwen-3-235b-a22b-instruct-2507",
    },
    {
        "dept_id": "d4", "name": "product",
        "account": "LBJLincoln26", "token_env": "HF_TOKEN_2",
        "emoji": "📦",
        "mission": "Improve user-facing products: dashboard, Telegram bot, Bloomberg terminal.",
        "color_from": "yellow", "color_to": "red",
        "preferred_model": "openrouter:qwen/qwen3.6-plus:free",
    },
    {
        "dept_id": "d5", "name": "business",
        "account": "Nomos42", "token_env": "HF_TOKEN_3",
        "emoji": "💼",
        "mission": "Grow revenue, track bankroll performance, optimize bet sizing.",
        "color_from": "indigo", "color_to": "purple",
        "preferred_model": "openrouter:deepseek/deepseek-r1:free",
    },
    {
        "dept_id": "d6", "name": "evaluation",
        "account": "Nomos42", "token_env": "HF_TOKEN_3",
        "emoji": "📊",
        "mission": "Audit prediction quality, calibration, and catch anomalies.",
        "color_from": "red", "color_to": "yellow",
        "preferred_model": "groq:llama-3.3-70b-versatile",
    },
    {
        "dept_id": "d7", "name": "infra",
        "account": "TESTforge42", "token_env": "HF_TOKEN_FORGE",
        "emoji": "🏗️",
        "mission": "Monitor and maintain all 6 HF evolution islands, VM, and crons.",
        "color_from": "gray", "color_to": "green",
        "preferred_model": "groq:llama-3.1-8b-instant",
    },
    {
        "dept_id": "d8", "name": "finance",
        "account": "TESTforge42", "token_env": "HF_TOKEN_FORGE",
        "emoji": "💰",
        "mission": "Track bankroll, ROI, burn rate, and financial health.",
        "color_from": "yellow", "color_to": "green",
        "preferred_model": "cerebras:qwen-3-235b-a22b-instruct-2507",
    },
    {
        "dept_id": "d9", "name": "cross-repo",
        "account": "TESTforge42", "token_env": "HF_TOKEN_FORGE",
        "emoji": "🔗",
        "mission": "Ensure consistency across all 4 repos: engine parity, cron sync, docs.",
        "color_from": "purple", "color_to": "blue",
        "preferred_model": "openrouter:qwen/qwen3.6-plus:free",
    },
]

TEMPLATE_DIR = Path("/home/termius/mon-ipad/council-spaces/template")


def make_readme(dept: dict) -> str:
    """Generate HF Space README.md with YAML front matter."""
    return f"""---
title: Nomos42 Dept {dept['dept_id'].upper()} {dept['name'].title()}
emoji: {dept['emoji']}
colorFrom: {dept['color_from']}
colorTo: {dept['color_to']}
sdk: gradio
sdk_version: "5.12.0"
app_file: app.py
pinned: true
---

# Nomos42 -- {dept['dept_id'].upper()}: {dept['name'].upper()} Council

Autonomous Karpathy autoresearch loop for Nomos42 NBA Quant AI.
Runs 24/7 on CPU. Uses free LLM inference (HF Router / Cerebras / Groq / OpenRouter).

**Mission:** {dept['mission']}

**Loop:** SCAN -> THINK (LLM) -> DECIDE -> ACT -> LOG (every 30 minutes)
"""


def build_space_folder(dept: dict, base_dir: Path) -> Path:
    """Create a temporary folder with all files for one space."""
    space_dir = base_dir / f"{dept['dept_id']}-{dept['name']}"
    space_dir.mkdir(parents=True, exist_ok=True)

    # Copy app.py
    shutil.copy2(TEMPLATE_DIR / "app.py", space_dir / "app.py")

    # Copy requirements.txt
    shutil.copy2(TEMPLATE_DIR / "requirements.txt", space_dir / "requirements.txt")

    # Generate README.md
    (space_dir / "README.md").write_text(make_readme(dept))

    return space_dir


def deploy_space(dept: dict, dry_run: bool = False) -> bool:
    """Create HF Space, upload files, set secrets."""
    dept_id = dept["dept_id"]
    name = dept["name"]
    account = dept["account"]
    token = os.environ.get(dept["token_env"], "")
    space_id = f"{account}/nomos-dept-{dept_id}-{name}"

    print(f"\n{'='*60}")
    print(f"  {dept_id.upper()}: {name.upper()}")
    print(f"  Space: {space_id}")
    print(f"  Account: {account} (token: {dept['token_env']})")
    print(f"{'='*60}")

    if not token:
        print(f"  SKIP -- {dept['token_env']} not set")
        return False

    if dry_run:
        print(f"  DRY RUN -- would create {space_id}")
        return True

    api = HfApi(token=token)

    # Step 1: Create repo (space) if it doesn't exist
    try:
        api.repo_info(repo_id=space_id, repo_type="space")
        print(f"  Space already exists")
    except RepositoryNotFoundError:
        print(f"  Creating space...")
        try:
            api.create_repo(
                repo_id=space_id,
                repo_type="space",
                space_sdk="gradio",
                private=False,
            )
            print(f"  Created: {space_id}")
        except Exception as e:
            print(f"  CREATE FAILED: {e}")
            return False
    except Exception as e:
        print(f"  Repo check error: {e}")
        # Try creating anyway
        try:
            api.create_repo(
                repo_id=space_id,
                repo_type="space",
                space_sdk="gradio",
                private=False,
            )
            print(f"  Created: {space_id}")
        except Exception as e2:
            print(f"  CREATE FAILED: {e2}")
            return False

    # Step 2: Build folder and upload
    with tempfile.TemporaryDirectory() as tmpdir:
        space_dir = build_space_folder(dept, Path(tmpdir))
        print(f"  Uploading files from {space_dir}...")
        try:
            api.upload_folder(
                folder_path=str(space_dir),
                repo_id=space_id,
                repo_type="space",
                commit_message=f"Deploy {dept_id.upper()} {name} council space",
            )
            print(f"  Files uploaded successfully")
        except Exception as e:
            print(f"  UPLOAD FAILED: {e}")
            return False

    # Step 3: Set secrets
    secrets = {
        "DEPT_ID": dept_id,
        "DEPT_NAME": name,
        "DEPT_MISSION": dept["mission"],
        "LOOP_INTERVAL_MINUTES": "30",
        "PREFERRED_MODEL": dept.get("preferred_model", ""),
    }

    # Add LLM API keys if available
    for key_env in ["CEREBRAS_API_KEY", "GROQ_API_KEY"]:
        val = os.environ.get(key_env, "")
        if val:
            secrets[key_env] = val

    or_key = os.environ.get("OPENROUTER_KEY_QUANTITATIVE", "") or os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        secrets["OPENROUTER_API_KEY"] = or_key

    vm_url = os.environ.get("VM_API_URL", "")
    if vm_url:
        secrets["VM_API_URL"] = vm_url

    print(f"  Setting {len(secrets)} secrets...")
    secrets_ok = True
    for key, val in secrets.items():
        if not val:
            continue
        try:
            api.add_space_secret(repo_id=space_id, key=key, value=val)
        except Exception as e:
            print(f"    Secret '{key}' failed: {e}")
            secrets_ok = False

    if secrets_ok:
        print(f"  All secrets set")
    else:
        print(f"  Some secrets failed (space will still work with defaults)")

    url = f"https://{account.lower()}-nomos-dept-{dept_id}-{name}.hf.space"
    print(f"  URL: {url}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Deploy Nomos42 department council spaces")
    parser.add_argument("--dept", default=None, help="Deploy single dept (e.g. d1)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    depts = DEPTS
    if args.dept:
        depts = [d for d in DEPTS if d["dept_id"] == args.dept]
        if not depts:
            print(f"Unknown dept: {args.dept}")
            sys.exit(1)

    print(f"Deploying {len(depts)} department council spaces...")
    if args.dry_run:
        print("(DRY RUN MODE)")

    results = {}
    for dept in depts:
        ok = deploy_space(dept, dry_run=args.dry_run)
        results[dept["dept_id"]] = ok

    # Summary
    print(f"\n{'='*60}")
    print("DEPLOYMENT SUMMARY")
    print(f"{'='*60}")
    for dept in depts:
        dept_id = dept["dept_id"]
        status = "OK" if results.get(dept_id) else "FAILED"
        account = dept["account"]
        name = dept["name"]
        url = f"https://{account.lower()}-nomos-dept-{dept_id}-{name}.hf.space"
        print(f"  {dept_id.upper()} {name:12s} [{status:6s}] {url}")

    ok_count = sum(1 for v in results.values() if v)
    print(f"\n  {ok_count}/{len(depts)} spaces deployed successfully")


if __name__ == "__main__":
    main()
