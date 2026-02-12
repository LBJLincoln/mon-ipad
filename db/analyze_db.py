import psycopg2
import os
import json

# --- Database Credentials ---
SUPABASE_PASSWORD = os.environ.get("SUPABASE_PASSWORD", "udVECdcSnkMCAPiY")
DB_CONNECTION_STRING = f"postgresql://postgres.ayqviqmxifzmhphiqfmj:{SUPABASE_PASSWORD}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"

def connect_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DB_CONNECTION_STRING)
        print("Successfully connected to the database.")
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def query_db(conn, query, params=None, fetch_one=False):
    """Executes a query and returns results."""
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if fetch_one:
                return cur.fetchone()
            else:
                return cur.fetchall()
    except Exception as e:
        print(f"Error executing query '{query}': {e}")
        return None

def analyze_database_schema_and_data(conn):
    """Analyzes the database for relevant tables and sample data."""
    print("
--- Database Schema and Data Analysis ---")

    # 1. Check for 'documents' table existence and schema
    print("
1. Checking for 'documents' table:")
    exists_query = "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'documents');"
    documents_table_exists = query_db(conn, exists_query, fetch_one=True)[0]

    if documents_table_exists:
        print("   'documents' table exists.")
        schema_query = """
        SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'documents'
        ORDER BY ordinal_position;
        """
        schema = query_db(conn, schema_query)
        print("   Schema:")
        for col in schema:
            print(f"     - {col[0]} ({col[1]}{'['+str(col[2])+']' if col[2] else ''}) NULLABLE:{col[3]} DEFAULT:{col[4]}")
        
        # Count rows in documents table
        count_docs = query_db(conn, "SELECT COUNT(*) FROM documents;", fetch_one=True)[0]
        print(f"   Row count in 'documents': {count_docs}")

        # Fetch sample data from documents table
        if count_docs > 0:
            print("   Sample data from 'documents':")
            sample_docs = query_db(conn, "SELECT id, content, source, tenant_id FROM documents LIMIT 2;")
            for doc in sample_docs:
                print(f"     - ID: {doc[0]}, Source: {doc[2]}, Tenant: {doc[3]}, Content: {doc[1][:100]}...")
    else:
        print("   'documents' table does NOT exist.")

    # 2. Query for row counts in relevant tables
    print("
2. Checking row counts for other relevant tables:")
    tables_to_check = [
        "community_summaries",
        "finqa_tables",
        "tatqa_tables",
        "convfinqa_tables",
        "v_phase2_financial_questions" # View
    ]
    for table_name in tables_to_check:
        try:
            count_query = f"SELECT COUNT(*) FROM {table_name} WHERE tenant_id = 'benchmark';"
            count = query_db(conn, count_query, fetch_one=True)[0]
            print(f"   Row count in '{table_name}' (tenant='benchmark'): {count}")
            
            # Fetch sample data
            if count > 0 and table_name != "v_phase2_financial_questions": # Avoid querying views for sample directly if possible
                print(f"   Sample data from '{table_name}' (first 2 rows):")
                sample_query = f"SELECT * FROM {table_name} WHERE tenant_id = 'benchmark' LIMIT 2;"
                sample_data = query_db(conn, sample_query)
                for row in sample_data:
                    print(f"     - {row}")
            elif count > 0 and table_name == "v_phase2_financial_questions":
                 print(f"   Sample data from '{table_name}' (first 2 rows):")
                 sample_query = f"SELECT question, context_text, table_string FROM {table_name} WHERE tenant_id = 'benchmark' LIMIT 2;"
                 sample_data = query_db(conn, sample_query)
                 for row in sample_data:
                     print(f"     - Question: {row[0]}, Context: {row[1][:100]}..., Table: {row[2][:100]}...")
                     
        except Exception as e:
            print(f"   Could not query '{table_name}': {e}")

    print("
--- Database Analysis Complete ---")


if __name__ == "__main__":
    conn = connect_db()
    if conn:
        analyze_database_schema_and_data(conn)
        conn.close()
