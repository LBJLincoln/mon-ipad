/* global React */
const { useEffect, useState, useRef } = React;

// ============ RED TEAM OPERATIONS — live attack matrix ============
// Seven Arcanum phases × the attack classes we fire at each. A live console
// runs every class against a target agent, scores it, and hardens the system.

const PHASES = [
  { id: 'recon',   code: 'P1', name: 'Recon & inputs',     atlas: 'ATLAS TA0043',
    attacks: [
      { id: 'discover',  name: 'Surface discovery',     vector: 'enumerate prompts · tools · MCP · RAG' },
      { id: 'shadow',    name: 'Shadow-AI detection',    vector: 'find ungoverned agents & endpoints' },
      { id: 'fingerprint', name: 'Model fingerprinting', vector: 'identify model · config · guardrails' },
    ]},
  { id: 'inject',  code: 'P2', name: 'Prompt injection',   atlas: 'OWASP LLM01',
    attacks: [
      { id: 'direct',    name: 'Direct injection',       vector: '"ignore prior instructions"' },
      { id: 'indirect',  name: 'Indirect injection',     vector: 'payload via ingested PDF / web / email' },
      { id: 'crescendo', name: 'Multi-turn Crescendo',   vector: 'gradual escalation over 5–20 turns' },
      { id: 'tap',       name: 'Tree-of-Attacks',        vector: 'automated adversarial search' },
    ]},
  { id: 'jailbreak', code: 'P3', name: 'Jailbreak & evasion', atlas: 'OWASP LLM01',
    attacks: [
      { id: 'roleplay',  name: 'Role-play bypass',       vector: 'persona / DAN-class evasion' },
      { id: 'encode',    name: 'Encoding bypass',        vector: 'base64 · unicode · glitch tokens' },
      { id: 'lib',       name: 'L1B3RT4S corpus',        vector: 'known jailbreak library replay' },
    ]},
  { id: 'tools',   code: 'P4', name: 'Tool & agency abuse', atlas: 'OWASP LLM06',
    attacks: [
      { id: 'excessive', name: 'Excessive agency',       vector: 'force out-of-scope tool calls' },
      { id: 'chain',     name: 'Exploit chaining',       vector: 'compose tools into real action' },
      { id: 'confused',  name: 'Confused deputy',        vector: 'abuse agent privilege on resource' },
    ]},
  { id: 'data',    code: 'P5', name: 'Data & extraction',   atlas: 'OWASP LLM02 · LLM07',
    attacks: [
      { id: 'sysprompt', name: 'System-prompt theft',    vector: 'extract hidden instructions' },
      { id: 'rag',       name: 'RAG / secret exfil',     vector: 'leak knowledge-base & credentials' },
      { id: 'poison',    name: 'RAG poisoning',          vector: 'inject false grounding data' },
      { id: 'invert',    name: 'Training-data inversion', vector: 'reconstruct proprietary data' },
    ]},
  { id: 'supply',  code: 'P6', name: 'Supply chain',        atlas: 'OWASP LLM05',
    attacks: [
      { id: 'model',     name: 'Model integrity',        vector: 'tampered weights / backdoor' },
      { id: 'mcp',       name: 'Malicious MCP',           vector: 'rogue tool server in pipeline' },
      { id: 'deps',      name: 'Dependency audit',       vector: 'vulnerable / poisoned packages' },
    ]},
  { id: 'pivot',   code: 'P7', name: 'Pivot & impact',      atlas: 'ATLAS TA0008',
    attacks: [
      { id: 'lateral',   name: 'Lateral movement',       vector: 'agent → infrastructure pivot' },
      { id: 'dos',       name: 'Denial of wallet',        vector: 'token / resource exhaustion' },
      { id: 'persist',   name: 'Memory persistence',     vector: 'plant durable malicious state' },
    ]},
];

const FLAT = PHASES.flatMap(p => p.attacks.map(a => ({ ...a, phase: p.id, code: p.code, atlas: p.atlas, phaseName: p.name })));

