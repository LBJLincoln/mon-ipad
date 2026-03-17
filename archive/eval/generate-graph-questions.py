#!/usr/bin/env python3
"""
Generate eval questions for the Graph RAG pipeline.

The Graph V3.7 pipeline extracts keywords from queries, searches Neo4j
(Entity.name, SectorDocument.question), and traverses MENTIONS relationships
to find related documents/entities/laws/organizations.

Node types in Neo4j (~71,890 nodes):
  - Entity (34,899): named entities (companies, people, concepts, regulations)
  - SectorDocument (30,143): Q&A pairs with question/answer fields
  - Law (5,232): legal references (articles, codes)
  - Organization (1,616): named organizations

Relationships: MENTIONS (SectorDocument -> Entity/Law/Organization)

Sector distribution: BTP 36K, Finance 17K, Juridique 15K, Industrie 2.7K

Output: sectors/eval-datasets/graph-eval-generated.json
Target: 1,500+ questions
"""

import json
import random
import hashlib
from datetime import datetime, timezone
from collections import Counter
from itertools import combinations

OUTPUT_PATH = "/home/termius/mon-ipad/sectors/eval-datasets/graph-eval-generated.json"

# Seed for reproducibility
random.seed(42)

# =============================================================================
# SECTOR ENTITY DATA
# =============================================================================
# Real entities that would exist in Neo4j based on sector document ingestion.
# Each sector has: entities, organizations, laws, concepts, topics

FINANCE_DATA = {
    "entities": [
        "BNP Paribas", "AXA", "Goldman Sachs", "LVMH", "Apple", "BCE",
        "AMF", "Société Générale", "Crédit Agricole", "JPMorgan Chase",
        "BlackRock", "Total Energies", "Sanofi", "L'Oréal", "Hermès",
        "Kering", "Danone", "Schneider Electric", "Air Liquide", "Capgemini",
        "EssilorLuxottica", "Safran", "Thales", "Pernod Ricard", "Publicis",
        "Bouygues", "Orange", "Engie", "Veolia", "Vinci",
        "Microsoft", "Amazon", "Alphabet", "Tesla", "Meta",
        "Berkshire Hathaway", "Visa", "Mastercard", "HSBC", "UBS",
        "Deutsche Bank", "Barclays", "Morgan Stanley", "Citigroup",
        "Wells Fargo", "Bank of America", "Credit Suisse", "ING",
        "Crédit Mutuel", "BPCE", "La Banque Postale", "Natixis",
        "Euronext", "CME Group", "NASDAQ", "NYSE",
    ],
    "organizations": [
        "Autorité des marchés financiers", "Banque de France",
        "Banque centrale européenne", "Commission européenne",
        "Securities and Exchange Commission", "Federal Reserve",
        "Fonds monétaire international", "Banque mondiale",
        "ACPR", "Haut Conseil de stabilité financière",
        "European Banking Authority", "ESMA",
        "Comité de Bâle", "Financial Stability Board",
        "IOSCO", "BIS", "OCDE",
    ],
    "laws_regulations": [
        "Bâle III", "Bâle IV", "MiFID II", "MiFIR", "IFRS",
        "Solvabilité II", "EMIR", "SFDR", "Taxonomie européenne",
        "Directive AIFM", "Directive UCITS", "Directive CRD",
        "Règlement PRIIPs", "Directive PSD2", "Directive AMLD",
        "Loi Sapin II", "Règlement MAR", "Loi Pacte",
        "Dodd-Frank Act", "Sarbanes-Oxley", "FATCA", "CRS",
        "Directive Transparence", "Règlement Benchmark",
    ],
    "concepts": [
        "ratio de solvabilité", "ratio de liquidité", "fonds propres",
        "spread de crédit", "risque de marché", "risque opérationnel",
        "risque de crédit", "value at risk", "stress test",
        "notation financière", "titrisation", "produits dérivés",
        "obligation verte", "ESG", "investissement responsable",
        "gestion d'actifs", "private equity", "hedge fund",
        "introduction en bourse", "augmentation de capital",
        "dividende", "rachat d'actions", "fusion-acquisition",
        "leverage buyout", "due diligence", "valorisation",
        "flux de trésorerie", "EBITDA", "bénéfice par action",
        "capitalisation boursière", "cours de bourse",
        "rendement obligataire", "taux directeur", "inflation",
        "politique monétaire", "quantitative easing",
    ],
    "topics": [
        "finance durable", "fintech", "blockchain", "cryptomonnaies",
        "banque digitale", "open banking", "néobanque",
        "intelligence artificielle en finance", "trading algorithmique",
        "gestion des risques", "conformité réglementaire",
        "lutte anti-blanchiment", "fraude financière",
        "inclusion financière", "microfinance",
    ],
}

