# Stratégie Agentic Commerce — Nomos AI Products

> Créé: 2026-03-07 | Supercède: prop (conversation Gemini)

## Contexte Marché (Mars 2026)

- **45% des consommateurs** utilisent des agents IA pour acheter (IBM 2026)
- **ACP (Agentic Commerce Protocol)** est en production live — agent-to-agent commerce
- **ChatGPT, Perplexity, Microsoft Copilot** supportent l'achat in-app
- **McKinsey projette $1-5 trillion** de revenus agentic commerce d'ici 2030
- **Adobe Commerce** supporte Universal Commerce Protocol + ACP

## Plateformes de Vente (Priorité d'implémentation)

### Tier 1 — Ce soir (comptes à créer)

| # | Plateforme | Pourquoi | Fee | Agent-Ready |
|---|-----------|----------|-----|-------------|
| 1 | **Gumroad** (nomos42) | DONE. Simple, API REST, JSON-LD | 10% | Oui (API) |
| 2 | **Lemon Squeezy** | Merchant of record, 135+ pays, TVA auto | 5%+50¢ | Oui (API headless) |
| 3 | **Payhip** | 0% fee (plan gratuit), paiement instant Stripe | 0-5% | Partiel |
| 4 | **Stripe Direct** | ACP natif, agent-to-agent, checkout links | 2.9%+30¢ | **Natif ACP** |

### Tier 2 — Cette semaine

| # | Plateforme | Pourquoi | Type |
|---|-----------|----------|------|
| 5 | **Product Hunt** | Launch Enterprise Kit, visibilité dev | Launch |
| 6 | **Udemy** | Cours vidéo, audience massive | Cours |
| 7 | **Dev.to / Medium** | Articles funnel → vente | Content |
| 8 | **GitHub Marketplace** | Context files pour développeurs | Dev tools |

### Tier 3 — Semaine prochaine

| # | Plateforme | Pourquoi | Type |
|---|-----------|----------|------|
| 9 | **Flippa** | Revente de sites/chatbots complets | Flip |
| 10 | **Acquire.com** | SaaS chatbot Multi-RAG | Acquisition |

## Produits × Plateformes (Matrice)

| Produit | Prix | Gumroad | Lemon | Stripe | Udemy |
|---------|------|---------|-------|--------|-------|
| RAG Debug Playbook | $47 | ✅ | ✅ | ✅ | ✅ |
| AI Agent Context Kit | $27 | ✅ | ✅ | ✅ | — |
| Multi-RAG Blueprint | $197 | ✅ | ✅ | ✅ | ✅ |
| Enterprise Kit | $497-997 | ✅ | ✅ | ✅ | — |
| Site 5min | $17 | ✅ | ✅ | ✅ | ✅ |
| Site 20min | $47 | ✅ | ✅ | ✅ | ✅ |
| Site 1h | $127 | ✅ | ✅ | ✅ | ✅ |
| Full Stack Masterclass | $297 | ✅ | ✅ | ✅ | ✅ |

## Optimisation pour Agents IA Acheteurs

### JSON-LD (sur chaque page produit)
```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "RAG Debug Playbook — 75+ Production Fixes",
  "description": "Complete diagnostic guide for RAG systems with root cause analysis and solutions",
  "offers": {
    "@type": "Offer",
    "price": "47.00",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "url": "https://nomos42.gumroad.com/l/rag-debug-playbook"
  },
  "category": "AI/ML Training",
  "audience": {
    "@type": "Audience",
    "audienceType": ["AI Engineers", "Tech Leads", "AI Agents"]
  }
}
```

### API Endpoints pour Agents
Chaque plateforme doit exposer :
- `GET /products` — catalogue lisible par agents
- `POST /purchase` — achat programmatique
- Structured data JSON-LD sur landing pages
- Sitemap XML avec product markup

### Canaux de Découverte par Agents
1. **ChatGPT Shopping** — produits indexés via ACP/Stripe
2. **Perplexity Shopping** — structured data crawlé
3. **Google Shopping** — JSON-LD + Merchant Center
4. **Reddit/HN** — posts avec liens directs (agents scrappent)

## Architecture Codespace Monetisation

```
monetisation-bot (Codespace 8GB RAM)
├── OpenClaw (agent orchestrateur)
│   ├── Telegram bot (interface utilisateur)
│   ├── Claude Code CLI (génération contenu)
│   ├── MCP servers:
│   │   ├── Gumroad API
│   │   ├── Lemon Squeezy API
│   │   ├── Stripe API (ACP)
│   │   └── GitHub (tous les repos)
│   └── Skills:
│       ├── product-creator (packaging contenu)
│       ├── social-poster (Reddit, Twitter, Dev.to)
│       ├── price-optimizer (dynamic pricing)
│       └── sales-monitor (dashboard revenus)
├── 7 repos clonés (matière première)
└── Cron jobs (posting automatique)
```

## Comptes à Créer (Action utilisateur)

1. ✅ **Gumroad** — nomos42.gumroad.com (DONE)
2. ⬜ **Lemon Squeezy** — lemonsqueezy.com (5 min)
3. ⬜ **Stripe** — stripe.com (10 min, besoin IBAN)
4. ⬜ **Payhip** — payhip.com (5 min)
5. ⬜ **Product Hunt** — producthunt.com (2 min)
6. ⬜ **Udemy** — udemy.com/teaching (10 min)
7. ⬜ **Dev.to** — dev.to (2 min)

**Total: ~35 minutes de setup** → puis tout est automatisé.

## Revenue Projections (Conservateur)

| Source | Mois 1 | Mois 3 | Mois 6 |
|--------|--------|--------|--------|
| Gumroad (humains) | $500 | $2,000 | $5,000 |
| Gumroad (agents IA) | $200 | $1,500 | $8,000 |
| Lemon Squeezy | $300 | $1,500 | $4,000 |
| Stripe/ACP (agents) | $100 | $2,000 | $10,000 |
| Udemy | $200 | $1,000 | $3,000 |
| Flippa (revente) | — | $2,000 | $5,000 |
| **TOTAL** | **$1,300** | **$10,000** | **$35,000** |

## Différences vs Gemini (prop)

| Aspect | Gemini (prop) | Notre stratégie |
|--------|--------------|-----------------|
| Plateformes | 10 vagues | 10 concrètes avec fees et priorités |
| Agentic | Mentionné Meltobot | ACP live, ChatGPT Shopping, Stripe natif |
| Architecture | Aucune | OpenClaw + MCP + Claude Code + Telegram |
| Timeline | Aucune | Ce soir → semaine → mois |
| Revenue | Aucune | Projections réalistes par canal |
| Automatisation | "Script de base" | Codespace dédié 24/7 |
