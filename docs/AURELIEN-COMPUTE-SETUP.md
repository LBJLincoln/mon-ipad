# Aurelien — Acer Aspire 3 Compute Node Setup

> Alexis's brother. His Acer = free compute for ML training.
> Aurelien doesn't interact with the system — Alexis SSHs in.
> Updated: 2026-03-30

## Message Telegram pour Aurelien

---

Salut Aurelien ! J'ai besoin de configurer ton PC pour que je puisse lancer des calculs dessus a distance. Ca prend 10 minutes, tu fais ca une fois et apres tu n'as plus rien a faire.

**ETAPE 1 — Installer WSL2 (Linux sur Windows)**

Ouvre PowerShell en tant qu'Administrateur (clic droit > Executer en tant qu'administrateur) et copie-colle :

```
wsl --install -d Ubuntu
```

Redemarre le PC quand c'est demande. Apres le redemarrage, Ubuntu va s'ouvrir et te demander un nom d'utilisateur et mot de passe. Mets ce que tu veux et envoie-moi les deux.

**ETAPE 2 — Installer les outils (dans Ubuntu)**

Ouvre Ubuntu (depuis le menu Demarrer) et copie-colle :

```
sudo apt update && sudo apt install -y python3 python3-pip openssh-server git curl && pip3 install scikit-learn xgboost lightgbm catboost pandas numpy nba_api
```

Puis active SSH :

```
sudo systemctl enable ssh && sudo systemctl start ssh
```

**ETAPE 3 — M'envoyer l'acces**

Dans Ubuntu, copie-colle :

```
ip addr show | grep "inet " | grep -v 127.0.0.1
```

Envoie-moi le numero qui s'affiche (ex: 192.168.1.XX). C'est l'adresse de ton PC sur le reseau.

Puis :

```
mkdir -p ~/.ssh && echo "ALEXIS_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
```

(Je t'envoie la cle exacte a coller a la place de ALEXIS_PUBLIC_KEY_HERE)

**APRES CA**

Tu n'as plus rien a faire. Ton PC lance des calculs en fond quand il est allume. Ca ne ralentit pas ton utilisation normale. Si tu veux eteindre le PC c'est OK, les calculs reprennent quand tu le rallumes.

---

## Setup cote VM (Alexis)

```bash
# 1. Add Aurelien's IP to env
echo 'export AURELIEN_IP=192.168.X.XX' >> ~/.bashrc

# 2. Copy SSH key
ssh-copy-id -i ~/.ssh/id_ed25519 aurelien_user@$AURELIEN_IP

# 3. Test
ssh aurelien_user@$AURELIEN_IP "python3 -c 'import sklearn; print(\"ML ready\")"

# 4. Remote training example
ssh aurelien_user@$AURELIEN_IP "cd /tmp && python3 -c '
from sklearn.ensemble import RandomForestClassifier
import numpy as np
X = np.random.rand(1000, 50)
y = (X[:, 0] > 0.5).astype(int)
rf = RandomForestClassifier(n_estimators=100)
rf.fit(X, y)
print(f\"Score: {rf.score(X, y):.4f}\")
print(\"Acer compute node working!\")
'"
```

## Cron (VM side — run training on Acer remotely)

```bash
# Add to VM crontab when Acer is on same network
# 0 */4 * * * ssh aurelien_user@$AURELIEN_IP "cd /tmp/nomos-training && python3 train.py" >> /tmp/acer-training.log 2>&1
```

## Specs: Acer Aspire 3
- CPU: Intel (multi-core)
- RAM: 4-8 GB
- GPU: Intel integrated (CPU training only)
- OS: Windows 11 + WSL2 Ubuntu
- Good for: scikit-learn, XGBoost, LightGBM, CatBoost (tree-based)
- Not for: PyTorch/TensorFlow GPU training (no discrete GPU)

---

*Nomos42 Fleet — Compute node | 2026-03-30*
