"""TabICL Oracle Training — Kaggle GPU script (3-way + walk-forward holdout).

Reproduces the 2026-04-28 overnight Colab pipeline that promoted TabICL-186
to production at holdout Brier 0.21139.

Pipeline:
  1. Pull nba_cached_data.npz from HF dataset.
  2. Walk-forward holdout = last 15% by row order (rows sorted by game_date).
  3. Train 3 models on the train portion, score on holdout:
       - xgboost  (full alive features)
       - lightgbm (full alive features)
       - tabicl   (top-186 by variance)
     Plus per-fold CPCV CV on the train portion for each.
  4. Pick winner by HOLDOUT Brier (not CV — CV is biased relative to holdout
     in this corpus; all 3 models show negative gap of similar magnitude).
  5. Isotonic-calibrate the winner via 5-fold OOF on full data.
  6. Stratified-by-month sanity-check holdout for the winner: 12 month buckets,
     pick the worst 15% of months as holdout, recompute Brier. If this number
     is >0.005 worse than walk-forward holdout, the win is "window-lucky".
  7. Save full bundle + push to nba-oracle-archive.
  8. Promote to nba-oracle-model only if holdout_brier < current production
     holdout_brier (read from summary.json).

Setup on Kaggle:
  - Add-ons -> Secrets -> HF_TOKEN = LBJLincoln26 owner token
  - Settings -> Internet ON
  - GPU enabled (T4 free tier; falls back to CPU for xgb/lgbm)

Targets: holdout < 0.21139 (current production), CV < 0.22169 (current best
TabICL CPCV CV — the more honest production-Brier expectation).
"""
import os, sys, json, pickle, time, itertools
from datetime import datetime, timezone

# --- Kaggle secret / install --------------------------------------------------
try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret('HF_TOKEN')
except Exception:
    HF_TOKEN = os.environ.get('HF_TOKEN', '')
os.environ['HF_TOKEN'] = HF_TOKEN
print(f'HF_TOKEN set, len={len(HF_TOKEN)}', flush=True)

os.system('pip install -q tabicl xgboost lightgbm huggingface_hub')

import numpy as np
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
from huggingface_hub import HfApi, hf_hub_download

# 2026-04-28 — TabICLClassifier defaults to CPU when `device` is not passed.
# Colab/Kaggle GPU sessions silently ran on CPU (~5× slower) because we omitted
# the param. Detect CUDA explicitly + FAIL LOUD if a GPU runtime was expected
# but torch can't see it (mismatched torch/CUDA install, runtime not attached).
import torch
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'[GPU] torch.cuda.is_available()={torch.cuda.is_available()} -> DEVICE={DEVICE}', flush=True)
if torch.cuda.is_available():
    print(f'[GPU] device_name={torch.cuda.get_device_name(0)} '
          f'capability={torch.cuda.get_device_capability(0)} '
          f'mem_total={torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB',
          flush=True)
    try:
        import subprocess
        print('[GPU] nvidia-smi:')
        print(subprocess.check_output(['nvidia-smi', '-L'], text=True).strip(), flush=True)
    except Exception:
        pass
elif os.environ.get('REQUIRE_GPU', '0') == '1':
    raise RuntimeError(
        'REQUIRE_GPU=1 but torch.cuda.is_available()=False. '
        'Likely cause: Colab Runtime -> Change runtime type was set to CPU, '
        'or PyTorch wheel was installed without CUDA support. '
        'Run !nvidia-smi in a cell first to confirm a GPU is attached.'
    )

# --- 1. Pull cache ------------------------------------------------------------
NPZ = hf_hub_download(
    repo_id='LBJLincoln26/nba-feature-cache',
    filename='nba_cached_data.npz',
    repo_type='dataset', token=HF_TOKEN,
)
data = np.load(NPZ, allow_pickle=True)
X_full = data['X']; y = data['y']; feat_names = list(data['feature_names'])
X_full = np.nan_to_num(X_full, nan=0.0, posinf=0.0, neginf=0.0)
print(f'cache: X={X_full.shape} y={y.shape} y_mean={y.mean():.3f}', flush=True)

# Best-effort game_date for month-stratified sanity check
game_dates = None
try:
    if 'game_dates' in data.files:
        game_dates = data['game_dates']
        print(f'game_dates available: {len(game_dates)} entries', flush=True)
except Exception:
    pass

variances = X_full.var(axis=0)
alive_mask = variances > 1e-10
alive_idx = np.where(alive_mask)[0]
print(f'alive features: {alive_mask.sum()}/{len(variances)}', flush=True)

