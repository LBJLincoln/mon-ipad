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
KELLY_FRACTION = 0.25  # quarter-Kelly (research-validated: arXiv:2107.08827)
MAX_BET_PCT = 0.025    # 2.5% max per position (was 5%)
MAX_DAILY_EXPOSURE = 0.25  # 25% max nightly exposure
MIN_EDGE = 0.03

# Flat-bet tracking (independent of Kelly for clean comparison)
flat_bankroll = INITIAL_BANKROLL
FLAT_BET_SIZE = 5.0  # $5 flat bets
flat_wins = 0
flat_losses = 0
flat_pnl_total = 0.0

# ── Load real market odds ──
# Attempt to load from Kaggle dataset, Supabase, or OddsShark CSV
ODDS_LOOKUP = {}  # key: "YYYY-MM-DD_HOME_AWAY" → {ml_home, ml_away, odds_home, odds_away, spread, total, ...}

def american_to_decimal(ml):
    if ml is None or ml == 0: return None
    ml = float(ml)
    return (1.0 + ml / 100.0) if ml > 0 else (1.0 + 100.0 / abs(ml))

TEAM_NORM = {
    "gs": "GSW", "ny": "NYK", "no": "NOP", "sa": "SAS", "por": "POR", "phi": "PHI",
    "hou": "HOU", "lal": "LAL", "lac": "LAC", "bkn": "BKN", "bos": "BOS", "chi": "CHI",
    "cle": "CLE", "dal": "DAL", "den": "DEN", "det": "DET", "gsw": "GSW", "ind": "IND",
    "mem": "MEM", "mia": "MIA", "mil": "MIL", "min": "MIN", "nop": "NOP", "nyk": "NYK",
    "okc": "OKC", "orl": "ORL", "phx": "PHX", "sac": "SAC", "sas": "SAS", "tor": "TOR",
    "uta": "UTA", "was": "WAS", "atl": "ATL", "cha": "CHA", "utah": "UTA",
    "phl": "PHI", "brk": "BKN", "pho": "PHX", "wsh": "WAS",
    # Full team names (from odds CSV)
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN",
    "charlotte hornets": "CHA", "chicago bulls": "CHI", "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL", "denver nuggets": "DEN", "detroit pistons": "DET",
    "golden state warriors": "GSW", "houston rockets": "HOU", "indiana pacers": "IND",
    "los angeles clippers": "LAC", "l.a. clippers": "LAC", "los angeles lakers": "LAL",
    "memphis grizzlies": "MEM", "miami heat": "MIA", "milwaukee bucks": "MIL",
    "minnesota timberwolves": "MIN", "new orleans pelicans": "NOP", "new york knicks": "NYK",
    "oklahoma city thunder": "OKC", "orlando magic": "ORL", "philadelphia 76ers": "PHI",
    "phoenix suns": "PHX", "portland trail blazers": "POR", "sacramento kings": "SAC",
    "san antonio spurs": "SAS", "toronto raptors": "TOR", "utah jazz": "UTA",
    "washington wizards": "WAS",
}
def norm_team(t): return TEAM_NORM.get(t.lower().strip(), t.upper().strip())

