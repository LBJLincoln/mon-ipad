#!/usr/bin/env python3
"""YouTube → FinBERT sentiment precompute (Tier 1 per HAWKEYE 2026-04-21).

Loads `data/youtube/manual-ingested.json`, runs ProsusAI/finBERT on each
video's title+description[:512], caches per-id into
`data/youtube/sentiment.parquet`. Idempotent — re-runs only hit new ids.

Output schema (parquet):
  id:str, published_at:datetime64[ns, UTC], channel:str,
  sent_pos:float64, sent_neu:float64, sent_neg:float64, polarity:float64

Downstream: features/engine.py loads this parquet into
`_youtube_sentiment_features(game_date, sim_cutoff)` which emits 6 scalars
(yt_pol_mean_{3,7,14}, yt_abs_pol_mean_{3,7,14}) per game row.

CPU-safe (~30ms/doc). Usage:
  python3 scripts/youtube_sentiment_precompute.py            # incremental
  python3 scripts/youtube_sentiment_precompute.py --rebuild  # wipe + redo
  python3 scripts/youtube_sentiment_precompute.py --limit 5  # smoke test
"""
from __future__ import annotations
import argparse
import json
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "youtube" / "manual-ingested.json"
OUT = ROOT / "data" / "youtube" / "sentiment.parquet"


def _load_videos() -> list[dict]:
    if not SRC.exists():
        return []
    try:
        return json.loads(SRC.read_text()).get("videos", []) or []
    except Exception as e:
        sys.stderr.write(f"bad manual-ingested.json: {e}\n")
        return []


def _existing_ids() -> set[str]:
    if not OUT.exists():
        return set()
    try:
        import pandas as pd
        return set(pd.read_parquet(OUT)["id"].astype(str).tolist())
    except Exception as e:
        sys.stderr.write(f"warn: cannot read existing parquet ({e}); rebuilding\n")
        return set()


def _finbert_pipeline():
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    except ImportError:
        sys.stderr.write(
            "transformers not installed. Install:\n"
            "  pip install --break-system-packages transformers torch pandas pyarrow\n"
        )
        sys.exit(2)
    tok = AutoTokenizer.from_pretrained("ProsusAI/finbert")
    mdl = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
    return pipeline("text-classification", model=mdl, tokenizer=tok,
                    top_k=None, truncation=True, max_length=512, device=-1)


def _score(pipe, text: str) -> dict:
    # Pipeline returns [[{label,score}, {label,score}, {label,score}]] for top_k=None
    res = pipe(text)
    if isinstance(res, list) and res and isinstance(res[0], list):
        res = res[0]
    out = {"sent_pos": 0.0, "sent_neu": 0.0, "sent_neg": 0.0}
    for r in res:
        lab = (r.get("label") or "").lower()
        sc = float(r.get("score", 0.0))
        if lab.startswith("pos"):
            out["sent_pos"] = sc
        elif lab.startswith("neg"):
            out["sent_neg"] = sc
        elif lab.startswith("neu"):
            out["sent_neu"] = sc
    out["polarity"] = out["sent_pos"] - out["sent_neg"]
    return out


def _parse_published(s: str) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Process at most N videos (smoke test)")
    args = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        sys.stderr.write("pandas required — pip install pandas pyarrow\n")
        return 2

    vids = _load_videos()
    if not vids:
        sys.stdout.write(json.dumps({"status": "EMPTY", "reason": "no videos in corpus"}) + "\n")
        return 0

    done = set() if args.rebuild else _existing_ids()
    todo = [v for v in vids if v.get("id") and v["id"] not in done]
    if args.limit > 0:
        todo = todo[:args.limit]

    if not todo:
        sys.stdout.write(json.dumps({
            "status": "UP_TO_DATE", "cached": len(done), "corpus": len(vids)
        }) + "\n")
        return 0

    sys.stderr.write(f"Loading FinBERT (first run downloads ~440MB)...\n")
    pipe = _finbert_pipeline()

    rows = []
    for i, v in enumerate(todo):
        title = (v.get("title") or "").strip()
        desc = (v.get("description") or "").strip()[:512]
        text = (title + ". " + desc) if desc else title
        if not text:
            continue
        try:
            scored = _score(pipe, text)
        except Exception as e:
            sys.stderr.write(f"warn: scoring failed for {v['id']}: {e}\n")
            continue
        pub = _parse_published(v.get("published_at") or v.get("ingested_at") or "")
        rows.append({
            "id": v["id"],
            "published_at": pub,
            "channel": v.get("channel") or "",
            **scored,
        })
        if (i + 1) % 20 == 0:
            sys.stderr.write(f"  scored {i+1}/{len(todo)}\n")

    if not rows:
        sys.stdout.write(json.dumps({"status": "NO_NEW_ROWS"}) + "\n")
        return 0

    new_df = pd.DataFrame(rows)
    # Coerce tz-aware timestamps
    new_df["published_at"] = pd.to_datetime(new_df["published_at"], utc=True, errors="coerce")

    if args.rebuild or not OUT.exists():
        out_df = new_df
    else:
        try:
            old_df = pd.read_parquet(OUT)
            out_df = pd.concat([old_df, new_df], ignore_index=True)
            out_df = out_df.drop_duplicates(subset=["id"], keep="last")
        except Exception:
            out_df = new_df

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(OUT, index=False)

    summary = {
        "status": "OK",
        "corpus": len(vids),
        "new_scored": len(rows),
        "total_cached": len(out_df),
        "polarity_mean": float(out_df["polarity"].mean()),
        "polarity_std": float(out_df["polarity"].std()),
    }
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
