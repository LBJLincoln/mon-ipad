#!/usr/bin/env python3
"""Nomos AI Telegram Channel Poster — Product catalog, announcements & auto-posting.

Posts formatted product announcements to a Telegram channel.
The bot must be added as an admin to the channel with posting rights.

Usage:
    source .env.local

    # First time — print setup instructions
    python3 monetisation/telegram-channel-poster.py --setup

    # Post full product catalog to the channel
    python3 monetisation/telegram-channel-poster.py --catalog

    # Post a single product card
    python3 monetisation/telegram-channel-poster.py --product mega_bundle

    # Post the welcome/pinned message
    python3 monetisation/telegram-channel-poster.py --welcome

    # Post a daily featured product (rotates automatically)
    python3 monetisation/telegram-channel-poster.py --daily

    # Auto-post schedule: daily product + weekly catalog (runs as daemon)
    python3 monetisation/telegram-channel-poster.py --auto

    # Post to the community group instead of the channel
    python3 monetisation/telegram-channel-poster.py --catalog --group

    # List all product IDs
    python3 monetisation/telegram-channel-poster.py --list

No external dependencies — uses only stdlib (urllib, json).
"""

import argparse
import json
import os
import sys
import time
import datetime
import urllib.request
import urllib.error
import hashlib
import traceback

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk",
)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Channel & group IDs — set via env vars or command-line
# For public channels, use @channelname format
# For private channels, use the numeric chat ID (e.g., -1001234567890)
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")
GROUP_ID = os.environ.get("TELEGRAM_GROUP_ID", "")

# Sales page URL
SALES_PAGE = "https://lbjlincoln.github.io/rag-dashboard/store.html"
BOT_URL = "https://t.me/Nomos42Bot"

# Auto-post schedule
DAILY_POST_HOUR = 10   # 10:00 UTC
WEEKLY_CATALOG_DAY = 1  # Monday (0=Mon, 6=Sun in isoweekday()-1)

# State file for tracking daily rotation
STATE_FILE = "/tmp/nomos-channel-poster-state.json"

# ---------------------------------------------------------------------------
# Product catalog — 14 products in 4 tiers
# ---------------------------------------------------------------------------

