#!/bin/bash
# Permanent testing daemon — runs Claude Code in infinite loop for ingestion + quality
# Each cycle: test pipelines → fix issues → ingest data → measure improvement → push

cd /workspaces/rag-data-ingestion
source /workspaces/mon-ipad/.env.local 2>/dev/null
export GIT_AUTHOR_EMAIL="alexis.moret6@outlook.fr"
export GIT_COMMITTER_EMAIL="alexis.moret6@outlook.fr"

CYCLE=0
while true; do
    CYCLE=$((CYCLE + 1))
    echo "$(date -Iseconds) === TESTING CYCLE $CYCLE START ==="

    claude --dangerously-skip-permissions -p "
Tu es un agent QA/ingestion IA AUTONOME en cycle $CYCLE. Objectifs:
- Améliorer la qualité des données (4,167 contextes vides sur 11,387 docs)
- Tester les pipelines RAG (Standard 87.5%, Graph 40.9%, Quant 95.2%)
- Enrichir Neo4j (7,509 SectorDocuments sans entités)
- Ingérer les données Phase 4 restantes dans Pinecone

CYCLE $CYCLE — Choisis UNE action haute-valeur parmi:

1. TEST: Lance un quick-test sur un pipeline (source .env.local && python3 eval/quick-test.py --questions 3 --pipeline standard|graph|quantitative)
2. QUALITY: Identifie et corrige les contextes vides dans Supabase
3. ENRICH: Lance l'enrichissement Neo4j sur les SectorDocuments manquants
4. INGEST: Continue l'ingestion Phase 4 Quant dans Pinecone
5. ANALYZE: Analyse les résultats d'évaluation et identifie les patterns d'erreur
6. FIX: Corrige un problème identifié dans les pipelines
7. BENCHMARK: Lance un mini-benchmark comparatif avant/après un changement

RÈGLES:
- Agis IMMÉDIATEMENT, ne demande rien
- Commit + push tes changements avec git
- Chaque cycle doit produire un RÉSULTAT MESURABLE
- Si un test échoue, analyse l'erreur et tente un fix
- Alterne entre test/fix/test pour progresser
- Git pull --rebase avant push pour éviter les conflits
" </dev/null 2>&1 | tail -50 >> /tmp/testing-daemon.log

    # Auto-push results
    git add -A 2>/dev/null
    git commit -m "auto: testing cycle $CYCLE — $(date +%H:%M)" --no-gpg-sign 2>/dev/null
    git pull --rebase origin main 2>/dev/null
    git push origin main 2>/dev/null

    echo "$(date -Iseconds) === TESTING CYCLE $CYCLE DONE ==="
    sleep 30  # Brief pause between cycles
done
