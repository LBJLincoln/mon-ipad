#!/usr/bin/env python3
"""
GPU Orchestrator — Triggers Kaggle & Colab GPU training for NBA Quant AI

Used by Eve (OpenClaw agent) to:
1. Submit GPU experiments to Supabase queue
2. Trigger Kaggle kernel runs via API
3. Poll for results
4. Report back to the agent

Usage:
  python3 gpu-orchestrator.py submit --model ft_transformer --desc "Test FT-Transformer with focal loss"
  python3 gpu-orchestrator.py trigger-kaggle
  python3 gpu-orchestrator.py status
  python3 gpu-orchestrator.py poll --wait
"""
import os, sys, json, time, subprocess, argparse, uuid
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────
KAGGLE_KERNEL_ID = "alexismoret6/nba-quant-gpu-runner"
KAGGLE_KERNEL_DIR = "/tmp/kaggle-kernel"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_KEY", ""))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
BASELINE_BRIER = 0.2205

GPU_MODELS = [
    "mlp", "mlp_residual", "lstm", "ft_transformer", "tabnet",
    "node", "mc_dropout_rnn", "saint", "tft",
    "xgboost_gpu", "lightgbm_gpu", "catboost_gpu"
]


def submit_experiment(model_type, experiment_type, description, hyperparams=None, priority=8):
    """Submit a GPU experiment to Supabase queue."""
    exp_id = f"exp_eve_{uuid.uuid4().hex[:8]}"
    payload = {
        "experiment_id": exp_id,
        "agent_name": "eve_orchestrator",
        "experiment_type": experiment_type,
        "description": description,
        "params": json.dumps({
            "model_type": model_type,
            "hyperparams": hyperparams or {},
        }),
        "priority": priority,
        "status": "pending",
        "target_space": "gpu",
        "baseline_brier": BASELINE_BRIER,
    }

    if SUPABASE_URL and SUPABASE_KEY:
        import urllib.request
        url = f"{SUPABASE_URL}/rest/v1/nba_experiments"
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Prefer", "return=representation")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
                print(f"[OK] Experiment {exp_id} submitted to Supabase")
                return {"success": True, "experiment_id": exp_id, "data": result}
        except Exception as e:
            print(f"[ERROR] Supabase insert failed: {e}")
            return {"success": False, "error": str(e)}
    elif DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO nba_experiments
                   (experiment_id, agent_name, experiment_type, description, params,
                    priority, status, target_space, baseline_brier)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (exp_id, payload["agent_name"], experiment_type, description,
                 payload["params"], priority, "pending", "gpu", BASELINE_BRIER)
            )
            conn.commit()
            cur.close()
            conn.close()
            print(f"[OK] Experiment {exp_id} submitted via psycopg2")
            return {"success": True, "experiment_id": exp_id}
        except Exception as e:
            print(f"[ERROR] psycopg2 insert failed: {e}")
            return {"success": False, "error": str(e)}
    else:
        print("[ERROR] No database connection configured (SUPABASE_URL or DATABASE_URL)")
        return {"success": False, "error": "No DB configured"}


