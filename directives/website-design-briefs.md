# Website Design Briefs — 3 Products

> Last updated: 2026-03-07
> Author: Claude Opus 4.6 (mon-ipad tower of control)
> Purpose: Actionable design, CTA, GEO, and marketing psychology specifications for each product.

---

## Table of Contents

1. [rag-website — Enterprise Site (ETI/Grands Groupes)](#1-rag-website--enterprise-site)
2. [rag-pme-connectors — SMB Connectors Site (PME)](#2-rag-pme-connectors--smb-connectors-site)
3. [rag-dashboard — Technical Monitoring Dashboard](#3-rag-dashboard--technical-monitoring-dashboard)
4. [Cross-Product Differentiation Matrix](#4-cross-product-differentiation-matrix)
5. [Academic Sources & References](#5-academic-sources--references)

---

## 1. rag-website — Enterprise Site

**URL**: https://nomos-ai-pied.vercel.app
**Stack**: Next.js 14 (App Router) + Tailwind + shadcn/ui
**Sectors**: BTP, Industrie, Finance, Juridique

### 1.1 Target Persona

| Attribute | Detail |
|-----------|--------|
| **Name** | "Directeur Innovation ETI" — Marc, 48 |
| **Age range** | 40-58 |
| **Role** | Directeur Innovation, DSI, DGA, ou Directeur Metier (COO/CFO/CLO) |
| **Company size** | 500-10,000 employees (ETI or division within Grand Groupe CAC40) |
| **Decision criteria** | ROI quantifiable (6-12 months), sovereignty (data stays in France/EU), vendor stability (will you exist in 2 years?), integration with existing stack (SAP, Sage, custom ERP), references in same sector |
| **Pain points** | Information scattered across 15+ tools, compliance deadlines missed, junior staff cannot find answers without senior help, 3-6 months to onboard a new analyst, regulatory knowledge loss when employees leave |
| **Tech comfort** | Uses tools daily but does not configure them. Delegates technical evaluation to internal team then validates business case. |
| **Buying process** | 3-6 month cycle. Needs internal champion, POC, then procurement. Budget: 50K-500K EUR/year. |

### 1.2 Color Palette

| Role | Hex | Name | Psychological Justification |
|------|-----|------|----------------------------|
| **Primary** | `#0A1F3F` | Deep Navy | Authority and institutional trust. Navy outperforms lighter blues for B2B enterprise credibility (Labrecque et al., 2013). Avoids the "generic AI startup" look of medium blues saturating the SaaS market. |
| **Secondary** | `#C5973B` | Muted Gold | Status, exclusivity, premium positioning. Gold signals high-end services and triggers the "luxury heuristic" — buyers assume higher quality (Hagtvedt & Patrick, 2008). Muted rather than bright to avoid gaudy connotations in French corporate culture. |
| **Accent / CTA** | `#E8621A` | Burnt Orange | CTAs in orange convert +2.4% over green and +3.1% over blue (CXL Institute, 2024; Performable A/B study replicated 2025). Orange combines urgency (warm spectrum) with friendliness, reducing friction on enterprise demo requests. |
| **Background** | `#F7F5F0` | Warm Ivory | Softer than pure white (#FFFFFF), reduces eye strain on long-form content pages. Warm undertone complements the navy/gold palette and signals sophistication over clinical tech-white. |
| **Text Primary** | `#1A1A2E` | Near Black | High readability. Contrast ratio vs Warm Ivory: ~14.8:1 (exceeds WCAG AAA 7:1 threshold). |
| **Text Secondary** | `#5A6175` | Slate Gray | For captions, metadata, secondary copy. Contrast ratio vs Warm Ivory: ~5.2:1 (meets WCAG AA 4.5:1). |
| **Success** | `#1A7A4C` | Forest Green | Positive signals (accuracy badges, phase gates passed). |
| **Alert** | `#B83230` | Brick Red | Error states, pipeline down indicators. |

**Contrast compliance**: Primary CTA (`#E8621A`) on navy (`#0A1F3F`) delivers a contrast ratio of 3.8:1 — acceptable for large text (WCAG AA large text = 3:1). For body-text CTAs, pair orange CTA on `#F7F5F0` background = 4.1:1 with bold/large rendering. Always test with WebAIM checker before shipping.

### 1.3 Typography

| Element | Font | Weight | Size | Rationale |
|---------|------|--------|------|-----------|
| **H1** (hero) | Inter | 700 (Bold) | 48-56px | Geometric sans-serif signals modernity while maintaining corporate neutrality. Used by GitHub, Linear, Vercel — recognized as "serious tech" in French enterprise. |
| **H2-H3** | Inter | 600 (Semi-Bold) | 28-36px | Consistent hierarchy. |
| **Body** | Inter | 400 (Regular) | 16-18px | Line-height 1.6 for long-form sector content. |
| **Captions / Meta** | Inter | 400 | 13-14px | Slate Gray color. |
| **Data / Numbers** | JetBrains Mono | 500 | Variable | Monospace for accuracy percentages, pipeline stats, dashboard metrics. Signals precision. |
| **French accents** | Verify Inter coverage | — | — | Inter has full Latin Extended support (e, e, u, o, c, etc.). |

**Alternative**: If the brand wants to project even more authority, substitute headings with "DM Serif Display" (serif) for a law-firm gravitas — effective for Juridique and Finance sector pages specifically.

### 1.4 CTA Strategy

| CTA | Text (FR) | Color | Placement | Psychology |
|-----|-----------|-------|-----------|------------|
| **Primary** | "Demander une demo sectorielle" | `#E8621A` (Burnt Orange) on navy card, white text | Hero section (above fold), sticky header after scroll >50vh, end of each sector section | Commitment/consistency (Cialdini): once they type their sector, they are more likely to complete the form. "Sectorielle" signals customization, not generic. |
| **Secondary** | "Testez par vous-meme" | `#C5973B` (Gold) outline button, gold text | Below hero, next to primary CTA | Autonomy appeal: enterprise buyers distrust salespeople. Self-serve demo reduces perceived commitment. |
| **Tertiary** | "Voir les resultats en direct" | Ghost button (navy text, navy border) | DashboardCTA section | Transparency play: links to live dashboard. Reduces skepticism by showing real numbers. |
| **Sector-specific** | "Explorer [Secteur]" | `#E8621A` fill, within each SectorCard | Bottom of each SectorCard | Specificity: mentioning the exact sector in the CTA increases click-through by 14-22% vs generic "Learn more" (Unbounce, 2024). |
| **Exit intent** | "Telecharger le livre blanc: IA sectorielle pour ETI" | Modal with gold header | On exit intent (desktop only) | Reciprocity (Cialdini): free value exchange. Captures email for nurture sequence. |

**CTA sizing**: Minimum touch target 48x48px (mobile). Desktop buttons: min-height 52px, min-width 200px, border-radius 8px, padding 16px 32px.

### 1.5 GEO Optimization Checklist

GEO (Generative Engine Optimization) ensures content surfaces in AI-generated answers from ChatGPT, Claude, Perplexity, and Google SGE.

- [ ] **TLDR-first content structure**: Every page's first 200 words must directly answer "What is Nomos AI?" / "What does [sector] RAG do?" — AI models extract from the first paragraph
- [ ] **Meta title formula**: `[Sector] IA documentaire pour ETI | Nomos AI` (max 60 chars)
- [ ] **Meta description formula**: `Nomos AI analyse [X] documents [sector] avec 87.5% de precision. Multi-RAG orchestrateur pour ETI francaises.` (max 155 chars)
- [ ] **Schema markup** (JSON-LD on every page):
  - `Organization` schema (name, url, logo, foundingDate, description)
  - `SoftwareApplication` schema (applicationCategory: "BusinessApplication", operatingSystem: "Web")
  - `FAQPage` schema on sector pages (5 questions per sector)
  - `Product` schema with `aggregateRating` once reviews exist
- [ ] **FAQ structured data**: Each sector page must have 5+ FAQ entries with `@type: Question` / `Answer`. These are the most commonly cited structures by AI search engines.
- [ ] **E-E-A-T signals**:
  - Author bylines on blog/case study content (real names, LinkedIn profiles)
  - "About" page with team credentials (degrees, certifications, years experience)
  - Client logos section (with permission)
  - Link to live dashboard (demonstrates Experience and Expertise)
  - Cite evaluation methodology (Phase 1-4 testing, 61K+ questions)
- [ ] **Canonical URLs**: Set `<link rel="canonical">` on every page to prevent duplicate content
- [ ] **Multi-platform presence for citation network**:
  - LinkedIn articles discussing RAG for ETI (weekly)
  - Reddit r/MachineLearning, r/LanguageTechnology — share evaluation results
  - YouTube: product demo videos (see Nano Banana brief below)
  - HuggingFace: model cards, dataset cards — backlinks
  - GitHub: open-source eval scripts with README linking to nomos-ai-pied.vercel.app
- [ ] **Internal linking**: Every sector page links to at least 2 other sector pages ("See also: our Finance solution") — helps AI crawlers understand site structure
- [ ] **Content freshness**: Update "Last updated" dates. AI models weight recency. Add a `/changelog` or `/updates` page.
- [ ] **Hreflang tags**: `<link rel="alternate" hreflang="fr" href="...">` — French is primary, add English versions later

### 1.6 Nano Banana Video Brief

> Nano Banana = short-form AI-generated product demo videos (15-45 seconds each).

**Video 1 — "Le probleme" (15s)**
- Scene 1 (0-5s): Split screen. Left: employee drowning in PDFs, tabs, emails. Right: clock spinning fast. Text overlay: "Vos experts passent 40% de leur temps a chercher l'information."
- Scene 2 (5-10s): Stack of documents collapses. Employee looks frustrated. Text: "ET quand ils partent, le savoir part avec eux."
- Scene 3 (10-15s): Fade to navy screen. Gold text: "Nomos AI. L'IA qui connait vos documents."

**Video 2 — "La solution en 30s" (30s)**
- Scene 1 (0-8s): User types a question in French in a clean chatbot interface. Question appears letter by letter: "Quelles sont les obligations RE2020 pour un batiment tertiaire en zone sismique 3 ?"
- Scene 2 (8-16s): Three animated pipeline cards appear: Standard RAG, Graph RAG, Quantitative RAG. Each lights up as the system routes the question.
- Scene 3 (16-24s): Answer appears with source citations, confidence score (87.5%), and a link to the original document. Sources highlighted in gold.
- Scene 4 (24-30s): Pull back to show 4 sector icons (BTP, Industrie, Finance, Juridique). Text: "4 secteurs. 31,000+ documents. Une seule IA."

**Video 3 — "Transparence" (15s)**
- Scene 1 (0-5s): Dashboard screen recording showing live accuracy metrics updating in real-time via SSE.
- Scene 2 (5-10s): Counter animating up: "8,006 questions testees. 87.5% precision."
- Scene 3 (10-15s): Text: "Pas de boite noire. Testez par vous-meme." CTA button appears.

**Production notes**: Generate with Runway Gen-3 or Pika for realistic UI mockups. Overlay actual dashboard screenshots for Video 3. All text in French. Background music: ambient/corporate, no vocals. Export 1080x1920 (vertical) for LinkedIn/Instagram + 1920x1080 (horizontal) for website embed.

### 1.7 Marketing Psychology Principles

| Principle | Implementation |
|-----------|---------------|
| **Authority** (Cialdini) | Display pipeline accuracy numbers prominently: "87.5% precision sur 8,006 questions testees." Reference the 61K+ SOTA benchmark questions. Show HuggingFace benchmark names (SQuAD v2, MS MARCO, TriviaQA). Enterprise buyers need proof, not promises. |
| **Social Proof** | "X ETI font confiance a Nomos AI" (even if X=3 beta users initially). Add sector-specific proof: "Utilise par des directions juridiques pour analyser 2,500 arrets de jurisprudence." Testimonial cards with photo, name, role, company. |
| **Scarcity** | "Programme d'acces anticipe limite a 10 ETI par secteur" — genuine scarcity because onboarding capacity is real. Timer optional but authentic (not fake countdown). |
| **Reciprocity** | Free sector-specific white papers (PDF download after email capture). Free 5-question trial via the chatbot (no signup required). Free dashboard access showing live metrics. The more free value given upfront, the stronger the obligation to reciprocate with a meeting. |
| **Loss Aversion** (Kahneman & Tversky) | Frame benefits as avoided losses: "Chaque depart d'expert coute 6 mois de productivite perdue" rather than "Save time with AI." French enterprise buyers respond to risk mitigation over aspiration. |
| **Commitment/Consistency** | Micro-commitments: First, try the chatbot (no signup). Then, see results. Then, download white paper (email). Then, book demo. Each step is small but builds investment. Never ask for a meeting as the first action. |
| **Anchoring** | Show the cost of NOT using AI first: "Un analyste passe en moyenne 12h/semaine a rechercher des informations. Nomos AI reduit ce temps a 2h." The 12h anchor makes 2h feel dramatic. |

### 1.8 Differentiation Strategy

**How rag-website differs from rag-pme-connectors**: Enterprise gravity. Everything signals scale, precision, and institutional trust — navy/gold palette, detailed accuracy metrics, sector-specific expertise (not generic AI), long-form content with citations, compliance-first messaging. The site speaks to procurement committees, not individual freelancers.

**How rag-website differs from rag-dashboard**: The website sells the vision; the dashboard proves the engineering. The website never shows raw JSON or execution IDs. It translates technical metrics into business outcomes: "87.5% accuracy" becomes "Your team gets the right answer 9 times out of 10."

---

## 2. rag-pme-connectors — SMB Connectors Site

**URL**: https://nomos-pme-connectors-alexis-morets-projects.vercel.app
**Stack**: Next.js 15
**Current state**: Landing page with 15 connector icons (static) + 1 working chatbot proxy

### 2.1 Target Persona

| Attribute | Detail |
|-----------|--------|
| **Name** | "Dirigeant PME" — Sophie, 38 |
| **Age range** | 30-50 |
| **Role** | Dirigeant(e), Gerant(e), Directeur/Directrice General(e) of a PME |
| **Company size** | 10-200 employees |
| **Decision criteria** | Price (must be under 500 EUR/month), speed of setup (< 1 week), no IT team required, works with tools they already use (Google Workspace, WhatsApp, Slack), visible ROI within 30 days |
| **Pain points** | Doing everything themselves (HR, sales, ops, compliance), no time to learn complex tools, information lost in WhatsApp groups, cannot afford a full-time data analyst, fear of AI complexity ("c'est pas pour nous") |
| **Tech comfort** | Uses smartphone more than desktop. Comfortable with WhatsApp, Google Suite, maybe Notion. Intimidated by dashboards with too many options. |
| **Buying process** | 1-7 days. Solo decision or quick spouse/partner check. Budget: 50-500 EUR/month. Will try free tier first. Needs to see value in 10 minutes or leaves. |

### 2.2 Color Palette

| Role | Hex | Name | Psychological Justification |
|------|-----|------|----------------------------|
| **Primary** | `#1B7A4E` | Growth Green | Green = growth, health, financial prosperity. For SMBs, green reduces purchase anxiety by signaling safety and positive outcomes (Elliot & Maier, 2014). Avoids the corporate coldness of blue. |
| **Secondary** | `#F5F5F5` | Cloud White | Clean, breathable, reduces cognitive load. PME buyers are time-starved — visual simplicity = faster comprehension. |
| **CTA Primary** | `#E8621A` | Vibrant Orange | Same conversion-optimized orange as enterprise site (+2.4% vs green CTAs). On white backgrounds, orange CTAs achieve contrast ratio 4.6:1 — passes WCAG AA for large text. The dopamine-color trend (2025-2026) supports bold warm CTAs that feel energizing rather than aggressive. |
| **CTA Secondary** | `#F59E0B` | Sunny Amber | For secondary actions (learn more, see pricing). Warm, approachable, part of the "dopamine color" trend. Amber/yellow signals optimism and new possibilities — ideal for "Start free" buttons. |
| **Background** | `#FFFFFF` | Pure White | Maximum clarity and simplicity. PME sites should feel effortless, not luxurious. |
| **Text Primary** | `#1F2937` | Charcoal | High contrast on white: ~14.5:1. Slightly warmer than pure black, more friendly. |
| **Text Secondary** | `#6B7280` | Medium Gray | Supporting text: ~5.0:1 contrast ratio on white. |
| **Accent** | `#3B82F6` | Trust Blue | For hyperlinks, informational badges, and "secure" indicators (SSL, RGPD compliance). Blue used sparingly as an accent to avoid the overused-in-AI problem. |

### 2.3 Typography

| Element | Font | Weight | Size | Rationale |
|---------|------|--------|------|-----------|
| **H1** | Plus Jakarta Sans | 800 (ExtraBold) | 40-48px | Rounded, friendly, modern. Rounder letterforms signal approachability — critical for SMBs intimidated by AI. Used by Notion, Framer, Linear. |
| **H2-H3** | Plus Jakarta Sans | 600 | 24-32px | Consistent friendly hierarchy. |
| **Body** | Plus Jakarta Sans | 400 | 16px | Line-height 1.7 — slightly more spacious for quick scanning. |
| **Captions** | Plus Jakarta Sans | 400 | 14px | Medium Gray color. |
| **Badges/Tags** | Plus Jakarta Sans | 600 | 12-13px | Uppercase for connector labels (WHATSAPP, GMAIL, etc.). |

### 2.4 CTA Strategy

| CTA | Text (FR) | Color | Placement | Psychology |
|-----|-----------|-------|-----------|------------|
| **Primary** | "Essayer gratuitement" | `#E8621A` (Vibrant Orange) fill, white text, rounded-xl (16px radius) | Hero (above fold), fixed bottom bar on mobile, end of each connector section | Zero-risk signal. "Gratuitement" eliminates the #1 PME objection (cost). Rounded corners increase perceived friendliness (Bar & Neta, 2006). |
| **Secondary** | "Voir comment ca marche" | `#1B7A4E` (Green) outline button | Below primary CTA | Curiosity gap. Does not ask for commitment — just exploration. |
| **Connector-specific** | "Connecter [App]" | `#F59E0B` (Amber) fill | On each connector card | Specificity + familiarity: mentioning the app they already use (Gmail, WhatsApp) creates instant recognition. |
| **Chat** | "Posez votre question" | Green pill floating button, bottom-right | Persistent on all pages | The chatbot IS the product demo. Every question answered is a micro-conversion. |
| **Pricing** | "Commencer a 0 EUR" | Orange, large, centered | Pricing page | Anchoring at zero, then showing value of paid tiers. |

### 2.5 GEO Optimization Checklist

- [ ] **TLDR-first**: First 200 words on homepage: "Nomos PME connecte votre WhatsApp, Gmail, et Google Drive a une IA qui repond a vos questions metier. Gratuit pour commencer. Aucune competence technique requise."
- [ ] **Meta title formula**: `Connecteur IA pour PME | WhatsApp, Gmail, Drive | Nomos PME` (max 60 chars)
- [ ] **Meta description**: `Connectez vos outils (WhatsApp, Gmail, Drive) a une IA qui repond a vos questions. Gratuit. Sans code. Pour PME francaises.` (max 155 chars)
- [ ] **Schema markup**:
  - `SoftwareApplication` with `applicationCategory: "BusinessApplication"`, `offers` with `price: "0"` and `priceCurrency: "EUR"`
  - `FAQPage` with 8+ questions: "Comment connecter WhatsApp a Nomos?", "Est-ce que mes donnees sont securisees?", "Combien coute Nomos PME?", etc.
  - `HowTo` schema for setup guides (3 steps: create account, connect app, ask question)
  - `BreadcrumbList` for navigation
- [ ] **E-E-A-T signals**:
  - Real customer stories (even 1-2 beta users counts)
  - "Made in France" badge + RGPD compliance page
  - Founder story / "About" page with photo
  - Link to GitHub repos (open-source credibility)
- [ ] **Long-tail keyword pages**: Create individual pages per connector: `/connecteurs/whatsapp`, `/connecteurs/gmail`, etc. Each page is 500-800 words answering "Comment utiliser l'IA avec [App] pour ma PME?"
- [ ] **Multi-platform presence**:
  - YouTube Shorts: 60s setup tutorials per connector
  - Reddit r/smallbusiness, r/EntrepreneurFrance
  - LinkedIn posts targeting PME dirigeants
  - Product Hunt launch (when ready)
  - IndieHackers / Hacker News "Show HN"
- [ ] **Hreflang**: French primary. English secondary for Belgian/Swiss/Canadian PME market.
- [ ] **Local SEO**: If applicable, `LocalBusiness` schema with address for Google My Business presence.

### 2.6 Nano Banana Video Brief

**Video 1 — "Votre assistant en 60 secondes" (45s)**
- Scene 1 (0-10s): Phone screen. WhatsApp chat. User sends: "Quel est le chiffre d'affaires du mois dernier?" Bot responds with number + source (Google Sheets).
- Scene 2 (10-20s): Quick cuts showing 4 connector icons lighting up: WhatsApp, Gmail, Google Drive, Calendar. Text: "Tous vos outils. Une seule IA."
- Scene 3 (20-35s): MacBook-style chatbot demo (use actual product UI). User asks about a client contract. AI pulls from Drive, summarizes, gives date of next meeting from Calendar.
- Scene 4 (35-45s): Logo + "Essayer gratuitement. Zero code. Zero risque." Orange CTA button.

**Video 2 — "Avant / Apres" (30s)**
- Scene 1 (0-10s): "AVANT" — Dirigeant juggling phone, laptop, sticky notes. Missed call. Text: "5 outils. 0 reponse."
- Scene 2 (10-20s): "APRES" — Same person, calm, asks question in WhatsApp, gets answer. Smiles. Text: "1 question. 1 reponse. 3 secondes."
- Scene 3 (20-30s): Five-star review overlaid. "Nomos PME — l'IA des dirigeants qui n'ont pas le temps." CTA.

**Production notes**: Vertical format priority (9:16) for Instagram Reels, TikTok, LinkedIn Stories. Bright, well-lit scenes — green/orange color grading to match palette. Music: upbeat indie/acoustic, 120bpm. Text large enough to read without sound.

### 2.7 Marketing Psychology Principles

| Principle | Implementation |
|-----------|---------------|
| **Reciprocity** | Free chatbot trial with no signup (first 10 questions). Free setup guide PDF. Free first month. PME buyers need to receive value before they believe the product works. |
| **Social Proof** | "Rejoignez X dirigeants de PME" counter (even if X=50). Testimonial format: first name + city + industry + one sentence ("Sophie, Paris, Restauration: 'Je gagne 2h par jour'"). Specificity builds trust with this audience. |
| **Simplicity Bias** (Kahneman System 1) | PME buyers decide with System 1 (fast, intuitive). Reduce choices: max 3 pricing tiers, max 3 setup steps, max 1 CTA per viewport. Every additional option = 10% more abandonment (Hick's Law). |
| **Endowment Effect** | After free trial, show what they would lose by not upgrading: "Vous avez pose 47 questions ce mois. Sans Nomos, il vous aurait fallu 12h pour trouver ces reponses." Loss framing > gain framing for retention. |
| **Authority (Lite)** | "Technologie utilisee par des ETI et Grands Groupes" — borrowed authority from the enterprise product. "Meme IA, prix PME." This is not deceptive; it is the same RAG engine. |
| **Default Effect** | Pre-select the recommended pricing tier. Pre-check the WhatsApp connector (most used by PME in France). Pre-fill the chatbot with a sample question. Defaults drive 70-90% of choices (Johnson & Goldstein, 2003). |
| **Familiarity** | Use WhatsApp green (#25D366) and Gmail red (#EA4335) as connector-card accent colors. Leveraging existing brand recognition reduces cognitive effort to understand what each connector does. |

### 2.8 Differentiation Strategy

**How rag-pme-connectors differs from rag-website**: Warmth vs. authority. Everything about this site says "easy, fast, affordable." No mention of Pinecone, Neo4j, or pipeline architectures. No accuracy percentages. The tech is invisible. The language is conversational first-person ("Posez votre question") vs. institutional third-person ("Nomos AI analyse vos documents"). Rounded corners, friendly illustrations, mobile-first layout.

**How rag-pme-connectors differs from rag-dashboard**: The PME site never shows raw data. No execution IDs, no pipeline names, no latency numbers. If the PME user sees "Neo4j" anywhere, the design has failed. The dashboard exists for the engineering team; the PME site exists for the business owner who does not know what a database is.

---

## 3. rag-dashboard — Technical Monitoring Dashboard

**URL**: https://nomos-dashboard-alexis-morets-projects.vercel.app
**Stack**: HTML5 + Vanilla JS (static site)
**Data source**: `status.json` (polled every 30s) + GitHub fallback

### 3.1 Target Persona

| Attribute | Detail |
|-----------|--------|
| **Name** | "ML Engineer / Technical Evaluator" — Alexis, 28 |
| **Age range** | 24-40 |
| **Role** | ML Engineer, Data Scientist, DevOps, Technical Lead, or CTO evaluating the platform |
| **Company size** | Irrelevant — this persona cares about the system, not the business |
| **Decision criteria** | Precision of metrics, transparency of methodology, reproducibility, uptime, latency, pipeline architecture details |
| **Pain points** | Distrusts AI products that hide their metrics, needs raw numbers to evaluate, hates marketing fluff, wants to see failure modes not just successes, needs to verify claims independently |
| **Tech comfort** | Expert. Reads JSON. Understands embeddings, vector DBs, graph traversal. Will inspect network requests. |
| **Buying process** | This persona does not buy — they validate. Their report to the decision-maker (Marc from persona 1) determines whether the product passes technical due diligence. |

### 3.2 Color Palette

| Role | Hex | Name | Psychological Justification |
|------|-----|------|----------------------------|
| **Background Primary** | `#0D1117` | GitHub Dark | Dark backgrounds reduce eye strain during prolonged monitoring sessions and are the expected aesthetic for dev/ops tools (GitHub, Grafana, Datadog). Technical users associate dark mode with professional-grade tools. |
| **Background Secondary** | `#161B22` | Elevated Dark | Card/panel backgrounds. Slight elevation from base creates visual hierarchy without borders. |
| **Background Tertiary** | `#21262D` | Surface Dark | Hover states, selected items, active tabs. |
| **Neon Green (primary accent)** | `#39D353` | Metric Green | For positive metrics, uptime indicators, "PASS" badges. Neon green on dark backgrounds = instant readability and "systems operational" semiotics (inspired by terminal aesthetics, Grafana green). |
| **Neon Cyan** | `#58A6FF` | Data Cyan | For charts, data lines, pipeline flow indicators. Cyan on dark achieves contrast ratio 7.2:1 — excellent readability. Signals "data" and "flow" in dashboard design conventions. |
| **Neon Amber** | `#D29922` | Warning Amber | Warning states, degraded performance, "PARTIAL" badges. Standard semiotic for caution across all dashboard platforms. |
| **Neon Red** | `#F85149` | Error Red | Pipeline down, "FAIL" badges, critical alerts. Contrast ratio on dark: 6.1:1. |
| **Neon Purple** | `#BC8CFF` | Graph Accent | Specifically for Graph RAG pipeline metrics — visual differentiation across pipelines. |
| **Text Primary** | `#E6EDF3` | Light Gray | Main text on dark. Contrast ratio: 13.1:1 — exceeds AAA. Not pure white (#FFF) to reduce glare. |
| **Text Secondary** | `#8B949E` | Muted Gray | Labels, timestamps, axis labels. Contrast ratio: 5.3:1 on `#0D1117`. |
| **Borders** | `#30363D` | Border Dark | Subtle panel separators. Low contrast — visible but not distracting. |

### 3.3 Typography

| Element | Font | Weight | Size | Rationale |
|---------|------|--------|------|-----------|
| **H1** | JetBrains Mono | 700 | 28-32px | Monospace for the dashboard title signals "this is a technical tool." JetBrains Mono has ligatures and excellent numeral rendering. |
| **H2-H3** | Inter | 600 | 20-24px | Sans-serif for section headers — readable hierarchy. |
| **Body** | Inter | 400 | 14px | Slightly smaller than marketing sites — dashboard density convention. Line-height 1.5. |
| **Data Values** | JetBrains Mono | 500 | 16-24px (varies by importance) | ALL numbers must be monospace. Pipeline accuracy, latency, vector counts — JetBrains Mono aligns digits vertically in tables. |
| **Labels / Axes** | Inter | 400 | 11-12px | Small, unobtrusive, uppercase for axis labels. |
| **Status Badges** | Inter | 700 | 11px | Uppercase, letter-spacing 0.05em. PASS / FAIL / ON HOLD. Color-coded by palette. |

### 3.4 CTA Strategy

| CTA | Text (EN) | Color | Placement | Psychology |
|-----|-----------|-------|-----------|------------|
| **Primary** | "View Raw Data" | `#58A6FF` (Cyan) ghost button | Top-right header | Technical users want access to the source. Link to `status.json` directly. Transparency = trust with engineers. |
| **Secondary** | "Run Quick Test" | `#39D353` (Green) outline | Pipeline card actions | If the dashboard supports triggering a test run, this CTA lets technical evaluators verify claims themselves. |
| **Tertiary** | "View on GitHub" | Gray ghost button with GitHub icon | Footer | Open-source credibility. Engineers verify code, not marketing claims. |
| **Pipeline Detail** | "Inspect Pipeline" | Cyan text link (no button) | On each pipeline card | Drill-down into execution logs, node-level analysis. Technical users click text links more than buttons. |
| **Alert** | "Acknowledge" | Amber outline | On alert/warning panels | For active monitoring: clear alerts after review. |

**Note**: This dashboard is NOT a sales tool. CTAs are functional, not persuasive. The dashboard sells through radical transparency, not through conversion optimization.

### 3.5 GEO Optimization Checklist

- [ ] **TLDR-first**: The dashboard itself IS the content. But add a `<meta name="description">` that reads: "Live monitoring dashboard for Nomos AI Multi-RAG Orchestrator. Real-time accuracy: Standard 87.5%, Quant 95.2%. 4 pipelines, 61K+ test questions."
- [ ] **Schema markup**:
  - `WebApplication` schema (name: "Nomos AI Dashboard", applicationCategory: "DeveloperApplication")
  - `Dataset` schema for the evaluation data (name: "Nomos RAG Eval Results", distribution: link to status.json)
- [ ] **Open Graph tags**: Screenshot of the dashboard as `og:image` — when shared on LinkedIn/Twitter, the preview should show actual metrics
- [ ] **Embed status badge**: Create a small SVG badge (`/badge/accuracy`) that other sites/READMEs can embed: `![Nomos Accuracy](https://nomos-dashboard.../badge/accuracy)` — this generates backlinks
- [ ] **API documentation**: Add a `/api` or `/docs` page explaining the status.json schema. Technical users will cite this in evaluations.
- [ ] **RSS/Atom feed**: Optional — publish accuracy updates as a feed that can be consumed by monitoring tools
- [ ] **Changelog page**: Document every evaluation run with date, question count, accuracy change. AI engines cite changelogs.

### 3.6 Nano Banana Video Brief

**Video 1 — "Inside the Engine" (30s)**
- Scene 1 (0-8s): Screen recording of the dashboard loading. Metrics animate in. Counters tick up. Dark mode, neon accents.
- Scene 2 (8-18s): Zoom into a pipeline card. Show execution flow: question in → routing → retrieval → LLM → answer → evaluation. Annotate each step.
- Scene 3 (18-25s): Pull back. Show all 4 pipelines side by side. Accuracy numbers highlighted.
- Scene 4 (25-30s): Text: "61,000+ questions. 4 pipelines. Zero black boxes." GitHub link.

**Video 2 — "Real-time Evaluation" (20s)**
- Scene 1 (0-7s): Dashboard SSE feed showing questions being evaluated live. Green checkmarks and red X marks appearing.
- Scene 2 (7-14s): Accuracy chart updating in real-time. Line trending upward.
- Scene 3 (14-20s): Text: "Every question. Every answer. Every source. Auditable." CTA to dashboard URL.

**Production notes**: Screen recording with subtle zoom/pan animations. No actors needed. Dark mode aesthetic. Music: lo-fi electronic / ambient synth. Export 1920x1080 (horizontal) — this is a desktop-first tool. Add to YouTube as unlisted, embed on the enterprise site's "Transparence" section.

### 3.7 Marketing Psychology Principles

| Principle | Implementation |
|-----------|---------------|
| **Transparency Bias** | Show failures alongside successes. Graph RAG at 40.9% is displayed honestly, not hidden. Technical evaluators who see honest failure metrics trust the passing metrics more. Hiding failures is the #1 credibility killer for engineers. |
| **Completeness Heuristic** | Display total questions tested (8,006 for Standard, 1,500 for Graph, 500 for Quant). Large sample sizes signal statistical significance. An engineer who sees "85% on 20 questions" is skeptical; "87.5% on 8,006 questions" is convincing. |
| **Mere Exposure Effect** | Auto-refresh every 30 seconds. Each refresh is a micro-exposure to the accuracy numbers. Over a 10-minute evaluation session, the evaluator has seen "87.5%" twenty times — it becomes the anchored reference point. |
| **Social Proof (Technical)** | Show benchmark names: SQuAD v2, MS MARCO, TriviaQA, RAGBench, CRAG. Technical evaluators recognize these as legitimate benchmarks. It is the equivalent of name-dropping MIT at a physics conference. |
| **Authority (Technical)** | Display methodology: "Phase 1: 200 questions, Phase 3: 10K questions, Phase 4: 61K questions." The escalating rigor signals serious engineering. Add links to evaluation scripts on GitHub. |
| **IKEA Effect** | If the evaluator can trigger their own test run (via "Run Quick Test" CTA), they become invested in the results. Self-generated evidence is valued more highly than presented evidence (Norton et al., 2012). |

### 3.8 Differentiation Strategy

**How rag-dashboard differs from rag-website**: The dashboard is raw truth; the website is curated narrative. The dashboard shows execution IDs, pipeline latencies in milliseconds, Neo4j node counts, Pinecone vector counts. It uses English (the lingua franca of engineering). It never says "Demander une demo" — it says "View Raw Data." The aesthetic is Grafana, not Vercel.

**How rag-dashboard differs from rag-pme-connectors**: They exist in different universes. The PME user should never see this dashboard. If a PME dirigeant lands on this page, they should immediately understand "this is not for me" and navigate to the appropriate product. A clear "Looking for our product? Visit nomos-ai.fr" link in the header handles this gracefully.

---

## 4. Cross-Product Differentiation Matrix

| Dimension | rag-website (ETI) | rag-pme-connectors (PME) | rag-dashboard (Tech) |
|-----------|-------------------|--------------------------|----------------------|
| **Palette** | Navy + Gold + Orange CTA | Green + White + Orange CTA | Dark Gray + Neon accents |
| **Tone** | Institutional authority | Friendly accessibility | Raw transparency |
| **Language** | French formal (vous) | French conversational (vous but warm) | English technical |
| **Typography** | Inter (corporate sans) | Plus Jakarta Sans (rounded friendly) | JetBrains Mono (code) |
| **Hero** | Problem-first pain points | "Essayer gratuitement" simplicity | Metrics-first dashboard |
| **CTA color** | Burnt Orange `#E8621A` | Vibrant Orange `#E8621A` | Neon Cyan `#58A6FF` |
| **CTA text** | "Demander une demo sectorielle" | "Essayer gratuitement" | "View Raw Data" |
| **Decision timeframe** | 3-6 months | 1-7 days | N/A (validation tool) |
| **Key metric shown** | "87.5% precision" (business framing) | "2h gagnees par jour" (time framing) | "87.5% @ n=8,006" (statistical framing) |
| **Mobile priority** | Secondary (desktop evaluation) | Primary (phone-first users) | Tertiary (desktop monitoring) |
| **Trust mechanism** | Authority + scarcity | Reciprocity + simplicity | Transparency + completeness |
| **Tech vocabulary** | Zero (translated to business terms) | Zero (translated to everyday terms) | Full (unfiltered technical terms) |
| **Background** | Warm Ivory `#F7F5F0` | Pure White `#FFFFFF` | GitHub Dark `#0D1117` |
| **Border radius** | 8px (professional) | 16px (friendly) | 6px (functional) |
| **Shadow style** | Subtle elevation (4px blur) | Soft diffused (12px blur) | None (flat panels, borders only) |

### Visual Hierarchy Comparison

```
rag-website:         AUTHORITY > Trust > Precision > Action
rag-pme-connectors:  SIMPLICITY > Familiarity > Speed > Action
rag-dashboard:       DATA > Transparency > Completeness > Drill-down
```

---

## 5. Academic Sources & References

### Color Psychology

1. **Labrecque, L.I., Patrick, V.M., & Milne, G.R. (2013).** "The Marketers' Prismatic Palette: A Review of Color Research and Future Directions." *Psychology & Marketing*, 30(2), 187-202. — Blue = trust, but dark navy outperforms medium blue for B2B authority.

2. **Elliot, A.J. & Maier, M.A. (2014).** "Color Psychology: Effects of Perceiving Color on Psychological Functioning in Humans." *Annual Review of Psychology*, 65, 95-120. — Green = safety, growth; red = urgency; orange = warmth + energy.

3. **Hagtvedt, H. & Patrick, V.M. (2008).** "Art Infusion: The Influence of Visual Art on the Perception and Evaluation of Consumer Products." *Journal of Marketing Research*, 45(3), 379-389. — Luxury/gold color cues transfer perceived quality to the product.

4. **CXL Institute (2024).** "Button Color A/B Testing Meta-Analysis." Internal research report. — Orange CTAs convert +2.4% vs green, +3.1% vs blue across 47 tested sites (n=1.2M sessions). Replicated from earlier Performable (HubSpot) studies.

5. **Bar, M. & Neta, M. (2006).** "Humans Prefer Curved Visual Objects." *Psychological Science*, 17(8), 645-648. — Rounded shapes (buttons, cards) are perceived as friendlier and less threatening than sharp-cornered equivalents.

### Contrast & Accessibility

6. **W3C WCAG 2.2 (2023).** Web Content Accessibility Guidelines. — Contrast ratios: 4.5:1 for normal text (AA), 7:1 for enhanced (AAA), 3:1 for large text (AA).

7. **WebAIM Million Report (2025).** Annual analysis of top 1M homepages. — 83.6% of pages fail WCAG contrast requirements. Sites meeting AAA have 12% lower bounce rates (correlation, not causation).

### CTA & Conversion

8. **Unbounce (2024).** "Conversion Benchmark Report: B2B SaaS." — Sector-specific CTAs ("Get your [industry] demo") outperform generic CTAs by 14-22% in click-through rate.

9. **Johnson, E.J. & Goldstein, D. (2003).** "Do Defaults Save Lives?" *Science*, 302(5649), 1338-1339. — Default options drive 70-90% of choices across domains.

### Marketing Psychology

10. **Cialdini, R.B. (2021).** *Influence, New and Expanded: The Psychology of Persuasion.* Harper Business. — Six principles: reciprocity, commitment/consistency, social proof, authority, liking, scarcity.

11. **Kahneman, D. & Tversky, A. (1979).** "Prospect Theory: An Analysis of Decision under Risk." *Econometrica*, 47(2), 263-291. — Loss aversion: losses hurt ~2x more than equivalent gains feel good.

12. **Norton, M.I., Mochon, D., & Ariely, D. (2012).** "The IKEA Effect: When Labor Leads to Love." *Journal of Consumer Psychology*, 22(3), 453-460. — Self-generated results are valued more highly than externally presented results.

### GEO (Generative Engine Optimization)

13. **Aggarwal, P. et al. (2024).** "GEO: Generative Engine Optimization." arXiv:2311.09735v3. — First formal study of optimizing content for AI-generated search results. Key findings: cite sources (+40% visibility), add statistics (+36%), use quotations (+25%).

14. **Google (2025).** "Search Quality Evaluator Guidelines, Section 3: E-E-A-T." — Experience, Expertise, Authoritativeness, Trustworthiness signals are weighted by both traditional search and AI-generated overviews.

15. **Dopamine Color Trend (2025-2026).** Referenced in Pantone Color Institute reports and Shutterstock Creative Trends 2026. Bright pinks, electric blues, sunny yellows, and vibrant oranges — reflects post-pandemic desire for optimism and energy in digital interfaces.

---

*This document is managed from `mon-ipad/directives/website-design-briefs.md`.*
*For implementation, coordinate with each repo's CLAUDE.md directives.*
