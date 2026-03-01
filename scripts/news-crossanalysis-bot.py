#!/usr/bin/env python3
"""
News Cross-Analysis Telegram Bot — Cadeau pour Papa
====================================================
Aggregates major US news media via RSS feeds, provides:
- /briefing  — Daily news briefing across all sources
- /topics    — Trending topics (cross-source analysis)
- /compare   — How different outlets cover the same story
- /search    — Find articles by keyword across all sources
- /sources   — List all connected media sources
- /digest    — Deep analysis of top 3 stories

Sources: CNN, NYT, Washington Post, AP, Reuters, Bloomberg,
         NPR, BBC News, Fox News, The Guardian US, PBS, ABC News

Built: 2026-02-28
"""

import asyncio
import hashlib
import html
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError

# ─── Config ──────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_NEWS_BOT_TOKEN", "")
if not BOT_TOKEN:
    # Try loading from .env.local
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("TELEGRAM_NEWS_BOT_TOKEN="):
                    BOT_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")

if not BOT_TOKEN:
    print("ERROR: Set TELEGRAM_NEWS_BOT_TOKEN in environment or .env.local")
    sys.exit(1)

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("news-bot")

# ─── RSS Sources (major US + international English-language media) ─
RSS_SOURCES = {
    "CNN": {
        "feeds": [
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "http://rss.cnn.com/rss/cnn_world.rss",
        ],
        "icon": "🔴",
        "bias": "center-left",
    },
    "NYT": {
        "feeds": [
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        ],
        "icon": "📰",
        "bias": "center-left",
    },
    "Washington Post": {
        "feeds": [
            "https://feeds.washingtonpost.com/rss/national",
            "https://feeds.washingtonpost.com/rss/world",
        ],
        "icon": "🏛️",
        "bias": "center-left",
    },
    "AP News": {
        "feeds": [
            "https://rsshub.app/apnews/topics/apf-topnews",
        ],
        "icon": "⚡",
        "bias": "center",
    },
    "Reuters": {
        "feeds": [
            "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best",
        ],
        "icon": "🌐",
        "bias": "center",
    },
    "Bloomberg": {
        "feeds": [
            "https://feeds.bloomberg.com/markets/news.rss",
        ],
        "icon": "💹",
        "bias": "center-right",
    },
    "NPR": {
        "feeds": [
            "https://feeds.npr.org/1001/rss.xml",
            "https://feeds.npr.org/1004/rss.xml",
        ],
        "icon": "🎙️",
        "bias": "center-left",
    },
    "BBC News": {
        "feeds": [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
        ],
        "icon": "🇬🇧",
        "bias": "center",
    },
    "Fox News": {
        "feeds": [
            "https://moxie.foxnews.com/google-publisher/latest.xml",
        ],
        "icon": "🦊",
        "bias": "right",
    },
    "The Guardian US": {
        "feeds": [
            "https://www.theguardian.com/us-news/rss",
            "https://www.theguardian.com/world/rss",
        ],
        "icon": "🔵",
        "bias": "left",
    },
    "PBS": {
        "feeds": [
            "https://www.pbs.org/newshour/feeds/rss/headlines",
        ],
        "icon": "📺",
        "bias": "center",
    },
    "ABC News": {
        "feeds": [
            "https://abcnews.go.com/abcnews/topstories",
        ],
        "icon": "🔶",
        "bias": "center",
    },
}

# ─── Cache ───────────────────────────────────────────────────
_article_cache = {}  # source -> [articles]
_cache_ts = 0
CACHE_TTL = 300  # 5 minutes

# ─── Stopwords for topic extraction ─────────────────────────
STOPWORDS = set(
    "the a an and or but in on at to for of is it that this was were be been "
    "being have has had do does did will would shall should may might can could "
    "with from by as are not no nor so if then than too very just about above "
    "after again all also am any because before between both each few more most "
    "other over own same she some such their them there these they through under "
    "until up we what when where which while who whom why how its our you your "
    "he him his her new said says one two three many much get got us into out "
    "been going made make way even first still back now day time year years old "
    "long last great big high right left part think come could know take people "
    "like want give use find tell ask work seem feel try leave call good need "
    "become keep let begin show hear play run move live believe bring happen "
    "must set write provide sit stand lose pay meet include continue after".split()
)


