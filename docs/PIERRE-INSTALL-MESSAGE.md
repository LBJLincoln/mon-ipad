# Message Telegram pour Pierre — Installation Acer Aspire 3

> A copier-coller tel quel dans Telegram. En français. 3 actions max par étape.

---

## MESSAGE A ENVOYER

---

Salut Pierre ! Voici les 3 étapes pour connecter ton Acer au système. Ça prend environ 15 minutes. Suis les étapes dans l'ordre.

---

**ETAPE 1 sur 3 — Installer WSL2 (Linux sur Windows)**

Ouvre PowerShell EN TANT QU'ADMINISTRATEUR :
- Clique sur le menu Démarrer
- Tape "PowerShell"
- Fais clic droit → "Exécuter en tant qu'administrateur"

Puis copie-colle cette commande et appuie sur Entrée :

```
wsl --install -d Ubuntu
```

➜ Ton PC va redémarrer automatiquement. C'est normal.
➜ Après le redémarrage, Ubuntu s'ouvre et te demande un nom d'utilisateur + mot de passe. Mets ce que tu veux (note-les quelque part).

---

**ETAPE 2 sur 3 — Installer tous les outils (1 seule commande)**

Dans la fenêtre Ubuntu qui vient de s'ouvrir, copie-colle cette commande (c'est long, prends tout) :

```
sudo apt update && sudo apt upgrade -y && sudo apt install -y git python3-pip python3-venv curl wget build-essential && pip3 install nba_api pandas numpy requests && ssh-keygen -t ed25519 -f ~/.ssh/nomos_fleet -N "" && cat ~/.ssh/nomos_fleet.pub
```

➜ Ça va prendre 3-5 minutes.
➜ A la fin, tu vas voir une longue ligne commençant par "ssh-ed25519 AAAA...". Envoie-moi cette ligne par Telegram — c'est ta clé SSH, pas un mot de passe, c'est public.

---

**ETAPE 3 sur 3 — Connecter au serveur + tester**

Attends que je t'ajoute (je reçois ta clé SSH et je l'installe en 2 minutes). Puis lance :

```
ssh -i ~/.ssh/nomos_fleet termius@34.136.180.66 "echo 'Pierre connecte OK depuis '$(hostname)"
```

➜ Si tu vois "Pierre connecte OK depuis..." — c'est bon, tout fonctionne !
➜ Ensuite lance le script de vérification complet :

```
bash <(curl -s https://raw.githubusercontent.com/LBJLincoln/mon-ipad/main/scripts/fleet/pierre-health-check.sh)
```

---

**SI CA NE MARCHE PAS — Dépannage**

Problème : "wsl n'est pas reconnu"
→ Solution : ton Windows est trop vieux. Fais Windows Update d'abord, puis réessaie l'étape 1.

Problème : Ubuntu te demande un mot de passe UNIX
→ Solution : invente-en un (il ne s'affiche pas quand tu tapes, c'est normal). Retiens-le.

Problème : "Permission denied" à l'étape 3
→ Solution : envoie-moi ta clé SSH (la ligne ssh-ed25519) — je ne l'ai pas encore installée.

Problème : La commande de l'étape 2 s'arrête avec une erreur rouge
→ Solution : envoie-moi une capture d'écran de l'erreur.

Problème : "ssh: connect to host 34.136.180.66 port 22: Connection refused"
→ Solution : attends 5 minutes et réessaie. Le serveur est peut-être en train de redémarrer.

---

Une fois les 3 étapes faites, ton Acer tourne automatiquement comme noeud de collecte de données pour le système NBA. Tu n'as plus rien à faire.

---

*Nomos42 Fleet — Data Node setup | 2026-03-28*
