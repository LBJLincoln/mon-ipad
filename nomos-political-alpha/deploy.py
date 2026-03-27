#!/usr/bin/env python3
"""
Deploy Nomos Political Alpha to HF Spaces + VM Cron.

Usage:
  python deploy.py space HF_TOKEN         # Deploy HF Space (P1)
  python deploy.py cron                    # Install VM cron jobs
  python deploy.py dashboard              # Add /political route to Vercel dashboard
  python deploy.py supabase               # Create Supabase tables
  python deploy.py all HF_TOKEN           # Everything
"""

import os, sys, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ═══════════════════════════════════════════════════════════
# HF SPACE DEPLOYMENT
# ═══════════════════════════════════════════════════════════

def deploy_hf_space(token, space_id="LBJLincoln26/nomos-political-alpha"):
    """Deploy Political Alpha to HF Space."""
    try:
        from huggingface_hub import HfApi, upload_folder
    except ImportError:
        print("pip install huggingface_hub")
        return

    api = HfApi(token=token)

    # Create space if needed
    try:
        api.create_repo(repo_id=space_id, repo_type="space", space_sdk="gradio",
                       space_hardware="cpu-basic", private=False, exist_ok=True)
        print(f"✅ Space created/exists: {space_id}")
    except Exception as e:
        print(f"Space creation: {e}")

    # Files to upload
    files_to_upload = [
        "hf-space/app.py",
        "features/political_engine.py",
        "features/__init__.py",
        "models/kelly.py",
        "models/donor_power_index.py",
        "models/__init__.py",
        "ops/fetch_political_data.py",
        "ops/__init__.py",
        "evolution/run_logger.py",
        "evolution/__init__.py",
        "calibration/isotonic_calibrator.py",
        "calibration/__init__.py",
        "requirements.txt",
    ]

    for f in files_to_upload:
        src = ROOT / f
        if src.exists():
            # Map to HF space path
            if f.startswith("hf-space/"):
                dest = f.replace("hf-space/", "")
            else:
                dest = f
            api.upload_file(path_or_fileobj=str(src), path_in_repo=dest,
                          repo_id=space_id, repo_type="space", token=token)
            print(f"  ✅ {f} → {dest}")
        else:
            print(f"  ❌ {f} not found")

    print(f"\n🚀 Deployed to https://huggingface.co/spaces/{space_id}")


# ═══════════════════════════════════════════════════════════
# VM CRON SETUP
# ═══════════════════════════════════════════════════════════

CRON_JOBS = """
# Nomos42 Political Alpha — Data Fetchers
# Fast fetch (signals + polymarket): every 30 min
*/30 * * * * cd /home/termius/nomos-political-alpha && python3 ops/fetch_political_data.py --fast >> /tmp/political-fast.log 2>&1

# Full fetch (all data): every 6 hours
0 */6 * * * cd /home/termius/nomos-political-alpha && python3 ops/fetch_political_data.py --all >> /tmp/political-full.log 2>&1

# Insider trades: daily after market close (10 PM UTC = 4 PM ET)
0 22 * * 1-5 cd /home/termius/nomos-political-alpha && python3 ops/fetch_political_data.py --insider >> /tmp/political-insider.log 2>&1

# Stock prices: daily at 10:30 PM UTC
30 22 * * 1-5 cd /home/termius/nomos-political-alpha && python3 ops/fetch_political_data.py --prices >> /tmp/political-prices.log 2>&1
"""

def setup_vm_cron():
    """Print cron jobs to add to VM."""
    print("Add these cron jobs to your VM (34.136.180.66):")
    print("Run: crontab -e")
    print(CRON_JOBS)


# ═══════════════════════════════════════════════════════════
# SUPABASE TABLES
# ═══════════════════════════════════════════════════════════

