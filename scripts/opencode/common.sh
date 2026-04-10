#!/bin/bash
################################################################################
# OpenCode Department Agent — Shared Functions
# Sources API keys, locates binary, provides fallback to python3+HF Inference
################################################################################

REPO_ROOT="/home/termius/mon-ipad"
OPENCODE_BIN="/home/termius/.local/bin/opencode"
DATA_DIR="$REPO_ROOT/data/opencode"
ENV_FILE="$REPO_ROOT/.env.local"
TIMEOUT_SECONDS=300

# Source environment
source "$ENV_FILE" 2>/dev/null || true

# Export keys OpenCode expects
export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
export GEMINI_API_KEY="${GOOGLE_API_KEY:-}"

# Ensure data directory exists
mkdir -p "$DATA_DIR"

# Check if OpenCode is available and configured
opencode_available() {
    if [ ! -x "$OPENCODE_BIN" ]; then
        return 1
    fi
    # Need at least one API key
    if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$OPENROUTER_API_KEY" ] && [ -z "$GEMINI_API_KEY" ]; then
        echo "WARNING: No API keys found for OpenCode" >&2
        return 1
    fi
    return 0
}

# Generate temporary .opencode.json config for non-interactive use
generate_opencode_config() {
    local work_dir="${1:-$REPO_ROOT}"
    local model="${2:-claude-sonnet-4}"
    local max_tokens="${3:-4000}"

    # Determine provider and model from available keys
    local provider="anthropic"
    local actual_model="$model"

    if [ -n "$ANTHROPIC_API_KEY" ]; then
        provider="anthropic"
    elif [ -n "$OPENROUTER_API_KEY" ]; then
        provider="openrouter"
        actual_model="anthropic/claude-sonnet-4"
    elif [ -n "$OPENAI_API_KEY" ]; then
        provider="openai"
        actual_model="gpt-4o"
    elif [ -n "$GEMINI_API_KEY" ]; then
        provider="gemini"
        actual_model="gemini-2.5-flash"
    fi

    cat > "$work_dir/.opencode.json" << JSONEOF
{
  "data": {
    "directory": ".opencode"
  },
  "providers": {
    "anthropic": {
      "apiKey": "${ANTHROPIC_API_KEY:-}",
      "disabled": $([ -z "$ANTHROPIC_API_KEY" ] && echo "true" || echo "false")
    },
    "openai": {
      "apiKey": "${OPENAI_API_KEY:-}",
      "disabled": $([ -z "$OPENAI_API_KEY" ] && echo "true" || echo "false")
    },
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY:-}",
      "disabled": $([ -z "$OPENROUTER_API_KEY" ] && echo "true" || echo "false")
    },
    "gemini": {
      "apiKey": "${GEMINI_API_KEY:-}",
      "disabled": $([ -z "$GEMINI_API_KEY" ] && echo "true" || echo "false")
    }
  },
  "agents": {
    "coder": {
      "model": "$actual_model",
      "maxTokens": $max_tokens
    },
    "task": {
      "model": "$actual_model",
      "maxTokens": $max_tokens
    },
    "title": {
      "model": "$actual_model",
      "maxTokens": 80
    }
  },
  "autoCompact": false,
  "debug": false
}
JSONEOF
}

# Run OpenCode with a prompt, return output
run_opencode() {
    local prompt="$1"
    local output_format="${2:-json}"

    generate_opencode_config "$REPO_ROOT"
    timeout "$TIMEOUT_SECONDS" "$OPENCODE_BIN" \
        -p "$prompt" \
        -f "$output_format" \
        -q \
        -c "$REPO_ROOT" \
        2>/dev/null
}

