#!/usr/bin/env python3
"""
Guardian Orchestrator v3 — Cross-Department Intelligence System

Runs all 11 department Karpathy loops then performs:
  1. Cross-department intelligence (reads all karpathy-output.json)
  2. Priority-ordered action queue
  3. Elimination tracking (strategies, agents, features)
  4. Auto-actions for stagnation / parity mismatch / phantom games
  5. Consolidated guardian-report.json
  6. Telegram broadcast to @Nomos42
"""
import subprocess, json, time, os, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone

DEPARTMENTS = {
    'research': {'script': 'research-loop.sh', 'metric': 'proposals_generated', 'max_time': 300},
    'engineering': {'script': 'engineering-loop.sh', 'metric': 'brier_delta', 'max_time': 300},
    'evolution': {'script': 'evolution-loop.sh', 'metric': 'best_brier', 'max_time': 300},
    'betting': {'script': 'betting-loop.sh', 'metric': 'roi_delta', 'max_time': 300},
    'evaluation': {'script': 'evaluation-loop.sh', 'metric': 'calibration_error', 'max_time': 300},
    'infra': {'script': 'infra-loop.sh', 'metric': 'uptime_pct', 'max_time': 300},
    'political': {'script': 'political-loop.sh', 'metric': 'political_brier', 'max_time': 300},
    'creative': {'script': 'creative-loop.sh', 'metric': 'quality_score', 'max_time': 300},
    'communication': {'script': 'comm-loop.sh', 'metric': 'engagement_rate', 'max_time': 300},
    'business': {'script': 'business-loop.sh', 'metric': 'mrr', 'max_time': 300},
    'finance': {'script': 'finance-loop.sh', 'metric': 'financial_accuracy', 'max_time': 300},
}

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / 'data' / 'departments'
GUARDIAN_REPORT = DATA_DIR / 'guardian-report.json'
ELIMINATIONS_FILE = DATA_DIR / 'eliminations.json'

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID', '@Nomos42')
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
MAX_MSG_LEN = 4000

# Island definitions — canonical specialist roles per CLAUDE.md
ISLANDS = {
    'S10': {'url': 'nomos42-nba-quant',   'role': 'exploitation',         'specialist_model': None,          'mut': 0.09, 'feat': 63},
    'S11': {'url': 'nomos42-nba-quant-2', 'role': 'exploration',          'specialist_model': None,          'mut': 0.15, 'feat': 80},
    'S12': {'url': 'nomos42-nba-evo-3',   'role': 'extra_trees_specialist','specialist_model': 'extra_trees', 'mut': 0.08, 'feat': 60},
    'S13': {'url': 'nomos42-nba-evo-4',   'role': 'catboost_specialist',   'specialist_model': 'catboost',    'mut': 0.10, 'feat': 66},
    'S14': {'url': 'nomos42-nba-evo-5',   'role': 'lightgbm_specialist',  'specialist_model': 'lightgbm',    'mut': 0.08, 'feat': 55},
    'S15': {'url': 'nomos42-nba-evo-6',   'role': 'wide_search',          'specialist_model': None,          'mut': 0.18, 'feat': 80},
}

# Thresholds for auto-intervention
STAGNATION_AUTO_DIVERSIFY = 15   # Auto-send diversify at this level
DIVERSITY_SCORE_THRESHOLD = 0.4  # Fleet diversity score — inject specialist configs below this


# ── API helpers ──────────────────────────────────────────────────────────────

