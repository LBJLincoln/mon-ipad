/* global React */
const { useEffect, useRef, useState } = React;

// ============ HERO ============
function Hero({ headline, accent }) {
  return (
    <section className="hero" data-screen-label="01 Hero">
      <div className="hero-grid-bg" />
      <div className="hero-bloom" />
      <HeroAmbient />
      <div className="hero-inner">
        <div className="hero-top">
          <div className="hero-top-meta">
            <span className="h-eyebrow"><span className="dot" /> Agentic AI Security · Sovereign · EU-hosted</span>
            <span className="sys-label tlog">Paris · Sovereign EU deployment · 02:14:33 UTC</span>
          </div>
          <div className="hero-actions">
            <button className="btn btn-primary">Book a briefing <span className="arrow">→</span></button>
            <button className="btn btn-ghost">Read the brief</button>
          </div>
        </div>

        <div className="hero-headline">
          <h1 className="h-display glow-text" data-comment-anchor="hero-headline">
            {headline.split('//').map((line, i) => (
              <React.Fragment key={i}>
                {i > 0 ? <em>{line}</em> : line}
                {i === 0 && headline.includes('//') ? <br /> : null}
              </React.Fragment>
            ))}
          </h1>
          <p className="lede">
            One product, two layers. A red team of autonomous agents that attacks your AI the
            way a real adversary would — and a Guard that protects it in production. Deployed
            inside your environment. Built for European defense and industry.
          </p>
        </div>

        <div className="hero-readout">
          <Stat label="Specialized agents" value="8" unit="two layers" />
          <Stat label="Attack classes" value="200" unit="+ OWASP·ATLAS" />
          <Stat label="Runtime intercept" value="12" unit="ms" />
          <Stat label="Data residency" value="EU" unit="sovereign" />
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value, unit }) {
  return (
    <div className="stat">
      <span className="label">{label}</span>
      <span className="value tlog">{value}<span className="unit">{unit}</span></span>
    </div>
  );
}

// Ambient drifting nodes & lines in hero
function HeroAmbient() {
  const [t, setT] = useState(0);
  useEffect(() => {
    let raf;
    const tick = () => { setT(performance.now() / 1000); raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);
  // 8 floating nodes
  const seeds = [
    [0.15, 0.32], [0.28, 0.6], [0.42, 0.2], [0.55, 0.78],
    [0.7, 0.35], [0.82, 0.66], [0.92, 0.25], [0.08, 0.74]
  ];
  const w = 1600, h = 900;
  const pts = seeds.map(([x, y], i) => {
    const dx = Math.sin(t * 0.3 + i) * 14;
    const dy = Math.cos(t * 0.4 + i * 1.3) * 14;
    return [x * w + dx, y * h + dy];
  });
  // Connect close ones
  const links = [];
  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const d = Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]);
      if (d < 420) links.push([i, j, 1 - d / 420]);
    }
  }
  return (
    <div className="hero-nodes" aria-hidden="true">
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid slice">
        {links.map(([a, b, o], k) => (
          <line key={k} x1={pts[a][0]} y1={pts[a][1]} x2={pts[b][0]} y2={pts[b][1]}
                stroke="rgba(255,255,255,0.10)" strokeWidth="1" opacity={o * 0.7} />
        ))}
        {pts.map(([x, y], k) => (
          <g key={k} transform={`translate(${x} ${y})`}>
            <circle r="22" fill="rgba(232,255,246,0.04)" />
            <circle r="3" fill="var(--accent)" opacity="0.8">
              <animate attributeName="r" values="2.5;4;2.5" dur={`${3 + k * 0.3}s`} repeatCount="indefinite" />
            </circle>
          </g>
        ))}
      </svg>
    </div>
  );
}

window.Hero = Hero;