def load_odds_from_csv():
    """Load real market odds from available CSV files."""
    global ODDS_LOOKUP
    csv_paths = [
        # 2025-26 real odds (1,128 games, BetMGM + SBR)
        '/kaggle/input/nba-2025-26-odds/nba_2025-26_odds.csv',
        'data/historical-odds/nba_2025-26_odds.csv',
        '/home/termius/nomos-nba-agent/data/historical-odds/nba_2025-26_odds.csv',
        # Historical (2007-2024)
        '/kaggle/input/nba-betting-data-october-2007-to-june-2024/NBA Betting Data (2007-2024).csv',
        '/kaggle/input/nba-odds/nba_2008-2025.csv',
        '/kaggle/working/nba_2008-2025.csv',
        'data/historical-odds/nba_2008-2025.csv',
    ]
    for path in csv_paths:
        if os.path.exists(path):
            print(f"Loading real odds from: {path}")
            import csv as csv_mod
            with open(path, 'r') as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    date = row.get('date', row.get('game_date', ''))
                    home = norm_team(row.get('home', row.get('home_team', '')))
                    away = norm_team(row.get('away', row.get('away_team', '')))
                    ml_h = row.get('moneyline_home', row.get('ml_home', ''))
                    ml_a = row.get('moneyline_away', row.get('ml_away', ''))
                    spread = row.get('spread', '')
                    total = row.get('total', '')
                    h2_spread = row.get('h2_spread', '')
                    h2_total = row.get('h2_total', '')
                    favored = row.get('whos_favored', '')

                    if ml_h and ml_a:
                        try:
                            key = f"{date}_{home}_{away}"
                            ODDS_LOOKUP[key] = {
                                'ml_home': float(ml_h),
                                'ml_away': float(ml_a),
                                'odds_home': american_to_decimal(float(ml_h)),
                                'odds_away': american_to_decimal(float(ml_a)),
                                'spread': float(spread) if spread else None,
                                'total': float(total) if total else None,
                                'h2_spread': float(h2_spread) if h2_spread else None,
                                'h2_total': float(h2_total) if h2_total else None,
                                'favored': favored,
                            }
                        except (ValueError, TypeError):
                            pass
            print(f"  Loaded {len(ODDS_LOOKUP)} games with real odds")
            return True
    print("WARNING: No odds CSV found — will use Supabase odds or implied probabilities")
    return False

def load_odds_from_supabase():
    """Load real odds from Supabase predictions table."""
    global ODDS_LOOKUP
    if not DATABASE_URL:
        return False
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        cur = conn.cursor()
        cur.execute("SELECT game_date, home_team, away_team, market_odds_home, market_odds_away FROM nba_predictions WHERE market_odds_home IS NOT NULL")
        for row in cur.fetchall():
            key = f"{row[0]}_{row[1]}_{row[2]}"
            if key not in ODDS_LOOKUP:
                ODDS_LOOKUP[key] = {
                    'odds_home': float(row[3]) if row[3] else None,
                    'odds_away': float(row[4]) if row[4] else None,
                }
        conn.close()
        print(f"  Added {len(ODDS_LOOKUP)} games from Supabase odds")
        return True
    except Exception as e:
        print(f"  Supabase odds load failed: {e}")
        return False

# Try to load odds
load_odds_from_csv()
load_odds_from_supabase()

# Resume from checkpoint (only if --resume flag)
CHECKPOINT = os.path.join(WORK_DIR, 'backtest_checkpoint.json')
RESUME = '--resume' in sys.argv
if RESUME and os.path.exists(CHECKPOINT):
    ckpt = json.loads(open(CHECKPOINT).read())
    print(f"Resuming from {ckpt['last_date']}, bankroll=${ckpt['bankroll']:.2f}")