def _post_json(url, payload, timeout=15):
    """Generic POST returning (success, result_dict)."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={'Content-Type': 'application/json', 'User-Agent': 'Nomos42Guardian/1.0'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read())
    except Exception as e:
        return False, {'error': str(e)[:200]}


def post_command(space_url, command):
    url = f'https://{space_url}.hf.space/api/command'
    ok, result = _post_json(url, {'command': command})
    return {'success': ok, 'result': result}


def post_config(space_url, params):
    url = f'https://{space_url}.hf.space/api/config'
    ok, result = _post_json(url, params)
    return {'success': ok, 'result': result}


# ── Fleet analysis from agent-health.json ────────────────────────────────────

def load_fleet_state():
    """Load current island states from agent-health.json."""
    health_file = ROOT / 'data' / 'agent-health.json'
    if not health_file.exists():
        return {}
    try:
        data = json.loads(health_file.read_text())
        return data.get('projects', {}).get('nba', {}).get('spaces', {})
    except Exception:
        return {}


def calc_diversity_score(spaces):
    """Composite diversity: 60% model variety + 40% Brier spread."""
    if not spaces:
        return 0.0
    models = [v.get('model', 'unknown') for v in spaces.values()]
    briers = [v.get('brier') for v in spaces.values() if v.get('brier')]
    model_diversity = len(set(models)) / max(len(models), 1)
    if len(briers) > 1:
        avg = sum(briers) / len(briers)
        std = (sum((b - avg) ** 2 for b in briers) / len(briers)) ** 0.5
        brier_cv = std / avg if avg > 0 else 0
        brier_diversity = min(brier_cv / 0.02, 1.0)
    else:
        brier_diversity = 0.0
    return round(0.6 * model_diversity + 0.4 * brier_diversity, 3)


# ── Auto-intervention logic ───────────────────────────────────────────────────

def auto_stagnation_response(spaces, cycle_interventions):
    """
    If any island stagnation > STAGNATION_AUTO_DIVERSIFY:
        - Send diversify command
        - Boost mutation to max
    Returns list of intervention records.
    """
    interventions = []
    for sid, info in spaces.items():
        stag = info.get('stagnation_cycles', 0)
        if stag > STAGNATION_AUTO_DIVERSIFY:
            island_cfg = ISLANDS.get(sid, {})
            space_url = island_cfg.get('url', '')
            if not space_url:
                continue

            print(f'[guardian] AUTO-DIVERSIFY: {sid} stagnation={stag} (threshold={STAGNATION_AUTO_DIVERSIFY})')

            # Step 1: diversify command
            div_result = post_command(space_url, 'diversify')

            # Step 2: mutation boost
            canonical_feat = island_cfg.get('feat', 60)
            mut_result = post_config(space_url, {
                'mutation_rate': min(island_cfg.get('mut', 0.09) * 1.5, 0.15),
                'target_features': canonical_feat,
            })

            record = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'trigger': 'auto_stagnation',
                'island': sid,
                'space_url': space_url,
                'stagnation_cycles': stag,
                'threshold': STAGNATION_AUTO_DIVERSIFY,
                'actions': {
                    'diversify': div_result,
                    'mutation_boost': mut_result,
                },
                'success': div_result.get('success', False) or mut_result.get('success', False),
            }
            interventions.append(record)
            cycle_interventions.append(record)
            print(f'[guardian]   diversify: {div_result["success"]} | mutation_boost: {mut_result["success"]}')

    return interventions


def auto_diversity_response(spaces, diversity_score, cycle_interventions):
    """
    If diversity_score < DIVERSITY_SCORE_THRESHOLD:
        - Find specialist islands that have drifted from their designated model
        - Inject specialist configs to restore diversity
    Returns list of intervention records.
    """
    interventions = []
    if diversity_score >= DIVERSITY_SCORE_THRESHOLD:
        return interventions

    print(f'[guardian] AUTO-DIVERSITY: score={diversity_score} < threshold={DIVERSITY_SCORE_THRESHOLD}')

    for sid, island_cfg in ISLANDS.items():
        specialist_model = island_cfg.get('specialist_model')
        if specialist_model is None:
            continue  # Non-specialist islands (S10, S11, S15) — skip

        actual_model = spaces.get(sid, {}).get('model', '')
        if actual_model == specialist_model:
            continue  # Already on correct model

        space_url = island_cfg.get('url', '')
        if not space_url:
            continue

        print(f'[guardian]   {sid}: model drift {actual_model} -> {specialist_model} — injecting specialist config')

        # Step 1: diversify to clear drifted population
        div_result = post_command(space_url, 'diversify')

        # Step 2: push specialist model config
        config_result = post_config(space_url, {
            'model_type': specialist_model,
            'mutation_rate': island_cfg.get('mut', 0.09),
            'target_features': island_cfg.get('feat', 60),
        })

        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'trigger': 'auto_diversity',
            'island': sid,
            'space_url': space_url,
            'diversity_score': diversity_score,
            'threshold': DIVERSITY_SCORE_THRESHOLD,
            'model_drift': {'expected': specialist_model, 'actual': actual_model},
            'actions': {
                'diversify': div_result,
                'specialist_config': config_result,
            },
            'success': div_result.get('success', False) or config_result.get('success', False),
        }
        interventions.append(record)
        cycle_interventions.append(record)
        print(f'[guardian]   diversify: {div_result["success"]} | specialist_config: {config_result["success"]}')

    return interventions


def save_interventions(interventions):
    """Append interventions to fleet-actions.json (rotating, keeps last 100)."""
    actions_file = DATA_DIR / 'evolution' / 'fleet-actions.json'
    actions_file.parent.mkdir(parents=True, exist_ok=True)

    existing = []
    if actions_file.exists():
        try:
            data = json.loads(actions_file.read_text())
            # Support both list format (new) and dict format (legacy)
            if isinstance(data, list):
                existing = data
            elif isinstance(data, dict):
                existing = data.get('interventions', [])
        except Exception:
            existing = []

    existing.extend(interventions)
    # Keep last 100 intervention records
    existing = existing[-100:]

    actions_file.write_text(json.dumps({
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'total_recorded': len(existing),
        'interventions': existing,
    }, indent=2))


# ── Department runner ─────────────────────────────────────────────────────────

def run_department(name, config):
    """Run one department's Karpathy loop with 5-min timeout"""
    script = ROOT / 'scripts' / 'departments' / name / config['script']
    start = time.time()
    result = {'department': name, 'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'pending'}

    if not script.exists():
        result['status'] = 'skipped'
        result['reason'] = f'script not found: {script}'
        return result

    try:
        proc = subprocess.run(
            ['bash', str(script)],
            capture_output=True, text=True,
            timeout=config['max_time'],
            cwd=str(ROOT)
        )
        result['status'] = 'completed' if proc.returncode == 0 else 'failed'
        result['returncode'] = proc.returncode
        result['duration_s'] = round(time.time() - start, 1)
        # Try to read metrics from stdout (JSON on last line)
        try:
            result['metrics'] = json.loads(proc.stdout.strip().split('\n')[-1])
        except Exception:
            result['output_tail'] = proc.stdout[-500:] if proc.stdout else ''
        if proc.stderr:
            result['stderr_tail'] = proc.stderr[-300:]
    except subprocess.TimeoutExpired:
        result['status'] = 'timeout'
        result['duration_s'] = config['max_time']
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)

    return result