SUPABASE_SQL = """
-- Nomos42 Political Alpha Tables

CREATE TABLE IF NOT EXISTS political_donors (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10) NOT NULL,
  name VARCHAR(200),
  sector VARCHAR(50),
  donated BIGINT DEFAULT 0,
  channel VARCHAR(50),
  favor TEXT,
  favor_delivered BOOLEAN DEFAULT FALSE,
  dpi_score FLOAT DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(ticker)
);

CREATE TABLE IF NOT EXISTS political_signals (
  id SERIAL PRIMARY KEY,
  signal_date DATE NOT NULL,
  signal_type VARCHAR(50),
  title TEXT,
  affected_sectors TEXT[],
  affected_tickers TEXT[],
  source VARCHAR(50),
  url TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_signals_date ON political_signals(signal_date DESC);

CREATE TABLE IF NOT EXISTS polymarket_whales (
  id SERIAL PRIMARY KEY,
  market_id VARCHAR(200),
  question TEXT,
  whale_side VARCHAR(10),
  whale_size FLOAT,
  whale_price FLOAT,
  maker_address VARCHAR(50),
  timestamp TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS insider_trades (
  id SERIAL PRIMARY KEY,
  ticker VARCHAR(10),
  file_date DATE,
  form_type VARCHAR(20),
  filer_name TEXT,
  transaction_type VARCHAR(20),
  shares FLOAT,
  price FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_insider_ticker ON insider_trades(ticker, file_date DESC);

CREATE TABLE IF NOT EXISTS political_predictions (
  id SERIAL PRIMARY KEY,
  prediction_date DATE NOT NULL,
  ticker VARCHAR(10) NOT NULL,
  signal_type VARCHAR(50),
  predicted_prob FLOAT,
  kelly_stake FLOAT,
  actual_outcome INT,
  excess_return FLOAT,
  model_type VARCHAR(50),
  model_generation INT,
  features_used INT,
  brier_cv FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_predictions_date ON political_predictions(prediction_date DESC);

CREATE TABLE IF NOT EXISTS political_experiments (
  id SERIAL PRIMARY KEY,
  space_id VARCHAR(100),
  generation INT,
  cycle INT,
  best_brier FLOAT,
  best_roi FLOAT,
  best_sharpe FLOAT,
  best_model_type VARCHAR(50),
  n_features INT,
  feature_engine_version VARCHAR(50),
  pop_size INT,
  mutation_rate FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS political_bankroll (
  id SERIAL PRIMARY KEY,
  date DATE NOT NULL,
  balance FLOAT,
  daily_pnl FLOAT,
  total_bets INT,
  wins INT,
  losses INT,
  total_wagered FLOAT,
  total_profit FLOAT,
  max_drawdown_pct FLOAT,
  created_at TIMESTAMP DEFAULT NOW()
);
"""

def create_supabase_tables():
    """Print SQL to create tables in Supabase."""
    print("Run this SQL in your Supabase SQL Editor:")
    print(SUPABASE_SQL)


# ═══════════════════════════════════════════════════════════
# DASHBOARD ROUTE
# ═══════════════════════════════════════════════════════════

def add_dashboard_route():
    """Instructions for adding /political to nomosdashboard.vercel.app."""
    print("""
Add to nomosdashboard.vercel.app:

1. Create pages/political.html (or equivalent in your framework)
2. Add navigation link: [🏛️ Political Alpha](/political)
3. Dashboard sections:
   - Donor Power Index table (DPI scores)
   - Recent policy signals feed
   - Polymarket whale activity
   - Insider trading heatmap
   - P&L tracking (same format as /nba)
   - Active positions & Kelly recommendations

4. API endpoints to consume:
   - HF Space: https://lbjlincoln26-nomos-political-alpha.hf.space/api/results
   - Supabase: political_predictions, political_bankroll tables
""")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "space":
        token = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HF_TOKEN", "")
        if not token:
            print("Usage: python deploy.py space HF_TOKEN")
            sys.exit(1)
        deploy_hf_space(token)

    elif cmd == "cron":
        setup_vm_cron()

    elif cmd == "supabase":
        create_supabase_tables()

    elif cmd == "dashboard":
        add_dashboard_route()

    elif cmd == "all":
        token = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("HF_TOKEN", "")
        deploy_hf_space(token)
        print("\n" + "="*60 + "\n")
        setup_vm_cron()
        print("\n" + "="*60 + "\n")
        create_supabase_tables()
        print("\n" + "="*60 + "\n")
        add_dashboard_route()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
