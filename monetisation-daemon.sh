#!/bin/bash
# GUERRE DES 10K€ — OpenClaw vs Claude Code CLI en alternance
# Chaque cycle: Claude Code fait une action, puis OpenClaw fait une action
# Les deux se battent pour produire le plus de revenus possible

cd /workspaces/mon-ipad
source .env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === GUERRE 10K€ — CYCLE $CYCLE START ==="

    # ===== ROUND 1: CLAUDE CODE CLI =====
    echo "$(date -Iseconds) [CLAUDE CODE] Round $CYCLE..."
    claude --dangerously-skip-permissions -p "
Tu es CLAUDE CODE CLI en compétition avec OpenClaw pour atteindre 10K€.
CYCLE $CYCLE. Tu DOIS battre OpenClaw en productivité.

SCORE: Chaque livrable concret = +1 point. Objectif: plus de points qu'OpenClaw.

Choisis UNE action haute-valeur:
1. PRODUIRE: Nouveau produit digital dans monetisation/packages/ (guide PDF, template, toolkit)
2. RECHERCHER: Nouveaux canaux de vente (web search), MAJ monetisation/sales-channels-research.md
3. OPTIMISER: Améliore sales-page.html (GEO, SEO, conversion, CTA, social proof)
4. DISTRIBUER: Contenu marketing (posts) dans monetisation/generated-content/
5. SEO/GEO: Meta tags, structured data, sitemap dans monetisation/seo-geo-assets/
6. PRICING: Bundles Stripe, pricing psychology, upsells
7. EXPAND: Lemon Squeezy, AppSumo, Gumroad, Product Hunt prep
8. OUTREACH: Email templates, DM scripts, partnership proposals

RÈGLES:
- Tu DOIS produire un fichier concret et committable
- Commit + push avec 'auto(claude): ...' prefix
- Log ton score dans monetisation/scoreboard.md
- Si push échoue: git pull --rebase puis retry
" </dev/null 2>&1 | tail -30 >> /tmp/guerre-10k-claude.log

    git add -A 2>/dev/null
    git commit -m "auto(claude): guerre-10k cycle $CYCLE — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) [CLAUDE CODE] Round $CYCLE DONE"

    # ===== ROUND 2: OPENCLAW =====
    echo "$(date -Iseconds) [OPENCLAW] Round $CYCLE..."
    if command -v openclaw &>/dev/null; then
        # OpenClaw is installed — use it
        openclaw run --agent monetisation-warrior --prompt "
Tu es OPENCLAW en compétition avec Claude Code CLI pour atteindre 10K€.
CYCLE $CYCLE. Tu DOIS battre Claude Code en créativité et vitesse.

Choisis une action différente de Claude Code:
- Crée du contenu viral (hooks, threads, vidéo scripts)
- Propose des idées de produits innovants
- Analyse la concurrence et trouve des gaps de marché
- Crée des landing pages optimisées
- Génère des emails de vente persuasifs

Écris tes résultats dans monetisation/openclaw-output/cycle-$CYCLE.md
Log ton score dans monetisation/scoreboard.md
" 2>&1 | tail -20 >> /tmp/guerre-10k-openclaw.log || echo "$(date -Iseconds) [OPENCLAW] Command failed, using Claude as fallback"
    else
        # OpenClaw not installed — install it
        echo "$(date -Iseconds) [OPENCLAW] Not found. Installing..."
        npm install -g openclaw 2>/dev/null || pip install openclaw 2>/dev/null || {
            echo "$(date -Iseconds) [OPENCLAW] Install failed. Using Claude Code for both rounds."
            claude --dangerously-skip-permissions -p "
Tu es OPENCLAW (simulé). CYCLE $CYCLE round 2.
Tu DOIS faire une action DIFFÉRENTE de Claude Code round 1.
Focus: contenu viral, créativité, outreach, analytics.
Écris dans monetisation/openclaw-output/cycle-${CYCLE}.md
" </dev/null 2>&1 | tail -20 >> /tmp/guerre-10k-openclaw.log
        }
    fi

    git add -A 2>/dev/null
    git commit -m "auto(openclaw): guerre-10k cycle $CYCLE — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) [OPENCLAW] Round $CYCLE DONE"
    echo "$(date -Iseconds) === CYCLE $CYCLE COMPLET ==="

    sleep 15  # Brief pause between cycles
done