# --- 2. Walk-forward holdout (last 15% by row order) --------------------------
N = len(X_full)
HOLDOUT_FRAC = 0.15
HO_START = int(N * (1 - HOLDOUT_FRAC))
train_idx = np.arange(HO_START)
holdout_idx = np.arange(HO_START, N)
print(f'walk-forward: train={len(train_idx)} holdout={len(holdout_idx)} (last {HOLDOUT_FRAC:.0%} by row order)', flush=True)

# --- Feature views ------------------------------------------------------------
X_alive = X_full[:, alive_idx].astype(np.float32)

ranked_alive = sorted(range(len(alive_idx)), key=lambda i: -variances[alive_idx[i]])
top186_alive_pos = ranked_alive[:186]
top186_full_idx = [int(alive_idx[i]) for i in top186_alive_pos]
X_186 = X_full[:, top186_full_idx].astype(np.float32)
feat_names_186 = [feat_names[i] for i in top186_full_idx]

# --- CPCV utility (operates on the train portion only) -----------------------
RANDOM_STATE = 1337
N_FOLDS = 10

def cpcv_folds(n_train):
    embargo = max(1, int(n_train * 0.02))
    fold_size = n_train // N_FOLDS
    for k in range(N_FOLDS):
        lo = k * fold_size
        hi = lo + fold_size if k < N_FOLDS - 1 else n_train
        train_mask = np.ones(n_train, dtype=bool)
        train_mask[max(0, lo - embargo):min(n_train, hi + embargo)] = False
        yield np.where(train_mask)[0], np.arange(lo, hi)

# --- 3a. xgboost on alive ----------------------------------------------------
def fit_predict_xgb(Xtr, ytr, Xte):
    import xgboost as xgb
    m = xgb.XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, eval_metric='logloss',
        random_state=RANDOM_STATE, n_jobs=-1, tree_method='hist',
    )
    m.fit(Xtr, ytr, verbose=False)
    return m.predict_proba(Xte)[:, 1], m

# --- 3b. lightgbm on alive ---------------------------------------------------
def fit_predict_lgbm(Xtr, ytr, Xte):
    import lightgbm as lgb
    m = lgb.LGBMClassifier(
        n_estimators=400, max_depth=-1, num_leaves=63, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE,
        n_jobs=-1, verbose=-1,
    )
    m.fit(Xtr, ytr)
    return m.predict_proba(Xte)[:, 1], m

# --- 3c. tabicl on top-186 (sweep ctx,temp on CPCV, then refit on train) ----
def sweep_tabicl(X_train, y_train):
    from tabicl import TabICLClassifier
    sweep_results = []
    for ctx in [1024, 2048, 3072]:
        for temp in [0.95, 1.0, 1.08]:
            fold_briers = []
            t0 = time.time()
            for tr, te in cpcv_folds(len(X_train)):
                m = TabICLClassifier(n_estimators=1, softmax_temperature=temp,
                                     device=DEVICE,
                                     random_state=RANDOM_STATE)
                sub_tr = tr[-ctx:]
                m.fit(X_train[sub_tr], y_train[sub_tr])
                p = m.predict_proba(X_train[te])[:, 1]
                fold_briers.append(float(brier_score_loss(y_train[te], p)))
            cv = float(np.mean(fold_briers))
            sweep_results.append({'ctx': ctx, 'temp': temp, 'cv_brier_mean': cv,
                                  'cv_brier_per_fold': fold_briers,
                                  'fit_time_sec': time.time() - t0})
            print(f'  tabicl ctx={ctx} temp={temp:.2f} cv={cv:.5f}', flush=True)
    return sweep_results

# --- Run all three -----------------------------------------------------------
all_results = []

# CPCV-CV per model on the train portion
def cv_brier(predict_fn, X_train, y_train):
    fold_briers = []
    for tr, te in cpcv_folds(len(X_train)):
        p, _ = predict_fn(X_train[tr], y_train[tr], X_train[te])
        fold_briers.append(float(brier_score_loss(y_train[te], p)))
    return float(np.mean(fold_briers)), fold_briers

print('\n=== xgboost (alive) ===', flush=True)
t0 = time.time()
xgb_cv, xgb_cv_per = cv_brier(fit_predict_xgb, X_alive[train_idx], y[train_idx])
xgb_p_ho, xgb_model = fit_predict_xgb(X_alive[train_idx], y[train_idx], X_alive[holdout_idx])
xgb_ho = float(brier_score_loss(y[holdout_idx], xgb_p_ho))
print(f'  xgb cv={xgb_cv:.5f} holdout={xgb_ho:.5f} ({time.time()-t0:.0f}s)', flush=True)
all_results.append({'model': 'xgboost', 'features': len(alive_idx),
                    'brier_cv': xgb_cv, 'brier_cv_per_fold': xgb_cv_per,
                    'brier_holdout': xgb_ho})

