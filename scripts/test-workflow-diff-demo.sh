#!/bin/bash
# Demo script for workflow-diff-engine.py
# Shows all main use cases

echo "=========================================="
echo "WORKFLOW DIFF ENGINE - DEMO"
echo "=========================================="
echo

echo "1. Check single pipeline on single space (fast)"
echo "--------------------------------------------------"
python3 scripts/workflow-diff-engine.py \
  --space https://lbjlincoln-nomos-rag-engine.hf.space \
  --pipeline standard
echo

echo "2. Check all pipelines on single space"
echo "--------------------------------------------------"
python3 scripts/workflow-diff-engine.py \
  --space https://lbjlincoln-nomos-rag-engine.hf.space
echo

echo "3. Check single pipeline across ALL spaces (parallel)"
echo "--------------------------------------------------"
python3 scripts/workflow-diff-engine.py --pipeline graph
echo

echo "4. Dry-run: Show what would be reverted"
echo "--------------------------------------------------"
python3 scripts/workflow-diff-engine.py \
  --pipeline quantitative \
  --dry-run
echo

echo "5. View detailed JSON report"
echo "--------------------------------------------------"
LATEST_REPORT=$(ls -t /home/termius/mon-ipad/logs/workflow-diff-*.json | head -1)
echo "Latest report: $LATEST_REPORT"
echo
echo "Summary:"
python3 << EOPYTHON
import json
with open("$LATEST_REPORT") as f:
    data = json.load(f)
    print(f"Timestamp: {data['timestamp']}")
    print(f"Spaces checked: {data['total_spaces']}")
    print(f"Results: {len(data['results'])} spaces")
    
    # Count pipelines
    pipelines = {}
    for r in data['results']:
        for p, pdata in r.get('workflows', {}).items():
            if p not in pipelines:
                pipelines[p] = {'clean': 0, 'diffs': 0}
            if sum(pdata.get('severity_counts', {}).values()) == 0:
                pipelines[p]['clean'] += 1
            else:
                pipelines[p]['diffs'] += 1
    
    print("\nPipeline status:")
    for p, counts in sorted(pipelines.items()):
        total = counts['clean'] + counts['diffs']
        print(f"  {p}: {counts['clean']}/{total} spaces clean")
EOPYTHON

echo
echo "=========================================="
echo "DEMO COMPLETE"
echo "=========================================="
echo
echo "Next steps:"
echo "  - Review analysis: cat /home/termius/mon-ipad/logs/workflow-diff-analysis-20260225.md"
echo "  - Fix issues: python3 scripts/workflow-diff-engine.py --pipeline <PIPELINE> --revert"
echo "  - Verify: python3 scripts/workflow-diff-engine.py --pipeline <PIPELINE>"
