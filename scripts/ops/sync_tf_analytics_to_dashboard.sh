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
for f in scorecard-latest.md rigorous-latest.md cross-llm-latest.md digest-latest.md trajectory-latest.md scientific-scorecard-latest.md scientific-scorecard-latest.json rigorous-latest.json scorecard-latest.json; do
  src="/home/termius/mon-ipad/data/audit/$f"
  if [ -f "$src" ]; then
    cp "$src" "$DEST/audit/$f"
  fi
done
# 2026-05-01 — dashboard-bundle.json is the lab-grade aggregate the new
# /nba + /political pages will fetch (CI bands, walk-forward time series,
# calibration buckets, trust signals). Emitted by tf_dashboard_bundle.py.
if [ -f "/home/termius/mon-ipad/data/tf-analytics/dashboard-bundle.json" ]; then
  cp "/home/termius/mon-ipad/data/tf-analytics/dashboard-bundle.json" "$DEST/dashboard-bundle.json"
fi
# 2026-04-25: ship the per-agent forensic deep-audit MDs to the dashboard so
# user can browse "why each odd was chosen" per-agent / per-game / cross-agent.
TODAY=$(date -u +%Y-%m-%d)
for tf in nba pol itf pqtf; do
  for kind in per-agent-deep per-game-deep per-agent-factual coverage-report; do
    src="/home/termius/mon-ipad/data/audit/${kind}-${tf}-${TODAY}.md"
    if [ -f "$src" ]; then
      cp "$src" "$DEST/audit/${kind}-${tf}-latest.md"
    fi
  done
done
# Failing-agents diagnostic + combined coverage JSON
for f in failing-agents-diagnostic-${TODAY}.md coverage-report-${TODAY}.json coverage-report-latest.json; do
  src="/home/termius/mon-ipad/data/audit/$f"
  if [ -f "$src" ]; then
    cp "$src" "$DEST/audit/$(basename "$f")"
  fi
done
# 2026-04-26 — day-context forensic (per-day full agent + engine context)
# Copies ALL day-context MDs + the index JSON consumed by /audit dropdown.
for f in /home/termius/mon-ipad/data/audit/day-context-nba-*.md; do
  if [ -f "$f" ]; then
    cp "$f" "$DEST/audit/$(basename "$f")"
  fi
done
if [ -f /home/termius/mon-ipad/data/audit/day-context-nba-index.json ]; then
  cp /home/termius/mon-ipad/data/audit/day-context-nba-index.json "$DEST/audit/"
fi
# Also write -latest.md aliases for files the dashboard expects under stable
# names (the audit page hard-codes failing-agents-diagnostic-latest.md).
diag_dated="/home/termius/mon-ipad/data/audit/failing-agents-diagnostic-${TODAY}.md"
if [ -f "$diag_dated" ]; then
  cp "$diag_dated" "$DEST/audit/failing-agents-diagnostic-latest.md"
fi
# Per-agent narrative trails (one file per agent per TF)
if [ -d "/home/termius/mon-ipad/data/audit/per-agent-deep" ]; then
  mkdir -p "$DEST/audit/per-agent-deep"
  cp -r /home/termius/mon-ipad/data/audit/per-agent-deep/. "$DEST/audit/per-agent-deep/" 2>/dev/null || true
fi
# 2026-04-28 — mirror dispatch-log.jsonl + arena/council-log to dashboard public/
# so /api/crew-activity + /api/arena/council-log have a public source. Vercel
# can't fetch private mon-ipad without a token; HF mirror was unreliable.
if [ -f "/home/termius/mon-ipad/data/ops/dispatch-log.jsonl" ]; then
  mkdir -p "$DEST/ops"
  cp /home/termius/mon-ipad/data/ops/dispatch-log.jsonl "$DEST/ops/dispatch-log.jsonl"
fi
if [ -d "/home/termius/mon-ipad/data/arena" ]; then
  mkdir -p "$DEST/arena"
  # only the small summary files the dashboard needs
  for f in /home/termius/mon-ipad/data/arena/council-log-*.json /home/termius/mon-ipad/data/arena/backfill-summary*.json; do
    [ -f "$f" ] && cp "$f" "$DEST/arena/" 2>/dev/null || true
  done
fi
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
