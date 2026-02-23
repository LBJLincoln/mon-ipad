# OpenRouter Key Rotation System

> Last updated: 2026-02-23T17:00:00+01:00

## Overview

Distributes OpenRouter API requests across 7 keys (3 accounts) to achieve ~140 req/min aggregate throughput instead of being limited to 20 req/min per single key.

## Rate Limit Math

```
Single key:    20 req/min
7 keys total: 140 req/min (7 × 20)
Efficiency:    7x throughput increase
```

## Setup

### 1. Environment Variables

Set up your keys in `.env.local`:

```bash
# Main account (Account 1)
OPENROUTER_API_KEY=sk-or-v1-xxxxx          # Main key
OPENROUTER_KEY_STANDARD=sk-or-v1-xxxxx    # Standard RAG pipeline
OPENROUTER_KEY_GRAPH=sk-or-v1-xxxxx       # Graph RAG pipeline

# Account 2
OPENROUTER_KEY_QUANTITATIVE=sk-or-v1-xxxxx  # Quantitative pipeline
OPENROUTER_KEY_ORCHESTRATOR=sk-or-v1-xxxxx  # Orchestrator pipeline

# Account 3
OPENROUTER_KEY_PME=sk-or-v1-xxxxx           # PME pipelines
OPENROUTER_KEY_ACCOUNT3=sk-or-v1-xxxxx      # Additional key
```

**Note**: The rotator will deduplicate keys automatically if the same key is set multiple times.

### 2. HF Space Secrets

For n8n workflows on HF Space, set these as Space secrets:

```bash
# Via HuggingFace Space Settings → Variables and Secrets
OPENROUTER_KEY_STANDARD=sk-or-v1-xxxxx
OPENROUTER_KEY_GRAPH=sk-or-v1-xxxxx
OPENROUTER_KEY_QUANTITATIVE=sk-or-v1-xxxxx
OPENROUTER_KEY_ORCHESTRATOR=sk-or-v1-xxxxx
OPENROUTER_KEY_PME=sk-or-v1-xxxxx
```

Then in workflow JSONs, use: `={{$env.OPENROUTER_KEY_STANDARD}}`

## Usage in Python Scripts

### Basic Usage

```python
from openrouter_key_rotation import get_rotator

# Initialize rotator (loads keys from environment)
rotator = get_rotator()

# Get next available key
api_key = rotator.get_next_key()

# Make your OpenRouter request
response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={...}
)

# Record usage after successful request
rotator.record_usage(api_key)
```

### Integration with Eval Scripts

```python
# In eval/quick-test.py, eval/iterative-eval.py, etc.

from openrouter_key_rotation import get_rotator

rotator = get_rotator()

def call_openrouter_llm(prompt: str, model: str) -> str:
    """Call OpenRouter with automatic key rotation."""
    key = rotator.get_next_key()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://nomos-ai.com",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    rotator.record_usage(key)
    return response.json()["choices"][0]["message"]["content"]
```

### Thread-Safe Usage

The rotator is thread-safe and can be used in parallel eval scripts:

```python
import concurrent.futures
from openrouter_key_rotation import get_rotator

rotator = get_rotator()

def process_question(question):
    key = rotator.get_next_key()
    # ... make request ...
    rotator.record_usage(key)
    return result

with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(process_question, questions)
```

## CLI Commands

### View Current Status

```bash
python3 scripts/openrouter-key-rotation.py --status
```

Output:
```
================================================================================
OpenRouter Key Rotation Status
================================================================================
Key                  Current    Total      Capacity   Usage %    Last Used
--------------------------------------------------------------------------------
sk-or-v1...abc       5          150        20         25.0%      2026-02-23 16:45:30
sk-or-v1...def       3          120        20         15.0%      2026-02-23 16:45:28
sk-or-v1...ghi       7          200        20         35.0%      2026-02-23 16:45:32
...
--------------------------------------------------------------------------------
TOTAL                15         470        140        10.7%
================================================================================
```

### Test Key Distribution

Simulate 100 requests to see how they're distributed:

```bash
python3 scripts/openrouter-key-rotation.py --test 100
```

### Reset Statistics

```bash
python3 scripts/openrouter-key-rotation.py --reset
```

## How It Works

### Key Selection Algorithm

1. **Load all keys** from environment variables at initialization
2. **Track usage** per key in a 60-second rolling window
3. **Select best key** based on:
   - Lowest current usage count (requests in last 60s)
   - Least recently used (tie-breaker)
4. **Record usage** after each request
5. **Auto-cleanup** old timestamps outside the 60s window

### Rate Limit Protection

- Warns when a key reaches 80% capacity (16/20 req/min)
- Blocks and waits if ALL keys hit rate limit
- Automatically resumes after cooldown period

### Thread Safety

- Uses `threading.Lock()` for concurrent access
- Safe for parallel eval scripts (e.g., `run-eval-parallel.py`)

## Performance Impact

### Before (single key)

```
Pipeline: Standard RAG
Questions: 500
Time: ~25 minutes (20 req/min limit)
Bottleneck: Rate limit
```

### After (7 keys)

```
Pipeline: Standard RAG
Questions: 500
Time: ~3.6 minutes (140 req/min aggregate)
Bottleneck: n8n/pipeline processing
```

**Speedup**: ~7x faster for LLM-heavy workloads

## Integration Checklist

- [ ] Set all 7 keys in `.env.local` (VM)
- [ ] Set per-pipeline keys in HF Space secrets
- [ ] Import `get_rotator()` in eval scripts
- [ ] Replace hardcoded `OPENROUTER_API_KEY` with `rotator.get_next_key()`
- [ ] Call `rotator.record_usage(key)` after each request
- [ ] Test with `--test 100` to verify distribution
- [ ] Monitor with `--status` during eval runs

## Troubleshooting

### No keys found

```
ValueError: No OpenRouter keys found
```

**Fix**: Set at least one key in `.env.local`:
```bash
source .env.local  # Load environment
python3 scripts/openrouter-key-rotation.py --status
```

### All keys at rate limit

```
[KeyRotator] All keys at rate limit. Waiting 12.3s for cooldown...
```

**Normal behavior**: The rotator will automatically wait and retry. If this happens frequently, you're exceeding 140 req/min aggregate.

### Key not rotating

Check if you have duplicate keys:
```bash
python3 scripts/openrouter-key-rotation.py --status
```

The rotator deduplicates keys automatically. If you see fewer keys than expected, some env vars point to the same key.

## Future Enhancements

- [ ] Persist usage stats to disk for cross-session tracking
- [ ] Add Prometheus metrics export
- [ ] Support custom rate limits per key (paid tiers)
- [ ] Add key health monitoring (detect banned/invalid keys)
- [ ] Integrate with n8n workflow execution tracking

## References

- **Main implementation**: `/home/termius/mon-ipad/scripts/openrouter-key-rotation.py`
- **Integration guide**: This README
- **Env vars documentation**: `/home/termius/mon-ipad/technicals/infra/env-vars-exhaustive.md`
- **OpenRouter docs**: https://openrouter.ai/docs#rate-limits
