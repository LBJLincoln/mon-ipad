#!/usr/bin/env python3
"""COMMUNICATION Agent — Social media, content generation, Telegram broadcasts.

Posts updates to Twitter/X and Telegram channel.
Generates content via LiteLLM.
"""

import json
import os
import sys
import hashlib
import hmac
import time
import base64
import urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base import load_env, llm_call, telegram_notify, log_event, http_get, http_post, run_agent_loop, ctx
import urllib.request

CATEGORY = "communication"


def generate_content():
    """Generate a social media post about Nomos AI."""
    prompt = """Genere UN tweet (max 280 chars) pour promouvoir Nomos AI — assistant IA expert sectoriel.

Contexte:
- 4 secteurs: Finance, BTP, Juridique, Industrie
- 4 pipelines RAG: Standard (recherche vectorielle), Graph (relations entites), Quantitative (donnees chiffrees), Orchestrator (routage intelligent)
- 13 fournisseurs LLM en fallback automatique
- Self-hosted sur HuggingFace Spaces
- Nomos42.vercel.app

Ton: professionnel mais accessible. Pas de hashtags excessifs. En francais.
Reponds UNIQUEMENT avec le texte du tweet, rien d'autre."""

    return llm_call(prompt, temperature=0.7, max_tokens=100)


def post_to_telegram_channel(message):
    """Post to @Nomos42 Telegram channel."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "@Nomos42")

    if not token:
        return {"telegram": "NO_TOKEN"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({
        "chat_id": channel,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }).encode()

    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"telegram": "sent", "status": resp.status}
    except Exception as e:
        return {"telegram": f"error: {e}"}


def _oauth1_sign(method, url, params, consumer_key, consumer_secret, token, token_secret):
    """Generate OAuth 1.0a signature for Twitter API."""
    import urllib.parse
    # Sort and encode params
    sorted_params = sorted(params.items())
    param_string = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params)

    base_string = f"{method.upper()}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
    signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"

    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()

    return signature


def post_to_twitter(text):
    """Post tweet via Twitter API v2 with OAuth 1.0a."""
    consumer_key = os.environ.get("TWITTER_CONSUMER_KEY", "")
    consumer_secret = os.environ.get("TWITTER_CONSUMER_SECRET", "")
    access_token = os.environ.get("TWITTER_ACCESS_TOKEN", "")
    access_secret = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")

    if not all([consumer_key, consumer_secret, access_token, access_secret]):
        return {"twitter": "MISSING_KEYS"}

    url = "https://api.twitter.com/2/tweets"
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": hashlib.sha256(str(time.time()).encode()).hexdigest()[:32],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    signature = _oauth1_sign("POST", url, oauth_params, consumer_key, consumer_secret, access_token, access_secret)
    oauth_params["oauth_signature"] = signature

    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )

    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": auth_header,
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            result = json.loads(resp.read())
            return {"twitter": "posted", "tweet_id": result.get("data", {}).get("id")}
    except Exception as e:
        return {"twitter": f"error: {e}"}


def tick():
    """One communication cycle."""
    print("  Generating content...")
    content = generate_content()

    if content.startswith("LLM_ERROR"):
        print(f"  Content generation failed: {content}")
        return {"error": content}

    print(f"  Content: {content[:100]}...")

    # Post to Telegram channel
    print("  Posting to Telegram channel...")
    tg_result = post_to_telegram_channel(content)
    print(f"  Telegram: {tg_result}")

    # NOTE: Twitter posting is disabled by default to avoid spam
    # Uncomment to enable: tw_result = post_to_twitter(content)
    tw_result = {"twitter": "disabled_by_default"}

    report = {
        "content": content,
        "telegram": tg_result,
        "twitter": tw_result,
    }

    return report


if __name__ == "__main__":
    # Every 12 hours — we don't want to spam
    run_agent_loop(CATEGORY, tick, interval=43200)
