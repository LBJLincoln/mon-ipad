---
name: Free LLM Inference Capacity — Full Audit April 2026
description: Complete capacity audit of all free LLM inference providers across our 4 HF + 5 Groq + 7 OpenRouter + 2 Cohere + 1 Gemini + Cerebras accounts. Includes multi-key scaling rules.
type: project
---

# Free LLM Inference Capacity — Full Audit (April 4, 2026)

## CRITICAL SCALING RULES (READ FIRST)

| Provider | Limits Apply Per | Multi-Account Works? | Our Keys |
|----------|-----------------|---------------------|----------|
| Groq | Per ORGANIZATION (not per key) | YES — separate org = separate pool | 5 keys (check if same org) |
| OpenRouter | GLOBALLY (platform-wide IP/fingerprint) | NO — multiple accounts don't help | 7 keys (all share same pool) |
| Cerebras | Per ACCOUNT | YES — separate accounts = separate pools | 1 key (add more accounts) |
| HuggingFace | Per TOKEN/ACCOUNT | YES — each account has own $0.10/month | 4 tokens = 4x pool |
| Google AI Studio | Per PROJECT | YES — separate projects = separate pools | 1 key |
| Cohere | Per API KEY (trial key) | YES — separate accounts = separate pools | 2 keys |
| SambaNova | Per ACCOUNT | YES — separate accounts = separate pools | 0 (to add) |
| Mistral | Per WORKSPACE | YES — separate workspaces = separate pools | 0 (to add) |
| GitHub Models | Per GITHUB ACCOUNT | YES — separate accounts = separate pools | 0 (to add) |
| Fireworks.ai | Per ACCOUNT (no CC) | YES | 0 (to add) |

## Complete Provider Table

### Tier 1: High Volume (>1000 RPD per account)

| Provider | Model | RPM | RPD | TPD | Quality | Notes |
|----------|-------|-----|-----|-----|---------|-------|
| Cerebras | qwen-3-235b-a22b | 30 | 14,400 | 1M tokens | Excellent | 235B MoE, 1400 tps |
| Cerebras | llama3.1-8b | 30 | 14,400 | 1M tokens | Good | 2600 tps, fastest |
| Cerebras | qwen-3-32b | 30 | 14,400 | 1M tokens | Very Good | 2600 tps |
| Cerebras | gpt-oss-120b | 30 | 14,400 | 1M tokens | Excellent | 64K TPM |
| Groq | llama-3.1-8b-instant | 30 | 14,400 | 500K | Good | Bulk queries |
| Groq | llama-prompt-guard-2-22m | 30 | 14,400 | 500K | Specialized | Safety only |
| Mistral | Any model | 2 | ~2,880* | 1B tok/month | Excellent | *RPM-constrained |
| Fireworks.ai | Any model | 10 | 14,400 | — | Good | No CC required |

### Tier 2: Medium Volume (100–1000 RPD per account)

| Provider | Model | RPM | RPD | TPD | Quality | Notes |
|----------|-------|-----|-----|-----|---------|-------|
| Groq | llama-3.3-70b-versatile | 30 | 1,000 | 100K | Very Good | Best quality Groq |
| Groq | llama-4-scout-17b | 30 | 1,000 | 500K | Excellent | Multimodal, 131K ctx |
| Groq | qwen/qwen3-32b | 60 | 1,000 | 500K | Very Good | |
| Groq | kimi-k2-instruct | 60 | 1,000 | 300K | Good | |
| Groq | openai/gpt-oss-120b | 30 | 1,000 | 200K | Excellent | |
| Gemini 2.5 Flash (AI Studio) | gemini-2.5-flash | 10 | 250 | 250K TPM | Excellent | Per PROJECT |
| Gemini Flash-Lite | gemini-flash-lite | 15 | 1,000 | 250K TPM | Good | Fastest Gemini |
| SambaNova | Llama 3.1 8B | 30 | ~2,880* | 200K | Good | *RPM-constrained |
| GitHub Models | Llama 3.3 70B | 15 | 150 | — | Very Good | Free GH account |

### Tier 3: Low Volume (<100 RPD per account)

| Provider | Model | RPM | RPD | TPD | Quality | Notes |
|----------|-------|-----|-----|-----|---------|-------|
| OpenRouter :free | 28 models | 20 | 50* | — | Varies | *per account, NO multi-acct |
| OpenRouter :free | (with $10 credit) | 20 | 1,000 | — | Varies | One-time $10 purchase |
| Cohere (trial) | Command R+ | 20 | ~1,200* | 1K req/month | Very Good | *RPM limit |
| HuggingFace | Various | Varies | ~1,000* | $0.10/month | Good | Inference Providers |
| Gemini 2.5 Pro | gemini-2.5-pro | 5 | 100 | 250K TPM | SOTA | Very limited free |
| NVIDIA NIM | Any | 40 | 1,000 credits | — | Excellent | Credits only, no daily reset |
| GitHub Models | GPT-4o (High tier) | 10 | 50 | 8K in/4K out | SOTA | GitHub account required |
| Cloudflare Workers AI | Llama 3.2, Mistral | N/A | ~10K neurons | — | Good | Neurons ≠ requests |

## Our Current Keys — Calculated Total Capacity

