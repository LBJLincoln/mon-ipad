#!/usr/bin/env python3
"""
Generate thousands of eval questions for the Quantitative RAG pipeline.

Reads /tmp/financials_all.json (225 records) and produces structured eval
questions covering direct lookups, comparatives, sector aggregates, and
French-language variants.

Output: /home/termius/mon-ipad/sectors/eval-datasets/quant-eval-generated.json
"""

import json
import sys
from datetime import datetime, timezone
from collections import defaultdict
from itertools import combinations

INPUT_PATH = "/tmp/financials_all.json"
OUTPUT_PATH = "/home/termius/mon-ipad/sectors/eval-datasets/quant-eval-generated.json"

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

METRICS = {
    "revenue":          {"en": "revenue",            "fr": "chiffre d'affaires",     "nullable": False},
    "cost_of_revenue":  {"en": "cost of revenue",    "fr": "coût des ventes",        "nullable": False},
    "gross_profit":     {"en": "gross profit",       "fr": "marge brute",            "nullable": False},
    "operating_income": {"en": "operating income",   "fr": "résultat opérationnel",  "nullable": False},
    "net_income":       {"en": "net income",         "fr": "résultat net",           "nullable": False},
    "ebitda":           {"en": "EBITDA",             "fr": "EBITDA",                 "nullable": False},
    "eps":              {"en": "EPS",                "fr": "bénéfice par action",    "nullable": True},
    "shares_outstanding": {"en": "shares outstanding", "fr": "nombre d'actions",     "nullable": True},
    "capex":            {"en": "capital expenditure", "fr": "dépenses d'investissement", "nullable": True},
    "r_and_d":          {"en": "R&D spending",        "fr": "dépenses de R&D",       "nullable": True},
}

# English question templates for direct lookup
EN_DIRECT_TEMPLATES = [
    "What is the FY{year} {metric_en} for {company}?",
    "What was {company}'s {metric_en} in fiscal year {year}?",
    "How much {metric_en} did {company} report in FY{year}?",
]

# French question templates for direct lookup
FR_DIRECT_TEMPLATES = [
    "Quel est le {metric_fr} de {company} en {year} ?",
    "Combien de {metric_fr} a déclaré {company} pour l'exercice {year} ?",
]

# Comparative templates (English)
EN_COMPARATIVE_TEMPLATES = [
    "How did {company}'s {metric_en} change between FY{year1} and FY{year2}?",
    "Compare {company}'s {metric_en} in FY{year1} vs FY{year2}.",
    "What was the trend in {company}'s {metric_en} from FY{year1} to FY{year2}?",
]

# Comparative templates (French)
FR_COMPARATIVE_TEMPLATES = [
    "Comment a évolué le {metric_fr} de {company} entre {year1} et {year2} ?",
    "Comparez le {metric_fr} de {company} en {year1} et {year2}.",
]

# Sector aggregate templates (English)
EN_SECTOR_TEMPLATES = [
    "Which {sector} company had the highest {metric_en} in FY{year}?",
    "Which {sector} company had the lowest {metric_en} in FY{year}?",
    "What was the average {metric_en} for {sector} companies in FY{year}?",
    "What was the total {metric_en} across all {sector} companies in FY{year}?",
]

# Sector aggregate templates (French)
FR_SECTOR_TEMPLATES = [
    "Quelle entreprise du secteur {sector} a le plus haut {metric_fr} en {year} ?",
    "Quel est le {metric_fr} moyen des entreprises du secteur {sector} en {year} ?",
]

# Cross-company comparison templates
EN_CROSS_COMPANY_TEMPLATES = [
    "Which company had higher {metric_en} in FY{year}: {company1} or {company2}?",
    "Compare the FY{year} {metric_en} of {company1} and {company2}.",
]

# Ratio / derived metric templates
EN_RATIO_TEMPLATES = [
    "What was {company}'s gross margin in FY{year}?",
    "What was {company}'s operating margin in FY{year}?",
    "What was {company}'s net margin in FY{year}?",
]

