#!/usr/bin/env python3
"""
Mass Question Generator — 10,000+ Expert Evaluation Questions
==============================================================
Generates thousands of expert-level evaluation questions for all 4 sectors
(Finance, BTP, Juridique, Industrie) and all 4 pipelines (Standard, Graph,
Quantitative, Orchestrator).

Two modes:
  1. Templates-only: Pure combinatorial expansion (2000+ questions, no LLM)
  2. LLM-augmented: Templates + LLM variation via LiteLLM proxy (5000-10000+)

Usage:
  source .env.local
  python3 eval/mass-question-generator.py --target 5000
  python3 eval/mass-question-generator.py --sector finance --target 1000
  python3 eval/mass-question-generator.py --dry-run
  python3 eval/mass-question-generator.py --templates-only
  python3 eval/mass-question-generator.py --templates-only --target 3000
  python3 eval/mass-question-generator.py --target 10000 --batch-size 25
"""

import json
import os
import sys
import time
import random
import argparse
import hashlib
import socket
import itertools
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ─── IPv4 monkey-patch ───────────────────────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    responses = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET] or responses
socket.getaddrinfo = _ipv4_only_getaddrinfo

import requests

# ─── Paths ───────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(REPO_ROOT, "sectors", "eval-datasets")
OUTPUT_FILE = os.path.join(DATASET_DIR, "sector-full-eval-extended.json")
PROGRESS_FILE = os.path.join(DATASET_DIR, ".mass-gen-progress.json")

# ─── Load .env.local ─────────────────────────────────────────────────────
env_file = os.path.join(REPO_ROOT, ".env.local")
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key.strip(), val)

# ─── LiteLLM Config ─────────────────────────────────────────────────────
LITELLM_URL = os.environ.get(
    "LITELLM_URL",
    "https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions"
)
LITELLM_KEY = os.environ.get("LITELLM_API_KEY", "sk-litellm-nomos-2026")
LITELLM_MODEL = os.environ.get("LITELLM_MODEL", "smart")

# Fallback: direct Groq
GROQ_KEYS = [v for k, v in sorted(os.environ.items())
             if k.startswith("GROQ_API_KEY") and v and "QUANTITATIVE" not in k]
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

_lock = Lock()
_groq_idx = 0
_stats = {
    "llm_calls": 0,
    "llm_successes": 0,
    "llm_failures": 0,
    "llm_retries": 0,
    "questions_generated": 0,
    "questions_from_templates": 0,
    "questions_from_llm": 0,
    "duplicates_removed": 0,
}


def _next_groq_key():
    global _groq_idx
    with _lock:
        if not GROQ_KEYS:
            return ""
        key = GROQ_KEYS[_groq_idx % len(GROQ_KEYS)]
        _groq_idx += 1
        return key


# =========================================================================
#  SECTION 1 — SECTOR QUESTION TEMPLATES (50+ per sector)
# =========================================================================

SECTORS = ["finance", "btp", "juridique", "industrie"]
PIPELINES = ["standard", "graph", "quantitative", "orchestrator"]
DIFFICULTIES = ["basic", "intermediate", "expert"]

# ─── Finance Templates ───────────────────────────────────────────────────

FINANCE_METRICS = [
    "marge nette", "marge brute", "marge operationnelle", "ROE", "ROA", "ROIC",
    "ratio dette/EBITDA", "ratio de liquidite generale", "ratio de liquidite reduite",
    "ratio cours/benefice (P/E)", "EV/EBITDA", "price-to-book",
    "CAPEX", "free cash flow", "BFR", "tresorerie nette", "dette nette",
    "taux d'endettement", "ratio de couverture des interets",
    "dividende par action", "rendement du dividende", "payout ratio",
    "chiffre d'affaires", "resultat operationnel", "EBITDA",
    "resultat net", "benefice par action (BPA)", "actif net par action",
    "taux de croissance du CA", "marge d'EBITDA",
    "ratio dettes/capitaux propres", "ratio de solvabilite",
    "taux d'imposition effectif", "WACC", "cout de la dette",
    "rotation des stocks", "delai de rotation des creances",
    "delai de paiement fournisseurs", "cycle de conversion de tresorerie",
]

FINANCE_COMPANIES = [
    "Boeing", "3M", "Verizon", "Pfizer", "AMD", "JPMorgan", "Best Buy",
    "TORM", "Republic Services", "Microsoft", "Apple", "Amazon",
    "TotalEnergies", "LVMH", "BNP Paribas", "Societe Generale",
    "Sanofi", "AXA", "Schneider Electric", "Airbus",
    "Hermes", "Dassault Systemes", "Legrand", "Saint-Gobain",
    "Tesla", "Alphabet", "Meta", "Nvidia", "Goldman Sachs", "Citigroup",
]

FINANCE_YEARS = ["2018", "2019", "2020", "2021", "2022", "2023", "2024"]

FINANCE_TOPICS = [
    "normes IFRS", "SEC filings", "analyse fondamentale", "analyse technique",
    "gestion de portefeuille", "risque de credit", "risque de marche",
    "risque operationnel", "conformite reglementaire", "Bale III/IV",
    "stress tests bancaires", "titrisation", "produits derives",
    "politique monetaire", "taux directeurs", "inflation",
    "fusions et acquisitions", "LBO", "IPO", "augmentation de capital",
    "rachat d'actions", "reporting ESG", "taxonomie verte EU",
    "audit financier", "commissariat aux comptes", "consolidation",
    "normes US GAAP vs IFRS", "goodwill et depreciation",
    "provisions et passifs eventuels", "instruments financiers IFRS 9",
    "leasing IFRS 16", "reconnaissance du revenu IFRS 15",
    "risque de change", "couverture de change", "swaps de taux",
    "marche obligataire", "notation de credit", "spread de credit",
    "private equity", "venture capital", "asset management",
    "reglementation MiFID II", "directive AIFM", "Solvabilite II",
    "fintech et disruption bancaire", "blockchain en finance",
    "intelligence artificielle en trading", "scoring de credit ML",
]

FINANCE_TEMPLATE_PATTERNS = [
    # Quantitative (pipeline: quantitative)
    ("Quel est le {metric} de {company} en {year} ?",
     "quantitative", ["metric", "company", "year"]),
    ("Quelle est la variation du {metric} de {company} entre {year1} et {year2} ?",
     "quantitative", ["metric", "company", "year_pair"]),
    ("Compare le {metric} de {company1} et {company2} en {year}.",
     "quantitative", ["metric", "company_pair", "year"]),

    # Standard (pipeline: standard)
    ("Quels sont les principaux risques identifies dans le rapport annuel de {company} en {year} ?",
     "standard", ["company", "year"]),
    ("Comment {company} explique-t-elle l'evolution de son {metric} dans son rapport {year} ?",
     "standard", ["company", "metric", "year"]),
    ("Quelles sont les perspectives strategiques annoncees par {company} pour {year} ?",
     "standard", ["company", "year"]),
    ("Quels segments d'activite contribuent le plus au chiffre d'affaires de {company} ?",
     "standard", ["company"]),
    ("Quelle est la politique de distribution de dividendes de {company} ?",
     "standard", ["company"]),
    ("Comment {company} gere-t-elle son risque de change ?",
     "standard", ["company"]),
    ("Quelles sont les principales acquisitions realisees par {company} ces dernieres annees ?",
     "standard", ["company"]),
    ("Quel est l'impact de {topic} sur le secteur bancaire francais ?",
     "standard", ["topic"]),
    ("Comment les {topic} affectent-ils la valorisation des entreprises cotees ?",
     "standard", ["topic"]),
    ("Expliquez le concept de {topic} et son application en analyse financiere.",
     "standard", ["topic"]),
    ("Quels sont les enjeux de {topic} pour les institutions financieres en 2024 ?",
     "standard", ["topic"]),

    # Graph (pipeline: graph)
    ("Quelle est la relation entre {company1} et {company2} dans la chaine de valeur ?",
     "graph", ["company_pair"]),
    ("Quels sont les principaux fournisseurs et clients de {company} ?",
     "graph", ["company"]),
    ("Comment {company} est-elle liee aux normes {topic} ?",
     "graph", ["company", "topic"]),
    ("Quelles entites sont mentionnees dans le rapport annuel de {company} en {year} ?",
     "graph", ["company", "year"]),

    # Orchestrator (pipeline: orchestrator)
    ("Analyse complete de {company} : performance financiere, risques et perspectives pour {year}.",
     "orchestrator", ["company", "year"]),
    ("Compare la strategie financiere de {company1} et {company2} en tenant compte de leur {metric} et de leurs risques operationnels.",
     "orchestrator", ["company_pair", "metric"]),
    ("Quel est l'impact de {topic} sur le {metric} de {company} et comment cela affecte-t-il sa position concurrentielle ?",
     "orchestrator", ["topic", "metric", "company"]),
]

# ─── BTP Templates ───────────────────────────────────────────────────────

