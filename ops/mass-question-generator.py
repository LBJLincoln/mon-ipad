#!/usr/bin/env python3
"""Mass Question Generator — Scale eval questions to 100K per pipeline.

Generates expert-level questions with golden answers using LLM,
then stores them directly in Supabase eval_question_bank.

Current: ~30K total (Finance 10K, Industrie 8.5K, BTP 5.7K, Juridique 5.5K)
Target: 100K per pipeline x 4 = 400K

Generates diverse question types per sector:
  - Factual, analytical, comparative, procedural, regulatory
  - Multiple difficulty levels
  - With expected_contains for keyword matching
  - With golden_answer for LLM judge

Usage:
    source .env.local
    python3 ops/mass-question-generator.py --sector finance --batch 50
    python3 ops/mass-question-generator.py --sector all --batch 100 --daemon 600
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
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

# Load .env.local
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

LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = "sk-litellm-nomos-2026"
DATABASE_URL = os.environ.get("DATABASE_URL", "")

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
        log(f"DB error: {e}")
        try: conn.rollback()
        except: pass
        return None

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# Sector question categories — diverse coverage
SECTOR_TOPICS = {
    "finance": {
        "categories": [
            "comptabilite", "fiscalite", "bourse", "banque", "assurance",
            "audit", "compliance", "gestion-patrimoine", "fintech", "crypto",
            "analyse-financiere", "credit", "tresorerie", "fusion-acquisition",
            "reglementation", "normes-IFRS", "risques", "investissement",
            "droit-bancaire", "epargne", "marches-derives", "private-equity",
        ],
        "topics": [
            "bilan comptable", "compte de resultat", "ratios financiers",
            "TVA et fiscalite", "impot sur les societes", "CAC 40",
            "OPCVM et fonds", "credit immobilier", "scoring credit",
            "analyse technique", "analyse fondamentale", "Bale III",
            "MiFID II", "AMF", "normes IFRS 16", "consolidation comptable",
            "due diligence", "LBO", "DCF", "multiple EBITDA",
            "PEA", "assurance-vie", "crowdfunding", "open banking",
            "Solvabilite II", "provision pour risques", "plan comptable general",
        ],
        "difficulties": ["easy", "medium", "hard", "expert"],
    },
    "btp": {
        "categories": [
            "normes-DTU", "eurocodes", "urbanisme", "chantier", "securite",
            "materiaux", "gros-oeuvre", "second-oeuvre", "VRD", "RE2020",
            "BIM", "marches-publics", "CCTP", "diagnostics", "renovation",
            "structure", "fondations", "etancheite", "isolation", "electricite",
            "plomberie", "CVC", "domotique", "accessibilite-PMR",
        ],
        "topics": [
            "DTU 13.12 fondations", "Eurocode 2 beton", "Eurocode 3 acier",
            "RE2020 reglementation", "RT2012", "permis de construire",
            "declaration prealable", "PLU", "CCTP", "DPGF",
            "coordination SPS", "PPSPS", "DOE", "DIUO",
            "etude de sol G1 G2", "beton arme", "charpente bois",
            "isolation thermique", "pare-vapeur", "toiture vegetalisee",
            "assainissement", "ANC", "BIM IFC", "maquette numerique",
        ],
        "difficulties": ["easy", "medium", "hard", "expert"],
    },
    "juridique": {
        "categories": [
            "droit-civil", "droit-travail", "droit-commercial", "droit-societes",
            "droit-penal", "droit-administratif", "RGPD", "propriete-intellectuelle",
            "contrats", "contentieux", "arbitrage", "droit-fiscal",
            "droit-immobilier", "droit-famille", "droit-numerique",
            "droit-consommation", "droit-environnement", "droit-europeen",
        ],
        "topics": [
            "contrat de travail CDI CDD", "licenciement", "rupture conventionnelle",
            "clause de non-concurrence", "SAS statuts", "SARL", "AGO AGE",
            "cession de parts", "pacte d'associes", "bail commercial",
            "prescription civile", "responsabilite civile", "prejudice",
            "RGPD conformite", "DPO", "analyse d'impact", "cookies",
            "marque depot INPI", "brevet", "droit d'auteur",
            "procedure prudhomale", "tribunal de commerce", "injonction de payer",
            "code civil article 1240", "procedure collective", "redressement judiciaire",
        ],
        "difficulties": ["easy", "medium", "hard", "expert"],
    },
    "industrie": {
        "categories": [
            "qualite-ISO", "maintenance", "securite", "lean", "six-sigma",
            "AMDEC", "supply-chain", "logistique", "automatisation", "robotique",
            "metrologie", "environnement", "energie", "materiaux", "usinage",
            "soudure", "controle-non-destructif", "HSE", "ICPE",
        ],
        "topics": [
            "ISO 9001 qualite", "ISO 14001 environnement", "ISO 45001 securite",
            "ISO 50001 energie", "AMDEC processus", "AMDEC produit",
            "5S", "Kaizen", "TPM", "SMED", "Kanban", "Value Stream Mapping",
            "MRP planification", "ERP", "GPAO", "Cpk capabilite",
            "SPC controle statistique", "FMEA", "plan de maintenance preventive",
            "machine CNC", "soudure TIG MIG", "controle ultrason",
            "ICPE seveso", "ATEX", "fiche de donnees securite",
            "bilan carbone", "ACV analyse cycle vie", "economie circulaire",
        ],
        "difficulties": ["easy", "medium", "hard", "expert"],
    },
}

QUESTION_TYPES = [
    "factuelle",       # What is X?
    "analytique",      # Analyze X vs Y
    "procedurale",     # How to do X?
    "reglementaire",   # What does the law say about X?
    "comparative",     # Compare X and Y
    "cas-pratique",    # Given situation X, what should be done?
    "chiffree",        # What are the numbers for X?
    "definition",      # Define X in the context of Y
]

def generate_questions_batch(sector, batch_size=20):
    """Generate a batch of diverse questions via LLM."""
    config = SECTOR_TOPICS.get(sector, SECTOR_TOPICS["finance"])
    categories = random.sample(config["categories"], min(5, len(config["categories"])))
    topics = random.sample(config["topics"], min(8, len(config["topics"])))
    qtypes = random.sample(QUESTION_TYPES, min(4, len(QUESTION_TYPES)))
    difficulties = random.sample(config["difficulties"], min(3, len(config["difficulties"])))

    prompt = f"""Tu es un generateur de questions d'evaluation pour un systeme RAG expert en {sector}.

