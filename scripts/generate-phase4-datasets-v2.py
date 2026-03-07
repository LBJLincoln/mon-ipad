#!/usr/bin/env python3
"""
Phase 4 Dataset Generator V2 — SOTA RAG Benchmarks (~100K+ questions)
=====================================================================
Downloads from the best RAG evaluation benchmarks available on HuggingFace:

Standard (~50K):
  - RAGBench (galileo-ai/ragbench) — 12 subsets, ~100K total (sample per subset)
  - SQuAD v2 — 11.8K validation
  - MS MARCO v1.1 — 10K validation
  - CRAG (Quivr/CRAG) — 4.4K comprehensive RAG
  - TriviaQA — 11K validation

Graph (~25K):
  - RAGBench hotpotqa subset — multi-hop
  - HotpotQA distractor — 7.4K validation
  - 2WikiMultiHopQA — 12.5K validation
  - MuSiQue — 2.4K validation
  - MultiHop-RAG (yixuantt/MultiHopRAG) — 2.5K cross-document

Quantitative (~25K):
  - RAGBench finqa + tatqa subsets
  - FinQA (ibm-research/finqa) — full train+validation
  - TAT-QA — full
  - ConvFinQA (TheFinAI/convfinqa) — conversational financial
  - WikiTableQuestions — 4.3K test
  - HybridQA — table+text reasoning

Usage:
  source .env.local
  python3 scripts/generate-phase4-datasets-v2.py
  python3 scripts/generate-phase4-datasets-v2.py --pipeline standard --max 20000
  python3 scripts/generate-phase4-datasets-v2.py --pipeline graph --dry-run
"""
import json
import os
import sys
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

try:
    from datasets import load_dataset
except ImportError:
    print("FATAL: pip install datasets")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
PHASE4_DIR = REPO_ROOT / "datasets" / "phase-4"
PHASE4_DIR.mkdir(parents=True, exist_ok=True)

# ─── Dataset Registry ─────────────────────────────────────────────
# (hf_id, hf_subset, split, question_field, answer_field, context_field, max_per_ds)

STANDARD_DATASETS = {
    # RAGBench subsets (best RAG benchmark, 100K total)
    "ragbench_msmarco":     ("galileo-ai/ragbench", "msmarco", "train", "question", "response", "documents", 8000),
    "ragbench_expertqa":    ("galileo-ai/ragbench", "expertqa", "train", "question", "response", "documents", 3000),
    "ragbench_emanual":     ("galileo-ai/ragbench", "emanual", "train", "question", "response", "documents", 2000),
    "ragbench_techqa":      ("galileo-ai/ragbench", "techqa", "train", "question", "response", "documents", 2000),
    "ragbench_hagrid":      ("galileo-ai/ragbench", "hagrid", "train", "question", "response", "documents", 3000),
    "ragbench_covidqa":     ("galileo-ai/ragbench", "covidqa", "train", "question", "response", "documents", 2000),
    "ragbench_delucionqa":  ("galileo-ai/ragbench", "delucionqa", "train", "question", "response", "documents", 2000),
    "ragbench_pubmedqa":    ("galileo-ai/ragbench", "pubmedqa", "train", "question", "response", "documents", 2000),
    # Classic benchmarks
    "squad_v2":             ("rajpurkar/squad_v2", None, "validation", "question", "answers", "context", 8000),
    "msmarco":              ("microsoft/ms_marco", "v1.1", "validation", "query", "answers", "passages", 8000),
    "triviaqa":             ("trivia_qa", "rc.nocontext", "validation", "question", "answer", None, 8000),
    "crag":                 ("Quivr/CRAG", "crag_task_1_and_2", "train", "query", "answer", None, 4000),
}

GRAPH_DATASETS = {
    # RAGBench multi-hop subset
    "ragbench_hotpotqa":    ("galileo-ai/ragbench", "hotpotqa", "train", "question", "response", "documents", 5000),
    # Classic multi-hop
    "hotpotqa_distractor":  ("hotpotqa/hotpot_qa", "distractor", "validation", "question", "answer", "context", 7000),
    "2wikimultihopqa":      ("xanhho/2WikiMultihopQA", None, "validation", "question", "answer", "context", 7000),
    "musique":              ("bdsaglam/musique", "answerable", "validation", "question", "answer", "paragraphs", 3000),
    # Dedicated multi-hop RAG benchmark
    "multihop_rag":         ("yixuantt/MultiHopRAG", "MultiHopRAG", "train", "query", "answer", None, 2600),
}

QUANT_DATASETS = {
    # RAGBench financial subsets
    "ragbench_finqa":       ("galileo-ai/ragbench", "finqa", "train", "question", "response", "documents", 4000),
    "ragbench_tatqa":       ("galileo-ai/ragbench", "tatqa", "train", "question", "response", "documents", 4000),
    # Full financial benchmarks (using mirrors/parquet for deprecated scripts)
    "finqa_dreamer":        ("dreamerdeo/finqa", None, "train", "question", "answer", "table", 6000),
    "finqa_dreamer_val":    ("dreamerdeo/finqa", None, "validation", "question", "answer", "table", 1500),
    "finqa_verified":       ("Aiera/finqa-verified", None, "train", "question", "answer", None, 3000),
    "finqa_embedding":      ("embedding-benchmark/FinQA", None, "test", "query", "relevant_docs", None, 2000),
    "financial_qa":         ("adityarane/financial-qa-dataset", None, "train", "question", "answer", None, 3000),
}

ALL_PIPELINES = {
    "standard": (STANDARD_DATASETS, 52000),
    "graph": (GRAPH_DATASETS, 25000),
    "quantitative": (QUANT_DATASETS, 28000),
}


