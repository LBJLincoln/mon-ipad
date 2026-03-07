#!/usr/bin/env python3
"""
Phase 4 Dataset Generator — Download & format ~100K questions from HuggingFace
===============================================================================
Downloads larger splits from the 13 HF benchmark datasets already validated in
Phase 3, formats them for our eval pipeline, and saves to datasets/phase-4/.

Target:
  - Standard: ~50K (9 datasets)
  - Graph: ~20K (3 datasets)
  - Quantitative: ~20K (4 datasets)

Usage:
  python3 scripts/generate-phase4-datasets.py
  python3 scripts/generate-phase4-datasets.py --pipeline standard --max 10000
"""
import json
import os
import sys
import hashlib
import argparse
from pathlib import Path

# HuggingFace datasets library
try:
    from datasets import load_dataset
except ImportError:
    print("FATAL: pip install datasets")
    sys.exit(1)

REPO_ROOT = Path(__file__).parent.parent
PHASE4_DIR = REPO_ROOT / "datasets" / "phase-4"
PHASE4_DIR.mkdir(parents=True, exist_ok=True)

# ─── Dataset configs ───────────────────────────────────────────────
# Each entry: (hf_id, hf_subset, split, question_field, answer_field, context_field, pipeline, max_per_ds)

STANDARD_DATASETS = [
    ("rajpurkar/squad_v2", None, "validation", "question", "answers", "context", 5000),
    ("microsoft/ms_marco", "v1.1", "validation", "query", "answers", "passages", 8000),
    ("hotpotqa/hotpot_qa", "fullwiki", "validation", "question", "answer", "context", 5000),
    ("web_questions", None, "test", "question", "answers", None, 2000),
    ("trivia_qa", "rc.nocontext", "validation", "question", "answer", None, 5000),
    ("natural_questions", "default", "validation", "question", "answer", None, 5000),
    ("PubMedQA", "pqa_labeled", "train", "question", "final_decision", "context", 1000),
]

GRAPH_DATASETS = [
    ("hotpotqa/hotpot_qa", "distractor", "validation", "question", "answer", "context", 7000),
    ("xanhho/2WikiMultihopQA", None, "validation", "question", "answer", "context", 7000),
    ("bdsaglam/musique", "answerable", "validation", "question", "answer", "paragraphs", 3000),
]

QUANT_DATASETS = [
    ("ibm-research/finqa", None, "validation", "question", "answer", "table", 3000),
    ("next-tat/TAT-QA", None, "test", "question", "answer", "table", 5000),
    ("wikitablequestions", None, "test", "question", "answers", "table", 5000),
]


def safe_id(dataset_name, idx):
    """Generate a unique ID for a question."""
    raw = f"{dataset_name}-{idx}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def extract_answer(answer_field_value):
    """Extract a clean answer string from various HF answer formats."""
    if answer_field_value is None:
        return ""
    if isinstance(answer_field_value, str):
        return answer_field_value.strip()
    if isinstance(answer_field_value, dict):
        # SQuAD format: {"text": ["answer1", ...], "answer_start": [...]}
        texts = answer_field_value.get("text", [])
        if texts and isinstance(texts, list):
            return texts[0].strip() if texts[0] else ""
        return str(answer_field_value)
    if isinstance(answer_field_value, list):
        if len(answer_field_value) > 0:
            first = answer_field_value[0]
            if isinstance(first, str):
                return first.strip()
            if isinstance(first, dict):
                return first.get("text", str(first))
        return ""
    return str(answer_field_value).strip()


def extract_context(row, context_field):
    """Extract context from various HF context formats."""
    if not context_field or context_field not in row:
        return ""
    ctx = row[context_field]
    if isinstance(ctx, str):
        return ctx[:3000]  # Limit context size
    if isinstance(ctx, dict):
        # HotpotQA format: {"title": [...], "sentences": [[...]]}
        titles = ctx.get("title", [])
        sentences = ctx.get("sentences", [])
        parts = []
        for i, title in enumerate(titles[:5]):
            sents = sentences[i] if i < len(sentences) else []
            if isinstance(sents, list):
                text = " ".join(str(s) for s in sents[:3])
            else:
                text = str(sents)
            parts.append(f"{title}: {text}")
        return "\n".join(parts)[:3000]
    if isinstance(ctx, list):
        # MuSiQue paragraphs format
        parts = []
        for item in ctx[:5]:
            if isinstance(item, dict):
                title = item.get("title", "")
                text = item.get("paragraph_text", item.get("text", ""))
                parts.append(f"{title}: {text}" if title else str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)[:3000]
    return str(ctx)[:3000]


