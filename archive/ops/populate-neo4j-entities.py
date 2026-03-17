#!/usr/bin/env python3
"""
Populate Neo4j with entities extracted from sector JSONL data.

Reads all .jsonl files from ~/rag-data-ingestion/datasets/sectors/{sector}/
Extracts entities using regex-based NER heuristics, creates:
  - (:Entity {name, sector, type}) nodes
  - (:SectorDocument)-[:MENTIONS]->(:Entity) relationships

Target: 200+ entities per sector, 2000+ total.
"""

import json
import os
import re
import sys
import hashlib
from collections import defaultdict
from pathlib import Path

# --- Config ---
DATASETS_DIR = Path.home() / "rag-data-ingestion" / "datasets" / "sectors"
SECTORS = ["finance", "btp", "juridique", "industrie"]
BATCH_SIZE = 200  # Neo4j UNWIND batch size

# --- Entity extraction patterns ---

# Company suffixes (international)
COMPANY_SUFFIXES = r'\b(?:Inc\.?|Corp\.?|Ltd\.?|LLC|LLP|PLC|S\.?A\.?|SAS|SARL|EURL|SCI|SNC|GmbH|AG|SpA|BV|NV|SE|Co\.?|Group|Holdings|International|Partners|Capital|Ventures|Industries|Technologies|Solutions|Systems|Services|Consulting|Associates|Advisors|Management|Investments|Securities|Insurance|Bank|Trust|Fund|REIT)\b'

# French legal / law patterns
LAW_PATTERNS = [
    # Article references
    r'[Aa]rticle\s+(?:L\.?\s*)?[\d][\d\-\.]+(?:\s+(?:du|de\s+la|des|de|et\s+suivants))?',
    r'[Aa]rt(?:icle)?\.?\s*(?:R\.?\s*|D\.?\s*|L\.?\s*)?[\d][\d\-\.]+',
    # Code references
    r'[Cc]ode\s+(?:civil|de\s+commerce|du\s+travail|p[eé]nal|de\s+proc[eé]dure\s+civile|de\s+proc[eé]dure\s+p[eé]nale|de\s+l[\'\u2019]environnement|de\s+la\s+construction|de\s+l[\'\u2019]urbanisme|g[eé]n[eé]ral\s+des\s+imp[oô]ts|mon[eé]taire\s+et\s+financier|de\s+la\s+s[eé]curit[eé]\s+sociale|des\s+march[eé]s\s+publics|de\s+la\s+sant[eé]\s+publique|de\s+l[\'\u2019]organisation\s+judiciaire|de\s+la\s+consommation|de\s+la\s+propri[eé]t[eé]\s+intellectuelle|des\s+pensions\s+militaires[^,;.]*)',
    # Loi / Décret / Ordonnance
    r'[Ll]oi\s+n[°o]?\s*[\d\-]+(?:\s+du\s+\d+\s+\w+\s+\d{4})?',
    r'[Dd][eé]cret\s+n[°o]?\s*[\d\-]+(?:\s+du\s+\d+\s+\w+\s+\d{4})?',
    r'[Oo]rdonnance\s+n[°o]?\s*[\d\-]+(?:\s+du\s+\d+\s+\w+\s+\d{4})?',
    r'[Dd]irective\s+(?:\d{4}/\d+/[A-Z]+|\([A-Z]+\)\s*\d{4}/\d+)',
    r'[Rr][eè]glement\s+(?:\([A-Z]+\)\s*)?\d{4}/\d+',
]

# Standards / norms
STANDARD_PATTERNS = [
    r'ISO\s*\d{3,5}(?:[:\-]\d+)?(?:\s*[-/]\s*\d{4})?',
    r'NF\s+[A-Z]\s*\d{2}[\-\.]\d{3,}',
    r'NF\s+EN\s+\d{3,}(?:[:\-]\d+)?',
    r'EN\s+\d{3,}(?:[:\-]\d+)?(?:\s*[-/]\s*\d{4})?',
    r'DTU\s+\d{1,2}(?:\.\d+)*',
    r'Eurocode\s*\d{1}(?:\s*[-:]\s*\d+)?',
    r'AFNOR\s+[A-Z]{1,3}\s*\d+',
    r'CPV[:\s]*\d{8}',
    r'ASTM\s+[A-Z]\d+',
    r'IEEE\s+\d+',
    r'IEC\s+\d+',
    r'AMDEC',
    r'CCTP',
    r'CCAG(?:\s*[-/]\s*(?:Travaux|PI|TIC|FCS|MOE))?',
    r'BOAMP',
    r'RGPD',
    r'IFRS\s*\d{0,2}',
    r'IAS\s*\d{1,2}',
    r'GAAP',
    r'SEC\s+(?:Rule|Form|Regulation)\s*[\w\-]+',
    r'SOX|Sarbanes[\-\s]Oxley',
    r'Basel\s+(?:I{1,3}|IV)',
    r'MiFID\s*(?:I{1,2})?',
    r'DORA',
    r'Solvency\s*(?:I{1,2})',
]

