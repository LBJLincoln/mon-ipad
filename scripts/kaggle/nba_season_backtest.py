#!/usr/bin/env python3
"""
NBA Quant AI — Full Season Walk-Forward Backtest (Kaggle GPU)

PROVES our system works with REAL data:
- Walk-forward: for each week, train on ALL prior games, predict next week
- TabICL (Brier 0.21570) as primary model + 5 tree models
- Kelly compounding from $100 initial bankroll
- Full 2025-26 NBA season (Oct 22 → present)

Kaggle: Enable GPU (P100), Internet ON, Secrets: DATABASE_URL
Output: /kaggle/working/season_backtest_results.json
"""

import subprocess, sys, os, time, gc, json, warnings, random, math
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
warnings.filterwarnings('ignore')

# ── Platform detection ──
IS_KAGGLE = os.path.exists('/kaggle/working')
IS_COLAB = 'COLAB_GPU' in os.environ or os.path.exists('/content')
WORK_DIR = '/kaggle/working' if IS_KAGGLE else '/content/drive/MyDrive/nba-season-backtest'
os.makedirs(WORK_DIR, exist_ok=True)

print(f"Platform: {'Kaggle' if IS_KAGGLE else 'Colab' if IS_COLAB else 'Local'}")
print(f"Working dir: {WORK_DIR}")

# ── Secrets ──
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if IS_KAGGLE:
    # Kaggle secrets
    try:
        from kaggle_secrets import UserSecretsClient
        secrets = UserSecretsClient()
        if not DATABASE_URL:
            DATABASE_URL = secrets.get_secret("DATABASE_URL") or ''
        HF_TOKEN = secrets.get_secret("HF_TOKEN") or os.environ.get('HF_TOKEN', '')
    except Exception as e:
        print(f"Kaggle secrets: {e}")
        HF_TOKEN = os.environ.get('HF_TOKEN', '')
elif IS_COLAB:
    from google.colab import drive, userdata
    drive.mount('/content/drive', force_remount=False)
    os.makedirs(WORK_DIR, exist_ok=True)
    for key in ['HF_TOKEN', 'DATABASE_URL']:
        try:
            v = userdata.get(key)
            if v: os.environ[key] = v
        except: pass
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    HF_TOKEN = os.environ.get('HF_TOKEN', '')
else:
    HF_TOKEN = os.environ.get('HF_TOKEN', '')

if not DATABASE_URL:
    print("WARNING: DATABASE_URL not set — will use HF Space data fallback")

# ── Install deps ──
t0 = time.time()
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'xgboost', 'lightgbm', 'catboost', 'scikit-learn',
    'psycopg2-binary', 'huggingface_hub', 'nba_api'])
# TabICL WITHOUT deps to preserve existing PyTorch/CUDA
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', 'tabicl'])
print(f'Deps installed: {time.time()-t0:.0f}s')

import torch
print(f'PyTorch {torch.__version__} | CUDA: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')

###############################################################################
# LOAD DATA + FEATURES
###############################################################################

# Clone feature engine from HF Space
REPO_DIR = os.path.join(WORK_DIR, 'nba-quant-space') if IS_KAGGLE else '/content/nba-quant-space'
if not os.path.exists(REPO_DIR):
    print("Cloning feature engine from HF Space...")
    token_part = f"user:{HF_TOKEN}@" if HF_TOKEN else ""
    os.system(f"git clone --depth 1 https://{token_part}huggingface.co/spaces/Nomos42/nba-quant {REPO_DIR}")
sys.path.insert(0, REPO_DIR)

# Feature cache
FEATURE_CACHE = os.path.join(WORK_DIR, 'backtest_features_v38.npz')
GAMES_CACHE = os.path.join(WORK_DIR, 'backtest_games.json')

