# Message Telegram pour Aurelien — Installation Acer Aspire 3

> A copier-coller tel quel dans Telegram. En francais. 2 etapes seulement.

---

## MESSAGE A ENVOYER

---

Salut Aurelien ! Voici 2 etapes pour connecter ton Acer au systeme. Ca prend 10 minutes. Apres ca, ton ordi travaille tout seul en fond — toi tu n'as rien a faire.

---

**ETAPE 1 sur 2 — Installer WSL2 + les outils**

Ouvre PowerShell EN TANT QU'ADMINISTRATEUR :
- Menu Demarrer > tape "PowerShell" > clic droit > "Executer en tant qu'administrateur"

Copie-colle :

```
wsl --install -d Ubuntu
```

Ton PC redemarrera. C'est normal. Apres, Ubuntu te demande un nom + mot de passe (mets ce que tu veux, note-les).

Ensuite dans Ubuntu, copie-colle cette commande :

```
sudo apt update && sudo apt upgrade -y && sudo apt install -y git python3-pip python3-venv curl wget build-essential && pip3 install nba_api pandas numpy requests scikit-learn xgboost lightgbm catboost && ssh-keygen -t ed25519 -f ~/.ssh/nomos_fleet -N "" && cat ~/.ssh/nomos_fleet.pub
```

Ca installe Python + les librairies de machine learning.
Envoie-moi la ligne ssh-ed25519 AAAA... qui s'affiche a la fin.

---

**ETAPE 2 sur 2 — Je fais le reste a distance**

Une fois que j'ai ta cle SSH, je configure tout depuis le serveur. Tu n'as plus rien a faire.

Ton Acer va faire tourner automatiquement :
- Des modeles de prediction (toutes les nuits, en fond)
- De la collecte de donnees sportives (toutes les heures)
- Du calcul qu'on faisait avant sur des serveurs payants

Ca n'utilise pas ta connexion internet de maniere visible, et ca ne ralentit pas ton PC sauf quand les modeles tournent (la nuit surtout).

Si tu veux arreter temporairement : ferme juste la fenetre Ubuntu.
Si tu veux relancer : ouvre Ubuntu, tape `screen -r` et c'est reparti.

---

**SI CA NE MARCHE PAS**

Probleme : "wsl n'est pas reconnu"
Solution : fais Windows Update d'abord, puis reessaie.

Probleme : erreur rouge pendant l'installation
Solution : capture d'ecran et envoie-moi.

---

Merci frero ! Ton Acer nous fait economiser ~50euros/mois de serveur GPU.

---

*Nomos42 Fleet — Compute Node setup | 2026-03-30*
