#!/usr/bin/env python3
"""Nomos AI Telegram Active Seller — Outbound content marketing + DM sales.

This script COMPLEMENTS the passive catalog bot (telegram-sales-bot.py).
It does NOT replace it. Both can run simultaneously (same bot token, no conflict
because this script uses sendMessage only, not getUpdates polling — see note below).

NOTE ON DUAL-BOT ARCHITECTURE:
- The passive bot uses getUpdates (long-polling) to receive messages.
- This active seller uses sendMessage/getChat only (outbound).
- IMPORTANT: Only ONE process can use getUpdates at a time per bot token.
  This script includes a lightweight DM responder that uses getUpdates.
  If you run BOTH scripts, disable the DM responder here (set ENABLE_DM_RESPONDER=False)
  or stop the passive bot.

Usage:
    source .env.local
    # Active posting only (passive bot handles DMs):
    ENABLE_DM_RESPONDER=false python3 monetisation/telegram-active-seller.py

    # Full mode (active posting + DM sales — stop passive bot first):
    python3 monetisation/telegram-active-seller.py

    # Daemon mode:
    setsid python3 monetisation/telegram-active-seller.py > /tmp/telegram-active-seller.log 2>&1 &

No external dependencies — uses only stdlib (urllib, json, time, random, os, threading).
"""

import json
import os
import sys
import time
import random
import threading
import traceback
import urllib.request
import urllib.error
import hashlib
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk",
)
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Feature toggles
ENABLE_DM_RESPONDER = os.environ.get("ENABLE_DM_RESPONDER", "true").lower() in ("true", "1", "yes")
ENABLE_GROUP_POSTING = os.environ.get("ENABLE_GROUP_POSTING", "true").lower() in ("true", "1", "yes")
ENABLE_CHANNEL_POSTING = os.environ.get("ENABLE_CHANNEL_POSTING", "true").lower() in ("true", "1", "yes")

# Rate limiting
GROUP_POST_INTERVAL = int(os.environ.get("GROUP_POST_INTERVAL", "3600"))  # 1 hour between posts per group
CHANNEL_POST_INTERVAL = int(os.environ.get("CHANNEL_POST_INTERVAL", "21600"))  # 6 hours between channel posts
DM_POLL_INTERVAL = 2  # seconds between getUpdates calls
GLOBAL_COOLDOWN = 10  # seconds between ANY outbound message (anti-spam)

# State file — persists post history across restarts
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".active-seller-state.json")

# Owner chat ID for admin commands/notifications
OWNER_CHAT_ID = int(os.environ.get("OWNER_CHAT_ID", "6582544948"))

# ---------------------------------------------------------------------------
# Product catalog (same as passive bot, kept in sync)
# ---------------------------------------------------------------------------
PRODUCTS = {
    "mega_bundle": {
        "name": "MEGA BUNDLE -- All 13 Products",
        "price": "$497",
        "url": "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d",
        "tags": ["rag", "ai", "n8n", "architecture", "evaluation", "debug"],
        "one_liner": "The complete RAG engineering toolkit. 80+ sessions of production experience, packaged.",
    },
    "architecture": {
        "name": "Architecture Blueprint",
        "price": "$197",
        "url": "https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602",
        "tags": ["rag", "architecture", "n8n", "pinecone", "neo4j"],
        "one_liner": "Multi-pipeline RAG system design — Standard, Graph, and Quantitative pipelines.",
    },
    "n8n_workflows": {
        "name": "n8n Workflow Collection",
        "price": "$197",
        "url": "https://buy.stripe.com/bJe00c9PI8Tp2b1a8l5J603",
        "tags": ["n8n", "workflow", "automation", "rag"],
        "one_liner": "7 production n8n workflows for RAG — import and customize.",
    },
    "enterprise_site": {
        "name": "Enterprise Site Template",
        "price": "$197",
        "url": "https://buy.stripe.com/14A6oAaTM4D94j93JX5J604",
        "tags": ["nextjs", "website", "chatbot", "enterprise"],
        "one_liner": "Next.js 15 site with 4 sector verticals and embedded chatbots.",
    },
    "agentic_commerce": {
        "name": "Agentic Commerce Playbook",
        "price": "$197",
        "url": "https://buy.stripe.com/aFa3co9PI5Hd2b11BP5J607",
        "tags": ["ai", "commerce", "agents", "acp"],
        "one_liner": "How to sell to AI agents. The McKinsey $1T market nobody is talking about.",
    },
    "rag_handbook": {
        "name": "RAG Engineering Handbook",
        "price": "$147",
        "url": "https://buy.stripe.com/eVq14g6Dwd9F6rh54h5J606",
        "tags": ["rag", "engineering", "llm", "embeddings"],
        "one_liner": "80+ sessions of RAG engineering knowledge, distilled.",
    },
    "eval_framework": {
        "name": "RAG Eval Framework",
        "price": "$127",
        "url": "https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605",
        "tags": ["rag", "evaluation", "benchmarks", "testing"],
        "one_liner": "61K-question evaluation system from 18 SOTA benchmarks.",
    },
    "ingestion_toolkit": {
        "name": "Ingestion Toolkit",
        "price": "$97",
        "url": "https://buy.stripe.com/dRm7sEfa27PlcPFgwJ5J608",
        "tags": ["rag", "ingestion", "data", "pinecone", "neo4j"],
        "one_liner": "V4 ingestion pipeline: 34K records across 4 sectors.",
    },
    "dashboard_template": {
        "name": "Dashboard Template",
        "price": "$97",
        "url": "https://buy.stripe.com/14AcMYbXQ7PldTJ5S55J60a",
        "tags": ["dashboard", "metrics", "monitoring"],
        "one_liner": "Real-time RAG metrics dashboard. Auto-generates from status.json.",
    },
    "benchmark_dataset": {
        "name": "Benchmark Dataset Toolkit",
        "price": "$67",
        "url": "https://buy.stripe.com/cNi5kwaTMfhN5nd3JX5J60b",
        "tags": ["rag", "benchmarks", "dataset", "evaluation"],
        "one_liner": "61K questions from 18 SOTA benchmarks, pre-categorized by pipeline.",
    },
    "embeddings_service": {
        "name": "Embeddings Service",
        "price": "$67",
        "url": "https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c",
        "tags": ["embeddings", "jina", "self-hosted", "huggingface"],
        "one_liner": "Self-hosted Jina embeddings on HF Spaces. Free, unlimited, drop-in replacement.",
    },
    "debug_playbook": {
        "name": "RAG Debug Playbook",
        "price": "$47",
        "url": "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600",
        "tags": ["rag", "debug", "fixes", "production"],
        "one_liner": "75+ battle-tested fixes. Diagnostic flowcharts. Never debug blind again.",
    },
    "claude_skills": {
        "name": "Claude Code Skills Pack",
        "price": "$47",
        "url": "https://buy.stripe.com/7sY8wIge64D93f53JX5J609",
        "tags": ["claude", "ai", "skills", "automation"],
        "one_liner": "17 custom Claude Code commands for RAG engineering workflows.",
    },
    "agent_context_kit": {
        "name": "Agent Context Kit",
        "price": "$27",
        "url": "https://buy.stripe.com/7sY9AMbXQ4D94j95S55J601",
        "tags": ["claude", "copilot", "cursor", "context"],
        "one_liner": "CLAUDE.md + state files template. Give your AI assistant instant expertise.",
    },
}

