#!/usr/bin/env python3
"""
YouTube Feature Extractor for NBA Quant Research (Cycle 7)

Mines YouTube transcripts for specific NBA prediction features mentioned by
analytics channels. Extracts feature-relevant segments and generates proposals
for model improvement.

Usage:
    python3 scripts/youtube_feature_extractor.py --search "NBA analytics shot quality" --max 10
    python3 scripts/youtube_feature_extractor.py --channel UCzzz --feature-categories clutch,refs,market
    python3 scripts/youtube_feature_extractor.py --video dQw4w9WgXcQ --extract-features
"""

import argparse, json, os, sys, re, time, warnings, logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

warnings.filterwarnings("ignore")
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "youtube-transcripts"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Feature categories and associated keywords (Cycle 7)
FEATURE_CATEGORIES = {
    "clutch": {
        "keywords": ["clutch", "close game", "pressure", "final minutes", "ecc", "estimation of clutch competency"],
        "expected_features": 10,
        "category_num": 47
    },
    "refs": {
        "keywords": ["referee", "ref", "foul", "bias", "crew", "home favoritism", "technical foul", "l2m"],
        "expected_features": 12,
        "category_num": 48
    },
    "game_flow": {
        "keywords": ["game flow", "game script", "momentum", "halftime", "garbage time", "phase", "lead"],
        "expected_features": 8,
        "category_num": 49
    },
    "market_micro": {
        "keywords": ["sharp money", "steam", "line movement", "polymarket", "public betting", "clv", "vegas"],
        "expected_features": 14,
        "category_num": 50
    },
    "lineups": {
        "keywords": ["lineup", "rotation", "bench", "five-man", "depth chart", "continuity"],
        "expected_features": 10,
        "category_num": 51
    },
    "hustle": {
        "keywords": ["player tracking", "hustle", "deflection", "contested", "screen assist", "speed distance"],
        "expected_features": 12,
        "category_num": 52
    },
    "rest": {
        "keywords": ["rest", "back-to-back", "b2b", "fatigue", "travel", "altitude", "timezone"],
        "expected_features": 10,
        "category_num": 53
    },
    "shot_zones": {
        "keywords": ["shot location", "rim", "three-point", "mid-range", "paint", "zone", "xefg", "shot quality"],
        "expected_features": 8,
        "category_num": 54
    },
    "h2h": {
        "keywords": ["head-to-head", "h2h", "history", "matchup", "style clash", "pace delta"],
        "expected_features": 8,
        "category_num": 55
    },
    "season_phase": {
        "keywords": ["season phase", "playoff", "tanking", "playoff race", "playoff implications"],
        "expected_features": 8,
        "category_num": 56
    },
    "injuries": {
        "keywords": ["injury", "injured", "availability", "war", "minutes load", "workload", "health"],
        "expected_features": 10,
        "category_num": 57
    },
    "tempo": {
        "keywords": ["pace", "tempo", "transition", "fast break", "possession", "pace-adjusted"],
        "expected_features": 8,
        "category_num": 58
    },
    "calibration": {
        "keywords": ["calibration", "calibrated", "brier", "probability", "miscalibrated", "well-calibrated"],
        "expected_features": 6,
        "category_num": "meta"
    }
}


