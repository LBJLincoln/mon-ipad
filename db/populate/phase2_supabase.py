#!/usr/bin/env python3
"""
Populate Phase 2 Supabase tables (finqa_tables, tatqa_tables, convfinqa_tables)
from the hf-1000.json dataset file.

Parses table_data and context fields from each question and inserts
structured records into the appropriate Supabase table.

Uses psycopg2 Python driver (no psql CLI needed).
Install: pip3 install psycopg2-binary

Usage:
    python3 db/populate/phase2_supabase.py --reset     # Wipe + repopulate (RECOMMENDED)
    python3 db/populate/phase2_supabase.py             # Populate (upsert)
    python3 db/populate/phase2_supabase.py --dry-run   # Parse only, no DB writes
    python3 db/populate/phase2_supabase.py --dataset finqa  # Single dataset
"""
import json
import os
import re
import sys
from datetime import datetime

# ============================================================
# Configuration
# ============================================================
SUPABASE_HOST = "aws-1-eu-west-1.pooler.supabase.com"
SUPABASE_PORT = 6543
SUPABASE_DB = "postgres"
SUPABASE_USER = "postgres.ayqviqmxifzmhphiqfmj"

DATASET_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "phase-2", "hf-1000.json")
MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "..", "migrations", "phase2-financial-tables.sql")

DATASET_TABLE_MAP = {
    "finqa": "finqa_tables",
    "tatqa": "tatqa_tables",
    "convfinqa": "convfinqa_tables",
}


# ============================================================
# Database connection (psycopg2)
# ============================================================

