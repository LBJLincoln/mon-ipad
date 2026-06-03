/* global React, ReactDOM, useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakColor, TweakText, TweakSlider */
const { useEffect, useState } = React;

const ACCENT_OPTIONS = ['#E8FFF6', '#7DF9FF', '#FF8A3D', '#39FF7A'];

function hexToRgbStr(hex) {
  const h = hex.replace('#', '');
  const n = parseInt(h.length === 3
    ? h.split('').map(c => c + c).join('')
    : h, 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

function App() {
  const [t, setT] = useTweaks(/*EDITMODE-BEGIN*/{
    "accent": "#E8FFF6",
    "density": "default",
    "headline": "Protect your AI agents//and workflows."
  }/*EDITMODE-END*/);

  // Apply accent + density to root
  useEffect(() => {
    document.documentElement.style.setProperty('--accent', t.accent);
    document.documentElement.style.setProperty('--accent-rgb', hexToRgbStr(t.accent));
    document.body.setAttribute('data-density', t.density);
  }, [t.accent, t.density]);

  return (
    <>
      <Nav />
      <Hero headline={t.headline} accent={t.accent} />
      <Marquee />
      <Squad />
      <Intercept />
      <Coordination />
      <Dashboard />
      <Surface />
      <Globe />
      <Coverage />
      <Protocol />
      <CTA />
      <Footer />

      <TweaksPanel title="Tweaks · Nomos42">
        <TweakSection label="Accent">
          <TweakColor
            label="Accent color"
            value={t.accent}
            options={ACCENT_OPTIONS}
            onChange={(v) => setT('accent', v)}
          />
        </TweakSection>
        <TweakSection label="Density">
          <TweakRadio
            label="Section spacing"
            value={t.density}
            options={[
              { value: 'airy',    label: 'Airy' },
              { value: 'default', label: 'Default' },
              { value: 'dense',   label: 'Dense' },
            ]}
            onChange={(v) => setT('density', v)}
          />
        </TweakSection>
        <TweakSection label="Hero headline">
          <TweakText
            label="Use // to break the line. Second half renders dim."
            value={t.headline}
            onChange={(v) => setT('headline', v)}
          />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

function Nav() {
  return (
    <header className="nav">
      <div className="nav-logo">
        <span className="mark" />
        <span>NOMOS42</span>
      </div>
      <nav className="nav-links">
        <a href="#">Red Team</a>
        <a href="#">Guard</a>
        <a href="#">Coverage</a>
        <a href="#">Trust</a>
      </nav>
      <button className="nav-cta">Book a briefing</button>
    </header>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
