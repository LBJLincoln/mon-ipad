#!/usr/bin/env python3
"""
Extract entities from Phase 2 graph question contexts and seed into Neo4j.

Processes 500 graph questions (200 musique + 300 2wikimultihopqa) from
hf-1000.json, extracts entities from their context paragraphs, and
creates Entity nodes and CONNECTE relationships in Neo4j.

Uses heuristic extraction by default (fast, no API calls).
Use --llm flag for LLM-based extraction (slower but higher quality).

Usage:
    python db/populate/phase2_neo4j.py              # Heuristic (fast)
    python db/populate/phase2_neo4j.py --llm        # LLM extraction
    python db/populate/phase2_neo4j.py --reset      # Wipe Phase 2 entities first, then re-extract
    python db/populate/phase2_neo4j.py --dry-run    # Parse only
    python db/populate/phase2_neo4j.py --limit 50   # First 50 questions
"""
import json
import os
import re
import sys
import time
import base64
from datetime import datetime
from urllib import request, error

# ============================================================
# Configuration
# ============================================================
NEO4J_HOST = "38c949a2.databases.neo4j.io"
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_ENTITY_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

NEO4J_HTTP_URL = f"https://{NEO4J_HOST}/db/neo4j/query/v2"
NEO4J_AUTH = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()

DATASET_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "datasets", "phase-2", "hf-1000.json")

VALID_ENTITY_TYPES = ["Organization", "Person", "City", "Museum", "Technology", "Disease", "Entity",
                      "Location", "Event", "Concept", "Country"]
VALID_RELATIONSHIP_TYPES = [
    "A_CREE", "CAUSE_PAR", "CONNECTE", "PROTEGE_CONTRE",
    "ETUDIE", "UTILISE", "CIBLE", "EXPOSE_A",
    "VISE_A_LIMITER", "SOUS_ENSEMBLE_DE", "ETEND"
]


# ============================================================
# Neo4j HTTP helpers (reused from neo4j.py)
# ============================================================

