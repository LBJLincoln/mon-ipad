---
name: Claude Code Karpathy Plugins & Ecosystem (April 2026)
description: What exists vs. gap analysis. Real patterns: autoresearch universal skill, forrestchang CLAUDE.md, wiki-skills. NO Brier-specific plugin exists yet.
type: project
---

# Claude Code Karpathy Plugins Ecosystem (April 2026)

## What EXISTS (Real, Shipped, In Use)

### 1. **karpathy/autoresearch** (Official)
- **GitHub**: https://github.com/karpathy/autoresearch
- **Pattern**: 630-line Python script. Modify train.py → 5min train → measure val_bpb → keep/revert → repeat
- **Constraint-driven**: Fixed budget, single metric, one file to edit, git as memory
- **Results**: 700 experiments in 2 days, 20 optimizations discovered (11% speedup on larger models)
- **NOT A CLAUDE CODE PLUGIN** — standalone Python, but the *pattern* is what Claude Code skill devs adapted

### 2. **uditgoenka/autoresearch** (Claude Code Skill)
- **GitHub**: https://github.com/uditgoenka/autoresearch
- **Type**: Universal Claude Code skill with 10 subcommands
- **Core Loop**: Review state → Select change → Modify (1x) → Commit → Verify → Evaluate → Log → Repeat
- **Commands**:
  - `/autoresearch` — core improvement loop
  - `/autoresearch:plan` — goal→config wizard
  - `/autoresearch:debug`, `:fix`, `:learn`, `:predict`, `:reason`, `:scenario`
- **State**: `.autoresearch/` stores current prompt, best prompt, loop state (JSON), results.jsonl
- **Metric**: Binary yes/no evaluation (4-6 questions), deterministic, fixed validation items
- **Platforms**: Claude Code, OpenCode, Codex (syntax variants)

### 3. **forrestchang/andrej-karpathy-skills** (CLAUDE.md Pattern)
- **GitHub**: https://github.com/forrestchang/andrej-karpathy-skills
- **Type**: CLAUDE.md file (not a traditional plugin, but installable as one)
- **Philosophy**: "Goal-driven execution" — tell agent success criteria, not what to do
- **Installable**: Via Claude Code plugin marketplace
- **Focus**: LLM coding pitfalls (overcomplication, unsurgical changes, unverifiable success)

### 4. **kfchou/wiki-skills** (Karpathy Wiki Pattern)
- **GitHub**: https://github.com/kfchou/wiki-skills
- **Pattern**: Persistent LLM-maintained knowledge base (from Karpathy's llm-wiki gist)
- **Use case**: Compounding knowledge base that improves over time
- **Implementation**: Claude Code skill that auto-updates markdown wiki

### 5. **Hyperparameter Tuning Skills**
- **Implementations**: Optuna, scikit-learn grid/random/Bayesian search
- **Available**: mcpmarket.com, Tessl registry
- **NOT Brier-specific** — generic ML optimization

### 6. **Market Mechanics & Betting Skill**
- **Purpose**: Kelly Criterion, Brier score for calibration, crowd wisdom
- **Metric**: Brier score used for validation
- **Limitation**: Generic betting framework, not domain-specific (no NBA/sports specialization)

## What DOES NOT EXIST (Gap Analysis)

### 🚨 **No Brier-specific autoresearch plugin**
- Autoresearch exists generically (uditgoenka), but no variant optimized for Brier score
- No plugin that auto-iterates: "mutate feature → train → measure Brier → keep if Brier improves"
- Market Mechanics skill mentions Brier but doesn't implement autonomous Brier-driven evolution

### 🚨 **No sports-ML-specific skill**
- Sports prediction plugins exist but are generic (no feature engineering domain knowledge)
- No integration with live odds APIs, game context, player stats
- No plugin tuned for NBA/NFL/betting calibration

### 🚨 **No GPU-aware autoresearch**
- uditgoenka/autoresearch works on single machines
- No variant that distributes to HF Spaces, Kaggle, Colab, or manages multi-GPU islands
- Karpathy's autoresearch assumes single GPU + 5min budget (not multi-island fleet)

### 🚨 **No feature-engineering-aware skill**
- Autoresearch modifies config/prompt, not feature engineering
- No plugin for: mutate features → evaluate impact → keep winners
- Our feature engine (v3.1-54cat, 7213 raw features) has no Claude Code plugin

## Why This Matters for Nomos42

Our `/karpathy-loop` skill is **research-only** (calls research agents via Claude Code).
Our actual **iteration loop** runs **offline on Kaggle** via `scripts/kaggle/nba_karpathy_loop.py`.

**Gap**: We need a Claude Code skill that:
1. ✅ Infers current Brier from recent runs
2. ✅ Proposes mutations (feature add/drop, GA params, ensemble weights)
3. ✅ Validates locally (fast backtest on hold-out)
4. ✅ Commits if Brier improves
5. ✅ Distributes to HF islands for full training
6. ❌ Currently: We do 1-2 manually, rest on Kaggle

## Implementation Recommendation

**Build: `/karpathy-nba` skill** (7-10 days)

1. **Inherit structure** from uditgoenka/autoresearch (8-step loop)
2. **Specialize** for Brier metric:
   - Read latest Brier from `data/nba-agent/backtest-results.json`
   - Store `.karpathy-nba/` with: current config, best config, loop state, brier_log.jsonl
3. **Feature mutations** not prompt mutations:
   - Use our feature engine to propose adds/drops
   - Quick validation via cached CV split (5min on VM)
4. **Distribute to fleet**:
   - If local Brier improves, push config to HF Spaces S10-S17 via HF API
   - Poll results every 1h (is 0.2min old Brier beaten?)
5. **Commands**:
   - `/karpathy-nba` — run loop once
   - `/karpathy-nba:plan` — preview next mutation
   - `/karpathy-nba:ship` — distribute to all islands
   - `/karpathy-nba:status` — show fleet progress

**Expected impact**: -0.001 to -0.003 Brier (1-3 improvements per day discovered autonomously)

---

## References

- [Karpathy AutoResearch](https://github.com/karpathy/autoresearch) — canonical pattern
- [Claude Autoresearch Skill](https://github.com/uditgoenka/autoresearch) — universal implementation
- [Karpathy Skills CLAUDE.md](https://github.com/forrestchang/andrej-karpathy-skills) — coding pitfalls
- [Wiki Skills](https://github.com/kfchou/wiki-skills) — knowledge compounding pattern
- [Official Claude Plugins](https://github.com/anthropics/claude-plugins-official) — marketplace
- [Market Mechanics Betting Skill](https://mcpmarket.com/tools/skills/market-mechanics-betting) — Brier calibration (generic)
