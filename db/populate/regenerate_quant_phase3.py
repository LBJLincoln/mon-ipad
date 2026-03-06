#!/usr/bin/env python3
"""
Regenerate Phase 3 Quantitative dataset with CORRECT expected answers from Supabase.

Problem: The original quantitative-500.json had synthetic expected answers that don't match
the actual values in Supabase. This script generates Q&A pairs from the real seed data.

Data source: db/migrations/financial-tables.sql (3 companies x 4 FY + 4 Q2023 = 24 rows)
Output: datasets/phase-3/quantitative-500-v2.json

Usage:
    source .env.local
    python3 db/populate/regenerate_quant_phase3.py
    python3 db/populate/regenerate_quant_phase3.py --count 250  # fewer questions
"""

import json
import os
import random
import sys
from pathlib import Path
from typing import List, Dict, Any

SEED = 42
random.seed(SEED)
OUTPUT_DIR = Path("/home/termius/mon-ipad/datasets/phase-3")

# ============================================================
# REAL FINANCIAL DATA from db/migrations/financial-tables.sql
# 3 companies x (4 FY + 4 Q2023) = 24 rows
# ============================================================

FINANCIALS = [
    # TechVision Inc - FY 2020-2023
    {"company": "TechVision Inc", "cid": "techvision", "year": 2020, "period": "FY",
     "revenue": 4250000000, "cogs": 1487500000, "gross_profit": 2762500000,
     "opex": 1700000000, "rd": 850000000, "sga": 850000000,
     "operating_income": 1062500000, "int_income": 12500000, "int_expense": 45000000,
     "other_income": 8000000, "income_before_tax": 1038000000, "tax": 218000000,
     "net_income": 820000000, "basic_eps": 8.20, "diluted_eps": 7.95, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2021, "period": "FY",
     "revenue": 5100000000, "cogs": 1734000000, "gross_profit": 3366000000,
     "opex": 1938000000, "rd": 1020000000, "sga": 918000000,
     "operating_income": 1428000000, "int_income": 15000000, "int_expense": 42000000,
     "other_income": 10000000, "income_before_tax": 1411000000, "tax": 296000000,
     "net_income": 1115000000, "basic_eps": 11.15, "diluted_eps": 10.80, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2022, "period": "FY",
     "revenue": 5865000000, "cogs": 1935450000, "gross_profit": 3929550000,
     "opex": 2229000000, "rd": 1173000000, "sga": 1056000000,
     "operating_income": 1700550000, "int_income": 25000000, "int_expense": 38000000,
     "other_income": 5000000, "income_before_tax": 1692550000, "tax": 355000000,
     "net_income": 1337550000, "basic_eps": 13.38, "diluted_eps": 12.95, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2023, "period": "FY",
     "revenue": 6745000000, "cogs": 2158400000, "gross_profit": 4586600000,
     "opex": 2563000000, "rd": 1349000000, "sga": 1214000000,
     "operating_income": 2023600000, "int_income": 45000000, "int_expense": 35000000,
     "other_income": 12000000, "income_before_tax": 2045600000, "tax": 429000000,
     "net_income": 1616600000, "basic_eps": 16.17, "diluted_eps": 15.65, "shares": 100000000},
    # TechVision quarterly 2023
    {"company": "TechVision Inc", "cid": "techvision", "year": 2023, "period": "Q1",
     "revenue": 1552350000, "cogs": 496752000, "gross_profit": 1055598000,
     "opex": 589690000, "rd": 310390000, "sga": 279300000,
     "operating_income": 465908000, "int_income": 10000000, "int_expense": 9000000,
     "other_income": 3000000, "income_before_tax": 469908000, "tax": 98681000,
     "net_income": 371227000, "basic_eps": 3.71, "diluted_eps": 3.59, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2023, "period": "Q2",
     "revenue": 1619400000, "cogs": 518208000, "gross_profit": 1101192000,
     "opex": 615372000, "rd": 323880000, "sga": 291492000,
     "operating_income": 485820000, "int_income": 11000000, "int_expense": 9000000,
     "other_income": 3000000, "income_before_tax": 490820000, "tax": 103072000,
     "net_income": 387748000, "basic_eps": 3.88, "diluted_eps": 3.75, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2023, "period": "Q3",
     "revenue": 1721750000, "cogs": 550960000, "gross_profit": 1170790000,
     "opex": 654265000, "rd": 344350000, "sga": 309915000,
     "operating_income": 516525000, "int_income": 12000000, "int_expense": 8500000,
     "other_income": 3000000, "income_before_tax": 523025000, "tax": 109835000,
     "net_income": 413190000, "basic_eps": 4.13, "diluted_eps": 4.00, "shares": 100000000},
    {"company": "TechVision Inc", "cid": "techvision", "year": 2023, "period": "Q4",
     "revenue": 1851500000, "cogs": 592480000, "gross_profit": 1259020000,
     "opex": 703673000, "rd": 370300000, "sga": 333373000,
     "operating_income": 555347000, "int_income": 12000000, "int_expense": 8500000,
     "other_income": 3000000, "income_before_tax": 561847000, "tax": 117988000,
     "net_income": 443859000, "basic_eps": 4.44, "diluted_eps": 4.30, "shares": 100000000},

    # GreenEnergy Corp - FY 2020-2023
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2020, "period": "FY",
     "revenue": 1800000000, "cogs": 1080000000, "gross_profit": 720000000,
     "opex": 504000000, "rd": 180000000, "sga": 324000000,
     "operating_income": 216000000, "int_income": 5000000, "int_expense": 28000000,
     "other_income": 3000000, "income_before_tax": 196000000, "tax": 41200000,
     "net_income": 154800000, "basic_eps": 3.10, "diluted_eps": 2.98, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2021, "period": "FY",
     "revenue": 2160000000, "cogs": 1252800000, "gross_profit": 907200000,
     "opex": 583200000, "rd": 216000000, "sga": 367200000,
     "operating_income": 324000000, "int_income": 6000000, "int_expense": 25000000,
     "other_income": 4000000, "income_before_tax": 309000000, "tax": 64900000,
     "net_income": 244100000, "basic_eps": 4.88, "diluted_eps": 4.70, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2022, "period": "FY",
     "revenue": 2808000000, "cogs": 1544400000, "gross_profit": 1263600000,
     "opex": 702000000, "rd": 281000000, "sga": 421000000,
     "operating_income": 561600000, "int_income": 8000000, "int_expense": 22000000,
     "other_income": 6000000, "income_before_tax": 553600000, "tax": 116300000,
     "net_income": 437300000, "basic_eps": 8.75, "diluted_eps": 8.42, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2023, "period": "FY",
     "revenue": 3650000000, "cogs": 1935000000, "gross_profit": 1715000000,
     "opex": 876000000, "rd": 365000000, "sga": 511000000,
     "operating_income": 839000000, "int_income": 12000000, "int_expense": 18000000,
     "other_income": 8000000, "income_before_tax": 841000000, "tax": 176600000,
     "net_income": 664400000, "basic_eps": 13.29, "diluted_eps": 12.80, "shares": 50000000},
    # GreenEnergy quarterly 2023
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2023, "period": "Q1",
     "revenue": 803000000, "cogs": 425590000, "gross_profit": 377410000,
     "opex": 192720000, "rd": 80300000, "sga": 112420000,
     "operating_income": 184690000, "int_income": 2500000, "int_expense": 4500000,
     "other_income": 2000000, "income_before_tax": 184690000, "tax": 38785000,
     "net_income": 145905000, "basic_eps": 2.92, "diluted_eps": 2.81, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2023, "period": "Q2",
     "revenue": 876500000, "cogs": 464545000, "gross_profit": 411955000,
     "opex": 210360000, "rd": 87650000, "sga": 122710000,
     "operating_income": 201595000, "int_income": 3000000, "int_expense": 4500000,
     "other_income": 2000000, "income_before_tax": 202095000, "tax": 42440000,
     "net_income": 159655000, "basic_eps": 3.19, "diluted_eps": 3.07, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2023, "period": "Q3",
     "revenue": 949000000, "cogs": 503170000, "gross_profit": 445830000,
     "opex": 227760000, "rd": 94900000, "sga": 132860000,
     "operating_income": 218070000, "int_income": 3200000, "int_expense": 4500000,
     "other_income": 2000000, "income_before_tax": 218770000, "tax": 45941000,
     "net_income": 172829000, "basic_eps": 3.46, "diluted_eps": 3.33, "shares": 50000000},
    {"company": "GreenEnergy Corp", "cid": "greenenergy", "year": 2023, "period": "Q4",
     "revenue": 1021500000, "cogs": 541395000, "gross_profit": 480105000,
     "opex": 245160000, "rd": 102150000, "sga": 143010000,
     "operating_income": 234945000, "int_income": 3300000, "int_expense": 4500000,
     "other_income": 2000000, "income_before_tax": 235745000, "tax": 49507000,
     "net_income": 186238000, "basic_eps": 3.72, "diluted_eps": 3.59, "shares": 50000000},

    # HealthPlus Labs - FY 2020-2023
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2020, "period": "FY",
     "revenue": 320000000, "cogs": 176000000, "gross_profit": 144000000,
     "opex": 128000000, "rd": 96000000, "sga": 32000000,
     "operating_income": 16000000, "int_income": 1000000, "int_expense": 12000000,
     "other_income": 500000, "income_before_tax": 5500000, "tax": 1155000,
     "net_income": 4345000, "basic_eps": 0.17, "diluted_eps": 0.16, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2021, "period": "FY",
     "revenue": 480000000, "cogs": 252000000, "gross_profit": 228000000,
     "opex": 172800000, "rd": 134400000, "sga": 38400000,
     "operating_income": 55200000, "int_income": 1500000, "int_expense": 10000000,
     "other_income": 1000000, "income_before_tax": 47700000, "tax": 10017000,
     "net_income": 37683000, "basic_eps": 1.51, "diluted_eps": 1.45, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2022, "period": "FY",
     "revenue": 768000000, "cogs": 391680000, "gross_profit": 376320000,
     "opex": 261120000, "rd": 199680000, "sga": 61440000,
     "operating_income": 115200000, "int_income": 3000000, "int_expense": 8000000,
     "other_income": 2000000, "income_before_tax": 112200000, "tax": 23562000,
     "net_income": 88638000, "basic_eps": 3.55, "diluted_eps": 3.41, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2023, "period": "FY",
     "revenue": 1152000000, "cogs": 553000000, "gross_profit": 599000000,
     "opex": 380160000, "rd": 288000000, "sga": 92160000,
     "operating_income": 218840000, "int_income": 5000000, "int_expense": 6000000,
     "other_income": 3000000, "income_before_tax": 220840000, "tax": 46376000,
     "net_income": 174464000, "basic_eps": 6.98, "diluted_eps": 6.71, "shares": 25000000},
    # HealthPlus quarterly 2023
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2023, "period": "Q1",
     "revenue": 253440000, "cogs": 121652000, "gross_profit": 131788000,
     "opex": 83635000, "rd": 63360000, "sga": 20275000,
     "operating_income": 48153000, "int_income": 1000000, "int_expense": 1500000,
     "other_income": 750000, "income_before_tax": 48403000, "tax": 10165000,
     "net_income": 38238000, "basic_eps": 1.53, "diluted_eps": 1.47, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2023, "period": "Q2",
     "revenue": 276480000, "cogs": 132710000, "gross_profit": 143770000,
     "opex": 91238000, "rd": 69120000, "sga": 22118000,
     "operating_income": 52532000, "int_income": 1200000, "int_expense": 1500000,
     "other_income": 750000, "income_before_tax": 52982000, "tax": 11126000,
     "net_income": 41856000, "basic_eps": 1.67, "diluted_eps": 1.61, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2023, "period": "Q3",
     "revenue": 299520000, "cogs": 143770000, "gross_profit": 155750000,
     "opex": 98842000, "rd": 74880000, "sga": 23962000,
     "operating_income": 56908000, "int_income": 1300000, "int_expense": 1500000,
     "other_income": 750000, "income_before_tax": 57458000, "tax": 12066000,
     "net_income": 45392000, "basic_eps": 1.82, "diluted_eps": 1.75, "shares": 25000000},
    {"company": "HealthPlus Labs", "cid": "healthplus", "year": 2023, "period": "Q4",
     "revenue": 322560000, "cogs": 154868000, "gross_profit": 167692000,
     "opex": 106445000, "rd": 80640000, "sga": 25805000,
     "operating_income": 61247000, "int_income": 1500000, "int_expense": 1500000,
     "other_income": 750000, "income_before_tax": 61997000, "tax": 13019000,
     "net_income": 48978000, "basic_eps": 1.96, "diluted_eps": 1.88, "shares": 25000000},
]


