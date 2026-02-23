#!/usr/bin/env python3
"""
Create the n8n_engine schema in Supabase PostgreSQL.

n8n will auto-create its tables in this schema on first boot.
This keeps n8n tables separate from the existing 40 benchmark/RAG tables.

Usage:
    source .env.local && python3 scripts/setup-supabase-n8n-schema.py
"""
import os
import sys

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system(f"{sys.executable} -m pip install psycopg2-binary -q")
    import psycopg2

PASSWORD = os.environ.get("SUPABASE_PASSWORD", "")
if not PASSWORD:
    print("ERROR: SUPABASE_PASSWORD not set. Run: source .env.local")
    sys.exit(1)

# Use connection pooler (port 6543) — more reliable than direct connection
conn = psycopg2.connect(
    host="aws-1-eu-west-1.pooler.supabase.com",
    port=6543,
    dbname="postgres",
    user="postgres.ayqviqmxifzmhphiqfmj",
    password=PASSWORD,
    sslmode="disable",
    connect_timeout=15,
)
conn.autocommit = True
cur = conn.cursor()

print("Connected to Supabase PostgreSQL")

# Create schema for n8n engine
print("Creating n8n_engine schema...")
cur.execute("CREATE SCHEMA IF NOT EXISTS n8n_engine;")

# Verify
cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'n8n_engine';")
result = cur.fetchone()
if result:
    print(f"  Schema '{result[0]}' exists")
else:
    print("  ERROR: Schema not created")
    sys.exit(1)

# Check existing n8n tables in this schema
cur.execute("""
    SELECT table_name FROM information_schema.tables
    WHERE table_schema = 'n8n_engine'
    ORDER BY table_name;
""")
tables = cur.fetchall()
if tables:
    print(f"  Existing tables in n8n_engine: {len(tables)}")
    for t in tables:
        print(f"    - {t[0]}")
else:
    print("  No tables yet (n8n will create them on first boot)")

cur.close()
conn.close()
print("Done.")