FR_RATIO_TEMPLATES = [
    "Quelle était la marge brute de {company} en {year} ?",
    "Quelle était la marge opérationnelle de {company} en {year} ?",
    "Quelle était la marge nette de {company} en {year} ?",
]


def load_data():
    with open(INPUT_PATH) as f:
        data = json.load(f)
    print(f"Loaded {len(data)} records from {INPUT_PATH}")
    return data


def val_str(v):
    """Return a clean string of a numeric value, or None if null."""
    if v is None:
        return None
    s = str(v)
    # Remove trailing .0 for integers stored as floats
    if s.endswith(".0"):
        s = s[:-2]
    return s


def generate_questions(data):
    questions = []
    qid = 0

    # Index by company
    by_company = defaultdict(list)
    for rec in data:
        by_company[rec["company_name"]].append(rec)

    # Index by (sector, year)
    by_sector_year = defaultdict(list)
    for rec in data:
        by_sector_year[(rec["sector"], rec["fiscal_year"])].append(rec)

    # Determine which sectors get French questions (all, but especially btp/juridique)
    french_sectors = {"btp", "juridique", "finance", "industrie"}

    # -----------------------------------------------------------------------
    # 1) DIRECT LOOKUP questions
    # -----------------------------------------------------------------------
    print("Generating direct lookup questions...")
    for rec in data:
        company = rec["company_name"]
        year = rec["fiscal_year"]
        sector = rec["sector"]

        for metric_key, meta in METRICS.items():
            raw = rec.get(metric_key)
            vs = val_str(raw)
            if vs is None:
                continue

            # English template 1 (always)
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_DIRECT_TEMPLATES[0].format(
                    year=year, metric_en=meta["en"], company=company
                ),
                "expected_answer": f"{company} FY{year} {meta['en']}: {vs}",
                "expected_contains": vs,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "easy",
                "category": "direct_lookup",
            })

            # English template 2
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_DIRECT_TEMPLATES[1].format(
                    year=year, metric_en=meta["en"], company=company
                ),
                "expected_answer": f"{company} FY{year} {meta['en']}: {vs}",
                "expected_contains": vs,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "easy",
                "category": "direct_lookup",
            })

            # English template 3
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_DIRECT_TEMPLATES[2].format(
                    year=year, metric_en=meta["en"], company=company
                ),
                "expected_answer": f"{company} FY{year} {meta['en']}: {vs}",
                "expected_contains": vs,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "easy",
                "category": "direct_lookup",
            })

            # French templates (all sectors)
            if sector in french_sectors:
                for tmpl in FR_DIRECT_TEMPLATES:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": tmpl.format(
                            year=year, metric_fr=meta["fr"], company=company
                        ),
                        "expected_answer": f"{company} {year} {meta['fr']}: {vs}",
                        "expected_contains": vs,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "easy",
                        "category": "french",
                    })

    direct_count = len(questions)
    print(f"  Direct lookup: {direct_count} questions")

    # -----------------------------------------------------------------------
    # 2) COMPARATIVE questions (companies with 2+ years)
    # -----------------------------------------------------------------------
    print("Generating comparative questions...")
    comp_start = len(questions)
    for company, recs in by_company.items():
        if len(recs) < 2:
            continue
        recs_sorted = sorted(recs, key=lambda r: r["fiscal_year"])
        sector = recs_sorted[0]["sector"]

        # Generate pairs: consecutive years + first-last
        year_pairs = []
        for i in range(len(recs_sorted) - 1):
            year_pairs.append((recs_sorted[i], recs_sorted[i + 1]))
        # Also add first vs last if more than 2 years
        if len(recs_sorted) > 2:
            year_pairs.append((recs_sorted[0], recs_sorted[-1]))

        # Core metrics for comparison (skip less interesting ones)
        comp_metrics = ["revenue", "net_income", "ebitda", "operating_income", "gross_profit", "eps"]

        for rec1, rec2 in year_pairs:
            y1, y2 = rec1["fiscal_year"], rec2["fiscal_year"]
            for mk in comp_metrics:
                v1 = val_str(rec1.get(mk))
                v2 = val_str(rec2.get(mk))
                if v1 is None or v2 is None:
                    continue

                meta = METRICS[mk]

                # English comparative templates
                for tmpl in EN_COMPARATIVE_TEMPLATES:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": tmpl.format(
                            company=company, metric_en=meta["en"],
                            year1=y1, year2=y2
                        ),
                        "expected_answer": f"{company} {meta['en']}: FY{y1}={v1}, FY{y2}={v2}",
                        "expected_contains": company,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "medium",
                        "category": "comparative",
                    })

                # French comparative (for relevant sectors)
                if sector in french_sectors:
                    for tmpl in FR_COMPARATIVE_TEMPLATES:
                        qid += 1
                        questions.append({
                            "id": f"quant-gen-{qid:05d}",
                            "question": tmpl.format(
                                company=company, metric_fr=meta["fr"],
                                year1=y1, year2=y2
                            ),
                            "expected_answer": f"{company} {meta['fr']}: {y1}={v1}, {y2}={v2}",
                            "expected_contains": company,
                            "pipeline": "quantitative",
                            "sector": sector,
                            "dataset_source": "financials_table",
                            "difficulty": "medium",
                            "category": "french",
                        })

    comp_count = len(questions) - comp_start
    print(f"  Comparative: {comp_count} questions")

    # -----------------------------------------------------------------------
    # 3) SECTOR AGGREGATE questions
    # -----------------------------------------------------------------------
    print("Generating sector aggregate questions...")
    agg_start = len(questions)
    agg_metrics = ["revenue", "net_income", "ebitda", "operating_income", "eps"]

    for (sector, year), recs in by_sector_year.items():
        if len(recs) < 2:
            continue

        for mk in agg_metrics:
            meta = METRICS[mk]
            vals = [(r["company_name"], r.get(mk)) for r in recs if r.get(mk) is not None]
            if len(vals) < 2:
                continue

            # Parse to float for comparison
            try:
                parsed = [(name, float(v)) for name, v in vals]
            except (ValueError, TypeError):
                continue

            top_company = max(parsed, key=lambda x: x[1])[0]
            bottom_company = min(parsed, key=lambda x: x[1])[0]
            avg_val = sum(v for _, v in parsed) / len(parsed)

            # "Which {sector} company had the highest..."
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_SECTOR_TEMPLATES[0].format(
                    sector=sector, metric_en=meta["en"], year=year
                ),
                "expected_answer": f"{top_company} had the highest {meta['en']} in {sector} FY{year}",
                "expected_contains": top_company,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "hard",
                "category": "sector_aggregate",
            })

            # "Which {sector} company had the lowest..."
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_SECTOR_TEMPLATES[1].format(
                    sector=sector, metric_en=meta["en"], year=year
                ),
                "expected_answer": f"{bottom_company} had the lowest {meta['en']} in {sector} FY{year}",
                "expected_contains": bottom_company,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "hard",
                "category": "sector_aggregate",
            })

            # "What was the average..."
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_SECTOR_TEMPLATES[2].format(
                    sector=sector, metric_en=meta["en"], year=year
                ),
                "expected_answer": f"Average {meta['en']} for {sector} in FY{year}: {avg_val:.0f}",
                "expected_contains": sector,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "hard",
                "category": "sector_aggregate",
            })

            # "What was the total..."
            total_val = sum(v for _, v in parsed)
            qid += 1
            questions.append({
                "id": f"quant-gen-{qid:05d}",
                "question": EN_SECTOR_TEMPLATES[3].format(
                    sector=sector, metric_en=meta["en"], year=year
                ),
                "expected_answer": f"Total {meta['en']} for {sector} in FY{year}: {total_val:.0f}",
                "expected_contains": sector,
                "pipeline": "quantitative",
                "sector": sector,
                "dataset_source": "financials_table",
                "difficulty": "hard",
                "category": "sector_aggregate",
            })

            # French sector templates
            if sector in french_sectors:
                # Highest
                qid += 1
                questions.append({
                    "id": f"quant-gen-{qid:05d}",
                    "question": FR_SECTOR_TEMPLATES[0].format(
                        sector=sector, metric_fr=meta["fr"], year=year
                    ),
                    "expected_answer": f"{top_company} a le plus haut {meta['fr']} en {sector} {year}",
                    "expected_contains": top_company,
                    "pipeline": "quantitative",
                    "sector": sector,
                    "dataset_source": "financials_table",
                    "difficulty": "hard",
                    "category": "french",
                })

                # Average
                qid += 1
                questions.append({
                    "id": f"quant-gen-{qid:05d}",
                    "question": FR_SECTOR_TEMPLATES[1].format(
                        sector=sector, metric_fr=meta["fr"], year=year
                    ),
                    "expected_answer": f"{meta['fr']} moyen {sector} {year}: {avg_val:.0f}",
                    "expected_contains": sector,
                    "pipeline": "quantitative",
                    "sector": sector,
                    "dataset_source": "financials_table",
                    "difficulty": "hard",
                    "category": "french",
                })

    agg_count = len(questions) - agg_start
    print(f"  Sector aggregate: {agg_count} questions")

    # -----------------------------------------------------------------------
    # 4) CROSS-COMPANY COMPARISON questions
    # -----------------------------------------------------------------------
    print("Generating cross-company comparison questions...")
    cross_start = len(questions)
    cross_metrics = ["revenue", "net_income", "ebitda"]

    for (sector, year), recs in by_sector_year.items():
        if len(recs) < 2:
            continue
        # Pick pairs (limit to avoid explosion: max 10 pairs per sector-year)
        pairs = list(combinations(recs, 2))
        if len(pairs) > 10:
            # Take first 5 + last 5 for diversity
            pairs = pairs[:5] + pairs[-5:]

        for rec1, rec2 in pairs:
            c1, c2 = rec1["company_name"], rec2["company_name"]
            for mk in cross_metrics:
                v1 = rec1.get(mk)
                v2 = rec2.get(mk)
                if v1 is None or v2 is None:
                    continue
                try:
                    winner = c1 if float(v1) >= float(v2) else c2
                except (ValueError, TypeError):
                    continue

                meta = METRICS[mk]
                for tmpl in EN_CROSS_COMPANY_TEMPLATES:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": tmpl.format(
                            metric_en=meta["en"], year=year,
                            company1=c1, company2=c2
                        ),
                        "expected_answer": f"{winner} had higher {meta['en']} in FY{year}",
                        "expected_contains": winner,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "medium",
                        "category": "comparative",
                    })

    cross_count = len(questions) - cross_start
    print(f"  Cross-company: {cross_count} questions")

    # -----------------------------------------------------------------------
    # 5) RATIO / DERIVED METRIC questions
    # -----------------------------------------------------------------------
    print("Generating ratio/derived metric questions...")
    ratio_start = len(questions)

    for rec in data:
        company = rec["company_name"]
        year = rec["fiscal_year"]
        sector = rec["sector"]

        try:
            revenue_f = float(rec["revenue"])
        except (ValueError, TypeError):
            continue
        if revenue_f == 0:
            continue

        # Gross margin
        gp = rec.get("gross_profit")
        if gp is not None:
            try:
                gm = float(gp) / revenue_f * 100
                gm_str = f"{gm:.1f}%"
                qid += 1
                questions.append({
                    "id": f"quant-gen-{qid:05d}",
                    "question": EN_RATIO_TEMPLATES[0].format(company=company, year=year),
                    "expected_answer": f"{company} FY{year} gross margin: {gm_str}",
                    "expected_contains": company,
                    "pipeline": "quantitative",
                    "sector": sector,
                    "dataset_source": "financials_table",
                    "difficulty": "medium",
                    "category": "derived_ratio",
                })
                if sector in french_sectors:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": FR_RATIO_TEMPLATES[0].format(company=company, year=year),
                        "expected_answer": f"Marge brute de {company} en {year}: {gm_str}",
                        "expected_contains": company,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "medium",
                        "category": "french",
                    })
            except (ValueError, TypeError):
                pass

        # Operating margin
        oi = rec.get("operating_income")
        if oi is not None:
            try:
                om = float(oi) / revenue_f * 100
                om_str = f"{om:.1f}%"
                qid += 1
                questions.append({
                    "id": f"quant-gen-{qid:05d}",
                    "question": EN_RATIO_TEMPLATES[1].format(company=company, year=year),
                    "expected_answer": f"{company} FY{year} operating margin: {om_str}",
                    "expected_contains": company,
                    "pipeline": "quantitative",
                    "sector": sector,
                    "dataset_source": "financials_table",
                    "difficulty": "medium",
                    "category": "derived_ratio",
                })
                if sector in french_sectors:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": FR_RATIO_TEMPLATES[1].format(company=company, year=year),
                        "expected_answer": f"Marge opérationnelle de {company} en {year}: {om_str}",
                        "expected_contains": company,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "medium",
                        "category": "french",
                    })
            except (ValueError, TypeError):
                pass

        # Net margin
        ni = rec.get("net_income")
        if ni is not None:
            try:
                nm = float(ni) / revenue_f * 100
                nm_str = f"{nm:.1f}%"
                qid += 1
                questions.append({
                    "id": f"quant-gen-{qid:05d}",
                    "question": EN_RATIO_TEMPLATES[2].format(company=company, year=year),
                    "expected_answer": f"{company} FY{year} net margin: {nm_str}",
                    "expected_contains": company,
                    "pipeline": "quantitative",
                    "sector": sector,
                    "dataset_source": "financials_table",
                    "difficulty": "medium",
                    "category": "derived_ratio",
                })
                if sector in french_sectors:
                    qid += 1
                    questions.append({
                        "id": f"quant-gen-{qid:05d}",
                        "question": FR_RATIO_TEMPLATES[2].format(company=company, year=year),
                        "expected_answer": f"Marge nette de {company} en {year}: {nm_str}",
                        "expected_contains": company,
                        "pipeline": "quantitative",
                        "sector": sector,
                        "dataset_source": "financials_table",
                        "difficulty": "medium",
                        "category": "french",
                    })
            except (ValueError, TypeError):
                pass

    ratio_count = len(questions) - ratio_start
    print(f"  Ratio/derived: {ratio_count} questions")

    return questions


