#!/usr/bin/env python3
"""GPU experiment dispatcher — coordinates 2 Colab + 2 Modal + 2 Lightning + Kaggle accounts.

Closes the months-long bleed of "every account training the same RF on same features".

State of the world:
- LBJLincoln26/nba-experiment-queue (HF dataset, single JSON file)
  - { "experiments": [ {id, kind, config, status, claimed_by, started_at, brier, notes}, ... ] }
- Each GPU script: claim_experiment(account_label) → returns next pending one
- After training: report_result(id, brier, archive_url) → marks done, frees slot
- 30-min stale claim: any experiment with claimed_by but no result after 30min reverts to pending

USAGE — every GPU script does this at startup:

    from scripts.gpu.experiment_registry import claim_experiment, report_result
    exp = claim_experiment(account_label='colab-1')
    if not exp:
        print('no pending experiments — exiting'); sys.exit(0)
    # ... train using exp['config'] ...
    report_result(exp['id'], brier=measured_brier, archive_url=archive_url, notes='...')

EXPERIMENT KINDS:
- 'oracle_rf'       — RandomForest with feature subset (Kaggle baseline)
- 'oracle_xgb'      — XGBoost with feature subset
- 'oracle_extratrees' — ExtraTrees
- 'oracle_lightgbm' — LightGBM
- 'oracle_tabicl'   — TabICL (GPU only, Colab T4+ / Modal A10G)
- 'oracle_tabpfn'   — TabPFN-2.5 (GPU only)
- 'oracle_ensemble' — stack top-N from above
- 'pol_oracle_rf'   — Political variant
- 'feature_search'  — GA on features (CPU islands handle this)

CONFIG: { 'model_type': str, 'n_features': int, 'feature_seed': int, 'cv_folds': int,
          'hyperparams': {...}, 'train_data': 'nba_cached_data.npz' (HF dataset link) }
"""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

REGISTRY_DATASET = 'LBJLincoln26/nba-experiment-queue'
REGISTRY_FILE = 'experiments.json'
STALE_CLAIM_MINUTES = 30


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _api():
    from huggingface_hub import HfApi
    # Prefer HF_TOKEN_NBA (LBJLincoln26 owns the dataset) over HF_TOKEN (LBJLincoln, no write access)
    tok = os.environ.get('HF_TOKEN_NBA') or os.environ.get('HF_TOKEN') or ''
    if not tok:
        raise RuntimeError('HF_TOKEN_NBA / HF_TOKEN missing')
    return HfApi(token=tok)


def _load_registry() -> List[Dict[str, Any]]:
    """Pull current registry from HF. Empty list if missing."""
    try:
        from huggingface_hub import hf_hub_download
        api = _api()
        # Ensure dataset exists
        try:
            api.create_repo(REGISTRY_DATASET, repo_type='dataset', private=False, exist_ok=True)
        except Exception:
            pass
        try:
            p = hf_hub_download(repo_id=REGISTRY_DATASET, filename=REGISTRY_FILE,
                                repo_type='dataset', token=api.token)
            return json.loads(open(p).read()).get('experiments', [])
        except Exception:
            return []
    except Exception as e:
        print(f'[registry] load err: {e}', file=sys.stderr)
        return []


def _save_registry(experiments: List[Dict[str, Any]]) -> bool:
    try:
        api = _api()
        body = json.dumps({'experiments': experiments, 'updated_at': _utc_now()}, indent=2)
        api.upload_file(
            path_or_fileobj=body.encode(),
            path_in_repo=REGISTRY_FILE,
            repo_id=REGISTRY_DATASET, repo_type='dataset',
            commit_message=f'[registry] update — {len(experiments)} entries',
        )
        return True
    except Exception as e:
        print(f'[registry] save err: {e}', file=sys.stderr)
        return False


def _is_stale(exp: Dict[str, Any]) -> bool:
    if exp.get('status') != 'claimed': return False
    started = exp.get('started_at', '')
    if not started: return False
    try:
        t = datetime.fromisoformat(started.replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - t) > timedelta(minutes=STALE_CLAIM_MINUTES)
    except Exception:
        return False


