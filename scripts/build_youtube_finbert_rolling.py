#!/usr/bin/env python3
"""build_youtube_finbert_rolling.py — roll up sentiment.parquet into a
compact summary JSON consumable by POL export_hot_signals (Cat 44).

Schema out (finbert_rolling_summary.json):
  {
    "generated_at": iso,
    "window_days": 7,
    "n_videos": int,
    "overall": {"polarity_mean": float, "polarity_3d": float, "polarity_7d": float},
    "by_channel": [{"channel": str, "n": int, "polarity_3d": float, "polarity_7d": float}],
    "top_tickers": [{"ticker": str, "n": int, "polarity_3d": float}]   # optional, requires watchlist match
  }

Ticker extraction: scan video title+description+transcript_excerpt for watchlist
tickers (loaded from data/youtube/ticker_watchlist.json if present; otherwise
overall + by_channel only).
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path("/home/termius/mon-ipad")
YT = ROOT / "data" / "youtube"
SENTIMENT = YT / "sentiment.parquet"
OUT = YT / "finbert_rolling_summary.json"
WATCHLIST = YT / "ticker_watchlist.json"


def _load_sentiment():
    try:
        import pandas as pd
    except ImportError:
        print("[yt-finbert] pandas unavailable — skipping", file=sys.stderr)
        return None
    if not SENTIMENT.exists():
        print(f"[yt-finbert] missing {SENTIMENT}", file=sys.stderr)
        return None
    return pd.read_parquet(SENTIMENT)


def _load_video_meta():
    """Gather all {id -> (title+desc+transcript, channel)} from recent YT JSONs."""
    meta = {}
    for p in sorted(YT.glob("2026-*.json")):
        try:
            body = json.loads(p.read_text())
        except Exception:
            continue
        vids = body.get("videos") or []
        for v in vids:
            vid = v.get("id")
            if not vid or vid in meta:
                continue
            text = " ".join([
                v.get("title") or "",
                v.get("description") or "",
                v.get("transcript_excerpt") or "",
            ])
            meta[vid] = {"text": text, "channel": v.get("channel") or ""}
    return meta


def _load_watchlist():
    if not WATCHLIST.exists():
        # Seed a reasonable macro+mega-cap watchlist. User can curate later.
        default = [
            "SPY", "QQQ", "IWM", "DIA", "VXX", "TLT", "GLD", "UUP", "USO",
            "XLE", "XLF", "XLK", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE",
            "NVDA", "TSLA", "AAPL", "MSFT", "GOOGL", "GOOG", "META", "AMZN", "AMD", "NFLX",
            "COIN", "MSTR", "GME", "PLTR", "SOFI", "RIVN", "LCID",
            "JPM", "BAC", "WFC", "GS", "MS",
            "BTC", "ETH", "SOL", "DOGE",
        ]
        WATCHLIST.write_text(json.dumps(default, indent=2))
        return default
    try:
        return json.loads(WATCHLIST.read_text())
    except Exception:
        return []


def build() -> dict:
    df = _load_sentiment()
    if df is None or df.empty:
        return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "note": "no sentiment data"}
    import pandas as pd
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    now = datetime.now(timezone.utc)
    cut7 = now - timedelta(days=7)
    cut3 = now - timedelta(days=3)
    d7 = df[df["published_at"] >= cut7].copy()
    d3 = df[df["published_at"] >= cut3].copy()

    overall = {
        "polarity_mean": round(float(df["polarity"].mean()), 4),
        "polarity_3d": round(float(d3["polarity"].mean()) if not d3.empty else 0.0, 4),
        "polarity_7d": round(float(d7["polarity"].mean()) if not d7.empty else 0.0, 4),
        "n_total": int(len(df)),
        "n_3d": int(len(d3)),
        "n_7d": int(len(d7)),
    }

    by_channel = []
    if not d7.empty:
        for ch, grp in d7.groupby("channel"):
            grp3 = d3[d3["channel"] == ch]
            by_channel.append({
                "channel": str(ch)[:40],
                "n": int(len(grp)),
                "polarity_3d": round(float(grp3["polarity"].mean()) if not grp3.empty else 0.0, 4),
                "polarity_7d": round(float(grp["polarity"].mean()), 4),
            })
        by_channel.sort(key=lambda r: -abs(r["polarity_7d"]) * r["n"])
        by_channel = by_channel[:8]

    # Per-ticker rolling 3d — requires meta join (title+desc+transcript)
    top_tickers = []
    watchlist = set(_load_watchlist())
    if watchlist:
        meta = _load_video_meta()
        tkr_counts = {}
        tkr_polarity = {}
        # match uppercase word boundaries — "$NVDA" or " NVDA "
        tkr_re = re.compile(r"(?:\$|\b)(" + "|".join(re.escape(t) for t in watchlist) + r")\b")
        for _, row in d7.iterrows():
            m = meta.get(row["id"])
            if not m:
                continue
            hits = set(tkr_re.findall(m["text"].upper()))
            for t in hits:
                tkr_counts[t] = tkr_counts.get(t, 0) + 1
                tkr_polarity.setdefault(t, []).append(float(row["polarity"]))
        rows = []
        for t, polarities in tkr_polarity.items():
            if len(polarities) < 2:
                continue
            rows.append({
                "ticker": t,
                "n": tkr_counts[t],
                "polarity_3d": round(sum(polarities) / len(polarities), 4),
            })
        rows.sort(key=lambda r: -abs(r["polarity_3d"]) * r["n"])
        top_tickers = rows[:10]

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "window_days": 7,
        "n_videos": int(len(d7)),
        "overall": overall,
        "by_channel": by_channel,
        "top_tickers": top_tickers,
    }


def main() -> int:
    summary = build()
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"[yt-finbert] wrote {OUT.name} ({len(OUT.read_bytes())} B) · "
          f"overall 3d={summary.get('overall', {}).get('polarity_3d')} "
          f"tickers={len(summary.get('top_tickers', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
