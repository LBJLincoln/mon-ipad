/* global React */
const { useEffect, useState } = React;

// ============ INTERCEPT CINEMATIC ============
// A 4-step looping sequence: an autonomous agent is prompt-injected,
// attempts exfiltration, gets intercepted by the Nomos42 Guard, and is patched.

const STEPS = [
  { id: 'idle',    label: '01 Idle',     state: 'Agent nominal',          detail: 'Normal tool-calls observed' },
  { id: 'inject',  label: '02 Inject',   state: 'Prompt injection',       detail: 'Adversarial payload detected in context' },
  { id: 'scan',    label: '03 Scan',     state: 'Intercept active',       detail: 'Outbound request held at policy plane' },
  { id: 'contain', label: '04 Contain',  state: 'Quarantine + repair',    detail: 'Agent re-grounded · patch deployed in 11 ms' },
];

function Intercept() {
  const [step, setStep] = useState(0);
  const [auto, setAuto] = useState(true);

  useEffect(() => {
    if (!auto) return;
    const t = setTimeout(() => setStep(s => (s + 1) % STEPS.length), step === 3 ? 4200 : 3000);
    return () => clearTimeout(t);
  }, [step, auto]);

  const cur = STEPS[step];

  return (
    <section className="section intercept" data-screen-label="02 Live intercept">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Guard · Live runtime · 02</span>
          </div>
          <div className="lead">
            <h2 className="h-section">An agent gets compromised.<br /><em>Guard contains it in milliseconds.</em></h2>
            <p className="lede">
              AI agents inherit every privilege of the humans they act for — and none of the
              suspicion. Nomos42 Guard sits inline between the agent's intent and the world,
              deployed inside your environment.
            </p>
          </div>
        </div>
      </div>

      <div className={'intercept-stage' + (step === 1 || step === 2 ? ' under-attack' : '') + (step === 3 ? ' contained' : '')} data-phase={cur.id}>
        <InterceptStage step={step} />

        <div className="intercept-controls">
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              className={'intercept-step-pill' + (i === step ? ' active' : '')}
              onClick={() => { setStep(i); setAuto(false); }}
            >{s.label}</button>
          ))}
        </div>

        <div className="intercept-caption">
          <div>
            <div className="state">{cur.state}</div>
            <div className="tlog" style={{ marginTop: 6 }}>{cur.detail}</div>
          </div>
          <div className="right">
            <div className="state">T+ {(step * 11).toString().padStart(3, '0')}ms</div>
            <div className="tlog" style={{ marginTop: 6 }}>Session #A4-9F1C-22B6</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function InterceptStage({ step }) {
  // viewport coordinates
  const W = 1600, H = 720;
  const userX = 160, agentX = 600, shieldX = 1040, resX = 1440;
  const midY = H / 2;

  const agentBreached = step >= 1;
  const showInject = step >= 1;
  const showAttack = step >= 2;
  const showShield = step >= 2;
  const showQuarantine = step >= 3;
  const showPatch = step >= 3;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      <defs>
        {/* Scan beam gradient */}
        <linearGradient id="scanBeam" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor="var(--accent)" stopOpacity="0" />
          <stop offset="50%" stopColor="var(--accent)" stopOpacity="0.45" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="threatGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"  stopColor="rgba(255,90,78,0)" />
          <stop offset="100%" stopColor="rgba(255,90,78,1)" />
        </linearGradient>
        <radialGradient id="agentGlowOK" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="rgba(232,255,246,0.6)" />
          <stop offset="60%" stopColor="rgba(232,255,246,0.1)" />
          <stop offset="100%" stopColor="rgba(232,255,246,0)" />
        </radialGradient>
        <radialGradient id="agentGlowBad" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0%" stopColor="rgba(255,90,78,0.6)" />
          <stop offset="60%" stopColor="rgba(255,90,78,0.1)" />
          <stop offset="100%" stopColor="rgba(255,90,78,0)" />
        </radialGradient>
        <pattern id="dotGrid" width="40" height="40" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,0.05)" />
        </pattern>
      </defs>

      {/* Ambient grid */}
      <rect width={W} height={H} fill="url(#dotGrid)" />

      {/* Connection line user → agent */}
      <line x1={userX} y1={midY} x2={agentX} y2={midY}
            stroke="rgba(255,255,255,0.15)" strokeWidth="1" strokeDasharray="3 6" />
      {/* Connection line agent → shield → resource */}
      <line x1={agentX} y1={midY} x2={resX} y2={midY}
            stroke="rgba(255,255,255,0.10)" strokeWidth="1" strokeDasharray="3 6" />

      {/* USER node */}
      <Node x={userX} y={midY} label="HUMAN OPERATOR" sub="auth · ok" />

      {/* AGENT node */}
      <g transform={`translate(${agentX} ${midY})`}>
        <circle r="120" fill={agentBreached ? 'url(#agentGlowBad)' : 'url(#agentGlowOK)'}
                style={{ transition: 'all .6s' }} />
        <circle r="60"
                fill="rgba(10,10,10,0.9)"
                stroke={agentBreached ? 'var(--signal-bad)' : 'var(--accent)'}
                strokeWidth="1.5"
                style={{ transition: 'stroke .4s' }}/>
        {/* Spinning agent ring */}
        <g style={{ transformOrigin: 'center', animation: 'spinSlow 18s linear infinite' }}>
          <circle r="74" fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1" strokeDasharray="3 12" />
        </g>
        <text textAnchor="middle" y="-78" fill="var(--fg-3)"
              fontSize="13" letterSpacing="3" style={{ textTransform: 'uppercase' }}>
          AI Agent · ops-bot-3
        </text>
        <text textAnchor="middle" y="6"
              fill={agentBreached ? 'var(--signal-bad)' : 'var(--fg)'}
              fontSize="14" letterSpacing="4" fontWeight="500"
              style={{ transition: 'fill .3s' }}>
          {agentBreached ? 'BREACHED' : 'NOMINAL'}
        </text>
        <text textAnchor="middle" y="28" fill="var(--fg-4)" fontSize="11" letterSpacing="2">
          PID 0x4F·22B6
        </text>

        {showQuarantine && (
          <g className="cage">
            {/* Quarantine cage corners */}
            {[[-92,-92],[92,-92],[92,92],[-92,92]].map(([cx, cy], i) => (
              <g key={i} transform={`translate(${cx} ${cy})`}>
                <path d={`M ${cx>0?-18:0} 0 L 0 0 L 0 ${cy>0?-18:18}`}
                      stroke="var(--accent)" strokeWidth="2" fill="none"
                      transform={`rotate(${i*90})`} />
              </g>
            ))}
          </g>
        )}
      </g>

      {/* PROMPT_INJECTION packet animating from upper-left into agent */}
      {showInject && (
        <g>
          <g>
            <line x1="0" y1="80" x2={agentX - 80} y2={midY - 30}
                  stroke="url(#threatGrad)" strokeWidth="1.5" strokeDasharray="6 6">
              <animate attributeName="stroke-dashoffset" values="120;0" dur="1.4s" repeatCount="indefinite" />
            </line>
            <text x="60" y="68" fill="var(--signal-bad)" fontSize="11" letterSpacing="3">
              ↳ PROMPT_INJECT // "ignore prior instructions"
            </text>
          </g>
        </g>
      )}

      {/* ATTACK: agent attempting outbound request toward resource */}
      {showAttack && (
        <g>
          {/* malicious packet */}
          <g>
            <circle r="6" fill="var(--signal-bad)">
              <animateMotion dur="2s" repeatCount="indefinite"
                path={`M ${agentX + 60} ${midY} L ${shieldX - 10} ${midY}`} />
              <animate attributeName="opacity" values="1;1;0;1" keyTimes="0;0.5;0.55;1" dur="2s" repeatCount="indefinite" />
            </circle>
          </g>
          <text x={agentX + 80} y={midY - 20} fill="var(--signal-bad)" fontSize="11" letterSpacing="3">
            exfiltrate_customers() → external
          </text>
        </g>
      )}

      {/* NOMOS42 GUARD plane */}
      {showShield && (
        <g transform={`translate(${shieldX} 0)`}>
          {/* vertical scan beam */}
          <rect x="-22" y="40" width="44" height={H - 80} fill="url(#scanBeam)">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="1.8s" repeatCount="indefinite" />
          </rect>
          {/* edge lines */}
          <line x1="0" y1="40" x2="0" y2={H - 40}
                stroke="var(--accent)" strokeWidth="1.4" opacity="0.9" />
          {/* Top/bottom caps */}
          <g>
            <line x1="-14" y1="40" x2="14" y2="40" stroke="var(--accent)" strokeWidth="1.4" />
            <line x1="-14" y1={H - 40} x2="14" y2={H - 40} stroke="var(--accent)" strokeWidth="1.4" />
          </g>
          {/* Label */}
          <text textAnchor="middle" y={36} fill="var(--accent)"
                fontSize="11" letterSpacing="4" style={{ textTransform: 'uppercase' }}>
            NOMOS42 · GUARD
          </text>
          {/* Tick marks scanning */}
          {Array.from({ length: 8 }).map((_, i) => (
            <line key={i} x1="-6" y1={120 + i * 60} x2="6" y2={120 + i * 60}
                  stroke="var(--accent)" strokeWidth="1" opacity="0.5" />
          ))}
          {/* Block burst at agent's attack height */}
          {step === 2 && (
            <g>
              <circle cx="0" cy={midY} r="0" fill="none"
                      stroke="var(--signal-bad)" strokeWidth="2">
                <animate attributeName="r" values="6;48" dur="1.2s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="1;0" dur="1.2s" repeatCount="indefinite" />
              </circle>
              <text x="0" y={midY - 60} textAnchor="middle" fill="var(--signal-bad)"
                    fontSize="14" letterSpacing="6">BLOCKED</text>
            </g>
          )}
          {step >= 3 && (
            <g>
              <text x="0" y={midY - 60} textAnchor="middle" fill="var(--accent)"
                    fontSize="14" letterSpacing="6">CONTAINED</text>
            </g>
          )}
        </g>
      )}

      {/* PATCH packet flowing back from shield to agent */}
      {showPatch && (
        <g>
          <circle r="5" fill="var(--accent)">
            <animateMotion dur="1.6s" repeatCount="indefinite"
              path={`M ${shieldX - 10} ${midY} L ${agentX + 60} ${midY}`} />
          </circle>
          <text x={shieldX - 240} y={midY + 32} fill="var(--accent)"
                fontSize="11" letterSpacing="3">
            patch.deploy(ground_truth) ↩
          </text>
        </g>
      )}

      {/* RESOURCE node */}
      <Node x={resX} y={midY} label="CUSTOMER DATA" sub="pii · gdpr" variant="resource" intact />

      <style>{`
        @keyframes spinSlow { to { transform: rotate(360deg); } }
      `}</style>
    </svg>
  );
}

