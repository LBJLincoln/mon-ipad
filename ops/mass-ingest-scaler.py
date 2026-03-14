#!/usr/bin/env python3
"""Mass Ingestion Scaler — Scale documents to 1M via n8n workflows.

Discovers content via Exa.AI web search, then feeds to n8n Ingestion V4.0
which handles: chunking, embedding, Pinecone, Supabase, Neo4j enrichment.

Current: ~43K docs (mostly 'benchmark' tenant) + 12K Pinecone vectors
Target: 1M docs across 4 sectors

Strategy:
  1. Use Exa.AI to discover real sector documents/articles
  2. Feed each to n8n Ingestion V4.0 webhook with proper sector tenant_id
  3. n8n handles all processing (Docling, chunking, embedding, storage)
  4. Run enrichment chain for Neo4j graph
  5. Re-tag existing 'benchmark' docs to proper sectors

Usage:
    source .env.local
    python3 ops/mass-ingest-scaler.py --sector finance --batch 20
    python3 ops/mass-ingest-scaler.py --sector all --daemon 300
    python3 ops/mass-ingest-scaler.py --retag-benchmark   # Fix 43K benchmark docs
"""

# IPv4 fix
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import hashlib
import json
import os
import random
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k = k.strip().lstrip("export").strip()
                v = v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# n8n endpoints
N8N_INGEST_SPACES = [
    "https://lbjlincoln-nomos-rag-engine-9.hf.space",   # S9 primary
    "https://lbjlincoln-nomos-rag-engine.hf.space",       # S1 fallback
]
INGEST_WEBHOOK = "/webhook/ingest-v4"
ENRICH_WEBHOOK = "/webhook/enrich-v4"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

_db_conn = None
def get_db():
    global _db_conn
    if _db_conn and not _db_conn.closed:
        return _db_conn
    try:
        import psycopg2
        _db_conn = psycopg2.connect(DATABASE_URL)
        _db_conn.autocommit = True
        return _db_conn
    except Exception as e:
        log(f"DB error: {e}")
        return None

