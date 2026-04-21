# La Forge Factory — Full SaaS Architecture

> The AI Company Factory: from idea to live product with 7 autonomous agents
> Version 2.0 — 2026-03-30

## Vision

Un utilisateur arrive avec une **idée**. Il repart avec un **produit complet** :
produit construit, stratégie business définie, communication lancée, infra gérée, finances trackées, légal vérifié.

**L'utilisateur ne touche JAMAIS au backend.** Il discute avec ses agents via chatbot (Telegram @Forge42Bot ou dashboard).

## Core Principles

1. **Teamwork agentic**: Layer 1 agents work as a swarm — each agent knows what the other 2 are doing and inflects its own plans/research accordingly. Business findings reshape Product priorities; Communication adapts to Business persona; Product feeds back build status to both.
2. **Pain resolution is king**: Every product must quantify (a) the user's pain intensity, (b) how much the solution reduces it, (c) how much the user *perceives* the reduction. Perception > reality.
3. **Psychological pricing**: User persona includes behavioral economics evaluation — willingness to pay, anchoring effects, loss aversion triggers, pricing expectations based on 2026 consumer psychology research.
4. **Metrics like Pierre**: Every user's agents are monitored with the same metrics dashboard we use internally (commits, messages, revenue, agent performance, time-to-productive).
5. **Best practices = ours**: The iterative test loop (modify → run 5 min → measure → keep if better → repeat) is the same Karpathy pattern we use for NBA evolution. Users inherit our battle-tested methodology.

---

