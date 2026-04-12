#!/usr/bin/env python3
"""
Nomos42 — Feature Cache Sync
==============================
Downloads a prebuilt feature matrix from the fleet-best HF Space and uploads
it to an HF Dataset repo, making it instantly available to every GPU session.

Problem solved:
  Each Kaggle/Colab/ZeroGPU session rebuilds the feature matrix from scratch,
  which costs ~30 min of expensive GPU time on pure CPU work.  With this cache,
  GPU sessions download the matrix in <30s and spend all session time training.

Workflow:
  1. Check if local cache is fresh (<24h old) → skip if yes
  2. Try to fetch /api/feature_cache from S15 / S11 / S10 (islands cache the matrix)
  3. Download the .pkl to data/feature-cache/nba-feature-matrix.pkl
  4. Upload to HF Dataset repo (LBJLincoln/nomos42-feature-cache) via HF Content API
  5. Write a gpu-session-cache-loader.py snippet for Kaggle/Colab notebooks

To unlock step 2, add this endpoint to HF Space app.py:
    @app.get("/api/feature_cache")
    def feature_cache_info():
        import os
        pkl_path = Path("/app/data/nba-feature-matrix.pkl")
        if not pkl_path.exists():
            return {"available": False}
        stat = pkl_path.stat()
        return {
            "available": True,
            "cache_url": f"{os.environ.get('SPACE_HOST', '')}/api/feature_cache_download",
            "n_games": ...,         # read from metadata
            "n_features": ...,
            "engine_version": ENGINE_VERSION,
            "size_mb": stat.st_size / 1e6,
            "created_ts": stat.st_mtime,
        }

Usage:
    python3 scripts/gpu-burst/feature-cache-sync.py
    HF_TOKEN=hf_xxx python3 scripts/gpu-burst/feature-cache-sync.py

Cron (daily 07:00 UTC — dispatched by compute-orchestrator.py):
    0 7 * * * python3 /home/termius/mon-ipad/scripts/gpu-burst/feature-cache-sync.py
"""

import json
import os
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT  = Path(__file__).resolve().parent.parent.parent
CACHE_DIR  = REPO_ROOT / "data" / "feature-cache"
LOG_FILE   = CACHE_DIR / "sync.log"
CACHE_META = CACHE_DIR / "cache-metadata.json"

HF_DATASET_REPO = "LBJLincoln/nomos42-feature-cache"
HF_DATASET_FILE = "nba-feature-matrix.pkl"

# Islands to check for /api/feature_cache, in priority order
HF_ISLANDS = {
    "S15": "https://nomos42-nba-evo-6.hf.space",   # fleet best (0.22041)
    "S11": "https://nomos42-nba-quant-2.hf.space",  # exploration
    "S10": "https://nomos42-nba-quant.hf.space",    # exploitation
    "S16": "https://lbjlincoln26-nba-evo-s16.hf.space",
    "S17": "https://lbjlincoln26-nba-evo-s17.hf.space",
}

MAX_CACHE_AGE_HOURS = 24


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════