# Financial terms / metrics
FINANCIAL_TERMS = [
    r'\bEBITDA\b', r'\bEBIT\b', r'\bROE\b', r'\bROA\b', r'\bROI\b',
    r'\bROCE\b', r'\bWACC\b', r'\bEPS\b', r'\bP/E\b', r'\bPER\b',
    r'\bBFR\b', r'\bCAF\b', r'\bVAN\b', r'\bTRI\b', r'\bDCF\b',
    r'\bFCF\b', r'\bFCFF\b', r'\bFCFE\b', r'\bNAV\b', r'\bLTV\b',
    r'\bCDS\b', r'\bMBS\b', r'\bABS\b', r'\bCDO\b', r'\bIPO\b',
    r'\bM&A\b', r'\bLBO\b', r'\bPER\b', r'\bGoodwill\b',
]

# BTP-specific terms
BTP_TERMS = [
    r'\b(?:gros\s+[oœ]uvre|second\s+[oœ]uvre)\b',
    r'\b(?:b[eé]ton\s+arm[eé]|b[eé]ton\s+pr[eé]contraint)\b',
    r'\b(?:charpente\s+m[eé]tallique|charpente\s+bois)\b',
    r'\b(?:[eé]tanch[eé]it[eé]|isolation\s+thermique|isolation\s+phonique)\b',
    r'\b(?:VRD|CVC|HVAC|CFO|CFA|SSI)\b',
    r'\bDQE\b', r'\bDPGF\b', r'\bDCE\b', r'\bDOE\b',
    r'\b(?:ma[iî]tre\s+d[\'\u2019](?:ouvrage|[oœ]uvre))\b',
    r'\bOPC\b', r'\bBET\b', r'\bAMO\b',
    r'\b(?:permis\s+de\s+construire)\b',
    r'\b(?:plan\s+local\s+d[\'\u2019]urbanisme|PLU)\b',
    r'\b(?:[eé]tude\s+de\s+sol|[eé]tude\s+g[eé]otechnique)\b',
]

# Industrie-specific terms
INDUSTRIE_TERMS = [
    r'\bAMDEC\b', r'\bAPQP\b', r'\bPPAP\b', r'\bFMEA\b',
    r'\b(?:5S|6\s*Sigma|Six\s*Sigma|Lean|Kaizen|Kanban|SMED|TPM|TRS|TRG)\b',
    r'\b(?:ISO\s*9001|ISO\s*14001|ISO\s*45001|ISO\s*50001|IATF\s*16949)\b',
    r'\b(?:contr[oô]le\s+qualit[eé]|assurance\s+qualit[eé])\b',
    r'\b(?:maintenance\s+pr[eé]ventive|maintenance\s+pr[eé]dictive|maintenance\s+corrective)\b',
    r'\bGMPP?\b',
    r'\b(?:additive\s+manufacturing|3D\s+printing)\b',
    r'\b(?:topology\s+optimization)\b',
    r'\b(?:CNC|PLC|SCADA|MES|ERP|MRP)\b',
    r'\bSPC\b',
]

# Juridique-specific terms
JURIDIQUE_TERMS = [
    r'\b(?:Cour\s+de\s+cassation|Conseil\s+d[\'\u2019][EÉeé]tat|Conseil\s+constitutionnel)\b',
    r'\b(?:Cour\s+d[\'\u2019]appel(?:\s+de\s+\w+)?)\b',
    r'\b(?:tribunal\s+(?:de\s+grande\s+instance|judiciaire|de\s+commerce|administratif|correctionnel))\b',
    r'\b(?:juridiction|jurisprudence|pourvoi|cassation)\b',
    r'\b(?:proc[eé]dure\s+(?:civile|p[eé]nale|collective))\b',
    r'\b(?:mise\s+en\s+demeure|r[eé]f[eé]r[eé])\b',
    r'\b(?:CNIL|DGCCRF|AMF|ACPR|ARS)\b',
    r'\bECLI[:\s]*FR[:\w]+\b',
]

