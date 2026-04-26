#!/usr/bin/env python3
"""HF Harvest helper — used by every GPU training script (Modal/Lightning/Colab/Kaggle/ZeroGPU).

Closes the months-long bleed of "training runs that never get saved".

CALL CONTRACT — every GPU script calls this AT THE END:

    from scripts.gpu.hf_harvest import push_oracle_artifact

    push_oracle_artifact(
        bundle={
            'model': trained_model,
            'calibrator': isotonic_or_None,
            'feature_indices': [...200 indices...],
            'feature_names': [...names...],
            'cv_brier_mean': 0.21570,
            'cv_brier_per_fold': [...],
            'config': {...},
            'n_samples': N,
        },
        source='colab-tabicl',  # 'modal' | 'lightning' | 'colab-tabicl' | 'kaggle' | 'zerogpu'
        brier=0.21570,
        notes='TabICL 186f iter 129',
    )

What it does:
  1. Saves bundle to /tmp/{source}-oracle.pkl
  2. Uploads to HF dataset LBJLincoln26/nba-oracle-archive/{source}-{utc}.pkl
  3. Compares brier vs current production Oracle (LBJLincoln26/nba-oracle-model)
  4. If better → uploads as nba-oracle.pkl on the production dataset (becomes new Oracle)
  5. Always returns (uploaded_path, became_production: bool, prev_brier, new_brier)

Logging:
  - Writes /home/termius/mon-ipad/data/gpu-harvest/{source}-{utc}.json receipt
  - Writes line to /home/termius/mon-ipad/data/gpu-harvest/log.jsonl

Failure modes (all non-fatal — the training itself isn't lost):
  - HF_TOKEN missing: returns (None, False, None, brier) so caller can warn
  - HF API down: same
  - Bundle malformed: ValueError raised early so caller's training run still saves locally

USAGE INSIDE Modal/Lightning/etc — must have HF_TOKEN in env:

    Modal:     modal secret create hf-token HF_TOKEN=hf_GKGLi...
    Lightning: lightning add-secret HF_TOKEN hf_GKGLi...
    Colab:     userdata.get('HF_TOKEN')
    Kaggle:    kaggle secrets attach
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ARCHIVE_DATASET = "LBJLincoln26/nba-oracle-archive"
PRODUCTION_DATASET = "LBJLincoln26/nba-oracle-model"
PRODUCTION_FILE = "nba-oracle.pkl"
SUMMARY_FILE = "summary.json"

VALID_SOURCES = {"modal", "lightning", "colab-tabicl", "colab-tree", "kaggle", "zerogpu", "vm-local"}


def _validate_bundle(bundle: Dict[str, Any]) -> None:
    required = {"model", "feature_indices", "cv_brier_mean"}
    missing = required - bundle.keys()
    if missing:
        raise ValueError(f"hf_harvest: bundle missing required keys {missing}")
    if not isinstance(bundle.get("feature_indices"), (list, tuple)):
        raise ValueError("hf_harvest: feature_indices must be list/tuple")
    if not (0.0 < float(bundle.get("cv_brier_mean")) < 1.0):
        raise ValueError(f"hf_harvest: cv_brier_mean must be in (0,1), got {bundle.get('cv_brier_mean')}")


def _local_log(receipt: Dict[str, Any]) -> None:
    log_dir = Path("/home/termius/mon-ipad/data/gpu-harvest")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = receipt["utc"].replace(":", "-")
        (log_dir / f"{receipt['source']}-{ts}.json").write_text(json.dumps(receipt, indent=2))
        with (log_dir / "log.jsonl").open("a") as f:
            f.write(json.dumps(receipt) + "\n")
    except Exception as e:
        print(f"[hf_harvest] local log err (non-fatal): {e}", file=sys.stderr)


def _fetch_current_production_brier(api) -> Optional[float]:
    """Pull current production summary.json to compare brier."""
    try:
        from huggingface_hub import hf_hub_download
        p = hf_hub_download(
            repo_id=PRODUCTION_DATASET, filename=SUMMARY_FILE, repo_type="dataset",
            token=api.token if hasattr(api, "token") else None,
        )
        s = json.loads(Path(p).read_text())
        b = s.get("cv_brier_mean")
        return float(b) if b is not None else None
    except Exception:
        return None


def push_oracle_artifact(
    bundle: Dict[str, Any],
    source: str,
    brier: Optional[float] = None,
    notes: str = "",
    promote_if_better: bool = True,
) -> Tuple[Optional[str], bool, Optional[float], float]:
    """Push trained Oracle bundle to HF, optionally promote if Brier improves.

    Returns (archive_path, became_production, prev_brier, new_brier).
    On HF auth failure: (None, False, None, new_brier) — local log still written.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"hf_harvest: source must be one of {VALID_SOURCES}")
    _validate_bundle(bundle)

    new_brier = float(brier if brier is not None else bundle["cv_brier_mean"])
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    receipt = {
        "source": source,
        "utc": utc,
        "new_brier": new_brier,
        "n_features": len(bundle["feature_indices"]),
        "n_samples": int(bundle.get("n_samples", 0)),
        "model_type": type(bundle["model"]).__name__,
        "notes": notes,
    }

    # Save bundle locally first (no auth required)
    out_path = Path(f"/tmp/{source}-oracle-{utc}.pkl")
    with out_path.open("wb") as f:
        pickle.dump(bundle, f)
    receipt["local_path"] = str(out_path)
    receipt["local_size_mb"] = round(out_path.stat().st_size / 1024 / 1024, 2)

    # Try HF auth + push (HF_TOKEN_NBA is LBJLincoln26-owner, prefer it)
    tok = os.environ.get("HF_TOKEN_NBA") or os.environ.get("HF_TOKEN") or ""
    if not tok:
        receipt["upload_status"] = "no_hf_token"
        _local_log(receipt)
        print(f"[hf_harvest] WARNING: no HF_TOKEN env var; bundle saved locally only at {out_path}",
              file=sys.stderr)
        return (None, False, None, new_brier)

    try:
        from huggingface_hub import HfApi, CommitOperationAdd
        api = HfApi(token=tok)
        # Ensure archive dataset exists
        try:
            api.create_repo(ARCHIVE_DATASET, repo_type="dataset", private=False, exist_ok=True)
        except Exception:
            pass
        archive_filename = f"{source}-{utc}.pkl"
        api.upload_file(
            path_or_fileobj=str(out_path),
            path_in_repo=archive_filename,
            repo_id=ARCHIVE_DATASET, repo_type="dataset",
            commit_message=f"[hf_harvest] {source} Brier={new_brier:.5f} {notes}".strip(),
        )
        receipt["archive_url"] = f"https://huggingface.co/datasets/{ARCHIVE_DATASET}/blob/main/{archive_filename}"
        receipt["upload_status"] = "archived"
    except Exception as e:
        receipt["upload_status"] = f"archive_err: {e}"
        _local_log(receipt)
        print(f"[hf_harvest] archive push failed: {e}", file=sys.stderr)
        return (None, False, None, new_brier)

    # Compare vs production
    prev_brier = _fetch_current_production_brier(api)
    became_production = False
    if promote_if_better and (prev_brier is None or new_brier < prev_brier):
        try:
            # Push as production pkl + update summary.json
            api.upload_file(
                path_or_fileobj=str(out_path),
                path_in_repo=PRODUCTION_FILE,
                repo_id=PRODUCTION_DATASET, repo_type="dataset",
                commit_message=f"[hf_harvest] PROMOTE {source} Brier={new_brier:.5f} (was {prev_brier})",
            )
            summary = {
                "cv_brier_mean": new_brier,
                "cv_brier_per_fold": bundle.get("cv_brier_per_fold", []),
                "feature_indices": list(bundle["feature_indices"]),
                "feature_names": list(bundle.get("feature_names", [])),
                "config": bundle.get("config", {}),
                "n_samples": int(bundle.get("n_samples", 0)),
                "trained_at": utc,
                "trained_on": source,
                "promoted_from_brier": prev_brier,
            }
            api.upload_file(
                path_or_fileobj=json.dumps(summary, indent=2).encode(),
                path_in_repo=SUMMARY_FILE,
                repo_id=PRODUCTION_DATASET, repo_type="dataset",
                commit_message=f"[hf_harvest] summary update {source} Brier={new_brier:.5f}",
            )
            became_production = True
            receipt["promoted"] = True
            receipt["prev_brier"] = prev_brier
        except Exception as e:
            receipt["promoted"] = False
            receipt["promote_err"] = str(e)

    _local_log(receipt)
    print(f"[hf_harvest] {source} Brier {new_brier:.5f} archived "
          f"(prev_prod={prev_brier} promoted={became_production})", file=sys.stderr)
    return (receipt.get("archive_url"), became_production, prev_brier, new_brier)


if __name__ == "__main__":
    # Self-test: load existing Kaggle Oracle, push as smoke-test artifact
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        b = pickle.load(open("/tmp/nba-oracle.pkl", "rb"))
        result = push_oracle_artifact(b, source="vm-local", notes="harvest smoke test", promote_if_better=False)
        print("smoke result:", result)