def db_execute(query, params=None):
    conn = get_db()
    if not conn: return None
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                return cur.fetchall()
            return True
    except Exception as e:
        log(f"DB: {e}")
        try: conn.rollback()
        except: pass
        return None

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ── Sector search queries — diverse document discovery ──
SECTOR_QUERIES = {
    "finance": [
        "rapport annuel entreprise cotee france 2024",
        "bilan financier PME france",
        "normes IFRS 16 application pratique",
        "analyse financiere ratios sectoriels",
        "reglementation AMF marches financiers",
        "comptabilite analytique methodes",
        "fiscalite entreprise france 2024",
        "audit financier procedures controle",
        "tresorerie gestion BFR",
        "fusion acquisition due diligence guide",
        "bale III ratio liquidite banques",
        "assurance solvabilite II",
        "marches financiers derivees options",
        "plan comptable general france",
        "TVA intracommunautaire regles",
        "credit scoring modeles prediction",
        "private equity france performance",
        "OPCVM gestion collective reglement",
        "reporting financier ESG",
        "blockchain finance decentralisee DeFi",
        "SEC 10-K filing analysis",
        "EBITDA margin industry benchmarks",
        "financial modeling DCF valuation",
        "risk management VaR calculation",
        "corporate bond analysis credit spread",
    ],
    "btp": [
        "DTU normes construction france",
        "Eurocode 2 calcul beton arme",
        "RE2020 reglementation environnementale batiment",
        "CCTP cahier clauses techniques",
        "permis construire urbanisme PLU",
        "BIM maquette numerique construction",
        "isolation thermique ITE materiaux",
        "fondations profondes micropieux",
        "etude sol geotechnique G1 G2",
        "securite chantier coordonnateur SPS",
        "assainissement non collectif ANC",
        "toiture etancheite DTU 43.1",
        "electricite norme NF C 15-100",
        "plomberie sanitaire DTU 60.11",
        "menuiseries exterieures performance thermique",
        "beton precontraint technique",
        "charpente metallique eurocode 3",
        "ravalement facade DTU 42.1",
        "accessibilite PMR ERP batiment",
        "diagnostics immobiliers amiante plomb DPE",
        "marches publics BTP BOAMP procedures",
        "VRD voirie reseaux divers",
        "construction bois CLT technique",
        "pompe chaleur dimensionnement",
        "ventilation double flux VMC",
    ],
    "juridique": [
        "code civil obligations contrats",
        "droit travail licenciement procedure",
        "RGPD conformite entreprise guide",
        "droit societes SAS statuts",
        "bail commercial renouvellement",
        "propriete intellectuelle brevet france",
        "droit consommation vente distance",
        "procedure collective redressement judiciaire",
        "droit penal des affaires abus bien",
        "responsabilite civile delictuelle contractuelle",
        "contrat travail CDI clauses essentielles",
        "rupture conventionnelle homologation procedure",
        "marque depot INPI protection",
        "droit numerique hebergeur responsabilite",
        "CNIL sanctions RGPD jurisprudence",
        "pacte associes clauses types",
        "cession fonds commerce formalites",
        "arbitrage commercial international",
        "clause non-concurrence validite",
        "procedure prudhomale delais etapes",
        "droit immobilier copropriete loi",
        "droit environnement ICPE autorisation",
        "contrat distribution concession franchise",
        "droit europeen reglement directive",
        "mediation conciliation modes alternatifs",
    ],
    "industrie": [
        "ISO 9001 systeme management qualite",
        "maintenance preventive predictive industrielle",
        "AMDEC analyse modes defaillances",
        "lean manufacturing 5S kaizen",
        "six sigma DMAIC methode",
        "supply chain logistique optimisation",
        "automatisation robotique industrielle",
        "metrologie industrielle calibration",
        "controle non destructif ultrason radiographie",
        "soudure qualification procedure",
        "ICPE installations classees seveso",
        "HSE sante securite environnement",
        "TPM total productive maintenance",
        "ERP MRP planification production",
        "SPC controle statistique processus",
        "ISO 14001 environnement certification",
        "ISO 45001 securite travail",
        "usinage CNC programmation",
        "traitement surface protection corrosion",
        "gestion stocks methode ABC Kanban",
        "audit qualite interne externe",
        "fiche donnees securite FDS chimique",
        "bilan carbone industrie methodologie",
        "industrie 4.0 IoT jumeaux numeriques",
        "analyse cycle vie ACV impact",
    ],
}