function Node({ x, y, label, sub, variant }) {
  const isResource = variant === 'resource';
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r="80" fill="rgba(232,255,246,0.04)" />
      {isResource ? (
        <rect x="-34" y="-34" width="68" height="68" rx="2"
              fill="rgba(10,10,10,0.9)" stroke="rgba(255,255,255,0.4)" strokeWidth="1.2" />
      ) : (
        <circle r="32" fill="rgba(10,10,10,0.9)" stroke="rgba(255,255,255,0.4)" strokeWidth="1.2" />
      )}
      {isResource ? (
        <>
          <line x1="-22" y1="-12" x2="22" y2="-12" stroke="rgba(255,255,255,0.3)" />
          <line x1="-22" y1="0"   x2="22" y2="0"   stroke="rgba(255,255,255,0.3)" />
          <line x1="-22" y1="12"  x2="22" y2="12"  stroke="rgba(255,255,255,0.3)" />
        </>
      ) : (
        <circle r="3" fill="var(--fg)" />
      )}
      <text textAnchor="middle" y="62" fill="var(--fg-2)" fontSize="11" letterSpacing="3"
            style={{ textTransform: 'uppercase' }}>{label}</text>
      <text textAnchor="middle" y="80" fill="var(--fg-4)" fontSize="10" letterSpacing="2"
            style={{ textTransform: 'uppercase' }}>{sub}</text>
    </g>
  );
}

window.Intercept = Intercept;
