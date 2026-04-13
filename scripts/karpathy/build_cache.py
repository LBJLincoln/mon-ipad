#!/usr/bin/env python3
"""
Build real NBA feature cache from game data.

Loads game JSON files from nomos-nba-agent (or other data dirs),
runs the feature engine, and saves a compressed .npz cache
that nba_iterate.py can load instantly.

Designed to run on GH Actions (7GB RAM, 45 min timeout).

Usage:
    python3 scripts/karpathy/build_cache.py
    python3 scripts/karpathy/build_cache.py --max-seasons 3  # recent only
"""

import json
import sys
import time
import argparse
import logging
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_PATH = ROOT / "data" / "karpathy" / "nba_cached_data.npz"

log = logging.getLogger("cache-builder")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_games(max_seasons: int = 0) -> list:
    """Load game data from all available sources."""
    data_dirs = [
        ROOT.parent / "nomos-nba-agent" / "data" / "historical",
        ROOT / "hf-space" / "data" / "historical",
        ROOT / "data" / "historical-odds",
    ]

    games = []
    files_found = []

    for d in data_dirs:
        if not d.exists():
            log.info(f"  Skip (not found): {d}")
            continue
        for f in sorted(d.glob("games-*.json")):
            files_found.append(f)

    if not files_found:
        log.error("NO game data files found in any data directory!")
        log.error(f"Searched: {[str(d) for d in data_dirs]}")
        sys.exit(1)

    # If max_seasons specified, take only the most recent N files
    if max_seasons > 0 and len(files_found) > max_seasons:
        files_found = files_found[-max_seasons:]

    for f in files_found:
        try:
            raw = json.loads(f.read_text())
            if isinstance(raw, list):
                games.extend(raw)
            elif isinstance(raw, dict) and "games" in raw:
                games.extend(raw["games"])
            log.info(f"  Loaded {f.name}: {len(raw) if isinstance(raw, list) else len(raw.get('games', []))} games")
        except Exception as e:
            log.warning(f"  Failed to load {f}: {e}")

    log.info(f"Total games loaded: {len(games)}")
    return games


def build_features(games: list) -> tuple:
    """Run the feature engine on game data."""
    # Import engine from hf-space
    engine_path = ROOT / "hf-space" / "features"
    if not engine_path.exists():
        log.error(f"Feature engine not found at {engine_path}")
        sys.exit(1)

    sys.path.insert(0, str(ROOT / "hf-space"))
    from features.engine import NBAFeatureEngine

    log.info("Building features with NBAFeatureEngine...")
    engine = NBAFeatureEngine()

    t0 = time.time()
    X, y, feature_names = engine.build(games)
    elapsed = time.time() - t0

    X = np.nan_to_num(np.array(X, dtype=np.float32))
    y = np.array(y, dtype=np.float64)

    log.info(f"Features built in {elapsed:.1f}s: {X.shape[0]} games x {X.shape[1]} features")
    log.info(f"y distribution: mean={y.mean():.3f}, sum={y.sum():.0f}/{len(y)}")

    # Sanity checks
    assert X.shape[0] > 100, f"Too few games: {X.shape[0]}"
    assert X.shape[1] > 50, f"Too few features: {X.shape[1]}"
    assert 0.3 < y.mean() < 0.7, f"Suspicious y distribution: mean={y.mean():.3f}"

    # Verify features are real (not synthetic noise)
    if all(fn.startswith("feat_") for fn in feature_names[:20]):
        log.error("SYNTHETIC DATA DETECTED — feature names are 'feat_000' etc!")
        sys.exit(1)

    return X, y, feature_names


def save_cache(X, y, feature_names):
    """Save the cache as compressed .npz."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Remove old synthetic cache if present
    for old in CACHE_PATH.parent.glob("nba_cached_data.npz*"):
        if "synthetic" not in old.name:
            old.unlink()
            log.info(f"Removed old cache: {old.name}")

    np.savez_compressed(
        CACHE_PATH,
        X=X,
        y=y,
        feature_names=np.array(feature_names),
    )

    size_mb = CACHE_PATH.stat().st_size / (1024 * 1024)
    log.info(f"Cache saved: {CACHE_PATH} ({size_mb:.1f} MB)")
    log.info(f"Shape: {X.shape[0]} games x {X.shape[1]} features")
    log.info(f"Sample feature names: {feature_names[:5]}")


def main():
    parser = argparse.ArgumentParser(description="Build real NBA feature cache")
    parser.add_argument(
        "--max-seasons", type=int, default=0,
        help="Limit to N most recent seasons (0 = all)",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only verify existing cache, don't rebuild",
    )
    args = parser.parse_args()

    if args.verify_only:
        if not CACHE_PATH.exists():
            log.error(f"No cache at {CACHE_PATH}")
            sys.exit(1)
        data = np.load(CACHE_PATH, allow_pickle=True)
        X, y = data["X"], data["y"]
        names = list(data["feature_names"])
        log.info(f"Cache OK: {X.shape[0]} games x {X.shape[1]} features")
        log.info(f"y mean: {y.mean():.3f}")
        log.info(f"First 5 features: {names[:5]}")
        if all(n.startswith("feat_") for n in names[:20]):
            log.error("SYNTHETIC DATA — cache is garbage!")
            sys.exit(1)
        log.info("Cache verified: REAL DATA")
        return

    log.info("=" * 50)
    log.info("NBA Feature Cache Builder")
    log.info("=" * 50)

    t0 = time.time()
    games = load_games(max_seasons=args.max_seasons)
    X, y, feature_names = build_features(games)
    save_cache(X, y, feature_names)

    log.info(f"Total time: {time.time() - t0:.1f}s")
    log.info("Done — nba_iterate.py will use this cache automatically")


if __name__ == "__main__":
    main()
