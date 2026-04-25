# Failing-Agents Diagnostic — 2026-04-25

**Generated**: post-reset deep-audit synthesis (NBA 80d, POL 36d, ITF live, PQTF 50d frozen).
**Source data**: `data/audit/per-agent-deep-{tf}-2026-04-25.json` + ITF live `/api/status`.
**Reset cutoff**: `2026-04-25T08:00:00Z` for NBA+POL — pre-fix data excluded.

## TL;DR — where the bleeding is

| TF | n_agents | profitable | break-even | bleeding | catastrophic |
|---|---:|---:|---:|---:|---:|
| **NBA** | 17 | 0 | 2 (-3%) | 10 (-10% to -50%) | 5 (-74%) |
| **POL** | 17 | 11 | 2 | 4 (-9% to -24%) | 0 |
| **PQTF** ⛔frozen | 6 | 4 (huge winners) | 0 | 2 (small) | 0 |
| **ITF** live | 17 | 12 | 0 | 3 | 2 (loss > seed) |

NBA is the worst — every agent is losing post-reset. POL is healthy (11/17 profitable). PQTF preserves $602K artifact across mistral-large/medium/nemo/gemini-anl. ITF was just unblocked at the executor layer (bracket-DTBP + cross-agent collision); needs days, not minutes, to read result.

---

## NBA — every agent is losing post-reset (80 days)

### Catastrophic bleeders (-74%) — share root cause

| agent | days_active | bets | bankroll | top_categories |
|---|---:|---:|---|---|
| `mistral-ministral` | 18/80 | 32 | $96→$24 | `pp_steals_star1_away`×5, `pp_blocks_star3_home`×2 |
| `mistral-nemo` | 19/80 | 32 | $96→$25 | `pp_steals_star1_away`×6, `pp_steals_star1_home`×3 |
| `mistral-small` | 37/80 | 40 | $98→$25 | `pp_steals_star1_away`×3, `alt_spread_home_minus3`×2 |
| `selfhost-qwen06` | 19/80 | 34 | $94→$24 | `pp_steals_star2_away`×3, `pp_threes_role2_home`×2 |
| `nemotron-120b` | 16/80 | 31 | $94→$24 | `pp_steals_star1_home`×3, `pp_steals_star1_away`×3 |

