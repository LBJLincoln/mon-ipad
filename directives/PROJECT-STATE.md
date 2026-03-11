# Etat Systeme — Session 96 (continued #2)

> Date: 2026-03-11T01:30Z | Auteur: Claude Code Opus 4.6

---

## 1. INFRASTRUCTURE

| Composant | Status | Notes |
|-----------|--------|-------|
| **VM GCP** (34.136.180.66) | UP | 969MB RAM |
| **S1** (engine) | UP | Standard+Graph+Orch+Quant+AutoHealer+ErrorTrigger |
| **S3** (engine-3) | UP | Standard+Graph+Orch+Quant+ErrorTrigger |
| **S5** (engine-5) | UP | Standard+Graph+Orch+Quant+ErrorTrigger |
| **S9** (engine-9) | UP | Standard+ErrorTrigger |
| **S6** (Docling) | UP | converter loaded, health OK |
| **S7** (LiteLLM) | **UP** | 9 model groups, 13-provider fallback, DB partially broken (spend tracking only) |

## 2. DATABASES

| DB | Used | Content |
|----|------|---------|
| **E5 Pinecone** | **58,533** vectors | Sectors (target 100K) |
| **Jina Pinecone** | ~43K vectors | Legacy (still queried in multi-index) |
| **Neo4j** | **71,890** nodes | Entity + SectorDocument |
| **Supabase** | **43,357** docs | finance 25.8K, juridique 10.1K, btp 4.4K, industrie 2.9K |
| **Supabase pipeline_errors** | Active | Auto-captures n8n errors via Error Trigger |
| **Supabase financials** | **212** rows | Companies: Microsoft, JPMorgan, Boeing, etc. |

## 3. PIPELINES — ALL VIA LiteLLM

### Smoke Test Results (V3.8 / V3.5 / V3.2 / V13 — ALL LiteLLM)
| Pipeline | Pass | Latency | Status | LLM Provider |
|----------|------|---------|--------|-------------|
| **Standard** | 3/3 | 41-50s | **PASS** | LiteLLM → smart (13 fallbacks) |
| **Orchestrator** | 1/1 | 52s | **PASS** | Routes to sub-pipelines |
| **Graph** | 2/2 | 27-86s | **PASS** | LiteLLM → smart + self-hosted embeddings |
| **Quant** | 3/3 | 11-87s | **PASS** | LiteLLM → smart |
| Docling | - | - | UP | converter loaded |

### Workflow IDs
| Pipeline | ID | Version | Spaces |
|----------|----|---------|--------|
| Standard | `TmgyRP20N4JFd9CB` | **V3.8** (LiteLLM) | S1/S3/S5 |
| Graph | `6257AfT1l4FMC6lY` | **V3.5** (LiteLLM+self-hosted embed) | S1/S3 |
| Quant | `cjhEhVs0KV1ExHqX` | **V3.2** (LiteLLM) | S1/S3/S5 |
| Orchestrator | `qOSaFFrqO8Jb4VGb` | **V13** (LiteLLM) | S1/S3/S5 |
| Auto-Healer | `Yqw7Pzn0e7m0C6i3` | V1.2 | S1/S3/S5 |
| Error Trigger | `AH3eXOmgxt5cOd93` / `JyrwJ6UOQeSH9WXX` | V1.0 | ALL |

## 4. LiteLLM S7 — KEY ROTATION ENGINE

| Model Group | Providers | Fallback Chain |
|-------------|-----------|----------------|
| **smart** | 13 | OpenRouter llama-70b → qwen-235b → Gemini Flash → Groq llama |
| **default** | 10 | OpenRouter trinity → Gemini Flash → Groq llama |
| **fast** | 11 | OpenRouter trinity → gemma-27b → Gemini Flash |
| **llama-70b** | 12 | OpenRouter llama → Groq (5 keys) |
| **gemma-27b** | 7 | OpenRouter gemma |
| **gemini-flash** | 1 | Gemini direct |
| **groq-llama** | 5 | Groq only (NO fallback — avoid!) |

**All pipelines now use `smart` model group** = automatic failover when any provider hits rate limits.

## 5. S96 ACCOMPLISHMENTS (ALL)
- [x] **LiteLLM MIGRATION** — All 4 pipelines migrated from Groq direct to LiteLLM with 13-provider fallback
- [x] **Quant FIXED** — Was 0/3 (40/100) → now 3/3 SUCCESS with real financial data
- [x] **S7 LiteLLM RECOVERED** — Was thought BROKEN, actually UP (just needs auth key)
- [x] **SQL Validator V2** — Robust JSON parser handles markdown blocks, raw text, LLM quirks
- [x] **ERROR TRIGGER n8n DEPLOYED** — All Spaces, linked to all pipelines
- [x] **Standard V3.8** — LiteLLM + tenant_id fallback + BM25 GIN index
- [x] **Juridique FIXED** — Was 91s timeout → 31s with 10 sources
- [x] **Smart Smoke Test** — 12 golden Q&A, parallel, node-by-node comparison
- [x] **Supabase pipeline_errors** — Auto-captures all n8n failures
- [x] **Full workflow inventory** — 134 per Space, 129 archived
- [x] **Eval Runner V2** — Auto-discover real PDFs per sector
- [x] **Error Analyzer** — Success+failure tracking, error library

## 6. CRITICAL FIXES THIS SESSION
1. **Groq → LiteLLM**: All 5 Groq keys hit daily TPD limits. Migrated all pipelines to LiteLLM proxy with automatic key/model rotation
2. **n8n predefinedCredentialType bug**: HTTP nodes had stored Groq credentials that OVERRODE manual Authorization headers. Fixed by setting `authentication: "none"`
3. **Quant SQL Validator**: LLM responses wrapped in markdown code blocks. Added regex extraction fallback
4. `tenant_id` fallback to `input.sector` (V3.7 fix carried forward)

## 7. GRAPH V3.5 FIXES
1. Jina API keys expired → self-hosted embeddings Space (1024 dims, same format)
2. Pinecone: legacy `sota-rag-jina-1024` → current `website-sectors-jina-1024`
3. LLM prompt: ultra-short entity answers → expert-level 3-5 sentence responses
4. Answer Formatter: degraded state detection (LOW_CONFIDENCE, DEGRADED status)
5. Reranker: disabled (Jina expired), fallback handler catches it

## 8. NEXT PRIORITIES
1. **Sources count = 0** — Standard answers correctly but 0 sources (Pinecone query/response parsing)
2. Run full 220q eval with V3.8
3. Clean 100+ inactive workflows from Spaces
4. Add more financial data to Supabase (TotalEnergies, French companies)
5. Reranking integration (FlashRank or Cohere MCP)
6. Get new Jina API keys or migrate Graph reranker to Cohere
7. Docling: targeted use only (high-value PDFs, not bulk)
