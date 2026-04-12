#!/bin/bash
# La Forge Factory — User Duplication Script
# Duplicates the full agent environment for a new user
# Usage: ./duplicate-user.sh <username> <tier> [product_idea]
# Tiers: free, builder, factory

set -euo pipefail

USERNAME="${1:?Usage: $0 <username> <tier> [product_idea]}"
TIER="${2:?Usage: $0 <username> <tier> — tiers: free, builder, factory}"
PRODUCT_IDEA="${3:-TBD}"
DATE=$(date +%Y-%m-%d)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORGE_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEMPLATE_DIR="$FORGE_DIR/scripts/forge/templates"
AGENTS_DIR="$FORGE_DIR/scripts/forge/agents"
USER_DIR="$FORGE_DIR/forge-users/$USERNAME"
DATA_DIR="$FORGE_DIR/data/forge-users"

echo "═══════════════════════════════════════════"
echo "  LA FORGE FACTORY — User Setup"
echo "  User: $USERNAME | Tier: $TIER"
echo "═══════════════════════════════════════════"

# Validate tier
if [[ ! "$TIER" =~ ^(free|builder|factory)$ ]]; then
    echo "ERROR: Invalid tier '$TIER'. Must be: free, builder, factory"
    exit 1
fi

# 1. Create user directory structure
echo "[1/8] Creating user directory structure..."
mkdir -p "$USER_DIR"/{products,strategy,comms,legal,finance,infra,.claude/commands}
mkdir -p "$USER_DIR"/data/agent-state
mkdir -p "$USER_DIR"/briefs
mkdir -p "$USER_DIR"/data/iterations

# 2. Generate CLAUDE.md from template
echo "[2/8] Generating CLAUDE.md for $TIER tier..."

# Set agent block based on tier
case "$TIER" in
    free)
        TIER_AGENTS_BLOCK=$(cat <<'AGENTS'
### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | ACTIVE (limited) | 5 msg/day, 1 brief, basic scan |
| 1 | Product Builder | DEMO ONLY | View-only, no build capability |
| 2 | Business Strategist | LOCKED | Upgrade to Builder ($50/mo) |
| 3 | Communication Manager | LOCKED | Upgrade to Builder ($50/mo) |
| 4 | Infra Manager | LOCKED | Upgrade to Factory ($200/mo) |
| 5 | Finance & Comptabilité | LOCKED | Upgrade to Factory ($200/mo) |
| 6 | Admin & Legal | LOCKED | Upgrade to Factory ($200/mo) |
AGENTS
)
        TIER_SKILLS_BLOCK="5 of 27 skills active (brainstorm, write-plan, browse, learn, verify)"
        ;;
    builder)
        TIER_AGENTS_BLOCK=$(cat <<'AGENTS'
### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | FULL | 100 msg/day, 3 briefs/mo, full scan |
| 1 | Product Builder | FULL | 3 products, 50 iter/day, shared Space |
| 2 | Business Strategist | FULL | Full niche + persona + pain canvas |
| 3 | Communication Manager | FULL | 3 channels, 30 posts/mo, text only |
| 4 | Infra Manager | READ-ONLY | View status only |
| 5 | Finance & Comptabilité | LOCKED | Upgrade to Factory ($200/mo) |
| 6 | Admin & Legal | LOCKED | Upgrade to Factory ($200/mo) |
AGENTS
)
        TIER_SKILLS_BLOCK="20 of 27 skills active (see tier-builder.md for full list)"
        ;;
    factory)
        TIER_AGENTS_BLOCK=$(cat <<'AGENTS'
### Active Agents
| # | Agent | Status | Capability |
|---|-------|--------|------------|
| 0 | Strategy Definer | FULL + UNLIMITED | Unlimited briefs, full market scan |
| 1 | Product Builder | FULL + UNLIMITED | Unlimited products, dedicated Space |
| 2 | Business Strategist | FULL + UNLIMITED | Big4 synthesis, PE-grade analysis |
| 3 | Communication Manager | FULL + UNLIMITED | ALL channels, full A/B, video scripts |
| 4 | Infra Manager | FULL | 24/7 monitoring, auto-restart, GPU |
| 5 | Finance & Comptabilité | FULL | Multi-channel tracking, invoices, forecast |
| 6 | Admin & Legal | FULL | Custom CGV/CGU, GDPR, KYC, disputes |
AGENTS
)
        TIER_SKILLS_BLOCK="ALL 27 skills active (see tier-factory.md for full list)"
        ;;
esac

# Generate CLAUDE.md
sed -e "s/{USERNAME}/$USERNAME/g" \
    -e "s/{TIER}/$TIER/g" \
    -e "s/{DATE}/$DATE/g" \
    -e "s/{PRODUCT_IDEA}/$PRODUCT_IDEA/g" \
    -e "s/{TARGET_USER}/TBD — Agent 2 will define/g" \
    -e "s/{PAIN_STATEMENT}/TBD — Agent 0 will discover/g" \
    -e "s/{REVENUE_MODEL}/TBD — Agent 2 will recommend/g" \
    "$TEMPLATE_DIR/CLAUDE.md.template" > "$USER_DIR/CLAUDE.md"

# Replace multi-line blocks (sed can't do this, use python)
python3 -c "
content = open('$USER_DIR/CLAUDE.md').read()
content = content.replace('{TIER_AGENTS_BLOCK}', '''$TIER_AGENTS_BLOCK''')
content = content.replace('{TIER_SKILLS_BLOCK}', '$TIER_SKILLS_BLOCK')
open('$USER_DIR/CLAUDE.md', 'w').write(content)
"