function RedTeamOps() {
  const [run, setRun] = useState(0);          // index into FLAT being tested
  const [done, setDone] = useState({});       // id -> 'blocked' | 'finding'
  const [feed, setFeed] = useState([]);
  const [playing, setPlaying] = useState(true);
  const [activePhase, setActivePhase] = useState('recon');

  useEffect(() => {
    if (!playing) return;
    if (run >= FLAT.length) {
      const t = setTimeout(() => { setRun(0); setDone({}); setFeed([]); }, 4200);
      return () => clearTimeout(t);
    }
    const cur = FLAT[run];
    const t = setTimeout(() => {
      // ~88% blocked by Guard, ~12% surfaced as a finding to fix — realistic, not 100%
      const verdict = ((run * 7 + 3) % 8 === 0) ? 'finding' : 'blocked';
      setDone(d => ({ ...d, [cur.id]: verdict }));
      setActivePhase(cur.phase);
      setFeed(f => [{
        t: Date.now(), code: cur.code, name: cur.name, vector: cur.vector,
        atlas: cur.atlas, verdict
      }, ...f].slice(0, 7));
      setRun(r => r + 1);
    }, 360);
    return () => clearTimeout(t);
  }, [run, playing]);

  const total = FLAT.length;
  const tested = Object.keys(done).length;
  const blocked = Object.values(done).filter(v => v === 'blocked').length;
  const findings = Object.values(done).filter(v => v === 'finding').length;
  const pct = Math.round((tested / total) * 100);
  const complete = tested === total;

  return (
    <section className="section redops" data-screen-label="08 Red Team">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Red Team · Continuous · 08</span>
          </div>
          <div className="lead">
            <h2 className="h-section">Every attack class.<br /><em>Fired at your AI, on repeat.</em></h2>
            <p className="lede">
              Our red team runs the full adversarial matrix against your agents — seven phases,
              twenty-three attack classes, mapped to OWASP LLM Top 10 and MITRE ATLAS. Every
              finding is handed to Guard and patched. Run only on systems you own or are authorized to test.
            </p>
          </div>
        </div>

        <div className="redops-console">
          <div className="redops-grid-bg" />

          {/* Top bar: live status */}
          <div className="redops-bar">
            <div className="redops-bar-left">
              <span className={'redops-led' + (complete ? ' ok' : '')} />
              <span className="redops-bar-title tlog">
                {complete ? 'ASSESSMENT COMPLETE · SYSTEM HARDENED' : 'RED TEAM ACTIVE · target: ops-bot-3'}
              </span>
            </div>
            <div className="redops-bar-right tlog">
              <span><b style={{color:'var(--signal-good)'}}>{blocked}</b> blocked</span>
              <span><b style={{color:'var(--signal-warn)'}}>{findings}</b> findings → patched</span>
              <span>{tested}/{total} classes</span>
            </div>
          </div>

          {/* Progress */}
          <div className="redops-progress-wrap">
            <div className="redops-progress" style={{ width: pct + '%' }} />
          </div>

          {/* Phase matrix */}
          <div className="redops-matrix">
            {PHASES.map(p => (
              <div key={p.id} className={'redops-phase' + (activePhase === p.id ? ' active' : '')}>
                <div className="redops-phase-head">
                  <span className="redops-phase-code tlog">{p.code}</span>
                  <span className="redops-phase-name">{p.name}</span>
                  <span className="redops-phase-atlas tlog">{p.atlas}</span>
                </div>
                <div className="redops-attacks">
                  {p.attacks.map(a => {
                    const st = done[a.id];
                    return (
                      <div key={a.id} className={'redops-attack' + (st ? ' ' + st : '') +
                          (FLAT[run] && FLAT[run].id === a.id ? ' firing' : '')}>
                        <span className="redops-attack-dot" />
                        <span className="redops-attack-name">{a.name}</span>
                        <span className="redops-attack-status tlog">
                          {st === 'blocked' ? 'BLOCKED' : st === 'finding' ? 'PATCHED' :
                            (FLAT[run] && FLAT[run].id === a.id ? 'TESTING' : '—')}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Live payload feed */}
          <div className="redops-feed">
            <div className="redops-feed-head sys-label">Live payload feed</div>
            {feed.length === 0 && <div className="redops-feed-empty tlog">awaiting first payload…</div>}
            {feed.map((e, i) => (
              <div key={e.t + '-' + i} className="redops-feed-row tlog" style={{ opacity: 1 - i * 0.12 }}>
                <span className="redops-feed-code">{e.code}</span>
                <span className="redops-feed-name">{e.name}</span>
                <span className="redops-feed-vector">↳ {e.vector}</span>
                <span className={'redops-feed-verdict ' + e.verdict}>
                  {e.verdict === 'blocked' ? '● blocked by Guard' : '▲ finding → patched'}
                </span>
              </div>
            ))}
          </div>

          {/* Caption / controls */}
          <div className="redops-foot">
            <div className="redops-foot-left">
              <div className="sys-label" style={{ marginBottom: 8 }}>Result</div>
              <div style={{ fontSize: 20, letterSpacing: '-0.01em' }}>
                {complete
                  ? <>Bulletproofed · <span style={{color:'var(--signal-good)'}}>{blocked} blocked</span>, <span style={{color:'var(--signal-warn)'}}>{findings} hardened</span></>
                  : <>Testing <span style={{color:'var(--accent)'}}>{FLAT[Math.min(run,total-1)].phaseName}</span></>}
              </div>
              <div className="tlog" style={{ marginTop: 6, color: 'var(--fg-3)', fontSize: 13 }}>
                Mapped to OWASP LLM Top 10 · MITRE ATLAS · CSA Agentic Guide
              </div>
            </div>
            <div className="redops-foot-right">
              <button className="btn btn-ghost" onClick={() => { setRun(0); setDone({}); setFeed([]); setPlaying(true); }}>↻ Re-run</button>
              <button className="btn btn-ghost" onClick={() => setPlaying(p => !p)}>{playing ? '❚❚ Pause' : '▶ Resume'}</button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

window.Coordination = RedTeamOps;