TIERS = [
    {
        "name": "\U0001f48e MEGA BUNDLE",
        "emoji": "\U0001f48e",
        "desc": "Everything. One payment. Lifetime access.",
        "products": [
            {
                "id": "mega_bundle",
                "name": "\U0001f31f MEGA BUNDLE -- All 13 Products",
                "short": "Complete RAG engineering toolkit",
                "desc": (
                    "Every single product below in one package. "
                    "Over $1,400 in value for just $497. "
                    "Architecture, workflows, templates, datasets, "
                    "playbooks, and more."
                ),
                "price": "$497",
                "value": "$1,400+",
                "highlights": [
                    "4 Premium products ($197 each)",
                    "6 Professional tools ($67-$147)",
                    "3 Starter kits ($27-$47)",
                    "Lifetime access, all future updates",
                ],
                "url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
            },
        ],
    },
    {
        "name": "\U0001f680 PREMIUM TIER ($197)",
        "emoji": "\U0001f680",
        "desc": "Enterprise-grade assets for serious builders.",
        "products": [
            {
                "id": "architecture",
                "name": "\U0001f3d7\ufe0f Architecture Blueprint",
                "short": "Multi-pipeline RAG system design",
                "desc": (
                    "Complete architecture for a production multi-pipeline RAG system. "
                    "Standard, Graph, and Quantitative pipelines. "
                    "n8n orchestration, Pinecone + Neo4j + Supabase integration. "
                    "Battle-tested across 61,000+ questions."
                ),
                "price": "$197",
                "highlights": [
                    "3 specialized RAG pipelines",
                    "n8n workflow orchestration",
                    "Triple database integration",
                    "Phase-gated evaluation methodology",
                ],
                "url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
            },
            {
                "id": "n8n_workflows",
                "name": "\u2699\ufe0f n8n Workflow Collection",
                "short": "Production RAG workflows (JSON export)",
                "desc": (
                    "7 production n8n workflow files covering Standard RAG, "
                    "Graph RAG, Quantitative RAG, website pipelines, "
                    "and the orchestrator. Ready to import and customize."
                ),
                "price": "$197",
                "highlights": [
                    "7 production workflow JSONs",
                    "Standard + Graph + Quant pipelines",
                    "Website integration workflows",
                    "Import, customize, deploy",
                ],
                "url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
            },
            {
                "id": "enterprise_site",
                "name": "\U0001f310 Enterprise Site Template",
                "short": "Next.js 15 site with 4 sector verticals",
                "desc": (
                    "Full Next.js 15 website template with 4 sector verticals "
                    "(Finance, Legal, Construction, Industry), embedded chatbots, "
                    "responsive design, and deployment config."
                ),
                "price": "$197",
                "highlights": [
                    "Next.js 15 + React",
                    "4 sector verticals (Finance, Legal, BTP, Industry)",
                    "Embedded AI chatbots",
                    "Responsive design + Vercel deploy config",
                ],
                "url": "https://buy.stripe.com/14A6oAaTM4D94j93JX5J604",
            },
            {
                "id": "agentic_commerce",
                "name": "\U0001f916 Agentic Commerce Playbook",
                "short": "Sell to AI agents (McKinsey $1T market)",
                "desc": (
                    "The definitive guide to agentic commerce. "
                    "How to make your products discoverable and purchasable "
                    "by AI agents (ChatGPT, Copilot, Perplexity). "
                    "ACP protocol implementation, structured data, GEO strategy."
                ),
                "price": "$197",
                "highlights": [
                    "ACP protocol implementation",
                    "AI-discoverable product markup",
                    "GEO (Generative Engine Optimization)",
                    "McKinsey $1T market playbook",
                ],
                "url": "https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607",
            },
        ],
    },
    {
        "name": "\U0001f4bc PROFESSIONAL TIER ($67-$147)",
        "emoji": "\U0001f4bc",
        "desc": "Core tools for RAG practitioners.",
        "products": [
            {
                "id": "rag_handbook",
                "name": "\U0001f4da RAG Engineering Handbook",
                "short": "80+ sessions of RAG engineering knowledge",
                "desc": (
                    "Comprehensive handbook distilled from 80+ engineering sessions. "
                    "Covers retrieval strategies, prompt engineering, "
                    "embedding optimization, reranking, evaluation methodology, "
                    "and production deployment patterns."
                ),
                "price": "$147",
                "highlights": [
                    "80+ sessions of knowledge distilled",
                    "Retrieval, prompting, embedding strategies",
                    "Reranking & evaluation methodology",
                    "Production deployment patterns",
                ],
                "url": "https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606",
            },
            {
                "id": "eval_framework",
                "name": "\U0001f3af RAG Eval Framework",
                "short": "61K-question evaluation system",
                "desc": (
                    "Complete evaluation framework used to test across 61,661 questions "
                    "from 18 SOTA benchmarks. Parallel runner, golden evals, "
                    "regression detection, Phase 1-4 methodology."
                ),
                "price": "$127",
                "highlights": [
                    "61,661 questions from 18 benchmarks",
                    "Parallel evaluation runner",
                    "Golden eval + regression detection",
                    "Phase 1-4 methodology",
                ],
                "url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
            },
            {
                "id": "ingestion_toolkit",
                "name": "\U0001f527 Ingestion Toolkit",
                "short": "V4 pipeline: 34K records across 4 sectors",
                "desc": (
                    "Data ingestion pipeline that processed 34,000+ records "
                    "across Finance, Legal, Construction, and Industry sectors. "
                    "Includes Docling integration, sector-aware chunking, "
                    "and multi-database upsert (Pinecone + Neo4j + Supabase)."
                ),
                "price": "$97",
                "highlights": [
                    "34K+ records processed",
                    "4 sector verticals",
                    "Docling PDF extraction",
                    "Multi-DB upsert (Pinecone + Neo4j + Supabase)",
                ],
                "url": "https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608",
            },
            {
                "id": "dashboard_template",
                "name": "\U0001f4ca Dashboard Template",
                "short": "Real-time RAG metrics dashboard",
                "desc": (
                    "HTML/JS dashboard showing live pipeline metrics, "
                    "accuracy trends, infrastructure status, and phase progress. "
                    "Auto-generates from status.json. Deploy anywhere."
                ),
                "price": "$97",
                "highlights": [
                    "Live pipeline metrics",
                    "Accuracy trend charts",
                    "Infrastructure status view",
                    "Auto-generated, deploy anywhere",
                ],
                "url": "https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a",
            },
            {
                "id": "benchmark_dataset",
                "name": "\U0001f4c8 Benchmark Dataset Toolkit",
                "short": "61K questions from 18 SOTA benchmarks",
                "desc": (
                    "Curated dataset of 61,661 questions drawn from 18 SOTA benchmarks "
                    "(HotpotQA, NQ, MMLU, FinQA, and more). "
                    "Pre-categorized by pipeline type (Standard, Graph, Quant)."
                ),
                "price": "$67",
                "highlights": [
                    "61,661 curated questions",
                    "18 SOTA benchmarks (HotpotQA, NQ, MMLU...)",
                    "Pre-categorized by pipeline type",
                    "Ready for immediate evaluation",
                ],
                "url": "https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b",
            },
            {
                "id": "embeddings_service",
                "name": "\U0001f9e0 Embeddings Service",
                "short": "Self-hosted Jina embeddings (HF Space)",
                "desc": (
                    "Self-hosted embedding service on Hugging Face Spaces. "
                    "Jina v3 1024-dim model, Gradio API, health monitoring, "
                    "lazy loading for cpu-basic. Drop-in replacement for Jina Cloud."
                ),
                "price": "$67",
                "highlights": [
                    "Self-hosted on HF Spaces (free tier)",
                    "Jina v3 1024-dim embeddings",
                    "Drop-in Jina Cloud replacement",
                    "Health monitoring + lazy loading",
                ],
                "url": "https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c",
            },
        ],
    },
    {
        "name": "\u26a1 STARTER TIER ($27-$47)",
        "emoji": "\u26a1",
        "desc": "Quick wins. Instant value.",
        "products": [
            {
                "id": "debug_playbook",
                "name": "\U0001f525 RAG Debug Playbook",
                "short": "75+ battle-tested fixes",
                "desc": (
                    "Library of 75+ real fixes encountered across 80+ sessions. "
                    "Diagnostic flowcharts, n8n gotchas, Pinecone/Neo4j/Supabase "
                    "patterns, embedding pitfalls, and LLM prompt fixes."
                ),
                "price": "$47",
                "highlights": [
                    "75+ real production fixes",
                    "Diagnostic flowcharts",
                    "Database & embedding gotchas",
                    "LLM prompt fix patterns",
                ],
                "url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
            },
            {
                "id": "claude_skills",
                "name": "\U0001f9e9 Claude Code Skills Pack",
                "short": "17 custom Claude Code commands",
                "desc": (
                    "17 production slash commands for Claude Code: "
                    "session-start, eval, sync-directives, self-heal, "
                    "progress-10pct, regression-check, and more. "
                    "Accelerate your AI-assisted development workflow."
                ),
                "price": "$47",
                "highlights": [
                    "17 production slash commands",
                    "Session management & eval",
                    "Self-healing & regression checks",
                    "Instant AI-assisted productivity",
                ],
                "url": "https://buy.stripe.com/7sY8wIge64D93f53JX5J609",
            },
            {
                "id": "agent_context_kit",
                "name": "\U0001f4e6 Agent Context Kit",
                "short": "CLAUDE.md + state files template",
                "desc": (
                    "Template system for managing AI agent context: "
                    "CLAUDE.md project instructions, PROJECT-STATE.md memory, "
                    "DEBUG-PLAYBOOK.md knowledge base, INFRASTRUCTURE.md reference. "
                    "The exact system powering this project."
                ),
                "price": "$27",
                "highlights": [
                    "CLAUDE.md project instructions template",
                    "PROJECT-STATE.md memory system",
                    "DEBUG-PLAYBOOK.md knowledge base",
                    "Drop-in for Claude Code / Copilot / Cursor",
                ],
                "url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
            },
        ],
    },
]