# ---------------------------------------------------------------------------
# Content library — value-first posts with natural product mentions
# Each post: tip/insight first, product mention at the end
# ---------------------------------------------------------------------------
VALUE_POSTS = [
    # --- RAG tips ---
    {
        "topic": "rag",
        "title": "HyDE retrieval trick",
        "body": (
            "Quick RAG tip that boosted our retrieval by 5-15%:\n\n"
            "Instead of embedding the user's question directly, ask your LLM to "
            "generate a *hypothetical answer* first, then embed THAT.\n\n"
            "Why? The hypothetical answer is closer in embedding space to the actual "
            "document than the question is.\n\n"
            "This is called HyDE (Hypothetical Document Embedding). Works with any "
            "embedding model, any vector DB.\n\n"
            "We tested this across 10,000+ questions — consistent improvement on "
            "every query type except exact-match lookups."
        ),
        "product": "architecture",
        "cta": "We documented the full multi-pipeline architecture (Standard + Graph + Quant RAG) here:",
    },
    {
        "topic": "rag",
        "title": "SQL generation gotcha",
        "body": (
            "If you're building RAG with SQL generation, here's something that will "
            "save you hours:\n\n"
            "Different LLMs format SQL output differently — even with the SAME prompt:\n"
            "- Llama returns JSON: {\"sql\": \"SELECT ...\"}\n"
            "- Gemma returns markdown: ```sql SELECT ... ```\n"
            "- Some models return raw: SELECT ...\n\n"
            "You NEED multi-strategy extraction:\n"
            "1. Try JSON.parse\n"
            "2. Try regex for code blocks\n"
            "3. Try raw SELECT detection\n\n"
            "Without this, accuracy drops 15-20%. We learned this the hard way "
            "across 80+ debugging sessions."
        ),
        "product": "debug_playbook",
        "cta": "We compiled 75+ production RAG fixes like this into a searchable playbook:",
    },
    {
        "topic": "rag",
        "title": "Phase-gated evaluation",
        "body": (
            "Most RAG systems are tested on 10-50 questions. That tells you almost nothing.\n\n"
            "Here's the evaluation methodology we use:\n\n"
            "Phase 1: 200 questions -> catches infrastructure bugs\n"
            "Phase 2: 500 questions -> catches edge cases\n"
            "Phase 3: 10K questions -> reveals statistical patterns\n"
            "Phase 4: 61K questions -> tests generalization (SOTA benchmarks)\n\n"
            "The jump from Phase 1 to Phase 3 is where everything changes. "
            "A 0.5% failure rate is invisible at 200 questions but means 50 broken queries at 10K.\n\n"
            "Each phase catches a *qualitatively different* class of failures."
        ),
        "product": "eval_framework",
        "cta": "Our full eval framework (61K questions from 18 benchmarks) is available here:",
    },
    {
        "topic": "rag",
        "title": "ILIKE vs exact match",
        "body": (
            "This one fix took our Quantitative RAG from 85% to 95.2% accuracy:\n\n"
            "Replace exact match:\n"
            "  WHERE company = 'BNP Paribas'\n\n"
            "With fuzzy match:\n"
            "  WHERE company ILIKE '%bnp paribas%'\n\n"
            "Why? Entity names have variants:\n"
            "- \"BNP Paribas\"\n"
            "- \"BNP PARIBAS SA\"\n"
            "- \"bnp paribas\"\n\n"
            "Exact match fails silently. Query runs, returns zero rows. "
            "LLM says \"no data found.\" You think the data is missing — "
            "but it's just a case/format mismatch.\n\n"
            "This applies to any RAG system with structured data."
        ),
        "product": "rag_handbook",
        "cta": "More patterns like this in our RAG Engineering Handbook (80+ sessions distilled):",
    },
    # --- n8n tips ---
    {
        "topic": "n8n",
        "title": "n8n disabled nodes gotcha",
        "body": (
            "n8n gotcha that cost us 3 debugging sessions:\n\n"
            "Disabled nodes in n8n still fire HTTP requests.\n\n"
            "Data flows through a disabled node. If that node is an HTTP Request, "
            "the request still executes. The node is 'disabled' for data processing, "
            "not for side effects.\n\n"
            "This is documented nowhere. Found it the hard way.\n\n"
            "Fix: Remove the node entirely, or disconnect it from the flow. "
            "Don't rely on the disable toggle for HTTP nodes."
        ),
        "product": "n8n_workflows",
        "cta": "We have 7 production-tested n8n RAG workflows (ready to import):",
    },
    {
        "topic": "n8n",
        "title": "HF Spaces persistence",
        "body": (
            "Running n8n on HuggingFace Spaces? Here's the #1 thing to know:\n\n"
            "HF Spaces have NO persistent storage by default.\n\n"
            "Your workflows, credentials, and settings vanish on restart. "
            "And restarts happen randomly (idle timeout, Space updates, OOM).\n\n"
            "Fix: Configure n8n to use external PostgreSQL as its database. "
            "Supabase free tier works perfectly (port 5432, NOT 6543).\n\n"
            "We run 9 n8n instances this way. Zero data loss across hundreds of restarts."
        ),
        "product": "architecture",
        "cta": "Full infrastructure setup (9 n8n instances, all free tier) documented here:",
    },
    # --- AI engineering ---
    {
        "topic": "ai",
        "title": "Free-tier LLM stack",
        "body": (
            "Our entire RAG system runs on $0/month infrastructure. Here's the stack:\n\n"
            "LLMs (all free tier):\n"
            "- Llama 3.3 70B (Groq) -> SQL, intent, planning, QA\n"
            "- Gemma 3 27B (OpenRouter) -> fast lightweight tasks\n"
            "- Trinity Large (OpenRouter) -> extraction, summaries\n\n"
            "Infrastructure:\n"
            "- 9 n8n instances on HF Spaces\n"
            "- Pinecone: 77K vectors (100K free limit)\n"
            "- Neo4j Aura: 79K nodes (200K free limit)\n"
            "- Supabase: 40 tables (500MB free)\n"
            "- Self-hosted embeddings on HF Spaces\n\n"
            "Results: 87.5% Standard RAG, 95.2% Quantitative RAG.\n\n"
            "The constraint is throughput, not capability."
        ),
        "product": "mega_bundle",
        "cta": "Everything above (architecture, workflows, eval, debug playbook) in one package:",
    },
    {
        "topic": "ai",
        "title": "Self-hosted embeddings",
        "body": (
            "Burned through your embedding API credits? Here's what we did:\n\n"
            "We deployed the same Jina v3 model on a free HF Space (Gradio + PyTorch).\n\n"
            "Key details:\n"
            "- 1024-dim embeddings, identical to Jina Cloud\n"
            "- Lazy model loading (avoids startup timeout on cpu-basic)\n"
            "- PyTorch 2.4+ needs a monkey-patch for all_tied_weights_keys\n"
            "- Throughput: ~6.3 contexts/min on cpu-basic\n"
            "- Jina-compatible /v1/embeddings endpoint\n\n"
            "Slow? Yes. Free and unlimited? Also yes.\n\n"
            "Drop-in replacement for Jina Cloud API. No code changes needed."
        ),
        "product": "embeddings_service",
        "cta": "Full self-hosted embedding service (code + deployment guide):",
    },
    # --- Claude Code ---
    {
        "topic": "ai",
        "title": "Claude Code context files",
        "body": (
            "One pattern that 10x'd our AI-assisted development:\n\n"
            "Drop a CLAUDE.md file in your project root with:\n"
            "- System identity and role\n"
            "- Infrastructure map (endpoints, credentials, limits)\n"
            "- Core rules (never commit secrets, 1 fix per iteration)\n"
            "- Debug knowledge base (known fixes, patterns)\n"
            "- State file (what happened last session)\n\n"
            "Claude Code, Copilot, and Cursor all read these files automatically.\n\n"
            "Result: Your AI assistant knows every past fix, every endpoint, "
            "every gotcha — without you re-explaining anything.\n\n"
            "We've been doing this across 80+ sessions with Claude Code."
        ),
        "product": "agent_context_kit",
        "cta": "Our exact CLAUDE.md template + state files (battle-tested):",
    },
    # --- Evaluation ---
    {
        "topic": "rag",
        "title": "Graph RAG accuracy is bounded by coverage",
        "body": (
            "Counterintuitive finding from testing Graph RAG at scale:\n\n"
            "Phase 1 (200 questions): 78% accuracy\n"
            "Phase 3 (10K questions): 40.9% accuracy\n\n"
            "The pipeline didn't get worse. More test questions referenced entities "
            "that weren't in the knowledge graph.\n\n"
            "Graph RAG accuracy = graph coverage. Period.\n\n"
            "No amount of retrieval optimization helps if the entity isn't in the graph. "
            "This is the kind of insight that only emerges at scale.\n\n"
            "Lesson: Before optimizing Graph RAG retrieval, measure your entity coverage. "
            "Ingestion quality > retrieval quality for graph-based systems."
        ),
        "product": "benchmark_dataset",
        "cta": "Our 61K benchmark dataset (pre-categorized by pipeline type):",
    },
    # --- Production patterns ---
    {
        "topic": "rag",
        "title": "Pinecone silent failures",
        "body": (
            "Pinecone gotcha that will waste your time:\n\n"
            "If your metadata exceeds 40KB per vector, upserts SILENTLY FAIL.\n\n"
            "No error. No warning. The API returns success. "
            "But when you query, the data isn't there.\n\n"
            "Fix: Trim metadata before upsert. Store large text in a separate DB "
            "(Supabase, etc.) and keep only IDs + small fields in Pinecone metadata.\n\n"
            "We discovered this after 2 days of debugging \"missing\" vectors."
        ),
        "product": "debug_playbook",
        "cta": "75+ fixes like this in our RAG Debug Playbook:",
    },
    {
        "topic": "rag",
        "title": "Reciprocal Rank Fusion",
        "body": (
            "Simple technique that improved our retrieval quality significantly:\n\n"
            "Reciprocal Rank Fusion (RRF)\n\n"
            "Run multiple retrieval methods in parallel:\n"
            "1. Vector search (query embedding)\n"
            "2. Vector search (HyDE embedding)\n"
            "3. BM25 keyword search\n\n"
            "Then merge with RRF: score = 1/(k + rank), k=60\n\n"
            "Why RRF? You don't need to normalize scores across different systems. "
            "Pinecone cosine similarity and BM25 scores are on completely different scales. "
            "RRF uses rank positions only.\n\n"
            "Works with any combination of retrieval methods."
        ),
        "product": "architecture",
        "cta": "Full multi-pipeline architecture with RRF, HyDE, and reranking:",
    },
    # --- Agentic commerce ---
    {
        "topic": "ai",
        "title": "Agentic commerce is coming",
        "body": (
            "McKinsey estimates agentic commerce will be a $1T+ market.\n\n"
            "AI agents (ChatGPT plugins, Copilot, Perplexity) are starting to "
            "make purchasing decisions. Your products need to be discoverable "
            "by machines, not just humans.\n\n"
            "Key actions:\n"
            "- Structured data (JSON-LD) on every product page\n"
            "- ACP (Agent Commerce Protocol) implementation\n"
            "- GEO (Generative Engine Optimization) > SEO\n"
            "- TLDR-first content for AI citation\n\n"
            "By 2027, Semrush predicts GEO will surpass traditional SEO. "
            "The companies that optimize for AI agents now will have a massive advantage."
        ),
        "product": "agentic_commerce",
        "cta": "Our Agentic Commerce Playbook (ACP implementation, GEO strategy):",
    },
]

