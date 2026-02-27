#!/bin/bash
# ==============================================================================
# LAUNCH-ALL.sh — Restore and activate all 10 HF Spaces
# ==============================================================================
# Single self-contained script for non-technical users.
# Restores credentials, activates workflows, tests all webhooks, and reports status.
#
# Usage: bash scripts/launch-all.sh
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_ROOT/logs"
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
LOG_FILE="$LOG_DIR/launch-all-$TIMESTAMP.log"

# Scripts
RESTORE_SCRIPT="$SCRIPT_DIR/restore-all-spaces.py"
ACTIVATE_SCRIPT="$SCRIPT_DIR/activate-all-spaces.py"

# Environment file
ENV_FILE="$PROJECT_ROOT/.env.local"

# HF Spaces (10 total)
declare -a SPACES=(
    "https://lbjlincoln-nomos-rag-engine.hf.space"
    "https://lbjlincoln26-nomos-rag-engine-2.hf.space"
    "https://lbjlincoln-nomos-rag-engine-3.hf.space"
    "https://lbjlincoln26-nomos-rag-engine-4.hf.space"
    "https://lbjlincoln-nomos-rag-engine-5.hf.space"
    "https://lbjlincoln26-nomos-rag-engine-6.hf.space"
    "https://lbjlincoln-nomos-rag-engine-7.hf.space"
    "https://lbjlincoln26-nomos-rag-engine-8.hf.space"
    "https://lbjlincoln-nomos-rag-engine-9.hf.space"
    "https://lbjlincoln26-nomos-rag-engine-10.hf.space"
)

# Webhooks to test (5 core pipelines)
declare -A WEBHOOKS=(
    ["Standard"]="/webhook/rag-multi-index-v3"
    ["Graph"]="/webhook/ff622742-6d71-4e91-af71-b5c666088717"
    ["Quantitative"]="/webhook/3e0f8010-39e0-4bca-9d19-35e5094391a9"
    ["Orchestrator"]="/webhook/92217bb8-ffc8-459a-8331-3f553812c3d0"
    ["PME"]="/webhook/pme-assistant-gateway"
)

# Required environment variables
REQUIRED_VARS=(
    "OPENROUTER_API_KEY"
    "OPENROUTER_KEY_STANDARD"
    "OPENROUTER_KEY_GRAPH"
    "OPENROUTER_KEY_QUANTITATIVE"
    "OPENROUTER_KEY_ORCHESTRATOR"
    "PINECONE_API_KEY"
    "SUPABASE_PASSWORD"
    "NEO4J_PASSWORD"
)

# ==============================================================================
# Logging functions
# ==============================================================================

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log_no_color() {
    echo "$1" >> "$LOG_FILE"
}

header() {
    local msg="$1"
    local line="$(printf '=%.0s' {1..80})"
    log "\n${BOLD}${CYAN}$line${NC}"
    log "${BOLD}${CYAN}$msg${NC}"
    log "${BOLD}${CYAN}$line${NC}\n"
}

step() {
    log "${BOLD}${BLUE}▶ $1${NC}"
}

success() {
    log "${GREEN}✓ $1${NC}"
}

warning() {
    log "${YELLOW}⚠ $1${NC}"
}

error() {
    log "${RED}✗ $1${NC}"
}

progress() {
    log "${MAGENTA}→ $1${NC}"
}

# ==============================================================================
# Utility functions
# ==============================================================================

# Print banner
print_banner() {
    header "NOMOS AI — LAUNCH ALL HF SPACES"
    log "${BOLD}Date :${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    log "${BOLD}VM   :${NC} $(hostname) ($(hostname -I | awk '{print $1}'))"
    log "${BOLD}User :${NC} $(whoami)"
    log "${BOLD}Log  :${NC} $LOG_FILE"
    log ""
    log "${BOLD}Spaces à activer : ${GREEN}${#SPACES[@]}${NC}"
    log "${BOLD}Pipelines à tester : ${GREEN}${#WEBHOOKS[@]}${NC}"
    log ""
}

