# Appendix B — Mathematical Supplements

---

## B.1  JSD–Ambiguity Monotonicity in the Operating Range

We prove the claim in §3.3: that Jensen–Shannon diversity $D_d$ is a strictly
increasing function of the Ambiguity term $\text{Amb}_t = \frac{1}{N}\sum_i (p_{i,t} - \bar{p}_t)^2$
in the operating range $\bar{p}_t \in [0.24, 0.76]$, $\text{Amb}_t \leq 0.04$
(pilot-season empirical range; Table 4, §5.1), when $\bar{p}_t$ is held fixed.

**Setup.** For a fixed event $t$, let $p_1, \ldots, p_N \in [0,1]$ be agent predictions,
$\bar{p} = \frac{1}{N}\sum_i p_i$, and $\delta_i = p_i - \bar{p}$ (so $\sum_i \delta_i = 0$).
The JSD for $N$ Bernoulli distributions is:

$$\text{JSD} = H(\bar{p}) - \frac{1}{N}\sum_{i=1}^N H(p_i)$$

with $H(p) = -p\log_2 p - (1-p)\log_2(1-p)$ and $\text{Amb} = \frac{1}{N}\sum_i \delta_i^2$.

**Taylor expansion.** Expanding $H(p_i) = H(\bar{p} + \delta_i)$ to second order:

$$H(\bar{p} + \delta_i) = H(\bar{p}) + H'(\bar{p})\,\delta_i + \frac{1}{2}H''(\bar{p})\,\delta_i^2 + R_i$$

where $R_i = \frac{1}{6}H'''(\xi_i)\,\delta_i^3$ for some $\xi_i$ between $\bar{p}$ and $p_i$.

Averaging over $i$ and using $\sum_i \delta_i = 0$:

$$\frac{1}{N}\sum_{i=1}^N H(p_i) = H(\bar{p}) + \frac{1}{2}H''(\bar{p})\cdot\text{Amb} + \bar{R}$$

where $\bar{R} = \frac{1}{N}\sum_i R_i$.  Substituting into the JSD formula:

$$\text{JSD} = -\frac{1}{2}H''(\bar{p})\cdot\text{Amb} - \bar{R} \tag{B.1}$$

**Sign of the leading coefficient.** The second derivative of the binary entropy is:

$$H''(p) = -\frac{1}{p(1-p)\ln 2} < 0 \quad \forall\, p \in (0,1)$$

Therefore $-\frac{1}{2}H''(\bar{p}) = \frac{1}{2\bar{p}(1-\bar{p})\ln 2} > 0$.

Numerically, at the worst-case boundary of the empirical operating range $\bar{p} = 0.24$:

$$-\frac{1}{2}H''(0.24) = \frac{1}{2 \times 0.24 \times 0.76 \times \ln 2} = \frac{1}{0.2518} \approx 3.97$$

(units: bits per unit Ambiguity; *not* nats$^{-1}$, which would arise from a natural-log JSD)
and at $\bar{p} = 0.50$, the coefficient is $\frac{1}{2 \times 0.25 \times \ln 2} \approx 2.89$.

**Bounding the remainder.** The third derivative is:

$$H'''(p) = \frac{(1-2p)}{p^2(1-p)^2\ln 2}$$

which vanishes at $p = 0.5$ and is maximised in magnitude at the boundary of the
empirical operating range. At $\bar{p} = 0.24$:

