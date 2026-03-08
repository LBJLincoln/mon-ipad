#!/usr/bin/env python3
"""Nomos AI Telegram Sales Bot — Product Showcase & Stripe Checkout.

READ-ONLY bot. Never modifies any data, databases, or pipelines.
Sends product information and Stripe payment links only.

Usage:
    source .env.local
    setsid python3 monetisation/telegram-sales-bot.py > /tmp/telegram-sales-bot.log 2>&1 &

No external dependencies — uses only stdlib (urllib, json).
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import traceback

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk",
)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 2

# ---------------------------------------------------------------------------
# Product catalog — 14 products in 4 tiers
# ---------------------------------------------------------------------------

TIERS = [
    {
        "name": "\ud83d\udc8e MEGA BUNDLE",
        "desc": "Everything. One payment. Lifetime access.",
        "products": [
            {
                "id": "mega_bundle",
                "name": "\ud83c\udf1f MEGA BUNDLE \u2014 All 13 Products",
                "short": "Complete RAG engineering toolkit",
                "desc": (
                    "Every single product below in one package. "
                    "Over $1,400 in value for just $497. "
                    "Architecture, workflows, templates, datasets, "
                    "playbooks, and more."
                ),
                "price": "$497",
                "value": "$1,400+",
                "url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
            },
        ],
    },
    {
        "name": "\ud83d\ude80 PREMIUM TIER ($197)",
        "desc": "Enterprise-grade assets for serious builders.",
        "products": [
            {
                "id": "architecture",
                "name": "\ud83c\udfd7\ufe0f Architecture Blueprint",
                "short": "Multi-pipeline RAG system design",
                "desc": (
                    "Complete architecture for a production multi-pipeline RAG system. "
                    "Standard, Graph, and Quantitative pipelines. "
                    "n8n orchestration, Pinecone + Neo4j + Supabase integration. "
                    "Battle-tested across 61,000+ questions."
                ),
                "price": "$197",
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
                "url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
            },
            {
                "id": "enterprise_site",
                "name": "\ud83c\udf10 Enterprise Site Template",
                "short": "Next.js 15 site with 4 sector verticals",
                "desc": (
                    "Full Next.js 15 website template with 4 sector verticals "
                    "(Finance, Legal, Construction, Industry), embedded chatbots, "
                    "responsive design, and deployment config."
                ),
                "price": "$197",
                "url": "https://buy.stripe.com/14A6oAaTM4D94j93JX5J604",
            },
            {
                "id": "agentic_commerce",
                "name": "\ud83e\udd16 Agentic Commerce Playbook",
                "short": "Sell to AI agents (McKinsey $1T market)",
                "desc": (
                    "The definitive guide to agentic commerce. "
                    "How to make your products discoverable and purchasable "
                    "by AI agents (ChatGPT, Copilot, Perplexity). "
                    "ACP protocol implementation, structured data, GEO strategy."
                ),
                "price": "$197",
                "url": "https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607",
            },
        ],
    },
    {
        "name": "\ud83d\udcbc PROFESSIONAL TIER ($67\u2013$147)",
        "desc": "Core tools for RAG practitioners.",
        "products": [
            {
                "id": "rag_handbook",
                "name": "\ud83d\udcda RAG Engineering Handbook",
                "short": "80+ sessions of RAG engineering knowledge",
                "desc": (
                    "Comprehensive handbook distilled from 80+ engineering sessions. "
                    "Covers retrieval strategies, prompt engineering, "
                    "embedding optimization, reranking, evaluation methodology, "
                    "and production deployment patterns."
                ),
                "price": "$147",
                "url": "https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606",
            },
            {
                "id": "eval_framework",
                "name": "\ud83c\udfaf RAG Eval Framework",
                "short": "61K-question evaluation system",
                "desc": (
                    "Complete evaluation framework used to test across 61,661 questions "
                    "from 18 SOTA benchmarks. Parallel runner, golden evals, "
                    "regression detection, Phase 1\u21924 methodology."
                ),
                "price": "$127",
                "url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
            },
            {
                "id": "ingestion_toolkit",
                "name": "\ud83d\udd27 Ingestion Toolkit",
                "short": "V4 pipeline: 34K records across 4 sectors",
                "desc": (
                    "Data ingestion pipeline that processed 34,000+ records "
                    "across Finance, Legal, Construction, and Industry sectors. "
                    "Includes Docling integration, sector-aware chunking, "
                    "and multi-database upsert (Pinecone + Neo4j + Supabase)."
                ),
                "price": "$97",
                "url": "https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608",
            },
            {
                "id": "dashboard_template",
                "name": "\ud83d\udcca Dashboard Template",
                "short": "Real-time RAG metrics dashboard",
                "desc": (
                    "HTML/JS dashboard showing live pipeline metrics, "
                    "accuracy trends, infrastructure status, and phase progress. "
                    "Auto-generates from status.json. Deploy anywhere."
                ),
                "price": "$97",
                "url": "https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a",
            },
            {
                "id": "benchmark_dataset",
                "name": "\ud83d\udcc8 Benchmark Dataset Toolkit",
                "short": "61K questions from 18 SOTA benchmarks",
                "desc": (
                    "Curated dataset of 61,661 questions drawn from 18 SOTA benchmarks "
                    "(HotpotQA, NQ, MMLU, FinQA, and more). "
                    "Pre-categorized by pipeline type (Standard, Graph, Quant)."
                ),
                "price": "$67",
                "url": "https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b",
            },
            {
                "id": "embeddings_service",
                "name": "\ud83e\udde0 Embeddings Service",
                "short": "Self-hosted Jina embeddings (HF Space)",
                "desc": (
                    "Self-hosted embedding service on Hugging Face Spaces. "
                    "Jina v3 1024-dim model, Gradio API, health monitoring, "
                    "lazy loading for cpu-basic. Drop-in replacement for Jina Cloud."
                ),
                "price": "$67",
                "url": "https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c",
            },
        ],
    },
    {
        "name": "\u26a1 STARTER TIER ($27\u2013$47)",
        "desc": "Quick wins. Instant value.",
        "products": [
            {
                "id": "debug_playbook",
                "name": "\ud83d\udd25 RAG Debug Playbook",
                "short": "75+ battle-tested fixes",
                "desc": (
                    "Library of 75+ real fixes encountered across 80+ sessions. "
                    "Diagnostic flowcharts, n8n gotchas, Pinecone/Neo4j/Supabase "
                    "patterns, embedding pitfalls, and LLM prompt fixes."
                ),
                "price": "$47",
                "url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
            },
            {
                "id": "claude_skills",
                "name": "\ud83e\udde9 Claude Code Skills Pack",
                "short": "17 custom Claude Code commands",
                "desc": (
                    "17 production slash commands for Claude Code: "
                    "session-start, eval, sync-directives, self-heal, "
                    "progress-10pct, regression-check, and more. "
                    "Accelerate your AI-assisted development workflow."
                ),
                "price": "$47",
                "url": "https://buy.stripe.com/7sY8wIge64D93f53JX5J609",
            },
            {
                "id": "agent_context_kit",
                "name": "\ud83d\udce6 Agent Context Kit",
                "short": "CLAUDE.md + state files template",
                "desc": (
                    "Template system for managing AI agent context: "
                    "CLAUDE.md project instructions, PROJECT-STATE.md memory, "
                    "DEBUG-PLAYBOOK.md knowledge base, INFRASTRUCTURE.md reference. "
                    "The exact system powering this project."
                ),
                "price": "$27",
                "url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
            },
        ],
    },
]

# Flatten for quick lookup
ALL_PRODUCTS = {}
for tier in TIERS:
    for p in tier["products"]:
        ALL_PRODUCTS[p["id"]] = p

# ---------------------------------------------------------------------------
# Demo RAG result (hardcoded, no live API)
# ---------------------------------------------------------------------------
DEMO_RESULT = """
\ud83d\udd0d *Sample RAG Query Result*

