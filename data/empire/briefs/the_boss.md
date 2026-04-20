# THE_BOSS — Empire Brief
_Generated 2026-04-20T09:27:49Z_

**Mission:** Decide which agents wake next cycle; dispatch not implement.
**Focus:** all

## State This Agent Must Know

### Ten Optimization Points (strategic)
- **1.** Close the loop: every post-mortem → overrides.json → HF deploy within 24h — *Wire prompt_mutator to run nightly; add tf_postmortem as pre-hook*
- **2.** Own your silence: every fallback path must emit a traceable bet — *Uniform-fallback emitter (done on 3/4 TFs) — finish on ITF*
- **3.** Diversify the selfhost fleet across all 4 HF accounts — *Migrate Nomos42's 3 dead selfhost: routes to TESTforge42 or LBJLincoln*
- **4.** Validate menu visibility in prompt bytes, not prompt intent — *Unit-test _build_prompt covers every asset class after every persona add*
- **5.** Enforce structural divergence by rule, not advice — *Hard-exclude top-ranked consensus category per agent (prompt_mutator rule lockstep_v2)*
- **6.** Every TF must define its 'walk-forward equivalent' before celebrating WR — *INTERNAL_AFFAIRS already runs this — extend to auto-revert overrides that violate*
- **7.** Port winners across TFs — don't reinvent architectures — *Next port: Polymarket TF (queued in memory) inherits PQTF strategy ladder + POL intel*
- **8.** Treat free-tier quotas as a resource to allocate, not a constraint to hit — *Quarterly 'slot audit' — is every Space earning its concurrent cap?*
- **9.** Intelligent monitor > LLM ping-test — *Retire `keepalive-spaces.sh` for TF Spaces, keep only for static assets*
- **10.** The empire is the ledger — logs compound into edge — *Regen data/empire/MASTER.md nightly @ 04:00 UTC; commit; distribute brief per agent*
### Today's Go/No-Go
- NBA fresh reset (day 0) — let it cook 24h before intervention
- POL prompt_v4 active — check category diversity at :13 monitor cycle
- PQTF paused, preserve
- ITF live mode — watch broker_401 rate, should be 0

## Your Slice of The Empire Ledger
- Full ledger: `data/empire/MASTER.md`
- Machine-readable: `data/empire/MASTER_DATA.json`
- Scorecard: `data/empire/strategy-scorecard.json`

## Your Next Moves (until next empire regen)
1. Read your slice above + full MASTER.md scorecard (sections 2-3)
2. Check `data/ops/tf-intel-summary.md` for 3-min-fresh alerts in your domain
3. Action one concrete fix; update MEMORY.md with the lesson