## Les 4 Layers

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 0 — USER INTAKE                                  │
│  L'utilisateur soumet son idée (= un produit à vendre)  │
│  → Chatbot @Forge42Bot ou dashboard /forge               │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  LAYER 1 — STRATEGIC STRUCTURE (3 agents)               │
│                                                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ PRODUCT     │ │ BUSINESS     │ │ COMMUNICATION    │  │
│  │ BUILDER     │ │ STRATEGIST   │ │ MANAGER          │  │
│  │             │ │              │ │                  │  │
│  │ MVP→Pro     │ │ Big4 analyse │ │ Réseaux sociaux  │  │
│  │ Test loops  │ │ TAM/SOM/SAM  │ │ Content strategy │  │
│  │ Karpathy    │ │ User persona │ │ Growth hacking   │  │
│  │ iterations  │ │ Sales canaux │ │ Brand identity   │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  LAYER 2 — INTENDANCE & LOGISTICS (3 agents)            │
│                                                         │
│  ┌─────────────┐ ┌──────────────┐ ┌──────────────────┐  │
│  │ INFRA       │ │ FINANCE      │ │ ADMIN/LEGAL      │  │
│  │ MANAGER     │ │ COMPTABLE    │ │ COMPLIANCE       │  │
│  │             │ │              │ │                  │  │
│  │ Backend     │ │ Revenus      │ │ Réglementations  │  │
│  │ Resources   │ │ Commissions  │ │ RGPD/CGV/CGU     │  │
│  │ HF Spaces   │ │ Excel/Drive  │ │ Admin user       │  │
│  │ Monitoring  │ │ Multi-canal  │ │ KYC if needed    │  │
│  └─────────────┘ └──────────────┘ └──────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  LAYER 3 — CONTINUOUS EVALUATION                        │
│  Boucle permanente: mesure → ajuste → améliore          │
│  Dashboard live sur nomosdashboard.vercel.app/forge      │
└─────────────────────────────────────────────────────────┘
```

---

## Agent Definitions

### LAYER 0: User Intake + Strategy Definition

Le point d'entrée. L'utilisateur décrit son idée en langage naturel.

**Phase 1 — Ideation** (Agent 0: Strategy Definer)
L'idée doit être définie comme un **produit/service/quelque chose** qui est **créé et vendu à quelqu'un**.
- Quoi exactement ? (produit, SaaS, API, marketplace, tool, content, service)
- Vendu à qui ? (user cible — démographie, psychographie, capacité de paiement)
- Quel problème résolu ? (pain statement — 1 phrase)
- À quel prix ? (fourchette, modèle de monétisation)
- Existe-t-il déjà ? (10-minute competitive scan)

**Phase 2 — Product Brief**
Le système transforme ça en **Product Brief** structuré :
- Quoi ? (produit/service défini)
- Pour qui ? (cible initiale)
- Pourquoi ? (problème résolu + pain intensity 1-10)
- Comment ? (technologie/approche)
- Budget ? (free/payant)
- Revenue model ? (subscription/usage/commission/one-time)

**Canal :** @Forge42Bot Telegram ou dashboard /forge
**Output :** Product Brief JSON → distribué aux 3 agents Layer 1 **simultanément** (swarm mode)

---

### LAYER 1: Strategic Structure (Swarm Mode)

> **CRITICAL**: These 3 agents work as a **coordinated swarm**. Each agent has read access
> to the other 2 agents' current plans, findings, and outputs. When Business discovers
> a niche, Product pivots its MVP scope. When Product ships a feature, Communication
> updates its messaging. When Communication finds viral traction, Business recalibrates TAM.
>
> Coordination mechanism: shared `forge-{user}/data/agent-state/` directory.
> Each agent writes its state JSON; others read before each decision cycle.

#### Agent 1: PRODUCT BUILDER

**Rôle :** Transformer l'idée en produit fonctionnel via itérations courtes loggées et analysées.

**Processus :**
1. **Analyse de l'idée** → Identifier le MVP minimal viable
2. **Plan itératif** :
   - **Step 1 — MVP** : Fonctionnalité core, 1 page, 0 design
   - **Step 2 — Alpha** : +2-3 features, feedback loop
   - **Step 3 — Beta** : Design, onboarding, analytics
   - **Step 4 — Pro** : Scale, performance, monetization
3. **Boucle Karpathy** pour chaque step :
   - Modifier → Tester (5 min) → Mesurer métrique clé → Garder si mieux → Répéter
   - **All iterations logged** → Supabase `forge_iterations` table
   - **Each test analyzed** → what improved, what regressed, why
   - **Improved and retest** → never ship without green metrics
4. **Import des agents personnels** : utilise nos 22 agents existants (research, engineering, evolution) selon besoin du produit
5. **Reads Business + Comms state** : adapts MVP scope to market findings, adjusts features to match communication promises

**Skills :**
- `/build-mvp` — Scaffolding automatique (Next.js, Python, etc.)
- `/iterate` — Karpathy loop sur le produit
- `/test-protocol` — Protocoles de test itératifs (A/B, user testing)
- `/deploy` — Deploy sur HF Space ou Vercel

**Outils :** Claude Code CLI, GitHub, Vercel, HF Spaces, GStack (/review, /qa, /ship), Superpowers (TDD, subagent-driven-development)

**Research 2026 intégrée :**
- Karpathy autoresearch pattern (modify → run → measure → keep)
- Lean Startup methodology (Build-Measure-Learn)
- Y Combinator "Do Things That Don't Scale" framework
- Paul Graham "Schlep Blindness" detection
- GStack /qa + /review as automated gates before each deploy

---

#### Agent 2: BUSINESS & STRATEGIC PLANNER

**Rôle :** Analyse stratégique Big 4 + Investment Banks + PE style pour définir le marché, la cible, et la stratégie de vente. **Always actualized** avec les derniers rapports McKinsey, BCG, Bain, Deloitte, Goldman Sachs, JP Morgan, a16z, Sequoia, Y Combinator.

**Outputs :**

**A. Niche Discovery (Rapid Growth + Rapid Revenue)**
- Scan latest Big 4 USA reports, investment bank sector analyses, PE deal flow
- Identify the **niche inside the SAM** that has:
  - **Rapid growth** trajectory (>30% YoY)
  - **Rapid revenue bootstrap** potential (revenue in <90 days)
  - **Startup-friendly** entry point (low capital, high leverage)
- TAM/SAM/SOM with compound interest projections 3/5/10 ans
- Porter's 5 Forces + Blue Ocean Strategy canvas
- **Output**: Niche Opportunity Score (0-100) with confidence interval

**B. User Persona — Full Psychological Evaluation**
- Démographie : âge, genre, localisation, revenu
- Psychographie : motivations, frustrations, aspirations
- **Pricing Expectations (Psychological)**:
  - Willingness to pay (Van Westendorp Price Sensitivity Meter)
  - Anchoring effects — what reference prices exist in user's mind
  - Loss aversion triggers — what they fear losing more than gaining
  - Prix psychologique — 9.99 vs 10 vs 19 vs 49 sweet spots
  - Comparison: how much competitors charge and perceived value gap
- Comportement digital : réseaux préférés, heures actives, format consommé
- **Research 2026 :** Fogg Behavior Model, Hook Model, nudge theory, consumer neuroscience 2025-2026, attention economics

**C. Pain Resolution Measurement**
- **Pain Intensity Score** (1-10): how severe is the problem today?
- **Solution Coverage** (%): how much of the pain does our product resolve?
- **Perceived Resolution** (%): how much does the user *feel* the pain is resolved?
  - Gap analysis: if Solution=80% but Perceived=40%, the UX/messaging is broken
- **Pain Metrics**: time saved, money saved, frustration reduced, status gained
- **Competitive pain gap**: what % of pain do competitors leave unresolved?
- **Output**: Pain Resolution Canvas (visual, shared with Product + Comms agents)

**D. Sales Channels Strategy**
- Canaux de vente prioritaires (rank par ROI estimé)
- Modèle de pricing optimal (freemium, subscription, usage-based)
- Funnel conversion : awareness → interest → decision → action
- Métriques clés par étape (CAC, LTV, churn rate, NPS)

**E. Live Adaptation + Swarm Coordination**
- Virages stratégiques automatiques si métriques KPI dévient
- Weekly reports avec recommandations
- A/B testing suggestions pour pricing et messaging
- **Reads Product state**: knows what's built, what's blocked, adjusts business plan
- **Writes to Comms**: sends user persona + pain canvas → Comms adapts messaging

**Skills :**
- `/market-analysis` — Full TAM/SAM/SOM report with niche scoring
- `/user-persona` — Complete psychological + behavioral profile
- `/pricing-strategy` — Van Westendorp + psychological pricing optimization
- `/competitor-scan` — Veille concurrentielle + PE/VC report synthesis
- `/pain-canvas` — Pain resolution measurement + gap analysis

**Outils :** Gemini Flash (recherche), WebSearch, academic paper search, market data APIs, Browser Use (scrape reports)

---

#### Agent 3: COMMUNICATION MANAGER

**Rôle :** Stratégie de communication et exécution sur tous les canaux. **Psychologically targets the defined user** based on Business Planner's persona + pain canvas.

**Processus :**

**A. Stratégie de communication (informed by Business agent)**
- Reads User Persona + Pain Canvas from Business agent state
- Ton et voix adaptés au profil psychologique de la cible
- **Psychological hooks**: addresses the EXACT pain points identified
  - Headlines that trigger loss aversion ("Stop losing X every day")
  - Social proof calibrated to target demographic
  - Urgency/scarcity tuned to user's decision-making speed
- Calendrier éditorial (content plan mensuel)
- Mix content : éducatif (40%), engagement (30%), conversion (20%), viral (10%)

**B. Canaux digitaux (matched to user persona)**
- **Réseaux sociaux** : Twitter/X, LinkedIn, Reddit, TikTok, Instagram, YouTube
  - Chaque réseau = format adapté (thread, carousel, short video, long form)
  - **Channel priority from Business agent** — only invest in channels where target user actually lives
- **Sites internet** : SEO, landing pages, blog, Product Hunt, Hacker News
- **Email** : newsletters, drip campaigns, onboarding sequences
- **Community** : Discord, Telegram groups, forums

**C. Psychological Targeting**
- Message-market fit: does the copy address the pain at the right intensity?
- Conversion copy based on Van Westendorp pricing sweet spot from Business agent
- A/B testing: emotional vs rational messaging per audience segment
- Retargeting sequences calibrated to user's purchase decision timeline

**D. Swarm Coordination**
- **Reads Product state**: knows what features just shipped → writes launch posts
- **Reads Business state**: adapts messaging to new persona/niche discoveries
- **Writes to both**: shares engagement metrics, viral hits → Product prioritizes popular features, Business validates market fit

**Skills :**
- `/content-plan` — Calendrier éditorial mensuel
- `/write-post` — Rédiger post psychologically targeted to persona
- `/seo-audit` — Audit SEO du site
- `/growth-hack` — Stratégies de croissance rapide
- `/trend-scout` — Veille tendances du moment
- `/pain-messaging` — Convert pain canvas into compelling copy

**Outils :** Gemini Flash, WebSearch, social media APIs, analytics, Browser Use

---

### LAYER 2: Intendance & Logistics

#### Agent 4: INFRA MANAGER

**Rôle :** Gestion complète du backend, allocation des ressources, monitoring live.

**Responsabilités :**
- **Backend** : HF Spaces, Vercel, Codespaces, databases, APIs
- **Allocation ressources** : CPU/GPU distribution, cron jobs, rate limiting
- **Monitoring** : Health checks toutes les 5 min, auto-restart si down
- **Scaling** : Détection de charge, scaling automatique (HF Space → GPU si besoin)
- **Sécurité** : Isolation des users, credential management, backup
- **Deploy strategy** : selon les plans des autres agents, deploy sur la plateforme optimale

**Free Hosting Platforms (always scan for new ones):**
- HF Spaces (CPU gratuit, GPU payant)
- Vercel (hobby plan gratuit)
- GitHub Codespaces (60h/mois gratuit)
- Railway (500h/mois gratuit)
- Render (750h/mois gratuit)
- Fly.io (3 VMs gratuites)
- Cloudflare Workers (100K req/jour gratuit)
- Deno Deploy (100K req/jour gratuit)
- Supabase (500MB gratuit)
- **Agent scans for new free platforms monthly**

**Skills :**
- `/infra-status` — Dashboard complet de l'infrastructure
- `/scale-up` — Augmenter les ressources pour un produit
- `/deploy-space` — Déployer un nouveau HF Space
- `/backup` — Backup des données utilisateur
- `/security-audit` — Vérification sécurité
- `/platform-scout` — Scan for new free hosting platforms

**Outils :** HF API, Vercel API, Supabase, monitoring scripts, E2B (sandboxed code execution)

**Best Skills 2026 :**
- GitOps (infrastructure as code)
- Observability (OpenTelemetry, structured logging)
- Chaos engineering (resilience testing)
- Zero-trust security model

---

#### Agent 5: FINANCE & COMPTABILITE

**Rôle :** Tracking précis de tous les flux financiers, commissions, et reporting légal.

**Responsabilités :**

**A. Revenue Tracking**
- Multi-canal : Stripe, PayPal, crypto, virement
- Attribution : quel canal a généré quel revenu
- Récurrence : MRR, ARR, churn revenue, expansion revenue

**B. Commission Alexis**
- Commission obligatoire sur revenus générés (% défini par plan)
- Calcul automatique mensuel
- Historique complet pour chaque user

**C. Excel/Drive Export**
- Google Sheets ou Excel live document
- Colonnes : date, user, produit, revenu brut, commission %, commission €, net
- Accessible par Alexis en permanence
- Prêt pour expert-comptable / déclaration fiscale

**D. Métriques financières**
- Burn rate, runway, unit economics
- P&L par produit et par user
- Prévisions à 3/6/12 mois

**Skills :**
- `/revenue-report` — Rapport revenus du mois
- `/commission-calc` — Calcul commissions dues
- `/export-excel` — Export vers Google Sheets
- `/financial-forecast` — Prévisions financières
- `/invoice-generate` — Génération de factures

**Outils :** Stripe API, Google Sheets API, accounting templates

---

#### Agent 6: ADMIN & LEGAL COMPLIANCE

**Rôle :** Vérification que tout est conforme aux réglementations locales.

**Responsabilités :**

**A. Réglementations produit**
- RGPD (si users EU) : consentement, DPO, droit à l'oubli
- CGV/CGU : générées automatiquement selon le type de produit
- Mentions légales : adaptées au pays de l'user
- Cookie policy, privacy policy

**B. Admin utilisateur**
- KYC (Know Your Customer) si nécessaire (fintech, betting)
- Vérification d'âge si contenu restreint
- Gestion des litiges et remboursements
- DMCA / copyright compliance

**C. Admin Alexis**
- Statut juridique de La Forge (auto-entrepreneur, SAS, etc.)
- Obligations déclaratives (TVA, impôts)
- Contrats type pour les users (licence d'utilisation)
- Assurance responsabilité civile pro

**Skills :**
- `/legal-check` — Vérification conformité du produit
- `/generate-terms` — Génération CGV/CGU/Privacy Policy
- `/gdpr-audit` — Audit RGPD
- `/dispute-handle` — Gestion d'un litige
- `/tax-report` — Obligations fiscales

**Outils :** Legal templates, regulatory databases, Gemini Flash (research)

---

## Pricing

### Plan 1: STARTER — Gratuit

| Feature | Inclus |
|---------|--------|
| Agents | Aperçu limité (Product Builder demo only) |
| Interactions | 5 messages/jour |
| Produits | 1 produit max |
| HF Space | Non |
| Purpose | Découverte, hook vers plans payants |

### Plan 2: BUILDER — $50/mois

| Feature | Inclus |
|---------|--------|
| Agents | **ALL Layer 1** (Product Builder + Business Strategist + Communication) |
| Interactions | 100 messages/jour |
| Produits | 3 produits simultanés |
| HF Space | 1 space partagé |
| Supabase | Tables dédiées |
| Layer 2 (Intendance) | **NON** — aperçu seulement |
| Commission Alexis | 10% sur revenus générés |

### Plan 3: FACTORY — $200/mois

| Feature | Inclus |
|---------|--------|
| Agents | **ALL LAYERS** (6 agents + infra complète) |
| Interactions | **Illimité** |
| Produits | Illimité |
| HF Space | 1 space **dédié** + option GPU ($) |
| Supabase | Projet dédié |
| Neo4j/Pinecone | Index dédié |
| Layer 2 (Intendance) | **OUI** — Infra, Finance, Legal |
| Infra power-up | Possibilité d'ajouter GPU, scaling |
| Commission Alexis | 5% sur revenus générés |
| Support | Prioritaire, 1:1 mensuel |

---

## User Access & Authentication

### @Forge42Bot (Telegram)
- Chaque user reçoit un identifiant unique via le bot
- Le bot sert d'interface principale pour discuter avec les agents
- Rate limiting selon le plan (5/100/illimité messages/jour)

### Dashboard /forge
- nomosdashboard.vercel.app/forge
- Vue de ses produits, métriques, agents, et statut
- Login via identifiants Forge42Bot

### HF Space
- Chaque user Builder/Factory reçoit un HF token pour son space dédié
- Token envoyé via @Forge42Bot (secure delivery)
- Space isolé — l'user ne voit que son produit

### Credentials (pré-chargées)
- L'user ne gère JAMAIS les credentials
- Tout est pré-configuré dans son `.env.local`
- Les agents ont accès aux APIs sans intervention user

---

## Monitoring Alexis (Full Control)

### Ce qu'Alexis voit pour chaque user :
- **Git commits** : chaque action de Claude Code auto-push
- **Messages** : nombre de messages/jour, agents utilisés
- **Revenus** : tracking Stripe en temps réel
- **Commissions** : calcul automatique mensuel
- **Usage Claude Code CLI** : tokens consommés (console.anthropic.com)
- **Infra** : CPU/RAM utilisés par user
- **Compliance** : alertes si un produit pose problème légal

### Dashboard Alexis (admin)
- `/forge/admin` : vue globale de tous les users
- Revenus, commissions, usage, alertes
- Possibilité de suspendre/activer un user
- Export Excel pour comptabilité

---

## Revenue Model

```
User paie $50 ou $200/mois
    └── Alexis reçoit: abonnement + commission sur revenus user
        ├── $50 plan: 10% commission
        └── $200 plan: 5% commission (volume incentive)