def cross_pollinate(cycle):
    """Propagate winning metrics/config hints between departments."""
    wins = {}
    for name, result in cycle['departments'].items():
        if result.get('status') == 'completed' and 'metrics' in result:
            m = result['metrics']
            if m.get('improved'):
                wins[name] = m
    cycle['cross_pollination'] = {
        'wins_detected': list(wins.keys()),
        'total_wins': len(wins),
    }
    if wins:
        wins_file = DATA_DIR / 'wins-latest.json'
        wins_file.write_text(json.dumps({'wins': wins, 'ts': datetime.now(timezone.utc).isoformat()}, indent=2))
    return cycle


# ── Cross-department intelligence ─────────────────────────────────────────────

def load_karpathy_outputs() -> dict:
    """Load all department karpathy-output.json files (including trading_floor)."""
    outputs = {}
    all_depts = list(DEPARTMENTS.keys()) + ['trading_floor']
    for dept in all_depts:
        path = DATA_DIR / dept / 'karpathy-output.json'
        if path.exists():
            try:
                outputs[dept] = json.loads(path.read_text())
            except Exception as e:
                outputs[dept] = {'_load_error': str(e)}
        else:
            outputs[dept] = {}
    return outputs


def extract_key_metrics(outputs: dict) -> dict:
    """Pull the most important metrics from each department's output."""
    ev = outputs.get('evaluation', {})
    evo = outputs.get('evolution', {})
    bet = outputs.get('betting', {})
    res = outputs.get('research', {})
    inf = outputs.get('infra', {})

    return {
        'evaluation': {
            'brier': ev.get('brier_score'),
            'ece': (ev.get('calibration_analysis') or {}).get('ece'),
            'fp_rate': ev.get('false_positive_rate'),
            'phantom_games': (ev.get('prediction_distribution') or {}).get('today_phantom_games', 0),
            'bias_detected': ev.get('bias_detected', []),
            'critical_alerts': ev.get('critical_alerts', []),
            'improvements_proposed': ev.get('improvements_proposed', []),
            'status': (ev.get('metrics_summary') or {}).get('status_overall'),
            'roi_pct': (ev.get('performance_trends') or {}).get('roi_pct'),
            'sharpe': (ev.get('performance_trends') or {}).get('sharpe'),
        },
        'evolution': {
            'best_brier': (evo.get('fleet_metrics') or {}).get('best_brier') or evo.get('best_brier'),
            'fleet_avg': (evo.get('fleet_metrics') or {}).get('fleet_avg') or evo.get('fleet_avg_brier'),
            'best_island': (evo.get('fleet_metrics') or {}).get('best_island') or evo.get('best_island'),
            'total_generations': (evo.get('fleet_metrics') or {}).get('total_generations') or evo.get('total_generations'),
            'stagnation_detected': evo.get('stagnation_detected', []),
            'stagnant_count': evo.get('stagnant_count', len(evo.get('stagnation_detected', []))),
            'diversity_score': evo.get('diversity_score'),
            'cross_pollination_candidates': evo.get('cross_pollination_candidates', []),
            'recommendations': evo.get('recommendations', []),
            'model_drift': [r for r in evo.get('recommendations', []) if r.get('type') == 'model_drift'],
        },
        'betting': {
            'bankroll': (bet.get('live_status') or {}).get('bankroll'),
            'roi_pct': (bet.get('live_status') or {}).get('roi_pct'),
            'sharpe': (bet.get('live_status') or {}).get('sharpe'),
            'win_rate_pct': (bet.get('live_status') or {}).get('win_rate_pct'),
            'health': (bet.get('live_status') or {}).get('health'),
            'eliminated_strategies': bet.get('eliminated_strategies', []),
            'strategy_rankings': bet.get('strategy_rankings', []),
        },
        'research': {
            'papers_scanned': res.get('papers_scanned', 0),
            'techniques_extracted': res.get('techniques_extracted', 0),
            'proposals_generated': res.get('proposals_generated', 0),
            'sota_reference': res.get('sota_reference'),
            'gap_to_close': res.get('gap_to_close'),
        },
        'infra': {
            'spaces_up': inf.get('spaces_up'),
            'spaces_total': inf.get('spaces_total', 6),
            'restart_count': inf.get('restart_count', 0),
            'uptime_pct': inf.get('uptime_pct'),
            'spaces_down': inf.get('spaces_down', []),
        },
        'political': {
            'brier': outputs.get('political', {}).get('political_brier'),
            'etf_roi': outputs.get('political', {}).get('etf_roi'),
            'signal_accuracy': outputs.get('political', {}).get('signal_accuracy'),
        },
        'creative': {
            'quality_score': outputs.get('creative', {}).get('quality_score'),
            'pieces_today': outputs.get('creative', {}).get('pieces_today', 0),
        },
        'trading_floor': {
            'best_strategy': outputs.get('trading_floor', {}).get('best_strategy', {}),
            'best_model': outputs.get('trading_floor', {}).get('best_model', {}),
            'best_category': outputs.get('trading_floor', {}).get('best_category', {}),
            'iteration': outputs.get('trading_floor', {}).get('iteration'),
            'new_eliminations': outputs.get('trading_floor', {}).get('new_eliminations', []),
            'mutations': outputs.get('trading_floor', {}).get('mutations', {}),
            'leaderboard': outputs.get('trading_floor', {}).get('leaderboard', []),
            'recommendations': outputs.get('trading_floor', {}).get('recommendations', []),
        },
    }


