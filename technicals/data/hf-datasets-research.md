# HuggingFace Production-Grade Dataset Research

> Research date: 2026-03-09
> Goal: Identify TOP 5 datasets per sector for 1M documents across 100+ document types
> Sectors: Finance, Legal/Juridique, BTP/Construction, Manufacturing/Industrie

---

## SECTOR 1: FINANCE

### TOP 5 Datasets

| # | Dataset | HF Path | Size | Doc Types | Complexity | Language | License |
|---|---------|---------|------|-----------|------------|----------|---------|
| 1 | **PleIAs SEC** | `PleIAs/SEC` | 245,211 entries, 7.2B words | 10-K annual reports (1993-2024) | HIGH - tables, footnotes, multi-section, avg 34K words/entry | EN | Open |
| 2 | **EDGAR Corpus** | `eloukas/edgar-corpus` | 6B+ tokens, 28 years (1993-2020) | 10-K filings, 20 sections per report | HIGH - largest financial NLP corpus, multi-section | EN | Academic |
| 3 | **TAT-QA** | `next-tat/TAT-QA` | 16,552 questions, 2,757 hybrid contexts | Financial reports with tables + text | VERY HIGH - hybrid tabular+textual, numerical reasoning | EN | Apache 2.0 |
| 4 | **FinQA** | `ibm-research/finqa` | 8,281 QA pairs, 2,800 financial reports | Earnings reports with tables | VERY HIGH - numerical reasoning, annotated programs | EN | MIT |
| 5 | **PleIAs AMF-PDF** | `PleIAs/AMF-PDF` | Large (multimodal) | French financial regulatory PDFs | VERY HIGH - native PDF, multimodal, French financial authority | FR | Open |

### Honorable Mentions

| Dataset | HF Path | Size | Notes |
|---------|---------|------|-------|
| PatronusAI FinanceBench | `PatronusAI/financebench` | 150 QA pairs | Gold-standard RAG eval for 10-K/10-Q |
| SP500 EDGAR 10-K | `jlohding/sp500-edgar-10k` | SP500 companies 2010-2022 | Focused on large-cap |
| FinRAGBench-V | Paper (2025) | 60K CN + 51K EN pages | Multimodal: tables, charts, visual citations |
| FLUE FiQA | `SALT-NLP/FLUE-FiQA` | Financial QA benchmark | Sentiment + QA tasks |
| Financial Reports SEC | `JanosAudran/financial-reports-sec` | 1993-2020, labeled | Sentiment labels (positive/negative) |

### Key Insight - Finance
**PleIAs/SEC alone provides 245K documents (7.2B words) covering 30+ years of SEC filings.** Combined with TAT-QA and FinQA for complex table reasoning, and AMF-PDF for French regulatory documents, this sector is the best-served on HuggingFace. Potential: 250K+ documents easily.

---

## SECTOR 2: LEGAL / JURIDIQUE

### TOP 5 Datasets

| # | Dataset | HF Path | Size | Doc Types | Complexity | Language | License |
|---|---------|---------|------|-----------|------------|----------|---------|
| 1 | **Multi Legal Pile** | `joelniklaus/Multi_Legal_Pile` | 689 GB, 10M-100M entries | Legislation, caselaw, contracts (24 EU languages) | VERY HIGH - 24 languages, all legal doc types | Multilingual (incl. FR) | CC BY-NC-SA 4.0 |
| 2 | **COLD French Law** | `harvard-lil/cold-french-law` | 841,761 articles | Codes, lois, decrets, arretes (current French law) | HIGH - full French legal corpus with EN translations | FR + EN | CC BY 4.0 |
| 3 | **French Jurisprudence** | `antoinejeannot/jurisprudence` | 971,636 decisions | Tribunal judiciaire, Cour d'appel, Cour de cassation | HIGH - 3 jurisdiction levels, updated every 72h | FR | Open |
| 4 | **Argimi French Jurisprudence** | `artefactory/Argimi-Legal-French-Jurisprudence` | 100K-1M entries | Bulletin Civil + Criminal Chambers (since 1960) | HIGH - structured JSON from DILA XML | FR | CC BY-SA 4.0 |
| 5 | **MultiEURLEX** | `nlpaueb/multi_eurlex` | 65,000 EU laws | EU legislation, 23 languages, EUROVOC taxonomy | HIGH - 23 languages, multi-label classification | 23 EU languages | CC BY-SA 4.0 |