def get_youtube_service():
    """Build YouTube API client. Returns (service, method) or (None, None)."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("YOUTUBE_API_KEY")
    if api_key:
        try:
            from googleapiclient.discovery import build
            svc = build("youtube", "v3", developerKey=api_key)
            svc.videos().list(part="id", id="dQw4w9WgXcQ").execute()
            print("[OK] YouTube API via API key")
            return svc, "api_key"
        except Exception as e:
            print(f"[WARN] API key failed: {e}")

    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/youtube.readonly"]
        )
        svc = build("youtube", "v3", credentials=creds)
        svc.videos().list(part="id", id="dQw4w9WgXcQ").execute()
        print(f"[OK] YouTube API via gcloud ADC (project: {project})")
        return svc, "oauth"
    except Exception as e:
        print(f"[WARN] gcloud ADC: {e}")

    print("[INFO] No YouTube API. Transcript-only mode available.")
    return None, None


def fetch_transcript(video_id):
    """Fetch English transcript. Returns (text, segments) or (None, error_string)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=['en'])
        snippets = transcript.snippets if hasattr(transcript, 'snippets') else transcript
        segments = []
        for t in snippets:
            if hasattr(t, 'text'):
                segments.append({'text': t.text, 'start': getattr(t, 'start', 0),
                                 'duration': getattr(t, 'duration', 0)})
            elif isinstance(t, dict):
                segments.append(t)
        full_text = ' '.join(s.get('text', '') for s in segments)
        return full_text, segments
    except Exception as e:
        err = str(e).lower()
        if "disabled" in err or "no transcript" in err:
            return None, "No transcript available"
        if "not found" in err or "unavailable" in err:
            return None, "Video unavailable"
        return None, f"Transcript error: {e}"


def extract_feature_insights(transcript_text, title=""):
    """Extract feature-relevant segments from transcript."""
    insights = defaultdict(list)

    # Lowercase for matching
    blob = f"{title} {transcript_text}".lower()

    # Find mentions of each feature category
    for cat_name, cat_config in FEATURE_CATEGORIES.items():
        keywords = cat_config["keywords"]
        for kw in keywords:
            # Find all occurrences
            pattern = re.compile(f"([^.!?]*{re.escape(kw)}[^.!?]*[.!?])", re.IGNORECASE)
            matches = pattern.findall(blob)
            if matches:
                insights[cat_name].extend([m.strip() for m in matches[:2]])  # Top 2 mentions

    return insights


def score_feature_relevance(transcript_text, title=""):
    """Score relevance for each feature category."""
    scores = {}
    blob = f"{title} {transcript_text}".lower()

    for cat_name, cat_config in FEATURE_CATEGORIES.items():
        keywords = cat_config["keywords"]
        hit_count = sum(1 for kw in keywords if kw in blob)
        score = min(hit_count / len(keywords), 1.0)  # Fraction of keywords found
        scores[cat_name] = round(score, 3)

    return scores


def analyze_video(video_id, metadata=None):
    """Analyze video for feature insights."""
    meta = metadata or {}
    title = meta.get("title", "")
    description = meta.get("description", "")

    transcript_text, _ = fetch_transcript(video_id)
    if transcript_text is None:
        return None

    # Extract insights
    insights = extract_feature_insights(transcript_text, title)
    scores = score_feature_relevance(transcript_text, title)

    # Top categories
    top_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]

    record = {
        "video_id": video_id,
        "title": title,
        "channel": meta.get("channel", ""),
        "transcript_length": len(transcript_text),
        "feature_category_scores": scores,
        "top_categories": [{"category": c, "score": s} for c, s in top_cats],
        "sample_insights": {cat: insightlist[:1] for cat, insightlist in insights.items() if insightlist},
        "analyzed_at": datetime.utcnow().isoformat() + "Z"
    }

    return record


def generate_proposals(analyses):
    """Generate feature proposals from multiple video analyses."""
    if not analyses:
        return []

    # Aggregate category scores
    cat_scores = defaultdict(list)
    for a in analyses:
        if a and "feature_category_scores" in a:
            for cat, score in a["feature_category_scores"].items():
                cat_scores[cat].append(score)

    # Average scores
    avg_scores = {cat: sum(scores) / len(scores) for cat, scores in cat_scores.items()}

    proposals = []
    for cat_name in sorted(avg_scores.keys(), key=lambda x: avg_scores[x], reverse=True):
        cat_config = FEATURE_CATEGORIES[cat_name]
        score = avg_scores[cat_name]

        if score > 0.2:  # Only high-relevance categories
            proposals.append({
                "category": cat_name,
                "category_num": cat_config["category_num"],
                "relevance_score": round(score, 3),
                "expected_features": cat_config["expected_features"],
                "keywords_found": cat_config["keywords"][:3]
            })

    return proposals


