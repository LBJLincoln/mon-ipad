import psycopg2
import os
import json
import uuid
from datetime import datetime

# --- Database Credentials ---
# Placeholder for SUPABASE_PASSWORD, will be taken from env or hardcoded for now
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

def fetch_data(conn, query):
    """Fetches data from the database using the given query."""
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchall()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def populate_documents_table(conn):
    """Populates the documents table from community_summaries and financial questions."""
    
    # Clear existing documents to prevent duplicates on re-run
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE tenant_id = 'benchmark';")
            conn.commit()
            print("Cleared existing 'benchmark' documents from the documents table.")
    except Exception as e:
        print(f"Error clearing documents table: {e}")
        conn.rollback()
        return

    # --- Populate from community_summaries ---
    print("Populating from community_summaries...")
    community_summaries_query = """
    SELECT summary, entity_names, title, tenant_id FROM community_summaries WHERE tenant_id = 'benchmark';
    """
    community_data = fetch_data(conn, community_summaries_query)
    if community_data:
        try:
            with conn.cursor() as cur:
                for summary, entity_names, title, tenant_id in community_data:
                    doc_id = str(uuid.uuid4())
                    content = summary
                    source = f"community_summary:{title}" # Use title as part of source
                    is_obsolete = False
                    cur.execute(
                        """
                        INSERT INTO documents (id, content, source, tenant_id, is_obsolete)
                        VALUES (%s, %s, %s, %s, %s);
                        """,
                        (doc_id, content, source, tenant_id, is_obsolete)
                    )
                conn.commit()
                print(f"Inserted {len(community_data)} documents from community_summaries.")
        except Exception as e:
            print(f"Error inserting community summaries data: {e}")
            conn.rollback()

    # --- Populate from v_phase2_financial_questions ---
    print("Populating from v_phase2_financial_questions...")
    financial_questions_query = """
    SELECT question, context_text, table_string, question_id, dataset, tenant_id FROM v_phase2_financial_questions WHERE tenant_id = 'benchmark';
    """
    financial_data = fetch_data(conn, financial_questions_query)
    if financial_data:
        try:
            with conn.cursor() as cur:
                for question, context_text, table_string, question_id, dataset, tenant_id in financial_data:
                    doc_id = str(uuid.uuid4())
                    
                    # Combine relevant text content
                    content_parts = []
                    if question:
                        content_parts.append(f"Question: {question}")
                    if context_text:
                        content_parts.append(f"Context: {context_text}")
                    if table_string: # table_string is human-readable text version of table
                        content_parts.append(f"Table: {table_string}")
                    
                    content = "
".join(content_parts)
                    source = f"{dataset}:{question_id}"
                    is_obsolete = False
                    
                    if content.strip(): # Only insert if content is not empty
                        cur.execute(
                            """
                            INSERT INTO documents (id, content, source, tenant_id, is_obsolete)
                            VALUES (%s, %s, %s, %s, %s);
                            """,
                            (doc_id, content, source, tenant_id, is_obsolete)
                        )
                conn.commit()
                print(f"Inserted {len(financial_data)} documents from v_phase2_financial_questions.")
        except Exception as e:
            print(f"Error inserting financial questions data: {e}")
            conn.rollback()

    print("Documents table population complete.")


if __name__ == "__main__":
    conn = connect_db()
    if conn:
        populate_documents_table(conn)
        conn.close()