### Honorable Mentions

| Dataset | HF Path | Size | Notes |
|---------|---------|------|-------|
| CUAD (Contracts) | `theatticusproject/cuad` | 510 contracts, 13K+ labels | 41 clause types, NDA/M&A contracts |
| LexGLUE | `coastalcph/lex_glue` | 7 legal NLP tasks, 100K+ | ECtHR, SCOTUS, contracts |
| LegalBench | `nguha/legalbench` | Large benchmark | Legal reasoning tasks |
| DILA Vectors | `AgentPublic/DILA-Vectors` | 4 vector databases | French gov legal docs, pre-embedded |
| DILA OpenData FR | `Nicolas-BZRD/DILA_OPENDATA_FR_2023` | 25.65 GB | Full French legal/admin corpus |
| AgentPublic/legi | `AgentPublic/legi` | Full Legifrance | Consolidated French legislation |
| LegalKit | `louisbrulenaudet/legalkit` | Daily updated | All French legal codes, LLaMA-labeled |
| EUR-Lex Sum | `dennlinger/eur-lex-sum` | 24 languages | Summarization benchmark |
| EUR-Lex Resources | `joelniklaus/eurlex_resources` | 179 GB | Full EUR-Lex pretraining corpus |
| BSARD (Belgian) | `maastrichtlawtech/bsard` | Belgian law | FR legal retrieval benchmark |

### Key Insight - Legal
**This sector is MASSIVELY covered.** Multi Legal Pile alone is 689GB across 24 languages. French-specific datasets (COLD French Law + French Jurisprudence + DILA) provide 1.8M+ documents of actual French law and court decisions. Combined with EU legislation (MultiEURLEX, EUR-Lex), this sector can easily reach 2M+ documents. **Best-served sector after Finance.**

---

## SECTOR 3: BTP / CONSTRUCTION

### TOP 5 Datasets

| # | Dataset | HF Path | Size | Doc Types | Complexity | Language | License |
|---|---------|---------|------|-----------|------------|----------|---------|
| 1 | **IFC BIM QA** | `Dietmar2020/ifc-bim-qa-dataset` | 8,626 QA pairs | IFC4X3 EXPRESS schema (BIM standards) | MEDIUM - structured QA from IFC standards | EN | Open |
| 2 | **ConstructionSite** | `LouisChen15/ConstructionSite` | 10,013 images + annotations | Construction inspection images | MEDIUM - VLM benchmark, safety/inspection | EN | Open |
| 3 | **BOAMP (via API)** | API: data.gouv.fr/BOAMP | Millions of notices | Public procurement notices (marches publics) | HIGH - structured procurement data | FR | Licence Ouverte v2.0 |
| 4 | **Project Management LLM** | `ai-in-projectmanagement/ProjectManagementLLM_dataset` | Unknown | Project management documents | MEDIUM - PM terminology and processes | EN | Unknown |
| 5 | **CODE-ACCORD** | Paper/dataset (EU Horizon) | 862 sentences | Building regulations (England + Finland) | HIGH - regulatory compliance checking | EN/FI | Research |

### Critical Gap Analysis - BTP

**BTP/Construction is the WORST-SERVED sector on HuggingFace.** Key missing document types:

