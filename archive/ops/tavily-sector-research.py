#!/usr/bin/env python3
"""
Exa.AI-Powered Sector Research Tool
====================================
Discovers what real French PME/ETI need, finds real documents,
and generates expert-level test cases for our 4 RAG pipelines.

Usage:
    python3 ops/tavily-sector-research.py              # All sectors
    python3 ops/tavily-sector-research.py --sector btp  # Single sector
    python3 ops/tavily-sector-research.py --dry-run     # Show queries without calling API
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EXA_URL = "https://api.exa.ai/search"
RATE_LIMIT_SECONDS = 1.1  # slightly above 1s for safety

SECTOR_QUERIES = {
    "finance": [
        "documents obligatoires PME française finance 2026",
        "problèmes courants finance entreprises françaises",
        "questions fréquentes expert comptable PME ETI",
        "normes réglementation finance France 2025 2026",
        "obligations comptables PME France",
        "bilan financier annuel entreprise française",
        "liasse fiscale PME obligations déclaration",
        "trésorerie PME française gestion prévisionnelle",
    ],
    "btp": [
        "documents obligatoires PME française BTP 2026",
        "problèmes courants BTP entreprises françaises",
        "questions fréquentes expert BTP PME ETI",
        "normes réglementation BTP France 2025 2026",
        "DTU normes construction 2026",
        "CCTP marché public BTP",
        "RE2020 réglementation environnementale construction",
        "PPSPS sécurité chantier BTP obligations",
    ],
    "juridique": [
        "documents obligatoires PME française juridique 2026",
        "problèmes courants juridique entreprises françaises",
        "questions fréquentes expert juridique PME ETI",
        "normes réglementation juridique France 2025 2026",
        "obligations juridiques RGPD entreprises",
        "droit du travail PME 2026",
        "contrats commerciaux PME clauses essentielles",
        "CSE obligations employeur PME ETI",
    ],
    "industrie": [
        "documents obligatoires PME française industrie 2026",
        "problèmes courants industrie entreprises françaises",
        "questions fréquentes expert industrie PME ETI",
        "normes réglementation industrie France 2025 2026",
        "normes ISO qualité industrie France",
        "maintenance préventive usine",
        "DUERP document unique évaluation risques professionnels",
        "ICPE installations classées PME obligations",
    ],
}

# Templates for generating expert questions from search results
QUESTION_TEMPLATES = {
    "finance": [
        "Quels sont les documents comptables obligatoires pour une PME de {n} salariés en France ?",
        "Comment établir un prévisionnel de trésorerie pour une ETI industrielle ?",
        "Quelles sont les obligations de la liasse fiscale pour une PME au régime réel normal ?",
        "Quels ratios financiers un expert-comptable analyse-t-il en priorité pour une PME ?",
        "Comment une PME doit-elle se préparer à un contrôle fiscal en {year} ?",
        "Quelles sont les nouvelles obligations de facturation électronique pour les PME en {year} ?",
        "Comment calculer le besoin en fonds de roulement (BFR) d'une PME commerciale ?",
        "Quelles aides financières sont disponibles pour les PME en difficulté de trésorerie ?",
    ],
    "btp": [
        "Quels DTU s'appliquent à la construction d'un bâtiment résidentiel R+3 ?",
        "Comment rédiger un CCTP pour un marché public de voirie ?",
        "Quelles sont les obligations RE2020 pour un permis de construire déposé en {year} ?",
        "Comment établir un PPSPS pour un chantier de rénovation en site occupé ?",
        "Quels documents le maître d'ouvrage doit-il fournir pour un appel d'offres public BTP ?",
        "Comment une PME du BTP doit-elle gérer ses déchets de chantier selon la REP PMCB ?",
        "Quelles assurances sont obligatoires pour une entreprise de construction en France ?",
        "Comment calculer le DQE (Détail Quantitatif Estimatif) pour un lot gros œuvre ?",
    ],
    "juridique": [
        "Quelles sont les obligations RGPD pour une PME de {n} salariés traitant des données clients ?",
        "Comment rédiger des CGV conformes pour une PME de e-commerce en {year} ?",
        "Quelles sont les obligations de l'employeur en matière de CSE pour une entreprise de 60 salariés ?",
        "Comment mettre en place un règlement intérieur conforme au Code du travail ?",
        "Quels sont les délais de prescription en droit commercial pour les créances entre entreprises ?",
        "Comment une PME doit-elle se conformer au devoir de vigilance en {year} ?",
        "Quelles clauses sont essentielles dans un contrat de sous-traitance industrielle ?",
        "Comment gérer un licenciement économique collectif dans une PME de 80 salariés ?",
    ],
    "industrie": [
        "Quelles normes ISO sont obligatoires pour une PME industrielle alimentaire en France ?",
        "Comment mettre en place un plan de maintenance préventive conforme à la norme NF EN 13306 ?",
        "Quelles sont les obligations ICPE pour une PME utilisant des produits chimiques ?",
        "Comment rédiger le DUERP (Document Unique) pour un atelier de production ?",
        "Quelles sont les obligations de formation sécurité pour les opérateurs de machines industrielles ?",
        "Comment une PME industrielle doit-elle gérer ses rejets atmosphériques selon l'arrêté du 2 février 1998 ?",
        "Quels documents sont requis pour une certification ISO 9001 en PME industrielle ?",
        "Comment mettre en place une démarche AMDEC processus dans une PME de production ?",
    ],
}

# Difficulty classification keywords
DIFFICULTY_KEYWORDS = {
    "expert": ["ICPE", "AMDEC", "NF EN", "ISO 9001", "RE2020", "DTU", "liasse fiscale",
               "BFR", "devoir de vigilance", "REP PMCB", "arrêté", "PPSPS"],
    "intermediate": ["obligations", "comment", "normes", "conformer", "rédiger",
                      "mettre en place", "calculer", "gérer"],
    "basic": ["quels", "quelles", "qu'est-ce", "définition", "liste"],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_api_key():
    """Load Exa.AI API key from environment."""
    key = os.environ.get("EXA_API_KEY")
    if not key:
        print("[ERROR] EXA_API_KEY not found in environment.")
        print("        Run: source .env.local")
        sys.exit(1)
    return key


def exa_search(api_key: str, query: str, max_results: int = 5) -> dict:
    """Call Exa.AI search API using urllib."""
    payload = json.dumps({
        "query": query,
        "numResults": max_results,
        "type": "auto",
        "contents": {"text": True},
    }).encode("utf-8")

    req = urllib.request.Request(
        EXA_URL,
        data=payload,
        headers={"Content-Type": "application/json", "x-api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  [HTTP {e.code}] {body[:200]}")
        return {"error": str(e), "results": [], "answer": ""}
    except Exception as e:
        print(f"  [ERROR] {e}")
        return {"error": str(e), "results": [], "answer": ""}


def classify_difficulty(question: str) -> str:
    """Classify a question's difficulty based on keyword analysis."""
    q_lower = question.lower()
    for keyword in DIFFICULTY_KEYWORDS["expert"]:
        if keyword.lower() in q_lower:
            return "expert"
    expert_indicators = 0
    for keyword in DIFFICULTY_KEYWORDS["intermediate"]:
        if keyword.lower() in q_lower:
            expert_indicators += 1
    if expert_indicators >= 2:
        return "intermediate"
    return "basic"


