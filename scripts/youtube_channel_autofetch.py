#!/usr/bin/env python3
"""YouTube channel auto-fetch — every 6h, pulls recent uploads from a seeded
channel list and appends new videos to data/youtube/manual-ingested.json.

Downstream, youtube_feeder.py reads manual-ingested.json and injects the
narrative into data/prompts/overrides.json for ALL 4 TFs (NBA/POL/ITF/PQTF).

Why seeded channels (not full subscriptions): the OAuth refresh token saved at
data/credentials/youtube-oauth.json (auth_tokens[0]) returned 400 invalid_token
so we can't call subscriptions.list. Seeded channels are easy to extend —
add channel_ids to CHANNELS below.

API key: reads YOUTUBE_API_KEY first (working AIzaSyC8N0GUbjAqoW... on project
549962199864), falls back to the api_key field in youtube-oauth.json.

Usage:
  python3 scripts/youtube_channel_autofetch.py               # fetch + dedupe
  python3 scripts/youtube_channel_autofetch.py --max 3       # per-channel cap
  python3 scripts/youtube_channel_autofetch.py --dry-run     # print, no write
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import datetime as dt
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUAL_PATH = ROOT / "data" / "youtube" / "manual-ingested.json"
CREDS_PATH = ROOT / "data" / "credentials" / "youtube-oauth.json"
LOG_PATH = ROOT / "data" / "youtube" / "autofetch-log.jsonl"

# Seeded channels — add channel_ids here as user flags more.
# Every new channel will pull its N most-recent uploads every 6h.
CHANNELS = {
    "UCN7D80fY9xMYu5mHhUhXEFw": "Moon Dev",
    "UCOHxDwCcOzBaLkeTazanwcw": "Bravos Research",
    "UCbekhhidkzkGryM7mi5Ys_w": "Tech Jarves",
}

MAX_PER_CHANNEL_DEFAULT = 5
LOOKBACK_DAYS = 7  # ignore videos older than this (initial backfill uses all)


def _api_key() -> str | None:
    k = os.environ.get("YOUTUBE_API_KEY")
    if k:
        return k
    if CREDS_PATH.exists():
        try:
            return json.loads(CREDS_PATH.read_text()).get("api_key")
        except Exception:
            return None
    return os.environ.get("GOOGLE_API_KEY")


def _http_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "nomos-yt-autofetch"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _uploads_playlist_id(channel_id: str, key: str) -> str | None:
    params = {"part": "contentDetails", "id": channel_id, "key": key}
    url = "https://www.googleapis.com/youtube/v3/channels?" + urllib.parse.urlencode(params)
    d = _http_json(url)
    items = d.get("items") or []
    if not items:
        return None
    return ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")


def _recent_uploads(playlist_id: str, key: str, limit: int) -> list[dict]:
    params = {"part": "snippet,contentDetails", "playlistId": playlist_id, "maxResults": str(limit), "key": key}
    url = "https://www.googleapis.com/youtube/v3/playlistItems?" + urllib.parse.urlencode(params)
    d = _http_json(url)
    out = []
    for it in d.get("items") or []:
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
        if not vid:
            continue
        out.append({
            "id": vid,
            "title": sn.get("title") or "",
            "channel": sn.get("channelTitle") or "",
            "channel_id": sn.get("channelId") or "",
            "published_at": sn.get("publishedAt") or cd.get("videoPublishedAt") or "",
            "description": (sn.get("description") or "")[:600],
        })
    return out


def _hydrate(video_ids: list[str], key: str) -> dict[str, dict]:
    """Batch-fetch statistics + duration for a list of video IDs."""
    if not video_ids:
        return {}
    out = {}
    for i in range(0, len(video_ids), 50):  # videos.list accepts up to 50 ids
        params = {"part": "statistics,contentDetails", "id": ",".join(video_ids[i:i+50]), "key": key}
        url = "https://www.googleapis.com/youtube/v3/videos?" + urllib.parse.urlencode(params)
        try:
            d = _http_json(url)
        except Exception:
            continue
        for it in d.get("items") or []:
            st = it.get("statistics") or {}
            cd = it.get("contentDetails") or {}
            out[it["id"]] = {
                "view_count": int(st.get("viewCount", 0) or 0),
                "like_count": int(st.get("likeCount", 0) or 0),
                "comment_count": int(st.get("commentCount", 0) or 0),
                "duration": cd.get("duration") or "",
            }
    return out


def _load_manual() -> dict:
    if not MANUAL_PATH.exists():
        return {"videos": [], "updated_at": ""}
    try:
        return json.loads(MANUAL_PATH.read_text())
    except Exception:
        return {"videos": [], "updated_at": ""}


def _append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=MAX_PER_CHANNEL_DEFAULT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS)
    args = ap.parse_args()

    key = _api_key()
    if not key:
        print("no YOUTUBE_API_KEY (or GOOGLE_API_KEY fallback) — aborting", file=sys.stderr)
        return 1

    lib = _load_manual()
    existing_ids = {v["id"] for v in lib.get("videos", [])}
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    cutoff = now - dt.timedelta(days=args.lookback_days)

    candidates: list[dict] = []
    per_channel: dict[str, int] = {}
    errors: list[dict] = []

    for cid, name in CHANNELS.items():
        try:
            pl = _uploads_playlist_id(cid, key)
            if not pl:
                errors.append({"channel_id": cid, "name": name, "error": "no_uploads_playlist"})
                continue
            vids = _recent_uploads(pl, key, args.max)
            kept = 0
            for v in vids:
                if v["id"] in existing_ids:
                    continue
                try:
                    pub = dt.datetime.fromisoformat(v["published_at"].replace("Z", "+00:00"))
                except Exception:
                    pub = now
                if pub < cutoff:
                    continue
                candidates.append(v)
                kept += 1
            per_channel[name] = kept
        except Exception as e:
            errors.append({"channel_id": cid, "name": name, "error": str(e)[:200]})

    hydra = _hydrate([c["id"] for c in candidates], key)
    for c in candidates:
        c.update(hydra.get(c["id"], {}))
        c["url"] = f"https://www.youtube.com/watch?v={c['id']}"
        c["ingested_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        c["source"] = "channel_autofetch"
        c["user_note"] = f"Auto-ingested from {c['channel']} uploads — shared across NBA/POL/ITF/PQTF"

    log_entry = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channels": len(CHANNELS),
        "new_videos": len(candidates),
        "per_channel": per_channel,
        "errors": errors,
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        print(json.dumps({"log": log_entry, "candidates": [{"id": c["id"], "title": c["title"][:80]} for c in candidates]}, indent=2))
        return 0

    if candidates:
        lib.setdefault("videos", []).extend(candidates)
        lib["updated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        MANUAL_PATH.write_text(json.dumps(lib, indent=2, ensure_ascii=False))

    _append_log(log_entry)
    print(json.dumps(log_entry, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