BTP_DATA = {
    "entities": [
        "Bouygues", "Vinci", "Eiffage", "Saint-Gobain", "Lafarge",
        "Holcim", "Legrand", "Nexity", "Icade", "Kaufman & Broad",
        "Spie", "GTM", "Colas", "Eurovia", "Sogea",
        "Rabot Dutilleul", "Demathieu Bard", "Fayat", "NGE",
        "Groupe Charles André", "Engie Solutions",
        "Dassault Systèmes", "Autodesk", "Trimble",
        "Altarea", "Covivio", "Unibail-Rodamco", "Gecina",
        "Maisons du Monde", "Leroy Merlin", "Point P",
    ],
    "organizations": [
        "FFB", "Fédération Française du Bâtiment",
        "CAPEB", "FNTP",
        "Qualibat", "OPPBTP", "CSTB",
        "Agence Qualité Construction", "ADEME",
        "Ministère de la Transition écologique",
        "Cerema", "AFNOR", "CEN",
        "Ordre des architectes", "UNSFA",
        "Bureau Veritas", "Socotec", "Apave",
    ],
    "laws_regulations": [
        "DTU", "Eurocodes", "RE2020", "RT2012",
        "NF DTU 20.1", "NF DTU 31.2", "NF DTU 40.11",
        "NF DTU 43.1", "NF DTU 52.1", "NF DTU 60.1",
        "Loi ELAN", "Loi SRU", "Loi Spinetta",
        "Code de la construction", "Code de l'urbanisme",
        "Décret tertiaire", "Loi Climat et Résilience",
        "Règlement parasismique", "Eurocode 2", "Eurocode 3",
        "Eurocode 5", "Eurocode 7", "Eurocode 8",
        "Norme NF EN 206", "Norme NF EN 1992",
        "CCTP", "CCAG Travaux", "Loi MOP",
    ],
    "concepts": [
        "béton armé", "charpente métallique", "charpente bois",
        "fondations profondes", "fondations superficielles",
        "isolation thermique", "isolation phonique",
        "étanchéité toiture", "étanchéité façade",
        "coefficient thermique", "résistance thermique",
        "performance énergétique", "bilan carbone",
        "diagnostic amiante", "diagnostic plomb",
        "permis de construire", "déclaration préalable",
        "lot gros oeuvre", "lot second oeuvre",
        "VRD", "terrassement", "démolition",
        "BIM", "maquette numérique",
        "DQE", "DPGF", "mémoire technique",
        "réception des travaux", "garantie décennale",
        "garantie biennale", "garantie de parfait achèvement",
        "assurance dommages-ouvrage", "responsabilité décennale",
        "maîtrise d'ouvrage", "maîtrise d'oeuvre",
        "sous-traitance", "coordination SPS",
    ],
    "topics": [
        "construction durable", "bâtiment passif",
        "rénovation énergétique", "déconstruction sélective",
        "économie circulaire BTP", "matériaux biosourcés",
        "béton bas carbone", "construction modulaire",
        "impression 3D construction", "drone BTP",
        "sécurité chantier", "prévention risques BTP",
        "marchés publics BTP", "appel d'offres",
    ],
}

