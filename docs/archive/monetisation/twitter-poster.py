#!/usr/bin/env python3
"""Twitter/X Auto-Poster for Nomos RAG Products.

Posts tweets using Twitter API v2 with OAuth 1.0a authentication.
Uses only stdlib — no external dependencies.

Usage:
    source .env.local
    python3 monetisation/twitter-poster.py --list              # List all tweets
    python3 monetisation/twitter-poster.py --verify            # Check credentials
    python3 monetisation/twitter-poster.py --post              # Post next tweet
    python3 monetisation/twitter-poster.py --thread 0          # Post tweet #0 as thread
    python3 monetisation/twitter-poster.py --schedule           # Post one per hour
    python3 monetisation/twitter-poster.py --schedule --interval 1800  # Every 30 min
    python3 monetisation/twitter-poster.py --reset             # Reset posted history

Environment variables required:
    TWITTER_CONSUMER_KEY
    TWITTER_CONSUMER_SECRET
    TWITTER_ACCESS_TOKEN
    TWITTER_ACCESS_TOKEN_SECRET
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".twitter-state.json")

TWITTER_API_BASE = "https://api.twitter.com"
TWEETS_ENDPOINT = f"{TWITTER_API_BASE}/2/tweets"
VERIFY_ENDPOINT = f"{TWITTER_API_BASE}/2/users/me"

# Stripe payment links
LINKS = {
    "mega_bundle":  "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
    "architecture": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
    "n8n_workflows": "https://buy.stripe.com/dRm8wI1jcerf1148B85J609",
    "eval_framework": "https://buy.stripe.com/5kQ7sEaTMgzjgbV28g5J60a",
    "engineering":  "https://buy.stripe.com/5kQeV6cXU9Xt0WY4h85J608",
    "ingestion":    "https://buy.stripe.com/3cs5kw6D627175pbcp5J60e",
    "dashboard":    "https://buy.stripe.com/bJe00c0f84Dh4j96sz5J60f",
    "debug_playbook": "https://buy.stripe.com/8x214g8LEdnbbLBdky5J60h",
    "claude_skills": "https://buy.stripe.com/fZu00c4vo5Hdd5J9Bo5J60i",
    "enterprise_site": "https://buy.stripe.com/fZu5kwgaacjb4j99Bo5J607",
}

# ---------------------------------------------------------------------------
# Tweet Catalog — 15 pre-written tweets with Stripe links
# ---------------------------------------------------------------------------

TWEET_CATALOG = [
    # 0 — MEGA BUNDLE highlight
    {
        "text": (
            "We tested 61,661 RAG questions across 4 pipelines.\n\n"
            "Results:\n"
            "  Standard: 87.5% accuracy\n"
            "  Quantitative: 95.2%\n"
            "  Graph: 40.9% (improving)\n\n"
            "Everything we built is in the MEGA BUNDLE ($497):\n"
            "7 n8n workflows, eval framework, debug playbook, dashboard, and more.\n\n"
            f"{LINKS['mega_bundle']}"
        ),
        "tags": ["mega_bundle", "results"],
    },
    # 1 — Architecture Blueprint
    {
        "text": (
            "Most RAG systems use one pipeline. That's why they fail.\n\n"
            "We built 4 specialized ones:\n"
            "  Standard (semantic search)\n"
            "  Graph (entity relationships)\n"
            "  Quantitative (SQL + tables)\n"
            "  Orchestrator (routing)\n\n"
            "Architecture blueprint ($197):\n"
            f"{LINKS['architecture']}"
        ),
        "tags": ["architecture", "pipelines"],
    },
    # 2 — Debug Playbook
    {
        "text": (
            "Debugging RAG pipelines is brutal.\n\n"
            "After 79+ fixes across 86 sessions, we compiled everything into a playbook:\n\n"
            "  Diagnostic flowcharts\n"
            "  79 documented fixes with root causes\n"
            "  n8n-specific gotchas\n"
            "  LLM behavior quirks\n\n"
            "Debug Playbook ($47):\n"
            f"{LINKS['debug_playbook']}"
        ),
        "tags": ["debug", "playbook"],
    },
    # 3 — n8n Workflows
    {
        "text": (
            "If you're building with n8n + RAG, this saves you weeks:\n\n"
            "7 production workflow files:\n"
            "  Standard RAG V3.4\n"
            "  Graph RAG V3.3\n"
            "  Quantitative RAG V3.1\n"
            "  Website pipelines (3)\n"
            "  Orchestrator\n\n"
            "All battle-tested on 61K questions.\n\n"
            "n8n Workflows ($197):\n"
            f"{LINKS['n8n_workflows']}"
        ),
        "tags": ["n8n", "workflows"],
    },
    # 4 — Ingestion Toolkit
    {
        "text": (
            "Building AI for enterprise sectors (BTP, Finance, Legal, Industry)?\n\n"
            "We ingested 11,387 docs across 4 French sectors into:\n"
            "  Pinecone (46K vectors)\n"
            "  Neo4j (79K nodes)\n"
            "  Supabase (3,876 financial tables)\n\n"
            "Ingestion toolkit ($97):\n"
            f"{LINKS['ingestion']}"
        ),
        "tags": ["ingestion", "data"],
    },
    # 5 — Self-hosted Embeddings
    {
        "text": (
            "Self-hosted embeddings on HuggingFace Spaces (free tier).\n\n"
            "We replaced Jina API ($$$) with a Gradio Space running jina-v3.\n\n"
            "Result: Same quality, $0/month.\n\n"
            "The setup guide is in our Engineering Handbook ($147):\n"
            f"{LINKS['engineering']}"
        ),
        "tags": ["embeddings", "engineering"],
    },
    # 6 — Claude Code Skills
    {
        "text": (
            "Claude Code + 17 custom skills = autonomous AI engineering.\n\n"
            "Our skills handle:\n"
            "  Self-healing pipelines\n"
            "  Continuous eval loops\n"
            "  Cross-repo sync\n"
            "  Automated monitoring\n\n"
            "All skills + setup guide ($47):\n"
            f"{LINKS['claude_skills']}"
        ),
        "tags": ["claude", "skills", "automation"],
    },
    # 7 — Eval Framework
    {
        "text": (
            "RAG evaluation is the most underrated skill in AI engineering.\n\n"
            "We built a framework that:\n"
            "  Tests 61K questions in parallel\n"
            "  Compares F1/BLEU/semantic scores\n"
            "  Auto-generates dashboards\n"
            "  Tracks regressions across sessions\n\n"
            "Eval Framework ($127):\n"
            f"{LINKS['eval_framework']}"
        ),
        "tags": ["eval", "framework", "testing"],
    },
    # 8 — Quantitative Pipeline
    {
        "text": (
            "The #1 mistake in production RAG: not having a quantitative pipeline.\n\n"
            "Financial tables, metrics, calculations -- standard semantic search can't handle them.\n\n"
            "Our Quant pipeline hits 95.2% accuracy on FinQA benchmarks.\n\n"
            "Full MEGA BUNDLE with all pipelines ($497):\n"
            f"{LINKS['mega_bundle']}"
        ),
        "tags": ["quant", "financial", "mega_bundle"],
    },
    # 9 — Open-source RAG gotchas
    {
        "text": (
            "Open-source RAG gotchas nobody tells you:\n\n"
            "  n8n disabled nodes still fire HTTP requests\n"
            "  Pinecone /records needs integrated inference\n"
            "  LiteLLM aliases != provider model names\n"
            "  Supabase port 5432 != 6543\n\n"
            "79 fixes documented ($47):\n"
            f"{LINKS['debug_playbook']}"
        ),
        "tags": ["debug", "gotchas"],
    },
    # 10 — Dashboard
    {
        "text": (
            "We built a live RAG metrics dashboard that tracks:\n\n"
            "  Pipeline accuracy over time\n"
            "  Response latency percentiles\n"
            "  Vector store coverage\n"
            "  Regression alerts\n\n"
            "HTML/JS, self-contained, no backend needed.\n\n"
            "Dashboard ($97):\n"
            f"{LINKS['dashboard']}"
        ),
        "tags": ["dashboard", "metrics"],
    },
    # 11 — Enterprise Site
    {
        "text": (
            "We built a Next.js enterprise site with 4 sector-specific AI chatbots.\n\n"
            "Each sector has:\n"
            "  Custom RAG pipeline routing\n"
            "  Sector-tuned prompts\n"
            "  Financial table rendering\n"
            "  Source attribution\n\n"
            "Enterprise Site template ($197):\n"
            f"{LINKS['enterprise_site']}"
        ),
        "tags": ["website", "enterprise"],
    },
    # 12 — 86 sessions deep
    {
        "text": (
            "86 sessions. 1,100+ commits. 61,661 evaluation questions.\n\n"
            "Building a production multi-pipeline RAG system from scratch "
            "taught us things no tutorial covers.\n\n"
            "We packaged all of it -- architecture, workflows, eval, debug, ingestion.\n\n"
            "MEGA BUNDLE ($497):\n"
            f"{LINKS['mega_bundle']}"
        ),
        "tags": ["mega_bundle", "story"],
    },
    # 13 — LiteLLM proxy
    {
        "text": (
            "Running 9 LLM models at $0/month.\n\n"
            "Our LiteLLM proxy on HuggingFace Spaces routes to:\n"
            "  Llama 3.3 70B (free)\n"
            "  Gemma 3 27B (free)\n"
            "  Trinity Large (free)\n\n"
            "Setup included in the Engineering Handbook ($147):\n"
            f"{LINKS['engineering']}"
        ),
        "tags": ["litellm", "cost"],
    },
    # 14 — Graph pipeline honesty
    {
        "text": (
            "Our Graph RAG scores 40.9%. We're not hiding it.\n\n"
            "Standard: 87.5%. Quant: 95.2%.\n"
            "Graph is hardest -- entity linking, multi-hop reasoning.\n\n"
            "CRAG grading shipping next to filter bad retrievals.\n\n"
            "Architecture Blueprint ($197):\n"
            f"{LINKS['architecture']}"
        ),
        "tags": ["graph", "transparency"],
    },
]

# Thread templates — multi-tweet threads
THREAD_CATALOG = [
    {
        "name": "rag_architecture",
        "tweets": [
            (
                "We built a multi-pipeline RAG system from scratch.\n\n"
                "86 sessions. 1,100+ commits. 61,661 eval questions.\n\n"
                "Here's what the architecture looks like (thread):"
            ),
            (
                "Pipeline 1: Standard RAG (87.5% accuracy)\n\n"
                "Jina v3 embeddings -> Pinecone vector search -> "
                "LLM reranking -> answer generation.\n\n"
                "Good for: factual lookups, document QA, general knowledge."
            ),
            (
                "Pipeline 2: Graph RAG (40.9%, improving)\n\n"
                "Neo4j knowledge graph -> entity resolution -> "
                "relationship traversal -> multi-hop reasoning.\n\n"
                "Good for: \"Who is connected to X?\" and relationship questions."
            ),
            (
                "Pipeline 3: Quantitative RAG (95.2% accuracy)\n\n"
                "SQL generation -> Supabase financial tables -> "
                "calculation engine -> formatted output.\n\n"
                "Good for: \"What was revenue in Q3?\" and any numbers question."
            ),
            (
                "Pipeline 4: Orchestrator (ON HOLD)\n\n"
                "Intelligent router that picks the right pipeline per question.\n\n"
                "Uses intent classification + confidence scoring. "
                "Coming in Phase 5."
            ),
            (
                "Everything is packaged and available:\n\n"
                f"  MEGA BUNDLE (all pipelines): {LINKS['mega_bundle']}\n"
                f"  Architecture Blueprint: {LINKS['architecture']}\n"
                f"  Eval Framework: {LINKS['eval_framework']}\n\n"
                "Built with n8n, Pinecone, Neo4j, Supabase, LiteLLM."
            ),
        ],
    },
    {
        "name": "debugging_story",
        "tweets": [
            (
                "79 bugs fixed across 86 sessions of RAG development.\n\n"
                "Here are the worst ones we hit (thread):"
            ),
            (
                "Bug #1: n8n disabled nodes still fire HTTP requests.\n\n"
                "We disabled a node to skip it. Data passed through fine. "
                "But the HTTP Request inside? Still fires. Still costs tokens.\n\n"
                "Fix: delete the node entirely, or route around it."
            ),
            (
                "Bug #2: Supabase port 5432 vs 6543.\n\n"
                "Session pooler (5432) works with psycopg2.\n"
                "Transaction pooler (6543) silently drops inserts.\n\n"
                "We lost hours of ingestion data before catching this."
            ),
            (
                "Bug #3: LiteLLM model aliases != provider names.\n\n"
                "We configured 'gemma-3-27b-it:free' in n8n.\n"
                "LiteLLM expected 'gemma-27b' (its alias).\n\n"
                "Result: HTTP 500 on every Quant query until we mapped it."
            ),
            (
                "All 79 fixes with root causes, diagnostic flowcharts, "
                "and prevention strategies:\n\n"
                f"Debug Playbook ($47): {LINKS['debug_playbook']}\n\n"
                "If you're building RAG in production, this will save you days."
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# OAuth 1.0a Signature (RFC 5849)
# ---------------------------------------------------------------------------

def percent_encode(s: str) -> str:
    """RFC 5849 percent-encoding."""
    return urllib.parse.quote(str(s), safe="")


def generate_oauth_signature(method: str, url: str, params: dict,
                              consumer_secret: str, token_secret: str) -> str:
    """Generate HMAC-SHA1 signature for OAuth 1.0a."""
    # Sort parameters and build parameter string
    sorted_params = sorted(
        (percent_encode(k), percent_encode(v)) for k, v in params.items()
    )
    param_string = "&".join(f"{k}={v}" for k, v in sorted_params)

    # Build signature base string
    base_string = f"{method.upper()}&{percent_encode(url)}&{percent_encode(param_string)}"

    # Build signing key
    signing_key = f"{percent_encode(consumer_secret)}&{percent_encode(token_secret)}"

    # HMAC-SHA1
    hashed = hmac.new(
        signing_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha1,
    )
    return base64.b64encode(hashed.digest()).decode("utf-8")


def build_oauth_header(method: str, url: str,
                        consumer_key: str, consumer_secret: str,
                        access_token: str, access_token_secret: str) -> str:
    """Build the full OAuth Authorization header value."""
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    oauth_params["oauth_signature"] = generate_oauth_signature(
        method, url, oauth_params, consumer_secret, access_token_secret
    )

    # Build header string
    header_parts = []
    for key in sorted(oauth_params):
        header_parts.append(f'{percent_encode(key)}="{percent_encode(oauth_params[key])}"')

    return "OAuth " + ", ".join(header_parts)


# ---------------------------------------------------------------------------
# Twitter API calls
# ---------------------------------------------------------------------------

def twitter_request(method: str, url: str, body: dict = None,
                     consumer_key: str = "", consumer_secret: str = "",
                     access_token: str = "", access_token_secret: str = "") -> dict:
    """Make an authenticated request to the Twitter API."""
    auth_header = build_oauth_header(
        method, url,
        consumer_key, consumer_secret,
        access_token, access_token_secret,
    )

    headers = {"Authorization": auth_header}

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {
                "status": resp.status,
                "data": json.loads(resp.read().decode("utf-8")),
            }
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        return {
            "status": e.code,
            "error": str(e),
            "body": error_body,
        }


def verify_credentials(creds: dict) -> bool:
    """Verify Twitter credentials and check permissions."""
    print("Verifying Twitter credentials...")
    print()

    result = twitter_request(
        "GET", VERIFY_ENDPOINT,
        consumer_key=creds["ck"], consumer_secret=creds["cs"],
        access_token=creds["at"], access_token_secret=creds["ats"],
    )

    if result["status"] == 200:
        user_data = result["data"].get("data", {})
        username = user_data.get("username", "unknown")
        name = user_data.get("name", "unknown")
        user_id = user_data.get("id", "unknown")
        print(f"  Authenticated as: @{username} ({name})")
        print(f"  User ID: {user_id}")
        print(f"  Status: credentials valid")
        print()
    elif result["status"] == 401:
        print("  FAILED: Invalid credentials (HTTP 401)")
        print(f"  Response: {result.get('body', '')[:200]}")
        print()
        print("  Check that your environment variables are set correctly:")
        print("    TWITTER_CONSUMER_KEY")
        print("    TWITTER_CONSUMER_SECRET")
        print("    TWITTER_ACCESS_TOKEN")
        print("    TWITTER_ACCESS_TOKEN_SECRET")
        return False
    elif result["status"] == 403:
        print("  FAILED: Access forbidden (HTTP 403)")
        print(f"  Response: {result.get('body', '')[:200]}")
        print()
        _print_permissions_help()
        return False
    else:
        print(f"  FAILED: HTTP {result['status']}")
        print(f"  Response: {result.get('body', '')[:200]}")
        return False

    # Now test write permissions with a dry check (we don't actually post)
    print("Checking write permissions...")
    print("  (Attempting to detect app permission level)")
    print()

    # We can infer permissions from the /2/users/me scopes, but the most
    # reliable way is to attempt a tweet and check for 403.
    # Instead, we'll just report the current state.
    print("  To test write access, use --post to attempt posting a tweet.")
    print("  If you get HTTP 403, your app needs Read+Write permissions.")
    print()
    _print_permissions_help()
    return True


def post_tweet(text: str, creds: dict, reply_to: str = None) -> dict:
    """Post a tweet. Returns the API response dict."""
    body = {"text": text}
    if reply_to:
        body["reply"] = {"in_reply_to_tweet_id": reply_to}

    result = twitter_request(
        "POST", TWEETS_ENDPOINT, body=body,
        consumer_key=creds["ck"], consumer_secret=creds["cs"],
        access_token=creds["at"], access_token_secret=creds["ats"],
    )

    if result["status"] == 201:
        tweet_data = result["data"].get("data", {})
        tweet_id = tweet_data.get("id", "unknown")
        print(f"  Posted tweet ID: {tweet_id}")
        return {"success": True, "tweet_id": tweet_id, "data": result["data"]}

    if result["status"] == 403:
        print(f"  FAILED: HTTP 403 Forbidden")
        print()
        error_body = result.get("body", "")
        try:
            err_json = json.loads(error_body)
            detail = err_json.get("detail", "")
            title = err_json.get("title", "")
            print(f"  Error: {title}")
            print(f"  Detail: {detail}")
        except (json.JSONDecodeError, ValueError):
            print(f"  Response: {error_body[:300]}")
        print()
        print("=" * 60)
        print("  YOUR APP DOES NOT HAVE WRITE PERMISSIONS")
        print("=" * 60)
        print()
        _print_permissions_help()
        return {"success": False, "status": 403}

    if result["status"] == 429:
        print(f"  RATE LIMITED (HTTP 429)")
        print(f"  Response: {result.get('body', '')[:200]}")
        return {"success": False, "status": 429}

    print(f"  FAILED: HTTP {result['status']}")
    print(f"  Response: {result.get('body', '')[:300]}")
    return {"success": False, "status": result["status"]}


def post_thread(tweets: list, creds: dict) -> list:
    """Post a thread (list of tweet texts). Each replies to the previous."""
    posted = []
    reply_to = None

    for i, text in enumerate(tweets):
        print(f"  Posting tweet {i + 1}/{len(tweets)}...")
        result = post_tweet(text, creds, reply_to=reply_to)

        if not result.get("success"):
            print(f"  Thread stopped at tweet {i + 1} due to error.")
            break

        posted.append(result["tweet_id"])
        reply_to = result["tweet_id"]

        # Small delay between tweets to avoid rate limits
        if i < len(tweets) - 1:
            time.sleep(2)

    return posted


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load the state file tracking posted tweets."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "posted_tweets": [],  # list of {index, tweet_id, timestamp, text_preview}
        "posted_threads": [],  # list of {name, tweet_ids, timestamp}
        "next_index": 0,
    }


def save_state(state: dict):
    """Save state to the JSON file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_next_tweet_index(state: dict) -> int:
    """Get the next tweet index to post, wrapping around the catalog."""
    posted_indices = {entry["index"] for entry in state["posted_tweets"]}

    # Find the first unposted tweet
    for i in range(len(TWEET_CATALOG)):
        idx = (state["next_index"] + i) % len(TWEET_CATALOG)
        if idx not in posted_indices:
            return idx

    # All tweets posted — reset and start from the beginning
    print("  All tweets have been posted. Starting a new rotation.")
    state["posted_tweets"] = []
    save_state(state)
    return state["next_index"] % len(TWEET_CATALOG)