else:
    # Fresh run — delete stale checkpoint
    if os.path.exists(CHECKPOINT):
        os.remove(CHECKPOINT)
        print("Deleted stale checkpoint — starting fresh")
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
all_trades = ckpt.get('trades', []) if ckpt else []
daily_log = ckpt.get('daily_log', []) if ckpt else []
daily_briers = ckpt.get('daily_briers', []) if ckpt else []

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

    # Filter indices to be within bounds of BOTH X_all and games
    max_valid = min(len(X_all), len(y_all), len(games)) - 1
    train_idx = train_idx[train_idx <= max_valid]
    test_idx = test_idx[test_idx <= max_valid]
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

    day_exposure = 0

    for j in range(len(test_idx)):
        home_prob = float(probs[j])
        actual_home_win = bool(y_test[j])
        game_date = test_dates_week[j]

        # Look up real market odds for this game
        game_idx = test_idx[j]
        game_home = games[game_idx]['home_team'] if game_idx < len(games) else None
        game_away = games[game_idx]['away_team'] if game_idx < len(games) else None
        odds_key = f"{game_date}_{game_home}_{game_away}" if game_home else None

        real_odds = ODDS_LOOKUP.get(odds_key, {}) if odds_key else {}
        odds_home = real_odds.get('odds_home')
        odds_away = real_odds.get('odds_away')

        # If no real odds found, derive from implied probability (less accurate)
        if not odds_home and not odds_away:
            # Use model-implied odds with 5% vig as conservative estimate
            if home_prob > 0.5:
                odds_home = 1.0 / (home_prob * 1.05)  # Home favorite
                odds_away = 1.0 / ((1 - home_prob) * 1.05)
            else:
                odds_home = 1.0 / (home_prob * 1.05)
                odds_away = 1.0 / ((1 - home_prob) * 1.05)

        # ── Moneyline bets ──
        bet_odds = None
        bet_on_home = None

        if home_prob > 0.5 and odds_home and 1.01 < odds_home <= 15.0:
            bet_odds = odds_home
            bet_on_home = True
        elif home_prob < 0.5 and odds_away and 1.01 < odds_away <= 15.0:
            bet_odds = odds_away
            bet_on_home = False

        if bet_odds is not None:
            bet_prob = home_prob if bet_on_home else (1 - home_prob)
            real_edge = bet_prob * bet_odds - 1

            if real_edge > MIN_EDGE:
                b = bet_odds - 1
                q = 1 - bet_prob
                kelly_full = max(0, (b * bet_prob - q) / b) if b > 0 else 0
                kelly_bet = kelly_full * KELLY_FRACTION
                stake = min(bankroll * kelly_bet, bankroll * MAX_BET_PCT)

                # Portfolio exposure cap
                if day_exposure + stake > bankroll * MAX_DAILY_EXPOSURE:
                    stake = max(0, bankroll * MAX_DAILY_EXPOSURE - day_exposure)

                if stake >= 0.50:
                    won = actual_home_win if bet_on_home else (not actual_home_win)
                    pnl = stake * (bet_odds - 1) if won else -stake

                    bankroll += pnl
                    week_pnl += pnl
                    week_bets += 1
                    day_exposure += stake
                    total_bets += 1

                    # Flat-bet tracking (independent)
                    flat_pnl_bet = FLAT_BET_SIZE * (bet_odds - 1) if won else -FLAT_BET_SIZE
                    flat_bankroll += flat_pnl_bet
                    flat_pnl_total += flat_pnl_bet
                    if won: flat_wins += 1
                    else: flat_losses += 1

                    if won:
                        wins += 1
                        week_wins += 1
                    else:
                        losses += 1

                    bet_side = 'home' if bet_on_home else 'away'
                    all_trades.append({
                        'date': game_date,
                        'side': bet_side,
                        'model_prob': round(bet_prob, 4),
                        'market_odds': round(bet_odds, 3),
                        'odds': round(bet_odds, 3),
                        'edge': round(real_edge, 4),
                        'stake': round(stake, 2),
                        'won': won,
                        'pnl': round(pnl, 2),
                        'bankroll': round(bankroll, 2),
                        'has_real_odds': bool(real_odds),
                    })

        # ── ATS Spread bets (if spread data available) ──
        if real_odds.get('spread') is not None:
            SPREAD_SCALE = 13.0
            NBA_STD = 11.0
            STANDARD_ODDS = 1.909  # -110 both sides

            predicted_spread = -SPREAD_SCALE * math.log(home_prob / (1 - home_prob)) if 0.01 < home_prob < 0.99 else None
            if predicted_spread is not None:
                line_spread = float(real_odds['spread'])
                if real_odds.get('favored') == 'away':
                    line_spread = abs(line_spread)
                else:
                    line_spread = -abs(line_spread)

                z = -(line_spread + predicted_spread) / NBA_STD
                cover_prob = 1.0 / (1.0 + math.exp(-1.7 * z))

                # Check both sides
                for side_prob, side_name, side_won_fn in [
                    (cover_prob, 'ATS_HOME', lambda m: m > -line_spread),
                    (1-cover_prob, 'ATS_AWAY', lambda m: m < -line_spread),
                ]:
                    ats_edge = side_prob * STANDARD_ODDS - 1
                    if ats_edge > MIN_EDGE:
                        b = STANDARD_ODDS - 1
                        q = 1 - side_prob
                        kelly_full = max(0, (b * side_prob - q) / b) if b > 0 else 0
                        stake = min(bankroll * kelly_full * KELLY_FRACTION, bankroll * MAX_BET_PCT)
                        if day_exposure + stake > bankroll * MAX_DAILY_EXPOSURE:
                            stake = max(0, bankroll * MAX_DAILY_EXPOSURE - day_exposure)
                        if stake >= 0.50:
                            margin = (games[game_idx]['home_score'] - games[game_idx]['away_score']) if game_idx < len(games) and 'home_score' in games[game_idx] else None
                            if margin is None:
                                # Derive from actual result + approximate margin
                                margin = 5 if actual_home_win else -5  # Rough estimate
                            ats_won = side_won_fn(margin)
                            pnl = stake * (STANDARD_ODDS - 1) if ats_won else -stake
                            bankroll += pnl
                            week_pnl += pnl
                            week_bets += 1
                            day_exposure += stake
                            total_bets += 1
                            if ats_won: wins += 1; week_wins += 1
                            else: losses += 1
                            all_trades.append({
                                'date': game_date, 'side': side_name,
                                'model_prob': round(side_prob, 4),
                                'market_odds': STANDARD_ODDS,
                                'odds': STANDARD_ODDS,
                                'edge': round(ats_edge, 4),
                                'stake': round(stake, 2),
                                'won': ats_won,
                                'pnl': round(pnl, 2),
                                'bankroll': round(bankroll, 2),
                                'has_real_odds': True,
                            })

        # ── Over/Under Totals bets (if total data available) ──
        if real_odds.get('total') is not None and game_idx < len(games):
            game = games[game_idx] if game_idx < len(games) else {}
            actual_total = None
            if 'home_score' in game and 'away_score' in game:
                actual_total = game['home_score'] + game['away_score']

            if actual_total is not None:
                market_total = float(real_odds['total'])
                STANDARD_ODDS_TOTAL = 1.909  # -110

                # Predict total from our model: use home_prob + pace proxies
                # Strong home favorites → higher totals (more possessions), underdogs → lower
                # Use logistic spread to estimate expected margin, then total
                if 0.01 < home_prob < 0.99:
                    expected_margin = -13.0 * math.log(home_prob / (1 - home_prob))
                    # NBA average total ~225, correlated with favorite strength
                    pred_total = 224.0 + abs(expected_margin) * 0.15
                else:
                    pred_total = 224.0

                total_diff = pred_total - market_total  # positive = we think OVER
                # Convert to probability
                TOTAL_STD = 12.0  # NBA total standard deviation
                z_over = total_diff / TOTAL_STD
                over_prob = 1.0 / (1.0 + math.exp(-1.7 * z_over))

                for side_prob, side_name, side_won in [
                    (over_prob, 'OVER', actual_total > market_total),
                    (1-over_prob, 'UNDER', actual_total < market_total),
                ]:
                    if actual_total == market_total:
                        continue  # Push
                    ou_edge = side_prob * STANDARD_ODDS_TOTAL - 1
                    if ou_edge > MIN_EDGE:
                        b = STANDARD_ODDS_TOTAL - 1
                        q = 1 - side_prob
                        kelly_full = max(0, (b * side_prob - q) / b) if b > 0 else 0
                        ou_stake = min(bankroll * kelly_full * KELLY_FRACTION, bankroll * MAX_BET_PCT)
                        if day_exposure + ou_stake > bankroll * MAX_DAILY_EXPOSURE:
                            ou_stake = max(0, bankroll * MAX_DAILY_EXPOSURE - day_exposure)
                        if ou_stake >= 0.50:
                            pnl = ou_stake * (STANDARD_ODDS_TOTAL - 1) if side_won else -ou_stake
                            bankroll += pnl
                            week_pnl += pnl
                            week_bets += 1
                            day_exposure += ou_stake
                            total_bets += 1
                            if side_won: wins += 1; week_wins += 1
                            else: losses += 1
                            all_trades.append({
                                'date': game_date, 'side': side_name,
                                'model_prob': round(side_prob, 4),
                                'market_odds': STANDARD_ODDS_TOTAL,
                                'odds': STANDARD_ODDS_TOTAL,
                                'edge': round(ou_edge, 4),
                                'stake': round(ou_stake, 2),
                                'won': side_won,
                                'pnl': round(pnl, 2),
                                'bankroll': round(bankroll, 2),
                                'has_real_odds': True,
                                'market_total': market_total,
                                'actual_total': actual_total,
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

def _compute_market_breakdown(trades):
    """Compute P&L breakdown by bet type (ML, ATS, etc.)."""
    markets = defaultdict(lambda: {'bets': 0, 'wins': 0, 'pnl': 0.0})
    for t in trades:
        side = t.get('side', 'home')
        if 'ATS' in side:
            mkt = 'ats'
        elif side in ('home', 'away'):
            mkt = 'moneyline'
        else:
            mkt = side
        markets[mkt]['bets'] += 1
        markets[mkt]['pnl'] += t.get('pnl', 0)
        if t.get('won'):
            markets[mkt]['wins'] += 1
    result = {}
    for mkt, stats in markets.items():
        result[mkt] = {
            'bets': stats['bets'],
            'wins': stats['wins'],
            'win_rate': round(stats['wins'] / stats['bets'] * 100, 1) if stats['bets'] else 0,
            'pnl': round(stats['pnl'], 2),
        }
    return result

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
    'by_market': _compute_market_breakdown(all_trades),
    'by_model': {'tabicl_ensemble': {'bets': total_bets, 'wins': wins, 'roi_pct': round(roi, 2),
                 'avg_edge': round(statistics.mean([t['edge'] * 100 for t in all_trades]) if all_trades else 0, 2)}},
    'real_odds_pct': round(sum(1 for t in all_trades if t.get('has_real_odds')) / max(len(all_trades), 1) * 100, 1),
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
    # Flat-bet baseline (Kelly-independent)
    'flat_bet': {
        'bet_size': FLAT_BET_SIZE,
        'bankroll': round(flat_bankroll, 2),
        'roi_pct': round((flat_bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100, 2),
        'wins': flat_wins,
        'losses': flat_losses,
        'win_rate': round(flat_wins / max(flat_wins + flat_losses, 1) * 100, 1),
        'total_pnl': round(flat_pnl_total, 2),
    },
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

  FLAT BET ($5/bet):
  Bankroll:   ${INITIAL_BANKROLL} -> ${flat_bankroll:.2f} ({(flat_bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100:+.1f}%)
  Record:     {flat_wins}W - {flat_losses}L ({flat_wins / max(flat_wins + flat_losses, 1) * 100:.1f}%)

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

# ── MARKET BREAKDOWN ──
by_mkt = _compute_market_breakdown(all_trades)
if by_mkt:
    print("  BY MARKET:")
    for mkt, stats in sorted(by_mkt.items()):
        print(f"    {mkt:>12}: {stats['bets']}B, {stats['wins']}W ({stats['win_rate']:.1f}%), PnL ${stats['pnl']:+.2f}")
    print()

# ── KELLY FRACTION SWEEP (retroactive on recorded trades) ──
print("  KELLY OPTIMIZATION (retroactive on all trades):")
print(f"  {'Fraction':<12} {'Final $':<12} {'ROI':<10} {'Max DD':<10} {'Sharpe':<10}")
print(f"  {'-'*54}")
for kf in [0.05, 0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 0.75, 1.00]:
    br = INITIAL_BANKROLL
    pk = br
    mdd = 0
    rets = []
    for t in all_trades:
        # Re-derive kelly bet for this fraction
        edge = t['edge']
        odds = t['odds']
        prob = t['model_prob']
        b = odds - 1
        q = 1 - prob
        kfull = max(0, (b * prob - q) / b) if b > 0 else 0
        st = min(br * kfull * kf, br * MAX_BET_PCT)
        st = max(0, min(st, br * 0.5))  # never bet more than 50%
        if st < 0.50: continue
        pnl_k = st * (odds - 1) if t['won'] else -st
        rets.append(pnl_k / br if br > 0 else 0)
        br += pnl_k
        br = max(br, 0.01)
        if br > pk: pk = br
        dd_k = (pk - br) / pk * 100 if pk > 0 else 0
        if dd_k > mdd: mdd = dd_k
    roi_k = (br - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
    avg_r = statistics.mean(rets) if rets else 0
    std_r = statistics.stdev(rets) if len(rets) > 1 else 0.01
    sharpe_k = (avg_r / std_r) * (252**0.5) if std_r > 0 else 0
    marker = " <-- CURRENT" if abs(kf - KELLY_FRACTION) < 0.001 else ""
    print(f"  f={kf:<8.2f}   ${br:<10.2f}  {roi_k:>+8.1f}%   {mdd:>6.1f}%   {sharpe_k:>7.2f}{marker}")
print()

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