def detect_cross_department_issues(metrics: dict) -> list:
    """Detect issues that span department boundaries."""
    issues = []
    ts = datetime.now(timezone.utc).isoformat()
    ev = metrics.get('evaluation', {})
    evo = metrics.get('evolution', {})
    bet = metrics.get('betting', {})

    # Evaluation → Engineering: phantom games
    phantom_count = ev.get('phantom_games') or 0
    if phantom_count > 0:
        issues.append({
            'severity': 'CRITICAL',
            'source_dept': 'evaluation',
            'target_dept': 'engineering',
            'issue_type': 'PHANTOM_GAME',
            'description': f'{phantom_count} phantom game(s) detected (home==away) in today predictions',
            'recommended_action': 'Add assert game["home"] != game["away"] in predict_today.py',
            'auto_flag': True,
            'detected_at': ts,
        })

    # Evaluation → Engineering: calibration crisis
    ece = ev.get('ece') or 0.0
    if ece > 0.15:
        issues.append({
            'severity': 'CRITICAL',
            'source_dept': 'evaluation',
            'target_dept': 'engineering',
            'issue_type': 'CALIBRATION_CRISIS',
            'description': f'ECE={ece:.4f} — target <0.05, currently {ece/0.05:.1f}x over. Worst bucket: 60-70%',
            'recommended_action': 'Deploy Platt scaling / isotonic regression post-hoc calibration on HF Space',
            'auto_flag': True,
            'detected_at': ts,
        })

    # Evaluation → Engineering: corrupted odds / bias
    for bias in ev.get('bias_detected', []):
        btype = bias.get('type', 'UNKNOWN')
        bsev = bias.get('severity', 'MEDIUM')
        if bsev in ('CRITICAL', 'HIGH'):
            issues.append({
                'severity': bsev,
                'source_dept': 'evaluation',
                'target_dept': 'engineering',
                'issue_type': f'BIAS_{btype}',
                'description': bias.get('description') or f'{btype} bias detected in model outputs',
                'recommended_action': bias.get('fix', 'Investigate and fix in engineering pipeline'),
                'auto_flag': False,
                'detected_at': ts,
            })

    # Evolution → Infra: stagnation (already handled by auto-intervention above,
    # but also record as cross-dept issue for the report)
    for stag in evo.get('stagnation_detected', []):
        cycles = stag.get('stagnation_cycles', 0) or 0
        island = stag.get('island', '?')
        sev = 'CRITICAL' if cycles >= 15 else 'HIGH'
        issues.append({
            'severity': sev,
            'source_dept': 'evolution',
            'target_dept': 'infra',
            'issue_type': 'SPACE_STAGNATION',
            'description': f'{island} stagnant for {cycles} cycles (Brier={stag.get("brier")})',
            'recommended_action': f'POST /api/config {{"command":"diversify"}} → {island}',
            'auto_flag': True,
            'island': island,
            'cycles': cycles,
            'detected_at': ts,
        })

    # Evolution: model drift
    for drift in evo.get('model_drift', []):
        island = drift.get('island', '?')
        issues.append({
            'severity': 'MEDIUM',
            'source_dept': 'evolution',
            'target_dept': 'evolution',
            'issue_type': 'MODEL_DRIFT',
            'description': f'{island} specialist drift: expected {drift.get("expected_model")}, got {drift.get("actual_model")}',
            'recommended_action': f'Restore {island} specialist config to enforce {drift.get("expected_model")}',
            'auto_flag': False,
            'detected_at': ts,
        })

    # Evolution: low fleet diversity
    diversity = evo.get('diversity_score')
    if diversity is not None and diversity < 0.5:
        issues.append({
            'severity': 'MEDIUM',
            'source_dept': 'evolution',
            'target_dept': 'evolution',
            'issue_type': 'LOW_DIVERSITY',
            'description': f'Fleet diversity={diversity:.3f} < 0.50 — RF monoculture risk',
            'recommended_action': 'Force S12→extra_trees, S14→lightgbm specialist configs',
            'auto_flag': False,
            'detected_at': ts,
        })

    # Betting → Evaluation: negative ROI
    roi = bet.get('roi_pct')
    if roi is not None and roi < 0:
        issues.append({
            'severity': 'HIGH',
            'source_dept': 'betting',
            'target_dept': 'evaluation',
            'issue_type': 'NEGATIVE_ROI',
            'description': f'ROI={roi:.1f}% (target >5%) — calibration issues likely driver',
            'recommended_action': 'Prioritize ECE fix; pause full_kelly until ECE < 0.10',
            'auto_flag': False,
            'detected_at': ts,
        })

    # Trading Floor → Betting + Evolution: best strategy/model discoveries
    tf = metrics.get('trading_floor', {})
    tf_recs = tf.get('recommendations', [])
    for rec in tf_recs:
        target = rec.get('target_dept', 'betting')
        issues.append({
            'severity': 'MEDIUM',
            'source_dept': 'trading_floor',
            'target_dept': target,
            'issue_type': rec.get('type', 'TRADING_FLOOR_REC'),
            'description': rec.get('reason', ''),
            'recommended_action': rec.get('reason', ''),
            'auto_flag': False,
            'detected_at': ts,
        })

    # Trading Floor → Betting: new eliminations
    for elim in tf.get('new_eliminations', []):
        issues.append({
            'severity': 'HIGH',
            'source_dept': 'trading_floor',
            'target_dept': 'betting',
            'issue_type': 'STRATEGY_AUTO_ELIMINATED',
            'description': f"Strategy '{elim.get('strategy', '?')}' auto-eliminated: {elim.get('reason', '')}",
            'recommended_action': f"Remove '{elim.get('strategy', '?')}' from live betting agent preferred strategies",
            'auto_flag': True,
            'detected_at': ts,
        })

    return issues


