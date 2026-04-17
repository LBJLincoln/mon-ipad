#!/usr/bin/env python3
"""
NBA Quant AI — Full Season Walk-Forward Backtest (Kaggle CPU/GPU)
STRATEGY CONFRONTATION MODE

PROVES our system works with REAL data:
- Walk-forward: for each week, train on ALL prior games, predict next week
- TREE-ONLY models (no TabICL — P100 CUDA incompatible)
- 11 bet types: ML, ATS, O/U, H1, H2, team totals, value dogs
- 5 bankroll strategies: Kelly 25%, Kelly 15%, Kelly 10%, Flat $10, Proportional 1%
- Full confrontation table: every strategy combo ranked by ROI, Sharpe, MaxDD, WinRate
- Output: strategy-confrontation.json + season_backtest_results.json

Kaggle: CPU or GPU, Internet ON, Secrets: DATABASE_URL
Output: /kaggle/working/strategy-confrontation.json
"""

import subprocess, sys, os, time, gc, json, warnings, math, csv as csv_mod
import numpy as np
from datetime import datetime
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

# ── Install deps (TREE-ONLY — no TabICL) ──
t0 = time.time()
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'xgboost', 'lightgbm', 'catboost', 'scikit-learn',
    'psycopg2-binary', 'huggingface_hub', 'nba_api'])
print(f'Deps installed: {time.time()-t0:.0f}s')

# Detect GPU for XGBoost/CatBoost acceleration (optional)
try:
    import torch
    HAS_GPU = torch.cuda.is_available()
    if HAS_GPU:
        print(f'GPU: {torch.cuda.get_device_name(0)} — using for XGBoost/CatBoost')
    else:
        print('CPU-only mode')
except ImportError:
    HAS_GPU = False
    print('No torch — CPU-only mode')

###############################################################################
# LOAD GAME DATA + FEATURES
###############################################################################

# Clone feature engine from HF Space
REPO_DIR = os.path.join(WORK_DIR, 'nba-quant-space') if IS_KAGGLE else '/content/nba-quant-space'
if not os.path.exists(REPO_DIR):
    print("Cloning feature engine from HF Space...")
    token_part = f"user:{HF_TOKEN}@" if HF_TOKEN else ""
    os.system(f"git clone --depth 1 https://{token_part}huggingface.co/spaces/Nomos42/nba-quant {REPO_DIR}")
sys.path.insert(0, REPO_DIR)

FEATURE_CACHE = os.path.join(WORK_DIR, 'backtest_features_v43.npz')
GAMES_CACHE   = os.path.join(WORK_DIR, 'backtest_games.json')

if os.path.exists(FEATURE_CACHE) and os.path.exists(GAMES_CACHE):
    print("Loading cached features...")
    data = np.load(FEATURE_CACHE, allow_pickle=True)
    X_all = data["X"]
    y_all = data["y"]
    feature_names = list(data["feature_names"])
    with open(GAMES_CACHE) as f:
        games = json.load(f)
    print(f"Loaded: {X_all.shape}, {len(games)} games")
else:
    games = []

    if DATABASE_URL:
        print("Loading games from Supabase...")
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=30,
                                    options="-c search_path=public")
            cur = conn.cursor()
            cur.execute("SELECT game_data FROM nba_games ORDER BY game_date LIMIT 20000")
            for row in cur.fetchall():
                if row[0]:
                    g = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    games.append(g)
            cur.close(); conn.close()
            print(f"Loaded {len(games)} games from Supabase")
        except Exception as e:
            print(f"Supabase failed: {e}")

    if not games:
        print("Loading from HF Space data files...")
        import glob
        for fp in sorted(glob.glob(os.path.join(REPO_DIR, 'data', 'historical', 'games-*.json'))):
            raw = json.loads(open(fp).read())
            games.extend(raw if isinstance(raw, list) else raw.get('games', []))
        print(f"Loaded {len(games)} games from HF Space")

    if not games:
        print("ERROR: No game data available!")
        sys.exit(1)

    games.sort(key=lambda g: g.get('game_date', g.get('date', '')))

    # DIAGNOSTIC: show actual field names in game records so we can verify team/score extraction
    if games:
        print(f"Game fields: {list(games[0].keys())}")
        # Print sample of score-related fields for first 3 games
        for gi in range(min(3, len(games))):
            gg = games[gi]
            score_fields = {k: v for k, v in gg.items()
                           if any(x in k.lower() for x in ['score', 'pts', 'q1', 'q2', 'q3', 'q4', 'ot'])}
            team_fields = {k: v for k, v in gg.items()
                          if any(x in k.lower() for x in ['home', 'away', 'team', 'visitor'])}
            print(f"  Game[{gi}] teams: {team_fields}")
            print(f"  Game[{gi}] scores: {score_fields}")
        # Also check a season game (around index where 2025-26 starts)
        for gi in range(len(games)-1, max(0, len(games)-4), -1):
            gg = games[gi]
            score_fields = {k: v for k, v in gg.items()
                           if any(x in k.lower() for x in ['score', 'pts', 'q1', 'q2', 'q3', 'q4', 'ot'])}
            team_fields = {k: v for k, v in gg.items()
                          if any(x in k.lower() for x in ['home', 'away', 'team', 'visitor'])}
            print(f"  Game[{gi}] (recent) date={gg.get('game_date',gg.get('date',''))} teams={team_fields}")
            print(f"  Game[{gi}] (recent) scores={score_fields}")

    print("Building features (20-30 min)...")
    from features.engine import NBAFeatureEngine
    engine = NBAFeatureEngine()
    X_all, y_all, feature_names = engine.build(games)
    X_all = np.nan_to_num(np.array(X_all, dtype=np.float64))
    y_all = np.array(y_all, dtype=np.int32)
    y_margin = getattr(engine, 'y_margin', np.zeros(len(y_all), dtype=np.int32))
    y_total = getattr(engine, 'y_total', np.full(len(y_all), 225, dtype=np.int32))

    np.savez_compressed(FEATURE_CACHE, X=X_all, y=y_all,
                        feature_names=np.array(feature_names),
                        y_margin=y_margin, y_total=y_total)
    with open(GAMES_CACHE, 'w') as f:
        json.dump(games, f)
    print(f"Built & cached: {X_all.shape}")

# Extract game dates
game_dates = []
for g in games:
    d = g.get('game_date', g.get('date', ''))
    game_dates.append(d[:10] if isinstance(d, str) and len(d) >= 10 else '')
game_dates = np.array(game_dates)
print(f"Ready: {X_all.shape} | Dates: {game_dates[0]} to {game_dates[-1]}")

###############################################################################
# TREE-ONLY MODEL ENSEMBLE
###############################################################################
import xgboost as xgb
import lightgbm as lgbm
from catboost import CatBoostClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import brier_score_loss

def make_models():
    """Tree-only ensemble — no TabICL, safe on P100 CUDA."""
    return {
        'xgboost': xgb.XGBClassifier(
            max_depth=6, learning_rate=0.1, n_estimators=300,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, eval_metric='logloss', verbosity=0,
            tree_method='hist',
            device='cuda' if HAS_GPU else 'cpu'
        ),
        'extra_trees': ExtraTreesClassifier(
            n_estimators=300, max_depth=None, random_state=42, n_jobs=-1
        ),
        'lightgbm': lgbm.LGBMClassifier(
            max_depth=6, learning_rate=0.1, n_estimators=300,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, verbose=-1, n_jobs=-1
        ),
        'catboost': CatBoostClassifier(
            depth=6, learning_rate=0.1, iterations=300,
            random_state=42, verbose=0,
            task_type='GPU' if HAS_GPU else 'CPU'
        ),
        'random_forest': RandomForestClassifier(
            n_estimators=300, max_depth=None, random_state=42, n_jobs=-1
        ),
    }