# Fallback: use python3 + OpenRouter/HF Inference API
run_fallback() {
    local prompt="$1"
    local output_file="$2"

    # Try providers in order: OpenRouter → OpenAI → Gemini
    local providers=()
    [ -n "${OPENROUTER_API_KEY:-}" ] && providers+=("openrouter")
    [ -n "${OPENAI_API_KEY:-}" ] && providers+=("openai")
    [ -n "${GEMINI_API_KEY:-}${GOOGLE_API_KEY:-}" ] && providers+=("gemini")

    if [ ${#providers[@]} -eq 0 ]; then
        echo '{"error": "No API keys available for fallback", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$output_file"
        return 1
    fi

    # Export prompt via env var to avoid shell quoting issues with triple-quotes
    export _FALLBACK_PROMPT="$prompt"

    for provider in "${providers[@]}"; do
        local response=""
        local success=false

        case "$provider" in
            openrouter)
                log "fallback" "Trying OpenRouter..."
                response=$(python3 -c "
import json, os, sys
prompt = os.environ['_FALLBACK_PROMPT']
print(json.dumps({'model': 'anthropic/claude-sonnet-4', 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': prompt}]}))
" | curl -sSL "https://openrouter.ai/api/v1/chat/completions" \
                    -H "Content-Type: application/json" \
                    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
                    -d @- \
                    --max-time 120 2>/dev/null) && success=true
                ;;
            openai)
                log "fallback" "Trying OpenAI..."
                response=$(python3 -c "
import json, os
prompt = os.environ['_FALLBACK_PROMPT']
print(json.dumps({'model': 'gpt-4o-mini', 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': prompt}]}))
" | curl -sSL "https://api.openai.com/v1/chat/completions" \
                    -H "Content-Type: application/json" \
                    -H "Authorization: Bearer $OPENAI_API_KEY" \
                    -d @- \
                    --max-time 120 2>/dev/null) && success=true
                ;;
            gemini)
                log "fallback" "Trying Gemini..."
                local gkey="${GEMINI_API_KEY:-${GOOGLE_API_KEY:-}}"
                export _FALLBACK_GKEY="$gkey"
                response=$(python3 -c "
import json, urllib.request, os

prompt = os.environ['_FALLBACK_PROMPT']
gkey = os.environ['_FALLBACK_GKEY']
url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gkey}'
payload = json.dumps({'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'maxOutputTokens': 8000}}).encode()
req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
        text = data['candidates'][0]['content']['parts'][0]['text']
        # Wrap in OpenAI-compatible format for downstream parsing
        print(json.dumps({'choices': [{'message': {'content': text}}]}))
except Exception as e:
    print(json.dumps({'error': str(e)}))
" 2>/dev/null) && success=true
                ;;
        esac

        if $success && echo "$response" | python3 -c "
import json, sys, re
try:
    r = json.load(sys.stdin)
    if 'error' in r and 'choices' not in r:
        sys.exit(1)
    content = r.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    # Strip markdown code fences (common with Gemini)
    fence = chr(96) * 3
    content = re.sub(r'^\s*' + fence + r'(?:json)?\s*', '', content)
    content = re.sub(r'\s*' + fence + r'\s*$', '', content)
    content = content.strip()
    parsed = json.loads(content)
    print(json.dumps(parsed, indent=2))
except:
    sys.exit(1)
" > "$output_file" 2>/dev/null; then
            log "fallback" "Success via $provider"
            return 0
        fi
        log "fallback" "$provider failed, trying next..."
    done

    echo '{"error": "All API providers failed", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$output_file"
    return 1
}

# Write structured output with metadata wrapper
write_output() {
    local dept="$1"
    local content="$2"
    local output_file="$3"
    local method="${4:-opencode}"

    export _WRITE_DEPT="$dept"
    export _WRITE_CONTENT="$content"
    export _WRITE_METHOD="$method"

    python3 -c "
import json, os
from datetime import datetime, timezone

content = os.environ.get('_WRITE_CONTENT', '{}')
dept = os.environ.get('_WRITE_DEPT', 'unknown')
method = os.environ.get('_WRITE_METHOD', 'unknown')

try:
    parsed = json.loads(content)
except:
    parsed = {'raw_output': content[:5000]}

result = {
    'department': dept,
    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'method': method,
    'version': '1.0',
    'data': parsed
}
print(json.dumps(result, indent=2))
" > "$output_file"
}

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$1] $2" >&2
}