# ---------------------------------------------------------------------------
# Channel content — longer-form daily posts for @NomosAI channel
# ---------------------------------------------------------------------------
CHANNEL_POSTS = [
    {
        "title": "Daily RAG Stat",
        "body": (
            "RAG SYSTEM STATUS -- {date}\n\n"
            "Standard RAG: 87.5% accuracy (10K questions)\n"
            "Quantitative RAG: 95.2% accuracy (financial queries)\n"
            "Graph RAG: 40.9% (bounded by knowledge graph coverage)\n\n"
            "Total vectors indexed: 77,000+\n"
            "Knowledge graph: 79K nodes, 219K relationships\n"
            "Evaluation questions: 61,661 from 18 SOTA benchmarks\n"
            "Monthly infrastructure cost: $0\n\n"
            "All products: https://lbjlincoln.github.io/rag-dashboard/store.html"
        ),
    },
    {
        "title": "Tip of the Day: Multi-Strategy SQL Extraction",
        "body": (
            "TIP OF THE DAY\n\n"
            "When using LLMs to generate SQL, implement multi-strategy extraction:\n\n"
            "1. Try JSON.parse (Llama often returns {\"sql\": \"...\"})\n"
            "2. Try regex for ```sql ... ``` blocks (Gemma style)\n"
            "3. Try raw SELECT detection (fallback)\n\n"
            "Without this, you lose 15-20% accuracy because LLMs switch "
            "output formats unpredictably.\n\n"
            "This is fix #23 in our RAG Debug Playbook.\n"
            "https://buy.stripe.com/00w7sEd1U2v14j92FT5J600"
        ),
    },
    {
        "title": "Tip of the Day: Embedding API Key Exhaustion",
        "body": (
            "TIP OF THE DAY\n\n"
            "Your embedding API keys WILL run out at the worst possible time.\n\n"
            "Our fix: self-hosted Jina v3 on a free HF Space (Gradio).\n"
            "- Same 1024-dim embeddings\n"
            "- Jina-compatible API endpoint\n"
            "- ~6.3 contexts/min (slow but unlimited)\n"
            "- PyTorch monkey-patch for cpu-basic compatibility\n\n"
            "Drop-in replacement. No code changes in your RAG pipeline.\n\n"
            "Full service code: https://buy.stripe.com/aFa00ce5Y0mT9Dtcgt5J60c"
        ),
    },
    {
        "title": "Tip of the Day: Connection Pooler Ports",
        "body": (
            "TIP OF THE DAY\n\n"
            "Supabase has TWO connection pooler ports:\n"
            "- Port 5432 (session pooler) -> works with psycopg2\n"
            "- Port 6543 (transaction pooler) -> SILENTLY DROPS INSERTS\n\n"
            "No error. No warning. Rows just don't appear.\n\n"
            "This cost us 2 debugging sessions. Always use port 5432 "
            "for applications that need write consistency.\n\n"
            "More gotchas: https://buy.stripe.com/00w7sEd1U2v14j92FT5J600"
        ),
    },
    {
        "title": "Tip of the Day: Phase-Gated Testing",
        "body": (
            "TIP OF THE DAY\n\n"
            "Don't test your RAG on 10 questions and call it production-ready.\n\n"
            "Our methodology:\n"
            "Phase 1: 200 questions (infrastructure bugs)\n"
            "Phase 2: 500 questions (edge cases)\n"
            "Phase 3: 10K questions (statistical patterns)\n"
            "Phase 4: 61K questions (SOTA benchmarks)\n\n"
            "The 3-regression revert rule: if a fix breaks 3+ existing tests, "
            "revert immediately.\n\n"
            "Full eval framework: https://buy.stripe.com/fZu4gs2ng1qX6rh0xL5J605"
        ),
    },
    {
        "title": "Architecture Spotlight: 4-Pipeline RAG",
        "body": (
            "ARCHITECTURE SPOTLIGHT\n\n"
            "Why we use 4 specialized RAG pipelines instead of 1:\n\n"
            "1. Standard RAG -> text retrieval (HyDE + RRF + reranking)\n"
            "2. Graph RAG -> relationship queries (Neo4j traversal)\n"
            "3. Quantitative RAG -> financial data (LLM-generated SQL)\n"
            "4. Orchestrator -> multi-hop (decomposes complex queries)\n\n"
            "Each pipeline has its own data store, retrieval strategy, "
            "and prompt chain. An intent classifier routes queries.\n\n"
            "Single-pipeline RAG treats every query the same. "
            "Specialized pipelines treat every query type optimally.\n\n"
            "Full architecture: https://buy.stripe.com/aFa14g4vob1x3f5bcp5J602"
        ),
    },
    {
        "title": "By the Numbers",
        "body": (
            "NOMOS AI -- BY THE NUMBERS\n\n"
            "80+ engineering sessions\n"
            "61,661 evaluation questions\n"
            "18 SOTA benchmarks\n"
            "1,100+ commits\n"
            "79K knowledge graph nodes\n"
            "219K graph relationships\n"
            "77K+ indexed vectors\n"
            "75+ documented production fixes\n"
            "9 n8n instances\n"
            "3 production pipelines\n"
            "4 sector verticals\n"
            "$0/month infrastructure\n\n"
            "Everything packaged: https://lbjlincoln.github.io/rag-dashboard/store.html"
        ),
    },
    {
        "title": "Product Highlight: MEGA BUNDLE",
        "body": (
            "PRODUCT HIGHLIGHT: MEGA BUNDLE ($497)\n\n"
            "All 13 products. One payment. Lifetime access.\n\n"
            "Includes:\n"
            "- Architecture Blueprint ($197)\n"
            "- n8n Workflow Collection ($197)\n"
            "- Enterprise Site Template ($197)\n"
            "- Agentic Commerce Playbook ($197)\n"
            "- RAG Engineering Handbook ($147)\n"
            "- RAG Eval Framework ($127)\n"
            "- Ingestion Toolkit ($97)\n"
            "- Dashboard Template ($97)\n"
            "- Benchmark Dataset ($67)\n"
            "- Embeddings Service ($67)\n"
            "- Debug Playbook ($47)\n"
            "- Claude Code Skills ($47)\n"
            "- Agent Context Kit ($27)\n\n"
            "Total value: $1,400+\n"
            "Bundle price: $497\n\n"
            "https://buy.stripe.com/6oU7sEaTM3z59Dtdkx5J60d"
        ),
    },
]