def fmt_dollars(val: float) -> str:
    """Format as dollar string."""
    if abs(val) >= 1e9:
        return f"${val/1e9:,.2f} billion"
    elif abs(val) >= 1e6:
        return f"${val/1e6:,.2f} million"
    else:
        return f"${val:,.2f}"


def fmt_pct(val: float) -> str:
    """Format as percentage string."""
    return f"{val:.1f}%"


def get_fy(company: str, year: int) -> Dict:
    """Get FY data for a company/year."""
    for row in FINANCIALS:
        if row["company"] == company and row["year"] == year and row["period"] == "FY":
            return row
    return {}


def get_quarter(company: str, year: int, quarter: str) -> Dict:
    """Get quarterly data."""
    for row in FINANCIALS:
        if row["company"] == company and row["year"] == year and row["period"] == quarter:
            return row
    return {}


COMPANIES = ["TechVision Inc", "GreenEnergy Corp", "HealthPlus Labs"]
FY_YEARS = [2020, 2021, 2022, 2023]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]


def generate_direct_lookup_questions() -> List[Dict]:
    """Generate questions that directly look up a single financial field."""
    questions = []
    fields = [
        ("revenue", "revenue", fmt_dollars),
        ("net_income", "net income", fmt_dollars),
        ("operating_income", "operating income", fmt_dollars),
        ("gross_profit", "gross profit", fmt_dollars),
        ("cogs", "cost of goods sold", fmt_dollars),
        ("opex", "operating expenses", fmt_dollars),
        ("rd", "R&D expenses", fmt_dollars),
        ("sga", "selling, general and administrative expenses", fmt_dollars),
        ("tax", "tax expense", fmt_dollars),
        ("income_before_tax", "income before tax", fmt_dollars),
        ("basic_eps", "basic earnings per share", lambda v: f"${v:.2f}"),
        ("diluted_eps", "diluted earnings per share", lambda v: f"${v:.2f}"),
    ]

    templates = [
        "What was {company}'s {field_name} in {year}?",
        "Report the {field_name} of {company} for fiscal year {year}.",
        "How much was {company}'s {field_name} in {year}?",
        "According to financial data, what was the {field_name} of {company} in {year}?",
        "What is the {field_name} for {company} in FY{year}?",
    ]

    for company in COMPANIES:
        for year in FY_YEARS:
            row = get_fy(company, year)
            if not row:
                continue
            for field_key, field_name, formatter in fields:
                template = random.choice(templates)
                question = template.format(company=company, field_name=field_name, year=year)
                answer = formatter(row[field_key])
                questions.append({
                    "question": question,
                    "answer": answer,
                    "context": None,
                    "dataset_name": "supabase_financial",
                    "rag_target": "quantitative",
                    "item_index": len(questions),
                    "difficulty": "medium",
                    "phase": "phase3",
                    "sql_table": "financials",
                    "sql_field": field_key,
                    "raw_value": row[field_key]
                })

    return questions


