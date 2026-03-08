#!/bin/bash
# Permanent monetisation daemon — runs Claude Code in infinite loop
# Each cycle: research → produce → optimize → push → next cycle

cd /workspaces/mon-ipad
source .env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === CYCLE $CYCLE START ==="
    
    claude --dangerously-skip-permissions -p "
Tu es un agent commercial IA AUTONOME en cycle $CYCLE. Objectif: atteindre 10K€ de revenus.
Tu ne t'arrêtes JAMAIS. Chaque cycle tu DOIS produire quelque chose de concret.

CYCLE $CYCLE — Choisis UNE action haute-valeur parmi:

1. PRODUIRE: Crée un nouveau produit digital (guide, template, toolkit) dans monetisation/packages/
2. RECHERCHER: Trouve de nouveaux canaux de vente (web search), MAJ monetisation/sales-channels-research.md
3. OPTIMISER: Améliore sales-page.html (GEO, SEO, conversion, A/B copy)
4. DISTRIBUER: Crée du contenu marketing (posts LinkedIn, Reddit, Twitter, HN) dans monetisation/generated-content/
5. DEPLOYER: Améliore les meta tags, structured data, sitemap dans monetisation/seo-geo-assets/
6. ANALYSER: Vérifie les prix Stripe, crée des bundles, optimise le pricing
7. EXPANDRE: Prépare le listing sur de nouvelles plateformes (Lemon Squeezy, AppSumo, Gumroad, Udemy)

RÈGLES:
- Agis IMMÉDIATEMENT, ne demande rien
- Commit + push tes changements avec git
- Chaque cycle doit produire un LIVRABLE concret
- Pense comme un growth hacker: test, measure, iterate
- Si un push échoue, git pull --rebase puis retry
- Utilise web search pour trouver les meilleures pratiques 2026
" </dev/null 2>&1 | tail -50 >> /tmp/monetisation-daemon.log
    
    # Auto-push results
    git add -A 2>/dev/null
    git commit -m "auto: monetisation cycle $CYCLE — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null
    
    echo "$(date -Iseconds) === CYCLE $CYCLE DONE ==="
    sleep 30  # Brief pause between cycles
done