def exa_search(query, max_results=5):
    """Search via Exa.AI API for real web documents."""
    if not EXA_API_KEY:
        log("No EXA_API_KEY")
        return []

    payload = json.dumps({
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {"text": True},
    }).encode()

    req = urllib.request.Request(
        "https://api.exa.ai/search",
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": EXA_API_KEY},
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            return results
    except Exception as e:
        log(f"Exa.AI error: {e}")
        return []


def is_duplicate(doc_id):
    """Check if document already exists in Supabase."""
    result = db_execute(
        "SELECT 1 FROM sector_documents WHERE id = %s LIMIT 1",
        (doc_id,)
    )
    return bool(result)


def store_document_direct(title, content, url, sector, source="exa"):
    """Store document in Supabase sector_documents + document_registry."""
    if not content or len(content) < 200:
        return False

    doc_id = hashlib.md5(f"{sector}:{url}".encode()).hexdigest()[:24]
    if is_duplicate(doc_id):
        return False

    # sector_documents schema: id, sector, dataset_name, pipeline, question, answer, context, metadata, tenant_id
    metadata = json.dumps({"source_url": url, "source": source, "title": title[:200]})

    result = db_execute("""
        INSERT INTO sector_documents
            (id, sector, dataset_name, pipeline, question, answer, context,
             metadata, tenant_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, now())
        ON CONFLICT (id) DO NOTHING
    """, (
        doc_id, sector, f"exa_{source}", "standard",
        title[:500],  # question = title (for discovery)
        content[:5000],  # answer = content summary
        content[:30000],  # context = full content
        metadata, sector,
    ))

    # Also register in document_registry for tracking (best-effort)
    content_hash = hashlib.md5(content[:5000].encode()).hexdigest()
    # source_type must be: pdf, html, json, csv, api, exa, manual, dataset
    registry_source = "exa" if source == "exa" else "api" if source == "llm_generated" else "manual"
    db_execute("""
        INSERT INTO document_registry
            (sector, source_type, source_url, title, char_count, language,
             quality_score, processing_status, content_hash, discovered_at, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s::jsonb)
        ON CONFLICT DO NOTHING
    """, (
        sector, registry_source, url[:1000], title[:500], len(content), "fr",
        0.7, "ingested", content_hash, metadata,
    ))

    return result is not None


def feed_to_n8n(title, content, url, sector):
    """Feed document to n8n Ingestion V4.0 webhook."""
    doc_id = hashlib.md5(f"{sector}:{url}".encode()).hexdigest()[:24]

    payload = json.dumps({
        "documentId": doc_id,
        "filename": f"{title[:80]}.txt",
        "content_text": content[:30000],
        "content_url": url,
        "source": "exa_mass",
        "tenant_id": sector,
        "metadata": {
            "title": title,
            "sector": sector,
            "source_url": url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        },
    }).encode()

    for space in N8N_INGEST_SPACES:
        endpoint = f"{space}{INGEST_WEBHOOK}"
        req = urllib.request.Request(
            endpoint, data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                return True
        except Exception:
            continue

    return False


def generate_expert_document(sector, topic):
    """Generate expert-level document content via LLM when Exa.AI is unavailable."""
    prompt = f"""Tu es un expert du secteur {sector}. Ecris un document technique detaille sur le sujet suivant:

SUJET: {topic}

Regles:
- Ecris comme un vrai document professionnel (rapport technique, guide pratique, fiche reglementaire)
- Utilise le vocabulaire technique exact du secteur
- Inclus des references reglementaires reelles (normes, articles de loi, DTU, ISO, etc.)
- Minimum 800 mots, maximum 2000 mots
- Structure avec des sections et sous-sections
- Inclus des chiffres et donnees concretes quand applicable

Ecris directement le contenu du document, sans introduction meta."""

    LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
    LITELLM_KEY = "sk-litellm-nomos-2026"

    payload = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 3000,
    }).encode()

    req = urllib.request.Request(
        LITELLM_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LITELLM_KEY}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content and len(content) > 200 else None
    except Exception as e:
        log(f"LLM doc gen error: {e}")
        return None


def ingest_sector_batch(sector, batch_size=10):
    """Discover and ingest a batch of documents for a sector."""
    queries = SECTOR_QUERIES.get(sector, SECTOR_QUERIES["finance"])

    stored = 0

    # Try Exa.AI first
    if EXA_API_KEY:
        query = random.choice(queries)
        log(f"{sector}: Exa.AI search '{query[:50]}...'")
        results = exa_search(query, max_results=batch_size)
        for r in results:
            title = r.get("title", "")
            content = r.get("text", "")
            url = r.get("url", "")
            if content and len(content) >= 200:
                if store_document_direct(title, content, url, sector):
                    stored += 1
                    try:
                        feed_to_n8n(title, content, url, sector)
                    except Exception:
                        pass

        if stored > 0:
            log(f"{sector}: stored {stored}/{len(results)} via Exa.AI")
            return stored

    # Fallback: generate expert documents via LLM
    log(f"{sector}: Exa.AI unavailable, generating expert docs via LLM")
    topics = random.sample(queries, min(batch_size, len(queries)))

    for topic in topics:
        content = generate_expert_document(sector, topic)
        if not content:
            continue

        title = topic[:100]
        url = f"llm://generated/{sector}/{hashlib.md5(topic.encode()).hexdigest()[:12]}"

        if store_document_direct(title, content, url, sector, source="llm_generated"):
            stored += 1
            try:
                feed_to_n8n(title, content, url, sector)
            except Exception:
                pass
        time.sleep(2)  # Rate limit LLM

    log(f"{sector}: generated {stored} expert documents via LLM")
    return stored


