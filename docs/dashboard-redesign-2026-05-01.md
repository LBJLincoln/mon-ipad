# Nomos42 Dashboard — Lab-Grade Redesign Spec (2026-05-01)

> **Read this if:** you are the session implementing the Vercel dashboard
> rebuild in `lbjlincoln/nomos-dashboard`. This file is the contract.
>
> **Goal:** match the visual + scientific credibility of the 5 best AI lab
> dashboards on earth, in service of the $1M revenue target.

## 0. Why this exists

PIXEL audit (2026-05-01) found `0 SVGs / 0 canvases / 0 tables` on **all 7
routes**. Trust signals (CI bands, walk-forward, calibration, methodology,
git SHA) are 0/7 too. Mobile breaks on `/nba` `/political` `/trading-floor`;
`/world` is blank on mobile. The current site is typographically pleasant
and substantively empty.

Source materials:
- `data/audit/dashboard-2026-05-01/pixel-audit.md` — visual audit, top-10 fixes
- `data/audit/dashboard-2026-05-01/structural-metrics.json` — programmatic per-route metrics
- `data/audit/dashboard-2026-05-01/accountant-trust-levers.md` — business / conversion strategy
- `data/research/dashboard-redesign-apr14-2026.md` — top-5 quant dashboards (Bloomberg / OpenBB / TradingView / dYdX / Reddit-Moltbook) with palette + patterns
- `data/research/dashboard-libraries-apr14-2026.md` — Recharts / Tremor / shadcn / @pixi/react with code samples
- `data/research/dashboard-overhaul-plan-apr16.md` — concrete `/infra` + `/` + `/world` rebuild plan with ASCII sketches
- `docs/anthropic-trigger-plumbing-2026-05-01.md` — cloud-brain heartbeat alarms

## 1. Information architecture (routes)

| Route | Purpose | Audience | Required components |
|---|---|---|---|
| `/` | 60-second pitch | cold visitor | hero KPIs (3 numbers above fold), 3-line "what is this", CTAs to `/picks` + `/methodology` |
| `/nba` | NBA TF live tape + science | customer prospect | `<KPICard>` × 4, `<WalkforwardRibbon>`, `<ReliabilityDiagram>`, `<AgentLeaderboard>`, `<TheTape>` (last 50 bets, paginated) |
| `/political` | POL TF live tape | same | mirror `/nba` schema |
| `/trading-floor` | cross-fleet — NBA + POL + ITF + PQTF | investor / partner | `<FleetGrid>` (4 tile + status pill), per-tile sparkline equity, cross-TF Welch test row |
| `/picks` (NEW) | public pick log — daily picks ≥24h old, full settlement | conversion driver for paid Telegram | `<PickRow>` × N, columns: timestamp BEFORE tip-off, agent, edge%, stake$, settlement, CLV |
| `/methodology` (NEW) | scientific transparency | due-diligence reviewer | engine.py SHA + version, walk-forward window definition, calibration approach, public April reset changelog, paper refs |
| `/investor` (NEW, password-walled) | season PnL + diligence pack | partner negotiation | embed of `/trading-floor` + 17-agent LLM diversity matrix + infra uptime |
| `/evolution` | 6 NBA + 5 POL islands GA progress | curious user | per-island Brier line chart, generation gauge |
| `/forge` | dept councils (deprecated 2026-04-20) | hide or 404 | (was D1-D9, now no-op per CLAUDE.md) |
| `/world` | pixel-world (PixiJS) | brand / marketing | desktop-only — show static fallback on mobile, currently blank → broken WebGL on phone |

## 2. Design system

### 2.1 Palette — adopt **dark canvas** (Bloomberg / W&B / Anthropic Console default)

The current cream `rgb(241, 234, 216)` is "lifestyle blog", not "lab". Switch to:

```css
--bg-canvas:        #0A0A0B;  /* near-black, OLED-friendly */
--bg-card:          #14141A;
--bg-card-hover:    #1A1A22;
--ring:             #2A2A33;
--text-primary:     #F4F4F5;
--text-secondary:   #A0A0AB;
--text-muted:       #6B6B75;

/* Semantic */
--accent-edge:      #00FF88;  /* WIN / IMPROVING / OK */
--accent-warn:      #FFB020;  /* STALE / WARN */
--accent-error:     #FF5C5C;  /* DEAD / DEGRADING / ERROR */
--accent-info:      #5C8DFF;  /* live / running */
--accent-frozen:    #B988FF;  /* PQTF FROZEN — distinct from live */

/* Chart palette */
--chart-1: #00FF88; --chart-2: #5C8DFF; --chart-3: #FFB020;
--chart-4: #FF5C5C; --chart-5: #B988FF; --chart-6: #00D4FF;
--chart-ci-fill: rgba(92, 141, 255, 0.20);  /* CI band semi-transparent */
```

