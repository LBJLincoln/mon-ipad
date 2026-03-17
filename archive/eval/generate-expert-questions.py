#!/usr/bin/env python3
"""
Expert Question Generator — Uses Exa.AI + LLM to create expert-level eval questions.

Flow:
  1. Exa.AI searches real sector documents per topic
  2. LLM generates expert-level questions WITH golden answers FROM real data
  3. Questions stored in eval_question_bank with dataset_source='expert_generated'
  4. Each question tagged with source URL and document reference

Usage:
  source .env.local
  python3 eval/generate-expert-questions.py                    # All sectors
  python3 eval/generate-expert-questions.py --sector finance   # One sector
  python3 eval/generate-expert-questions.py --count 50         # 50 per sector
"""

# ── IPv4 fix ──
import socket
from socket import AF_INET
_orig = socket.getaddrinfo
def _v4(*a, **kw):
    r = _orig(*a, **kw)
    return [x for x in r if x[0] == AF_INET] or r
socket.getaddrinfo = _v4

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(REPO_ROOT, ".env.local")

# Load env
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                if line.startswith("export "):
                    line = line[7:]
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v:
                    os.environ.setdefault(k, v)

_ssl = ssl.create_default_context()
_ssl.check_hostname = False
_ssl.verify_mode = ssl.CERT_NONE

EXA_API_KEY = os.environ.get("EXA_API_KEY", "")
LITELLM_URL = "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "sk-litellm-nomos-2026")
DB_URL = os.environ.get("DATABASE_URL", "")

# ── Sector Topics ──
SECTOR_TOPICS = {
    "finance": [
        "BCE taux directeur 2024 politique monetaire",
        "Credit Agricole resultats financiers EBITDA 2023",
        "Boeing revenue chiffre affaires 2022 2023",
        "BNP Paribas ratio CET1 solvabilite bale 3",
        "Societe Generale provisions risques credit 2023",
        "IFRS 17 impact assurance comptabilite",
        "ESG reporting CSRD directive europeenne finance",
        "Private equity performance rendement 2023",
        "Marche obligations taux souverains zone euro",
        "Fintech regulation MiCA crypto actifs europe",
        "CAC 40 performance sectorielle 2024",
        "Gestion actifs alternatifs hedge funds 2023",
    ],
    "btp": [
        "Eurocodes normes construction parasismique",
        "DTU 13.3 fondations profondes pieux",
        "CCTP cahier charges techniques batiment",
        "RE2020 reglementation environnementale construction",
        "NF EN 206 beton composition resistance",
        "securite chantier BTP chutes hauteur prevention",
        "PPSPS plan securite protection sante chantier",
        "diagnostic amiante batiment avant travaux",
        "BIM building information modeling construction",
        "BOAMP marches publics appel offres BTP",
        "RT2012 RE2020 performance energetique batiment",
        "gros oeuvre structure beton arme ferraillage",
    ],
    "juridique": [
        "RGPD protection donnees personnelles sanctions CNIL",
        "Code civil contrat obligations responsabilite",
        "droit travail licenciement procedure prud hommes",
        "Code commerce societes fusions acquisitions",
        "jurisprudence Cour cassation responsabilite civile 2023",
        "directive NIS2 cybersecurite obligations entreprises",
        "loi Sapin 2 anti corruption compliance",
        "droit immobilier bail commercial renouvellement",
        "propriete intellectuelle brevets marques contrefacon",
        "contentieux administratif recours urbanisme",
        "DORA regulation resilience operationnelle finance",
        "AI Act reglementation intelligence artificielle europe",
    ],
    "industrie": [
        "ISO 9001 management qualite certification",
        "maintenance predictive industrie 4.0 IoT",
        "AMDEC analyse modes defaillance processus",
        "norme ISO 14001 management environnemental",
        "lean manufacturing six sigma amelioration continue",
        "securite machines directive 2006/42/CE",
        "chaine approvisionnement supply chain resilience",
        "decarbonation industrie lourde acier ciment",
        "robotique industrielle cobots automatisation",
        "gestion risques industriels ICPE Seveso",
        "ISO 45001 sante securite travail",
        "efficacite energetique industrie audit performance",
    ],
}

EXPERT_PROMPT = """You are a senior sector expert creating evaluation questions for a RAG (Retrieval-Augmented Generation) system specialized in {sector} expertise.

Based on the following REAL DOCUMENT EXCERPTS retrieved from authoritative sources, create {count} expert-level questions that a senior professional in {sector} would ask.

REQUIREMENTS:
1. Questions must be SPECIFIC and reference real data, numbers, dates, or regulations from the documents
2. Each question must have a GOLDEN ANSWER (the correct, verifiable answer from the source)
3. Questions should test DEEP expertise, not surface-level knowledge
4. Mix question types: factual, analytical, comparative, regulatory
5. Include the expected_contains field with key terms/numbers the answer MUST include
6. Questions in French (primary market) with some in English
7. Each question must specify which pipeline is best suited: standard, graph, quantitative, or orchestrator

DOCUMENT EXCERPTS:
{documents}

Respond with EXACTLY this JSON format (no markdown, no extra text):
[
  {{
    "question": "the expert question",
    "golden_answer": "the complete correct answer (2-3 sentences)",
    "expected_contains": "key term or number that must be in any correct answer",
    "pipeline": "standard|graph|quantitative|orchestrator",
    "difficulty": "hard|expert",
    "source_url": "url of the source document",
    "source_title": "title of the source",
    "category": "factual|analytical|comparative|regulatory"
  }}
]"""


