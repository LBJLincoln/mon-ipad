# Site Internet — Reference Complete

> Dossier de reference pour le developpement du site web vitrine Multi-RAG.
> Le code source Next.js reste dans `../website/`.

---

## Fichiers dans ce dossier

| Fichier | Description |
|---------|-------------|
| `brief.md` | Brief creatif original (Apple-like, Termius modal, glassmorphism) |
| `n8n-artifacts-integration.md` | Spec d'integration des artifacts n8n dans le chat |
| `package.json` | Dependances (Next.js 15, React 19, Framer Motion, Tailwind) |
| `vercel.json` | Config de deploiement Vercel |
| `tailwind.config.ts` | Configuration Tailwind CSS |
| `tsconfig.json` | Configuration TypeScript |
| `dashboard.html` | Dashboard HTML (7 onglets, metriques live) |
| `13-fev-website-session.md` | Notes de session dev website (13 fev) |

---

## Architecture du site (`../website/src/`)

```
src/
├── app/
│   ├── page.tsx              # Landing page
│   ├── layout.tsx            # Root layout
│   ├── globals.css           # Styles globaux
│   └── api/chat/route.ts     # Endpoint API chat → n8n
├── components/
│   ├── landing/              # Hero, BentoGrid, HowItWorks, SectorCard
│   ├── layout/               # Header, Footer
│   ├── modal/                # TermiusModal, Chat*, Sidebars, SourceCard
│   └── ui/                   # GlassCard, Badge, Skeleton, TypingIndicator
├── hooks/                    # useChat, useSourceHighlight, useMediaQuery
├── stores/                   # chatStore (Zustand)
├── types/                    # api.ts, chat.ts, sector.ts
└── lib/                      # parseResponse, highlighter, api, constants
```

---

## Stack

- **Framework** : Next.js 15 (App Router)
- **UI** : Tailwind CSS + Framer Motion + Lucide Icons
- **State** : Zustand
- **Backend** : n8n Docker webhooks (34.136.180.66:5678)
- **Deploy** : Vercel (gratuit)

---

## Design

- Apple-like glassmorphism
- Modal Termius (2/3 largeur)
- 4 secteurs : BTP, Industrie, Finance, Juridique
- Chat avec sidebar artifacts + surlignage sources
