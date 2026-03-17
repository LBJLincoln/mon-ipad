#!/usr/bin/env python3
"""
Generate 3,000+ eval questions for the Standard RAG pipeline.

Based on ACTUAL data in E5 Pinecone (77K vectors) across 4 sectors.
Pure template expansion — no LLM needed.

Output: /home/termius/mon-ipad/sectors/eval-datasets/standard-eval-generated.json
"""

import json
import os
import random
import hashlib
from datetime import datetime, timezone
from itertools import product

OUTPUT_PATH = "/home/termius/mon-ipad/sectors/eval-datasets/standard-eval-generated.json"

# ============================================================================
# SECTOR TOPIC KNOWLEDGE (derived from actual ingested data)
# ============================================================================

FINANCE_TOPICS = {
    # From tavily_web.jsonl: IFRS, IAS, accounting standards, banking
    "ifrs": {
        "terms": ["IFRS", "normes IFRS", "International Financial Reporting Standards"],
        "keyword": "IFRS",
        "subtopics": [
            "IFRS 9 financial instruments", "IFRS 16 leases", "IFRS 17 insurance contracts",
            "IFRS 15 revenue recognition", "IFRS 3 business combinations",
            "IAS 1 presentation of financial statements", "IAS 36 impairment",
            "IAS 38 intangible assets", "IASB standard-setting process",
            "fair value measurement under IFRS 13",
        ],
    },
    "banking_regulation": {
        "terms": ["Basel", "réglementation bancaire", "banking regulation"],
        "keyword": "Basel",
        "subtopics": [
            "Basel III capital requirements", "Basel II risk-weighted assets",
            "CET1 ratio", "liquidity coverage ratio LCR",
            "net stable funding ratio NSFR", "stress testing",
            "systemic risk buffers", "countercyclical capital buffer",
            "leverage ratio requirements", "Pillar 1 minimum capital",
        ],
    },
    "financial_instruments": {
        "terms": ["instruments financiers", "financial instruments", "derivatives"],
        "keyword": "instrument",
        "subtopics": [
            "bonds and fixed income securities", "equity derivatives",
            "interest rate swaps", "credit default swaps CDS",
            "options pricing and valuation", "futures contracts",
            "securitization and asset-backed securities", "foreign exchange forwards",
            "structured products", "convertible bonds",
        ],
    },
    "risk_management": {
        "terms": ["gestion des risques", "risk management", "VaR"],
        "keyword": "risque",
        "subtopics": [
            "Value at Risk VaR methodology", "credit risk assessment",
            "market risk management", "operational risk framework",
            "liquidity risk management", "counterparty credit risk",
            "risk appetite framework", "Monte Carlo simulation for risk",
            "expected shortfall ES", "stress testing scenarios",
        ],
    },
    "accounting": {
        "terms": ["comptabilité", "accounting", "GAAP"],
        "keyword": "comptab",
        "subtopics": [
            "consolidation accounting methods", "revenue recognition principles",
            "depreciation and amortization methods", "goodwill impairment testing",
            "deferred tax assets and liabilities", "lease accounting",
            "inventory valuation FIFO LIFO", "earnings per share calculation",
            "cash flow statement preparation", "segment reporting",
        ],
    },
    "insurance": {
        "terms": ["assurance", "insurance", "actuarial"],
        "keyword": "assurance",
        "subtopics": [
            "life insurance products", "property and casualty insurance",
            "reinsurance mechanisms", "actuarial valuation methods",
            "Solvency II framework", "insurance reserves",
            "underwriting process", "claims management",
            "insurance distribution directive IDD", "parametric insurance",
        ],
    },
    "asset_management": {
        "terms": ["gestion d'actifs", "asset management", "portfolio"],
        "keyword": "portfolio",
        "subtopics": [
            "portfolio diversification strategies", "ETF and index fund management",
            "hedge fund strategies", "private equity fund structure",
            "ESG investing criteria", "active vs passive management",
            "alternative investments", "real estate investment trusts REITs",
            "risk-adjusted return metrics Sharpe ratio", "asset allocation models",
        ],
    },
    "stock_market": {
        "terms": ["marché boursier", "stock market", "bourse"],
        "keyword": "bourse",
        "subtopics": [
            "stock exchange listing requirements", "IPO process",
            "market microstructure", "high-frequency trading",
            "market making and liquidity provision", "securities regulation",
            "insider trading rules", "short selling mechanisms",
            "market indices construction", "dividend policy",
        ],
    },
}