def generate_calculated_metric_questions() -> List[Dict]:
    """Generate questions about derived metrics (margins, ratios, etc.)."""
    questions = []

    for company in COMPANIES:
        for year in FY_YEARS:
            row = get_fy(company, year)
            if not row:
                continue

            # Operating margin
            op_margin = row["operating_income"] / row["revenue"] * 100
            questions.append({
                "question": f"What was {company}'s operating margin in {year}?",
                "answer": fmt_pct(op_margin),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "operating_margin",
                "raw_value": round(op_margin, 1)
            })

            # Gross margin
            gross_margin = row["gross_profit"] / row["revenue"] * 100
            questions.append({
                "question": f"What was the gross margin of {company} in {year}?",
                "answer": fmt_pct(gross_margin),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "gross_margin",
                "raw_value": round(gross_margin, 1)
            })

            # Net profit margin
            net_margin = row["net_income"] / row["revenue"] * 100
            questions.append({
                "question": f"What was {company}'s net profit margin in {year}?",
                "answer": fmt_pct(net_margin),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "net_margin",
                "raw_value": round(net_margin, 1)
            })

            # R&D as % of revenue
            rd_pct = row["rd"] / row["revenue"] * 100
            questions.append({
                "question": f"What percentage of revenue did {company} spend on R&D in {year}?",
                "answer": fmt_pct(rd_pct),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "rd_pct",
                "raw_value": round(rd_pct, 1)
            })

            # Effective tax rate
            if row["income_before_tax"] > 0:
                tax_rate = row["tax"] / row["income_before_tax"] * 100
                questions.append({
                    "question": f"What was {company}'s effective tax rate in {year}?",
                    "answer": fmt_pct(tax_rate),
                    "context": None,
                    "dataset_name": "supabase_financial",
                    "rag_target": "quantitative",
                    "item_index": len(questions),
                    "difficulty": "hard",
                    "phase": "phase3",
                    "sql_table": "financials",
                    "sql_field": "tax_rate",
                    "raw_value": round(tax_rate, 1)
                })

    return questions


