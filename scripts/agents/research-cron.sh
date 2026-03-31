#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# NOMOS42 RESEARCH AGENTS (R1-R4) — Automated Literature Scanner
# Runs every 12h (6:00 + 18:00 UTC)
# Scans ArXiv + GitHub for NBA prediction / sports ML research
# Alerts via Telegram on breakthrough papers/repos
# ═══════════════════════════════════════════════════════════════

set -euo pipefail
export PATH="$PATH:/home/termius/.local/bin"
MON_DIR="/home/termius/mon-ipad"
RESEARCH_DIR="$MON_DIR/data/research"
LOG_DIR="$MON_DIR/logs/agents"
TODAY=$(date +%Y-%m-%d)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$RESEARCH_DIR" "$LOG_DIR"

# Source env for tokens
if [ -f "$MON_DIR/.env.local" ]; then
    set -a
    source "$MON_DIR/.env.local"
    set +a
fi

LOGFILE="$LOG_DIR/research-cron-$TODAY.log"

log() { echo "[$TIMESTAMP] $1" | tee -a "$LOGFILE"; }

send_telegram() {
    local msg="$1"
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -H 'Content-Type: application/json' \
            -d "{\"chat_id\":\"${ADMIN_TELEGRAM_ID:-6582544948}\",\"text\":\"${msg}\",\"parse_mode\":\"HTML\"}" \
            > /dev/null 2>&1 || true
    fi
}

log "═══ RESEARCH SCAN START ═══"

# ─── R1: ArXiv Scan ──────────────────────────────────────────
log "[R1] Scanning ArXiv for NBA prediction / sports ML papers..."

ARXIV_URL="http://export.arxiv.org/api/query?search_query=all:NBA+prediction+OR+all:sports+betting+machine+learning+OR+all:Brier+score+calibration&sortBy=submittedDate&sortOrder=descending&max_results=5"
ARXIV_XML=$(curl -sf --max-time 30 "$ARXIV_URL" 2>/dev/null) || ARXIV_XML=""

if [ -n "$ARXIV_XML" ]; then
    python3 -c "
import xml.etree.ElementTree as ET
import json, sys, re

xml_data = sys.stdin.read()
ns = {'atom': 'http://www.w3.org/2005/Atom'}
root = ET.fromstring(xml_data)

papers = []
for entry in root.findall('atom:entry', ns):
    title = entry.find('atom:title', ns)
    summary = entry.find('atom:summary', ns)
    published = entry.find('atom:published', ns)
    link = entry.find('atom:id', ns)
    authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]

    paper = {
        'title': title.text.strip().replace('\n', ' ') if title is not None else '',
        'summary': summary.text.strip()[:500].replace('\n', ' ') if summary is not None else '',
        'published': published.text if published is not None else '',
        'url': link.text if link is not None else '',
        'authors': authors
    }

    # Check for Brier score mentions with values < 0.20
    text = (paper['title'] + ' ' + paper['summary']).lower()
    brier_matches = re.findall(r'brier[^\d]*(\d+\.\d+)', text)
    paper['brier_scores'] = [float(b) for b in brier_matches if float(b) < 1.0]
    paper['has_breakthrough_brier'] = any(b < 0.20 for b in paper['brier_scores'])

    papers.append(paper)

result = {
    'scan_date': '$TODAY',
    'scan_time': '$TIMESTAMP',
    'query': 'NBA prediction OR sports betting ML OR Brier calibration',
    'paper_count': len(papers),
    'papers': papers,
    'breakthroughs': [p for p in papers if p['has_breakthrough_brier']]
}