# Equal weights for tree ensemble
WEIGHTS = {
    'xgboost': 0.25,
    'extra_trees': 0.20,
    'lightgbm': 0.25,
    'catboost': 0.20,
    'random_forest': 0.10,
}

def ensemble_predict(models_fitted, X_test):
    total_weight = 0.0
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
# REAL ODDS LOADER
###############################################################################
ODDS_LOOKUP = {}  # "YYYY-MM-DD_HOME_AWAY" -> dict

TEAM_NORM = {
    "gs": "GSW", "ny": "NYK", "no": "NOP", "sa": "SAS", "por": "POR",
    "phi": "PHI", "hou": "HOU", "lal": "LAL", "lac": "LAC", "bkn": "BKN",
    "bos": "BOS", "chi": "CHI", "cle": "CLE", "dal": "DAL", "den": "DEN",
    "det": "DET", "gsw": "GSW", "ind": "IND", "mem": "MEM", "mia": "MIA",
    "mil": "MIL", "min": "MIN", "nop": "NOP", "nyk": "NYK", "okc": "OKC",
    "orl": "ORL", "phx": "PHX", "sac": "SAC", "sas": "SAS", "tor": "TOR",
    "uta": "UTA", "was": "WAS", "atl": "ATL", "cha": "CHA",
    "utah": "UTA", "phl": "PHI", "brk": "BKN", "pho": "PHX", "wsh": "WAS",
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN",
    "charlotte hornets": "CHA", "chicago bulls": "CHI", "cleveland cavaliers": "CLE",
    "dallas mavericks": "DAL", "denver nuggets": "DEN", "detroit pistons": "DET",
    "golden state warriors": "GSW", "houston rockets": "HOU", "indiana pacers": "IND",
    "los angeles clippers": "LAC", "l.a. clippers": "LAC", "los angeles lakers": "LAL",
    "memphis grizzlies": "MEM", "miami heat": "MIA", "milwaukee bucks": "MIL",
    "minnesota timberwolves": "MIN", "new orleans pelicans": "NOP",
    "new york knicks": "NYK", "oklahoma city thunder": "OKC",
    "orlando magic": "ORL", "philadelphia 76ers": "PHI", "phoenix suns": "PHX",
    "portland trail blazers": "POR", "sacramento kings": "SAC",
    "san antonio spurs": "SAS", "toronto raptors": "TOR",
    "utah jazz": "UTA", "washington wizards": "WAS",
}

def norm_team(t):
    return TEAM_NORM.get(t.lower().strip(), t.upper().strip())

def american_to_decimal(ml):
    if ml is None or ml == 0: return None
    ml = float(ml)
    return (1.0 + ml / 100.0) if ml > 0 else (1.0 + 100.0 / abs(ml))

def load_odds_from_csv():
    csv_paths = [
        '/kaggle/input/nba-2025-26-odds/nba_2025-26_odds.csv',
        'data/historical-odds/nba_2025-26_odds.csv',
        '/kaggle/input/nba-betting-data-october-2007-to-june-2024/NBA Betting Data (2007-2024).csv',
        '/kaggle/input/nba-odds/nba_2008-2025.csv',
        '/kaggle/working/nba_2008-2025.csv',
        'data/historical-odds/nba_2008-2025.csv',
    ]

    # DEBUG: list /kaggle/input/ to see what datasets are mounted
    if IS_KAGGLE:
        import glob
        inputs = glob.glob('/kaggle/input/*')
        print(f"  Kaggle inputs mounted: {inputs}")
        for inp in inputs:
            files = glob.glob(f'{inp}/*')
            print(f"    {inp}: {files[:5]}")

    # Fallback: download odds CSV if not found locally
    if IS_KAGGLE and not any(os.path.exists(p) for p in csv_paths):
        print("  Attempting Kaggle API download of odds dataset...")
        try:
            subprocess.run(['kaggle', 'datasets', 'download', '-d',
                            'alexismoret6/nba-2025-26-odds',
                            '-p', '/kaggle/working/', '--unzip'],
                           capture_output=True, timeout=60)
            csv_paths.insert(0, '/kaggle/working/nba_2025-26_odds.csv')
        except Exception as e:
            print(f"  Kaggle download failed: {e}")

    for path in csv_paths:
        if os.path.exists(path):
            print(f"Loading odds from: {path}")
            with open(path, 'r') as f:
                reader = csv_mod.DictReader(f)
                for row in reader:
                    date  = row.get('date', row.get('game_date', ''))
                    home  = norm_team(row.get('home', row.get('home_team', '')))
                    away  = norm_team(row.get('away', row.get('away_team', '')))
                    ml_h  = row.get('moneyline_home', row.get('ml_home', ''))
                    ml_a  = row.get('moneyline_away', row.get('ml_away', ''))
                    # FIX: CSV uses 'spread_home' not 'spread'
                    spread   = row.get('spread', row.get('spread_home', ''))
                    total    = row.get('total', row.get('total_points', ''))
                    h2_spread = row.get('h2_spread', row.get('h2_spread_home', ''))
                    h2_total  = row.get('h2_total', '')
                    favored   = row.get('whos_favored', '')
                    if ml_h and ml_a:
                        try:
                            key = f"{date}_{home}_{away}"
                            sp_val = float(spread) if spread else None
                            tot_val = float(total) if total else None
                            h2s_val = float(h2_spread) if h2_spread else None
                            h2t_val = float(h2_total) if h2_total else None
                            # Derive favored from spread_home sign if not explicit
                            if not favored and sp_val is not None:
                                favored = 'away' if sp_val > 0 else 'home'
                            ODDS_LOOKUP[key] = {
                                'ml_home':   float(ml_h),
                                'ml_away':   float(ml_a),
                                'odds_home': american_to_decimal(float(ml_h)),
                                'odds_away': american_to_decimal(float(ml_a)),
                                'spread':    abs(sp_val)  if sp_val is not None else None,
                                'total':     tot_val,
                                'h2_spread': abs(h2s_val) if h2s_val is not None else None,
                                'h2_total':  h2t_val,
                                'favored':   favored,
                            }
                        except (ValueError, TypeError):
                            pass
            print(f"  Loaded {len(ODDS_LOOKUP)} odds records")
            return True
    print("WARNING: No odds CSV found")
    return False

def load_odds_from_supabase():
    if not DATABASE_URL: return False
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=15)
        cur = conn.cursor()
        cur.execute("""SELECT game_date, home_team, away_team,
                              market_odds_home, market_odds_away
                       FROM nba_predictions
                       WHERE market_odds_home IS NOT NULL""")
        for row in cur.fetchall():
            key = f"{row[0]}_{row[1]}_{row[2]}"
            if key not in ODDS_LOOKUP:
                ODDS_LOOKUP[key] = {
                    'odds_home': float(row[3]) if row[3] else None,
                    'odds_away': float(row[4]) if row[4] else None,
                }
        conn.close()
        print(f"  Supabase odds: {len(ODDS_LOOKUP)} records")
        return True
    except Exception as e:
        print(f"  Supabase odds load failed: {e}")
        return False

