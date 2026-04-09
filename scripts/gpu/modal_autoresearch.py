"""
Modal GPU Autoresearch — Serverless Karpathy Loop
==================================================
Runs on Modal's serverless GPUs (T4/A10G/A100).
Free tier: ~30 min/month GPU, or $10 gets ~5h T4.

Usage:
  modal run scripts/gpu/modal_autoresearch.py          # Run one iteration batch
  modal run scripts/gpu/modal_autoresearch.py --hours 2 # Run for 2 hours
  modal deploy scripts/gpu/modal_autoresearch.py       # Deploy as cron

Two Modal accounts available:
  - lbjlincoln (primary)
  - aurelienm03master (secondary)
"""

import modal
import os

# Modal app
app = modal.App("nba-karpathy-autoresearch")

# GPU image with all best ML libraries pre-installed
gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        # Core ML
        "numpy>=1.26", "scikit-learn>=1.5", "pandas>=2.2",
        # Tree-based (GPU-accelerated)
        "xgboost>=2.1", "lightgbm>=4.5", "catboost>=1.2",
        # Neural nets
        "torch>=2.4", "pytorch-tabnet>=4.1",
        # SOTA tabular
        "tabicl>=0.3",
        # Hyperparameter tuning
        "optuna>=4.0",
        # Data
        "psycopg2-binary", "nba_api",
        # HF for cloning
        "huggingface_hub",
    )
    .apt_install("git")
)


@app.function(
    image=gpu_image,
    gpu="T4",  # T4 (free tier friendly) or "A10G" or "A100"
    timeout=7200,  # 2 hours max
    secrets=[
        modal.Secret.from_name("hf-token"),
        modal.Secret.from_name("supabase-url"),
    ],
)
def run_autoresearch(hours: float = 1.0):
    """Run Karpathy autoresearch loop on Modal GPU."""
    import subprocess, sys, json, time
    from pathlib import Path

    WORK = Path("/tmp/nba-quant-gpu")
    WORK.mkdir(exist_ok=True)

    hf_token = os.environ.get("HF_TOKEN", "")
    db_url = os.environ.get("DATABASE_URL", "")

    # Clone feature engine from HF Space
    repo_dir = WORK / "nba-quant-space"
    if not repo_dir.exists():
        print("Cloning feature engine from HF Space...")
        os.system(f"git clone --depth 1 https://user:{hf_token}@huggingface.co/spaces/Nomos42/nba-quant {repo_dir}")

    # Clone the autoresearch script
    script_dir = WORK / "scripts"
    script_dir.mkdir(exist_ok=True)

    # Download autoresearch from GitHub
    os.system(f"git clone --depth 1 https://github.com/LBJLincoln/mon-ipad.git {WORK / 'mon-ipad'}")

    autoresearch_path = WORK / "mon-ipad" / "scripts" / "gpu" / "karpathy_gpu_autoresearch.py"

    if autoresearch_path.exists():
        sys.path.insert(0, str(WORK / "mon-ipad" / "scripts" / "gpu"))
        sys.path.insert(0, str(repo_dir))

        # Override session limit
        import karpathy_gpu_autoresearch as kar
        kar.SESSION_LIMITS = {"modal": int(hours * 3600)}
        kar.PLATFORM = "modal"
        kar.WORK = WORK
        kar.run_autoresearch()
    else:
        print(f"Autoresearch script not found at {autoresearch_path}")
        # Fallback: run inline
        _run_inline_autoresearch(WORK, repo_dir, hours)

    # Return results
    result_file = WORK / "result.json"
    if result_file.exists():
        return json.loads(result_file.read_text())
    return {"status": "completed", "hours": hours}


def _run_inline_autoresearch(work, repo_dir, hours):
    """Fallback inline autoresearch if script not found."""
    import sys, time, json, numpy as np
    from pathlib import Path

    sys.path.insert(0, str(repo_dir))

    print("Running inline autoresearch...")

    # Build features
    try:
        from features.engine import NBAFeatureEngine
        import psycopg2

        db_url = os.environ.get("DATABASE_URL", "")
        games = []
        if db_url:
            conn = psycopg2.connect(db_url, connect_timeout=30)
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 15000")
            for row in cur.fetchall():
                if row[0]:
                    games.append(row[0] if isinstance(row[0], dict) else json.loads(row[0]))
            cur.close()
            conn.close()

        if games:
            engine = NBAFeatureEngine()
            X, y, feature_names = engine.build(games)
            X = np.nan_to_num(np.array(X, dtype=np.float64))
            y = np.array(y, dtype=np.int32)
            print(f"Features built: {X.shape}")

            # Simple XGBoost training as test
            import xgboost as xgb
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.metrics import brier_score_loss

            tscv = TimeSeriesSplit(n_splits=3)
            briers = []
            for train_idx, test_idx in tscv.split(X):
                model = xgb.XGBClassifier(
                    max_depth=6, learning_rate=0.1, n_estimators=200,
                    tree_method="hist", device="cuda", verbosity=0
                )
                model.fit(X[train_idx], y[train_idx])
                probs = model.predict_proba(X[test_idx])[:, 1]
                briers.append(brier_score_loss(y[test_idx], probs))

            avg_brier = np.mean(briers)
            print(f"GPU XGBoost Brier: {avg_brier:.5f}")

            result = {"brier": avg_brier, "features": X.shape[1], "games": len(games)}
            (work / "result.json").write_text(json.dumps(result))
    except Exception as e:
        print(f"Inline autoresearch failed: {e}")
        import traceback
        traceback.print_exc()


@app.function(
    image=gpu_image,
    gpu="T4",
    timeout=14400,  # 4 hours
    schedule=modal.Cron("0 6 * * *"),  # Daily at 6 AM UTC
    secrets=[
        modal.Secret.from_name("hf-token"),
        modal.Secret.from_name("supabase-url"),
    ],
)
def daily_autoresearch():
    """Daily scheduled autoresearch run (4 hours)."""
    return run_autoresearch.local(hours=4.0)


@app.local_entrypoint()
def main(hours: float = 1.0):
    """Local entrypoint for `modal run`."""
    print(f"Launching autoresearch on Modal GPU for {hours}h...")
    result = run_autoresearch.remote(hours=hours)
    print(f"Result: {result}")
