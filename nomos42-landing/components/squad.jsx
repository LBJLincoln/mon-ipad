/* global React */
const { useEffect, useState } = React;

// ============ THE SQUAD — 8 autonomous security agents ============
const SQUAD = [
  // ===== RED TEAM — offensive testing of your AI (consenting systems only) =====
  {
    id: 'sentinel', layer: 'red',
    role: 'Recon agent',
    glyph: 'REC',
    domain: 'Recon',
    desc: 'Maps your AI attack surface: every prompt, tool, MCP server, RAG source and browser-use connector. Surfaces shadow AI no one inventoried.',
    kpi: { label: 'Surfaces mapped', value: '1.2k' },
    actions: ['enumerated 9 MCP tools \u00b7 ops', 'found shadow agent \u00b7 finance', 'mapped RAG corpus \u00b7 legal'],
  },
  {
    id: 'ghost', layer: 'red',
    role: 'Injection agent',
    glyph: 'INJ',
    domain: 'Offense',
    desc: 'Runs direct and indirect prompt-injection, including multi-turn Crescendo, against your agents. Finds the jailbreak before an adversary does.',
    kpi: { label: 'Attacks / hr', value: '14,200' },
    actions: ['crescendo bypass \u00b7 support-bot', 'indirect inject via PDF \u00b7 ok', 'jailbreak \u00b7 sev-high'],
  },
  {
    id: 'oracle', layer: 'red',
    role: 'Exploitation agent',
    glyph: 'EXP',
    domain: 'Exploit',
    desc: 'Chains tool abuse and excessive-agency exploits across your agent graph \u2014 the path from a single injection to a real-world action.',
    kpi: { label: 'Exploit chains', value: '317' },
    actions: ['tool abuse \u00b7 fin-reconcile', 'scope creep \u2192 write access', 'agent pivot \u00b7 mapped'],
  },
  {
    id: 'archivist', layer: 'red',
    role: 'Extraction agent',
    glyph: 'EXF',
    domain: 'Exfil',
    desc: 'Attempts system-prompt theft, RAG/secret exfiltration and training-data extraction \u2014 proving the industrial-secret risk in your own systems.',
    kpi: { label: 'Findings', value: 'OWASP LLM07' },
    actions: ['system-prompt extracted', 'secret leak \u00b7 redacted demo', 'RAG exfil \u00b7 contained'],
  },
  // ===== GUARD — runtime protection in production (deployed in your environment) =====
  {
    id: 'warden', layer: 'guard',
    role: 'AI runtime guard',
    glyph: 'GRD',
    domain: 'Runtime',
    desc: 'Sits inline on every LLM call and tool invocation. Intercepts prompt injection, scope creep and exfiltration intent before the action reaches the world.',
    kpi: { label: 'Calls / day', value: '4.1B' },
    actions: ['blocked exfil \u00b7 ops-bot-3', 're-grounded \u00b7 support-triage', 'revoked tool \u00b7 fin-reconcile'],
  },
  {
    id: 'cipher', layer: 'guard',
    role: 'Egress & identity guard',
    glyph: 'EGR',
    domain: 'Egress',
    desc: 'Enforces network egress allowlists and least-privilege on every human and non-human identity. Your agent only reaches what policy permits.',
    kpi: { label: 'Identities', value: '142k' },
    actions: ['denied egress \u00b7 ru-9x', 'revoked stale token \u00b7 22', 'stepped-up MFA \u00b7 contractor'],
  },
  {
    id: 'surgeon', layer: 'guard',
    role: 'Auto-remediation',
    glyph: 'RPR',
    domain: 'Repair',
    desc: 'On detection: quarantine, re-ground the agent with verified truth, and ship a policy patch across the fleet \u2014 in milliseconds, no war room.',
    kpi: { label: 'MTTR', value: '12 ms' },
    actions: ['quarantined ops-bot-3', 'shipped policy v1.4.2', 'fleet re-grounded \u00b7 ok'],
  },
  {
    id: 'notary', layer: 'guard',
    role: 'Compliance notary',
    glyph: 'PRV',
    domain: 'Audit',
    desc: 'Writes a signed, append-only timeline of every agent action and maps it to EU AI Act, NIS2, OWASP LLM and MITRE ATLAS \u2014 in real time.',
    kpi: { label: 'Controls', value: '413' },
    actions: ['EU AI Act art.15 evidence', 'append-only audit anchored', 'NIS2 control attested'],
  },
];

