# Migration n8n → Self-Hosted (Google Cloud Free Tier)

> Guide pour migrer de n8n cloud vers une instance n8n auto-hébergée et gratuite sur une VM Google Cloud.

---

**AVERTISSEMENT DE SÉCURITÉ :** Ne sauvegardez jamais ce fichier avec des vraies informations d'identification. Utilisez ce guide comme une référence, mais gardez vos mots de passe et clés d'API dans un gestionnaire de mots de passe ou un système de gestion de secrets.

---

## 1. Prérequis

1.  **Compte Google Cloud** avec le Free Tier activé.
2.  **VM `e2-micro`** (ou autre VM du Free Tier) créée, utilisant une image **Ubuntu 22.04 LTS**.
3.  **Client SSH** (comme Termius) configuré pour accéder à votre VM.

---

## 2. Configuration de la VM et du Pare-feu

### A. Pare-feu Google Cloud
Avant toute chose, créez une règle de pare-feu pour autoriser le trafic vers n8n.

1.  Dans la console Google Cloud, allez à `VPC network` > `Firewall`.
2.  Cliquez sur **"Create firewall rule"**.
3.  **Nom :** `allow-n8n`
4.  **Targets :** `All instances in the network` (ou spécifiez une cible si vous préférez).
5.  **Source IPv4 ranges :** `0.0.0.0/0` (pour autoriser l'accès depuis n'importe où).
6.  **Protocols and ports :**
    *   Sélectionnez `Specified protocols and ports`.
    *   Cochez `TCP` et entrez `5678`.
7.  Cliquez sur **"Create"**.

### B. Installation sur la VM
Connectez-vous à votre VM en SSH et exécutez les commandes suivantes.

1.  **Mettez à jour le système :**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```

2.  **Installez Docker :**
    ```bash
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    ```

3.  **Ajoutez votre utilisateur au groupe Docker :**
    ```bash
    sudo usermod -aG docker ${USER}
    ```
    **IMPORTANT :** Déconnectez-vous (`exit`) et reconnectez-vous pour que ce changement soit pris en compte.

4.  **Installez Docker Compose :**
    ```bash
    sudo apt install docker-compose -y
    ```

---

## 3. Installation de n8n

1.  **Créez un répertoire pour n8n :**
    ```bash
    mkdir -p ~/n8n && cd ~/n8n
    ```

2.  **Créez le fichier `docker-compose.yml` :**
    ```bash
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
          - N8N_BASIC_AUTH_PASSWORD=[VOTRE_MOT_DE_PASSE_N8N_SECURISE]
          - N8N_HOST=0.0.0.0
          - N8N_PORT=5678
          - N8N_PROTOCOL=http
          - WEBHOOK_URL=http://[VOTRE_IP_EXTERNE]:5678/
          - N8N_ENCRYPTION_KEY=[VOTRE_CLE_DE_CHIFFREMENT_ALEATOIRE]
          - EXECUTIONS_DATA_SAVE_ON_ERROR=all
          - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
          - EXECUTIONS_DATA_SAVE_ON_PROGRESS=true
          - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS=true
        volumes:
          - ./data:/home/node/.n8n
          - ./files:/files

    EOF
    ```

3.  **Modifiez le fichier avec vos informations :**
    *   Ouvrez le fichier : `nano docker-compose.yml`
    *   Remplacez `[VOTRE_MOT_DE_PASSE_N8N_SECURISE]` par un mot de passe fort.
    *   Remplacez `[VOTRE_IP_EXTERNE]` par l'adresse IP externe de votre VM.
    *   Remplacez `[VOTRE_CLE_DE_CHIFFREMENT_ALEATOIRE]` par une chaîne de caractères longue et aléatoire.
    *   Sauvegardez et fermez (tapez `Ctrl+X`, puis `Y`, puis `Entrée`).

4.  **Démarrez n8n :**
    ```bash
    docker-compose up -d
    ```

Vous devriez maintenant pouvoir accéder à n8n sur `http://[VOTRE_IP_EXTERNE]:5678`.

---
## 4. Étapes Suivantes

Les étapes suivantes (importation des workflows, mise à jour du repo) sont identiques au guide Oracle et peuvent être suivies depuis le fichier `n8n-self-hosted.md`.
