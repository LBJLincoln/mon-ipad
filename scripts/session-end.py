#!/usr/bin/env python3
"""Session end script — run at the end of each Claude Code session.

Usage: python3 scripts/session-end.py [--message "what was done"]

This script:
1. Syncs workflows from n8n
2. Regenerates status.json
3. Updates session-state.md
4. Shows a summary of what to commit
"""

import os
import sys
import json
import subprocess
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def sync_workflows():
    sync_script = os.path.join(ROOT, "workflows", "sync.py")
    if os.path.exists(sync_script):
        try:
            result = subprocess.run(
                ["python3", sync_script],
                capture_output=True, text=True, cwd=ROOT, timeout=30
            )
            if result.returncode == 0:
                print(f"{GREEN}Workflows synced from n8n{RESET}")
            else:
                print(f"{YELLOW}Workflow sync failed: {result.stderr[:200]}{RESET}")
        except Exception as e:
            print(f"{YELLOW}Workflow sync skipped: {e}{RESET}")
    else:
        print(f"{YELLOW}sync.py not found{RESET}")

def regenerate_status():
    gen_script = os.path.join(ROOT, "eval", "generate_status.py")
    if os.path.exists(gen_script):
        try:
            result = subprocess.run(
                ["python3", gen_script],
                capture_output=True, text=True, cwd=ROOT, timeout=15
            )
            if result.returncode == 0:
                print(f"{GREEN}status.json regenerated{RESET}")
            else:
                print(f"{YELLOW}Status generation failed: {result.stderr[:200]}{RESET}")
        except Exception as e:
            print(f"{YELLOW}Status generation skipped: {e}{RESET}")

def update_session_state(message=""):
    state_path = os.path.join(ROOT, "context", "session-state.md")
    status_path = os.path.join(ROOT, "docs", "status.json")

    date = datetime.now().strftime("%Y-%m-%d")

    pipeline_status = ""
    if os.path.exists(status_path):
        with open(status_path) as f:
            status = json.load(f)
        pipelines = status.get("pipelines", {})
        for name, data in pipelines.items():
            acc = data.get("accuracy", 0)
            tested = data.get("tested", 0)
            met = "Oui" if data.get("met", False) else "Non"
            pipeline_status += f"| {name.capitalize()} | {tested}q | {acc}% | {met} |\n"

    content = f"""# Etat de Session

> Ce fichier est mis a jour a chaque fin de session Claude Code.
> Lire `docs/status.json` pour les metriques live.

---

## Derniere session

- **Date** : {date}
- **Ce qui a ete fait** : {message or "Session terminee"}
- **Ce qui reste a faire** :
  1. Consulter docs/status.json pour les gaps actuels
  2. Continuer les iterations sur le pipeline prioritaire
  3. Atteindre 10/10 sur chaque pipeline
  4. Lancer l'eval 200q Phase 1

---

## Pipeline Status (auto-genere)

| Pipeline | Dernier test | Score | Gate atteinte ? |
|----------|-------------|-------|-----------------|
{pipeline_status}
---

## Notes pour la prochaine session

- Commencer par `python3 scripts/session-start.py`
- Ou directement : `cat docs/status.json`
- Suivre `context/workflow-process.md` pour le processus
"""

    with open(state_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"{GREEN}session-state.md updated{RESET}")

def show_git_summary():
    result = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, cwd=ROOT
    )
    changes = result.stdout.strip()
    if changes:
        print(f"\n{BOLD}Files to commit:{RESET}")
        for line in changes.split("\n"):
            print(f"  {line}")
        print(f"\n{YELLOW}Remember to commit and push!{RESET}")
    else:
        print(f"{GREEN}No changes to commit{RESET}")

def main():
    message = ""
    if len(sys.argv) > 2 and sys.argv[1] == "--message":
        message = " ".join(sys.argv[2:])

    print_header("SESSION END - Multi-RAG Orchestrator")

    print(f"\n{BOLD}1. Syncing workflows{RESET}")
    sync_workflows()

    print(f"\n{BOLD}2. Regenerating status{RESET}")
    regenerate_status()

    print(f"\n{BOLD}3. Updating session state{RESET}")
    update_session_state(message)

    print(f"\n{BOLD}4. Git summary{RESET}")
    show_git_summary()

    print(f"\n{BOLD}{GREEN}Session end complete.{RESET}")

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}  {text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")

if __name__ == "__main__":
    main()