BTP_NORMES = [
    "DTU 13.11", "DTU 13.12", "DTU 20.1", "DTU 21", "DTU 23.1",
    "DTU 25.1", "DTU 25.41", "DTU 26.1", "DTU 31.1", "DTU 31.2",
    "DTU 32.1", "DTU 34.1", "DTU 36.5", "DTU 39", "DTU 40.11",
    "DTU 40.14", "DTU 41.2", "DTU 43.1", "DTU 43.3", "DTU 43.4",
    "DTU 45.1", "DTU 45.2", "DTU 51.1", "DTU 52.1", "DTU 52.2",
    "DTU 53.2", "DTU 55.2", "DTU 58.1", "DTU 59.1", "DTU 60.1",
    "DTU 60.11", "DTU 64.1", "DTU 65.14", "DTU 68.3",
    "Eurocode 0", "Eurocode 1", "Eurocode 2", "Eurocode 3",
    "Eurocode 4", "Eurocode 5", "Eurocode 6", "Eurocode 7", "Eurocode 8",
    "NF EN 206", "NF EN 12811", "NF EN 1090", "NF P94-500",
    "NF X 46-020", "NF C 15-100", "NF P01-010",
]

BTP_LOTS = [
    "gros oeuvre", "charpente metallique", "charpente bois",
    "couverture", "etancheite", "bardage", "menuiseries exterieures",
    "menuiseries interieures", "cloisons seches", "platrerie",
    "carrelage", "peinture", "sol souple", "faux plafond",
    "plomberie sanitaire", "chauffage", "ventilation", "climatisation",
    "electricite courants forts", "electricite courants faibles",
    "VRD", "terrassement", "assainissement", "espaces verts",
    "ascenseur", "desenfumage", "securite incendie",
]

BTP_MATERIALS = [
    "beton arme", "beton precontraint", "acier de construction",
    "bois lamelle-colle", "brique", "parpaing", "pierre naturelle",
    "verre trempe", "aluminium", "zinc", "cuivre",
    "laine de verre", "laine de roche", "polystyrene expanse (PSE)",
    "polyurethane", "fibre de bois", "ouate de cellulose",
    "enduit monocouche", "enduit de facade", "plaques de platre BA13",
    "carrelage gres cerame", "PVC", "EPDM", "bitume elastomere",
]

BTP_BUILDING_TYPES = [
    "maison individuelle", "logement collectif R+3", "logement collectif R+8",
    "ERP type M (commerce)", "ERP type L (salle de spectacle)",
    "ERP type O (hotel)", "ERP type R (enseignement)",
    "ERP type U (etablissement sanitaire)", "batiment industriel",
    "entrepot logistique", "parking souterrain", "bureau R+5",
    "IGH (immeuble de grande hauteur)", "ouvrage d'art (pont)",
    "station d'epuration", "reservoir d'eau potable",
]

BTP_ZONES_CLIM = ["H1a", "H1b", "H1c", "H2a", "H2b", "H2c", "H2d", "H3"]
BTP_ZONES_SISMIQUE = ["1", "2", "3", "4", "5"]
BTP_ZONES_NEIGE = ["A1", "A2", "B1", "B2", "C1", "C2", "D", "E"]

BTP_TEMPLATE_PATTERNS = [
    # Standard
    ("Quelles sont les exigences du {norme} pour les travaux de {lot} ?",
     "standard", ["norme", "lot"]),
    ("Comment dimensionner une fondation pour un {building_type} en zone sismique {zone_sismique} ?",
     "standard", ["building_type", "zone_sismique"]),
    ("Quelles sont les prescriptions de mise en oeuvre du {material} selon les regles de l'art ?",
     "standard", ["material"]),
    ("Quelle est la resistance thermique minimale exigee en zone {zone_clim} pour un {building_type} ?",
     "standard", ["zone_clim", "building_type"]),
    ("Comment calculer les charges de neige en zone {zone_neige} selon l'{norme} ?",
     "standard", ["zone_neige", "norme"]),
    ("Quels sont les documents du CCTP a produire pour le lot {lot} ?",
     "standard", ["lot"]),
    ("Quelles sont les regles de securite incendie pour un {building_type} ?",
     "standard", ["building_type"]),
    ("Comment traiter les ponts thermiques dans un {building_type} en zone {zone_clim} ?",
     "standard", ["building_type", "zone_clim"]),
    ("Quelles sont les exigences acoustiques pour un {building_type} selon la NRA ?",
     "standard", ["building_type"]),
    ("Comment gerer les interfaces entre le lot {lot1} et le lot {lot2} ?",
     "standard", ["lot_pair"]),
    ("Quelle est la procedure de reception des travaux de {lot} ?",
     "standard", ["lot"]),
    ("Quels essais et controles sont obligatoires pour le lot {lot} ?",
     "standard", ["lot"]),

    # Graph
    ("Quelle est la relation entre le {norme} et les exigences du lot {lot} ?",
     "graph", ["norme", "lot"]),
    ("Quels DTU s'appliquent aux travaux de {lot} pour un {building_type} ?",
     "graph", ["lot", "building_type"]),
    ("Quelles normes regissent l'utilisation du {material} en construction ?",
     "graph", ["material"]),
    ("Quels lots techniques sont lies au lot {lot} dans un {building_type} ?",
     "graph", ["lot", "building_type"]),
    ("Quelle est la relation entre le {material} et les normes du {norme} ?",
     "graph", ["material", "norme"]),

    # Quantitative
    ("Quelle epaisseur minimale de {material} est requise par le {norme} ?",
     "quantitative", ["material", "norme"]),
    ("Quelles sont les valeurs de resistance thermique exigees en zone {zone_clim} par la RE2020 ?",
     "quantitative", ["zone_clim"]),
    ("Quel est le cout moyen au m2 du lot {lot} pour un {building_type} ?",
     "quantitative", ["lot", "building_type"]),
    ("Quelles sont les charges de neige en kN/m2 en zone {zone_neige} selon l'{norme} ?",
     "quantitative", ["zone_neige", "norme"]),
    ("Quel est le delai reglementaire pour le lot {lot} dans un marche public ?",
     "quantitative", ["lot"]),

    # Orchestrator
    ("Analyse complete d'un projet de {building_type} en zone {zone_clim} sismique {zone_sismique} : normes, materiaux, lots et budget.",
     "orchestrator", ["building_type", "zone_clim", "zone_sismique"]),
    ("Quels sont les impacts croises de la RE2020 et de l'{norme} sur la conception d'un {building_type} ?",
     "orchestrator", ["norme", "building_type"]),
    ("Analyse technique et reglementaire du lot {lot} pour un {building_type} en zone {zone_clim} : normes, materiaux et mise en oeuvre.",
     "orchestrator", ["lot", "building_type", "zone_clim"]),
]

# ─── Juridique Templates ─────────────────────────────────────────────────

JUR_CODES = [
    "Code civil", "Code de commerce", "Code du travail",
    "Code de procedure civile", "Code penal", "Code de procedure penale",
    "Code general des impots", "Code de l'urbanisme",
    "Code de l'environnement", "Code de l'energie",
    "Code de la consommation", "Code de la propriete intellectuelle",
    "Code de la securite sociale", "Code des assurances",
    "Code des transports", "Code de la sante publique",
    "Code monetaire et financier", "Code de la construction et de l'habitation",
]

JUR_DOMAINES = [
    "droit des contrats", "droit de la responsabilite civile",
    "droit des societes", "droit du travail", "droit penal",
    "droit administratif", "droit de la concurrence",
    "droit de la consommation", "droit de la propriete intellectuelle",
    "droit des marques", "droit des brevets", "droit d'auteur",
    "droit bancaire et financier", "droit des assurances",
    "droit fiscal", "droit de l'urbanisme", "droit de l'environnement",
    "droit europeen", "droit international prive",
    "droit des procedures collectives", "droit de la famille",
    "droit des successions", "droit immobilier", "droit de la construction",
    "RGPD et protection des donnees", "droit du numerique",
    "droit de la cybersecurite", "droit des marches publics",
]

JUR_CONCEPTS = [
    "force majeure", "imprevision", "clause abusive",
    "vice du consentement", "responsabilite du fait des choses",
    "responsabilite du fait d'autrui", "garantie des vices caches",
    "prescription extinctive", "prescription acquisitive",
    "subrogation", "compensation", "novation", "delegation",
    "clause penale", "clause resolutoire", "clause compromissoire",
    "droit de retractation", "obligation d'information",
    "devoir de conseil", "bonne foi contractuelle",
    "abus de droit", "enrichissement sans cause",
    "stipulation pour autrui", "action oblique", "action paulienne",
    "mise en demeure", "exception d'inexecution",
    "resolution pour inexecution", "theorie de l'apparence",
    "personnalite morale", "responsabilite des dirigeants",
    "abus de biens sociaux", "delit d'initie",
    "licenciement pour motif personnel", "licenciement economique",
    "rupture conventionnelle", "prise d'acte",
    "harcelement moral", "harcelement sexuel",
    "discrimination", "egalite de traitement",
    "convention collective", "accord d'entreprise",
    "contrat a duree determinee (CDD)", "contrat a duree indeterminee (CDI)",
]

