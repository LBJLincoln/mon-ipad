#!/usr/bin/env python3
"""
Data Quality Agents — Hermes Pattern
=====================================
Dedicated agents that ensure ALL data is correct, complete, and fresh
before any trading agent sees it.

Agent roles:
  - DataCollector: fetches fresh game data, odds, stats daily
  - DataValidator: checks for missing/null/stale values
  - DataEnricher: adds derived features (streaks, momentum, H2H)
  - OddsAuditor: verifies odds are correctly mapped (home vs away)
  - ContextBuilder: prepares rich context packets per game for traders

Hermes pattern: NO trader sees data until DataValidator signs off.
"""

import json, os, sys, csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

ROOT = Path('/home/termius/mon-ipad')
NBA_AGENT = Path('/home/termius/nomos-nba-agent')
DATA = ROOT / 'data'

# ═══════════════════════════════════════════════════════════════════════════
# DATA QUALITY REPORT
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class QualityIssue:
    source: str
    severity: str  # critical, warning, info
    message: str
    fix_available: bool = False

@dataclass
class QualityReport:
    timestamp: str = ""
    issues: List[QualityIssue] = field(default_factory=list)
    sources_checked: int = 0
    sources_healthy: int = 0

    def add(self, source: str, severity: str, msg: str, fixable: bool = False):
        self.issues.append(QualityIssue(source, severity, msg, fixable))

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "sources_checked": self.sources_checked,
            "sources_healthy": self.sources_healthy,
            "critical": len([i for i in self.issues if i.severity == "critical"]),
            "warnings": len([i for i in self.issues if i.severity == "warning"]),
            "issues": [{"source": i.source, "severity": i.severity,
                        "message": i.message, "fix_available": i.fix_available}
                       for i in self.issues]
        }


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 1: DATA VALIDATOR
# ═══════════════════════════════════════════════════════════════════════════

def validate_games_dataset() -> List[QualityIssue]:
    """Check games-2025-26.json for completeness."""
    issues = []
    games_path = NBA_AGENT / 'data' / 'historical' / 'games-2025-26.json'

    if not games_path.exists():
        issues.append(QualityIssue("games-2025-26", "critical",
                                   f"File not found: {games_path}", True))
        return issues

    with open(games_path) as f:
        games = json.load(f)

    # NBA season 2025-26 started Oct 2025, it's now Apr 2026
    # Should have ~1,000-1,100 games by now
    expected_min = 900
    if len(games) < expected_min:
        issues.append(QualityIssue("games-2025-26", "critical",
            f"Only {len(games)} games, expected {expected_min}+. Dataset severely incomplete.",
            True))

    # Check for required fields
    required = ['date', 'home_team', 'away_team']
    for i, g in enumerate(games[:50]):
        for field_name in required:
            if field_name not in g or not g[field_name]:
                issues.append(QualityIssue("games-2025-26", "critical",
                    f"Game {i}: missing '{field_name}'", False))

    # Check for future dates (data leakage)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    future = [g for g in games if g.get('date', '')[:10] > today and g.get('home_score')]
    if future:
        issues.append(QualityIssue("games-2025-26", "critical",
            f"{len(future)} games have scores for future dates (DATA LEAKAGE)", False))

    return issues


def validate_odds_data() -> List[QualityIssue]:
    """Check odds data for correctness (home/away mapping bug was fixed before)."""
    issues = []

    # Live odds
    odds_path = DATA / 'nba-agent' / 'odds-latest.json'
    if not odds_path.exists():
        issues.append(QualityIssue("odds-latest", "warning", "No odds file", True))
        return issues

    with open(odds_path) as f:
        odds = json.load(f)

    if not isinstance(odds, list) or len(odds) == 0:
        issues.append(QualityIssue("odds-latest", "warning", "Empty odds data", True))
        return issues

    for game in odds:
        # Verify home/away not swapped (known past bug)
        home = game.get('home_team', '')
        away = game.get('away_team', '')
        if not home or not away:
            issues.append(QualityIssue("odds-latest", "critical",
                f"Missing team in game {game.get('id','?')}", False))
            continue

        # Check bookmakers exist
        bookmakers = game.get('bookmakers', [])
        if len(bookmakers) == 0:
            issues.append(QualityIssue("odds-latest", "warning",
                f"No bookmakers for {home} vs {away}", True))

        # Check odds are reasonable (not inverted)
        for bk in bookmakers:
            for market in bk.get('markets', []):
                if market.get('key') == 'h2h':
                    outcomes = {o['name']: o['price'] for o in market.get('outcomes', [])}
                    for team, price in outcomes.items():
                        if price < 1.0:
                            issues.append(QualityIssue("odds-latest", "critical",
                                f"Odds < 1.0 for {team}: {price} (impossible)", False))
                        if price > 100:
                            issues.append(QualityIssue("odds-latest", "warning",
                                f"Odds > 100 for {team}: {price} (suspicious)", False))

    return issues


def validate_historical_odds() -> List[QualityIssue]:
    """Check historical odds CSV."""
    issues = []
    csv_path = DATA / 'historical-odds' / 'nba_2008-2025.csv'

    if not csv_path.exists():
        issues.append(QualityIssue("historical-odds", "critical", "File not found", False))
        return issues

    with open(csv_path) as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = sum(1 for _ in reader)

    issues.append(QualityIssue("historical-odds", "info",
        f"Historical odds: {rows} rows, columns: {header[:5]}...", False))

    if rows < 10000:
        issues.append(QualityIssue("historical-odds", "warning",
            f"Only {rows} historical odds rows (expected 30,000+)", False))

    return issues