def neo4j_execute_single(cypher, parameters=None, timeout=30):
    """Execute a single Cypher statement via Neo4j Query API v2."""
    payload = {"statement": cypher}
    if parameters:
        payload["parameters"] = parameters
    body = json.dumps(payload).encode()
    req = request.Request(
        NEO4J_HTTP_URL,
        data=body,
        headers={
            "Authorization": f"Basic {NEO4J_AUTH}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
                if result.get("errors"):
                    print(f"  Neo4j errors: {result['errors'][:2]}")
                    return None
                return result
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  Neo4j FAILED: {e}")
                return None


def neo4j_batch_merge_entities(entities, tenant_id="benchmark"):
    """Merge entity nodes in Neo4j using batched UNWIND for efficiency."""
    if not entities:
        return 0

    # Group entities by type for proper labeling
    by_type = {}
    for ent in entities:
        etype = ent.get("type", "Entity")
        if etype not in VALID_ENTITY_TYPES:
            etype = "Entity"
        by_type.setdefault(etype, []).append(ent)

    total = 0
    for etype, ents in by_type.items():
        # Batch in groups of 100
        for i in range(0, len(ents), 100):
            batch = ents[i:i + 100]
            params = {
                "entities": [
                    {
                        "name": e["name"],
                        "description": (e.get("description") or "")[:500],
                        "source": "phase2_extraction"
                    }
                    for e in batch
                ]
            }

            cypher = f"""
            UNWIND $entities AS ent
            MERGE (n:{etype} {{name: ent.name, tenant_id: '{tenant_id}'}})
            ON CREATE SET n.created_at = datetime(), n.source = ent.source
            SET n:Entity, n.description = CASE WHEN ent.description <> '' THEN ent.description ELSE n.description END
            """

            result = neo4j_execute_single(cypher, params, timeout=60)
            if result is not None:
                total += len(batch)

    return total


def neo4j_batch_merge_relationships(relationships, tenant_id="benchmark"):
    """Merge relationships in Neo4j using batched UNWIND."""
    if not relationships:
        return 0

    # Group by relationship type
    by_type = {}
    for rel in relationships:
        rtype = rel.get("type", "CONNECTE")
        if rtype not in VALID_RELATIONSHIP_TYPES:
            rtype = "CONNECTE"
        by_type.setdefault(rtype, []).append(rel)

    total = 0
    for rtype, rels in by_type.items():
        for i in range(0, len(rels), 100):
            batch = rels[i:i + 100]
            params = {
                "rels": [
                    {"source": r["source"], "target": r["target"]}
                    for r in batch
                ]
            }

            cypher = f"""
            UNWIND $rels AS rel
            MATCH (a:Entity {{name: rel.source, tenant_id: '{tenant_id}'}})
            MATCH (b:Entity {{name: rel.target, tenant_id: '{tenant_id}'}})
            MERGE (a)-[r:{rtype}]->(b)
            ON CREATE SET r.created_at = datetime(), r.source = 'phase2_extraction'
            """

            result = neo4j_execute_single(cypher, params, timeout=60)
            if result is not None:
                total += len(batch)

    return total


# ============================================================
# Entity extraction
# ============================================================

def parse_musique_context(context_str):
    """Parse MuSiQue context: JSON array of {idx, title, paragraph_text, is_supporting}."""
    if not context_str:
        return []

    try:
        docs = json.loads(context_str) if isinstance(context_str, str) else context_str
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(docs, list):
        return []

    result = []
    for doc in docs:
        if isinstance(doc, dict):
            result.append({
                "title": doc.get("title", ""),
                "text": doc.get("paragraph_text", doc.get("text", "")),
                "is_supporting": doc.get("is_supporting", False),
            })
    return result


def parse_2wiki_context(context_str):
    """Parse 2WikiMultiHopQA context: may be JSON array or dict format."""
    if not context_str:
        return []

    try:
        context = json.loads(context_str) if isinstance(context_str, str) else context_str
    except (json.JSONDecodeError, TypeError):
        return []

    docs = []
    if isinstance(context, list):
        for item in context:
            if isinstance(item, dict):
                docs.append({
                    "title": item.get("title", ""),
                    "text": item.get("paragraph_text", item.get("text", "")),
                    "is_supporting": item.get("is_supporting", False),
                })
            elif isinstance(item, list) and len(item) >= 2:
                title = item[0] if isinstance(item[0], str) else str(item[0])
                sentences = item[1] if isinstance(item[1], list) else [str(item[1])]
                docs.append({
                    "title": title,
                    "text": " ".join(str(s) for s in sentences),
                    "is_supporting": False,
                })
    elif isinstance(context, dict):
        titles = context.get("title", [])
        sentences = context.get("sentences", [])
        for i, title in enumerate(titles):
            text = " ".join(sentences[i]) if i < len(sentences) and isinstance(sentences[i], list) else ""
            docs.append({"title": str(title), "text": text, "is_supporting": False})

    return docs


def extract_entities_heuristic(question, docs):
    """Extract entities from document titles and text using heuristics."""
    entities = []
    relationships = []
    seen_names = set()

    for doc in docs:
        title = doc.get("title", "").strip()
        if not title or title in seen_names or len(title) < 2:
            continue
        seen_names.add(title)

        entity_type = classify_entity_type(title)
        entities.append({
            "name": title,
            "type": entity_type,
            "description": doc.get("text", "")[:300]
        })

    # Also extract named entities from supporting fact texts
    for doc in docs:
        if not doc.get("is_supporting"):
            continue
        text = doc.get("text", "")
        # Extract capitalized multi-word names (likely entities)
        names = extract_names_from_text(text)
        for name in names:
            if name not in seen_names and len(name) > 2:
                seen_names.add(name)
                entities.append({
                    "name": name,
                    "type": classify_entity_type(name),
                    "description": ""
                })

    # Create CONNECTE relationships between entities from the same question
    entity_names = [e["name"] for e in entities[:20]]  # limit to avoid quadratic explosion
    for i, name1 in enumerate(entity_names):
        for name2 in entity_names[i + 1:i + 5]:  # connect to next 4 only
            relationships.append({
                "source": name1,
                "target": name2,
                "type": "CONNECTE"
            })

    return {"entities": entities, "relationships": relationships}


def classify_entity_type(name):
    """Classify an entity name into a type using heuristics."""
    name_lower = name.lower()

    # Organization patterns
    if any(w in name_lower for w in ["university", "college", "inc", "corp", "company",
                                      "group", "foundation", "institute", "academy",
                                      "association", "church", "army", "navy",
                                      "party", "league", "council", "committee"]):
        return "Organization"

    # Museum/Cultural patterns
    if any(w in name_lower for w in ["museum", "gallery", "library", "theater", "theatre"]):
        return "Museum"

    # Location/City patterns
    if any(w in name_lower for w in ["city", "town", "village", "prefecture",
                                      "district", "province", "county", "state of",
                                      "republic of", "kingdom of"]):
        return "City"

    # Country patterns
    if any(w in name_lower for w in ["united states", "united kingdom", "soviet union"]):
        return "Country"

    # Disease patterns
    if any(w in name_lower for w in ["disease", "syndrome", "virus", "cancer",
                                      "fever", "plague", "infection"]):
        return "Disease"

    # Technology patterns
    if any(w in name_lower for w in ["technology", "software", "algorithm",
                                      "protocol", "engine", "system"]):
        return "Technology"

    # Event patterns
    if any(w in name_lower for w in ["war", "battle", "revolution", "treaty",
                                      "election", "championship", "olympics"]):
        return "Event"

    # Person name heuristic (2-4 capitalized words)
    words = name.split()
    if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w and w[0].isalpha()):
        return "Person"

    # Single word starting with capital - likely a proper noun (place or person)
    if len(words) == 1 and name[0].isupper():
        return "Entity"

    return "Entity"


def extract_names_from_text(text):
    """Extract likely entity names from text using regex patterns."""
    names = set()

    # Pattern: sequences of 2-5 capitalized words (likely proper nouns)
    pattern = r'\b([A-Z][a-z]+(?:\s+(?:of|the|and|de|von|van|la|el|le|du|des|di|da)\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
    for match in re.finditer(pattern, text):
        name = match.group(1).strip()
        # Filter out common false positives
        if name not in {"The SpongeBob", "In The", "The United", "It Was"}:
            if len(name) > 3 and len(name) < 60:
                names.add(name)

    return names


def extract_entities_llm(question, docs):
    """Use LLM to extract entities and relationships from question + context."""
    if not OPENROUTER_API_KEY:
        return extract_entities_heuristic(question, docs)

    # Build context from supporting documents first, then others
    supporting = [d for d in docs if d.get("is_supporting")]
    others = [d for d in docs if not d.get("is_supporting")]
    selected = (supporting + others)[:8]

    context_str = ""
    for doc in selected:
        title = doc.get("title", "Unknown")
        text = doc.get("text", "")[:400]
        context_str += f"[{title}]: {text}\n"

    prompt = f"""Extract entities and relationships from this multi-hop question and its documents.

QUESTION: {question}

DOCUMENTS:
{context_str[:4000]}

Return JSON with:
1. "entities": [{{"name": str, "type": "Person"|"Organization"|"City"|"Country"|"Event"|"Technology"|"Disease"|"Entity", "description": str}}]
2. "relationships": [{{"source": str, "target": str, "type": "CONNECTE"|"A_CREE"|"CAUSE_PAR"}}]

Rules:
- Extract ALL named entities (people, places, organizations, concepts)
- Focus on entities that help answer the question
- Create relationships between co-mentioned entities
- Max 25 entities, 30 relationships
- Return ONLY valid JSON."""

    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "Extract structured knowledge graph data. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }).encode()

    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mon-ipad",
            "X-Title": "RAG-Phase2-Entity-Extraction"
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            data = json.loads(content)
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            for e in entities:
                if e.get("type") not in VALID_ENTITY_TYPES:
                    e["type"] = "Entity"
            for r in relationships:
                if r.get("type") not in VALID_RELATIONSHIP_TYPES:
                    r["type"] = "CONNECTE"
            return {"entities": entities, "relationships": relationships}
    except Exception as e:
        print(f"    LLM error: {e}")
        return extract_entities_heuristic(question, docs)


# ============================================================
# Main pipeline
# ============================================================

def reset_phase2_entities(dry_run=False):
    """Delete all Phase 2 extracted entities and relationships from Neo4j."""
    if dry_run:
        print("  [DRY RUN] Would delete all nodes/rels where source='phase2_extraction'")
        return True

    print("  Deleting Phase 2 relationships...")
    r1 = neo4j_execute_single(
        "MATCH ()-[r]->() WHERE r.source = 'phase2_extraction' DELETE r",
        timeout=120
    )
    if r1:
        print("    Relationships deleted.")

    print("  Deleting Phase 2 entity nodes...")
    # Delete in batches to avoid timeout on large graphs
    deleted = 0
    for _ in range(50):  # max 50 batches of 1000
        r2 = neo4j_execute_single(
            "MATCH (n:Entity) WHERE n.source = 'phase2_extraction' "
            "WITH n LIMIT 1000 DETACH DELETE n RETURN count(*) as deleted",
            timeout=60
        )
        if r2 and r2.get("data"):
            data = r2["data"]
            # Parse count from response
            batch_count = 0
            if isinstance(data, dict) and "values" in data:
                batch_count = data["values"][0] if data["values"] else 0
            elif isinstance(data, list) and len(data) > 0:
                row = data[0]
                if isinstance(row, dict):
                    batch_count = row.get("deleted", row.get("values", [0])[0] if row.get("values") else 0)
                elif isinstance(row, list):
                    batch_count = row[0] if row else 0
            deleted += batch_count if isinstance(batch_count, int) else 0
            if batch_count == 0:
                break
        else:
            break

    print(f"    Deleted ~{deleted} Phase 2 entity nodes.")
    return True


def main():
    use_llm = "--llm" in sys.argv
    dry_run = "--dry-run" in sys.argv
    do_reset = "--reset" in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    print("=" * 60)
    print("PHASE 2 NEO4J ENTITY EXTRACTION")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Mode: {'LLM' if use_llm else 'Heuristic'} | {'DRY RUN' if dry_run else 'LIVE'}{' + RESET' if do_reset else ''}")
    if limit:
        print(f"Limit: {limit} questions")
    print("=" * 60)

    if not dry_run and not NEO4J_PASSWORD:
        print("ERROR: NEO4J_PASSWORD not set")
        sys.exit(1)

    # Step 0: Reset if requested
    if do_reset:
        print("\n0. Resetting Phase 2 entities (--reset)...")
        reset_phase2_entities(dry_run)

    # Step 1: Load questions
    print("\n1. Loading Phase 2 graph questions...")
    dataset_path = os.path.abspath(DATASET_FILE)
    with open(dataset_path) as f:
        data = json.load(f)

    graph_questions = [
        q for q in data["questions"]
        if q["rag_target"] == "graph"
    ]
    if limit:
        graph_questions = graph_questions[:limit]

    musique_count = sum(1 for q in graph_questions if q["dataset_name"] == "musique")
    wiki2_count = sum(1 for q in graph_questions if q["dataset_name"] == "2wikimultihopqa")
    print(f"   Total graph questions: {len(graph_questions)}")
    print(f"   musique: {musique_count}, 2wikimultihopqa: {wiki2_count}")

    # Step 2: Extract entities
    print(f"\n2. Extracting entities ({'LLM' if use_llm else 'heuristic'})...")
    all_entities = []
    all_relationships = []
    seen_names = set()
    stats = {"questions_processed": 0, "entities_extracted": 0, "relationships_extracted": 0}

    for i, q in enumerate(graph_questions):
        if i % 100 == 0:
            print(f"   Processing {i + 1}/{len(graph_questions)}...")

        # Parse context
        context = q.get("context", "")
        if q["dataset_name"] == "musique":
            docs = parse_musique_context(context)
        else:
            docs = parse_2wiki_context(context)

        if not docs:
            continue

        # Extract
        if use_llm:
            extracted = extract_entities_llm(q["question"], docs)
            time.sleep(0.3)  # rate limiting
        else:
            extracted = extract_entities_heuristic(q["question"], docs)

        # Deduplicate entities
        for e in extracted.get("entities", []):
            name = e["name"].strip()
            if name and name not in seen_names:
                seen_names.add(name)
                all_entities.append(e)

        all_relationships.extend(extracted.get("relationships", []))
        stats["questions_processed"] += 1

    stats["entities_extracted"] = len(all_entities)
    stats["relationships_extracted"] = len(all_relationships)

    print(f"   Questions processed: {stats['questions_processed']}")
    print(f"   Unique entities: {stats['entities_extracted']}")
    print(f"   Relationships: {stats['relationships_extracted']}")

    # Entity type distribution
    type_dist = {}
    for e in all_entities:
        t = e.get("type", "Entity")
        type_dist[t] = type_dist.get(t, 0) + 1
    print(f"   Entity types: {json.dumps(type_dist, indent=2)}")

    if dry_run:
        print("\n3. [DRY RUN] Would create entities and relationships in Neo4j")
        print(f"   Sample entities (first 20):")
        for e in all_entities[:20]:
            print(f"     [{e['type']}] {e['name']}")
        print(f"\n   Sample relationships (first 10):")
        for r in all_relationships[:10]:
            print(f"     {r['source']} --[{r['type']}]--> {r['target']}")
    else:
        # Step 3: Write to Neo4j
        print("\n3. Creating Neo4j indexes...")
        indexes = [
            "CREATE INDEX phase2_entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
            "CREATE INDEX phase2_entity_tenant IF NOT EXISTS FOR (n:Entity) ON (n.tenant_id)",
        ]
        for idx in indexes:
            neo4j_execute_single(idx, timeout=60)

        print(f"\n4. Writing {len(all_entities)} entities to Neo4j...")
        entity_count = neo4j_batch_merge_entities(all_entities)
        print(f"   Created/merged: {entity_count} entity nodes")

        print(f"\n5. Writing {len(all_relationships)} relationships to Neo4j...")
        rel_count = neo4j_batch_merge_relationships(all_relationships)
        print(f"   Created/merged: {rel_count} relationships")

        # Verify
        print(f"\n6. Verifying Neo4j graph...")
        result = neo4j_execute_single(
            "MATCH (n:Entity) WHERE n.source = 'phase2_extraction' RETURN count(n) as nodes"
        )
        if result and result.get("data"):
            print(f"   Phase 2 entities: {result['data']}")

        result2 = neo4j_execute_single(
            "MATCH ()-[r]->() WHERE r.source = 'phase2_extraction' RETURN count(r) as rels"
        )
        if result2 and result2.get("data"):
            print(f"   Phase 2 relationships: {result2['data']}")

        result3 = neo4j_execute_single("MATCH (n:Entity) RETURN count(n) as total_nodes")
        if result3 and result3.get("data"):
            print(f"   Total entity nodes: {result3['data']}")

    # Save extraction log
    log_path = os.path.join(os.path.dirname(__file__), "..", "..", "logs",
                            "db-snapshots", f"phase2-neo4j-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "mode": "llm" if use_llm else "heuristic",
            "dry_run": dry_run,
            "stats": stats,
            "type_distribution": type_dist,
            "sample_entities": [{"name": e["name"], "type": e["type"]} for e in all_entities[:50]],
        }, f, indent=2)
    print(f"\n   Log saved: {log_path}")

    print(f"\n{'='*60}")
    print("PHASE 2 NEO4J EXTRACTION COMPLETE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