*Question:* _"What is the average EBITDA margin for French construction companies in 2025?"_

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

\ud83c\udfaf *Pipeline:* Quantitative RAG
\ud83d\udcca *Confidence:* 95.2%
\u23f1 *Latency:* 2.3s

*Answer:*
Based on analysis of 847 financial filings from major French constructors (Vinci, Bouygues, Eiffage), the average EBITDA margin for 2025 is *8.7%*, up from 7.9% in 2024.

Key drivers:
\u2022 Infrastructure spending +12% (France 2030 plan)
\u2022 Material costs stabilized (-3% YoY)
\u2022 Labor productivity gains from AI/BIM adoption

\ud83d\udcc4 *Sources:* 4 documents retrieved | 2 financial tables matched
\ud83e\udde0 *Embeddings:* Jina v3 (1024-dim, self-hosted)
\ud83d\udcbe *Databases:* Pinecone + Neo4j + Supabase

\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
_This is a real example from our 61,661-question Phase 4 evaluation._
_Build this yourself \u2192 /products_
"""

# ---------------------------------------------------------------------------
# About section
# ---------------------------------------------------------------------------
ABOUT_TEXT = """\ud83c\udfe2 *About Nomos AI*

Founded by *Alexis Moret* \u2014 Polytechnique + HEC Paris (double degree).