JURIDIQUE_DATA = {
    "entities": [
        "Cour de cassation", "Conseil d'État", "Conseil constitutionnel",
        "Tribunal judiciaire", "Cour d'appel", "Tribunal administratif",
        "Cour administrative d'appel", "Tribunal de commerce",
        "Conseil de prud'hommes", "Tribunal des conflits",
        "Cour européenne des droits de l'homme", "CJUE",
        "Défenseur des droits", "Médiateur de la République",
        "Haute Autorité pour la transparence",
        "Commission nationale consultative des droits de l'homme",
        "Autorité de la concurrence",
    ],
    "organizations": [
        "CNIL", "Conseil national des barreaux",
        "Ordre des avocats", "Chambre des notaires",
        "Ministère de la Justice", "Direction des affaires civiles",
        "Direction des affaires criminelles",
        "Commission européenne", "Parlement européen",
        "Sénat", "Assemblée nationale",
        "Cour des comptes", "Cour pénale internationale",
        "Barreau de Paris", "Barreau de Lyon",
    ],
    "laws_regulations": [
        "Code civil", "Code pénal", "Code du travail",
        "Code de commerce", "Code de procédure civile",
        "Code de procédure pénale", "Code de l'environnement",
        "Code de la consommation", "Code de la propriété intellectuelle",
        "Code général des impôts", "Code de la sécurité sociale",
        "Code de l'urbanisme", "Code de la santé publique",
        "RGPD", "Loi Informatique et Libertés",
        "Convention européenne des droits de l'homme",
        "Charte des droits fondamentaux",
        "Traité sur le fonctionnement de l'UE",
        "Directive 2019/1937", "Règlement eIDAS",
        "Loi Badinter", "Loi Hamon", "Loi Macron",
        "Loi El Khomri", "Loi Sapin II",
        "Article 1103 Code civil", "Article 1240 Code civil",
        "Article L1231-1 Code du travail",
        "Article L121-1 Code de la consommation",
        "Article 9 Code civil", "Article 16 Code civil",
    ],
    "concepts": [
        "responsabilité civile", "responsabilité pénale",
        "responsabilité contractuelle", "responsabilité délictuelle",
        "force majeure", "cas fortuit", "fait du prince",
        "préjudice moral", "préjudice matériel", "préjudice corporel",
        "droit de propriété", "servitude", "usufruit",
        "contrat de travail", "licenciement", "rupture conventionnelle",
        "convention collective", "accord d'entreprise",
        "clause de non-concurrence", "clause pénale",
        "droit au bail", "bail commercial", "bail d'habitation",
        "prescription", "forclusion", "déchéance",
        "action en justice", "voies de recours",
        "droit des sociétés", "statuts", "assemblée générale",
        "protection des données personnelles",
        "droit à l'image", "vie privée", "liberté d'expression",
        "médiation", "arbitrage", "conciliation",
        "procédure collective", "redressement judiciaire",
        "liquidation judiciaire", "sauvegarde",
    ],
    "topics": [
        "droit du numérique", "droit de l'IA",
        "protection du consommateur", "droit de la concurrence",
        "droit fiscal", "droit social",
        "droit de l'environnement", "droit pénal des affaires",
        "droit international privé", "droit européen",
        "compliance", "lanceurs d'alerte",
        "justice prédictive", "legaltech",
    ],
}

INDUSTRIE_DATA = {
    "entities": [
        "Airbus", "Michelin", "Renault", "PSA", "Stellantis",
        "Safran", "Thales", "Dassault Aviation", "Naval Group",
        "Alstom", "Schneider Electric", "Legrand", "ABB",
        "Siemens", "Bosch", "Continental", "Valeo",
        "ArcelorMittal", "Vallourec", "Aperam",
        "Air Liquide", "Arkema", "Solvay",
        "Toyota", "BMW", "Volkswagen",
        "General Electric", "Honeywell", "3M",
        "Caterpillar", "John Deere",
    ],
    "organizations": [
        "AFNOR", "ISO", "CEN", "CETIM",
        "INERIS", "INRS", "CARSAT",
        "Direction générale des entreprises",
        "Ministère de l'Industrie",
        "Alliance Industrie du Futur",
        "Fédération des Industries Mécaniques",
        "UIMM", "Syntec", "GIFAS",
        "Bureau Veritas", "SGS", "TÜV",
    ],
    "laws_regulations": [
        "ISO 9001", "ISO 14001", "ISO 45001", "ISO 27001",
        "ISO 50001", "ISO 13485", "ISO 22000",
        "IATF 16949", "AS 9100", "EN 9100",
        "Directive machines 2006/42/CE", "Directive ATEX",
        "Directive PED", "Directive EMC",
        "Règlement REACH", "Directive RoHS",
        "Marquage CE", "Norme NF",
        "Code du travail partie IV",
        "Décret 2008-244", "Arrêté du 4 octobre 2010",
    ],
    "concepts": [
        "AMDEC", "lean manufacturing", "Six Sigma",
        "kaizen", "5S", "TPM", "SMED",
        "contrôle qualité", "assurance qualité",
        "gestion de production", "MRP", "ERP",
        "supply chain", "logistique industrielle",
        "maintenance préventive", "maintenance prédictive",
        "maintenance corrective", "GMAO",
        "automatisation", "robotique industrielle",
        "industrie 4.0", "usine du futur",
        "jumeau numérique", "IoT industriel",
        "impression 3D industrielle", "fabrication additive",
        "traitement thermique", "traitement de surface",
        "soudage", "usinage", "emboutissage",
        "injection plastique", "fonderie",
        "plan de prévention", "document unique",
        "analyse des risques", "arbre des causes",
    ],
    "topics": [
        "transition énergétique industrie",
        "décarbonation industrielle",
        "économie circulaire", "recyclage industriel",
        "cybersécurité industrielle", "SCADA",
        "performance industrielle", "excellence opérationnelle",
        "formation professionnelle industrie",
        "attractivité métiers industriels",
        "relocalisation industrielle", "réindustrialisation",
    ],
}

