---
name: Claude Code Karpathy Skills & Autoresearch Ecosystem
description: Official and community Claude Code skills implementing Karpathy autoresearch pattern (no official skill yet, but 3 active projects + Andrej Karpathy CLAUDE.md principles)
type: reference
---

# Claude Code Karpathy Skills Research (April 2026)

## Status Summary

**NO official Karpathy autoresearch skill in Anthropic/skills repo.** However, a vibrant community ecosystem exists with 3 production-ready projects and established design patterns.

---

## Main Projects

### 1. Claude Autoresearch (uditgoenka) — TIER 1 (Most Complete)

**GitHub:** [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch)
**Status:** Production-ready, actively maintained
**Installation:**
```bash
/plugin marketplace add uditgoenka/autoresearch
/plugin install autoresearch@autoresearch
```

**Core Loop:**
```
Review git/state → Pick next change → Make focused modification → 
Commit → Run mechanical verification → Keep/revert → Log → Repeat
```

**Commands:**
- `/autoresearch` — Run unbounded optimization loop
- `/autoresearch:plan` — Goal-to-config wizard (interactive)
- `/autoresearch:debug` — Scientific method bug hunting
- `/autoresearch:fix` — Iterative error repair (all failures)
- `/autoresearch:security` — STRIDE/OWASP audit
- `/autoresearch:ship` — Universal deployment workflow
- `/autoresearch:learn` — Auto-generate/update documentation
- `/autoresearch:predict` — 5-expert consensus analysis
- `/autoresearch:reason` — Adversarial debate for subjective decisions
- `/autoresearch:scenario` — Edge-case explorer (12 dimensions)

**Key Philosophy:**
- Mechanical verification only (no subjectivity)
- Git as permanent memory
- Failures revert but stay in history
- Simplicity wins (equal results = less code is better)
- Read git logs before each iteration

### 2. Andrej Karpathy Skills (forrestchang) — TIER 1 (CLAUDE.md Principles)

**GitHub:** [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)
**Status:** Single CLAUDE.md file, distributable as plugin or per-project
**Installation:**
```bash
/plugin marketplace add forrestchang/andrej-karpathy-skills
/plugin install andrej-karpathy-skills@karpathy-skills
```

**Four Core Principles:**

1. **Think Before Coding**
   - State uncertainties explicitly
   - Present multiple interpretations for ambiguities
   - Ask for clarification, don't guess
   - Avoids "silent assumptions and running along with them"

2. **Simplicity First**
   - Minimal code solving only stated problem
   - No speculative features
   - No single-use abstractions
   - No pre-emptive error handling

3. **Surgical Changes**
   - Modify only what's necessary
   - Don't refactor adjacent code unless requested
   - Don't remove dead code unless asked
   - Each change traces directly to user request

4. **Goal-Driven Execution**
   - Transform tasks into verifiable success criteria
   - Instead of "fix the bug" → "write a test that fails, make it pass"
   - Define exit conditions upfront
   - Measure before/after

**Antidotes to Common LLM Coding Mistakes:**
- Wrong assumptions without checking
- Unnecessary complexity + bloated abstractions
- Altering unrelated code model doesn't fully understand

---

### 3. Autoresearch Claude Skills Tuning (arush361) — TIER 1 (ML Framework)

