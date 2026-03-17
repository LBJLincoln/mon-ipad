# Sector Datasets & Document Types — Multi-RAG SOTA 2026

> Last updated: 2026-02-19T15:30:00+01:00

> Reference documentaire pour le Multi-RAG Orchestrator ciblant les ETI et Grands Groupes francais.
> 4 secteurs verticaux, 50 datasets identifies, ~2.6M questions disponibles.
> **7,609 items telecharges** en Session 25 (19 fev 2026) — voir Section 8.

### Datasets telecharges (Session 25 — 19 fev 2026)
| Secteur | Fichiers HF | Items | Taille |
|---------|-------------|-------|--------|
| Finance | 6 (financebench, convfinqa, tatqa, sec_qa, tatqa_ragbench, finqa_ragbench) | 2,250 | 6.5 MB |
| Juridique | 5 (french_case_law_juri, french_case_law_cetat, cold_french_law, cail2018, hotpotqa_ragbench) | 2,500 | 13 MB |
| BTP | 4 (code_accord_entities, code_accord_relations, ragbench_techqa, docie) | 1,844 | 5.7 MB |
| Industrie | 3 (manufacturing_qa, ragbench_emanual, additive_manufacturing) | 1,015 | 1.6 MB |
| **Total** | **18 fichiers** | **7,609** | **~27 MB** |

Script : `scripts/download-sectors.py` (6 IDs HF corriges — FIX-23)

---

## 1. Vue d'ensemble

### 1.1 Perimetre

| Dimension | Valeur |
|-----------|--------|
| **Secteurs cibles** | BTP/Construction, Industrie/Manufacturing, Finance, Juridique |
| **Cible entreprises** | ETI (250-4999 salaries) et Grands Groupes francais (5000+) |
| **Datasets identifies** | 50 (10 techniques/secteur + 10 generaux cross-secteur) |
| **Questions disponibles** | ~2.6M (total brut avant deduplication) |
| **Echantillon realiste** | ~324K (apres deduplication et filtrage qualite) |
| **Langues** | Francais (prioritaire), Anglais (datasets techniques), Multilingue (EU) |
| **Types de documents** | ~1000 types uniques (250 par secteur) |

### 1.2 Objectif

Constituer une base de connaissance exhaustive pour un chatbot RAG multi-pipeline capable de :

1. **Comprendre** les documents metiers specifiques a chaque secteur
2. **Repondre** avec precision aux questions techniques, reglementaires et contractuelles
3. **Raisonner** sur des documents complexes (multi-hop, calculs, tableaux)
4. **Couvrir** le spectre complet des besoins documentaires des ETI/Grands Groupes francais

### 1.3 Repartition par pipeline

| Pipeline | Secteurs principaux | Type de raisonnement |
|----------|-------------------|---------------------|
| **Standard** (Pinecone) | Tous | Recherche semantique dense |
| **Graph** (Neo4j + Supabase) | Juridique, BTP | Relations entre entites, hierarchies |
| **Quantitative** (Supabase) | Finance, Industrie | Calculs, tableaux, donnees numeriques |
| **Orchestrator** (Meta) | Tous | Routage intelligent + multi-hop |

---

## 2. Types de Documents par Secteur (~250 par secteur, 1000 total)

### 2.1 BTP & Construction (250 types)

Le secteur BTP est le plus riche en documents normatifs et contractuels. Les ETI de construction (Eiffage, Bouygues, Vinci, Spie Batignolles) manipulent quotidiennement des centaines de types documentaires.

#### Categories principales

| # | Categorie | Nb types | Exemples cles |
|---|-----------|----------|---------------|
| 1 | Pieces marches publics/prives | 35 | DCE, RC, AE, AAPC, acte d'engagement |
| 2 | Documents techniques/normatifs | 30 | DTU, Eurocodes, NF EN, avis techniques |
| 3 | Plans et dessins | 25 | Plans archi, plans execution, plans de coffrage |
| 4 | Securite chantier | 20 | PPSPS, DIUO, PGC, registre journal |
| 5 | RE2020 / Environnement | 20 | ACV, etude thermique, FDES, PEB |
| 6 | Assurances / Garanties | 15 | DO, RC decennale, GPA, attestation |
| 7 | Documents contractuels | 25 | Marche, avenant, ordre de service, mise en demeure |
| 8 | CCTP / CCAP | 15 | CCTP lots, CCAP, CCAG, DQE |
| 9 | PV de reception | 15 | PV reception, PV reserve, PV levee reserve |
| 10 | Rapports d'expertise | 25 | Rapport geotechnique, diagnostic amiante, DPE |
| 11 | Documents urbanisme | 25 | PLU, permis construire, declaration prealable, CERFA |

#### 50 types representatifs detailles

