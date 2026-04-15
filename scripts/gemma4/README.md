# Gemma4 Cross-Repo Helper

Self-hosted Phi-3.5 (T12 "gemma4-selfhost" in the trading-floor roster)
running as an autonomous code reviewer across the Nomos42 org.

## What it does

Every 6 hours at :45 UTC, a GitHub Action (`.github/workflows/gemma4-cross-repo-helper.yml`)
checks out 4 repos and asks the self-host Phi-3.5 Space
(`Nomos42/nomos42-llm-cpu`) for **one concrete improvement per repo**.

1. Checks out `mon-ipad`, `nomos-dashboard`, `nomos-nba-agent`, `nomos-political-alpha`
2. For each repo, runs `cross-repo-helper.py`, which:
   - Reads `git log --oneline -20`
   - Reads up to 2 recently-modified files (truncated to 6000 chars)
   - Calls the self-host Space (`/chat/completions`, OpenAI-compatible)
   - Writes the suggestion to `data/gemma4-helper/<repo>-<date>.md`
3. Commits and pushes the `data/gemma4-helper/` updates to `mon-ipad`

Self-imposed limits: **3 suggestions max per run**, suggestion-only,
never auto-merges, never touches production code.

## Why Phi-3.5 self-host?

- Free / no quota (CPU GGUF, our own Space)
- Slow (~5-8s/call) → only used for **routine audits**, never critical paths
- Unlimited calls → safe to run every 6h across 4 repos without hitting
  Cerebras / Gemini / OpenRouter rate limits

## Secrets needed

Add these as GitHub repo secrets on `mon-ipad`:

| Secret | Purpose |
| --- | --- |
| `NOMOS_HF_TOKEN` | HF token with read access to `Nomos42/nomos42-llm-cpu` (optional — Space is public, call works without) |
| `NOMOS_CROSSREPO_PAT` | Classic GitHub PAT with `repo` scope on the org. Used to check out the three sibling repos. Falls back to `HF_TOKEN_GH`, then `GITHUB_TOKEN` (which only works for `mon-ipad` itself). |

If you want the helper to remain fully functional without `NOMOS_CROSSREPO_PAT`,
the workflow tolerates missing secondary checkouts — it just skips those repos
and reports for `mon-ipad` only.

## Output

Each run writes up to 4 files like:

```
data/gemma4-helper/
  mon-ipad-2026-04-15.md
  nomos-dashboard-2026-04-15.md
  nomos-nba-agent-2026-04-15.md
  nomos-political-alpha-2026-04-15.md
```

Each file has a header (date, model, latency, source URL) plus a 4-section
suggestion in the format `TITLE / WHY / WHAT / RISK`.

## Manually test locally

```bash
NOMOS_HF_TOKEN=$HF_TOKEN_3 \
python3 scripts/gemma4/cross-repo-helper.py \
  --repo . \
  --name mon-ipad \
  --out data/gemma4-helper
```

## Disable

Either:

- Comment out the `schedule:` block in `.github/workflows/gemma4-cross-repo-helper.yml`
- Delete the workflow file entirely
- Or keep it runnable on-demand only via `workflow_dispatch`

The helper is **idempotent**: re-running on the same day overwrites the
per-repo file. No state is accumulated outside `data/gemma4-helper/`.

## Scope boundaries (what it will NEVER do)

- Never edit source code in any repo
- Never open PRs automatically
- Never force-push
- Never call paid LLM APIs
- Never exceed 3 suggestions per run (enforced by the 4-repo checkout + early-exit)
