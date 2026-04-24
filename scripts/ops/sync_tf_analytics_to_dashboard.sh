#!/bin/bash
# sync_tf_analytics_to_dashboard.sh -- mirror data/tf-analytics/ into
# nomos-dashboard/public/tf-analytics/ and push to dashboard repo.
#
# Why: the dashboard deploy lives on Vercel with no private-repo access.
# GITHUB_TOKEN setup on Vercel has failed repeatedly. So we ship the data
# as static assets in the dashboard repo itself -- no external auth needed,
# just an hourly commit-and-push.
#
# Idempotent: rsync detects no-change, git commit exits 0 on nothing-to-commit.
#
# Cron:  40 * * * * /home/termius/mon-ipad/scripts/ops/sync_tf_analytics_to_dashboard.sh

set -euo pipefail

SRC="/home/termius/mon-ipad/data/tf-analytics"
DEST="/home/termius/nomos-dashboard/public/tf-analytics"
DASH_REPO="/home/termius/nomos-dashboard"
LOG_TAG="sync_tf_analytics"

if [ ! -d "$SRC" ]; then
  echo "[$LOG_TAG] src missing: $SRC"
  exit 1
fi
if [ ! -d "$DASH_REPO/.git" ]; then
  echo "[$LOG_TAG] dashboard repo missing: $DASH_REPO"
  exit 1
fi

mkdir -p "$DEST"

# Mirror JSON + MD files (rsync not installed). Clear DEST of stale data,
# then cp -r fresh from SRC. Also mirror audit MD files (scorecard-latest,
# rigorous-latest, cross-llm-latest, digest-*) so dashboard pages can render them.
find "$DEST" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.md' \) -delete 2>/dev/null || true
mkdir -p "$DEST"
cp -r "$SRC"/. "$DEST/" 2>/dev/null || true
# Also copy audit MD files into a subdirectory
mkdir -p "$DEST/audit"
for f in scorecard-latest.md rigorous-latest.md cross-llm-latest.md digest-latest.md trajectory-latest.md; do
  src="/home/termius/mon-ipad/data/audit/$f"
  if [ -f "$src" ]; then
    cp "$src" "$DEST/audit/$f"
  fi
done
# Strip cron.log and other non-allowed noise
find "$DEST" -type f ! \( -name '*.json' -o -name '*.jsonl' -o -name '*.md' \) -delete 2>/dev/null || true

# Build the manifest Vercel reads server-side.
cd "$DEST"
python3 - <<'PY'
import os, json
out = {"summary": "summary.json" if os.path.exists("summary.json") else None}
for tf in ("nba","pol","itf","pqtf"):
    if os.path.isdir(tf):
        out[tf] = sorted(f for f in os.listdir(tf) if f.startswith("day-") and f.endswith(".json"))
    else:
        out[tf] = []
with open("manifest.json","w") as f:
    json.dump(out, f, indent=2)
PY

cd "$DASH_REPO"

# Commit + push only if something changed.
git add public/tf-analytics
if git diff --cached --quiet; then
  echo "[$LOG_TAG] no change"
  exit 0
fi

TS=$(date -u +%Y-%m-%dT%H:%MZ)
NBA=$(ls public/tf-analytics/nba 2>/dev/null | wc -l)
POL=$(ls public/tf-analytics/pol 2>/dev/null | wc -l)
ITF=$(ls public/tf-analytics/itf 2>/dev/null | wc -l)
PQTF=$(ls public/tf-analytics/pqtf 2>/dev/null | wc -l)

git commit -m "tf-analytics: hourly sync ${TS} (nba=${NBA} pol=${POL} itf=${ITF} pqtf=${PQTF})" --no-verify >/dev/null

for attempt in 1 2 3; do
  if git push origin main 2>&1 | tail -2; then
    echo "[$LOG_TAG] push ok (attempt $attempt)"
    exit 0
  fi
  git pull --rebase --autostash origin main 2>&1 | tail -2 || exit 4
done

echo "[$LOG_TAG] push FAILED after 3 attempts"
exit 5
