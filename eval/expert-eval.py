#!/usr/bin/env python3
"""
Expert-Grade RAG Evaluation Framework
======================================
Transforms RAG testing from basic string matching to real expert-level
quality assessment using LLM-as-judge multi-criteria scoring.

Features:
  1. Expert Question Bank — 50+ questions per sector (Finance, BTP, Juridique, Industrie)
  2. Multi-criteria LLM Scoring — 5 dimensions scored 1-5 by GPT/Gemini/Groq judge
  3. Node-by-node Performance Analysis — n8n execution timing per node
  4. Random Sampling — diverse coverage across multiple runs
  5. Adversarial Tests — cross-domain, ambiguous, out-of-scope, multilingual
  6. Results Storage — expert-results.json, sector-scores.json, bottlenecks.json

Usage:
  source .env.local
  python3 eval/expert-eval.py --proxy --sample 10                    # Quick sample
  python3 eval/expert-eval.py --proxy --sector finance --sample 5    # Finance only
  python3 eval/expert-eval.py --proxy --full                         # All questions
  python3 eval/expert-eval.py --proxy --adversarial                  # Adversarial only
  python3 eval/expert-eval.py --report                               # Show latest scores
"""

import json
import os
import sys
import time
import random
import argparse
import re
import requests
from datetime import datetime
from collections import defaultdict
from importlib.machinery import SourceFileLoader
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ─── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data", "eval")
os.makedirs(DATA_DIR, exist_ok=True)

RESULTS_FILE = os.path.join(DATA_DIR, "expert-results.json")
SECTOR_SCORES_FILE = os.path.join(DATA_DIR, "sector-scores.json")
BOTTLENECKS_FILE = os.path.join(DATA_DIR, "bottlenecks.json")
PROGRESS_FILE = os.path.join(DATA_DIR, "progress.json")
LIVE_RESULTS_FILE = os.path.join(DATA_DIR, "expert-results-live.json")

# ─── RAG Proxy ────────────────────────────────────────────────────────────
USE_PROXY = "--proxy" in sys.argv
rag_proxy = None
if USE_PROXY:
    try:
        sys.path.insert(0, os.path.join(REPO_ROOT, "ops"))
        import rag_proxy as _rp
        rag_proxy = _rp
    except ImportError:
        rag_proxy = SourceFileLoader(
            "rag_proxy", os.path.join(REPO_ROOT, "ops", "rag-proxy.py")
        ).load_module()

# ─── n8n config (for non-proxy mode + node analysis) ─────────────────────
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
WEBHOOK_PATHS = {
    "standard":     "/webhook/rag-multi-index-v3",
    "graph":        "/webhook/ff622742-6d71-4e91-af71-b5c666088717",
    "quantitative": "/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9",
    "orchestrator": "/webhook/orchestrator-v2",
}
WORKFLOW_IDS = {
    "standard": "TmgyRP20N4JFd9CB",
    "graph": "6257AfT1l4FMC6lY",
    "quantitative": "cjhEhVs0KV1ExHqX",
    "orchestrator": "ALd4gOEqiKL5KR1p",
}

# ─── LLM Judge config ────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
_GROQ_KEYS = [v for k, v in sorted(os.environ.items())
              if k.startswith("GROQ_API_KEY") and v]
if not _GROQ_KEYS:
    _GROQ_KEYS = [os.environ.get("GROQ_API_KEY", "")]
_GROQ_KEYS = [k for k in _GROQ_KEYS if k]

_lock = Lock()
_groq_idx = 0


def _next_groq_key():
    global _groq_idx
    with _lock:
        if not _GROQ_KEYS:
            return ""
        key = _GROQ_KEYS[_groq_idx % len(_GROQ_KEYS)]
        _groq_idx += 1
        return key


# =========================================================================
#  SECTION 1 — EXPERT QUESTION BANK (50+ per sector)
# =========================================================================

