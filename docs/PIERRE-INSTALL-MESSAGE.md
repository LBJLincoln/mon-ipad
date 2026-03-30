# Message Telegram pour Pierre — Installation MacBook Air 2016

> A copier-coller tel quel dans Telegram. En francais. 3 actions max par etape.

---

## MESSAGE A ENVOYER

---

Salut Pierre ! Voici les 3 etapes pour installer Claude Code Desktop sur ton MacBook Air. Ca prend environ 10 minutes. Suis les etapes dans l'ordre.

---

**ETAPE 1 sur 3 — Installer les outils de base**

Ouvre le Terminal (Applications > Utilitaires > Terminal) et copie-colle cette commande :

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Quand c'est fini, copie-colle :

```
brew install git python3 node && pip3 install nba_api pandas numpy requests && ssh-keygen -t ed25519 -f ~/.ssh/nomos_fleet -N "" && cat ~/.ssh/nomos_fleet.pub
```

Envoie-moi la ligne ssh-ed25519 AAAA... qui s'affiche a la fin — c'est ta cle SSH publique (pas un mot de passe).

---

**ETAPE 2 sur 3 — Installer Claude Code Desktop + Chrome extension**

1. Telecharge Claude Code Desktop :
   - Va sur https://claude.ai/download
   - Telecharge la version macOS
   - Ouvre le .dmg et deplace Claude dans Applications

2. Installe l'extension Chrome :
   - Ouvre Chrome
   - Va sur le Chrome Web Store
   - Cherche "Claude in Chrome" par Anthropic
   - Clique "Ajouter a Chrome"

3. Ouvre Claude Desktop, connecte-toi avec le compte que je t'envoie par message prive.

---

**ETAPE 3 sur 3 — Cloner le workspace + tester**

Attends que je t'ajoute (je recois ta cle SSH et je l'installe en 2 minutes). Puis dans le Terminal :

```
git clone git@github.com:LBJLincoln/nomos-pierre.git
cd nomos-pierre
```

Puis teste la connexion au serveur :

```
ssh -i ~/.ssh/nomos_fleet termius@34.136.180.66 "echo 'Pierre connecte OK depuis '$(hostname)"
```

Si tu vois "Pierre connecte OK depuis..." — tout fonctionne !

Puis lance le check complet :

```
bash scripts/pierre-health-check.sh
```

---

**ETAPE BONUS — Activer le dispatch (pour que je puisse utiliser ton navigateur)**

Dans Claude Desktop, va dans Settings > Extensions et verifie que "Claude in Chrome" est active.

Ensuite dans le Terminal :

```
cd ~/nomos-pierre
claude
```

Ca lance Claude Code en CLI. Tu peux le laisser tourner en fond — je pourrai t'envoyer des taches qui s'executent automatiquement sur ton Mac (scraping ESPN, DraftKings, etc. via ton Chrome).

---

**SI CA NE MARCHE PAS — Depannage**

Probleme : "brew: command not found"
Solution : Ferme et rouvre le Terminal, puis refais la commande brew.

Probleme : Le .dmg ne s'ouvre pas
Solution : Va dans Preferences Systeme > Securite, et autorise l'app.

Probleme : "Permission denied" au SSH
Solution : Envoie-moi ta cle SSH (la ligne ssh-ed25519) — je ne l'ai pas encore installee.

Probleme : Claude Desktop demande un code
Solution : Contacte-moi, je t'envoie les identifiants.

---

Une fois les 3 etapes faites, ton MacBook fait partie du reseau Nomos42. Claude Desktop + Chrome = je peux dispatcher des taches de scraping sur ton navigateur, et tu peux lancer les agents de recherche toi-meme.

---

*Nomos42 Fleet — Browser Node setup | 2026-03-30*
