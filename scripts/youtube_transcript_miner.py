#!/usr/bin/env python3
"""YouTube Transcript Miner for NBA Quant Research.

Mines YouTube video transcripts and scores them for NBA analytics relevance.
Supports: --search, --channel, --playlist, --video, --liked modes.

Usage:
    python3 scripts/youtube_transcript_miner.py --search "NBA advanced analytics" --max 5
    python3 scripts/youtube_transcript_miner.py --video dQw4w9WgXcQ
    python3 scripts/youtube_transcript_miner.py --channel UC... --max 20
    python3 scripts/youtube_transcript_miner.py --playlist PL... --max 50
"""

import argparse, json, os, sys, re, time, warnings, logging
from pathlib import Path
from datetime import datetime

# Suppress noisy httplib2/google warnings
warnings.filterwarnings("ignore")
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
logging.getLogger("googleapiclient.discovery").setLevel(logging.ERROR)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "youtube-transcripts"
DATA_DIR.mkdir(parents=True, exist_ok=True)

KEYWORDS = [
    "nba", "analytics", "stats", "prediction", "model", "machine learning",
    "basketball", "advanced stats", "efg", "raptor", "epm", "tracking",
    "hustle", "shot quality", "clutch", "pace", "efficiency", "win shares",
    "bpm", "vorp", "per", "true shooting", "usage rate", "assist ratio",
    "betting", "spread", "moneyline", "over under", "prop", "sportsbook",
    "brier", "elo", "xgboost", "gradient boost", "random forest", "neural",
    "feature engineering", "backtest", "sharpe", "kelly", "bankroll",
    # Cycle 7 additions (2026-03-28)
    "clutch performance", "game script", "game flow", "garbage time", "halftime",
    "referee bias", "foul calls", "home favoritism", "referee crew", "last two minutes",
    "player tracking", "deflections", "contested shots", "screen assists", "speed distance",
    "rest days", "back-to-back", "travel fatigue", "altitude", "timezone",
    "lineup combinations", "rotation depth", "bench depth", "five-man units",
    "shot location", "rim attempts", "three-point frequency", "mid-range", "paint",
    "market microstructure", "sharp money", "steam move", "line movement", "public betting",
    "sharp vs public", "reverse line movement", "closing line value", "clv", "polymarket",
    "injury report", "player availability", "war lost", "minutes load", "workload",
    "head-to-head", "h2h history", "matchup", "style clash", "pace delta",
    "offense defense splits", "perimeter defense", "paint defense", "transition",
    "calibration", "brier score", "probability", "well-calibrated", "miscalibrated",
    "expected goals", "xg", "shot quality", "expected field goal",
    "game importance", "playoff implications", "tanking", "playoff race",
    "tempo-free", "pace-adjusted", "possessions", "per possession",
]