# Organization names from BOAMP
ORG_PATTERNS = [
    r'(?:Conseil\s+[DdGg][eé][a-z]*(?:\s+(?:du|de\s+la|des|de)\s+[\w\-]+)+)',
    r'(?:Communaut[eé]\s+(?:d[\'\u2019]agglom[eé]ration|de\s+communes|urbaine)(?:\s+[\w\-]+)*)',
    r'(?:Mairie\s+de\s+[\w\-]+)',
    r'(?:Commune\s+de\s+[\w\-]+)',
    r'(?:R[eé]gion\s+[\w\-]+)',
    r'(?:M[eé]tropole\s+(?:de\s+)?[\w\-]+)',
    r'(?:SNCF|EDF|ENGIE|RATP|TOTAL|Orange|Bouygues|Vinci|Eiffage)',
]


def make_doc_id(record, dataset_name):
    """Generate a deterministic document ID from record."""
    raw_id = record.get("id", "")
    if raw_id:
        return str(raw_id)
    # Fallback: hash content
    content = json.dumps(record, sort_keys=True, ensure_ascii=False)[:500]
    return hashlib.md5(content.encode()).hexdigest()[:16]


def extract_text_from_record(record):
    """Extract all searchable text from a record, regardless of format."""
    texts = []

    # Common fields
    for field in ["question", "answer", "response", "content", "text",
                  "document", "documents", "fact", "summary",
                  "justification", "Explanation", "title",
                  "article_contenu_text", "article_contenu_markdown",
                  "texte_titre", "texte_contexte", "keywords",
                  "processed_content", "applied_laws"]:
        val = record.get(field)
        if val and isinstance(val, str):
            texts.append(val)

    # BOAMP metadata
    meta = record.get("metadata", {})
    if isinstance(meta, dict):
        for k in ["acheteur", "descripteurs", "titulaire", "location"]:
            v = meta.get(k)
            if v and isinstance(v, str):
                texts.append(v)

    return " ".join(texts)


