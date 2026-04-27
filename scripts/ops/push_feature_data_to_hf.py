#!/usr/bin/env python3
"""Push raw feature data files to HF dataset LBJLincoln26/nba-feature-cache.

Files pushed (Colab will pull these to build cache + train Oracle):
  - referee_data.json
  - player_data_merged.json (combined player+coach+altitude+tracking+synergy+position)
  - quarter_data.json
  - polymarket_data.json
  - games-2025-26.json (raw games + scores + odds_data structure proxy)
  - features/engine.py (so Colab can import the same engine)

Usage: HF_TOKEN_NBA=... python3 scripts/ops/push_feature_data_to_hf.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KARP = REPO / "data" / "karpathy"
DATASET = "LBJLincoln26/nba-feature-cache"


def main() -> int:
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN")
    if not tok:
        print("ERR: HF_TOKEN_NBA / HF_TOKEN missing", file=sys.stderr)
        return 1

    files = [
        (KARP / "referee_data.json", "feature_data/referee_data.json"),
        (KARP / "player_data_merged.json", "feature_data/player_data_merged.json"),
        (KARP / "quarter_data.json", "feature_data/quarter_data.json"),
        (KARP / "polymarket_data.json", "feature_data/polymarket_data.json"),
        (REPO.parent / "nomos-nba-agent" / "data" / "historical" / "games-2025-26.json",
         "feature_data/games-2025-26.json"),
        (REPO / "features" / "engine.py", "feature_data/engine.py"),
        (REPO / "data" / "full-odds-2025-26.json", "feature_data/full-odds-2025-26.json"),
    ]

    # Sanity check
    for src, _ in files:
        if not src.exists():
            print(f"WARN: {src} missing — skipping", file=sys.stderr)

    try:
        from huggingface_hub import HfApi, CommitOperationAdd
    except ImportError:
        print("pip install huggingface_hub", file=sys.stderr)
        return 2

    api = HfApi(token=tok)
    api.create_repo(DATASET, repo_type="dataset", private=False, exist_ok=True)

    operations = []
    sizes = []
    for src, dst in files:
        if not src.exists():
            continue
        operations.append(CommitOperationAdd(path_in_repo=dst, path_or_fileobj=str(src)))
        sz_mb = src.stat().st_size / 1024 / 1024
        sizes.append((dst, sz_mb))

    if not operations:
        print("nothing to push", file=sys.stderr)
        return 1

    commit = api.create_commit(
        repo_id=DATASET, repo_type="dataset",
        operations=operations,
        commit_message=f"[feature_data] {len(operations)} files: enriched ref+player_merged+quarter+polymarket+engine",
    )
    print(f"\npushed {len(operations)} files in commit {commit.oid[:12]}")
    for dst, sz in sizes:
        print(f"  {dst:50s} {sz:6.2f} MB")
    print(f"\ndataset: https://huggingface.co/datasets/{DATASET}/tree/main/feature_data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