# 3. Copy tier config
echo "[3/8] Copying tier configuration..."
cp "$TEMPLATE_DIR/tier-$TIER.md" "$USER_DIR/.claude/tier-config.md"

# 4. Copy relevant agent definitions
echo "[4/8] Setting up agent definitions..."
case "$TIER" in
    free)
        cp "$AGENTS_DIR/agent-0-strategy-definer.md" "$USER_DIR/.claude/"
        ;;
    builder)
        cp "$AGENTS_DIR/agent-0-strategy-definer.md" "$USER_DIR/.claude/"
        cp "$AGENTS_DIR/agent-1-product-builder.md" "$USER_DIR/.claude/"
        cp "$AGENTS_DIR/agent-2-business-strategist.md" "$USER_DIR/.claude/"
        cp "$AGENTS_DIR/agent-3-communication-manager.md" "$USER_DIR/.claude/"
        ;;
    factory)
        cp "$AGENTS_DIR"/agent-*.md "$USER_DIR/.claude/"
        ;;
esac

# 5. Copy relevant skills (slash commands)
echo "[5/8] Installing skills for $TIER tier..."
COMMANDS_SRC="$FORGE_DIR/.claude/commands"

# Skills available per tier
FREE_SKILLS="sp-brainstorm sp-write-plan gstack-browse gstack-learn sp-verification-before-completion"
BUILDER_SKILLS="$FREE_SKILLS gstack-ship gstack-qa gstack-review gstack-investigate sp-test-driven-development sp-subagent-driven-development sp-dispatching-parallel-agents sp-execute-plan sp-systematic-debugging gstack-plan-eng-review gstack-retro progress-10pct karpathy-loop agent-review evolve-report"
FACTORY_SKILLS="$BUILDER_SKILLS gstack-cso gstack-guard gstack-careful gstack-canary spaces-health cross-repo-audit daily-edge"

case "$TIER" in
    free) SKILLS="$FREE_SKILLS" ;;
    builder) SKILLS="$BUILDER_SKILLS" ;;
    factory) SKILLS="$FACTORY_SKILLS" ;;
esac

for skill in $SKILLS; do
    if [ -f "$COMMANDS_SRC/$skill.md" ]; then
        cp "$COMMANDS_SRC/$skill.md" "$USER_DIR/.claude/commands/"
    fi
done

SKILL_COUNT=$(ls "$USER_DIR/.claude/commands/" 2>/dev/null | wc -l)
echo "   → $SKILL_COUNT skills installed"

# 6. Initialize agent state files
echo "[6/8] Initializing agent state..."
for i in 0 1 2 3 4 5 6; do
    cat > "$USER_DIR/data/agent-state/agent-$i-state.json" <<EOF
{
  "agent_id": $i,
  "user": "$USERNAME",
  "tier": "$TIER",
  "status": "idle",
  "last_action": null,
  "last_updated": "$DATE",
  "current_task": null,
  "outputs": []
}
EOF
done

# 7. Create user profile in forge-users data
echo "[7/8] Creating user profile..."
mkdir -p "$DATA_DIR"

# Add/update user in users.json
python3 -c "
import json, os
users_file = '$DATA_DIR/users.json'
if os.path.exists(users_file):
    with open(users_file) as f:
        users = json.load(f)
else:
    users = {}

users['$USERNAME'] = {
    'name': '$USERNAME',
    'tier': '$TIER',
    'created': '$DATE',
    'product_idea': '$PRODUCT_IDEA',
    'telegram_id': None,
    'login_code': 'FORGE-${USERNAME^^}-$(shuf -i 100-999 -n 1)',
    'active': True,
    'agents_active': $(case "$TIER" in free) echo 1;; builder) echo 4;; factory) echo 7;; esac),
    'skills_active': $SKILL_COUNT,
    'commission_rate': $(case "$TIER" in free) echo 0;; builder) echo 0.10;; factory) echo 0.05;; esac),
    'monthly_fee': $(case "$TIER" in free) echo 0;; builder) echo 50;; factory) echo 200;; esac)
}

with open(users_file, 'w') as f:
    json.dump(users, f, indent=2)
print(f'   → User {\"$USERNAME\"} registered ({\"$TIER\"} tier)')
"

# 8. Summary
echo "[8/8] Setup complete!"
echo ""
echo "═══════════════════════════════════════════"
echo "  USER SETUP COMPLETE"
echo "═══════════════════════════════════════════"
echo "  User:      $USERNAME"
echo "  Tier:      $TIER"
echo "  Directory: $USER_DIR"
echo "  Agents:    $(case "$TIER" in free) echo "1 active (Agent 0)";; builder) echo "4 active (Agents 0-3)";; factory) echo "7 active (ALL)";; esac)"
echo "  Skills:    $SKILL_COUNT of 27"
echo "  Fee:       $(case "$TIER" in free) echo "Free";; builder) echo '$50/mo + 10% commission';; factory) echo '$200/mo + 5% commission';; esac)"
echo ""
echo "  Next steps:"
echo "  1. User connects via @Forge42Bot with login code"
echo "  2. Agent 0 (Strategy Definer) starts ideation interview"
echo "  3. Product Brief → dispatched to active agents"
echo "═══════════════════════════════════════════"
