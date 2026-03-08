#!/usr/bin/env python3
"""Twitter/X Auto-Poster — Posts product tweets with Stripe links.

Posts one tweet every 30 minutes with rotating content.
Uses OAuth 1.0a (stdlib only, no tweepy).

Usage:
    source .env.local
    nohup python3 monetisation/twitter-poster.py >> /tmp/twitter-poster.log 2>&1 &
"""

import urllib.request, json, time, hmac, hashlib, base64, urllib.parse, os, uuid, sys, random

CK = os.environ.get('TWITTER_CONSUMER_KEY', '')
CS = os.environ.get('TWITTER_CONSUMER_SECRET', '')
AT = os.environ.get('TWITTER_ACCESS_TOKEN', '')
ATS = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET', '')

if not all([CK, CS, AT, ATS]):
    print("Missing Twitter OAuth credentials in env"); sys.exit(1)

# Tweet templates — rotate through these
TWEETS = [
    "We tested 61,000 RAG questions across 4 pipelines.\n\nResults:\n→ Standard: 87.5% accuracy\n→ Quantitative: 95.2%\n→ Graph: 40.9% (improving)\n\nThe full architecture blueprint + n8n workflows are available.\n\nhttps://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",

    "Most RAG systems use a single pipeline.\n\nThat's why they fail on financial tables, legal docs, and multi-hop questions.\n\nWe built 4 specialized pipelines:\n• Standard (semantic search)\n• Graph (entity relationships)\n• Quantitative (SQL + tables)\n• Orchestrator (intelligent routing)\n\nhttps://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",

    "🔧 Debugging RAG pipelines is brutal.\n\nAfter 79+ fixes across 86 sessions, we compiled everything into a playbook.\n\n• Diagnostic flowcharts\n• 79 documented fixes\n• n8n-specific patterns\n• LLM behavior quirks\n\n$47 → https://buy.stripe.com/8x214g8LEdnbbLBdky5J60h",

    "If you're building with n8n + RAG, this saves you weeks:\n\n7 production workflow files:\n✅ Standard RAG V3.4\n✅ Graph RAG V3.3\n✅ Quantitative RAG V3.1\n✅ Website pipelines (3)\n✅ Orchestrator\n\nAll battle-tested on 61K questions.\n\n$197 → https://buy.stripe.com/dRm8wI1jcerf1148B85J609",

    "Building AI for enterprise sectors (BTP, Finance, Legal, Industry)?\n\nWe ingested 11,387 docs across 4 French sectors into:\n→ Pinecone (46K vectors)\n→ Neo4j (79K nodes, 94.6% entity coverage)\n→ Supabase (3,876 financial tables)\n\nIngestion toolkit: $97\nhttps://buy.stripe.com/3cs5kw6D627175pbcp5J60e",

    "Self-hosted embeddings on HuggingFace Spaces (free tier).\n\nWe replaced Jina API ($$$) with a Gradio Space running jina-v3.\n\nResult: Same quality, $0/month.\n\nThe setup guide is in our Engineering Handbook.\n\n$147 → https://buy.stripe.com/5kQeV6cXU9Xt0WY4h85J608",

    "Claude Code + 17 custom skills = autonomous AI engineering.\n\nOur skills handle:\n• Self-healing pipelines\n• Continuous eval loops\n• Cross-repo sync\n• Automated monitoring\n\nAll skills + setup guide: $47\nhttps://buy.stripe.com/fZu00c4vo5Hdd5J9Bo5J60i",

    "RAG evaluation is the most underrated skill in AI engineering.\n\nWe built a framework that:\n• Tests 61K questions in parallel\n• Compares F1/BLEU/semantic scores\n• Auto-generates dashboards\n• Tracks regressions across sessions\n\n$127 → https://buy.stripe.com/5kQ7sEaTMgzjgbV28g5J60a",

    "The #1 mistake in production RAG: not having a quantitative pipeline.\n\nFinancial tables, metrics, calculations — standard semantic search can't handle them.\n\nOur Quant pipeline hits 95.2% accuracy on FinQA benchmarks.\n\nFull architecture: $197\nhttps://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",

    "Open-source RAG is powerful but painful to debug.\n\nHere's what nobody tells you:\n• n8n disabled nodes still fire HTTP requests\n• Pinecone /records needs integrated inference\n• LiteLLM model aliases ≠ provider names\n• Supabase port 5432 ≠ 6543\n\nFull debug playbook: $47\nhttps://buy.stripe.com/8x214g8LEdnbbLBdky5J60h",
]

def oauth_sign(method, url, params, cs, ats):
    parts = sorted((urllib.parse.quote(k, ''), urllib.parse.quote(str(v), '')) for k, v in params.items())
    param_str = '&'.join(f'{k}={v}' for k, v in parts)
    base = f"{method}&{urllib.parse.quote(url, '')}&{urllib.parse.quote(param_str, '')}"
    key = f"{urllib.parse.quote(cs, '')}&{urllib.parse.quote(ats, '')}"
    return base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()

def post_tweet(text):
    url = 'https://api.twitter.com/2/tweets'
    body = json.dumps({'text': text}).encode()
    oa = {
        'oauth_consumer_key': CK, 'oauth_nonce': uuid.uuid4().hex,
        'oauth_signature_method': 'HMAC-SHA1', 'oauth_timestamp': str(int(time.time())),
        'oauth_token': AT, 'oauth_version': '1.0'
    }
    oa['oauth_signature'] = oauth_sign('POST', url, oa, CS, ATS)
    auth = 'OAuth ' + ', '.join(
        f'{urllib.parse.quote(k, "")}="{urllib.parse.quote(str(v), "")}"'
        for k, v in sorted(oa.items())
    )
    req = urllib.request.Request(url, data=body, headers={
        'Authorization': auth,
        'Content-Type': 'application/json'
    })
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode())

# Main loop
print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] Twitter poster started — {len(TWEETS)} tweets in rotation")
tweet_index = 0
INTERVAL = 1800  # 30 minutes between tweets

while True:
    tweet = TWEETS[tweet_index % len(TWEETS)]
    try:
        result = post_tweet(tweet)
        tweet_id = result.get('data', {}).get('id', '?')
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] POSTED tweet #{tweet_index+1} (ID: {tweet_id})")
        print(f"  {tweet[:80]}...")
        tweet_index += 1
    except Exception as e:
        body = e.read().decode()[:300] if hasattr(e, 'read') else str(e)
        print(f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] FAILED: {e}")
        print(f"  Body: {body}")
        # If rate limited, wait longer
        if '429' in str(e):
            print("  Rate limited — waiting 15 minutes")
            time.sleep(900)
            continue

    time.sleep(INTERVAL)
