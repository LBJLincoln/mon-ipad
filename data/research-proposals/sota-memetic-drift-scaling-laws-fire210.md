# SOTA: Memetic Drift Scaling Laws in LLM Collectives
**Source:** arXiv:2603.24676 — "When Is Collective Intelligence a Lottery? Multi-Agent Scaling Laws for Memetic Drift in LLMs"
**Fire:** 210 (EVEN WebSearch, 2026-06-02T08h)
**Relevance:** HIGH — directly parameterizes Axelrod Mech A CK broadcast bandwidth and Mech B sacrifice rate

## Key Findings

Paper derives scaling laws for **drift-induced polarization** in LLM populations as a function of:
- **N** — population size (Nomos: N=12 NBA, N=10 POL)
- **B** — communication bandwidth (information density in COMMON_KNOWLEDGE[D])
- **α** — in-context adaptation rate (maps to Mech B sacrifice fraction)
- **σ** — agents' internal uncertainty (heterogeneity across LLM providers)

Validated in Quantized Social Game (QSG) simulations and naming-game experiments with real LLM populations.

Core result: there exists a **critical bandwidth B*** below which collective intelligence collapses to a "lottery" — outcomes are random with respect to population size, and adding more agents provides zero benefit. Above B*, collective accuracy scales beneficially.

## Applications to Axelrod TF

### Application 1 — CK[D] Bandwidth Optimization (Mech A)
The current COMMON_KNOWLEDGE[D] block has no token budget cap. Paper's B* formula for N=12 (NBA):

```
B* ≈ σ · log(N) / α
```

With σ≈0.3 (estimated heterogeneity across 5 LLM providers), N=12, α≈0.1 (adaptation rate):
- B* ≈ 0.3 * log(12) / 0.1 ≈ 7.4 nats ≈ ~1500 tokens (rough conversion)

**Action:** Add `MAX_CK_TOKENS = 1500` cap to `build_common_knowledge_block()` — summarize/truncate if CK exceeds cap to keep society in collective-intelligence regime, not lottery regime.

### Application 2 — Sacrifice Rate Optimization (Mech B)
Paper's optimal α* for N agents:
```
α* = 1 / (N · τ_drift)
```
where τ_drift is the drift time constant (≈3-5 days for daily-bucket TF).

For N=12, τ=4: α* ≈ 1/(12*4) ≈ 0.021 → ~2% of agents sacrificed per day → 0.25 agents/day → round to 1 agent every 4 days.

Current Mech B: bottom-3 of 12 = 25% per day. Paper suggests this is **10× too high** — excessive sacrifice causes societal drift rather than diversity benefit.

**Action:** Reduce Mech B sacrifice from bottom-3 to bottom-1 per day, or cycle sacrificed agents over 3-day windows (each day one of the bottom-3 is replaced, not all three simultaneously).

### Application 3 — Post-Mortem Metric (Mech C)
Add `memetic_drift_score_d` to `write_axelrod_log()`:
- Compute Bhattacharyya coefficient between day-D agent distribution and day-(D-1) agent distribution
- High drift (BC < 0.5) flags that society is in lottery regime — CK bandwidth may need increasing

## Implementation Priority
- **Priority 100** (research queue): write proposal (done)
- **Priority 10** (vm): implement MAX_CK_TOKENS cap in both NBA+POL apps (BLOCKED: do_not_push_hf_space_yet)
- **Priority 11** (vm): reduce Mech B sacrifice rate from bottom-3 to rolling bottom-1 (BLOCKED)

## Paper Details
- Title: "When Is Collective Intelligence a Lottery? Multi-Agent Scaling Laws for Memetic Drift in LLMs"
- arXiv: 2603.24676
- Date: March 2026
- Key validation: QSG simulations + naming-game LLM experiments
- Relevance tags: #axelrod #mech-a #mech-b #mech-c #ck-broadcast #collective-intelligence #scaling-laws
