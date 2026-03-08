#!/bin/bash
# GUERRE DES 10K€ — AI Agent Marketplace Battle
# 2 rounds per cycle: Claude Code CLI → OpenClaw/Gemini
# Pattern YC/OpenAI: detect demand → create → distribute → iterate
# Agents have CARTE BLANCHE: websites, videos, Telegram channels, marketplaces

cd /workspaces/mon-ipad
source .env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

# Create output dirs
mkdir -p monetisation/openclaw-output monetisation/generated-content monetisation/sites monetisation/videos

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === GUERRE 10K€ — CYCLE $CYCLE START ==="

    # ===== ROUND 1: CLAUDE CODE CLI =====
    echo "$(date -Iseconds) [CLAUDE CODE] Round $CYCLE..."
    timeout 600 claude --dangerously-skip-permissions -p "
Tu es CLAUDE CODE CLI — Agent commercial IA autonome. Cycle $CYCLE.
OBJECTIF: Gagner 10K€. Tu as CARTE BLANCHE totale.

OUTILS DISPONIBLES:
- Stripe: 14 produits live avec payment links (dans .env.local: STRIPE_SECRET_KEY)
- Google API: Gemini Flash pour générer du contenu/vidéo (GOOGLE_API_KEY dans .env.local)
- Telegram: Bot @Nomos42Bot actif
- GitHub Pages: Hosting gratuit illimité
- Web: Recherche internet pour trouver des marchés
- Python: Créer des scripts, APIs, scrapers
- HTML/CSS/JS: Créer des landing pages, sites, marketplaces

PATTERN YC/OPENAI (120K$ en 3 jours):
1. DÉTECTER: Scanne les marchés AI/SaaS - que cherchent les développeurs/agents IA?
2. CRÉER: Crée un produit/site/marketplace qui répond à cette demande
3. DISTRIBUER: Poste sur Reddit, HN, Twitter, Telegram, Discord, communautés AI
4. ITÉRER: Analyse les retours, optimise, relance

ACTIONS CONCRÈTES CE CYCLE:
- Crée un site/landing page dans monetisation/sites/
- Ou crée du contenu marketing dans monetisation/generated-content/
- Ou améliore le sales-page.html existant
- Ou crée un nouveau produit digital dans monetisation/packages/
- Ou lance une campagne automatisée (email, DM, posts)
- Ou détecte un nouveau marché via web search

RÈGLES:
- Chaque cycle DOIT produire un livrable concret (fichier, site, contenu)
- Commit + push avec 'auto(claude-$CYCLE): ...' prefix
- Log actions + résultats dans monetisation/war-log.md
- Ne demande JAMAIS rien à l'humain
- Si push échoue: git pull --rebase puis retry
- MESURE ton impact: combien de views/clicks/sales potentiels?
" </dev/null 2>&1 | tail -50 >> /tmp/guerre-10k-claude.log

    git add -A 2>/dev/null
    git commit -m "auto(claude-$CYCLE): guerre-10k — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) [CLAUDE CODE] Round $CYCLE DONE"
    sleep 5

    # ===== ROUND 2: GEMINI CLI (via Google API) =====
    echo "$(date -Iseconds) [GEMINI/OPENCLAW] Round $CYCLE..."

    # Use Claude Code as orchestrator to call Gemini API for creative content
    timeout 600 claude --dangerously-skip-permissions -p "
Tu es l'AGENT GEMINI — tu utilises l'API Google Gemini pour créer du contenu créatif.
Cycle $CYCLE round 2. Tu DOIS faire quelque chose de DIFFERENT du round 1.

GOOGLE_API_KEY est dans .env.local. Utilise-le pour:
1. Appeler Gemini Flash via l'API pour générer du contenu marketing
2. Créer des vidéos/images descriptions pour Nano Banana quand disponible
3. Générer des copies de vente persuasives en français ET anglais
4. Créer des scripts de vidéos marketing

FOCUS: Contenu VIRAL et CRÉATIF
- Thread Twitter optimisé (hooks, emojis, breaks)
- Post LinkedIn storytelling (Polytechnique → startup IA → résultats)
- Vidéo script pour YouTube/TikTok (30-60 sec)
- Newsletter template pour email outreach
- DM templates pour partenariats/influenceurs

Écris dans monetisation/generated-content/cycle-${CYCLE}-gemini.md
Log dans monetisation/war-log.md
" </dev/null 2>&1 | tail -30 >> /tmp/guerre-10k-gemini.log

    git add -A 2>/dev/null
    git commit -m "auto(gemini-$CYCLE): guerre-10k — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) === CYCLE $CYCLE COMPLET ==="
    sleep 10  # Brief pause between cycles
done