load_odds_from_csv()
load_odds_from_supabase()
print(f"\n=== ODDS LOADED: {len(ODDS_LOOKUP)} records ===")
if ODDS_LOOKUP:
    sample_keys = list(ODDS_LOOKUP.keys())[:5]
    for k in sample_keys:
        v = ODDS_LOOKUP[k]
        print(f"  {k}: home={v.get('odds_home'):.3f}, away={v.get('odds_away'):.3f}, "
              f"spread={v.get('spread')}, total={v.get('total')}, fav={v.get('favored')}")
    # Count how many have spread/total data
    n_with_spread = sum(1 for v in ODDS_LOOKUP.values() if v.get('spread') is not None)
    n_with_total = sum(1 for v in ODDS_LOOKUP.values() if v.get('total') is not None)
    print(f"  Spread data: {n_with_spread}/{len(ODDS_LOOKUP)} | Total data: {n_with_total}/{len(ODDS_LOOKUP)}")
else:
    print("  *** NO ODDS DATA — ALL BETS WILL BE SKIPPED ***")
    print("  Fix: Add alexismoret6/nba-2025-26-odds as Kaggle input dataset")

###############################################################################
# MULTI-MARKET BET GENERATION HELPERS
###############################################################################

SPREAD_SCALE = 13.0    # empirical: spread = -SCALE * log(p/(1-p))
NBA_STD_SPREAD = 11.0  # game score-diff std dev
NBA_STD_TOTAL  = 12.0  # game total std dev
STANDARD_ODDS  = 1.909 # -110 both sides

def prob_to_spread(p_home):
    if p_home <= 0.01 or p_home >= 0.99: return None
    return -SPREAD_SCALE * math.log(p_home / (1.0 - p_home))

def cover_prob(pred_spread, line_spread):
    """P(home covers line_spread)."""
    z = -(line_spread + pred_spread) / NBA_STD_SPREAD
    return 1.0 / (1.0 + math.exp(-1.7 * z))

def over_prob(pred_total, line_total):
    z = (pred_total - line_total) / NBA_STD_TOTAL
    return 1.0 / (1.0 + math.exp(-1.7 * z))


def generate_all_bets(p_home, real_odds, actual_outcome, MIN_EDGE=0.03):
    """
    Generate ALL bets with edge > MIN_EDGE for one game.

    actual_outcome = dict with keys:
        home_win (bool), margin (int), total_pts (int),
        h1_margin (int), h2_margin (int),
        h1_total (int), h2_total (int),
        home_score (int), away_score (int)

    Returns list of dicts:
        {type, odds, model_prob, edge, won (bool)}
    """
    bets = []
    p_away = 1.0 - p_home
    pred_spread = prob_to_spread(p_home)
    if pred_spread is None:
        return bets

    # Predict total: close games slightly lower, blowouts slightly higher
    pred_total = 224.0 + abs(pred_spread) * 0.15

    margin     = actual_outcome['margin']
    total_pts  = actual_outcome['total_pts']
    h1_margin  = actual_outcome.get('h1_margin', 0)
    h2_margin  = actual_outcome.get('h2_margin', 0)
    h1_pts     = actual_outcome.get('h1_total', 0)
    h2_pts     = actual_outcome.get('h2_total', 0)
    home_score = actual_outcome.get('home_score', 0)
    away_score = actual_outcome.get('away_score', 0)

    odds_h = real_odds.get('odds_home')
    odds_a = real_odds.get('odds_away')
    spread = real_odds.get('spread')
    total  = real_odds.get('total')
    h2_sp  = real_odds.get('h2_spread')
    h2_to  = real_odds.get('h2_total')
    fav    = real_odds.get('favored', '')

    def signed_spread(raw, favored):
        if raw is None: return None
        raw = float(raw)
        return abs(raw) if favored == 'away' else -abs(raw)

    # ── 1. ML_HOME ──
    if odds_h and 1.01 < odds_h <= 15.0 and p_home > 0.5:
        edge = p_home * odds_h - 1
        if edge > MIN_EDGE:
            bets.append({'type': 'ML_HOME', 'odds': odds_h,
                         'model_prob': p_home, 'edge': edge,
                         'won': actual_outcome['home_win']})

    # ── 2. ML_AWAY ──
    if odds_a and 1.01 < odds_a <= 15.0 and p_away > 0.5:
        edge = p_away * odds_a - 1
        if edge > MIN_EDGE:
            bets.append({'type': 'ML_AWAY', 'odds': odds_a,
                         'model_prob': p_away, 'edge': edge,
                         'won': not actual_outcome['home_win']})

    # ── 3. ATS_HOME ──
    if spread is not None:
        line = signed_spread(spread, fav)
        cp_home = cover_prob(pred_spread, line)
        edge = cp_home * STANDARD_ODDS - 1
        if edge > MIN_EDGE:
            bets.append({'type': 'ATS_HOME', 'odds': STANDARD_ODDS,
                         'model_prob': cp_home, 'edge': edge,
                         'won': margin > -line})

        # ── 4. ATS_AWAY ──
        cp_away = 1.0 - cp_home
        edge_away = cp_away * STANDARD_ODDS - 1
        if edge_away > MIN_EDGE:
            bets.append({'type': 'ATS_AWAY', 'odds': STANDARD_ODDS,
                         'model_prob': cp_away, 'edge': edge_away,
                         'won': margin < -line})

    # ── 5. OVER ──
    if total is not None:
        op = over_prob(pred_total, float(total))
        edge = op * STANDARD_ODDS - 1
        if edge > MIN_EDGE and total_pts != float(total):
            bets.append({'type': 'OVER', 'odds': STANDARD_ODDS,
                         'model_prob': op, 'edge': edge,
                         'won': total_pts > float(total)})

        # ── 6. UNDER ──
        up = 1.0 - op
        edge_u = up * STANDARD_ODDS - 1
        if edge_u > MIN_EDGE and total_pts != float(total):
            bets.append({'type': 'UNDER', 'odds': STANDARD_ODDS,
                         'model_prob': up, 'edge': edge_u,
                         'won': total_pts < float(total)})

    # ── 7. H2_ATS_HOME ──
    if h2_sp is not None:
        h2_line = signed_spread(h2_sp, fav)
        h2_pred_spread = pred_spread * 0.45
        cp_h2 = cover_prob(h2_pred_spread, h2_line)
        edge = cp_h2 * STANDARD_ODDS - 1
        if edge > MIN_EDGE:
            bets.append({'type': 'H2_ATS_HOME', 'odds': STANDARD_ODDS,
                         'model_prob': cp_h2, 'edge': edge,
                         'won': h2_margin > -h2_line})

        # ── 8. H2_ATS_AWAY ──
        cp_h2a = 1.0 - cp_h2
        edge_a = cp_h2a * STANDARD_ODDS - 1
        if edge_a > MIN_EDGE:
            bets.append({'type': 'H2_ATS_AWAY', 'odds': STANDARD_ODDS,
                         'model_prob': cp_h2a, 'edge': edge_a,
                         'won': h2_margin < -h2_line})

    # ── 9. H2_OVER / H2_UNDER ──
    if h2_to is not None:
        h2_pred_total = pred_total * 0.48
        h2op = over_prob(h2_pred_total, float(h2_to))
        edge = h2op * STANDARD_ODDS - 1
        if edge > MIN_EDGE and h2_pts != float(h2_to):
            bets.append({'type': 'H2_OVER', 'odds': STANDARD_ODDS,
                         'model_prob': h2op, 'edge': edge,
                         'won': h2_pts > float(h2_to)})
        h2up = 1.0 - h2op
        edge_u = h2up * STANDARD_ODDS - 1
        if edge_u > MIN_EDGE and h2_pts != float(h2_to):
            bets.append({'type': 'H2_UNDER', 'odds': STANDARD_ODDS,
                         'model_prob': h2up, 'edge': edge_u,
                         'won': h2_pts < float(h2_to)})

    # ── 10. H1 derived from full + H2 ──
    if spread is not None and h2_sp is not None:
        full_line = signed_spread(spread, fav)
        h2_line   = signed_spread(h2_sp, fav)
        h1_line   = full_line - h2_line
        h1_pred_spread = pred_spread * 0.55
        cp_h1 = cover_prob(h1_pred_spread, h1_line)
        edge = cp_h1 * STANDARD_ODDS - 1
        if edge > MIN_EDGE:
            bets.append({'type': 'H1_ATS_HOME', 'odds': STANDARD_ODDS,
                         'model_prob': cp_h1, 'edge': edge,
                         'won': h1_margin > -h1_line})
        cp_h1a = 1.0 - cp_h1
        edge_a = cp_h1a * STANDARD_ODDS - 1
        if edge_a > MIN_EDGE:
            bets.append({'type': 'H1_ATS_AWAY', 'odds': STANDARD_ODDS,
                         'model_prob': cp_h1a, 'edge': edge_a,
                         'won': h1_margin < -h1_line})

    if total is not None and h2_to is not None:
        h1_line_total = float(total) - float(h2_to)
        h1_pred_total = pred_total * 0.52
        h1op = over_prob(h1_pred_total, h1_line_total)
        edge = h1op * STANDARD_ODDS - 1
        if edge > MIN_EDGE and h1_pts != h1_line_total:
            bets.append({'type': 'H1_OVER', 'odds': STANDARD_ODDS,
                         'model_prob': h1op, 'edge': edge,
                         'won': h1_pts > h1_line_total})
        h1up = 1.0 - h1op
        edge_u = h1up * STANDARD_ODDS - 1
        if edge_u > MIN_EDGE and h1_pts != h1_line_total:
            bets.append({'type': 'H1_UNDER', 'odds': STANDARD_ODDS,
                         'model_prob': h1up, 'edge': edge_u,
                         'won': h1_pts < h1_line_total})

    # ── 11. VALUE_DOG — big underdog where model disagrees ──
    if odds_h and odds_h > 3.0 and p_home > 0.28:
        edge = p_home * odds_h - 1
        if edge > MIN_EDGE * 2:
            bets.append({'type': 'VALUE_DOG', 'odds': odds_h,
                         'model_prob': p_home, 'edge': edge,
                         'won': actual_outcome['home_win']})
    if odds_a and odds_a > 3.0 and p_away > 0.28:
        edge = p_away * odds_a - 1
        if edge > MIN_EDGE * 2:
            bets.append({'type': 'VALUE_DOG', 'odds': odds_a,
                         'model_prob': p_away, 'edge': edge,
                         'won': not actual_outcome['home_win']})

    # ── 12. TEAM_TOTAL (home/away O/U) ──
    if total is not None:
        market_total = float(total)
        # Home team scoring: half total +/- half spread
        home_pred_pts = (pred_total / 2) + (-pred_spread / 2)
        away_pred_pts = (pred_total / 2) + (pred_spread / 2)
        home_line_pts = market_total / 2 + (-(signed_spread(spread, fav) or 0) / 2)
        away_line_pts = market_total / 2 + ((signed_spread(spread, fav) or 0) / 2)

        for pts_pred, pts_line, side_type, actual_pts in [
            (home_pred_pts, home_line_pts, 'TEAM_TOTAL_HOME_OVER', home_score),
            (away_pred_pts, away_line_pts, 'TEAM_TOTAL_AWAY_OVER', away_score),
        ]:
            op = over_prob(pts_pred, pts_line)
            edge = op * STANDARD_ODDS - 1
            if edge > MIN_EDGE and actual_pts != pts_line:
                bets.append({'type': side_type, 'odds': STANDARD_ODDS,
                             'model_prob': op, 'edge': edge,
                             'won': actual_pts > pts_line})

    return bets