# Flatten for quick lookup
ALL_PRODUCTS = {}
PRODUCT_ORDER = []  # Maintains display order for rotation
for tier in TIERS:
    for p in tier["products"]:
        ALL_PRODUCTS[p["id"]] = p
        PRODUCT_ORDER.append(p["id"])


# ---------------------------------------------------------------------------
# Telegram API helpers
# ---------------------------------------------------------------------------

def api_call(method, payload=None):
    """Call Telegram Bot API. Returns parsed JSON or None."""
    url = f"{API_URL}/{method}"
    if payload:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[API ERROR] {method}: HTTP {e.code} -- {body[:500]}")
        return None
    except Exception as e:
        print(f"[API ERROR] {method}: {e}")
        return None


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML",
                 disable_preview=True):
    """Send a text message. Falls back to no formatting on failure."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = api_call("sendMessage", payload)
    # HTML can fail on edge cases -- retry without parse_mode
    if result is None or not result.get("ok"):
        payload.pop("parse_mode", None)
        payload.pop("reply_markup", None)
        result = api_call("sendMessage", payload)
    return result


def pin_message(chat_id, message_id, disable_notification=True):
    """Pin a message in a chat/channel."""
    return api_call("pinChatMessage", {
        "chat_id": chat_id,
        "message_id": message_id,
        "disable_notification": disable_notification,
    })


def make_inline_keyboard(rows):
    """Build InlineKeyboardMarkup from rows of button dicts."""
    return {"inline_keyboard": rows}


def make_url_button(text, url):
    """Create a URL inline button."""
    return {"text": text, "url": url}


# ---------------------------------------------------------------------------
# Message formatters (HTML mode for channel posts)
# ---------------------------------------------------------------------------

def format_welcome_message():
    """Format the welcome/pinned message for the channel."""
    return (
        "<b>\U0001f680 Nomos AI Products</b>\n"
        "\n"
        "The most rigorously tested RAG system in the open.\n"
        "\n"
        "\U0001f4ca <b>By the numbers:</b>\n"
        "  \u2022 80+ engineering sessions documented\n"
        "  \u2022 61,661 evaluation questions from 18 SOTA benchmarks\n"
        "  \u2022 1,100+ commits across 7 repositories\n"
        "  \u2022 3 production pipelines: Standard (87.5%), Graph, Quant (95.2%)\n"
        "  \u2022 77,000+ vectors in Pinecone\n"
        "  \u2022 79,000+ nodes in Neo4j knowledge graph\n"
        "  \u2022 9 n8n instances on HuggingFace Spaces\n"
        "  \u2022 Entire stack runs on free-tier infrastructure ($0/month)\n"
        "\n"
        "\U0001f6e0 <b>Tech Stack:</b>\n"
        "n8n \u00b7 Pinecone \u00b7 Neo4j \u00b7 Supabase \u00b7 Next.js \u00b7 Claude Code \u00b7 "
        "Groq \u00b7 Jina Embeddings \u00b7 LiteLLM \u00b7 HuggingFace\n"
        "\n"
        "\U0001f464 <b>Built by Alexis Moret</b> -- Polytechnique + HEC Paris\n"
        "Previously founded an AI company serving top-3 French construction firms.\n"
        "\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "\n"
        "<b>14 products</b> extracted directly from this real, working system.\n"
        "From $27 (Agent Context Kit) to $497 (MEGA BUNDLE with everything).\n"
        "\n"
        f"\U0001f310 <b>Full catalog:</b> {SALES_PAGE}\n"
        f"\U0001f916 <b>Chat with our bot:</b> {BOT_URL}\n"
        "\n"
        "<i>Follow this channel for new products, engineering insights, "
        "and exclusive offers.</i>"
    )


def format_product_card(product_id):
    """Format a detailed product card for channel posting."""
    p = ALL_PRODUCTS.get(product_id)
    if not p:
        return None, None

    is_bundle = product_id == "mega_bundle"

    lines = []
    lines.append(f"<b>{p['name']}</b>")
    lines.append("")
    lines.append(p["desc"])
    lines.append("")

    # Highlights
    if p.get("highlights"):
        lines.append("\u2705 <b>What's included:</b>")
        for h in p["highlights"]:
            lines.append(f"  \u2022 {h}")
        lines.append("")

    # Price
    if is_bundle:
        lines.append(f"\U0001f4b0 <b>Price:</b> {p['price']}  (value: {p.get('value', '')})")
        lines.append(f"\U0001f4c9 <b>You save:</b> $900+")
    else:
        lines.append(f"\U0001f4b0 <b>Price:</b> {p['price']}")
    lines.append("")

    # CTA
    lines.append(f"\U0001f6d2 <b>Buy now:</b> {p['url']}")

    # Upsell for non-bundle
    if not is_bundle:
        bundle = ALL_PRODUCTS["mega_bundle"]
        lines.append("")
        lines.append(
            f"\U0001f48e <i>Or get ALL 13 products for $497:</i> {bundle['url']}"
        )

    text = "\n".join(lines)

    # Build keyboard
    buttons = []
    buttons.append([make_url_button(f"\U0001f6d2 Buy Now -- {p['price']}", p["url"])])
    if not is_bundle:
        buttons.append([
            make_url_button(
                "\U0001f48e MEGA BUNDLE -- $497 (save $900+)",
                ALL_PRODUCTS["mega_bundle"]["url"],
            )
        ])
    buttons.append([make_url_button("\U0001f310 Full Store", SALES_PAGE)])
    kb = make_inline_keyboard(buttons)

    return text, kb


def format_tier_message(tier_index):
    """Format a tier overview message for channel posting."""
    tier = TIERS[tier_index]
    lines = []
    lines.append(f"<b>{tier['name']}</b>")
    lines.append(f"<i>{tier['desc']}</i>")
    lines.append("")

    buttons = []
    for p in tier["products"]:
        lines.append(f"\u2022 <b>{p['name']}</b> -- {p['price']}")
        lines.append(f"  <i>{p['short']}</i>")
        lines.append("")
        buttons.append([make_url_button(f"\U0001f6d2 {p['price']} -- {p['name']}", p["url"])])

    # Upsell
    if tier_index != 0:
        buttons.append([
            make_url_button(
                "\U0001f48e MEGA BUNDLE -- All 13 for $497",
                ALL_PRODUCTS["mega_bundle"]["url"],
            )
        ])

    kb = make_inline_keyboard(buttons)
    return "\n".join(lines), kb


def format_catalog_header():
    """Format a header message for the full catalog post."""
    return (
        "\U0001f4e2 <b>PRODUCT CATALOG -- Nomos AI</b>\n"
        "\n"
        "14 products extracted from a real multi-pipeline RAG system.\n"
        "Tested on 61,661 questions. 1,100+ commits. 80+ engineering sessions.\n"
        "\n"
        "Everything below is battle-tested, documented, and ready to deploy.\n"
        "\n"
        "\u2b07\ufe0f <b>Browse by tier:</b>"
    )


def format_daily_tip(product_id):
    """Format a 'product of the day' style post with engineering context."""
    p = ALL_PRODUCTS.get(product_id)
    if not p:
        return None, None

    # Engineering tips per product (adds value beyond just selling)
    tips = {
        "mega_bundle": (
            "\U0001f4a1 <b>Engineering tip:</b> The fastest way to build a production "
            "RAG system is to start with a working reference implementation. "
            "The MEGA BUNDLE gives you every component -- architecture, workflows, "
            "evaluation, data pipeline -- all integrated and tested."
        ),
        "architecture": (
            "\U0001f4a1 <b>Engineering tip:</b> Most RAG systems fail because they use "
            "a single retrieval strategy. Different query types need different pipelines. "
            "Financial queries need SQL generation. Relationship queries need graph traversal. "
            "Factual queries need dense + sparse retrieval."
        ),
        "n8n_workflows": (
            "\U0001f4a1 <b>Engineering tip:</b> n8n workflows on HuggingFace Spaces lose "
            "all state on restart. Always version-control your workflow JSONs externally "
            "and use a sync script. We learned this the hard way."
        ),
        "enterprise_site": (
            "\U0001f4a1 <b>Engineering tip:</b> Sector-specific RAG needs sector-specific "
            "UI. Finance users expect data tables. Legal users need citation precision. "
            "Construction users want visual project overviews."
        ),
        "agentic_commerce": (
            "\U0001f4a1 <b>Engineering tip:</b> By 2027, AI agents will make more "
            "purchases than humans for B2B software (Semrush). Make your products "
            "discoverable by AI: structured data, clear pricing, machine-readable catalogs."
        ),
        "rag_handbook": (
            "\U0001f4a1 <b>Engineering tip:</b> The single biggest accuracy improvement "
            "in our system came from HyDE (Hypothetical Document Embedding). "
            "Instead of embedding the raw query, generate a hypothetical answer first, "
            "then embed that. +5-10% retrieval precision."
        ),
        "eval_framework": (
            "\U0001f4a1 <b>Engineering tip:</b> Testing RAG on 10 questions is like testing "
            "a web app by clicking one button. Bugs that appear in 0.5% of queries are "
            "invisible at 200 questions but show up as 50 failures at 10K."
        ),
        "ingestion_toolkit": (
            "\U0001f4a1 <b>Engineering tip:</b> Pinecone metadata has a 40KB per-vector limit. "
            "Exceed it and upserts silently fail. No error. Just missing data at query time. "
            "Truncate metadata before upserting."
        ),
        "dashboard_template": (
            "\U0001f4a1 <b>Engineering tip:</b> If you can't measure it, you can't improve it. "
            "Track accuracy per pipeline, latency percentiles, and retrieval recall. "
            "Auto-generate your dashboard from a status.json -- no manual updates needed."
        ),
        "benchmark_dataset": (
            "\U0001f4a1 <b>Engineering tip:</b> Don't evaluate RAG with random questions. "
            "Use established benchmarks: HotpotQA for multi-hop, SQuAD for factual, "
            "FinQA for numerical, NQ for open-domain. Each reveals different failure modes."
        ),
        "embeddings_service": (
            "\U0001f4a1 <b>Engineering tip:</b> Jina Cloud API keys have usage limits. "
            "Self-hosting on a free HF Space (cpu-basic) gives unlimited embeddings at "
            "~6.3 contexts/min. Slow but free and reliable."
        ),
        "debug_playbook": (
            "\U0001f4a1 <b>Engineering tip:</b> The #1 recurring bug in our system: "
            "n8n disabled nodes still fire HTTP requests. The data passes through, and "
            "HTTP Request nodes execute regardless of the disabled flag."
        ),
        "claude_skills": (
            "\U0001f4a1 <b>Engineering tip:</b> Claude Code custom skills (slash commands) "
            "save 5-10 minutes per session. /session-start auto-loads context. "
            "/eval runs tests. /self-heal diagnoses and fixes pipeline issues."
        ),
        "agent_context_kit": (
            "\U0001f4a1 <b>Engineering tip:</b> An AI coding assistant is only as good "
            "as its context. A well-structured CLAUDE.md file turns Claude Code from "
            "a code generator into a project-aware engineering partner."
        ),
    }

    tip = tips.get(product_id, "")
    is_bundle = product_id == "mega_bundle"

    lines = []
    lines.append(f"\U0001f31e <b>Product of the Day</b>")
    lines.append("")
    lines.append(f"<b>{p['name']}</b>")
    lines.append(f"<i>{p['short']}</i>")
    lines.append("")
    lines.append(p["desc"])
    lines.append("")

    if p.get("highlights"):
        for h in p["highlights"]:
            lines.append(f"  \u2705 {h}")
        lines.append("")

    if is_bundle:
        lines.append(f"\U0001f4b0 <b>{p['price']}</b>  (value: {p.get('value', '')})")
    else:
        lines.append(f"\U0001f4b0 <b>{p['price']}</b>")
    lines.append("")

    if tip:
        lines.append(tip)
        lines.append("")

    lines.append(f"\U0001f6d2 {p['url']}")

    text = "\n".join(lines)

    buttons = [[make_url_button(f"\U0001f6d2 Buy Now -- {p['price']}", p["url"])]]
    if not is_bundle:
        buttons.append([
            make_url_button(
                "\U0001f48e Or get everything -- $497",
                ALL_PRODUCTS["mega_bundle"]["url"],
            )
        ])
    kb = make_inline_keyboard(buttons)

    return text, kb


def format_community_welcome():
    """Format welcome message for the community/support group."""
    return (
        "<b>\U0001f91d Welcome to Nomos AI Community</b>\n"
        "\n"
        "This is the discussion and support group for Nomos AI products.\n"
        "\n"
        "<b>What you can do here:</b>\n"
        "  \u2022 Ask questions about RAG engineering\n"
        "  \u2022 Get help with purchased products\n"
        "  \u2022 Share your RAG implementations\n"
        "  \u2022 Discuss evaluation methodology\n"
        "  \u2022 Request features and give feedback\n"
        "\n"
        "<b>Rules:</b>\n"
        "  1. Be respectful and constructive\n"
        "  2. No spam or off-topic promotion\n"
        "  3. Share code snippets with proper formatting\n"
        "  4. Tag @Nomos42Bot for product questions\n"
        "\n"
        f"\U0001f4e2 <b>Product announcements:</b> Follow our channel for updates\n"
        f"\U0001f310 <b>Full catalog:</b> {SALES_PAGE}\n"
        f"\U0001f916 <b>Product bot:</b> {BOT_URL}\n"
        "\n"
        "<i>Built by Alexis Moret -- Polytechnique + HEC Paris</i>"
    )


# ---------------------------------------------------------------------------
# State management (for daily rotation)
# ---------------------------------------------------------------------------

def load_state():
    """Load posting state from file."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_daily_index": -1, "last_daily_date": "", "last_catalog_date": ""}