# ---------------------------------------------------------------------------
# Permissions help
# ---------------------------------------------------------------------------

def _print_permissions_help():
    """Print instructions for fixing app permissions."""
    print("  To fix this, update your app permissions at developer.twitter.com:")
    print()
    print("  1. Go to https://developer.twitter.com/en/portal/projects-and-apps")
    print("  2. Select your app")
    print("  3. Go to 'Settings' tab")
    print("  4. Under 'App permissions', click 'Edit'")
    print("  5. Select 'Read and Write' (or 'Read and Write and Direct Messages')")
    print("  6. Save the changes")
    print("  7. IMPORTANT: After changing permissions, you MUST regenerate")
    print("     your Access Token and Secret under the 'Keys and tokens' tab")
    print("  8. Update your environment variables with the new tokens")
    print()
    print("  Note: Regenerating tokens is mandatory. Old tokens retain the")
    print("  old permission level even after you change app settings.")
    print()


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_list():
    """List all tweets in the catalog with their post status."""
    state = load_state()
    posted_indices = {entry["index"] for entry in state["posted_tweets"]}

    print(f"Tweet Catalog ({len(TWEET_CATALOG)} tweets)")
    print("=" * 70)

    for i, tweet in enumerate(TWEET_CATALOG):
        status = "POSTED" if i in posted_indices else "PENDING"
        preview = tweet["text"][:80].replace("\n", " ")
        tags = ", ".join(tweet["tags"])
        char_count = len(tweet["text"])
        print(f"\n  [{i:2d}] [{status:7s}] ({char_count} chars) [{tags}]")
        print(f"       {preview}...")

    print()
    print(f"Thread Catalog ({len(THREAD_CATALOG)} threads)")
    print("=" * 70)
    posted_thread_names = {entry["name"] for entry in state.get("posted_threads", [])}
    for i, thread in enumerate(THREAD_CATALOG):
        status = "POSTED" if thread["name"] in posted_thread_names else "PENDING"
        print(f"\n  [{i:2d}] [{status:7s}] \"{thread['name']}\" ({len(thread['tweets'])} tweets)")
        for j, t in enumerate(thread["tweets"]):
            preview = t[:70].replace("\n", " ")
            print(f"       {j + 1}. {preview}...")

    print()
    next_idx = get_next_tweet_index(state)
    print(f"Next tweet to post: #{next_idx}")
    print(f"State file: {STATE_FILE}")
    print()


