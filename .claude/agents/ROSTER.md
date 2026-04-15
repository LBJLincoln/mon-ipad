# Nomos42 Sub-agent Roster — v2 (2026-04-15)

**Principle:** one agent, one domain, one repo, one cred set, one cron slot.
No overlap. Every agent knows exactly which HF account / API key to use and
which repo it can write to. Orchestrator dispatches — never duplicates.

## Account Layout (4 HF accounts × ≤8 Spaces = 32 slots)

| Account | Token env | Role | Spaces |
|---|---|---|---|
| **LBJLincoln26** | `HF_TOKEN_NBA` | 🏀 NBA evolution | S10 S11 S12 S13 S14 S15 S16 S17 |
| **LBJLincoln** | `HF_TOKEN` | 🗳 Political evolution | P1 P2 P3 P4 P5 P6 P7 P8 |
| **Nomos42** | `HF_TOKEN_LLM` | 🧠 LLM + TFs + pixel | llm-gateway, gemma4-chat, qwen35-chat, cpu-gemma4, nba-TF, political-TF, pixel-world, langfuse |
| **TESTforge42** | `HF_TOKEN_COUNCILS` | ⚙️ Councils + evo overflow | D1 D2 D3 D4 D5 D6 D7 D8 (D9 → GH Action) |

## New agent roster (10 agents)

| # | Agent | Replaces | Repo | Cred env | Cadence |
|---|---|---|---|---|---|
| 1 | **nomos-brain** | `nba-brain` | mon-ipad | all HF tokens (read-only) | `:00` every 4h |
| 2 | **nomos-hoops** | — (split from `evolution-optimizer`) | mon-ipad | `HF_TOKEN_NBA` | `:10` every 4h |
| 3 | **nomos-alpha** | — (new) | nomos-political-alpha | `HF_TOKEN` | `:15` every 4h |
| 4 | **nomos-llm** | — (new) | mon-ipad | `HF_TOKEN_LLM` | `:20` every 6h |
| 5 | **nomos-forge** | — (split from `nba-brain`) | mon-ipad | `HF_TOKEN_COUNCILS` | `:25` every 4h |
| 6 | **nomos-tape** | `market-analyst` | nomos-nba-agent | `ODDS_API_KEY` | every 30 min |
| 7 | **nomos-wire** | — (new) | nomos-nba-agent | `BOT_TOKEN_NBA`, `STRIPE_SECRET_KEY` | daily 18:00 UTC |
| 8 | **nomos-scout** | merges `karpathy-researcher` + `research-analyst` + `repo-scout` | mon-ipad | `BRAVE_API_KEY`, `FIRECRAWL_API_KEY`, `EXA_API_KEY` | daily 06:00 UTC |
| 9 | **nomos-lab** | merges `feature-engineer` + `karpathy-feature-eng` | mon-ipad | `MISTRAL_API_KEY`, `GOOGLE_API_KEY` | every 12h |
| 10 | **nomos-pay** | — (new, deadline-critical) | nomos-dashboard | `STRIPE_SECRET_KEY`, `WHOP_API_KEY`, `LEMON_SQUEEZY_API_KEY` | daily 09:00 UTC |

## Cron schedule (aggregated)

```
*/30  nomos-tape               (every 30 min)
0 */4 nomos-brain           (:00 every 4h)
10 */4 nomos-hoops               (:10 every 4h)
15 */4 nomos-alpha         (:15 every 4h)
20 */6 nomos-llm               (:20 every 6h)
25 */4 nomos-forge                (:25 every 4h)
0 */12 nomos-lab                 (00:00 and 12:00 UTC)
0 6 * nomos-scout               (06:00 UTC daily)
0 9 * nomos-pay             (09:00 UTC daily)
0 18 * nomos-wire             (18:00 UTC daily)
```

## Session-start bootstrap

Every Claude Code session: nomos-brain runs once via
`.claude/settings.json` SessionStart hook to emit a health snapshot
(which agents last ran / last failed / what's stale).

## Retired agents (migrate + delete)

- `nba-brain` → split into `nomos-brain` + `nomos-hoops` + `nomos-forge`
- `evolution-optimizer` → absorbed into `nomos-hoops` + `nomos-alpha`
- `karpathy-researcher`, `research-analyst`, `repo-scout` → merged into `nomos-scout`
- `feature-engineer`, `karpathy-feature-eng` → merged into `nomos-lab`
- `market-analyst` → renamed `nomos-tape`

## Cred mapping per agent

Each agent's YAML frontmatter lists `env:` with the exact keys it needs.
Never more, never fewer. If an agent tries to read a cred it doesn't
declare, the wrapper script rejects it.
