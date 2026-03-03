#!/usr/bin/env -S python3 -u
"""Ingest Phase 3 graph contexts into Neo4j.

Reads datasets/phase-3/graph-1500.json, extracts entities and paragraphs
from JSON context arrays, and creates Document/Paragraph nodes + relationships
in Neo4j via the HTTP API.

Features:
- Deduplication by paragraph title
- Progress state file for resume after interruption
- Batch Cypher operations (20 paragraphs per call)
- Entity extraction from paragraph_text
- Relationship creation between entities

Usage:
  source .env.local
  python3 scripts/ingest-phase3-neo4j.py                # Full run
  python3 scripts/ingest-phase3-neo4j.py --dry-run       # Count only
  python3 scripts/ingest-phase3-neo4j.py --max 100        # Limit paragraphs
"""
import json, os, sys, hashlib, time, urllib.request, urllib.error, re

# Config
DATASET = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "datasets", "phase-3", "graph-1500.json")
STATE_FILE = "/tmp/ingest-phase3-neo4j-state.json"
# Neo4j Aura HTTP API endpoint
# NEO4J_URI is neo4j+s://38c949a2.databases.neo4j.io → HTTP API at https://38c949a2.databases.neo4j.io
_neo4j_uri = os.environ.get("NEO4J_URI", "")
if _neo4j_uri:
    _host = _neo4j_uri.replace("neo4j+s://", "").replace("neo4j://", "")
    NEO4J_URL = f"https://{_host}/db/neo4j/query/v2"
else:
    NEO4J_URL = os.environ.get("NEO4J_URL", "")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
BATCH_SIZE = 20


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"completed_titles": [], "total_paragraphs": 0, "total_entities": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def neo4j_run(statement, parameters, url, user, password):
    """Execute a single Cypher statement via Neo4j Aura Query API v2."""
    import base64
    auth = base64.b64encode(f"{user}:{password}".encode()).decode()
    body = json.dumps({
        "statement": statement,
        "parameters": parameters
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Basic {auth}",
        "Accept": "application/json"
    })
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read().decode())
    if "errors" in result and result["errors"]:
        raise RuntimeError(f"Neo4j error: {result['errors']}")
    return result


def extract_paragraphs(dataset_path):
    """Extract unique paragraphs from graph-1500.json contexts."""
    with open(dataset_path) as f:
        data = json.load(f)

    paragraphs = {}  # title -> {text, is_supporting, question_ids}
    question_entities = []  # list of {question, entities_mentioned, supporting_titles}

    for q in data.get("questions", []):
        ctx_raw = q.get("context", "")
        if not ctx_raw:
            continue

        # Parse JSON context array
        try:
            if isinstance(ctx_raw, str):
                ctx_items = json.loads(ctx_raw)
            else:
                ctx_items = ctx_raw
        except (json.JSONDecodeError, TypeError):
            continue

        supporting_titles = []
        for item in ctx_items:
            title = item.get("title", "").strip()
            text = item.get("paragraph_text", "").strip()
            is_supporting = item.get("is_supporting", False)

            if not title or not text:
                continue

            if title not in paragraphs:
                paragraphs[title] = {
                    "text": text,
                    "is_supporting": is_supporting,
                    "question_count": 0
                }
            paragraphs[title]["question_count"] += 1

            if is_supporting:
                supporting_titles.append(title)

        if supporting_titles:
            question_entities.append({
                "question": q.get("question", "")[:200],
                "supporting_titles": supporting_titles,
                "answer": q.get("answer", q.get("expected_answer", ""))[:200]
            })

    return paragraphs, question_entities


def extract_entities_from_text(text):
    """Simple NER: extract capitalized multi-word entities from paragraph text."""
    entities = set()
    # Match capitalized words (2+ words = likely entity)
    matches = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text)
    for m in matches:
        if len(m) > 3 and m not in ("The", "This", "That", "These", "Those"):
            entities.add(m)

    # Single capitalized words that appear to be proper nouns (after period or at start)
    single = re.findall(r'(?:^|[.!?]\s+)([A-Z][a-z]{2,})\b', text)
    for s in single:
        if s not in ("The", "This", "That", "These", "Those", "However", "Although",
                      "Because", "After", "Before", "During", "Since", "While"):
            entities.add(s)

    return list(entities)