Previously founded an AI company serving top-3 French construction firms. Now building the most rigorously tested RAG system in the open.

\ud83d\udcca *By the numbers:*
\u2022 *80+ engineering sessions* documented
\u2022 *61,661 evaluation questions* from 18 SOTA benchmarks
\u2022 *1,100+ commits* across 7 repositories
\u2022 *3 production pipelines* (Standard, Graph, Quantitative)
\u2022 *87.5% Standard* | *95.2% Quantitative* accuracy
\u2022 *45,000+ vectors* indexed in Pinecone
\u2022 *79,000+ nodes* in Neo4j knowledge graph
\u2022 *9 n8n instances* on Hugging Face Spaces

\ud83d\udee0\ufe0f *Tech Stack:*
n8n \u00b7 Pinecone \u00b7 Neo4j \u00b7 Supabase \u00b7 Next.js \u00b7 Claude Code \u00b7 Groq \u00b7 Jina Embeddings \u00b7 LiteLLM \u00b7 Hugging Face

\ud83d\udce7 *Contact:* alexis.moret6@outlook.fr
\ud83c\udf10 *GitHub:* 7 repos, all battle-tested

_Every product in our catalog is extracted directly from this real system._
"""

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
        print(f"[API ERROR] {method}: HTTP {e.code} \u2014 {body[:300]}")
        return None
    except Exception as e:
        print(f"[API ERROR] {method}: {e}")
        return None


def send_msg(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send a text message, optionally with inline keyboard."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = api_call("sendMessage", payload)
    # Markdown can fail on special chars \u2014 retry without parse_mode
    if result is None or not result.get("ok"):
        payload["parse_mode"] = None
        payload.pop("parse_mode", None)
        # Strip parse_mode entirely
        payload2 = {k: v for k, v in payload.items() if k != "parse_mode"}
        result = api_call("sendMessage", payload2)
    return result


def answer_callback(callback_query_id, text=""):
    """Answer a callback query (dismiss the loading indicator)."""
    return api_call("answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text[:200] if text else "",
    })


def make_button(text, url=None, callback_data=None):
    """Create an inline keyboard button."""
    btn = {"text": text}
    if url:
        btn["url"] = url
    if callback_data:
        btn["callback_data"] = callback_data
    return btn


def make_keyboard(rows):
    """Wrap button rows into an InlineKeyboardMarkup."""
    return {"inline_keyboard": rows}


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_start(chat_id):
    """Welcome message with quick-access buttons."""
    text = (
        "\ud83d\ude80 *Welcome to Nomos AI*\n"
        "\n"
        "The most rigorously tested RAG system in the open.\n"
        "Built across 80+ sessions \u00b7 61,661 evaluation questions \u00b7 3 production pipelines.\n"
        "\n"
        "Everything we sell is extracted directly from this real, working system.\n"
        "\n"
        "\u2b07\ufe0f *Explore our products:*"
    )
    kb = make_keyboard([
        [make_button("\ud83d\udc8e MEGA BUNDLE \u2014 $497 (save $900+)", callback_data="show_mega")],
        [make_button("\ud83d\ude80 Premium Products ($197)", callback_data="show_premium")],
        [make_button("\ud83d\udcbc Professional Tools ($67\u2013$147)", callback_data="show_professional")],
        [make_button("\u26a1 Starter Kits ($27\u2013$47)", callback_data="show_starter")],
        [make_button("\ud83d\udd0d Live Demo Result", callback_data="show_demo")],
        [make_button("\ud83c\udfe2 About Nomos AI", callback_data="show_about")],
    ])
    send_msg(chat_id, text, reply_markup=kb)


def cmd_products(chat_id):
    """Full product catalog organized by tier."""
    for tier in TIERS:
        lines = [f"*{tier['name']}*", f"_{tier['desc']}_", ""]
        rows = []
        for p in tier["products"]:
            lines.append(f"\u2022 *{p['name']}* \u2014 {p['price']}")
            lines.append(f"  _{p['short']}_")
            lines.append("")
            rows.append([make_button(f"\ud83d\uded2 {p['name']} \u2014 {p['price']}", url=p["url"])])

        kb = make_keyboard(rows)
        send_msg(chat_id, "\n".join(lines), reply_markup=kb)
        time.sleep(0.3)  # Avoid rate limits


def cmd_bundle(chat_id):
    """Feature the MEGA BUNDLE."""
    bundle = ALL_PRODUCTS["mega_bundle"]
    text = (
        "\ud83d\udc8e\ud83d\udc8e\ud83d\udc8e *THE MEGA BUNDLE* \ud83d\udc8e\ud83d\udc8e\ud83d\udc8e\n"
        "\n"
        "*All 13 products. One payment. Lifetime access.*\n"
        "\n"
        "\ud83d\udcb0 *Price:* ~$497~ (value: $1,400+)\n"
        "\ud83d\udcc9 *You save:* $900+\n"
        "\n"
        "*What\u2019s included:*\n"
        "\n"
        "\ud83d\ude80 *Premium ($197 each):*\n"
        "  \u2022 Architecture Blueprint\n"
        "  \u2022 n8n Workflow Collection\n"
        "  \u2022 Enterprise Site Template\n"
        "  \u2022 Agentic Commerce Playbook\n"
        "\n"
        "\ud83d\udcbc *Professional ($67\u2013$147):*\n"
        "  \u2022 RAG Engineering Handbook\n"
        "  \u2022 RAG Eval Framework\n"
        "  \u2022 Ingestion Toolkit\n"
        "  \u2022 Dashboard Template\n"
        "  \u2022 Benchmark Dataset Toolkit\n"
        "  \u2022 Embeddings Service\n"
        "\n"
        "\u26a1 *Starter ($27\u2013$47):*\n"
        "  \u2022 RAG Debug Playbook\n"
        "  \u2022 Claude Code Skills Pack\n"
        "  \u2022 Agent Context Kit\n"
        "\n"
        "_\"Buy the bundle. Skip 80 sessions of trial and error.\"_"
    )
    kb = make_keyboard([
        [make_button("\ud83d\uded2 Buy MEGA BUNDLE \u2014 $497", url=bundle["url"])],
        [make_button("\ud83d\udc40 Browse individual products", callback_data="cmd_products")],
    ])
    send_msg(chat_id, text, reply_markup=kb)


def cmd_demo(chat_id):
    """Show a hardcoded RAG demo result."""
    send_msg(chat_id, DEMO_RESULT)


def cmd_about(chat_id):
    """About Nomos AI."""
    kb = make_keyboard([
        [make_button("\ud83d\uded2 View Products", callback_data="cmd_products")],
        [make_button("\ud83d\udc8e MEGA BUNDLE \u2014 $497", url=ALL_PRODUCTS["mega_bundle"]["url"])],
    ])
    send_msg(chat_id, ABOUT_TEXT, reply_markup=kb)


def cmd_help(chat_id):
    """List all commands."""
    text = (
        "\ud83d\udcdd *Available Commands*\n"
        "\n"
        "/start \u2014 Welcome & product catalog\n"
        "/products \u2014 Browse all 14 products by tier\n"
        "/bundle \u2014 MEGA BUNDLE details ($497, $1400+ value)\n"
        "/demo \u2014 See a sample RAG query result\n"
        "/about \u2014 About Alexis Moret & Nomos AI\n"
        "/help \u2014 This message\n"
        "\n"
        "Or tap any product name to get its details & buy link."
    )
    send_msg(chat_id, text)


def show_product_card(chat_id, product_id):
    """Send a detailed product card with Buy button."""
    p = ALL_PRODUCTS.get(product_id)
    if not p:
        send_msg(chat_id, "Product not found. Try /products to browse.")
        return
    value_line = f"\n\ud83d\udcc9 *Value:* {p['value']}" if p.get("value") else ""
    text = (
        f"*{p['name']}*\n"
        f"\n"
        f"{p['desc']}\n"
        f"\n"
        f"\ud83d\udcb0 *Price:* {p['price']}{value_line}\n"
    )
    rows = [[make_button(f"\ud83d\uded2 Buy Now \u2014 {p['price']}", url=p["url"])]]

    # Add bundle upsell for non-bundle products
    if product_id != "mega_bundle":
        rows.append([
            make_button(
                "\ud83d\udc8e Or get ALL products for $497",
                url=ALL_PRODUCTS["mega_bundle"]["url"],
            )
        ])
    rows.append([make_button("\u25c0\ufe0f Back to catalog", callback_data="cmd_products")])
    kb = make_keyboard(rows)
    send_msg(chat_id, text, reply_markup=kb)


def show_tier(chat_id, tier_key):
    """Show products from a specific tier."""
    tier_map = {
        "show_mega": 0,
        "show_premium": 1,
        "show_professional": 2,
        "show_starter": 3,
    }
    idx = tier_map.get(tier_key, 0)
    tier = TIERS[idx]

    lines = [f"*{tier['name']}*", f"_{tier['desc']}_", ""]
    rows = []
    for p in tier["products"]:
        lines.append(f"\u2022 *{p['name']}*")
        lines.append(f"  _{p['short']}_")
        lines.append(f"  \ud83d\udcb0 {p['price']}")
        lines.append("")
        # Build button label (truncate for Telegram's 64-byte callback limit)
        btn_label = p["name"]
        if "\u2014" in btn_label:
            btn_label = btn_label.split("\u2014")[0].strip()
        elif " " in btn_label:
            btn_label = btn_label.split(" ", 1)[-1]
        rows.append([
            make_button(f"\ud83d\uded2 {p['price']} \u2014 {btn_label}", url=p["url"]),
            make_button("\u2139\ufe0f Info", callback_data=f"product_{p['id']}"),
        ])

    if idx != 0:
        rows.append([make_button("\ud83d\udc8e MEGA BUNDLE \u2014 save $900+", url=ALL_PRODUCTS["mega_bundle"]["url"])])
    rows.append([make_button("\u25c0\ufe0f Back to start", callback_data="cmd_start")])

    kb = make_keyboard(rows)
    send_msg(chat_id, "\n".join(lines), reply_markup=kb)


# ---------------------------------------------------------------------------
# Message & callback routing
# ---------------------------------------------------------------------------

def handle_message(message):
    """Route incoming text messages."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    if not text:
        return

    user = message.get("from", {})
    name = user.get("first_name", "")
    print(f"[MSG] {name} ({chat_id}): {text[:100]}")

    # Commands
    if text.startswith("/"):
        cmd = text.split()[0].split("@")[0].lower()
        if cmd in ("/start", "/aide"):
            cmd_start(chat_id)
        elif cmd in ("/products", "/produits", "/catalog"):
            cmd_products(chat_id)
        elif cmd in ("/bundle", "/mega", "/megabundle"):
            cmd_bundle(chat_id)
        elif cmd in ("/demo", "/example", "/sample"):
            cmd_demo(chat_id)
        elif cmd in ("/about", "/info"):
            cmd_about(chat_id)
        elif cmd in ("/help", "/commands"):
            cmd_help(chat_id)
        else:
            send_msg(
                chat_id,
                f"Unknown command: `{cmd}`\n\nTry /help for available commands, or /products to browse our catalog.",
            )
        return

    # Free-text \u2014 friendly redirect
    text_lower = text.lower()
    if any(w in text_lower for w in ["price", "prix", "cost", "how much", "combien"]):
        cmd_products(chat_id)
    elif any(w in text_lower for w in ["bundle", "mega", "everything", "all", "tout"]):
        cmd_bundle(chat_id)
    elif any(w in text_lower for w in ["demo", "example", "sample", "d\u00e9mo", "essai"]):
        cmd_demo(chat_id)
    elif any(w in text_lower for w in ["who", "about", "founder", "alexis", "polytechnique"]):
        cmd_about(chat_id)
    elif any(w in text_lower for w in ["buy", "acheter", "purchase", "stripe", "pay"]):
        cmd_bundle(chat_id)
    elif any(w in text_lower for w in ["hello", "hi", "hey", "bonjour", "salut"]):
        cmd_start(chat_id)
    else:
        text_reply = (
            "\ud83d\udc4b Thanks for your message!\n"
            "\n"
            "I\u2019m the Nomos AI product catalog bot. Here\u2019s what I can help with:\n"
            "\n"
            "\u2022 /products \u2014 Browse all 14 products\n"
            "\u2022 /bundle \u2014 See the MEGA BUNDLE ($497)\n"
            "\u2022 /demo \u2014 See a live RAG result\n"
            "\u2022 /about \u2014 Learn about us\n"
        )
        send_msg(chat_id, text_reply)


