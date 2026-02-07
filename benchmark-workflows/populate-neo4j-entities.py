#!/usr/bin/env python3
"""
Populate Neo4j with Entity nodes and relationships for Graph RAG.

Extracts entities from HotpotQA/2WikiMultiHopQA context documents stored
in Supabase and creates a proper knowledge graph with:
- Entity nodes: Organization, Person, City, Museum, Technology, Disease + generic Entity
- Typed relationships: A_CREE, CONNECTE, CAUSE_PAR, PROTEGE_CONTRE, ETUDIE, UTILISE, etc.
- Multi-tenancy: tenant_id on all nodes

This is what the WF2 Graph RAG V3.3 workflow expects to traverse.
"""
import json
import os
import sys
import time
import base64
import hashlib
from datetime import datetime
from urllib import request, error, parse

# ============================================================
# Configuration
# ============================================================
# Use Supabase Transaction Pooler (IPv4 compatible, port 6543)
SUPABASE_CONN = f"postgresql://postgres.ayqviqmxifzmhphiqfmj:{os.environ['SUPABASE_PASSWORD']}@aws-1-eu-west-1.pooler.supabase.com:6543/postgres"
NEO4J_HOST = "38c949a2.databases.neo4j.io"
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_ENTITY_MODEL", "google/gemini-2.0-flash-001")

# Neo4j Aura Query API v2 (port 443, works through firewalls)
NEO4J_HTTP_URL = f"https://{NEO4J_HOST}/db/neo4j/query/v2"
NEO4J_AUTH = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()

# Entity types expected by WF2 Graph RAG
VALID_ENTITY_TYPES = ["Organization", "Person", "City", "Museum", "Technology", "Disease", "Entity"]

# Relationship types expected by WF2 Graph RAG (with weights)
VALID_RELATIONSHIP_TYPES = [
    "A_CREE", "CAUSE_PAR", "CONNECTE", "PROTEGE_CONTRE",
    "ETUDIE", "UTILISE", "CIBLE", "EXPOSE_A",
    "VISE_A_LIMITER", "SOUS_ENSEMBLE_DE", "ETEND"
]

# ============================================================
# Neo4j HTTP helpers
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
                print(f"  Neo4j retry {attempt+1}: {e}")
                time.sleep(2 ** attempt)
            else:
                print(f"  Neo4j FAILED: {e}")
                return None


def neo4j_execute(statements, timeout=30):
    """Execute multiple Cypher statements sequentially via Query API v2."""
    last_result = None
    for stmt in statements:
        cypher = stmt if isinstance(stmt, str) else stmt.get("statement", "")
        params = stmt.get("parameters") if isinstance(stmt, dict) else None
        result = neo4j_execute_single(cypher, params, timeout)
        if result is None:
            return None
        last_result = result
    return last_result or {"ok": True}


def neo4j_setup_constraints():
    """Create indexes and constraints for the entity graph."""
    indexes = [
        "CREATE INDEX entity_name IF NOT EXISTS FOR (n:Entity) ON (n.name)",
        "CREATE INDEX entity_tenant IF NOT EXISTS FOR (n:Entity) ON (n.tenant_id)",
        "CREATE INDEX person_name IF NOT EXISTS FOR (n:Person) ON (n.name)",
        "CREATE INDEX org_name IF NOT EXISTS FOR (n:Organization) ON (n.name)",
        "CREATE INDEX city_name IF NOT EXISTS FOR (n:City) ON (n.name)",
        "CREATE INDEX museum_name IF NOT EXISTS FOR (n:Museum) ON (n.name)",
        "CREATE INDEX tech_name IF NOT EXISTS FOR (n:Technology) ON (n.name)",
        "CREATE INDEX disease_name IF NOT EXISTS FOR (n:Disease) ON (n.name)",
    ]
    for idx_cypher in indexes:
        result = neo4j_execute_single(idx_cypher, timeout=60)
        if result is None:
            print(f"  WARNING: Failed to create index: {idx_cypher[:50]}...")
    print("  Neo4j indexes created/verified")
    return True