def save_state(state):
    """Save posting state to file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_next_daily_product():
    """Get the next product to feature, rotating through all products."""
    state = load_state()
    idx = (state.get("last_daily_index", -1) + 1) % len(PRODUCT_ORDER)
    return PRODUCT_ORDER[idx], idx


# ---------------------------------------------------------------------------
# Posting actions
# ---------------------------------------------------------------------------

def resolve_chat_id(args):
    """Resolve which chat ID to use based on args."""
    if args.group:
        chat_id = args.group_id or GROUP_ID
        label = "group"
    else:
        chat_id = args.channel_id or CHANNEL_ID
        label = "channel"

    if not chat_id:
        env_var = "TELEGRAM_GROUP_ID" if args.group else "TELEGRAM_CHANNEL_ID"
        print(f"[ERROR] No {label} ID configured.")
        print(f"  Set {env_var} in .env.local or use --channel-id / --group-id flag.")
        print(f"  Run with --setup for full instructions.")
        sys.exit(1)

    return chat_id, label


def post_welcome(args):
    """Post and pin the welcome message."""
    chat_id, label = resolve_chat_id(args)
    print(f"[POST] Sending welcome message to {label} {chat_id}...")

    if args.group:
        text = format_community_welcome()
    else:
        text = format_welcome_message()

    kb = make_inline_keyboard([
        [make_url_button("\U0001f6d2 Browse Products", SALES_PAGE)],
        [make_url_button("\U0001f916 Chat with Bot", BOT_URL)],
        [make_url_button(
            "\U0001f48e MEGA BUNDLE -- $497",
            ALL_PRODUCTS["mega_bundle"]["url"],
        )],
    ])

    result = send_message(chat_id, text, reply_markup=kb)
    if result and result.get("ok"):
        msg_id = result["result"]["message_id"]
        print(f"  [OK] Welcome message sent (ID: {msg_id})")

        # Pin it
        pin_result = pin_message(chat_id, msg_id)
        if pin_result and pin_result.get("ok"):
            print(f"  [OK] Message pinned")
        else:
            print(f"  [WARN] Could not pin message (bot needs admin rights)")
    else:
        print(f"  [FAIL] Could not send welcome message")
        if result:
            print(f"  Response: {json.dumps(result, indent=2)[:500]}")


def post_catalog(args):
    """Post the full product catalog to the channel."""
    chat_id, label = resolve_chat_id(args)
    print(f"[POST] Sending full catalog to {label} {chat_id}...")

    # Header
    header_text = format_catalog_header()
    result = send_message(chat_id, header_text)
    if result and result.get("ok"):
        print(f"  [OK] Catalog header sent")
    else:
        print(f"  [FAIL] Could not send header")
        return
    time.sleep(1)

    # Each tier
    for i, tier in enumerate(TIERS):
        text, kb = format_tier_message(i)
        result = send_message(chat_id, text, reply_markup=kb)
        if result and result.get("ok"):
            print(f"  [OK] Tier {i+1}/{len(TIERS)}: {tier['name']}")
        else:
            print(f"  [FAIL] Tier {i+1}: {tier['name']}")
        time.sleep(1.5)  # Respect rate limits

    print(f"[DONE] Full catalog posted ({len(TIERS)} tiers, {len(ALL_PRODUCTS)} products)")

    # Update state
    state = load_state()
    state["last_catalog_date"] = datetime.date.today().isoformat()
    save_state(state)


def post_product(args):
    """Post a single product card."""
    chat_id, label = resolve_chat_id(args)
    product_id = args.product

    if product_id not in ALL_PRODUCTS:
        print(f"[ERROR] Unknown product: {product_id}")
        print(f"  Available: {', '.join(PRODUCT_ORDER)}")
        sys.exit(1)

    print(f"[POST] Sending product card '{product_id}' to {label} {chat_id}...")

    text, kb = format_product_card(product_id)
    result = send_message(chat_id, text, reply_markup=kb)
    if result and result.get("ok"):
        print(f"  [OK] Product card sent: {ALL_PRODUCTS[product_id]['name']}")
    else:
        print(f"  [FAIL] Could not send product card")


def post_daily(args):
    """Post the daily featured product (auto-rotates)."""
    chat_id, label = resolve_chat_id(args)
    product_id, idx = get_next_daily_product()

    print(f"[POST] Daily featured product: {product_id} (index {idx}/{len(PRODUCT_ORDER)})")
    print(f"  Posting to {label} {chat_id}...")

    text, kb = format_daily_tip(product_id)
    if not text:
        print(f"  [FAIL] Could not format daily post for {product_id}")
        return

    result = send_message(chat_id, text, reply_markup=kb)
    if result and result.get("ok"):
        print(f"  [OK] Daily post sent: {ALL_PRODUCTS[product_id]['name']}")
        # Update state
        state = load_state()
        state["last_daily_index"] = idx
        state["last_daily_date"] = datetime.date.today().isoformat()
        save_state(state)
    else:
        print(f"  [FAIL] Could not send daily post")


def run_auto(args):
    """Run the auto-posting daemon. Posts daily product + weekly catalog."""
    chat_id, label = resolve_chat_id(args)

    print("=" * 60)
    print("  Nomos AI Channel Auto-Poster")
    print("=" * 60)
    print(f"  Target: {label} {chat_id}")
    print(f"  Daily post hour: {DAILY_POST_HOUR}:00 UTC")
    print(f"  Weekly catalog: {'Monday' if WEEKLY_CATALOG_DAY == 0 else ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][WEEKLY_CATALOG_DAY]}")
    print(f"  Products in rotation: {len(PRODUCT_ORDER)}")
    print(f"  State file: {STATE_FILE}")
    print()

    # Verify bot
    me = api_call("getMe")
    if not me or not me.get("ok"):
        print("[FATAL] Cannot connect to Telegram Bot API. Check token.")
        sys.exit(1)
    bot = me["result"]
    print(f"  Bot: @{bot.get('username')} ({bot.get('first_name')})")
    print()
    print("Running... (Ctrl+C to stop)")
    print()

    while True:
        try:
            now = datetime.datetime.utcnow()
            today = now.date().isoformat()
            state = load_state()

            # Daily product post
            if (now.hour >= DAILY_POST_HOUR
                    and state.get("last_daily_date") != today):
                print(f"\n[AUTO] {now.strftime('%Y-%m-%d %H:%M')} -- Daily product post")
                post_daily(args)

            # Weekly catalog (check day of week)
            if (now.weekday() == WEEKLY_CATALOG_DAY
                    and now.hour >= DAILY_POST_HOUR + 1
                    and state.get("last_catalog_date") != today):
                print(f"\n[AUTO] {now.strftime('%Y-%m-%d %H:%M')} -- Weekly catalog post")
                post_catalog(args)

            # Sleep 10 minutes between checks
            time.sleep(600)

        except KeyboardInterrupt:
            print("\nAuto-poster stopped by user.")
            break
        except Exception:
            traceback.print_exc()
            time.sleep(60)


def print_setup_instructions():
    """Print instructions for creating the Telegram channel and group."""
    print("""