def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str, level: str = "INFO"):
    line = f"[{ts()}] [{level}] {msg}"
    print(line)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, token: str = "", timeout: int = 30) -> Optional[dict]:
    headers = {"User-Agent": "Nomos42-CacheSync/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"GET {url}: {e}", "WARN")
        return None


def cache_is_fresh() -> bool:
    """Return True if local cache was created within MAX_CACHE_AGE_HOURS."""
    if not CACHE_META.exists():
        return False
    try:
        meta = json.loads(CACHE_META.read_text())
        age_h = (time.time() - float(meta.get("created_ts", 0))) / 3600
        return age_h < MAX_CACHE_AGE_HOURS
    except Exception:
        return False


# ══════════════════════════════════════════════════════════
# CACHE DOWNLOAD FROM ISLAND
# ══════════════════════════════════════════════════════════

def fetch_cache_meta(name: str, url: str, token: str) -> Optional[dict]:
    """Query /api/feature_cache on an island. Returns metadata dict or None."""
    resp = http_get(f"{url}/api/feature_cache", token=token, timeout=20)
    if resp and resp.get("available") and resp.get("cache_url"):
        log(f"{name}: cache available — {resp.get('n_games', '?')} games, "
            f"{resp.get('n_features', '?')} features, v{resp.get('engine_version', '?')}, "
            f"{resp.get('size_mb', 0):.1f} MB")
        return resp
    return None


def download_cache(cache_url: str, token: str, local_path: Path) -> bool:
    """Download the feature matrix .pkl to local_path. Returns True on success."""
    log(f"Downloading feature cache from {cache_url}...")
    headers = {"User-Agent": "Nomos42-CacheSync/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(cache_url, headers=headers)
        with urllib.request.urlopen(req, timeout=300, context=_ssl_ctx()) as resp:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(resp.read())
        size_mb = local_path.stat().st_size / 1e6
        log(f"Downloaded: {size_mb:.1f} MB → {local_path}")
        return True
    except Exception as e:
        log(f"Download failed: {e}", "ERROR")
        return False


# ══════════════════════════════════════════════════════════
# UPLOAD TO HF DATASET
# ══════════════════════════════════════════════════════════

def upload_to_hf_dataset(local_path: Path, hf_token: str) -> bool:
    """
    Upload the .pkl to HuggingFace Dataset repo via the HF Content API.
    GPU sessions then download from:
      https://huggingface.co/datasets/{HF_DATASET_REPO}/resolve/main/{HF_DATASET_FILE}
    """
    if not hf_token:
        log("No HF_TOKEN — skipping HF Dataset upload (GPU sessions can't access cache)", "WARN")
        return False

    upload_url = (
        f"https://huggingface.co/api/datasets/{HF_DATASET_REPO}"
        f"/upload/{HF_DATASET_FILE}"
    )
    log(f"Uploading to HF Dataset {HF_DATASET_REPO}/{HF_DATASET_FILE}...")
    try:
        with open(local_path, "rb") as f:
            data = f.read()
        req = urllib.request.Request(
            upload_url,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {hf_token}",
                "Content-Type": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as resp:
            result = json.loads(resp.read())
        log(f"HF Dataset upload OK: {result.get('url', 'uploaded')}")
        return True
    except Exception as e:
        log(f"HF Dataset upload failed: {e}", "WARN")
        return False


# ══════════════════════════════════════════════════════════
# GPU SESSION SNIPPET
# ══════════════════════════════════════════════════════════

def write_gpu_session_snippet():
    """
    Write gpu-session-cache-loader.py — paste at top of Kaggle/Colab notebooks
    to download the feature cache instead of rebuilding (saves ~30 min).
    """
    snippet_path = CACHE_DIR / "gpu-session-cache-loader.py"
    snippet = f'''#!/usr/bin/env python3
"""
Nomos42 — Feature Cache Loader for GPU Sessions
================================================
Paste at the top of Kaggle/Colab/ZeroGPU notebooks.
Downloads the prebuilt feature matrix from HF Datasets instead of
rebuilding from raw data (~30 min saved per GPU session).

After running: X_train, X_test, y_train, y_test, feature_names are available.
"""
import os, ssl, json, urllib.request
from pathlib import Path

HF_DATASET = "{HF_DATASET_REPO}"
CACHE_FILE  = "{HF_DATASET_FILE}"
HF_TOKEN    = os.environ.get("HF_TOKEN", "")

def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def load_feature_cache():
    import pickle
    local = Path(f"/tmp/{{CACHE_FILE}}")
    if not local.exists():
        url = f"https://huggingface.co/datasets/{{HF_DATASET}}/resolve/main/{{CACHE_FILE}}"
        print(f"Downloading feature cache...")
        headers = {{"User-Agent": "Nomos42/1.0"}}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {{HF_TOKEN}}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=120, context=_ssl_ctx()) as r:
                local.write_bytes(r.read())
            print(f"Downloaded: {{local.stat().st_size / 1e6:.1f}} MB")
        except Exception as e:
            print(f"Cache download failed: {{e}} — fall back to full rebuild")
            return None
    with open(local, "rb") as f:
        cache = pickle.load(f)
    print(f"Cache loaded: {{cache[\'n_games\']}} games, {{cache[\'n_features\']}} features, "
          f"engine {{cache[\'engine_version\']}}")
    return cache

_cache = load_feature_cache()
if _cache:
    X_train         = _cache["X_train"]
    X_test          = _cache["X_test"]
    y_train         = _cache["y_train"]
    y_test          = _cache["y_test"]
    feature_names   = _cache["feature_names"]
    feature_indices = _cache["feature_indices_all"]
    print(f"Ready: X_train={{len(X_train)}}x{{len(X_train[0])}}, X_test={{len(X_test)}}x{{len(X_test[0])}}")
else:
    print("Cache unavailable — rebuild features manually")
'''
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    snippet_path.write_text(snippet)
    log(f"GPU session snippet: {snippet_path}")
    return snippet_path


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def run_sync():
    log("=== Feature Cache Sync ===")

    hf_token = os.environ.get("HF_TOKEN", "")

    if cache_is_fresh():
        meta = json.loads(CACHE_META.read_text())
        age_h = (time.time() - float(meta.get("created_ts", 0))) / 3600
        log(f"Cache is fresh ({age_h:.1f}h old, max {MAX_CACHE_AGE_HOURS}h) — skipping download")
    else:
        log("Cache stale or missing — polling islands for /api/feature_cache...")

        cache_meta   = None
        source_island = None

        for name, url in HF_ISLANDS.items():
            meta = fetch_cache_meta(name, url, hf_token)
            if meta:
                cache_meta    = meta
                source_island = name
                break

        if cache_meta and cache_meta.get("cache_url"):
            local_path = CACHE_DIR / HF_DATASET_FILE
            ok = download_cache(cache_meta["cache_url"], hf_token, local_path)
            if ok:
                cache_meta["created_ts"] = time.time()
                cache_meta["source_island"] = source_island
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                CACHE_META.write_text(json.dumps(cache_meta, indent=2))
                # Upload to HF Dataset so GPU sessions can pull it
                upload_to_hf_dataset(local_path, hf_token)
        else:
            log("No island has /api/feature_cache yet — endpoint needs to be added to HF Space", "WARN")
            log("See docstring above for the endpoint implementation to paste into app.py", "INFO")

    # Always write the GPU session snippet (idempotent, <1ms)
    snippet_path = write_gpu_session_snippet()
    log(f"Paste {snippet_path} at the top of Kaggle/Colab notebooks to skip 30-min rebuild")


if __name__ == "__main__":
    run_sync()