def neo4j_create_entities(entities, tenant_id="benchmark"):
    """Create Entity nodes in Neo4j with proper labels."""
    statements = []
    for ent in entities:
        name = ent["name"].replace('"', '\\"').replace("'", "\\'")
        label = ent.get("type", "Entity")
        if label not in VALID_ENTITY_TYPES:
            label = "Entity"

        # Use MERGE to avoid duplicates, add Entity label always
        cypher = f"""
        MERGE (n:{label} {{name: "{name}", tenant_id: "{tenant_id}"}})
        ON CREATE SET n.created_at = datetime(), n.source = "hotpotqa_extraction"
        SET n:Entity
        """
        if ent.get("description"):
            desc = ent["description"].replace('"', '\\"')[:500]
            cypher += f', n.description = "{desc}"'

        statements.append({"statement": cypher})

    if not statements:
        return 0

    # Batch in groups of 50
    total = 0
    for i in range(0, len(statements), 50):
        batch = statements[i:i+50]
        result = neo4j_execute(batch)
        if result is not None:
            total += len(batch)
    return total


def neo4j_create_relationships(relationships, tenant_id="benchmark"):
    """Create relationships between entity nodes."""
    statements = []
    for rel in relationships:
        src = rel["source"].replace('"', '\\"').replace("'", "\\'")
        tgt = rel["target"].replace('"', '\\"').replace("'", "\\'")
        rel_type = rel.get("type", "CONNECTE")
        if rel_type not in VALID_RELATIONSHIP_TYPES:
            rel_type = "CONNECTE"

        cypher = f"""
        MATCH (a:Entity {{name: "{src}", tenant_id: "{tenant_id}"}})
        MATCH (b:Entity {{name: "{tgt}", tenant_id: "{tenant_id}"}})
        MERGE (a)-[r:{rel_type}]->(b)
        ON CREATE SET r.created_at = datetime(), r.source = "hotpotqa_extraction"
        """
        statements.append({"statement": cypher})

    if not statements:
        return 0

    total = 0
    for i in range(0, len(statements), 50):
        batch = statements[i:i+50]
        result = neo4j_execute(batch)
        if result is not None:
            total += len(batch)
    return total


# ============================================================
# Entity extraction via LLM
# ============================================================

def extract_entities_llm(question, context_docs):
    """Use LLM to extract entities and relationships from question + context."""
    if not OPENROUTER_API_KEY:
        return extract_entities_heuristic(question, context_docs)

    # Build context string from documents
    context_str = ""
    for doc in context_docs[:5]:  # limit to 5 docs to stay within token limits
        title = doc.get("title", "Unknown")
        text = doc.get("text", "")
        context_str += f"Document: {title}\n{text}\n\n"

    prompt = f"""Extract entities and relationships from this question and its supporting documents.

QUESTION: {question}

DOCUMENTS:
{context_str[:3000]}

Return a JSON object with:
1. "entities": array of objects with "name" (string), "type" (one of: Person, Organization, City, Museum, Technology, Disease, Entity), and optional "description" (short string)
2. "relationships": array of objects with "source" (entity name), "target" (entity name), and "type" (one of: A_CREE, CAUSE_PAR, CONNECTE, PROTEGE_CONTRE, ETUDIE, UTILISE, CIBLE, EXPOSE_A, VISE_A_LIMITER, SOUS_ENSEMBLE_DE, ETEND)

Guidelines:
- Extract ALL named entities from the documents (people, places, organizations, technologies, etc.)
- Create relationships between entities that are mentioned together or have clear connections
- Use CONNECTE for general associations
- Use A_CREE for creation/founding relationships
- Use CAUSE_PAR for causal relationships
- Entity names should be clean (no extra quotes, parentheses, etc.)
- Maximum 20 entities and 30 relationships per extraction

Return ONLY valid JSON, no explanation."""

    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You extract structured knowledge graph data from text. Always return valid JSON."},
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
            "X-Title": "RAG-Benchmark-Entity-Extraction"
        },
        method="POST"
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            # Strip markdown code blocks if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            data = json.loads(content)
            entities = data.get("entities", [])
            relationships = data.get("relationships", [])
            # Validate entity types
            for e in entities:
                if e.get("type") not in VALID_ENTITY_TYPES:
                    e["type"] = "Entity"
            for r in relationships:
                if r.get("type") not in VALID_RELATIONSHIP_TYPES:
                    r["type"] = "CONNECTE"
            return {"entities": entities, "relationships": relationships}
    except Exception as e:
        print(f"    LLM extraction error: {e}")
        return extract_entities_heuristic(question, context_docs)