###############################################################################
# BANKROLL STRATEGY SIMULATORS (run in parallel — share same bets per game)
###############################################################################

BET_TYPES_ALL = [
    'ML_HOME', 'ML_AWAY',
    'ATS_HOME', 'ATS_AWAY',
    'OVER', 'UNDER',
    'H2_ATS_HOME', 'H2_ATS_AWAY',
    'H2_OVER', 'H2_UNDER',
    'H1_ATS_HOME', 'H1_ATS_AWAY',
    'H1_OVER', 'H1_UNDER',
    'VALUE_DOG',
    'TEAM_TOTAL_HOME_OVER', 'TEAM_TOTAL_AWAY_OVER',
]

# Strategy definitions: (label, sizing_fn)
# sizing_fn(edge, odds, prob, bankroll, max_bet_pct) → stake
def kelly_stake(f):
    def _stake(edge, odds, prob, bankroll, max_bet_pct=0.025):
        b = odds - 1.0
        q = 1.0 - prob
        kelly_full = max(0.0, (b * prob - q) / b) if b > 0 else 0.0
        return min(bankroll * kelly_full * f, bankroll * max_bet_pct)
    return _stake

def flat_stake(flat):
    def _stake(edge, odds, prob, bankroll, max_bet_pct=0.025):
        return flat
    return _stake

def prop_stake(pct):
    def _stake(edge, odds, prob, bankroll, max_bet_pct=0.025):
        return bankroll * pct
    return _stake

# ── Martingale: double after loss, reset after win ──
def martingale_stake(base=5.0):
    streak = [0]  # loss streak (mutable closure)
    def _stake(edge, odds, prob, bankroll, max_bet_pct=0.20):
        raw = base * (2 ** streak[0])
        return min(raw, bankroll * max_bet_pct, bankroll)
    def _update(won):
        if won: streak[0] = 0
        else:   streak[0] += 1
    return _stake, _update

# ── AntiMartingale: double after win, reset after loss ──
def anti_martingale_stake(base=5.0, max_doubles=4):
    streak = [0]  # win streak (mutable closure)
    def _stake(edge, odds, prob, bankroll, max_bet_pct=0.20):
        doubles = min(streak[0], max_doubles)
        raw = base * (2 ** doubles)
        return min(raw, bankroll * max_bet_pct, bankroll)
    def _update(won):
        if won: streak[0] += 1
        else:   streak[0] = 0
    return _stake, _update

SIZING_STRATEGIES = {
    'Kelly_25pct':      kelly_stake(0.25),
    'Kelly_15pct':      kelly_stake(0.15),
    'Kelly_10pct':      kelly_stake(0.10),
    'Kelly_50pct':      kelly_stake(0.50),       # Aggressive Kelly
    'Kelly_Full':       kelly_stake(1.00),        # Full Kelly (dangerous but max compound)
    'Flat_10':          flat_stake(10.0),
    'Prop_1pct':        prop_stake(0.01),
    'Prop_5pct':        prop_stake(0.05),         # 5% of bankroll per bet
    'Prop_10pct':       prop_stake(0.10),         # 10% of bankroll — compound heavy
    'AllIn_Daily':      prop_stake(1.00),         # All bankroll = max compound interest
    # NOTE: Martingale / AntiMartingale are stateful — handled separately below
}