Keep light mode toggle (existing serif identity is good for light) but **default = dark**.

### 2.2 Typography — already correct

Keep as-is: `Instrument Serif` headlines, `JetBrains Mono` numbers, `Inter` body. The bones are right.

Add: 8pt baseline grid (multiple of 4 for spacing), `tabular-nums` on every digit (`font-feature-settings: 'tnum'`).

### 2.3 Motion vocabulary

- New data arriving: `0.3s ease-out` opacity 0→1
- KPI value change: number tween 0.6s with `monotone` easing — never instant snap
- CI band: render once, never animate (animating uncertainty is dishonest)
- Status pill blink: `2s pulse` for `LIVE`, none for `STALE` / `DEAD`

## 3. Component contracts

The data-layer commit `bd6b954` (2026-05-01) lands `data/tf-analytics/dashboard-bundle.json`. Schema version `2026-05-01`. The Vercel app fetches it from `https://nomosdashboard.vercel.app/tf-analytics/dashboard-bundle.json` (mirrored hourly by `sync_tf_analytics_to_dashboard.sh`).

### 3.1 `<KPICard>` — replaces every existing `<HeroNumber>`

Required props (all read from `bundle.tfs[tf].kpi`):

```ts
type KPICardProps = {
  label: string;          // "NBA Brier (30d)"
  value: number;          // 0.2244
  ci_low: number;         // 0.2189
  ci_high: number;        // 0.2301
  n_bets: number;         // 1247
  unit: 'brier' | 'wr' | 'pnl_usd' | 'roi_pct';
  trend24h?: number;      // -0.0012  (improving = lower for Brier)
  last_updated_iso: string;
  source_link: string;    // /api/tf-analytics/dashboard-bundle.json
  methodology_link: string;  // /methodology#brier
};
```

Visual:
```
┌────────────────────────────────────────────┐
│ NBA Brier · 30d                  ●LIVE    │   ← status pill, accent-info pulse
│                                            │
│  0.2244                          ▾ 0.0012  │   ← value (Instrument Serif, big), trend chip
│  ┄┄┄┄┄┄┄┄[CI band]┄┄┄┄┄┄┄┄┄                │   ← 95% CI [0.2189, 0.2301]
│  n=1,247 bets · ECE 0.041                  │
│  updated 23s ago · [methodology]           │
└────────────────────────────────────────────┘
```

**Pattern `WB-CI-BAND`** — the CI band is the most-important pixel on the card. If you have to drop something for space, drop the trend chip first, never the CI.

**Pattern `OAI-SAMPLE-CHIP`** — the `n=1,247` number is non-negotiable. A KPI without sample size is a number, not a measurement.

### 3.2 `<WalkforwardRibbon>` — Recharts AreaChart

```tsx
import { AreaChart, Area, XAxis, YAxis, ReferenceLine, Tooltip } from 'recharts';

const data = bundle.tfs.nba.walk_forward;  // [{start_day, end_day, n, brier}]

<AreaChart data={data} width={720} height={220}>
  <defs>
    <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.3}/>
      <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0}/>
    </linearGradient>
  </defs>
  <XAxis dataKey="end_day" tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}/>
  <YAxis domain={[0.18, 0.27]} reversed={false} tick={{ fontFamily: 'JetBrains Mono', fontSize: 11 }}/>
  <ReferenceLine y={0.243} stroke="var(--text-muted)" strokeDasharray="3 3"
                 label={{ value: 'Vegas baseline 0.243', position: 'right', fill: 'var(--text-muted)' }}/>
  <Area type="monotone" dataKey="brier" stroke="var(--chart-2)"
        strokeWidth={2} fill="url(#ciGrad)" />
  <Tooltip />
</AreaChart>
```

Below the y-axis ≤ 0.243 line is "beating Vegas". This is THE chart that justifies the brand.

### 3.3 `<ReliabilityDiagram>` — Recharts ScatterChart

```tsx
const data = bundle.tfs.nba.calibration_buckets;
// [{bucket: '0.0-0.1', n: 23, avg_predicted: 0.05, avg_actual: 0.04, gap: -0.01}]

<ScatterChart width={420} height={420}>
  <XAxis type="number" dataKey="avg_predicted" domain={[0,1]} name="predicted"/>
  <YAxis type="number" dataKey="avg_actual" domain={[0,1]} name="actual"/>
  <ReferenceLine segment={[{x:0,y:0},{x:1,y:1}]} stroke="var(--text-muted)" strokeDasharray="4 4"/>
  <Scatter data={data} fill="var(--accent-edge)">
    {data.map((d, i) => <Cell key={i} r={Math.sqrt(d.n)*1.5} />)}  // radius ∝ √n
  </Scatter>
  <Tooltip formatter={(v, name, props) => [`${v}`, `${name} (n=${props.payload.n})`]}/>
</ScatterChart>
```