def generate_yoy_growth_questions() -> List[Dict]:
    """Generate year-over-year growth comparison questions."""
    questions = []

    growth_fields = [
        ("revenue", "revenue"),
        ("net_income", "net income"),
        ("operating_income", "operating income"),
        ("rd", "R&D spending"),
    ]

    templates = [
        "What was the year-over-year growth rate of {company}'s {field} from {y1} to {y2}?",
        "By what percentage did {company}'s {field} change from {y1} to {y2}?",
        "How much did {company}'s {field} grow between {y1} and {y2}?",
    ]

    for company in COMPANIES:
        for i in range(len(FY_YEARS) - 1):
            y1, y2 = FY_YEARS[i], FY_YEARS[i + 1]
            row1 = get_fy(company, y1)
            row2 = get_fy(company, y2)
            if not row1 or not row2:
                continue

            for field_key, field_name in growth_fields:
                if row1[field_key] == 0:
                    continue
                growth = (row2[field_key] - row1[field_key]) / row1[field_key] * 100
                template = random.choice(templates)
                question = template.format(company=company, field=field_name, y1=y1, y2=y2)
                questions.append({
                    "question": question,
                    "answer": fmt_pct(growth),
                    "context": None,
                    "dataset_name": "supabase_financial",
                    "rag_target": "quantitative",
                    "item_index": len(questions),
                    "difficulty": "hard",
                    "phase": "phase3",
                    "sql_table": "financials",
                    "sql_field": f"yoy_{field_key}",
                    "raw_value": round(growth, 1)
                })

        # Revenue increase/decrease direction
        for i in range(len(FY_YEARS) - 1):
            y1, y2 = FY_YEARS[i], FY_YEARS[i + 1]
            row1 = get_fy(company, y1)
            row2 = get_fy(company, y2)
            if not row1 or not row2:
                continue
            direction = "increase" if row2["revenue"] > row1["revenue"] else "decrease"
            questions.append({
                "question": f"Did {company}'s revenue increase or decrease from {y1} to {y2}?",
                "answer": direction,
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "easy",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "revenue_direction",
                "raw_value": direction
            })

    return questions