def extract_entities_heuristic(question, context_docs):
    """Fallback: extract entities from document titles (always available)."""
    entities = []
    relationships = []
    seen_names = set()

    for doc in context_docs:
        title = doc.get("title", "").strip()
        if not title or title in seen_names:
            continue
        seen_names.add(title)

        # Heuristic type detection based on common patterns
        entity_type = "Entity"
        title_lower = title.lower()
        if any(w in title_lower for w in ["university", "inc", "corp", "company", "group", "foundation", "institute"]):
            entity_type = "Organization"
        elif any(w in title_lower for w in ["museum", "gallery", "library"]):
            entity_type = "Museum"
        elif any(w in title_lower for w in ["city", "town", "village", "prefecture"]):
            entity_type = "City"
        elif any(w in title_lower for w in ["disease", "syndrome", "virus", "cancer"]):
            entity_type = "Disease"
        elif any(w in title_lower for w in ["technology", "software", "algorithm", "protocol"]):
            entity_type = "Technology"
        else:
            # If it looks like a person name (2-3 words, capitalized)
            words = title.split()
            if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w):
                entity_type = "Person"

        entities.append({
            "name": title,
            "type": entity_type,
            "description": doc.get("text", "")[:200]
        })

    # Create CONNECTE relationships between entities in same question context
    entity_names = [e["name"] for e in entities]
    for i, name1 in enumerate(entity_names):
        for name2 in entity_names[i+1:]:
            relationships.append({
                "source": name1,
                "target": name2,
                "type": "CONNECTE"
            })

    return {"entities": entities, "relationships": relationships}


# ============================================================
# Supabase data fetching
# ============================================================