Points on the dashed diagonal = perfectly calibrated. Above = overconfident, below = underconfident.

### 3.4 `<TrustBadgeRow>` — pattern `HF-LB-BADGE`

```tsx
const t = bundle.tfs.nba.trust_signals;
const badge = (label, ok) => ok ? '🟢' : ok === false ? '🔴' : '🟡';

<div className="flex gap-2 text-xs font-mono">
  <Badge ok={t.baseline_pass}>baseline {badge('', t.baseline_pass)}</Badge>
  <Badge ok={t.leakage_score > 0.95}>leakage {t.leakage_score}</Badge>
  <Badge ok={t.lockstep_score < 0.85}>lockstep {t.lockstep_score}</Badge>
  <Badge ok={t.walkforward_status === 'PASS'}>walkforward {t.walkforward_status}</Badge>
  <Badge ok={t.source_purity_pct > 90}>source {t.source_purity_pct}%</Badge>
  <Badge>{t.trajectory_verdict}</Badge>
</div>
```

These pills appear on every TF page, top-right. They are the public face of the leakage / lockstep / walk-forward audits the system already does internally.

### 3.5 `<EquitySpark>` — for ITF (only TF with rich equity series)

```tsx
const series = bundle.tfs.itf.equity_series;  // [{ts, equity, cash, long, short}]
<LineChart data={series} width={120} height={32}>
  <Line type="monotone" dataKey="equity" stroke="var(--chart-1)" strokeWidth={1.5} dot={false}/>
</LineChart>
```

Goes inside `<KPICard>` as a header sparkline.

### 3.6 `<AgentLeaderboard>` — `<Table>` not `<div>`

```tsx
const agents = bundle.tfs.nba.per_agent;  // [{tid, n, wr, brier, pnl}]

<Table>
  <Thead>
    <Tr>
      <Th>#</Th><Th>Agent</Th><Th>LLM</Th><Th right>Bets</Th><Th right>WR</Th>
      <Th right>Brier</Th><Th right>PnL</Th><Th>Tier</Th>
    </Tr>
  </Thead>
  <Tbody>
    {agents.map((a, i) => (
      <Tr key={a.tid}>
        <Td>{i+1}</Td>
        <Td className="font-mono">{a.tid}</Td>
        <Td className="text-secondary">{LLM_MAP[a.tid]}</Td>
        <Td right>{a.n}</Td>
        <Td right className={a.wr > 0.5 ? 'text-edge' : ''}>{(a.wr*100).toFixed(1)}%</Td>
        <Td right>{a.brier.toFixed(4)}</Td>
        <Td right className={a.pnl > 0 ? 'text-edge' : 'text-error'}>${a.pnl.toFixed(0)}</Td>
        <Td><TierPill brier={a.brier}/></Td>
      </Tr>
    ))}
  </Tbody>
</Table>
```

Sortable columns. Sticky header. Horizontally scrollable on mobile (the current div-stack is what makes mobile overflow).

### 3.7 `<FrozenArtifactPill>` — PQTF must always wear it

```tsx
<span className="bg-frozen/10 text-frozen ring-1 ring-frozen/30 px-2 py-0.5 rounded text-xs font-mono">
  ❄ FROZEN ARTIFACT · $602K validation proof, 2026-04-15 final state
</span>
```

PQTF is not live. Anywhere it appears on the dashboard, this pill is mandatory. Per ACCOUNTANT memo, the dishonesty risk is the single biggest threat to the brand.

## 4. Top-of-funnel: above-the-fold KPI hierarchy on `/`

3 numbers, no more. Per ACCOUNTANT trust levers:

```
┌────────────────────────────────────────────────────────────────────┐
│  Walk-Forward Brier 0.2244           Live Capital Deployed          │
│   95% CI [0.219, 0.230] · n=1,247    $629,016 across 4 TFs          │
│   ▾ vs Vegas 0.243                   (live $26K + paper $90K +      │
│                                       frozen-artifact $602K)         │
│                                                                      │
│  Picks YTD: 1,461 · Hit-rate 53.2% · ROI +2.4%                       │
│  [See today's free pick →]   [Subscribe — $29/mo →]                 │
└────────────────────────────────────────────────────────────────────┘
```

Three CTAs: `/picks` (free proof), `/methodology` (transparency moat), Stripe checkout. No fourth CTA.

## 5. The `/methodology` page — the moat

ACCOUNTANT calls this the brand's defensible position. Page sections (in order):