BTP_TOPICS = {
    # From tavily_web.jsonl: DTU norms, Eurocodes, building permits, construction
    "dtu": {
        "terms": ["DTU", "Document Technique Unifié"],
        "keyword": "DTU",
        "subtopics": [
            "DTU 31.2 construction bois", "DTU 20.1 murs en maçonnerie",
            "DTU 13.3 dallages", "DTU 43.1 étanchéité toitures",
            "DTU 25.1 enduits intérieurs en plâtre", "DTU 26.1 enduits monocouche",
            "DTU 40.11 couvertures en ardoises", "DTU 60.11 canalisations",
            "DTU 65.16 installation de chaudières", "DTU 36.5 mise en oeuvre fenêtres",
        ],
    },
    "eurocodes": {
        "terms": ["Eurocode", "EN 1990", "EN 1991", "EN 1992"],
        "keyword": "Eurocode",
        "subtopics": [
            "Eurocode 0 basis of structural design EN 1990",
            "Eurocode 1 actions on structures EN 1991",
            "Eurocode 2 design of concrete structures EN 1992",
            "Eurocode 3 design of steel structures EN 1993",
            "Eurocode 5 design of timber structures EN 1995",
            "Eurocode 7 geotechnical design EN 1997",
            "Eurocode 8 seismic design EN 1998",
            "partial safety factors in Eurocodes",
            "national annexes to Eurocodes",
            "load combinations according to Eurocodes",
        ],
    },
    "building_permit": {
        "terms": ["permis de construire", "building permit", "autorisation d'urbanisme"],
        "keyword": "permis",
        "subtopics": [
            "permis de construire application process",
            "déclaration préalable de travaux",
            "PLU plan local d'urbanisme regulations",
            "coefficient d'emprise au sol CES",
            "surface de plancher calculation",
            "recours des tiers contre un permis",
            "conformité des travaux certificat",
            "permis de démolir requirements",
            "architecte obligatoire seuil surface",
            "affichage du permis de construire obligations",
        ],
    },
    "re2020": {
        "terms": ["RE2020", "réglementation environnementale", "RT2012"],
        "keyword": "RE2020",
        "subtopics": [
            "RE2020 carbon impact thresholds",
            "RE2020 energy performance Bbio coefficient",
            "RE2020 summer comfort indicator DH",
            "RT2012 vs RE2020 comparison",
            "lifecycle analysis ACV in RE2020",
            "biosourced materials in RE2020",
            "RE2020 implementation timeline",
            "energy labels DPE and RE2020",
            "low carbon concrete requirements",
            "photovoltaic integration RE2020",
        ],
    },
    "cctp": {
        "terms": ["CCTP", "cahier des clauses techniques particulières"],
        "keyword": "CCTP",
        "subtopics": [
            "CCTP rédaction pour lot gros oeuvre",
            "CCTP spécifications techniques charpente",
            "CCTP lot plomberie sanitaire",
            "CCTP électricité courants forts faibles",
            "CCTP menuiseries extérieures aluminium",
            "CCTP étanchéité toiture terrasse",
            "CCTP peinture revêtements muraux",
            "CCTP VRD voirie et réseaux divers",
            "CCTP chauffage ventilation climatisation CVC",
            "CCTP ascenseur monte-charge",
        ],
    },
    "safety_construction": {
        "terms": ["sécurité chantier", "construction safety", "prévention BTP"],
        "keyword": "sécurité",
        "subtopics": [
            "plan général de coordination PGC",
            "plan particulier de sécurité PPSPS",
            "coordonnateur SPS rôle et missions",
            "échafaudage réglementation vérification",
            "travail en hauteur protection collective",
            "risques amiante désamiantage",
            "risques électriques sur chantier",
            "équipements de protection individuelle EPI BTP",
            "registre journal de chantier obligations",
            "déclaration préalable d'ouverture de chantier",
        ],
    },
    "urban_planning": {
        "terms": ["urbanisme", "urban planning", "PLU"],
        "keyword": "urbanisme",
        "subtopics": [
            "PLU plan local d'urbanisme zonage",
            "SCoT schéma de cohérence territoriale",
            "ZAC zone d'aménagement concerté",
            "servitudes d'utilité publique",
            "droit de préemption urbain",
            "espaces boisés classés EBC",
            "zones inondables PPRi",
            "coefficient de biotope par surface CBS",
            "orientation d'aménagement et de programmation OAP",
            "carte communale et règlement national d'urbanisme RNU",
        ],
    },
    "materials": {
        "terms": ["matériaux construction", "béton", "acier construction"],
        "keyword": "béton",
        "subtopics": [
            "béton armé dosage et résistance",
            "acier de construction nuances et propriétés",
            "bois lamellé-collé utilisation structurelle",
            "isolation thermique matériaux performants",
            "parpaings blocs béton caractéristiques",
            "briques terre cuite propriétés",
            "plâtre et plaques de plâtre BA13",
            "géotextiles et géomembranes",
            "tuiles et ardoises couverture",
            "béton précontraint principes",
        ],
    },
}

JURIDIQUE_TOPICS = {
    # From cold_french_law.jsonl: Code civil, Code du travail, Code de commerce, etc.
    "code_civil": {
        "terms": ["Code civil", "droit civil", "civil code"],
        "keyword": "Code civil",
        "subtopics": [
            "responsabilité civile délictuelle article 1240",
            "droit des contrats réforme 2016",
            "régimes matrimoniaux communauté légale",
            "successions et libéralités",
            "droit de propriété et servitudes",
            "obligations contractuelles formation du contrat",
            "vices du consentement erreur dol violence",
            "responsabilité du fait des choses",
            "prescription extinctive délais",
            "copropriété loi du 10 juillet 1965",
        ],
    },
    "code_travail": {
        "terms": ["Code du travail", "droit du travail", "employment law"],
        "keyword": "travail",
        "subtopics": [
            "contrat de travail CDI CDD",
            "licenciement pour motif personnel",
            "licenciement économique procédure",
            "durée du travail 35 heures",
            "heures supplémentaires majoration",
            "congés payés droits et calcul",
            "représentants du personnel CSE",
            "convention collective application",
            "rupture conventionnelle procédure",
            "harcèlement moral au travail",
        ],
    },
    "code_commerce": {
        "terms": ["Code de commerce", "droit commercial", "commercial law"],
        "keyword": "commerce",
        "subtopics": [
            "bail commercial statut des baux commerciaux",
            "procédures collectives redressement liquidation",
            "fonds de commerce cession et évaluation",
            "société par actions simplifiée SAS",
            "société à responsabilité limitée SARL",
            "registre du commerce et des sociétés RCS",
            "actes de commerce définition et classification",
            "droit de la concurrence pratiques anticoncurrentielles",
            "clause de non-concurrence validité",
            "commissaire aux comptes obligation et missions",
        ],
    },
    "rgpd": {
        "terms": ["RGPD", "GDPR", "protection des données"],
        "keyword": "RGPD",
        "subtopics": [
            "RGPD principes fondamentaux traitement données",
            "consentement conditions de validité RGPD",
            "droit d'accès rectification effacement",
            "délégué à la protection des données DPO",
            "analyse d'impact AIPD obligation",
            "transferts de données hors UE",
            "notification de violation de données",
            "registre des traitements obligation",
            "sanctions CNIL amendes RGPD",
            "sous-traitant responsabilités RGPD",
        ],
    },
    "corporate_law": {
        "terms": ["droit des sociétés", "corporate law", "société"],
        "keyword": "société",
        "subtopics": [
            "création d'une SAS statuts et formalités",
            "assemblée générale ordinaire et extraordinaire",
            "responsabilité du dirigeant social",
            "apports en nature évaluation commissaire",
            "augmentation de capital social procédure",
            "dissolution et liquidation amiable",
            "pacte d'associés clauses essentielles",
            "transformation de forme sociale",
            "holding société mère filiale",
            "droit d'information des associés",
        ],
    },
    "intellectual_property": {
        "terms": ["propriété intellectuelle", "intellectual property", "brevet"],
        "keyword": "propriété intellectuelle",
        "subtopics": [
            "brevet d'invention conditions de brevetabilité",
            "droit d'auteur oeuvres protégées",
            "marque déposée enregistrement INPI",
            "contrefaçon sanctions et recours",
            "licence de brevet clauses",
            "secret des affaires protection",
            "dessins et modèles industriels",
            "propriété intellectuelle logiciel",
            "droit des bases de données",
            "indication géographique protégée",
        ],
    },
    "code_urbanisme": {
        "terms": ["Code de l'urbanisme", "droit de l'urbanisme"],
        "keyword": "urbanisme",
        "subtopics": [
            "certificat d'urbanisme opérationnel",
            "droit de préemption urbain conditions",
            "recours contentieux permis de construire",
            "zone naturelle N du PLU",
            "déclaration préalable travaux champ d'application",
            "taxe d'aménagement calcul et exonérations",
            "plan de prévention des risques naturels PPRn",
            "opération d'aménagement ZAC",
            "lotissement autorisation et cahier des charges",
            "sursis à statuer urbanisme",
        ],
    },
    "contract_law": {
        "terms": ["droit des contrats", "contract law", "contrat"],
        "keyword": "contrat",
        "subtopics": [
            "formation du contrat offre et acceptation",
            "conditions de validité du contrat",
            "clause pénale et clause résolutoire",
            "inexécution contractuelle remèdes",
            "force majeure et imprévision",
            "contrat de vente obligations vendeur",
            "contrat de bail habitation loi ALUR",
            "contrat de prestation de services",
            "cession de contrat conditions",
            "nullité du contrat relative et absolue",
        ],
    },
}