| # | Type de document | Categorie | Format | Volume typique |
|---|-----------------|-----------|--------|----------------|
| 1 | Acte d'engagement (AE) | Marches publics | PDF | 5-15 pages |
| 2 | Reglement de consultation (RC) | Marches publics | PDF | 10-30 pages |
| 3 | Avis d'Appel Public a la Concurrence (AAPC) | Marches publics | PDF/HTML | 1-3 pages |
| 4 | Dossier de Consultation des Entreprises (DCE) | Marches publics | ZIP/PDF | 50-500 pages |
| 5 | Bordereau de Prix Unitaires (BPU) | Marches publics | XLS/PDF | 10-100 pages |
| 6 | Detail Quantitatif Estimatif (DQE) | Marches publics | XLS/PDF | 20-200 pages |
| 7 | Cahier des Clauses Techniques Particulieres (CCTP) | CCTP/CCAP | PDF | 30-200 pages |
| 8 | Cahier des Clauses Administratives Particulieres (CCAP) | CCTP/CCAP | PDF | 15-50 pages |
| 9 | CCAG Travaux | CCTP/CCAP | PDF | 40 pages (fixe) |
| 10 | Memoire technique | Marches publics | PDF | 20-100 pages |
| 11 | Planning previsionnel Gantt | Documents techniques | PDF/MPP | 1-10 pages |
| 12 | DTU (Documents Techniques Unifies) | Normatif | PDF | 20-100 pages |
| 13 | Eurocodes (EC0 a EC9) | Normatif | PDF | 50-500 pages |
| 14 | Normes NF EN (beton, acier, bois) | Normatif | PDF | 30-300 pages |
| 15 | Avis Technique CSTB | Normatif | PDF | 10-30 pages |
| 16 | ATEx (Appreciation Technique d'Experimentation) | Normatif | PDF | 5-15 pages |
| 17 | Plan architecte (permis) | Plans | DWG/PDF | 1-5 planches |
| 18 | Plan d'execution beton arme | Plans | DWG/PDF | 10-50 planches |
| 19 | Plan de coffrage | Plans | DWG/PDF | 5-30 planches |
| 20 | Plan de ferraillage | Plans | DWG/PDF | 5-30 planches |
| 21 | Plan CVC (Chauffage, Ventilation, Climatisation) | Plans | DWG/PDF | 5-20 planches |
| 22 | Plan electricite (CFO/CFA) | Plans | DWG/PDF | 5-20 planches |
| 23 | Plan plomberie | Plans | DWG/PDF | 3-15 planches |
| 24 | Plan VRD (Voirie et Reseaux Divers) | Plans | DWG/PDF | 3-10 planches |
| 25 | Note de calcul structure | Documents techniques | PDF/XLS | 20-200 pages |
| 26 | PPSPS (Plan Particulier de Securite et de Protection de la Sante) | Securite | PDF | 30-80 pages |
| 27 | PGC (Plan General de Coordination) | Securite | PDF | 20-50 pages |
| 28 | DIUO (Dossier d'Interventions Ulterieures sur l'Ouvrage) | Securite | PDF | 10-30 pages |
| 29 | Registre journal de coordination SPS | Securite | PDF | variable |
| 30 | Plan d'installation de chantier (PIC) | Securite | PDF/DWG | 2-5 pages |
| 31 | Fiche de Donnees Environnementales et Sanitaires (FDES) | RE2020 | PDF/XML | 5-15 pages |
| 32 | Etude thermique RE2020 | RE2020 | PDF | 20-50 pages |
| 33 | Analyse de Cycle de Vie (ACV) batiment | RE2020 | PDF | 30-80 pages |
| 34 | Attestation RE2020 (Bbio, Cep, Ic) | RE2020 | PDF | 3-5 pages |
| 35 | Diagnostic de Performance Energetique (DPE) | Expertise | PDF | 5-10 pages |
| 36 | Diagnostic amiante avant travaux (DAAT) | Expertise | PDF | 15-40 pages |
| 37 | Diagnostic plomb (CREP) | Expertise | PDF | 10-25 pages |
| 38 | Rapport geotechnique (missions G1 a G5) | Expertise | PDF | 20-100 pages |
| 39 | Etude de sol (sondages, essais) | Expertise | PDF | 15-50 pages |
| 40 | Attestation d'assurance Dommage-Ouvrage (DO) | Assurances | PDF | 2-5 pages |
| 41 | Attestation RC Decennale | Assurances | PDF | 1-3 pages |
| 42 | Garantie de Parfait Achevement (GPA) | Assurances | PDF | 2-5 pages |
| 43 | PV de reception des travaux | Reception | PDF | 3-10 pages |
| 44 | PV de reception avec reserves | Reception | PDF | 5-15 pages |
| 45 | PV de levee de reserves | Reception | PDF | 2-5 pages |
| 46 | Ordre de Service (OS) | Contractuel | PDF | 1-2 pages |
| 47 | Avenant au marche | Contractuel | PDF | 3-10 pages |
| 48 | Permis de construire (CERFA 13406) | Urbanisme | PDF | 5-20 pages |
| 49 | Declaration prealable de travaux (CERFA 13703) | Urbanisme | PDF | 3-10 pages |
| 50 | Plan Local d'Urbanisme (PLU) / reglement | Urbanisme | PDF | 50-300 pages |

---

### 2.2 Industrie / Manufacturing (250 types)

Le secteur industriel francais (Airbus, Safran, Saint-Gobain, Schneider Electric) repose sur une documentation technique normee, des procedures qualite strictes et une reglementation ICPE/Seveso exigeante.

#### Categories principales

| # | Categorie | Nb types | Exemples cles |
|---|-----------|----------|---------------|
| 1 | Fiches de securite (FDS/SDS) | 20 | FDS 16 sections, etiquetage CLP, scenarios exposition |
| 2 | Procedures qualite ISO | 30 | Manuel qualite, procedures, enregistrements, audits |
| 3 | Gammes de fabrication | 25 | Gammes operatoires, nomenclatures, instructions |
| 4 | Plans de maintenance | 25 | Plans preventifs, curatifs, predictifs, GMAO |
| 5 | Rapports de controle | 20 | Controles CND, metrologie, essais, certificats |
| 6 | Cahiers des charges | 20 | CDC technique, fonctionnel, industrialisation |
| 7 | AMDEC/FMEA | 15 | AMDEC produit, process, moyen, fiabilite |
| 8 | Documentation S1000D | 25 | Data modules, CSDB, IETP, IETM |
| 9 | ICPE / Seveso | 20 | Dossier ICPE, etude de dangers, POI, PPRT |
| 10 | Audit / Certification | 25 | Rapports audit ISO, IATF, AS9100, NADCAP |
| 11 | HSE (Hygiene, Securite, Environnement) | 25 | DUERP, plan de prevention, protocole chargement |

#### 50 types representatifs detailles

| # | Type de document | Categorie | Format | Volume typique |
|---|-----------------|-----------|--------|----------------|
| 1 | Fiche de Donnees de Securite (FDS) 16 sections | FDS | PDF | 10-40 pages |
| 2 | Etiquetage CLP (Classification, Labelling, Packaging) | FDS | PDF/Image | 1-2 pages |
| 3 | Scenario d'exposition REACH | FDS | PDF | 5-20 pages |
| 4 | Manuel Qualite ISO 9001 | Qualite | PDF | 30-80 pages |
| 5 | Procedure qualite (type P) | Qualite | PDF | 5-15 pages |
| 6 | Instruction de travail (type IT) | Qualite | PDF | 2-10 pages |
| 7 | Enregistrement qualite (type E) | Qualite | PDF/XLS | 1-5 pages |
| 8 | Plan Qualite Projet (PQP) | Qualite | PDF | 20-50 pages |
| 9 | Revue de Direction (compte-rendu) | Qualite | PDF | 5-15 pages |
| 10 | Non-conformite (fiche NC) | Qualite | PDF | 1-3 pages |
| 11 | Action corrective/preventive (8D, PDCA) | Qualite | PDF | 2-10 pages |
| 12 | Gamme operatoire de fabrication | Fabrication | PDF/MES | 1-10 pages |
| 13 | Nomenclature (BOM — Bill of Materials) | Fabrication | XLS/ERP | variable |
| 14 | Fiche suiveuse de production | Fabrication | PDF | 1-2 pages |
| 15 | Instruction de montage/assemblage | Fabrication | PDF/Video | 5-30 pages |
| 16 | Plan de controle (Control Plan) | Fabrication | XLS/PDF | 2-10 pages |
| 17 | Dossier de fabrication (DFab) | Fabrication | PDF | 20-100 pages |
| 18 | Plan de maintenance preventive (niveaux 1-5) | Maintenance | PDF/GMAO | 5-30 pages |
| 19 | Bon de travail maintenance curative | Maintenance | PDF/GMAO | 1-2 pages |
| 20 | Rapport d'intervention maintenance | Maintenance | PDF | 2-5 pages |
| 21 | Plan de maintenance predictive (vibrations, thermographie) | Maintenance | PDF | 10-30 pages |
| 22 | Arbre de defaillance / Arbre des causes | Maintenance | PDF/Visio | 1-5 pages |
| 23 | Fiche equipement (life cycle record) | Maintenance | GMAO/PDF | 2-5 pages |
| 24 | Rapport de Controle Non Destructif (CND) | Controle | PDF | 5-20 pages |
| 25 | Certificat matiere (EN 10204 type 3.1) | Controle | PDF | 1-3 pages |
| 26 | Rapport de metrologie / etalonnage | Controle | PDF | 2-10 pages |
| 27 | PV d'essais mecaniques (traction, durete, resilience) | Controle | PDF | 3-10 pages |
| 28 | Cahier des charges technique | CDC | PDF | 20-80 pages |
| 29 | Cahier des charges fonctionnel (CdCF) | CDC | PDF | 15-50 pages |
| 30 | Specification technique de besoin (STB) | CDC | PDF | 10-40 pages |
| 31 | AMDEC Produit (Design FMEA) | AMDEC | XLS/PDF | 5-30 pages |
| 32 | AMDEC Process (Process FMEA) | AMDEC | XLS/PDF | 5-30 pages |
| 33 | AMDEC Moyen (Equipment FMEA) | AMDEC | XLS/PDF | 5-20 pages |
| 34 | Plan de surveillance (selon IATF 16949) | AMDEC | XLS/PDF | 5-15 pages |
| 35 | Data Module S1000D (descriptif, procedural) | S1000D | XML/SGML | 1-50 pages |
| 36 | IETP (Interactive Electronic Technical Publication) | S1000D | XML/HTML | variable |
| 37 | Catalogue de pieces (IPC — Illustrated Parts Catalogue) | S1000D | PDF/XML | 50-500 pages |
| 38 | Dossier ICPE (Installation Classee pour la Protection de l'Environnement) | ICPE | PDF | 50-300 pages |
| 39 | Etude de dangers (SEVESO) | ICPE | PDF | 100-500 pages |
| 40 | Plan d'Operation Interne (POI) | ICPE | PDF | 30-80 pages |
| 41 | Plan de Prevention des Risques Technologiques (PPRT) | ICPE | PDF | 50-200 pages |
| 42 | Bilan des emissions de gaz a effet de serre (BEGES) | ICPE | PDF/XLS | 20-50 pages |
| 43 | Rapport d'audit ISO 9001 / 14001 / 45001 | Audit | PDF | 10-40 pages |
| 44 | Rapport d'audit IATF 16949 (automobile) | Audit | PDF | 15-50 pages |
| 45 | Rapport d'audit AS9100 (aeronautique) | Audit | PDF | 15-50 pages |
| 46 | Certificat NADCAP (procedes speciaux) | Audit | PDF | 2-5 pages |
| 47 | Document Unique d'Evaluation des Risques (DUERP) | HSE | PDF/XLS | 20-80 pages |
| 48 | Plan de prevention (coactivite) | HSE | PDF | 5-15 pages |
| 49 | Protocole de securite chargement/dechargement | HSE | PDF | 3-10 pages |
| 50 | Permis de feu / permis de travail | HSE | PDF | 1-2 pages |

---

### 2.3 Finance (250 types)

Le secteur financier francais (BNP Paribas, Societe Generale, AXA, Amundi) est le plus reglemente, avec des exigences de reporting prudentiel, de conformite et de transparence qui generent une masse documentaire considerable.

#### Categories principales

| # | Categorie | Nb types | Exemples cles |
|---|-----------|----------|---------------|
| 1 | Etats financiers | 30 | Bilan, compte de resultat, annexes, CAF |
| 2 | Reporting prudentiel (Bale III/IV, Solvabilite II) | 25 | COREP, FINREP, QRT, RSR, SFCR |
| 3 | KYC / AML | 20 | Fiche KYC, declaration Tracfin, screening |
| 4 | Liasse fiscale | 15 | Cerfa 2050-2059, 2065, 2033, IS, TVA |
| 5 | Rapports CAC (Commissaires aux Comptes) | 15 | Rapport general, rapport special, lettre affirmation |
| 6 | IFRS | 20 | Notes annexes IFRS, disclosure checklist |
| 7 | Contrats financiers | 25 | ISDA, CSA, Global Master Repurchase, credit |
| 8 | Due diligence | 25 | VDD, financial DD, legal DD, data room index |
| 9 | Prospectus | 15 | Prospectus AMF, note d'operation, DICI/KID |
| 10 | Declarations reglementaires | 30 | DEB, EMIR, MiFID II, SFDR, taxonomie EU |
| 11 | Documents internes | 30 | Comite de credit, comite des risques, PV CA |

#### 50 types representatifs detailles

| # | Type de document | Categorie | Format | Volume typique |
|---|-----------------|-----------|--------|----------------|
| 1 | Bilan comptable (actif/passif) | Etats financiers | PDF/XLS | 2-5 pages |
| 2 | Compte de resultat | Etats financiers | PDF/XLS | 1-3 pages |
| 3 | Tableau des flux de tresorerie | Etats financiers | PDF/XLS | 1-2 pages |
| 4 | Annexes aux comptes annuels | Etats financiers | PDF | 20-100 pages |
| 5 | Rapport de gestion | Etats financiers | PDF | 30-100 pages |
| 6 | Document d'Enregistrement Universel (DEU/URD) | Etats financiers | PDF | 200-500 pages |
| 7 | Rapport COREP (Common Reporting) | Prudentiel | XBRL/XLS | 50-200 pages |
| 8 | Rapport FINREP (Financial Reporting) | Prudentiel | XBRL/XLS | 50-200 pages |
| 9 | ICAAP (Internal Capital Adequacy Assessment Process) | Prudentiel | PDF | 50-150 pages |
| 10 | ILAAP (Internal Liquidity Adequacy Assessment Process) | Prudentiel | PDF | 30-80 pages |
| 11 | Rapport Solvabilite II — RSR (Regular Supervisory Report) | Prudentiel | PDF | 50-150 pages |
| 12 | SFCR (Solvency and Financial Condition Report) | Prudentiel | PDF | 80-200 pages |
| 13 | QRT (Quantitative Reporting Templates) | Prudentiel | XBRL/XLS | variable |
| 14 | Plan de resolution (recovery plan) | Prudentiel | PDF | 100-300 pages |
| 15 | Fiche KYC personne physique | KYC/AML | PDF | 2-5 pages |
| 16 | Fiche KYC personne morale | KYC/AML | PDF | 5-15 pages |
| 17 | Questionnaire Beneficiaire Effectif (UBO) | KYC/AML | PDF | 2-5 pages |
| 18 | Declaration de soupcon Tracfin | KYC/AML | PDF | 3-10 pages |
| 19 | Rapport de filtrage / screening (sanctions, PEP) | KYC/AML | PDF | 1-5 pages |
| 20 | Liasse fiscale — Cerfa 2050 a 2059 (regime reel normal) | Liasse fiscale | PDF/EDI | 15-25 feuillets |
| 21 | Liasse fiscale — Cerfa 2033 (regime simplifie) | Liasse fiscale | PDF/EDI | 8-12 feuillets |
| 22 | Declaration IS (Cerfa 2065) | Liasse fiscale | PDF/EDI | 2-5 pages |
| 23 | Declaration TVA (CA3) | Liasse fiscale | PDF/EDI | 1-2 pages |
| 24 | Declaration de prix de transfert (Cerfa 2257) | Liasse fiscale | PDF | 3-10 pages |
| 25 | Rapport general du CAC (NEP 700) | CAC | PDF | 3-8 pages |
| 26 | Rapport special du CAC (conventions reglementees) | CAC | PDF | 2-5 pages |
| 27 | Lettre d'affirmation de la direction | CAC | PDF | 2-4 pages |
| 28 | Rapport sur le controle interne (art. L.225-235) | CAC | PDF | 5-15 pages |
| 29 | Notes annexes IFRS (IFRS 7, 9, 15, 16, 17) | IFRS | PDF | 30-100 pages |
| 30 | Disclosure checklist IFRS | IFRS | XLS/PDF | 20-50 pages |
| 31 | Contrat-cadre ISDA (Master Agreement) | Contrats | PDF | 30-50 pages |
| 32 | Credit Support Annex (CSA) | Contrats | PDF | 10-20 pages |
| 33 | Global Master Repurchase Agreement (GMRA) | Contrats | PDF | 25-40 pages |
| 34 | Contrat de credit syndique (LMA format) | Contrats | PDF | 50-150 pages |
| 35 | Convention de compte courant d'associe | Contrats | PDF | 5-10 pages |
| 36 | Vendor Due Diligence (VDD) | Due diligence | PDF | 50-200 pages |
| 37 | Financial Due Diligence report | Due diligence | PDF | 80-250 pages |
| 38 | Legal Due Diligence report | Due diligence | PDF | 50-150 pages |
| 39 | Tax Due Diligence report | Due diligence | PDF | 30-100 pages |
| 40 | Data room index (VDR) | Due diligence | XLS/PDF | 5-20 pages |
| 41 | Prospectus AMF (IPO, augmentation de capital) | Prospectus | PDF | 200-600 pages |
| 42 | Note d'operation (supplement au prospectus) | Prospectus | PDF | 20-50 pages |
| 43 | DICI / KID (Document d'Information Cle) | Prospectus | PDF | 2-3 pages |
| 44 | Rapport annuel OPCVM / FIA | Prospectus | PDF | 30-80 pages |
| 45 | Declaration EMIR (reporting derives) | Reglementaire | XML/CSV | variable |
| 46 | Reporting MiFID II (transaction reporting) | Reglementaire | XML/CSV | variable |
| 47 | Reporting SFDR (Sustainable Finance Disclosure) | Reglementaire | PDF/XBRL | 10-30 pages |
| 48 | Declaration Taxonomie Europeenne (art. 8 delegue) | Reglementaire | PDF/XBRL | 10-20 pages |
| 49 | PV du Comite de credit | Interne | PDF | 3-10 pages |
| 50 | PV du Comite des risques | Interne | PDF | 5-15 pages |

---

### 2.4 Juridique (250 types)

Le secteur juridique francais (cabinets d'avocats, directions juridiques, legaltech) traite une documentation extremement variee, des actes de procedure aux contrats complexes, en passant par la compliance et la veille reglementaire.

#### Categories principales

| # | Categorie | Nb types | Exemples cles |
|---|-----------|----------|---------------|
| 1 | Actes de procedure | 25 | Assignation, conclusions, requete, ordonnance |
| 2 | Contrats | 35 | SPA, SHA, bail, contrat de travail, CGV |
| 3 | Droit des societes | 25 | Statuts, PV AG, pacte d'associes, Kbis |
| 4 | Droit du travail | 25 | Contrats, accords collectifs, CSE, licenciement |
| 5 | Propriete intellectuelle | 20 | Brevets, marques, licences, NDA |
| 6 | RGPD | 20 | AIPD, registre traitements, clauses, DPO |
| 7 | Compliance Sapin II | 15 | Cartographie risques, code conduite, alerte |
| 8 | Droit public | 25 | Memoire, recours, QPC, arrete, decret |
| 9 | Veille reglementaire | 25 | Textes JORF, transposition, circulaires |
| 10 | Jurisprudence | 35 | Arrets, jugements, ordonnances, avis |

#### 50 types representatifs detailles

| # | Type de document | Categorie | Format | Volume typique |
|---|-----------------|-----------|--------|----------------|
| 1 | Assignation (TJ, TC, CPH) | Procedure | PDF | 10-50 pages |
| 2 | Conclusions (demandeur/defendeur) | Procedure | PDF | 15-80 pages |
| 3 | Requete en refere | Procedure | PDF | 5-20 pages |
| 4 | Ordonnance de refere | Procedure | PDF | 3-10 pages |
| 5 | Memoire en demande (TA, CAA) | Procedure | PDF | 10-40 pages |
| 6 | Jugement de premiere instance | Jurisprudence | PDF | 5-30 pages |
| 7 | Arret de Cour d'appel | Jurisprudence | PDF | 5-40 pages |
| 8 | Arret de la Cour de cassation | Jurisprudence | PDF | 3-15 pages |
| 9 | Arret du Conseil d'Etat | Jurisprudence | PDF | 3-20 pages |
| 10 | Decision du Conseil constitutionnel (QPC) | Jurisprudence | PDF | 5-15 pages |
| 11 | Contrat de cession d'actions (SPA) | Contrats | PDF | 30-100 pages |
| 12 | Pacte d'actionnaires (SHA) | Contrats | PDF | 20-60 pages |
| 13 | Protocole d'accord transactionnel | Contrats | PDF | 5-20 pages |
| 14 | Bail commercial (3/6/9) | Contrats | PDF | 15-40 pages |
| 15 | Bail professionnel | Contrats | PDF | 10-25 pages |
| 16 | Contrat de travail CDI | Contrats | PDF | 5-15 pages |
| 17 | Contrat de travail CDD | Contrats | PDF | 5-10 pages |
| 18 | Convention de rupture conventionnelle | Droit du travail | PDF | 3-5 pages |
| 19 | Lettre de licenciement (personnel, economique) | Droit du travail | PDF | 2-5 pages |
| 20 | Accord d'entreprise (NAO, temps de travail) | Droit du travail | PDF | 10-30 pages |
| 21 | Convention collective nationale (CCN) | Droit du travail | PDF | 50-300 pages |
| 22 | PV de reunion CSE | Droit du travail | PDF | 5-20 pages |
| 23 | Reglement interieur | Droit du travail | PDF | 10-20 pages |
| 24 | Statuts de societe (SAS, SA, SARL) | Droit des societes | PDF | 10-30 pages |
| 25 | PV d'Assemblee Generale (AGO, AGE) | Droit des societes | PDF | 5-20 pages |
| 26 | Rapport du Conseil d'administration | Droit des societes | PDF | 5-15 pages |
| 27 | Pacte d'associes | Droit des societes | PDF | 15-40 pages |
| 28 | Extrait Kbis | Droit des societes | PDF | 1-2 pages |
| 29 | Delegation de pouvoirs | Droit des societes | PDF | 2-5 pages |
| 30 | Brevet d'invention (demande INPI/OEB) | PI | PDF | 20-80 pages |
| 31 | Certificat d'enregistrement de marque | PI | PDF | 1-3 pages |
| 32 | Contrat de licence de brevet | PI | PDF | 10-30 pages |
| 33 | Accord de confidentialite (NDA) | PI | PDF | 3-8 pages |
| 34 | Contrat de cession de droits d'auteur | PI | PDF | 5-15 pages |
| 35 | Analyse d'Impact relative a la Protection des Donnees (AIPD) | RGPD | PDF | 15-40 pages |
| 36 | Registre des traitements (art. 30 RGPD) | RGPD | XLS/PDF | 10-50 pages |
| 37 | Clauses contractuelles types (CCT) transferts hors UE | RGPD | PDF | 10-20 pages |
| 38 | Politique de confidentialite / Privacy Policy | RGPD | PDF/HTML | 5-15 pages |
| 39 | Notification de violation de donnees (art. 33) | RGPD | PDF | 3-5 pages |
| 40 | Cartographie des risques de corruption (Sapin II) | Compliance | PDF/XLS | 10-30 pages |
| 41 | Code de conduite anti-corruption | Compliance | PDF | 10-20 pages |
| 42 | Procedure d'alerte interne (lanceur d'alerte) | Compliance | PDF | 5-15 pages |
| 43 | Rapport de l'Agence Francaise Anticorruption (AFA) | Compliance | PDF | 20-50 pages |
| 44 | Programme de conformite (plan de vigilance) | Compliance | PDF | 20-60 pages |
| 45 | Question Prioritaire de Constitutionnalite (QPC) | Droit public | PDF | 5-15 pages |
| 46 | Recours pour exces de pouvoir (REP) | Droit public | PDF | 10-30 pages |
| 47 | Arrete prefectoral / ministeriel | Veille | PDF | 2-10 pages |
| 48 | Decret d'application | Veille | PDF | 2-20 pages |
| 49 | Circulaire ministerielle | Veille | PDF | 5-20 pages |
| 50 | Avis de la CNIL (deliberation) | Veille | PDF | 3-15 pages |

---

## 3. Datasets Techniques par Secteur (10 par secteur)

### 3.1 BTP & Construction

| # | Dataset | Source / HF Path | Questions / Taille | Pertinence | Reference |
|---|---------|------------------|--------------------|------------|-----------|
| 1 | **CODE-ACCORD** | `GT4SD/code-accord` | 862 phrases annotees | NER sur reglementations batiment (codes construction francais). Extraction d'entites reglementaires. | Ezzini et al., "CODE-ACCORD: A Corpus of Building Regulatory Data for NER", CIB W78 2023 |
| 2 | **BDNB** (Base de Donnees Nationale des Batiments) | `data.gouv.fr/bdnb` | 32M fiches batiment | Base de donnees exhaustive du parc immobilier francais. DPE, materiaux, geometrie. Ideal pour le pipeline quantitatif. | CSTB & Etalab, BDNB v0.7, 2024 |
| 3 | **ConstructionSite VQA** | `joyjeni/ConstructionSite-VQA-GPT4` | 10,013 images + QA | Visual Question Answering sur chantiers. Detection d'equipements, evaluation securite. Pipeline multimodal futur. | OpenAI GPT-4V generated, 2024 |
| 4 | **Engineering Drawings AS1100** | `cclabsai/engineering-drawing-qa-as1100` | 210 exemples | QA sur dessins techniques selon norme AS1100 (similaire NF EN ISO 5457). Comprehension de plans. | CCLabs AI, 2024 |
| 5 | **DesignQA** | `filipeabperes/DesignQA` | 300 questions | QA sur conformite aux normes d'ingenierie. Verification de specifications techniques. | Peres et al., "DesignQA: A Multimodal Benchmark for Evaluating LLMs in Engineering Design", 2024 |
| 6 | **NBCC QA** | custom (Canadian Building Code) | ~500 paires QA | Questions-reponses sur le Code National du Batiment du Canada. Structure similaire aux DTU/Eurocodes. | NRC Canada, National Building Code QA initiative |
| 7 | **LIQA** (Legal Interpretation QA for Building Codes) | research dataset | 171 questions | Interpretation juridique des codes de construction. Questions d'ambiguite reglementaire. | Fan et al., "LIQA: Legal Interpretation QA Dataset for Building Codes", 2024 |
| 8 | **Construction Safety Object Detection** | `oscarkfpang/construction_safety_yolov7` | 398 images annotees | Detection d'objets de securite sur chantier (casques, gilets, echafaudages). Enrichissement visuel. | Pang et al., YOLOv7 for Construction Safety, 2023 |
| 9 | **SQuAD Construction subset** | `rajpurkar/squad_v2` (filtre) | ~2,000 paires QA | Sous-ensemble de SQuAD filtre sur les articles Wikipedia lies a la construction (buildings, bridges, materials). | Rajpurkar et al., "SQuAD 2.0", EMNLP 2018 |
| 10 | **ISO Open Data** | `iso.org/open-data` | 24,000+ fiches normes | Metadonnees de toutes les normes ISO publiees. Mapping vers DTU, EN, NF. Enrichissement du graph Neo4j. | ISO, Open Data Portal, 2024 |

---

### 3.2 Industrie / Manufacturing

| # | Dataset | Source / HF Path | Questions / Taille | Pertinence | Reference |
|---|---------|------------------|--------------------|------------|-----------|
| 1 | **IndustryCorpus2** | `BAAI/IndustryCorpus2` | Milliards de tokens | Corpus massif couvrant industrie, manufacturing, chimie, energie. Pre-training et fine-tuning pour embeddings sectoriels. | BAAI, "IndustryCorpus2: A Large-Scale Industrial Text Corpus", 2024 |
| 2 | **Manufacturing QA** | `thesven/manufacturing-qa-gpt4o` | 5,000 paires QA | QA synthetique generee par GPT-4o sur les processus de fabrication, controle qualite, lean manufacturing. | Svensson, 2024 |
| 3 | **ISO Open Data** | `iso.org/open-data` | 24,000+ fiches | Metadonnees des normes ISO 9001, 14001, 45001, IATF 16949, AS9100. Essentiel pour le graph des normes. | ISO, Open Data Portal, 2024 |
| 4 | **TAT-QA** (Tabular And Textual QA) | `nextplusplus/TAT-QA` | 16,552 questions | QA necessitant raisonnement sur tableaux + texte. Directement applicable aux rapports qualite, fiches techniques. | Zhu et al., "TAT-QA: A Question Answering Benchmark on a Hybrid of Tabular and Textual Content", ACL 2021 |
| 5 | **QuALITY** | `nyu-mll/quality` | 6,737 questions | QA sur documents longs (5000+ tokens). Teste la comprehension de documents techniques etendus (manuels, procedures). | Pang et al., "QuALITY: Question Answering with Long Input Texts, Yes!", NAACL 2022 |
| 6 | **RAGBench** | `rungalileo/ragbench` | 100,000 exemples | Benchmark RAG multi-domaine incluant industrie. Mesure fidelite, pertinence, completude. | Galileo AI, "RAGBench: Explainable Benchmark for Retrieval-Augmented Generation", 2024 |
| 7 | **Awesome Industrial Datasets** | `github.com/makinarocks/awesome-industrial-machine-datasets` | 100+ datasets references | Meta-collection de datasets industriels (capteurs, predictif, qualite). Source de donnees pour le pipeline quantitatif. | Makinarocks, curated list, 2023 |
| 8 | **S1000D Documentation** | standard specification + samples | ~10,000 modules techniques | Standard de documentation technique (aeronautique, defense, naval). XML structure. IETPs interactives. | ASD/AIA, S1000D Issue 5.0, 2018 |
| 9 | **AMDEC/FMEA Templates NF EN IEC 60812** | normes + templates industriels | ~500 templates | Templates et exemples d'AMDEC conformes NF EN IEC 60812. Raisonnement sur severite/occurrence/detection. | IEC 60812:2018 "Failure modes and effects analysis (FMEA and FMECA)" |
| 10 | **CRAG** (Comprehensive RAG Benchmark) | `facebook/crag` | 4,409 paires QA | Benchmark Meta (NeurIPS 2024) avec questions dynamiques, multi-hop, et verifiabilite. Teste les limites du RAG. | Yang et al., "CRAG: Comprehensive RAG Benchmark", NeurIPS 2024 Datasets and Benchmarks |

---

### 3.3 Finance

| # | Dataset | Source / HF Path | Questions / Taille | Pertinence | Reference |
|---|---------|------------------|--------------------|------------|-----------|
| 1 | **FinQA** | `ibm/finqa` | 8,281 paires QA | QA numerique sur rapports financiers annuels (10-K). Necessite raisonnement arithmetique sur tableaux. Pipeline quantitatif. | Chen et al., "FinQA: A Dataset of Numerical Reasoning over Financial Data", EMNLP 2021 |
| 2 | **TAT-QA** | `nextplusplus/TAT-QA` | 16,552 questions | QA hybride tableaux + texte sur rapports financiers. Raisonnement multi-step (addition, soustraction, ratio). | Zhu et al., "TAT-QA", ACL 2021 |
| 3 | **FiQA BEIR** | `BeIR/fiqa` | 6,648 requetes | Benchmark information retrieval financiere. Questions d'analystes, opinions de marche. Test du pipeline standard. | Maia et al., "FiQA: Financial Opinion Mining and Question Answering", WWW 2018 |
| 4 | **FinanceBench** | `PatronusAI/financebench` | 150 QA expert | QA haute qualite validee par des analystes financiers. Questions complexes sur 10-K/10-Q reels. Gold standard. | Islam et al., "FinanceBench: A New Benchmark for Financial Question Answering", 2023 |
| 5 | **ConvFinQA** | `TheFinAI/convfinqa` | 3,800 conversations | QA conversationnel multi-tour sur donnees financieres. Chaine de raisonnement sur plusieurs echanges. | Chen et al., "ConvFinQA: Exploring the Chain of Numerical Reasoning in Conversational Finance QA", EMNLP 2022 |
| 6 | **Sujet-Finance-QA-Vision-100k** | `sujet-ai/Sujet-Finance-QA-Vision-100k` | 100,000 QA | QA multimodal sur documents financiers (graphiques, tableaux, captures). Volume massif pour fine-tuning. | Sujet AI, 2024 |
| 7 | **Finance-Instruct-500k** | `sujet-ai/Sujet-Finance-Instruct-500k` | 500,000 instructions | Instructions financieres couvrant comptabilite, analyse, reglementation. Ideal pour fine-tuning LLM sectoriel. | Sujet AI, 2024 |
| 8 | **FinCoT / Fino1** | `TheFinAI/Fino1_Reasoning_Path_FinQA` | ~15,000 chemins de raisonnement | Chain-of-thought sur donnees financieres. Raisonnement explicite step-by-step. Ameliore la transparence du pipeline. | TheFinAI, "Fino1: Financial Reasoning with Chain-of-Thought", 2024 |
| 9 | **FinMME** | `TheFinAI/FinMME` | ~11,000 questions multimodales | Benchmark multimodal financier : graphiques, tableaux, documents scannes. Evaluation comprehension visuelle. | TheFinAI, "FinMME: A Multimodal Finance Benchmark", 2024 |
| 10 | **MTRAG** (Multi-Turn RAG) | custom / research | 110 conversations | Conversations multi-tour sur documents financiers avec retrieval. Teste la coherence du RAG conversationnel. | NVIDIA, "MTRAG: Multi-Turn RAG Benchmark", 2024 |

---

### 3.4 Juridique

| # | Dataset | Source / HF Path | Questions / Taille | Pertinence | Reference |
|---|---------|------------------|--------------------|------------|-----------|
| 1 | **LLEQA** | `maastrichtlawtech/lleqa` | 1,900 paires QA | QA juridique expert. Couvre droit europeen, belge, francais. Questions d'interpretation legale avec raisonnement. | Louis et al., "LLEQA: Legal Long-Form Question Answering", AAAI 2024 |
| 2 | **LegalBench** | `nguha/legalbench` | 20,000 questions (162 taches) | Benchmark juridique massif couvrant 6 types de raisonnement legal. Interpretation, application de regles, rhetorique. | Guha et al., "LegalBench: A Collaboratively Built Benchmark for Measuring Legal Reasoning in LLMs", NeurIPS 2023 |
| 3 | **CUAD** (Contract Understanding Atticus Dataset) | `theatticusteam/cuad-qa` | 13,101 clauses annotees | Comprehension de contrats : 41 types de clauses legales (indemnification, limitation, termination). Pipeline standard. | Hendrycks et al., "CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review", NeurIPS 2021 |
| 4 | **MultiEURLEX** | `multi_eurlex` | 65,000 textes legislatifs EU | Legislation europeenne en 23 langues. Classification multi-label (EuroVoc). Corpus juridique multilingue massif. | Chalkidis et al., "MultiEURLEX: A Multi-Lingual and Multi-Label Legal Document Classification Dataset", EMNLP 2021 |
| 5 | **COLD French Law** | `harvardlil/cold-french-law` | Integralite du droit francais | Corpus complet de la legislation francaise (codes, lois, decrets). Harvard Law. Base de reference pour le graph juridique. | Harvard Library Innovation Lab, Caselaw Access Project — COLD, 2023 |
| 6 | **HFforLegal Case Law** | `rcds/french_case_law` | 534,289 decisions | Decisions de justice francaises (Cour de cassation, cours d'appel). Jurisprudence integrale. Graph Neo4j. | French Open Data initiative, data.gouv.fr, 2024 |
| 7 | **LegalKit** | custom / French legal embeddings | embeddings pre-calcules | Embeddings juridiques francais pre-entraines. Optimises pour la recherche semantique en droit francais. | Communaute LegalTech FR, 2024 |
| 8 | **Jurisprudence Cour de Cassation** | `data.gouv.fr/judilibre` | 100,000+ arrets (mise a jour auto) | Feed temps reel des arrets de la Cour de cassation via l'API Judilibre. Source vivante pour la veille. | Cour de cassation, API Judilibre, 2024 |
| 9 | **CNIL Dataset** | `cnil.fr/open-data` | ~5,000 documents | Deliberations, mises en demeure, sanctions CNIL. Corpus reglementaire RGPD francais. Compliance pipeline. | CNIL, Open Data, 2024 |
| 10 | **EUR-Lex-Sum** | `dennlinger/eur-lex-sum` | 1,500 resumes | Resumes de textes legislatifs EUR-Lex. Multi-lingue. Test de la capacite de synthese du RAG sur textes longs. | Aumiller et al., "EUR-Lex-Sum: A Multi- and Cross-lingual Dataset for Long-Form Summarization", EMNLP 2022 |

---

## 4. Datasets Generaux Performance (10, cross-secteur)

Ces datasets evaluent les capacites fondamentales du systeme RAG independamment du domaine metier.

| # | Dataset | Source / HF Path | Questions | Type | Pertinence RAG | Reference |
|---|---------|------------------|-----------|------|----------------|-----------|
| 1 | **HotpotQA** | `hotpot_qa` | 112,779 | Multi-hop reasoning | Teste la capacite a combiner des informations de 2+ documents. Critique pour l'orchestrateur. | Yang et al., "HotpotQA: A Dataset for Diverse, Explainable Multi-hop QA", EMNLP 2018 |
| 2 | **MuSiQue** | `dgslinym/musique` | 25,000 | Multi-hop (shortcut-proof) | Multi-hop resistant aux raccourcis. Verifie que le RAG raisonne reellement (pas de pattern matching). | Trivedi et al., "MuSiQue: Multi-hop Questions via Single-hop Question Composition", TACL 2022 |
| 3 | **Natural Questions** | `google-research-datasets/natural_questions` | 307,372 | Real Google queries | Questions reelles d'utilisateurs Google. Benchmark realiste pour le pipeline standard. | Kwiatkowski et al., "Natural Questions: A Benchmark for Question Answering Research", TACL 2019 |
| 4 | **SQuAD 2.0** | `rajpurkar/squad_v2` | 142,192 | Extractive + unanswerable | Inclut des questions sans reponse. Teste la capacite du RAG a dire "je ne sais pas". | Rajpurkar et al., "Know What You Don't Know: Unanswerable Questions for SQuAD", ACL 2018 |
| 5 | **FRAMES** | `google/frames-benchmark` | 824 | Multi-step factuality | Benchmark Google de verification factuelle multi-etape. Teste la precision factuelle du pipeline. | Krishna et al., "FRAMES: Fact Retrieval And Multi-step rEaSoning", Google Research 2024 |
| 6 | **CRAG** | `facebook/crag` | 4,409 | Comprehensive RAG | Benchmark Meta (NeurIPS 2024). 8 domaines, questions dynamiques, multi-hop. Reference RAG 2024-2026. | Yang et al., "CRAG", NeurIPS 2024 |
| 7 | **RAGBench** | `rungalileo/ragbench` | 100,000 | Industry RAG | 5 domaines industriels. Mesure fidelite, pertinence, completude avec metriques explicables. | Galileo AI, "RAGBench", 2024 |
| 8 | **TruthfulQA** | `truthful_qa` | 817 | Anti-hallucination | Detecte les hallucinations et biais. Questions conçues pour pieger les LLMs. Metrique de fiabilite. | Lin et al., "TruthfulQA: Measuring How Models Mimic Human Falsehoods", ACL 2022 |
| 9 | **FEVER** | `fever/fever` | 185,445 | Fact verification | Verification de faits contre Wikipedia. Teste la capacite du RAG a confirmer/infirmer des assertions. | Thorne et al., "FEVER: A Large-Scale Dataset for Fact Extraction and VERification", NAACL 2018 |
| 10 | **FQuAD + PIAF** | `manu/fquad2_test` + `piaf` | 28,800 | French QA | Seuls benchmarks QA natifs francais. FQuAD (25,000) + PIAF (3,800). Indispensable pour valider le francais. | d'Hoffschmidt et al., "FQuAD: French Question Answering Dataset", LREC 2020; Keraron et al., "Project PIAF", 2020 |

---

## 5. Totaux et Projection

### 5.1 Recapitulatif par secteur

| Secteur | Datasets | Questions brutes | Echantillon realiste | Dedup ratio |
|---------|----------|-----------------|---------------------|-------------|
| BTP/Construction | 10 | ~69,554 | ~15,000 | 0.22 |
| Industrie | 10 | ~262,689 | ~55,000 | 0.21 |
| Finance | 10 | ~661,431 | ~120,000 | 0.18 |
| Juridique | 10 | ~741,290 | ~95,000 | 0.13 |
| **Generaux** | 10 | ~907,638 | ~39,000 | 0.04 |
| **TOTAL** | **50** | **~2,642,602** | **~324,000** | **0.12** |

### 5.2 Detail des questions brutes par dataset

#### BTP/Construction (69,554)

| Dataset | Questions brutes |
|---------|-----------------|
| CODE-ACCORD | 862 |
| BDNB | 32,000 (fiches exploitables en QA) |
| ConstructionSite VQA | 10,013 |
| Engineering Drawings AS1100 | 210 |
| DesignQA | 300 |
| NBCC QA | 500 |
| LIQA | 171 |
| Construction Safety OD | 398 |
| SQuAD Construction subset | 2,000 |
| ISO Open Data | 24,000 |
| **Sous-total** | **~69,554** |

#### Industrie (262,689)

| Dataset | Questions brutes |
|---------|-----------------|
| IndustryCorpus2 | 50,000 (echantillon QA) |
| Manufacturing QA | 5,000 |
| ISO Open Data | 24,000 |
| TAT-QA | 16,552 |
| QuALITY | 6,737 |
| RAGBench | 100,000 |
| Awesome Industrial | 50,000 (agreges) |
| S1000D | 10,000 |
| AMDEC/FMEA | 500 |
| CRAG | 4,409 |
| **Sous-total** | **~262,689** |

#### Finance (661,431)

| Dataset | Questions brutes |
|---------|-----------------|
| FinQA | 8,281 |
| TAT-QA | 16,552 |
| FiQA BEIR | 6,648 |
| FinanceBench | 150 |
| ConvFinQA | 3,800 |
| Sujet-Finance-QA-Vision-100k | 100,000 |
| Finance-Instruct-500k | 500,000 |
| FinCoT/Fino1 | 15,000 |
| FinMME | 11,000 |
| MTRAG | 110 |
| **Sous-total** | **~661,431** |

#### Juridique (741,290)

| Dataset | Questions brutes |
|---------|-----------------|
| LLEQA | 1,900 |
| LegalBench | 20,000 |
| CUAD | 13,101 |
| MultiEURLEX | 65,000 |
| COLD French Law | 500,000 (articles exploitables) |
| HFforLegal Case Law | 534,289 |
| LegalKit | N/A (embeddings) |
| Jurisprudence CC | 100,000 |
| CNIL Dataset | 5,000 |
| EUR-Lex-Sum | 1,500 |
| **Sous-total** | **~741,290** |

#### Generaux (907,638)

| Dataset | Questions brutes |
|---------|-----------------|
| HotpotQA | 112,779 |
| MuSiQue | 25,000 |
| Natural Questions | 307,372 |
| SQuAD 2.0 | 142,192 |
| FRAMES | 824 |
| CRAG | 4,409 |
| RAGBench | 100,000 |
| TruthfulQA | 817 |
| FEVER | 185,445 |
| FQuAD + PIAF | 28,800 |
| **Sous-total** | **~907,638** |

### 5.3 Notes sur la deduplication

La deduplication est necessaire car :

1. **Chevauchements inter-datasets** : TAT-QA apparait dans Industrie ET Finance (compte une seule fois dans le total)
2. **ISO Open Data** : partage entre BTP et Industrie
3. **CRAG et RAGBench** : presents dans Generaux ET Industrie
4. **Qualite variable** : les datasets synthetiques (Finance-Instruct-500k) ont un taux de filtrage plus eleve
5. **Pertinence francaise** : seuls ~30% des datasets anglophones sont directement exploitables sans traduction

Le ratio dedup/filtrage de 0.12 global traduit ces facteurs combines.

---

## 6. Plan d'Integration (Ingestion / Enrichment)

### 6.1 Architecture d'ingestion

```
Dataset (HF/CSV/JSON)
    |
    v
[Preprocessing] ── Nettoyage, normalisation, traduction si necessaire
    |
    v
[Chunking] ── Strategy adaptee au type de document
    |              - 512 tokens pour texte standard
    |              - Tableaux entiers pour donnees quantitatives
    |              - Sections normatives pour reglementation
    v
[Embedding] ── Jina Embeddings v3 (1024-dim, free tier)
    |
    v
[Indexation] ── Pipeline cible selon type
    |              - Pinecone (standard)
    |              - Neo4j (relations, graph)
    |              - Supabase (quantitatif, tableaux)
    v
[Validation] ── Test sur echantillon de questions du dataset
```

### 6.2 Mapping datasets vers pipelines

| Pipeline | Datasets prioritaires | Justification |
|----------|----------------------|---------------|
| **Standard** (Pinecone) | FQuAD, PIAF, SQuAD 2.0, RAGBench, HotpotQA, LLEQA, CUAD | Recherche semantique dense sur texte |
| **Graph** (Neo4j) | COLD French Law, HFforLegal Case Law, ISO Open Data, MultiEURLEX, BDNB | Relations hierarchiques (lois > articles > jurisprudence) |
| **Quantitative** (Supabase) | FinQA, TAT-QA, ConvFinQA, FinanceBench, Manufacturing QA | Raisonnement numerique, tableaux |
| **Orchestrator** | CRAG, MuSiQue, FRAMES, HotpotQA, TruthfulQA | Multi-hop, routage, verification |

### 6.3 Timeline par phases

| Phase | Periode | Datasets | Volume | Objectif |
|-------|---------|----------|--------|----------|
| **Phase 1** (actuelle) | Fev 2026 | FQuAD, PIAF, SQuAD 2.0, HotpotQA, MuSiQue | ~200 questions curees | Validation des 4 pipelines, accuracy >= 75% |
| **Phase 2** | Mars 2026 | + FinQA, TAT-QA, LLEQA, CUAD, LegalBench | ~1,000 questions HF | Scale-up multi-secteur, accuracy >= 70% |
| **Phase 3** | Avr 2026 | + RAGBench, CRAG, FRAMES, Finance-Instruct | ~10,000 questions | Benchmark SOTA, accuracy >= 65% |
| **Phase 4** | Mai-Juin 2026 | + COLD French Law, HFforLegal, BDNB | ~100,000 questions | Scale industriel, latence < 5s |
| **Phase 5** | Juil+ 2026 | Tous les 50 datasets, generation synthetique | ~324,000 questions | Production, accuracy >= 75% sur 324K |

### 6.4 Strategies d'enrichissement

| Strategie | Description | Datasets concernes |
|-----------|-------------|-------------------|
| **Traduction FR** | Traduction automatique (NLLB/OPUS-MT) des datasets anglophones | FinQA, CUAD, LegalBench, HotpotQA |
| **Generation synthetique** | Generation de questions supplementaires par LLM a partir des documents | BDNB, ISO, COLD French Law |
| **Cross-linking** | Enrichissement Neo4j avec liens entre entites (loi <-> jurisprudence <-> commentaire) | COLD French Law, HFforLegal, MultiEURLEX |
| **Table extraction** | Extraction structuree des tableaux pour le pipeline quantitatif | FinQA, TAT-QA, FinanceBench |
| **Metadata enrichment** | Ajout de metadonnees sectorielles (secteur, sous-secteur, type_doc, difficulte) | Tous |

### 6.5 Workflows n8n concernes

| Workflow | Role dans l'ingestion | Modification necessaire |
|----------|----------------------|------------------------|
| **Standard RAG** (ID: voir n8n-endpoints.md) | Ingestion Pinecone via Jina embeddings | Ajout batch ingestion mode |
| **Graph Pipeline** | Ingestion Neo4j (nodes + relations) | Ajout import CSV/JSON bulk |
| **Quantitative Pipeline** | Ingestion Supabase (tables structurees) | Ajout parseur de tableaux |
| **Orchestrator** | Pas d'ingestion directe | Mise a jour routing rules |
| **Nouveau : Ingestion Workflow** | Workflow dedie batch ingestion | A creer (Phase 3) |

---

## 7. Observations Cles

### 7.1 Le gap francophone

| Secteur | Couverture FR native | Couverture EN (a traduire) | Gap |
|---------|---------------------|---------------------------|-----|
| **BTP/Construction** | Tres faible (CODE-ACCORD, BDNB seuls) | Moyenne (NBCC, DesignQA) | CRITIQUE |
| **Industrie** | Faible (normes NF via ISO) | Forte (IndustryCorpus2, RAGBench) | Eleve |
| **Finance** | Faible (pas de FinQA francais) | Tres forte (FinQA, TAT-QA, etc.) | Eleve |
| **Juridique** | Forte (COLD French Law, Judilibre, CNIL) | Forte (LegalBench, CUAD) | Modere |

Le secteur BTP/Construction est le plus deficitaire en datasets francophones. La generation synthetique a partir de documents normatifs (DTU, Eurocodes FR) sera indispensable.

Le secteur Juridique est le mieux couvert grace a l'Open Data judiciaire francais (Judilibre, data.gouv.fr) et aux initiatives acadamiques (COLD French Law de Harvard).

### 7.2 L'emergence des benchmarks RAG-specifiques (2024-2026)

Les benchmarks traditionnels (SQuAD, Natural Questions) testent l'extraction mais pas le pipeline RAG complet. La nouvelle generation inclut :

| Benchmark | Annee | Specificite RAG |
|-----------|-------|-----------------|
| **CRAG** (Meta) | 2024 | Questions dynamiques, multi-hop, verifiabilite |
| **RAGBench** (Galileo) | 2024 | Metriques explicables (fidelite, pertinence, completude) |
| **FRAMES** (Google) | 2024 | Verification factuelle multi-etape |
| **MTRAG** (NVIDIA) | 2024 | Conversations multi-tour avec retrieval |
| **FinMME** (TheFinAI) | 2024 | RAG multimodal sectoriel (finance) |

Ces benchmarks sont directement alignes avec notre architecture multi-pipeline et doivent etre prioritises.

### 7.3 Le raisonnement multi-hop est critique

L'orchestrateur doit gerer des questions necessitant 2 a 5 etapes de raisonnement. Les datasets cles pour cette capacite :

| Dataset | Nb hops moyen | Type de raisonnement |
|---------|--------------|---------------------|
| HotpotQA | 2 | Bridging, comparison |
| MuSiQue | 2-4 | Composition (shortcut-proof) |
| FRAMES | 3-5 | Multi-step factuality |
| ConvFinQA | 2-3 | Numerical chain-of-thought |
| CRAG | 1-4 | Dynamic, mixed |

Le pipeline orchestrateur doit etre evalue prioritairement sur MuSiQue et FRAMES, qui sont les plus exigeants et les plus resistant aux raccourcis.

### 7.4 La dimension multimodale (futur)

Plusieurs datasets integrent deja des composantes visuelles :

- **ConstructionSite VQA** : images de chantier
- **Engineering Drawings AS1100** : plans techniques
- **Sujet-Finance-QA-Vision-100k** : documents financiers scannes
- **FinMME** : graphiques et tableaux financiers

L'integration multimodale (OCR + VLM) est planifiee pour la Phase 5 mais doit etre anticipee dans le choix des embeddings et la structure des indexes.

### 7.5 Recommandations prioritaires

| Priorite | Action | Impact | Effort |
|----------|--------|--------|--------|
| P0 | Integrer FQuAD + PIAF dans Phase 1 | Validation FR native | Faible |
| P0 | Integrer FinQA + TAT-QA dans Phase 2 | Pipeline quantitatif | Moyen |
| P1 | Integrer COLD French Law dans Neo4j | Graph juridique complet | Eleve |
| P1 | Traduire HotpotQA/MuSiQue subset en FR | Tests multi-hop francais | Moyen |
| P2 | Generation synthetique BTP a partir des DTU | Combler le gap BTP | Eleve |
| P2 | Ingestion BDNB dans Supabase | Pipeline quantitatif BTP | Moyen |
| P3 | Integration Judilibre temps reel | Veille jurisprudentielle live | Eleve |
| P3 | Pipeline multimodal (VQA chantier + plans) | Capacite visuelle | Tres eleve |

---

> **Document genere le 2026-02-16 pour le projet Multi-RAG Orchestrator.**
> **50 datasets, ~2.6M questions, 4 secteurs, ciblant les ETI et Grands Groupes francais.**