JUR_PROCEDURES = [
    "assignation", "requete", "refere", "injonction de payer",
    "saisie conservatoire", "saisie-attribution",
    "appel", "pourvoi en cassation", "recours gracieux",
    "recours contentieux", "recours pour exces de pouvoir",
    "question prioritaire de constitutionnalite (QPC)",
    "procedure de sauvegarde", "redressement judiciaire",
    "liquidation judiciaire", "conciliation", "mediation",
    "arbitrage", "procedure participative",
]

JUR_ARTICLES_CELEBRES = [
    "article 1103 du Code civil (force obligatoire du contrat)",
    "article 1104 du Code civil (bonne foi)",
    "article 1112-1 du Code civil (devoir d'information precontractuel)",
    "article 1130 du Code civil (vices du consentement)",
    "article 1195 du Code civil (imprevision)",
    "article 1217 du Code civil (inexecution)",
    "article 1240 du Code civil (responsabilite delictuelle)",
    "article 1242 du Code civil (responsabilite du fait d'autrui)",
    "article L.1231-1 du Code du travail (licenciement)",
    "article L.1234-1 du Code du travail (preavis)",
    "article L.1235-3 du Code du travail (indemnites baremes Macron)",
    "article L.442-1 du Code de commerce (pratiques restrictives)",
    "article 121-3 du Code penal (faute non intentionnelle)",
    "articles 5 a 83 du RGPD (principes et droits)",
]

JUR_TEMPLATE_PATTERNS = [
    # Standard
    ("Quelles sont les conditions d'application de {concept} en {domaine} ?",
     "standard", ["concept", "domaine"]),
    ("Comment le {code} encadre-t-il les obligations en matiere de {domaine} ?",
     "standard", ["code", "domaine"]),
    ("Quels sont les delais de prescription applicables en {domaine} ?",
     "standard", ["domaine"]),
    ("Quelle est la procedure de {procedure} en droit francais ?",
     "standard", ["procedure"]),
    ("Comment s'applique l'{article} dans la jurisprudence recente ?",
     "standard", ["article"]),
    ("Quelles sanctions sont prevues en cas de manquement aux obligations de {domaine} ?",
     "standard", ["domaine"]),
    ("Comment la reforme de 2016 a-t-elle modifie le regime de {concept} ?",
     "standard", ["concept"]),
    ("Quelles sont les obligations de l'employeur en matiere de {concept} ?",
     "standard", ["concept"]),
    ("Comment le juge apprecie-t-il la {concept} dans le cadre d'un litige de {domaine} ?",
     "standard", ["concept", "domaine"]),
    ("Quels sont les droits du salarie en cas de {concept} ?",
     "standard", ["concept"]),

    # Graph
    ("Quelle est la relation entre l'{article} et les dispositions du {code} ?",
     "graph", ["article", "code"]),
    ("Quels articles du {code} sont lies a la notion de {concept} ?",
     "graph", ["code", "concept"]),
    ("Comment s'articulent {concept1} et {concept2} en droit francais ?",
     "graph", ["concept_pair"]),
    ("Quelles sont les entites juridiques liees a {concept} en {domaine} ?",
     "graph", ["concept", "domaine"]),
    ("Quel est le lien entre la {procedure} et les dispositions du {code} ?",
     "graph", ["procedure", "code"]),

    # Quantitative
    ("Quels sont les delais chiffres prevus par le {code} en matiere de {domaine} ?",
     "quantitative", ["code", "domaine"]),
    ("Quels sont les seuils et montants prevus par le {code} pour {concept} ?",
     "quantitative", ["code", "concept"]),
    ("Quelles sont les amendes et penalites chiffrees en {domaine} selon le {code} ?",
     "quantitative", ["domaine", "code"]),
    ("Quel est le montant maximum des sanctions en cas de {concept} ?",
     "quantitative", ["concept"]),
    ("Quels sont les plafonds d'indemnisation en {domaine} ?",
     "quantitative", ["domaine"]),

    # Orchestrator
    ("Analyse juridique complete d'un litige de {domaine} impliquant {concept} : textes applicables, jurisprudence et procedure.",
     "orchestrator", ["domaine", "concept"]),
    ("Comment les dispositions du {code} en matiere de {domaine} interagissent-elles avec le droit europeen ?",
     "orchestrator", ["code", "domaine"]),
    ("Analyse croisee de {concept} sous l'angle du {code} et de la jurisprudence recente en {domaine}.",
     "orchestrator", ["concept", "code", "domaine"]),
]

# ─── Industrie Templates ─────────────────────────────────────────────────

IND_NORMES = [
    "ISO 9001:2015", "ISO 14001:2015", "ISO 45001:2018", "ISO 50001:2018",
    "ISO 13485:2016", "ISO 22000:2018", "ISO 22005", "ISO 27001",
    "ISO 14644", "ISO/IEC 17025", "ISO 19011:2018",
    "ISO/ASTM 52900", "ISO 3834", "EN 1090",
    "IEC 62443", "IEC 61131", "IEC 61508",
    "directive 2006/42/CE (machines)", "directive ATEX 2014/34/EU",
    "reglement REACH", "reglement CLP", "directive Seveso III",
    "NF EN 13306 (maintenance)", "NF EN 15341 (KPI maintenance)",
]

IND_METHODES = [
    "AMDEC (FMEA)", "HAZOP", "5S", "Kaizen", "SMED",
    "Six Sigma DMAIC", "lean manufacturing", "TPM",
    "SPC (maitrise statistique des procedes)",
    "8D (resolution de problemes)", "diagramme d'Ishikawa",
    "analyse Pareto", "methode 5 Pourquoi", "PDCA (roue de Deming)",
    "VSM (Value Stream Mapping)", "kanban", "Jidoka", "Poka-Yoke",
    "analyse de la valeur", "benchmarking industriel",
    "analyse vibratoire", "thermographie infrarouge",
    "analyse d'huile", "ultrasons industriels",
]

IND_EQUIPEMENTS = [
    "tour CNC", "fraiseuse 5 axes", "presse hydraulique",
    "robot de soudage", "robot de peinture", "convoyeur a bande",
    "compresseur d'air", "chaudiere industrielle", "echangeur thermique",
    "pompe centrifuge", "moteur electrique", "variateur de frequence",
    "automate programmable (API)", "systeme SCADA", "IHM tactile",
    "imprimante 3D metal (SLM)", "machine de decoupe laser",
    "machine d'injection plastique", "extrudeuse", "four de traitement thermique",
    "pont roulant", "chariot elevateur", "salle blanche",
    "station de traitement de surface", "banc d'essai", "MMT (machine a mesurer)",
]

IND_KPI = [
    "TRS (OEE)", "MTBF", "MTTR", "taux de rebut",
    "Cp", "Cpk", "PPM", "taux de rendement premier passage (FPY)",
    "taux de service", "taux de disponibilite", "temps de cycle",
    "lead time", "takt time", "cout de non-qualite (CNQ)",
    "taux de frequence des accidents", "taux de gravite",
    "consommation energetique specifique", "empreinte carbone",
]

IND_SECTORS_SPECIFIC = [
    "automobile", "aeronautique", "agroalimentaire", "pharmaceutique",
    "chimie", "metallurgie", "plasturgie", "electronique",
    "cimenterie", "papeterie", "verrerie", "textile",
    "energie (nucleaire)", "energie (renouvelable)", "naval",
]

IND_TEMPLATE_PATTERNS = [
    # Standard
    ("Quelles sont les exigences de la norme {norme} en matiere de {methode} ?",
     "standard", ["norme", "methode"]),
    ("Comment mettre en oeuvre la methode {methode} dans un contexte {secteur_ind} ?",
     "standard", ["methode", "secteur_ind"]),
    ("Quels sont les KPI a suivre pour mesurer le {kpi} d'un {equipement} ?",
     "standard", ["kpi", "equipement"]),
    ("Comment realiser la maintenance predictive d'un {equipement} ?",
     "standard", ["equipement"]),
    ("Quelles sont les regles de securite pour l'utilisation d'un {equipement} ?",
     "standard", ["equipement"]),
    ("Comment la norme {norme} s'applique-t-elle au secteur {secteur_ind} ?",
     "standard", ["norme", "secteur_ind"]),
    ("Quels sont les parametres critiques a controler sur un {equipement} ?",
     "standard", ["equipement"]),
    ("Comment calculer le {kpi} d'une ligne de production ?",
     "standard", ["kpi"]),
    ("Quelles sont les etapes de mise en conformite {norme} pour un site industriel ?",
     "standard", ["norme"]),
    ("Comment gerer les non-conformites detectees lors d'un audit {norme} ?",
     "standard", ["norme"]),

    # Graph
    ("Quelle est la relation entre la norme {norme1} et la norme {norme2} ?",
     "graph", ["norme_pair"]),
    ("Quels equipements sont concernes par la norme {norme} ?",
     "graph", ["norme"]),
    ("Comment la methode {methode} s'integre-t-elle dans un systeme {norme} ?",
     "graph", ["methode", "norme"]),

    # Quantitative
    ("Quel est le {kpi} typique pour un {equipement} dans le secteur {secteur_ind} ?",
     "quantitative", ["kpi", "equipement", "secteur_ind"]),
    ("Comment calculer et interpreter le {kpi} d'une chaine de production {secteur_ind} ?",
     "quantitative", ["kpi", "secteur_ind"]),

    # Orchestrator
    ("Analyse complete de la performance d'un {equipement} : {kpi}, maintenance, normes {norme} et optimisation.",
     "orchestrator", ["equipement", "kpi", "norme"]),
    ("Comment optimiser une ligne de production {secteur_ind} en combinant {methode} et les exigences {norme} ?",
     "orchestrator", ["secteur_ind", "methode", "norme"]),
]


