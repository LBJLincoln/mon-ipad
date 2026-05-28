# SOTA Research Proposal: Collective Alignment in LLM Multi-Agent Systems via Statistical Physics

**Source:** arXiv:2605.10528 — "Collective Alignment in LLM Multi-Agent Systems: Disentangling Bias from Cooperation via Statistical Physics"  
**Author:** Cristiano De Nobili  
**Fire:** 212 (EVEN, 2026-06-02T16h)  
**Priority:** 101 (TF architecture upgrade)  
**Work-queue ID:** vm-research-collective-alignment-statistical-physics-fire212  

---

## Summary

Applies statistical physics (Ising model + finite-size scaling) to characterize emergent alignment dynamics in multi-agent LLM systems. Extracts two compact **collective behavior fingerprints** per model:
- **h̃(T)**: intrinsic bias parameter — tendency to converge on one answer independent of neighbors  
- **J̃(T)**: cooperative coupling parameter — tendency to conform to neighboring agents

**Key finding:** In all tested LLMs (llama3.1:8b, phi4-mini:3.8b, mistral:7b), **intrinsic bias (h̃) substantially dominates cooperative coupling (J̃)** across all temperatures. Collective alignment is **field-driven** (by shared model biases) rather than **interaction-driven** (by peer conformity).

Critical implication: the primary failure mode of collective intelligence is NOT groupthink from peer pressure — it is **shared intrinsic bias baked into model priors**. All prior multi-agent LLM research (including fire-204 arXiv:2604.06091, fire-206 arXiv:2505.11556) assumed peer-pressure as primary driver. This paper corrects that assumption.

---

## Applications to Axelrod Trading Floor

### 1. Bias-Aware DMAD Gate (Mech A upgrade)
Current DMAD gate detects convergence from peer conformity. But if bias dominates coupling, convergence happens BEFORE agents see peers' picks — it's intrinsic to the models.

**Action:** Add `intrinsic_bias_score_d` per agent = fraction of agent picks in day D that deviated from market-implied probability by <5% (low independent judgment proxy). When `mean(intrinsic_bias_score_d) > 0.7` across agents: flag as `ck_bias_dominated` → DMAD-DIVERGE must source contradictory evidence from external data only, not peer picks (which share the same bias).

### 2. Bias-Inverse COMMON_KNOWLEDGE Aggregation (Mech A, upgrades PolySwarm fire-208)
PolySwarm (arXiv:2604.03888, fire-208) proposed confidence-weighted Bayesian aggregation. Statistical physics finding suggests better weight: **inverse bias weight** — agents with lower h̃ (more independent judgment) should dominate consensus.

**Action:** COMMON_KNOWLEDGE[D] weight per agent: `w_agent = 1 / (1 + intrinsic_bias_score_d)`. More weight to agents with historically high pick independence from market priors. Combines with confidence weighting: `w_agent = confidence_d / (1 + intrinsic_bias_score_d)`.

### 3. Phase Transition Trigger for Mech B (Mech B upgrade)
Paper shows order-disorder phase transitions where ensemble shifts from diverse to aligned. When bias_std → 0 across agents, ensemble enters ordered phase (all agents share same bias → collective intelligence fails).

**Action:** Add `bias_std_d` = std(intrinsic_bias_score_d across agents) to Mech B trigger conditions. When `bias_std_d < 0.05` AND `mean > 0.6`: trigger Mech B sacrificial reallocation preemptively (before the ordered phase produces wrong consensus).

### 4. Mech C Post-Mortem Log Fields
Add:
- `mean_intrinsic_bias_d`: mean bias score across agents for day D
- `std_intrinsic_bias_d`: std deviation (low = ordered phase risk)
- `bias_dominated_flag`: bool (True when mean>0.7 AND std<0.1)
- 30-day rolling `bias_dominated_rate`: fraction of days where bias_dominated_flag was True — sustained high rate means TF ensemble has homogeneous priors → consider adding a more contrarian agent archetype

### 5. DiscoUQ Complement (arXiv:2603.20975, secondary fire-212 find)
DiscoUQ (Bo Jiang, 2026): structured disagreement analysis using linguistic + geometric patterns for ensemble UQ. AUROC 0.802, ECE 0.036 vs 0.098 baseline. Largest improvements in "weak disagreement" tier where simple vote counting fails.

**Action:** When DiscoUQ score is low (high apparent agreement) AND `bias_dominated_flag` is True: this is the highest-risk collective intelligence failure mode. Halve Kelly stakes or abstain that day.

---

## Expected Improvement
- Reduces systematic collective alignment failures by detecting bias-dominated convergence (not just peer-pressure groupthink)
- Bias-inverse weighting should yield 2-3x fewer false-consensus detections vs current approach
- Combined with PolySwarm (fire-208): bias-inverse + confidence weighting creates robust CK[D] aggregation resistant to both failure modes
- Phase transition trigger (bias_std_d) provides preemptive Mech B activation before ordered-phase consensus errors

---

## Implementation Notes
- h̃ formal computation requires lattice topology; practical proxy: `intrinsic_bias_score_d` from historical Mech C logs (no lattice needed)
- Temperature T maps to agent exploration rate (already in DMAD config)
- Phase transition detection: use `bias_std_d` over 7-day rolling window — watch for std trend → 0
- Priority 101 (after memetic drift fire-210 priority=100); implement after Mech B/C baseline established