def extract_answer(val):
    """Extract clean answer string from various HF formats."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, dict):
        # SQuAD: {"text": ["ans"], "answer_start": [...]}
        texts = val.get("text", [])
        if texts and isinstance(texts, list) and texts[0]:
            return str(texts[0]).strip()
        return str(val)
    if isinstance(val, list):
        if len(val) > 0:
            first = val[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                return str(first.get("text", first.get("answer", first)))
        return ""
    return str(val).strip()


def extract_context(row, ctx_field):
    """Extract context from various HF formats."""
    if not ctx_field or ctx_field not in row:
        return ""
    ctx = row[ctx_field]
    if isinstance(ctx, str):
        return ctx[:3000]
    if isinstance(ctx, dict):
        # HotpotQA: {"title": [...], "sentences": [[...]]}
        titles = ctx.get("title", [])
        sentences = ctx.get("sentences", [])
        parts = []
        for i, title in enumerate(titles[:5]):
            sents = sentences[i] if i < len(sentences) else []
            text = " ".join(str(s) for s in sents[:3]) if isinstance(sents, list) else str(sents)
            parts.append(f"{title}: {text}")
        return "\n".join(parts)[:3000]
    if isinstance(ctx, list):
        parts = []
        for item in ctx[:5]:
            if isinstance(item, dict):
                title = item.get("title", "")
                text = item.get("paragraph_text", item.get("text", item.get("segment", "")))
                parts.append(f"{title}: {text}" if title else str(text))
            elif isinstance(item, str):
                parts.append(item)
            else:
                parts.append(str(item))
        return "\n".join(parts)[:3000]
    return str(ctx)[:3000]


def download_one(ds_name, config, pipeline, dry_run=False):
    """Download and format a single HF dataset."""
    hf_id, hf_subset, split, q_field, a_field, ctx_field, max_items = config
    print(f"  [{ds_name}] Loading {hf_id}" + (f" ({hf_subset})" if hf_subset else "") + f" split={split}...", end=" ", flush=True)

    if dry_run:
        print("DRY RUN — skipped")
        return []

    try:
        kwargs = {"split": split}
        if hf_subset:
            ds = load_dataset(hf_id, hf_subset, **kwargs)
        else:
            ds = load_dataset(hf_id, **kwargs)
    except Exception as e:
        print(f"FAILED: {e}")
        return []

    total = len(ds)
    if total > max_items:
        ds = ds.select(range(max_items))
    print(f"got {len(ds)}/{total}", end=" ", flush=True)

    questions = []
    skipped = 0
    for idx, row in enumerate(ds):
        try:
            question = str(row.get(q_field, "")).strip()
            answer = extract_answer(row.get(a_field))
            context = extract_context(row, ctx_field)

            if not question or not answer:
                skipped += 1
                continue

            q_obj = {
                "id": f"p4-{pipeline[:3]}-{ds_name}-{idx:06d}",
                "question": question,
                "expected_answer": answer,
                "rag_target": pipeline,
                "dataset_name": ds_name,
                "category": "benchmark",
                "tenant_id": "benchmark",
            }
            if context:
                q_obj["context"] = context

            questions.append(q_obj)
        except Exception:
            skipped += 1

    print(f"→ {len(questions)} valid (skipped {skipped})")
    return questions


def generate_pipeline(pipeline, max_total=None, dry_run=False):
    """Generate dataset for a single pipeline."""
    datasets_cfg, default_max = ALL_PIPELINES[pipeline]
    cap = max_total or default_max

    print(f"\n{'='*60}")
    print(f"  PHASE 4 — {pipeline.upper()} (target: {cap})")
    print(f"{'='*60}")

    all_questions = []
    dataset_counts = {}

    for ds_name, config in datasets_cfg.items():
        if len(all_questions) >= cap:
            print(f"  [{ds_name}] SKIPPED (reached {cap} cap)")
            continue

        remaining = min(config[6], cap - len(all_questions))
        adjusted = list(config[:6]) + [remaining]
        qs = download_one(ds_name, tuple(adjusted), pipeline, dry_run)
        all_questions.extend(qs)
        if qs:
            dataset_counts[ds_name] = len(qs)

    # Save
    target_file = f"{pipeline}-{len(all_questions)}.json"
    output = {
        "metadata": {
            "phase": 4,
            "version": 2,
            "pipeline": pipeline,
            "total_questions": len(all_questions),
            "datasets": dataset_counts,
            "generated": datetime.now().isoformat(),
        },
        "questions": all_questions,
    }

    filepath = PHASE4_DIR / target_file
    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False)
        size_mb = filepath.stat().st_size / 1024 / 1024
        print(f"\n  SAVED: {filepath} ({len(all_questions)} questions, {size_mb:.1f} MB)")
    else:
        print(f"\n  DRY RUN: would save {len(all_questions)} questions to {filepath}")

    return len(all_questions)


def main():
    parser = argparse.ArgumentParser(description="Phase 4 Dataset Generator V2")
    parser.add_argument("--pipeline", choices=["standard", "graph", "quantitative", "all"],
                       default="all")
    parser.add_argument("--max", type=int, default=None, help="Max questions per pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    args = parser.parse_args()

    pipelines = ["standard", "graph", "quantitative"] if args.pipeline == "all" else [args.pipeline]
    total = 0

    for p in pipelines:
        n = generate_pipeline(p, args.max, args.dry_run)
        total += n

    print(f"\n{'='*60}")
    print(f"  PHASE 4 V2 COMPLETE: {total} total questions")
    print(f"  Files in: {PHASE4_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