Genere exactement {batch_size} questions DIVERSES et REALISTES pour le secteur {sector}.

Regles:
- Chaque question doit etre une VRAIE question qu'un professionnel poserait
- Varie les types: {', '.join(qtypes)}
- Couvre ces categories: {', '.join(categories)}
- Utilise ces sujets: {', '.join(topics)}
- Niveaux de difficulte: {', '.join(difficulties)}
- Mix francais (80%) et anglais (20%)
- Chaque question a des mots-cles attendus dans la reponse

Reponds UNIQUEMENT en JSON valide (pas de markdown):
[
  {{
    "question": "La question complete",
    "expected_contains": "mot-cle1, mot-cle2, mot-cle3",
    "category": "categorie",
    "difficulty": "easy|medium|hard|expert",
    "language": "fr|en",
    "golden_answer": "Reponse de reference en 2-3 phrases"
  }},
  ...
]"""

    payload = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "max_tokens": 4000,
    }).encode()

    req = urllib.request.Request(
        f"{LITELLM_URL}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode())
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        # Parse JSON from response
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        questions = json.loads(content)
        if not isinstance(questions, list):
            return []

        # Enrich with metadata
        result = []
        for q in questions:
            if not isinstance(q, dict) or not q.get("question"):
                continue
            qtext = q["question"].strip()
            qid = hashlib.md5(f"{sector}:{qtext}".encode()).hexdigest()[:16]
            result.append({
                "id": qid,
                "question": qtext,
                "sector": sector,
                "pipeline": "standard",
                "expected_contains": q.get("expected_contains", ""),
                "category": q.get("category", "general"),
                "difficulty": q.get("difficulty", "medium"),
                "language": q.get("language", "fr"),
                "golden_answer": q.get("golden_answer", ""),
                "dataset_source": "llm_generated_v2",
            })

        return result

    except Exception as e:
        log(f"LLM error: {e}")
        return []


def store_questions(questions):
    """Insert questions into Supabase eval_question_bank."""
    stored = 0
    for q in questions:
        result = db_execute("""
            INSERT INTO eval_question_bank
                (id, question, sector, pipeline, expected_contains, difficulty,
                 category, language, dataset_source, golden_answer,
                 times_asked, times_passed, times_failed, avg_latency_ms,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    0, 0, 0, 0, now(), now())
            ON CONFLICT (id) DO NOTHING
        """, (
            q["id"], q["question"], q["sector"], q["pipeline"],
            q["expected_contains"], q["difficulty"],
            q["category"], q["language"], q["dataset_source"],
            q.get("golden_answer", ""),
        ))
        if result is not None:
            stored += 1
    return stored


def get_counts():
    """Get current question counts per sector."""
    result = db_execute("""
        SELECT sector, COUNT(*) FROM eval_question_bank
        GROUP BY sector ORDER BY sector
    """)
    if result:
        return {r[0]: r[1] for r in result}
    return {}


def run_generation(sector, batch_size=20, target_per_sector=100000):
    """Generate questions until target reached."""
    counts = get_counts()
    current = counts.get(sector, 0)
    remaining = target_per_sector - current

    if remaining <= 0:
        log(f"{sector}: already at {current} (target {target_per_sector})")
        return 0

    log(f"{sector}: {current}/{target_per_sector} — generating {min(batch_size, remaining)} more")

    questions = generate_questions_batch(sector, min(batch_size, remaining))
    if not questions:
        log(f"{sector}: LLM returned 0 questions")
        return 0

    stored = store_questions(questions)
    log(f"{sector}: generated {len(questions)}, stored {stored} new")
    return stored


def main():
    parser = argparse.ArgumentParser(description="Mass question generator")
    parser.add_argument("--sector", default="all", help="Sector or 'all'")
    parser.add_argument("--batch", type=int, default=30, help="Questions per LLM call")
    parser.add_argument("--target", type=int, default=100000, help="Target per sector")
    parser.add_argument("--daemon", type=int, default=0, help="Loop interval (seconds)")
    parser.add_argument("--max-cycles", type=int, default=0, help="Max cycles (0=unlimited)")
    args = parser.parse_args()

    sectors = ["finance", "btp", "juridique", "industrie"] if args.sector == "all" else [args.sector]

    cycle = 0
    total_generated = 0

    while True:
        cycle += 1
        log(f"\n{'='*60}")
        log(f"CYCLE {cycle} — Sectors: {', '.join(sectors)}")

        counts = get_counts()
        log("Current counts:")
        for s in sectors:
            c = counts.get(s, 0)
            pct = round(c / args.target * 100, 1)
            log(f"  {s}: {c:,} / {args.target:,} ({pct}%)")

        cycle_total = 0
        for sector in sectors:
            stored = run_generation(sector, args.batch, args.target)
            cycle_total += stored
            total_generated += stored
            time.sleep(2)  # Rate limit

        log(f"Cycle {cycle} done: +{cycle_total} questions (total session: {total_generated:,})")

        # Check if all targets reached
        counts = get_counts()
        all_done = all(counts.get(s, 0) >= args.target for s in sectors)
        if all_done:
            log("ALL TARGETS REACHED!")
            break

        if args.max_cycles and cycle >= args.max_cycles:
            log(f"Max cycles ({args.max_cycles}) reached")
            break

        if args.daemon <= 0:
            break

        log(f"Sleeping {args.daemon}s...")
        time.sleep(args.daemon)


if __name__ == "__main__":
    main()