================================================================================
  NOMOS AI TELEGRAM CHANNEL SETUP GUIDE
================================================================================

Telegram bots cannot create channels or groups. You need to create them manually
in the Telegram app, then add the bot as an admin.

STEP 1: Create the Channel
--------------------------------------------------------------------------------
1. Open Telegram (mobile or desktop)
2. Tap the pencil/compose icon
3. Select "New Channel"
4. Name:        Nomos AI Products
   Description: RAG engineering tools & products by Alexis Moret.
                14 products from $27-$497. Built from a real production system
                tested on 61,661 questions.
   Photo:       Use the Nomos AI logo or a tech/AI related image
5. Choose "Public Channel"
   Link:        @NomosAIProducts  (or similar available name)
6. Skip adding subscribers for now
7. Go to Channel Settings > Administrators > Add Administrator
8. Search for @Nomos42Bot
9. Grant these permissions:
   - Post Messages: YES
   - Edit Messages: YES
   - Delete Messages: YES
   - Pin Messages: YES (optional but recommended)

STEP 2: Create the Community Group
--------------------------------------------------------------------------------
1. Open Telegram > New Group
2. Name:        Nomos AI Community
   Photo:       Same or related branding
3. Add @Nomos42Bot to the group
4. Make the bot an administrator with posting rights
5. Optionally link the group to the channel (Channel Settings > Discussion)