| Missing Document Type | Source | Availability |
|----------------------|--------|--------------|
| NF DTU (Documents Techniques Unifies) | AFNOR | PAID - not open data |
| CCAG/CCTP (marches publics templates) | Legifrance/BOAMP | Partial via API |
| RE2020 (Reglementation Environnementale) | Legifrance | Open but not on HF |
| Eurocodes (structural design) | CEN/AFNOR | PAID - ISO standards |
| Rapports de controle technique | Private | Not available |
| Plans/DOE (Dossier des Ouvrages Executes) | Private | Not available |
| Diagnostics immobiliers (DPE, amiante) | ADEME/open data | Partial |

### Recommended Strategy for BTP
1. **Scrape BOAMP** via API for public procurement documents (CCTP, RC, AAPC)
2. **Use DILA/Legifrance** datasets for construction-related regulations (Code de la Construction, Code de l'Urbanisme)
3. **ArchCAD-400K** (not on HF) for CAD/drawing understanding (413K chunks from 5,538 drawings)
4. **Create custom dataset** from open-source construction technical guides
5. **Patent data (HUPD)** filtered for construction/civil engineering CPC codes

---

## SECTOR 4: MANUFACTURING / INDUSTRIE

### TOP 5 Datasets

| # | Dataset | HF Path | Size | Doc Types | Complexity | Language | License |
|---|---------|---------|------|-----------|------------|----------|---------|
| 1 | **FabNER** | `DFKI-SLT/fabner` | 350,000+ words | Manufacturing process science abstracts | HIGH - 12 entity types (materials, processes, equipment) | EN | Research |
| 2 | **TechQA** | `PrimeQA/TechQA` | 600 train + 800K TechNotes | Technical support documents (IBM) | VERY HIGH - real domain-adapted QA from tech manuals | EN | Research |
| 3 | **EManual** | `AnuPandey/emanual` | 307,957 e-manuals | Electronic device manuals | HIGH - product documentation, QA benchmark | EN | Research |
| 4 | **Big Patent** | `NortheasternUniversity/big_patent` | 1.3M patents | US patent descriptions + abstracts | HIGH - technical specifications, 9 CPC categories | EN | Open |
| 5 | **Harvard USPTO (HUPD)** | `HUPD/hupd` | 4.5M patents (2004-2018) | Full patent applications (34 fields per app) | VERY HIGH - claims, descriptions, drawings refs | EN | CC BY 4.0 |

### Honorable Mentions

| Dataset | HF Path | Size | Notes |
|---------|---------|------|-------|
| Maintenance Dataset | `Jaya1995/Maintenance` | Small | Equipment maintenance data |
| Predictive Maintenance | `MohammedSohail/predictive-maintenance-dataset` | Sensor data | Time-series, not text |
| Manufacturing (akumar33) | `akumar33/manufacturing` | Research | Manufacturing NER |
| Engineering Drawings AS1100 | `jcrzd/engineering-drawings-as1100` | Images | Australian standard drawings |
| PANORAMA (Patents) | `LG-AI-Research/PANORAMA` | 8,143 patent office actions | USPTO examiner documents 2015-2024 |

### Key Insight - Manufacturing
**Manufacturing is poorly served for TEXT-based datasets** on HuggingFace. Most industrial datasets focus on sensor/time-series data, not documents. The best strategy is:
1. **Patents (HUPD + Big Patent)** filtered for manufacturing IPC codes = 500K+ relevant documents
2. **TechQA + EManual** for technical documentation = 308K+ manuals
3. **FabNER** for manufacturing-specific NLP
4. **Custom ingestion** of ISO standards, FMEA templates, SDS sheets (most are proprietary)

---

## CROSS-SECTOR DATASETS (Applicable to All)

| Dataset | HF Path | Size | Relevance |
|---------|---------|------|-----------|
| **RAGBench** | `galileo-ai/ragbench` | 100K examples | 5 industry domains incl. manuals, legal, finance |
| **Open RAG Bench** | `vectara/open_ragbench` | 3,045 QA pairs, 1000 PDFs | Multimodal PDF (tables, images, text) |
| **OmniDocBench** | `opendatalab/OmniDocBench` | 1,355 pages, 20K+ blocks | 9 doc types, tables, formulas, charts (CVPR 2025) |
| **M3DocVQA** | `jonghakim/m3doc` | 3,000+ PDFs, 40K+ pages | Open-domain multi-document VQA |
| **T2-RAGBench** | Paper (2025) | 23,088 QA triples | Text + Table RAG evaluation |
| **TabLib** | Paper (2023) | 627M tables | Largest table dataset ever |
| **DocVQA** | `lmms-lab/DocVQA` | 50K questions, 12,767 images | Document visual QA benchmark |
| **MP-DocVQA** | `rubentito/mp-docvqa` | Multi-page documents | Multi-page document VQA |

---

## SUMMARY: PATH TO 1M DOCUMENTS

| Sector | Available on HF | Easy to Reach | Gap to Fill | Strategy |
|--------|----------------|---------------|-------------|----------|
| **Finance** | 250K+ (PleIAs SEC alone) | 300K+ | Minimal | SEC + AMF + FinQA/TAT-QA |
| **Legal** | 2M+ (Multi Legal Pile + French law) | 2M+ | None | Already exceeds 1M target |
| **BTP/Construction** | ~20K | ~50K with BOAMP API | **950K GAP** | Custom scraping needed |
| **Manufacturing** | ~310K (EManual + patents) | 500K+ with patent filtering | **500K GAP** | Patent CPC filtering + custom |

### Total Realistic Estimate

| Source | Documents | Effort |
|--------|-----------|--------|
| HuggingFace datasets (direct) | ~2.6M | LOW - download + process |
| APIs (BOAMP, Legifrance, EDGAR) | ~500K | MEDIUM - API scraping |
| Custom ingestion needed | ~200K | HIGH - Docling + manual |
| **TOTAL** | **~3.3M** | Mixed |

### Priority Actions

1. **IMMEDIATE**: Download PleIAs/SEC (245K), COLD French Law (841K), French Jurisprudence (971K)
2. **WEEK 1**: Filter HUPD patents for construction + manufacturing CPC codes
3. **WEEK 2**: Set up BOAMP API scraping for public procurement documents
4. **WEEK 3**: Process EManual corpus (307K device manuals)
5. **ONGOING**: Custom Docling ingestion for BTP-specific documents (DTU, diagnostics)

### Document Type Coverage (Target: 100 types)

| Category | Types Available | Examples |
|----------|----------------|----------|
| Financial Reports | 8+ | 10-K, 10-Q, 8-K, annual reports, earnings, prospectus, proxy statements, AMF filings |
| Legal Documents | 15+ | Codes, lois, decrets, arretes, jurisprudence, contracts, NDA, EU directives, regulations, GDPR |
| Technical Standards | 5+ | Patents, IFC/BIM, building codes, ISO references, engineering specs |
| Product Documentation | 6+ | User manuals, e-manuals, tech notes, data sheets, SDS, FMEA |
| Public Procurement | 5+ | AAPC, RC, CCTP, CCAG, actes d'engagement |
| Construction Docs | 4+ | Inspection reports, diagnostics, DOE, plans |
| Research/Academic | 3+ | Papers, abstracts, conference proceedings |
| **TOTAL** | **~46 types** | Need 54 more via custom ingestion |

---

## SOURCES

### Finance
- [PleIAs/SEC](https://huggingface.co/datasets/PleIAs/SEC) - 245K SEC annual reports
- [eloukas/edgar-corpus](https://huggingface.co/datasets/eloukas/edgar-corpus) - 6B+ tokens EDGAR
- [next-tat/TAT-QA](https://huggingface.co/datasets/next-tat/TAT-QA) - 16K hybrid QA
- [ibm-research/finqa](https://huggingface.co/datasets/ibm-research/finqa) - 8K financial QA
- [PleIAs/AMF-PDF](https://huggingface.co/datasets/PleIAs/AMF-PDF) - French AMF regulatory PDFs
- [PatronusAI/financebench](https://huggingface.co/datasets/PatronusAI/financebench) - RAG eval benchmark
- [JanosAudran/financial-reports-sec](https://huggingface.co/datasets/JanosAudran/financial-reports-sec) - Labeled SEC filings
- [FinRAGBench-V paper](https://arxiv.org/abs/2505.17471) - Multimodal financial RAG

### Legal
- [joelniklaus/Multi_Legal_Pile](https://huggingface.co/datasets/joelniklaus/Multi_Legal_Pile) - 689GB multilingual legal
- [harvard-lil/cold-french-law](https://huggingface.co/datasets/harvard-lil/cold-french-law) - 841K French law articles
- [antoinejeannot/jurisprudence](https://huggingface.co/datasets/antoinejeannot/jurisprudence) - 971K French court decisions
- [artefactory/Argimi-Legal-French-Jurisprudence](https://huggingface.co/datasets/artefactory/Argimi-Legal-French-Jurisprudence) - DILA jurisprudence
- [nlpaueb/multi_eurlex](https://huggingface.co/datasets/nlpaueb/multi_eurlex) - 65K EU laws, 23 languages
- [theatticusproject/cuad](https://huggingface.co/datasets/theatticusproject/cuad) - 510 legal contracts
- [coastalcph/lex_glue](https://huggingface.co/datasets/coastalcph/lex_glue) - Legal NLP benchmark
- [AgentPublic/legi](https://huggingface.co/datasets/AgentPublic/legi) - Full Legifrance
- [Nicolas-BZRD/DILA_OPENDATA_FR_2023](https://huggingface.co/datasets/Nicolas-BZRD/DILA_OPENDATA_FR_2023) - 25.65 GB French gov data
- [louisbrulenaudet/legalkit](https://huggingface.co/datasets/louisbrulenaudet/legalkit) - Daily-updated French codes

### BTP/Construction
- [Dietmar2020/ifc-bim-qa-dataset](https://huggingface.co/datasets/Dietmar2020/ifc-bim-qa-dataset) - 8.6K BIM QA
- [LouisChen15/ConstructionSite](https://huggingface.co/datasets/LouisChen15/ConstructionSite) - 10K inspection images
- [BOAMP API](https://www.dila.gouv.fr/services/api/boamp/api-boamp-version-2-beta) - French public procurement
- [Open French Law RAG](https://lil.law.harvard.edu/open-french-law-rag/) - Harvard RAG experiment

### Manufacturing
- [DFKI-SLT/fabner](https://huggingface.co/datasets/DFKI-SLT/fabner) - 350K+ words manufacturing NER
- [PrimeQA/TechQA](https://huggingface.co/datasets/PrimeQA/TechQA) - 800K tech notes
- [AnuPandey/emanual](https://huggingface.co/datasets/AnuPandey/emanual) - 307K e-manuals
- [NortheasternUniversity/big_patent](https://huggingface.co/datasets/NortheasternUniversity/big_patent) - 1.3M patents
- [HUPD/hupd](https://huggingface.co/datasets/HUPD/hupd) - 4.5M USPTO patents
- [LG-AI-Research/PANORAMA](https://huggingface.co/datasets/LG-AI-Research/PANORAMA) - 8K patent office actions

### Cross-Sector
- [galileo-ai/ragbench](https://huggingface.co/datasets/galileo-ai/ragbench) - 100K RAG benchmark
- [vectara/open_ragbench](https://huggingface.co/datasets/vectara/open_ragbench) - Multimodal PDF RAG
- [opendatalab/OmniDocBench](https://huggingface.co/datasets/opendatalab/OmniDocBench) - CVPR 2025 doc parsing
- [jonghakim/m3doc](https://huggingface.co/datasets/jonghakim/m3doc) - Multi-doc VQA
- [lmms-lab/DocVQA](https://huggingface.co/datasets/lmms-lab/DocVQA) - Document VQA