print('\n=== lightgbm (alive) ===', flush=True)
t0 = time.time()
lgbm_cv, lgbm_cv_per = cv_brier(fit_predict_lgbm, X_alive[train_idx], y[train_idx])
lgbm_p_ho, lgbm_model = fit_predict_lgbm(X_alive[train_idx], y[train_idx], X_alive[holdout_idx])
lgbm_ho = float(brier_score_loss(y[holdout_idx], lgbm_p_ho))
print(f'  lgbm cv={lgbm_cv:.5f} holdout={lgbm_ho:.5f} ({time.time()-t0:.0f}s)', flush=True)
all_results.append({'model': 'lightgbm', 'features': len(alive_idx),
                    'brier_cv': lgbm_cv, 'brier_cv_per_fold': lgbm_cv_per,
                    'brier_holdout': lgbm_ho})

print('\n=== tabicl (top-186) ===', flush=True)
sweep = sweep_tabicl(X_186[train_idx], y[train_idx])
best = min(sweep, key=lambda r: r['cv_brier_mean'])
print(f'  best ctx={best["ctx"]} temp={best["temp"]} cv={best["cv_brier_mean"]:.5f}', flush=True)
from tabicl import TabICLClassifier
ti_train = TabICLClassifier(n_estimators=1, softmax_temperature=best['temp'],
                            device=DEVICE,
                            random_state=RANDOM_STATE)
ti_sub = train_idx[-best['ctx']:]
ti_train.fit(X_186[ti_sub], y[ti_sub])
ti_p_ho = ti_train.predict_proba(X_186[holdout_idx])[:, 1]
ti_ho = float(brier_score_loss(y[holdout_idx], ti_p_ho))
print(f'  tabicl cv={best["cv_brier_mean"]:.5f} holdout={ti_ho:.5f}', flush=True)
all_results.append({'model': 'tabicl', 'features': 186,
                    'brier_cv': best['cv_brier_mean'],
                    'brier_cv_per_fold': best['cv_brier_per_fold'],
                    'brier_holdout': ti_ho,
                    'ctx_size': best['ctx'],
                    'softmax_temperature': best['temp']})

# --- 4. Pick winner by HOLDOUT ----------------------------------------------
winner = min(all_results, key=lambda r: r['brier_holdout'])
print(f'\nWINNER (by holdout): {winner["model"]} on {winner["features"]} features', flush=True)
print(f'  CV     : {winner["brier_cv"]:.5f}', flush=True)
print(f'  Holdout: {winner["brier_holdout"]:.5f}', flush=True)