STEP 3: Get Chat IDs
--------------------------------------------------------------------------------
Option A (easiest): Use a public channel username
   TELEGRAM_CHANNEL_ID="@NomosAIProducts"
   TELEGRAM_GROUP_ID="@NomosAICommunity"

Option B: Get numeric IDs
   1. Forward a message from the channel to @userinfobot
   2. Or use this script to detect the chat ID:

      # Send a test message to the channel, then run:
      source .env.local
      python3 -c "
      import urllib.request, json
      url = 'https://api.telegram.org/bot{TOKEN}/getUpdates'.format(
          TOKEN='8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk')
      resp = urllib.request.urlopen(url)
      data = json.loads(resp.read())
      for u in data.get('result', []):
          msg = u.get('message') or u.get('channel_post', {})
          chat = msg.get('chat', {})
          if chat:
              print(f'Chat: {chat.get(\"title\", \"DM\")} | ID: {chat[\"id\"]} | Type: {chat.get(\"type\", \"?\")}')
      "

STEP 4: Configure Environment
--------------------------------------------------------------------------------
Add to .env.local:

   export TELEGRAM_CHANNEL_ID="@NomosAIProducts"
   export TELEGRAM_GROUP_ID="@NomosAICommunity"

(Replace with your actual channel/group username or numeric ID)