# Check dependencies
check_dependencies() {
    step "Vérification des dépendances système..."

    local deps=("python3" "curl" "jq")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing+=("$dep")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Dépendances manquantes : ${missing[*]}"
        error "Installez avec : sudo apt-get install -y ${missing[*]}"
        exit 1
    fi

    success "Toutes les dépendances sont installées"
}

# Check scripts exist
check_scripts() {
    step "Vérification des scripts Python..."

    if [ ! -f "$RESTORE_SCRIPT" ]; then
        error "Script manquant : $RESTORE_SCRIPT"
        exit 1
    fi

    if [ ! -f "$ACTIVATE_SCRIPT" ]; then
        error "Script manquant : $ACTIVATE_SCRIPT"
        exit 1
    fi

    success "Scripts Python trouvés"
}

# Source environment
source_env() {
    step "Chargement des variables d'environnement..."

    if [ ! -f "$ENV_FILE" ]; then
        error "Fichier .env.local introuvable : $ENV_FILE"
        exit 1
    fi

    # Source the file
    set +u  # Allow unset variables temporarily
    source "$ENV_FILE"
    set -u

    success "Fichier .env.local chargé"
}

# Check required environment variables
check_env_vars() {
    step "Vérification des variables d'environnement requises..."

    local missing=()
    local masked_count=0

    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var:-}" ]; then
            missing+=("$var")
        else
            # Show masked value
            local val="${!var}"
            local masked="${val:0:8}...${val: -4}"
            log "  ${GREEN}✓${NC} $var = $masked"
            masked_count=$((masked_count + 1))
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Variables manquantes : ${missing[*]}"
        warning "Éditez $ENV_FILE et ajoutez ces variables"
        exit 1
    fi

    success "Toutes les variables requises sont définies ($masked_count/$((${#REQUIRED_VARS[@]})))"
}

# Test HF Space connectivity
test_space_connectivity() {
    local space_url="$1"
    local timeout=10

    # Try health endpoint first
    if curl -sf --max-time "$timeout" "$space_url/healthz" > /dev/null 2>&1; then
        return 0
    fi

    # Try base URL
    if curl -sf --max-time "$timeout" "$space_url" > /dev/null 2>&1; then
        return 0
    fi

    return 1
}

# Test all HF Spaces
test_all_spaces() {
    step "Test de connectivité avec les ${#SPACES[@]} HF Spaces..."

    local reachable=0
    local unreachable=0

    for space in "${SPACES[@]}"; do
        local short_name=$(echo "$space" | sed 's|https://||' | sed 's|.hf.space||')
        progress "Test de $short_name..."

        if test_space_connectivity "$space"; then
            success "  $short_name : ACCESSIBLE"
            reachable=$((reachable + 1))
        else
            warning "  $short_name : INACCESSIBLE (timeout)"
            unreachable=$((unreachable + 1))
        fi
    done

    log ""
    if [ $unreachable -eq 0 ]; then
        success "Tous les spaces sont accessibles ($reachable/${#SPACES[@]})"
    else
        warning "$unreachable spaces inaccessibles sur ${#SPACES[@]}"
        log "${YELLOW}Ces spaces peuvent être en veille. Ils vont se réveiller lors du premier appel.${NC}"
    fi
}