def claim_experiment(account_label: str, kinds: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Claim the next pending experiment for this account.

    account_label: e.g. 'colab-bartoli', 'colab-lahargne', 'modal-1', 'lightning-1', 'kaggle'
    kinds: filter by experiment kind (e.g. ['oracle_tabicl'] for GPU-only accounts)
    """
    exps = _load_registry()
    # Reset stale claims
    for e in exps:
        if _is_stale(e):
            e['status'] = 'pending'
            e['claimed_by'] = None
            e['stale_reset_at'] = _utc_now()
    # Find a pending one matching kinds
    candidates = [e for e in exps if e.get('status') == 'pending'
                  and (not kinds or e.get('kind') in kinds)]
    if not candidates:
        _save_registry(exps)  # save stale resets even if nothing claimed
        return None
    chosen = candidates[0]
    chosen['status'] = 'claimed'
    chosen['claimed_by'] = account_label
    chosen['started_at'] = _utc_now()
    if _save_registry(exps):
        print(f'[registry] {account_label} claimed exp {chosen["id"]} ({chosen["kind"]})', file=sys.stderr)
        return chosen
    return None


def report_result(exp_id: str, brier: float, archive_url: Optional[str] = None,
                  status: str = 'done', notes: str = '') -> bool:
    """Mark experiment complete with brier + optional archive URL."""
    exps = _load_registry()
    target = next((e for e in exps if e.get('id') == exp_id), None)
    if not target:
        print(f'[registry] report_result: exp {exp_id} not found', file=sys.stderr)
        return False
    target['status'] = status  # 'done' | 'failed'
    target['brier'] = float(brier) if brier is not None else None
    target['archive_url'] = archive_url
    target['completed_at'] = _utc_now()
    target['notes'] = notes
    return _save_registry(exps)


def add_experiment(kind: str, config: Dict[str, Any], notes: str = '') -> str:
    """Add a new experiment to the queue. Returns its id."""
    exps = _load_registry()
    eid = f'{kind}-{int(time.time())}-{len(exps):04d}'
    exps.append({
        'id': eid, 'kind': kind, 'config': config,
        'status': 'pending', 'claimed_by': None, 'started_at': None,
        'completed_at': None, 'brier': None, 'archive_url': None,
        'created_at': _utc_now(), 'notes': notes,
    })
    _save_registry(exps)
    return eid


def status() -> Dict[str, Any]:
    """One-line status: pending vs claimed vs done counts + best brier so far."""
    exps = _load_registry()
    by_status = {}
    for e in exps:
        by_status[e.get('status', 'unknown')] = by_status.get(e.get('status', 'unknown'), 0) + 1
    done = [e for e in exps if e.get('status') == 'done' and e.get('brier')]
    best = min(done, key=lambda e: e['brier']) if done else None
    return {
        'total': len(exps),
        'by_status': by_status,
        'best_brier_so_far': best.get('brier') if best else None,
        'best_kind': best.get('kind') if best else None,
        'best_archive': best.get('archive_url') if best else None,
    }


def seed_initial_queue() -> int:
    """Idempotent — populate queue with ~20 diverse experiments if empty."""
    if _load_registry():
        return 0
    exps_to_add = [
        # GPU-required (TabICL/TabPFN are recent SOTA)
        ('oracle_tabicl', {'model_type': 'tabicl', 'n_features': 200, 'feature_seed': 42}, 'TabICL 200f s42'),
        ('oracle_tabicl', {'model_type': 'tabicl', 'n_features': 300, 'feature_seed': 7}, 'TabICL 300f s7'),
        ('oracle_tabicl', {'model_type': 'tabicl', 'n_features': 500, 'feature_seed': 11}, 'TabICL 500f s11'),
        ('oracle_tabpfn', {'model_type': 'tabpfn', 'n_features': 100, 'feature_seed': 13}, 'TabPFN-2.5 100f'),
        ('oracle_tabpfn', {'model_type': 'tabpfn', 'n_features': 200, 'feature_seed': 17}, 'TabPFN-2.5 200f'),
        # Tree models (CPU is fine — Modal/Lightning don't need GPU for these)
        ('oracle_xgb', {'model_type': 'xgboost', 'n_features': 200, 'feature_seed': 1, 'max_depth': 8}, 'XGB-200-d8'),
        ('oracle_xgb', {'model_type': 'xgboost', 'n_features': 300, 'feature_seed': 3, 'max_depth': 12}, 'XGB-300-d12'),
        ('oracle_lightgbm', {'model_type': 'lightgbm', 'n_features': 200, 'feature_seed': 5}, 'LGBM-200'),
        ('oracle_lightgbm', {'model_type': 'lightgbm', 'n_features': 400, 'feature_seed': 19}, 'LGBM-400'),
        ('oracle_extratrees', {'model_type': 'extra_trees', 'n_features': 200, 'feature_seed': 23}, 'ET-200'),
        ('oracle_extratrees', {'model_type': 'extra_trees', 'n_features': 350, 'feature_seed': 29}, 'ET-350'),
        ('oracle_rf', {'model_type': 'random_forest', 'n_features': 200, 'feature_seed': 31}, 'RF-200-s31'),
        ('oracle_rf', {'model_type': 'random_forest', 'n_features': 250, 'feature_seed': 37}, 'RF-250-s37'),
        # Stacked ensemble (run after individuals complete)
        ('oracle_ensemble', {'mode': 'stacking', 'top_n': 5}, 'stack top-5'),
        # Political
        ('pol_oracle_rf', {'model_type': 'random_forest', 'n_features': 200, 'feature_seed': 41}, 'POL-RF-200'),
        ('pol_oracle_xgb', {'model_type': 'xgboost', 'n_features': 200, 'feature_seed': 43}, 'POL-XGB-200'),
    ]
    for k, c, n in exps_to_add:
        add_experiment(k, c, n)
    return len(exps_to_add)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--seed', action='store_true', help='populate initial queue')
    p.add_argument('--status', action='store_true')
    p.add_argument('--claim', help='claim next experiment for this account label')
    p.add_argument('--kinds', help='comma-separated kind filter for --claim')
    p.add_argument('--report', help='exp_id to mark done')
    p.add_argument('--brier', type=float, help='brier for --report')
    args = p.parse_args()

    if args.seed:
        n = seed_initial_queue()
        print(f'seeded {n} experiments')
    if args.status:
        print(json.dumps(status(), indent=2))
    if args.claim:
        kinds = args.kinds.split(',') if args.kinds else None
        e = claim_experiment(args.claim, kinds)
        print(json.dumps(e, indent=2) if e else 'no pending experiment')
    if args.report:
        ok = report_result(args.report, brier=args.brier or 0.99)
        print('reported:', ok)