### Groq (5 keys — CRITICAL: check if same org)
If all 5 keys are DIFFERENT organizations:
- llama-3.1-8b: 5 × 14,400 = **72,000 RPD**
- llama-4-scout: 5 × 1,000 = **5,000 RPD**
- llama-3.3-70b: 5 × 1,000 = **5,000 RPD**
If all 5 keys are SAME organization: limits are shared = no multiplication

### OpenRouter (7 keys — NO multiplication, global limits)
- :free without credits: 50 RPD TOTAL (not per key)
- :free with $10 credit on account: 1,000 RPD TOTAL
- 7 keys = 0 benefit unless 7 separate accounts created from scratch
- VERDICT: Our 7 keys on same account = 50 or 1,000 RPD only

### Cerebras (1 key — add more accounts)
- Current: 14,400 RPD (Qwen3-235B), 1M tokens/day
- Each new account: +14,400 RPD, +1M tokens/day
- HIGH PRIORITY: Register 4 more accounts to match HF token count

### HuggingFace (4 tokens — YES multiplication)
- 4 accounts × $0.10/month = $0.40/month free inference credits
- Mainly useful for file downloads (5,000 resolves per 5 min per account)
- For inference: negligible ($0.10 = ~10K tokens at typical pricing)
- API Hub calls: 4 × 1,000 per 5-min = 4,000 per 5-min window

### Google/Gemini (1 key)
- Gemini 2.5 Flash: 250 RPD, 10 RPM
- Gemini Flash-Lite: 1,000 RPD, 15 RPM
- To multiply: create separate GCP projects (each gets own quota)
- HIGH PRIORITY: Create 4 more GCP projects

### Cohere (2 trial keys)
- 2 × 1,000 req/month = 2,000 req/month = ~66 req/day
- Low value for trading floor scale

## Total Daily Capacity Summary (Current Accounts)

| Provider | Account Count | Best Daily Capacity | Best Model Available |
|----------|--------------|--------------------|--------------------|
| Cerebras | 1 | 14,400 req/day | Qwen3-235B (235B MoE) |
| Groq (if 5 orgs) | 5 | 72,000 req/day (8B) | Llama 4 Scout / 8B |
| Groq (if 1 org) | 1 | 14,400 req/day (8B) | Same |
| OpenRouter | 1 account | 50 req/day (free) | 28 models including top-tier |
| HuggingFace | 4 | ~$0.40/mo credits | Varies (inference providers) |
| Google AI Studio | 1 | 1,000 req/day (Flash-Lite) | Gemini 2.5 Flash |
| Cohere | 2 | ~66 req/day | Command R+ |
| Mistral | 0 | — | Large 2 (2 RPM free) |
| SambaNova | 0 | — | Llama 3.1 405B |
| Fireworks.ai | 0 | — | 14,400 RPD free |
| GitHub Models | 0 | — | GPT-4o (50 RPD) |

## TOTAL CURRENT: ~88,000 to 16,000 RPD
(88K if Groq keys = 5 orgs; 16K if Groq keys = 1 org)

## NBA Trading Floor Context
- 5 games/day average NBA season
- 200 agents × 5 calls/agent/day = 1,000 calls/day minimum
- 200 agents × 20 calls/agent/day = 4,000 calls/day full analysis

Even conservative scenario (Groq 1 org): 16,000+ RPD >> 4,000 needed. Capacity is NOT the bottleneck.

## Recommended Additions (Free, No CC)

Priority 1 — Register immediately:
1. Cerebras: 4 more accounts (+57,600 RPD of Qwen3-235B)
2. Mistral: 1 account (+2 RPM free on ALL models including Large)
3. SambaNova: 1 account (+200K tokens/day free)
4. Google AI Studio: Create 4 more projects (+3,000 Flash-Lite RPD)

Priority 2 — With $10 one-time spend:
5. OpenRouter: One $10 credit purchase → 1,000 RPD :free models (28 models)
6. GitHub Models: Free with GitHub account (+150 RPD Llama 3.3 70B)

## Optimal Agent Assignment (200-agent floor)

| Agent Tier | # Agents | Provider | Model | Calls/Day Each | Purpose |
|-----------|---------|----------|-------|---------------|---------|
| Heavy analysis | 10 | Cerebras | Qwen3-235B | 100 | Complex NBA strategy |
| Fast analysis | 50 | Groq | Llama 4 Scout | 20 | Game analysis |
| Bulk processing | 100 | Groq | Llama 3.1 8B | 100 | Feature extraction |
| Long context | 5 | OpenRouter | Qwen3.6+:free | 200 | Full season context |
| Vision/multi | 10 | Gemini | 2.5 Flash | 25 | Chart analysis |
| Benchmark | 5 | Cerebras | GPT-OSS-120B | 50 | Model comparison |
| Political | 20 | Cerebras | Qwen3-235B | 50 | Political alpha |

Total: 200 agents × avg 80 calls/day = 16,000 calls/day — FEASIBLE with current keys

**Why**: Capacity research triggered by trading floor expansion to 200+ agents. Key finding: Groq multi-org is the highest-leverage action (verify 5 keys = 5 orgs). Cerebras new accounts add 14,400 RPD each at top-tier quality.

**How to apply**: Before adding new agent types, check this table. Cerebras is the highest quality-per-call free provider. For bulk low-stakes queries, Groq Llama 8B at 14,400 RPD is the workhorse.