def handle_callback(callback_query):
    """Route inline keyboard button presses."""
    cb_id = callback_query["id"]
    data = callback_query.get("data", "")
    chat_id = callback_query["message"]["chat"]["id"]

    print(f"[CALLBACK] {data} from {chat_id}")
    answer_callback(cb_id)

    if data == "cmd_start":
        cmd_start(chat_id)
    elif data == "cmd_products":
        cmd_products(chat_id)
    elif data == "show_demo":
        cmd_demo(chat_id)
    elif data == "show_about":
        cmd_about(chat_id)
    elif data.startswith("show_"):
        show_tier(chat_id, data)
    elif data.startswith("product_"):
        product_id = data[len("product_"):]
        show_product_card(chat_id, product_id)
    else:
        send_msg(chat_id, "Unknown action. Try /products")


# ---------------------------------------------------------------------------
# Main polling loop
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Nomos AI Telegram Sales Bot")
    print("=" * 60)
    print(f"  Token: ...{BOT_TOKEN[-10:]}")
    print(f"  Products: {len(ALL_PRODUCTS)}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Verify bot connection
    me = api_call("getMe")
    if not me or not me.get("ok"):
        print("[FATAL] Cannot connect to Telegram Bot API. Check token.")
        sys.exit(1)

    bot = me["result"]
    print(f"  Bot: @{bot.get('username')} ({bot.get('first_name')})")
    print(f"  Bot ID: {bot.get('id')}")
    print()
    print("Polling for updates...\n")

    offset = 0
    consecutive_errors = 0

    while True:
        try:
            updates = api_call("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message", "callback_query"],
            })

            if not updates or not updates.get("ok"):
                consecutive_errors += 1
                if consecutive_errors > 20:
                    print("[FATAL] Too many consecutive errors. Exiting.")
                    sys.exit(1)
                time.sleep(5)
                continue

            consecutive_errors = 0

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if "message" in update:
                        handle_message(update["message"])
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"])
                except Exception:
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("\nBot stopped by user.")
            break
        except Exception:
            traceback.print_exc()
            consecutive_errors += 1
            time.sleep(5)


if __name__ == "__main__":
    main()