# French article numbers for juridique
ARTICLES_CODE_CIVIL = [
    "Article 1er", "Article 2", "Article 6", "Article 9", "Article 16",
    "Article 544", "Article 1100", "Article 1101", "Article 1103",
    "Article 1104", "Article 1112", "Article 1130", "Article 1137",
    "Article 1170", "Article 1195", "Article 1217", "Article 1231-1",
    "Article 1240", "Article 1241", "Article 1242", "Article 1243",
    "Article 1244", "Article 1245", "Article 1302", "Article 1347",
    "Article 1382", "Article 1583", "Article 1601", "Article 1641",
    "Article 1710", "Article 1719", "Article 1792", "Article 1875",
    "Article 2224",
]

ARTICLES_CODE_TRAVAIL = [
    "Article L1111-1", "Article L1221-1", "Article L1231-1",
    "Article L1232-1", "Article L1233-3", "Article L1234-1",
    "Article L1234-9", "Article L1237-11", "Article L1243-1",
    "Article L2261-1", "Article L3121-27", "Article L3141-1",
    "Article L4121-1", "Article L4121-2",
    "Article L1152-1", "Article L1153-1",
    "Article L2312-1", "Article L2314-1",
]

ARTICLES_CODE_COMMERCE = [
    "Article L110-1", "Article L121-1", "Article L123-1",
    "Article L210-1", "Article L221-1", "Article L223-1",
    "Article L225-1", "Article L225-35", "Article L225-51",
    "Article L225-100", "Article L226-1", "Article L227-1",
    "Article L611-1", "Article L620-1", "Article L631-1",
    "Article L640-1",
]


# =============================================================================
# QUESTION TEMPLATES
# =============================================================================

# --- Category 1: Entity Lookup (easy) ---

EN_ENTITY_LOOKUP = [
    "What is {entity}?",
    "Tell me about {entity}.",
    "Who is {entity}?",
    "What does {entity} do?",
    "Describe {entity}.",
    "What role does {entity} play in {sector_en}?",
    "Give me information about {entity}.",
    "What is {entity} known for?",
]

FR_ENTITY_LOOKUP = [
    "Qu'est-ce que {entity} ?",
    "Présentez {entity}.",
    "Qui est {entity} ?",
    "Que fait {entity} ?",
    "Décrivez {entity}.",
    "Quel est le rôle de {entity} dans le secteur {sector_fr} ?",
    "Donnez-moi des informations sur {entity}.",
    "Parlez-moi de {entity}.",
]

EN_ORG_LOOKUP = [
    "What is {org}?",
    "What is the role of {org}?",
    "Tell me about {org}.",
    "What does {org} do?",
    "What is the mission of {org}?",
    "Describe the organization {org}.",
]

FR_ORG_LOOKUP = [
    "Qu'est-ce que {org} ?",
    "Quel est le rôle de {org} ?",
    "Parlez-moi de {org}.",
    "Que fait {org} ?",
    "Quelle est la mission de {org} ?",
    "Décrivez l'organisation {org}.",
]

# --- Category 2: Relationship questions (medium) ---

EN_RELATIONSHIP_DOC = [
    "What documents mention {entity}?",
    "What information is available about {entity}?",
    "Find documents related to {entity}.",
    "What do the documents say about {entity}?",
    "Summarize what is known about {entity} from the documents.",
]

FR_RELATIONSHIP_DOC = [
    "Quels documents mentionnent {entity} ?",
    "Quelles informations sont disponibles sur {entity} ?",
    "Trouvez les documents liés à {entity}.",
    "Que disent les documents sur {entity} ?",
    "Résumez ce qui est connu sur {entity} dans les documents.",
]

EN_RELATIONSHIP_LAW = [
    "What laws relate to {topic}?",
    "What regulations apply to {topic}?",
    "What are the legal requirements for {topic}?",
    "Which rules govern {topic}?",
    "What is the regulatory framework for {topic}?",
]