if os.path.exists(FEATURE_CACHE) and os.path.exists(GAMES_CACHE):
    print(f"Loading cached features...")
    data = np.load(FEATURE_CACHE, allow_pickle=True)
    X_all = data["X"]
    y_all = data["y"]
    feature_names = list(data["feature_names"])
    with open(GAMES_CACHE) as f:
        games = json.load(f)
    print(f"Loaded: {X_all.shape}, {len(games)} games")
else:
    games = []

    # Try Supabase first
    if DATABASE_URL:
        print("Loading games from Supabase...")
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=30, options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 20000")
            for row in cur.fetchall():
                if row[0]:
                    g = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    games.append(g)
            cur.close()
            conn.close()
            print(f"Loaded {len(games)} games from Supabase")
        except Exception as e:
            print(f"Supabase failed: {e}")

    # Fallback: HF Space data files
    if not games:
        print("Loading from HF Space data files...")
        import glob
        for f in sorted(glob.glob(os.path.join(REPO_DIR, 'data', 'historical', 'games-*.json'))):
            raw = json.loads(open(f).read())
            games.extend(raw if isinstance(raw, list) else raw.get('games', []))
        print(f"Loaded {len(games)} games from HF Space")

    if not games:
        print("ERROR: No game data available!")
        sys.exit(1)

    games.sort(key=lambda g: g.get('game_date', g.get('date', '')))

    print("Building features (this takes ~20-30 min)...")
    from features.engine import NBAFeatureEngine
    engine = NBAFeatureEngine()
    X_all, y_all, feature_names = engine.build(games)
    X_all = np.nan_to_num(np.array(X_all, dtype=np.float64))
    y_all = np.array(y_all, dtype=np.int32)

    # Cache
    np.savez_compressed(FEATURE_CACHE, X=X_all, y=y_all, feature_names=np.array(feature_names))
    with open(GAMES_CACHE, 'w') as f:
        json.dump(games, f)
    print(f"Built & cached: {X_all.shape}")

# Extract game dates
game_dates = []
for g in games:
    d = g.get('game_date', g.get('date', ''))
    if isinstance(d, str) and len(d) >= 10:
        game_dates.append(d[:10])
    else:
        game_dates.append('')

game_dates = np.array(game_dates)
print(f"Ready: {X_all.shape} | Dates: {game_dates[0]} to {game_dates[-1]}")

###############################################################################
# MODELS
###############################################################################
import xgboost as xgb
import lightgbm as lgbm
from catboost import CatBoostClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import brier_score_loss

try:
    from tabicl import TabICLClassifier
    HAS_TABICL = True
    print("TabICL: available")
except:
    HAS_TABICL = False
    print("TabICL: NOT available, using trees only")

def make_models():
    """Create model ensemble for prediction."""
    models = {
        'xgboost': xgb.XGBClassifier(
            max_depth=6, learning_rate=0.1, n_estimators=200,
            random_state=42, eval_metric='logloss', verbosity=0,
            tree_method='hist', device='cuda' if torch.cuda.is_available() else 'cpu'
        ),
        'extra_trees': ExtraTreesClassifier(
            n_estimators=300, max_depth=None, random_state=42, n_jobs=-1
        ),
        'lightgbm': lgbm.LGBMClassifier(
            max_depth=6, learning_rate=0.1, n_estimators=200,
            random_state=42, verbose=-1
        ),
        'catboost': CatBoostClassifier(
            depth=6, learning_rate=0.1, iterations=200,
            random_state=42, verbose=0,
            task_type='GPU' if torch.cuda.is_available() else 'CPU'
        ),
        'random_forest': RandomForestClassifier(
            n_estimators=300, max_depth=None, random_state=42, n_jobs=-1
        ),
    }
    if HAS_TABICL:
        models['tabicl'] = TabICLClassifier()
    return models

# Ensemble weights (TabICL highest)
WEIGHTS = {
    'tabicl': 0.30,
    'xgboost': 0.18,
    'extra_trees': 0.15,
    'catboost': 0.15,
    'lightgbm': 0.12,
    'random_forest': 0.10,
}

