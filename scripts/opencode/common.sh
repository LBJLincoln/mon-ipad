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
    local model="${2:-claude-sonnet-4-20250514}"
    local max_tokens="${3:-4000}"

    # Determine provider and model from available keys
    local provider="anthropic"
    local actual_model="$model"

    if [ -n "$ANTHROPIC_API_KEY" ]; then
        provider="anthropic"
    elif [ -n "$OPENROUTER_API_KEY" ]; then
        provider="openrouter"
        actual_model="anthropic/claude-sonnet-4-20250514"
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

    # Try OpenRouter first (has multiple model keys)
    local api_key="${OPENROUTER_API_KEY:-}"
    local api_url="https://openrouter.ai/api/v1/chat/completions"
    local model="anthropic/claude-sonnet-4-20250514"

    if [ -z "$api_key" ]; then
        # Try OpenAI
        api_key="${OPENAI_API_KEY:-}"
        api_url="https://api.openai.com/v1/chat/completions"
        model="gpt-4o-mini"
    fi

    if [ -z "$api_key" ]; then
        echo '{"error": "No API keys available for fallback", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$output_file"
        return 1
    fi

    local response
    response=$(curl -fsSL "$api_url" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $api_key" \
        -d "$(python3 -c "
import json, sys
prompt = '''$prompt'''
payload = {
    'model': '$model',
    'max_tokens': 2000,
    'messages': [{'role': 'user', 'content': prompt}],
    'response_format': {'type': 'json_object'}
}
print(json.dumps(payload))
")" \
        --max-time 120 \
        2>/dev/null)

    if [ $? -eq 0 ]; then
        echo "$response" | python3 -c "
import json, sys
try:
    r = json.load(sys.stdin)
    content = r.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    # Validate it's JSON
    parsed = json.loads(content)
    print(json.dumps(parsed, indent=2))
except Exception as e:
    print(json.dumps({'error': str(e), 'raw': r if 'r' in dir() else 'parse_failed'}))
" > "$output_file"
    else
        echo '{"error": "API call failed", "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > "$output_file"
        return 1
    fi
}

# Write structured output with metadata wrapper
write_output() {
    local dept="$1"
    local content="$2"
    local output_file="$3"
    local method="${4:-opencode}"

    python3 -c "
import json, sys
from datetime import datetime, timezone

content = '''$content'''
try:
    parsed = json.loads(content)
except:
    parsed = {'raw_output': content}

result = {
    'department': '$dept',
    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'method': '$method',
    'version': '1.0',
    'data': parsed
}
print(json.dumps(result, indent=2))
" > "$output_file"
}

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [$1] $2" >&2
}
