# La Forge Factory — Full SaaS Architecture

> The AI Company Factory: from idea to live product with 7 autonomous agents
> Version 1.0 — 2026-03-28

## Vision

Un utilisateur arrive avec une **idée**. Il repart avec un **produit complet** :
produit construit, stratégie business définie, communication lancée, infra gérée, finances trackées, légal vérifié.

**L'utilisateur ne touche JAMAIS au backend.** Il discute avec ses agents via chatbot (Telegram @Forge42Bot ou dashboard).

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

### LAYER 0: User Intake

Le point d'entrée. L'utilisateur décrit son idée en langage naturel.
Le système transforme ça en **Product Brief** structuré :
- Quoi ? (produit/service)
- Pour qui ? (cible initiale)
- Pourquoi ? (problème résolu)
- Comment ? (technologie/approche)
- Budget ? (free/payant)

**Canal :** @Forge42Bot Telegram ou dashboard /forge
**Output :** Product Brief JSON → distribué aux 3 agents Layer 1

---

### LAYER 1: Strategic Structure

#### Agent 1: PRODUCT BUILDER

**Rôle :** Transformer l'idée en produit fonctionnel via itérations.

**Processus :**
1. **Analyse de l'idée** → Identifier le MVP minimal viable
2. **Plan itératif** :
   - **Step 1 — MVP** : Fonctionnalité core, 1 page, 0 design
   - **Step 2 — Alpha** : +2-3 features, feedback loop
   - **Step 3 — Beta** : Design, onboarding, analytics
   - **Step 4 — Pro** : Scale, performance, monetization
3. **Boucle Karpathy** pour chaque step :
   - Modifier → Tester (5 min) → Mesurer métrique clé → Garder si mieux → Répéter
4. **Import des agents personnels** : utilise nos 22 agents existants (research, engineering, evolution) selon besoin du produit

**Skills :**
- `/build-mvp` — Scaffolding automatique (Next.js, Python, etc.)
- `/iterate` — Karpathy loop sur le produit
- `/test-protocol` — Protocoles de test itératifs (A/B, user testing)
- `/deploy` — Deploy sur HF Space ou Vercel

**Outils :** Claude Code CLI, GitHub, Vercel, HF Spaces, tout notre stack

**Research 2026 intégrée :**
- Karpathy autoresearch pattern (modify → run → measure → keep)
- Lean Startup methodology (Build-Measure-Learn)
- Y Combinator "Do Things That Don't Scale" framework
- Paul Graham "Schlep Blindness" detection

---

#### Agent 2: BUSINESS & STRATEGIC PLANNER

**Rôle :** Analyse stratégique Big 4 style pour définir le marché, la cible, et la stratégie de vente.

**Outputs :**

**A. Market Analysis (TAM/SAM/SOM)**
- **TAM** (Total Addressable Market) : taille globale du marché
- **SAM** (Serviceable Available Market) : segment atteignable
- **SOM** (Serviceable Obtainable Market) : part réaliste Year 1
- Compound interest projections sur 3/5/10 ans
- Comparaison concurrents (Porter's 5 Forces)

**B. User Persona — Carte d'identité parfaite**
- Démographie : âge, genre, localisation, revenu
- Psychographie : motivations, frustrations, aspirations
- Comportement digital : réseaux préférés, heures actives, format consommé
- Processus d'achat : triggers, objections, prix psychologique
- **Research 2026 :** Psychologie comportementale internet (Fogg Behavior Model, Hook Model, nudge theory)
- **Academic papers :** Consumer neuroscience 2025-2026, attention economics, dark patterns ethics

**C. Sales Channels Strategy**
- Canaux de vente prioritaires (rank par ROI estimé)
- Modèle de pricing optimal (freemium, subscription, usage-based)
- Funnel conversion : awareness → interest → decision → action
- Métriques clés par étape (CAC, LTV, churn rate, NPS)

**D. Live Adaptation**
- Virages stratégiques automatiques si métriques KPI dévient
- Weekly reports avec recommandations
- A/B testing suggestions pour pricing et messaging

**Skills :**
- `/market-analysis` — Full TAM/SAM/SOM report
- `/user-persona` — Carte d'identité cible
- `/pricing-strategy` — Optimisation prix
- `/competitor-scan` — Veille concurrentielle

**Outils :** Gemini Flash (recherche), WebSearch, academic paper search, market data APIs

---

#### Agent 3: COMMUNICATION MANAGER

**Rôle :** Stratégie de communication et exécution sur tous les canaux.

**Processus :**

**A. Stratégie de communication**
- Alignée avec le profil utilisateur défini par Business Planner
- Ton et voix adaptés (formel/casual, technique/grand public)
- Calendrier éditorial (content plan mensuel)
- Mix content : éducatif (40%), engagement (30%), conversion (20%), viral (10%)

**B. Canaux digitaux**
- **Réseaux sociaux** : Twitter/X, LinkedIn, Reddit, TikTok, Instagram, YouTube
  - Chaque réseau = format adapté (thread, carousel, short video, long form)
- **Sites internet** : SEO, landing pages, blog, Product Hunt, Hacker News
- **Email** : newsletters, drip campaigns, onboarding sequences
- **Community** : Discord, Telegram groups, forums

**C. Skills toujours améliorées**
- Veille permanente des best practices 2026 (algorithmes réseaux, SEO updates)
- Auto-research des tendances virales dans la niche
- Copy testing (A/B titres, hooks, CTA)

**Skills :**
- `/content-plan` — Calendrier éditorial mensuel
- `/write-post` — Rédiger post adapté au réseau
- `/seo-audit` — Audit SEO du site
- `/growth-hack` — Stratégies de croissance rapide
- `/trend-scout` — Veille tendances du moment

**Outils :** Gemini Flash, WebSearch, social media APIs, analytics

---

### LAYER 2: Intendance & Logistics

#### Agent 4: INFRA MANAGER

**Rôle :** Gestion complète du backend, allocation des ressources, monitoring live.

**Responsabilités :**
- **Backend** : HF Spaces, Vercel, databases, APIs
- **Allocation ressources** : CPU/GPU distribution, cron jobs, rate limiting
- **Monitoring** : Health checks toutes les 5 min, auto-restart si down
- **Scaling** : Détection de charge, scaling automatique (HF Space → GPU si besoin)
- **Sécurité** : Isolation des users, credential management, backup

**Skills :**
- `/infra-status` — Dashboard complet de l'infrastructure
- `/scale-up` — Augmenter les ressources pour un produit
- `/deploy-space` — Déployer un nouveau HF Space
- `/backup` — Backup des données utilisateur
- `/security-audit` — Vérification sécurité

**Outils :** HF API, Vercel API, Supabase, monitoring scripts

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

## Implementation Roadmap

### Phase 1: Pierre (NOW — validation)
- [ ] Pierre teste le système complet
- [ ] Mesurer : temps setup, usage patterns, satisfaction
- [ ] Ajuster agents et workflows

### Phase 2: Forge MVP ($50 plan only)
- [ ] @Forge42Bot operational
- [ ] 3 agents Layer 1 fonctionnels
- [ ] Onboarding automatique (repo + env + space)
- [ ] Stripe integration pour $50/mois
- [ ] 3-5 beta users

### Phase 3: Factory ($200 plan)
- [ ] Layer 2 agents opérationnels
- [ ] Finance tracking + Excel export
- [ ] Legal compliance automatique
- [ ] Scale à 20+ users

### Phase 4: Growth
- [ ] Product Hunt launch
- [ ] Content marketing via Communication agent
- [ ] Referral program
- [ ] Enterprise tier ($500+)