def fetch_questions_with_context(limit=1000, offset=0):
    """Fetch multi-hop questions with context from Supabase."""
    import subprocess

    sql = f"""SELECT dataset_name, item_index, question, expected_answer, context, supporting_facts
    FROM benchmark_datasets
    WHERE category IN ('multi_hop_qa', 'rag_benchmark')
      AND context IS NOT NULL
      AND tenant_id = 'benchmark'
    ORDER BY dataset_name, item_index
    LIMIT {limit} OFFSET {offset};"""

    result = subprocess.run(
        ["psql", SUPABASE_CONN, "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True, timeout=30
    )

    if result.returncode != 0:
        print(f"  Supabase error: {result.stderr[:300]}")
        return []

    rows = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            context = None
            if len(parts) > 4 and parts[4]:
                try:
                    context = json.loads(parts[4])
                except json.JSONDecodeError:
                    context = parts[4]

            rows.append({
                "dataset_name": parts[0],
                "item_index": int(parts[1]),
                "question": parts[2],
                "expected_answer": parts[3],
                "context": context,
                "supporting_facts": json.loads(parts[5]) if len(parts) > 5 and parts[5] else None
            })
        except (ValueError, IndexError) as e:
            continue

    return rows


def parse_context_docs(context):
    """Parse HotpotQA/2WikiMultiHopQA context into a list of {title, text} dicts."""
    docs = []
    if context is None:
        return docs

    if isinstance(context, str):
        try:
            context = json.loads(context)
        except json.JSONDecodeError:
            return docs

    # HotpotQA format: list of [title, [sentence1, sentence2, ...]]
    if isinstance(context, list):
        for item in context:
            if isinstance(item, list) and len(item) >= 2:
                title = item[0] if isinstance(item[0], str) else str(item[0])
                sentences = item[1] if isinstance(item[1], list) else [str(item[1])]
                docs.append({
                    "title": title,
                    "text": " ".join(str(s) for s in sentences)
                })
            elif isinstance(item, dict):
                # MuSiQue format: {idx, title, paragraph_text}
                docs.append({
                    "title": item.get("title", "Unknown"),
                    "text": item.get("paragraph_text", item.get("text", ""))
                })

    # 2WikiMultiHopQA format: {title: [...], sentences: [[...], [...]]}
    elif isinstance(context, dict):
        titles = context.get("title", [])
        sentences = context.get("sentences", [])
        for i, title in enumerate(titles):
            text = " ".join(sentences[i]) if i < len(sentences) and isinstance(sentences[i], list) else ""
            docs.append({"title": str(title), "text": text})

    return docs


# ============================================================
# Main pipeline
# ============================================================

def populate_from_contexts():
    """Main: extract entities from all multi-hop question contexts and load into Neo4j."""
    print("=" * 60)
    print("NEO4J ENTITY GRAPH POPULATION")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Setup constraints
    print("\n1. Setting up Neo4j indexes...")
    neo4j_setup_constraints()

    # Fetch questions with context from Supabase
    print("\n2. Fetching multi-hop questions from Supabase...")
    all_questions = []
    offset = 0
    batch_size = 500

    while True:
        batch = fetch_questions_with_context(limit=batch_size, offset=offset)
        if not batch:
            break
        all_questions.extend(batch)
        print(f"   Fetched {len(all_questions)} questions so far...")
        offset += batch_size
        if len(batch) < batch_size:
            break

    print(f"   Total questions with context: {len(all_questions)}")

    if not all_questions:
        print("\n  WARNING: No questions with context found in Supabase.")
        print("  Falling back to generating entities from known datasets...")
        populate_from_known_entities()
        return

    # Extract entities and create graph
    print(f"\n3. Extracting entities and creating graph...")
    total_entities = 0
    total_relationships = 0
    all_entity_names = set()

    for i, q in enumerate(all_questions):
        if i % 50 == 0:
            print(f"   Processing question {i+1}/{len(all_questions)}...")

        # Parse context documents
        docs = parse_context_docs(q["context"])
        if not docs:
            continue

        # Extract entities
        extracted = extract_entities_llm(q["question"], docs)

        entities = extracted.get("entities", [])
        relationships = extracted.get("relationships", [])

        if entities:
            count = neo4j_create_entities(entities)
            total_entities += count
            for e in entities:
                all_entity_names.add(e["name"])

        if relationships:
            count = neo4j_create_relationships(relationships)
            total_relationships += count

        # Rate limit for LLM calls
        if OPENROUTER_API_KEY and i % 10 == 9:
            time.sleep(0.5)

    print(f"\n   Entities created: {total_entities}")
    print(f"   Relationships created: {total_relationships}")
    print(f"   Unique entity names: {len(all_entity_names)}")

    # Verify
    print("\n4. Verifying Neo4j graph...")
    verify = neo4j_execute([
        {"statement": "MATCH (n:Entity) RETURN labels(n) as labels, count(*) as cnt"},
        {"statement": "MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as cnt ORDER BY cnt DESC LIMIT 15"}
    ])
    if verify and verify.get("results"):
        for r in verify["results"]:
            for row in r.get("data", []):
                print(f"   {row.get('row', row)}")

    print(f"\n{'='*60}")
    print("NEO4J POPULATION COMPLETE")
    print(f"{'='*60}")


def populate_from_known_entities():
    """Fallback: create a rich entity graph from curated knowledge base.

    Creates entities and relationships typical of what HotpotQA/2WikiMultiHopQA
    questions ask about: historical figures, organizations, cities, etc.
    """
    print("\n  Creating curated entity graph...")

    # Curated entities spanning typical multi-hop QA topics
    entities = [
        # People - Scientists & Inventors
        {"name": "Albert Einstein", "type": "Person", "description": "Theoretical physicist, developed theory of relativity"},
        {"name": "Marie Curie", "type": "Person", "description": "Physicist and chemist, pioneer in radioactivity research"},
        {"name": "Nikola Tesla", "type": "Person", "description": "Inventor, electrical and mechanical engineer"},
        {"name": "Thomas Edison", "type": "Person", "description": "Inventor and businessman, developed the phonograph and light bulb"},
        {"name": "Isaac Newton", "type": "Person", "description": "Mathematician, physicist, astronomer, author of Principia Mathematica"},
        {"name": "Charles Darwin", "type": "Person", "description": "Naturalist, developed the theory of evolution by natural selection"},
        {"name": "Alan Turing", "type": "Person", "description": "Mathematician and computer scientist, father of theoretical computer science"},
        {"name": "Ada Lovelace", "type": "Person", "description": "Mathematician, first computer programmer"},
        {"name": "Alexander Fleming", "type": "Person", "description": "Bacteriologist, discovered penicillin"},
        {"name": "Louis Pasteur", "type": "Person", "description": "Microbiologist and chemist, developed pasteurization"},

        # People - Leaders & Historical Figures
        {"name": "Winston Churchill", "type": "Person", "description": "British Prime Minister during World War II"},
        {"name": "Franklin D. Roosevelt", "type": "Person", "description": "32nd President of the United States"},
        {"name": "Napoleon Bonaparte", "type": "Person", "description": "French military leader and Emperor"},
        {"name": "Mahatma Gandhi", "type": "Person", "description": "Leader of Indian independence movement"},
        {"name": "Nelson Mandela", "type": "Person", "description": "Anti-apartheid activist, first Black president of South Africa"},
        {"name": "Abraham Lincoln", "type": "Person", "description": "16th President of the United States, abolished slavery"},
        {"name": "Cleopatra", "type": "Person", "description": "Last active ruler of the Ptolemaic Kingdom of Egypt"},
        {"name": "Leonardo da Vinci", "type": "Person", "description": "Italian polymath: painter, sculptor, architect, scientist, inventor"},

        # People - Artists & Writers
        {"name": "William Shakespeare", "type": "Person", "description": "English playwright and poet"},
        {"name": "Wolfgang Amadeus Mozart", "type": "Person", "description": "Prolific and influential composer of the Classical period"},
        {"name": "Pablo Picasso", "type": "Person", "description": "Spanish painter and sculptor, co-founder of Cubism"},
        {"name": "Vincent van Gogh", "type": "Person", "description": "Dutch Post-Impressionist painter"},
        {"name": "Frida Kahlo", "type": "Person", "description": "Mexican painter known for self-portraits"},
        {"name": "Mark Twain", "type": "Person", "description": "American author, humorist, and lecturer"},

        # People - Film Directors
        {"name": "Steven Spielberg", "type": "Person", "description": "American film director and producer"},
        {"name": "Alfred Hitchcock", "type": "Person", "description": "English filmmaker, Master of Suspense"},
        {"name": "Stanley Kubrick", "type": "Person", "description": "American film director and producer"},
        {"name": "Martin Scorsese", "type": "Person", "description": "American film director and producer"},
        {"name": "Frank Tuttle", "type": "Person", "description": "American film director"},
        {"name": "Sergei Yutkevich", "type": "Person", "description": "Soviet film director"},

        # Organizations
        {"name": "NASA", "type": "Organization", "description": "National Aeronautics and Space Administration"},
        {"name": "European Space Agency", "type": "Organization", "description": "Intergovernmental organization of 22 member states"},
        {"name": "MIT", "type": "Organization", "description": "Massachusetts Institute of Technology"},
        {"name": "Stanford University", "type": "Organization", "description": "Private research university in Stanford, California"},
        {"name": "Harvard University", "type": "Organization", "description": "Private Ivy League research university"},
        {"name": "University of Cambridge", "type": "Organization", "description": "Collegiate research university in Cambridge, England"},
        {"name": "University of Oxford", "type": "Organization", "description": "Collegiate research university in Oxford, England"},
        {"name": "CERN", "type": "Organization", "description": "European Organization for Nuclear Research"},
        {"name": "World Health Organization", "type": "Organization", "description": "Specialized agency of the United Nations for international public health"},
        {"name": "United Nations", "type": "Organization", "description": "International organization for cooperation among sovereign states"},
        {"name": "Nobel Foundation", "type": "Organization", "description": "Private institution managing the finances and administration of the Nobel Prizes"},
        {"name": "Royal Society", "type": "Organization", "description": "Learned society and the United Kingdom national academy of sciences"},
        {"name": "Apple Inc", "type": "Organization", "description": "American multinational technology company"},
        {"name": "Google", "type": "Organization", "description": "American multinational technology company specializing in search"},
        {"name": "Microsoft", "type": "Organization", "description": "American multinational technology corporation"},

        # Cities
        {"name": "London", "type": "City", "description": "Capital of England and the United Kingdom"},
        {"name": "Paris", "type": "City", "description": "Capital of France"},
        {"name": "New York City", "type": "City", "description": "Most populous city in the United States"},
        {"name": "Berlin", "type": "City", "description": "Capital of Germany"},
        {"name": "Tokyo", "type": "City", "description": "Capital of Japan"},
        {"name": "Rome", "type": "City", "description": "Capital city of Italy"},
        {"name": "Washington D.C.", "type": "City", "description": "Capital of the United States"},
        {"name": "Moscow", "type": "City", "description": "Capital of Russia"},
        {"name": "Beijing", "type": "City", "description": "Capital of China"},
        {"name": "Cairo", "type": "City", "description": "Capital of Egypt"},
        {"name": "Vienna", "type": "City", "description": "Capital of Austria"},
        {"name": "Salzburg", "type": "City", "description": "City in Austria, birthplace of Mozart"},
        {"name": "Florence", "type": "City", "description": "City in central Italy, birthplace of the Renaissance"},
        {"name": "Zurich", "type": "City", "description": "City in Switzerland, global financial center"},
        {"name": "Princeton", "type": "City", "description": "Municipality in New Jersey, home of Princeton University"},

        # Museums
        {"name": "Louvre Museum", "type": "Museum", "description": "World's largest art museum in Paris"},
        {"name": "British Museum", "type": "Museum", "description": "Museum of human history and culture in London"},
        {"name": "Metropolitan Museum of Art", "type": "Museum", "description": "Largest art museum in the Americas in New York City"},
        {"name": "Smithsonian Institution", "type": "Museum", "description": "Group of museums and education centers in Washington D.C."},
        {"name": "Museo del Prado", "type": "Museum", "description": "National art museum in Madrid, Spain"},

        # Technologies
        {"name": "Internet", "type": "Technology", "description": "Global system of interconnected computer networks"},
        {"name": "World Wide Web", "type": "Technology", "description": "Information system enabling documents to be connected via hypertext links"},
        {"name": "Artificial Intelligence", "type": "Technology", "description": "Intelligence demonstrated by machines"},
        {"name": "Nuclear Energy", "type": "Technology", "description": "Energy released during nuclear fission or fusion"},
        {"name": "Theory of Relativity", "type": "Technology", "description": "Einstein's theory of physics describing gravity and spacetime"},
        {"name": "Penicillin", "type": "Technology", "description": "Group of antibiotics derived from Penicillium fungi"},
        {"name": "Vaccination", "type": "Technology", "description": "Administration of an agent to stimulate immune response"},
        {"name": "Electricity", "type": "Technology", "description": "Set of physical phenomena associated with electric charge"},
        {"name": "Telephone", "type": "Technology", "description": "Telecommunications device for transmitting speech"},
        {"name": "Steam Engine", "type": "Technology", "description": "Heat engine performing mechanical work using steam"},

        # Diseases
        {"name": "COVID-19", "type": "Disease", "description": "Infectious disease caused by the SARS-CoV-2 virus"},
        {"name": "Influenza", "type": "Disease", "description": "Infectious disease caused by influenza viruses"},
        {"name": "Cancer", "type": "Disease", "description": "Group of diseases involving abnormal cell growth"},
        {"name": "Tuberculosis", "type": "Disease", "description": "Infectious disease caused by Mycobacterium tuberculosis"},
        {"name": "Malaria", "type": "Disease", "description": "Infectious disease caused by Plasmodium parasites"},
    ]

    # Relationships based on known connections
    relationships = [
        # Scientific discoveries
        {"source": "Albert Einstein", "target": "Theory of Relativity", "type": "A_CREE"},
        {"source": "Albert Einstein", "target": "Princeton", "type": "CONNECTE"},
        {"source": "Albert Einstein", "target": "Nobel Foundation", "type": "CONNECTE"},
        {"source": "Marie Curie", "target": "Nobel Foundation", "type": "CONNECTE"},
        {"source": "Marie Curie", "target": "Paris", "type": "CONNECTE"},
        {"source": "Marie Curie", "target": "Cancer", "type": "ETUDIE"},
        {"source": "Alexander Fleming", "target": "Penicillin", "type": "A_CREE"},
        {"source": "Penicillin", "target": "Tuberculosis", "type": "PROTEGE_CONTRE"},
        {"source": "Louis Pasteur", "target": "Vaccination", "type": "A_CREE"},
        {"source": "Louis Pasteur", "target": "Paris", "type": "CONNECTE"},
        {"source": "Vaccination", "target": "Influenza", "type": "PROTEGE_CONTRE"},
        {"source": "Vaccination", "target": "COVID-19", "type": "PROTEGE_CONTRE"},
        {"source": "Charles Darwin", "target": "University of Cambridge", "type": "ETUDIE"},
        {"source": "Charles Darwin", "target": "London", "type": "CONNECTE"},
        {"source": "Charles Darwin", "target": "Royal Society", "type": "CONNECTE"},
        {"source": "Isaac Newton", "target": "University of Cambridge", "type": "ETUDIE"},
        {"source": "Isaac Newton", "target": "Royal Society", "type": "CONNECTE"},
        {"source": "Isaac Newton", "target": "London", "type": "CONNECTE"},

        # Computer science
        {"source": "Alan Turing", "target": "Artificial Intelligence", "type": "A_CREE"},
        {"source": "Alan Turing", "target": "University of Cambridge", "type": "ETUDIE"},
        {"source": "Alan Turing", "target": "London", "type": "CONNECTE"},
        {"source": "Ada Lovelace", "target": "London", "type": "CONNECTE"},
        {"source": "Ada Lovelace", "target": "Artificial Intelligence", "type": "CONNECTE"},

        # Invention connections
        {"source": "Nikola Tesla", "target": "Electricity", "type": "A_CREE"},
        {"source": "Thomas Edison", "target": "Electricity", "type": "UTILISE"},
        {"source": "Thomas Edison", "target": "Telephone", "type": "CONNECTE"},
        {"source": "Nikola Tesla", "target": "Thomas Edison", "type": "CONNECTE"},
        {"source": "Nikola Tesla", "target": "New York City", "type": "CONNECTE"},
        {"source": "Thomas Edison", "target": "New York City", "type": "CONNECTE"},

        # Space & Technology organizations
        {"source": "NASA", "target": "Washington D.C.", "type": "CONNECTE"},
        {"source": "NASA", "target": "Nuclear Energy", "type": "UTILISE"},
        {"source": "European Space Agency", "target": "Paris", "type": "CONNECTE"},
        {"source": "CERN", "target": "Zurich", "type": "CONNECTE"},
        {"source": "CERN", "target": "Nuclear Energy", "type": "ETUDIE"},
        {"source": "World Wide Web", "target": "CERN", "type": "A_CREE"},
        {"source": "World Wide Web", "target": "Internet", "type": "ETEND"},

        # Tech companies
        {"source": "Apple Inc", "target": "Artificial Intelligence", "type": "UTILISE"},
        {"source": "Google", "target": "Artificial Intelligence", "type": "UTILISE"},
        {"source": "Microsoft", "target": "Artificial Intelligence", "type": "UTILISE"},
        {"source": "Google", "target": "Internet", "type": "UTILISE"},
        {"source": "Google", "target": "Stanford University", "type": "CONNECTE"},
        {"source": "Apple Inc", "target": "New York City", "type": "CONNECTE"},
        {"source": "Microsoft", "target": "New York City", "type": "CONNECTE"},

        # Universities
        {"source": "MIT", "target": "Artificial Intelligence", "type": "ETUDIE"},
        {"source": "Stanford University", "target": "Artificial Intelligence", "type": "ETUDIE"},
        {"source": "Harvard University", "target": "Cambridge", "type": "CONNECTE"},
        {"source": "University of Oxford", "target": "London", "type": "CONNECTE"},

        # Health
        {"source": "World Health Organization", "target": "COVID-19", "type": "ETUDIE"},
        {"source": "World Health Organization", "target": "Malaria", "type": "ETUDIE"},
        {"source": "World Health Organization", "target": "United Nations", "type": "SOUS_ENSEMBLE_DE"},

        # Political leaders
        {"source": "Winston Churchill", "target": "London", "type": "CONNECTE"},
        {"source": "Franklin D. Roosevelt", "target": "Washington D.C.", "type": "CONNECTE"},
        {"source": "Winston Churchill", "target": "Franklin D. Roosevelt", "type": "CONNECTE"},
        {"source": "Napoleon Bonaparte", "target": "Paris", "type": "CONNECTE"},
        {"source": "Napoleon Bonaparte", "target": "Louvre Museum", "type": "CONNECTE"},
        {"source": "Mahatma Gandhi", "target": "London", "type": "ETUDIE"},
        {"source": "Nelson Mandela", "target": "Nobel Foundation", "type": "CONNECTE"},
        {"source": "Abraham Lincoln", "target": "Washington D.C.", "type": "CONNECTE"},
        {"source": "Cleopatra", "target": "Cairo", "type": "CONNECTE"},

        # Artists
        {"source": "Leonardo da Vinci", "target": "Florence", "type": "CONNECTE"},
        {"source": "Leonardo da Vinci", "target": "Louvre Museum", "type": "CONNECTE"},
        {"source": "William Shakespeare", "target": "London", "type": "CONNECTE"},
        {"source": "Wolfgang Amadeus Mozart", "target": "Salzburg", "type": "CONNECTE"},
        {"source": "Wolfgang Amadeus Mozart", "target": "Vienna", "type": "CONNECTE"},
        {"source": "Pablo Picasso", "target": "Paris", "type": "CONNECTE"},
        {"source": "Pablo Picasso", "target": "Museo del Prado", "type": "CONNECTE"},
        {"source": "Vincent van Gogh", "target": "Paris", "type": "CONNECTE"},
        {"source": "Frida Kahlo", "target": "Louvre Museum", "type": "CONNECTE"},

        # Film directors
        {"source": "Steven Spielberg", "target": "New York City", "type": "CONNECTE"},
        {"source": "Alfred Hitchcock", "target": "London", "type": "CONNECTE"},
        {"source": "Stanley Kubrick", "target": "London", "type": "CONNECTE"},
        {"source": "Martin Scorsese", "target": "New York City", "type": "CONNECTE"},

        # Museums in cities
        {"source": "Louvre Museum", "target": "Paris", "type": "CONNECTE"},
        {"source": "British Museum", "target": "London", "type": "CONNECTE"},
        {"source": "Metropolitan Museum of Art", "target": "New York City", "type": "CONNECTE"},
        {"source": "Smithsonian Institution", "target": "Washington D.C.", "type": "CONNECTE"},

        # Disease research chains
        {"source": "Cancer", "target": "World Health Organization", "type": "ETUDIE"},
        {"source": "Tuberculosis", "target": "World Health Organization", "type": "ETUDIE"},
        {"source": "COVID-19", "target": "Vaccination", "type": "VISE_A_LIMITER"},
        {"source": "Malaria", "target": "World Health Organization", "type": "CIBLE"},

        # Technology chains
        {"source": "Electricity", "target": "Internet", "type": "CONNECTE"},
        {"source": "Internet", "target": "Artificial Intelligence", "type": "CONNECTE"},
        {"source": "Steam Engine", "target": "Electricity", "type": "CONNECTE"},
        {"source": "Nuclear Energy", "target": "Electricity", "type": "CONNECTE"},
        {"source": "Telephone", "target": "Internet", "type": "CONNECTE"},
    ]

    # Create entities
    print(f"    Creating {len(entities)} curated entities...")
    entity_count = neo4j_create_entities(entities)
    print(f"    Created {entity_count} entity nodes")

    # Create relationships
    print(f"    Creating {len(relationships)} curated relationships...")
    rel_count = neo4j_create_relationships(relationships)
    print(f"    Created {rel_count} relationships")

    return entity_count, rel_count


if __name__ == "__main__":
    populate_from_contexts()
