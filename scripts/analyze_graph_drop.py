#!/usr/bin/env python3
"""Analyze Graph pipeline accuracy drop from Phase 2 (78%) to Phase 3 (40.9%)"""

import json
import sys
from collections import defaultdict, Counter
from pathlib import Path

def load_phase3_graph_dataset():
    """Load Phase 3 graph dataset"""
    with open('/home/termius/mon-ipad/datasets/phase-3/graph-1500.json', 'r') as f:
        data = json.load(f)
        # Handle both list and dict with 'questions' key
        if isinstance(data, dict) and 'questions' in data:
            return data['questions']
        return data

def load_phase3_results():
    """Load Phase 3 eval results from data.json"""
    with open('/home/termius/mon-ipad/docs/data.json', 'r') as f:
        data = json.load(f)

    # Find Graph Phase 3 results
    graph_results = []
    for iteration in data.get('iterations', []):
        label = iteration.get('label', '')
        if 'Graph' in label or 'graph' in label.lower():
            graph_results.append(iteration)

    return graph_results

def analyze_by_source(dataset, results):
    """Analyze accuracy by source dataset"""
    print("\n" + "="*80)
    print("PHASE 3 GRAPH DATASET ANALYSIS")
    print("="*80)

    # Count by source - check different possible metadata locations
    source_counts = Counter()
    for q in dataset:
        # Try different metadata locations
        if isinstance(q, dict):
            source = q.get('metadata', {}).get('source', q.get('source', 'unknown'))
        else:
            source = 'unknown'
        source_counts[source] += 1

    print(f"\n📊 Questions by source:")
    for source, count in source_counts.most_common():
        print(f"  {source}: {count} questions ({count/len(dataset)*100:.1f}%)")

    # Try to map results to questions
    print(f"\n📈 Total questions in dataset: {len(dataset)}")

    return source_counts

def analyze_wrong_answers(dataset, sample_size=10):
    """Sample wrong answers from Phase 3 results"""
    print("\n" + "="*80)
    print("SAMPLING WRONG ANSWERS")
    print("="*80)

    # Load the latest Graph Phase 3 results
    results_dir = Path('/home/termius/mon-ipad/eval/outputs/phase-3')
    if not results_dir.exists():
        print(f"⚠️  Results directory not found: {results_dir}")
        return []

    # Find latest Graph results file
    graph_files = sorted(results_dir.glob('graph-*.json'), reverse=True)
    if not graph_files:
        print(f"⚠️  No Graph results files found in {results_dir}")
        return []

    latest_file = graph_files[0]
    print(f"\n📂 Loading results from: {latest_file.name}")

    with open(latest_file, 'r') as f:
        results = json.load(f)

    # Extract wrong answers
    wrong_answers = []
    for result in results:
        if not result.get('correct', True):  # If marked incorrect
            wrong_answers.append(result)

    print(f"\n❌ Total wrong answers: {len(wrong_answers)}")
    print(f"✅ Total correct answers: {len(results) - len(wrong_answers)}")
    print(f"📊 Accuracy: {(len(results) - len(wrong_answers))/len(results)*100:.1f}%")

    # Sample wrong answers
    sample = wrong_answers[:sample_size]

    print(f"\n🔍 Sample of {len(sample)} wrong answers:\n")

    for i, result in enumerate(sample, 1):
        print(f"\n--- WRONG ANSWER #{i} ---")
        print(f"Question: {result.get('question', 'N/A')[:150]}...")
        print(f"Expected: {result.get('expected_answer', 'N/A')[:100]}")
        print(f"Actual: {result.get('actual_answer', 'N/A')[:100]}")
        print(f"Source: {result.get('metadata', {}).get('source', 'unknown')}")

        # Check reasoning if available
        reasoning = result.get('reasoning', '')
        if reasoning:
            print(f"Reasoning: {reasoning[:200]}...")

    return wrong_answers

def analyze_by_source_accuracy(dataset, results_file):
    """Calculate accuracy by source dataset"""
    print("\n" + "="*80)
    print("ACCURACY BY SOURCE DATASET")
    print("="*80)

    if not Path(results_file).exists():
        print(f"⚠️  Results file not found: {results_file}")
        return

    with open(results_file, 'r') as f:
        results = json.load(f)

    # Map results by question text to source
    source_correct = defaultdict(int)
    source_total = defaultdict(int)

    # Build question to source map
    question_to_source = {}
    for q in dataset:
        if isinstance(q, dict) and 'question' in q:
            source = q.get('metadata', {}).get('source', q.get('source', 'unknown'))
            question_to_source[q['question'].strip()] = source

    # Count by source
    for result in results:
        question = result.get('question', '').strip()
        source = question_to_source.get(question, 'unknown')

        source_total[source] += 1
        if result.get('correct', False):
            source_correct[source] += 1

    print(f"\n📊 Accuracy breakdown by source:\n")
    for source in sorted(source_total.keys()):
        total = source_total[source]
        correct = source_correct[source]
        accuracy = (correct / total * 100) if total > 0 else 0
        print(f"  {source:30s}: {correct:4d}/{total:4d} = {accuracy:5.1f}%")

    return source_correct, source_total

def main():
    print("🔍 Analyzing Graph Pipeline Accuracy Drop (Phase 2: 78% → Phase 3: 40.9%)")

    # Load dataset
    dataset = load_phase3_graph_dataset()

    # Analyze by source
    source_counts = analyze_by_source(dataset, None)

    # Find latest results file
    results_dir = Path('/home/termius/mon-ipad/eval/outputs/phase-3')
    if results_dir.exists():
        graph_files = sorted(results_dir.glob('graph-*.json'), reverse=True)
        if graph_files:
            latest_file = graph_files[0]

            # Analyze accuracy by source
            analyze_by_source_accuracy(dataset, latest_file)

            # Sample wrong answers
            analyze_wrong_answers(dataset, sample_size=10)

    print("\n" + "="*80)
    print("✅ Analysis complete")
    print("="*80)

if __name__ == "__main__":
    main()