# ═══════════════════════════════════════════════════════════════
# RSS Fetching
# ═══════════════════════════════════════════════════════════════

def fetch_rss(url, timeout=10):
    """Fetch and parse an RSS feed, return list of articles."""
    articles = []
    try:
        req = Request(url, headers={"User-Agent": "NewsBot/1.0"})
        resp = urlopen(req, timeout=timeout)
        data = resp.read().decode("utf-8", errors="replace")
        root = ET.fromstring(data)

        # Handle both RSS 2.0 and Atom formats
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # RSS 2.0
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc = item.findtext("description", "").strip()
            pub_date = item.findtext("pubDate", "").strip()

            # Clean HTML from description
            desc = re.sub(r"<[^>]+>", "", desc)
            desc = html.unescape(desc)
            if len(desc) > 300:
                desc = desc[:297] + "..."

            if title:
                articles.append({
                    "title": html.unescape(title),
                    "link": link,
                    "description": desc,
                    "published": pub_date,
                })

        # Atom format
        if not articles:
            for entry in root.findall("atom:entry", ns):
                title = entry.findtext("atom:title", "", ns).strip()
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                summary = entry.findtext("atom:summary", "", ns).strip()
                updated = entry.findtext("atom:updated", "", ns).strip()

                summary = re.sub(r"<[^>]+>", "", summary)
                summary = html.unescape(summary)
                if len(summary) > 300:
                    summary = summary[:297] + "..."

                if title:
                    articles.append({
                        "title": html.unescape(title),
                        "link": link,
                        "description": summary,
                        "published": updated,
                    })

    except Exception as e:
        log.warning(f"RSS fetch failed for {url}: {e}")

    return articles[:20]  # Max 20 per feed


def fetch_all_sources(force=False):
    """Fetch all RSS sources, with caching."""
    global _article_cache, _cache_ts

    if not force and time.time() - _cache_ts < CACHE_TTL and _article_cache:
        return _article_cache

    log.info("Fetching all RSS sources...")
    all_articles = {}

    for source_name, config in RSS_SOURCES.items():
        source_articles = []
        for feed_url in config["feeds"]:
            articles = fetch_rss(feed_url)
            for a in articles:
                a["source"] = source_name
                a["icon"] = config["icon"]
                a["bias"] = config["bias"]
            source_articles.extend(articles)
        all_articles[source_name] = source_articles
        log.info(f"  {source_name}: {len(source_articles)} articles")

    _article_cache = all_articles
    _cache_ts = time.time()
    return all_articles


# ═══════════════════════════════════════════════════════════════
# Analysis Engine
# ═══════════════════════════════════════════════════════════════

def extract_keywords(text, min_len=3):
    """Extract meaningful keywords from text."""
    words = re.findall(r"[A-Za-z'']+", text.lower())
    return [w for w in words if len(w) >= min_len and w not in STOPWORDS]


def find_trending_topics(all_articles, top_n=10):
    """Find topics mentioned across multiple sources."""
    # Count keyword frequency across sources
    keyword_sources = defaultdict(set)  # keyword -> set of sources
    keyword_count = Counter()

    for source_name, articles in all_articles.items():
        for article in articles:
            text = f"{article['title']} {article.get('description', '')}"
            keywords = extract_keywords(text)
            for kw in set(keywords):  # unique per article
                keyword_sources[kw].add(source_name)
                keyword_count[kw] += 1

    # Score: prioritize keywords appearing in many different sources
    scored = []
    for kw, sources in keyword_sources.items():
        if len(sources) >= 2:  # At least 2 different sources
            score = len(sources) * 10 + keyword_count[kw]
            scored.append((kw, score, len(sources), keyword_count[kw]))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def find_related_articles(all_articles, keyword):
    """Find articles matching a keyword across all sources."""
    results = []
    kw_lower = keyword.lower()
    for source_name, articles in all_articles.items():
        for article in articles:
            text = f"{article['title']} {article.get('description', '')}".lower()
            if kw_lower in text:
                results.append(article)
    return results