def generate_priority_queue(metrics: dict, issues: list) -> list:
    """Build priority-ordered action queue from cross-dept findings + proposals."""
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
    queue = []

    # From cross-dept issues
    for issue in issues:
        queue.append({
            'priority': issue['severity'],
            'action': issue['recommended_action'],
            'dept': issue['target_dept'],
            'source': issue['source_dept'],
            'issue_type': issue['issue_type'],
            'description': issue['description'],
        })

    # From evaluation improvements_proposed
    for prop in metrics.get('evaluation', {}).get('improvements_proposed', []):
        pnum = prop.get('priority', 99)
        prio = 'CRITICAL' if pnum <= 1 else ('HIGH' if pnum <= 3 else 'MEDIUM')
        queue.append({
            'priority': prio,
            'action': prop.get('action', prop.get('title', '')),
            'dept': prop.get('department', 'engineering').lower().replace('d5/', '').replace('d2/', ''),
            'source': 'evaluation',
            'issue_type': prop.get('type', 'improvement'),
            'description': prop.get('title', ''),
        })

    # From evolution recommendations
    for rec in metrics.get('evolution', {}).get('recommendations', []):
        rp = rec.get('priority', 3)
        prio = 'CRITICAL' if rp == 1 else ('HIGH' if rp == 2 else 'MEDIUM')
        queue.append({
            'priority': prio,
            'action': rec.get('command', rec.get('action', '')),
            'dept': 'evolution',
            'source': 'evolution',
            'issue_type': rec.get('type', 'evolution'),
            'description': rec.get('reason', ''),
        })

    # Deduplicate by (dept, issue_type, action prefix)
    seen, deduped = set(), []
    for item in queue:
        key = (item['dept'], item['issue_type'], item['action'][:60])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    deduped.sort(key=lambda x: priority_order.get(x['priority'], 3))
    return deduped


# ── Elimination tracking ───────────────────────────────────────────────────────

def update_eliminations(outputs: dict, iteration: int) -> dict:
    """Track eliminated strategies, agents, features across iterations."""
    existing = {}
    if ELIMINATIONS_FILE.exists():
        try:
            existing = json.loads(ELIMINATIONS_FILE.read_text())
        except Exception:
            existing = {}

    elim_strategies = existing.get('strategies', {})
    coffins = existing.get('coffins', [])

    bet = outputs.get('betting', {})
    rankings = bet.get('strategy_rankings', [])
    new_elim = bet.get('eliminated_strategies', [])

    # Mark strategies ranked with weak/eliminated verdict
    for entry in rankings:
        strat = entry.get('strategy', '')
        verdict = entry.get('verdict', '')
        if verdict in ('ELIMINATED', 'WEAK', 'FAILING') and strat and strat not in elim_strategies:
            elim_strategies[strat] = {
                'eliminated_at_iteration': iteration,
                'reason': f'verdict={verdict}',
                'avg_roi_pct': entry.get('avg_roi_pct'),
                'eliminated_at': datetime.now(timezone.utc).isoformat(),
            }
            coffins.append({
                'type': 'strategy',
                'name': strat,
                'iteration': iteration,
                'cause_of_death': verdict,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })

    # Explicit eliminations list from betting output
    for item in new_elim:
        name = item if isinstance(item, str) else item.get('strategy', str(item))
        if name and name not in elim_strategies:
            elim_strategies[name] = {
                'eliminated_at_iteration': iteration,
                'reason': 'betting_loop_elimination',
                'eliminated_at': datetime.now(timezone.utc).isoformat(),
            }
            coffins.append({
                'type': 'strategy',
                'name': name,
                'iteration': iteration,
                'cause_of_death': 'betting_loop_elimination',
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })

    result = {
        'strategies': elim_strategies,
        'iteration': iteration,
        'coffins': coffins,
        'total_eliminated': len(elim_strategies),
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }
    ELIMINATIONS_FILE.write_text(json.dumps(result, indent=2))
    return result