def download_dataset(hf_id, hf_subset, split, q_field, a_field, ctx_field, max_items, pipeline, ds_name):
    """Download and format a single HF dataset."""
    print(f"\n  [{ds_name}] Loading {hf_id} ({split})...", end=" ", flush=True)

    try:
        kwargs = {"split": split, "trust_remote_code": True}
        if hf_subset:
            ds = load_dataset(hf_id, hf_subset, **kwargs)
        else:
            ds = load_dataset(hf_id, **kwargs)
    except Exception as e:
        print(f"FAILED: {e}")
        return []

    # Limit to max_items
    total = len(ds)
    if total > max_items:
        ds = ds.select(range(max_items))
    print(f"got {len(ds)}/{total} rows", flush=True)

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
            continue

    print(f"  [{ds_name}] {len(questions)} valid questions (skipped {skipped})")
    return questions


def generate_pipeline(pipeline, dataset_configs, dataset_names, target_file, max_total=None):
    """Generate dataset for a single pipeline."""
    print(f"\n{'='*60}")
    print(f"Generating Phase 4 {pipeline.upper()} dataset")
    print(f"{'='*60}")

    all_questions = []
    for i, config in enumerate(dataset_configs):
        hf_id, hf_subset, split, q_field, a_field, ctx_field, max_items = config
        ds_name = dataset_names[i]

        if max_total and len(all_questions) >= max_total:
            print(f"  [{ds_name}] SKIPPED (already have {len(all_questions)} >= {max_total})")
            continue

        remaining = max_items
        if max_total:
            remaining = min(max_items, max_total - len(all_questions))

        qs = download_dataset(hf_id, hf_subset, split, q_field, a_field, ctx_field,
                            remaining, pipeline, ds_name)
        all_questions.extend(qs)

    # Save
    output = {
        "metadata": {
            "phase": 4,
            "pipeline": pipeline,
            "total_questions": len(all_questions),
            "datasets": dataset_names,
            "generated": __import__("datetime").datetime.now().isoformat(),
        },
        "questions": all_questions,
    }

    filepath = PHASE4_DIR / target_file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    size_mb = filepath.stat().st_size / 1024 / 1024
    print(f"\n  SAVED: {filepath} ({len(all_questions)} questions, {size_mb:.1f} MB)")
    return len(all_questions)


def main():
    parser = argparse.ArgumentParser(description="Phase 4 Dataset Generator")
    parser.add_argument("--pipeline", choices=["standard", "graph", "quantitative", "all"],
                       default="all", help="Which pipeline(s) to generate")
    parser.add_argument("--max", type=int, default=None, help="Max questions per pipeline")
    args = parser.parse_args()

    total = 0

    if args.pipeline in ("standard", "all"):
        ds_names = ["squad_v2", "msmarco", "hotpotqa_std", "web_questions",
                    "triviaqa", "natural_questions", "pubmedqa"]
        n = generate_pipeline("standard", STANDARD_DATASETS, ds_names,
                            "standard-50000.json", args.max or 50000)
        total += n

    if args.pipeline in ("graph", "all"):
        ds_names = ["hotpotqa_graph", "2wikimultihopqa", "musique"]
        n = generate_pipeline("graph", GRAPH_DATASETS, ds_names,
                            "graph-20000.json", args.max or 20000)
        total += n

    if args.pipeline in ("quantitative", "all"):
        ds_names = ["finqa", "tatqa", "wikitablequestions"]
        n = generate_pipeline("quantitative", QUANT_DATASETS, ds_names,
                            "quantitative-20000.json", args.max or 20000)
        total += n

    print(f"\n{'='*60}")
    print(f"PHASE 4 GENERATION COMPLETE: {total} total questions")
    print(f"Files in: {PHASE4_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