INDUSTRIE_TOPICS = {
    # From tavily_web.jsonl: ISO 9001, quality management, manufacturing
    "iso_9001": {
        "terms": ["ISO 9001", "management qualité", "quality management"],
        "keyword": "ISO 9001",
        "subtopics": [
            "ISO 9001 2015 requirements overview",
            "quality management system QMS implementation",
            "internal audit ISO 9001 process",
            "management review ISO 9001",
            "risk-based thinking ISO 9001",
            "document control and records management",
            "corrective actions and nonconformity",
            "customer satisfaction measurement ISO 9001",
            "ISO 9001 certification process steps",
            "continuous improvement PDCA cycle",
        ],
    },
    "iso_14001": {
        "terms": ["ISO 14001", "management environnemental", "environmental management"],
        "keyword": "ISO 14001",
        "subtopics": [
            "ISO 14001 environmental management system",
            "environmental aspects and impacts identification",
            "legal compliance environmental regulations",
            "environmental objectives and targets",
            "lifecycle perspective ISO 14001",
            "pollution prevention measures",
            "environmental performance indicators",
            "waste management hierarchy",
            "carbon footprint reduction strategies",
            "ISO 14001 and ISO 9001 integration",
        ],
    },
    "maintenance": {
        "terms": ["maintenance industrielle", "industrial maintenance", "GMAO"],
        "keyword": "maintenance",
        "subtopics": [
            "maintenance préventive planification",
            "maintenance corrective vs préventive",
            "maintenance prédictive technologies",
            "GMAO système gestion maintenance assistée",
            "total productive maintenance TPM",
            "fiabilité disponibilité maintenabilité",
            "AMDEC analyse des modes de défaillance",
            "plan de maintenance préventive",
            "indicateurs maintenance MTBF MTTR",
            "maintenance conditionnelle vibrations",
        ],
    },
    "safety_industry": {
        "terms": ["sécurité industrielle", "industrial safety", "ICPE"],
        "keyword": "sécurité",
        "subtopics": [
            "ICPE installations classées protection environnement",
            "directive Seveso III seuils et obligations",
            "document unique d'évaluation des risques DUER",
            "analyse de risques méthode HAZOP",
            "équipements de protection individuelle EPI",
            "plan d'opération interne POI",
            "consignation déconsignation procédure",
            "atmosphères explosives ATEX réglementation",
            "permis de travail et autorisation",
            "accident du travail déclaration et prévention",
        ],
    },
    "supply_chain": {
        "terms": ["chaîne d'approvisionnement", "supply chain", "logistique"],
        "keyword": "supply chain",
        "subtopics": [
            "supply chain management fundamentals",
            "lean manufacturing principles",
            "just-in-time JIT production",
            "kanban system implementation",
            "inventory management EOQ model",
            "supply chain risk management",
            "procurement and sourcing strategies",
            "warehouse management systems WMS",
            "transportation and logistics optimization",
            "supplier quality management",
        ],
    },
    "manufacturing_process": {
        "terms": ["processus de fabrication", "manufacturing process", "production"],
        "keyword": "fabrication",
        "subtopics": [
            "additive manufacturing 3D printing",
            "CNC machining and programming",
            "injection molding process parameters",
            "welding techniques MIG TIG",
            "surface treatment and coating",
            "assembly line design and balancing",
            "quality control statistical process control SPC",
            "six sigma DMAIC methodology",
            "lean production waste elimination",
            "industrial automation and robotics",
        ],
    },
    "iso_45001": {
        "terms": ["ISO 45001", "santé sécurité au travail", "occupational health"],
        "keyword": "ISO 45001",
        "subtopics": [
            "ISO 45001 occupational health and safety",
            "hazard identification and risk assessment",
            "worker participation and consultation",
            "incident investigation root cause analysis",
            "emergency preparedness and response",
            "occupational health surveillance",
            "safety culture and leadership",
            "contractor safety management",
            "ISO 45001 certification audit",
            "performance monitoring leading indicators",
        ],
    },
    "energy_management": {
        "terms": ["ISO 50001", "management énergie", "energy management"],
        "keyword": "énergie",
        "subtopics": [
            "ISO 50001 energy management system",
            "energy audit industrial processes",
            "energy performance indicators EnPI",
            "compressed air system efficiency",
            "heat recovery industrial applications",
            "variable speed drives energy savings",
            "lighting efficiency industrial buildings",
            "energy procurement strategies",
            "renewable energy integration industry",
            "decarbonization roadmap industry",
        ],
    },
}

