/* global React */

// ============ COVERAGE — three layers ============
function Coverage() {
  const layers = [
    {
      n: 'L1',
      title: 'Test \u2014 Red Team',
      sub: 'Attack your AI before an adversary does.',
      desc: 'Autonomous offensive agents probe every model, agent, tool call and MCP server. Direct and multi-turn prompt injection, tool abuse, prompt and data extraction, supply-chain integrity. Mapped to OWASP LLM Top 10 and MITRE ATLAS.',
      bullets: [
        'Prompt injection \u00b7 multi-turn Crescendo',
        'Tool abuse \u00b7 excessive agency',
        'System-prompt + data extraction',
        'Model & MCP supply-chain integrity',
      ],
      lead: 'Recon \u00b7 Injection \u00b7 Exploit',
    },
    {
      n: 'L2',
      title: 'Protect \u2014 Guard',
      sub: 'Runtime defense, inline, in your environment.',
      desc: 'A reverse-proxy gateway sits between your agents and the world. Hosted in your cloud, your region, your tenant \u2014 your code and data never leave. Zero-egress mode for air-gapped defense fleets.',
      bullets: [
        'Ingress / egress inspection',
        'Tool allowlists \u00b7 per-agent budgets',
        'Memory redaction \u00b7 re-grounding',
        'Network egress allowlist \u00b7 no decrypt',
      ],
      lead: 'Guard \u00b7 Egress guard',
    },
    {
      n: 'L3',
      title: 'Prove \u2014 Sovereign',
      sub: 'Signed evidence. EU data residency.',
      desc: 'Every action lands in an append-only, tamper-evident timeline and is mapped to the frameworks your auditors and regulators require. Sovereign by design \u2014 built for European defense, industry and public administration.',
      bullets: [
        'Append-only signed audit trail',
        'EU AI Act \u00b7 NIS2 evidence',
        'OWASP LLM \u00b7 MITRE ATLAS mapping',
        'EU data residency \u00b7 self-hosted',
      ],
      lead: 'Notary \u00b7 Archivist',
    },
  ];
  return (
    <section className="section coverage" data-screen-label="10 Coverage">
      <div className="container">
        <div className="section-head">
          <div>
            <span className="h-eyebrow"><span className="dot" /> Coverage · 10</span>
          </div>
          <div className="lead">
            <h2 className="h-section">One product.<br /><em>Test. Protect. Prove.</em></h2>
            <p className="lede">
              Nomos42 is not another point tool stitched onto your stack. One red team, one guard,
              one signed timeline — deployed inside your environment, so your code and data
              stay sovereign.
            </p>
          </div>
        </div>

        <div className="coverage-grid">
          {layers.map(l => (
            <article className="coverage-card" key={l.n}>
              <header>
                <span className="coverage-n tlog">{l.n}</span>
                <span className="sys-label">{l.lead}</span>
              </header>
              <h3>{l.title}</h3>
              <p className="coverage-sub">{l.sub}</p>
              <p>{l.desc}</p>
              <ul>
                {l.bullets.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </article>
          ))}
        </div>

        <div className="coverage-strip">
          {['OpenAI', 'Anthropic', 'Bedrock', 'Azure AI', 'LangChain', 'MCP', 'browser-use', 'Ollama', 'OWASP LLM', 'MITRE ATLAS', 'NIST AI RMF', 'EU AI Act'].map((b, i) => (
            <div key={i} className="coverage-strip-item">{b}</div>
          ))}
        </div>
      </div>
    </section>
  );
}

window.Coverage = Coverage;