def generate_comparison_questions() -> List[Dict]:
    """Generate cross-company comparison questions."""
    questions = []

    for year in FY_YEARS:
        rows = {c: get_fy(c, year) for c in COMPANIES}
        if not all(rows.values()):
            continue

        # Highest revenue
        max_rev_co = max(COMPANIES, key=lambda c: rows[c]["revenue"])
        questions.append({
            "question": f"Which company had the highest revenue in {year}?",
            "answer": max_rev_co,
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "medium",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "max_revenue_company",
            "raw_value": max_rev_co
        })

        # Highest net income
        max_ni_co = max(COMPANIES, key=lambda c: rows[c]["net_income"])
        questions.append({
            "question": f"Which company had the highest net income in {year}?",
            "answer": max_ni_co,
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "medium",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "max_net_income_company",
            "raw_value": max_ni_co
        })

        # Highest operating margin
        margins = {c: rows[c]["operating_income"] / rows[c]["revenue"] * 100 for c in COMPANIES}
        max_margin_co = max(COMPANIES, key=lambda c: margins[c])
        questions.append({
            "question": f"Which company had the highest operating margin in {year}?",
            "answer": max_margin_co,
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "max_margin_company",
            "raw_value": max_margin_co
        })

        # Highest R&D as % of revenue
        rd_pcts = {c: rows[c]["rd"] / rows[c]["revenue"] * 100 for c in COMPANIES}
        max_rd_co = max(COMPANIES, key=lambda c: rd_pcts[c])
        questions.append({
            "question": f"Which company invested the most in R&D as a percentage of revenue in {year}?",
            "answer": max_rd_co,
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "max_rd_pct_company",
            "raw_value": max_rd_co
        })

        # Total revenue across all companies
        total_rev = sum(rows[c]["revenue"] for c in COMPANIES)
        questions.append({
            "question": f"What was the combined total revenue of TechVision, GreenEnergy, and HealthPlus in {year}?",
            "answer": fmt_dollars(total_rev),
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "total_revenue",
            "raw_value": total_rev
        })

    return questions