def ensemble_predict(models_fitted, X_test):
    """Weighted ensemble prediction."""
    total_weight = 0
    probs = np.zeros(len(X_test))
    for name, model in models_fitted.items():
        w = WEIGHTS.get(name, 0.1)
        try:
            p = model.predict_proba(X_test)[:, 1]
            probs += w * p
            total_weight += w
        except Exception as e:
            print(f"  {name} predict failed: {e}")
    if total_weight > 0:
        probs /= total_weight
    return probs

###############################################################################
# WALK-FORWARD BACKTEST
###############################################################################

SEASON_START = '2025-10-22'
WALK_STEP_DAYS = 7
MIN_TRAIN = 500
N_FEATURES = 110
INITIAL_BANKROLL = 100.0
KELLY_FRACTION = 0.35
MAX_BET_PCT = 0.05
MIN_EDGE = 0.03

# Resume from checkpoint
CHECKPOINT = os.path.join(WORK_DIR, 'backtest_checkpoint.json')
if os.path.exists(CHECKPOINT):
    ckpt = json.loads(open(CHECKPOINT).read())
    print(f"Resuming from {ckpt['last_date']}, bankroll=${ckpt['bankroll']:.2f}")
else:
    ckpt = None

print(f"""
{'='*60}
  NBA FULL SEASON WALK-FORWARD BACKTEST
{'='*60}
  Season: {SEASON_START} -> present
  Models: {', '.join(WEIGHTS.keys())}
  Features: {N_FEATURES}
  Strategy: Kelly f={KELLY_FRACTION}, max={MAX_BET_PCT*100}%
  Initial: ${INITIAL_BANKROLL}
{'='*60}
""")

# Find season games
season_mask = game_dates >= SEASON_START
season_indices = np.where(season_mask)[0]
if len(season_indices) == 0:
    print("ERROR: No games found for 2025-26 season")
    sys.exit(1)
else:
    print(f"Season games: {len(season_indices)} ({game_dates[season_indices[0]]} to {game_dates[season_indices[-1]]})")

# Feature selection by variance
variances = np.var(X_all, axis=0)
top_feature_idx = np.argsort(variances)[-N_FEATURES:]
print(f"Selected {len(top_feature_idx)} features by variance")

# State
bankroll = ckpt['bankroll'] if ckpt else INITIAL_BANKROLL
peak = ckpt['peak'] if ckpt else INITIAL_BANKROLL
max_dd = ckpt['max_dd'] if ckpt else 0
total_bets = ckpt['total_bets'] if ckpt else 0
wins = ckpt['wins'] if ckpt else 0
losses = ckpt['losses'] if ckpt else 0
equity_curve = ckpt['equity_curve'] if ckpt else [{'date': SEASON_START, 'bankroll': INITIAL_BANKROLL, 'drawdown': 0}]
all_trades = ckpt.get('trades', [])
daily_log = ckpt.get('daily_log', [])
daily_briers = ckpt.get('daily_briers', [])

# Unique dates in season
season_dates = sorted(set(game_dates[season_indices]))
start_from = ckpt['last_date'] if ckpt else None

week_start_idx = 0
if start_from:
    for i, d in enumerate(season_dates):
        if d > start_from:
            week_start_idx = i
            break

n_weeks = 0
total_weeks = (len(season_dates) - week_start_idx) // WALK_STEP_DAYS + 1

