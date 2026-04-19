# Intraday Trading Floor — Routing Matrix (4 HF Accounts + Codespaces + Modal)

**Status:** 2026-04-19, drafted by resumed CLI session after crash.
**Scope:** 6 self-hosted LLMs backing the 6 ITF personas, load-balanced across
4 Hugging Face accounts, with GitHub Codespaces and Modal as burst compute.

## Why this migration matters

All 5 current self-hosted LLM Spaces live on the **Nomos42** account. That one
account now carries:

- 13 NBA evolution islands (partial)
- 5 self-host LLM Spaces (qwen3-4b, gemma2-2b, qwen25-05b, llama32-1b, nomos42-llm-cpu)
- Nomos42/pixel-world + Nomos42/langfuse

One HF quota exhaustion = every TF agent that falls back to `selfhost:*` fails.
Distributing across 4 accounts removes that single point of failure.

## Target Routing Matrix (ITF)

| Persona      | Model                    | Current HF account | Target HF account | Space name               | Tier | Fallback                 |
|--------------|--------------------------|--------------------|-------------------|--------------------------|------|--------------------------|
| scalper-1    | selfhost:qwen3-0.6b      | Nomos42            | **Nomos42**       | qwen25-05b-cpu           | S    | selfhost:gemma-3-4b      |
| momentum-1   | selfhost:gemma-3-4b      | Nomos42            | **LBJLincoln**    | gemma2-2b-cpu-lbj        | M    | selfhost:qwen3-4b        |
| mean-rev-1   | selfhost:qwen3-4b        | Nomos42            | **LBJLincoln26**  | qwen3-4b-cpu-lbj26       | L    | selfhost:gemma-3-4b      |
| breakout-1   | selfhost:dolphin3-l32-3b | Nomos42            | **TESTforge42**   | llama32-1b-cpu-tf42      | M    | selfhost:qwen3-4b        |
| pairs-1      | selfhost:phi-4-mini      | Nomos42            | **LBJLincoln**    | nomos42-llm-cpu-lbj      | M    | selfhost:dolphin3-l32-3b |
| vol-1        | selfhost:cpu-gemma4      | Nomos42            | **TESTforge42**   | nomos-cpu-gemma4-tf42    | M    | selfhost:gemma-3-4b      |

**Account distribution after migration:**

- Nomos42      → 1 selfhost (qwen25-05b-cpu, scalper)
- LBJLincoln   → 2 selfhost (gemma2-2b-cpu-lbj, nomos42-llm-cpu-lbj)
- LBJLincoln26 → 1 selfhost (qwen3-4b-cpu-lbj26)
- TESTforge42  → 2 selfhost (llama32-1b-cpu-tf42, nomos-cpu-gemma4-tf42)

## Runtime fallback ladder

Each ITF tick:

1. **Primary:** the persona's `selfhost:*` model on its target account.
2. **Fallback-1 (selfhost):** tier-matched selfhost on a *different* account.
3. **Burst-GPU (Modal):** if both selfhost are unhealthy AND market-hours critical,
   route to `modal://nomos42-llm-gpu` (already provisioned via
   `scripts/gpu-burst/modal-burst.py`). Max 4 calls/tick across the fleet.
4. **Codespaces keepalive:** a 4-core Codespaces runner (free 120 hr/month)
   wakes dead HF Spaces asynchronously while the tick proceeds. Launched via
   `scripts/codespaces/wake-dead-selfhost.yml` (to be added).
5. **Cloud (absolute last):** only if all 6 selfhost + Modal are down AND we're
   about to skip the tick — temporary degraded route to cerebras/google.
   Audit log flags `degraded=true`.

## Codespaces runner role

- Free tier: 120 core-hours/month (4-core, 15 GB RAM) — enough to run `app.py`
  24/7 as a loop watcher that:
    a. Polls `/api/status` on each of the 6 self-host Spaces every 5 min.
    b. If any Space returns 5xx for > 15 min, POSTs the HF "restart_space"
       endpoint (using NOMOS_HF_TOKEN scoped to the owning account).
    c. Writes health log to `data/intraday/selfhost-health.jsonl`.
- Start script: `.devcontainer/intraday-watchdog.sh` (to be added).

## Modal role

- GPU burst (A10G / L40S) for 30-minute research tasks, NOT intraday real-time.
- Already used by ZeroGPU and Lightning for evolution island bursts.
- ITF usage capped at 1 request/hour/persona to respect Modal free tier credits.

## Migration steps (not yet executed)

1. Duplicate each HF Space to its target account via `HfApi.duplicate_space`.
2. Update `scripts/arena/hf-llm-gateway/app.py` MODELS dict with new URLs +
   `key_env` mapping to that account's `HF_TOKEN_*` secret.
3. Update `scripts/arena/hf-intraday-trading-floor/personas.py` `hf_account`
   + `hf_space` fields (cosmetic — actual route follows gateway URL).
4. Smoke-test each migrated Space via `/v1/chat/completions` before retiring
   the original.
5. Delete the originals only after 48 hrs stable on the new location.

## Cost model

- 4 HF accounts × ∞ free CPU quota = zero marginal cost.
- Codespaces 120 hr/mo free tier — watchdog loop is lightweight (stays under).
- Modal free credits ($30/mo) — ITF usage < 5% of envelope.
- Cloud LLMs (Cerebras/Google/Mistral/OR) — ZERO in normal operation.

## Success criteria

- 5 selfhost Spaces on Nomos42 → 1 Space ≤ one account quota incident/week.
- ITF tick success rate ≥ 95% during market hours without touching cloud.
- Modal budget usage ≤ 5% of monthly credits.