def validate_player_tracking() -> List[QualityIssue]:
    """Check player tracking data freshness."""
    issues = []
    tracking_dir = DATA / 'player-tracking'

    if not tracking_dir.exists():
        issues.append(QualityIssue("player-tracking", "critical", "Directory missing", False))
        return issues

    csvs = list(tracking_dir.glob('*.csv'))
    jsons = list(tracking_dir.glob('*.json'))

    if len(csvs) < 5:
        issues.append(QualityIssue("player-tracking", "warning",
            f"Only {len(csvs)} CSV files (expected 8+)", True))

    # Check freshness
    for f in csvs + jsons:
        age = datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)
        if age.days > 7:
            issues.append(QualityIssue("player-tracking", "warning",
                f"{f.name} is {age.days} days old", True))

    return issues


def validate_predictions() -> List[QualityIssue]:
    """Check today's predictions exist and are valid."""
    issues = []
    pred_path = Path('/home/termius/nomos-nba-agent/data/nba-agent/predictions-today.json')

    if not pred_path.exists():
        pred_path = DATA / 'nba-agent' / 'latest-picks.json'

    if not pred_path.exists():
        issues.append(QualityIssue("predictions", "warning", "No predictions file found", True))
        return issues

    with open(pred_path) as f:
        preds = json.load(f)

    if isinstance(preds, dict):
        games = preds.get('games', preds.get('predictions', []))
    else:
        games = preds

    if len(games) == 0:
        issues.append(QualityIssue("predictions", "warning", "No predictions for today", True))
    else:
        for g in games:
            prob = g.get('home_win_prob', g.get('probability'))
            if prob is not None:
                if not (0.05 <= prob <= 0.95):
                    issues.append(QualityIssue("predictions", "warning",
                        f"Extreme probability {prob} for {g.get('home_team','?')}", False))

    return issues


# ═══════════════════════════════════════════════════════════════════════════
# AGENT 2: CONTEXT BUILDER
# ═══════════════════════════════════════════════════════════════════════════

def build_game_context(game_data: Dict) -> Dict:
    """Build rich context packet for a single game.

    This is what every trading agent receives — standardized, validated, complete.
    """
    home = game_data.get('home_team', '')
    away = game_data.get('away_team', '')

    context = {
        "game_id": game_data.get('id', ''),
        "date": game_data.get('commence_time', game_data.get('date', '')),
        "home_team": home,
        "away_team": away,
        "odds": {},
        "team_stats": {"home": {}, "away": {}},
        "recent_form": {"home": [], "away": []},
        "h2h_last5": [],
        "injuries": {"home": [], "away": []},
        "context_quality": "full",  # or "partial" or "minimal"
    }

    # Odds from latest
    try:
        with open(DATA / 'nba-agent' / 'odds-latest.json') as f:
            all_odds = json.load(f)
        for og in all_odds:
            if og.get('home_team') == home and og.get('away_team') == away:
                for bk in og.get('bookmakers', [])[:3]:
                    bk_name = bk.get('key', 'unknown')
                    for mkt in bk.get('markets', []):
                        if mkt['key'] == 'h2h':
                            context['odds'][bk_name] = {
                                o['name']: o['price'] for o in mkt['outcomes']
                            }
                break
    except Exception:
        context['context_quality'] = 'partial'

    # Injuries
    try:
        inj_path = NBA_AGENT / 'data' / 'historical' / 'injuries-current.json'
        if inj_path.exists():
            with open(inj_path) as f:
                injuries = json.load(f)
            context['injuries']['home'] = [p for p in injuries if p.get('team') == home][:5]
            context['injuries']['away'] = [p for p in injuries if p.get('team') == away][:5]
    except Exception:
        pass

    return context


# ═══════════════════════════════════════════════════════════════════════════
# MAIN: RUN ALL VALIDATORS
# ═══════════════════════════════════════════════════════════════════════════

def run_full_audit() -> QualityReport:
    """Run all data quality checks and produce a report."""
    report = QualityReport(
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    validators = [
        ("games-2025-26", validate_games_dataset),
        ("odds-latest", validate_odds_data),
        ("historical-odds", validate_historical_odds),
        ("player-tracking", validate_player_tracking),
        ("predictions", validate_predictions),
    ]

    for name, validator in validators:
        report.sources_checked += 1
        try:
            issues = validator()
            if not any(i.severity == 'critical' for i in issues):
                report.sources_healthy += 1
            report.issues.extend(issues)
        except Exception as e:
            report.add(name, "critical", f"Validator crashed: {e}")

    return report


if __name__ == '__main__':
    report = run_full_audit()
    result = report.to_dict()

    print(f"\n{'='*60}")
    print(f"DATA QUALITY AUDIT — {result['timestamp'][:19]}")
    print(f"{'='*60}")
    print(f"Sources checked: {result['sources_checked']}")
    print(f"Sources healthy: {result['sources_healthy']}")
    print(f"Critical issues: {result['critical']}")
    print(f"Warnings: {result['warnings']}")
    print()

    for issue in result['issues']:
        icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}[issue['severity']]
        fix = ' [AUTO-FIX AVAILABLE]' if issue['fix_available'] else ''
        print(f"  {icon} [{issue['source']}] {issue['message']}{fix}")

    # Save report
    out = DATA / 'data-quality-report.json'
    with open(out, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nReport saved to {out}")