def cross_source_analysis(all_articles, topic_keyword):
    """Analyze how different sources cover the same topic."""
    coverage = {}
    kw_lower = topic_keyword.lower()

    for source_name, articles in all_articles.items():
        matching = []
        for article in articles:
            text = f"{article['title']} {article.get('description', '')}".lower()
            if kw_lower in text:
                matching.append(article)
        if matching:
            coverage[source_name] = matching

    return coverage


def generate_briefing(all_articles):
    """Generate a cross-source news briefing."""
    # Get top stories (appear in most sources)
    title_hashes = defaultdict(list)  # simplified title -> [articles]

    for source_name, articles in all_articles.items():
        for article in articles:
            # Simplify title for matching
            simplified = re.sub(r"[^a-z0-9 ]", "", article["title"].lower())
            key_words = set(simplified.split()) - STOPWORDS
            if len(key_words) >= 2:
                # Use top 3 keywords as hash
                key = " ".join(sorted(list(key_words)[:5]))
                title_hashes[key].append(article)

    # Find stories covered by multiple sources
    multi_source = []
    seen_titles = set()
    for key, articles in title_hashes.items():
        sources = set(a["source"] for a in articles)
        if len(sources) >= 2:
            # Pick the best title (longest)
            best = max(articles, key=lambda a: len(a["title"]))
            if best["title"] not in seen_titles:
                seen_titles.add(best["title"])
                multi_source.append({
                    "title": best["title"],
                    "link": best["link"],
                    "sources": sorted(sources),
                    "count": len(sources),
                    "description": best.get("description", ""),
                })

    multi_source.sort(key=lambda x: x["count"], reverse=True)

    # Also get top story from each source
    top_per_source = {}
    for source_name, articles in all_articles.items():
        if articles:
            top_per_source[source_name] = articles[0]

    return multi_source[:10], top_per_source


# ═══════════════════════════════════════════════════════════════
# Telegram Bot
# ═══════════════════════════════════════════════════════════════

def tg_request(method, data=None, timeout=30):
    """Make a Telegram API request."""
    import json
    url = f"{TELEGRAM_API}/{method}"
    if data:
        payload = json.dumps(data).encode("utf-8")
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = Request(url)

    try:
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode())
    except Exception as e:
        log.error(f"Telegram API error ({method}): {e}")
        return None


