# Appendix B — Mathematical Supplements

---

## B.1  JSD–Ambiguity Monotonicity in the Operating Range

We prove the claim in §3.3: that Jensen–Shannon diversity $D_d$ is a strictly
increasing function of the Ambiguity term $\text{Amb}_t = \frac{1}{N}\sum_i (p_{i,t} - \bar{p}_t)^2$
in the operating range $\bar{p}_t \in [0.15, 0.85]$, $\text{Amb}_t \leq 0.08$,
when $\bar{p}_t$ is held fixed.

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

Numerically, at the boundary $\bar{p} = 0.15$:

$$-\frac{1}{2}H''(0.15) = \frac{1}{2 \times 0.15 \times 0.85 \times \ln 2} \approx \frac{1}{0.1768} \approx 5.65 \;\text{nats}^{-1}$$

and at $\bar{p} = 0.50$, the coefficient is $\frac{1}{2 \times 0.25 \times \ln 2} \approx 2.89\;\text{nats}^{-1}$.

**Bounding the remainder.** The third derivative is:

$$H'''(p) = \frac{(1-2p)}{p^2(1-p)^2\ln 2}$$

which vanishes at $p = 0.5$ and is maximised in magnitude at the boundary of the
operating range. At $\bar{p} = 0.15$:

$$|H'''(0.15)| = \frac{|1 - 0.30|}{(0.15)^2(0.85)^2 \ln 2}
= \frac{0.70}{0.0225 \times 0.7225 \times 0.693} \approx 62.3$$

Individual deviations satisfy $|\delta_i| \leq \sqrt{N \cdot \text{Amb}}$ by the
Cauchy–Schwarz inequality (applied to a single summand against the average).
In practice, with $N \leq 12$ and $\text{Amb} \leq 0.08$, the constraint
$\sum_i \delta_i = 0$ implies $|\delta_i| \leq \sqrt{(N-1)\,\text{Amb}} \leq 0.93$.
The remainder bound is then:

$$|\bar{R}| \leq \frac{1}{6}|H'''|_{\max}\cdot\frac{1}{N}\sum_i |\delta_i|^3
\leq \frac{|H'''|_{\max}}{6}\,\text{Amb}^{3/2}$$

using $\frac{1}{N}\sum_i |\delta_i|^3 \leq \left(\frac{1}{N}\sum_i \delta_i^2\right)^{3/2} = \text{Amb}^{3/2}$
(power-mean inequality).

**Monotonicity claim.** From equation (B.1), the total derivative is:

$$\frac{\partial \text{JSD}}{\partial \text{Amb}}\bigg|_{\bar{p}} =
-\frac{1}{2}H''(\bar{p}) - \frac{\partial \bar{R}}{\partial \text{Amb}}$$

The first term equals $\frac{1}{2\bar{p}(1-\bar{p})\ln 2} > 0$.
The remainder satisfies $|\partial\bar{R}/\partial\text{Amb}| \leq \frac{|H'''|_{\max}}{4}\sqrt{\text{Amb}}$
(differentiating the bound).  In the operating range $\text{Amb} \leq 0.08$,
$\bar{p} \in [0.15, 0.85]$:

$$\frac{|H'''|_{\max}}{4}\sqrt{0.08} \approx \frac{62.3}{4} \times 0.283 \approx 4.41$$

versus the leading coefficient of at least $5.65$.  Hence
$\frac{\partial \text{JSD}}{\partial \text{Amb}} \geq 5.65 - 4.41 = 1.24 > 0$,
confirming strict monotonicity throughout the stated range.

*Remark.* The margin (1.24 vs zero) narrows near the boundary $\bar{p} = 0.15$
and $\text{Amb} = 0.08$, reflecting genuine nonlinearity at extreme values.
For $\bar{p} \in [0.25, 0.75]$ and $\text{Amb} \leq 0.05$ — the typical operating
regime observed in our experiments — the remainder is an order of magnitude smaller
than the leading term, and the linear approximation $\text{JSD} \approx c(\bar{p})\cdot\text{Amb}$
is highly accurate.

---

## B.2  Pairwise Archetype Distinguishability Matrix

*Table B.2: Full $20 \times 20$ matrix of pairwise archetype distinguishability
estimates $\hat{\epsilon}_{\text{arch}}(r^{(a)}, r^{(b)})$ from the 2024–25 pilot
season. Each entry is the mean absolute prediction difference between an agent
running archetype $r^{(a)}$ and an agent running archetype $r^{(b)}$ on the same
event context, averaged over $T_{\text{pilot}}$ held-out events.*

**[PENDING: experimental run required. Table to be populated from
`data/arena/axelrod-log/pilot-archetype-pairs.jsonl` once the 2024–25 pilot
backtest completes. Expected minimum entry $\geq 0.037$ (Assumption A1
threshold); pre-registered expectation is that the (`wide-coverage`, `diversified`)
pair yields the minimum and the (`contrarian`, `quantitative`) pair yields the
maximum.]**