# Run credential restoration
restore_credentials() {
    header "ÉTAPE 1/3 : RESTAURATION DES CREDENTIALS"

    step "Lancement de restore-all-spaces.py..."
    log "${CYAN}Ce processus va restaurer les credentials sur tous les HF Spaces.${NC}"
    log "${CYAN}Durée estimée : 2-3 minutes${NC}\n"

    # Run Python script
    if python3 "$RESTORE_SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
        success "Restauration des credentials terminée"

        # Check for report file
        local report="/home/termius/mon-ipad/logs/space-restoration-report.json"
        if [ -f "$report" ]; then
            log "\n${CYAN}Résumé du rapport :${NC}"
            local total=$(jq -r '.total_restored' "$report" 2>/dev/null || echo "0")
            local activated=$(jq -r '.total_activated' "$report" 2>/dev/null || echo "0")
            log "  Workflows restaurés : ${GREEN}$total${NC}"
            log "  Workflows activés : ${GREEN}$activated${NC}"
        fi

        return 0
    else
        error "Échec de la restauration des credentials"
        return 1
    fi
}

# Run workflow activation
activate_workflows() {
    header "ÉTAPE 2/3 : ACTIVATION DES WORKFLOWS"

    step "Lancement de activate-all-spaces.py..."
    log "${CYAN}Ce processus va activer tous les workflows sur tous les HF Spaces.${NC}"
    log "${CYAN}Durée estimée : 3-5 minutes${NC}\n"

    # Run Python script
    if python3 "$ACTIVATE_SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
        success "Activation des workflows terminée"

        # Check for report file
        local report="/home/termius/mon-ipad/logs/spaces-activation-report.json"
        if [ -f "$report" ]; then
            log "\n${CYAN}Résumé du rapport :${NC}"
            local total=$(jq -r '.total_workflows_activated' "$report" 2>/dev/null || echo "0")
            local successful=$(jq -r '.successful_logins' "$report" 2>/dev/null || echo "0")
            log "  Spaces activés : ${GREEN}$successful/${#SPACES[@]}${NC}"
            log "  Workflows activés : ${GREEN}$total${NC}"
        fi

        return 0
    else
        error "Échec de l'activation des workflows"
        return 1
    fi
}

# Test webhook on a single space
test_webhook_on_space() {
    local space_url="$1"
    local webhook_path="$2"
    local pipeline_name="$3"

    local full_url="${space_url}${webhook_path}"
    local timeout=30

    # Test with simple query
    local test_data='{"query":"What is RAG?","sector":"technology"}'

    local response
    local http_code

    response=$(curl -sf --max-time "$timeout" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        -w "\n%{http_code}" \
        "$full_url" 2>/dev/null || echo "ERROR")

    if [ "$response" = "ERROR" ]; then
        echo "TIMEOUT"
        return 1
    fi

    # Extract HTTP code (last line)
    http_code=$(echo "$response" | tail -n 1)

    # Extract body (all but last line)
    local body=$(echo "$response" | head -n -1)

    # Check if successful
    if [ "$http_code" = "200" ] && [ -n "$body" ] && [ "$body" != "null" ]; then
        echo "OK:$http_code"
        return 0
    elif [ "$http_code" = "200" ]; then
        echo "EMPTY:$http_code"
        return 1
    else
        echo "ERROR:$http_code"
        return 1
    fi
}

