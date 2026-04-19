#!/usr/bin/env python3
"""Langfuse 24h summary — traces grouped by TF / provider / status.

Uses /api/public/traces (the working endpoint). /observations + /metrics
both return 500 on Nomos42/langfuse HF deploy — ignore them.

Usage:
    python3 scripts/analysis/langfuse_24h_summary.py [--hours N] [--limit M]

Env: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
"""
import os, base64, urllib.request, json, collections, argparse, sys
from datetime import datetime, timezone, timedelta

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--pages", type=int, default=10)  # 100/page
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    pk = os.environ.get("LANGFUSE_PUBLIC_KEY","")
    sk = os.environ.get("LANGFUSE_SECRET_KEY","")
    host = os.environ.get("LANGFUSE_HOST","https://nomos42-langfuse.hf.space").rstrip("/")
    if not pk or not sk:
        print("[err] LANGFUSE_PUBLIC_KEY/SECRET_KEY not set", file=sys.stderr); sys.exit(2)
    auth = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    t_from = (datetime.now(timezone.utc) - timedelta(hours=args.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for page in range(1, args.pages+1):
        url = f"{host}/api/public/traces?limit=100&page={page}&fromTimestamp={t_from}"
        req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        try:
            body = json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception as e:
            print(f"[err] page {page}: {e}", file=sys.stderr); break
        data = body.get("data", [])
        rows.extend(data)
        if len(data) < 100: break

    by_tf       = collections.Counter()
    by_status   = collections.Counter()
    by_provider = collections.Counter()
    by_model    = collections.Counter()
    by_day      = collections.Counter()
    fallback    = 0
    latencies   = []

    for t in rows:
        m  = t.get("metadata") or {}
        nm = (t.get("name") or "")
        by_provider[m.get("provider","?")] += 1
        by_status[m.get("status","?")] += 1
        by_model[m.get("model","?")] += 1
        by_day[m.get("day","?")] += 1
        if "fallback" in nm: fallback += 1
        prefix = nm.split("-",1)[0]
        if prefix in ("nba","pol","pqtf"): by_tf[prefix] += 1
        else: by_tf["other"] += 1
        lat = m.get("latency_s")
        if isinstance(lat,(int,float)): latencies.append(lat)

    out = {
        "hours": args.hours, "total_traces": len(rows),
        "by_tf": dict(by_tf), "by_status": dict(by_status),
        "by_provider_top10": dict(by_provider.most_common(10)),
        "by_model_top10": dict(by_model.most_common(10)),
        "by_day_top10": dict(by_day.most_common(10)),
        "fallback_count": fallback,
        "fallback_pct": fallback/max(1,len(rows)),
        "latency_mean_s": (sum(latencies)/max(1,len(latencies))) if latencies else None,
        "latency_n": len(latencies),
    }
    if args.json:
        print(json.dumps(out, indent=2)); return
    print(f"=== Langfuse {args.hours}h summary ({len(rows)} traces) ===")
    print(f"by TF       : {dict(by_tf)}")
    print(f"by status   : {dict(by_status)}")
    print(f"fallback    : {fallback}/{len(rows)} = {fallback/max(1,len(rows)):.1%}")
    if latencies: print(f"latency mean: {sum(latencies)/len(latencies):.2f}s (n={len(latencies)})")
    print("providers top10:")
    for k,v in by_provider.most_common(10): print(f"  {v:5d}  {k}")
    print("models top10:")
    for k,v in by_model.most_common(10): print(f"  {v:5d}  {k}")

if __name__ == "__main__":
    main()
