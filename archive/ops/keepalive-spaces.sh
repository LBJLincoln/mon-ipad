#!/bin/bash
# Keepalive ping for HF Spaces — prevents auto-sleep on free tier
# Cron: */30 * * * * /home/termius/mon-ipad/scripts/keepalive-spaces.sh --cron

SPACES=(
  "https://lbjlincoln-nomos-rag-engine.hf.space"
  "https://lbjlincoln-nomos-rag-engine-3.hf.space"
  "https://lbjlincoln-nomos-rag-engine-5.hf.space"
  "https://lbjlincoln-nomos-rag-engine-7.hf.space"
  "https://lbjlincoln-nomos-rag-engine-9.hf.space"
  "https://lbjlincoln-nomos-embeddings-api.hf.space/health"
  "https://lbjlincoln-nomos-docling-api.hf.space/health"
)

for url in "${SPACES[@]}"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url")
  name=$(echo "$url" | sed 's|https://lbjlincoln-||;s|\.hf\.space.*||')
  if [ "$1" != "--cron" ]; then
    echo "$name: HTTP $code"
  fi
  if [ "$code" = "000" ] || [ "$code" = "502" ] || [ "$code" = "503" ]; then
    echo "$(date -Iseconds) WARN: $name returned $code" >> /tmp/keepalive-spaces.log
  fi
done