# ── Enhanced cross-pollination ─────────────────────────────────────────────────

def cross_pollinate_enhanced(outputs: dict, metrics: dict) -> dict:
    """Enhanced cross-pollination: detect wins and write actionable recommendations."""
    wins = {}
    recs = []

    # Evolution wins
    for cand in metrics.get('evolution', {}).get('cross_pollination_candidates', []):
        recs.append({
            'from': f"evolution/{cand.get('source')}",
            'to': f"evolution/{cand.get('target')}",
            'action': f"Seed {cand.get('target')} with {cand.get('source')} config "
                      f"(potential Brier gain: {cand.get('potential_gain', 0):.5f})",
        })

    # Research → Engineering
    res = metrics.get('research', {})
    if res.get('techniques_extracted', 0) > 0:
        wins['research'] = {
            'techniques': res['techniques_extracted'],
            'papers': res.get('papers_scanned'),
        }
        recs.append({
            'from': 'research',
            'to': 'engineering',
            'action': f"Apply {res['techniques_extracted']} extracted techniques "
                      f"from {res.get('papers_scanned', 0)} papers",
        })

    # Trading Floor → Betting + Evolution
    tf = metrics.get('trading_floor', {})
    tf_best_strat = tf.get('best_strategy', {})
    tf_best_model = tf.get('best_model', {})
    if tf_best_strat.get('roi_pct', 0) > 5:
        wins['trading_floor'] = {
            'best_strategy': tf_best_strat.get('name'),
            'roi_pct': tf_best_strat.get('roi_pct'),
        }
        recs.append({
            'from': 'trading_floor',
            'to': 'betting',
            'action': f"Promote strategy '{tf_best_strat.get('name')}' to live "
                      f"({tf_best_strat.get('roi_pct', 0):+.1f}% ROI from full-season backtest)",
        })
    if tf_best_model.get('avg_daily_profit', 0) > 0.3:
        recs.append({
            'from': 'trading_floor',
            'to': 'evolution',
            'action': f"Prioritize model '{tf_best_model.get('name')}' in evolution "
                      f"(avg daily profit {tf_best_model.get('avg_daily_profit', 0):+.4f})",
        })

    # Evaluation → Betting: calibration status
    ev = metrics.get('evaluation', {})
    if ev.get('brier') and ev['brier'] < 0.222:
        wins['evaluation'] = {'brier': ev['brier']}

    wins_file = DATA_DIR / 'wins-latest.json'
    wins_file.write_text(json.dumps({
        'wins': wins,
        'recommendations': recs,
        'ts': datetime.now(timezone.utc).isoformat(),
    }, indent=2))

    return {
        'wins_detected': list(wins.keys()),
        'total_wins': len(wins),
        'cross_pollination_recommendations': recs,
    }


# ── Health score ───────────────────────────────────────────────────────────────

def compute_health_score(metrics: dict, issues: list) -> int:
    """Compute overall system health 0-100."""
    score = 100
    score -= sum(15 for i in issues if i.get('severity') == 'CRITICAL')
    score -= sum(7  for i in issues if i.get('severity') == 'HIGH')
    score -= sum(2  for i in issues if i.get('severity') == 'MEDIUM')

    ev = metrics.get('evaluation', {})
    brier = ev.get('brier')
    if brier:
        score -= int(max(0, brier - 0.20) * 300)

    roi = ev.get('roi_pct')
    if roi is not None and roi < 0:
        score -= min(20, int(abs(roi) * 2))

    evo = metrics.get('evolution', {})
    diversity = evo.get('diversity_score')
    if diversity is not None and diversity >= 0.6:
        score += 5

    inf = metrics.get('infra', {})
    spaces_up = inf.get('spaces_up')
    spaces_total = inf.get('spaces_total') or 6
    if spaces_up is not None:
        score -= max(0, spaces_total - spaces_up) * 5

    return max(0, min(100, score))


# ── Per-department summaries ───────────────────────────────────────────────────

