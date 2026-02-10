# Migration n8n Cloud → Self-Hosted (Oracle Cloud Free Tier)

> Guide complet pour migrer de n8n cloud payant vers n8n self-hosted gratuit.

---

## Pourquoi migrer ?

| Aspect | Cloud (actuel) | Self-hosted (cible) |
|--------|---------------|---------------------|
| **Coût** | ~20 EUR/mois | $0 (Oracle free tier) |
| **Accès DB** | Proxy 403 (Supabase/Neo4j bloqués) | Accès direct à tout |
| **Contrôle** | Limité | Total (custom nodes, logs, debug) |
| **Performance** | Partagé | Dédié (4 OCPU, 24GB RAM) |
| **MCP** | Seulement via webhooks | Accès direct aux DB |

---

## Prérequis

1. **Compte Oracle Cloud** (free tier) : https://cloud.oracle.com/
2. **VM ARM Ampere A1** : 4 OCPU, 24GB RAM (toujours gratuit)
3. **Termius** sur iPad (ou autre client SSH)
4. **Nom de domaine** (optionnel, pour HTTPS) ou utiliser l'IP directement

---

## Étape 1 : Créer la VM Oracle Cloud

1. Aller sur Oracle Cloud Console
2. Compute → Instances → Create Instance
3. Choisir :
   - **Shape** : VM.Standard.A1.Flex (ARM)
   - **OCPU** : 4
   - **RAM** : 24 GB
   - **OS** : Ubuntu 22.04
   - **Boot volume** : 200 GB (gratuit jusqu'à 200GB)
4. Télécharger la clé SSH
5. Noter l'IP publique

### Configurer le firewall Oracle (IMPORTANT)
```bash
# Dans Oracle Cloud Console → Networking → Virtual Cloud Networks
# → Security Lists → Default Security List
# Ajouter une règle Ingress :
# - Source CIDR : 0.0.0.0/0
# - Port : 5678 (n8n)
# - Protocol : TCP
```

---

## Étape 2 : Setup de la VM

```bash
# Depuis Termius, se connecter
ssh -i ~/key.pem ubuntu@<oracle-ip>

# Mettre à jour
sudo apt update && sudo apt upgrade -y

# Installer Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Se reconnecter pour que le groupe prenne effet
exit
ssh -i ~/key.pem ubuntu@<oracle-ip>

# Installer docker-compose
sudo apt install docker-compose -y

# Ouvrir le port dans iptables (Ubuntu sur Oracle)
sudo iptables -I INPUT -p tcp --dport 5678 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## Étape 3 : Installer n8n avec Docker

```bash
mkdir -p ~/n8n && cd ~/n8n

cat > docker-compose.yml << 'EOF'
version: '3'
services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=ChangeMeSecure123
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_URL=http://<oracle-ip>:5678/
      - N8N_ENCRYPTION_KEY=ChangeThisToRandomString
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
      - EXECUTIONS_DATA_SAVE_ON_PROGRESS=true
      - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true
    volumes:
      - ./data:/home/node/.n8n
      - ./files:/files

  redis:
    image: redis:alpine
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - ./redis-data:/data

EOF

# Démarrer
docker-compose up -d

# Vérifier
docker-compose logs -f n8n
```

Accéder à `http://<oracle-ip>:5678` depuis un navigateur.

---

## Étape 4 : Importer les workflows

### Depuis le repo GitHub
```bash
# Sur la VM Oracle
cd ~/n8n
git clone https://github.com/LBJLincoln/mon-ipad.git

# Importer via l'API n8n (une fois n8n démarré et API key générée)
export N8N_HOST="http://localhost:5678"
export N8N_API_KEY="<nouvelle-api-key>"

# Importer chaque workflow
for wf in mon-ipad/workflows/live/*.json; do
    curl -s -X POST "$N8N_HOST/api/v1/workflows" \
      -H "X-N8N-API-KEY: $N8N_API_KEY" \
      -H "Content-Type: application/json" \
      -d @"$wf"
done
```

### Configurer les credentials dans n8n
Dans l'UI n8n, aller dans Settings → Credentials et ajouter :
1. **OpenRouter** : Header Auth → `Authorization: Bearer sk-or-v1-...`
2. **Pinecone** : API Key → `pcsk_6GzVdD_...`
3. **Neo4j** : Bolt URL + password
4. **Supabase** : URL + API key
5. **Jina** : API Key → `jina_f1348...`

### Configurer les variables n8n
Settings → Variables :
- `EMBEDDING_MODEL` = `jina-embeddings-v3`
- `EMBEDDING_DIM` = `1024`
- `OPENROUTER_API_KEY` = `sk-or-v1-...`

---

## Étape 5 : Mettre à jour le repo

Après l'import, les workflows auront de nouveaux IDs. Mettre à jour :

```bash
# Sur votre machine de dev
# Mettre à jour N8N_HOST
export N8N_HOST="http://<oracle-ip>:5678"
export N8N_API_KEY="<nouvelle-api-key>"

# Vérifier que tout fonctionne
curl -s "$N8N_HOST/api/v1/workflows" -H "X-N8N-API-KEY: $N8N_API_KEY"

# Récupérer les nouveaux IDs et mettre à jour les fichiers :
# - docs/technical/credentials.md
# - docs/technical/n8n-endpoints.md
# - context/stack.md
# - .claude/settings.json
# - eval/quick-test.py (RAG_ENDPOINTS)
```

---

## Étape 6 : Setup Claude Code sur la VM

```bash
# Sur la VM Oracle
# Installer Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Installer Claude Code
npm install -g @anthropic-ai/claude-code

# Cloner le repo
cd ~
git clone https://github.com/LBJLincoln/mon-ipad.git
cd mon-ipad

# Configurer les credentials
source docs/technical/credentials.sh  # ou exporter manuellement

# Lancer Claude Code
claude
```

---

## Étape 7 : Vérification post-migration

```bash
# 1. Tester chaque webhook
python3 eval/quick-test.py --questions 1

# 2. Vérifier les accès DB directs (nouveau avantage !)
curl -s "http://localhost:5678/api/v1/workflows" -H "X-N8N-API-KEY: $N8N_API_KEY"

# 3. Sync les workflows
python3 workflows/sync.py

# 4. Commit les nouveaux workflow IDs
git add -A && git commit -m "chore: update workflow IDs after n8n migration"
git push -u origin main
```

---

## Rollback

Si la migration échoue, rester sur n8n cloud (aucun changement n'a été fait au cloud).
La migration est non-destructive : les workflows cloud restent actifs tant que vous ne résiliez pas.

---

## Checklist post-migration

- [ ] VM Oracle créée et accessible via SSH
- [ ] Docker + n8n installés et running
- [ ] 4 workflows importés et actifs
- [ ] Credentials configurées dans n8n
- [ ] Variables n8n configurées
- [ ] Webhooks testés (1 question par pipeline)
- [ ] Tous les fichiers du repo mis à jour avec les nouveaux IDs
- [ ] Claude Code installé sur la VM
- [ ] MCP servers configurés avec les nouveaux endpoints
- [ ] Eval 5/5 passé sur les 4 pipelines