# ============================================================================
# COMPANIES/ENTITIES from actual datasets
# ============================================================================

FINANCE_COMPANIES = [
    "3M", "AES Corporation", "AMD", "Activision Blizzard", "Adobe", "Amazon",
    "Amcor", "American Express", "American Water Works", "Best Buy", "Block",
    "Boeing", "CVS Health", "Coca-Cola", "Corning", "Costco", "Foot Locker",
    "General Mills", "JPMorgan", "Johnson & Johnson", "Kraft Heinz",
    "Lockheed Martin", "MGM Resorts", "Microsoft", "Netflix", "Nike",
    "Paypal", "PepsiCo", "Pfizer", "Ulta Beauty", "Verizon", "Walmart",
    # French companies from tavily data
    "BNP Paribas", "Société Générale", "AXA", "LVMH", "TotalEnergies",
    "Crédit Agricole", "Amundi", "Natixis", "Hermès", "Danone",
]

BTP_COMPANIES = [
    "Bouygues Construction", "Vinci Construction", "Eiffage", "Saint-Gobain",
    "Colas", "Spie Batignolles", "Fayat", "Demathieu Bard", "Rabot Dutilleul",
    "Legrand", "Schneider Electric", "Lafarge Holcim", "Vicat", "Knauf",
    "Daikin", "Atlantic", "Isover", "Rockwool", "Velux", "Geberit",
]

JURIDIQUE_ENTITIES = [
    "Code civil", "Code du travail", "Code de commerce", "Code de l'urbanisme",
    "Code de l'environnement", "Code de l'énergie", "Code des assurances",
    "Code de la construction et de l'habitation", "Code de la sécurité sociale",
    "Code général des impôts", "Code général des collectivités territoriales",
    "Code rural et de la pêche maritime", "Code forestier", "Code des transports",
    "Code de procédure pénale", "Code du patrimoine", "Code du service national",
    "CNIL", "Conseil constitutionnel", "Cour de cassation", "Conseil d'État",
    "Tribunal de commerce", "Cour d'appel", "INPI", "AMF",
]

INDUSTRIE_COMPANIES = [
    "Airbus", "Michelin", "Renault", "Schneider Electric", "Safran",
    "Thales", "Dassault Systèmes", "Alstom", "Valeo", "Stellantis",
    "ArcelorMittal", "Air Liquide", "Legrand", "Faurecia", "Plastic Omnium",
    "Bureau Veritas", "SGS", "TÜV Rheinland", "DNV", "BSI",
]

# ============================================================================
# FRENCH LAW CODES actually in dataset (cold_french_law.jsonl)
# ============================================================================

FRENCH_LAW_CODES = [
    "Code civil", "Code de commerce", "Code de l'action sociale et des familles",
    "Code de l'environnement", "Code de l'urbanisme", "Code de l'énergie",
    "Code de la construction et de l'habitation", "Code de la sécurité sociale",
    "Code de procédure pénale", "Code des assurances", "Code des transports",
    "Code du patrimoine", "Code du service national", "Code du travail",
    "Code forestier", "Code général de la propriété des personnes publiques",
    "Code général des collectivités territoriales", "Code général des impôts",
    "Code rural et de la pêche maritime",
    "Code des pensions militaires d'invalidité et des victimes de guerre",
]

# ============================================================================
# QUESTION TEMPLATES
# ============================================================================

# Category 1: Domain knowledge (easy)
EN_DOMAIN_TEMPLATES = [
    "What is {subtopic}?",
    "Explain the key principles of {subtopic}.",
    "What are the main requirements of {subtopic}?",
    "How does {subtopic} work in practice?",
    "What is the purpose of {subtopic}?",
    "Describe the fundamentals of {subtopic}.",
    "What are the key components of {subtopic}?",
    "What role does {subtopic} play in the {sector_en} sector?",
]

FR_DOMAIN_TEMPLATES = [
    "Qu'est-ce que {subtopic} ?",
    "Expliquez les principes clés de {subtopic}.",
    "Quelles sont les principales exigences de {subtopic} ?",
    "Comment fonctionne {subtopic} en pratique ?",
    "Quel est l'objectif de {subtopic} ?",
    "Décrivez les fondamentaux de {subtopic}.",
    "Quels sont les éléments essentiels de {subtopic} ?",
    "Quel rôle joue {subtopic} dans le secteur {sector_fr} ?",
]

# Category 2: Entity-based (medium)
EN_ENTITY_TEMPLATES = [
    "What is {entity} known for in the {sector_en} sector?",
    "Describe the role of {entity} in {sector_en}.",
    "What are the key activities of {entity}?",
    "How does {entity} contribute to the {sector_en} industry?",
    "What information is available about {entity}?",
]

FR_ENTITY_TEMPLATES = [
    "Quel est le rôle de {entity} dans le secteur {sector_fr} ?",
    "Décrivez les activités principales de {entity}.",
    "Que fait {entity} dans le domaine {sector_fr} ?",
    "Quelles informations sont disponibles sur {entity} ?",
    "Quelle est l'importance de {entity} pour le secteur {sector_fr} ?",
]

# Category 3: French language domain (mixed)
FR_DEEP_DOMAIN_TEMPLATES = [
    "Quelles sont les obligations liées à {subtopic} ?",
    "Comment appliquer {subtopic} dans un projet concret ?",
    "Quels sont les avantages et inconvénients de {subtopic} ?",
    "Quelle est la réglementation applicable à {subtopic} ?",
    "Quelles sont les étapes pour mettre en oeuvre {subtopic} ?",
    "Quels documents sont nécessaires pour {subtopic} ?",
    "Quelles sont les sanctions en cas de non-respect de {subtopic} ?",
    "Quelle est l'évolution récente de {subtopic} ?",
    "Quels sont les acteurs impliqués dans {subtopic} ?",
    "Comment {subtopic} impacte-t-il les professionnels du secteur ?",
]

