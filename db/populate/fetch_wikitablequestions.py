#!/usr/bin/env python3
"""
Fetch missing table data for 50 wikitablequestions from HuggingFace and
patch hf-1000.json with the table content.

The TableSenseAI/WikiTableQuestions dataset stores table data as CSV files.
This script fetches each table, converts to a 2D array format, and updates
the questions in hf-1000.json with both context and table_data fields.

Usage:
    python db/populate/fetch_wikitablequestions.py              # Fetch and patch
    python db/populate/fetch_wikitablequestions.py --dry-run    # Preview only
"""
import csv
import io
import json
import os
import sys
import time
from datetime import datetime
from urllib import request, error

# ============================================================
# Configuration
# ============================================================
DATASET_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "phase-2", "hf-1000.json")
HF_API_BASE = "https://datasets-server.huggingface.co/rows"
HF_DATASET = "TableSenseAI/WikiTableQuestions"
HF_FILE_BASE = "https://huggingface.co/datasets/TableSenseAI/WikiTableQuestions/resolve/main"


def fetch_hf_row(item_index):
    """Fetch a single row from the HuggingFace dataset."""
    url = f"{HF_API_BASE}?dataset={HF_DATASET}&config=default&split=test&offset={item_index}&length=1"
    for attempt in range(3):
        try:
            req = request.Request(url, headers={"Accept": "application/json"})
            with request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                rows = data.get("rows", [])
                if rows:
                    return rows[0].get("row", {})
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"    Failed to fetch row {item_index}: {e}")
    return None


def fetch_csv_content(csv_path):
    """Fetch CSV file content from HuggingFace dataset repo."""
    url = f"{HF_FILE_BASE}/{csv_path}"
    for attempt in range(3):
        try:
            req = request.Request(url, headers={"Accept": "*/*"})
            with request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"    Failed to fetch CSV {csv_path}: {e}")
    return None


def csv_to_table_data(csv_content):
    """Convert CSV content to a 2D array (list of lists)."""
    if not csv_content:
        return None

    rows = []
    reader = csv.reader(io.StringIO(csv_content))
    for row in reader:
        rows.append(row)
    return rows if rows else None


def table_data_to_context(table_data):
    """Convert table data to a human-readable context string."""
    if not table_data or len(table_data) < 2:
        return ""

    headers = table_data[0]
    lines = [" | ".join(headers)]
    lines.append("-+-".join("-" * max(len(h), 5) for h in headers))

    for row in table_data[1:]:
        cells = [str(c) for c in row]
        # Pad to match header count
        while len(cells) < len(headers):
            cells.append("")
        lines.append(" | ".join(cells[:len(headers)]))

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    print("=" * 60)
    print("FETCH WIKITABLEQUESTIONS TABLE DATA")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 60)

    # Load dataset
    print("\n1. Loading hf-1000.json...")
    with open(DATASET_FILE) as f:
        data = json.load(f)

    wiki_questions = [
        q for q in data["questions"]
        if q["dataset_name"] == "wikitablequestions"
    ]
    print(f"   Found {len(wiki_questions)} wikitablequestions")

    # Fetch table data for each question
    print("\n2. Fetching table data from HuggingFace...")
    fetched = 0
    failed = 0

    for i, q in enumerate(wiki_questions):
        item_index = q["item_index"]
        print(f"   [{i + 1}/{len(wiki_questions)}] {q['id']} (item_index={item_index})")

        # Fetch the HF row to get the CSV path
        hf_row = fetch_hf_row(item_index)
        if not hf_row:
            print(f"     SKIP: Could not fetch HF row")
            failed += 1
            continue

        context_info = hf_row.get("context", {})
        csv_path = context_info.get("csv", "")
        if not csv_path:
            print(f"     SKIP: No CSV path in HF row")
            failed += 1
            continue

        # Fetch the actual CSV
        csv_content = fetch_csv_content(csv_path)
        if not csv_content:
            print(f"     SKIP: Could not fetch CSV")
            failed += 1
            continue

        # Parse CSV to table data
        table_data = csv_to_table_data(csv_content)
        if not table_data:
            print(f"     SKIP: Could not parse CSV")
            failed += 1
            continue

        # Build context string
        context_str = table_data_to_context(table_data)

        if not dry_run:
            # Update the question in the dataset
            q["table_data"] = json.dumps(table_data)
            q["context"] = context_str
            q["metadata"]["table_source"] = f"HuggingFace {HF_DATASET} {csv_path}"

        num_rows = len(table_data) - 1
        num_cols = len(table_data[0]) if table_data else 0
        print(f"     OK: {num_rows} rows x {num_cols} cols")
        fetched += 1

        # Rate limiting
        if i % 10 == 9:
            time.sleep(1)

    print(f"\n3. Results:")
    print(f"   Fetched: {fetched}")
    print(f"   Failed:  {failed}")

    if not dry_run and fetched > 0:
        print(f"\n4. Saving updated hf-1000.json...")
        with open(DATASET_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"   Saved.")
    elif dry_run:
        print(f"\n4. [DRY RUN] Would have updated {fetched} questions")

    print(f"\n{'='*60}")
    print("FETCH COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