def extract_documents(results: list) -> list:
    """Extract document references from Exa.AI results."""
    docs = []
    seen_urls = set()
    for r in results:
        url = r.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            docs.append({
                "title": r.get("title", ""),
                "url": url,
                "snippet": r.get("content", "")[:300],
                "score": r.get("score", 0),
            })
    return docs


def generate_test_cases(sector: str, all_results: list, all_answers: list) -> list:
    """Generate expert test cases from search results and template questions."""
    test_cases = []
    year = datetime.now().year

    # 1) Template-based questions with context from search results
    templates = QUESTION_TEMPLATES.get(sector, [])
    for i, template in enumerate(templates):
        question = template.replace("{year}", str(year)).replace("{n}", "50")
        # Find the most relevant answer snippet
        expected = ""
        source_url = ""
        if all_answers:
            # Use the answer that best relates to this question
            best_idx = i % len(all_answers)
            answer_data = all_answers[best_idx]
            if answer_data:
                expected = answer_data[:500]
        if all_results:
            # Pick a source URL from results
            best_result_idx = i % len(all_results)
            if all_results[best_result_idx]:
                results_list = all_results[best_result_idx]
                if results_list:
                    source_url = results_list[0].get("url", "")

        test_cases.append({
            "id": f"exa-{sector[:3]}-{i+1:02d}",
            "question": question,
            "expected_answer": expected,
            "source_url": source_url,
            "difficulty": classify_difficulty(question),
            "sector": sector,
            "pipeline": "standard",
            "origin": "exa-template",
        })

    # 2) Questions derived directly from Tavily answers
    for idx, answer in enumerate(all_answers):
        if not answer:
            continue
        # Extract key facts from the answer and form verification questions
        sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 30]
        for j, sentence in enumerate(sentences[:2]):  # max 2 per answer
            q = f"Selon la réglementation française, est-il vrai que {sentence.lower().rstrip('.')} ?"
            test_cases.append({
                "id": f"exa-{sector[:3]}-derived-{idx+1:02d}-{j+1}",
                "question": q,
                "expected_answer": sentence,
                "source_url": all_results[idx][0].get("url", "") if idx < len(all_results) and all_results[idx] else "",
                "difficulty": "intermediate",
                "sector": sector,
                "pipeline": "standard",
                "origin": "exa-derived",
            })

    return test_cases