EXPERT_QUESTIONS = {
    "finance": [
        # --- Factual / Numerical ---
        {"id": "exp-fin-01", "question": "Quel est le ratio dette/EBITDA de 3M en FY2018 et comment se compare-t-il au secteur ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-02", "question": "Quels sont les risques operationnels identifies dans le 10-K de Boeing ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-03", "question": "Quel est le montant des depenses d'investissement (CAPEX) de 3M pour l'exercice 2018 ?", "category": "numerical", "difficulty": "easy", "language": "fr"},
        {"id": "exp-fin-04", "question": "Comment la marge brute de Boeing a-t-elle evolue entre FY2020 et FY2022 ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-05", "question": "What are the main revenue segments for Boeing in FY2022?", "category": "factual", "difficulty": "easy", "language": "en"},
        {"id": "exp-fin-06", "question": "Quelle est la structure du bilan de Verizon en termes de ratio dette/capitaux propres ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-07", "question": "Quels sont les principaux postes de charges d'exploitation de 3M en 2022 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-08", "question": "What was the net cash from operating activities in fiscal year 2009?", "category": "numerical", "difficulty": "easy", "language": "en"},
        {"id": "exp-fin-09", "question": "Comment la politique de dividendes de 3M reflete-t-elle sa strategie de retour aux actionnaires ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-10", "question": "Quels sont les engagements hors bilan de Boeing mentionnes dans les notes annexes ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-11", "question": "What is the breakdown of Boeing's backlog by segment?", "category": "factual", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-12", "question": "Quel est le taux d'imposition effectif de Boeing en FY2022 et pourquoi differe-t-il du taux statutaire ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-13", "question": "Quelle est la variation des creances clients entre 2008 et 2009 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-14", "question": "How does AMD's customer concentration risk affect its revenue stability?", "category": "analytical", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-15", "question": "Quel est le montant de la reserve de garantie (Warranty Reserve) en 2019 ?", "category": "numerical", "difficulty": "easy", "language": "fr"},
        {"id": "exp-fin-16", "question": "Comment les charges de restructuration de 3M impactent-elles le resultat operationnel de 2022 ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-17", "question": "What were Republic Services' pro forma revenues in 2008?", "category": "numerical", "difficulty": "easy", "language": "en"},
        {"id": "exp-fin-18", "question": "Quelle est la sensibilite du resultat net de Boeing aux variations de taux de change ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-19", "question": "Quels types de contrats (fixed-price, cost-plus, T&M) sont utilises dans les rapports financiers ?", "category": "factual", "difficulty": "easy", "language": "fr"},
        {"id": "exp-fin-20", "question": "Comment la tresorerie d'exploitation a-t-elle evolue entre 2005 et 2009 ?", "category": "analytical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-21", "question": "What is Pfizer's PP&E growth trend between FY2020 and FY2021?", "category": "analytical", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-22", "question": "Quel est le ratio CAPEX/Revenue de 3M et que revele-t-il sur l'intensite capitalistique ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-23", "question": "Quelles provisions pour litiges 3M a-t-elle constituees en 2022 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-24", "question": "What is the average total interest expense for 2017 to 2019?", "category": "numerical", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-25", "question": "Comment TORM definit-elle sa liquidite et quels indicateurs utilise-t-elle ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-26", "question": "Quelle est la part des ventes d'emballages industriels nord-americains dans le total en 2012 ?", "category": "numerical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-27", "question": "What drove the reduction in SG&A expense as a percent of net sales for 3M?", "category": "analytical", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-28", "question": "Quel segment a le plus contribue a la croissance de 3M en 2022 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-29", "question": "Les marges brutes de Best Buy sont-elles stables sur la periode 2020-2023 ?", "category": "analytical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-30", "question": "What is the diluted earnings per share on a pro forma basis for 2008?", "category": "numerical", "difficulty": "easy", "language": "en"},
        {"id": "exp-fin-31", "question": "Quel est le resultat net par segment de JPMorgan au T1 2021 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-32", "question": "Comment l'evolution des creances clients en 2009 impacte-t-elle le free cash flow ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-33", "question": "What percentage of Boeing's total revenue comes from the defense segment in 2022?", "category": "numerical", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-34", "question": "Quels facteurs expliquent la variation du BFR (besoin en fonds de roulement) de 3M ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-35", "question": "Quel est le montant des dividendes verses en 2009 ?", "category": "numerical", "difficulty": "easy", "language": "fr"},
        {"id": "exp-fin-36", "question": "How did unrecognized tax benefits change between 2017 and 2018?", "category": "analytical", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-37", "question": "Quelles sont les principales expositions au risque de credit de Verizon ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-38", "question": "Quelle est la variation du ratio dette nette/EBITDA entre FY18 et FY19 ?", "category": "numerical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-39", "question": "What is the significance of Boeing's production rate changes for 737 MAX?", "category": "analytical", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-40", "question": "Quels sont les engagements de location operationnelle de 3M et comment affectent-ils le bilan IFRS 16 ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-41", "question": "Quel est le chiffre d'affaires total en Thailande entre 2017 et 2019 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-42", "question": "What factors contributed to AMD's revenue growth in FY2022?", "category": "factual", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-43", "question": "Quelle est la moyenne des actifs contractuels pour decembre 2018 et 2019 ?", "category": "numerical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-44", "question": "Comment le cout moyen pondere du capital (WACC) de Boeing evolue-t-il avec sa structure de dette actuelle ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-45", "question": "Quels indicateurs de liquidite 3M presente-t-elle dans son rapport annuel ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-46", "question": "What was Verizon's projected pension payment for 2024?", "category": "numerical", "difficulty": "medium", "language": "en"},
        {"id": "exp-fin-47", "question": "Quelle est la croissance organique par segment geographique de 3M en 2022 ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-fin-48", "question": "How does Best Buy's gross margin decline between FY2022 and FY2023 compare to industry trends?", "category": "comparison", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-49", "question": "Quels sont les principaux facteurs de risque reglementaire mentionnes par Pfizer ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-50", "question": "Quelle est la variation en pourcentage des depenses de loyer entre 2005 et 2006 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-fin-51", "question": "What is the breakdown of 3M's R&D spending by segment?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-fin-52", "question": "Comment le ratio de couverture des interets de Boeing a-t-il evolue suite aux pertes du 737 MAX ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
    ],

    "btp": [
        {"id": "exp-btp-01", "question": "Quelles sont les exigences du DTU 31.2 pour les ossatures bois ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-02", "question": "Comment calculer le U-value d'une paroi selon la RE2020 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-03", "question": "Quel est le diametre minimum d'espace de retournement pour un fauteuil roulant selon les normes d'accessibilite ?", "category": "numerical", "difficulty": "easy", "language": "fr"},
        {"id": "exp-btp-04", "question": "Quelles sont les regles de contreventement pour une structure en acier selon l'Eurocode 3 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-05", "question": "Comment dimensionner une fondation superficielle selon le DTU 13.12 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-06", "question": "Quels sont les delais de paiement reglementaires dans les marches publics BTP ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-07", "question": "What are the fire resistance requirements for structural elements in ERP buildings?", "category": "factual", "difficulty": "medium", "language": "en"},
        {"id": "exp-btp-08", "question": "Quelles sont les exigences d'etancheite a l'air selon la RE2020 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-09", "question": "Comment s'applique le CCAG Travaux 2021 pour la reception des ouvrages ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-10", "question": "Quels essais de sol sont obligatoires avant la construction d'un batiment R+3 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-11", "question": "Quelle est la pression d'essai pour les canalisations d'eau potable selon le DTU 60.1 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-12", "question": "Comment verifier la conformite d'un echafaudage selon la norme NF EN 12811 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-13", "question": "Quels sont les documents obligatoires du CCTP pour un marche de gros oeuvre ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-14", "question": "What is the minimum concrete cover for reinforcement in exposure class XC4?", "category": "numerical", "difficulty": "hard", "language": "en"},
        {"id": "exp-btp-15", "question": "Comment calculer les charges de neige selon l'Eurocode 1 pour la zone C2 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-16", "question": "Quelles sont les obligations du maitre d'ouvrage en matiere de coordination SPS ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-17", "question": "Quel est le classement au feu minimal pour les materiaux d'isolation en ERP ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-18", "question": "Comment dimensionner un reseau d'evacuation des eaux pluviales pour un batiment de 500m2 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-19", "question": "Quels sont les seuils de marche public pour les procedures formalisees en travaux ?", "category": "factual", "difficulty": "easy", "language": "fr"},
        {"id": "exp-btp-20", "question": "Comment s'articulent les garanties decennale et biennale dans le Code civil ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-21", "question": "Quelle est la resistance thermique minimale pour un mur exterieur en zone H1 ?", "category": "numerical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-22", "question": "What safety measures are required for working at heights above 3 meters?", "category": "factual", "difficulty": "medium", "language": "en"},
        {"id": "exp-btp-23", "question": "Comment appliquer la methode de calcul Th-BCE pour le bilan energetique d'un batiment ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-24", "question": "Quels sont les criteres de conformite QUALIBAT pour la mention RGE ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-25", "question": "Comment gerer les interfaces entre lots dans un marche en lots separes ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-26", "question": "Quelles sont les exigences acoustiques selon la NRA pour un logement collectif ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-27", "question": "Quel est le delai de garantie de parfait achevement en marche public ?", "category": "factual", "difficulty": "easy", "language": "fr"},
        {"id": "exp-btp-28", "question": "Comment realiser un diagnostic amiante avant travaux selon la norme NF X 46-020 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-29", "question": "Quelles sont les prescriptions du DTU 20.1 pour les murs en maconnerie de petits elements ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-30", "question": "What are the Eurocode 2 requirements for minimum reinforcement in slabs?", "category": "numerical", "difficulty": "hard", "language": "en"},
        {"id": "exp-btp-31", "question": "Comment dimensionner un systeme de ventilation VMC double flux selon les normes en vigueur ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-32", "question": "Quels documents doit contenir le DOE (Dossier des Ouvrages Executes) ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-33", "question": "Quelle est la portee maximale d'une dalle BA de 20cm sans poutre intermediaire ?", "category": "numerical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-34", "question": "Comment s'applique la norme NF P94-500 pour les missions geotechniques ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-35", "question": "Quelles sont les regles de recul par rapport aux limites separatives selon le PLU ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-36", "question": "Comment verifier la stabilite d'un mur de soutenement en beton arme ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-37", "question": "Quels sont les criteres de choix entre isolation thermique par l'interieur (ITI) et par l'exterieur (ITE) ?", "category": "analytical", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-38", "question": "Quelle est la procedure de demande de permis de construire pour un batiment de plus de 20m2 ?", "category": "procedural", "difficulty": "easy", "language": "fr"},
        {"id": "exp-btp-39", "question": "What are the requirements for fire compartmentation in multi-story buildings?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-btp-40", "question": "Comment traiter un pont thermique de liaison facade/plancher selon les regles Th-Bat ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-41", "question": "Quelles sont les obligations du CSPS en phase conception ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-42", "question": "Comment calculer le taux de boisement d'une parcelle selon le Code forestier ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-43", "question": "Quels sont les criteres d'acceptation du beton frais sur chantier selon la NF EN 206 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-44", "question": "Comment se deroule la procedure de reception avec reserves en marche public ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-45", "question": "Quel est le role du bureau de controle selon la loi Spinetta ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-46", "question": "Quelles normes AFNOR s'appliquent aux installations electriques de chantier ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-47", "question": "Comment gerer les aleas geotechniques decouverts en cours de chantier ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-48", "question": "Quelle est la duree de vie conventionnelle des ouvrages de genie civil selon l'Eurocode 0 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-49", "question": "What are the requirements for concrete curing in hot weather conditions?", "category": "procedural", "difficulty": "medium", "language": "en"},
        {"id": "exp-btp-50", "question": "Comment realiser un metre de terrassement pour un bilan quantitatif ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-btp-51", "question": "Quelles sont les obligations en matiere de gestion des dechets de chantier BTP ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-btp-52", "question": "Comment dimensionner les aciers d'une poutre BA en flexion simple selon l'EC2 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
    ],

    "juridique": [
        {"id": "exp-jur-01", "question": "Quelles sont les sanctions RGPD pour non-conformite au registre des traitements ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-02", "question": "Comment s'articulent les articles L.111-1 et L.112-1 du Code de commerce ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-03", "question": "Quelles sont les conditions de validite d'un contrat de travail a duree determinee ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-04", "question": "Comment fonctionne la responsabilite civile delictuelle selon l'article 1240 du Code civil ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-05", "question": "Quels sont les delais de prescription en matiere commerciale ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-06", "question": "What are the key provisions of the French Labor Code regarding wrongful dismissal?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-07", "question": "Comment s'applique le droit de retractation dans les contrats conclus a distance ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-08", "question": "Quelles sont les obligations du responsable de traitement en matiere de notification de violation de donnees ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-09", "question": "Que dit l'article R151-19 du Code de l'urbanisme sur les zones constructibles ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-10", "question": "Comment s'articule le mecanisme de subrogation en droit des assurances ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-11", "question": "Quelles sont les regles de competence du tribunal de commerce pour les litiges entre commercants ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-12", "question": "Comment le Code de l'energie definit-il les certificats d'economie d'energie ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-13", "question": "Quels sont les droits du salarie en cas de licenciement economique collectif ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-14", "question": "What are the French competition law provisions regarding abuse of dominant position?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-15", "question": "Comment fonctionne la procedure de sauvegarde en droit des entreprises en difficulte ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-16", "question": "Quelles clauses sont reputees abusives dans les contrats de consommation ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-17", "question": "Comment s'applique le principe de loyaute de la preuve en procedure civile ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-18", "question": "Quels sont les effets juridiques de la publication d'un acte au Journal Officiel ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-19", "question": "Comment le Conseil d'Etat controle-t-il la proportionnalite des sanctions administratives ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-20", "question": "Quelles sont les conditions de la caducite d'une offre en droit des contrats ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-21", "question": "What are the requirements for a valid arbitration clause under French law?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-22", "question": "Comment s'exerce le droit a la portabilite des donnees personnelles selon le RGPD ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-23", "question": "Quels sont les pouvoirs du juge des libertes et de la detention en matiere de garde a vue prolongee ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-24", "question": "Comment le regime de la TVA s'applique-t-il aux operations immobilieres ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-25", "question": "Quelles sont les obligations d'information prealable du franchiseur selon la loi Doubin ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-26", "question": "Comment s'applique la garantie des vices caches en matiere de vente immobiliere ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-27", "question": "Quels articles du Code de l'energie concernent les certificats d'economie d'energie ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-28", "question": "Comment le Code du travail encadre-t-il le teletravail depuis 2020 ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-29", "question": "Quelles sont les conditions de recevabilite d'un pourvoi en cassation ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-30", "question": "What are the main differences between French civil procedure and common law procedure?", "category": "comparison", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-31", "question": "Comment s'applique la clause de non-concurrence en droit du travail francais ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-32", "question": "Quels sont les seuils d'effectif declenchant l'obligation de mise en place d'un CSE ?", "category": "factual", "difficulty": "easy", "language": "fr"},
        {"id": "exp-jur-33", "question": "Comment fonctionne la responsabilite du fait des produits defectueux en droit francais ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-34", "question": "Quelles sont les mentions obligatoires d'une facture selon le Code general des impots ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-35", "question": "Comment le droit europeen de la concurrence s'articule-t-il avec le droit francais ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-36", "question": "Quels sont les effets du jugement d'ouverture d'une procedure de redressement judiciaire ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-37", "question": "Comment calculer les indemnites de licenciement selon la convention collective ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-38", "question": "What are the GDPR requirements for data protection impact assessments?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-39", "question": "Quelles sont les conditions de la force majeure en droit des contrats depuis la reforme de 2016 ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-40", "question": "Comment s'effectue le controle de constitutionnalite a priori et a posteriori en France ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-41", "question": "Quels sont les delais de recours contentieux en matiere administrative ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-42", "question": "Comment s'applique le principe de proportionnalite des peines en droit penal francais ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-43", "question": "Quelles sont les conditions de formation du contrat d'adhesion selon le Code civil ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-44", "question": "Comment le droit des societes encadre-t-il les conventions reglementees ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-45", "question": "Quels sont les recours possibles contre une decision de la CNIL ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-46", "question": "How does the French doctrine of imprévision apply to commercial contracts?", "category": "analytical", "difficulty": "hard", "language": "en"},
        {"id": "exp-jur-47", "question": "Quelles sont les obligations du mandataire social envers la societe ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-48", "question": "Comment s'articule la responsabilite penale des personnes morales ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-49", "question": "Quels sont les criteres de qualification du contrat de travail en droit francais ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-jur-50", "question": "Comment le juge administratif controle-t-il les mesures de police administrative ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-51", "question": "Quelles sont les consequences de la nullite d'un contrat en droit civil francais ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-jur-52", "question": "Comment s'applique le regime des aides d'Etat en droit europeen dans le contexte francais ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
    ],

    "industrie": [
        {"id": "exp-ind-01", "question": "Quelle est la frequence d'etalonnage recommandee pour les capteurs de pression selon ISO 9001 ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-02", "question": "Comment structurer un plan AMDEC pour une ligne de production ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-03", "question": "Quelles sont les exigences de la norme ISO 14001 pour la gestion des dechets industriels ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-04", "question": "Comment mettre en place un systeme de management de la qualite selon ISO 9001:2015 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-05", "question": "Quelles sont les methodes de controle non destructif (CND) pour les soudures selon EN 1090 ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-06", "question": "What are the key requirements for a predictive maintenance program?", "category": "procedural", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-07", "question": "Comment calculer le TRS (Taux de Rendement Synthetique) d'une ligne de production ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-08", "question": "Quelles fiches de donnees de securite sont obligatoires selon le reglement REACH ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-09", "question": "Comment mettre en oeuvre une demarche 5S dans un atelier de production ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-10", "question": "Quels sont les criteres d'acceptation pour la fabrication additive metallique selon ISO/ASTM 52900 ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-11", "question": "Comment elaborer un plan de maintenance preventive pour des equipements critiques ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-12", "question": "What are the ISO 45001 requirements for occupational health and safety management?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-13", "question": "Quelles sont les etapes d'une analyse de risques selon la methode HAZOP ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-14", "question": "Comment dimensionner un systeme de filtration industrielle pour les particules fines ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-15", "question": "Quels indicateurs de performance cles (KPI) utiliser pour le suivi qualite en production ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-16", "question": "Comment appliquer le lean manufacturing dans une PME industrielle ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-17", "question": "Quelles sont les normes de securite machine selon la directive 2006/42/CE ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-18", "question": "What are the requirements for statistical process control (SPC) in manufacturing?", "category": "procedural", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-19", "question": "Comment realiser un audit interne qualite selon ISO 19011 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-20", "question": "Quels sont les parametres critiques a controler en fabrication additive par fusion laser ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-21", "question": "Comment mettre en place un systeme de tracabilite industrielle conforme ISO 22005 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-22", "question": "Quelles sont les obligations de l'exploitant ICPE en matiere de surveillance des emissions ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-23", "question": "Comment calculer la capabilite d'un processus (Cp et Cpk) ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-24", "question": "What are the energy management requirements under ISO 50001?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-25", "question": "Quelles sont les etapes de validation d'un processus de fabrication selon ISO 13485 ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-26", "question": "Comment gerer les non-conformites selon la procedure 8D ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-27", "question": "Quels sont les types de maintenance (corrective, preventive, predictive) et leurs indicateurs ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-28", "question": "Comment mettre en oeuvre le Total Productive Maintenance (TPM) ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-29", "question": "Quelles sont les exigences de la norme EN 1090 pour l'execution des structures en acier ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-30", "question": "How do you implement Six Sigma DMAIC methodology in a manufacturing process?", "category": "procedural", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-31", "question": "Comment configurer les parametres d'un automate programmable pour un process industriel ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-32", "question": "Quels sont les criteres de selection d'un robot industriel pour une application de soudage ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-33", "question": "Comment realiser une analyse vibratoire pour la surveillance d'un roulement ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-34", "question": "Quelles sont les exigences ATEX pour les zones a risque explosif ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-35", "question": "What are the key principles of Good Manufacturing Practice (GMP)?", "category": "factual", "difficulty": "medium", "language": "en"},
        {"id": "exp-ind-36", "question": "Comment piloter un projet d'amelioration continue par la methode Kaizen ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-37", "question": "Quelles sont les normes applicables aux installations de chauffage industriel ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-38", "question": "Comment realiser un bilan carbone industriel selon la methode Bilan Carbone ADEME ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-39", "question": "Quels parametres mesurer pour le controle qualite en usinage de precision ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-40", "question": "How do you design a SCADA system for industrial process monitoring?", "category": "procedural", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-41", "question": "Comment mettre en place un plan de continuite d'activite (PCA) pour un site industriel ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-42", "question": "Quelles sont les exigences de la norme IEC 62443 pour la cybersecurite industrielle ?", "category": "factual", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-43", "question": "Comment optimiser la consommation energetique d'un systeme d'air comprime industriel ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-44", "question": "Quels sont les principes de la maintenance conditionnelle basee sur l'analyse d'huile ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-45", "question": "Comment realiser un diagramme d'Ishikawa pour identifier les causes racines d'un defaut ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-46", "question": "What are the requirements for cleanroom classification according to ISO 14644?", "category": "factual", "difficulty": "hard", "language": "en"},
        {"id": "exp-ind-47", "question": "Quelles sont les etapes de mise en service d'une installation industrielle ?", "category": "procedural", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-48", "question": "Comment gerer la sous-traitance industrielle selon les exigences ISO 9001 ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-49", "question": "Quels sont les criteres de choix d'un procede de traitement de surface (anodisation, PVD, CVD) ?", "category": "analytical", "difficulty": "hard", "language": "fr"},
        {"id": "exp-ind-50", "question": "Comment calculer le MTBF et le MTTR d'un equipement industriel ?", "category": "procedural", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-51", "question": "Quelles sont les regles de stockage des produits chimiques incompatibles en milieu industriel ?", "category": "factual", "difficulty": "medium", "language": "fr"},
        {"id": "exp-ind-52", "question": "How do you implement a closed-loop quality control system in automated manufacturing?", "category": "procedural", "difficulty": "hard", "language": "en"},
    ],
}

# =========================================================================
#  SECTION 5 — ADVERSARIAL QUESTIONS
# =========================================================================

ADVERSARIAL_QUESTIONS = [
    # Cross-domain
    {"id": "adv-01", "question": "Compare les normes IFRS avec les exigences du Code de commerce francais en matiere de presentation des comptes annuels.", "category": "cross-domain", "sectors": ["finance", "juridique"], "difficulty": "hard", "language": "fr"},
    {"id": "adv-02", "question": "Comment les exigences de la RE2020 impactent-elles les couts de construction et le financement des projets immobiliers ?", "category": "cross-domain", "sectors": ["btp", "finance"], "difficulty": "hard", "language": "fr"},
    {"id": "adv-03", "question": "Quelles obligations ISO 14001 s'appliquent aux entreprises BTP en matiere de gestion environnementale ?", "category": "cross-domain", "sectors": ["industrie", "btp"], "difficulty": "hard", "language": "fr"},
    {"id": "adv-04", "question": "How do GDPR requirements affect industrial IoT data collection in manufacturing?", "category": "cross-domain", "sectors": ["juridique", "industrie"], "difficulty": "hard", "language": "en"},
    {"id": "adv-05", "question": "Comment la responsabilite du constructeur au titre de la garantie decennale interagit-elle avec les assurances obligatoires et les normes DTU ?", "category": "cross-domain", "sectors": ["juridique", "btp"], "difficulty": "hard", "language": "fr"},

    # Ambiguous (no context)
    {"id": "adv-06", "question": "Quels sont les delais ?", "category": "ambiguous", "sectors": [], "difficulty": "medium", "language": "fr"},
    {"id": "adv-07", "question": "Comment calculer le ratio ?", "category": "ambiguous", "sectors": [], "difficulty": "medium", "language": "fr"},
    {"id": "adv-08", "question": "Quelle est la norme applicable ?", "category": "ambiguous", "sectors": [], "difficulty": "medium", "language": "fr"},
    {"id": "adv-09", "question": "What are the requirements?", "category": "ambiguous", "sectors": [], "difficulty": "medium", "language": "en"},
    {"id": "adv-10", "question": "Donnez-moi les chiffres.", "category": "ambiguous", "sectors": [], "difficulty": "medium", "language": "fr"},

    # Out-of-scope
    {"id": "adv-11", "question": "Quelle est la capitale de la France ?", "category": "out-of-scope", "sectors": [], "difficulty": "easy", "language": "fr"},
    {"id": "adv-12", "question": "Ecris-moi un poeme sur les fleurs.", "category": "out-of-scope", "sectors": [], "difficulty": "easy", "language": "fr"},
    {"id": "adv-13", "question": "What is the recipe for chocolate cake?", "category": "out-of-scope", "sectors": [], "difficulty": "easy", "language": "en"},
    {"id": "adv-14", "question": "Qui a gagne la Coupe du Monde 2022 ?", "category": "out-of-scope", "sectors": [], "difficulty": "easy", "language": "fr"},
    {"id": "adv-15", "question": "Raconte-moi une blague.", "category": "out-of-scope", "sectors": [], "difficulty": "easy", "language": "fr"},

    # Multilingual mix
    {"id": "adv-16", "question": "What are les exigences du DTU 31.2 for timber frame construction?", "category": "multilingual", "sectors": ["btp"], "difficulty": "hard", "language": "mixed"},
    {"id": "adv-17", "question": "Explain le ratio dette/EBITDA and its significance for credit analysis.", "category": "multilingual", "sectors": ["finance"], "difficulty": "hard", "language": "mixed"},
    {"id": "adv-18", "question": "Comment s'applique the GDPR's right to erasure dans le contexte francais ?", "category": "multilingual", "sectors": ["juridique"], "difficulty": "hard", "language": "mixed"},
    {"id": "adv-19", "question": "Describe la methode AMDEC and how it integrates with ISO 9001 quality management.", "category": "multilingual", "sectors": ["industrie"], "difficulty": "hard", "language": "mixed"},
    {"id": "adv-20", "question": "What est la difference between garantie decennale and garantie biennale?", "category": "multilingual", "sectors": ["btp", "juridique"], "difficulty": "hard", "language": "mixed"},
]


# =========================================================================
#  SECTION 2 — LLM JUDGE (Multi-criteria scoring)
# =========================================================================

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for a French sector-specific AI assistant.
You evaluate answers on 5 criteria, each scored 1-5:

1. **factual_accuracy** (1-5): Is the information factually correct based on the provided sources?
   1=completely wrong, 2=mostly wrong, 3=partially correct, 4=mostly correct, 5=fully correct

2. **source_citation** (1-5): Does the answer cite specific documents, articles, or data sources?
   1=no citations, 2=vague references, 3=some citations, 4=good citations, 5=precise source references

3. **expert_terminology** (1-5): Does the answer use correct professional/technical terminology?
   1=layman language, 2=some terms, 3=adequate, 4=professional, 5=expert-level terminology

4. **completeness** (1-5): Is the answer thorough enough for a professional?
   1=empty/trivial, 2=superficial, 3=adequate, 4=thorough, 5=comprehensive expert answer

5. **language_match** (1-5): Does the response match the question's language?
   1=wrong language, 3=mixed, 5=perfect language match

Respond ONLY with valid JSON in this exact format:
{"factual_accuracy": N, "source_citation": N, "expert_terminology": N, "completeness": N, "language_match": N, "reasoning": "brief explanation"}"""


def _build_judge_prompt(question, answer, sources, sector, category):
    """Build the user prompt for the LLM judge."""
    sources_text = ""
    if sources:
        for i, s in enumerate(sources[:5]):
            text = s.get("text", "") or s.get("content", "")
            src_name = s.get("source", s.get("id", f"source-{i+1}"))
            if text:
                sources_text += f"\n[Source {i+1}: {src_name}] {text[:400]}"

    return f"""Sector: {sector}
Category: {category}

QUESTION: {question}

RAG ANSWER: {answer[:1500] if answer else "(empty)"}

RETRIEVED SOURCES: {sources_text if sources_text else "(none)"}

Score this answer on the 5 criteria (1-5 each). Respond with JSON only."""


def _parse_judge_response(content):
    """Parse JSON from LLM judge response, handling markdown code blocks."""
    content = content.strip()
    # Strip <think> tags (qwen)
    if content.startswith("<think>"):
        idx = content.find("</think>")
        if idx > 0:
            content = content[idx + 8:].strip()
    # Strip markdown code block
    if "```" in content:
        parts = content.split("```")
        for part in parts[1:]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    # Try direct parse
    # Find first { and last }
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _call_openai_judge(system_prompt, user_prompt):
    """Call OpenAI GPT as judge."""
    if not OPENAI_API_KEY:
        return None, "No OPENAI_API_KEY"
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
                "max_tokens": 300,
            },
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=45,
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            return _parse_judge_response(content), None
        return None, f"OpenAI HTTP {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return None, f"OpenAI error: {str(e)[:150]}"


def _call_gemini_judge(system_prompt, user_prompt):
    """Call Google Gemini as judge."""
    if not GOOGLE_API_KEY:
        return None, "No GOOGLE_API_KEY"
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={GOOGLE_API_KEY}",
            json={
                "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300},
            },
            headers={"Content-Type": "application/json"},
            timeout=45,
        )
        if r.status_code == 200:
            data = r.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_judge_response(content), None
        return None, f"Gemini HTTP {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return None, f"Gemini error: {str(e)[:150]}"


def _call_groq_judge(system_prompt, user_prompt):
    """Call Groq LLM as judge with key rotation and model fallback."""
    if not _GROQ_KEYS:
        return None, "No GROQ_API_KEY"
    models = [
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3-32b",
        "llama-3.1-8b-instant",
    ]
    for model in models:
        for _ in range(len(_GROQ_KEYS)):
            key = _next_groq_key()
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.0,
                        "max_tokens": 300,
                    },
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    parsed = _parse_judge_response(content)
                    if parsed:
                        return parsed, None
                    return None, f"Groq parse error: {content[:200]}"
                if r.status_code != 429:
                    return None, f"Groq HTTP {r.status_code}: {r.text[:150]}"
            except Exception as e:
                if "429" not in str(e):
                    return None, f"Groq error: {str(e)[:150]}"
            time.sleep(0.5)
    return None, "All Groq keys/models exhausted"


def judge_answer(question, answer, sources, sector, category):
    """Score a RAG answer using LLM-as-judge. Returns scores dict or None."""
    user_prompt = _build_judge_prompt(question, answer, sources, sector, category)

    # Try backends in priority order: OpenAI > Gemini > Groq
    for caller, name in [
        (_call_openai_judge, "openai"),
        (_call_gemini_judge, "gemini"),
        (_call_groq_judge, "groq"),
    ]:
        scores, err = caller(JUDGE_SYSTEM_PROMPT, user_prompt)
        if scores and isinstance(scores, dict):
            # Validate all 5 criteria present with 1-5 range
            valid = True
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = scores.get(key)
                if not isinstance(val, (int, float)) or val < 1 or val > 5:
                    valid = False
                    break
            if valid:
                scores["judge_backend"] = name
                return scores
        # Log failure and try next
        if err:
            print(f"      Judge ({name}): {err[:80]}")

    # All backends failed — return default scores
    return {
        "factual_accuracy": 0, "source_citation": 0, "expert_terminology": 0,
        "completeness": 0, "language_match": 0,
        "reasoning": "All judge backends failed", "judge_backend": "none",
    }


# =========================================================================
#  SECTION 3 — NODE-BY-NODE PERFORMANCE ANALYSIS
# =========================================================================

def _n8n_api(path, timeout=30):
    """Call n8n REST API. Returns parsed JSON or None."""
    url = f"{N8N_HOST}/api/v1{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if N8N_API_KEY:
        headers["X-N8N-API-KEY"] = N8N_API_KEY
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def fetch_last_execution(workflow_id):
    """Fetch the most recent execution for a workflow. Returns execution data or None."""
    data = _n8n_api(f"/executions?workflowId={workflow_id}&limit=1&status=success")
    if data and data.get("data"):
        exec_id = data["data"][0].get("id")
        if exec_id:
            return _n8n_api(f"/executions/{exec_id}")
    return None


def analyze_execution_nodes(execution_data):
    """Extract per-node timing from an n8n execution. Returns list of node timings."""
    if not execution_data:
        return []
    result_data = execution_data.get("data", {}).get("resultData", {})
    run_data = result_data.get("runData", {})
    nodes = []
    for node_name, runs in run_data.items():
        if not runs:
            continue
        run = runs[0]  # Take first run
        start = run.get("startTime")
        end = run.get("executionTime")  # ms
        if end is None and start:
            # Estimate from data timestamps
            end = 0
        status = "success" if not run.get("error") else "error"
        error_msg = ""
        if run.get("error"):
            error_msg = str(run["error"].get("message", ""))[:200]

        items_in = 0
        items_out = 0
        if run.get("data"):
            main_data = run["data"].get("main", [])
            if main_data:
                for branch in main_data:
                    if branch:
                        items_out += len(branch)
        if run.get("source"):
            for src in run["source"]:
                if src:
                    items_in += 1

        nodes.append({
            "name": node_name,
            "execution_time_ms": end or 0,
            "status": status,
            "error": error_msg,
            "items_in": items_in,
            "items_out": items_out,
        })

    # Sort by execution time descending
    nodes.sort(key=lambda x: x["execution_time_ms"], reverse=True)
    return nodes


def analyze_pipeline_bottlenecks(pipeline):
    """Fetch latest execution for a pipeline and return node analysis."""
    wf_id = WORKFLOW_IDS.get(pipeline)
    if not wf_id:
        return None
    execution = fetch_last_execution(wf_id)
    if not execution:
        return None
    nodes = analyze_execution_nodes(execution)
    total_ms = sum(n["execution_time_ms"] for n in nodes)
    slowest = nodes[0] if nodes else None
    return {
        "pipeline": pipeline,
        "workflow_id": wf_id,
        "total_ms": total_ms,
        "node_count": len(nodes),
        "slowest_node": slowest["name"] if slowest else None,
        "slowest_ms": slowest["execution_time_ms"] if slowest else 0,
        "nodes": nodes[:10],  # Top 10 by time
    }


# =========================================================================
#  SECTION 4 — RAG QUERY FUNCTIONS
# =========================================================================

def call_proxy(query, sector=None):
    """Call RAG proxy and return structured result."""
    if not rag_proxy:
        return {"answer": "", "sources": [], "error": "Proxy not loaded", "latency_ms": 0}
    try:
        start = time.time()
        result = rag_proxy.rag_query(query, sector)
        latency = int((time.time() - start) * 1000)
        if result.get("error"):
            return {"answer": "", "sources": [], "error": result.get("message", "proxy error"), "latency_ms": latency}
        return {
            "answer": result.get("response", ""),
            "sources": result.get("sources", []),
            "error": None,
            "latency_ms": latency,
            "n_hits": result.get("n_hits", 0),
        }
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)[:200], "latency_ms": 0}


def call_webhook(pipeline, query, timeout=90):
    """Call n8n webhook endpoint."""
    webhook_path = WEBHOOK_PATHS.get(pipeline)
    if not webhook_path:
        return {"answer": "", "sources": [], "error": f"Unknown pipeline: {pipeline}", "latency_ms": 0}
    payload = {
        "query": query,
        "tenant_id": "benchmark",
        "top_k": 10,
        "include_sources": True,
        "benchmark_mode": True,
    }
    endpoint = f"{N8N_HOST}{webhook_path}"
    try:
        start = time.time()
        r = requests.post(endpoint, json=payload, timeout=timeout)
        latency = int((time.time() - start) * 1000)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, list):
                data = data[0] if data else {}
            answer = ""
            for key in ["response", "answer", "result", "interpretation", "final_response"]:
                if key in data and data[key]:
                    answer = str(data[key])
                    break
            return {"answer": answer, "sources": data.get("sources", []), "error": None, "latency_ms": latency}
        return {"answer": "", "sources": [], "error": f"HTTP {r.status_code}", "latency_ms": latency}
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)[:200], "latency_ms": 0}


# =========================================================================
#  SECTION 5b — STREAMING / INCREMENTAL OUTPUT
# =========================================================================

def _write_progress(current, total, sector, last_score, errors, elapsed_s=0):
    """Write progress.json after each question for external monitoring."""
    progress = {
        "current": current,
        "total": total,
        "sector": sector,
        "last_score": round(last_score, 2) if last_score else None,
        "errors": errors,
        "pct": round(current / total * 100, 1) if total > 0 else 0,
        "elapsed_s": round(elapsed_s, 1),
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Never crash on progress write


def _write_live_results(results):
    """Write partial results to expert-results-live.json after each question."""
    sector_agg = defaultdict(lambda: {
        "count": 0, "errors": 0,
        "factual_accuracy": [], "source_citation": [], "expert_terminology": [],
        "completeness": [], "language_match": [],
    })
    for r in results:
        s = r.get("sector", "unknown")
        sector_agg[s]["count"] += 1
        if r.get("error"):
            sector_agg[s]["errors"] += 1
        if r.get("scores"):
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = r["scores"].get(key, 0)
                if val > 0:
                    sector_agg[s][key].append(val)

    sector_summary = {}
    for s, sd in sector_agg.items():
        scores = {}
        for key in ["factual_accuracy", "source_citation", "expert_terminology",
                    "completeness", "language_match"]:
            vals = sd[key]
            scores[key] = round(sum(vals) / len(vals), 2) if vals else 0
        overall_vals = [v for v in scores.values() if v > 0]
        scores["overall"] = round(sum(overall_vals) / len(overall_vals), 2) if overall_vals else 0
        sector_summary[s] = {"count": sd["count"], "errors": sd["errors"], "scores": scores}

    live_output = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_questions": len(results),
        "sector_summary": sector_summary,
        "results": results,
    }
    try:
        with open(LIVE_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(live_output, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Never crash on live results write


def _result_avg_score(result):
    """Compute the average score from a result dict. Returns float or None."""
    scores = result.get("scores")
    if not scores:
        return None
    vals = [scores.get(k, 0) for k in
            ["factual_accuracy", "source_citation", "expert_terminology",
             "completeness", "language_match"]]
    non_zero = [v for v in vals if v > 0]
    return sum(non_zero) / len(non_zero) if non_zero else 0.0


# =========================================================================
#  SECTION 6 — EVALUATION ENGINE
# =========================================================================

_eval_stats = {
    "total": 0, "judged": 0, "errors": 0, "skipped": 0,
    "judge_backends": defaultdict(int),
}


def evaluate_single(question_data, pipeline="standard", use_proxy=True):
    """Evaluate a single question: query RAG + judge the answer."""
    qtext = question_data["question"]
    sector = question_data.get("sector", "unknown")
    category = question_data.get("category", "factual")
    qid = question_data.get("id", "unknown")

    # Query RAG
    if use_proxy:
        resp = call_proxy(qtext, sector if sector != "unknown" else None)
    else:
        resp = call_webhook(pipeline, qtext)

    if resp["error"]:
        _eval_stats["errors"] += 1
        return {
            "id": qid,
            "question": qtext,
            "sector": sector,
            "category": category,
            "difficulty": question_data.get("difficulty", "medium"),
            "language": question_data.get("language", "fr"),
            "pipeline": pipeline,
            "answer": "",
            "sources": [],
            "error": resp["error"],
            "latency_ms": resp["latency_ms"],
            "scores": None,
        }

    # Judge the answer
    scores = judge_answer(qtext, resp["answer"], resp.get("sources", []), sector, category)
    _eval_stats["judged"] += 1
    _eval_stats["judge_backends"][scores.get("judge_backend", "none")] += 1

    return {
        "id": qid,
        "question": qtext,
        "sector": sector,
        "category": category,
        "difficulty": question_data.get("difficulty", "medium"),
        "language": question_data.get("language", "fr"),
        "pipeline": pipeline,
        "answer": resp["answer"][:500],
        "sources": resp.get("sources", [])[:3],
        "error": None,
        "latency_ms": resp["latency_ms"],
        "scores": scores,
    }


def run_evaluation(questions, pipeline="standard", use_proxy=True, delay=3):
    """Run evaluation on a list of questions. Returns list of result dicts.

    Streaming mode: writes progress.json and expert-results-live.json after
    each question so external tools can monitor progress in real time.
    """
    results = []
    total = len(questions)
    eval_start = time.time()

    for i, q in enumerate(questions):
        sector = q.get("sector", "?")
        qid = q.get("id", "?")
        q_start = time.time()

        result = evaluate_single(q, pipeline=pipeline, use_proxy=use_proxy)
        results.append(result)
        _eval_stats["total"] += 1

        q_elapsed = time.time() - q_start
        total_elapsed = time.time() - eval_start
        avg = _result_avg_score(result)

        # ── One-line streaming summary to stdout ──
        if result["error"]:
            print(f"[{i+1}/{total}] {sector} | ERR: {result['error'][:60]} | {q_elapsed:.1f}s",
                  flush=True)
        else:
            scores = result["scores"] or {}
            marker = "+" if (avg and avg >= 3) else "-"
            print(f"[{i+1}/{total}] {sector} | score={avg:.1f} | "
                  f"{q_elapsed:.1f}s | "
                  f"f={scores.get('factual_accuracy',0)} c={scores.get('source_citation',0)} "
                  f"t={scores.get('expert_terminology',0)} k={scores.get('completeness',0)} "
                  f"l={scores.get('language_match',0)} | "
                  f"{scores.get('judge_backend','?')}",
                  flush=True)

        # ── Write progress + live results after EACH question ──
        _write_progress(
            current=i + 1,
            total=total,
            sector=sector,
            last_score=avg,
            errors=_eval_stats["errors"],
            elapsed_s=total_elapsed,
        )
        _write_live_results(results)

        if i < total - 1:
            time.sleep(delay)

    return results


def evaluate_adversarial(use_proxy=True, delay=3):
    """Run adversarial question evaluation.

    Streaming mode: writes progress.json and expert-results-live.json after
    each question so external tools can monitor progress in real time.
    """
    results = []
    total = len(ADVERSARIAL_QUESTIONS)
    eval_start = time.time()

    for i, q in enumerate(ADVERSARIAL_QUESTIONS):
        cat = q["category"]
        qid = q["id"]
        sector = q.get("sectors", ["unknown"])[0] if q.get("sectors") else "unknown"
        q_start = time.time()

        q_eval = {**q, "sector": sector}
        result = evaluate_single(q_eval, pipeline="standard", use_proxy=use_proxy)
        result["adversarial_category"] = cat
        results.append(result)
        _eval_stats["total"] += 1

        q_elapsed = time.time() - q_start
        total_elapsed = time.time() - eval_start
        avg = _result_avg_score(result)

        # ── One-line streaming summary to stdout ──
        if result["error"]:
            print(f"[{i+1}/{total}] ADV/{cat} | ERR: {result['error'][:60]} | {q_elapsed:.1f}s",
                  flush=True)
        else:
            note = ""
            if cat == "out-of-scope":
                note = " (refuse?)"
            elif cat == "ambiguous":
                note = " (clarify?)"
            print(f"[{i+1}/{total}] ADV/{cat} | score={avg:.1f} | "
                  f"{q_elapsed:.1f}s | {result['latency_ms']}ms{note}",
                  flush=True)

        # ── Write progress + live results after EACH question ──
        _write_progress(
            current=i + 1,
            total=total,
            sector=f"adversarial/{cat}",
            last_score=avg,
            errors=_eval_stats["errors"],
            elapsed_s=total_elapsed,
        )
        _write_live_results(results)

        if i < total - 1:
            time.sleep(delay)

    return results


# =========================================================================
#  SECTION 7 — RESULTS AGGREGATION & STORAGE
# =========================================================================

def compute_sector_scores(results):
    """Aggregate scores per sector across 5 criteria."""
    sector_data = defaultdict(lambda: {
        "count": 0, "errors": 0, "total_latency": 0,
        "factual_accuracy": [], "source_citation": [], "expert_terminology": [],
        "completeness": [], "language_match": [],
    })

    for r in results:
        sector = r.get("sector", "unknown")
        sd = sector_data[sector]
        sd["count"] += 1
        sd["total_latency"] += r.get("latency_ms", 0)
        if r.get("error"):
            sd["errors"] += 1
        if r.get("scores"):
            for key in ["factual_accuracy", "source_citation", "expert_terminology",
                        "completeness", "language_match"]:
                val = r["scores"].get(key, 0)
                if val > 0:
                    sd[key].append(val)

    output = {}
    for sector, sd in sector_data.items():
        count = sd["count"]
        scores = {}
        for key in ["factual_accuracy", "source_citation", "expert_terminology",
                    "completeness", "language_match"]:
            vals = sd[key]
            scores[key] = round(sum(vals) / len(vals), 2) if vals else 0
        overall = [v for v in scores.values() if v > 0]
        scores["overall"] = round(sum(overall) / len(overall), 2) if overall else 0

        output[sector] = {
            "count": count,
            "errors": sd["errors"],
            "avg_latency_ms": round(sd["total_latency"] / count) if count else 0,
            "scores": scores,
        }
    return output


def save_results(results, sector_scores, bottlenecks=None):
    """Save all evaluation results to data/eval/."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # expert-results.json — full detail
    expert_output = {
        "timestamp": ts,
        "total_questions": len(results),
        "stats": {
            "total": _eval_stats["total"],
            "judged": _eval_stats["judged"],
            "errors": _eval_stats["errors"],
            "judge_backends": dict(_eval_stats["judge_backends"]),
        },
        "results": results,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(expert_output, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved: {RESULTS_FILE}")

    # sector-scores.json — aggregated
    scores_output = {
        "timestamp": ts,
        "sectors": sector_scores,
    }
    with open(SECTOR_SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores_output, f, indent=2, ensure_ascii=False)
    print(f"  Sector scores saved: {SECTOR_SCORES_FILE}")

    # bottlenecks.json — node timing
    if bottlenecks:
        bn_output = {
            "timestamp": ts,
            "pipelines": bottlenecks,
        }
        with open(BOTTLENECKS_FILE, "w", encoding="utf-8") as f:
            json.dump(bn_output, f, indent=2, ensure_ascii=False)
        print(f"  Bottlenecks saved: {BOTTLENECKS_FILE}")


def print_report(sector_scores):
    """Print a formatted report of sector scores."""
    print("\n" + "=" * 75)
    print("  EXPERT EVALUATION REPORT")
    print("=" * 75)

    criteria_labels = {
        "factual_accuracy": "Factual",
        "source_citation": "Citation",
        "expert_terminology": "Terms",
        "completeness": "Complete",
        "language_match": "Lang",
        "overall": "OVERALL",
    }

    header = f"  {'Sector':<12}"
    for key, label in criteria_labels.items():
        header += f" {label:>9}"
    header += f" {'Latency':>9} {'Errors':>7}"
    print(header)
    print("  " + "-" * 72)

    for sector in ["finance", "btp", "juridique", "industrie"]:
        data = sector_scores.get(sector)
        if not data:
            continue
        scores = data["scores"]
        row = f"  {sector:<12}"
        for key in criteria_labels:
            val = scores.get(key, 0)
            row += f" {val:>8.1f}/5" if key != "overall" else f" {val:>8.1f}/5"
        row += f" {data['avg_latency_ms']:>7}ms"
        row += f" {data['errors']:>7}"
        print(row)

    # Handle adversarial if present
    adv_data = sector_scores.get("unknown")
    if adv_data:
        scores = adv_data["scores"]
        row = f"  {'adversarial':<12}"
        for key in criteria_labels:
            val = scores.get(key, 0)
            row += f" {val:>8.1f}/5" if key != "overall" else f" {val:>8.1f}/5"
        row += f" {adv_data['avg_latency_ms']:>7}ms"
        row += f" {adv_data['errors']:>7}"
        print(row)

    print("=" * 75)


def show_latest_report():
    """Load and display the latest saved report."""
    if not os.path.exists(SECTOR_SCORES_FILE):
        print("  No previous results found. Run an evaluation first.")
        return
    with open(SECTOR_SCORES_FILE, "r") as f:
        data = json.load(f)
    print(f"  Last run: {data.get('timestamp', 'unknown')}")
    print_report(data.get("sectors", {}))

    # Also show bottlenecks if available
    if os.path.exists(BOTTLENECKS_FILE):
        with open(BOTTLENECKS_FILE, "r") as f:
            bn = json.load(f)
        print("\n  NODE BOTTLENECKS:")
        for pipe, info in bn.get("pipelines", {}).items():
            if info:
                print(f"    {pipe}: slowest={info.get('slowest_node','?')} "
                      f"({info.get('slowest_ms',0)}ms) | total={info.get('total_ms',0)}ms")


# =========================================================================
#  MAIN
# =========================================================================

def select_questions(sector=None, sample=None, full=False):
    """Select questions based on filters."""
    questions = []
    sectors = [sector] if sector else ["finance", "btp", "juridique", "industrie"]

    for s in sectors:
        qs = EXPERT_QUESTIONS.get(s, [])
        for q in qs:
            q["sector"] = s  # Ensure sector is set
        questions.extend(qs)

    if not full and sample:
        if sample < len(questions):
            questions = random.sample(questions, sample)

    return questions


def main():
    parser = argparse.ArgumentParser(description="Expert-Grade RAG Evaluation Framework")
    parser.add_argument("--proxy", action="store_true", help="Use RAG proxy (E5+Groq)")
    parser.add_argument("--sector", type=str, default=None,
                        choices=["finance", "btp", "juridique", "industrie"],
                        help="Evaluate single sector only")
    parser.add_argument("--sample", type=int, default=None,
                        help="Random sample N questions")
    parser.add_argument("--full", action="store_true",
                        help="Run all questions (200+)")
    parser.add_argument("--adversarial", action="store_true",
                        help="Run adversarial tests only")
    parser.add_argument("--pipeline", type=str, default="standard",
                        help="Pipeline to test (default: standard)")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between queries (default: 3)")
    parser.add_argument("--report", action="store_true",
                        help="Show latest report without running eval")
    parser.add_argument("--bottlenecks", action="store_true",
                        help="Also run node-level bottleneck analysis")
    parser.add_argument("--allow-local", action="store_true",
                        help="Allow localhost n8n")
    args = parser.parse_args()

    # Report mode
    if args.report:
        show_latest_report()
        return

    # Guard: block VM n8n
    if not USE_PROXY and not args.allow_local:
        if re.search(r'localhost|127\.0\.0\.1|34\.136\.180\.66', N8N_HOST):
            print("FATAL: N8N_HOST points to local/VM. Use --proxy or --allow-local.")
            sys.exit(1)

    # Header
    print("=" * 75)
    print("  EXPERT-GRADE RAG EVALUATION")
    print(f"  Mode: {'RAG PROXY (E5+Groq)' if USE_PROXY else f'n8n webhook ({args.pipeline})'}")
    print(f"  Judge priority: OpenAI > Gemini > Groq")
    judges = []
    if OPENAI_API_KEY:
        judges.append("OpenAI (gpt-4o)")
    if GOOGLE_API_KEY:
        judges.append("Gemini (2.5-pro)")
    if _GROQ_KEYS:
        judges.append(f"Groq ({len(_GROQ_KEYS)} keys)")
    print(f"  Available judges: {', '.join(judges) if judges else 'NONE - scores will be 0'}")

    if args.adversarial:
        print(f"  Mode: ADVERSARIAL ({len(ADVERSARIAL_QUESTIONS)} questions)")
    elif args.full:
        total = sum(len(v) for v in EXPERT_QUESTIONS.values())
        print(f"  Mode: FULL ({total} questions)")
    elif args.sample:
        print(f"  Mode: SAMPLE {args.sample} questions")
        if args.sector:
            print(f"  Sector: {args.sector}")
    print("=" * 75)

    # Select and run questions
    all_results = []

    if args.adversarial:
        results = evaluate_adversarial(use_proxy=USE_PROXY, delay=args.delay)
        all_results.extend(results)
    else:
        questions = select_questions(
            sector=args.sector,
            sample=args.sample,
            full=args.full,
        )
        if not questions:
            print("  No questions selected. Check --sector or question bank.")
            sys.exit(1)
        print(f"  Questions selected: {len(questions)}")
        results = run_evaluation(
            questions,
            pipeline=args.pipeline,
            use_proxy=USE_PROXY,
            delay=args.delay,
        )
        all_results.extend(results)

    # Compute scores
    sector_scores = compute_sector_scores(all_results)

    # Bottleneck analysis (optional)
    bottlenecks = {}
    if args.bottlenecks and not USE_PROXY:
        print("\n  Analyzing pipeline bottlenecks...")
        for pipe in WORKFLOW_IDS:
            bn = analyze_pipeline_bottlenecks(pipe)
            if bn:
                bottlenecks[pipe] = bn
                print(f"    {pipe}: slowest={bn['slowest_node']} ({bn['slowest_ms']}ms)")

    # Print report
    print_report(sector_scores)

    # Print stats
    print(f"\n  Stats: {_eval_stats['total']} tested | {_eval_stats['judged']} judged | "
          f"{_eval_stats['errors']} errors")
    if _eval_stats["judge_backends"]:
        print(f"  Judge backends: {dict(_eval_stats['judge_backends'])}")

    # Save
    save_results(all_results, sector_scores, bottlenecks if bottlenecks else None)


if __name__ == "__main__":
    main()