Coûts Alexis:
    ├── Claude Code Max subscription: ~$100/mois
    ├── HF Spaces: gratuit (CPU)
    ├── Vercel: gratuit (hobby)
    ├── Supabase: gratuit (free tier par user)
    └── Gemini: gratuit (1500 req/jour)

Breakeven: 2 users Builder ($100) ou 1 user Factory ($200)
Target Year 1: 20 users → $2,000-4,000/mois ARR
```

---

## Technical Stack Per User

```
User's isolated environment:
├── GitHub repo: LBJLincoln/forge-{username} (private)
├── Claude Code CLI (Alexis's Max subscription)
├── CLAUDE.md with 6 agents + skills
├── .env.local (pre-loaded credentials)
├── HF Space: Nomos42/forge-{username}
├── Supabase: forge_{username}_* tables
├── Telegram: @Forge42Bot (authenticated)
└── Dashboard: nomosdashboard.vercel.app/forge/{username}
```

---

## Skills × Agents Matrix (27 skills)

| Skill | Ag0 | Ag1 | Ag2 | Ag3 | Ag4 | Ag5 | Ag6 | Free | Builder | Factory |
|-------|-----|-----|-----|-----|-----|-----|-----|------|---------|---------|
| `/sp-brainstorm` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/sp-write-plan` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/sp-execute-plan` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/sp-test-driven-development` | — | ✓ | — | — | ✓ | ✓ | — | — | ✓ | ✓ |
| `/sp-subagent-driven-development` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/sp-dispatching-parallel-agents` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/sp-systematic-debugging` | — | ✓ | — | — | ✓ | — | ✓ | — | ✓ | ✓ |
| `/sp-verification-before-completion` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/gstack-ship` | — | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/gstack-qa` | — | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/gstack-review` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/gstack-browse` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| `/gstack-canary` | — | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| `/gstack-careful` | — | ✓ | ✓ | — | ✓ | ✓ | — | — | — | ✓ |
| `/gstack-guard` | — | ✓ | — | ✓ | ✓ | — | ✓ | — | — | ✓ |
| `/gstack-cso` | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | — | ✓ |
| `/gstack-investigate` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/gstack-learn` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `/gstack-plan-eng-review` | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/gstack-retro` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/karpathy-loop` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/progress-10pct` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/evolve-report` | — | ✓ | — | — | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/agent-review` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ |
| `/spaces-health` | — | ✓ | — | — | ✓ | — | — | — | — | ✓ |
| `/cross-repo-audit` | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | ✓ |
| `/daily-edge` | — | — | — | — | — | — | — | — | — | ✓ |
| **Total** | **8** | **25** | **17** | **16** | **25** | **21** | **22** | **5** | **20** | **27** |

---

## User Duplication System

```bash
# Create new user (duplicates Pierre's full environment)
./scripts/forge/duplicate-user.sh <username> <tier> [product_idea]

# Examples:
./scripts/forge/duplicate-user.sh pierre factory "NBA Quant dashboard"
./scripts/forge/duplicate-user.sh sarah builder "Fitness meal planner"
./scripts/forge/duplicate-user.sh demo free "Testing the platform"
```

**What gets created for each user:**
```
forge-users/{username}/
├── CLAUDE.md                    # Tier-adapted agent config
├── .claude/
│   ├── commands/                # Skills (5/20/27 based on tier)
│   ├── tier-config.md           # Tier quotas and limits
│   └── agent-*.md               # Active agent definitions
├── products/                    # Built products
├── strategy/                    # Business analysis outputs
├── comms/                       # Content & campaigns
├── legal/                       # Legal documents
├── finance/                     # Financial tracking
├── infra/                       # Infrastructure config
├── briefs/                      # Product briefs from Agent 0
└── data/
    ├── agent-state/             # 7 agent state files (swarm coordination)
    └── iterations/              # Karpathy loop iteration logs
```

---

## Implementation Roadmap

### Phase 1: Pierre (NOW — validation)
- [x] 7 agent definitions created (scripts/forge/agents/)
- [x] 3 tier configs (free/builder/factory)
- [x] User duplication script (scripts/forge/duplicate-user.sh)
- [x] 27 skills mapped to agents × tiers
- [x] CLAUDE.md template with tier gating
- [ ] Pierre teste le système complet
- [ ] Mesurer : temps setup, usage patterns, satisfaction
- [ ] Ajuster agents et workflows

### Phase 2: Forge MVP ($50 plan only)
- [ ] @Forge42Bot routes to correct agent per tier
- [ ] 4 agents (0-3) fully operational with skill routing
- [ ] Onboarding automatique (repo + env + space)
- [ ] Stripe integration pour $50/mois
- [ ] 3-5 beta users

### Phase 3: Factory ($200 plan)
- [ ] Layer 2 agents (4-6) opérationnels
- [ ] Finance tracking + Google Sheets export
- [ ] Legal compliance automatique (CGV/CGU generator)
- [ ] Scale à 20+ users

### Phase 4: Growth
- [ ] Product Hunt launch (via Agent 3 Communication)
- [ ] Content marketing via Communication agent
- [ ] Referral program
- [ ] Enterprise tier ($500+)
