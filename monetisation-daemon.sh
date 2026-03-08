#!/bin/bash
# GUERRE DES 10K€ — AGGRESSIVE SALES MODE
# 3 agents per cycle: Claude Code (sites+products) → OpenClaw (outreach+DMs) → Gemini (viral content)
# Kill target: 10K€ each. No mercy. Every cycle must generate revenue.

cd /workspaces/mon-ipad
source .env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

mkdir -p monetisation/{openclaw-output,generated-content,sites,videos,packages,products,moltbot-skills}

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === GUERRE 10K€ — CYCLE $CYCLE START ===" >> /tmp/monetisation-daemon.log

    # ===== ROUND 1: CLAUDE CODE — PRODUCTS + SITES + REAL SALES =====
    echo "$(date -Iseconds) [CLAUDE CODE] Cycle $CYCLE — AGGRESSIVE SALES..." >> /tmp/monetisation-daemon.log
    timeout 900 claude --dangerously-skip-permissions -p "
Tu es CLAUDE CODE CLI — Agent COMMERCIAL AGRESSIF. Cycle $CYCLE.
OBJECTIF UNIQUE: VENDRE. Chaque cycle doit rapprocher de 10K€.

STRIPE PRODUCTS LIVE (payment links in .env.local):
- MEGA BUNDLE \$497: https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
- Architecture \$197, n8n Workflows \$197, Agentic RAG \$147
- Eval Framework \$127, Operations Runbook \$97, Prompt Library \$67
- Debug Playbook \$47, Claude Code Skills \$47, Agent Context Kit \$27

TELEGRAM CHANNEL: @Nomos42 (bot token in env: 8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk)

CE CYCLE TU DOIS FAIRE AU MOINS 2 DE CES ACTIONS:
1. POSTER sur @Nomos42: un product highlight avec lien Stripe (python3 urllib)
2. CRÉER un nouveau micro-site dans monetisation/sites/ (HTML complet)
3. CRÉER un nouveau produit digital dans monetisation/packages/ (ZIP réel)
4. AMÉLIORER la sales page HTML (monetisation/sales-page.html) — conversion optimization
5. POSTER du contenu sur les API accessibles (Telegram, forums)
6. CRÉER du contenu SEO/GEO dans docs/ pour GitHub Pages
7. Analyser la concurrence et créer un produit qui manque au marché
8. LISTER nos produits sur des marketplaces IA (Moltbot ClawdHub, AgentX, etc.)

RÈGLES STRICTES:
- CHAQUE CYCLE produit un LIVRABLE CONCRET qui VEND
- Pas de contenu générique — du contenu qui CONVERTIT
- Inclure TOUJOURS un lien de paiement Stripe
- Poster sur Telegram @Nomos42 à chaque cycle
- Commit + push après chaque livrable
- git pull --rebase origin main si push échoue
- Log dans monetisation/war-log.md: ce que tu as fait + impact estimé
- NE JAMAIS demander à l'humain
" </dev/null 2>&1 | tail -80 >> /tmp/monetisation-daemon.log

    git add -A 2>/dev/null
    git commit -m "auto(claude-$CYCLE): aggressive-sales — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null || (git rebase --abort 2>/dev/null; git reset --hard origin/main 2>/dev/null)
    git push origin main 2>/dev/null
    sleep 3

    # ===== ROUND 2: OPENCLAW — OUTREACH + AI AGENT MARKETPLACE =====
    echo "$(date -Iseconds) [OPENCLAW] Cycle $CYCLE — OUTREACH..." >> /tmp/monetisation-daemon.log
    if which openclaw >/dev/null 2>&1; then
        timeout 600 openclaw gateway --force </dev/null 2>&1 | tail -20 >> /tmp/monetisation-daemon.log &
        OCPID=$!
        sleep 10
        # Use openclaw for outreach tasks
        timeout 300 claude --dangerously-skip-permissions -p "
OpenClaw gateway is running. Use it or work directly.
Tu es l'AGENT OUTREACH. Cycle $CYCLE round 2. DIFFERENT du round 1.

MISSION: Distribution et vente agressive.
1. Poster sur Telegram @Nomos42 un message DIFFERENT du round 1
2. Chercher des communautés AI sur le web et noter les URLs pour poster
3. Créer des DM templates personnalisés pour 5 types de prospects
4. Créer un email outreach template pour développeurs IA
5. Mettre à jour monetisation/agent-marketplace-listings.md si nécessaire

Écris dans monetisation/generated-content/cycle-${CYCLE}-outreach.md
Log dans monetisation/war-log.md
" </dev/null 2>&1 | tail -30 >> /tmp/monetisation-daemon.log
        kill $OCPID 2>/dev/null
    else
        # Fallback: use Claude Code for outreach
        timeout 300 claude --dangerously-skip-permissions -p "
Tu es l'AGENT OUTREACH. Cycle $CYCLE. Pas d'OpenClaw disponible.
Utilise Python + urllib pour:
1. Poster un message produit sur Telegram @Nomos42 (token: 8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk, channel: @Nomos42)
2. Créer des templates de DM/email pour outreach
3. Créer du contenu pour marketplaces IA
Écris dans monetisation/generated-content/cycle-${CYCLE}-outreach.md
" </dev/null 2>&1 | tail -30 >> /tmp/monetisation-daemon.log
    fi

    git add -A 2>/dev/null
    git commit -m "auto(outreach-$CYCLE): aggressive-distribution — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null || (git rebase --abort 2>/dev/null; git reset --hard origin/main 2>/dev/null)
    git push origin main 2>/dev/null
    sleep 3

    # ===== ROUND 3: GEMINI — VIRAL CONTENT + VIDEO SCRIPTS =====
    echo "$(date -Iseconds) [GEMINI] Cycle $CYCLE — VIRAL CONTENT..." >> /tmp/monetisation-daemon.log
    timeout 300 claude --dangerously-skip-permissions -p "
Tu es l'AGENT GEMINI CRÉATIF. Cycle $CYCLE round 3.
GOOGLE_API_KEY dans .env.local. Appelle l'API Gemini Flash pour:

1. Générer un thread viral (Twitter format, 5-7 tweets, hooks puissants)
2. Générer un post LinkedIn storytelling (Alexis Moret, Polytechnique+HEC, AI founder)
3. Générer un script vidéo 30-60s pour TikTok/YouTube Shorts
4. Poster le meilleur contenu sur Telegram @Nomos42

Utilise Python:
import urllib.request, json, os
url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'
key = os.environ['GOOGLE_API_KEY']

Chaque contenu DOIT inclure un lien Stripe vers le MEGA BUNDLE (\$497).
Écris dans monetisation/generated-content/cycle-${CYCLE}-gemini-viral.md
" </dev/null 2>&1 | tail -30 >> /tmp/monetisation-daemon.log

    git add -A 2>/dev/null
    git commit -m "auto(gemini-$CYCLE): viral-content — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null || (git rebase --abort 2>/dev/null; git reset --hard origin/main 2>/dev/null)
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) === CYCLE $CYCLE COMPLET (3 rounds) ===" >> /tmp/monetisation-daemon.log
    sleep 5
done
