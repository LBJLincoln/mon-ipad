# Bottleneck Actions Playbook (Operator-ready)

Updated: 2026-02-27T16:00:00Z

## Goal
Give Alexis a fast, practical list of actions to unblock throughput/reliability without deep debugging.

## 1) API Throughput Bottlenecks (LLM)
### Symptoms
- 429 rate limits
- latency spikes
- sudden drop in successful responses

### Fast actions you can do
1. Create/add new provider keys (OpenRouter, Groq) and place them in `.env.local`.
2. Increase key pool variables (`OPENROUTER_KEY_*`, `GROQ_API_KEY_*`).
3. Re-run key pool discovery + health checks.
4. Switch heavy pipelines to faster models temporarily.

### Impact
- Immediate req/min increase
- Better resilience under parallel load

## 2) Compute Bottlenecks (HF Space / workers)
### Symptoms
- timeouts on Standard/Graph
- webhook 500 under concurrency

### Fast actions you can do
1. Start additional HF Spaces (already using 10 when available).
2. Increase worker count only after passing smoke tests.
3. Reduce concurrency per unstable pipeline, keep high for stable ones.
4. Add/scale Google Run worker services for burst tasks.

### Impact
- Better stability and sustained throughput

## 3) Activation / webhook Bottlenecks
### Symptoms
- 404 on webhook path
- workflow not started
- credentials not loaded

### Fast actions you can do
1. Re-activate workflows with launch/restore scripts.
2. Verify webhook IDs did not drift after imports.
3. Rebind credentials and re-test with 1-question smoke.

## 4) Data bottlenecks (ingestion/enrichment)
### Symptoms
- ingest 500 errors
- enrichment partial outputs

### Fast actions you can do
1. Run ingestion on Codespaces/GH Actions (not only HF).
2. Split datasets by sector/type and process in parallel batches.
3. Keep garbage outputs archived to rag-storage autosync for forensics.

## 5) What to prioritize first (operator order)
1. Restore red pipelines (health)
2. Restore correctness (golden checks)
3. Increase throughput safely (workers/keys)
4. Scale expensive experiments

## 6) Toward full mathematical autofix (target architecture)
Yes, target is: **auto-detect → auto-fix code/config → auto-validate** with minimal CLI intervention.

Required components:
- Signature engine (OpenRouter/webhook/n8n/db errors)
- Confidence-scored fix planner
- Auto-apply safe patches
- Automatic rollback on regression
- Golden-based acceptance gate

This means:
- CLI remains for oversight/emergency,
- normal corrections become autonomous by policy.
