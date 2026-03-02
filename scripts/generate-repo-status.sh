#!/bin/bash
# Generate repo-status.json with status of all 7 repos
# Output: docs/repo-status.json
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT="$REPO_ROOT/docs/repo-status.json"

python3 - "$REPO_ROOT" "$OUTPUT" << 'PYEOF'
import json, subprocess, sys, os
from datetime import datetime, timezone

repo_root = sys.argv[1]
output = sys.argv[2]

REPOS = [
    ("mon-ipad", "/home/termius/mon-ipad", "Control Tower", None),
    ("rag-dashboard", "/home/termius/rag-dashboard", "Dashboard", "https://nomos-dashboard-alexis-morets-projects.vercel.app"),
    ("rag-tests", "/home/termius/rag-tests", "Eval & Tests", None),
    ("rag-website", "/home/termius/rag-website", "Website (4 sectors)", "https://nomos-ai-pied.vercel.app"),
    ("rag-data-ingestion", "/home/termius/rag-data-ingestion", "Data Ingestion", None),
    ("rag-pme-connectors", "/home/termius/rag-pme-connectors", "PME Connectors", "https://nomos-pme-connectors-alexis-morets-projects.vercel.app"),
    ("rag-pme-usecases", "/home/termius/rag-pme-usecases", "PME Use Cases", "https://nomos-pme-usecases-alexis-morets-projects.vercel.app"),
]

repos_data = []
for name, dir_path, role, url in REPOS:
    entry = {"name": name, "role": role, "status": "ok"}

    if os.path.isdir(os.path.join(dir_path, ".git")):
        try:
            info = subprocess.check_output(
                ["git", "-C", dir_path, "log", "-1", "--format=%H|%s|%ci"],
                text=True, timeout=10
            ).strip().split("|", 2)
            entry["lastCommit"] = info[0][:8]
            entry["lastCommitMsg"] = info[1][:80] if len(info) > 1 else ""
            entry["lastCommitDate"] = info[2] if len(info) > 2 else ""
        except Exception:
            entry["lastCommit"] = "error"
            entry["status"] = "error"

        try:
            subprocess.check_call(
                ["git", "-C", dir_path, "ls-remote", "--exit-code", "origin", "HEAD"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10
            )
            entry["remoteReachable"] = True
        except Exception:
            entry["remoteReachable"] = False
    else:
        entry["lastCommit"] = "not-cloned"
        entry["remoteReachable"] = False
        entry["status"] = "missing"

    if url:
        entry["url"] = url
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5", url],
                capture_output=True, text=True, timeout=10
            )
            code = int(result.stdout.strip())
            entry["httpStatus"] = code
            if code != 200:
                entry["status"] = "degraded"
        except Exception:
            entry["httpStatus"] = 0
            entry["status"] = "degraded"

    repos_data.append(entry)

output_data = {
    "repos": repos_data,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
}

with open(output, "w") as f:
    json.dump(output_data, f, indent=2, ensure_ascii=False)

print(f"Generated: {output}")
PYEOF