# Category 4: Comparative/analytical (hard)
EN_COMPARATIVE_TEMPLATES = [
    "Compare {subtopic1} and {subtopic2}.",
    "What are the key differences between {subtopic1} and {subtopic2}?",
    "How do {subtopic1} and {subtopic2} relate to each other?",
    "What are the advantages of {subtopic1} over {subtopic2}?",
    "In what situations would you choose {subtopic1} over {subtopic2}?",
]

FR_COMPARATIVE_TEMPLATES = [
    "Comparez {subtopic1} et {subtopic2}.",
    "Quelles sont les différences entre {subtopic1} et {subtopic2} ?",
    "Quel est le lien entre {subtopic1} et {subtopic2} ?",
    "Quels sont les avantages de {subtopic1} par rapport à {subtopic2} ?",
    "Dans quels cas choisir {subtopic1} plutôt que {subtopic2} ?",
]

# Entity comparison templates
EN_ENTITY_COMPARE_TEMPLATES = [
    "Compare {entity1} and {entity2} in the {sector_en} sector.",
    "What are the differences between {entity1} and {entity2}?",
    "How do {entity1} and {entity2} compete in {sector_en}?",
]

FR_ENTITY_COMPARE_TEMPLATES = [
    "Comparez {entity1} et {entity2} dans le secteur {sector_fr}.",
    "Quelles sont les différences entre {entity1} et {entity2} ?",
    "Comment {entity1} et {entity2} se positionnent-ils dans le {sector_fr} ?",
]

# Sector-specific deep questions (French, targeting ingested data)
FINANCE_SPECIFIC_FR = [
    ("Quelles sont les normes IFRS applicables aux instruments financiers ?", "IFRS"),
    ("Comment les normes IAS et IFRS se complètent-elles ?", "IAS"),
    ("Quel est le rôle de l'IASB dans la normalisation comptable internationale ?", "IASB"),
    ("Comment fonctionne la consolidation comptable selon les normes IFRS ?", "consolidation"),
    ("Quels sont les principes de juste valeur selon IFRS 13 ?", "juste valeur"),
    ("Comment évaluer le goodwill selon les normes IFRS ?", "goodwill"),
    ("Quelle est la réforme de la comptabilité des contrats de location IFRS 16 ?", "IFRS 16"),
    ("Comment fonctionne le ratio de solvabilité Bâle III ?", "solvabilité"),
    ("Quels sont les exigences de fonds propres CET1 ?", "CET1"),
    ("Comment calculer le ratio de liquidité LCR ?", "LCR"),
    ("Quelles sont les exigences de Bâle III pour les banques systémiques ?", "Bâle"),
    ("Comment fonctionne la titrisation en finance ?", "titrisation"),
    ("Quel est le rôle des agences de notation financière ?", "notation"),
    ("Comment évaluer le risque de crédit d'une contrepartie ?", "crédit"),
    ("Quels sont les instruments dérivés de taux d'intérêt ?", "dérivé"),
    ("Comment fonctionne un swap de taux d'intérêt ?", "swap"),
    ("Quels sont les différents types de fonds d'investissement ?", "fonds"),
    ("Comment fonctionne la gestion indicielle et les ETF ?", "ETF"),
    ("Quels sont les critères ESG en gestion d'actifs ?", "ESG"),
    ("Comment fonctionne l'introduction en bourse IPO ?", "IPO"),
    ("Quelles sont les obligations de transparence financière ?", "transparence"),
    ("Comment fonctionne le régime Solvabilité II pour les assureurs ?", "Solvabilité"),
    ("Quel est le rôle de l'AMF dans la régulation des marchés ?", "AMF"),
    ("Comment fonctionne le marché obligataire ?", "obligat"),
    ("Quels sont les risques opérationnels en banque ?", "opérationnel"),
]

BTP_SPECIFIC_FR = [
    ("Quels sont les DTU applicables à la construction en bois ?", "DTU"),
    ("Comment appliquer le DTU 31.2 pour l'ossature bois ?", "DTU 31.2"),
    ("Quelles sont les exigences du DTU 20.1 pour les murs en maçonnerie ?", "maçonnerie"),
    ("Comment calculer les charges selon l'Eurocode 1 ?", "Eurocode"),
    ("Quelles sont les règles de dimensionnement béton armé Eurocode 2 ?", "béton"),
    ("Comment obtenir un permis de construire en France ?", "permis"),
    ("Quels documents faut-il pour une déclaration préalable de travaux ?", "déclaration"),
    ("Quelles sont les exigences de la RE2020 pour les bâtiments neufs ?", "RE2020"),
    ("Comment rédiger un CCTP pour un lot gros oeuvre ?", "CCTP"),
    ("Quelles sont les obligations du coordonnateur SPS sur un chantier ?", "SPS"),
    ("Comment fonctionne le plan local d'urbanisme PLU ?", "PLU"),
    ("Quels sont les marchés publics de travaux sur le BOAMP ?", "marché"),
    ("Quelles sont les normes parasismiques en France ?", "parasismique"),
    ("Comment calculer la surface de plancher ?", "surface"),
    ("Quels sont les matériaux d'isolation thermique performants ?", "isolation"),
    ("Comment fonctionne l'étanchéité d'une toiture terrasse ?", "étanchéité"),
    ("Quelles sont les règles de sécurité incendie dans les ERP ?", "incendie"),
    ("Comment réaliser un dallage selon le DTU 13.3 ?", "dallage"),
    ("Quels sont les contrôles techniques obligatoires en construction ?", "contrôle"),
    ("Comment fonctionnent les marchés publics de construction ?", "marché public"),
    ("Quelles sont les garanties décennale et biennale ?", "décennale"),
    ("Comment fonctionne le diagnostic de performance énergétique DPE ?", "DPE"),
    ("Quelles sont les exigences de ventilation dans les logements ?", "ventilation"),
    ("Comment réaliser une étude de sol géotechnique ?", "géotechnique"),
    ("Quels sont les types de fondations en construction ?", "fondation"),
]

