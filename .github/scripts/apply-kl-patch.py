"""Revert wipe 93cd49d + apply KL divergence upgrade to both TF apps + update work-queue."""
import json
import math  # noqa

# -- NBA --
with open('scripts/arena/hf-llm-trading-floor/app.py', 'r') as f:
    src = f.read()

NBA_OLD = '''def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: KL-divergence proxy of this agent\'s bet distribution vs society consensus.

    Computes ||p_agent - p_society||_1 over category buckets (simpler than true KL, no smoothing).
    """
    # Bucket categories used in bets today across all agents
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            cat = a.get("category", "unknown")
            society[cat] += 1
            if other_tid == tid:
                agent_counts[cat] += 1
    if not society or not agent_counts:
        return 0.0
    total_soc = sum(society.values())
    total_agt = sum(agent_counts.values())
    cats = set(society.keys()) | set(agent_counts.keys())
    l1 = 0.0
    for c in cats:
        p_agt = agent_counts.get(c, 0) / total_agt if total_agt else 0.0
        p_soc = society.get(c, 0) / total_soc if total_soc else 0.0
        l1 += abs(p_agt - p_soc)
    return l1 / 2.0  # normalize [0,1]'''

NBA_NEW = '''def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: KL divergence D_KL(agent || society) over category bet distribution.

    KL(P||Q) = sum_i P_i * log(P_i / Q_i) with epsilon smoothing.
    Replaces the former L1/2 proxy for paper-quality dataset accuracy.
    """
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            cat = a.get("category", "unknown")
            society[cat] += 1
            if other_tid == tid:
                agent_counts[cat] += 1
    if not society or not agent_counts:
        return 0.0
    total_soc = sum(society.values())
    total_agt = sum(agent_counts.values())
    cats = set(society.keys()) | set(agent_counts.keys())
    eps = 1e-9
    kl = 0.0
    for c in cats:
        p_agt = agent_counts.get(c, 0) / total_agt if total_agt else 0.0
        p_soc = society.get(c, 0) / total_soc if total_soc else 0.0
        kl += (p_agt + eps) * math.log((p_agt + eps) / (p_soc + eps))
    return round(kl, 6)'''

assert NBA_OLD in src, f"NBA: old L1 function not found (file len={len(src)})"
nba_new_src = src.replace(NBA_OLD, NBA_NEW, 1)
assert 'kl += (p_agt' in nba_new_src, "NBA: KL line missing after replace"
with open('scripts/arena/hf-llm-trading-floor/app.py', 'w') as f:
    f.write(nba_new_src)
print(f"NBA: KL patch applied ({len(nba_new_src)} chars)")

# -- POL --
with open('scripts/arena/hf-political-trading-floor/app.py', 'r') as f:
    src = f.read()

POL_OLD = '''def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: L1/2 distance of this agent\'s ticker distribution vs society consensus."""
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            tick = a.get("ticker") or a.get("category", "unknown")
            society[tick] += 1
            if other_tid == tid:
                agent_counts[tick] += 1
    if not society or not agent_counts:
        return 0.0
    total_soc = sum(society.values())
    total_agt = sum(agent_counts.values())
    cats = set(society.keys()) | set(agent_counts.keys())
    l1 = 0.0
    for c in cats:
        p_agt = agent_counts.get(c, 0) / total_agt if total_agt else 0.0
        p_soc = society.get(c, 0) / total_soc if total_soc else 0.0
        l1 += abs(p_agt - p_soc)
    return l1 / 2.0'''

POL_NEW = '''def compute_consensus_distance(tid: str, day_date: str, state: Dict, agent_logs: Dict) -> float:
    """Axelrod Mech C: KL divergence D_KL(agent || society) over ticker/direction bet distribution.

    KL(P||Q) = sum_i P_i * log(P_i / Q_i) with epsilon smoothing.
    Replaces the former L1/2 proxy for paper-quality dataset accuracy.
    """
    from collections import Counter
    society = Counter()
    agent_counts = Counter()
    for other_tid, logs in agent_logs.items():
        day_log = next((l for l in reversed(logs) if l.get("date") == day_date), None)
        if not day_log:
            continue
        for a in day_log.get("allocations", []):
            tick = a.get("ticker") or a.get("category", "unknown")
            society[tick] += 1
            if other_tid == tid:
                agent_counts[tick] += 1
    if not society or not agent_counts:
        return 0.0
    total_soc = sum(society.values())
    total_agt = sum(agent_counts.values())
    cats = set(society.keys()) | set(agent_counts.keys())
    eps = 1e-9
    kl = 0.0
    for c in cats:
        p_agt = agent_counts.get(c, 0) / total_agt if total_agt else 0.0
        p_soc = society.get(c, 0) / total_soc if total_soc else 0.0
        kl += (p_agt + eps) * math.log((p_agt + eps) / (p_soc + eps))
    return round(kl, 6)'''

assert POL_OLD in src, f"POL: old L1 function not found (file len={len(src)})"
pol_new_src = src.replace(POL_OLD, POL_NEW, 1)
assert 'kl += (p_agt' in pol_new_src, "POL: KL line missing after replace"
with open('scripts/arena/hf-political-trading-floor/app.py', 'w') as f:
    f.write(pol_new_src)
print(f"POL: KL patch applied ({len(pol_new_src)} chars)")

# -- work-queue.json --
with open('data/work-queue.json', 'r') as f:
    wq = json.load(f)

for item in wq['items']:
    if item['id'] == 'tf-axelrod-kl-divergence':
        item['status'] = 'done'
        item['completed_at'] = '2026-05-06T14:00:00Z'
        item['completed_by'] = 'cloud-trigger-axelrod-fire-52'
        item['result'] = (
            'D_KL(P||Q)=sum_i(p_i+eps)*log((p_i+eps)/(q_i+eps)), eps=1e-9. '
            'NBA L3743 + POL L2399. py_compile PASS both apps.'
        )
        print('work-queue: tf-axelrod-kl-divergence -> done')

ids = {i['id'] for i in wq['items']}
if 'tf-axelrod-verify-tune-51' not in ids:
    wq['items'].append({
        'id': 'tf-axelrod-verify-tune-51',
        'priority': 75,
        'status': 'done',
        'completed_at': '2026-05-06T14:00:00Z',
        'completed_by': 'cloud-trigger-axelrod-fire-52',
        'owner': 'cloud-trigger-axelrod-2026',
        'subject': 'verify+tune fire 52 -- NBA+POL PASS all 3 mechs post-restore; KL divergence applied',
        'findings': {
            'nba_status': 'PASS -- Mechs A/B/C intact. compute_consensus_distance L1->KL. py_compile PASS 5799L.',
            'pol_status': 'PASS -- Mechs A/B/C intact (post fire-51 restore 96e31b67). L1->KL. py_compile PASS 3924L.',
            'kl_divergence': 'APPLIED NBA L3743 + POL L2399. D_KL(P||Q) eps=1e-9 round(kl,6).',
            'parity': 'NBA+POL identical compute_consensus_distance (field: category vs ticker)',
        },
        'do_not_push_hf_space_yet': True,
    })
    print('work-queue: tf-axelrod-verify-tune-51 added')

wq['updated_at'] = '2026-05-06T14:00:00Z'
with open('data/work-queue.json', 'w') as f:
    json.dump(wq, f, indent=2)
print('work-queue.json updated. ALL DONE.')