def extract_entities_from_text(text, sector):
    """Extract entities from text using regex patterns. Returns list of (name, type)."""
    entities = set()

    if not text or len(text) < 10:
        return entities

    # 1. Company names with suffixes
    for m in re.finditer(r'(?:(?:[A-Z][\w\-&\.]*\s+){0,4})' + COMPANY_SUFFIXES, text):
        name = m.group(0).strip()
        if len(name) > 2 and len(name) < 100:
            entities.add((name, "company"))

    # 2. Company names: "société X" pattern (French)
    for m in re.finditer(r'(?:soci[eé]t[eé]|association|entreprise|groupe|filiale)\s+([A-Z][\w\-&\.\s]{1,50}?)(?:[,;.\s]|$)', text, re.IGNORECASE):
        name = m.group(1).strip()
        if len(name) > 2 and len(name) < 60:
            entities.add((name, "company"))

    # 3. Law references
    for pattern in LAW_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            name = m.group(0).strip()
            if len(name) > 3:
                entities.add((name, "law_ref"))

    # 4. Standards / norms
    for pattern in STANDARD_PATTERNS:
        for m in re.finditer(pattern, text):
            name = m.group(0).strip()
            if len(name) > 2:
                entities.add((name, "standard"))

    # 5. Financial terms
    if sector == "finance":
        for pattern in FINANCIAL_TERMS:
            for m in re.finditer(pattern, text):
                entities.add((m.group(0).strip(), "metric"))

    # 6. BTP terms
    if sector == "btp":
        for pattern in BTP_TERMS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                entities.add((m.group(0).strip(), "technical_term"))
        for pattern in ORG_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                name = m.group(0).strip()
                if len(name) > 4:
                    entities.add((name, "organization"))

    # 7. Industrie terms
    if sector == "industrie":
        for pattern in INDUSTRIE_TERMS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                entities.add((m.group(0).strip(), "technical_term"))

    # 8. Juridique terms
    if sector == "juridique":
        for pattern in JURIDIQUE_TERMS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                entities.add((m.group(0).strip(), "institution"))
        # ECLI references
        for m in re.finditer(r'ECLI:FR:[A-Z]+:\d{4}:[A-Z]*\d+', text):
            entities.add((m.group(0).strip(), "case_ref"))

    # 9. Named entities: capitalized multi-word names (heuristic for proper nouns)
    for m in re.finditer(r'\b([A-Z][a-zéèêëàâäôöûüùïîç]+(?:\s+[A-Z][a-zéèêëàâäôöûüùïîç]+){1,3})\b', text):
        name = m.group(1).strip()
        # Filter out common phrases
        skip_words = {"The", "This", "That", "These", "Those", "What", "When",
                      "Where", "Which", "How", "Why", "There", "Here", "Some",
                      "Dans", "Pour", "Avec", "Selon", "Entre", "Depuis",
                      "Sous", "Vers", "Dans", "Chez", "Par", "Sur", "Aux",
                      "Les", "Des", "Mais", "Donc", "Puis", "Aussi",
                      "Other", "After", "Before", "About", "Above", "Under",
                      "System", "Section", "Chapter", "Part", "Document",
                      "Table", "Figure", "Note", "Year", "December", "January",
                      "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November"}
        first_word = name.split()[0]
        if first_word in skip_words:
            continue
        if len(name) > 4 and len(name) < 60:
            entities.add((name, "named_entity"))

    # 10. ALL-CAPS abbreviations (3+ letters, domain terms)
    for m in re.finditer(r'\b([A-Z]{3,8})\b', text):
        abbr = m.group(1)
        skip = {"THE", "AND", "FOR", "NOT", "BUT", "FROM", "WITH", "THIS",
                "THAT", "HAVE", "BEEN", "WILL", "WAS", "ARE", "HAS", "HAD",
                "ALL", "ITS", "CAN", "MAY", "DES", "LES", "AUX", "QUI",
                "QUE", "PAR", "SUR", "DANS", "POUR", "AVEC", "PLUS", "NOM",
                "NULL", "TRUE", "FALSE", "NONE", "DATA", "JSON", "HTTP",
                "OPEN", "FREE", "NEW", "OLD", "END", "RUN", "GET", "SET",
                "KEY", "LOG", "URL", "API", "PDF", "CSV", "XML", "SQL",
                "EUR", "USD", "GBP", "JPY", "CHF", "CNY", "CAD", "AUD",
                "TECHNOTE", "TROUBLESHOOTING", "PROBLEM", "ABSTRACT", "SYMPTOM",
                "CAUSE", "RESOLVING", "PRODUCT", "ALIAS", "SYNONYM",
                "CASSE", "ANNULE", "MOTIFS", "CHAMBRE", "CIVILE", "PUBLIQUE",
                "ARRET", "FAIT", "PROC", "ETAT", "SOURCE", "TRAIN"}
        if abbr not in skip and len(abbr) >= 3:
            entities.add((abbr, "abbreviation"))

    # 11. BOAMP specific: extract CPV codes as technical categories
    for m in re.finditer(r'Lot\s+n[°o]?\d+\s*[.:]\s*([^|,\n]{3,60})', text):
        lot_desc = m.group(1).strip()
        if lot_desc:
            entities.add((lot_desc, "lot_category"))

    # 12. Company names from financebench style: look for known patterns
    for m in re.finditer(r'\b([A-Z][A-Za-z&\.\-]+(?:\s+[A-Z][A-Za-z&\.\-]+){0,2})\s+(?:reported|announced|filed|disclosed|earned|generated|recorded|achieved|posted|received)', text):
        name = m.group(1).strip()
        if len(name) > 2:
            entities.add((name, "company"))

    # 13. 10-K / 10-Q / SEC form references
    for m in re.finditer(r'\b(10-[KQ]|20-F|8-K|S-1|DEF\s*14A)\b', text):
        entities.add((m.group(0).strip(), "sec_filing"))

    return entities