def build_dept_summaries(metrics: dict, dept_results: dict) -> dict:
    ev = metrics.get('evaluation', {})
    evo = metrics.get('evolution', {})
    bet = metrics.get('betting', {})
    res = metrics.get('research', {})
    inf = metrics.get('infra', {})

    brier = ev.get('brier')
    ece = ev.get('ece')

    return {
        'evaluation': (
            f"Brier={brier} | ECE={ece:.4f} | FP={ev.get('fp_rate')} | "
            f"ROI={ev.get('roi_pct')}% | phantom={ev.get('phantom_games',0)}"
        ) if brier else "No evaluation data",

        'evolution': (
            f"Best={evo.get('best_brier')} ({evo.get('best_island')}) | "
            f"Avg={evo.get('fleet_avg')} | Gen={evo.get('total_generations')} | "
            f"Stagnant={evo.get('stagnant_count',0)}"
        ) if evo.get('best_brier') else "No evolution data",

        'betting': (
            f"${bet.get('bankroll')} | ROI={bet.get('roi_pct')}% | "
            f"Sharpe={bet.get('sharpe')} | WR={bet.get('win_rate_pct')}% | {bet.get('health','?')}"
        ) if bet.get('bankroll') else "No betting data",

        'research': (
            f"{res.get('papers_scanned',0)} papers | "
            f"{res.get('techniques_extracted',0)} techniques | "
            f"gap={res.get('gap_to_close')} ({res.get('sota_reference','')})"
        ),

        'infra': (
            f"Spaces {inf.get('spaces_up',0)}/{inf.get('spaces_total',6)} UP | "
            f"restarts={inf.get('restart_count',0)}"
        ),

        'political': (
            f"Brier={metrics['political'].get('brier')} | "
            f"ETF ROI={metrics['political'].get('etf_roi')} | "
            f"accuracy={metrics['political'].get('signal_accuracy')}"
        ),

        'creative': (
            f"quality={metrics['creative'].get('quality_score')} | "
            f"pieces={metrics['creative'].get('pieces_today',0)}"
        ),

        'engineering': (
            lambda m: (
                f"Brier delta={m.get('brier_delta',0)} | "
                f"features added={m.get('features_added',0)} | "
                f"pass rate={m.get('test_pass_rate')}"
            )
        )(dept_results.get('engineering', {}).get('metrics', {})),

        'trading_floor': (
            lambda tf: (
                f"iter={tf.get('iteration','?')} | "
                f"best_strat={tf.get('best_strategy',{}).get('name','?')} "
                f"({tf.get('best_strategy',{}).get('roi_pct',0):+.1f}%) | "
                f"best_model={tf.get('best_model',{}).get('name','?')} | "
                f"elim={len(tf.get('new_eliminations',[]))} | "
                f"mutations={len(tf.get('mutations',{}))}"
            )
        )(metrics.get('trading_floor', {})),
    }


# ── Telegram notification ──────────────────────────────────────────────────────