1. **Engine version** — `engine.py` SHA pinned, version v3.1, 54 categories, ~7213 raw features, MAX_FEATURES=200 cap explained
2. **Walk-forward window definition** — 30-day rolling, 1000-resample bootstrap CI95, ECE on 10 buckets, link to `tf_rigorous_validation.py` source on GitHub
3. **Calibration approach** — isotonic + Venn-Abers fusion (planned), reliability diagram
4. **Reset incident changelog** — public list of the 5 April 2026 reset events with date, TF affected, root cause, what was preserved (champion-snapshot mechanism). This is uncomfortable but it IS the moat.
5. **Paper references** — TabICL, TauricResearch (2412.20138), Prediction Arena (2604.07355), DMAD (2502.21321 — anti-groupthink)
6. **Data sources** — Bovada (odds), nba_api (games), THE TICKER scrape windows
7. **What's NOT validated** — explicit "we have not yet" list (live capital > $1M tested, multi-season generalization, etc.)

Link from every `<KPICard>`'s `methodology_link` prop into the right anchor (`#brier` `#walkforward` `#calibration`).

## 6. The `/picks` page — conversion driver

Per ACCOUNTANT: **all picks ≥ 24h old shown free, with full settlement**, today's pre-tip picks paid.

```
2026-04-30 18:42 UTC  before tip-off
NBA · MIL @ BOS · spread_away +5.5
agent: nvidia-llama70 · edge: +0.073 · stake: $24
THESIS: "Boston short-rest after BAA; books slow to adjust."
RESULT (final 22:31 UTC): MIL won by 4 → bet won, +$22.10
CLV: opening +5.5 → closing +6.5  (+1.0 line move in our favor)
```

Each row links to that day's full agent decision matrix (already exists in
`data/audit/per-agent-deep-nba-{date}.md` mirrored to
`/audit/per-agent-deep-nba-{date}.md`). That deep audit IS the proof.

Pricing wall: today's picks pre-tip require subscription. Yesterday's picks free.

## 7. Mobile — fix the 3 overflow routes

- `/nba`, `/political`, `/trading-floor`: bodies render at 476-578px in a 390px viewport. Audit tailwind classes for `min-w-[460px]` `whitespace-nowrap` on `<TheTape>` rows. Replace with `overflow-x-auto` on the parent table and let the inner table scroll horizontally — that's intentional and scannable. NOT `min-w` on the body.
- `/world`: WebGL fails on mobile. Either gate to `if (window.innerWidth >= 768)` or ship a static screenshot via `<picture>` for narrow viewports.

## 8. Implementation phases

| Phase | Lift | Visible impact |
|---|---|---|
| **P1 — week 1** | `<KPICard>` + `<TrustBadgeRow>` + dark palette + `/methodology` skeleton | 80% of credibility upgrade unlocked |
| **P2 — week 2** | `<WalkforwardRibbon>` + `<ReliabilityDiagram>` + `<AgentLeaderboard>` Table | dashboard finally renders charts |
| **P3 — week 3** | `/picks` route + Stripe wall + `<FrozenArtifactPill>` everywhere | conversion path live |
| **P4 — week 4** | `/investor` route + cross-TF Welch test display + mobile fixes | partner-ready |

Ship in order. P1 alone is the biggest single jump.

## 9. What NOT to do (per ACCOUNTANT honesty constraints)

- **Don't hide the resets.** Surface them on `/methodology` as a public changelog. They're the moat.
- **Don't conflate paper and live capital.** ITF $90K is Alpaca paper. Don't paint it as same color as a real $90K. Use `--accent-info` for paper, `--accent-edge` for actual settled cash.
- **Don't show PQTF without `<FrozenArtifactPill>`.** Ever.
- **Don't promise % vs Vegas without the CI band rendered next to it.** Number alone reads as cherry-picked.
- **Don't ship dark mode before charts.** Dark mode on an empty page is still empty.

## 10. Verification — when is "done" done?

Run PIXEL again post-deploy. Expect:
- `svgCount > 5` on every route
- `hasCI = true` on `/`, `/nba`, `/political`, `/trading-floor`
- `hasWalkforward = true` on `/nba`, `/political`
- `hasCalibration = true` on `/nba`, `/political`
- `hasMethodology = true` on every route (link in footer)
- `hasGitSha = true` on every route (footer chip)
- `kpiCardCandidates >= 4` per route
- mobile `bodyW <= viewportW + 16px` on all routes
- `console_first10 = []` on every route

If any of those fail post-deploy, the spec wasn't fully applied.

---

**Bundle URL the dashboard fetches:** `https://nomosdashboard.vercel.app/tf-analytics/dashboard-bundle.json`

**Schema version it's contracted against:** `2026-05-01`

**If schema_version differs:** show a banner "Dashboard data schema mismatch — frontend stale, redeploy needed" rather than rendering wrong numbers.
