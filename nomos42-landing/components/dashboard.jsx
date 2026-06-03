/* global React */
const { useEffect, useMemo, useRef, useState } = React;

// ============ SOC DASHBOARD (live working prototype) ============
const NAV = [
  { id: 'overview', label: 'Overview', badge: null, icon: '◇' },
  { id: 'agents',   label: 'Agents',   badge: '24', icon: '◯' },
  { id: 'threats',  label: 'Threats',  badge: '7',  icon: '△' },
  { id: 'policies', label: 'Policies', badge: null, icon: '▢' },
  { id: 'audit',    label: 'Audit log',badge: null, icon: '≡' },
];

const SEED_AGENTS = [
  { id: 'ops-bot-3',      env: 'production',   risk: 92, status: 'bad',  perms: 18, owner: 'Platform' },
  { id: 'fin-reconcile',  env: 'production',   risk: 64, status: 'warn', perms: 11, owner: 'Finance' },
  { id: 'sales-research', env: 'staging',      risk: 22, status: 'good', perms: 6,  owner: 'GTM' },
  { id: 'support-triage', env: 'production',   risk: 41, status: 'warn', perms: 9,  owner: 'CX' },
  { id: 'ml-data-loader', env: 'production',   risk: 12, status: 'good', perms: 4,  owner: 'ML Infra' },
  { id: 'legal-review',   env: 'production',   risk: 8,  status: 'good', perms: 3,  owner: 'Legal' },
];

const SEED_FEED = [
  { ts: '02:14:33', sev: 'bad',  desc: <><b>ops-bot-3</b> attempted exfiltration of <b>customers.pii</b> · blocked</> },
  { ts: '02:14:19', sev: 'warn', desc: <><b>fin-reconcile</b> requested elevated AWS scope · pending review</> },
  { ts: '02:13:51', sev: 'good', desc: <>Policy <b>no-cross-tenant-read</b> auto-deployed to 12 agents</> },
  { ts: '02:13:02', sev: 'warn', desc: <><b>support-triage</b> received prompt injection from inbound email</> },
  { ts: '02:12:14', sev: 'good', desc: <>Patch <b>v0.93.2</b> applied to <b>ml-data-loader</b></> },
];

