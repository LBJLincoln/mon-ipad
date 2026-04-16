# Appendix C — Replication Instructions

We release the full experimental stack at the following locations. All
steps below reproduce Full LPSG on either the NBA or political corpus
from a clean environment; ablations (§4.5) are produced by environment
flags documented in C.4.

- **Code:** `github.com/LBJLincoln/mon-ipad` at tag
  `paper/axelrod-cycle2` (commit `df0d0d72c` or later in that branch).
  The two Space apps are embedded at
  `scripts/arena/hf-llm-trading-floor/app.py` (NBA) and
  `scripts/arena/hf-political-trading-floor/app.py` (political).
- **Live Spaces (read-only for non-authors):**
  `huggingface.co/spaces/LBJLincoln26/nba-llm-trading-floor`,
  `huggingface.co/spaces/LBJLincoln26/political-llm-trading-floor`.
- **LLM gateway:** `huggingface.co/spaces/LBJLincoln26/llm-gateway`.
- **Datasets:** NBA 2025–26 regular season schedule + odds bundle in
  `data/nba-agent/full-season-odds.json`; political events in the sister
  repo `github.com/LBJLincoln/nomos-political-alpha` at the same freeze
  commit.
- **Per-day logs (Mech C):** `data/arena/axelrod-log/{nba,political}/`
  after at least one complete full-season run has been pulled from the
  live Space via the `/api/axelrod-log` endpoint.

---

## C.1 Prerequisites

| Requirement | Version used | Notes |
|---|---|---|
| Python | 3.11 | Both Spaces pin 3.11. |
| Node | 20.x | Only required for the optional dashboard replication. |
| Git | 2.40+ | Worktree support is used by the paper branch workflow. |
| HuggingFace account | any | Required to fork the two Spaces. Free CPU hardware is sufficient. |
| Provider API keys | see C.3 | Free tiers cover one full-season run. |

## C.2 Fork the Spaces

1. On `huggingface.co`, duplicate both Spaces to your account:
   `LBJLincoln26/nba-llm-trading-floor` and
   `LBJLincoln26/political-llm-trading-floor`. Select **CPU basic (free)**.
2. Fork the gateway Space `LBJLincoln26/llm-gateway` to your account.
3. Note the resulting URLs (e.g.
   `<username>-nba-llm-trading-floor.hf.space`).

## C.3 Configure Provider Keys

Free-tier keys suffice for a single full-season run. Set the following
as **Space secrets** (not variables) on both forked TF Spaces. Missing
keys cause the corresponding agents to silently revert to the
market-consensus baseline and are logged as `llm_failures`.

| Secret | Source | Notes |
|---|---|---|
| `CEREBRAS_API_KEY` | inference.cerebras.ai | 30 RPM free. |
| `GOOGLE_API_KEY` | aistudio.google.com (key 2) | 14 RPM free; set `thinkingBudget=0` in-code. |
| `MISTRAL_API_KEY` | console.mistral.ai | 20 RPM free tier. |
| `OPENROUTER_API_KEY` | openrouter.ai | Free slice for Nemotron-3-Super-120B. |
| `NOMOS_HF_TOKEN` | huggingface.co/settings/tokens | Used for the self-hosted Phi-3.5 call. |
| `GATEWAY_URL` | `https://<username>-llm-gateway.hf.space` | Point to your fork of the gateway Space. |

## C.4 Run a Baseline

Each Space exposes a FastAPI control surface. From the command line:

```bash
# Full LPSG (default — all four mechanisms active)
curl -X POST https://<username>-nba-llm-trading-floor.hf.space/api/run

# Poll status until days_processed == days_total (typically 2–3 h with
# intra-day parallelism enabled; see B.7)
watch -n 30 'curl -s https://<username>-nba-llm-trading-floor.hf.space/api/status \
    | python3 -c "import sys,json; d=json.load(sys.stdin); \
      print(d.get(\"days_processed\"), \"/\", d.get(\"days_total\"))"'
```

