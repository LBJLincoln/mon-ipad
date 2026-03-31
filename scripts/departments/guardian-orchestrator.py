#!/usr/bin/env python3
"""Guardian Orchestrator — runs all department Karpathy loops"""
import subprocess, json, time, os
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
}

ROOT = Path('/home/termius/mon-ipad')
DATA_DIR = ROOT / 'data' / 'departments'


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
            # Capture any improvement signals
            if m.get('improved'):
                wins[name] = m
    cycle['cross_pollination'] = {
        'wins_detected': list(wins.keys()),
        'total_wins': len(wins),
    }
    # Write wins file for downstream loops to read
    if wins:
        wins_file = DATA_DIR / 'wins-latest.json'
        wins_file.write_text(json.dumps({'wins': wins, 'ts': datetime.now(timezone.utc).isoformat()}, indent=2))
    return cycle


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    cycle = {
        'cycle_start': datetime.now(timezone.utc).isoformat(),
        'departments': {},
        'summary': {}
    }

    for name, config in DEPARTMENTS.items():
        print(f'[guardian] Running {name}...')
        result = run_department(name, config)
        cycle['departments'][name] = result
        print(f'[guardian] {name}: {result["status"]} ({result.get("duration_s", 0)}s)')

    # Cross-pollinate wins
    cycle = cross_pollinate(cycle)

    # Summary
    cycle['summary'] = {
        'total': len(DEPARTMENTS),
        'completed': sum(1 for d in cycle['departments'].values() if d['status'] == 'completed'),
        'failed': sum(1 for d in cycle['departments'].values() if d['status'] == 'failed'),
        'timeout': sum(1 for d in cycle['departments'].values() if d['status'] == 'timeout'),
        'skipped': sum(1 for d in cycle['departments'].values() if d['status'] == 'skipped'),
        'total_duration_s': sum(d.get('duration_s', 0) for d in cycle['departments'].values()),
    }
    cycle['cycle_end'] = datetime.now(timezone.utc).isoformat()

    # Write status
    status_file = DATA_DIR / 'guardian-status.json'
    status_file.write_text(json.dumps(cycle, indent=2))
    print(json.dumps(cycle['summary']))


if __name__ == '__main__':
    main()