def main():
    dry_run = "--dry-run" in sys.argv
    max_paragraphs = None
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_paragraphs = int(sys.argv[i + 1])

    if not dry_run and (not NEO4J_URL or not NEO4J_PASSWORD):
        print("ERROR: NEO4J_URL and NEO4J_PASSWORD required. Run: source .env.local")
        print(f"  NEO4J_URL={NEO4J_URL!r}")
        sys.exit(1)

    print(f"Loading contexts from {DATASET}...")
    paragraphs, question_entities = extract_paragraphs(DATASET)
    print(f"  {len(paragraphs)} unique paragraphs from {len(question_entities)} multi-hop questions")

    # Load state for resume
    state = load_state()
    completed = set(state.get("completed_titles", []))

    # Filter out already-done
    pending = {t: p for t, p in paragraphs.items() if t not in completed}
    print(f"  {len(completed)} already done, {len(pending)} remaining")

    if dry_run:
        total_chars = sum(len(p["text"]) for p in pending.values())
        all_entities = set()
        for p in pending.values():
            all_entities.update(extract_entities_from_text(p["text"]))
        print(f"\n  DRY RUN: {total_chars:,} chars, ~{len(all_entities)} unique entities")
        print(f"  Paragraphs to ingest: {len(pending)}")
        return

    if max_paragraphs:
        items = list(pending.items())[:max_paragraphs]
    else:
        items = list(pending.items())

    total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
    batch_num = 0
    total_entities_created = state.get("total_entities", 0)
    errors = 0

    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        batch_num += 1

        try:
            # Prepare batch data for UNWIND operations
            para_rows = []
            entity_rows = []

            for title, para in batch:
                entities = extract_entities_from_text(para["text"])
                para_rows.append({
                    "title": title,
                    "text": para["text"][:5000],
                    "is_supporting": para["is_supporting"],
                    "qcount": para["question_count"]
                })
                for ent in entities[:10]:
                    entity_rows.append({"title": title, "name": ent})
                    total_entities_created += 1

            # Bulk create paragraphs (1 API call)
            neo4j_run(
                "UNWIND $rows AS row "
                "MERGE (p:Paragraph {title: row.title}) "
                "SET p.text = row.text, p.source = 'phase3_graph', "
                "p.is_supporting = row.is_supporting, p.question_count = row.qcount",
                {"rows": para_rows},
                NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD
            )

            # Bulk create entities + links (1 API call)
            if entity_rows:
                neo4j_run(
                    "UNWIND $rows AS row "
                    "MERGE (e:Entity {name: row.name, tenant_id: 'phase3'}) "
                    "WITH e, row "
                    "MATCH (p:Paragraph {title: row.title}) "
                    "MERGE (p)-[:HAS_ENTITY]->(e)",
                    {"rows": entity_rows},
                    NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD
                )

            # Update state
            batch_titles = [t for t, _ in batch]
            completed.update(batch_titles)
            state["completed_titles"] = list(completed)
            state["total_paragraphs"] = len(completed)
            state["total_entities"] = total_entities_created

            if batch_num % 5 == 0:
                save_state(state)

            done_pct = len(completed) / len(paragraphs) * 100
            print(f"  Batch {batch_num}/{total_batches}: +{len(batch)} paragraphs, "
                  f"{len(completed)}/{len(paragraphs)} ({done_pct:.1f}%), "
                  f"~{total_entities_created} entities")

            time.sleep(0.5)
            errors = 0

        except Exception as e:
            errors += 1
            print(f"  ERROR batch {batch_num}: {e}")
            if errors >= 3:
                print("  3 consecutive errors, stopping.")
                break
            time.sleep(2)

    # Create cross-paragraph relationships based on shared entities
    if not dry_run and len(completed) > 0:
        print("\nCreating cross-paragraph relationships...")
        try:
            neo4j_run(
                "MATCH (p1:Paragraph)-[:HAS_ENTITY]->(e:Entity)<-[:HAS_ENTITY]-(p2:Paragraph) "
                "WHERE p1.source = 'phase3_graph' AND p2.source = 'phase3_graph' "
                "AND id(p1) < id(p2) "
                "WITH p1, p2, count(e) AS shared "
                "WHERE shared >= 2 "
                "MERGE (p1)-[r:RELATED_TO]-(p2) "
                "SET r.shared_entities = shared, r.source = 'phase3_graph'",
                {},
                NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD
            )
            print("  Cross-paragraph relationships created.")
        except Exception as e:
            print(f"  WARNING: Cross-paragraph relationships failed: {e}")

    # Final save
    save_state(state)
    print(f"\nDone: {len(completed)}/{len(paragraphs)} paragraphs ingested, "
          f"~{total_entities_created} entity links")
    print(f"State saved to {STATE_FILE}")


if __name__ == "__main__":
    main()