def trigger_kaggle():
    """Trigger a Kaggle kernel run."""
    kernel_dir = Path(KAGGLE_KERNEL_DIR)
    if not kernel_dir.exists():
        print(f"[ERROR] Kaggle kernel dir not found: {kernel_dir}")
        print("[INFO] Pull first: kaggle kernels pull alexismoret6/nba-quant-gpu-runner -p /tmp/kaggle-kernel")
        return False

    result = subprocess.run(
        ["kaggle", "kernels", "push", "-p", str(kernel_dir)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        print(f"[OK] Kaggle kernel pushed: {result.stdout.strip()}")
        return True
    else:
        print(f"[ERROR] Kaggle push failed: {result.stderr}")
        return False


def kaggle_status():
    """Check Kaggle kernel status."""
    result = subprocess.run(
        ["kaggle", "kernels", "status", KAGGLE_KERNEL_ID],
        capture_output=True, text=True, timeout=30
    )
    status = result.stdout.strip()
    print(f"Kaggle kernel status: {status}")
    return status


def kaggle_output():
    """Download Kaggle kernel output."""
    out_dir = Path("/tmp/kaggle-output")
    out_dir.mkdir(exist_ok=True)
    result = subprocess.run(
        ["kaggle", "kernels", "output", KAGGLE_KERNEL_ID, "-p", str(out_dir)],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        print(f"[OK] Output downloaded to {out_dir}")
        for f in out_dir.iterdir():
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    else:
        print(f"[ERROR] Output download failed: {result.stderr}")


def check_pending():
    """Check pending GPU experiments in queue."""
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                SELECT experiment_id, agent_name, experiment_type, description, priority, created_at
                FROM nba_experiments
                WHERE status = 'pending' AND (target_space IN ('gpu', 'any') OR target_space IS NULL)
                ORDER BY priority DESC, created_at ASC
                LIMIT 20
            """)
            rows = cur.fetchall()
            cur.execute("""
                SELECT status, COUNT(*) FROM nba_experiments
                WHERE target_space IN ('gpu', 'any') OR target_space IS NULL
                GROUP BY status
            """)
            counts = dict(cur.fetchall())
            cur.close()
            conn.close()

            print(f"GPU Experiment Queue:")
            print(f"  Pending: {counts.get('pending', 0)}")
            print(f"  Running: {counts.get('running', 0)}")
            print(f"  Completed: {counts.get('completed', 0)}")
            print(f"  Failed: {counts.get('failed', 0)}")
            if rows:
                print(f"\nNext {len(rows)} pending:")
                for r in rows:
                    print(f"  [{r[4]}] {r[0]} ({r[2]}) — {r[3][:80]}")
            return counts
        except Exception as e:
            print(f"[ERROR] DB query failed: {e}")
            return {}
    else:
        print("[ERROR] DATABASE_URL not configured")
        return {}


def get_results(limit=10):
    """Get recent GPU experiment results."""
    if DATABASE_URL:
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("""
                SELECT experiment_id, agent_name, experiment_type,
                       result_brier, result_accuracy, status, completed_at
                FROM nba_experiments
                WHERE status IN ('completed', 'failed')
                  AND (target_space IN ('gpu', 'any') OR target_space IS NULL)
                ORDER BY completed_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            cur.close()
            conn.close()

            print(f"Recent GPU Results (last {limit}):")
            for r in rows:
                brier = f"Brier={r[3]:.4f}" if r[3] else "N/A"
                acc = f"Acc={r[4]:.4f}" if r[4] else "N/A"
                status = r[5]
                print(f"  {r[0]} ({r[2]}) — {brier} {acc} [{status}]")
            return rows
        except Exception as e:
            print(f"[ERROR] DB query failed: {e}")
            return []
    else:
        print("[ERROR] DATABASE_URL not configured")
        return []


def submit_benchmark(models=None):
    """Submit a full GPU benchmark comparing all models."""
    models = models or GPU_MODELS
    return submit_experiment(
        model_type="benchmark",
        experiment_type="gpu_benchmark",
        description=f"Full GPU benchmark: {', '.join(models)}",
        hyperparams={"models": models},
        priority=9
    )


def main():
    parser = argparse.ArgumentParser(description="GPU Orchestrator for NBA Quant AI")
    sub = parser.add_subparsers(dest="command")

    # submit
    p_sub = sub.add_parser("submit", help="Submit GPU experiment")
    p_sub.add_argument("--model", required=True, choices=GPU_MODELS + ["benchmark"])
    p_sub.add_argument("--type", default="model_test",
                       choices=["model_test", "gpu_benchmark", "feature_test", "calibration_test"])
    p_sub.add_argument("--desc", required=True, help="Experiment description")
    p_sub.add_argument("--priority", type=int, default=8)

    # trigger-kaggle
    sub.add_parser("trigger-kaggle", help="Trigger Kaggle kernel run")

    # status
    sub.add_parser("status", help="Check queue and Kaggle status")

    # results
    p_res = sub.add_parser("results", help="Get recent results")
    p_res.add_argument("--limit", type=int, default=10)

    # benchmark
    sub.add_parser("benchmark", help="Submit full GPU benchmark")

    # poll
    p_poll = sub.add_parser("poll", help="Trigger Kaggle and poll until done")
    p_poll.add_argument("--interval", type=int, default=60)

    args = parser.parse_args()

    if args.command == "submit":
        submit_experiment(args.model, args.type, args.desc, priority=args.priority)
    elif args.command == "trigger-kaggle":
        trigger_kaggle()
    elif args.command == "status":
        check_pending()
        print()
        kaggle_status()
    elif args.command == "results":
        get_results(args.limit)
    elif args.command == "benchmark":
        submit_benchmark()
    elif args.command == "poll":
        trigger_kaggle()
        while True:
            time.sleep(args.interval)
            status = kaggle_status()
            if "complete" in status.lower() or "error" in status.lower():
                print(f"\nKaggle kernel finished: {status}")
                kaggle_output()
                break
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