def search_channels(search_queries=None):
    """Return list of recommended NBA analytics YouTube channels to explore."""
    channels = [
        {
            "name": "Thinking Basketball",
            "handle": "@thinkingbasketball",
            "url": "https://www.youtube.com/@thinkingbasketball",
            "focus": "Shot quality, lineup analysis, advanced metrics",
            "feature_categories": ["shot_zones", "lineups", "calibration"]
        },
        {
            "name": "Cleaning the Glass",
            "handle": "@cleaningtheglass",
            "url": "https://www.youtube.com/@cleaningtheglass",
            "focus": "Garbage time filters, situational defense, bench depth",
            "feature_categories": ["game_flow", "lineups", "hustle"]
        },
        {
            "name": "BBall Index",
            "handle": "@bballindex",
            "url": "https://www.youtube.com/@bballindex",
            "focus": "Advanced metrics, game flow, clutch dynamics",
            "feature_categories": ["clutch", "game_flow"]
        },
        {
            "name": "Half Court Hoops",
            "handle": "@HalfCourtHoops",
            "url": "https://www.youtube.com/@HalfCourtHoops",
            "focus": "Niche analytics, deep dives",
            "feature_categories": ["refs", "market_micro"]
        },
        {
            "name": "The Athletic / Seth Partnow",
            "handle": "@theathletic",
            "url": "https://www.youtube.com/@theathletic",
            "focus": "Player impact, injuries, Bayesian methods",
            "feature_categories": ["injuries", "h2h", "calibration"]
        }
    ]
    return channels


def main():
    parser = argparse.ArgumentParser(description="YouTube Feature Extractor for NBA Quant")
    parser.add_argument("--search", type=str, help="Search for videos on topic")
    parser.add_argument("--video", type=str, help="Analyze single video ID")
    parser.add_argument("--channels", action="store_true", help="List recommended NBA analytics channels")
    parser.add_argument("--max", type=int, default=10, help="Max videos")
    parser.add_argument("--output", type=str, default="proposals.json", help="Output file")
    args = parser.parse_args()

    if args.channels:
        channels = search_channels()
        print("\n=== Recommended NBA Analytics YouTube Channels ===\n")
        for ch in channels:
            print(f"• {ch['name']} (@{ch['handle']})")
            print(f"  Focus: {ch['focus']}")
            print(f"  Features: {', '.join(ch['feature_categories'])}")
            print()
        return

    service, _ = get_youtube_service()

    if args.video:
        print(f"Analyzing video {args.video}...")
        meta = {}
        if service:
            try:
                resp = service.videos().list(part="snippet,contentDetails", id=args.video).execute()
                if resp.get("items"):
                    item = resp["items"][0]
                    snip = item.get("snippet", {})
                    meta = {
                        "title": snip.get("title", ""),
                        "channel": snip.get("channelTitle", ""),
                        "description": snip.get("description", "")[:500]
                    }
            except Exception:
                pass

        analysis = analyze_video(args.video, meta)
        if analysis:
            print(json.dumps(analysis, indent=2))
        else:
            print("[ERROR] Could not analyze video")
        return

    if args.search:
        print(f"\nSearching for: '{args.search}'")
        print("Recommended: Use --channels to find and subscribe to key NBA analytics channels")
        print("Then use --video <id> to extract features from specific videos\n")
        return

    print("Use --help for usage. Example:")
    print("  python3 scripts/youtube_feature_extractor.py --channels")
    print("  python3 scripts/youtube_feature_extractor.py --video dQw4w9WgXcQ")


if __name__ == "__main__":
    main()