def print_stats(questions):
    """Print distribution statistics."""
    from collections import Counter
    print("\n--- Distribution ---")

    cats = Counter(q["category"] for q in questions)
    print("By category:")
    for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n}")

    diffs = Counter(q["difficulty"] for q in questions)
    print("By difficulty:")
    for d, n in sorted(diffs.items()):
        print(f"  {d}: {n}")

    sects = Counter(q["sector"] for q in questions)
    print("By sector:")
    for s, n in sorted(sects.items(), key=lambda x: -x[1]):
        print(f"  {s}: {n}")


def main():
    print("=" * 60)
    print("Quantitative Pipeline Eval Question Generator")
    print("=" * 60)

    data = load_data()
    questions = generate_questions(data)

    print(f"\n{'=' * 60}")
    print(f"TOTAL QUESTIONS GENERATED: {len(questions)}")
    print(f"{'=' * 60}")

    if len(questions) < 3000:
        print(f"WARNING: Only {len(questions)} questions generated (target: 3000+)")

    print_stats(questions)

    output = {
        "metadata": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "total": len(questions),
            "source": "financials_table",
            "input_records": len(data),
            "generator": "eval/generate-quant-questions.py",
        },
        "questions": questions,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nWritten to: {OUTPUT_PATH}")
    print(f"File size: {len(json.dumps(output, ensure_ascii=False)) / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