def get_youtube_service():
    """Try to build YouTube Data API v3 client. Returns (service, method) or (None, None)."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("YOUTUBE_API_KEY")
    if api_key:
        try:
            from googleapiclient.discovery import build
            svc = build("youtube", "v3", developerKey=api_key)
            # Validate with a cheap call
            svc.videos().list(part="id", id="dQw4w9WgXcQ").execute()
            print("[OK] YouTube API via API key")
            return svc, "api_key"
        except Exception as e:
            print(f"[WARN] API key failed: {e}")

    # Try gcloud ADC -- verify it actually works for YouTube
    try:
        import google.auth
        from googleapiclient.discovery import build
        creds, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/youtube.readonly"]
        )
        svc = build("youtube", "v3", credentials=creds)
        # Validate
        svc.videos().list(part="id", id="dQw4w9WgXcQ").execute()
        print(f"[OK] YouTube API via gcloud ADC (project: {project})")
        return svc, "oauth"
    except Exception as e:
        if "403" in str(e) or "insufficient" in str(e).lower():
            print("[WARN] gcloud ADC lacks YouTube API scopes")
        else:
            print(f"[WARN] gcloud ADC: {e}")

    print("[INFO] No YouTube Data API. Transcript-only mode available (--video, --search via yt-dlp).")
    print("  For full API: export GOOGLE_API_KEY=<key from console.cloud.google.com/apis/credentials>")
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


def score_relevance(title, description, transcript_text):
    """Score NBA quant relevance 0.0-1.0 based on keyword presence and position."""
    blob = f"{title} {description} {transcript_text}".lower()
    found = []
    for kw in KEYWORDS:
        if kw in blob:
            found.append(kw)
    if not found:
        return 0.0, found
    title_l, desc_l = title.lower(), description.lower()
    score = 0
    for kw in found:
        w = 1
        if kw in title_l: w += 3
        if kw in desc_l: w += 2
        score += w
    normalized = min(score / (len(KEYWORDS) * 6), 1.0)
    return round(normalized, 3), found


def parse_duration(iso_dur):
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    if not iso_dur:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_dur)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def get_video_metadata(service, video_ids):
    """Batch fetch video metadata from YouTube API."""
    if not service or not video_ids:
        return {}
    meta = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        try:
            resp = service.videos().list(
                part="snippet,contentDetails", id=",".join(batch)
            ).execute()
            for item in resp.get("items", []):
                vid = item["id"]
                snip = item.get("snippet", {})
                dur = item.get("contentDetails", {}).get("duration", "")
                meta[vid] = {
                    "title": snip.get("title", ""),
                    "channel": snip.get("channelTitle", ""),
                    "published_at": snip.get("publishedAt", ""),
                    "description": snip.get("description", "")[:500],
                    "duration_seconds": parse_duration(dur),
                }
        except Exception as e:
            print(f"[WARN] Metadata fetch: {e}")
    return meta


def search_videos_api(service, query, max_results):
    """Search via YouTube Data API v3."""
    ids = []
    try:
        page_token = None
        while len(ids) < max_results:
            resp = service.search().list(
                part="id", q=query, type="video",
                maxResults=min(50, max_results - len(ids)),
                pageToken=page_token,
            ).execute()
            for item in resp.get("items", []):
                ids.append(item["id"]["videoId"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"[ERROR] API search failed: {e}")
    return ids[:max_results]


def search_videos_ytdlp(query, max_results):
    """Fallback: search via yt-dlp (no API key needed)."""
    import subprocess
    try:
        cmd = ["yt-dlp", f"ytsearch{max_results}:{query}", "--flat-playlist",
               "--print", "id", "--no-warnings", "-q"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        ids = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        if ids:
            print(f"[OK] yt-dlp found {len(ids)} videos")
        return ids[:max_results]
    except FileNotFoundError:
        print("[WARN] yt-dlp not installed. Install: pip install yt-dlp")
        return []
    except Exception as e:
        print(f"[ERROR] yt-dlp search: {e}")
        return []


def channel_videos(service, channel_id, max_results):
    """Get video IDs from a channel."""
    try:
        resp = service.channels().list(part="contentDetails", id=channel_id).execute()
        items = resp.get("items", [])
        if not items:
            print(f"[ERROR] Channel {channel_id} not found")
            return []
        uploads_pl = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        return playlist_videos(service, uploads_pl, max_results)
    except Exception as e:
        print(f"[ERROR] Channel: {e}")
        return []


def playlist_videos(service, playlist_id, max_results):
    """Get video IDs from a playlist."""
    ids = []
    try:
        page_token = None
        while len(ids) < max_results:
            resp = service.playlistItems().list(
                part="contentDetails", playlistId=playlist_id,
                maxResults=min(50, max_results - len(ids)),
                pageToken=page_token,
            ).execute()
            for item in resp.get("items", []):
                ids.append(item["contentDetails"]["videoId"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        print(f"[ERROR] Playlist: {e}")
    return ids[:max_results]


def mine_video(video_id, metadata=None):
    """Mine a single video: fetch transcript, score, save."""
    out_path = DATA_DIR / f"{video_id}.json"
    if out_path.exists():
        print(f"  [{video_id}] cached")
        with open(out_path) as f:
            return json.load(f)

    meta = metadata or {}
    title = meta.get("title", "")
    description = meta.get("description", "")

    transcript_text, result = fetch_transcript(video_id)
    if transcript_text is None:
        print(f"  [{video_id}] SKIP: {result}")
        return None

    score, kw_found = score_relevance(title, description, transcript_text)
    record = {
        "video_id": video_id,
        "title": title,
        "channel": meta.get("channel", ""),
        "published_at": meta.get("published_at", ""),
        "description": description,
        "transcript": transcript_text,
        "duration_seconds": meta.get("duration_seconds", 0),
        "keywords_found": kw_found,
        "quant_relevance_score": score,
        "mined_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(out_path, "w") as f:
        json.dump(record, f, indent=2)

    kw_short = ", ".join(kw_found[:5]) + ("..." if len(kw_found) > 5 else "")
    print(f"  [{video_id}] score={score:.3f} kw=[{kw_short}] chars={len(transcript_text)}")
    return record


def update_index():
    """Rebuild _index.json from all mined video JSONs."""
    index = []
    for p in sorted(DATA_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            with open(p) as f:
                rec = json.load(f)
            index.append({
                "video_id": rec.get("video_id"),
                "title": rec.get("title"),
                "channel": rec.get("channel"),
                "quant_relevance_score": rec.get("quant_relevance_score"),
                "keywords_found": rec.get("keywords_found", []),
                "mined_at": rec.get("mined_at"),
            })
        except Exception:
            pass
    index.sort(key=lambda x: x.get("quant_relevance_score", 0), reverse=True)
    idx_path = DATA_DIR / "_index.json"
    with open(idx_path, "w") as f:
        json.dump({"count": len(index), "updated": datetime.utcnow().isoformat() + "Z",
                    "videos": index}, f, indent=2)
    print(f"\n[INDEX] {len(index)} videos -> {idx_path}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Transcript Miner for NBA Quant")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", type=str, help="Search query")
    group.add_argument("--channel", type=str, help="Channel ID")
    group.add_argument("--playlist", type=str, help="Playlist ID")
    group.add_argument("--video", type=str, help="Single video ID (or comma-separated)")
    group.add_argument("--liked", action="store_true", help="Liked videos (OAuth)")
    parser.add_argument("--max", type=int, default=10, help="Max videos (default: 10)")
    parser.add_argument("--min-score", type=float, default=0.0, help="Min relevance to keep")
    args = parser.parse_args()

    # --video mode: transcript-only, API optional for metadata
    if args.video:
        video_ids = [v.strip() for v in args.video.split(",") if v.strip()]
        print(f"Mining {len(video_ids)} video(s)...")
        service, _ = get_youtube_service()
        meta = get_video_metadata(service, video_ids) if service else {}
        for vid in video_ids:
            mine_video(vid, meta.get(vid, {}))
        update_index()
        return

    # --search can fallback to yt-dlp
    if args.search:
        service, _ = get_youtube_service()
        if service:
            print(f"Searching API: '{args.search}' (max {args.max})...")
            video_ids = search_videos_api(service, args.search, args.max)
        else:
            print(f"Searching via yt-dlp: '{args.search}' (max {args.max})...")
            video_ids = search_videos_ytdlp(args.search, args.max)
            service = None
    else:
        # --channel, --playlist, --liked all require API
        service, auth_method = get_youtube_service()
        if not service:
            print("[FATAL] --channel/--playlist/--liked require YouTube Data API.")
            print("  export GOOGLE_API_KEY=<your key>")
            sys.exit(1)
        print(f"Collecting videos (max {args.max})...")
        if args.channel:
            video_ids = channel_videos(service, args.channel, args.max)
        elif args.playlist:
            video_ids = playlist_videos(service, args.playlist, args.max)
        elif args.liked:
            if auth_method != "oauth":
                print("[FATAL] --liked requires OAuth, not API key.")
                sys.exit(1)
            video_ids = playlist_videos(service, "LL", args.max)
        else:
            video_ids = []

    if not video_ids:
        print("No videos found.")
        return

    print(f"Found {len(video_ids)} videos. Fetching metadata...")
    metadata = get_video_metadata(service, video_ids) if service else {}

    print(f"Mining transcripts...")
    results = []
    for vid in video_ids:
        rec = mine_video(vid, metadata.get(vid, {}))
        if rec and rec.get("quant_relevance_score", 0) >= args.min_score:
            results.append(rec)
        time.sleep(0.3)

    print(f"\n--- Results ---")
    print(f"Videos: {len(video_ids)} | Mined: {len(results)}")
    if results:
        avg = sum(r["quant_relevance_score"] for r in results) / len(results)
        print(f"Avg relevance: {avg:.3f}")
        top = sorted(results, key=lambda x: x["quant_relevance_score"], reverse=True)[:3]
        for r in top:
            print(f"  {r['quant_relevance_score']:.3f} | {r['title'][:60] or r['video_id']}")

    update_index()


if __name__ == "__main__":
    main()
