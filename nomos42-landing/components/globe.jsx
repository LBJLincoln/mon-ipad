/* global React */
const { useEffect, useState } = React;

// ============ GLOBAL OPS MAP ============
// A stylized world overview with active sites and traveling event pulses.
// (Abstract dot-grid silhouette of continents, hand-tuned 64x28.)

const LAND = [
  /* row 0 */ '..............................................................',
  /* row 1 */ '.....###....##.....######........###...####...........#.......',
  /* row 2 */ '....######.######.########......###############......#####....',
  /* row 3 */ '....################.######....######################...##....',
  /* row 4 */ '.....################..#######..#######################......',
  /* row 5 */ '......################.######....###################.........',
  /* row 6 */ '......################..####.....##################..........',
  /* row 7 */ '.......##############....##.......################...........',
  /* row 8 */ '........##############............################...........',
  /* row 9 */ '..........############............###############............',
  /* row 10*/ '...........###########..............#############............',
  /* row 11*/ '............##########...............############............',
  /* row 12*/ '..............########...##............##########...##.......',
  /* row 13*/ '...............######....####..........#########..####.......',
  /* row 14*/ '................####....######.........########..######......',
  /* row 15*/ '.................##....#######...........######.######.......',
  /* row 16*/ '..................######...###...........####..#####.........',
  /* row 17*/ '....................####...##............####...####.........',
  /* row 18*/ '.....................###..................###...####.........',
  /* row 19*/ '.....................##....................##....##..........',
  /* row 20*/ '......................#.....................#................',
  /* row 21*/ '..............................................................',
  /* row 22*/ '..............................................................',
];

// Approx city positions (col, row) on the 64x23 grid
const SITES = [
  { id: 'sfo', name: 'San Francisco', c: 7,  r: 8,  tier: 1 },
  { id: 'nyc', name: 'New York',      c: 14, r: 8,  tier: 1 },
  { id: 'sao', name: 'São Paulo',     c: 19, r: 17, tier: 2 },
  { id: 'lon', name: 'London',        c: 30, r: 6,  tier: 1 },
  { id: 'par', name: 'Paris',         c: 31, r: 7,  tier: 1 },
  { id: 'ber', name: 'Berlin',        c: 33, r: 6,  tier: 1 },
  { id: 'dxb', name: 'Dubai',         c: 39, r: 11, tier: 2 },
  { id: 'mum', name: 'Mumbai',        c: 43, r: 12, tier: 2 },
  { id: 'sng', name: 'Singapore',     c: 49, r: 14, tier: 2 },
  { id: 'tok', name: 'Tokyo',         c: 55, r: 9,  tier: 1 },
  { id: 'syd', name: 'Sydney',        c: 56, r: 19, tier: 2 },
  { id: 'jhb', name: 'Johannesburg',  c: 34, r: 17, tier: 2 },
];

// Live traffic links (pairs of site ids + severity)
const LINKS = [
  ['sfo', 'tok', 'high'],
  ['nyc', 'lon', 'high'],
  ['par', 'mum', 'med'],
  ['ber', 'dxb', 'med'],
  ['sng', 'tok', 'high'],
  ['sao', 'nyc', 'med'],
  ['syd', 'sng', 'low'],
  ['jhb', 'par', 'low'],
];

const EVENT_SAMPLES = [
  { sev: 'bad',  site: 'par', msg: 'prompt-injection blocked \u00b7 defense agent' },
  { sev: 'warn', site: 'ber', msg: 'tool-abuse attempt \u00b7 industrial bot' },
  { sev: 'good', site: 'par', msg: 'EU AI Act evidence signed' },
  { sev: 'bad',  site: 'lon', msg: 'system-prompt exfil \u00b7 contained' },
  { sev: 'warn', site: 'dxb', msg: 'red-team finding \u00b7 OWASP LLM07' },
  { sev: 'good', site: 'ber', msg: 'guard policy v1.4.2 deployed' },
  { sev: 'bad',  site: 'par', msg: 'indirect injection via RAG \u00b7 blocked' },
  { sev: 'good', site: 'lon', msg: 'NIS2 control attested \u00b7 12 ms' },
];