# ---------------------------------------------------------------------------
# Target groups/channels — AI/RAG/LLM/n8n communities
# Add group usernames or chat IDs here. The bot must be a member.
# Format: {"id": "@username" or numeric_id, "name": "...", "topics": [...]}
# ---------------------------------------------------------------------------
# IMPORTANT: The bot must be added to these groups/channels MANUALLY first.
# Bots cannot join groups on their own via the API.
# Instructions: Add @Nomos42Bot to each group, then add the group here.
TARGET_GROUPS = [
    # Add groups as you join them. Examples:
    # {"id": "@ai_engineering_chat", "name": "AI Engineering", "topics": ["ai", "rag"]},
    # {"id": "@n8n_community", "name": "n8n Community", "topics": ["n8n", "automation"]},
    # {"id": "@llm_developers", "name": "LLM Developers", "topics": ["ai", "llm"]},
    # {"id": -1001234567890, "name": "RAG Builders", "topics": ["rag"]},
]

# Channel managed by this bot (create via @BotFather or Telegram app, then add bot as admin)
# Set to None until channel is created
CHANNEL_ID = os.environ.get("NOMOS_CHANNEL_ID", None)  # e.g., "@NomosAI" or "-100xxxxxxxxxx"

# ---------------------------------------------------------------------------
# State management — persist across restarts
# ---------------------------------------------------------------------------

