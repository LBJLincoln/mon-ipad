# Diagnostic CORRIGÉ - Migration Embeddings

**Date:** 2026-02-12  
**Correction:** Migration Cohere EFFECTUÉE et FONCTIONNELLE  
**Auteur:** Claude Code

---

## ✅ État Réel des Embeddings (CORRIGÉ)

### 🎯 Découverte
La migration vers Cohere a été **RÉUSSIE** ! Les deux indexes existent :

| Index | Dimension | Vecteurs | Status |
|-------|-----------|----------|--------|
| **sota-rag** | 1536d | 10,411 | Legacy (backup) |
| **sota-rag-cohere-1024** | **1024d** | **10,411** | ✅ **ACTIF** |

### Configuration n8n (Vérifiée)
```
EMBEDDING_MODEL: embed-english-v3.0
PINECONE_URL: https://sota-rag-cohere-1024-a4mkzmz.svc.aped-4627-b74a.pinecone.io
```

✅ **Les workflows utilisent bien l'index Cohere 1024d !**

---

## 🔴 Vrai Problème Identifié

Si la migration est faite et les workflows sont configurés correctement, pourquoi les pipelines échouent ?

### Analyse de l'exécution Graph RAG (ID#19305)

**Question:** "What disease is caused by mosquitoes?"

**Problème réel:** Les documents retrieved par Pinecone sont hors sujet :
- Climate change (score: 0.346)
- Vaccines (score: 0.315)
- Liver function (score: 0.300)

**Cause probable:**
1. **HyDE Generator** produit un document trop générique
2. **Entity Extraction** extrait des entités non pertinentes
3. **Embedding** est correct (1024d), mais le **texte** est mauvais
4. **Pinecone** retourne des résultats qui matchent le texte HyDE, pas la question

### Root Cause

```
Question: "What disease is caused by mosquitoes?"
       ↓
HyDE Generator (LLM - Trinity)
       ↓
Document HyDE: "Mosquitoes transmit malaria... [LONG TEXT about diseases]"
       ↓
Embedding (Cohere 1024d) ← CORRECT
       ↓
Pinecone Search sur sota-rag-cohere-1024
       ↓
🔴 Résultats: Climate change, Vaccines (PAS sur les moustiques !)
```

**Le problème n'est PAS la dimension, mais la QUALITÉ du HyDE et la RELEVANCE des embeddings.**

---

## 📊 Analyse des 2 Indexes

### Index Legacy (sota-rag - 1536d)
```
Dimension: 1536
Vectors: 10,411
Model: OpenAI text-embedding-3-small (legacy)
Status: Backup (conservé pour sécurité)
```

### Index Cohere (sota-rag-cohere-1024 - 1024d)
```
Dimension: 1024
Vectors: 10,411
Model: Cohere embed-english-v3.0
Status: ✅ ACTIF et utilisé par les workflows
```

**Migration réussie:** 10,411/10,411 vecteurs migrés (100%)

---

## 🔍 Pourquoi les Pipelines Échouent Malgré la Migration

### Hypothèses

1. **Problème HyDE Generator**
   - Le LLM (Trinity) génère des documents trop verbeux
   - Le prompt HyDE n'est pas assez contraint
   - Solution: Ajouter max_tokens ou reformuler le prompt

2. **Problème de Pertinence des Données**
   - Les vecteurs dans Pinecone ne correspondent pas aux questions
   - Les datasets de benchmark ont des questions difficiles
   - Solution: Vérifier la qualité des embeddings des documents

3. **Problème de Reranking**
   - Cohere Rerank n'est pas configuré correctement
   - Solution: Vérifier le nœud de reranking

4. **Problème de Seuil (Threshold)**
   - Le seuil de score pour considérer un document comme pertinent est trop haut
   - Solution: Ajuster le minimum score

---

## ✅ Checklist Post-Migration (À Vérifier)

- [x] Index Cohere 1024d créé
- [x] 10,411 vecteurs migrés
- [x] Variable n8n `EMBEDDING_MODEL` = embed-english-v3.0
- [x] Variable n8n `PINECONE_URL` = sota-rag-cohere-1024
- [ ] HyDE Generator produit des documents pertinents
- [ ] Scores de similarité > 0.5 pour documents pertinents
- [ ] Reranking fonctionne correctement
- [ ] Pipelines passent les tests 5/5

---

## 🎯 Prochaines Étapes Réelles

### 1. Tester un Query Direct sur Pinecone Cohere
```bash
# Générer un embedding avec Cohere
# Faire une requête sur sota-rag-cohere-1024
# Vérifier si les résultats sont pertinents
```

### 2. Analyser le Node HyDE Generator
```bash
python3 eval/node-analyzer.py --execution-id <ID>
# Vérifier le contenu généré par HyDE
# Vérifier la qualité de l'embedding
```

### 3. Comparer les Scores
- Legacy (1536d) vs Cohere (1024d) sur même query
- Si Cohere a des scores plus bas → problème de modèle
- Si scores similaires → problème de données

### 4. Vérifier le Workflow Standard RAG
- Exécution ID#19404 (Feb 12, 02:16:23) - Succeeded
- Analyser pourquoi celle-ci fonctionne
- Comparer avec l'exécution Graph RAG (ID#19305) - Semi-échouée

---

## 📁 Fichiers de Référence

| Fichier | Description |
|---------|-------------|
| `db/populate/migrate_to_cohere.py` | Script de migration (DÉJÀ EXÉCUTÉ) |
| `verify_pinecone_dims.py` | Vérification dimensions (pointe vers cohere-1024) |
| `docs/technical/credentials.md` | Clés API (Cohere ajoutée) |

---

## 📝 Conclusion

**La migration Cohere est RÉUSSIE et FONCTIONNELLE.**

Le problème des pipelines n'est pas la dimension des embeddings, mais probablement :
1. La qualité du HyDE generation
2. La pertinence des données dans Pinecone
3. La configuration du reranking

**Action prioritaire:** Analyser le node HyDE Generator et les scores de similarité réels.

---

*Document CORRIGÉ - La migration avait bien été effectuée !*