To run an ablation (§4.5, Table 3), set the corresponding Space variable
before starting the run. These flags are read once at the top of
`run_experiment()`:

| Variable | Value | Effect |
|---|---|---|
| `LPSG_DISABLE_SRR` | `1` | No sacrificial reallocation (the `No-SRR` ablation). |
| `LPSG_DISABLE_CK` | `1` | Common-knowledge broadcast replaced by empty string (the `No-CK` ablation). |
| `LPSG_DISABLE_PACTS` | `1` | Coalition proposals ignored; reputation tracking disabled (the `No-Pacts` ablation). |
| `LPSG_FIXED_ARCHETYPE` | `1` | Archetypes pinned at day-0 assignment (the `Fixed-ensemble` baseline). |
| `LPSG_SINGLE_TRADER` | `<tid>` | Run only the named trader (the `Single-best` baseline). |

After the run completes, pull the Mech-C log bundle:

```bash
# From a VM with the mon-ipad repo checked out:
bash scripts/pull-axelrod-log.sh
ls data/arena/axelrod-log/nba/  # one day-NNN.jsonl per day
```

## C.5 Produce the Paper Tables

With the logs pulled, the analysis script (in progress; will be
committed at `scripts/paper/analyze-axelrod-run.py`) computes:

- Table 4 (§5.1 main result): eight configurations × six metrics.
- Figure 1 (§5.2): SRR reassignment frequency vs day.
- Figure 2 (§5.3): common-knowledge ablation time series.
- Figure 3 (§5.4): pact density evolution.
- Figure 4 (§5.5): reliability diagrams per configuration.
- Table 5 (§5.7): between-seed variance ($n = 5$).

The analysis script reads only the per-day JSONL files; no live Space
access required for post-hoc analysis.

## C.6 Expected Cost and Wall-Clock

Measured 2026-04-16 with intra-day parallelism enabled (B.7):

| Configuration | Wall-clock | Provider cost | Notes |
|---|---|---|---|
| Full LPSG, one seed | 2–3 h | $\leq \$0.40$ | Free tiers cover the entire run. |
| Six ablations × two corpora × five seeds | 70 full runs | $\leq \$600$ | Matches §7.7. |
| Single-seed full corpora pair | 4–6 h | $\leq \$1$ | Sufficient for "does the framework run at all" sanity. |

Wall-clock scales roughly inversely with provider count: fewer providers
mean more agents contend for the same rate-limit bucket.

## C.7 Known Failure Modes

| Symptom | Diagnosis | Fix |
|---|---|---|
| All Gemini agents return empty. | `thinkingBudget` not set. | See B.5. |
| All OpenRouter free-tier models 429. | Daily free-tier exhausted. | Wait 24 h or switch to paid tier; falls back to direct provider via gateway. |
| `days_processed` stalls at 0 for > 5 min. | Run thread crashed before first checkpoint. | Check `/api/logs`; restart via `/api/reset` then `/api/run`. |
| `cooperation_pacts_count` stays at 0 past day 30. | Agents are not proposing pacts. | Verify `AXELROD_CANON` is prepended (`/api/status → axelrod_canon_active == true`). |
| Ambiguity $A(t)$ is constant near 0. | Agents converged on near-identical outputs. | Expected for `Fixed-ensemble` ablation; unexpected for Full LPSG — check SRR assignments are rotating. |
| Endpoint `/api/axelrod-log` returns `n_days: 0` after a full run. | HF Space ephemeral `/tmp` wiped on rebuild before logs were pulled. | Run again with the puller cron active (`scripts/pull-axelrod-log.sh` at 20-min cadence). |

## C.8 Citation

If you use this code or the accompanying datasets, please cite the
paper (§10, main text) and note the git commit at which your run was
produced. The `/api/status` response includes the Space commit hash so
that downstream logs are self-identifying.