json.dump(result, sys.stdout, indent=2)
" <<< "$ARXIV_XML" > "$RESEARCH_DIR/arxiv-scan-$TODAY.json" 2>>"$LOGFILE"

    PAPER_COUNT=$(python3 -c "import json; d=json.load(open('$RESEARCH_DIR/arxiv-scan-$TODAY.json')); print(d['paper_count'])" 2>/dev/null || echo "0")
    log "[R1] Found $PAPER_COUNT papers"

    # Check for Brier breakthroughs
    BREAKTHROUGHS=$(python3 -c "
import json
d = json.load(open('$RESEARCH_DIR/arxiv-scan-$TODAY.json'))
for p in d.get('breakthroughs', []):
    scores = ', '.join(f'{s:.4f}' for s in p['brier_scores'] if s < 0.20)
    print(f\"BREAKTHROUGH: {p['title'][:80]} | Brier: {scores} | {p['url']}\")
" 2>/dev/null || echo "")

    if [ -n "$BREAKTHROUGHS" ]; then
        log "[R1] BREAKTHROUGH DETECTED!"
        log "$BREAKTHROUGHS"
        send_telegram "🔬 <b>R1 RESEARCH ALERT</b>%0A%0AArXiv paper with Brier < 0.20 detected!%0A%0A${BREAKTHROUGHS}"
    fi
else
    log "[R1] ArXiv API unreachable, skipping"
    echo '{"scan_date":"'"$TODAY"'","error":"API unreachable","papers":[]}' > "$RESEARCH_DIR/arxiv-scan-$TODAY.json"
fi

# ─── R2: GitHub Repo Scan ────────────────────────────────────
log "[R2] Scanning GitHub for NBA prediction repos..."

GITHUB_JSON=$(curl -sf --max-time 30 \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/search/repositories?q=NBA+prediction+machine+learning&sort=updated&order=desc&per_page=5" \
    2>/dev/null) || GITHUB_JSON=""

if [ -n "$GITHUB_JSON" ]; then
    python3 -c "
import json, sys
from datetime import datetime, timedelta

data = json.loads(sys.stdin.read())
repos = []
alerts = []
now = datetime.utcnow()
week_ago = now - timedelta(days=7)

for item in data.get('items', []):
    repo = {
        'name': item.get('full_name', ''),
        'description': (item.get('description') or '')[:200],
        'stars': item.get('stargazers_count', 0),
        'forks': item.get('forks_count', 0),
        'language': item.get('language', ''),
        'updated_at': item.get('updated_at', ''),
        'url': item.get('html_url', ''),
        'topics': item.get('topics', [])
    }

    # Check: >50 stars AND updated in last 7 days
    try:
        updated = datetime.strptime(repo['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
        repo['recently_active'] = updated > week_ago
    except:
        repo['recently_active'] = False

    repo['is_notable'] = repo['stars'] > 50 and repo['recently_active']
    if repo['is_notable']:
        alerts.append(repo)

    repos.append(repo)

result = {
    'scan_date': '$TODAY',
    'scan_time': '$TIMESTAMP',
    'query': 'NBA prediction machine learning',
    'repo_count': len(repos),
    'repos': repos,
    'notable_repos': alerts
}

json.dump(result, sys.stdout, indent=2)
" <<< "$GITHUB_JSON" > "$RESEARCH_DIR/github-scan-$TODAY.json" 2>>"$LOGFILE"

    REPO_COUNT=$(python3 -c "import json; d=json.load(open('$RESEARCH_DIR/github-scan-$TODAY.json')); print(d['repo_count'])" 2>/dev/null || echo "0")
    log "[R2] Found $REPO_COUNT repos"

    # Check for notable repos
    NOTABLE=$(python3 -c "
import json
d = json.load(open('$RESEARCH_DIR/github-scan-$TODAY.json'))
for r in d.get('notable_repos', []):
    print(f\"NOTABLE: {r['name']} | {r['stars']} stars | {r['language']} | {r['url']}\")
" 2>/dev/null || echo "")

    if [ -n "$NOTABLE" ]; then
        log "[R2] NOTABLE REPO DETECTED!"
        log "$NOTABLE"
        send_telegram "🔬 <b>R2 RESEARCH ALERT</b>%0A%0AActive NBA ML repo (>50 stars, updated this week):%0A%0A${NOTABLE}"
    fi
else
    log "[R2] GitHub API unreachable, skipping"
    echo '{"scan_date":"'"$TODAY"'","error":"API unreachable","repos":[]}' > "$RESEARCH_DIR/github-scan-$TODAY.json"
fi

# ─── R3: Additional ArXiv queries (calibration + ensemble) ───
log "[R3] Scanning ArXiv for calibration & ensemble methods..."

ARXIV_URL2="http://export.arxiv.org/api/query?search_query=all:probability+calibration+neural+network+OR+all:ensemble+sports+prediction&sortBy=submittedDate&sortOrder=descending&max_results=5"
ARXIV_XML2=$(curl -sf --max-time 30 "$ARXIV_URL2" 2>/dev/null) || ARXIV_XML2=""

if [ -n "$ARXIV_XML2" ]; then
    python3 -c "
import xml.etree.ElementTree as ET
import json, sys, re

xml_data = sys.stdin.read()
ns = {'atom': 'http://www.w3.org/2005/Atom'}
root = ET.fromstring(xml_data)

papers = []
for entry in root.findall('atom:entry', ns):
    title = entry.find('atom:title', ns)
    summary = entry.find('atom:summary', ns)
    published = entry.find('atom:published', ns)
    link = entry.find('atom:id', ns)
    authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]

    paper = {
        'title': title.text.strip().replace('\n', ' ') if title is not None else '',
        'summary': summary.text.strip()[:500].replace('\n', ' ') if summary is not None else '',
        'published': published.text if published is not None else '',
        'url': link.text if link is not None else '',
        'authors': authors
    }

    text = (paper['title'] + ' ' + paper['summary']).lower()
    brier_matches = re.findall(r'brier[^\d]*(\d+\.\d+)', text)
    paper['brier_scores'] = [float(b) for b in brier_matches if float(b) < 1.0]
    paper['has_breakthrough_brier'] = any(b < 0.20 for b in paper['brier_scores'])
    papers.append(paper)

result = {
    'scan_date': '$TODAY',
    'scan_time': '$TIMESTAMP',
    'query': 'probability calibration OR ensemble sports prediction',
    'paper_count': len(papers),
    'papers': papers,
    'breakthroughs': [p for p in papers if p['has_breakthrough_brier']]
}

json.dump(result, sys.stdout, indent=2)
" <<< "$ARXIV_XML2" > "$RESEARCH_DIR/arxiv-calibration-scan-$TODAY.json" 2>>"$LOGFILE"

    CAL_COUNT=$(python3 -c "import json; d=json.load(open('$RESEARCH_DIR/arxiv-calibration-scan-$TODAY.json')); print(d['paper_count'])" 2>/dev/null || echo "0")
    log "[R3] Found $CAL_COUNT calibration/ensemble papers"

    # Check breakthroughs from R3 too
    BREAKTHROUGHS3=$(python3 -c "
import json
d = json.load(open('$RESEARCH_DIR/arxiv-calibration-scan-$TODAY.json'))
for p in d.get('breakthroughs', []):
    scores = ', '.join(f'{s:.4f}' for s in p['brier_scores'] if s < 0.20)
    print(f\"BREAKTHROUGH: {p['title'][:80]} | Brier: {scores} | {p['url']}\")
" 2>/dev/null || echo "")

    if [ -n "$BREAKTHROUGHS3" ]; then
        log "[R3] BREAKTHROUGH DETECTED!"
        send_telegram "🔬 <b>R3 CALIBRATION ALERT</b>%0A%0ACalibration paper with Brier < 0.20:%0A%0A${BREAKTHROUGHS3}"
    fi
else
    log "[R3] ArXiv calibration query unreachable, skipping"
fi

# ─── R4: GitHub trending (sports analytics) ──────────────────
log "[R4] Scanning GitHub for sports analytics / betting repos..."

GITHUB_JSON2=$(curl -sf --max-time 30 \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/search/repositories?q=sports+betting+prediction+python&sort=stars&order=desc&per_page=5" \
    2>/dev/null) || GITHUB_JSON2=""

if [ -n "$GITHUB_JSON2" ]; then
    python3 -c "
import json, sys
from datetime import datetime, timedelta

data = json.loads(sys.stdin.read())
repos = []
now = datetime.utcnow()
week_ago = now - timedelta(days=7)

for item in data.get('items', []):
    repo = {
        'name': item.get('full_name', ''),
        'description': (item.get('description') or '')[:200],
        'stars': item.get('stargazers_count', 0),
        'forks': item.get('forks_count', 0),
        'language': item.get('language', ''),
        'updated_at': item.get('updated_at', ''),
        'url': item.get('html_url', ''),
        'topics': item.get('topics', [])
    }

    try:
        updated = datetime.strptime(repo['updated_at'], '%Y-%m-%dT%H:%M:%SZ')
        repo['recently_active'] = updated > week_ago
    except:
        repo['recently_active'] = False

    repo['is_notable'] = repo['stars'] > 50 and repo['recently_active']
    repos.append(repo)

notable = [r for r in repos if r['is_notable']]

result = {
    'scan_date': '$TODAY',
    'scan_time': '$TIMESTAMP',
    'query': 'sports betting prediction python',
    'repo_count': len(repos),
    'repos': repos,
    'notable_repos': notable
}

json.dump(result, sys.stdout, indent=2)
" <<< "$GITHUB_JSON2" > "$RESEARCH_DIR/github-betting-scan-$TODAY.json" 2>>"$LOGFILE"

    BET_COUNT=$(python3 -c "import json; d=json.load(open('$RESEARCH_DIR/github-betting-scan-$TODAY.json')); print(d['repo_count'])" 2>/dev/null || echo "0")
    log "[R4] Found $BET_COUNT sports betting repos"

    NOTABLE4=$(python3 -c "
import json
d = json.load(open('$RESEARCH_DIR/github-betting-scan-$TODAY.json'))
for r in d.get('notable_repos', []):
    print(f\"NOTABLE: {r['name']} | {r['stars']} stars | {r['language']} | {r['url']}\")
" 2>/dev/null || echo "")

    if [ -n "$NOTABLE4" ]; then
        log "[R4] NOTABLE REPO DETECTED!"
        send_telegram "🔬 <b>R4 BETTING REPO ALERT</b>%0A%0AActive sports betting repo (>50 stars):%0A%0A${NOTABLE4}"
    fi
else
    log "[R4] GitHub betting query unreachable, skipping"
fi

# ─── Summary ─────────────────────────────────────────────────
log "═══ RESEARCH SCAN COMPLETE ═══"
log "  ArXiv NBA/sports: ${PAPER_COUNT:-0} papers"
log "  ArXiv calibration: ${CAL_COUNT:-0} papers"
log "  GitHub NBA ML: ${REPO_COUNT:-0} repos"
log "  GitHub betting: ${BET_COUNT:-0} repos"

# Trigger weekly digest on Mondays
DOW=$(date +%u)
if [ "$DOW" -eq 1 ]; then
    log "[DIGEST] Monday — generating weekly research digest..."
    python3 "$MON_DIR/scripts/agents/research-digest.py" >> "$LOGFILE" 2>&1 || log "[DIGEST] Failed"
fi