**Common pattern**: all five over-trade `pp_steals_*` and `pp_threes_*` prop bets at universal `odds=1.91` (=parlay deathline), edge=11.1% (= the LLM's lazy default), 0% W-rate cluster. Read any per-agent file (e.g. `data/audit/per-agent-deep/nba/mistral-small.md`) and you'll see the same template:

> "X averages Y blocks/steals; market line implies Z; **edge 11.1%**"

The model is hallucinating the same edge number across totally different game contexts. That's a calibration disaster — the rationale is post-hoc decoration, not a signal.

### Mid-tier bleeders (-30% to -50%)
- `mistral-large` $102→$55 (-45.7%) — 14 bets in 11 days, mostly `pp_steals_*`
- `qwen-quant` $102→$65 (-36.6%) — 17 bets, slightly more variety
- `selfhost-qwen4b` $105→$72 (-31.4%) — `ml_home`×2, `ml_away`×2 — at least different categories
- `qwen-arb` $100→$69 (-30.8%) — only 4 bets but bad timing

### Best NBA agents (still losing, but defensively)
- `llama-contra` $100→$97 (-3.2%) — only 2 bets, 50% W. **Disciplined PASS strategy.**
- `nvidia-llama70` $100→$97 (-3.2%) — only `ml_home`/`ml_away`, no props.

### Why everyone's losing
The post-reset data has 80 days but agents only traded 16-37 days each. Their "best" bets at 1.91 odds need 52% W-rate to break even — fleet is hitting <30%. The 5 worst all converged on same prop universe with same hallucinated edge.

---

## POL — healthy (11/17 profitable)

### Winners
| agent | days_active | bets | bankroll | thesis_pattern |
|---|---:|---:|---|---|
| `llama-contra` | 32/36 | 90 | $100→$116 (+16%) | sector-rotation contrarian |
| `qwen-quant` | 28/36 | 107 | $100→$111 (+11%) | regulatory-delta quant |
| `mistral-medium` | 11/36 | 18 | $100→$107 (+7%) | low-volume diversified |
| `mistral-nemo` | 5/36 | 9 | $100→$107 (+7%) | aggressive but selective |

### POL bleeders (small, still recoverable)
- `gemini-anl` $100→$76 (-24.4%) — 64 bets, narrative-heavy theses on insider_trade
- `qwen-arb` $100→$77 (-22.7%) — 82 bets (this is the agent that hit $10K pre-reset; still has the pattern but RNG against it now)
- `gemini-tact` $100→$79 (-20.8%) — high volume, low conviction

POL fleet doctrine (v5_restored: non-consensus mandate ≥3 sectors/day) is working — that's why most agents are profitable.

---

## PQTF — frozen $602K artifact

| agent | sessions_active | positions | start | end | LLM |
|---|---:|---:|---:|---:|---|
| `mistral-large` | 50 | 505 | $100 | **$244,050** | mistral:large |
| `mistral-medium` | 50 | 497 | $100 | $154,566 | mistral:medium |
| `mistral-nemo` | 50 | 266 | $100 | $120,298 | mistral:nemo |
| `gemini-anl` | 25 | 87 | $100 | $83,208 | gemini |

`reasoning_template` distribution: mean-reversion + momentum + IV-crush on weekly options at strike ±1% with tte_days=2-5. PQTF's win formula = option leverage × disciplined holding period. ITF should mirror this; the `mistral:large` routing on iv-crush-1 / options-1 already does.

`llama-contra` $100→$94 (only 2 sessions) and `qwen-quant` $100→$138 (3 sessions) — sample too small.

---

## ITF — just unblocked, watch for next 24h

**Live state** (post round-2 restart, tick=3 fresh):
- 17 agents seeded ~$5857 (= $100,917 equity / 17)
- LLM leaderboard:
  - `mistral:large` $39,538 across 5 agents (iv-crush, mean-rev, momentum, options, vol)
  - `mistral:medium` $31,444 across 4 agents (crypto-whale, leveraged-momentum, pairs, scalper)
  - `cerebras:qwen-3-235b` $22,770 across 5 agents

**Today's wild swings** (tick 1-2, pre-round-2 fix):
- TOP: `news-catalyst-1` +$2K, `iv-crush-1` +$1.8K, `options-1` +$1.5K
- BOTTOM: `breakdown-1` -$13K (loss > seed via short rally), `crypto-whale-1` -$8K

**Two layers of structural fix shipped today**:
1. ✅ `ITF_PREFER_NON_BRACKET=1` — equity orders use simple market+integer-qty, regt BP not DTBP. Eliminates 40310000 "insufficient day trading buying power" errors.
2. ✅ `cross_agent_collision_skip` — when any other agent has opposite-side position on same ticker, skip clean. Eliminates "insufficient qty available for order" cascade (was 7/tick).

Live `/api/decisions` is in-memory, resets each restart — proper measurement requires letting it run 4-6h then re-running `per_agent_deep_audit.py --tf itf`.

---

## Action priority (highest leverage)

1. **NBA** — 5 catastrophic agents share single root cause: hallucinated `edge=11.1%` on prop bets. Fix at PROMPT layer: instruct LLM that edge values are continuous, not categorical. Or at ENGINE layer: reject any bet whose edge matches `0.10n` exactly across 3+ different games (anti-template guard).
2. **NBA** — implement `_FROZEN_BELOW_USD=$30` engine-level circuit breaker: agents below threshold emit forced-PASS regardless of LLM output. Currently the 0.01 Kelly cap doesn't stop volume bleed.
3. **POL** — stay the course. Fleet doctrine is working. Tighten `gemini-anl` / `gemini-tact` next refresh cycle if drawdown deepens.
4. **PQTF** — preserve forever. Resist any "improvement". Do NOT factory_reboot. The $244K mistral-large run is the proof everyone needs.
5. **ITF** — let round-2 fix run 24h, re-audit. If short-collision skips drive divert pool > 50% of attempts, add a per-ticker fleet allocation lock (one agent per direction per ticker).

## Dashboard surface

All forensic reports now ship to `https://nomosdashboard.vercel.app/tf-analytics/audit/`:
- `per-agent-deep-{tf}-latest.md` — rollup activity table per TF
- `per-game-deep-{tf}-latest.md` — cross-agent matrix per (date, game/event), last 14 dates
- `per-agent-deep/{tf}/{agent}.md` × 51 files — full narrative trail per agent (every bet + rationale across all days)
- `failing-agents-diagnostic-2026-04-25.md` — this report