JURIDIQUE_SPECIFIC_FR = [
    ("Quelles sont les conditions de validité d'un contrat selon le Code civil ?", "contrat"),
    ("Comment fonctionne le licenciement pour motif économique ?", "licenciement"),
    ("Quels sont les droits des salariés en cas de rupture conventionnelle ?", "rupture conventionnelle"),
    ("Quelles sont les obligations du RGPD pour les entreprises ?", "RGPD"),
    ("Comment fonctionne la responsabilité civile délictuelle ?", "responsabilité"),
    ("Quels sont les droits du locataire selon la loi ALUR ?", "locataire"),
    ("Comment créer une SAS en France ?", "SAS"),
    ("Quelles sont les procédures collectives pour une entreprise en difficulté ?", "procédure collective"),
    ("Comment fonctionne le bail commercial en France ?", "bail"),
    ("Quels sont les droits de propriété intellectuelle en France ?", "propriété intellectuelle"),
    ("Comment fonctionne la prescription en droit civil ?", "prescription"),
    ("Quelles sont les obligations du vendeur dans un contrat de vente ?", "vendeur"),
    ("Comment fonctionne le droit de préemption urbain ?", "préemption"),
    ("Quels sont les recours contre un permis de construire ?", "recours"),
    ("Comment fonctionne la CNIL et ses missions ?", "CNIL"),
    ("Quelles sont les obligations des sociétés en matière de comptabilité ?", "comptabilité"),
    ("Comment fonctionne le CSE comité social et économique ?", "CSE"),
    ("Quels sont les droits d'auteur sur les oeuvres numériques ?", "droit d'auteur"),
    ("Comment déposer une marque à l'INPI ?", "marque"),
    ("Quelles sont les sanctions en cas de non-respect du RGPD ?", "sanction"),
    ("Comment fonctionne la médiation en droit du travail ?", "médiation"),
    ("Quels sont les délais de prescription en droit commercial ?", "prescription"),
    ("Comment fonctionne le registre du commerce et des sociétés RCS ?", "RCS"),
    ("Quelles sont les obligations de l'employeur en matière de sécurité ?", "sécurité"),
    ("Comment fonctionne le droit des successions en France ?", "succession"),
]

INDUSTRIE_SPECIFIC_FR = [
    ("Quelles sont les exigences de la norme ISO 9001 version 2015 ?", "ISO 9001"),
    ("Comment mettre en place un système de management qualité ?", "qualité"),
    ("Quels sont les principes de la maintenance préventive ?", "maintenance"),
    ("Comment réaliser une AMDEC analyse des modes de défaillance ?", "AMDEC"),
    ("Quelles sont les obligations ICPE pour les installations classées ?", "ICPE"),
    ("Comment fonctionne la directive Seveso III ?", "Seveso"),
    ("Quels sont les principes du lean manufacturing ?", "lean"),
    ("Comment mettre en oeuvre le kaizen en production ?", "kaizen"),
    ("Quelles sont les exigences de la norme ISO 14001 ?", "ISO 14001"),
    ("Comment réaliser un audit interne ISO 9001 ?", "audit"),
    ("Quels sont les indicateurs de performance maintenance MTBF et MTTR ?", "MTBF"),
    ("Comment fonctionne la fabrication additive impression 3D ?", "impression 3D"),
    ("Quelles sont les normes de sécurité machine directive 2006/42/CE ?", "machine"),
    ("Comment mettre en place le Six Sigma DMAIC ?", "Six Sigma"),
    ("Quels sont les principes de la TPM maintenance productive totale ?", "TPM"),
    ("Comment fonctionne la gestion des stocks en juste-à-temps ?", "juste-à-temps"),
    ("Quelles sont les exigences de la norme ISO 45001 ?", "ISO 45001"),
    ("Comment réaliser une analyse HAZOP ?", "HAZOP"),
    ("Quels sont les principes du contrôle statistique des procédés SPC ?", "SPC"),
    ("Comment fonctionne la certification ISO pour une entreprise ?", "certification"),
    ("Quelles sont les obligations en matière de document unique DUER ?", "DUER"),
    ("Comment optimiser une chaîne d'approvisionnement industrielle ?", "approvisionnement"),
    ("Quels sont les avantages de l'automatisation industrielle ?", "automatisation"),
    ("Comment fonctionne le management de l'énergie ISO 50001 ?", "ISO 50001"),
    ("Quels sont les types de soudure et leurs applications ?", "soudure"),
]

# ============================================================================
# SECTOR METADATA
# ============================================================================

SECTOR_META = {
    "finance": {
        "en": "finance",
        "fr": "finance",
        "topics": FINANCE_TOPICS,
        "entities": FINANCE_COMPANIES,
        "specific_fr": FINANCE_SPECIFIC_FR,
    },
    "btp": {
        "en": "construction (BTP)",
        "fr": "BTP (bâtiment et travaux publics)",
        "topics": BTP_TOPICS,
        "entities": BTP_COMPANIES,
        "specific_fr": BTP_SPECIFIC_FR,
    },
    "juridique": {
        "en": "legal",
        "fr": "juridique",
        "topics": JURIDIQUE_TOPICS,
        "entities": JURIDIQUE_ENTITIES,
        "specific_fr": JURIDIQUE_SPECIFIC_FR,
    },
    "industrie": {
        "en": "industry and manufacturing",
        "fr": "industrie",
        "topics": INDUSTRIE_TOPICS,
        "entities": INDUSTRIE_COMPANIES,
        "specific_fr": INDUSTRIE_SPECIFIC_FR,
    },
}


def make_id(sector, idx):
    return f"std-gen-{sector[:3]}-{idx:04d}"