$$|H'''(0.24)| = \frac{|1 - 0.48|}{(0.24)^2(0.76)^2 \ln 2}
= \frac{0.52}{0.0576 \times 0.5776 \times 0.693} \approx 22.5$$

To bound $\frac{1}{N}\sum_i |\delta_i|^3$, we use the *extremal configuration*
under the constraints $\sum_i \delta_i = 0$ and $\frac{1}{N}\sum_i \delta_i^2 = \text{Amb}$:
the maximum of $\frac{1}{N}\sum_i |\delta_i|^3$ is attained at
$\delta_1 = c$, $\delta_j = -c/(N-1)$ for $j \neq 1$, where $c = \sqrt{(N-1)\,\text{Amb}}$.
Substituting:

$$\frac{1}{N}\sum_i |\delta_i|^3\bigg|_{\text{extremal}} = \frac{c^3}{N}\!\left(1 + \frac{1}{(N-1)^2}\right)
= \frac{(N-1)^{3/2}}{N}\!\left(1 + \frac{1}{(N-1)^2}\right)\text{Amb}^{3/2}$$

For $N = 12$: the factor is $\frac{11^{3/2}}{12}(1 + \frac{1}{121}) \approx 3.04 \times 1.008 \approx 3.07$.
*Note:* the power-mean inequality $M_2 \leq M_3$ gives the opposite direction ($\frac{1}{N}\sum_i |\delta_i|^3 \geq \text{Amb}^{3/2}$) and cannot be used for an upper bound here.

The remainder bound is therefore:

$$|\bar{R}| \leq \frac{|H'''|_{\max}}{6}\cdot\frac{(N-1)^{3/2}}{N}\!\left(1+\frac{1}{(N-1)^2}\right)\text{Amb}^{3/2}
\;\approx\; \frac{|H'''|_{\max}}{6}\times 3.07\times\text{Amb}^{3/2}$$

**Monotonicity claim.** From equation (B.1), the total derivative is:

$$\frac{\partial \text{JSD}}{\partial \text{Amb}}\bigg|_{\bar{p}} =
-\frac{1}{2}H''(\bar{p}) - \frac{\partial \bar{R}}{\partial \text{Amb}}$$

The remainder derivative satisfies (differentiating the extremal bound):

$$\left|\frac{\partial \bar{R}}{\partial \text{Amb}}\right| \leq \frac{|H'''|_{\max}}{6}\times 3.07\times\frac{3}{2}\sqrt{\text{Amb}}
= \frac{3\times 3.07\times|H'''|_{\max}}{12}\sqrt{\text{Amb}}$$

At the worst-case boundary of the empirical range ($\bar{p} = 0.24$, $\text{Amb} = 0.04$,
$N = 12$):

$$\left|\frac{\partial \bar{R}}{\partial \text{Amb}}\right| \leq \frac{3 \times 3.07 \times 22.5}{12}\times\sqrt{0.04}
= \frac{207.2}{12}\times 0.200 \approx 3.46$$

The leading coefficient at $\bar{p} = 0.24$ is $3.97$.  Hence:

$$\frac{\partial \text{JSD}}{\partial \text{Amb}}\bigg|_{\bar{p}=0.24,\,\text{Amb}=0.04} \geq 3.97 - 3.46 = 0.51 > 0$$

confirming strict monotonicity throughout the empirical operating range. $\square$

*Remark.* The margin (0.51 vs zero) is tightest at the corner $\bar{p} = 0.24$,
$\text{Amb} = 0.04$, reflecting the fact that for $\bar{p}$ near the market-boundary
and $\text{Amb}$ at its pilot maximum, higher-order terms are non-negligible.
For $\bar{p} \in [0.35, 0.65]$ (the modal game probability regime) and
$\text{Amb} \leq 0.02$, the remainder derivative is an order of magnitude smaller
than the leading term, and the linear approximation
$\text{JSD} \approx c(\bar{p})\cdot\text{Amb}$ is highly accurate.

*Scope note.* This proof is calibrated to the pilot-season empirical range
($\bar{p} \in [0.24, 0.76]$, $\text{Amb} \leq 0.04$; Table 4).  For larger
$\text{Amb}$ or more extreme $\bar{p}$ values, the Taylor-expansion argument does
not provide a guarantee; we do not claim monotonicity outside the empirical range.

---

## B.2  Pairwise Archetype Distinguishability Matrix

*Table B.2: Full $20 \times 20$ matrix of pairwise archetype distinguishability
estimates from the 2024–25 pilot season. For each pair $(r^{(a)}, r^{(b)})$,
two values are reported: (i) the cross-agent average
$\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)})$ — the mean absolute prediction
difference averaged over all $N = 12$ agents and $T_{\text{pilot}}$ events;
(ii) the per-agent minimum
$\hat{\epsilon}_{\text{arch}}^{\min}(r^{(a)}, r^{(b)})$ — the minimum over agents
of each agent's individual mean absolute difference. **The per-agent minimum is the
operative Assumption A1 test** (§3.5, §5.1): A1 is confirmed for this pair if and
only if $\hat{\epsilon}_{\text{arch}}^{\min} \geq 0.037$. The cross-agent average
is provided for descriptive comparison. Both values are derived from the same
$20 \times 12 \times T_{\text{pilot}}$ prediction matrix; no additional API calls
are required beyond the 295,200-call pilot batch (§5.1 footnote).*

**[PENDING: experimental run required. Table to be populated from
`data/arena/axelrod-log/pilot-archetype-pairs.jsonl` once the 2024–25 pilot
backtest completes. Each cell will report both
$\hat{\epsilon}_{\text{arch}}$ (avg) and $\hat{\epsilon}_{\text{arch}}^{\min}$
(per-agent min). Expected minimum per-agent-min entry $\geq 0.037$ (Assumption A1
threshold); pre-registered expectation is that the (`wide-coverage`, `diversified`)
pair yields the minimum and the (`contrarian`, `quantitative`) pair yields the
maximum. The agent expected to produce the minimum per-agent entry across all pairs
is T12 (selfhost-qwen4b), whose *disciplined* archetype may constrain its
prediction range even at 235B scale post-rerouting (§4.1 Table 3 note$^\dagger$).]**
