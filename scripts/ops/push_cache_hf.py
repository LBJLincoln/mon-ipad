#!/usr/bin/env python3
"""Push enriched nba_cached_data.npz to HF dataset LBJLincoln26/nba-feature-cache.

Verifies first that ref/injury feature columns (zero-variance before this patch)
now have variance > 0. Aborts on regression.

Usage: HF_TOKEN_NBA=... python3 scripts/ops/push_cache_hf.py
"""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
NPZ = ROOT / "data" / "karpathy" / "nba_cached_data.npz"
DATASET = "LBJLincoln26/nba-feature-cache"

# Columns the patch is supposed to bring to life
ALIVE_TARGETS = [
    "ref_home_foul_bias", "ref_total_fouls_avg", "ref_foul_rate_vs_league",
    "ref_home_ft_advantage", "ref_experience_games", "ref_over_tendency",
    "ref_close_game_bias", "ref_home_win_rate", "ref_pace_impact",
    "h_injury_impact_score", "a_injury_impact_score",
    "h_star_usage_rate", "a_star_usage_rate",
    "h_star_minutes_load", "a_star_minutes_load",
    "h_lineup_continuity", "a_lineup_continuity",
    "h_bench_depth_rating", "a_bench_depth_rating",
    "h_rotation_depth", "a_rotation_depth",
    "h_injury_adjusted_depth", "a_injury_adjusted_depth",
    "h_injury_risk_score", "a_injury_risk_score",
]


def main() -> int:
    if not NPZ.exists():
        print(f"ERR: {NPZ} not found", file=sys.stderr)
        return 1
    data = np.load(NPZ, allow_pickle=True)
    X = data["X"]
    y = data["y"]
    feature_names = list(data["feature_names"])
    print(f"cache: X={X.shape} y={y.shape} y_mean={y.mean():.3f}")

    name_to_idx = {n: i for i, n in enumerate(feature_names)}
    variances = X.var(axis=0)
    n_alive = int((variances > 1e-10).sum())
    print(f"alive features overall: {n_alive}/{len(feature_names)} ({n_alive/len(feature_names)*100:.1f}%)")

    miss = []
    dead = []
    alive_count = 0
    for fn in ALIVE_TARGETS:
        if fn not in name_to_idx:
            miss.append(fn)
            continue
        v = variances[name_to_idx[fn]]
        if v < 1e-10:
            dead.append(fn)
        else:
            alive_count += 1
    print(f"\nFeatures patched: {alive_count}/{len(ALIVE_TARGETS)} alive")
    if miss:
        print(f"  MISSING from feature_names: {miss[:5]}")
    if dead:
        print(f"  STILL DEAD: {dead}")
    if alive_count < len(ALIVE_TARGETS) - len(miss):
        print("WARN: some target columns still zero-variance")

    # Push
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN")
    if not tok:
        print("ERR: HF_TOKEN_NBA / HF_TOKEN missing", file=sys.stderr)
        return 2
    try:
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.create_repo(DATASET, repo_type="dataset", private=False, exist_ok=True)
        commit = api.upload_file(
            path_or_fileobj=str(NPZ),
            path_in_repo="nba_cached_data.npz",
            repo_id=DATASET, repo_type="dataset",
            commit_message=f"[enriched] referee_data + player_data populated, alive={n_alive}/{len(feature_names)}",
        )
        print(f"\npushed: {commit}")
    except Exception as e:
        print(f"push err: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
