#!/usr/bin/env python3
"""
YouTube feeder (no-API-key path) — daily narrative for NBA/POL/ITF trading floors.

Uses yt-dlp for search + metadata and youtube-transcript-api for transcripts.
Zero Google credentials required.

Output:
  data/youtube/YYYY-MM-DD-<fleet>.json   — raw digest
  data/prompts/overrides.json            — injects <fleet>.market_narrative

Usage:
  python3 scripts/youtube_feeder.py --fleet nba
  python3 scripts/youtube_feeder.py --fleet all
  python3 scripts/youtube_feeder.py --fleet itf --inject
"""

import argparse, json, os, sys, time, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "youtube"
OVERRIDES_PATH = ROOT / "data" / "prompts" / "overrides.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = {
    "nba": [
        "NBA playoff 2026 analysis today",
        "NBA DFS picks today",
        "NBA betting edge today",
    ],
    "pol": [
        "2026 election polling update",
        "political prediction markets today",
        "congressional race forecast",
    ],
    "itf": [
        "stock market close today",
        "unusual options flow today",
        "crypto market analysis today",
    ],
    "pqtf": [
        "options flow analysis today",
        "VIX volatility trading",
        "derivatives quant strategy",
    ],
}

# user-curated playlists (public + collaborative); add URLs as you build them
PLAYLISTS = {
    "nba": [],
    "pol": [],
    "itf": [],
    "pqtf": [],
}

MANUAL_PATH = ROOT / "data" / "youtube" / "manual-ingested.json"

MAX_PER_QUERY = 2
MAX_TRANSCRIPT_CHARS = 1000
TRANSCRIPT_TIMEOUT_S = 8


def _load_api_key():
    k = os.environ.get("GOOGLE_API_KEY") or os.environ.get("YOUTUBE_API_KEY")
    if k:
        return k
    creds = ROOT / "data" / "credentials" / "youtube-oauth.json"
    if creds.exists():
        try:
            return json.loads(creds.read_text()).get("api_key")
        except Exception:
            return None
    return None


def search_recent_api(query: str, max_results: int = MAX_PER_QUERY, api_key: str = None):
    import urllib.parse, urllib.request
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": str(max_results),
        "order": "date",
        "relevanceLanguage": "en",
        "key": api_key,
    }
    url = "https://www.googleapis.com/youtube/v3/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.load(r)
    out = []
    for it in data.get("items", []):
        vid = (it.get("id") or {}).get("videoId")
        sn = it.get("snippet") or {}
        if not vid:
            continue
        out.append({
            "id": vid,
            "title": sn.get("title", ""),
            "channel": sn.get("channelTitle", ""),
            "duration_s": 0,
            "view_count": 0,
            "url": f"https://www.youtube.com/watch?v={vid}",
            "published_at": sn.get("publishedAt", ""),
            "description": (sn.get("description") or "")[:300],
        })
    return out


def search_recent(query: str, max_results: int = MAX_PER_QUERY):
    key = _load_api_key()
    if key:
        try:
            return search_recent_api(query, max_results, key)
        except Exception as e:
            print(f"[warn] API search failed for '{query}', falling back to yt-dlp: {e}", file=sys.stderr)
    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": max_results,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        spec = f"ytsearch{max_results}:{query}"
        r = y.extract_info(spec, download=False) or {}
        return [
            {
                "id": e.get("id"),
                "title": e.get("title") or "",
                "channel": e.get("uploader") or e.get("channel") or "",
                "duration_s": e.get("duration") or 0,
                "view_count": e.get("view_count") or 0,
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
            }
            for e in (r.get("entries") or [])
            if e and e.get("id")
        ]


def fetch_transcript(video_id: str) -> str:
    import signal
    from youtube_transcript_api import YouTubeTranscriptApi

    def _timeout(signum, frame):
        raise TimeoutError("transcript fetch timeout")

    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(TRANSCRIPT_TIMEOUT_S)
    try:
        api = YouTubeTranscriptApi()
        segs = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        txt = " ".join(s.text for s in segs)
        return txt[:MAX_TRANSCRIPT_CHARS]
    except Exception as e:
        return f"<transcript unavailable: {type(e).__name__}>"
    finally:
        signal.alarm(0)


def playlist_videos(url: str, max_results: int = 10):
    import yt_dlp
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
        "playlistend": max_results,
    }
    with yt_dlp.YoutubeDL(opts) as y:
        r = y.extract_info(url, download=False) or {}
        return [
            {
                "id": e.get("id"),
                "title": e.get("title") or "",
                "channel": e.get("uploader") or e.get("channel") or "",
                "duration_s": e.get("duration") or 0,
                "view_count": e.get("view_count") or 0,
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                "source": "playlist",
            }
            for e in (r.get("entries") or [])
            if e and e.get("id")
        ]