def generate_all():
    questions = []
    counters = {s: 0 for s in SECTOR_META}

    for sector, meta in SECTOR_META.items():
        sector_en = meta["en"]
        sector_fr = meta["fr"]
        topics = meta["topics"]
        entities = meta["entities"]
        specific_fr = meta["specific_fr"]

        # ------------------------------------------------------------------
        # CAT 1: Domain knowledge (easy) — EN + FR for each subtopic
        # ------------------------------------------------------------------
        for topic_key, topic_data in topics.items():
            keyword = topic_data["keyword"]
            for subtopic in topic_data["subtopics"]:
                # English templates
                for tmpl in EN_DOMAIN_TEMPLATES:
                    counters[sector] += 1
                    questions.append({
                        "id": make_id(sector, counters[sector]),
                        "question": tmpl.format(
                            subtopic=subtopic,
                            sector_en=sector_en,
                            sector_fr=sector_fr,
                        ),
                        "expected_answer": "",
                        "expected_contains": keyword.lower(),
                        "pipeline": "standard",
                        "sector": sector,
                        "dataset_source": "generated",
                        "difficulty": "easy",
                        "category": "domain",
                        "language": "en",
                        "topic": topic_key,
                    })

                # French templates (pick 4 to avoid explosion)
                for tmpl in FR_DOMAIN_TEMPLATES[:4]:
                    counters[sector] += 1
                    questions.append({
                        "id": make_id(sector, counters[sector]),
                        "question": tmpl.format(
                            subtopic=subtopic,
                            sector_en=sector_en,
                            sector_fr=sector_fr,
                        ),
                        "expected_answer": "",
                        "expected_contains": keyword.lower(),
                        "pipeline": "standard",
                        "sector": sector,
                        "dataset_source": "generated",
                        "difficulty": "easy",
                        "category": "french",
                        "language": "fr",
                        "topic": topic_key,
                    })

        # ------------------------------------------------------------------
        # CAT 2: Entity-based (medium)
        # ------------------------------------------------------------------
        for entity in entities:
            # English
            for tmpl in EN_ENTITY_TEMPLATES:
                counters[sector] += 1
                # expected_contains: first word of entity (handles multi-word)
                kw = entity.split()[0].lower()
                if len(kw) < 3:
                    kw = entity.lower()
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl.format(
                        entity=entity,
                        sector_en=sector_en,
                        sector_fr=sector_fr,
                    ),
                    "expected_answer": "",
                    "expected_contains": kw,
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "medium",
                    "category": "entity",
                    "language": "en",
                    "topic": "entity",
                })

            # French
            for tmpl in FR_ENTITY_TEMPLATES:
                counters[sector] += 1
                kw = entity.split()[0].lower()
                if len(kw) < 3:
                    kw = entity.lower()
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl.format(
                        entity=entity,
                        sector_en=sector_en,
                        sector_fr=sector_fr,
                    ),
                    "expected_answer": "",
                    "expected_contains": kw,
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "medium",
                    "category": "entity",
                    "language": "fr",
                    "topic": "entity",
                })

        # ------------------------------------------------------------------
        # CAT 3: French deep domain questions
        # ------------------------------------------------------------------
        for topic_key, topic_data in topics.items():
            keyword = topic_data["keyword"]
            for subtopic in topic_data["subtopics"]:
                # Pick 3 French deep templates per subtopic
                for tmpl in FR_DEEP_DOMAIN_TEMPLATES[:3]:
                    counters[sector] += 1
                    questions.append({
                        "id": make_id(sector, counters[sector]),
                        "question": tmpl.format(subtopic=subtopic),
                        "expected_answer": "",
                        "expected_contains": keyword.lower(),
                        "pipeline": "standard",
                        "sector": sector,
                        "dataset_source": "generated",
                        "difficulty": "medium",
                        "category": "french",
                        "language": "fr",
                        "topic": topic_key,
                    })

        # ------------------------------------------------------------------
        # CAT 3b: Sector-specific curated French questions
        # ------------------------------------------------------------------
        for q_text, kw in specific_fr:
            counters[sector] += 1
            questions.append({
                "id": make_id(sector, counters[sector]),
                "question": q_text,
                "expected_answer": "",
                "expected_contains": kw.lower(),
                "pipeline": "standard",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french",
                "language": "fr",
                "topic": "curated",
            })

        # ------------------------------------------------------------------
        # CAT 4: Comparative/analytical (hard) — across subtopics
        # ------------------------------------------------------------------
        all_subtopics = []
        for topic_key, topic_data in topics.items():
            for st in topic_data["subtopics"]:
                all_subtopics.append((topic_key, st, topic_data["keyword"]))

        # Intra-topic comparisons (same topic, different subtopics)
        for topic_key, topic_data in topics.items():
            subs = topic_data["subtopics"]
            keyword = topic_data["keyword"]
            pairs = list(zip(subs[:-1], subs[1:]))  # adjacent pairs
            for s1, s2 in pairs:
                # English
                tmpl = random.choice(EN_COMPARATIVE_TEMPLATES)
                counters[sector] += 1
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl.format(subtopic1=s1, subtopic2=s2),
                    "expected_answer": "",
                    "expected_contains": keyword.lower(),
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "comparative",
                    "language": "en",
                    "topic": topic_key,
                })
                # French
                tmpl_fr = random.choice(FR_COMPARATIVE_TEMPLATES)
                counters[sector] += 1
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl_fr.format(subtopic1=s1, subtopic2=s2),
                    "expected_answer": "",
                    "expected_contains": keyword.lower(),
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "comparative",
                    "language": "fr",
                    "topic": topic_key,
                })

        # Cross-topic comparisons (pick 15 random pairs from different topics)
        topic_keys = list(topics.keys())
        cross_pairs = []
        for i in range(len(topic_keys)):
            for j in range(i + 1, len(topic_keys)):
                t1 = topics[topic_keys[i]]
                t2 = topics[topic_keys[j]]
                s1 = random.choice(t1["subtopics"])
                s2 = random.choice(t2["subtopics"])
                cross_pairs.append((s1, s2, t1["keyword"], t2["keyword"]))

        for s1, s2, kw1, kw2 in cross_pairs:
            tmpl = random.choice(EN_COMPARATIVE_TEMPLATES)
            counters[sector] += 1
            questions.append({
                "id": make_id(sector, counters[sector]),
                "question": tmpl.format(subtopic1=s1, subtopic2=s2),
                "expected_answer": "",
                "expected_contains": kw1.lower(),
                "pipeline": "standard",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "comparative",
                "language": "en",
                "topic": "cross-topic",
            })
            tmpl_fr = random.choice(FR_COMPARATIVE_TEMPLATES)
            counters[sector] += 1
            questions.append({
                "id": make_id(sector, counters[sector]),
                "question": tmpl_fr.format(subtopic1=s1, subtopic2=s2),
                "expected_answer": "",
                "expected_contains": kw1.lower(),
                "pipeline": "standard",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "comparative",
                "language": "fr",
                "topic": "cross-topic",
            })

        # Entity comparisons (pick 10 pairs)
        ent_pairs = list(zip(entities[:-1], entities[1:]))[:10]
        for e1, e2 in ent_pairs:
            for tmpl in EN_ENTITY_COMPARE_TEMPLATES:
                counters[sector] += 1
                kw = e1.split()[0].lower()
                if len(kw) < 3:
                    kw = e1.lower()
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl.format(
                        entity1=e1, entity2=e2,
                        sector_en=sector_en, sector_fr=sector_fr,
                    ),
                    "expected_answer": "",
                    "expected_contains": kw,
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "comparative",
                    "language": "en",
                    "topic": "entity-compare",
                })
            for tmpl in FR_ENTITY_COMPARE_TEMPLATES:
                counters[sector] += 1
                kw = e1.split()[0].lower()
                if len(kw) < 3:
                    kw = e1.lower()
                questions.append({
                    "id": make_id(sector, counters[sector]),
                    "question": tmpl.format(
                        entity1=e1, entity2=e2,
                        sector_en=sector_en, sector_fr=sector_fr,
                    ),
                    "expected_answer": "",
                    "expected_contains": kw,
                    "pipeline": "standard",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "comparative",
                    "language": "fr",
                    "topic": "entity-compare",
                })

    # ------------------------------------------------------------------
    # ADDITIONAL: French law code questions (juridique bonus from dataset)
    # ------------------------------------------------------------------
    for code_name in FRENCH_LAW_CODES:
        short = code_name.replace("Code ", "").replace("de ", "").replace("l'", "").replace("des ", "").strip()[:30]
        kw = code_name.split()[-1].lower() if len(code_name.split()) > 1 else code_name.lower()
        law_templates = [
            f"Quel est le champ d'application du {code_name} ?",
            f"Quels sont les principaux articles du {code_name} ?",
            f"Comment le {code_name} s'applique-t-il aux professionnels ?",
            f"Quelles sont les réformes récentes du {code_name} ?",
            f"What are the main provisions of the {code_name}?",
        ]
        for tmpl in law_templates:
            counters["juridique"] += 1
            questions.append({
                "id": make_id("juridique", counters["juridique"]),
                "question": tmpl,
                "expected_answer": "",
                "expected_contains": kw,
                "pipeline": "standard",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french" if "Quel" in tmpl else "domain",
                "language": "fr" if "Quel" in tmpl else "en",
                "topic": "french_law_codes",
            })

    return questions, counters