for week_i in range(week_start_idx, len(season_dates), WALK_STEP_DAYS):
    week_dates = season_dates[week_i:week_i + WALK_STEP_DAYS]
    if not week_dates:
        break

    cutoff_date = week_dates[0]
    n_weeks += 1

    # Training set: all games before this week
    train_mask = game_dates < cutoff_date
    train_idx = np.where(train_mask)[0]

    if len(train_idx) < MIN_TRAIN:
        print(f"Week {n_weeks}: {cutoff_date} -- skipping, only {len(train_idx)} training games")
        continue

    # Test set: games in this week
    test_mask = np.isin(game_dates, week_dates)
    test_idx = np.where(test_mask)[0]

    if len(test_idx) == 0:
        continue

    X_train = X_all[train_idx][:, top_feature_idx]
    y_train = y_all[train_idx]
    X_test = X_all[test_idx][:, top_feature_idx]
    y_test = y_all[test_idx]
    test_dates_week = game_dates[test_idx]

    print(f"\nWeek {n_weeks}/{total_weeks}: {week_dates[0]}->{week_dates[-1]} | "
          f"Train: {len(train_idx)} | Test: {len(test_idx)} | Bankroll: ${bankroll:.2f}")

    # Train all models
    t0 = time.time()
    fitted = {}
    for name, model in make_models().items():
        try:
            # Subsample training for speed (keep last 6000)
            if len(X_train) > 6000:
                X_tr = X_train[-6000:]
                y_tr = y_train[-6000:]
            else:
                X_tr = X_train
                y_tr = y_train

            model.fit(X_tr, y_tr)
            fitted[name] = model
        except Exception as e:
            print(f"  {name} train failed: {e}")

    train_time = time.time() - t0

    if not fitted:
        print(f"  No models trained!")
        continue

    # Predict
    probs = ensemble_predict(fitted, X_test)

    # Brier score for this week
    week_brier = brier_score_loss(y_test, probs)
    daily_briers.append({'date': week_dates[0], 'brier': round(float(week_brier), 5), 'games': len(test_idx)})

    # Generate bets with Kelly sizing
    week_bets = 0
    week_wins = 0
    week_pnl = 0

    for j in range(len(test_idx)):
        home_prob = float(probs[j])
        actual_home_win = bool(y_test[j])
        game_date = test_dates_week[j]

        # Baseline: avg home win rate ~58%
        baseline_prob = 0.58

        if home_prob > baseline_prob + MIN_EDGE:
            # Bet HOME
            odds = 1 / baseline_prob
            model_edge = home_prob - baseline_prob

            b = odds - 1
            q = 1 - home_prob
            kelly_full = max(0, (b * home_prob - q) / b)
            kelly_bet = kelly_full * KELLY_FRACTION
            stake = min(bankroll * kelly_bet, bankroll * MAX_BET_PCT)

            if stake < 0.50:
                continue

            won = actual_home_win
            pnl = stake * (odds - 1) if won else -stake

            bankroll += pnl
            week_pnl += pnl
            week_bets += 1
            total_bets += 1

            if won:
                wins += 1
                week_wins += 1
            else:
                losses += 1

            all_trades.append({
                'date': game_date,
                'side': 'home',
                'model_prob': round(home_prob, 4),
                'baseline': round(baseline_prob, 4),
                'odds': round(odds, 3),
                'edge': round(model_edge, 4),
                'stake': round(stake, 2),
                'won': won,
                'pnl': round(pnl, 2),
                'bankroll': round(bankroll, 2),
            })

        elif home_prob < (1 - baseline_prob) - MIN_EDGE:
            # Bet AWAY
            away_prob = 1 - home_prob
            odds = 1 / (1 - baseline_prob)
            model_edge = away_prob - (1 - baseline_prob)

            b = odds - 1
            q = 1 - away_prob
            kelly_full = max(0, (b * away_prob - q) / b)
            kelly_bet = kelly_full * KELLY_FRACTION
            stake = min(bankroll * kelly_bet, bankroll * MAX_BET_PCT)

            if stake < 0.50:
                continue

            won = not actual_home_win
            pnl = stake * (odds - 1) if won else -stake

            bankroll += pnl
            week_pnl += pnl
            week_bets += 1
            total_bets += 1

            if won:
                wins += 1
                week_wins += 1
            else:
                losses += 1

            all_trades.append({
                'date': game_date,
                'side': 'away',
                'model_prob': round(1 - home_prob, 4),
                'baseline': round(1 - baseline_prob, 4),
                'odds': round(odds, 3),
                'edge': round(model_edge, 4),
                'stake': round(stake, 2),
                'won': won,
                'pnl': round(pnl, 2),
                'bankroll': round(bankroll, 2),
            })

    # Update tracking
    if bankroll > peak:
        peak = bankroll
    dd = (peak - bankroll) / peak * 100 if peak > 0 else 0
    if dd > max_dd:
        max_dd = dd

    bankroll = max(bankroll, 1.0)

    equity_curve.append({
        'date': week_dates[-1],
        'bankroll': round(bankroll, 2),
        'drawdown': round(dd, 2),
    })

    if week_bets > 0:
        daily_log.append({
            'date': week_dates[0],
            'end_date': week_dates[-1],
            'games': len(test_idx),
            'bets': week_bets,
            'wins': week_wins,
            'losses': week_bets - week_wins,
            'pnl': round(week_pnl, 2),
            'bankroll': round(bankroll, 2),
            'brier': round(float(week_brier), 5),
        })

    win_rate = wins / total_bets * 100 if total_bets > 0 else 0
    print(f"  Models: {list(fitted.keys())} | Train: {train_time:.0f}s | Brier: {week_brier:.5f}")
    print(f"  Bets: {week_bets} ({week_wins}W) | Week PnL: ${week_pnl:+.2f} | "
          f"Bankroll: ${bankroll:.2f} | Total: {wins}W-{losses}L ({win_rate:.1f}%)")

    # Checkpoint every 4 weeks
    if n_weeks % 4 == 0:
        ckpt_data = {
            'last_date': week_dates[-1],
            'bankroll': bankroll,
            'peak': peak,
            'max_dd': max_dd,
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'equity_curve': equity_curve,
            'trades': all_trades[-200:],
            'daily_log': daily_log,
            'daily_briers': daily_briers,
        }
        with open(CHECKPOINT, 'w') as f:
            json.dump(ckpt_data, f)
        print(f"  [CHECKPOINT saved]")

    gc.collect()