# =========================================================================
#  SECTION 2 — TEMPLATE EXPANSION ENGINE
# =========================================================================

def _make_id(sector, pipeline, idx):
    """Generate unique question ID."""
    prefix = {"finance": "gfin", "btp": "gbtp", "juridique": "gjur", "industrie": "gind"}
    pipe_prefix = {"standard": "s", "graph": "g", "quantitative": "q", "orchestrator": "o"}
    return f"gen-{prefix.get(sector, sector)}-{pipe_prefix.get(pipeline, 'x')}-{idx:05d}"


def _expected_contains(question, sector):
    """Extract expected keywords from a question based on entities mentioned."""
    keywords = []
    # Extract quoted terms or capitalized multi-word proper nouns
    # For now, extract key nouns from the question itself
    q_lower = question.lower()

    # Sector-specific keyword extraction
    if sector == "finance":
        for m in FINANCE_METRICS:
            if m.lower() in q_lower:
                keywords.append(m.split("(")[0].strip().split("/")[0].strip())
                break
        for c in FINANCE_COMPANIES:
            if c.lower() in q_lower:
                keywords.append(c)
                break
    elif sector == "btp":
        for n in BTP_NORMES:
            if n.lower() in q_lower:
                keywords.append(n)
                break
        for m in BTP_MATERIALS:
            if m.lower().split("(")[0].strip() in q_lower:
                keywords.append(m.split("(")[0].strip())
                break
    elif sector == "juridique":
        for c in JUR_CONCEPTS:
            if c.lower().split("(")[0].strip() in q_lower:
                keywords.append(c.split("(")[0].strip())
                break
        for code in JUR_CODES:
            if code.lower() in q_lower:
                keywords.append(code)
                break
    elif sector == "industrie":
        for n in IND_NORMES:
            nm = n.split("(")[0].strip().split(":")[0].strip()
            if nm.lower() in q_lower:
                keywords.append(nm)
                break
        for m in IND_METHODES:
            mm = m.split("(")[0].strip()
            if mm.lower() in q_lower:
                keywords.append(mm)
                break

    if not keywords:
        # Fallback: extract a meaningful 2-3 word phrase
        words = [w for w in question.split() if len(w) > 4 and w[0].isupper()]
        keywords = words[:2] if words else [question.split("?")[0].split()[-1]]

    return keywords[:3]


def _pick_difficulty():
    """Weighted random difficulty."""
    r = random.random()
    if r < 0.25:
        return "basic"
    elif r < 0.60:
        return "intermediate"
    else:
        return "expert"


def _expand_finance_templates(max_questions=1500):
    """Expand finance templates into concrete questions."""
    questions = []
    seen = set()

    for pattern, pipeline, slots in FINANCE_TEMPLATE_PATTERNS:
        combos = []
        if slots == ["metric", "company", "year"]:
            combos = list(itertools.product(
                random.sample(FINANCE_METRICS, min(15, len(FINANCE_METRICS))),
                random.sample(FINANCE_COMPANIES, min(10, len(FINANCE_COMPANIES))),
                random.sample(FINANCE_YEARS, min(4, len(FINANCE_YEARS)))
            ))
        elif slots == ["metric", "company", "year_pair"]:
            year_pairs = [(y1, y2) for y1 in FINANCE_YEARS for y2 in FINANCE_YEARS if int(y2) > int(y1)]
            combos = list(itertools.product(
                random.sample(FINANCE_METRICS, min(10, len(FINANCE_METRICS))),
                random.sample(FINANCE_COMPANIES, min(8, len(FINANCE_COMPANIES))),
                random.sample(year_pairs, min(5, len(year_pairs)))
            ))
        elif slots == ["metric", "company_pair", "year"]:
            company_pairs = [(c1, c2) for c1, c2 in itertools.combinations(
                random.sample(FINANCE_COMPANIES, min(10, len(FINANCE_COMPANIES))), 2)]
            combos = list(itertools.product(
                random.sample(FINANCE_METRICS, min(8, len(FINANCE_METRICS))),
                random.sample(company_pairs, min(10, len(company_pairs))),
                random.sample(FINANCE_YEARS, min(3, len(FINANCE_YEARS)))
            ))
        elif slots == ["company", "year"]:
            combos = list(itertools.product(
                random.sample(FINANCE_COMPANIES, min(15, len(FINANCE_COMPANIES))),
                random.sample(FINANCE_YEARS, min(5, len(FINANCE_YEARS)))
            ))
        elif slots == ["company", "metric", "year"]:
            combos = list(itertools.product(
                random.sample(FINANCE_COMPANIES, min(10, len(FINANCE_COMPANIES))),
                random.sample(FINANCE_METRICS, min(8, len(FINANCE_METRICS))),
                random.sample(FINANCE_YEARS, min(3, len(FINANCE_YEARS)))
            ))
        elif slots == ["company"]:
            combos = [(c,) for c in random.sample(FINANCE_COMPANIES, min(20, len(FINANCE_COMPANIES)))]
        elif slots == ["topic"]:
            combos = [(t,) for t in random.sample(FINANCE_TOPICS, min(25, len(FINANCE_TOPICS)))]
        elif slots == ["company_pair"]:
            company_pairs = list(itertools.combinations(
                random.sample(FINANCE_COMPANIES, min(12, len(FINANCE_COMPANIES))), 2))
            combos = [(cp,) for cp in random.sample(company_pairs, min(20, len(company_pairs)))]
        elif slots == ["company", "topic"]:
            combos = list(itertools.product(
                random.sample(FINANCE_COMPANIES, min(8, len(FINANCE_COMPANIES))),
                random.sample(FINANCE_TOPICS, min(6, len(FINANCE_TOPICS)))
            ))
        elif slots == ["topic", "metric", "company"]:
            combos = list(itertools.product(
                random.sample(FINANCE_TOPICS, min(5, len(FINANCE_TOPICS))),
                random.sample(FINANCE_METRICS, min(5, len(FINANCE_METRICS))),
                random.sample(FINANCE_COMPANIES, min(5, len(FINANCE_COMPANIES)))
            ))
        elif slots == ["company_pair", "metric"]:
            company_pairs = list(itertools.combinations(
                random.sample(FINANCE_COMPANIES, min(10, len(FINANCE_COMPANIES))), 2))
            combos = list(itertools.product(
                random.sample(company_pairs, min(10, len(company_pairs))),
                random.sample(FINANCE_METRICS, min(5, len(FINANCE_METRICS)))
            ))
        else:
            continue

        random.shuffle(combos)
        for combo in combos:
            if len(questions) >= max_questions:
                break
            try:
                q = pattern
                slot_idx = 0
                for s in slots:
                    val = combo[slot_idx]
                    if s == "year_pair":
                        q = q.replace("{year1}", val[0]).replace("{year2}", val[1])
                    elif s == "company_pair":
                        q = q.replace("{company1}", val[0]).replace("{company2}", val[1])
                    elif s == "company_pair":
                        q = q.replace("{company1}", val[0]).replace("{company2}", val[1])
                    elif s == "lot_pair":
                        q = q.replace("{lot1}", val[0]).replace("{lot2}", val[1])
                    elif s == "concept_pair":
                        q = q.replace("{concept1}", val[0]).replace("{concept2}", val[1])
                    elif s == "norme_pair":
                        q = q.replace("{norme1}", val[0]).replace("{norme2}", val[1])
                    else:
                        q = q.replace("{" + s + "}", str(val))
                    slot_idx += 1
            except (IndexError, KeyError):
                continue

            # Check for leftover placeholders
            if "{" in q:
                continue

            q_hash = hashlib.md5(q.encode()).hexdigest()[:12]
            if q_hash in seen:
                continue
            seen.add(q_hash)

            questions.append({
                "question": q,
                "pipeline": pipeline,
                "sector": "finance",
                "difficulty": _pick_difficulty(),
                "expected_contains": _expected_contains(q, "finance"),
            })

        if len(questions) >= max_questions:
            break

    return questions[:max_questions]


