#!/usr/bin/env python3
"""Merge Phase 3 dataset files into a single file with correct field mapping.

Reads 4 files from datasets/phase-3/ and outputs datasets/phase-3-questions.json
with the format expected by eval/run_eval.py:load_questions().

Field mapping:
  answer → expected_answer
  rag_target → pipeline
  Adds unique 'id' per question if missing
"""
import json, os, hashlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHASE3_DIR = os.path.join(BASE, "datasets", "phase-3")
OUTPUT = os.path.join(BASE, "datasets", "phase-3-questions.json")

FILES = [
    ("standard-8700.json", "standard"),
    ("graph-1500.json", "graph"),
    ("quantitative-500.json", "quantitative"),
    ("orchestrator-auto.json", None),  # pipeline from rag_target field
]

def main():
    all_questions = []
    stats = {}

    for filename, default_pipeline in FILES:
        filepath = os.path.join(PHASE3_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP: {filename} not found")
            continue

        with open(filepath) as f:
            data = json.load(f)

        questions = data.get("questions", data) if isinstance(data, dict) else data
        if not isinstance(questions, list):
            print(f"  SKIP: {filename} unexpected format")
            continue

        count = 0
        for i, item in enumerate(questions):
            pipeline = default_pipeline or item.get("rag_target", "").lower()
            # Normalize pipeline names
            if pipeline in ("orchestrator", "meta"):
                pipeline = "orchestrator"
            elif pipeline not in ("standard", "graph", "quantitative"):
                pipeline = "standard"  # fallback

            qid = item.get("id", "")
            if not qid:
                # Generate deterministic ID from question text
                q_hash = hashlib.md5(item.get("question", "").encode()).hexdigest()[:8]
                qid = f"p3-{pipeline[:3]}-{i:05d}-{q_hash}"

            mapped = {
                "id": qid,
                "question": item.get("question", ""),
                "expected_answer": item.get("answer", item.get("expected_answer", "")),
                "pipeline": pipeline,
                "context": item.get("context", ""),
                "dataset_name": item.get("dataset_name", ""),
                "difficulty": item.get("difficulty", ""),
                "phase": "phase-3",
            }
            all_questions.append(mapped)
            count += 1

        stats[filename] = count
        print(f"  {filename}: {count} questions")

    output_data = {"questions": all_questions}
    with open(OUTPUT, "w") as f:
        json.dump(output_data, f, indent=1, ensure_ascii=False)

    file_size = os.path.getsize(OUTPUT)
    print(f"\nTotal: {len(all_questions)} questions → {OUTPUT}")
    print(f"File size: {file_size / 1024 / 1024:.1f} MB")

    # Stats by pipeline
    by_pipeline = {}
    for q in all_questions:
        p = q["pipeline"]
        by_pipeline[p] = by_pipeline.get(p, 0) + 1
    print(f"By pipeline: {by_pipeline}")


if __name__ == "__main__":
    main()
