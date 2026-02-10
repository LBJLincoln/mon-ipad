# État de Session

> Ce fichier est mis à jour à chaque fin de session Claude Code.
> Lire `docs/status.json` pour les métriques live.

---

## Dernière session

- **Date** : 2026-02-10
- **Ce qui a été fait** : Restructuration complète du repo
- **Ce qui reste à faire** :
  1. Fixer le pipeline Standard (0% → 85%)
  2. Fixer le pipeline Quantitative (0% → 85%)
  3. Fixer le pipeline Orchestrator (0% → 70%)
  4. Atteindre 10/10 sur chaque pipeline
  5. Lancer l'éval 200q Phase 1

---

## Pipeline Status (mise à jour manuelle)

| Pipeline | Dernier test | Score | 10/10 atteint ? |
|----------|-------------|-------|-----------------|
| Standard | Pas testé | 0% | Non |
| Graph | 17q | 76.5% | Non (mais passe la gate) |
| Quantitative | 8q | 0% | Non |
| Orchestrator | Pas testé | 0% | Non |

---

## Blockers connus

- Supabase/Neo4j pas accessibles directement (proxy 403) → passer par n8n
- Standard pipeline potentiellement cassé après migration embeddings
- Quantitative : 6 erreurs sur 8 questions

---

## Notes pour la prochaine session

- Commencer par `cat docs/status.json`
- Priorité : Standard > Quantitative > Orchestrator
- Graph est OK, ne pas toucher sauf régression
