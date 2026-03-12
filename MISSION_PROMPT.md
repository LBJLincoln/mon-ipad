# MISSION: NOMOS SATELLITE INTELLIGENCE & BUSINESS FACTORY

## 1. VISION & ESTHÉTIQUE (TARGET: "SPY SATELLITE SIMULATOR")
- **Interface UI**: Développer un dashboard ultra-futuriste utilisant **Cesium** pour le globe 3D, **WebGL** pour les shaders (CRT, Vision Nocturne, FLIR thermique) et **satellite.js** pour simuler des orbites de scan de données.
- **Transparence OSINT**: Chaque entité (agent ou entreprise) doit être visualisée comme une cible satellite. Le zoom doit révéler les preuves d'exécution en temps réel.

## 2. STACK TECHNIQUE DE RÉFÉRENCE
- **Compute**: GPU NVIDIA T4 (Lightning AI) - Bridge FastAPI sur port 8080 pour accès distant via OpenClaw (HF).
- **Intelligence**: Intégration de la 'Reasoning Loop' de Karpathy (autoresearch) connectée à mon infrastructure Nomos.
- **Data**: Supabase (Postgres), Neo4j (Graph), Pinecone (Vector), Docling S6 (Parsing PDF).
- **Libraries**: Utiliser les dossiers `/ops` et `/eval` de mes repos Nomos pour les fixes de production.

## 3. PILIERS BUSINESS (DÉVELOPPEMENT PRIORITAIRE)

### A. MARKETPLACE D'AGENTS & D'ENTREPRISES (M&A IA)
- **Concept**: Plateforme de vente/enchères d'entreprises (IA-natives ou réelles) et d'agents spécialisés.
- **Module Valuator-S7 (Due Diligence)**:
    - **Valeur Idée**: Analyse de rareté via recherche Karpathy/Tavily.
    - **Valeur Exécution**: Preuve de travail extraite des logs de pipelines Nomos.
    - **Revenus Réels**: Analyse transparente des flux financiers (principe de confiance zéro).
- **Agent Négociateur**: IA experte capable de gérer les enchères et les discussions de rachat.

### B. AUTOMATED BUSINESS FACTORY (ABF)
- **Concept**: Création d'entreprise "Idea-to-Exit" 100% automatisée.
- **Workflow**: 
    1. Validation humaine sur interface futuriste.
    2. Étude de marché autonome via `autoresearch`.
    3. Déploiement automatique de la flotte d'agents (Marketing, Sales, Ops) via `agentic-loop.py`.
    4. Monitoring via la stack Satellite (OSINT/WebGL).

## 4. MODULE DE VALORISATION & TRANSPARENCE
- Chaque actif doit avoir une "Signature Thermique" en WebGL :
    - **Bleu/Froid**: Idée pure, pas d'exécution.
    - **Orange/Chaud**: Exécution prouvée (Data Ingestion active).
    - **Blanc/Fusion**: Revenus réels et traction marché confirmée par OSINT.

## 5. INSTRUCTIONS OPÉRATIONNELLES POUR CLAUDE CODE
1. **Bridge Setup**: Créer le tunnel FastAPI entre ce GPU Lightning et l'espace OpenClaw sur Hugging Face.
2. **Nomos Integration**: Injecter LiteLLM S7 comme proxy unique pour tous les appels LLM du projet Karpathy.
3. **Data Logging**: Rediriger toutes les découvertes de recherche vers la table Supabase `document_registry`.
4. **Futur Docs**: Attendre le fichier `COMMANDS_EXT.md` pour les détails d'implémentation des agents spécifiques.
