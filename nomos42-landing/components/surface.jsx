/* global React */
const { useEffect, useRef, useState } = React;

// ============ THREAT SURFACE — force-graph-style visualization ============
// Static layout, animated pulses on the high-risk edges.

const NODES = [
  // Center: human tenant
  { id: 'tenant',  x: 0.50, y: 0.50, r: 28, kind: 'tenant', label: 'TENANT' },

  // Agents (orbital)
  { id: 'ops-bot-3',     x: 0.22, y: 0.32, r: 14, kind: 'agent', risk: 'high',   label: 'ops-bot-3' },
  { id: 'fin-reconcile', x: 0.30, y: 0.70, r: 12, kind: 'agent', risk: 'medium', label: 'fin-reconcile' },
  { id: 'support-triage',x: 0.62, y: 0.22, r: 12, kind: 'agent', risk: 'medium', label: 'support-triage' },
  { id: 'sales-research',x: 0.78, y: 0.42, r: 10, kind: 'agent', risk: 'low',    label: 'sales-research' },
  { id: 'ml-loader',     x: 0.68, y: 0.74, r: 10, kind: 'agent', risk: 'low',    label: 'ml-loader' },
  { id: 'legal-rev',     x: 0.45, y: 0.18, r:  9, kind: 'agent', risk: 'low',    label: 'legal-review' },
  { id: 'devops-7',      x: 0.45, y: 0.84, r:  9, kind: 'agent', risk: 'medium', label: 'devops-7' },

  // Resources (outer)
  { id: 'customers',   x: 0.08, y: 0.18, r: 14, kind: 'data', label: 'customers.pii' },
  { id: 'ledger',      x: 0.10, y: 0.82, r: 12, kind: 'data', label: 'finance.ledger' },
  { id: 'snowflake',   x: 0.92, y: 0.22, r: 12, kind: 'data', label: 'snowflake.dw' },
  { id: 'okta',        x: 0.92, y: 0.78, r: 11, kind: 'data', label: 'identity.idp' },
  { id: 'k8s',         x: 0.50, y: 0.06, r:  9, kind: 'data', label: 'prod.k8s' },
  { id: 'stripe',      x: 0.50, y: 0.94, r:  9, kind: 'data', label: 'stripe.api' },
];

const EDGES = [
  // tenant ↔ agents
  ['tenant', 'ops-bot-3',     'high'],
  ['tenant', 'fin-reconcile', 'medium'],
  ['tenant', 'support-triage','medium'],
  ['tenant', 'sales-research','low'],
  ['tenant', 'ml-loader',     'low'],
  ['tenant', 'legal-rev',     'low'],
  ['tenant', 'devops-7',      'medium'],
  // agents ↔ resources
  ['ops-bot-3',     'customers', 'high'],
  ['ops-bot-3',     'snowflake', 'medium'],
  ['fin-reconcile', 'ledger',    'medium'],
  ['fin-reconcile', 'stripe',    'medium'],
  ['support-triage','customers', 'medium'],
  ['sales-research','snowflake', 'low'],
  ['ml-loader',     'snowflake', 'low'],
  ['legal-rev',     'ledger',    'low'],
  ['devops-7',      'k8s',       'medium'],
  ['devops-7',      'okta',      'low'],
];