def generate_quarterly_questions() -> List[Dict]:
    """Generate questions about quarterly data (2023 only)."""
    questions = []

    for company in COMPANIES:
        for q in QUARTERS:
            row = get_quarter(company, 2023, q)
            if not row:
                continue

            # Revenue
            questions.append({
                "question": f"What was {company}'s revenue in {q} 2023?",
                "answer": fmt_dollars(row["revenue"]),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "revenue",
                "raw_value": row["revenue"]
            })

            # Net income
            questions.append({
                "question": f"What was the net income of {company} in {q} 2023?",
                "answer": fmt_dollars(row["net_income"]),
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "net_income",
                "raw_value": row["net_income"]
            })

            # EPS
            questions.append({
                "question": f"What was {company}'s basic EPS in {q} 2023?",
                "answer": f"${row['basic_eps']:.2f}",
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "medium",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "basic_eps",
                "raw_value": row["basic_eps"]
            })

        # Best quarter
        q_revenues = {q: get_quarter(company, 2023, q)["revenue"]
                      for q in QUARTERS if get_quarter(company, 2023, q)}
        if q_revenues:
            best_q = max(q_revenues, key=q_revenues.get)
            questions.append({
                "question": f"In which quarter of 2023 did {company} have the highest revenue?",
                "answer": best_q,
                "context": None,
                "dataset_name": "supabase_financial",
                "rag_target": "quantitative",
                "item_index": len(questions),
                "difficulty": "hard",
                "phase": "phase3",
                "sql_table": "financials",
                "sql_field": "best_quarter",
                "raw_value": best_q
            })

        # Q-over-Q growth
        for i in range(len(QUARTERS) - 1):
            q1, q2 = QUARTERS[i], QUARTERS[i + 1]
            r1 = get_quarter(company, 2023, q1)
            r2 = get_quarter(company, 2023, q2)
            if r1 and r2 and r1["revenue"] > 0:
                qoq = (r2["revenue"] - r1["revenue"]) / r1["revenue"] * 100
                questions.append({
                    "question": f"What was the quarter-over-quarter revenue growth for {company} from {q1} to {q2} 2023?",
                    "answer": fmt_pct(qoq),
                    "context": None,
                    "dataset_name": "supabase_financial",
                    "rag_target": "quantitative",
                    "item_index": len(questions),
                    "difficulty": "hard",
                    "phase": "phase3",
                    "sql_table": "financials",
                    "sql_field": "qoq_revenue_growth",
                    "raw_value": round(qoq, 1)
                })

    return questions


