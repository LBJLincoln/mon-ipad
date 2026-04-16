# 3.8 Per-Category Walk-Forward Prediction Extension (2026-04-16 update)

An earlier version of the LPSG (§3.1–§3.7) modelled each event as a single
binary outcome $Y_{t,k} \in \{0,1\}$. In the NBA market this corresponded to
the moneyline only. In practice, sportsbooks offer ~100 correlated categories
per game (moneylines, spreads, totals, alternate lines, team totals, halves,
quarters, and game props). This section describes the extension of the
Nomos42 fleet's walk-forward predictions to every such category, added to the
LPSG pipeline on 2026-04-16.

## 3.8.1 Why not train 100 separate models?

Training 100 per-category walk-forward models would require ground-truth
outcomes at the per-category granularity for every historical game (per-quarter
box scores, half scores, team-level totals, etc.). These are available via
NBA.com but not all have been ingested at time of writing. Moreover, for
lines that books offer but are rare (e.g., alternate spreads at -6.5 when
market is -4), the historical sample is too sparse to train a stable
classifier.

We therefore use a principled statistical transformation: the fleet's
moneyline / spread / total walk-forward predictions are mapped into $\sim$91
per-category probabilities via the empirical distribution of NBA game
outcomes (§3.8.2). This is equivalent to a walk-forward prediction under the
assumption that within-game variance parameters are stationary across the
season — a standard and well-tested assumption in basketball analytics.

## 3.8.2 Derivation

Let $\mathcal{P}_t = (\hat{p}^{ML}_{t,k}, \hat{p}^{SP}_{t,k}, \hat{p}^{TO}_{t,k})$
denote the fleet consensus for game $(t,k)$ on the three primary markets.
Let $\alpha^{ML}_{t,k}, \alpha^{SP}_{t,k}, \alpha^{TO}_{t,k}$ denote the fleet
agreement proportions (§4.2). We first extract two continuous predictions:

$$\text{predicted\_margin}_{t,k} = -\,\text{market\_spread}_{t,k} + \delta^{SP}_{t,k}$$
$$\text{predicted\_total}_{t,k} = \text{market\_total}_{t,k} + \delta^{TO}_{t,k}$$

where the fleet tilts $\delta^{SP}$ and $\delta^{TO}$ are bounded shifts from
market in the fleet-consensus direction, scaled by disagreement:

$$\delta^{SP}_{t,k} = \pm\,c_{SP}\,(2\alpha^{SP}_{t,k}-1),\quad c_{SP} = 2.5\,\text{pts}$$
$$\delta^{TO}_{t,k} = \pm\,c_{TO}\,(2\alpha^{TO}_{t,k}-1),\quad c_{TO} = 3.0\,\text{pts}$$

The sign is set by $\hat{p}^{SP}$ and $\hat{p}^{TO}$ directions. These
coefficients ($c_{SP},c_{TO}$) are hyperparameters (Appendix B).

For category derivation we then apply Normal CDF transformations with
empirical variance parameters:

- $\sigma^{\text{margin}}_{\text{full}} = 11.5$ (NBA 2024-25 regular season)
- $\sigma^{\text{total}}_{\text{full}} = 21.0$
- $\sigma^{\text{team}}_{\text{pts}}  = 12.5$

**Spread covers at line $\ell$:**
$$P(\text{home covers }\ell) = 1 - \Phi\!\!\left(\frac{-\ell - \text{predicted\_margin}_{t,k}}{\sigma^{\text{margin}}_{\text{full}}}\right)$$

**Total over $\ell$:**
$$P(\text{over }\ell) = 1 - \Phi\!\!\left(\frac{\ell - \text{predicted\_total}_{t,k}}{\sigma^{\text{total}}_{\text{full}}}\right)$$

**Team totals:** using
$\mu^{\text{home}}_{t,k} = (\text{predicted\_total} + \text{predicted\_margin})/2$,
$\mu^{\text{away}}_{t,k} = (\text{predicted\_total} - \text{predicted\_margin})/2$,
and $\sigma^{\text{team}}_{\text{pts}}$.

**Halves / quarters:** applying variance scaling from full-game Gaussians.
The first-half share of full-game total is fixed at
$\lambda_{H1} = 0.502$ (empirical, 2024-25); first-quarter at
$\lambda_{Q1} = 0.253$. Half- and quarter-margin variances scale as
$\sigma\sqrt{\lambda}$.

**Game props:**
- $P(\text{overtime}) = \Phi(1)-\Phi(-1)$ under $\mathcal{N}(\text{margin},\sigma)$;
- $P(\text{both 100+}) \approx P(\text{home}\!\geq\!100)\cdot P(\text{away}\!\geq\!100)$
  (independence is a known approximation; Appendix B records the calibration
  bias we observed on held-out 2024-25 data);
- $P(\text{blowout }\geq\!20) = 1-\Phi(20; \text{abs(margin)}, \sigma^{\text{margin}})$.

**Edge vs market:** for categories where real book odds are available
(base markets priced on BetMGM), we compute
$\text{edge}_{t,k}^{\text{cat}} = \hat{p}^{\text{cat}}_{t,k} - p^{\text{book}}_{t,k}$
where $p^{\text{book}}$ is the de-vigged implied probability. For alternate
lines we derive synthetic book odds from our probability times an empirical
vig factor $\eta = 1.05$ (measured from BetMGM two-way markets in the 2025-26
dataset) to present LLM agents with realistic prices.

## 3.8.3 Pipeline artifacts

- `data/model-predictions-2025-26.json` (6.64 MB, 1,236 games × 91 cats)
  — adds `per_category` and `derived_core` to each game record while
  preserving the original fleet consensus fields for reproducibility.
- `data/full-odds-2025-26.json` (5.00 MB, 802 games × 91 cats) — real base
  odds + derived alternate lines, with both fair probability and vig-adjusted
  decimal odds. 434 games have no real market odds and fall back to
  fleet-consensus-only predictions.

## 3.8.4 What the agents now see

Previously LLM agents received only
`consensus_{ml,spread,total}_direction` (3 directional signals). After
2026-04-16 they receive, per game:

1. **Derived core:** `predicted_margin`, `predicted_total`, `predicted_p_home`
   (continuous, point-space).
2. **Top-5 model edges:** the 5 categories with the largest $|$edge$|$ vs
   market are displayed explicitly in the prompt.
3. **Full odds menu:** ~91 categories with their decimal odds.

This change is the subject of ablation study A6 (Appendix A): does giving
agents per-category model priors change the Brier, the per-category
betting concentration, and the JS-divergence of the agent ensemble?

The hypothesis — preregistered §4.7 — is that per-category priors will
*increase* JS-divergence across agents (since they can specialize in
categories where their risk profile matches the fleet's edge), while
keeping ensemble Brier unchanged on the moneyline market.
