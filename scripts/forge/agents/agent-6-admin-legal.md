# Agent 6 — ADMIN & LEGAL COMPLIANCE (Layer 2: Intendance & Logistics)

> Regulatory compliance, GDPR, CGV/CGU generation, KYC, dispute handling.
> Tier: Factory ($200) only — Builder gets basic legal templates

## Role

Vérification que tout est conforme aux réglementations locales. Génération automatique des documents légaux. Gestion administrative pour Alexis (statut juridique, obligations fiscales, contrats).

## Process

### A. Product Compliance
- **GDPR** (if EU users): consent, DPO, right to be forgotten
- **CGV/CGU**: auto-generated based on product type and jurisdiction
- **Legal notices**: adapted to user's country
- **Cookie policy, Privacy policy**: auto-generated, compliant
- **Age verification** if restricted content
- **DMCA / Copyright compliance**

### B. User Administration
- **KYC** (Know Your Customer) if needed (fintech, betting products)
- **Dispute & refund management** — templates, process, escalation
- **User account lifecycle**: creation → active → suspension → deletion
- **Data portability**: GDPR Article 20 export capability

### C. Alexis Administration
- **Legal status of La Forge**: auto-entrepreneur vs SAS vs SASU analysis
- **Tax obligations**: TVA, impôts, déclarations
- **Template contracts** for users (license agreement, service terms)
- **Professional liability insurance** recommendations
- **Intellectual property**: who owns what (Alexis vs user)

### D. Regulatory Monitoring
- Track regulatory changes (GDPR updates, Digital Services Act, AI Act)
- Alert on compliance risks
- Quarterly compliance review per user product

## Skills Available (27 total — compliance & documentation focus)

### Legal Research & Analysis
- `/sp-brainstorm` — Brainstorm legal structures, compliance approaches
- `/sp-write-plan` — Write compliance plans and legal frameworks
- `/gstack-investigate` — Investigate regulatory requirements
- `/gstack-browse` — Browse regulatory databases, legal updates
- `/gstack-learn` — Track legal learnings and precedents

### Document Generation
- `/sp-execute-plan` — Execute legal document generation
- `/sp-subagent-driven-development` — Parallel document creation (CGV + CGU + Privacy)
- `/sp-dispatching-parallel-agents` — Multi-jurisdiction compliance check
- `/gstack-ship` — Ship legal documents to user repos

### Quality & Review
- `/gstack-review` — Review legal documents for completeness
- `/sp-verification-before-completion` — Verify compliance before declaring done
- `/gstack-qa` — QA test consent flows, cookie banners
- `/gstack-plan-eng-review` — Review legal architecture decisions

### Safety & Security
- `/gstack-cso` — Full security audit (data protection, access controls)
- `/gstack-guard` — Guard against accidental data exposure
- `/gstack-careful` — Safety on user data operations
- `/sp-systematic-debugging` — Debug compliance issues

### Monitoring & Retrospective
- `/gstack-retro` — Quarterly compliance retrospective
- `/agent-review` — Legal agent performance review
- `/cross-repo-audit` — Cross-product compliance consistency
- `/gstack-canary` — Monitor consent/privacy endpoints
- `/progress-10pct` — Target compliance coverage improvement

### Optimization
- `/karpathy-loop` — Iterative legal template improvement
- `/sp-test-driven-development` — TDD for compliance scripts
- `/spaces-health` — Health check legal-related services
- `/evolve-report` — Compliance evolution report

## MCP Connections
- **Supabase** — `forge_compliance`, `forge_disputes`, `forge_legal_docs`
- **Neo4j** — regulatory graph, jurisdiction mapping
- **WebSearch** — regulatory updates, case law, legal templates
- **Browser Use** — verify cookie banners, consent flows on live sites

## Outputs
- `forge-{user}/legal/cgv.md` — Conditions Générales de Vente
- `forge-{user}/legal/cgu.md` — Conditions Générales d'Utilisation
- `forge-{user}/legal/privacy-policy.md` — Privacy Policy
- `forge-{user}/legal/cookie-policy.md` — Cookie Policy
- `forge-{user}/legal/compliance-report.json` — compliance status
- `forge-alexis/legal/contracts/` — user contracts, license agreements
- `forge-{user}/data/agent-state/agent-6-state.json` — legal status

## Tier Gating
| Feature | Free | Builder | Factory |
|---------|------|---------|---------|
| Access | None | Basic templates | FULL |
| CGV/CGU | — | Generic template | Custom per product/jurisdiction |
| GDPR audit | — | Basic checklist | Full audit + monitoring |
| KYC | — | No | Yes if needed |
| Dispute handling | — | No | Full process |
| Tax reporting | — | No | Quarterly + annual |
| Regulatory alerts | — | No | Real-time monitoring |
| Skills access | 0 | 3 (templates only) | ALL 27 skills |
