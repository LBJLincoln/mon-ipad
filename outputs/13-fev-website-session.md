# Session Website — 13 Fevrier 2026

## Contexte
Reprise apres crash de la session precedente. Le website Next.js 15 etait deja construit (32 fichiers, 2093 lignes) mais non commite dans git et non fonctionnel a cause des timeouts npm/npx sur VM 1GB RAM.

## Accomplissements cette session

### 1. Diagnostic VM
- **VM**: 1 GB RAM, 2 vCPU, Debian 12, 18 GB disque libre
- **Node**: v20.20.0, npm 10.8.2
- **Probleme**: npm/npx timeout constant (RAM insuffisante)
- **n8n**: actif sur port 5678 (Docker)

### 2. Installation Bun v1.3.9
- `sudo apt-get install unzip`
- `curl -fsSL https://bun.sh/install | bash`
- Bun remplace npm/npx — beaucoup plus rapide, moins de RAM
- Commandes: `bun run build`, `bun run dev`, `bun run start`

### 3. Build Next.js reussi
- `bun run build` → **succes** (compile en 2.1 min)
- Next.js 15.5.12 avec .env.local
- Route `/` = 50 kB (152 kB First Load), static
- Route `/api/chat` = 123 B, dynamic (server-side)
- Serveur de production demarre sur **port 3000** (HTTP 200 verifie)

### 4. Securisation Git
- `.gitignore` cree (exclut node_modules, .next, .env.local, bun.lockb)
- **40 fichiers** commites (commit `e9689b5`)
- Header: lien GitHub corrige vers `LBJLincoln/mon-ipad`
- Push reussi sur `origin/main`

### 5. Audit code complet — Issues identifiees

#### Critiques (a faire)
1. **RightSidebar.tsx** — Pipeline tab et Metrics tab hardcodes (pas de donnees dynamiques n8n)
2. **parseResponse.ts:30** — Fallback JSON.stringify si pas de reponse (mauvais UX)

#### Moderes
3. **Footer.tsx** — Stats hardcodes ("10K+ vecteurs", "110 entites")
4. **constants.ts** — Metriques secteurs statiques (precision, documents, latence)
5. **Header.tsx** — Lien GitHub corrige ✅

#### Mineurs
6. **Skeleton.tsx** et **useMediaQuery.ts** — Non utilises dans le code actuel
7. **HowItWorks.tsx:16** — Typo "basee" → "basée"

## Architecture du website

```
website/src/
├── app/
│   ├── api/chat/route.ts    ← Proxy vers n8n orchestrator
│   ├── globals.css           ← Design system Apple dark mode
│   ├── layout.tsx            ← Root layout (Inter, JetBrains Mono)
│   └── page.tsx              ← Landing page
├── components/
│   ├── landing/              ← Hero, BentoGrid, SectorCard, HowItWorks
│   ├── layout/               ← Header, Footer
│   ├── modal/                ← TermiusModal, LeftSidebar, ChatPanel, RightSidebar, etc.
│   └── ui/                   ← GlassCard, Badge, TypingIndicator, Skeleton
├── hooks/                    ← useChat, useMediaQuery, useSourceHighlight
├── lib/                      ← api.ts, constants.ts, highlighter.ts, parseResponse.ts
├── stores/                   ← chatStore.ts (Zustand + localStorage)
└── types/                    ← api.ts, chat.ts, sector.ts
```

## Config backend
- N8N_HOST=http://34.136.180.66:5678
- N8N_WEBHOOK_PATH=/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0
- Timeout n8n: 120 secondes

## Comment relancer le serveur
```bash
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
cd /home/termius/mon-ipad/website
bun run start -p 3000
```

## Prochaines actions
1. Ouvrir le port 3000 en firewall GCP pour acces externe
2. Connecter les metriques dynamiques n8n au RightSidebar (Pipeline + Metrics tabs)
3. Deployer en production (Vercel ou directement sur la VM avec un reverse proxy)
4. Tester le chat end-to-end avec l'orchestrator n8n