def _expand_btp_templates(max_questions=1000):
    """Expand BTP templates into concrete questions."""
    questions = []
    seen = set()

    for pattern, pipeline, slots in BTP_TEMPLATE_PATTERNS:
        combos = []
        if slots == ["norme", "lot"]:
            combos = list(itertools.product(
                random.sample(BTP_NORMES, min(20, len(BTP_NORMES))),
                random.sample(BTP_LOTS, min(15, len(BTP_LOTS)))
            ))
        elif slots == ["building_type", "zone_sismique"]:
            combos = list(itertools.product(
                random.sample(BTP_BUILDING_TYPES, min(10, len(BTP_BUILDING_TYPES))),
                BTP_ZONES_SISMIQUE
            ))
        elif slots == ["material"]:
            combos = [(m,) for m in BTP_MATERIALS]
        elif slots == ["zone_clim", "building_type"]:
            combos = list(itertools.product(
                random.sample(BTP_ZONES_CLIM, min(5, len(BTP_ZONES_CLIM))),
                random.sample(BTP_BUILDING_TYPES, min(10, len(BTP_BUILDING_TYPES)))
            ))
        elif slots == ["zone_neige", "norme"]:
            eurocode_normes = [n for n in BTP_NORMES if "Eurocode" in n]
            combos = list(itertools.product(BTP_ZONES_NEIGE, eurocode_normes))
        elif slots == ["lot"]:
            combos = [(l,) for l in BTP_LOTS]
        elif slots == ["building_type"]:
            combos = [(b,) for b in BTP_BUILDING_TYPES]
        elif slots == ["lot_pair"]:
            lot_pairs = list(itertools.combinations(
                random.sample(BTP_LOTS, min(15, len(BTP_LOTS))), 2))
            combos = [(lp,) for lp in lot_pairs]
        elif slots == ["lot", "building_type"]:
            combos = list(itertools.product(
                random.sample(BTP_LOTS, min(12, len(BTP_LOTS))),
                random.sample(BTP_BUILDING_TYPES, min(8, len(BTP_BUILDING_TYPES)))
            ))
        elif slots == ["norme", "building_type"]:
            combos = list(itertools.product(
                random.sample(BTP_NORMES, min(10, len(BTP_NORMES))),
                random.sample(BTP_BUILDING_TYPES, min(8, len(BTP_BUILDING_TYPES)))
            ))
        elif slots == ["building_type", "zone_clim"]:
            combos = list(itertools.product(
                random.sample(BTP_BUILDING_TYPES, min(8, len(BTP_BUILDING_TYPES))),
                random.sample(BTP_ZONES_CLIM, min(4, len(BTP_ZONES_CLIM)))
            ))
        elif slots == ["building_type", "zone_clim", "zone_sismique"]:
            combos = list(itertools.product(
                random.sample(BTP_BUILDING_TYPES, min(6, len(BTP_BUILDING_TYPES))),
                random.sample(BTP_ZONES_CLIM, min(3, len(BTP_ZONES_CLIM))),
                random.sample(BTP_ZONES_SISMIQUE, min(3, len(BTP_ZONES_SISMIQUE)))
            ))
        elif slots == ["material", "norme"]:
            combos = list(itertools.product(
                random.sample(BTP_MATERIALS, min(15, len(BTP_MATERIALS))),
                random.sample(BTP_NORMES, min(10, len(BTP_NORMES)))
            ))
        elif slots == ["zone_clim"]:
            combos = [(z,) for z in BTP_ZONES_CLIM]
        elif slots == ["lot", "building_type", "zone_clim"]:
            combos = list(itertools.product(
                random.sample(BTP_LOTS, min(8, len(BTP_LOTS))),
                random.sample(BTP_BUILDING_TYPES, min(5, len(BTP_BUILDING_TYPES))),
                random.sample(BTP_ZONES_CLIM, min(3, len(BTP_ZONES_CLIM)))
            ))
        else:
            continue

        random.shuffle(combos)
        for combo in combos:
            if len(questions) >= max_questions:
                break
            try:
                q = pattern
                slot_idx = 0
                for s in slots:
                    val = combo[slot_idx]
                    if s == "lot_pair":
                        q = q.replace("{lot1}", val[0]).replace("{lot2}", val[1])
                    else:
                        q = q.replace("{" + s + "}", str(val))
                    slot_idx += 1
            except (IndexError, KeyError):
                continue

            if "{" in q:
                continue

            q_hash = hashlib.md5(q.encode()).hexdigest()[:12]
            if q_hash in seen:
                continue
            seen.add(q_hash)

            questions.append({
                "question": q,
                "pipeline": pipeline,
                "sector": "btp",
                "difficulty": _pick_difficulty(),
                "expected_contains": _expected_contains(q, "btp"),
            })

        if len(questions) >= max_questions:
            break

    return questions[:max_questions]


def _expand_juridique_templates(max_questions=1500):
    """Expand juridique templates into concrete questions."""
    questions = []
    seen = set()

    for pattern, pipeline, slots in JUR_TEMPLATE_PATTERNS:
        combos = []
        if slots == ["concept", "domaine"]:
            combos = list(itertools.product(
                random.sample(JUR_CONCEPTS, min(20, len(JUR_CONCEPTS))),
                random.sample(JUR_DOMAINES, min(15, len(JUR_DOMAINES)))
            ))
        elif slots == ["code", "domaine"]:
            combos = list(itertools.product(
                random.sample(JUR_CODES, min(12, len(JUR_CODES))),
                random.sample(JUR_DOMAINES, min(12, len(JUR_DOMAINES)))
            ))
        elif slots == ["domaine"]:
            combos = [(d,) for d in JUR_DOMAINES]
        elif slots == ["procedure"]:
            combos = [(p,) for p in JUR_PROCEDURES]
        elif slots == ["article"]:
            combos = [(a,) for a in JUR_ARTICLES_CELEBRES]
        elif slots == ["concept"]:
            combos = [(c,) for c in JUR_CONCEPTS]
        elif slots == ["article", "code"]:
            combos = list(itertools.product(
                random.sample(JUR_ARTICLES_CELEBRES, min(10, len(JUR_ARTICLES_CELEBRES))),
                random.sample(JUR_CODES, min(8, len(JUR_CODES)))
            ))
        elif slots == ["code", "concept"]:
            combos = list(itertools.product(
                random.sample(JUR_CODES, min(10, len(JUR_CODES))),
                random.sample(JUR_CONCEPTS, min(15, len(JUR_CONCEPTS)))
            ))
        elif slots == ["concept_pair"]:
            concept_pairs = list(itertools.combinations(
                random.sample(JUR_CONCEPTS, min(15, len(JUR_CONCEPTS))), 2))
            combos = [(cp,) for cp in concept_pairs]
        elif slots == ["domaine", "concept"]:
            combos = list(itertools.product(
                random.sample(JUR_DOMAINES, min(12, len(JUR_DOMAINES))),
                random.sample(JUR_CONCEPTS, min(12, len(JUR_CONCEPTS)))
            ))
        elif slots == ["procedure", "code"]:
            combos = list(itertools.product(
                random.sample(JUR_PROCEDURES, min(12, len(JUR_PROCEDURES))),
                random.sample(JUR_CODES, min(10, len(JUR_CODES)))
            ))
        elif slots == ["domaine", "code"]:
            combos = list(itertools.product(
                random.sample(JUR_DOMAINES, min(12, len(JUR_DOMAINES))),
                random.sample(JUR_CODES, min(10, len(JUR_CODES)))
            ))
        elif slots == ["concept", "code", "domaine"]:
            combos = list(itertools.product(
                random.sample(JUR_CONCEPTS, min(8, len(JUR_CONCEPTS))),
                random.sample(JUR_CODES, min(5, len(JUR_CODES))),
                random.sample(JUR_DOMAINES, min(5, len(JUR_DOMAINES)))
            ))
        else:
            continue

        random.shuffle(combos)
        for combo in combos:
            if len(questions) >= max_questions:
                break
            try:
                q = pattern
                slot_idx = 0
                for s in slots:
                    val = combo[slot_idx]
                    if s == "concept_pair":
                        q = q.replace("{concept1}", val[0]).replace("{concept2}", val[1])
                    else:
                        q = q.replace("{" + s + "}", str(val))
                    slot_idx += 1
            except (IndexError, KeyError):
                continue

            if "{" in q:
                continue

            q_hash = hashlib.md5(q.encode()).hexdigest()[:12]
            if q_hash in seen:
                continue
            seen.add(q_hash)

            questions.append({
                "question": q,
                "pipeline": pipeline,
                "sector": "juridique",
                "difficulty": _pick_difficulty(),
                "expected_contains": _expected_contains(q, "juridique"),
            })

        if len(questions) >= max_questions:
            break

    return questions[:max_questions]