def _tg_request(method: str, data: dict) -> dict:
    if not TELEGRAM_BOT_TOKEN:
        return {'ok': False, 'reason': 'no token'}
    url = f"{TG_API}/{method}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def send_telegram_report(report: dict) -> bool:
    """Format and send compact guardian report to @Nomos42."""
    if not TELEGRAM_BOT_TOKEN:
        print('[guardian] Telegram skipped: TELEGRAM_BOT_TOKEN not set')
        return False

    health = report.get('health_score', 0)
    icon = '\U0001f7e2' if health >= 80 else ('\U0001f7e1' if health >= 60 else '\U0001f534')
    ts = report.get('timestamp', '')[:16].replace('T', ' ')
    iteration = report.get('iteration', '?')

    lines = [
        f"<b>\U0001f6e1 Guardian #{iteration}</b>  {icon} {health}/100",
        f"<i>{ts} UTC</i>",
        "",
    ]

    alerts = report.get('critical_alerts', [])
    if alerts:
        lines.append("<b>\U0001f6a8 Critical</b>")
        for a in alerts[:4]:
            lines.append(f"  \u2022 [{a.get('issue_type','?')}] {a.get('description','')[:75]}")
        lines.append("")

    lines.append("<b>\U0001f4ca Departments</b>")
    label_map = {
        'evaluation': 'D5', 'evolution': 'D3', 'betting': 'D4',
        'research': 'D1', 'infra': 'D6', 'engineering': 'D2',
        'political': 'D7', 'creative': 'D8',
    }
    for dept, label in label_map.items():
        s = report.get('dept_summaries', {}).get(dept, 'no data')
        lines.append(f"  <b>{label}</b> {s[:85]}")
    lines.append("")

    cp = report.get('cross_pollination', {})
    wins = cp.get('wins_detected', [])
    if wins:
        lines.append(f"\U0001f31f Cross-pollination: {', '.join(wins)}")
        lines.append("")

    coffins = report.get('eliminations', {}).get('coffins', [])
    if coffins:
        lines.append(f"\u26b0 Eliminated: {len(coffins)} total")
        for c in coffins[-3:]:
            lines.append(f"  \u2620 {c.get('name')} \u2014 {c.get('cause_of_death')}")
        lines.append("")

    recs = report.get('priority_queue', [])[:3]
    if recs:
        lines.append("<b>\u27a1 Top Actions</b>")
        for r in recs:
            lines.append(f"  [{r.get('priority','?')}] {r.get('action','')[:65]}")

    text = "\n".join(lines)
    if len(text) > MAX_MSG_LEN:
        text = text[:MAX_MSG_LEN - 20] + "\n...(truncated)"

    result = _tg_request("sendMessage", {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
    })
    ok = result.get('ok', False)
    if ok:
        print(f'[guardian] Telegram report sent to {TELEGRAM_CHANNEL_ID}')
    else:
        print(f'[guardian] Telegram send failed: {result}')
    return ok


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now(timezone.utc)

    # ── Phase 1: PRE-RUN fleet health + auto-intervention ──────────────────────
    spaces = load_fleet_state()
    diversity_score = calc_diversity_score(spaces)
    print(f'[guardian] Fleet diversity score: {diversity_score} (threshold={DIVERSITY_SCORE_THRESHOLD})')

    cycle_interventions = []
    stag_interventions = auto_stagnation_response(spaces, cycle_interventions)
    diversity_interventions = auto_diversity_response(spaces, diversity_score, cycle_interventions)
    all_new_interventions = stag_interventions + diversity_interventions

    if all_new_interventions:
        save_interventions(all_new_interventions)
        print(f'[guardian] Fleet interventions: {len(stag_interventions)} stagnation, '
              f'{len(diversity_interventions)} diversity — logged to fleet-actions.json')
    else:
        print('[guardian] Fleet: no interventions needed')

    # ── Phase 2: Department loops ───────────────────────────────────────────────
    dept_results = {}
    for name, config in DEPARTMENTS.items():
        print(f'[guardian] Running {name}...')
        result = run_department(name, config)
        dept_results[name] = result
        print(f'[guardian] {name}: {result["status"]} ({result.get("duration_s", 0):.1f}s)')

    # ── Phase 3: Cross-department intelligence ──────────────────────────────────
    print('[guardian] Cross-department analysis...')
    karpathy_outputs = load_karpathy_outputs()
    metrics = extract_key_metrics(karpathy_outputs)
    issues = detect_cross_department_issues(metrics)
    priority_queue = generate_priority_queue(metrics, issues)
    print(f'[guardian] {len(issues)} cross-dept issues | {len(priority_queue)} priority actions')

    # ── Phase 4: Elimination tracking ──────────────────────────────────────────
    iteration = karpathy_outputs.get('betting', {}).get('iteration', 1)
    eliminations = update_eliminations(karpathy_outputs, iteration)

    # ── Phase 5: Enhanced cross-pollination ────────────────────────────────────
    # Basic win detection from dept loop outputs (backward compat)
    simple_cp_wins = {}
    for name, result in dept_results.items():
        if result.get('status') == 'completed' and result.get('metrics', {}).get('improved'):
            simple_cp_wins[name] = result['metrics']
    if simple_cp_wins:
        (DATA_DIR / 'wins-latest.json').write_text(
            json.dumps({'wins': simple_cp_wins, 'ts': start_time.isoformat()}, indent=2)
        )

    cross_poll = cross_pollinate_enhanced(karpathy_outputs, metrics)

    # ── Phase 6: Health + summaries ─────────────────────────────────────────────
    dept_summaries = build_dept_summaries(metrics, dept_results)
    health_score = compute_health_score(metrics, issues)

    # ── Phase 7: Run summary ────────────────────────────────────────────────────
    run_summary = {
        'total': len(DEPARTMENTS),
        'completed': sum(1 for d in dept_results.values() if d['status'] == 'completed'),
        'failed': sum(1 for d in dept_results.values() if d['status'] == 'failed'),
        'timeout': sum(1 for d in dept_results.values() if d['status'] == 'timeout'),
        'skipped': sum(1 for d in dept_results.values() if d['status'] == 'skipped'),
        'total_duration_s': round(sum(d.get('duration_s', 0) for d in dept_results.values()), 1),
        'fleet_interventions': len(all_new_interventions),
        'fleet_diversity_score': diversity_score,
    }
    end_time = datetime.now(timezone.utc)

    # ── Phase 8: Assemble consolidated guardian report ──────────────────────────
    report = {
        'timestamp': end_time.isoformat(),
        'iteration': iteration,
        'cycle_start': start_time.isoformat(),
        'cycle_end': end_time.isoformat(),
        'health_score': health_score,
        'run_summary': run_summary,
        'dept_summaries': dept_summaries,
        'critical_alerts': [i for i in issues if i.get('severity') == 'CRITICAL'],
        'all_issues': issues,
        'priority_queue': priority_queue,
        'cross_pollination': cross_poll,
        'eliminations': {
            'strategies': eliminations.get('strategies', {}),
            'total_eliminated': eliminations.get('total_eliminated', 0),
            'coffins': eliminations.get('coffins', []),
        },
        'fleet_interventions': all_new_interventions,
        'raw_metrics': metrics,
    }

    GUARDIAN_REPORT.write_text(json.dumps(report, indent=2))
    print(f'[guardian] Report written → {GUARDIAN_REPORT}')

    # ── Backward-compat guardian-status.json ────────────────────────────────────
    status_file = DATA_DIR / 'guardian-status.json'
    status_file.write_text(json.dumps({
        'cycle_start': start_time.isoformat(),
        'cycle_end': end_time.isoformat(),
        'departments': dept_results,
        'summary': run_summary,
        'cross_pollination': cross_poll,
        'health_score': health_score,
    }, indent=2))

    # ── Phase 9: Telegram broadcast ─────────────────────────────────────────────
    send_telegram_report(report)

    # Compact stdout for cron log / upstream consumers
    compact = {
        'health_score': health_score,
        'iteration': iteration,
        'critical_count': len([i for i in issues if i['severity'] == 'CRITICAL']),
        'high_count': len([i for i in issues if i['severity'] == 'HIGH']),
        'fleet_interventions': len(all_new_interventions),
        'best_brier': metrics.get('evolution', {}).get('best_brier'),
        'roi_pct': metrics.get('evaluation', {}).get('roi_pct'),
        **run_summary,
    }
    print(json.dumps(compact))
    return report


if __name__ == '__main__':
    main()
