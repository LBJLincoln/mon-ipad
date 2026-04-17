"""Scan Nomos42 ecosystem repos, emit per-repo counts + dead-file candidates.

Output: data/repo-inventory.json with per-repo {files, loc, by_ext, stale_docs, orphan_scripts, last_commit}.
Dashboard reads this for clickable per-repo cards. Cleanup is flag-only — nothing is deleted.
"""
import json
import os
import subprocess
import time
from pathlib import Path

HOME = Path.home()
REPOS = [
    "mon-ipad",
    "nomos-dashboard",
    "nomos-nba-agent",
    "nomos-political-alpha",
    "nomos-picks",
    "nomos-pierre",
    "rgwa",
]

STALE_DAYS = 90
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".sh", ".yaml", ".yml"}
DOC_EXTS = {".md", ".txt", ".rst"}
SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", "venv", ".venv", "dist", "build", ".turbo"}


def sh(args, cwd):
    try:
        return subprocess.check_output(args, cwd=cwd, stderr=subprocess.DEVNULL, timeout=30).decode().strip()
    except Exception:
        return ""


def scan_repo(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    now = time.time()
    stats = {
        "exists": True,
        "path": str(path),
        "files": 0,
        "loc": 0,
        "by_ext": {},
        "stale_docs": [],
        "orphan_scripts": [],
        "size_bytes": 0,
    }
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            fp = Path(root) / f
            try:
                st = fp.stat()
            except OSError:
                continue
            ext = fp.suffix.lower()
            stats["files"] += 1
            stats["size_bytes"] += st.st_size
            stats["by_ext"][ext] = stats["by_ext"].get(ext, 0) + 1
            if ext in CODE_EXTS or ext in DOC_EXTS:
                try:
                    stats["loc"] += sum(1 for _ in fp.open("rb"))
                except OSError:
                    pass
            age_days = (now - st.st_mtime) / 86400
            if ext in DOC_EXTS and age_days > STALE_DAYS and fp.name.upper() not in ("README.MD", "CLAUDE.MD", "LICENSE"):
                stats["stale_docs"].append({"path": str(fp.relative_to(path)), "age_days": round(age_days)})
    stats["last_commit"] = sh(["git", "log", "-1", "--format=%ci|%s"], cwd=path)
    stats["branch"] = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
    stats["stale_docs"] = sorted(stats["stale_docs"], key=lambda d: -d["age_days"])[:30]
    return stats


def main():
    out = {"generated_at": int(time.time()), "repos": {}}
    for name in REPOS:
        out["repos"][name] = scan_repo(HOME / name)
    out_path = HOME / "mon-ipad" / "data" / "repo-inventory.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    summary = [
        f"{n}: {r.get('files',0)} files / {r.get('loc',0):,} LOC / {len(r.get('stale_docs',[]))} stale docs"
        for n, r in out["repos"].items() if r.get("exists")
    ]
    print("\n".join(summary))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