def _expand_industrie_templates(max_questions=1000):
    """Expand industrie templates into concrete questions."""
    questions = []
    seen = set()

    for pattern, pipeline, slots in IND_TEMPLATE_PATTERNS:
        combos = []
        if slots == ["norme", "methode"]:
            combos = list(itertools.product(
                random.sample(IND_NORMES, min(12, len(IND_NORMES))),
                random.sample(IND_METHODES, min(12, len(IND_METHODES)))
            ))
        elif slots == ["methode", "secteur_ind"]:
            combos = list(itertools.product(
                random.sample(IND_METHODES, min(15, len(IND_METHODES))),
                random.sample(IND_SECTORS_SPECIFIC, min(10, len(IND_SECTORS_SPECIFIC)))
            ))
        elif slots == ["kpi", "equipement"]:
            combos = list(itertools.product(
                random.sample(IND_KPI, min(10, len(IND_KPI))),
                random.sample(IND_EQUIPEMENTS, min(10, len(IND_EQUIPEMENTS)))
            ))
        elif slots == ["equipement"]:
            combos = [(e,) for e in IND_EQUIPEMENTS]
        elif slots == ["norme", "secteur_ind"]:
            combos = list(itertools.product(
                random.sample(IND_NORMES, min(12, len(IND_NORMES))),
                random.sample(IND_SECTORS_SPECIFIC, min(10, len(IND_SECTORS_SPECIFIC)))
            ))
        elif slots == ["kpi"]:
            combos = [(k,) for k in IND_KPI]
        elif slots == ["norme"]:
            combos = [(n,) for n in IND_NORMES]
        elif slots == ["norme_pair"]:
            norme_pairs = list(itertools.combinations(
                random.sample(IND_NORMES, min(12, len(IND_NORMES))), 2))
            combos = [(np_,) for np_ in norme_pairs]
        elif slots == ["methode", "norme"]:
            combos = list(itertools.product(
                random.sample(IND_METHODES, min(10, len(IND_METHODES))),
                random.sample(IND_NORMES, min(10, len(IND_NORMES)))
            ))
        elif slots == ["kpi", "equipement", "secteur_ind"]:
            combos = list(itertools.product(
                random.sample(IND_KPI, min(6, len(IND_KPI))),
                random.sample(IND_EQUIPEMENTS, min(6, len(IND_EQUIPEMENTS))),
                random.sample(IND_SECTORS_SPECIFIC, min(5, len(IND_SECTORS_SPECIFIC)))
            ))
        elif slots == ["kpi", "secteur_ind"]:
            combos = list(itertools.product(
                random.sample(IND_KPI, min(10, len(IND_KPI))),
                random.sample(IND_SECTORS_SPECIFIC, min(8, len(IND_SECTORS_SPECIFIC)))
            ))
        elif slots == ["equipement", "kpi", "norme"]:
            combos = list(itertools.product(
                random.sample(IND_EQUIPEMENTS, min(6, len(IND_EQUIPEMENTS))),
                random.sample(IND_KPI, min(5, len(IND_KPI))),
                random.sample(IND_NORMES, min(5, len(IND_NORMES)))
            ))
        elif slots == ["secteur_ind", "methode", "norme"]:
            combos = list(itertools.product(
                random.sample(IND_SECTORS_SPECIFIC, min(5, len(IND_SECTORS_SPECIFIC))),
                random.sample(IND_METHODES, min(5, len(IND_METHODES))),
                random.sample(IND_NORMES, min(5, len(IND_NORMES)))
            ))
        else:
            continue

        random.shuffle(combos)
        for combo in combos:
            if len(questions) >= max_questions:
                break
            try:
                q = pattern
                slot_idx = 0
                for s in slots:
                    val = combo[slot_idx]
                    if s == "norme_pair":
                        q = q.replace("{norme1}", val[0]).replace("{norme2}", val[1])
                    else:
                        q = q.replace("{" + s + "}", str(val))
                    slot_idx += 1
            except (IndexError, KeyError):
                continue

            if "{" in q:
                continue

            q_hash = hashlib.md5(q.encode()).hexdigest()[:12]
            if q_hash in seen:
                continue
            seen.add(q_hash)

            questions.append({
                "question": q,
                "pipeline": pipeline,
                "sector": "industrie",
                "difficulty": _pick_difficulty(),
                "expected_contains": _expected_contains(q, "industrie"),
            })

        if len(questions) >= max_questions:
            break

    return questions[:max_questions]


def _balance_by_pipeline(questions, max_questions):
    """Re-balance questions to ensure pipeline diversity within budget."""
    # Target: standard 60%, graph 15%, quantitative 15%, orchestrator 10%
    pipeline_targets = {
        "standard": int(max_questions * 0.60),
        "graph": int(max_questions * 0.15),
        "quantitative": int(max_questions * 0.15),
        "orchestrator": int(max_questions * 0.10),
    }

    by_pipeline = {}
    for q in questions:
        p = q["pipeline"]
        by_pipeline.setdefault(p, []).append(q)

    result = []
    for pipeline, target in pipeline_targets.items():
        pool = by_pipeline.get(pipeline, [])
        random.shuffle(pool)
        result.extend(pool[:target])

    # Fill remaining from any pipeline
    used_ids = {id(q) for q in result}
    for q in questions:
        if len(result) >= max_questions:
            break
        if id(q) not in used_ids:
            result.append(q)
            used_ids.add(id(q))

    random.shuffle(result)
    return result[:max_questions]


def expand_all_templates(target=5000, sectors=None):
    """Expand all sector templates. Returns list of question dicts."""
    if sectors is None:
        sectors = SECTORS

    # Distribute target proportionally
    if len(sectors) == 1:
        # Single sector gets full target
        targets = {sectors[0]: target}
    else:
        # Multi-sector: Finance 30%, Juridique 30%, BTP 20%, Industrie 20%
        ratios = {"finance": 0.30, "btp": 0.20, "juridique": 0.30, "industrie": 0.20}
        # Normalize ratios for selected sectors
        total_ratio = sum(ratios.get(s, 0.25) for s in sectors)
        targets = {}
        for s in sectors:
            targets[s] = int(target * ratios.get(s, 0.25) / total_ratio)
        # Distribute remainder
        remainder = target - sum(targets.values())
        for s in sectors:
            if remainder <= 0:
                break
            targets[s] += 1
            remainder -= 1

    all_questions = []
    expanders = {
        "finance": _expand_finance_templates,
        "btp": _expand_btp_templates,
        "juridique": _expand_juridique_templates,
        "industrie": _expand_industrie_templates,
    }

    for sector in sectors:
        if sector in expanders and sector in targets:
            t = targets[sector]
            # Generate 2x target to have pool for pipeline balancing
            print(f"  Expanding {sector} templates (target: {t})...")
            qs = expanders[sector](max_questions=t * 2)
            balanced = _balance_by_pipeline(qs, t)
            # Show pipeline breakdown
            pipe_counts = {}
            for q in balanced:
                pipe_counts[q["pipeline"]] = pipe_counts.get(q["pipeline"], 0) + 1
            print(f"    -> Generated {len(balanced)} questions ({pipe_counts})")
            all_questions.extend(balanced)

    _stats["questions_from_templates"] = len(all_questions)
    return all_questions


# =========================================================================
#  SECTION 3 — LLM QUESTION GENERATION
# =========================================================================

def _call_llm(messages, max_retries=3, timeout=60):
    """Call LLM with retry logic. Tries LiteLLM first, falls back to Groq."""
    _stats["llm_calls"] += 1

    for attempt in range(max_retries):
        # Try LiteLLM proxy first
        try:
            r = requests.post(
                LITELLM_URL,
                headers={
                    "Authorization": f"Bearer {LITELLM_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LITELLM_MODEL,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": 4000,
                },
                timeout=timeout,
            )
            if r.status_code == 200:
                data = r.json()
                content = data["choices"][0]["message"]["content"]
                _stats["llm_successes"] += 1
                return content
            elif r.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                _stats["llm_retries"] += 1
                time.sleep(wait)
                continue
        except (requests.exceptions.RequestException, KeyError, IndexError):
            pass

        # Fallback: direct Groq
        groq_key = _next_groq_key()
        if groq_key:
            try:
                r = requests.post(
                    GROQ_URL,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "temperature": 0.8,
                        "max_tokens": 4000,
                    },
                    timeout=timeout,
                )
                if r.status_code == 200:
                    data = r.json()
                    content = data["choices"][0]["message"]["content"]
                    _stats["llm_successes"] += 1
                    return content
                elif r.status_code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 2)
                    _stats["llm_retries"] += 1
                    time.sleep(wait)
                    continue
            except (requests.exceptions.RequestException, KeyError, IndexError):
                pass

        # Wait before retry
        if attempt < max_retries - 1:
            wait = (2 ** attempt) + random.uniform(0, 1)
            _stats["llm_retries"] += 1
            time.sleep(wait)

    _stats["llm_failures"] += 1
    return None


SECTOR_DESCRIPTIONS = {
    "finance": """Finance d'entreprise et marches financiers.
Couvre: analyse financiere, comptabilite IFRS/US GAAP, SEC filings, ratios financiers,
valorisation d'entreprise, fusions-acquisitions, gestion de portefeuille, risques,
reglementation bancaire (Bale III/IV), reporting ESG, audit, fiscalite, marches de capitaux,
instruments derives, analyse de credit, private equity, fintech.""",

    "btp": """Batiment et Travaux Publics (construction) en France.
Couvre: DTU (Documents Techniques Unifies), Eurocodes, RE2020 (reglementation energetique),
beton arme, charpente, fondations, isolation thermique, acoustique, securite incendie,
VRD, assainissement, marches publics, CCTP, DQE, coordination SPS, reception des ouvrages,
normes AFNOR, accessibilite, diagnostics immobiliers, geotechnique, PLU.""",

    "juridique": """Droit francais dans toutes ses branches.
Couvre: Code civil, Code de commerce, Code du travail, droit des contrats, responsabilite civile,
droit des societes, droit penal, procedure civile, droit administratif, RGPD, propriete intellectuelle,
droit de la concurrence, droit bancaire, droit fiscal, droit de l'urbanisme, droit de l'environnement,
droit europeen, procedures collectives, arbitrage, mediation.""",

    "industrie": """Industrie et manufacturing.
Couvre: ISO 9001/14001/45001, AMDEC/FMEA, lean manufacturing, Six Sigma, TPM, maintenance predictive,
securite machines (directive 2006/42/CE), ATEX, REACH, fiches de securite, controle qualite,
SPC, 8D, metrologie, robotique industrielle, automatisation, SCADA, fabrication additive,
traitement de surface, audit qualite, supply chain, bilan carbone.""",
}