def clean_entity_name(name):
    """Normalize entity name."""
    # Strip HTML tags
    name = re.sub(r'<[^>]+>', '', name)
    # Remove leading/trailing punctuation
    name = name.strip(' .,;:!?"\'()[]{}')
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def process_sector(sector):
    """Process all JSONL files for a sector, return (doc_entities, all_entities)."""
    sector_dir = DATASETS_DIR / sector
    if not sector_dir.exists():
        print(f"  [SKIP] Directory not found: {sector_dir}")
        return [], set()

    jsonl_files = list(sector_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"  [SKIP] No JSONL files in {sector_dir}")
        return [], set()

    # doc_entities: list of (doc_id, dataset, sector, question_text, answer_text, set of (entity_name, entity_type))
    doc_entities = []
    all_entities = set()  # (name, sector, type)
    records_processed = 0

    for jsonl_file in sorted(jsonl_files):
        dataset_name = jsonl_file.stem
        file_records = 0
        file_entities = 0

        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                doc_id = make_doc_id(record, dataset_name)
                text = extract_text_from_record(record)
                entities = extract_entities_from_text(text, sector)

                # Clean entities
                cleaned_entities = set()
                for name, etype in entities:
                    name = clean_entity_name(name)
                    if name and len(name) >= 2 and len(name) <= 100:
                        cleaned_entities.add((name, etype))
                        all_entities.add((name, sector, etype))

                if cleaned_entities:
                    # Get question and answer for SectorDocument
                    question = record.get("question", record.get("Question", record.get("title", "")))
                    answer = record.get("answer", record.get("response", record.get("Answer", "")))
                    if isinstance(answer, (int, float)):
                        answer = str(answer)
                    if not question:
                        question = text[:200] if text else ""
                    if not answer:
                        answer = ""

                    doc_entities.append({
                        "doc_id": doc_id,
                        "dataset": dataset_name,
                        "sector": sector,
                        "question": question[:500],
                        "answer": answer[:500],
                        "entities": cleaned_entities,
                    })
                    file_entities += len(cleaned_entities)

                file_records += 1
                records_processed += 1

        print(f"  [{dataset_name}] {file_records} records -> {file_entities} entity mentions")

    print(f"  TOTAL: {records_processed} records, {len(all_entities)} unique entities, {len(doc_entities)} docs with entities")
    return doc_entities, all_entities