# Test all webhooks on all spaces
test_all_webhooks() {
    header "ÉTAPE 3/3 : TEST DES WEBHOOKS"

    step "Test de ${#WEBHOOKS[@]} webhooks sur ${#SPACES[@]} spaces..."
    log "${CYAN}Durée estimée : 5-10 minutes${NC}\n"

    local total_tests=$((${#WEBHOOKS[@]} * ${#SPACES[@]}))
    local completed=0
    local successful=0
    local failed=0

    # Results matrix
    declare -A results

    for space in "${SPACES[@]}"; do
        local short_name=$(echo "$space" | sed 's|https://||' | sed 's|.hf.space||')
        log "\n${BOLD}Testing space: $short_name${NC}"

        for pipeline in "${!WEBHOOKS[@]}"; do
            local webhook_path="${WEBHOOKS[$pipeline]}"

            progress "  $pipeline..."

            local result=$(test_webhook_on_space "$space" "$webhook_path" "$pipeline")
            local key="${short_name}::${pipeline}"
            results[$key]="$result"

            completed=$((completed + 1))

            if [[ "$result" == OK:* ]]; then
                success "    $pipeline : OK (HTTP ${result#OK:})"
                successful=$((successful + 1))
            elif [[ "$result" == EMPTY:* ]]; then
                warning "    $pipeline : EMPTY (HTTP ${result#EMPTY:})"
                failed=$((failed + 1))
            elif [[ "$result" == ERROR:* ]]; then
                error "    $pipeline : ERROR (HTTP ${result#ERROR:})"
                failed=$((failed + 1))
            else
                error "    $pipeline : TIMEOUT"
                failed=$((failed + 1))
            fi

            # Progress indicator
            local pct=$((completed * 100 / total_tests))
            log_no_color "Progress: $completed/$total_tests ($pct%)"
        done
    done

    # Summary
    log "\n${BOLD}${CYAN}Résultats globaux :${NC}"
    log "  Tests effectués : ${BOLD}$total_tests${NC}"
    log "  ${GREEN}✓ Succès : $successful${NC}"
    log "  ${RED}✗ Échecs : $failed${NC}"
    log "  ${BOLD}Taux de réussite : $((successful * 100 / total_tests))%${NC}"

    # Print matrix
    log "\n${BOLD}${CYAN}Matrice de résultats :${NC}\n"

    # Header
    printf "%-30s" "Space/Pipeline" | tee -a "$LOG_FILE"
    for pipeline in "${!WEBHOOKS[@]}"; do
        printf " %-15s" "$pipeline" | tee -a "$LOG_FILE"
    done
    echo "" | tee -a "$LOG_FILE"

    local line="$(printf '=%.0s' {1..120})"
    echo "$line" | tee -a "$LOG_FILE"

    # Rows
    for space in "${SPACES[@]}"; do
        local short_name=$(echo "$space" | sed 's|https://||' | sed 's|.hf.space||')
        printf "%-30s" "$short_name" | tee -a "$LOG_FILE"

        for pipeline in "${!WEBHOOKS[@]}"; do
            local key="${short_name}::${pipeline}"
            local result="${results[$key]}"

            local symbol
            if [[ "$result" == OK:* ]]; then
                symbol="${GREEN}✓${NC}"
            elif [[ "$result" == EMPTY:* ]]; then
                symbol="${YELLOW}∅${NC}"
            elif [[ "$result" == ERROR:* ]]; then
                symbol="${RED}✗${NC}"
            else
                symbol="${RED}⏱${NC}"
            fi

            printf " %-15s" "$(echo -e "$symbol")" | tee -a "$LOG_FILE"
        done
        echo "" | tee -a "$LOG_FILE"
    done

    # Per-pipeline summary
    log "\n${BOLD}${CYAN}Résultats par pipeline :${NC}"
    for pipeline in "${!WEBHOOKS[@]}"; do
        local pipeline_ok=0
        local pipeline_total=${#SPACES[@]}

        for space in "${SPACES[@]}"; do
            local short_name=$(echo "$space" | sed 's|https://||' | sed 's|.hf.space||')
            local key="${short_name}::${pipeline}"
            local result="${results[$key]}"

            if [[ "$result" == OK:* ]]; then
                pipeline_ok=$((pipeline_ok + 1))
            fi
        done

        local pct=$((pipeline_ok * 100 / pipeline_total))
        if [ $pct -ge 80 ]; then
            success "  $pipeline : $pipeline_ok/$pipeline_total spaces OK ($pct%)"
        elif [ $pct -ge 50 ]; then
            warning "  $pipeline : $pipeline_ok/$pipeline_total spaces OK ($pct%)"
        else
            error "  $pipeline : $pipeline_ok/$pipeline_total spaces OK ($pct%)"
        fi
    done

    return 0
}

# Generate final report
generate_final_report() {
    header "RAPPORT FINAL"

    local restore_report="/home/termius/mon-ipad/logs/space-restoration-report.json"
    local activate_report="/home/termius/mon-ipad/logs/spaces-activation-report.json"

    step "Génération du rapport consolidé..."

    # Consolidate data
    local total_spaces=${#SPACES[@]}
    local restored_workflows=0
    local activated_workflows=0
    local successful_logins=0

    if [ -f "$restore_report" ]; then
        restored_workflows=$(jq -r '.total_restored' "$restore_report" 2>/dev/null || echo "0")
    fi

    if [ -f "$activate_report" ]; then
        activated_workflows=$(jq -r '.total_workflows_activated' "$activate_report" 2>/dev/null || echo "0")
        successful_logins=$(jq -r '.successful_logins' "$activate_report" 2>/dev/null || echo "0")
    fi

    log "${BOLD}${GREEN}═══════════════════════════════════════════════════════${NC}"
    log "${BOLD}${GREEN}  NOMOS AI — DÉPLOIEMENT MULTI-SPACE COMPLÉTÉ${NC}"
    log "${BOLD}${GREEN}═══════════════════════════════════════════════════════${NC}\n"

    log "${BOLD}Résumé :${NC}"
    log "  ${CYAN}HF Spaces configurés :${NC} $successful_logins / $total_spaces"
    log "  ${CYAN}Workflows restaurés :${NC} $restored_workflows"
    log "  ${CYAN}Workflows activés :${NC} $activated_workflows"
    log ""

    log "${BOLD}Pipelines RAG disponibles :${NC}"
    for pipeline in "${!WEBHOOKS[@]}"; do
        log "  ${GREEN}✓${NC} $pipeline : ${WEBHOOKS[$pipeline]}"
    done
    log ""

    log "${BOLD}Prochaines étapes :${NC}"
    log "  1. Vérifiez les rapports détaillés :"
    log "     - $restore_report"
    log "     - $activate_report"
    log "  2. Lancez des tests avec : ${CYAN}python3 eval/quick-test.py --questions 5${NC}"
    log "  3. Consultez le dashboard : ${CYAN}https://nomos-dashboard-alexis-morets-projects.vercel.app${NC}"
    log ""

    log "${BOLD}Logs complets :${NC} $LOG_FILE"
    log ""

    success "Déploiement terminé avec succès!"
    log ""
}

# ==============================================================================
# Main execution
# ==============================================================================

main() {
    # Create log directory
    mkdir -p "$LOG_DIR"

    # Start logging
    log "Début du déploiement : $(date '+%Y-%m-%d %H:%M:%S')" > "$LOG_FILE"

    # Print banner
    print_banner

    # Pre-flight checks
    check_dependencies
    check_scripts
    source_env
    check_env_vars
    test_all_spaces

    # Pause before starting
    log "\n${YELLOW}Prêt à lancer le déploiement sur ${#SPACES[@]} HF Spaces...${NC}"
    if [ -t 0 ]; then
        log "${YELLOW}Appuyez sur ENTRÉE pour continuer ou CTRL+C pour annuler${NC}"
        read -r
    else
        log "${YELLOW}Mode non-interactif détecté: continuation automatique${NC}"
    fi

    # Main operations
    if ! restore_credentials; then
        error "La restauration des credentials a échoué. Vérifiez les logs."
        exit 1
    fi

    if ! activate_workflows; then
        error "L'activation des workflows a échoué. Vérifiez les logs."
        exit 1
    fi

    # Wait for spaces to settle
    step "Pause de 10 secondes pour laisser les spaces se stabiliser..."
    sleep 10

    if ! test_all_webhooks; then
        warning "Certains tests de webhooks ont échoué. Consultez le rapport."
    fi

    # Final report
    generate_final_report

    log "\n${BOLD}${GREEN}✓ Script terminé avec succès!${NC}"
    log "${CYAN}Consultez les logs : $LOG_FILE${NC}\n"
}

# Run main
main "$@"