def retag_benchmark_docs(batch_size=500):
    """Re-tag 'benchmark' docs to proper sector based on question/answer/context."""
    log("Re-tagging benchmark docs...")

    sector_keywords = {
        "finance": ["financier", "comptable", "bilan", "tresorerie", "banque",
                     "investissement", "bourse", "fiscal", "audit", "credit",
                     "financial", "revenue", "earnings", "stock", "dividend"],
        "btp": ["construction", "batiment", "chantier", "fondation", "beton",
                "isolation", "toiture", "electricite", "plomberie", "urbanisme",
                "DTU", "maconnerie", "permis construire"],
        "juridique": ["juridique", "contrat", "tribunal", "droit", "loi",
                      "procedure", "avocat", "juge", "code civil", "penal",
                      "RGPD", "CNIL", "licenciement"],
        "industrie": ["industriel", "usine", "production", "qualite", "maintenance",
                      "ISO 9001", "securite", "machine", "soudure", "fabrication",
                      "manufacturing", "supply chain", "lean"],
    }

    # sector_documents schema: id, sector, dataset_name, pipeline, question, answer, context, metadata, tenant_id
    result = db_execute("""
        SELECT id, question, answer, context FROM sector_documents
        WHERE tenant_id = 'benchmark'
        LIMIT %s
    """, (batch_size,))

    if not result:
        log("No benchmark docs to retag")
        return 0

    retagged = 0
    for row in result:
        doc_id, question, answer, context = row
        text = f"{question or ''} {answer or ''} {(context or '')[:2000]}".lower()

        best_sector = None
        best_score = 0
        for sector, keywords in sector_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            if score > best_score:
                best_score = score
                best_sector = sector

        if best_sector and best_score >= 2:
            db_execute("""
                UPDATE sector_documents
                SET tenant_id = %s, sector = %s
                WHERE id = %s
            """, (best_sector, best_sector, doc_id))
            retagged += 1

    log(f"Re-tagged {retagged}/{len(result)} docs")
    return retagged


def get_doc_counts():
    """Get current document counts per sector."""
    result = db_execute("""
        SELECT tenant_id, COUNT(*) FROM sector_documents
        GROUP BY tenant_id ORDER BY tenant_id
    """)
    if result:
        return {r[0]: r[1] for r in result}
    return {}


def main():
    parser = argparse.ArgumentParser(description="Mass ingestion scaler")
    parser.add_argument("--sector", default="all", help="Sector or 'all'")
    parser.add_argument("--batch", type=int, default=10, help="Docs per search")
    parser.add_argument("--target", type=int, default=250000, help="Target per sector")
    parser.add_argument("--daemon", type=int, default=0, help="Loop interval (seconds)")
    parser.add_argument("--retag-benchmark", action="store_true", help="Re-tag benchmark docs")
    parser.add_argument("--max-cycles", type=int, default=0, help="Max cycles")
    args = parser.parse_args()

    if args.retag_benchmark:
        total = 0
        while True:
            n = retag_benchmark_docs(500)
            total += n
            if n == 0:
                break
            log(f"Total re-tagged: {total}")
        log(f"Finished re-tagging: {total} docs")
        return

    sectors = ["finance", "btp", "juridique", "industrie"] if args.sector == "all" else [args.sector]

    cycle = 0
    total_ingested = 0

    while True:
        cycle += 1
        log(f"\n{'='*60}")
        log(f"CYCLE {cycle} — Sectors: {', '.join(sectors)}")

        counts = get_doc_counts()
        log("Current doc counts:")
        for s in sectors:
            c = counts.get(s, 0)
            pct = round(c / args.target * 100, 1) if args.target > 0 else 0
            log(f"  {s}: {c:,} / {args.target:,} ({pct}%)")

        cycle_total = 0
        for sector in sectors:
            current = counts.get(sector, 0)
            if current >= args.target:
                log(f"{sector}: target reached ({current:,})")
                continue

            stored = ingest_sector_batch(sector, args.batch)
            cycle_total += stored
            total_ingested += stored
            time.sleep(3)  # Rate limit Exa.AI

        log(f"Cycle {cycle}: +{cycle_total} docs (session total: {total_ingested:,})")

        if args.max_cycles and cycle >= args.max_cycles:
            log(f"Max cycles reached")
            break

        if args.daemon <= 0:
            break

        log(f"Sleeping {args.daemon}s...")
        time.sleep(args.daemon)


if __name__ == "__main__":
    main()