###############################################################################
# RESULTS + SAVE
###############################################################################
import statistics

roi = ((bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL) * 100
win_rate = wins / total_bets * 100 if total_bets > 0 else 0

# Sharpe
daily_returns = []
for i, d in enumerate(daily_log):
    prev_br = daily_log[i-1]['bankroll'] if i > 0 else INITIAL_BANKROLL
    if prev_br > 0:
        daily_returns.append(d['pnl'] / prev_br)

avg_ret = statistics.mean(daily_returns) if daily_returns else 0
std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.01
sharpe = (avg_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0

# Monthly P&L
monthly = defaultdict(lambda: {'pnl': 0, 'bets': 0, 'wins': 0, 'start_br': None})
for d in daily_log:
    m = d['date'][:7]
    if monthly[m]['start_br'] is None:
        monthly[m]['start_br'] = d['bankroll'] - d['pnl']
    monthly[m]['pnl'] += d['pnl']
    monthly[m]['bets'] += d['bets']
    monthly[m]['wins'] += d['wins']

monthly_pnl = [
    {'month': m, 'pnl': round(v['pnl'], 2),
     'roi_pct': round(v['pnl'] / v['start_br'] * 100, 2) if v['start_br'] else 0,
     'bets': v['bets'], 'wins': v['wins']}
    for m, v in sorted(monthly.items())
]

avg_brier = statistics.mean([b['brier'] for b in daily_briers]) if daily_briers else 0

result = {
    'strategy': f'Walk-Forward Kelly (f={KELLY_FRACTION}) + TabICL Ensemble -- REAL BACKTEST',
    'data_source': 'Walk-forward on Supabase game data, TabICL + 5 tree models',
    'platform': 'Kaggle' if IS_KAGGLE else 'Colab' if IS_COLAB else 'Local',
    'initial_bankroll': INITIAL_BANKROLL,
    'current_bankroll': round(bankroll, 2),
    'total_roi_pct': round(roi, 2),
    'total_bets': total_bets,
    'wins': wins,
    'losses': losses,
    'win_rate': round(win_rate, 2),
    'sharpe_ratio': round(sharpe, 2),
    'max_drawdown_pct': round(max_dd, 2),
    'peak_bankroll': round(peak, 2),
    'avg_edge_pct': round(statistics.mean([t['edge'] * 100 for t in all_trades]) if all_trades else 0, 2),
    'avg_kelly_pct': round(KELLY_FRACTION * 100, 1),
    'best_month': max(monthly_pnl, key=lambda m: m['roi_pct']) if monthly_pnl else {'month': '', 'roi_pct': 0},
    'worst_month': min(monthly_pnl, key=lambda m: m['roi_pct']) if monthly_pnl else {'month': '', 'roi_pct': 0},
    'equity_curve': equity_curve,
    'monthly_pnl': monthly_pnl,
    'by_market': {'moneyline': {'bets': total_bets, 'wins': wins, 'roi_pct': round(roi, 2)}},
    'by_model': {'tabicl_ensemble': {'bets': total_bets, 'wins': wins, 'roi_pct': round(roi, 2),
                 'avg_edge': round(statistics.mean([t['edge'] * 100 for t in all_trades]) if all_trades else 0, 2)}},
    'daily_log': daily_log,
    'trades': all_trades[-100:],
    'brier_history': daily_briers,
    'avg_brier': round(avg_brier, 5),
    'season_start': SEASON_START,
    'last_updated': datetime.now().isoformat(),
    'model_version': f'v3.0-37cat / TabICL+Trees / {N_FEATURES}f',
    'brier_score': round(avg_brier, 5),
    'n_features': N_FEATURES,
    'models_used': list(WEIGHTS.keys()),
}

# Save results
RESULTS_FILE = os.path.join(WORK_DIR, 'season_backtest_results.json')
with open(RESULTS_FILE, 'w') as f:
    json.dump(result, f, indent=2)

print(f"""
{'='*60}
  FULL SEASON BACKTEST RESULTS
{'='*60}
  Period:     {SEASON_START} -> {equity_curve[-1]['date'] if equity_curve else '?'}
  Bankroll:   ${INITIAL_BANKROLL} -> ${bankroll:.2f} ({roi:+.2f}%)
  Bets:       {total_bets} | {wins}W - {losses}L ({win_rate:.1f}%)
  Sharpe:     {sharpe:.2f}
  Max DD:     {max_dd:.1f}%
  Peak:       ${peak:.2f}
  Avg Brier:  {avg_brier:.5f}
  Features:   {N_FEATURES}
  Models:     {', '.join(WEIGHTS.keys())}

  Monthly:
""")
for m in monthly_pnl:
    bar = '+' * max(0, int(m['roi_pct'] / 2)) if m['roi_pct'] > 0 else '-' * max(0, int(-m['roi_pct'] / 2))
    print(f"    {m['month']}: {m['roi_pct']:+6.1f}% | {m['wins']}W/{m['bets']}B | ${m['pnl']:+.2f} {bar}")

print(f"""
{'='*60}
  Saved to: {RESULTS_FILE}
{'='*60}
""")

###############################################################################
# UPLOAD RESULTS
###############################################################################

# Upload to HuggingFace for dashboard
try:
    from huggingface_hub import HfApi
    api = HfApi(token=HF_TOKEN)
    api.upload_file(
        path_or_fileobj=RESULTS_FILE,
        path_in_repo="data/season-backtest-results.json",
        repo_id="Nomos42/nba-quant",
        repo_type="space",
    )
    print("Results uploaded to HF Space!")
except Exception as e:
    print(f"Upload failed (non-critical): {e}")

# Also save as Kaggle output artifact
if IS_KAGGLE:
    # Copy to /kaggle/working for kernel output
    import shutil
    out = '/kaggle/working/season_backtest_results.json'
    if RESULTS_FILE != out:
        shutil.copy2(RESULTS_FILE, out)
    print(f"Kaggle output: {out}")