def send_message(chat_id, text, parse_mode="HTML", disable_preview=True):
    """Send a message, splitting if too long."""
    MAX_LEN = 4000

    if len(text) <= MAX_LEN:
        return tg_request("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        })

    # Split on double newlines
    parts = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            parts.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        parts.append(current)

    for part in parts:
        tg_request("sendMessage", {
            "chat_id": chat_id,
            "text": part,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        })
        time.sleep(0.5)


def handle_start(chat_id):
    """Handle /start command."""
    text = (
        "📰 <b>News Cross-Analysis Bot</b>\n\n"
        "I aggregate news from <b>12 major US and international media</b> "
        "and provide cross-source analysis.\n\n"
        "<b>Commands:</b>\n"
        "📋 /briefing — Daily news briefing\n"
        "🔥 /topics — Trending topics across sources\n"
        "🔍 /compare <i>topic</i> — Cross-source coverage\n"
        "🔎 /search <i>keyword</i> — Search all sources\n"
        "📡 /sources — Connected media sources\n"
        "📊 /digest — Deep analysis top stories\n"
        "🔄 /refresh — Force refresh all feeds\n\n"
        "<i>Powered by RSS feeds from CNN, NYT, WaPo, AP, Reuters, "
        "Bloomberg, NPR, BBC, Fox News, The Guardian, PBS, ABC News</i>"
    )
    send_message(chat_id, text)


def handle_sources(chat_id):
    """Handle /sources command."""
    lines = ["📡 <b>Connected News Sources</b>\n"]
    for name, config in RSS_SOURCES.items():
        icon = config["icon"]
        bias = config["bias"]
        n_feeds = len(config["feeds"])
        lines.append(f"{icon} <b>{name}</b> — {bias} — {n_feeds} feed(s)")

    lines.append(f"\n<i>Total: {len(RSS_SOURCES)} sources</i>")
    send_message(chat_id, "\n".join(lines))


def handle_briefing(chat_id):
    """Handle /briefing command."""
    send_message(chat_id, "⏳ <i>Fetching news from 12 sources...</i>")
    all_articles = fetch_all_sources()

    multi_source, top_per_source = generate_briefing(all_articles)

    lines = [
        f"📋 <b>NEWS BRIEFING</b> — {datetime.now().strftime('%B %d, %Y %H:%M')}\n",
    ]

    # Multi-source stories
    if multi_source:
        lines.append("🔥 <b>TOP STORIES (multi-source)</b>\n")
        for i, story in enumerate(multi_source[:7], 1):
            sources_str = ", ".join(story["sources"][:4])
            if len(story["sources"]) > 4:
                sources_str += f" +{len(story['sources'])-4}"
            title = story["title"]
            link = story.get("link", "")
            if link:
                lines.append(f"{i}. <a href=\"{link}\">{title}</a>")
            else:
                lines.append(f"{i}. {title}")
            lines.append(f"   📌 <i>{sources_str}</i>\n")

    # Headlines per source
    lines.append("\n📰 <b>TOP HEADLINES BY SOURCE</b>\n")
    for source_name, article in sorted(top_per_source.items()):
        icon = RSS_SOURCES.get(source_name, {}).get("icon", "📄")
        title = article["title"][:80]
        link = article.get("link", "")
        if link:
            lines.append(f"{icon} <b>{source_name}</b>: <a href=\"{link}\">{title}</a>")
        else:
            lines.append(f"{icon} <b>{source_name}</b>: {title}")

    # Stats
    total = sum(len(arts) for arts in all_articles.values())
    active = sum(1 for arts in all_articles.values() if arts)
    lines.append(f"\n📊 <i>{total} articles from {active}/{len(RSS_SOURCES)} sources</i>")

    send_message(chat_id, "\n".join(lines))


def handle_topics(chat_id):
    """Handle /topics command."""
    send_message(chat_id, "⏳ <i>Analyzing trending topics...</i>")
    all_articles = fetch_all_sources()
    topics = find_trending_topics(all_articles)

    if not topics:
        send_message(chat_id, "No cross-source topics found. Try /refresh first.")
        return

    lines = [
        f"🔥 <b>TRENDING TOPICS</b> — {datetime.now().strftime('%H:%M')}\n",
        "<i>Topics mentioned across multiple news sources:</i>\n",
    ]

    for i, (keyword, score, n_sources, n_mentions) in enumerate(topics, 1):
        bar = "█" * min(n_sources, 10) + "░" * max(0, 10 - n_sources)
        lines.append(
            f"{i}. <b>{keyword.capitalize()}</b>\n"
            f"   {bar} {n_sources} sources, {n_mentions} mentions\n"
            f"   → /compare {keyword}"
        )

    lines.append(f"\n💡 <i>Use /compare &lt;topic&gt; for cross-source analysis</i>")
    send_message(chat_id, "\n".join(lines))


def handle_compare(chat_id, topic):
    """Handle /compare <topic> command."""
    if not topic:
        send_message(chat_id, "Usage: /compare <i>topic</i>\nExample: /compare ukraine")
        return

    send_message(chat_id, f"⏳ <i>Analyzing coverage of '{topic}'...</i>")
    all_articles = fetch_all_sources()
    coverage = cross_source_analysis(all_articles, topic)

    if not coverage:
        send_message(chat_id, f"No articles found about '{topic}'. Try a different keyword.")
        return

    lines = [
        f"🔍 <b>CROSS-SOURCE ANALYSIS: {topic.upper()}</b>\n",
        f"<i>Coverage across {len(coverage)} sources:</i>\n",
    ]

    # Sort by number of articles
    for source_name, articles in sorted(coverage.items(), key=lambda x: len(x[1]), reverse=True):
        icon = RSS_SOURCES.get(source_name, {}).get("icon", "📄")
        bias = RSS_SOURCES.get(source_name, {}).get("bias", "?")
        lines.append(f"{icon} <b>{source_name}</b> ({bias}) — {len(articles)} article(s)")
        for a in articles[:3]:
            title = a["title"][:70]
            link = a.get("link", "")
            if link:
                lines.append(f"   • <a href=\"{link}\">{title}</a>")
            else:
                lines.append(f"   • {title}")
        if len(articles) > 3:
            lines.append(f"   <i>...and {len(articles)-3} more</i>")
        lines.append("")

    # Coverage gap analysis
    not_covering = [s for s in RSS_SOURCES if s not in coverage]
    if not_covering:
        lines.append(f"⚠️ <b>Not covering this topic:</b> {', '.join(not_covering[:5])}")

    # Bias distribution
    bias_counts = Counter()
    for source_name in coverage:
        bias = RSS_SOURCES.get(source_name, {}).get("bias", "unknown")
        bias_counts[bias] += 1
    if bias_counts:
        bias_str = " | ".join(f"{b}: {c}" for b, c in sorted(bias_counts.items()))
        lines.append(f"\n📊 <b>Bias distribution:</b> {bias_str}")

    send_message(chat_id, "\n".join(lines))


def handle_search(chat_id, keyword):
    """Handle /search <keyword> command."""
    if not keyword:
        send_message(chat_id, "Usage: /search <i>keyword</i>\nExample: /search economy")
        return

    all_articles = fetch_all_sources()
    results = find_related_articles(all_articles, keyword)

    if not results:
        send_message(chat_id, f"No articles found for '{keyword}'.")
        return

    lines = [
        f"🔎 <b>SEARCH: {keyword}</b> — {len(results)} results\n",
    ]

    # Group by source
    by_source = defaultdict(list)
    for a in results:
        by_source[a["source"]].append(a)

    for source_name, articles in sorted(by_source.items()):
        icon = RSS_SOURCES.get(source_name, {}).get("icon", "📄")
        lines.append(f"\n{icon} <b>{source_name}</b>")
        for a in articles[:3]:
            title = a["title"][:70]
            link = a.get("link", "")
            if link:
                lines.append(f"  • <a href=\"{link}\">{title}</a>")
            else:
                lines.append(f"  • {title}")

    send_message(chat_id, "\n".join(lines))


def handle_digest(chat_id):
    """Handle /digest command — deep analysis."""
    send_message(chat_id, "⏳ <i>Building deep analysis digest...</i>")
    all_articles = fetch_all_sources()
    topics = find_trending_topics(all_articles, top_n=3)

    if not topics:
        send_message(chat_id, "Not enough data for digest. Try /refresh first.")
        return

    lines = [
        f"📊 <b>DEEP DIGEST</b> — {datetime.now().strftime('%B %d, %Y')}\n",
        "<i>In-depth cross-analysis of today's top 3 topics:</i>\n",
    ]

    for i, (keyword, score, n_sources, n_mentions) in enumerate(topics, 1):
        coverage = cross_source_analysis(all_articles, keyword)
        lines.append(f"{'─'*30}")
        lines.append(f"\n<b>#{i} {keyword.upper()}</b>")
        lines.append(f"📌 {n_sources} sources, {n_mentions} mentions\n")

        # How each source covers it
        for source_name, articles in sorted(coverage.items()):
            icon = RSS_SOURCES.get(source_name, {}).get("icon", "📄")
            bias = RSS_SOURCES.get(source_name, {}).get("bias", "?")
            best = articles[0]
            title = best["title"][:60]
            lines.append(f"{icon} {source_name} ({bias}): {title}")

        # Bias spread
        biases = [RSS_SOURCES.get(s, {}).get("bias", "?") for s in coverage]
        bias_set = set(biases)
        if len(bias_set) >= 3:
            lines.append(f"✅ <i>Broad coverage: {', '.join(sorted(bias_set))}</i>")
        elif len(bias_set) == 2:
            lines.append(f"⚠️ <i>Partial coverage: {', '.join(sorted(bias_set))}</i>")
        else:
            lines.append(f"🔴 <i>Narrow coverage: {', '.join(sorted(bias_set))}</i>")
        lines.append("")

    # Overall stats
    total = sum(len(arts) for arts in all_articles.values())
    active = sum(1 for arts in all_articles.values() if arts)
    lines.append(f"{'─'*30}")
    lines.append(f"\n📈 <b>Feed Health:</b> {active}/{len(RSS_SOURCES)} sources active, {total} total articles")

    send_message(chat_id, "\n".join(lines))


def handle_refresh(chat_id):
    """Handle /refresh command."""
    send_message(chat_id, "🔄 <i>Refreshing all feeds...</i>")
    all_articles = fetch_all_sources(force=True)
    total = sum(len(arts) for arts in all_articles.values())
    active = sum(1 for arts in all_articles.values() if arts)
    send_message(chat_id, f"✅ Refreshed! {total} articles from {active}/{len(RSS_SOURCES)} sources.")


def process_message(update):
    """Process a single Telegram update."""
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()

    if not chat_id or not text:
        return

    # Parse command
    if text.startswith("/"):
        parts = text.split(None, 1)
        cmd = parts[0].lower().split("@")[0]  # Handle @botname suffix
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/start" or cmd == "/help":
            handle_start(chat_id)
        elif cmd == "/sources":
            handle_sources(chat_id)
        elif cmd == "/briefing":
            handle_briefing(chat_id)
        elif cmd == "/topics":
            handle_topics(chat_id)
        elif cmd == "/compare":
            handle_compare(chat_id, arg)
        elif cmd == "/search":
            handle_search(chat_id, arg)
        elif cmd == "/digest":
            handle_digest(chat_id)
        elif cmd == "/refresh":
            handle_refresh(chat_id)
        else:
            send_message(chat_id, "Unknown command. Use /help to see available commands.")
    else:
        # Treat free text as a search
        handle_search(chat_id, text)


# ═══════════════════════════════════════════════════════════════
# Main Loop (Long Polling)
# ═══════════════════════════════════════════════════════════════

def main():
    log.info("Starting News Cross-Analysis Bot...")
    me = tg_request("getMe")
    if me and me.get("ok"):
        bot_info = me["result"]
        log.info(f"Bot: @{bot_info['username']} ({bot_info['first_name']})")
    else:
        log.error("Failed to connect to Telegram API")
        sys.exit(1)

    # Pre-fetch sources
    log.info("Pre-fetching RSS sources...")
    all_articles = fetch_all_sources(force=True)
    total = sum(len(arts) for arts in all_articles.values())
    active = sum(1 for arts in all_articles.values() if arts)
    log.info(f"Ready: {total} articles from {active}/{len(RSS_SOURCES)} sources")

    offset = 0
    while True:
        try:
            updates = tg_request("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message"],
            }, timeout=35)

            if updates and updates.get("ok"):
                for update in updates["result"]:
                    offset = update["update_id"] + 1
                    try:
                        process_message(update)
                    except Exception as e:
                        log.error(f"Error processing update: {e}")

        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error(f"Polling error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
