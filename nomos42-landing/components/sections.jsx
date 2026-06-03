/* global React */

// ============ 3-STEP PROTOCOL ============
function Protocol() {
  const steps = [
    {
      n: '01 / Observe',
      title: 'Full-fidelity telemetry of every agent action.',
      body: 'Every prompt, tool call, retrieval, and outbound packet is recorded into a signed, tamper-evident timeline. Zero blind spots across LangChain, OpenAI, Anthropic, custom runtimes.',
      visual: 'kernel-level shim · 3 lines of code',
    },
    {
      n: '02 / Reason',
      title: 'A purpose-built model judges intent in 11 ms.',
      body: 'Our security model is trained on millions of AI attack traces — prompt injection, scope creep, tool abuse, data exfiltration. It scores every action against policy in real time.',
      visual: 'Nomos-Guard · self-hosted · EU region',
    },
    {
      n: '03 / Repair',
      title: 'Contain, re-ground, and patch — autonomously.',
      body: 'On detection: quarantine, revoke creds, re-ground the agent context with verified truth, deploy a policy patch across the fleet. No pager. No war room. No leak.',
      visual: 'mean time to repair · 11 ms',
    },
  ];
  return (
    <section className="section protocol" data-screen-label="05 Protocol">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Protocol · 05</span>
          </div>
          <div className="lead">
            <h2 className="h-section">Three movements. Continuous.<br /><em>Observe. Reason. Repair.</em></h2>
            <p className="lede">
              The Nomos42 Guard loop runs at the speed of the agent itself — inline, inside your
              environment, with a human in the loop only where you require one.
            </p>
          </div>
        </div>
      </div>
      <div className="protocol-grid">
        {steps.map((s, i) => (
          <div className="protocol-step" key={i}>
            <span className="num tlog">{s.n}</span>
            <h3>{s.title}</h3>
            <p>{s.body}</p>
            <div className="visual">↳ {s.visual}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ============ CTA ============
function CTA() {
  return (
    <section className="cta" data-screen-label="06 CTA">
      <div className="cta-bloom" />
      <div className="cta-inner">
        <span className="h-eyebrow"><span className="dot" /> Now onboarding · European design partners</span>
        <h2 className="glow-text">
          Your AI agents are already in production.<br />
          <em>Their security isn't.</em>
        </h2>
        <p className="lede" style={{ maxWidth: '46ch', margin: '0 auto', textAlign: 'center' }}>
          We're onboarding a small number of European design partners in defense and industry.
          Bring your most adversarial AI workload — we'll bring the red team and the guard.
        </p>
        <div className="cta-actions">
          <button className="btn btn-primary">Book a briefing <span className="arrow">→</span></button>
          <button className="btn btn-ghost">Download the brief (PDF)</button>
        </div>
      </div>
    </section>
  );
}

// ============ FOOTER ============
function Footer() {
  return (
    <>
      <footer className="footer">
        <div>
          <div className="nav-logo" style={{ marginBottom: 18 }}>
            <span className="mark" />
            <span>NOMOS42</span>
          </div>
          <p style={{ color: 'var(--fg-3)', fontSize: 12, lineHeight: 1.6, maxWidth: 28 + 'ch' }}>
            The sovereign security layer for agentic AI. Red team and guard, in one product. Built in Europe.
          </p>
        </div>
        <div>
          <h5>Platform</h5>
          <ul>
            <li><a href="#">Red Team</a></li>
            <li><a href="#">Guard</a></li>
            <li><a href="#">Compliance</a></li>
            <li><a href="#">Integrations</a></li>
          </ul>
        </div>
        <div>
          <h5>Company</h5>
          <ul>
            <li><a href="#">Manifesto</a></li>
            <li><a href="#">Research</a></li>
            <li><a href="#">Careers · 12 open</a></li>
            <li><a href="#">Press</a></li>
          </ul>
        </div>
        <div>
          <h5>Trust</h5>
          <ul>
            <li><a href="#">EU AI Act</a></li>
            <li><a href="#">NIS2</a></li>
            <li><a href="#">ISO 27001</a></li>
            <li><a href="#">Data residency · EU</a></li>
          </ul>
        </div>
      </footer>
      <div className="footer-bottom">
        <span>© 2026 Nomos42</span>
        <span className="tlog">v1.0 · EU-hosted · sovereign</span>
      </div>
    </>
  );
}

// ============ MARQUEE ============
function Marquee() {
  const items = [
    'EU AI Act compliant',
    'SOC 2 Type II',
    'ISO 27001',
    'Self-hosted',
    'NIS2 ready',
    'Zero-egress mode',
    'Air-gap ready',
    'OWASP LLM Top 10',
    'MITRE ATLAS',
    'NIST AI RMF',
    'EU data residency',
    'Defense & Industry',
  ];
  return (
    <div className="scroll-marquee">
      <div className="marquee-track">
        {[...items, ...items, ...items].map((it, i) => <span key={i}>{it}</span>)}
      </div>
    </div>
  );
}

window.Protocol = Protocol;
window.CTA = CTA;
window.Footer = Footer;
window.Marquee = Marquee;