def cmd_post(creds: dict, index: int = None):
    """Post the next tweet (or a specific one by index)."""
    state = load_state()

    if index is not None:
        if index < 0 or index >= len(TWEET_CATALOG):
            print(f"Error: Tweet index {index} out of range (0-{len(TWEET_CATALOG) - 1})")
            sys.exit(1)
        idx = index
    else:
        idx = get_next_tweet_index(state)

    tweet = TWEET_CATALOG[idx]
    print(f"Posting tweet #{idx}...")
    print(f"  Tags: {', '.join(tweet['tags'])}")
    print(f"  Length: {len(tweet['text'])} chars")
    print(f"  Preview: {tweet['text'][:80].replace(chr(10), ' ')}...")
    print()

    result = post_tweet(tweet["text"], creds)

    if result.get("success"):
        state["posted_tweets"].append({
            "index": idx,
            "tweet_id": result["tweet_id"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "text_preview": tweet["text"][:60],
        })
        state["next_index"] = (idx + 1) % len(TWEET_CATALOG)
        save_state(state)
        print()
        print(f"  Tweet #{idx} posted successfully.")
        print(f"  URL: https://twitter.com/i/status/{result['tweet_id']}")
    else:
        print()
        print(f"  Tweet #{idx} failed to post.")
        sys.exit(1)


def cmd_thread(creds: dict, thread_index: int):
    """Post a thread by index."""
    if thread_index < 0 or thread_index >= len(THREAD_CATALOG):
        print(f"Error: Thread index {thread_index} out of range (0-{len(THREAD_CATALOG) - 1})")
        sys.exit(1)

    thread = THREAD_CATALOG[thread_index]
    state = load_state()

    print(f"Posting thread: \"{thread['name']}\" ({len(thread['tweets'])} tweets)")
    print()

    tweet_ids = post_thread(thread["tweets"], creds)

    if tweet_ids:
        state.setdefault("posted_threads", []).append({
            "name": thread["name"],
            "tweet_ids": tweet_ids,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        save_state(state)
        print()
        print(f"  Thread \"{thread['name']}\" posted ({len(tweet_ids)}/{len(thread['tweets'])} tweets).")
        if tweet_ids:
            print(f"  URL: https://twitter.com/i/status/{tweet_ids[0]}")
    else:
        print()
        print(f"  Thread failed to post.")
        sys.exit(1)


def cmd_schedule(creds: dict, interval: int = 3600):
    """Post one tweet per interval (default: 1 hour)."""
    print(f"Schedule mode: posting one tweet every {interval}s ({interval // 60} min)")
    print(f"Catalog size: {len(TWEET_CATALOG)} tweets")
    print(f"Press Ctrl+C to stop.")
    print()

    while True:
        state = load_state()
        idx = get_next_tweet_index(state)
        tweet = TWEET_CATALOG[idx]

        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        print(f"[{ts}] Posting tweet #{idx}...")

        result = post_tweet(tweet["text"], creds)

        if result.get("success"):
            state["posted_tweets"].append({
                "index": idx,
                "tweet_id": result["tweet_id"],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "text_preview": tweet["text"][:60],
            })
            state["next_index"] = (idx + 1) % len(TWEET_CATALOG)
            save_state(state)
            print(f"  URL: https://twitter.com/i/status/{result['tweet_id']}")
        elif result.get("status") == 403:
            print("  Stopping schedule due to permission error.")
            sys.exit(1)
        elif result.get("status") == 429:
            wait = interval * 2
            print(f"  Rate limited. Waiting {wait}s before retrying...")
            time.sleep(wait)
            continue
        else:
            print(f"  Failed. Will retry next cycle.")

        posted_count = len(state["posted_tweets"])
        remaining = len(TWEET_CATALOG) - len({e["index"] for e in state["posted_tweets"]})
        next_time = time.strftime("%H:%M:%S", time.localtime(time.time() + interval))
        print(f"  Posted total: {posted_count} | Remaining in rotation: {remaining}")
        print(f"  Next tweet at: {next_time}")
        print()

        time.sleep(interval)


def cmd_reset():
    """Reset the state file."""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print(f"State file deleted: {STATE_FILE}")
    else:
        print("No state file found.")
    print("Post history cleared. Next --post will start from tweet #0.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Twitter/X Auto-Poster for Nomos RAG Products",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --list                    List all tweets and status\n"
            "  %(prog)s --verify                  Check credentials\n"
            "  %(prog)s --post                    Post next tweet in rotation\n"
            "  %(prog)s --post --index 3          Post tweet #3 specifically\n"
            "  %(prog)s --thread 0                Post thread #0\n"
            "  %(prog)s --schedule                Post one per hour\n"
            "  %(prog)s --schedule --interval 1800  Post every 30 min\n"
            "  %(prog)s --reset                   Clear post history\n"
        ),
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all tweets in catalog")
    group.add_argument("--verify", action="store_true", help="Verify credentials")
    group.add_argument("--post", action="store_true", help="Post next tweet")
    group.add_argument("--thread", type=int, metavar="N", help="Post thread #N")
    group.add_argument("--schedule", action="store_true", help="Post one per hour")
    group.add_argument("--reset", action="store_true", help="Reset post history")

    parser.add_argument("--index", type=int, metavar="N",
                        help="Specific tweet index (with --post)")
    parser.add_argument("--interval", type=int, default=3600,
                        help="Seconds between tweets in schedule mode (default: 3600)")

    args = parser.parse_args()

    # --list and --reset don't need credentials
    if args.list:
        cmd_list()
        return

    if args.reset:
        cmd_reset()
        return

    # All other commands need credentials
    creds = {
        "ck": os.environ.get("TWITTER_CONSUMER_KEY", ""),
        "cs": os.environ.get("TWITTER_CONSUMER_SECRET", ""),
        "at": os.environ.get("TWITTER_ACCESS_TOKEN", ""),
        "ats": os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", ""),
    }

    missing = [name for name, val in [
        ("TWITTER_CONSUMER_KEY", creds["ck"]),
        ("TWITTER_CONSUMER_SECRET", creds["cs"]),
        ("TWITTER_ACCESS_TOKEN", creds["at"]),
        ("TWITTER_ACCESS_TOKEN_SECRET", creds["ats"]),
    ] if not val]

    if missing:
        print("ERROR: Missing required environment variables:")
        for m in missing:
            print(f"  {m}")
        print()
        print("Set them with: source .env.local")
        print("Or export them individually:")
        for m in missing:
            print(f"  export {m}='your-value-here'")
        sys.exit(1)

    if args.verify:
        success = verify_credentials(creds)
        sys.exit(0 if success else 1)

    if args.post:
        cmd_post(creds, index=args.index)
        return

    if args.thread is not None:
        cmd_thread(creds, args.thread)
        return

    if args.schedule:
        cmd_schedule(creds, interval=args.interval)
        return


if __name__ == "__main__":
    main()