FR_RELATIONSHIP_LAW = [
    "Quelles lois concernent {topic} ?",
    "Quelle réglementation s'applique à {topic} ?",
    "Quelles sont les exigences légales pour {topic} ?",
    "Quelles règles encadrent {topic} ?",
    "Quel est le cadre réglementaire de {topic} ?",
]

EN_RELATIONSHIP_ORG = [
    "Which organizations are involved in {topic}?",
    "What organizations regulate {topic}?",
    "Who are the key players in {topic}?",
    "Which bodies oversee {topic}?",
    "What institutions deal with {topic}?",
]

FR_RELATIONSHIP_ORG = [
    "Quelles organisations sont impliquées dans {topic} ?",
    "Quels organismes régulent {topic} ?",
    "Quels sont les acteurs clés de {topic} ?",
    "Quels organismes supervisent {topic} ?",
    "Quelles institutions traitent de {topic} ?",
]

EN_ENTITY_SECTOR_ROLE = [
    "What is the role of {entity} in {sector_en}?",
    "How does {entity} contribute to {sector_en}?",
    "What impact does {entity} have on the {sector_en} sector?",
    "How is {entity} relevant to {sector_en}?",
]

FR_ENTITY_SECTOR_ROLE = [
    "Quel est le rôle de {entity} dans le secteur {sector_fr} ?",
    "Comment {entity} contribue-t-il au secteur {sector_fr} ?",
    "Quel impact a {entity} sur le secteur {sector_fr} ?",
    "En quoi {entity} est-il pertinent pour {sector_fr} ?",
]

EN_CONCEPT_EXPLAIN = [
    "What is {concept}?",
    "Explain {concept}.",
    "Define {concept} in the context of {sector_en}.",
    "How does {concept} work?",
    "What are the key aspects of {concept}?",
]

FR_CONCEPT_EXPLAIN = [
    "Qu'est-ce que {concept} ?",
    "Expliquez {concept}.",
    "Définissez {concept} dans le contexte de {sector_fr}.",
    "Comment fonctionne {concept} ?",
    "Quels sont les aspects clés de {concept} ?",
]

# --- Category 3: French legal questions ---

FR_ARTICLE_QUESTIONS = [
    "Que dit l'{article} du {code} ?",
    "Quel est le contenu de l'{article} du {code} ?",
    "Que prévoit l'{article} du {code} ?",
    "Expliquez l'{article} du {code}.",
    "Quelles sont les dispositions de l'{article} du {code} ?",
]

FR_LEGAL_TOPIC = [
    "Quelles sont les obligations en matière de {topic} ?",
    "Que dit la loi sur {topic} ?",
    "Quel est le régime juridique de {topic} ?",
    "Quelles sont les règles applicables à {topic} ?",
    "Comment le droit encadre-t-il {topic} ?",
    "Quelles sont les sanctions en cas de non-respect de {topic} ?",
]

FR_LEGAL_REGULATION = [
    "Que prévoit {regulation} ?",
    "Quel est l'objet de {regulation} ?",
    "Quelles obligations impose {regulation} ?",
    "Qui est concerné par {regulation} ?",
    "Comment s'applique {regulation} ?",
    "Quelles sont les principales dispositions de {regulation} ?",
]

FR_JURISPRUDENCE = [
    "Quelle est la jurisprudence de {court} sur {topic} ?",
    "Comment {court} se prononce-t-il sur {topic} ?",
    "Quels sont les arrêts de {court} concernant {topic} ?",
    "Quelle est la position de {court} sur {topic} ?",
]

# --- Category 4: Cross-entity questions (hard) ---

EN_CROSS_ENTITY = [
    "What is the relationship between {entityA} and {entityB}?",
    "How are {entityA} and {entityB} connected?",
    "Compare {entityA} and {entityB}.",
    "What do {entityA} and {entityB} have in common?",
    "How do {entityA} and {entityB} interact?",
]

FR_CROSS_ENTITY = [
    "Quelle est la relation entre {entityA} et {entityB} ?",
    "Comment {entityA} et {entityB} sont-ils liés ?",
    "Comparez {entityA} et {entityB}.",
    "Que partagent {entityA} et {entityB} ?",
    "Comment interagissent {entityA} et {entityB} ?",
]

EN_MULTI_ENTITY_TOPIC = [
    "What entities are related to {topic} in {sector_en}?",
    "What companies and organizations are involved in {topic}?",
    "Map the key players related to {topic}.",
    "Who are the stakeholders in {topic}?",
]