# Arena-category map: maps sizing key → arena system name (for cross-system alignment)
ARENA_CATEGORY = {
    'Kelly_Full':       'Kelly_Full',
    'Kelly_50pct':      'Kelly_Half',
    'Kelly_25pct':      'Kelly_Quarter',
    'Flat_10':          'Flat_10',
    'Prop_1pct':        'Prop_1pct',
    'Prop_5pct':        'Prop_5pct',
    'Prop_10pct':       'Prop_2pct',   # closest arena analog
    'AllIn_Daily':      'AllIn_Daily',
    'Kelly_15pct':      'Kelly_Quarter',
    'Kelly_10pct':      'Kelly_Quarter',
    'Martingale':       'Martingale',
    'AntiMartingale':   'AntiMartingale',
    'Conservative':     'Conservative',
    'Aggressive':       'Aggressive',
}

INITIAL_BANKROLL = 100.0
MAX_BET_PCT      = 1.00    # No per-position cap — let Kelly manage risk
MAX_DAILY_EXPO   = 1.00    # 100% portfolio daily — full compound interest
MIN_BET_STAKE    = 0.25    # minimum bet size
MIN_EDGE         = 0.003   # 0.3% minimum edge — lower to capture real edges after vig
                             # Tree ensemble at 0.228 Brier has small but real edge
                             # Kelly sizing handles position size (tiny bets on small edges)

# Filter sets: which bet types to include in each "strategy group"
# Full = all types; ML_only = moneyline only; etc.
BET_FILTER_SETS = {
    'ALL':        set(BET_TYPES_ALL),
    'ML_ONLY':    {'ML_HOME', 'ML_AWAY'},
    'ATS_ONLY':   {'ATS_HOME', 'ATS_AWAY'},
    'TOTALS':     {'OVER', 'UNDER'},
    'H2_ONLY':    {'H2_ATS_HOME', 'H2_ATS_AWAY', 'H2_OVER', 'H2_UNDER'},
    'H1_ONLY':    {'H1_ATS_HOME', 'H1_ATS_AWAY', 'H1_OVER', 'H1_UNDER'},
    'VALUE_DOG':  {'VALUE_DOG'},
    'ML_ATS':     {'ML_HOME', 'ML_AWAY', 'ATS_HOME', 'ATS_AWAY'},
    'ML_TOTALS':  {'ML_HOME', 'ML_AWAY', 'OVER', 'UNDER'},
    'TEAM_TOTAL': {'TEAM_TOTAL_HOME_OVER', 'TEAM_TOTAL_AWAY_OVER'},
    'TOP4': {  # Best bets from multi-market analysis: H1_ATS_AWAY, H1_UNDER, H2_UNDER, ML_AWAY
        'H1_ATS_AWAY', 'H1_UNDER', 'H2_UNDER', 'ML_AWAY'
    },
    # Arena-aligned filter sets
    'CONSERVATIVE_FILTER': {'ML_HOME', 'ML_AWAY', 'ATS_HOME', 'ATS_AWAY'},          # safe markets only
    'AGGRESSIVE_FILTER':   set(BET_TYPES_ALL),                                        # all markets
}

# Extra per-combo edge overrides for conservative/aggressive combos (filter_name → min_edge)
FILTER_MIN_EDGE_OVERRIDE = {
    'CONSERVATIVE_FILTER': 0.05,   # 5% edge required
    'AGGRESSIVE_FILTER':   0.005,  # 0.5% edge required
    'TOP4_CONSERVATIVE':   0.05,
    'TOP4_AGGRESSIVE':     0.005,
}

# Build all (bet_filter × sizing) strategy combos
STRATEGIES = {}
for flt_name, flt_set in BET_FILTER_SETS.items():
    for siz_name, siz_fn in SIZING_STRATEGIES.items():
        key = f"{flt_name}__{siz_name}"
        STRATEGIES[key] = {
            'filter': flt_set,
            'sizing': siz_fn,
            'label': key,
            'min_edge_override': FILTER_MIN_EDGE_OVERRIDE.get(flt_name),
            'stateful': False,
            'arena_category': ARENA_CATEGORY.get(siz_name, siz_name),
        }

# ── Special combos: TOP4_CONSERVATIVE / TOP4_AGGRESSIVE ──
TOP4_FILTER = {'H1_ATS_AWAY', 'H1_UNDER', 'H2_UNDER', 'ML_AWAY'}
STRATEGIES['TOP4_CONSERVATIVE__Kelly_25pct'] = {
    'filter': TOP4_FILTER,
    'sizing': kelly_stake(0.25),
    'label':  'TOP4_CONSERVATIVE__Kelly_25pct',
    'min_edge_override': 0.05,
    'stateful': False,
    'arena_category': 'Conservative',
}
STRATEGIES['TOP4_AGGRESSIVE__Kelly_50pct'] = {
    'filter': set(BET_TYPES_ALL),
    'sizing': kelly_stake(0.50),
    'label':  'TOP4_AGGRESSIVE__Kelly_50pct',
    'min_edge_override': 0.005,
    'stateful': False,
    'arena_category': 'Aggressive',
}

# ── Stateful strategies: Martingale / AntiMartingale ──
# Built per-filter-set and stored with their state objects
_MART_FILTERS = {
    'ML_ONLY':    {'ML_HOME', 'ML_AWAY'},
    'ALL':        set(BET_TYPES_ALL),
    'TOP4':       TOP4_FILTER,
}
_STATEFUL_STRATEGIES = {}
for flt_name, flt_set in _MART_FILTERS.items():
    for siz_name, builder in [('Martingale', martingale_stake), ('AntiMartingale', anti_martingale_stake)]:
        siz_fn, update_fn = builder(base=5.0)
        key = f"{flt_name}__{siz_name}"
        _STATEFUL_STRATEGIES[key] = {
            'filter': flt_set,
            'sizing': siz_fn,
            'update': update_fn,
            'label': key,
            'min_edge_override': None,
            'stateful': True,
            'arena_category': siz_name,
        }
STRATEGIES.update(_STATEFUL_STRATEGIES)

print(f"\n{len(STRATEGIES)} strategy combos to test across {len(BET_TYPES_ALL)} bet types")
print(f"Sizing strategies: {list(SIZING_STRATEGIES.keys()) + ['Martingale', 'AntiMartingale']}")
print(f"Bet filter sets: {list(BET_FILTER_SETS.keys())}")

###############################################################################
# WALK-FORWARD BACKTEST
###############################################################################

SEASON_START   = '2025-10-22'
WALK_STEP_DAYS = 7
MIN_TRAIN      = 500
N_FEATURES     = 110  # top features by variance

# Feature selection
variances = np.var(X_all, axis=0)
top_feature_idx = np.argsort(variances)[-N_FEATURES:]
print(f"Selected {len(top_feature_idx)} features by variance")

# Game date arrays
season_mask    = game_dates >= SEASON_START
season_indices = np.where(season_mask)[0]
if len(season_indices) == 0:
    print("ERROR: No games found for 2025-26 season"); sys.exit(1)
print(f"Season games: {len(season_indices)} ({game_dates[season_indices[0]]} to {game_dates[season_indices[-1]]})")

season_dates = sorted(set(game_dates[season_indices]))

