#!/usr/bin/env python3
"""
Generate Phase 4 datasets for rag-tests evaluation.
Target: ~100K questions across 4 pipelines.

Phase 4 Distribution:
- Standard: 50,000 questions (knowledge-based QA)
- Graph: 20,000 questions (multi-hop reasoning)
- Quantitative: 20,000 questions (financial data)
- Orchestrator: 10,000 questions (mixed routing)

Usage:
    source /home/termius/mon-ipad/.env.local
    python3 scripts/generate_phase4_datasets.py
"""

import json
import os
import random
from typing import List, Dict, Any
from pathlib import Path
from datasets import load_dataset
from supabase import create_client, Client
from tqdm import tqdm
import itertools

# Configuration
OUTPUT_DIR = Path("/home/termius/mon-ipad/datasets/phase-4")
PHASE3_DIR = Path("/home/termius/mon-ipad/datasets/phase-3")

# Target sizes
STANDARD_TARGET = 50_000
GRAPH_TARGET = 20_000
QUANTITATIVE_TARGET = 20_000
ORCHESTRATOR_TARGET = 10_000

# Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_API_KEY")


def load_phase3_dataset(filename: str) -> List[Dict]:
    """Load existing Phase 3 dataset."""
    filepath = PHASE3_DIR / filename
    if not filepath.exists():
        print(f"⚠️  Phase 3 file not found: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    questions = data.get("questions", [])
    print(f"✓ Loaded {len(questions)} questions from {filename}")
    return questions


def save_dataset(questions: List[Dict], filename: str):
    """Save dataset to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"questions": questions}, f, indent=2, ensure_ascii=False)

    print(f"✓ Saved {len(questions)} questions to {filepath}")


def generate_standard_questions() -> List[Dict]:
    """
    Generate ~50K standard pipeline questions from multiple sources.

    Sources:
    - Phase 3 standard-8700.json (8,700 questions)
    - SQuAD v2 (~130K train questions - sample 20K)
    - Natural Questions (~300K - sample 15K)
    - TriviaQA (~95K train - sample 6,300 to reach 50K)
    """
    print("\n" + "="*60)
    print("GENERATING STANDARD PIPELINE QUESTIONS (target: 50,000)")
    print("="*60)

    questions = []

    # 1. Load Phase 3 baseline (8,700 questions)
    print("\n[1/4] Loading Phase 3 baseline...")
    phase3_standard = load_phase3_dataset("standard-8700.json")
    questions.extend(phase3_standard)
    print(f"Total so far: {len(questions):,}")

    # 2. Load SQuAD v2 (sample 20,000)
    print("\n[2/4] Loading SQuAD v2 dataset...")
    try:
        squad = load_dataset("rajpurkar/squad", split="train", streaming=True)
        squad_count = 0
        target_squad = 20_000

        for idx, item in enumerate(itertools.islice(squad, target_squad)):
            if not item.get("answers") or not item["answers"].get("text"):
                continue

            question = {
                "id": f"p4-std-squad-{idx:05d}",
                "question": item["question"],
                "answer": item["answers"]["text"][0],
                "expected_answer": item["answers"]["text"][0],
                "context": item["context"][:2000],  # Truncate long contexts
                "dataset_name": "squad_v2",
                "rag_target": "standard",
                "pipeline": "standard",
                "item_index": idx,
                "difficulty": "medium",
                "phase": "phase4"
            }
            questions.append(question)
            squad_count += 1

            if squad_count >= target_squad:
                break

        print(f"✓ Added {squad_count:,} SQuAD questions")
        print(f"Total so far: {len(questions):,}")
    except Exception as e:
        print(f"⚠️  Error loading SQuAD: {e}")

    # 3. Load Natural Questions (sample 15,000)
    print("\n[3/4] Loading Natural Questions dataset...")
    try:
        nq = load_dataset("google-research-datasets/natural_questions",
                         split="train", streaming=True)
        nq_count = 0
        target_nq = 15_000

        for idx, item in enumerate(itertools.islice(nq, target_nq * 3)):  # Over-sample for filtering
            # Extract short answer if available
            annotations = item.get("annotations", {})
            if not annotations:
                continue

            short_answers = annotations.get("short_answers", [])
            if not short_answers or not short_answers[0]:
                continue

            # Get answer text from document
            document_text = item.get("document", {}).get("tokens", {}).get("token", [])
            if not document_text:
                continue

            answer_start = short_answers[0].get("start_token", 0)
            answer_end = short_answers[0].get("end_token", 0)
            answer = " ".join(document_text[answer_start:answer_end])

            if not answer:
                continue

            question_text = item.get("question", {}).get("text", "")
            context = " ".join(document_text[:500])  # First 500 tokens as context

            question = {
                "id": f"p4-std-nq-{nq_count:05d}",
                "question": question_text,
                "answer": answer,
                "expected_answer": answer,
                "context": context,
                "dataset_name": "natural_questions",
                "rag_target": "standard",
                "pipeline": "standard",
                "item_index": nq_count,
                "difficulty": "medium",
                "phase": "phase4"
            }
            questions.append(question)
            nq_count += 1

            if nq_count >= target_nq:
                break

        print(f"✓ Added {nq_count:,} Natural Questions")
        print(f"Total so far: {len(questions):,}")
    except Exception as e:
        print(f"⚠️  Error loading Natural Questions: {e}")

    # 4. Load TriviaQA to reach 50K target
    remaining = STANDARD_TARGET - len(questions)
    if remaining > 0:
        print(f"\n[4/4] Loading TriviaQA dataset (need {remaining:,} more)...")
        try:
            trivia = load_dataset("mandarjoshi/trivia_qa", "rc.nocontext",
                                 split="train", streaming=True)
            trivia_count = 0

            for idx, item in enumerate(itertools.islice(trivia, remaining * 2)):
                if not item.get("answer") or not item["answer"].get("value"):
                    continue

                question = {
                    "id": f"p4-std-trivia-{idx:05d}",
                    "question": item["question"],
                    "answer": item["answer"]["value"],
                    "expected_answer": item["answer"]["value"],
                    "context": item.get("search_results", {}).get("description", [""])[0][:2000],
                    "dataset_name": "triviaqa",
                    "rag_target": "standard",
                    "pipeline": "standard",
                    "item_index": idx,
                    "difficulty": "medium",
                    "phase": "phase4"
                }
                questions.append(question)
                trivia_count += 1

                if trivia_count >= remaining:
                    break

            print(f"✓ Added {trivia_count:,} TriviaQA questions")
        except Exception as e:
            print(f"⚠️  Error loading TriviaQA: {e}")

    print(f"\n✓ Total standard questions: {len(questions):,} / {STANDARD_TARGET:,}")
    return questions[:STANDARD_TARGET]  # Ensure we don't exceed target


def generate_graph_questions() -> List[Dict]:
    """
    Generate ~20K graph pipeline questions (multi-hop reasoning).

    Sources:
    - Phase 3 graph-1500.json (1,500 questions)
    - MuSiQue (~20K questions)
    - HotpotQA (~90K train - supplement if needed)
    """
    print("\n" + "="*60)
    print("GENERATING GRAPH PIPELINE QUESTIONS (target: 20,000)")
    print("="*60)

    questions = []

    # 1. Load Phase 3 baseline
    print("\n[1/3] Loading Phase 3 baseline...")
    phase3_graph = load_phase3_dataset("graph-1500.json")
    questions.extend(phase3_graph)
    print(f"Total so far: {len(questions):,}")

    # 2. Load MuSiQue dataset
    print("\n[2/3] Loading MuSiQue dataset...")
    try:
        musique = load_dataset("dgslibisey/MuSiQue", split="train")
        musique_count = 0
        target_musique = 15_000

        for idx, item in enumerate(musique):
            if musique_count >= target_musique:
                break

            # Format context as JSON string (similar to Phase 3)
            context_docs = []
            for para in item.get("paragraphs", []):
                context_docs.append({
                    "idx": para.get("idx", 0),
                    "title": para.get("title", ""),
                    "paragraph_text": para.get("paragraph_text", ""),
                    "is_supporting": para.get("is_supporting", False)
                })

            question = {
                "id": f"p4-graph-musique-{idx:05d}",
                "question": item["question"],
                "answer": item["answer"],
                "expected_answer": item["answer"],
                "context": json.dumps(context_docs),
                "dataset_name": "musique",
                "rag_target": "graph",
                "pipeline": "graph",
                "item_index": idx,
                "difficulty": "hard",
                "phase": "phase4"
            }
            questions.append(question)
            musique_count += 1

        print(f"✓ Added {musique_count:,} MuSiQue questions")
        print(f"Total so far: {len(questions):,}")
    except Exception as e:
        print(f"⚠️  Error loading MuSiQue: {e}")

    # 3. Load HotpotQA if needed
    remaining = GRAPH_TARGET - len(questions)
    if remaining > 0:
        print(f"\n[3/3] Loading HotpotQA (need {remaining:,} more)...")
        try:
            hotpot = load_dataset("hotpotqa/hotpot_qa", "fullwiki",
                                 split="train", streaming=True)
            hotpot_count = 0

            for idx, item in enumerate(itertools.islice(hotpot, remaining * 2)):
                if item.get("level") != "hard":  # Only hard multi-hop questions
                    continue

                # Format context
                context_docs = []
                for ctx_title, ctx_sentences in zip(item["context"]["title"],
                                                    item["context"]["sentences"]):
                    context_docs.append({
                        "idx": len(context_docs),
                        "title": ctx_title,
                        "paragraph_text": " ".join(ctx_sentences),
                        "is_supporting": False
                    })

                question = {
                    "id": f"p4-graph-hotpot-{idx:05d}",
                    "question": item["question"],
                    "answer": item["answer"],
                    "expected_answer": item["answer"],
                    "context": json.dumps(context_docs),
                    "dataset_name": "hotpotqa_fullwiki",
                    "rag_target": "graph",
                    "pipeline": "graph",
                    "item_index": idx,
                    "difficulty": "hard",
                    "phase": "phase4"
                }
                questions.append(question)
                hotpot_count += 1

                if hotpot_count >= remaining:
                    break

            print(f"✓ Added {hotpot_count:,} HotpotQA questions")
        except Exception as e:
            print(f"⚠️  Error loading HotpotQA: {e}")

    print(f"\n✓ Total graph questions: {len(questions):,} / {GRAPH_TARGET:,}")
    return questions[:GRAPH_TARGET]


def generate_quantitative_questions() -> List[Dict]:
    """
    Generate ~20K quantitative pipeline questions.

    Sources:
    - Phase 3 quantitative-500-v2.json (326 questions from Supabase)
    - Expanded Supabase synthetic variations (~9,674 more)
    - FinQA dataset (~8K)
    - TatQA dataset (~2K)
    """
    print("\n" + "="*60)
    print("GENERATING QUANTITATIVE PIPELINE QUESTIONS (target: 20,000)")
    print("="*60)

    questions = []

    # 1. Load Phase 3 baseline
    print("\n[1/4] Loading Phase 3 baseline...")
    phase3_quant = load_phase3_dataset("quantitative-500-v2.json")
    questions.extend(phase3_quant)
    print(f"Total so far: {len(questions):,}")

    # 2. Generate expanded Supabase questions
    print("\n[2/4] Generating expanded Supabase questions...")
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Fetch all financial data
        response = supabase.table("financials").select("*").execute()
        financial_data = response.data

        if not financial_data:
            print("⚠️  No financial data found in Supabase")
        else:
            print(f"✓ Found {len(financial_data)} financial records")

            # Generate multiple question variations per record
            question_templates = [
                ("What was {company}'s revenue in {year}?", "revenue", "$"),
                ("What was {company}'s net income in {year}?", "net_income", "$"),
                ("What was {company}'s total assets in {year}?", "total_assets", "$"),
                ("What was {company}'s total liabilities in {year}?", "total_liabilities", "$"),
                ("What was {company}'s operating income for {year}?", "operating_income", "$"),
                ("What was {company}'s gross profit in {year}?", "gross_profit", "$"),
                ("How much revenue did {company} generate in {year}?", "revenue", "$"),
                ("What were {company}'s total assets at the end of {year}?", "total_assets", "$"),
                ("What was the net income of {company} in {year}?", "net_income", "$"),
                ("What was {company}'s operating income during {year}?", "operating_income", "$"),
            ]

            supabase_count = 0
            for record in financial_data:
                company = record.get("company_name", "")
                year = record.get("fiscal_year", "")

                for template, field, prefix in question_templates:
                    value = record.get(field)
                    if value is None:
                        continue

                    # Format value
                    if isinstance(value, (int, float)):
                        if value >= 1e9:
                            formatted_value = f"{prefix}{value/1e9:.2f} billion"
                        elif value >= 1e6:
                            formatted_value = f"{prefix}{value/1e6:.2f} million"
                        else:
                            formatted_value = f"{prefix}{value:,.2f}"
                    else:
                        formatted_value = str(value)

                    question = {
                        "id": f"p4-qua-supabase-{supabase_count:05d}",
                        "question": template.format(company=company, year=year),
                        "answer": formatted_value,
                        "expected_answer": formatted_value,
                        "context": None,
                        "dataset_name": "supabase_financial",
                        "rag_target": "quantitative",
                        "pipeline": "quantitative",
                        "item_index": supabase_count,
                        "difficulty": "medium",
                        "phase": "phase4",
                        "sql_table": "financials",
                        "sql_field": field,
                        "raw_value": value
                    }
                    questions.append(question)
                    supabase_count += 1

            print(f"✓ Generated {supabase_count:,} Supabase variations")
            print(f"Total so far: {len(questions):,}")
    except Exception as e:
        print(f"⚠️  Error generating Supabase questions: {e}")

    # 3. Load FinQA dataset
    print("\n[3/4] Loading FinQA dataset...")
    try:
        finqa = load_dataset("dreamerdeo/finqa", split="train")
        finqa_count = 0
        target_finqa = min(8_000, len(finqa))

        for idx, item in enumerate(finqa):
            if finqa_count >= target_finqa:
                break

            # Extract answer
            answer = item.get("answer", "")
            if not answer:
                continue

            question = {
                "id": f"p4-qua-finqa-{idx:05d}",
                "question": item["question"],
                "answer": answer,
                "expected_answer": answer,
                "context": item.get("pre_text", ""),
                "dataset_name": "finqa",
                "rag_target": "quantitative",
                "pipeline": "quantitative",
                "item_index": idx,
                "difficulty": "hard",
                "phase": "phase4"
            }
            questions.append(question)
            finqa_count += 1

        print(f"✓ Added {finqa_count:,} FinQA questions")
        print(f"Total so far: {len(questions):,}")
    except Exception as e:
        print(f"⚠️  Error loading FinQA: {e}")

    # 4. Add more synthetic questions if needed
    remaining = QUANTITATIVE_TARGET - len(questions)
    if remaining > 0:
        print(f"\n[4/4] Generating additional synthetic questions (need {remaining:,} more)...")

        # Create more complex questions (comparisons, ratios, trends)
        comparison_templates = [
            "What is the difference between {company}'s revenue in {year1} and {year2}?",
            "How much did {company}'s net income change from {year1} to {year2}?",
            "What was the percentage change in {company}'s total assets from {year1} to {year2}?",
            "Compare {company}'s operating income in {year1} versus {year2}.",
        ]

        try:
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            response = supabase.table("financials").select("*").execute()
            financial_data = response.data

            # Group by company
            by_company = {}
            for record in financial_data:
                company = record.get("company_name")
                if company not in by_company:
                    by_company[company] = []
                by_company[company].append(record)

            synthetic_count = 0
            for company, records in by_company.items():
                if len(records) < 2:
                    continue

                # Sort by year
                records.sort(key=lambda x: x.get("fiscal_year", ""))

                # Generate comparison questions
                for i in range(len(records) - 1):
                    for template in comparison_templates:
                        year1 = records[i].get("fiscal_year")
                        year2 = records[i + 1].get("fiscal_year")

                        question = {
                            "id": f"p4-qua-synthetic-{synthetic_count:05d}",
                            "question": template.format(company=company, year1=year1, year2=year2),
                            "answer": "comparative analysis required",
                            "expected_answer": "comparative analysis required",
                            "context": None,
                            "dataset_name": "synthetic_comparison",
                            "rag_target": "quantitative",
                            "pipeline": "quantitative",
                            "item_index": synthetic_count,
                            "difficulty": "hard",
                            "phase": "phase4"
                        }
                        questions.append(question)
                        synthetic_count += 1

                        if len(questions) >= QUANTITATIVE_TARGET:
                            break

                    if len(questions) >= QUANTITATIVE_TARGET:
                        break

                if len(questions) >= QUANTITATIVE_TARGET:
                    break

            print(f"✓ Generated {synthetic_count:,} synthetic comparison questions")
        except Exception as e:
            print(f"⚠️  Error generating synthetic questions: {e}")

    print(f"\n✓ Total quantitative questions: {len(questions):,} / {QUANTITATIVE_TARGET:,}")
    return questions[:QUANTITATIVE_TARGET]


def generate_orchestrator_questions(
    standard_questions: List[Dict],
    graph_questions: List[Dict],
    quantitative_questions: List[Dict]
) -> List[Dict]:
    """
    Generate ~10K orchestrator questions by sampling from all pipelines.

    Distribution:
    - 50% Standard (5,000)
    - 30% Graph (3,000)
    - 20% Quantitative (2,000)
    """
    print("\n" + "="*60)
    print("GENERATING ORCHESTRATOR PIPELINE QUESTIONS (target: 10,000)")
    print("="*60)

    questions = []

    # Sample from each pipeline
    n_standard = 5_000
    n_graph = 3_000
    n_quantitative = 2_000

    print(f"\nSampling questions:")
    print(f"  - Standard: {n_standard:,}")
    print(f"  - Graph: {n_graph:,}")
    print(f"  - Quantitative: {n_quantitative:,}")

    # Sample and update metadata
    sampled_standard = random.sample(standard_questions, min(n_standard, len(standard_questions)))
    sampled_graph = random.sample(graph_questions, min(n_graph, len(graph_questions)))
    sampled_quant = random.sample(quantitative_questions, min(n_quantitative, len(quantitative_questions)))

    # Update IDs and pipeline metadata for orchestrator
    idx = 0
    for q in sampled_standard:
        q_copy = q.copy()
        q_copy["id"] = f"p4-orch-{idx:05d}"
        q_copy["pipeline"] = "orchestrator"
        q_copy["expected_pipeline"] = "standard"  # Expected routing
        questions.append(q_copy)
        idx += 1

    for q in sampled_graph:
        q_copy = q.copy()
        q_copy["id"] = f"p4-orch-{idx:05d}"
        q_copy["pipeline"] = "orchestrator"
        q_copy["expected_pipeline"] = "graph"
        questions.append(q_copy)
        idx += 1

    for q in sampled_quant:
        q_copy = q.copy()
        q_copy["id"] = f"p4-orch-{idx:05d}"
        q_copy["pipeline"] = "orchestrator"
        q_copy["expected_pipeline"] = "quantitative"
        questions.append(q_copy)
        idx += 1

    # Shuffle to mix pipeline types
    random.shuffle(questions)

    print(f"\n✓ Total orchestrator questions: {len(questions):,} / {ORCHESTRATOR_TARGET:,}")
    return questions


def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("PHASE 4 DATASET GENERATION")
    print("Target: ~100K questions across 4 pipelines")
    print("="*60)

    # Check environment
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️  WARNING: Supabase credentials not set. Quantitative generation will be limited.")

    # Generate all pipeline datasets
    standard_questions = generate_standard_questions()
    graph_questions = generate_graph_questions()
    quantitative_questions = generate_quantitative_questions()
    orchestrator_questions = generate_orchestrator_questions(
        standard_questions,
        graph_questions,
        quantitative_questions
    )

    # Save datasets
    print("\n" + "="*60)
    print("SAVING DATASETS")
    print("="*60 + "\n")

    save_dataset(standard_questions, "standard-50000.json")
    save_dataset(graph_questions, "graph-20000.json")
    save_dataset(quantitative_questions, "quantitative-20000.json")
    save_dataset(orchestrator_questions, "orchestrator-10000.json")

    # Summary
    total = len(standard_questions) + len(graph_questions) + len(quantitative_questions) + len(orchestrator_questions)
    print("\n" + "="*60)
    print("PHASE 4 DATASET GENERATION COMPLETE")
    print("="*60)
    print(f"\nStandard:      {len(standard_questions):>7,} / {STANDARD_TARGET:>7,}")
    print(f"Graph:         {len(graph_questions):>7,} / {GRAPH_TARGET:>7,}")
    print(f"Quantitative:  {len(quantitative_questions):>7,} / {QUANTITATIVE_TARGET:>7,}")
    print(f"Orchestrator:  {len(orchestrator_questions):>7,} / {ORCHESTRATOR_TARGET:>7,}")
    print(f"{'─'*60}")
    print(f"TOTAL:         {total:>7,} / 100,000")
    print(f"\nCompletion: {total/100_000*100:.1f}%")
    print(f"\nOutput directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    main()