function Surface() {
  const W = 1600, H = 900;
  const px = (n, p) => n[p === 'x' ? 'x' : 'y'] * (p === 'x' ? W : H);
  const byId = Object.fromEntries(NODES.map(n => [n.id, n]));

  return (
    <section className="section surface" data-screen-label="04 Threat surface">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Map · 04</span>
          </div>
          <div className="lead">
            <h2 className="h-section">Every agent is an attack surface<br /><em>we render it as one.</em></h2>
            <p className="lede">
              Continuous lineage of which agent can reach which system, with which credentials,
              under which policy. Pull a thread and see who you'd expose.
            </p>
          </div>
        </div>

        <div className="surface-wrap">
          <div className="surface-canvas">
            <div className="surface-meta tlog">SURFACE_MAP · {NODES.length} nodes · {EDGES.length} edges</div>
            <div className="surface-legend">
              <span className="item"><span className="swatch" style={{ background: 'var(--signal-bad)' }} />high</span>
              <span className="item"><span className="swatch" style={{ background: 'var(--signal-warn)' }} />med</span>
              <span className="item"><span className="swatch" style={{ background: 'var(--accent)' }} />low</span>
            </div>

            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
              <defs>
                <radialGradient id="centerGlow" cx="0.5" cy="0.5" r="0.5">
                  <stop offset="0%" stopColor="rgba(232,255,246,0.5)" />
                  <stop offset="100%" stopColor="rgba(232,255,246,0)" />
                </radialGradient>
                {/* concentric rings */}
              </defs>

              {/* Concentric rings */}
              {[0.15, 0.28, 0.42].map((r, i) => (
                <circle key={i} cx={W/2} cy={H/2} r={r * W}
                        fill="none" stroke="rgba(255,255,255,0.06)" strokeDasharray="2 8" />
              ))}

              {/* Edges */}
              {EDGES.map(([a, b, risk], i) => {
                const A = byId[a], B = byId[b];
                const color = risk === 'high' ? 'var(--signal-bad)'
                           : risk === 'medium' ? 'var(--signal-warn)'
                           : 'rgba(232,255,246,0.3)';
                return (
                  <g key={i}>
                    <line x1={px(A,'x')} y1={px(A,'y')} x2={px(B,'x')} y2={px(B,'y')}
                          stroke={color} strokeWidth={risk === 'high' ? 1.6 : 1}
                          opacity={risk === 'low' ? 0.4 : 0.8} />
                    {risk === 'high' && (
                      <circle r="4" fill="var(--signal-bad)">
                        <animateMotion dur="2.2s" repeatCount="indefinite"
                          path={`M ${px(A,'x')} ${px(A,'y')} L ${px(B,'x')} ${px(B,'y')}`} />
                      </circle>
                    )}
                    {risk === 'medium' && (
                      <circle r="3" fill="var(--signal-warn)" opacity="0.7">
                        <animateMotion dur="3.5s" repeatCount="indefinite"
                          path={`M ${px(A,'x')} ${px(A,'y')} L ${px(B,'x')} ${px(B,'y')}`} />
                      </circle>
                    )}
                  </g>
                );
              })}

              {/* Center tenant glow */}
              <circle cx={W/2} cy={H/2} r="120" fill="url(#centerGlow)" />

              {/* Nodes */}
              {NODES.map(n => {
                const cx = px(n, 'x'), cy = px(n, 'y');
                if (n.kind === 'tenant') {
                  return (
                    <g key={n.id} transform={`translate(${cx} ${cy})`}>
                      <rect x={-n.r} y={-n.r} width={n.r*2} height={n.r*2}
                            fill="rgba(10,10,10,0.95)" stroke="var(--fg)" strokeWidth="1.5" />
                      <circle r="3" fill="var(--accent)" />
                      <text textAnchor="middle" y={n.r + 20} fill="var(--fg)"
                            fontSize="13" letterSpacing="4">{n.label}</text>
                    </g>
                  );
                }
                if (n.kind === 'agent') {
                  const stroke = n.risk === 'high' ? 'var(--signal-bad)'
                              : n.risk === 'medium' ? 'var(--signal-warn)'
                              : 'var(--accent)';
                  return (
                    <g key={n.id} transform={`translate(${cx} ${cy})`}>
                      <circle r={n.r + 6} fill="rgba(0,0,0,0.6)" />
                      <circle r={n.r} fill="rgba(10,10,10,0.95)" stroke={stroke} strokeWidth="1.5" />
                      {n.risk === 'high' && (
                        <circle r={n.r} fill="none" stroke={stroke} strokeWidth="1.5">
                          <animate attributeName="r" values={`${n.r};${n.r+18}`} dur="2s" repeatCount="indefinite" />
                          <animate attributeName="opacity" values="0.8;0" dur="2s" repeatCount="indefinite" />
                        </circle>
                      )}
                      <text textAnchor="middle" y={n.r + 18} fill="var(--fg-2)"
                            fontSize="11" letterSpacing="2">{n.label}</text>
                    </g>
                  );
                }
                // data
                return (
                  <g key={n.id} transform={`translate(${cx} ${cy})`}>
                    <rect x={-n.r} y={-n.r} width={n.r*2} height={n.r*2} rx="1"
                          fill="rgba(10,10,10,0.95)" stroke="rgba(255,255,255,0.4)" strokeWidth="1.2" />
                    <line x1={-n.r*0.6} y1="-2" x2={n.r*0.6} y2="-2" stroke="rgba(255,255,255,0.4)" />
                    <line x1={-n.r*0.6} y1="3"  x2={n.r*0.6} y2="3"  stroke="rgba(255,255,255,0.4)" />
                    <text textAnchor="middle" y={n.r + 18} fill="var(--fg-3)"
                          fontSize="11" letterSpacing="2">{n.label}</text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Below-map stats strip */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 24, marginTop: 32, borderTop: '1px solid var(--line)', paddingTop: 24 }}>
            <SurfaceStat label="Total reachable systems" value="142" />
            <SurfaceStat label="Cross-tenant edges" value="3" hi />
            <SurfaceStat label="Avg. permissions / agent" value="8.2" />
            <SurfaceStat label="Detected drifts (24h)" value="11" />
          </div>
        </div>
      </div>
    </section>
  );
}

function SurfaceStat({ label, value, hi }) {
  return (
    <div>
      <div className="sys-label" style={{ marginBottom: 10 }}>{label}</div>
      <div className="tlog" style={{ fontSize: 32, letterSpacing: '-0.02em', fontWeight: 500, color: hi ? 'var(--signal-bad)' : 'var(--fg)' }}>
        {value}
      </div>
    </div>
  );
}

window.Surface = Surface;