def write_to_neo4j(sector_data, neo4j_uri, neo4j_user, neo4j_password):
    """Write entities and relationships to Neo4j in batches."""
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    total_entities_created = 0
    total_rels_created = 0

    for sector, (doc_entities, all_entities) in sector_data.items():
        if not all_entities:
            print(f"\n[{sector}] No entities to write, skipping")
            continue

        print(f"\n[{sector}] Writing {len(all_entities)} entities and links for {len(doc_entities)} docs...")

        # Step 1: Create/merge Entity nodes in batches
        entity_list = [{"name": name, "sector": sec, "type": etype} for name, sec, etype in all_entities]

        with driver.session() as session:
            for i in range(0, len(entity_list), BATCH_SIZE):
                batch = entity_list[i:i + BATCH_SIZE]
                result = session.run("""
                    UNWIND $entities AS e
                    MERGE (entity:Entity {name: e.name, sector: e.sector})
                    ON CREATE SET entity.type = e.type
                    RETURN count(entity) AS cnt
                """, entities=batch)
                cnt = result.single()["cnt"]
                total_entities_created += cnt
                print(f"  Entities batch {i // BATCH_SIZE + 1}: {cnt} merged")

            # Add :Company label for company type
            session.run("""
                MATCH (e:Entity)
                WHERE e.type = 'company' AND e.sector = $sector AND NOT e:Company
                SET e:Company
            """, sector=sector)

            # Add :Law label for law_ref type
            session.run("""
                MATCH (e:Entity)
                WHERE e.type IN ['law_ref', 'standard'] AND e.sector = $sector AND NOT e:Law
                SET e:Law
            """, sector=sector)

            # Add :Organization label for organization type
            session.run("""
                MATCH (e:Entity)
                WHERE e.type = 'organization' AND e.sector = $sector AND NOT e:Organization
                SET e:Organization
            """, sector=sector)

        # Step 2: Create SectorDocument nodes and MENTIONS relationships
        with driver.session() as session:
            for i in range(0, len(doc_entities), BATCH_SIZE):
                batch = doc_entities[i:i + BATCH_SIZE]

                # Prepare batch data: each doc with its entity names
                batch_data = []
                for doc in batch:
                    for ent_name, ent_type in doc["entities"]:
                        batch_data.append({
                            "doc_id": doc["doc_id"],
                            "dataset": doc["dataset"],
                            "sector": doc["sector"],
                            "question": doc["question"],
                            "answer": doc["answer"],
                            "entity_name": ent_name,
                            "entity_sector": doc["sector"],
                        })

                if not batch_data:
                    continue

                # Process in sub-batches to avoid huge transactions
                SUB_BATCH = 500
                for j in range(0, len(batch_data), SUB_BATCH):
                    sub = batch_data[j:j + SUB_BATCH]
                    result = session.run("""
                        UNWIND $rels AS r
                        MERGE (d:SectorDocument {id: r.doc_id})
                        ON CREATE SET d.dataset = r.dataset,
                                      d.sector = r.sector,
                                      d.question = r.question,
                                      d.answer = r.answer,
                                      d.pipeline = 'entity_extraction'
                        WITH d, r
                        MATCH (e:Entity {name: r.entity_name, sector: r.entity_sector})
                        MERGE (d)-[:MENTIONS]->(e)
                        RETURN count(*) AS cnt
                    """, rels=sub)
                    cnt = result.single()["cnt"]
                    total_rels_created += cnt

                docs_done = min(i + BATCH_SIZE, len(doc_entities))
                print(f"  Docs+Rels batch {i // BATCH_SIZE + 1}: processed {docs_done}/{len(doc_entities)} docs")

    # Final counts
    with driver.session() as session:
        result = session.run("""
            MATCH (e:Entity)
            RETURN e.sector AS sector, count(e) AS cnt
            ORDER BY cnt DESC
        """)
        print("\n=== FINAL Entity counts by sector ===")
        for r in result:
            print(f"  {r['sector']}: {r['cnt']} entities")

        result = session.run("""
            MATCH (d:SectorDocument)-[r:MENTIONS]->(e:Entity)
            RETURN e.sector AS sector, count(r) AS cnt
            ORDER BY cnt DESC
        """)
        print("\n=== FINAL MENTIONS by sector ===")
        for r in result:
            print(f"  {r['sector']}: {r['cnt']} mentions")

        result = session.run("MATCH (n) RETURN count(n) AS total")
        print(f"\nTotal nodes: {result.single()['total']}")

        result = session.run("MATCH ()-[r]->() RETURN count(r) AS total")
        print(f"Total relationships: {result.single()['total']}")

    driver.close()
    print(f"\nDone! Created/merged {total_entities_created} entities, {total_rels_created} relationships")


def main():
    # Load env
    neo4j_uri = os.environ.get("NEO4J_URI", "")
    neo4j_password = os.environ.get("NEO4J_PASSWORD", "")
    neo4j_user = "neo4j"  # Default for Aura

    if not neo4j_uri or not neo4j_password:
        print("ERROR: Set NEO4J_URI and NEO4J_PASSWORD (source .env.local)")
        sys.exit(1)

    print(f"Neo4j: {neo4j_uri}")
    print(f"Datasets: {DATASETS_DIR}")
    print(f"Sectors: {SECTORS}")
    print()

    # Phase 1: Extract entities from all sectors
    sector_data = {}
    for sector in SECTORS:
        print(f"\n{'='*60}")
        print(f"Processing sector: {sector.upper()}")
        print(f"{'='*60}")
        doc_entities, all_entities = process_sector(sector)
        sector_data[sector] = (doc_entities, all_entities)

    # Summary
    print(f"\n{'='*60}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*60}")
    for sector in SECTORS:
        doc_entities, all_entities = sector_data[sector]
        print(f"  {sector}: {len(all_entities)} unique entities from {len(doc_entities)} docs")

    total_entities = sum(len(v[1]) for v in sector_data.values())
    print(f"  TOTAL: {total_entities} unique entities")

    if total_entities == 0:
        print("No entities extracted. Check data files.")
        sys.exit(1)

    # Phase 2: Write to Neo4j
    print(f"\n{'='*60}")
    print("WRITING TO NEO4J")
    print(f"{'='*60}")
    write_to_neo4j(sector_data, neo4j_uri, neo4j_user, neo4j_password)


if __name__ == "__main__":
    main()