def get_connection():
    """Get a psycopg2 connection to Supabase PostgreSQL."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed.")
        print("Fix:   pip3 install psycopg2-binary")
        sys.exit(1)

    password = os.environ.get("SUPABASE_PASSWORD", "")
    if not password:
        print("ERROR: SUPABASE_PASSWORD not set")
        sys.exit(1)

    return psycopg2.connect(
        host=SUPABASE_HOST,
        port=SUPABASE_PORT,
        dbname=SUPABASE_DB,
        user=SUPABASE_USER,
        password=password,
        connect_timeout=30,
    )


def execute_sql(conn, sql, params=None, fetch=False):
    """Execute SQL statement and optionally fetch results."""
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        if fetch:
            rows = cur.fetchall()
            return rows
        conn.commit()
        return cur.rowcount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()


# ============================================================
# Table data parsing
# ============================================================

def parse_table_data_string(td_str):
    """Parse a JSON-encoded 2D array string into structured table data.

    FinQA/ConvFinQA table_data is a JSON string like:
    '[["header1", "header2"], ["val1", "val2"], ...]'
    """
    if not td_str:
        return None, None, [], 0, 0

    try:
        rows = json.loads(td_str) if isinstance(td_str, str) else td_str
    except (json.JSONDecodeError, TypeError):
        return None, td_str, [], 0, 0

    if not isinstance(rows, list) or len(rows) == 0:
        return None, str(td_str), [], 0, 0

    headers = [str(h).strip() for h in rows[0]] if rows else []
    num_rows = len(rows) - 1
    num_cols = len(headers)
    table_string = format_table_string(rows)

    return rows, table_string, headers, num_rows, num_cols


def extract_tables_from_tatqa_context(context_str):
    """Extract embedded table data from TAT-QA context strings.

    TAT-QA embeds tables as inline JSON arrays within the context text.
    Format: 'Some text [["header1", ...], ["val1", ...]] More text'
    """
    if not context_str:
        return None, None, [], 0, 0

    pattern = r'\[\s*\[(?:"[^"]*"(?:\s*,\s*"[^"]*")*)\](?:\s*,\s*\[(?:"[^"]*"(?:\s*,\s*"[^"]*")*)\])*\s*\]'
    matches = re.findall(pattern, context_str)

    all_rows = []
    for match in matches:
        try:
            rows = json.loads(match)
            if isinstance(rows, list) and len(rows) > 0:
                all_rows.extend(rows)
        except json.JSONDecodeError:
            continue

    if not all_rows:
        try:
            if context_str.strip().startswith('['):
                rows = json.loads(context_str)
                if isinstance(rows, list):
                    all_rows = rows
        except json.JSONDecodeError:
            pass

    if not all_rows:
        return None, context_str, [], 0, 0

    headers = [str(h).strip() for h in all_rows[0]] if all_rows else []
    num_rows = len(all_rows) - 1
    num_cols = len(headers)
    table_string = format_table_string(all_rows)

    return all_rows, table_string, headers, num_rows, num_cols


def format_table_string(rows):
    """Convert a 2D array into a human-readable text table."""
    if not rows:
        return ""

    col_widths = []
    for row in rows:
        for i, cell in enumerate(row):
            cell_str = str(cell).strip()
            while i >= len(col_widths):
                col_widths.append(0)
            col_widths[i] = max(col_widths[i], len(cell_str))

    col_widths = [min(w, 30) for w in col_widths]

    lines = []
    for row_idx, row in enumerate(rows):
        cells = []
        for i, cell in enumerate(row):
            cell_str = str(cell).strip()[:30]
            if i < len(col_widths):
                cells.append(cell_str.ljust(col_widths[i]))
            else:
                cells.append(cell_str)
        lines.append(" | ".join(cells))
        if row_idx == 0:
            lines.append("-+-".join("-" * w for w in col_widths[:len(row)]))

    return "\n".join(lines)


# ============================================================
# Database operations
# ============================================================

def reset_tables(conn, dry_run=False):
    """Truncate all Phase 2 tables (clean slate)."""
    if dry_run:
        print("  [DRY RUN] Would TRUNCATE finqa_tables, tatqa_tables, convfinqa_tables")
        return True

    for table in DATASET_TABLE_MAP.values():
        try:
            execute_sql(conn, f"TRUNCATE {table} RESTART IDENTITY;")
            print(f"  Truncated {table}")
        except Exception as e:
            # Table may not exist yet — migration will create it
            print(f"  {table}: skip ({e})")
    return True


def run_migration(conn, dry_run=False):
    """Run the Phase 2 migration SQL."""
    if dry_run:
        print("  [DRY RUN] Would run migration: phase2-financial-tables.sql")
        return True

    migration_path = os.path.abspath(MIGRATION_FILE)
    if not os.path.exists(migration_path):
        print(f"  ERROR: Migration file not found: {migration_path}")
        return False

    with open(migration_path) as f:
        sql = f.read()

    try:
        execute_sql(conn, sql)
        print("  Migration executed successfully.")
        return True
    except Exception as e:
        print(f"  Migration error: {e}")
        return False


def insert_rows(conn, table_name, rows, dry_run=False):
    """Insert parsed rows into the specified Supabase table using psycopg2."""
    if dry_run:
        print(f"  [DRY RUN] Would insert {len(rows)} rows into {table_name}")
        return len(rows)

    if not rows:
        return 0

    import psycopg2.extras

    inserted = 0

    sql = f"""INSERT INTO {table_name}
        (tenant_id, question_id, question, expected_answer, context_text,
         table_data, table_string, num_rows, num_cols, headers)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (tenant_id, question_id) DO UPDATE SET
        table_data = EXCLUDED.table_data,
        table_string = EXCLUDED.table_string,
        context_text = EXCLUDED.context_text,
        num_rows = EXCLUDED.num_rows,
        num_cols = EXCLUDED.num_cols,
        headers = EXCLUDED.headers;"""

    cur = conn.cursor()
    try:
        for row in rows:
            table_data_json = json.dumps(row["table_data"]) if row["table_data"] else None
            params = (
                row["tenant_id"],
                row["question_id"],
                row["question"],
                row["expected_answer"],
                row["context_text"],
                table_data_json,
                row["table_string"],
                row["num_rows"],
                row["num_cols"],
                row["headers"] if row["headers"] else None,
            )
            try:
                cur.execute(sql, params)
                inserted += 1
            except Exception as e:
                conn.rollback()
                print(f"    Error inserting {row['question_id']}: {e}")
                continue

        conn.commit()
    finally:
        cur.close()

    return inserted


# ============================================================
# Main pipeline
# ============================================================

def load_and_parse_questions(dataset_filter=None):
    """Load hf-1000.json and parse questions by dataset."""
    dataset_path = os.path.abspath(DATASET_FILE)
    print(f"  Loading dataset: {dataset_path}")

    with open(dataset_path) as f:
        data = json.load(f)

    questions = data["questions"]
    print(f"  Total questions: {len(questions)}")

    parsed = {"finqa": [], "tatqa": [], "convfinqa": []}

    for q in questions:
        ds = q["dataset_name"]
        if ds not in parsed:
            continue
        if dataset_filter and ds != dataset_filter:
            continue

        question_id = q["id"]
        question_text = q["question"]
        expected_answer = q.get("expected_answer", "")
        context = q.get("context", "")
        table_data_raw = q.get("table_data")

        if ds in ("finqa", "convfinqa"):
            table_data, table_string, headers, num_rows, num_cols = parse_table_data_string(table_data_raw)
        elif ds == "tatqa":
            table_data, table_string, headers, num_rows, num_cols = extract_tables_from_tatqa_context(context)
        else:
            continue

        row = {
            "tenant_id": "benchmark",
            "question_id": question_id,
            "question": question_text,
            "expected_answer": expected_answer,
            "context_text": context[:10000] if context else None,
            "table_data": table_data,
            "table_string": table_string,
            "num_rows": num_rows,
            "num_cols": num_cols,
            "headers": headers,
        }
        parsed[ds].append(row)

    return parsed


def main():
    dry_run = "--dry-run" in sys.argv
    do_reset = "--reset" in sys.argv
    dataset_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--dataset"):
            if "=" in arg:
                dataset_filter = arg.split("=")[1]
            else:
                idx = sys.argv.index(arg) + 1
                if idx < len(sys.argv):
                    dataset_filter = sys.argv[idx]

    print("=" * 60)
    print("PHASE 2 SUPABASE TABLE POPULATION")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}{' + RESET' if do_reset else ''}")
    if dataset_filter:
        print(f"Dataset filter: {dataset_filter}")
    print("=" * 60)

    # Connect
    conn = None
    if not dry_run:
        print("\n  Connecting to Supabase PostgreSQL...")
        conn = get_connection()
        print("  Connected.")

    # Step 0: Reset if requested
    if do_reset:
        print("\n0. Resetting Phase 2 tables (--reset)...")
        reset_tables(conn, dry_run)

    # Step 1: Run migration
    print("\n1. Running Phase 2 migration...")
    if not run_migration(conn, dry_run):
        print("   Migration failed. Aborting.")
        if conn:
            conn.close()
        sys.exit(1)
    print("   Migration complete.")

    # Step 2: Parse questions
    print("\n2. Parsing questions from hf-1000.json...")
    parsed = load_and_parse_questions(dataset_filter)

    for ds, rows in parsed.items():
        has_table = sum(1 for r in rows if r["table_data"] is not None)
        print(f"   {ds}: {len(rows)} questions, {has_table} with parsed table data")

    # Step 3: Insert into Supabase
    print("\n3. Inserting into Supabase...")
    total_inserted = 0

    for ds, rows in parsed.items():
        if not rows:
            continue
        table_name = DATASET_TABLE_MAP[ds]
        print(f"   Inserting {len(rows)} rows into {table_name}...")
        count = insert_rows(conn, table_name, rows, dry_run)
        total_inserted += count
        print(f"   Inserted: {count}")

    # Step 4: Verify
    if not dry_run and conn:
        print("\n4. Verifying...")
        for ds, table_name in DATASET_TABLE_MAP.items():
            try:
                result = execute_sql(
                    conn,
                    f"SELECT COUNT(*) FROM {table_name} WHERE tenant_id = 'benchmark';",
                    fetch=True
                )
                count = result[0][0] if result else 0
                print(f"   {table_name}: {count} rows")
            except Exception as e:
                print(f"   {table_name}: verification failed - {e}")
    else:
        print("\n4. [DRY RUN] Skipping verification")

    if conn:
        conn.close()

    print(f"\n{'='*60}")
    print(f"PHASE 2 SUPABASE POPULATION {'(DRY RUN) ' if dry_run else ''}COMPLETE")
    print(f"Total inserted: {total_inserted}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