def load_state():
    """Load persistent state from disk."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "group_last_post": {},      # group_id -> timestamp
        "group_post_index": {},     # group_id -> last post index
        "channel_last_post": 0,     # timestamp of last channel post
        "channel_post_index": 0,    # index into CHANNEL_POSTS
        "dm_conversations": {},     # chat_id -> {"stage": "...", "interests": [...]}
        "messages_sent": 0,         # total outbound messages
        "started_at": time.time(),
    }


def save_state(state):
    """Persist state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except IOError as e:
        print(f"[WARN] Cannot save state: {e}")


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
        print(f"[API ERROR] {method}: HTTP {e.code} -- {body[:300]}")
        return None
    except Exception as e:
        print(f"[API ERROR] {method}: {e}")
        return None


def send_msg(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send a text message with anti-spam cooldown."""
    time.sleep(GLOBAL_COOLDOWN)  # Anti-spam: wait between messages
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = api_call("sendMessage", payload)
    # Markdown can fail on special chars — retry without parse_mode
    if result is None or not result.get("ok"):
        payload.pop("parse_mode", None)
        result = api_call("sendMessage", payload)
    if result and result.get("ok"):
        print(f"[SENT] -> {chat_id}: {text[:80]}...")
    return result


def send_msg_no_cooldown(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """Send without cooldown (for DM responses where user is waiting)."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = api_call("sendMessage", payload)
    if result is None or not result.get("ok"):
        payload.pop("parse_mode", None)
        result = api_call("sendMessage", payload)
    return result


def make_button(text, url=None, callback_data=None):
    btn = {"text": text}
    if url:
        btn["url"] = url
    if callback_data:
        btn["callback_data"] = callback_data
    return btn


def make_keyboard(rows):
    return {"inline_keyboard": rows}


# ---------------------------------------------------------------------------
# Content selection — picks the right post for a group based on its topics
# ---------------------------------------------------------------------------

def select_post_for_group(group, state):
    """Select the next value post for a group, matching its topics."""
    group_id = str(group["id"])
    group_topics = set(group.get("topics", ["rag", "ai"]))

    # Filter posts matching this group's topics
    matching = []
    for i, post in enumerate(VALUE_POSTS):
        if post["topic"] in group_topics:
            matching.append((i, post))

    if not matching:
        # Fallback: use all posts
        matching = list(enumerate(VALUE_POSTS))

    # Round-robin through matching posts
    last_idx = state["group_post_index"].get(group_id, -1)
    # Find next matching post after last_idx
    for idx, post in matching:
        if idx > last_idx:
            state["group_post_index"][group_id] = idx
            return post

    # Wrap around
    idx, post = matching[0]
    state["group_post_index"][group_id] = idx
    return post


def format_group_post(post):
    """Format a value post for group posting."""
    product = PRODUCTS[post["product"]]
    text = (
        f"{post['body']}\n\n"
        f"---\n"
        f"{post['cta']}\n"
        f"{product['name']} ({product['price']}): {product['url']}"
    )
    return text


def format_channel_post(post):
    """Format a channel post, substituting {date}."""
    now = datetime.now(timezone.utc)
    return post["body"].format(date=now.strftime("%Y-%m-%d"))


# ---------------------------------------------------------------------------
# DM Sales Handler — personalized responses
# ---------------------------------------------------------------------------

# Keywords that trigger specific product recommendations
KEYWORD_PRODUCTS = {
    # RAG keywords
    "rag": ["architecture", "rag_handbook", "mega_bundle"],
    "retrieval": ["architecture", "rag_handbook"],
    "vector": ["architecture", "embeddings_service", "ingestion_toolkit"],
    "embedding": ["embeddings_service", "architecture"],
    "pinecone": ["architecture", "ingestion_toolkit", "debug_playbook"],
    "neo4j": ["architecture", "ingestion_toolkit"],
    "knowledge graph": ["architecture", "ingestion_toolkit"],
    "graph rag": ["architecture", "benchmark_dataset"],
    "reranking": ["architecture", "rag_handbook"],
    "rerank": ["architecture", "rag_handbook"],
    # n8n keywords
    "n8n": ["n8n_workflows", "architecture", "debug_playbook"],
    "workflow": ["n8n_workflows", "architecture"],
    "automation": ["n8n_workflows", "claude_skills"],
    # Evaluation
    "eval": ["eval_framework", "benchmark_dataset"],
    "evaluation": ["eval_framework", "benchmark_dataset"],
    "benchmark": ["eval_framework", "benchmark_dataset"],
    "testing": ["eval_framework", "benchmark_dataset"],
    "accuracy": ["eval_framework", "rag_handbook"],
    # LLM/AI
    "llm": ["rag_handbook", "architecture", "debug_playbook"],
    "claude": ["claude_skills", "agent_context_kit"],
    "copilot": ["agent_context_kit", "claude_skills"],
    "cursor": ["agent_context_kit", "claude_skills"],
    "agent": ["agentic_commerce", "agent_context_kit"],
    "prompt": ["rag_handbook", "debug_playbook"],
    # Data
    "sql": ["architecture", "rag_handbook"],
    "financial": ["architecture", "benchmark_dataset", "ingestion_toolkit"],
    "ingestion": ["ingestion_toolkit", "architecture"],
    "data": ["ingestion_toolkit", "benchmark_dataset"],
    # Debug
    "debug": ["debug_playbook", "rag_handbook"],
    "fix": ["debug_playbook"],
    "error": ["debug_playbook"],
    "bug": ["debug_playbook"],
    "broken": ["debug_playbook"],
    # Infrastructure
    "deploy": ["architecture", "enterprise_site"],
    "huggingface": ["architecture", "embeddings_service"],
    "supabase": ["architecture", "debug_playbook"],
    "dashboard": ["dashboard_template"],
    "metrics": ["dashboard_template", "eval_framework"],
    # Commerce
    "sell": ["agentic_commerce"],
    "commerce": ["agentic_commerce"],
    "website": ["enterprise_site"],
    "nextjs": ["enterprise_site"],
    # Buy signals
    "price": "SHOW_CATALOG",
    "cost": "SHOW_CATALOG",
    "how much": "SHOW_CATALOG",
    "buy": "SHOW_CATALOG",
    "purchase": "SHOW_CATALOG",
    "pay": "SHOW_CATALOG",
    "stripe": "SHOW_CATALOG",
    "bundle": "SHOW_BUNDLE",
    "mega": "SHOW_BUNDLE",
    "everything": "SHOW_BUNDLE",
    "all products": "SHOW_BUNDLE",
}


def find_relevant_products(text):
    """Find products relevant to the user's message."""
    text_lower = text.lower()
    matched_products = {}  # product_id -> match_count

    for keyword, products in KEYWORD_PRODUCTS.items():
        if keyword in text_lower:
            if products == "SHOW_CATALOG":
                return "SHOW_CATALOG"
            if products == "SHOW_BUNDLE":
                return "SHOW_BUNDLE"
            for pid in products:
                matched_products[pid] = matched_products.get(pid, 0) + 1

    if not matched_products:
        return None

    # Sort by relevance (match count)
    sorted_products = sorted(matched_products.items(), key=lambda x: -x[1])
    return [pid for pid, _ in sorted_products[:3]]


def handle_dm(chat_id, text, user_name, state):
    """Handle a DM with personalized sales response."""
    text_lower = text.lower()

    # Greeting
    if any(w in text_lower for w in ["hello", "hi", "hey", "bonjour", "salut", "/start"]):
        msg = (
            f"Hey {user_name}! I'm the Nomos AI assistant.\n\n"
            "I can help you with:\n"
            "- RAG architecture & debugging questions\n"
            "- Finding the right product for your use case\n"
            "- Technical details about our system\n\n"
            "What are you working on? I'll point you to the most relevant resources."
        )
        send_msg_no_cooldown(chat_id, msg)
        return

    # Check for buy signals
    relevant = find_relevant_products(text)

    if relevant == "SHOW_CATALOG":
        show_full_catalog(chat_id)
        return

    if relevant == "SHOW_BUNDLE":
        show_bundle_pitch(chat_id)
        return

    if relevant and isinstance(relevant, list):
        # Answer their question with value, then recommend products
        answer_and_recommend(chat_id, text, relevant, user_name)
        return

    # Generic helpful response
    msg = (
        f"Great question! Here's what I can tell you:\n\n"
        "We built a multi-pipeline RAG system across 80+ sessions, "
        "tested on 61,661 questions from 18 SOTA benchmarks.\n\n"
        "Our results:\n"
        "- Standard RAG: 87.5% accuracy\n"
        "- Quantitative RAG: 95.2% accuracy\n"
        "- Graph RAG: 40.9% (bounded by graph coverage)\n\n"
        "What specifically are you trying to build? I can recommend "
        "the most relevant product from our catalog.\n\n"
        "Or type 'products' to see everything we offer."
    )
    send_msg_no_cooldown(chat_id, msg)


def answer_and_recommend(chat_id, question, product_ids, user_name):
    """Answer with value, then naturally recommend relevant products."""
    # Build product recommendations
    recs = []
    for pid in product_ids[:3]:
        p = PRODUCTS[pid]
        recs.append(f"- {p['name']} ({p['price']}): {p['one_liner']}\n  {p['url']}")

    recs_text = "\n".join(recs)

    msg = (
        f"Based on what you're asking about, here are the most relevant "
        f"resources from our production RAG system:\n\n"
        f"{recs_text}\n\n"
        f"All of these are extracted from a real system tested on 61K+ questions. "
        f"Not theoretical -- battle-tested.\n\n"
        f"Want the whole toolkit? The MEGA BUNDLE ($497) includes all 13 products "
        f"($1,400+ value):\n"
        f"{PRODUCTS['mega_bundle']['url']}"
    )

    kb = make_keyboard([
        [make_button(f"View {PRODUCTS[product_ids[0]]['name']}", url=PRODUCTS[product_ids[0]]["url"])]
        if product_ids else [],
        [make_button("MEGA BUNDLE -- $497", url=PRODUCTS["mega_bundle"]["url"])],
        [make_button("See All Products", url="https://lbjlincoln.github.io/rag-dashboard/store.html")],
    ])
    # Filter out empty rows
    kb["inline_keyboard"] = [row for row in kb["inline_keyboard"] if row]

    send_msg_no_cooldown(chat_id, msg, reply_markup=kb)


def show_full_catalog(chat_id):
    """Show full product catalog with buy links."""
    lines = [
        "Here's our complete product catalog:\n",
        "PREMIUM ($197 each):",
    ]
    premium = ["architecture", "n8n_workflows", "enterprise_site", "agentic_commerce"]
    for pid in premium:
        p = PRODUCTS[pid]
        lines.append(f"  {p['name']} -- {p['url']}")

    lines.append("\nPROFESSIONAL ($67-$147):")
    professional = ["rag_handbook", "eval_framework", "ingestion_toolkit",
                    "dashboard_template", "benchmark_dataset", "embeddings_service"]
    for pid in professional:
        p = PRODUCTS[pid]
        lines.append(f"  {p['name']} ({p['price']}) -- {p['url']}")

    lines.append("\nSTARTER ($27-$47):")
    starter = ["debug_playbook", "claude_skills", "agent_context_kit"]
    for pid in starter:
        p = PRODUCTS[pid]
        lines.append(f"  {p['name']} ({p['price']}) -- {p['url']}")

    lines.append(f"\nMEGA BUNDLE -- All 13 products for $497 (save $900+):")
    lines.append(PRODUCTS["mega_bundle"]["url"])

    lines.append(f"\nFull store: https://lbjlincoln.github.io/rag-dashboard/store.html")

    send_msg_no_cooldown(chat_id, "\n".join(lines))


def show_bundle_pitch(chat_id):
    """Dedicated bundle sales pitch."""
    msg = (
        "THE MEGA BUNDLE -- $497\n\n"
        "All 13 products. One payment. Lifetime access.\n\n"
        "What you get:\n"
        "- 4 Premium products ($197 each)\n"
        "- 6 Professional tools ($67-$147)\n"
        "- 3 Starter kits ($27-$47)\n\n"
        "Total value: $1,400+\n"
        "You save: $900+\n\n"
        "Everything is extracted from a real RAG system tested on "
        "61,661 questions. Not tutorials -- production code, configs, "
        "and documentation.\n\n"
        "\"Buy the bundle. Skip 80 sessions of trial and error.\"\n\n"
        f"{PRODUCTS['mega_bundle']['url']}"
    )
    kb = make_keyboard([
        [make_button("Buy MEGA BUNDLE -- $497", url=PRODUCTS["mega_bundle"]["url"])],
        [make_button("Browse Individual Products",
                     url="https://lbjlincoln.github.io/rag-dashboard/store.html")],
    ])
    send_msg_no_cooldown(chat_id, msg, reply_markup=kb)


# ---------------------------------------------------------------------------
# Admin commands (owner only)
# ---------------------------------------------------------------------------

def handle_admin_command(chat_id, text, state):
    """Handle admin commands from the owner."""
    global CHANNEL_ID

    if chat_id != OWNER_CHAT_ID:
        return False

    parts = text.strip().split(maxsplit=2)
    cmd = parts[0].lower() if parts else ""

    if cmd == "/status":
        uptime = time.time() - state.get("started_at", time.time())
        hours = int(uptime // 3600)
        mins = int((uptime % 3600) // 60)
        msg = (
            f"Active Seller Status\n\n"
            f"Uptime: {hours}h {mins}m\n"
            f"Messages sent: {state.get('messages_sent', 0)}\n"
            f"Groups configured: {len(TARGET_GROUPS)}\n"
            f"Channel: {CHANNEL_ID or 'Not configured'}\n"
            f"DM responder: {'ON' if ENABLE_DM_RESPONDER else 'OFF'}\n"
            f"Group posting: {'ON' if ENABLE_GROUP_POSTING else 'OFF'}\n"
            f"Channel posting: {'ON' if ENABLE_CHANNEL_POSTING else 'OFF'}\n"
        )
        send_msg_no_cooldown(chat_id, msg)
        return True

    if cmd == "/addgroup":
        if len(parts) < 2:
            send_msg_no_cooldown(chat_id, "Usage: /addgroup @username topic1,topic2")
            return True
        group_username = parts[1]
        topics = parts[2].split(",") if len(parts) > 2 else ["rag", "ai"]
        # Verify group exists
        result = api_call("getChat", {"chat_id": group_username})
        if result and result.get("ok"):
            chat_info = result["result"]
            group_entry = {
                "id": group_username,
                "name": chat_info.get("title", group_username),
                "topics": topics,
            }
            # Check if already in list
            existing = [g for g in TARGET_GROUPS if str(g["id"]) == str(group_username)]
            if not existing:
                TARGET_GROUPS.append(group_entry)
                send_msg_no_cooldown(chat_id,
                    f"Added group: {chat_info.get('title', group_username)}\n"
                    f"Topics: {', '.join(topics)}\n"
                    f"Total groups: {len(TARGET_GROUPS)}")
            else:
                send_msg_no_cooldown(chat_id, f"Group already in list: {group_username}")
        else:
            send_msg_no_cooldown(chat_id, f"Cannot access group: {group_username}\nMake sure the bot is a member.")
        return True

    if cmd == "/setchannel":
        if len(parts) < 2:
            send_msg_no_cooldown(chat_id, "Usage: /setchannel @ChannelUsername")
            return True
        CHANNEL_ID = parts[1]
        # Test sending
        result = api_call("getChat", {"chat_id": CHANNEL_ID})
        if result and result.get("ok"):
            send_msg_no_cooldown(chat_id,
                f"Channel set: {result['result'].get('title', CHANNEL_ID)}\n"
                f"ID: {CHANNEL_ID}")
        else:
            send_msg_no_cooldown(chat_id, f"Cannot access channel: {CHANNEL_ID}\nMake sure the bot is an admin.")
        return True

    if cmd == "/posttest":
        # Send a test post to the first group
        if TARGET_GROUPS:
            group = TARGET_GROUPS[0]
            post = select_post_for_group(group, state)
            text = format_group_post(post)
            result = send_msg(group["id"], text)
            if result and result.get("ok"):
                send_msg_no_cooldown(chat_id, f"Test post sent to {group['name']}")
            else:
                send_msg_no_cooldown(chat_id, f"Failed to post to {group['name']}")
        else:
            send_msg_no_cooldown(chat_id, "No groups configured. Use /addgroup first.")
        return True

    if cmd == "/channeltest":
        if CHANNEL_ID:
            post = CHANNEL_POSTS[0]
            text = format_channel_post(post)
            result = send_msg(CHANNEL_ID, text)
            if result and result.get("ok"):
                send_msg_no_cooldown(chat_id, f"Test post sent to channel {CHANNEL_ID}")
            else:
                send_msg_no_cooldown(chat_id, f"Failed to post to channel {CHANNEL_ID}")
        else:
            send_msg_no_cooldown(chat_id, "No channel configured. Use /setchannel first.")
        return True

    if cmd == "/forcepost":
        # Force immediate posting cycle
        send_msg_no_cooldown(chat_id, "Forcing immediate post cycle...")
        post_to_groups(state, force=True)
        post_to_channel(state, force=True)
        send_msg_no_cooldown(chat_id, "Done.")
        return True

    if cmd == "/help" or cmd == "/adminhelp":
        msg = (
            "Admin Commands:\n\n"
            "/status -- Bot status & stats\n"
            "/addgroup @username topic1,topic2 -- Add a target group\n"
            "/setchannel @ChannelName -- Set the managed channel\n"
            "/posttest -- Send test post to first group\n"
            "/channeltest -- Send test post to channel\n"
            "/forcepost -- Force immediate posting cycle\n"
        )
        send_msg_no_cooldown(chat_id, msg)
        return True

    return False


# ---------------------------------------------------------------------------
# Outbound posting — groups
# ---------------------------------------------------------------------------

def post_to_groups(state, force=False):
    """Post value content to target groups, respecting rate limits."""
    if not ENABLE_GROUP_POSTING and not force:
        return

    now = time.time()

    for group in TARGET_GROUPS:
        group_id = str(group["id"])
        last_post = state["group_last_post"].get(group_id, 0)

        if not force and (now - last_post) < GROUP_POST_INTERVAL:
            remaining = int(GROUP_POST_INTERVAL - (now - last_post))
            print(f"[SKIP] {group['name']}: {remaining}s until next post")
            continue

        # Select and format post
        post = select_post_for_group(group, state)
        text = format_group_post(post)

        print(f"[POST] -> {group['name']}: {post['title']}")
        result = send_msg(group["id"], text)

        if result and result.get("ok"):
            state["group_last_post"][group_id] = now
            state["messages_sent"] = state.get("messages_sent", 0) + 1
            save_state(state)
            print(f"[OK] Posted to {group['name']}")
        else:
            print(f"[FAIL] Could not post to {group['name']}")

        # Extra delay between groups to avoid rate limits
        time.sleep(30)


# ---------------------------------------------------------------------------
# Outbound posting — channel
# ---------------------------------------------------------------------------

def post_to_channel(state, force=False):
    """Post content to the managed channel."""
    if not ENABLE_CHANNEL_POSTING and not force:
        return

    if not CHANNEL_ID:
        return

    now = time.time()
    last_post = state.get("channel_last_post", 0)

    if not force and (now - last_post) < CHANNEL_POST_INTERVAL:
        remaining = int(CHANNEL_POST_INTERVAL - (now - last_post))
        print(f"[SKIP] Channel: {remaining}s until next post")
        return

    # Round-robin through channel posts
    idx = state.get("channel_post_index", 0) % len(CHANNEL_POSTS)
    post = CHANNEL_POSTS[idx]

    text = format_channel_post(post)
    print(f"[CHANNEL] -> {CHANNEL_ID}: {post['title']}")

    result = send_msg(CHANNEL_ID, text)
    if result and result.get("ok"):
        state["channel_last_post"] = now
        state["channel_post_index"] = idx + 1
        state["messages_sent"] = state.get("messages_sent", 0) + 1
        save_state(state)
        print(f"[OK] Posted to channel: {post['title']}")
    else:
        print(f"[FAIL] Could not post to channel")


# ---------------------------------------------------------------------------
# DM Responder thread — handles incoming DMs
# ---------------------------------------------------------------------------

def dm_responder_thread(state):
    """Long-polling thread that handles incoming DMs with sales responses."""
    print("[DM] DM responder thread started")
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
                if consecutive_errors > 50:
                    print("[DM] Too many consecutive errors. Responder stopping.")
                    return
                time.sleep(5)
                continue

            consecutive_errors = 0

            for update in updates.get("result", []):
                offset = update["update_id"] + 1

                try:
                    if "message" in update:
                        message = update["message"]
                        chat_id = message["chat"]["id"]
                        chat_type = message["chat"].get("type", "private")
                        text = message.get("text", "").strip()
                        user = message.get("from", {})
                        user_name = user.get("first_name", "there")

                        if not text:
                            continue

                        print(f"[DM] {user_name} ({chat_id}, {chat_type}): {text[:100]}")

                        # Admin commands (owner only, any chat type)
                        if text.startswith("/") and handle_admin_command(chat_id, text, state):
                            continue

                        # Only respond to DMs (private chats), not group messages
                        if chat_type == "private":
                            handle_dm(chat_id, text, user_name, state)

                    elif "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        api_call("answerCallbackQuery", {"callback_query_id": cb_id})

                except Exception:
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("[DM] Responder stopped.")
            return
        except Exception:
            traceback.print_exc()
            consecutive_errors += 1
            time.sleep(5)


# ---------------------------------------------------------------------------
# Main loop — orchestrates outbound posting + DM handling
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Nomos AI Active Seller")
    print("=" * 60)
    print(f"  Token: ...{BOT_TOKEN[-10:]}")
    print(f"  Products: {len(PRODUCTS)}")
    print(f"  Value posts: {len(VALUE_POSTS)}")
    print(f"  Channel posts: {len(CHANNEL_POSTS)}")
    print(f"  Target groups: {len(TARGET_GROUPS)}")
    print(f"  Channel: {CHANNEL_ID or 'Not configured'}")
    print(f"  DM responder: {'ON' if ENABLE_DM_RESPONDER else 'OFF'}")
    print(f"  Group posting: {'ON' if ENABLE_GROUP_POSTING else 'OFF'}")
    print(f"  Channel posting: {'ON' if ENABLE_CHANNEL_POSTING else 'OFF'}")
    print(f"  Group interval: {GROUP_POST_INTERVAL}s ({GROUP_POST_INTERVAL//60}min)")
    print(f"  Channel interval: {CHANNEL_POST_INTERVAL}s ({CHANNEL_POST_INTERVAL//3600}h)")
    print(f"  State file: {STATE_FILE}")
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

    # Load persistent state
    state = load_state()
    state["started_at"] = time.time()
    save_state(state)

    # Start DM responder thread
    if ENABLE_DM_RESPONDER:
        dm_thread = threading.Thread(target=dm_responder_thread, args=(state,), daemon=True)
        dm_thread.start()
        print("[MAIN] DM responder thread started")
    else:
        print("[MAIN] DM responder DISABLED (passive bot handles DMs)")

    # Notify owner
    send_msg_no_cooldown(OWNER_CHAT_ID,
        f"Active Seller started.\n\n"
        f"Groups: {len(TARGET_GROUPS)}\n"
        f"Channel: {CHANNEL_ID or 'Not set'}\n"
        f"DM responder: {'ON' if ENABLE_DM_RESPONDER else 'OFF'}\n\n"
        f"Admin commands: /status, /addgroup, /setchannel, /forcepost, /adminhelp"
    )

    print("[MAIN] Entering main posting loop...\n")
    consecutive_errors = 0

    while True:
        try:
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[CYCLE] {now_str}")

            # Post to groups
            if TARGET_GROUPS:
                post_to_groups(state)
            else:
                print("[SKIP] No groups configured")

            # Post to channel
            if CHANNEL_ID:
                post_to_channel(state)
            else:
                print("[SKIP] No channel configured")

            save_state(state)
            consecutive_errors = 0

            # Sleep until next check (check every 5 minutes)
            print(f"[MAIN] Next check in 300s...")
            time.sleep(300)

        except KeyboardInterrupt:
            print("\n[MAIN] Stopped by user.")
            save_state(state)
            break
        except Exception:
            traceback.print_exc()
            consecutive_errors += 1
            if consecutive_errors > 20:
                print("[FATAL] Too many consecutive errors. Exiting.")
                save_state(state)
                sys.exit(1)
            time.sleep(30)


if __name__ == "__main__":
    main()