PIPELINE_INSTRUCTIONS = {
    "standard": "questions de connaissances generales du domaine, factuelles ou analytiques",
    "graph": "questions sur les RELATIONS entre entites (entreprises, normes, personnes, concepts) — commencer par 'Quelle est la relation entre...', 'Quels sont les liens entre...', 'Quelles entites sont liees a...'",
    "quantitative": "questions NUMERIQUES necessitant des calculs, des donnees chiffrees, des comparaisons de metriques — commencer par 'Quel est le montant...', 'Calculez...', 'Comparez les chiffres...'",
    "orchestrator": "questions COMPLEXES multi-etapes necessitant plusieurs sources d'information, analyse croisee de documents, synthese de donnees et texte",
}


def _build_generation_prompt(sector, pipeline, batch_size, existing_questions=None):
    """Build prompt for LLM question generation."""
    sector_desc = SECTOR_DESCRIPTIONS.get(sector, sector)
    pipeline_desc = PIPELINE_INSTRUCTIONS.get(pipeline, pipeline)

    avoid_text = ""
    if existing_questions:
        sample = random.sample(existing_questions, min(5, len(existing_questions)))
        avoid_text = "\n\nEVITEZ de generer des questions similaires a celles-ci (deja existantes):\n"
        for eq in sample:
            avoid_text += f"- {eq['question'][:100]}\n"

    return f"""Tu es un expert en {sector}. Genere exactement {batch_size} questions d'evaluation uniques qu'un professionnel senior poserait.

DOMAINE: {sector_desc}

TYPE DE QUESTIONS (pipeline {pipeline}): {pipeline_desc}

REGLES:
- Questions SPECIFIQUES et TECHNIQUES (pas generiques)
- Terminologie professionnelle correcte du secteur, en FRANCAIS (80%) et ANGLAIS (20%)
- Difficultes variees : basic (20%), intermediate (40%), expert (40%)
- Couvrir differents sous-domaines et types de documents du secteur
- Chaque question doit avoir des mots-cles attendus dans la reponse
- Les questions doivent etre realistement posees par un professionnel
{avoid_text}

Reponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ou apres:
[
  {{"question": "...", "expected_contains": ["mot-cle1", "mot-cle2"], "difficulty": "basic|intermediate|expert", "doc_type": "type_de_document"}},
  ...
]"""


def _parse_llm_questions(content, sector, pipeline):
    """Parse LLM response into question dicts."""
    if not content:
        return []

    # Strip think tags
    if "<think>" in content:
        idx = content.find("</think>")
        if idx > 0:
            content = content[idx + 8:]

    # Strip markdown code blocks
    if "```" in content:
        parts = content.split("```")
        for part in parts[1:]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:]
            part = part.strip()
            try:
                items = json.loads(part)
                if isinstance(items, list):
                    content = part
                    break
            except json.JSONDecodeError:
                continue

    # Find JSON array
    start = content.find("[")
    end = content.rfind("]")
    if start < 0 or end <= start:
        return []

    try:
        items = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        # Try to fix common JSON issues
        raw = content[start:end + 1]
        # Fix trailing commas
        raw = re.sub(r",\s*]", "]", raw)
        raw = re.sub(r",\s*}", "}", raw)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return []

    if not isinstance(items, list):
        return []

    questions = []
    for item in items:
        if not isinstance(item, dict) or "question" not in item:
            continue

        q = item["question"].strip()
        if len(q) < 10:
            continue

        expected = item.get("expected_contains", [])
        if isinstance(expected, str):
            expected = [expected]
        if not expected:
            expected = _expected_contains(q, sector)

        difficulty = item.get("difficulty", "intermediate")
        if difficulty not in DIFFICULTIES:
            difficulty = "intermediate"

        questions.append({
            "question": q,
            "pipeline": pipeline,
            "sector": sector,
            "difficulty": difficulty,
            "expected_contains": expected[:5],
            "doc_type": item.get("doc_type", ""),
        })

    return questions


def generate_llm_questions(sector, pipeline, count, existing_questions=None, batch_size=20):
    """Generate questions via LLM for a specific sector+pipeline combination."""
    questions = []
    batches_needed = (count + batch_size - 1) // batch_size

    for batch_num in range(batches_needed):
        if len(questions) >= count:
            break

        remaining = min(batch_size, count - len(questions))
        prompt = _build_generation_prompt(
            sector, pipeline, remaining, existing_questions
        )

        content = _call_llm([
            {"role": "system", "content": "Tu generes des questions d'evaluation pour un systeme RAG sectoriel expert. Reponds UNIQUEMENT en JSON."},
            {"role": "user", "content": prompt},
        ])

        if content:
            batch_qs = _parse_llm_questions(content, sector, pipeline)
            questions.extend(batch_qs)
            if existing_questions is not None:
                existing_questions = existing_questions + batch_qs

        # Rate limiting between batches
        time.sleep(0.5)

    _stats["questions_from_llm"] += len(questions)
    return questions[:count]


def generate_llm_all_sectors(target, sectors=None, batch_size=20, max_workers=5):
    """Generate LLM questions for all sectors with concurrency control."""
    if sectors is None:
        sectors = SECTORS

    # Pipeline distribution: standard 60%, graph 15%, quantitative 15%, orchestrator 10%
    pipeline_ratios = {
        "standard": 0.60,
        "graph": 0.15,
        "quantitative": 0.15,
        "orchestrator": 0.10,
    }
    # Sector distribution
    sector_ratios = {"finance": 0.30, "btp": 0.20, "juridique": 0.30, "industrie": 0.20}

    tasks = []
    for sector in sectors:
        sector_target = int(target * sector_ratios.get(sector, 0.25))
        for pipeline, pratio in pipeline_ratios.items():
            pipe_target = max(5, int(sector_target * pratio))
            tasks.append((sector, pipeline, pipe_target))

    all_questions = []
    completed = 0
    total_tasks = len(tasks)

    print(f"\n  LLM generation plan: {total_tasks} sector*pipeline combinations")
    for sector, pipeline, pipe_target in tasks:
        print(f"    {sector}/{pipeline}: {pipe_target} questions")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for sector, pipeline, pipe_target in tasks:
            f = executor.submit(
                generate_llm_questions,
                sector, pipeline, pipe_target,
                existing_questions=None,
                batch_size=batch_size,
            )
            futures[f] = (sector, pipeline, pipe_target)

        for future in as_completed(futures):
            sector, pipeline, pipe_target = futures[future]
            completed += 1
            try:
                qs = future.result()
                all_questions.extend(qs)
                print(f"  [{completed}/{total_tasks}] {sector}/{pipeline}: {len(qs)}/{pipe_target} generated")
            except Exception as e:
                print(f"  [{completed}/{total_tasks}] {sector}/{pipeline}: ERROR - {e}")

    return all_questions


# =========================================================================
#  SECTION 4 — DEDUPLICATION & FINALIZATION
# =========================================================================

def deduplicate_questions(questions):
    """Remove duplicate questions by content similarity."""
    seen = set()
    unique = []

    for q in questions:
        # Normalize: lowercase, strip punctuation, collapse whitespace
        normalized = re.sub(r'[^\w\s]', '', q["question"].lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        q_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]

        if q_hash not in seen:
            seen.add(q_hash)
            unique.append(q)
        else:
            _stats["duplicates_removed"] += 1

    return unique


def assign_ids(questions):
    """Assign unique IDs to all questions."""
    # Group by sector+pipeline for sequential IDs
    groups = {}
    for q in questions:
        key = (q["sector"], q["pipeline"])
        groups.setdefault(key, []).append(q)

    for (sector, pipeline), qs in groups.items():
        for i, q in enumerate(qs):
            q["id"] = _make_id(sector, pipeline, i + 1)
            q["source"] = q.get("source", "template-generated-v1")

    return questions


def build_output(questions, include_existing=False):
    """Build final output JSON with metadata."""
    existing = []
    if include_existing:
        existing_file = os.path.join(DATASET_DIR, "sector-full-eval.json")
        if os.path.exists(existing_file):
            with open(existing_file) as f:
                data = json.load(f)
                existing = data.get("questions", [])
                for eq in existing:
                    eq["source"] = eq.get("source", "original-v3.0")

    all_questions = existing + questions

    # Stats
    sector_counts = {}
    pipeline_counts = {}
    difficulty_counts = {}
    for q in all_questions:
        sector_counts[q["sector"]] = sector_counts.get(q["sector"], 0) + 1
        pipeline_counts[q["pipeline"]] = pipeline_counts.get(q["pipeline"], 0) + 1
        difficulty_counts[q.get("difficulty", "unknown")] = difficulty_counts.get(q.get("difficulty", "unknown"), 0) + 1

    output = {
        "metadata": {
            "title": f"Sector Full Evaluation - Extended ({len(all_questions)} questions)",
            "generated_at": datetime.now().isoformat(),
            "version": "4.0-extended",
            "total_questions": len(all_questions),
            "new_questions": len(questions),
            "original_questions": len(existing),
            "sectors": SECTORS,
            "sector_distribution": sector_counts,
            "pipeline_distribution": pipeline_counts,
            "difficulty_distribution": difficulty_counts,
            "generation_stats": dict(_stats),
            "note": "Auto-generated via mass-question-generator.py. Includes template-expanded and LLM-generated questions.",
        },
        "questions": all_questions,
    }

    return output