def _load_manual_videos() -> list:
    """User-linked high-signal videos — ingested manually, shared across all fleets."""
    if not MANUAL_PATH.exists():
        return []
    try:
        lib = json.loads(MANUAL_PATH.read_text())
        out = []
        for v in lib.get("videos", []):
            out.append({
                "id": v["id"],
                "title": v.get("title", ""),
                "channel": v.get("channel", ""),
                "duration_s": 0,
                "view_count": v.get("view_count", 0),
                "url": v.get("url", ""),
                "published_at": v.get("published_at", ""),
                "description": (v.get("description") or "")[:800],
                "source": "manual",
            })
        return out
    except Exception:
        return []


def build_digest(fleet: str, extra_playlists=None) -> dict:
    queries = QUERIES[fleet]
    videos = []
    seen = set()

    # manual-ingested user-curated videos (shared across fleets, high signal)
    for mv in _load_manual_videos():
        if mv["id"] in seen:
            continue
        seen.add(mv["id"])
        mv["query"] = "manual:user_curated"
        videos.append(mv)
    for q in queries:
        try:
            hits = search_recent(q)
        except Exception as e:
            print(f"[warn] search failed for '{q}': {e}", file=sys.stderr)
            continue
        for h in hits:
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            h["query"] = q
            h["source"] = "search"
            videos.append(h)

    for url in (PLAYLISTS.get(fleet, []) + (extra_playlists or [])):
        try:
            hits = playlist_videos(url)
        except Exception as e:
            print(f"[warn] playlist failed {url}: {e}", file=sys.stderr)
            continue
        for h in hits:
            if h["id"] in seen:
                continue
            seen.add(h["id"])
            h["query"] = f"playlist:{url}"
            videos.append(h)

    for v in videos:
        tr = fetch_transcript(v["id"])
        if tr.startswith("<transcript unavailable"):
            # graceful fallback: use description (always available via API)
            v["transcript_excerpt"] = (v.get("description") or "")[:MAX_TRANSCRIPT_CHARS]
            v["transcript_source"] = "description_fallback"
        else:
            v["transcript_excerpt"] = tr
            v["transcript_source"] = "transcript"
        time.sleep(0.15)

    narrative = _summarize(videos)
    return {
        "fleet": fleet,
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "queries": queries,
        "playlists": PLAYLISTS.get(fleet, []) + (extra_playlists or []),
        "video_count": len(videos),
        "videos": videos,
        "narrative": narrative,
    }


def _summarize(videos: list) -> str:
    """Narrative: title + excerpt (from transcript or description fallback)."""
    lines = []
    for v in videos:
        tr = (v.get("transcript_excerpt") or "").strip().replace("\n", " ")
        snippet = " " + tr[:180] if tr else ""
        lines.append(f"- {v['channel']} «{v['title'][:90]}»{snippet}")
    header = f"YouTube narrative digest ({len(videos)} videos):"
    return header + "\n" + "\n".join(lines[:8])


def inject_override(fleet: str, narrative: str):
    overrides = {}
    if OVERRIDES_PATH.exists():
        try:
            overrides = json.loads(OVERRIDES_PATH.read_text())
        except Exception:
            overrides = {}
    node = overrides.setdefault(fleet, {})
    node["market_narrative"] = narrative
    node["market_narrative_ts"] = dt.datetime.utcnow().isoformat() + "Z"
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDES_PATH.write_text(json.dumps(overrides, indent=2, sort_keys=True))
    print(f"[inject] updated {OVERRIDES_PATH} -> {fleet}.market_narrative ({len(narrative)} chars)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fleet", choices=["nba", "pol", "itf", "pqtf", "all"], required=True)
    p.add_argument("--inject", action="store_true", help="write into data/prompts/overrides.json")
    args = p.parse_args()

    fleets = ["nba", "pol", "itf", "pqtf"] if args.fleet == "all" else [args.fleet]
    today = dt.date.today().isoformat()
    for f in fleets:
        print(f"[feeder] building digest for fleet={f} ...")
        digest = build_digest(f)
        out = OUT_DIR / f"{today}-{f}.json"
        out.write_text(json.dumps(digest, indent=2))
        print(f"[feeder] wrote {out}  (videos={digest['video_count']})")
        if args.inject:
            inject_override(f, digest["narrative"])


if __name__ == "__main__":
    main()