STEP 5: Post Initial Content
--------------------------------------------------------------------------------
# Source environment
source .env.local

# Post and pin the welcome message
python3 monetisation/telegram-channel-poster.py --welcome

# Post full product catalog
python3 monetisation/telegram-channel-poster.py --catalog

# Post welcome to community group
python3 monetisation/telegram-channel-poster.py --welcome --group

STEP 6: Start Auto-Posting
--------------------------------------------------------------------------------
# Run as daemon (survives SSH disconnect)
source .env.local
setsid python3 monetisation/telegram-channel-poster.py --auto > /tmp/telegram-channel-poster.log 2>&1 &

# Check logs
tail -f /tmp/telegram-channel-poster.log

SCHEDULE:
- Daily at 10:00 UTC: Featured product (rotates through all 14)
- Weekly on Monday at 11:00 UTC: Full catalog repost

================================================================================
""")


def list_products():
    """Print all product IDs and names."""
    print("\nAvailable products:")
    print("-" * 60)
    for tier in TIERS:
        print(f"\n{tier['name']}")
        for p in tier["products"]:
            print(f"  {p['id']:25s} {p['price']:8s}  {p['name']}")
    print(f"\nTotal: {len(ALL_PRODUCTS)} products")
    print(f"Use --product <id> to post a specific product card.\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Nomos AI Telegram Channel Poster",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --setup                    Print channel setup instructions
  %(prog)s --welcome                  Post & pin welcome message
  %(prog)s --catalog                  Post full product catalog
  %(prog)s --product mega_bundle      Post a specific product card
  %(prog)s --daily                    Post today's featured product
  %(prog)s --auto                     Run auto-posting daemon
  %(prog)s --catalog --group          Post catalog to community group
  %(prog)s --list                     List all product IDs
        """,
    )

    # Actions (mutually exclusive)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--setup", action="store_true",
                         help="Print setup instructions for creating the channel")
    actions.add_argument("--welcome", action="store_true",
                         help="Post and pin the welcome message")
    actions.add_argument("--catalog", action="store_true",
                         help="Post the full product catalog")
    actions.add_argument("--product", type=str, metavar="ID",
                         help="Post a single product card (use --list for IDs)")
    actions.add_argument("--daily", action="store_true",
                         help="Post the daily featured product (auto-rotates)")
    actions.add_argument("--auto", action="store_true",
                         help="Run auto-posting daemon (daily + weekly)")
    actions.add_argument("--list", action="store_true",
                         help="List all product IDs")

    # Target
    parser.add_argument("--group", action="store_true",
                        help="Post to community group instead of channel")
    parser.add_argument("--channel-id", type=str, default="",
                        help="Override channel ID (default: TELEGRAM_CHANNEL_ID env)")
    parser.add_argument("--group-id", type=str, default="",
                        help="Override group ID (default: TELEGRAM_GROUP_ID env)")

    args = parser.parse_args()

    # Dispatch
    if args.setup:
        print_setup_instructions()
    elif args.list:
        list_products()
    elif args.welcome:
        post_welcome(args)
    elif args.catalog:
        post_catalog(args)
    elif args.product:
        post_product(args)
    elif args.daily:
        post_daily(args)
    elif args.auto:
        run_auto(args)


if __name__ == "__main__":
    main()