FR_MULTI_ENTITY_TOPIC = [
    "Quelles entités sont liées à {topic} dans le secteur {sector_fr} ?",
    "Quelles entreprises et organisations sont impliquées dans {topic} ?",
    "Quels sont les acteurs clés liés à {topic} ?",
    "Quelles sont les parties prenantes de {topic} ?",
]

EN_LAW_ENTITY_LINK = [
    "How does {regulation} affect {entity}?",
    "What is the impact of {regulation} on {entity}?",
    "How must {entity} comply with {regulation}?",
    "What obligations does {regulation} impose on {entity}?",
]

FR_LAW_ENTITY_LINK = [
    "Comment {regulation} affecte-t-il {entity} ?",
    "Quel est l'impact de {regulation} sur {entity} ?",
    "Comment {entity} doit-il se conformer à {regulation} ?",
    "Quelles obligations {regulation} impose-t-il à {entity} ?",
]


# =============================================================================
# SECTOR METADATA
# =============================================================================

SECTOR_LABELS = {
    "finance": {"en": "finance", "fr": "finance"},
    "btp": {"en": "construction", "fr": "BTP"},
    "juridique": {"en": "law", "fr": "juridique"},
    "industrie": {"en": "industry", "fr": "industrie"},
}

ALL_SECTOR_DATA = {
    "finance": FINANCE_DATA,
    "btp": BTP_DATA,
    "juridique": JURIDIQUE_DATA,
    "industrie": INDUSTRIE_DATA,
}


# =============================================================================
# QUESTION GENERATOR
# =============================================================================