def main():
    random.seed(42)

    print("Generating Standard RAG eval questions...")
    questions, counters = generate_all()

    # Deduplicate by question text
    seen = set()
    unique = []
    for q in questions:
        key = q["question"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(q)

    # Re-index
    sector_idx = {s: 0 for s in SECTOR_META}
    for q in unique:
        s = q["sector"]
        sector_idx[s] += 1
        q["id"] = make_id(s, sector_idx[s])

    # Stats
    total = len(unique)
    by_sector = {}
    by_category = {}
    by_difficulty = {}
    by_language = {}
    for q in unique:
        by_sector[q["sector"]] = by_sector.get(q["sector"], 0) + 1
        by_category[q["category"]] = by_category.get(q["category"], 0) + 1
        by_difficulty[q["difficulty"]] = by_difficulty.get(q["difficulty"], 0) + 1
        lang = q.get("language", "en")
        by_language[lang] = by_language.get(lang, 0) + 1

    output = {
        "metadata": {
            "title": f"Standard RAG Pipeline Eval - Generated ({total} questions)",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "eval/generate-standard-questions.py",
            "total_questions": total,
            "pipeline": "standard",
            "sectors": ["finance", "btp", "juridique", "industrie"],
            "by_sector": by_sector,
            "by_category": by_category,
            "by_difficulty": by_difficulty,
            "by_language": by_language,
            "data_sources": {
                "pinecone": "website-sectors-jina-1024 (77K E5 vectors)",
                "datasets": [
                    "tavily_web (10,920 chunks across 4 sectors)",
                    "financebench (150 records, 32 companies)",
                    "cold_french_law (500 articles, 20 codes)",
                    "btp-boamp-marches (4,927 public tenders)",
                    "ISO 9001/14001/45001 quality standards",
                    "convfinqa, tatqa, finqa, sec_qa",
                    "code_accord, docie, cail2018, french_case_law",
                    "additive_manufacturing, ragbench_emanual",
                ],
            },
            "note": (
                "Questions are designed for SEMANTIC search evaluation. "
                "expected_contains is a lenient keyword that any reasonable "
                "correct answer would include. NOT specific numbers."
            ),
        },
        "questions": unique,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nGenerated {total} unique questions -> {OUTPUT_PATH}")
    print(f"\nBy sector:")
    for s, c in sorted(by_sector.items()):
        print(f"  {s}: {c}")
    print(f"\nBy category:")
    for cat, c in sorted(by_category.items()):
        print(f"  {cat}: {c}")
    print(f"\nBy difficulty:")
    for d, c in sorted(by_difficulty.items()):
        print(f"  {d}: {c}")
    print(f"\nBy language:")
    for lang, c in sorted(by_language.items()):
        print(f"  {lang}: {c}")


if __name__ == "__main__":
    main()