def generate_multi_year_questions() -> List[Dict]:
    """Generate questions spanning multiple years (CAGR, trends)."""
    questions = []

    for company in COMPANIES:
        r2020 = get_fy(company, 2020)
        r2023 = get_fy(company, 2023)
        if not r2020 or not r2023:
            continue

        # 3-year CAGR
        cagr = ((r2023["revenue"] / r2020["revenue"]) ** (1/3) - 1) * 100
        questions.append({
            "question": f"What was {company}'s compound annual growth rate (CAGR) of revenue from 2020 to 2023?",
            "answer": fmt_pct(cagr),
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "revenue_cagr",
            "raw_value": round(cagr, 1)
        })

        # Total revenue over 4 years
        total = sum(get_fy(company, y)["revenue"] for y in FY_YEARS if get_fy(company, y))
        questions.append({
            "question": f"What was {company}'s total cumulative revenue from 2020 to 2023?",
            "answer": fmt_dollars(total),
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "cumulative_revenue",
            "raw_value": total
        })

        # Total net income over 4 years
        total_ni = sum(get_fy(company, y)["net_income"] for y in FY_YEARS if get_fy(company, y))
        questions.append({
            "question": f"What was {company}'s total net income from 2020 to 2023?",
            "answer": fmt_dollars(total_ni),
            "context": None,
            "dataset_name": "supabase_financial",
            "rag_target": "quantitative",
            "item_index": len(questions),
            "difficulty": "hard",
            "phase": "phase3",
            "sql_table": "financials",
            "sql_field": "cumulative_net_income",
            "raw_value": total_ni
        })

    return questions


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Regenerate Phase 3 Quantitative dataset")
    parser.add_argument("--count", type=int, default=500, help="Target number of questions")
    parser.add_argument("--output", type=str, default=None, help="Output filename")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("REGENERATING PHASE 3 QUANTITATIVE DATASET")
    print(f"Target: {args.count} questions")
    print("=" * 60)

    # Generate all question types
    all_questions = []

    generators = [
        ("Direct lookups", generate_direct_lookup_questions),
        ("Calculated metrics", generate_calculated_metric_questions),
        ("YoY growth", generate_yoy_growth_questions),
        ("Cross-company comparisons", generate_comparison_questions),
        ("Quarterly data", generate_quarterly_questions),
        ("Multi-year analysis", generate_multi_year_questions),
    ]

    for name, gen_func in generators:
        qs = gen_func()
        print(f"  {name}: {len(qs)} questions")
        all_questions.extend(qs)

    print(f"\nTotal generated: {len(all_questions)} questions")

    # Sample down to target count if needed
    if len(all_questions) > args.count:
        random.shuffle(all_questions)
        all_questions = all_questions[:args.count]
        print(f"Sampled down to: {len(all_questions)} questions")
    elif len(all_questions) < args.count:
        print(f"WARNING: Only {len(all_questions)} questions generated (target was {args.count})")

    # Re-index
    for i, q in enumerate(all_questions):
        q["item_index"] = i

    # Save
    output_file = args.output or "quantitative-500-v2.json"
    output_path = OUTPUT_DIR / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"questions": all_questions}, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {len(all_questions)} questions to {output_path}")

    # Print sample
    print("\n--- SAMPLE QUESTIONS ---")
    for q in random.sample(all_questions, min(5, len(all_questions))):
        print(f"  Q: {q['question']}")
        print(f"  A: {q['answer']}")
        print(f"  (field: {q.get('sql_field', '?')}, raw: {q.get('raw_value', '?')})")
        print()


if __name__ == "__main__":
    main()
