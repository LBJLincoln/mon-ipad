#!/bin/bash
# GUERRE DES 10K€ — V3: REAL SALES (no more Telegram spam)
# Focus: build conversion assets, prepare community posts, optimize sites
# Telegram KILLED — 2 members = 0 reach

cd /workspaces/mon-ipad
source .env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

mkdir -p monetisation/{generated-content,sites,packages,products}

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === REAL SALES — CYCLE $CYCLE START ===" >> /tmp/monetisation-daemon.log

    # ===== ROUND 1: BUILD CONVERSION ASSETS =====
    echo "$(date -Iseconds) [BUILD] Cycle $CYCLE — conversion assets..." >> /tmp/monetisation-daemon.log
    timeout 900 claude --dangerously-skip-permissions -p "
Tu es l'agent CONVERSION. Cycle $CYCLE. OBJECTIF: créer des assets qui VENDENT.

STOP TELEGRAM — 2 membres = 0 reach. NE POSTER AUCUN MESSAGE TELEGRAM.

STRIPE PRODUCTS (17 produits, \$27-\$497):
- MEGA BUNDLE \$497: https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d
- Architecture \$197, n8n Workflows \$197, Agentic Commerce \$197
- MCP+RAG Playbook \$147, Engineering Handbook \$147, Eval Framework \$127
- Ingestion Toolkit \$97, Dashboard \$97, Benchmark Toolkit \$67, Embeddings \$67
- Debug Playbook \$47, Claude Code Skills \$47, Agent Context Kit \$27

SITES VERCEL LIVE: rag-mega-bundle, rag-free-tools, ai-agent-marketplace, rag-roi-calculator, rag-maturity-assessment, agent-orchestration

CE CYCLE CHOISIS 2+ ACTIONS:
1. AMÉLIORER un site existant dans monetisation/sites/ (A/B test copy, meilleurs CTAs, testimonials)
2. CRÉER un nouveau lead magnet interactif (quiz, calculator, configurator)
3. CRÉER un package ZIP vendable dans monetisation/packages/ (avec contenu RÉEL)
4. ÉCRIRE un article technique COMPLET pour Dev.to dans monetisation/generated-content/devto-article-N.md
5. PRÉPARER un post Reddit r/LocalLLaMA ou r/RAG (pas spam — VALEUR TECHNIQUE + lien discret)
6. CRÉER une landing page optimisée pour un produit spécifique (SEO, JSON-LD, GEO)
7. OPTIMISER le SEO de docs/ pour GitHub Pages (sitemap, structured data)
8. PRÉPARER un Show HN submission dans monetisation/generated-content/show-hn.md

RÈGLES:
- JAMAIS poster sur Telegram (personne ne lit)
- Contenu doit être PUBLIABLE TEL QUEL sur les vraies plateformes
- Chaque article/post doit apporter de la VRAIE VALEUR technique
- Les liens Stripe doivent être SUBTILS (pas spam, intégrés naturellement)
- Commit + push après chaque livrable
- git pull --rebase origin main avant push
- Log dans monetisation/war-log.md
- NE JAMAIS demander à l'humain
" </dev/null 2>&1 | tail -80 >> /tmp/monetisation-daemon.log

    git add -A 2>/dev/null
    git commit -m "auto(build-$CYCLE): conversion-assets — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null || (git rebase --abort 2>/dev/null; git reset --hard origin/main 2>/dev/null)
    git push origin main 2>/dev/null
    sleep 3

    # ===== ROUND 2: COMMUNITY CONTENT =====
    echo "$(date -Iseconds) [CONTENT] Cycle $CYCLE — community content..." >> /tmp/monetisation-daemon.log
    timeout 600 claude --dangerously-skip-permissions -p "
Tu es l'agent CONTENT MARKETING. Cycle $CYCLE.

Créer du contenu PUBLIABLE pour les VRAIES communautés:

1. **Dev.to article** dans monetisation/generated-content/devto-ready-$CYCLE.md
   - Markdown complet, titre, tags (#rag #ai #tutorial)
   - 1500+ mots de VRAI contenu technique (code, architecture, benchmarks)
   - Lien produit EN FIN d'article (pas en intro)

2. **Reddit post** dans monetisation/generated-content/reddit-ready-$CYCLE.md
   - Pour r/LocalLLaMA ou r/RAG
   - Technique FIRST, produit SECOND
   - Pas de call-to-action agressif — laisser le contenu parler

3. **Show HN** dans monetisation/generated-content/showhn-ready-$CYCLE.md
   - Format Show HN strict: titre court, URL du produit, commentaire technique du maker

4. **SEO blog post** dans docs/blog-$CYCLE.md pour GitHub Pages
   - Optimisé pour les moteurs de recherche et les AI (GEO)
   - Structured data JSON-LD

RÈGLES:
- Contenu TECHNIQUE et HONNÊTE (pas de bullshit marketing)
- Montrer les résultats RÉELS (87.5% accuracy, 95.2% quant, 0$/mois infra)
- Commit + push
- NE PAS poster sur Telegram
" </dev/null 2>&1 | tail -40 >> /tmp/monetisation-daemon.log

    git add -A 2>/dev/null
    git commit -m "auto(content-$CYCLE): community-posts — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null || (git rebase --abort 2>/dev/null; git reset --hard origin/main 2>/dev/null)
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) === CYCLE $CYCLE DONE ===" >> /tmp/monetisation-daemon.log
    sleep 5
done
