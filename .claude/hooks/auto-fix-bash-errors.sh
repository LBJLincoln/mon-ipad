#!/bin/bash
# AUTO-FIX BASH ERRORS FOR RESEARCH/EVOLUTION AGENTS
# Deployed: 2026-03-28 | Patterns: timeout, import, OOM, Kaggle, git, HF, Supabase

INPUT=$(cat)
STDERR=$(echo "$INPUT" | jq -r '.tool_output.stderr // ""' 2>/dev/null)

# PATTERN 1: Network timeout → retry with backoff
if echo "$STDERR" | grep -qiE "(timeout|connection reset|504|503)"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "Network timeout — wait 5s then retry with increased timeout."}}'
  exit 0
fi

# PATTERN 2: Python import error → install dependency
if echo "$STDERR" | grep -qE "ModuleNotFoundError|ImportError"; then
  MODULE=$(echo "$STDERR" | grep -oP "No module named '\K[^']+")
  echo "{\"hookSpecificOutput\": {\"hookEventName\": \"PostToolUseFailure\", \"additionalContext\": \"Missing module '$MODULE' — run: pip3 install $MODULE\"}}"
  exit 0
fi

# PATTERN 3: Out of memory → reduce scope
if echo "$STDERR" | grep -qiE "(MemoryError|out of memory|CUDA out of memory|Cannot allocate)"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "OOM — reduce MAX_FEATURES to 150, subsample to 5000 games, use 2-fold CV."}}'
  exit 0
fi

# PATTERN 4: Kaggle session died
if echo "$STDERR" | grep -qiE "kaggle.*timeout|session disconnected|quota exceeded"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "Kaggle GPU session lost. Wait 1hr or switch to Modal. Reduce to 3 models + 5000 games."}}'
  exit 0
fi

# PATTERN 5: Git conflict
if echo "$STDERR" | grep -qiE "merge conflict|CONFLICT|failed to push"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "Git conflict — run: git stash && git pull --rebase && git stash pop"}}'
  exit 0
fi

# PATTERN 6: HF Space permission
if echo "$STDERR" | grep -qiE "permission denied.*hf|readonly|remote rejected"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "HF Space read-only — use: git subtree push --prefix=hf-space"}}'
  exit 0
fi

# PATTERN 7: Supabase down
if echo "$STDERR" | grep -qiE "supabase.*connection|pooler.*offline|402|tenant.*not found"; then
  echo '{"hookSpecificOutput": {"hookEventName": "PostToolUseFailure", "additionalContext": "Supabase offline — primary paused (402). Use local JSON cache in data/nba-agent/."}}'
  exit 0
fi

exit 0