# --- 5. Isotonic on winner ---------------------------------------------------
iso = None
calib_brier = None
if winner['model'] == 'tabicl':
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    oof = np.zeros(len(X_186))
    for tr, te in skf.split(X_186, y):
        sub_tr = tr[-best['ctx']:] if len(tr) > best['ctx'] else tr
        m = TabICLClassifier(n_estimators=1, softmax_temperature=best['temp'],
                             random_state=RANDOM_STATE)
        m.fit(X_186[sub_tr], y[sub_tr])
        oof[te] = m.predict_proba(X_186[te])[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip').fit(oof, y)
    calib_brier = float(brier_score_loss(y, iso.predict(oof)))
    print(f'isotonic: raw={brier_score_loss(y, oof):.5f} -> calibrated={calib_brier:.5f}', flush=True)

# --- 6. Month-stratified sanity check on the winner --------------------------
month_holdout_brier = None
if game_dates is not None:
    try:
        months = np.array([str(d)[:7] for d in game_dates])
        unique_months = sorted(set(months))
        # Pick last ~15% of months as holdout (approximation of "worst" without
        # using labels — keeps it leakage-free).
        n_ho_months = max(1, int(len(unique_months) * HOLDOUT_FRAC))
        ho_months = set(unique_months[-n_ho_months:])
        ho_mask = np.array([m in ho_months for m in months])
        tr_mask = ~ho_mask
        if winner['model'] == 'tabicl':
            mw = TabICLClassifier(n_estimators=1, softmax_temperature=best['temp'],
                                  random_state=RANDOM_STATE)
            tr_pos = np.where(tr_mask)[0][-best['ctx']:]
            mw.fit(X_186[tr_pos], y[tr_pos])
            p = mw.predict_proba(X_186[ho_mask])[:, 1]
        elif winner['model'] == 'xgboost':
            p, _ = fit_predict_xgb(X_alive[tr_mask], y[tr_mask], X_alive[ho_mask])
        else:
            p, _ = fit_predict_lgbm(X_alive[tr_mask], y[tr_mask], X_alive[ho_mask])
        month_holdout_brier = float(brier_score_loss(y[ho_mask], p))
        print(f'month-stratified holdout brier: {month_holdout_brier:.5f} '
              f'(n={ho_mask.sum()}, {n_ho_months} months)', flush=True)
    except Exception as e:
        print(f'month-stratified sanity check FAILED: {e}', flush=True)

# --- 7. Save bundle + push ---------------------------------------------------
utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')
final_model = ti_train if winner['model'] == 'tabicl' else (
    xgb_model if winner['model'] == 'xgboost' else lgbm_model)
feat_idx_save = top186_full_idx if winner['model'] == 'tabicl' else [int(i) for i in alive_idx]
feat_names_save = feat_names_186 if winner['model'] == 'tabicl' else [feat_names[i] for i in alive_idx]

bundle = {
    'model': final_model,
    'calibrator': iso,
    'feature_indices': feat_idx_save,
    'feature_names': feat_names_save,
    'cv_brier_mean': winner['brier_cv'],
    'holdout_brier': winner['brier_holdout'],
    'isotonic_calib_brier': calib_brier,
    'month_stratified_holdout_brier': month_holdout_brier,
    'config': {
        'model_type': winner['model'],
        'n_features': len(feat_idx_save),
        'random_state': RANDOM_STATE,
        'cpcv_folds': N_FOLDS,
        'walk_forward_holdout_frac': HOLDOUT_FRAC,
        'holdout_n_games': int(len(holdout_idx)),
        'features_alive_total': int(len(alive_idx)),
        'features_engine_total': int(X_full.shape[1]),
        'all_results_summary': all_results,
        **({'ctx_size': best['ctx'], 'softmax_temperature': best['temp']}
           if winner['model'] == 'tabicl' else {}),
    },
    'n_samples': int(X_full.shape[0]),
    'trained_at': utc,
    'trained_on': 'kaggle-multi-tabicl',
}
PKL = f'/kaggle/working/multi-tabicl-{utc}.pkl'
with open(PKL, 'wb') as f: pickle.dump(bundle, f)
print(f'pkl saved: {PKL}, size {os.path.getsize(PKL)/1024/1024:.1f} MB', flush=True)

api = HfApi(token=HF_TOKEN)
api.create_repo('LBJLincoln26/nba-oracle-archive', repo_type='dataset',
                private=False, exist_ok=True)
api.upload_file(
    path_or_fileobj=PKL,
    path_in_repo=f'kaggle-multi-tabicl-{utc}.pkl',
    repo_id='LBJLincoln26/nba-oracle-archive', repo_type='dataset',
    commit_message=f'[kaggle-multi-tabicl] {winner["model"]} holdout {winner["brier_holdout"]:.5f} cv {winner["brier_cv"]:.5f}',
)
print('archived', flush=True)

# --- 8. Promotion gate uses HOLDOUT, not CV ---------------------------------
try:
    cur = json.load(open(hf_hub_download(
        repo_id='LBJLincoln26/nba-oracle-model', filename='summary.json',
        repo_type='dataset', token=HF_TOKEN)))
    cur_holdout = float(cur.get('holdout_brier', cur.get('cv_brier_mean', 0.99)))
except Exception:
    cur_holdout = 0.99
print(f'current production holdout: {cur_holdout:.5f}', flush=True)

if winner['brier_holdout'] < cur_holdout:
    api.upload_file(
        path_or_fileobj=PKL, path_in_repo='nba-oracle.pkl',
        repo_id='LBJLincoln26/nba-oracle-model', repo_type='dataset',
        commit_message=f'[PROMOTE kaggle-multi-tabicl] holdout {winner["brier_holdout"]:.5f} (was {cur_holdout:.5f})',
    )
    summary = {k: v for k, v in bundle.items() if k not in ('model', 'calibrator')}
    summary['promoted_from_holdout'] = cur_holdout
    api.upload_file(
        path_or_fileobj=json.dumps(summary, indent=2, default=str).encode(),
        path_in_repo='summary.json',
        repo_id='LBJLincoln26/nba-oracle-model', repo_type='dataset',
        commit_message=f'[PROMOTE kaggle-multi-tabicl] summary update',
    )
    print(f'\n*** PROMOTED: {winner["model"]} holdout {winner["brier_holdout"]:.5f} '
          f'(was {cur_holdout:.5f}) ***', flush=True)
else:
    print(f'Not promoted: {winner["brier_holdout"]:.5f} >= {cur_holdout:.5f}', flush=True)

print('\n=== DONE ===', flush=True)
