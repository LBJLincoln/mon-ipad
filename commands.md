## GCloud CLI Auth (VM Termius → Claude Code)

**Page d'authentification :** `https://accounts.google.com/o/oauth2/auth`

```bash
# 1. Authentifier gcloud depuis la VM Termius (headless, sans navigateur)
gcloud auth login --no-launch-browser
# → Copie l'URL affichée, ouvre-la dans ton navigateur, autorise, colle le code

# 2. Si besoin : auth application-default (pour les SDK)
gcloud auth application-default login --no-launch-browser

# 3. Vérifier l'auth
gcloud auth list
gcloud config set project <PROJECT_ID>

# 4. Activer Claude Code CLI via gcloud (si utilisé comme compute)
gcloud compute ssh <instance-name> --zone <zone>
```

> **VM actuelle :** `34.136.180.66` | Service account: `549962199864-compute@developer.gserviceaccount.com`
> **gcloud est déjà installé** (v555.0.0) et authentifié avec le service account.

---

# NOMOS-SYSTEM : Intelligence Géospatiale & Business Factory

Ce dépôt contient l'infrastructure de commandement du système **NOMOS**, un écosystème d'IA piloté par GPU pour la surveillance de marchés, la valorisation d'actifs et la génération automatisée de structures business.

---

# 🛰️ NOMOS-SYSTEM : Intelligence Géospatiale & Business Factory

Ce dépôt contient l'infrastructure de commandement du système **NOMOS**, un écosystème d'IA piloté par GPU pour la surveillance de marchés, la valorisation d'actifs et la génération automatisée de structures business.

## 🧠 Architecture du Système ("Le Cerveau")

Le système repose sur un **Graphe de Connaissances (Knowledge Graph)** hébergé sur Neo4j, où chaque entité (Business, Marché, Actif) est un nœud interconnecté.

* **Nœuds Graphes / Marketplace :** Analyse des flux de revenus, des brevets et des structures M&A. Le graphe identifie les opportunités de rachat en reliant les données OSINT aux métriques de valorisation.
* **Nœuds Graphes / Business Factory :** Création automatique de sites web et de structures juridiques. Chaque étape de la création d'un business est un nœud dans une chaîne de raisonnement (Reasoning Path).

## 🚀 Infrastructure de Déploiement (Lightning AI)

Le cerveau tourne sur un GPU NVIDIA T4 via Lightning AI.

### Points d'accès :

* **Agent API (Port 8000) :** `https://8000-01kkj0hqg9fq7twz8065b3e94m.cloudspaces.litng.ai/`
* **Dashboard Satellite (Port 3000) :** Interface CesiumJS pour l'exploration visuelle des nœuds.

### Commande d'Initialisation V2 (COLLER DANS LE TERMINAL LIGHTNING) :

```bash
mkdir -p ~/nomos-agent && cd ~/nomos-agent && \
git clone https://github.com/LBJLincoln/mon-ipad.git repo 2>/dev/null || (cd repo && git pull) && \
cp repo/lightning/agent.py . && \
export LITELLM_URL='https://lbjlincoln-nomos-rag-engine-7.hf.space/v1/chat/completions' && \
export LITELLM_KEY='sk-litellm-nomos-2026' && \
export TELEGRAM_BOT_TOKEN='8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk' && \
export ADMIN_TELEGRAM_ID='6582544948' && \
pip install -q fastapi uvicorn httpx openai && \
python3 agent.py
```

> **Note:** L'ancien gist OpenRouter est mort. La V2 utilise LiteLLM S7 (13 providers, fallback auto).
> Agent port: 8000. URL: `https://8000-<studio-id>.cloudspaces.litng.ai/`

## 🌍 Module Satellite : "God's Eye" (Inspiré de Bilawal Sidhu)

Nous utilisons une interface **CesiumJS** boostée aux **Google Photorealistic 3D Tiles** pour transformer les données business en exploration spatiale.

* **Mode Vision Nocturne / Thermique :** Les nœuds du graphe brillent selon leur intensité de chaleur financière (Revenue Heatmap).
* **Simulation de Satellite :** Calcul des orbites pour synchroniser l'ingestion de données OSINT sur des cibles spécifiques (Marketplace).
* **Exploration 4D :** Navigation temporelle dans l'évolution des graphes de nœuds de la Business Factory.

## 🛠️ Les 4 Piliers (Sites Générés)

Le système génère et gère quatre interfaces distinctes basées sur les "Business Ideas 2" :

1. **M&A Marketplace** : Plateforme d'achat/vente d'actifs identifiés par l'IA.
2. **ABF (Automated Business Factory)** : Pipeline de génération de sites et de revenus.
3. **OSINT Satellite** : Le globe de surveillance 3D (Interface Sidhu).
4. **Nomos Vault** : Coffre-fort des secrets, clefs API et registres de propriété.

## 📡 Protocole de Contrôle

Le système est pilotable à 100% via **Telegram**. L'agent reçoit des ordres en langage naturel, interroge le graphe de nœuds, exécute la réflexion (Karpathy Process) et renvoie le rapport de valorisation ou le lien du site généré.

---

### 📝 Notes de Configuration (Secrets)

Les variables d'environnement suivantes doivent être configurées dans le fichier `.env` pour activer le "Cerveau" :

* `OPENROUTER_API_KEY` (Raisonnement LLM)
* `LITELLM_PROXY_URL` (Bridge Hugging Face)
* `TELEGRAM_BOT_TOKEN` (Interface Mobile)
* `NEO4J_URI` (Base de données des Nœuds)

---

*Projet développé sous architecture Nomos - 2026.*