# =========================================================================
#  SECTION 5 — INCREMENTAL SAVE
# =========================================================================

def save_progress(questions, output_file=OUTPUT_FILE):
    """Save progress incrementally."""
    output = build_output(questions, include_existing=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    # Save progress marker
    progress = {
        "last_save": datetime.now().isoformat(),
        "questions_saved": len(questions),
        "stats": dict(_stats),
    }
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def load_progress():
    """Load previously generated questions for resumption."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                data = json.load(f)
            qs = data.get("questions", [])
            # Filter to only generated questions (not original)
            generated = [q for q in qs if q.get("source", "").startswith(("template-", "llm-"))]
            return generated
        except (json.JSONDecodeError, KeyError):
            pass
    return []


# =========================================================================
#  SECTION 6 — CLI & MAIN
# =========================================================================

def print_plan(target, sectors, templates_only, batch_size):
    """Print generation plan without executing."""
    print("=" * 70)
    print("  MASS QUESTION GENERATOR — DRY RUN")
    print("=" * 70)

    sector_ratios = {"finance": 0.30, "btp": 0.20, "juridique": 0.30, "industrie": 0.20}
    pipeline_ratios = {"standard": 0.60, "graph": 0.15, "quantitative": 0.15, "orchestrator": 0.10}

    print(f"\n  Target: {target} questions")
    print(f"  Sectors: {', '.join(sectors)}")
    print(f"  Mode: {'Templates only' if templates_only else 'Templates + LLM'}")
    print(f"  Batch size: {batch_size}")
    print(f"  Output: {OUTPUT_FILE}")

    print(f"\n  Sector distribution:")
    for s in sectors:
        s_target = int(target * sector_ratios.get(s, 0.25))
        print(f"    {s:12s}: {s_target:5d} questions")

    print(f"\n  Pipeline distribution (per sector):")
    for s in sectors:
        s_target = int(target * sector_ratios.get(s, 0.25))
        print(f"    {s}:")
        for p, pr in pipeline_ratios.items():
            p_target = max(5, int(s_target * pr))
            print(f"      {p:15s}: {p_target:5d}")

    if not templates_only:
        total_batches = 0
        for s in sectors:
            s_target = int(target * sector_ratios.get(s, 0.25))
            for p, pr in pipeline_ratios.items():
                p_target = max(5, int(s_target * pr))
                total_batches += (p_target + batch_size - 1) // batch_size
        print(f"\n  LLM calls needed: ~{total_batches} batches")
        print(f"  Estimated time: ~{total_batches * 3:.0f}s ({total_batches * 3 / 60:.1f} min)")

    # Template capacity estimate
    print(f"\n  Template expansion capacity (no LLM):")
    print(f"    Finance:   ~{len(FINANCE_METRICS) * len(FINANCE_COMPANIES) * len(FINANCE_YEARS) + len(FINANCE_TOPICS) * 4:,} possible")
    print(f"    BTP:       ~{len(BTP_NORMES) * len(BTP_LOTS) + len(BTP_BUILDING_TYPES) * 10:,} possible")
    print(f"    Juridique: ~{len(JUR_CONCEPTS) * len(JUR_DOMAINES) + len(JUR_CODES) * 10:,} possible")
    print(f"    Industrie: ~{len(IND_NORMES) * len(IND_METHODES) + len(IND_EQUIPEMENTS) * 10:,} possible")

    existing_file = os.path.join(DATASET_DIR, "sector-full-eval.json")
    if os.path.exists(existing_file):
        with open(existing_file) as f:
            data = json.load(f)
        print(f"\n  Existing dataset: {data['metadata']['total_questions']} questions")
        print(f"  Combined total: ~{data['metadata']['total_questions'] + target}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Mass Question Generator — 10,000+ expert evaluation questions"
    )
    parser.add_argument("--target", type=int, default=5000,
                        help="Target number of questions to generate (default: 5000)")
    parser.add_argument("--sector", type=str, default=None,
                        help="Generate for specific sector only (finance/btp/juridique/industrie)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show generation plan without executing")
    parser.add_argument("--templates-only", action="store_true",
                        help="Use template expansion only, no LLM calls")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Questions per LLM batch (default: 20)")
    parser.add_argument("--max-workers", type=int, default=5,
                        help="Max concurrent LLM calls (default: 5)")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output file path")
    parser.add_argument("--no-existing", action="store_true",
                        help="Don't include existing dataset in output")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previous progress")
    args = parser.parse_args()

    global OUTPUT_FILE
    if args.output:
        OUTPUT_FILE = args.output

    sectors = SECTORS
    if args.sector:
        if args.sector not in SECTORS:
            print(f"ERROR: Unknown sector '{args.sector}'. Choose from: {', '.join(SECTORS)}")
            sys.exit(1)
        sectors = [args.sector]

    # Dry run
    if args.dry_run:
        print_plan(args.target, sectors, args.templates_only, args.batch_size)
        return

    print("=" * 70)
    print("  MASS QUESTION GENERATOR")
    print("=" * 70)
    print(f"  Target: {args.target} questions")
    print(f"  Sectors: {', '.join(sectors)}")
    print(f"  Mode: {'Templates only' if args.templates_only else 'Templates + LLM'}")
    print(f"  Output: {OUTPUT_FILE}")
    print()

    start_time = time.time()
    all_questions = []

    # Resume?
    if args.resume:
        prev = load_progress()
        if prev:
            print(f"  Resuming: found {len(prev)} previously generated questions")
            all_questions.extend(prev)

    # Phase 1: Template expansion
    print("Phase 1: Template expansion...")
    template_target = args.target if args.templates_only else min(args.target, int(args.target * 0.6))
    template_qs = expand_all_templates(target=template_target, sectors=sectors)
    all_questions.extend(template_qs)
    print(f"  Template questions: {len(template_qs)}")

    # Incremental save after templates
    if len(all_questions) > 0:
        save_progress(all_questions, OUTPUT_FILE)
        print(f"  Saved {len(all_questions)} questions (incremental)")

    # Phase 2: LLM generation (if not templates-only)
    if not args.templates_only and len(all_questions) < args.target:
        remaining = args.target - len(all_questions)
        print(f"\nPhase 2: LLM generation ({remaining} questions needed)...")

        llm_qs = generate_llm_all_sectors(
            target=remaining,
            sectors=sectors,
            batch_size=args.batch_size,
            max_workers=args.max_workers,
        )

        # Mark LLM questions
        for q in llm_qs:
            q["source"] = "llm-generated-v1"

        all_questions.extend(llm_qs)
        print(f"  LLM questions: {len(llm_qs)}")

        # Incremental save
        save_progress(all_questions, OUTPUT_FILE)
        print(f"  Saved {len(all_questions)} questions (incremental)")

    # Phase 3: Deduplication
    print(f"\nPhase 3: Deduplication...")
    before = len(all_questions)
    all_questions = deduplicate_questions(all_questions)
    print(f"  Before: {before}, After: {len(all_questions)}, Removed: {before - len(all_questions)}")

    # Mark template questions
    for q in all_questions:
        if "source" not in q:
            q["source"] = "template-generated-v1"

    # Phase 4: Assign IDs
    print(f"\nPhase 4: Assigning IDs...")
    all_questions = assign_ids(all_questions)

    # Phase 5: Final save
    print(f"\nPhase 5: Final save...")
    _stats["questions_generated"] = len(all_questions)
    output = build_output(all_questions, include_existing=not args.no_existing)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("  GENERATION COMPLETE")
    print("=" * 70)
    print(f"  Total questions: {output['metadata']['total_questions']}")
    print(f"  New questions:   {output['metadata']['new_questions']}")
    print(f"  Original:        {output['metadata']['original_questions']}")
    print(f"  Time:            {elapsed:.1f}s")
    print(f"\n  Sector distribution:")
    for s, c in sorted(output["metadata"]["sector_distribution"].items()):
        print(f"    {s:12s}: {c:5d}")
    print(f"\n  Pipeline distribution:")
    for p, c in sorted(output["metadata"]["pipeline_distribution"].items()):
        print(f"    {p:15s}: {c:5d}")
    print(f"\n  Difficulty distribution:")
    for d, c in sorted(output["metadata"]["difficulty_distribution"].items()):
        print(f"    {d:15s}: {c:5d}")
    print(f"\n  Generation stats:")
    for k, v in sorted(_stats.items()):
        print(f"    {k:25s}: {v}")
    print(f"\n  Output: {OUTPUT_FILE}")
    print(f"  Eval capacity: {output['metadata']['total_questions'] / 5760 * 60:.0f} min of continuous eval at 48 workers")
    print("=" * 70)


if __name__ == "__main__":
    main()