# State for each strategy
state = {}
for skey in STRATEGIES:
    state[skey] = {
        'bankroll': INITIAL_BANKROLL,
        'peak': INITIAL_BANKROLL,
        'max_dd': 0.0,
        'bets': 0,
        'wins': 0,
        'losses': 0,
        'pnl_history': [],  # per-week PnL for Sharpe
        'equity': [],
        '_prev_bets': 0,
    }

# Per-bet-type stats (aggregated across all strategies for diagnostic)
global_bet_type_stats = defaultdict(lambda: {'bets': 0, 'wins': 0, 'pnl': 0.0})

# Brier tracking
brier_history = []

total_weeks = 0
n_weeks = 0

print(f"\n{'='*60}")
print("  STRATEGY CONFRONTATION — WALK-FORWARD")
print(f"{'='*60}")

for week_i in range(0, len(season_dates), WALK_STEP_DAYS):
    week_dates = season_dates[week_i:week_i + WALK_STEP_DAYS]
    if not week_dates:
        break

    cutoff_date = week_dates[0]
    n_weeks += 1

    # Training: all games before this week
    train_mask = game_dates < cutoff_date
    train_idx  = np.where(train_mask)[0]

    if len(train_idx) < MIN_TRAIN:
        print(f"Week {n_weeks}: {cutoff_date} — skip (only {len(train_idx)} train games)")
        continue

    # Test: games in this week
    test_mask = np.isin(game_dates, week_dates)
    test_idx  = np.where(test_mask)[0]
    if len(test_idx) == 0:
        continue

    max_valid  = min(len(X_all), len(y_all), len(games)) - 1
    train_idx  = train_idx[train_idx <= max_valid]
    test_idx   = test_idx[test_idx <= max_valid]
    if len(test_idx) == 0:
        continue

    X_train = X_all[train_idx][:, top_feature_idx]
    y_train = y_all[train_idx]
    X_test  = X_all[test_idx][:, top_feature_idx]
    y_test  = y_all[test_idx]
    test_game_dates = game_dates[test_idx]

    # Subsample training for speed
    if len(X_train) > 6000:
        X_train = X_train[-6000:]
        y_train = y_train[-6000:]

    print(f"\nWeek {n_weeks}: {week_dates[0]}->{week_dates[-1]} | "
          f"Train: {len(train_idx)} | Test: {len(test_idx)}")

    # P006: Temporal sample weighting — exponential decay (recent games up-weighted)
    # lambda=0.005 → half-weight at ~139 samples back (~half season)
    _n_tr = len(X_train)
    _sw = np.exp(-0.005 * (_n_tr - 1 - np.arange(_n_tr)))
    _sw = _sw * (_n_tr / _sw.sum())  # normalize: mean weight = 1.0

    # Train
    t0 = time.time()
    fitted = {}
    for name, model in make_models().items():
        try:
            model.fit(X_train, y_train, sample_weight=_sw)
            fitted[name] = model
        except Exception as e:
            print(f"  {name} train failed: {e}")

    if not fitted:
        print("  No models trained — skipping")
        continue

    # Predict
    probs = ensemble_predict(fitted, X_test)
    week_brier = float(brier_score_loss(y_test, probs))
    brier_history.append({'date': week_dates[0], 'brier': round(week_brier, 5),
                           'games': len(test_idx)})

    print(f"  Models: {list(fitted.keys())} | Train: {time.time()-t0:.0f}s | Brier: {week_brier:.5f}")

    # ── Per-game betting ──
    week_pnl_per_strategy = defaultdict(float)
    n_no_odds = 0
    n_with_odds = 0
    n_score_zero = 0
    n_bettable = 0
    _diag_printed = 0  # diagnostic: first N games with full detail

    for j in range(len(test_idx)):
        game_idx    = test_idx[j]
        p_home      = float(probs[j])
        game_date   = test_game_dates[j]

        g = games[game_idx] if game_idx < len(games) else {}

        # FIX: try all known field name patterns for home/away team
        raw_home = (g.get('home_team') or g.get('home') or g.get('HOME_TEAM') or
                    g.get('team_home') or g.get('home_team_abbreviation') or
                    g.get('visitor_team', '') or '')
        raw_away = (g.get('away_team') or g.get('away') or g.get('AWAY_TEAM') or
                    g.get('team_away') or g.get('away_team_abbreviation') or
                    g.get('visitor', '') or '')
        game_home = norm_team(raw_home) if raw_home else ''
        game_away = norm_team(raw_away) if raw_away else ''

        odds_key  = f"{game_date}_{game_home}_{game_away}"
        real_odds = ODDS_LOOKUP.get(odds_key, {})
        if not real_odds:
            # Try reverse key (away_home) — in case home/away are swapped
            odds_key_rev = f"{game_date}_{game_away}_{game_home}"
            real_odds = ODDS_LOOKUP.get(odds_key_rev, {})
            if real_odds:
                # Swap home/away odds to match our game orientation
                real_odds = dict(real_odds)
                real_odds['odds_home'], real_odds['odds_away'] = real_odds.get('odds_away'), real_odds.get('odds_home')

        if not real_odds and game_home and game_away:
            # SECONDARY: fuzzy date match — try +1 and -1 day (tip-off time zone edge)
            try:
                from datetime import datetime as _dt, timedelta as _td
                base_dt = _dt.strptime(game_date, '%Y-%m-%d')
                for delta in (-1, 1):
                    alt_date = (base_dt + _td(days=delta)).strftime('%Y-%m-%d')
                    for k_h, k_a in [(game_home, game_away), (game_away, game_home)]:
                        alt_key = f"{alt_date}_{k_h}_{k_a}"
                        if alt_key in ODDS_LOOKUP:
                            real_odds = dict(ODDS_LOOKUP[alt_key])
                            if k_h == game_away:  # reversed: swap odds
                                real_odds['odds_home'], real_odds['odds_away'] = real_odds.get('odds_away'), real_odds.get('odds_home')
                            break
                    if real_odds:
                        break
            except Exception:
                pass

        if not real_odds:
            if n_no_odds < 5:  # Print first 5 misses for diagnosis
                print(f"  No odds for: {odds_key} (raw: home={raw_home!r}, away={raw_away!r})")
            n_no_odds += 1
            continue
        n_with_odds += 1

        # Build actual outcome — exhaustive score field extraction
        home_score = 0
        away_score = 0
        for hs_key in ['home_score', 'score_home', 'PTS_home', 'pts_home', 'HOME_PTS', 'home_pts']:
            v = g.get(hs_key)
            if v is not None and v != '' and v != 0:
                home_score = int(v)
                break
        for as_key in ['away_score', 'score_away', 'PTS_away', 'pts_away', 'AWAY_PTS', 'away_pts']:
            v = g.get(as_key)
            if v is not None and v != '' and v != 0:
                away_score = int(v)
                break
        # Fallback: try nested stats objects — check 'home'/'away' dicts (nba_api format)
        # Recent games store scores at g['home']['pts'] and g['away']['pts']
        if home_score == 0:
            for stats_key in ['home_stats', 'home']:
                hs = g.get(stats_key)
                if isinstance(hs, dict):
                    v = hs.get('PTS', hs.get('pts', hs.get('points', 0)))
                    if v is not None and v != '' and v != 0:
                        home_score = int(float(v))
                        break
        if away_score == 0:
            for stats_key in ['away_stats', 'away']:
                as_ = g.get(stats_key)
                if isinstance(as_, dict):
                    v = as_.get('PTS', as_.get('pts', as_.get('points', 0)))
                    if v is not None and v != '' and v != 0:
                        away_score = int(float(v))
                        break
        # Fallback: reconstruct from quarter data
        if home_score == 0:
            q_h = sum(int(g.get(f'q{i}_home', 0) or 0) for i in range(1, 5))
            q_h += int(g.get('ot_home', 0) or 0)
            if q_h > 0:
                home_score = q_h
        if away_score == 0:
            q_a = sum(int(g.get(f'q{i}_away', 0) or 0) for i in range(1, 5))
            q_a += int(g.get('ot_away', 0) or 0)
            if q_a > 0:
                away_score = q_a

        if home_score == 0 and away_score == 0:
            n_score_zero += 1
            if n_score_zero <= 3:
                print(f"  SCORE=0 skip: {odds_key} | fields={list(g.keys())[:15]}")
            continue  # Game not played yet or missing score

        q_home = [int(g.get(f'q{i}_home', 0) or 0) for i in range(1, 5)]
        q_away = [int(g.get(f'q{i}_away', 0) or 0) for i in range(1, 5)]
        h1_margin = (sum(q_home[:2]) - sum(q_away[:2]))
        h2_margin = (sum(q_home[2:]) + int(g.get('ot_home', 0) or 0) -
                     sum(q_away[2:]) - int(g.get('ot_away', 0) or 0))
        h1_total  = sum(q_home[:2]) + sum(q_away[:2])
        h2_total  = (sum(q_home[2:]) + int(g.get('ot_home', 0) or 0) +
                     sum(q_away[2:]) + int(g.get('ot_away', 0) or 0))

        actual_outcome = {
            'home_win':  home_score > away_score,
            'margin':    home_score - away_score,
            'total_pts': home_score + away_score,
            'h1_margin': h1_margin,
            'h2_margin': h2_margin,
            'h1_total':  h1_total,
            'h2_total':  h2_total,
            'home_score': home_score,
            'away_score': away_score,
        }

        n_bettable += 1

        # Generate all bets for this game (use global MIN_EDGE as baseline floor)
        all_bets = generate_all_bets(p_home, real_odds, actual_outcome, MIN_EDGE)

        # DIAGNOSTIC: print detailed edge info for first 5 bettable games per week
        if _diag_printed < 5:
            odds_h = real_odds.get('odds_home')
            odds_a = real_odds.get('odds_away')
            edge_h = (p_home * odds_h - 1) if odds_h else None
            edge_a = ((1-p_home) * odds_a - 1) if odds_a else None
            eh_str = f"{edge_h:.4f}" if edge_h is not None else "N/A"
            ea_str = f"{edge_a:.4f}" if edge_a is not None else "N/A"
            print(f"  DIAG game {_diag_printed}: {game_home}v{game_away} | "
                  f"p_home={p_home:.4f} | odds_h={odds_h} odds_a={odds_a} | "
                  f"edge_h={eh_str} edge_a={ea_str} | "
                  f"score={home_score}-{away_score} | bets_generated={len(all_bets)}")
            if all_bets:
                for b in all_bets[:3]:
                    print(f"    -> {b['type']}: edge={b['edge']:.4f} odds={b['odds']:.3f} prob={b['model_prob']:.4f}")
            _diag_printed += 1

        # Diagnostic: accumulate global stats
        for bet in all_bets:
            bt = global_bet_type_stats[bet['type']]
            bt['bets'] += 1
            if bet['won']: bt['wins'] += 1

        # Run each strategy
        for skey, strat in STRATEGIES.items():
            flt          = strat['filter']
            siz          = strat['sizing']
            edge_floor   = strat.get('min_edge_override') or MIN_EDGE
            is_stateful  = strat.get('stateful', False)
            update_fn    = strat.get('update')
            br           = state[skey]['bankroll']
            day_expo     = 0.0

            filtered_bets = [b for b in all_bets
                             if b['type'] in flt and b['edge'] >= edge_floor]
            for bet in filtered_bets:
                stake = siz(bet['edge'], bet['odds'], bet['model_prob'], br, MAX_BET_PCT)

                if day_expo + stake > br * MAX_DAILY_EXPO:
                    stake = max(0, br * MAX_DAILY_EXPO - day_expo)

                if stake < MIN_BET_STAKE:
                    continue

                pnl = stake * (bet['odds'] - 1.0) if bet['won'] else -stake
                br  += pnl
                br   = max(br, 0.01)  # floor at 1 cent
                day_expo += stake
                week_pnl_per_strategy[skey] += pnl

                state[skey]['bets'] += 1
                if bet['won']: state[skey]['wins'] += 1
                else: state[skey]['losses'] += 1

                # Update stateful streak (Martingale / AntiMartingale)
                if is_stateful and update_fn:
                    update_fn(bet['won'])

                # Drawdown tracking
                if br > state[skey]['peak']:
                    state[skey]['peak'] = br
                dd = (state[skey]['peak'] - br) / state[skey]['peak'] * 100 if state[skey]['peak'] > 0 else 0
                if dd > state[skey]['max_dd']:
                    state[skey]['max_dd'] = dd

            state[skey]['bankroll'] = br

    # Record per-week PnL for Sharpe calculation
    for skey in STRATEGIES:
        week_pnl = week_pnl_per_strategy[skey]
        state[skey]['pnl_history'].append(week_pnl)
        state[skey]['equity'].append({
            'date': week_dates[-1],
            'bankroll': round(state[skey]['bankroll'], 2),
        })

    # Odds matching diagnostic + per-week bet count
    total_week_bets = sum(state[k]['bets'] - state[k].get('_prev_bets', 0) for k in state)
    if n_with_odds == 0 and n_no_odds > 0:
        print(f"  ODDS MISS: {n_no_odds} games had no odds, 0 matched => 0 bets possible")
    elif n_with_odds > 0:
        print(f"  Odds: {n_with_odds}/{n_with_odds + n_no_odds} matched | "
              f"Score OK: {n_bettable} | Score=0 skip: {n_score_zero} | "
              f"Bets this week: {total_week_bets}")
    else:
        print(f"  No odds data this week | Bets this week: {total_week_bets}")
    # Update _prev_bets snapshot for next week's delta
    for k in state:
        state[k]['_prev_bets'] = state[k]['bets']

    # Summary print for best strategies
    top5 = sorted(STRATEGIES.keys(),
                  key=lambda k: state[k]['bankroll'], reverse=True)[:5]
    for skey in top5:
        s = state[skey]
        roi = (s['bankroll'] - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
        print(f"  {skey[:35]:<35} ${s['bankroll']:.2f} ({roi:+.1f}%)")

    gc.collect()

# ── GLOBAL DIAGNOSTIC SUMMARY ──
print(f"\n{'='*60}")
print("  BET GENERATION DIAGNOSTIC")
print(f"{'='*60}")
print(f"Global bet type stats (across all weeks):")
if global_bet_type_stats:
    for bt_name, bt_stats in sorted(global_bet_type_stats.items()):
        wr = bt_stats['wins'] / bt_stats['bets'] * 100 if bt_stats['bets'] > 0 else 0
        print(f"  {bt_name:<25} bets={bt_stats['bets']:>5} wins={bt_stats['wins']:>5} ({wr:.1f}%)")
else:
    print("  *** NO BETS GENERATED AT ALL ***")
    print("  Likely causes:")
    print("    1. All games skipped (score=0/0) — check 'Score=0 skip' counts above")
    print("    2. All edges < MIN_EDGE (0.005) — model too close to market")
    print("    3. Odds not matching — check 'Odds MISS' counts above")
total_bets = sum(s['bets'] for s in state.values())
print(f"\nTotal bets placed across all strategies: {total_bets}")

###############################################################################
# COMPUTE FINAL CONFRONTATION TABLE
###############################################################################
import statistics

def compute_sharpe(pnl_history, initial_bankroll=INITIAL_BANKROLL):
    """Weekly Sharpe (annualized with sqrt(52))."""
    if len(pnl_history) < 2: return 0.0
    returns = [p / initial_bankroll for p in pnl_history]
    mean_r = statistics.mean(returns)
    std_r  = statistics.stdev(returns)
    if std_r == 0: return 0.0
    return round((mean_r / std_r) * (52 ** 0.5), 3)

confrontation = []
for skey, strat in STRATEGIES.items():
    s = state[skey]
    roi = (s['bankroll'] - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
    win_rate = s['wins'] / s['bets'] * 100 if s['bets'] > 0 else 0
    sharpe   = compute_sharpe(s['pnl_history'])

    parts = skey.split('__')
    bet_filter = parts[0] if len(parts) > 0 else skey
    sizing     = parts[1] if len(parts) > 1 else ''

    confrontation.append({
        'strategy':       skey,
        'bet_filter':     bet_filter,
        'sizing':         sizing,
        'arena_category': STRATEGIES[skey].get('arena_category', sizing),
        'roi_pct':        round(roi, 2),
        'final_bankroll': round(s['bankroll'], 2),
        'total_bets':     s['bets'],
        'wins':    s['wins'],
        'losses':  s['losses'],
        'win_rate_pct': round(win_rate, 1),
        'sharpe':       sharpe,
        'max_dd_pct':   round(s['max_dd'], 2),
        'equity': s['equity'],
    })

# Sort by ROI descending
confrontation.sort(key=lambda x: x['roi_pct'], reverse=True)

# Print top 20
avg_brier = statistics.mean([b['brier'] for b in brier_history]) if brier_history else 0
print(f"\n{'='*80}")
print(f"  STRATEGY CONFRONTATION — FINAL RANKINGS (Brier: {avg_brier:.5f})")
print(f"{'='*80}")
print(f"  {'Strategy':<40} {'ROI':>7} {'Bets':>6} {'Win%':>6} {'Sharpe':>7} {'MaxDD':>7}")
print(f"  {'-'*73}")
for row in confrontation[:20]:
    print(f"  {row['strategy']:<40} {row['roi_pct']:>+6.1f}% {row['total_bets']:>6} "
          f"{row['win_rate_pct']:>5.1f}% {row['sharpe']:>7.2f} {row['max_dd_pct']:>6.1f}%")

# Per-bet-type global diagnostic
print(f"\n{'='*60}")
print("  BET TYPE DIAGNOSTIC (across all strategies, kelly 25%)")
print(f"{'='*60}")
print(f"  {'Type':<25} {'Bets':>6} {'Wins':>6} {'Win%':>7}")
print(f"  {'-'*45}")
for bt, stats in sorted(global_bet_type_stats.items(),
                         key=lambda x: x[1]['bets'], reverse=True):
    wr = stats['wins'] / stats['bets'] * 100 if stats['bets'] else 0
    print(f"  {bt:<25} {stats['bets']:>6} {stats['wins']:>6} {wr:>6.1f}%")

# Best strategy per sizing method
print(f"\n{'='*60}")
print("  BEST BET_FILTER PER SIZING STRATEGY")
print(f"{'='*60}")
for siz in SIZING_STRATEGIES:
    group = [r for r in confrontation if r['sizing'] == siz]
    if group:
        best = group[0]
        print(f"  {siz:<20} -> {best['bet_filter']:<20} ROI={best['roi_pct']:+.1f}% "
              f"Sharpe={best['sharpe']:.2f}")

###############################################################################
# SAVE RESULTS
###############################################################################

output = {
    'run_at': datetime.now().isoformat(),
    'platform': 'Kaggle' if IS_KAGGLE else 'Colab' if IS_COLAB else 'Local',
    'season_start': SEASON_START,
    'n_weeks': n_weeks,
    'n_features': N_FEATURES,
    'models': list(WEIGHTS.keys()),
    'avg_brier': round(avg_brier, 5),
    'brier_history': brier_history,
    'initial_bankroll': INITIAL_BANKROLL,
    'total_strategies_tested': len(STRATEGIES),
    'bet_types_available': BET_TYPES_ALL,
    'bet_filter_sets': {k: sorted(v) for k, v in BET_FILTER_SETS.items()},
    'sizing_strategies': list(SIZING_STRATEGIES.keys()),
    'confrontation': confrontation,  # Full ranked table
    'global_bet_type_stats': {k: dict(v) for k, v in global_bet_type_stats.items()},
    'feature_engine_version': 'v3.0-43cat',
}

# Save to working dir
RESULTS_FILE = os.path.join(WORK_DIR, 'strategy-confrontation.json')
with open(RESULTS_FILE, 'w') as f:
    json.dump(output, f, indent=2)
print(f"\nSaved: {RESULTS_FILE}")

# Also save legacy format for compatibility
legacy = {
    'strategy': f'Tree Ensemble — Strategy Confrontation',
    'platform': output['platform'],
    'initial_bankroll': INITIAL_BANKROLL,
    'current_bankroll': confrontation[0]['final_bankroll'] if confrontation else INITIAL_BANKROLL,
    'total_roi_pct': confrontation[0]['roi_pct'] if confrontation else 0,
    'total_bets': confrontation[0]['total_bets'] if confrontation else 0,
    'wins': confrontation[0]['wins'] if confrontation else 0,
    'losses': confrontation[0]['losses'] if confrontation else 0,
    'win_rate': confrontation[0]['win_rate_pct'] if confrontation else 0,
    'sharpe_ratio': confrontation[0]['sharpe'] if confrontation else 0,
    'max_drawdown_pct': confrontation[0]['max_dd_pct'] if confrontation else 0,
    'avg_brier': round(avg_brier, 5),
    'brier_score': round(avg_brier, 5),
    'n_features': N_FEATURES,
    'models_used': list(WEIGHTS.keys()),
    'best_strategy': confrontation[0]['strategy'] if confrontation else 'N/A',
    'confrontation_top10': confrontation[:10],
    'last_updated': datetime.now().isoformat(),
    'season_start': SEASON_START,
    'model_version': 'v3.0-43cat / TreeOnly',
}
LEGACY_FILE = os.path.join(WORK_DIR, 'season_backtest_results.json')
with open(LEGACY_FILE, 'w') as f:
    json.dump(legacy, f, indent=2)

print(f"\n{'='*60}")
print(f"  WINNER: {confrontation[0]['strategy'] if confrontation else 'N/A'}")
if confrontation:
    w = confrontation[0]
    print(f"  ROI: {w['roi_pct']:+.2f}% | Bets: {w['total_bets']} | "
          f"Win: {w['win_rate_pct']:.1f}% | Sharpe: {w['sharpe']:.2f} | MaxDD: {w['max_dd_pct']:.1f}%")
print(f"  Avg Model Brier: {avg_brier:.5f}")
print(f"  Weeks: {n_weeks} | Strategies tested: {len(STRATEGIES)}")
print(f"{'='*60}")
print("Done.")