def exa_search(query, max_results=5):
    """Search Exa.AI for real documents."""
    data = json.dumps({
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {"text": True},
    }).encode()
    req = urllib.request.Request(
        "https://api.exa.ai/search",
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": EXA_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, context=_ssl, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("results", [])
    except Exception as e:
        print(f"  Exa.AI error: {e}")
        return []


def llm_generate(prompt, timeout=180):
    """Call LiteLLM to generate expert questions."""
    data = json.dumps({
        "model": "smart",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 3000,
        "temperature": 0.3,
    }).encode()
    req = urllib.request.Request(
        LITELLM_URL, data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LITELLM_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=_ssl, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
        return result["choices"][0]["message"]["content"]


def save_to_db(questions, sector):
    """Save expert questions to eval_question_bank."""
    import psycopg2
    import hashlib
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    saved = 0
    with conn.cursor() as c:
        c.execute("SET search_path TO public")
        for q in questions:
            qtext = q.get("question", "")
            if not qtext:
                continue
            qid = "exp_" + hashlib.md5(qtext.encode()).hexdigest()[:12]
            try:
                c.execute("""
                    INSERT INTO eval_question_bank
                    (id, question, sector, pipeline, expected_contains, golden_answer,
                     difficulty, dataset_source, source_url, category,
                     times_asked, times_passed, times_failed, consecutive_fails,
                     avg_score, score_trend)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'expert_generated', %s, %s,
                            0, 0, 0, 0, 0, 'stable')
                    ON CONFLICT (id) DO NOTHING
                """, (
                    qid, qtext, sector, q.get("pipeline", "standard"),
                    q.get("expected_contains", ""),
                    q.get("golden_answer", ""),
                    q.get("difficulty", "expert"),
                    q.get("source_url", ""),
                    q.get("category", "factual"),
                ))
                saved += 1
            except Exception as e:
                print(f"    DB error: {str(e)[:80]}")
    conn.close()
    return saved


def generate_for_sector(sector, topics, questions_per_topic=4):
    """Generate expert questions for one sector."""
    print(f"\n{'='*60}")
    print(f"  SECTOR: {sector.upper()}")
    print(f"{'='*60}")

    all_questions = []
    for i, topic in enumerate(topics):
        print(f"\n  [{i+1}/{len(topics)}] Exa.AI: {topic[:50]}...")
        results = exa_search(topic, max_results=3)
        if not results:
            print(f"    No results, skipping")
            continue

        # Build document context
        doc_texts = []
        for r in results[:3]:
            content = (r.get("text") or "")[:1200]
            url = r.get("url", "")
            title = r.get("title", "")
            doc_texts.append(f"SOURCE: {title}\nURL: {url}\n{content}\n")

        documents = "\n---\n".join(doc_texts)

        # Generate questions via LLM
        print(f"    LLM generating {questions_per_topic} expert questions...")
        try:
            prompt = EXPERT_PROMPT.format(
                sector=sector,
                count=questions_per_topic,
                documents=documents[:4000],
            )
            raw = llm_generate(prompt, timeout=180)

            # Parse JSON
            raw = raw.strip()
            if raw.startswith("```"):
                import re
                raw = re.sub(r'^```\w*\n?', '', raw)
                raw = re.sub(r'\n?```$', '', raw)

            questions = json.loads(raw)
            if isinstance(questions, list):
                all_questions.extend(questions)
                print(f"    Generated {len(questions)} questions")
                for q in questions:
                    print(f"      Q: {q.get('question', '')[:70]}...")
            else:
                print(f"    Unexpected format: {type(questions)}")

        except json.JSONDecodeError as e:
            print(f"    JSON parse error: {e}")
        except Exception as e:
            print(f"    LLM error: {e}")

        time.sleep(1)  # Rate limit

    # Save to DB
    if all_questions and DB_URL:
        print(f"\n  Saving {len(all_questions)} questions to Supabase...")
        saved = save_to_db(all_questions, sector)
        print(f"  Saved {saved}/{len(all_questions)} to eval_question_bank")

    # Also save to local JSON
    output_file = os.path.join(REPO_ROOT, "sectors", "eval-datasets",
                                f"expert-{sector}-generated.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w") as f:
        json.dump({
            "sector": sector,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(all_questions),
            "source": "exa+llm_expert_generation",
            "questions": all_questions,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Saved to {output_file}")

    return all_questions


def main():
    parser = argparse.ArgumentParser(description="Expert Question Generator")
    parser.add_argument("--sector", "-s", choices=["finance", "btp", "juridique", "industrie", "all"],
                        default="all")
    parser.add_argument("--count", "-c", type=int, default=4,
                        help="Questions per topic (default 4)")
    parser.add_argument("--topics", "-t", type=int, default=0,
                        help="Max topics per sector (0=all)")
    args = parser.parse_args()

    if not EXA_API_KEY:
        print("ERROR: EXA_API_KEY not set")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  EXPERT QUESTION GENERATOR")
    print(f"  Exa.AI + LLM → Expert-level eval questions")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*60}")

    sectors = list(SECTOR_TOPICS.keys()) if args.sector == "all" else [args.sector]
    total = 0

    for sector in sectors:
        topics = SECTOR_TOPICS[sector]
        if args.topics > 0:
            topics = topics[:args.topics]
        questions = generate_for_sector(sector, topics, args.count)
        total += len(questions)

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total} expert questions generated across {len(sectors)} sectors")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