def generate_questions():
    questions = []
    qid = 0

    for sector, data in ALL_SECTOR_DATA.items():
        sector_en = SECTOR_LABELS[sector]["en"]
        sector_fr = SECTOR_LABELS[sector]["fr"]
        entities = data["entities"]
        organizations = data["organizations"]
        laws = data["laws_regulations"]
        concepts = data["concepts"]
        topics = data["topics"]

        # =================================================================
        # CATEGORY 1: Entity Lookup (easy)
        # =================================================================

        # Entity lookups — English
        for entity in entities:
            for tmpl in EN_ENTITY_LOOKUP:
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(entity=entity, sector_en=sector_en),
                    "expected_answer": "",
                    "expected_contains": entity,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "easy",
                    "category": "entity_lookup",
                })

        # Entity lookups — French
        for entity in entities:
            for tmpl in FR_ENTITY_LOOKUP:
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(entity=entity, sector_fr=sector_fr),
                    "expected_answer": "",
                    "expected_contains": entity,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "easy",
                    "category": "entity_lookup",
                })

        # Organization lookups — English
        for org in organizations:
            for tmpl in EN_ORG_LOOKUP:
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(org=org),
                    "expected_answer": "",
                    "expected_contains": org,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "easy",
                    "category": "entity_lookup",
                })

        # Organization lookups — French
        for org in organizations:
            for tmpl in FR_ORG_LOOKUP:
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(org=org),
                    "expected_answer": "",
                    "expected_contains": org,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "easy",
                    "category": "entity_lookup",
                })

        # =================================================================
        # CATEGORY 2: Relationship questions (medium)
        # =================================================================

        # Documents mentioning entity
        for entity in entities:
            tmpl = random.choice(EN_RELATIONSHIP_DOC)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entity=entity),
                "expected_answer": "",
                "expected_contains": entity,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })
            tmpl = random.choice(FR_RELATIONSHIP_DOC)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entity=entity),
                "expected_answer": "",
                "expected_contains": entity,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

        # Laws relating to topic
        for topic in topics + concepts[:10]:
            tmpl = random.choice(EN_RELATIONSHIP_LAW)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })
            tmpl = random.choice(FR_RELATIONSHIP_LAW)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

        # Organizations involved in topic
        for topic in topics:
            tmpl = random.choice(EN_RELATIONSHIP_ORG)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })
            tmpl = random.choice(FR_RELATIONSHIP_ORG)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

        # Entity role in sector
        for entity in entities[:20]:
            tmpl = random.choice(EN_ENTITY_SECTOR_ROLE)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entity=entity, sector_en=sector_en),
                "expected_answer": "",
                "expected_contains": entity,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })
            tmpl = random.choice(FR_ENTITY_SECTOR_ROLE)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entity=entity, sector_fr=sector_fr),
                "expected_answer": "",
                "expected_contains": entity,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

        # Concept explanation
        for concept in concepts:
            tmpl = random.choice(EN_CONCEPT_EXPLAIN)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(concept=concept, sector_en=sector_en),
                "expected_answer": "",
                "expected_contains": concept,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })
            tmpl = random.choice(FR_CONCEPT_EXPLAIN)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(concept=concept, sector_fr=sector_fr),
                "expected_answer": "",
                "expected_contains": concept,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

        # Regulation questions (all sectors)
        for regulation in laws:
            tmpl = random.choice(FR_LEGAL_REGULATION)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(regulation=regulation),
                "expected_answer": "",
                "expected_contains": regulation,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "relationship",
            })

    # =================================================================
    # CATEGORY 3: French legal questions (juridique-specific)
    # =================================================================

    # Code civil articles
    for article in ARTICLES_CODE_CIVIL:
        for tmpl in FR_ARTICLE_QUESTIONS:
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(article=article, code="Code civil"),
                "expected_answer": "",
                "expected_contains": article.split()[-1],  # article number
                "pipeline": "graph",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french_legal",
            })

    # Code du travail articles
    for article in ARTICLES_CODE_TRAVAIL:
        for tmpl in FR_ARTICLE_QUESTIONS:
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(article=article, code="Code du travail"),
                "expected_answer": "",
                "expected_contains": article.split()[-1],
                "pipeline": "graph",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french_legal",
            })

    # Code de commerce articles
    for article in ARTICLES_CODE_COMMERCE:
        for tmpl in FR_ARTICLE_QUESTIONS:
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(article=article, code="Code de commerce"),
                "expected_answer": "",
                "expected_contains": article.split()[-1],
                "pipeline": "graph",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french_legal",
            })

    # Legal topics (juridique-specific deeper questions)
    juridique_legal_topics = [
        "responsabilité civile", "responsabilité pénale",
        "responsabilité contractuelle", "responsabilité délictuelle",
        "licenciement abusif", "harcèlement moral", "harcèlement sexuel",
        "protection des données personnelles", "droit à l'oubli",
        "contrat de travail", "rupture conventionnelle",
        "clause de non-concurrence", "clause pénale",
        "bail commercial", "bail d'habitation",
        "droit de propriété", "servitude", "usufruit",
        "prescription acquisitive", "prescription extinctive",
        "force majeure", "imprévision", "vice du consentement",
        "dol", "erreur", "violence",
        "nullité du contrat", "résolution du contrat",
        "exécution forcée", "dommages et intérêts",
        "abus de droit", "concurrence déloyale",
        "procédure collective", "redressement judiciaire",
        "liquidation judiciaire", "sauvegarde",
        "CSE", "comité social et économique",
        "convention collective", "accord d'entreprise",
        "temps de travail", "heures supplémentaires",
        "congés payés", "congé maternité",
        "discrimination", "égalité professionnelle",
        "lanceurs d'alerte", "devoir de vigilance",
        "médiation", "arbitrage", "conciliation",
        "action de groupe", "class action",
    ]

    for topic in juridique_legal_topics:
        for tmpl in FR_LEGAL_TOPIC:
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "medium",
                "category": "french_legal",
            })

    # Jurisprudence questions
    courts = [
        "la Cour de cassation", "le Conseil d'État",
        "le Conseil constitutionnel", "la CJUE",
        "la Cour européenne des droits de l'homme",
    ]
    jurisprudence_topics = [
        "la responsabilité civile", "le licenciement",
        "le droit de propriété", "la vie privée",
        "la liberté d'expression", "le harcèlement moral",
        "la clause de non-concurrence", "le bail commercial",
        "les droits fondamentaux", "la protection des données",
        "le droit du travail", "la concurrence déloyale",
        "les procédures collectives", "la responsabilité pénale",
    ]

    for court in courts:
        for topic in jurisprudence_topics:
            tmpl = random.choice(FR_JURISPRUDENCE)
            qid += 1
            # Extract the court name for expected_contains
            court_name = court.replace("la ", "").replace("le ", "").replace("l'", "")
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(court=court, topic=topic),
                "expected_answer": "",
                "expected_contains": court_name,
                "pipeline": "graph",
                "sector": "juridique",
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "french_legal",
            })

    # =================================================================
    # CATEGORY 4: Cross-entity questions (hard)
    # =================================================================

    for sector, data in ALL_SECTOR_DATA.items():
        sector_en = SECTOR_LABELS[sector]["en"]
        sector_fr = SECTOR_LABELS[sector]["fr"]
        entities = data["entities"]
        organizations = data["organizations"]
        laws = data["laws_regulations"]
        concepts = data["concepts"]
        topics = data["topics"]

        # Cross-entity pairs (limit to keep manageable)
        entity_pairs = list(combinations(entities[:20], 2))
        random.shuffle(entity_pairs)
        for entityA, entityB in entity_pairs[:30]:
            tmpl = random.choice(EN_CROSS_ENTITY)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entityA=entityA, entityB=entityB),
                "expected_answer": "",
                "expected_contains": entityA,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "cross_entity",
            })
            tmpl = random.choice(FR_CROSS_ENTITY)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(entityA=entityA, entityB=entityB),
                "expected_answer": "",
                "expected_contains": entityB,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "cross_entity",
            })

        # Entity + Organization pairs
        for entity in entities[:15]:
            for org in organizations[:5]:
                tmpl = random.choice(EN_CROSS_ENTITY)
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(entityA=entity, entityB=org),
                    "expected_answer": "",
                    "expected_contains": entity,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "cross_entity",
                })

        # Multi-entity topic
        for topic in topics:
            tmpl = random.choice(EN_MULTI_ENTITY_TOPIC)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic, sector_en=sector_en),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "cross_entity",
            })
            tmpl = random.choice(FR_MULTI_ENTITY_TOPIC)
            qid += 1
            questions.append({
                "id": f"graph-gen-{qid:05d}",
                "question": tmpl.format(topic=topic, sector_fr=sector_fr),
                "expected_answer": "",
                "expected_contains": topic,
                "pipeline": "graph",
                "sector": sector,
                "dataset_source": "generated",
                "difficulty": "hard",
                "category": "cross_entity",
            })

        # Law <-> Entity link questions
        for regulation in laws[:10]:
            for entity in entities[:8]:
                tmpl = random.choice(EN_LAW_ENTITY_LINK)
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(regulation=regulation, entity=entity),
                    "expected_answer": "",
                    "expected_contains": entity,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "cross_entity",
                })
                tmpl = random.choice(FR_LAW_ENTITY_LINK)
                qid += 1
                questions.append({
                    "id": f"graph-gen-{qid:05d}",
                    "question": tmpl.format(regulation=regulation, entity=entity),
                    "expected_answer": "",
                    "expected_contains": regulation,
                    "pipeline": "graph",
                    "sector": sector,
                    "dataset_source": "generated",
                    "difficulty": "hard",
                    "category": "cross_entity",
                })

    return questions