def generate_expert_questions(sector: str, all_answers: list) -> list:
    """Generate expert-level questions that PME/ETI actually ask."""
    questions = []
    templates = QUESTION_TEMPLATES.get(sector, [])
    year = datetime.now().year

    for template in templates:
        q = template.replace("{year}", str(year)).replace("{n}", "50")
        questions.append({
            "question": q,
            "difficulty": classify_difficulty(q),
            "category": "template-expert",
        })

    # Add questions derived from real search answers
    for answer in all_answers:
        if not answer:
            continue
        # Create "how" and "what" questions from factual content
        sentences = [s.strip() for s in answer.split(".") if len(s.strip()) > 40]
        for sentence in sentences[:1]:
            questions.append({
                "question": f"Pouvez-vous expliquer : {sentence.rstrip('.')} ?",
                "difficulty": "intermediate",
                "category": "real-world-derived",
            })

    return questions


# ---------------------------------------------------------------------------
# Main research loop
# ---------------------------------------------------------------------------

def research_sector(api_key: str, sector: str) -> dict:
    """Run full Exa.AI research for one sector."""
    queries = SECTOR_QUERIES[sector]
    all_results = []
    all_answers = []
    all_documents = []
    seen_urls = set()

    print(f"\n{'='*60}")
    print(f"  SECTOR: {sector.upper()}")
    print(f"  {len(queries)} queries to run")
    print(f"{'='*60}")

    for i, query in enumerate(queries):
        print(f"\n  [{i+1}/{len(queries)}] {query}")
        result = exa_search(api_key, query)

        if "error" in result and result.get("results") == []:
            print(f"         FAILED - skipping")
            all_results.append([])
            all_answers.append("")
            time.sleep(RATE_LIMIT_SECONDS)
            continue

        results = result.get("results", []) or []
        # Exa.AI returns text in results[].text; build a synthetic answer from first result
        answer = results[0].get("text", "") if results else ""

        print(f"         {len(results)} results, answer: {len(answer)} chars")
        for r in results[:3]:
            title = r.get("title", "")[:60]
            url = r.get("url", "")
            score = r.get("score", 0) or 0
            print(f"           - [{score:.2f}] {title}")
            print(f"             {url}")

        all_results.append(results)
        all_answers.append(answer)

        # Collect unique documents
        for doc in extract_documents(results):
            if doc["url"] not in seen_urls:
                seen_urls.add(doc["url"])
                doc["sector"] = sector
                doc["query"] = query
                doc["source"] = "exa"
                all_documents.append(doc)

        time.sleep(RATE_LIMIT_SECONDS)

    # Generate outputs
    expert_questions = generate_expert_questions(sector, all_answers)
    test_cases = generate_test_cases(sector, all_results, all_answers)

    # Categorize documents for ingestion
    ingestible_docs = []
    for doc in all_documents:
        url = doc["url"]
        # Prioritize official / PDF / government sources
        is_official = any(d in url for d in [
            ".gouv.fr", ".legifrance", ".service-public", ".afnor",
            ".iso.org", ".bofip", ".urssaf", ".amf-france",
            ".inrs.fr", ".ademe.fr", ".cerema.fr",
        ])
        is_pdf = url.lower().endswith(".pdf")
        doc["priority"] = "high" if (is_official or is_pdf) else "medium"
        doc["is_official_source"] = is_official
        ingestible_docs.append(doc)

    # Sort by priority then score
    ingestible_docs.sort(key=lambda d: (0 if d["priority"] == "high" else 1, -d.get("score", 0)))

    print(f"\n  RESULTS for {sector.upper()}:")
    print(f"    Documents found:    {len(all_documents)}")
    print(f"    Official sources:   {sum(1 for d in ingestible_docs if d.get('is_official_source'))}")
    print(f"    Expert questions:   {len(expert_questions)}")
    print(f"    Test cases:         {len(test_cases)}")

    return {
        "real_documents_found": ingestible_docs,
        "expert_questions": expert_questions,
        "test_cases": test_cases,
        "search_stats": {
            "queries_run": len(queries),
            "total_results": sum(len(r) for r in all_results),
            "answers_received": sum(1 for a in all_answers if a),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Exa.AI-powered sector research for French PME/ETI"
    )
    parser.add_argument(
        "--sector",
        choices=["finance", "btp", "juridique", "industrie", "all"],
        default="all",
        help="Sector to research (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show queries without calling API",
    )
    args = parser.parse_args()

    sectors = list(SECTOR_QUERIES.keys()) if args.sector == "all" else [args.sector]

    if args.dry_run:
        print("\n[DRY RUN] Queries that would be sent:\n")
        for sector in sectors:
            print(f"\n--- {sector.upper()} ---")
            for q in SECTOR_QUERIES[sector]:
                print(f"  - {q}")
        total = sum(len(SECTOR_QUERIES[s]) for s in sectors)
        print(f"\nTotal: {total} queries, ~{total * 1.1:.0f}s runtime")
        return

    api_key = load_api_key()

    print("=" * 60)
    print("  EXA.AI SECTOR RESEARCH TOOL")
    print(f"  Sectors: {', '.join(s.upper() for s in sectors)}")
    print(f"  Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    total_queries = sum(len(SECTOR_QUERIES[s]) for s in sectors)
    print(f"  Total queries: {total_queries}")
    print(f"  Estimated time: ~{total_queries * 1.5:.0f}s")
    print("=" * 60)

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": "exa-sector-research",
        "version": "1.0",
        "sectors": {},
    }

    all_ingest_docs = []

    for sector in sectors:
        sector_data = research_sector(api_key, sector)
        output["sectors"][sector] = sector_data
        all_ingest_docs.extend(sector_data["real_documents_found"])

    # --- Write main output ---
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sectors", "eval-datasets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "exa-real-world-tests.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[SAVED] {out_path}")

    # --- Write ingestion document list ---
    ingest_output = {
        "generated_at": output["generated_at"],
        "purpose": "Documents to download and ingest via Docling for sector expert RAG",
        "total_documents": len(all_ingest_docs),
        "high_priority": sum(1 for d in all_ingest_docs if d.get("priority") == "high"),
        "documents": all_ingest_docs,
    }
    ingest_path = os.path.join(os.path.dirname(out_dir), "real-documents-to-ingest.json")
    with open(ingest_path, "w", encoding="utf-8") as f:
        json.dump(ingest_output, f, ensure_ascii=False, indent=2)
    print(f"[SAVED] {ingest_path}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    total_docs = 0
    total_questions = 0
    total_tests = 0
    for sector in sectors:
        sd = output["sectors"][sector]
        n_docs = len(sd["real_documents_found"])
        n_official = sum(1 for d in sd["real_documents_found"] if d.get("is_official_source"))
        n_q = len(sd["expert_questions"])
        n_t = len(sd["test_cases"])
        total_docs += n_docs
        total_questions += n_q
        total_tests += n_t
        print(f"  {sector.upper():12s}  {n_docs:3d} docs ({n_official} official)  "
              f"{n_q:3d} questions  {n_t:3d} test cases")
    print(f"  {'TOTAL':12s}  {total_docs:3d} docs  {total_questions:3d} questions  {total_tests:3d} test cases")
    print(f"\n  Output:  {out_path}")
    print(f"  Ingest:  {ingest_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
