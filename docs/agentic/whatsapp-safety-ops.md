# WhatsApp Safety Operations Pack

> **Version:** 1.0  
> **Date:** 2026-02-27  
> **Status:** Implementation-ready  
> **Scope:** PME Gateway + WhatsApp Business API integration

---

## Table of Contents

1. [Overview](#overview)
2. [Personal Conversation Filtering](#personal-conversation-filtering)
3. [Emergency Disable/Enable Commands](#emergency-disableenable-commands)
4. [Monitoring Loop](#monitoring-loop)
5. [Incident Response Playbook](#incident-response-playbook)
6. [Dedicated Account Setup](#dedicated-account-setup)
7. [OpenClaw CLI Reference](#openclaw-cli-reference)

---

## Overview

### Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Personal messages routed to RAG | **Critical** | Keyword + pattern filtering |
| WhatsApp Business API abuse | **High** | Rate limiting + circuit breaker |
| Credential exposure | **Critical** | Dedicated account isolation |
| Data retention violation | **High** | Auto-purge + no-log modes |
| Unauthorized access | **Medium** | IP allowlist + webhook verification |

### Architecture Safety Layer

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   WhatsApp      │────→│  Safety Gateway  │────→│   RAG Engine    │
│  Business API   │     │  (OpenClaw CLI)  │     │  (n8n/HF Space) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ↓           ↓           ↓
            ┌──────────┐ ┌──────────┐ ┌──────────┐
            │ Personal │ │ Business │ │ Emergency│
            │  Filter  │ │  Router  │ │  Kill    │
            └──────────┘ └──────────┘ └──────────┘
```

---

## Personal Conversation Filtering

### 2.1 Detection Patterns

**File:** `config/whatsapp-safety-filters.json`

```json
{
  "personal_indicators": {
    "family_keywords": [
      "maman", "papa", "mère", "père", "fils", "fille",
      "frère", "sœur", "cousin", "tante", "oncle", "grand-mère"
    ],
    "personal_pronouns": [
      "je", "tu", "il", "elle", "nous", "vous", "ils", "elles"
    ],
    "intimate_phrases": [
      "je t'aime", "tu me manques", "rendez-vous", "ce soir",
      "dîner", "cinéma", "vacances", "anniversaire"
    ],
    "personal_questions": [
      "comment vas-tu", "qu'est-ce que tu fais", "où es-tu",
      "tu viens", "tu peux", "tu veux"
    ]
  },
  "business_indicators": {
    "professional_keywords": [
      "devis", "facture", "contrat", "proposition", "réunion",
      "projet", "client", "fournisseur", "budget", "deadline"
    ],
    "business_entities": [
      "SARL", "SAS", "EURL", "entreprise", "société",
      "numéro siret", "tva", "kbis"
    ],
    "formal_greetings": [
      "bonjour madame", "bonjour monsieur", "cher client",
      "cordialement", "bien à vous", "salutations distinguées"
    ]
  },
  "scoring_thresholds": {
    "personal_score_max": 3,
    "business_score_min": 2,
    "uncertain_handoff": "human"
  }
}
```

### 2.2 Implementation in n8n

**Node:** `Code` → `Personal Message Filter`

```javascript
// Filter personal vs business messages
const body = $input.item.json.body || $input.item.json;
const message = (body.message || body.text || '').toLowerCase();

// Load filters from config
const filters = $env.WHATSAPP_FILTERS ? JSON.parse($env.WHATSAPP_FILTERS) : {};

let personalScore = 0;
let businessScore = 0;

// Score personal indicators
filters.personal_indicators?.family_keywords?.forEach(kw => {
  if (message.includes(kw.toLowerCase())) personalScore += 2;
});
filters.personal_indicators?.intimate_phrases?.forEach(kw => {
  if (message.includes(kw.toLowerCase())) personalScore += 3;
});
filters.personal_indicators?.personal_questions?.forEach(kw => {
  if (message.includes(kw.toLowerCase())) personalScore += 1;
});

// Score business indicators  
filters.business_indicators?.professional_keywords?.forEach(kw => {
  if (message.includes(kw.toLowerCase())) businessScore += 2;
});
filters.business_indicators?.business_entities?.forEach(kw => {
  if (message.includes(kw.toLowerCase())) businessScore += 3;
});

// Decision logic
const MAX_PERSONAL = filters.scoring_thresholds?.personal_score_max || 3;
const MIN_BUSINESS = filters.scoring_thresholds?.business_score_min || 2;

let routing = 'uncertain';
if (personalScore > MAX_PERSONAL && businessScore < MIN_BUSINESS) {
  routing = 'personal';
} else if (businessScore >= MIN_BUSINESS || personalScore <= 1) {
  routing = 'business';
}

return {
  original_message: body.message || body.text,
  personal_score: personalScore,
  business_score: businessScore,
  routing: routing,
  timestamp: new Date().toISOString(),
  user_id: body.user_id || body.from
};
```

### 2.3 Personal Message Handling

```javascript
// Auto-reply for personal messages
const replies = [
  "Bonjour ! Ce numéro est dédié aux conversations professionnelles. Pour toute question business, je suis là pour vous aider.",
  "Hello! I'm your business assistant. For personal matters, please use my personal number. How can I help with your business today?"
];

const autoReply = {
  type: "personal_rejected",
  reply: replies[0],
  logged: false,  // Never log personal messages
  routed_to_rag: false
};

return autoReply;
```

---

## Emergency Disable/Enable Commands

### 3.1 Immediate Disable (Kill Switch)

```bash
# Disable WhatsApp webhook entirely
openclaw whatsapp disable --immediate --reason "security_incident"

# Disable specific phone number
openclaw whatsapp disable --phone "+33612345678" --reason "suspicious_activity"

# Disable with auto-reply template
openclaw whatsapp disable --auto-reply "maintenance_mode"
```

**Effect:**
- Webhook returns HTTP 503 to Meta
- Auto-reply sent: "Service temporairement indisponible"
- All queued messages dropped (not persisted)
- Alert sent to `#whatsapp-ops` Slack channel

### 3.2 Circuit Breaker Mode

```bash
# Enable circuit breaker (fail-open after threshold)
openclaw whatsapp circuit-breaker enable \
  --error-threshold 10 \
  --time-window 60s \
  --cooldown 300s

# Check circuit status
openclaw whatsapp circuit-breaker status

# Manual reset
openclaw whatsapp circuit-breaker reset
```

### 3.3 Re-enable Commands

```bash
# Gradual re-enable (10% traffic ramp)
openclaw whatsapp enable --gradual --ramp-percentage 10

# Full restore
openclaw whatsapp enable --full

# Enable with enhanced monitoring
openclaw whatsapp enable --watch-mode --alert-on-personal
```

### 3.4 n8n Workflow Toggle

```bash
# Disable specific n8n workflow
openclaw n8n workflow toggle \
  --space "lbjlincoln-nomos-rag-engine" \
  --workflow "whatsapp-gateway" \
  --active false

# Bulk disable across all spaces
openclaw n8n workflow toggle \
  --all-spaces \
  --workflow "whatsapp-gateway" \
  --active false \
  --confirm
```

---

## Monitoring Loop

### 4.1 Real-time Safety Monitor

**File:** `scripts/whatsapp-safety-monitor.py`

```bash
# Start monitoring daemon
openclaw monitor whatsapp --daemon --config config/whatsapp-safety.yaml

# Single check
openclaw monitor whatsapp --once

# Check with verbose output
openclaw monitor whatsapp --verbose --alert-webhook "https://hooks.slack.com/..."
```

### 4.2 Key Metrics

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Personal message rate | >5% | >15% | Auto-disable |
| Message volume (1min) | >100 | >500 | Rate limit |
| Error rate | >2% | >10% | Circuit break |
| Avg response time | >3s | >10s | Alert + scale |
| Failed auth | >3 | >10 | Immediate kill |

### 4.3 Monitoring Configuration

```yaml
# config/whatsapp-safety.yaml
monitoring:
  interval: 30s
  metrics_retention: 24h
  
  alerts:
    slack_webhook: "${SLACK_WEBHOOK_URL}"
    pagerduty_key: "${PAGERDUTY_KEY}"
    
  thresholds:
    personal_message_percent: 5
    error_rate_percent: 2
    response_time_ms: 3000
    
  auto_actions:
    kill_switch_on_critical: true
    circuit_breaker_on_warning: true
    
  logging:
    level: warn
    personal_messages: false  # NEVER log personal messages
    business_messages: true   # Log business only
    
  compliance:
    gdpr_mode: true
    data_retention_hours: 24
    anonymize_user_ids: true
```

### 4.4 Safety Dashboard

```bash
# Launch safety dashboard
openclaw dashboard safety --port 8080

# View in terminal
openclaw whatsapp status --watch
```

**Dashboard Output:**
```
┌─ WhatsApp Safety Monitor ──────────────────────┐
│ Status: 🟢 HEALTHY                              │
│                                                 │
│ Messages (1h):  1,247    ▲ 12%                 │
│ Personal %:     2.1%     🟡 (threshold: 5%)    │
│ Error Rate:     0.3%     🟢                     │
│ Avg Latency:    1.2s     🟢                     │
│                                                 │
│ Circuit: CLOSED  │  Kill Switch: ARMED          │
│ Last Incident:  3 days ago                      │
└─────────────────────────────────────────────────┘
```

---

## Incident Response Playbook

### 5.1 Severity Levels

| Level | Description | Example | Response Time |
|-------|-------------|---------|---------------|
| P0 | Data breach | Personal messages leaked | Immediate |
| P1 | Service down | WhatsApp API failing | 15 min |
| P2 | Elevated risk | Personal rate 10-15% | 1 hour |
| P3 | Minor issue | Single user complaint | 24 hours |

### 5.2 P0 - Data Breach Response

```bash
# 1. IMMEDIATE KILL (0-30 seconds)
openclaw whatsapp disable --immediate --reason "P0_data_breach"

# 2. Verify kill
openclaw whatsapp status --verify-kill

# 3. Preserve evidence (business only)
openclaw logs export --since "1h ago" --filter business \
  --output "incident-$(date +%Y%m%d-%H%M%S).jsonl"

# 4. Rotate credentials
openclaw credentials rotate --service whatsapp --immediate

# 5. Notify stakeholders
openclaw alert send \
  --channel "#security-incidents" \
  --severity P0 \
  --message "WhatsApp gateway disabled - potential data breach"
```

**Post-Incident:**
```bash
# Audit what was exposed
openclaw audit whatsapp --since "24h ago" --exposure-check

# Generate incident report
openclaw report generate --incident-id "INC-2026-0227-001" \
  --type post-mortem --output docs/incidents/
```

### 5.3 P1 - Service Outage Response

```bash
# 1. Enable circuit breaker
openclaw whatsapp circuit-breaker enable --error-threshold 5

# 2. Diagnose
openclaw diagnose whatsapp --full

# 3. Check upstream
openclaw status --space all --pipeline whatsapp

# 4. If Meta API issue, enable fallback
openclaw whatsapp fallback enable --mode telegram
```

### 5.4 P2 - Elevated Personal Message Rate

```bash
# 1. Enable strict filtering
openclaw whatsapp filter --mode strict \
  --personal-threshold 1 \
  --business-threshold 3

# 2. Enable human review queue
openclaw whatsapp queue enable --mode manual-review

# 3. Alert team
openclaw alert send --channel "#whatsapp-ops" \
  --message "Elevated personal message rate detected - strict mode enabled"
```

### 5.5 Incident Tracking

```bash
# Create incident ticket
openclaw incident create \
  --severity P2 \
  --title "Elevated personal message rate" \
  --assignee "oncall-engineer"

# Update incident
openclaw incident update INC-2026-0227-042 \
  --status mitigated \
  --note "Strict filtering reduced personal rate to 1.2%"

# Close incident
openclaw incident close INC-2026-0227-042 \
  --resolution "Filtering adjusted, monitoring for 24h"
```

---

## Dedicated Account Setup

### 6.1 WhatsApp Business Account Isolation

```bash
# Create dedicated business account
openclaw account create \
  --name "nomos-business-whatsapp" \
  --type business \
  --isolation strict

# Configure for safety
openclaw account configure nomos-business-whatsapp \
  --personal-filter strict \
  --auto-purge 24h \
  --no-training-data \
  --gdpr-compliant
```

### 6.2 Phone Number Strategy

| Number Type | Purpose | Personal Use |
|-------------|---------|--------------|
| Primary | Customer service | ❌ Forbidden |
| Secondary | Marketing | ❌ Forbidden |
| Dedicated | CEO/direct comms | ❌ Forbidden |
| Personal | Human employee | ✅ Allowed |

```bash
# Register business phone
openclaw whatsapp register \
  --phone "+33123456789" \
  --display-name "Nomos AI Assistant" \
  --category "TECHNOLOGY" \
  --business-profile "config/business-profile.json"
```

### 6.3 Webhook Security

```bash
# Generate secure webhook URL
openclaw webhook generate \
  --service whatsapp \
  --verify-token "$(openssl rand -hex 32)" \
  --ip-allowlist "15.197.128.0/22,3.33.157.128/25"

# Rotate verification token
openclaw webhook rotate-token \
  --service whatsapp \
  --grace-period 300s
```

### 6.4 Credential Isolation

```bash
# Create isolated credential set
openclaw credentials create-set whatsapp-production \
  --isolation level-3 \
  --rotation 7d \
  --scope "whatsapp:*"

# Bind to specific workflows only
openclaw credentials bind whatsapp-production \
  --workflow "whatsapp-gateway" \
  --workflow "whatsapp-bridge"
```

### 6.5 Environment Separation

```bash
# Development (no real WhatsApp)
openclaw env create whatsapp-dev --mock-mode

# Staging (test business account)
openclaw env create whatsapp-staging \
  --phone "+33987654321" \
  --test-mode

# Production (strict isolation)
openclaw env create whatsapp-prod \
  --phone "+33123456789" \
  --strict-mode \
  --audit-all
```

---

## OpenClaw CLI Reference

### 7.1 Global Flags

```bash
openclaw [command] [subcommand] [flags]

Global Flags:
  -c, --config string    Config file (default "$HOME/.openclaw/config.yaml")
  -o, --output string    Output format: json|yaml|table (default "table")
  -v, --verbose          Enable verbose logging
      --dry-run          Simulate without making changes
      --confirm          Skip confirmation prompts
```

### 7.2 WhatsApp Commands

| Command | Description | Example |
|---------|-------------|---------|
| `whatsapp status` | Show current status | `openclaw whatsapp status --watch` |
| `whatsapp enable` | Enable gateway | `openclaw whatsapp enable --gradual` |
| `whatsapp disable` | Disable gateway | `openclaw whatsapp disable --immediate` |
| `whatsapp filter` | Configure filtering | `openclaw whatsapp filter --mode strict` |
| `whatsapp circuit-breaker` | Manage circuit breaker | `openclaw whatsapp circuit-breaker enable` |
| `whatsapp logs` | View logs (business only) | `openclaw whatsapp logs --tail` |
| `whatsapp stats` | Show statistics | `openclaw whatsapp stats --last 24h` |

### 7.3 Monitoring Commands

| Command | Description | Example |
|---------|-------------|---------|
| `monitor whatsapp` | Start monitoring | `openclaw monitor whatsapp --daemon` |
| `monitor dashboard` | Launch dashboard | `openclaw monitor dashboard` |
| `alert test` | Test alert channels | `openclaw alert test --channel slack` |

### 7.4 Incident Commands

| Command | Description | Example |
|---------|-------------|---------|
| `incident create` | Create incident | `openclaw incident create --severity P1` |
| `incident list` | List incidents | `openclaw incident list --open` |
| `incident update` | Update incident | `openclaw incident update INC-001 --status resolved` |
| `incident close` | Close incident | `openclaw incident close INC-001` |

### 7.5 n8n Integration Commands

| Command | Description | Example |
|---------|-------------|---------|
| `n8n workflow toggle` | Enable/disable workflow | `openclaw n8n workflow toggle --active false` |
| `n8n workflow list` | List workflows | `openclaw n8n workflow list --space all` |
| `n8n execution logs` | View execution logs | `openclaw n8n execution logs --workflow whatsapp-gateway` |

### 7.6 Audit & Compliance

| Command | Description | Example |
|---------|-------------|---------|
| `audit whatsapp` | Run compliance audit | `openclaw audit whatsapp --gdpr-check` |
| `logs export` | Export logs | `openclaw logs export --since "24h ago"` |
| `report generate` | Generate report | `openclaw report generate --type safety` |

### 7.7 Quick Reference Card

```bash
# EMERGENCY PROCEDURES
openclaw whatsapp disable --immediate              # Kill switch
openclaw whatsapp enable --full                     # Restore service
openclaw credentials rotate --service whatsapp      # Rotate creds

# DAILY OPERATIONS
openclaw whatsapp status                            # Check status
openclaw monitor whatsapp --once                    # Quick health check
openclaw whatsapp stats --last 24h                  # Daily stats

# TROUBLESHOOTING
openclaw diagnose whatsapp --full                   # Full diagnostic
openclaw logs export --since "1h ago"               # Export recent logs
openclaw n8n execution logs --last 10               # Recent executions

# COMPLIANCE
openclaw audit whatsapp --exposure-check            # Check for exposure
openclaw report generate --type gdpr                # GDPR compliance report
```

---

## Appendix A: n8n Safety Workflow Template

**File:** `n8n/templates/whatsapp-safety-gateway.json`

```json
{
  "name": "WhatsApp Safety Gateway",
  "nodes": [
    {
      "name": "WhatsApp Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "httpMethod": "POST",
        "path": "whatsapp-safety-gateway",
        "options": {
          "responseData": "={{$json.response}}"
        }
      }
    },
    {
      "name": "Kill Switch Check",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// Check if kill switch is active\nconst killSwitch = await $getWorkflowStaticData('global').killSwitch;\nif (killSwitch?.active) {\n  return { json: { killSwitchActive: true, reason: killSwitch.reason }};\n}\nreturn { json: { killSwitchActive: false }};"
      }
    },
    {
      "name": "Personal Filter",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "// See Section 2.2 for implementation"
      }
    },
    {
      "name": "Route Decision",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "rules": {
          "rules": [
            { "value": "personal", "output": 0 },
            { "value": "business", "output": 1 },
            { "value": "uncertain", "output": 2 }
          ]
        }
      }
    },
    {
      "name": "Auto-Reply Personal",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "={{$env.WHATSAPP_API_URL}}/messages",
        "jsonBody": "={\"messaging_product\": \"whatsapp\", \"to\": \"{{$json.user_id}}\", \"type\": \"text\", \"text\": {\"body\": \"This is a business number. For personal matters, please contact me directly.\"}}"
      }
    },
    {
      "name": "Forward to RAG",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "={{$env.RAG_GATEWAY_URL}}",
        "jsonBody": "={{JSON.stringify({query: $json.original_message, channel: 'whatsapp', user_id: $json.user_id})}}"
      }
    },
    {
      "name": "Human Review Queue",
      "type": "n8n-nodes-base.slack",
      "parameters": {
        "channel": "whatsapp-review",
        "text": "=:warning: Uncertain message requires review"
      }
    }
  ]
}
```

---

## Appendix B: Environment Variables

```bash
# Required
WHATSAPP_BUSINESS_ID=""
WHATSAPP_PHONE_NUMBER_ID=""
WHATSAPP_ACCESS_TOKEN=""
WHATSAPP_VERIFY_TOKEN=""
WHATSAPP_WEBHOOK_SECRET=""

# Safety
WHATSAPP_KILL_SWITCH_ENABLED="true"
WHATSAPP_PERSONAL_THRESHOLD="3"
WHATSAPP_CIRCUIT_BREAKER_THRESHOLD="10"
WHATSAPP_AUTO_PURGE_HOURS="24"

# Monitoring
WHATSAPP_MONITOR_INTERVAL="30s"
WHATSAPP_ALERT_SLACK_WEBHOOK=""
WHATSAPP_ALERT_PAGERDUTY_KEY=""

# Compliance
WHATSAPP_GDPR_MODE="true"
WHATSAPP_ANONYMIZE_USER_IDS="true"
WHATSAPP_LOG_LEVEL="warn"
```

---

*Last updated: 2026-02-27T17:04:00Z*  
*Next review: 2026-03-06*