**GitHub:** [arush361/autoresearch-claude-skills](https://github.com/arush361/autoresearch-claude-skills)
**Status:** Production case study, tuning framework
**Methodology:** Karpathy's autoresearch + Hamel evals-skills framework + binary evals

**The Loop (ML-Applied):**
```
Run skill on test inputs → Score (binary: yes/no) → 
Analyze failures → Mutate skill instructions → 
Decide keep/discard → Repeat
```

**Case Study: Product Manager Skill**
- **Baseline:** 59.2% pass rate (71/120 tests)
- **Exp 1:** 81.7% (98/120) — added projected score totals
- **Exp 2:** 92.5% (111/120) — clarified scoring markers
- **Exp 3:** 97.5% (117/120) — handled incomplete inputs
- **Root Cause:** Skill had "waiting problem" — never output recommendations without user reply
- **Solution:** One paragraph: "Stop waiting, start recommending"
- **Biggest Win:** That single paragraph was largest improvement

---

## Community Ecosystem

**232+ community Claude Code skills** available (alirezarezvani/claude-skills)
**340+ plugins + 1367 agent skills** in broader ecosystem (jeremylongshore)
**Multiple plugin marketplaces:** claudemarketplace.com, liteLLM marketplace, self-hosted options

### Known Issues (Apr 2026)

Several active bugs in official Claude Code marketplace:
- Marketplace skills not exposed through Skill tool
- Skills missing from slash command autocomplete
- Path resolution errors for git-installed plugins
- Third-party marketplace skills not loading into context

**Workaround:** Manual installation to `~/.claude/skills/` directories usually works.

---

## Application to NBA Prediction (8 HF Spaces + Genetic Evolution)

### Potential Adaptations

#### 1. **Brier Score Autoresearch Loop**

Adapt `uditgoenka/autoresearch` to your GA evolution:

```python
# scripts/autoresearch-brier-loop.py
GOAL = "Minimize Brier on 2025-26 season holdout test set"
METRIC = "Brier score (binary: improved vs baseline?)"

Loop:
  1. Current best: read data/karpathy/nba-best-config.json
  2. Mutate: generate 5 feature combinations from S10-S17 best models
  3. Test: run GA iteration (30 min on Colab/Kaggle GPU)
  4. Measure: compute Brier vs holdout
  5. Keep/revert: if Brier improves, commit; else revert
  6. Log: append to metrics.jsonl + git commit
  7. Repeat: 24/7 via cron
```

**Expected:** 12-24 iterations/day, auto-discovery of feature engineering wins
**Metric:** Each iteration tests ONE change (Karpathy principle)

#### 2. **Karpathy Skills for Feature Engineering**

Apply Karpathy's 4 principles to feature mutation:

```markdown
# CLAUDE.md: Feature Engineering Skills

## Principle 1: Think Before Coding
- State assumptions about feature interactions
- Ask: "Will this correlation be stable OOS?"
- Don't auto-add features without hypothesis

## Principle 2: Simplicity First
- If correlation same at lower complexity, use lower
- No 3-interaction features if 2-interaction works
- Max 3 new features per iteration (one at a time)

## Principle 3: Surgical Changes
- Mutate ONLY feature engine, never touch model
- Don't refactor unrelated code
- Commit feature change before testing

## Principle 4: Goal-Driven Execution
- Define: "Feature improves Brier by >0.001"
- Test: binary pass/fail only
- Revert if fails
```

#### 3. **Eval Framework for Feature Evaluation**

Adapt `arush361` binary evals to feature discovery:

```python
# Binary eval: does feature improve Brier?
eval_features = {
    "feature_name": "cat39_circadian_hour",
    "test_set": "2025_holdout_500_games",
    "baseline_brier": 0.21570,
    "new_brier": 0.21540,
    "pass": new_brier < baseline_brier,  # Binary: yes/no
    "improvement": baseline_brier - new_brier  # Magnitude
}

# Autoresearch loop mutates feature instructions until pass rate > 95%
```

---

## Integration with mon-ipad

### Where to Install

1. **Andrej Karpathy Skills**
   ```bash
   /plugin marketplace add forrestchang/andrej-karpathy-skills
   # Add to project's .claude/skills/ for feature mutation tasks
   ```

2. **Claude Autoresearch**
   ```bash
   /plugin marketplace add uditgoenka/autoresearch
   # Run: /autoresearch:plan → goal=Brier<0.20 → auto-iterate
   ```

3. **Custom: arush361 Framework**
   - Adapt binary evals in `scripts/evaluate_features.py`
   - Feed results to genetic algorithm

### Modified Autonomous Cycle

```bash
# scripts/autonomous-cycle.sh (add autoresearch)

# Every 4 hours:
/autoresearch:plan \
  --goal "Minimize Brier on 2025-26 holdout" \
  --metric "binary: pass if Brier improves" \
  --timeout "30 minutes" \
  --keep-if "improvement > 0.0005"

# Then aggregate results:
python3 scripts/aggregate_autoresearch_results.py \
  >> data/autoresearch-log.jsonl
```

---

## Recommended 3-Phase Deployment

### Phase 1: Andrej Karpathy Principles (4-6 hours)
- Add CLAUDE.md to feature engineering workflow
- Train team on 4 principles
- Apply to manual feature mutation

### Phase 2: Claude Autoresearch Skill (1-2 days)
- Install uditgoenka/autoresearch plugin
- Customize for Brier metric
- Test on 1 island (S15 wide) first
- Measure: iterations/hour, Brier trend

### Phase 3: Binary Eval Framework (2-3 days)
- Adapt arush361's eval system
- Implement feature mutation → test → keep/revert
- Full 8-island autoresearch with multi-feature scenarios
- Target: -0.002 to -0.005 Brier over 2 weeks

---

## Known Limitations

1. **No Official Anthropic Skill**
   - Community projects are actively maintained but not officially endorsed
   - May need periodic updates as Claude Code evolves

2. **Marketplace Bugs (Apr 2026)**
   - Skill autodiscovery sometimes fails
   - Workaround: manual installation to ~/.claude/skills/

3. **Mechanical Verification Only**
   - Works best when metric is binary (pass/fail)
   - Brier score is perfect fit (lower=better)
   - Requires objective validation set (holdout test)

4. **No GPU Execution**
   - Autoresearch orchestrates; actual GA runs on HF Spaces/Kaggle/Colab
   - Skill would queue jobs, monitor, aggregate results

---

## Comparison: Official Karpathy Autoresearch vs Community Projects

| Feature | Karpathy Original (2024) | uditgoenka/autoresearch | arush361 Skills | forrestchang Principles |
|---------|-------------------------|------------------------|-----------------|------------------------|
| **Domain** | ML hyperparameter tuning | Any measurable metric | Skill instruction tuning | Code quality guidelines |
| **Metric** | Single scalar (loss) | Binary or continuous | Binary eval (pass/fail) | Behavioral principles |
| **Git Memory** | ✓ (auto-revert) | ✓ (auto-revert) | ✓ (auto-revert) | ✓ (manual review) |
| **Automation** | 100% (no human loop) | 100% (no human loop) | 100% (no human loop) | Requires human in loop |
| **NBA Fit** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Installation** | Manual (original repo) | Plugin marketplace | Manual fork + adapt | Plugin marketplace |
| **Maintenance** | Static (2024) | Active (2026) | Active (2026) | Active (2026) |

---

## References

- [Karpathy's Original Autoresearch (2024 GitHub thread)](https://news.ycombinator.com/item?id=38653237) — 630-line Python script, 50 experiments overnight
- [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch) — Claude Autoresearch Skill
- [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) — Karpathy CLAUDE.md principles
- [arush361/autoresearch-claude-skills](https://github.com/arush361/autoresearch-claude-skills) — Skill tuning 59%→97%
- [Medium: 10x Claude Skills with Karpathy Autoresearch](https://medium.com/coding-nexus/how-to-10x-your-claude-skills-using-karpathys-autoresearch-method-d4a759ac39d7)
- [The New Stack: Karpathy's Autonomous Experiment Loop](https://thenewstack.io/karpathy-autonomous-experiment-loop/)