def deduplicate(questions):
    """Remove exact duplicate questions (same question text)."""
    seen = set()
    unique = []
    for q in questions:
        key = q["question"]
        if key not in seen:
            seen.add(key)
            unique.append(q)
    return unique


def print_stats(questions):
    """Print distribution statistics."""
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

    print(f"\nSample questions:")
    for cat in sorted(cats.keys()):
        samples = [q for q in questions if q["category"] == cat][:2]
        for s in samples:
            print(f"  [{cat}/{s['difficulty']}/{s['sector']}] {s['question']}")


def main():
    print("=" * 60)
    print("Graph Pipeline Eval Question Generator")
    print("=" * 60)

    questions = generate_questions()
    print(f"Generated {len(questions)} raw questions")

    questions = deduplicate(questions)
    print(f"After dedup: {len(questions)} unique questions")

    # Re-number IDs sequentially after dedup
    for i, q in enumerate(questions, 1):
        q["id"] = f"graph-gen-{i:05d}"

    print(f"\n{'=' * 60}")
    print(f"TOTAL QUESTIONS GENERATED: {len(questions)}")
    print(f"{'=' * 60}")

    if len(questions) < 1500:
        print(f"WARNING: Only {len(questions)} questions (target: 1500+)")
    else:
        print(f"TARGET MET: {len(questions)} >= 1500")

    print_stats(questions)

    output = {
        "metadata": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "total": len(questions),
            "source": "neo4j_entity_knowledge",
            "generator": "eval/generate-graph-questions.py",
            "description": "Eval questions for Graph RAG V3.7 pipeline testing entity lookup, relationships, French legal, and cross-entity queries",
            "neo4j_stats": {
                "total_nodes": 71890,
                "entity_nodes": 34899,
                "sector_document_nodes": 30143,
                "law_nodes": 5232,
                "organization_nodes": 1616,
            },
            "sector_distribution_neo4j": {
                "btp": "36K nodes",
                "finance": "17K nodes",
                "juridique": "15K nodes",
                "industrie": "2.7K nodes",
            },
        },
        "questions": questions,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    size_mb = len(json.dumps(output, ensure_ascii=False)) / 1024 / 1024
    print(f"\nWritten to: {OUTPUT_PATH}")
    print(f"File size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