function Dashboard() {
  const [tab, setTab] = useState('overview');
  const [feed, setFeed] = useState(SEED_FEED);
  const [agents, setAgents] = useState(SEED_AGENTS);
  const [tick, setTick] = useState(0);

  // Live ticker
  useEffect(() => {
    const i = setInterval(() => setTick(t => t + 1), 2200);
    return () => clearInterval(i);
  }, []);

  // Inject new feed events
  useEffect(() => {
    if (!tick) return;
    const samples = [
      { sev: 'bad',  desc: <><b>ops-bot-3</b> retry attempt · contained</> },
      { sev: 'warn', desc: <>Anomalous tool-chain in <b>sales-research</b></> },
      { sev: 'good', desc: <>Re-grounded context for <b>support-triage</b></> },
      { sev: 'warn', desc: <>Outbound DNS to unknown domain · <b>fin-reconcile</b></> },
      { sev: 'good', desc: <>Policy diff committed by Nomos42</> },
    ];
    const next = samples[tick % samples.length];
    const now = new Date();
    const ts = now.toLocaleTimeString('en-GB', { hour12: false });
    setFeed(f => [{ ...next, ts, _new: true }, ...f].slice(0, 8));
  }, [tick]);

  // Sparkline data
  const sparkData = useMemo(() => {
    const out = [];
    for (let i = 0; i < 36; i++) {
      const base = 30 + Math.sin(i * 0.4 + tick * 0.15) * 18;
      const spike = (i % 11 === 0) ? 38 : 0;
      out.push(Math.max(8, Math.min(95, base + spike + Math.random() * 8)));
    }
    return out;
  }, [tick]);

  return (
    <section className="section" data-screen-label="03 Dashboard" style={{ paddingTop: 60 }}>
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Console · 03</span>
          </div>
          <div className="lead">
            <h2 className="h-section">Mission Control<br /><em>for every agent you ship.</em></h2>
            <p className="lede">
              A single console for risk, telemetry, policy and forensic replay across every
              autonomous workflow in your enterprise.
            </p>
          </div>
        </div>
      </div>

      <div className="dashboard-frame">
        <div className="dash-chrome">
          <div className="dots"><span className="dot" /><span className="dot" /><span className="dot" /></div>
          <div className="url tlog">nomos42.security <b>/ console / {tab}</b></div>
          <div style={{ width: 60, textAlign: 'right', fontSize: 11, color: 'var(--fg-4)', letterSpacing: '0.2em' }}>LIVE</div>
        </div>

        <div className="dash-body">
          <aside className="dash-side">
            <div className="dash-side-section">
              <h4>Workspace</h4>
              {NAV.map(n => (
                <div key={n.id}
                     className={'dash-nav-item' + (tab === n.id ? ' active' : '')}
                     onClick={() => setTab(n.id)}>
                  <span className="icon" aria-hidden="true">{n.icon}</span>
                  {n.label}
                  {n.badge && <span className="badge">{n.badge}</span>}
                </div>
              ))}
            </div>
            <div className="dash-side-section" style={{ marginTop: 'auto' }}>
              <h4>Tenant</h4>
              <div style={{ padding: '8px 24px', fontSize: 12, color: 'var(--fg-3)', lineHeight: 1.6 }}>
                Acme Industrial<br />
                <span style={{ color: 'var(--fg-4)', fontSize: 11, letterSpacing: '0.14em' }}>EU-WEST · TIER 4</span>
              </div>
            </div>
          </aside>

          <main className="dash-main">
            <div className="dash-topbar">
              <h2>
                {tab === 'overview' && 'Operational overview'}
                {tab === 'agents' && 'Agent fleet'}
                {tab === 'threats' && 'Active threats'}
                {tab === 'policies' && 'Policy editor'}
                {tab === 'audit' && 'Audit log'}
              </h2>
              <span className="meta tlog">{new Date().toUTCString().slice(17, 25)} UTC · last sync 0s</span>
            </div>

            {tab === 'overview' && <Overview agents={agents} feed={feed} sparkData={sparkData} />}
            {tab === 'agents'   && <AgentTable agents={agents} />}
            {tab === 'threats'  && <Threats feed={feed} />}
            {tab === 'policies' && <Policies />}
            {tab === 'audit'    && <Audit />}
          </main>
        </div>
      </div>
    </section>
  );
}

