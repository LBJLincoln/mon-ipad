# Directive — rag-pme-usecases

> Last updated: 2026-02-27T16:00:00+00:00

## Rôle de ce repo

**Site vitrine Next.js 14** présentant 200 use cases PME répartis sur 4 secteurs (finance, santé, juridique, industrie). Déployé sur Vercel. Pas d'intégration n8n (site statique).

### Architecture

| Composant | Description | Status |
|-----------|-------------|--------|
| Framework | Next.js 14 (App Router) | OK |
| Déploiement | Vercel (auto-deploy from GitHub) | OK |
| Use cases | 200 cas d'usage PME, 4 secteurs | OK |
| Chatbot | Chatbot RAG partagé avec autres sites | OK |
| n8n integration | AUCUNE (site statique) | N/A |

### Contenu

**4 secteurs × 50 use cases chacun = 200 total**

1. **Finance & Comptabilité** (50 use cases)
   - Automatisation comptable
   - Gestion trésorerie
   - Facturation intelligente
   - Conformité fiscale
   - Analyse financière

2. **Santé & Médical** (50 use cases)
   - Dossiers patients
   - Gestion rendez-vous
   - Conformité RGPD santé
   - Analyses médicales
   - Coordination équipes

3. **Juridique & Conformité** (50 use cases)
   - Analyse contrats
   - Veille réglementaire
   - Gestion litiges
   - Conformité RGPD
   - Documentation légale

4. **Industrie & Manufacturing** (50 use cases)
   - Maintenance prédictive
   - Gestion stock
   - Optimisation production
   - Qualité
   - Supply chain

### URLs

| Environnement | URL | Région |
|---------------|-----|--------|
| Production | nomos-pme-usecases-alexis-morets-projects.vercel.app | cdg1 |
| Preview | Auto-généré par Vercel | cdg1 |

### Structure fichiers

```
rag-pme-usecases/
├── app/
│   ├── page.tsx              # Page d'accueil (liste secteurs)
│   ├── layout.tsx            # Layout global + chatbot
│   ├── finance/
│   │   └── page.tsx          # 50 use cases finance
│   ├── sante/
│   │   └── page.tsx          # 50 use cases santé
│   ├── juridique/
│   │   └── page.tsx          # 50 use cases juridique
│   └── industrie/
│       └── page.tsx          # 50 use cases industrie
├── components/
│   ├── UseCaseCard.tsx       # Carte use case (title + description + tags)
│   ├── SectorHeader.tsx      # Header secteur
│   └── ChatbotModal.tsx      # Chatbot RAG partagé
├── lib/
│   └── usecases-data.ts      # Data des 200 use cases
├── public/
│   └── icons/                # Icônes secteurs
└── CLAUDE.md                 # Ce fichier (copié depuis mon-ipad)
```

### Chatbot RAG

**Chatbot partagé** avec rag-website et rag-pme-connectors. Architecture commune:

```typescript
// API route: /api/chat
// Proxy vers n8n Orchestrator
POST /api/chat
Body: { message: "Question utilisateur" }
→ Appel webhook n8n Orchestrator
→ Retour réponse RAG
```

**Endpoint n8n**: `/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0` (Orchestrator V10.1)

**Composant**: `<ChatbotModal />` — modal flottant en bas à droite, style MacBook.

### Déploiement

**Vercel auto-deploy**:
1. Push vers GitHub (rag-pme-usecases)
2. Vercel détecte le push
3. Build + deploy automatique
4. URL preview pour chaque PR
5. URL production sur merge vers main

**Build command**: `next build`
**Output directory**: `.next`
**Environment variables**: Aucune (site statique)

### Règles

1. **Site statique** — Aucune intégration backend (sauf chatbot)
2. **Chatbot RAG** — Partagé avec autres sites, endpoint commun
3. **200 use cases** — Données dans `lib/usecases-data.ts`
4. **Vercel auto-deploy** — Push GitHub → déploiement automatique
5. **CLAUDE.md sync** — Géré depuis mon-ipad via `push-directives.sh`
6. **Pas de n8n workflows** — Workflows PME sont dans mon-ipad, pas ici

### Tests

**Test site live**:
```bash
# Check homepage
curl -I https://nomos-pme-usecases-alexis-morets-projects.vercel.app

# Check sector pages
curl -I https://nomos-pme-usecases-alexis-morets-projects.vercel.app/finance
curl -I https://nomos-pme-usecases-alexis-morets-projects.vercel.app/sante
curl -I https://nomos-pme-usecases-alexis-morets-projects.vercel.app/juridique
curl -I https://nomos-pme-usecases-alexis-morets-projects.vercel.app/industrie
```

**Test chatbot**:
```bash
# Test API chatbot
curl -X POST "https://nomos-pme-usecases-alexis-morets-projects.vercel.app/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Quels sont les use cases pour automatiser la comptabilité?"}'
```

### Développement local

```bash
# Clone repo
gh repo clone LBJLincoln/rag-pme-usecases
cd rag-pme-usecases

# Install dependencies
npm install

# Run dev server
npm run dev
# → http://localhost:3000

# Build
npm run build

# Start production server
npm start
```

### Modification use cases

**Fichier data**: `lib/usecases-data.ts`

```typescript
export const usecases = {
  finance: [
    {
      id: 'fin-001',
      title: 'Automatisation de la comptabilité',
      description: 'IA qui catégorise automatiquement les transactions...',
      tags: ['comptabilité', 'automatisation', 'ML'],
      sector: 'finance',
      complexity: 'medium',
      roi: 'high'
    },
    // ... 49 autres
  ],
  sante: [ /* 50 use cases */ ],
  juridique: [ /* 50 use cases */ ],
  industrie: [ /* 50 use cases */ ]
}
```

**Process modification**:
1. Modifier `lib/usecases-data.ts`
2. Commit + push
3. Vercel auto-deploy
4. Vérifier live

### Notes

- Site 100% statique (sauf chatbot API)
- Aucune base de données
- Aucun workflow n8n dans ce repo
- Chatbot proxy vers n8n HF Space
- Déploiement Vercel instantané (<2 min)