function Globe() {
  const [events, setEvents] = useState(EVENT_SAMPLES.slice(0, 4));
  useEffect(() => {
    const i = setInterval(() => {
      setEvents(e => [EVENT_SAMPLES[Math.floor(Math.random() * EVENT_SAMPLES.length)], ...e].slice(0, 6));
    }, 2400);
    return () => clearInterval(i);
  }, []);

  const COLS = 64, ROWS = 23;
  const W = COLS * 22, H = ROWS * 22;  // canvas dimensions
  const cellW = W / COLS, cellH = H / ROWS;
  const px = (c) => c * cellW + cellW / 2;
  const py = (r) => r * cellH + cellH / 2;
  const byId = Object.fromEntries(SITES.map(s => [s.id, s]));

  return (
    <section className="section globe" data-screen-label="09 Globe">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Sovereign footprint · 09</span>
          </div>
          <div className="lead">
            <h2 className="h-section">Your region.<br /><em>Your tenancy. Your sovereignty.</em></h2>
            <p className="lede">
              Nomos42 runs in your tenancy, in your region, against your AI — never our cloud.
              Sovereign by default, EU-hosted, with a zero-egress mode for air-gapped defense
              and critical-industry fleets.
            </p>
          </div>
        </div>

        <div className="globe-grid">
          <div className="globe-canvas">
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
              <defs>
                <radialGradient id="siteGlow" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="rgba(var(--accent-rgb),0.6)" />
                  <stop offset="100%" stopColor="rgba(var(--accent-rgb),0)" />
                </radialGradient>
              </defs>

              {/* land dot grid */}
              {LAND.map((row, r) =>
                row.split('').map((ch, c) => ch === '#' ? (
                  <circle key={`${r}-${c}`} cx={px(c)} cy={py(r)} r="1.6"
                          fill="rgba(255,255,255,0.18)" />
                ) : null)
              )}

              {/* links */}
              {LINKS.map(([a, b, sev], i) => {
                const A = byId[a], B = byId[b];
                const x1 = px(A.c), y1 = py(A.r), x2 = px(B.c), y2 = py(B.r);
                // arc midpoint above straight line
                const mx = (x1 + x2) / 2;
                const my = (y1 + y2) / 2 - Math.abs(x2 - x1) * 0.15;
                const path = `M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`;
                const color = sev === 'high' ? 'var(--signal-bad)'
                           : sev === 'med'  ? 'var(--signal-warn)'
                           : 'rgba(var(--accent-rgb),0.5)';
                return (
                  <g key={i}>
                    <path d={path} stroke={color} strokeWidth="1" fill="none"
                          opacity={sev === 'high' ? 0.85 : 0.55} />
                    <circle r={sev === 'high' ? 3 : 2.5} fill={color}>
                      <animateMotion dur={sev === 'high' ? '2.4s' : '4.5s'} repeatCount="indefinite" path={path} />
                    </circle>
                  </g>
                );
              })}

              {/* sites */}
              {SITES.map(s => (
                <g key={s.id} transform={`translate(${px(s.c)} ${py(s.r)})`}>
                  <circle r="14" fill="url(#siteGlow)" />
                  <circle r="3.4" fill="var(--accent)" />
                  <circle r="3.4" fill="none" stroke="var(--accent)" strokeWidth="1">
                    <animate attributeName="r" values="3.4;12" dur={`${2 + (s.tier * 0.6)}s`} repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.7;0" dur={`${2 + (s.tier * 0.6)}s`} repeatCount="indefinite" />
                  </circle>
                  <text y={-8} textAnchor="middle" fill="var(--fg-2)"
                        fontSize="10" letterSpacing="2"
                        style={{ textTransform: 'uppercase' }}>{s.name}</text>
                </g>
              ))}
            </svg>

            <div className="globe-meta tlog">REGIONS_ACTIVE · 12 · SOVEREIGN_MODE</div>
          </div>

          <aside className="globe-feed">
            <div className="sys-label" style={{ marginBottom: 18 }}>Live events · global</div>
            {events.map((e, i) => (
              <div key={e.msg + i} className={'globe-event sev-' + e.sev}>
                <div className="globe-event-site tlog">{byId[e.site]?.name?.toUpperCase() || e.site.toUpperCase()}</div>
                <div className="globe-event-msg">{e.msg}</div>
                <div className="globe-event-sev tlog">{e.sev === 'bad' ? 'CRIT' : e.sev === 'warn' ? 'WARN' : 'OK'}</div>
              </div>
            ))}
          </aside>
        </div>
      </div>
    </section>
  );
}

window.Globe = Globe;