function Overview({ agents, feed, sparkData }) {
  const breached = agents.filter(a => a.status === 'bad').length;
  const warn = agents.filter(a => a.status === 'warn').length;
  return (
    <>
      <div className="dash-kpis">
        <Kpi label="Agents online" value={agents.length} delta="+2 this hour" />
        <Kpi label="Active threats" value={breached} alert delta="contained" />
        <Kpi label="At risk" value={warn} delta={`${warn} need policy review`} bad />
        <Kpi label="Mean intercept" value="11ms" delta="−3ms vs. baseline" />
      </div>

      <div className="dash-grid">
        <div className="panel">
          <div className="panel-head">
            <h3>Agent fleet · risk distribution</h3>
            <span className="legend">live</span>
          </div>
          <AgentTableInner agents={agents.slice(0, 5)} compact />
        </div>

        <div className="panel">
          <div className="panel-head">
            <h3>Telemetry · requests / sec</h3>
            <span className="legend tlog">last 90s</span>
          </div>
          <div className="spark">
            {sparkData.map((h, i) => (
              <div key={i} className="bar" style={{ height: `${h}%` }} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0 18px 18px', fontSize: 11, color: 'var(--fg-4)', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
            <span>p50 · 4.2k/s</span>
            <span>p99 · 18.1k/s</span>
            <span>peak · 22.4k/s</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Threat feed</h3>
          <span className="legend tlog">streaming · auto</span>
        </div>
        <div className="feed">
          {feed.slice(0, 6).map((f, i) => (
            <div key={f.ts + i} className={'feed-row ' + f.sev + (f._new && i === 0 ? ' new' : '')}>
              <div className="ts">{f.ts}</div>
              <div className="desc">{f.desc}</div>
              <div className="sev">{f.sev === 'bad' ? 'Critical' : f.sev === 'warn' ? 'Warning' : 'Resolved'}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="dash-extra">
        <div className="panel">
          <div className="panel-head"><h3>Defense posture</h3><span className="legend tlog">7d avg</span></div>
          <Gauge value={94} label="composite score" />
        </div>
        <div className="panel">
          <div className="panel-head"><h3>Activity · 24h × agent</h3><span className="legend tlog">heatmap</span></div>
          <Heatmap />
        </div>
        <div className="panel">
          <div className="panel-head"><h3>Threats by class</h3><span className="legend tlog">30d</span></div>
          <Distribution />
        </div>
      </div>
    </>
  );
}

function Gauge({ value, label }) {
  const r = 56;
  const C = 2 * Math.PI * r;
  const dash = (value / 100) * C;
  return (
    <div className="gauge">
      <div className="gauge-ring">
        <svg width="132" height="132">
          <circle cx="66" cy="66" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6" />
          <circle cx="66" cy="66" r={r} fill="none"
                  stroke="var(--accent)" strokeWidth="6"
                  strokeDasharray={`${dash} ${C}`}
                  strokeLinecap="round"
                  style={{ filter: 'drop-shadow(0 0 8px rgba(var(--accent-rgb),0.6))' }} />
        </svg>
        <div className="gauge-value tlog">
          {value}<small>{label}</small>
        </div>
      </div>
      <div className="gauge-legend">+3 vs. last week</div>
    </div>
  );
}

function Heatmap() {
  // 6 agents x 24 hours
  const rows = ['SNL', 'WRD', 'ORC', 'SRG', 'CPH', 'NTR'];
  return (
    <div style={{ padding: '10px 18px 18px' }}>
      {rows.map((label, i) => (
        <div key={label} style={{ display: 'grid', gridTemplateColumns: '40px 1fr', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <span className="tlog" style={{ fontSize: 10, letterSpacing: '0.18em', color: 'var(--fg-4)' }}>{label}</span>
          <div className="heatmap" style={{ padding: 0 }}>
            {Array.from({ length: 24 }).map((_, h) => {
              // deterministic per (i,h)
              const v = Math.sin((i + 1) * 1.3 + h * 0.6) * 0.5 + Math.cos(h * 0.4 + i) * 0.3 + 0.5;
              const intensity = Math.max(0.06, Math.min(0.95, v));
              const bg = intensity > 0.8
                ? `rgba(255,90,78,${intensity})`
                : intensity > 0.6
                ? `rgba(255,181,71,${intensity * 0.9})`
                : `rgba(var(--accent-rgb),${intensity * 0.6})`;
              return <div key={h} className="cell" style={{ background: bg }} />;
            })}
          </div>
        </div>
      ))}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0 0 50px', fontSize: 10, color: 'var(--fg-4)', letterSpacing: '0.16em' }}>
        <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
      </div>
    </div>
  );
}

function Distribution() {
  const rows = [
    { lab: 'Prompt inject', val: 42, sev: 'bad' },
    { lab: 'Exfiltration',  val: 28, sev: 'bad' },
    { lab: 'Scope creep',   val: 19, sev: 'warn' },
    { lab: 'C2 beacon',     val: 14, sev: 'bad' },
    { lab: 'Cred stuffing', val: 11, sev: 'warn' },
    { lab: 'Insider drift', val:  6, sev: '' },
  ];
  return (
    <div className="distbar">
      {rows.map(r => (
        <div key={r.lab} className={'distbar-row ' + r.sev}>
          <span className="lab">{r.lab}</span>
          <div className="track"><div className="fill" style={{ width: (r.val / 42 * 100) + '%' }} /></div>
          <span className="val tlog">{r.val}</span>
        </div>
      ))}
    </div>
  );
}

function Kpi({ label, value, delta, alert, bad }) {
  return (
    <div className={'kpi' + (alert ? ' alert' : '')}>
      <div className="label">{label}</div>
      <div className="value tlog">{value}</div>
      <div className={'delta' + (bad ? ' bad' : '')}>{delta}</div>
    </div>
  );
}

function AgentTableInner({ agents, compact }) {
  return (
    <>
      <div className="agent-row head">
        <span>#</span>
        <span>Agent</span>
        <span>Status</span>
        <span>Risk</span>
        <span style={{ textAlign: 'right' }}>Perms</span>
      </div>
      {agents.map((a, i) => (
        <div className="agent-row" key={a.id}>
          <span className="tlog" style={{ color: 'var(--fg-4)' }}>{String(i + 1).padStart(2, '0')}</span>
          <div className="name">
            {a.id}
            <small>{a.owner} · {a.env}</small>
          </div>
          <div>
            <span className={'pill ' + a.status}>
              {a.status === 'bad' ? 'breached' : a.status === 'warn' ? 'monitoring' : 'healthy'}
            </span>
          </div>
          <div>
            <div className="risk-bar"><div className="fill" style={{ width: a.risk + '%' }} /></div>
            <div className="tlog" style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}>{a.risk}/100</div>
          </div>
          <div style={{ textAlign: 'right', color: 'var(--fg-2)' }} className="tlog">{a.perms}</div>
        </div>
      ))}
    </>
  );
}

function AgentTable({ agents }) {
  return <div className="panel"><AgentTableInner agents={agents} /></div>;
}

function Threats({ feed }) {
  return (
    <div className="panel">
      <div className="panel-head"><h3>Active threats</h3><span className="legend tlog">streaming</span></div>
      <div className="feed">
        {feed.map((f, i) => (
          <div key={f.ts + i} className={'feed-row ' + f.sev}>
            <div className="ts">{f.ts}</div>
            <div className="desc">{f.desc}</div>
            <div className="sev">{f.sev === 'bad' ? 'Critical' : f.sev === 'warn' ? 'Warning' : 'Resolved'}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Policies() {
  const rules = [
    { id: 'no-cross-tenant-read',     scope: 'all-prod',     status: 'enforced' },
    { id: 'pii-exfil-block',          scope: 'all',          status: 'enforced' },
    { id: 'tool-allowlist:finance',   scope: 'fin-*',        status: 'enforced' },
    { id: 'rate-limit:external-http', scope: 'all',          status: 'enforced' },
    { id: 'memory-redaction',         scope: 'support-*',    status: 'draft' },
  ];
  return (
    <div className="dash-grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
      <div className="panel">
        <div className="panel-head"><h3>Policy fleet</h3><span className="legend">5 rules</span></div>
        {rules.map(r => (
          <div className="agent-row" key={r.id} style={{ gridTemplateColumns: '1fr 1fr 100px' }}>
            <div className="name">{r.id}</div>
            <div className="tlog" style={{ color: 'var(--fg-3)' }}>{r.scope}</div>
            <div style={{ textAlign: 'right' }}>
              <span className={'pill ' + (r.status === 'enforced' ? 'good' : 'warn')}>{r.status}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="panel">
        <div className="panel-head"><h3>Source · no-cross-tenant-read</h3><span className="legend tlog">v1.4</span></div>
        <pre style={{ margin: 0, padding: 18, fontSize: 12, lineHeight: 1.7, color: 'var(--fg-2)', overflowX: 'auto', fontFamily: 'Sora' }}>
{`policy "no-cross-tenant-read" {
  match {
    agent.tool == "db.read"
    request.tenant != agent.tenant
  }
  effect = DENY
  on_deny = quarantine(agent, ttl="5m")
  notify  = ["sec-oncall", "owner"]
}`}
        </pre>
      </div>
    </div>
  );
}

function Audit() {
  const rows = [
    ['02:14:33', 'nomos42.intercept', 'ops-bot-3 · exfiltration blocked'],
    ['02:14:19', 'human.review',     'reviewer@acme · approved policy diff'],
    ['02:13:51', 'nomos42.deploy',    'no-cross-tenant-read → 12 agents'],
    ['02:13:02', 'nomos42.detect',    'prompt-injection in support-triage'],
    ['02:12:14', 'nomos42.patch',     'ml-data-loader → v0.93.2'],
    ['02:11:08', 'human.review',     'ciso@acme · acknowledged incident #2204'],
  ];
  return (
    <div className="panel">
      <div className="panel-head"><h3>Audit log</h3><span className="legend tlog">immutable · signed</span></div>
      {rows.map((r, i) => (
        <div className="agent-row" key={i} style={{ gridTemplateColumns: '110px 220px 1fr', fontFamily: 'Sora' }}>
          <span className="tlog" style={{ color: 'var(--fg-3)' }}>{r[0]}</span>
          <span className="tlog" style={{ color: 'var(--fg-2)' }}>{r[1]}</span>
          <span style={{ color: 'var(--fg)' }}>{r[2]}</span>
        </div>
      ))}
    </div>
  );
}

window.Dashboard = Dashboard;