function Squad() {
  const [active, setActive] = useState('sentinel');
  const cur = SQUAD.find(s => s.id === active) || SQUAD[0];

  return (
    <section className="section squad" data-screen-label="07 Squad">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Two layers, one product · 07</span>
          </div>
          <div className="lead">
            <h2 className="h-section">A red team that attacks.<br /><em>A guard that protects.</em></h2>
            <p className="lede">
              Four agents continuously attack your AI the way a real adversary would. Four guard it
              in production. One signed timeline, one policy engine, deployed inside your own
              environment — sovereign by design.
            </p>
          </div>
        </div>

        <TwoLayer />

        <div className="squad-grid">
          {SQUAD.map(s => (
            <SquadCard
              key={s.id}
              s={s}
              active={active === s.id}
              onHover={() => setActive(s.id)}
            />
          ))}
        </div>

        <div className="squad-focus">
          <div className="squad-focus-left">
            <div className="sys-label tlog">{cur.layer === 'red' ? 'Red Team' : 'Guard'} · {cur.role}</div>
            <h3 className="h-section" style={{ fontSize: 'clamp(28px, 3vw, 44px)', marginTop: 14 }}>
              {cur.role}
            </h3>
            <p className="lede" style={{ marginTop: 16 }}>{cur.desc}</p>
          </div>
          <div className="squad-focus-right">
            <div className="squad-kpi">
              <span className="label">{cur.kpi.label}</span>
              <span className="value tlog">{cur.kpi.value}</span>
            </div>
            <div className="squad-actions">
              <div className="sys-label" style={{ marginBottom: 14 }}>Last 60 seconds</div>
              {cur.actions.map((a, i) => (
                <div key={i} className="squad-action tlog">
                  <span className="bullet">●</span> {a}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// Cinematic CSS diagram: agent core + Guard shield, red-team attacks fired inward and blocked.
function TwoLayer() {
  const ATTACKS = [
    'Prompt injection', 'Tool abuse', 'Jailbreak', 'RAG exfil',
    'Excessive agency', 'Supply chain', 'Crescendo', 'Data extraction',
  ];
  return (
    <div className="twolayer">
      <div className="twolayer-stage" aria-hidden="true">
        <div className="tl-rings" />
        <span className="tl-tag tl-tag-red">L1 · Red Team</span>
        {ATTACKS.map((a, i) => (
          <div className="tl-attack" key={i}
               style={{ transform: `rotate(${i * 45}deg)`, '--d': `${(i * 0.5).toFixed(2)}s` }}>
            <span className="tl-attack-label" style={{ transform: `rotate(${-i * 45}deg)` }}>{a}</span>
            <span className="tl-attack-streak" />
          </div>
        ))}
        <div className="tl-guard"><span className="tl-tag tl-tag-green">L2 · Guard</span></div>
        <div className="tl-core">
          <span className="tl-core-glyph">AI</span>
          <span className="tl-core-label tlog">agent secured</span>
        </div>
      </div>
      <div className="twolayer-copy">
        <div className="twolayer-line"><span className="tl-dot red" /> The red team finds every way in — injection, tool abuse, exfiltration.</div>
        <div className="twolayer-line"><span className="tl-dot green" /> The Guard shuts each one down inline, in <b>12 ms</b>, inside your environment.</div>
        <div className="twolayer-line strong">One product. Two layers. Zero standing exposure.</div>
      </div>
    </div>
  );
}

function SquadCard({ s, active, onHover }) {
  return (
    <div className={'squad-card' + (active ? ' active' : '')}
         onMouseEnter={onHover}
         onClick={onHover}>
      <div className="squad-card-head">
        <span className="squad-glyph">{s.glyph}</span>
        <span className="squad-layer-chip" style={{
          fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
          padding: '3px 7px', borderRadius: 999, fontWeight: 600,
          color: s.layer === 'red' ? 'var(--signal-bad)' : 'var(--signal-good)',
          border: '1px solid ' + (s.layer === 'red' ? 'rgba(255,90,78,0.4)' : 'rgba(107,230,166,0.4)'),
          background: s.layer === 'red' ? 'rgba(255,90,78,0.08)' : 'rgba(107,230,166,0.08)'
        }}>{s.layer === 'red' ? 'Red Team' : 'Guard'}</span>
      </div>
      <h4>{s.role}</h4>
      <div className="squad-card-foot">
        <span className="tlog">{s.kpi.value}</span>
        <span className="tlog">{s.kpi.label}</span>
      </div>
      <div className="squad-card-pulse" />
    </div>
  );
}

window.Squad = Squad;
