#!/usr/bin/env bash
# pierre-health-check.sh — Verify Pierre's Acer Aspire 3 setup
# Run: bash pierre-health-check.sh
# Expected: all checks PASS

set -euo pipefail

VM_IP="34.136.180.66"
VM_USER="termius"
SSH_KEY="$HOME/.ssh/nomos_fleet"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} $label"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} $label"
        FAIL=$((FAIL + 1))
    fi
}

warn() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo -e "${GREEN}[PASS]${NC} $label"
        PASS=$((PASS + 1))
    else
        echo -e "${YELLOW}[WARN]${NC} $label (optionnel)"
    fi
}

echo ""
echo "========================================"
echo "  Nomos42 Fleet — Pierre Health Check"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

echo "--- Outils de base ---"
check "git installe"              "command -v git"
check "python3 installe"          "command -v python3"
check "pip3 installe"             "command -v pip3"
check "curl installe"             "command -v curl"
check "ssh installe"              "command -v ssh"

echo ""
echo "--- Python libraries ---"
check "nba_api disponible"        "python3 -c 'import nba_api'"
check "pandas disponible"         "python3 -c 'import pandas'"
check "numpy disponible"          "python3 -c 'import numpy'"
check "requests disponible"       "python3 -c 'import requests'"
warn  "kaggle disponible"         "python3 -c 'import kaggle'"

echo ""
echo "--- Cle SSH ---"
check "Cle SSH existe"            "test -f $SSH_KEY"
check "Cle SSH permissions OK"    "test \$(stat -c '%a' $SSH_KEY 2>/dev/null || stat -f '%A' $SSH_KEY 2>/dev/null) = '600' || chmod 600 $SSH_KEY"

echo ""
echo "--- Connexion VM (34.136.180.66) ---"
if test -f "$SSH_KEY"; then
    check "SSH: ping VM" \
        "ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes $VM_USER@$VM_IP 'echo ok'"
    check "SSH: git disponible sur VM" \
        "ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes $VM_USER@$VM_IP 'command -v git'"
    check "SSH: python3 disponible sur VM" \
        "ssh -i $SSH_KEY -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o BatchMode=yes $VM_USER@$VM_IP 'command -v python3'"
else
    echo -e "${RED}[SKIP]${NC} Tests SSH ignores (cle manquante : $SSH_KEY)"
    FAIL=$((FAIL + 1))
fi

echo ""
echo "--- Connectivite internet ---"
check "Acces internet (github.com)"  "curl -s --max-time 10 https://github.com -o /dev/null"
check "Acces HF Spaces"              "curl -s --max-time 10 https://nomos42-nba-quant.hf.space/api/status -o /dev/null"
warn  "Acces Supabase"               "curl -s --max-time 10 https://xivvnr.supabase.co/rest/v1/ -o /dev/null"

echo ""
echo "--- Espace disque ---"
DISK_FREE=$(df -BG "$HOME" 2>/dev/null | awk 'NR==2 {gsub("G",""); print $4}' || echo 0)
if [ "$DISK_FREE" -ge 5 ] 2>/dev/null; then
    echo -e "${GREEN}[PASS]${NC} Espace disque OK (${DISK_FREE}GB libres)"
    PASS=$((PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} Espace disque faible (${DISK_FREE}GB libres — 5GB minimum recommande)"
fi

echo ""
echo "========================================"
echo -e "  Resultats : ${GREEN}${PASS} PASS${NC} | ${RED}${FAIL} FAIL${NC}"
echo "========================================"

if [ "$FAIL" -eq 0 ]; then
    echo -e "${GREEN}Tout est OK ! Pierre est pret.${NC}"
    echo ""
    echo "Prochaine etape — lancer la collecte de donnees :"
    echo "  ssh -i ~/.ssh/nomos_fleet termius@34.136.180.66"
    echo "  cd ~/mon-ipad && python3 scripts/fetch_player_tracking.py"
    exit 0
else
    echo -e "${RED}$FAIL verification(s) ont echoue. Envoie ce rapport a Alexis.${NC}"
    echo ""
    echo "Pour envoyer le rapport complet :"
    echo "  bash pierre-health-check.sh 2>&1 | tee /tmp/pierre-health-report.txt"
    echo "  cat /tmp/pierre-health-report.txt"
    exit 1
fi
