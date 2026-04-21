#!/usr/bin/env python3
"""YouTube OAuth — pull user's own subscriptions + liked videos + uploads.

This is the PRIMARY seed path for channel discovery. Replaces any hand-curated
CHANNELS extension for topics the user cares about — we trust their own
subscriptions list, not our guesses.

Auth flow (OAuth 2.0 installed-app, out-of-band):
  1. First run:  python3 scripts/youtube_oauth_subscriptions.py
                 → prints a URL. Open it in your browser, authorize, copy the code.
  2. Re-run:     python3 scripts/youtube_oauth_subscriptions.py --auth-code <CODE>
                 → exchanges code for refresh token, saves to
                   data/credentials/youtube-oauth-refresh.json (GITIGNORED).
  3. Subsequent runs use the refresh token silently. Run again to re-pull
     subscriptions / merge fresh liked-videos.

Outputs:
  - Appends `channel_id: channel_name` entries to the CHANNELS dict in
    scripts/youtube_channel_autofetch.py (idempotent — skips already-present ids).
  - Merges recent uploads from subscriptions + user's liked videos + user's
    own uploads (if the account has a channel) into
    data/youtube/manual-ingested.json (dedupe by video_id).

Required env (from .env.local):
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET — OAuth client creds for project
  549962199864 (the project with YT Data API v3 enabled).

Scopes: youtube.readonly (subscriptions, liked videos, channels, playlistItems).
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import datetime as dt
from pathlib import Path

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    sys.stderr.write(
        "Missing OAuth deps. Install with:\n"
        "  pip install --break-system-packages google-auth-oauthlib google-api-python-client\n"
        f"Error: {e}\n"
    )
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
REFRESH_PATH = ROOT / "data" / "credentials" / "youtube-oauth-refresh.json"
MANUAL_PATH = ROOT / "data" / "youtube" / "manual-ingested.json"
AUTOFETCH_PATH = ROOT / "scripts" / "youtube_channel_autofetch.py"

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"  # deprecated but still works for scripts


def _load_dotenv() -> None:
    """Load .env.local (simple KEY=VALUE parser, handles single-quoted values)."""
    env = ROOT / ".env.local"
    if not env.exists():
        return
    for raw in env.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)


def _client_config() -> dict:
    cid = os.environ.get("GOOGLE_CLIENT_ID")
    csec = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (cid and csec):
        raise SystemExit(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not in env. "
            "Source .env.local or export them."
        )
    return {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [OOB_REDIRECT, "http://localhost"],
        }
    }


def _save_creds(creds: Credentials) -> None:
    REFRESH_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFRESH_PATH.write_text(creds.to_json())
    try:
        os.chmod(REFRESH_PATH, 0o600)
    except Exception:
        pass


def _load_creds() -> Credentials | None:
    if not REFRESH_PATH.exists():
        return None
    try:
        creds = Credentials.from_authorized_user_info(
            json.loads(REFRESH_PATH.read_text()), SCOPES
        )
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_creds(creds)
        return creds
    except Exception as e:
        sys.stderr.write(f"warn: could not load refresh token ({e}); re-auth required\n")
        return None


def _get_credentials(auth_code: str | None) -> Credentials:
    creds = _load_creds()
    if creds and creds.valid:
        return creds

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=OOB_REDIRECT)

    if auth_code:
        flow.fetch_token(code=auth_code)
        _save_creds(flow.credentials)
        return flow.credentials

    # Print auth URL and exit — user must re-run with --auth-code
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    sys.stdout.write(
        "\n=== OAuth required ===\n"
        f"1. Open this URL in your browser:\n\n   {auth_url}\n\n"
        "2. Sign in with the Google account that owns the YouTube subscriptions you want.\n"
        "3. After granting access, copy the code Google shows you.\n"
        "4. Re-run this script with:\n\n"
        f"   python3 scripts/youtube_oauth_subscriptions.py --auth-code <CODE>\n\n"
        f"Refresh token will be saved to {REFRESH_PATH.relative_to(ROOT)} (gitignored).\n"
    )
    raise SystemExit(0)


# ----- YouTube API helpers -----

def _list_all(request_fn, items_key: str = "items", max_pages: int = 40) -> list[dict]:
    """Paginate a googleapiclient list request and collect all items."""
    out = []
    req = request_fn()
    pages = 0
    while req is not None and pages < max_pages:
        try:
            resp = req.execute()
        except HttpError as e:
            sys.stderr.write(f"warn: HttpError during pagination: {e}\n")
            break
        out.extend(resp.get(items_key, []) or [])
        req = None
        token = resp.get("nextPageToken")
        if token:
            # Recreate the request with the pageToken via the original closure
            req = request_fn(pageToken=token)
        pages += 1
    return out


def fetch_subscriptions(yt) -> list[dict]:
    def _req(pageToken=None):
        return yt.subscriptions().list(
            part="snippet", mine=True, maxResults=50, pageToken=pageToken,
            order="alphabetical",
        )
    items = _list_all(_req)
    subs = []
    for it in items:
        sn = it.get("snippet") or {}
        rid = (sn.get("resourceId") or {}).get("channelId")
        title = sn.get("title") or ""
        if rid:
            subs.append({"channel_id": rid, "name": title})
    return subs


def fetch_liked_videos(yt, limit: int = 50) -> list[dict]:
    def _req(pageToken=None):
        return yt.playlistItems().list(
            part="snippet,contentDetails", playlistId="LL",
            maxResults=min(limit, 50), pageToken=pageToken,
        )
    try:
        items = _list_all(_req, max_pages=max(1, limit // 50 + 1))
    except HttpError as e:
        sys.stderr.write(f"warn: liked videos list failed ({e}); skipping\n")
        return []
    out = []
    for it in items[:limit]:
        sn = it.get("snippet") or {}
        cd = it.get("contentDetails") or {}
        vid = cd.get("videoId") or (sn.get("resourceId") or {}).get("videoId")
        if not vid:
            continue
        out.append({
            "id": vid,
            "title": sn.get("title") or "",
            "channel": sn.get("videoOwnerChannelTitle") or sn.get("channelTitle") or "",
            "channel_id": sn.get("videoOwnerChannelId") or sn.get("channelId") or "",
            "published_at": sn.get("publishedAt") or cd.get("videoPublishedAt") or "",
            "description": (sn.get("description") or "")[:600],
        })
    return out


def fetch_own_uploads(yt, limit: int = 25) -> list[dict]:
    try:
        me = yt.channels().list(part="contentDetails", mine=True).execute()
    except HttpError as e:
        sys.stderr.write(f"warn: channels.list(mine) failed ({e}); skipping own uploads\n")
        return []
    items = me.get("items") or []
    if not items:
        return []
    uploads = (
        ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    )
    if not uploads:
        return []
    def _req(pageToken=None):
        return yt.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads,
            maxResults=min(limit, 50), pageToken=pageToken,
        )
    items = _list_all(_req, max_pages=max(1, limit // 50 + 1))
    out = []
    for it in items[:limit]:
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


# ----- Writers -----

def merge_channels(subs: list[dict]) -> tuple[int, int]:
    """Idempotent append of channel_id:name entries to CHANNELS dict in
    scripts/youtube_channel_autofetch.py. Returns (added, already_present)."""
    src = AUTOFETCH_PATH.read_text()
    existing_ids = set(re.findall(r'"(UC[A-Za-z0-9_\-]{20,26})"', src))
    added, already = 0, 0
    new_lines = []
    for s in subs:
        cid = s["channel_id"]
        if cid in existing_ids:
            already += 1
            continue
        # sanitize name for Python string literal
        name = s["name"].replace("\\", "\\\\").replace('"', '\\"')
        new_lines.append(f'    "{cid}": "{name}",  # oauth_subs {dt.date.today().isoformat()}')
        existing_ids.add(cid)
        added += 1

    if not new_lines:
        return (0, already)

    # Insert just before the closing brace of the CHANNELS dict.
    # Find the line that ends CHANNELS definition — look for the closing "}" after
    # the "CHANNELS = {" marker.
    pattern = re.compile(r"(CHANNELS\s*=\s*\{.*?)(\n\})", re.DOTALL)
    m = pattern.search(src)
    if not m:
        raise SystemExit("could not locate CHANNELS dict closing brace in youtube_channel_autofetch.py")
    block = "\n".join(new_lines)
    insert = f"    # --- OAuth-seeded subscriptions ({dt.date.today().isoformat()}) ---\n{block}\n"
    patched = src[:m.end(1)] + "\n" + insert + m.group(2) + src[m.end(2):]
    AUTOFETCH_PATH.write_text(patched)
    return (added, already)


def merge_videos(new_vids: list[dict]) -> tuple[int, int]:
    """Append new videos to data/youtube/manual-ingested.json, dedupe by id."""
    if not MANUAL_PATH.exists():
        lib = {"videos": [], "updated_at": ""}
    else:
        lib = json.loads(MANUAL_PATH.read_text())
    existing = {v.get("id") for v in lib.get("videos", []) if v.get("id")}
    added, dup = 0, 0
    now_iso = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for v in new_vids:
        if not v.get("id") or v["id"] in existing:
            dup += 1
            continue
        v["ingested_at"] = now_iso
        v.setdefault("source", "oauth_subscription_merge")
        v.setdefault("url", f"https://www.youtube.com/watch?v={v['id']}")
        v.setdefault("user_note", f"OAuth-merged from {v.get('channel','?')} — user subscription / liked")
        lib.setdefault("videos", []).append(v)
        existing.add(v["id"])
        added += 1
    if added:
        lib["updated_at"] = now_iso
        MANUAL_PATH.write_text(json.dumps(lib, indent=2, ensure_ascii=False))
    return (added, dup)


def count_keyword_hits(lib_path: Path) -> dict:
    if not lib_path.exists():
        return {"total": 0, "nba": 0, "pol": 0}
    vids = json.loads(lib_path.read_text()).get("videos", [])
    NBA_KW = ("nba","basketball","lakers","lebron","celtics","warriors","bucks",
              "nuggets","heat","playoff","knicks","mavericks","clippers","curry","doncic")
    POL_KW = ("trump","biden","election","senate","congress","fed","fomc","tariff",
              "politic","sec ","cpi","inflation","macro","treasury","yield",
              "recession","fiscal","debt ceiling","powell","white house")
    nba = sum(1 for v in vids if any(k in (v.get("title","")+" "+v.get("description","")).lower() for k in NBA_KW))
    pol = sum(1 for v in vids if any(k in (v.get("title","")+" "+v.get("description","")).lower() for k in POL_KW))
    return {"total": len(vids), "nba": nba, "pol": pol}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth-code", help="Paste the code from Google's OAuth page (first run only)")
    ap.add_argument("--liked-limit", type=int, default=100, help="Max liked videos to merge")
    ap.add_argument("--uploads-limit", type=int, default=25, help="Max own uploads to merge")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    _load_dotenv()

    before = count_keyword_hits(MANUAL_PATH)

    creds = _get_credentials(args.auth_code)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)

    subs = fetch_subscriptions(yt)
    liked = fetch_liked_videos(yt, limit=args.liked_limit)
    owns = fetch_own_uploads(yt, limit=args.uploads_limit)

    # Report-only if empty
    if not subs and not liked and not owns:
        sys.stdout.write(json.dumps({
            "status": "EMPTY",
            "message": "OAuth succeeded but user has 0 subscriptions, 0 liked videos, 0 own uploads. "
                       "Not falling back to guessed channels — report back.",
            "before_kw": before,
        }, indent=2) + "\n")
        return 0

    if args.dry_run:
        sys.stdout.write(json.dumps({
            "status": "DRY_RUN",
            "subscriptions_count": len(subs),
            "liked_count": len(liked),
            "own_uploads_count": len(owns),
            "first_5_subs": subs[:5],
        }, indent=2) + "\n")
        return 0

    ch_added, ch_dup = merge_channels(subs)
    merged_vids = liked + owns
    v_added, v_dup = merge_videos(merged_vids)

    after = count_keyword_hits(MANUAL_PATH)

    summary = {
        "status": "OK",
        "subscriptions_seen": len(subs),
        "channels_added": ch_added,
        "channels_already_present": ch_dup,
        "liked_videos_seen": len(liked),
        "own_uploads_seen": len(owns),
        "videos_added": v_added,
        "videos_already_present": v_dup,
        "before_kw": before,
        "after_kw": after,
        "delta_kw": {
            "total": after["total"] - before["total"],
            "nba": after["nba"] - before["nba"],
            "pol": after["pol"] - before["pol"],
        },
    }
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
