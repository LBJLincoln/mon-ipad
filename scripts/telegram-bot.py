#!/usr/bin/env python3
"""
Nomos AI Telegram Bot — Lightweight media cross-analysis bot.
Uses OpenRouter free models for text + vision analysis.
Connects to RAG pipelines for knowledge queries.

Usage:
    source .env.local
    python3 scripts/telegram-bot.py
"""

import os
import sys
import json
import logging
import asyncio
import base64
import httpx
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ── Config ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
N8N_HOST = os.environ.get("N8N_HOST", "https://lbjlincoln-nomos-rag-engine.hf.space")

# Multiple API keys for fallback (rotate on rate limit)
_KEYS = [
    os.environ.get("OPENROUTER_API_KEY", ""),
    os.environ.get("OPENROUTER_KEY_SPARE", ""),
    os.environ.get("OPENROUTER_KEY_STANDARD", ""),
    os.environ.get("OPENROUTER_KEY_GRAPH", ""),
]
OPENROUTER_KEYS = [k for k in _KEYS if k]
_key_idx = 0

def get_key():
    global _key_idx
    key = OPENROUTER_KEYS[_key_idx % len(OPENROUTER_KEYS)]
    return key

def rotate_key():
    global _key_idx
    _key_idx += 1

# Models
VISION_MODEL = "google/gemma-3-27b-it:free"  # Free, supports vision
TEXT_MODEL = "google/gemma-3-27b-it:free"  # Free, fast, less rate-limited
TEXT_MODEL_FALLBACK = "meta-llama/llama-3.3-70b-instruct:free"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# RAG webhook
RAG_WEBHOOK = f"{N8N_HOST}/webhook/rag-multi-index-v3"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("nomos-bot")

# ── Helpers ─────────────────────────────────────────────────────────

async def call_openrouter(messages: list, model: str = TEXT_MODEL, max_tokens: int = 1024) -> str:
    """Call OpenRouter API with key rotation on rate limit."""
    for attempt in range(len(OPENROUTER_KEYS)):
        headers = {
            "Authorization": f"Bearer {get_key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://nomos-ai-pied.vercel.app",
            "X-Title": "Nomos AI Telegram Bot",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            if resp.status_code == 429:
                log.warning(f"Rate limited on key #{_key_idx}, rotating...")
                rotate_key()
                # Try fallback model too
                if model == TEXT_MODEL:
                    payload["model"] = TEXT_MODEL_FALLBACK
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    raise Exception("All API keys rate limited")


async def call_rag(question: str) -> str:
    """Query the RAG Standard pipeline."""
    payload = {"question": question, "pipeline": "standard"}
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            resp = await client.post(RAG_WEBHOOK, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0].get("output", data[0].get("answer", str(data[0])))
                elif isinstance(data, dict):
                    return data.get("output", data.get("answer", str(data)))
                return str(data)
        except Exception as e:
            log.warning(f"RAG query failed: {e}")
    return None


async def analyze_image(image_bytes: bytes, caption: str = "") -> str:
    """Analyze an image using vision model via OpenRouter."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = caption if caption else "Describe this image in detail. What do you see? Provide analysis and insights."

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es Nomos AI, un assistant intelligent specialise dans l'analyse de medias. "
                "Reponds en francais sauf si l'utilisateur parle une autre langue. "
                "Sois precis, perspicace et utile. Fournis des analyses detaillees des images."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                },
            ],
        },
    ]
    return await call_openrouter(messages, model=VISION_MODEL, max_tokens=2048)


async def analyze_document(text: str, filename: str = "") -> str:
    """Analyze document text content."""
    messages = [
        {
            "role": "system",
            "content": (
                "Tu es Nomos AI, un assistant intelligent specialise dans l'analyse de documents. "
                "Reponds en francais. Fournis un resume structure, les points cles, et des insights."
            ),
        },
        {
            "role": "user",
            "content": f"Analyse ce document{f' ({filename})' if filename else ''}:\n\n{text[:8000]}",
        },
    ]
    return await call_openrouter(messages, model=TEXT_MODEL, max_tokens=2048)


# ── Bot Handlers ────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    await update.message.reply_text(
        f"Bonjour {user.first_name} !\n\n"
        "Je suis **Nomos AI**, ton assistant d'analyse intelligent.\n\n"
        "Ce que je peux faire :\n"
        "- Analyser des **photos** et **images**\n"
        "- Analyser des **documents** (PDF, texte)\n"
        "- Repondre a des **questions** avec ma base de connaissances RAG\n"
        "- **Cross-analyser** plusieurs medias ensemble\n\n"
        "Envoie-moi un message, une photo ou un document !",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "**Commandes disponibles :**\n"
        "/start - Message de bienvenue\n"
        "/help - Cette aide\n"
        "/rag <question> - Interroger la base de connaissances\n"
        "/analyze - Analyser le dernier media envoye\n\n"
        "**Usage simple :** Envoie-moi un message texte, une photo, ou un document et je l'analyserai automatiquement.",
        parse_mode="Markdown",
    )


async def cmd_rag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /rag command — query RAG pipeline."""
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text("Usage: /rag <ta question>")
        return

    thinking = await update.message.reply_text("Recherche en cours dans la base de connaissances...")

    answer = await call_rag(question)
    if answer:
        await thinking.edit_text(f"**Reponse RAG :**\n\n{answer[:4000]}", parse_mode="Markdown")
    else:
        # Fallback to LLM
        messages = [
            {"role": "system", "content": "Tu es Nomos AI. Reponds de maniere precise et utile en francais."},
            {"role": "user", "content": question},
        ]
        answer = await call_openrouter(messages)
        await thinking.edit_text(f"**Reponse :**\n\n{answer[:4000]}", parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages."""
    thinking = await update.message.reply_text("Analyse de l'image en cours...")

    try:
        photo = update.message.photo[-1]  # Highest resolution
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        caption = update.message.caption or ""
        analysis = await analyze_image(bytes(image_bytes), caption)

        await thinking.edit_text(f"**Analyse :**\n\n{analysis[:4000]}", parse_mode="Markdown")
    except Exception as e:
        log.error(f"Photo analysis error: {e}")
        await thinking.edit_text(f"Erreur lors de l'analyse: {str(e)[:200]}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle document messages."""
    doc = update.message.document
    thinking = await update.message.reply_text(f"Analyse du document *{doc.file_name}* en cours...", parse_mode="Markdown")

    try:
        file = await context.bot.get_file(doc.file_id)
        doc_bytes = await file.download_as_bytearray()

        # Check if image
        mime = doc.mime_type or ""
        if mime.startswith("image/"):
            analysis = await analyze_image(bytes(doc_bytes), update.message.caption or "")
        else:
            # Try to decode as text
            try:
                text = doc_bytes.decode("utf-8", errors="replace")
            except Exception:
                text = str(doc_bytes[:5000])
            analysis = await analyze_document(text, doc.file_name)

        await thinking.edit_text(f"**Analyse de {doc.file_name} :**\n\n{analysis[:4000]}", parse_mode="Markdown")
    except Exception as e:
        log.error(f"Document analysis error: {e}")
        await thinking.edit_text(f"Erreur lors de l'analyse: {str(e)[:200]}")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages."""
    await update.message.reply_text(
        "J'ai recu ton message vocal. La transcription audio sera bientot disponible.\n"
        "En attendant, envoie-moi le contenu en texte et je l'analyserai !"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    text = update.message.text
    if not text:
        return

    thinking = await update.message.reply_text("Reflexion en cours...")

    # Try RAG first for knowledge questions
    rag_keywords = ["qu'est", "quel", "combien", "comment", "pourquoi", "who", "what", "how", "gdp", "revenue", "company"]
    is_knowledge_q = any(kw in text.lower() for kw in rag_keywords)

    rag_answer = None
    if is_knowledge_q:
        rag_answer = await call_rag(text)

    if rag_answer:
        await thinking.edit_text(f"**Reponse (base de connaissances) :**\n\n{rag_answer[:4000]}", parse_mode="Markdown")
    else:
        # Use LLM directly
        messages = [
            {
                "role": "system",
                "content": (
                    "Tu es Nomos AI, un assistant intelligent et polyvalent. "
                    "Reponds en francais de maniere claire, precise et utile. "
                    "Tu peux analyser des textes, repondre a des questions, et fournir des insights."
                ),
            },
            {"role": "user", "content": text},
        ]
        answer = await call_openrouter(messages)
        await thinking.edit_text(f"{answer[:4000]}", parse_mode="Markdown")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    log.error(f"Error: {context.error}", exc_info=context.error)


# ── Main ────────────────────────────────────────────────────────────

def main():
    if not OPENROUTER_KEYS:
        log.error("No OpenRouter API keys found. Run: source .env.local")
        sys.exit(1)

    log.info(f"Starting Nomos AI Telegram Bot...")
    log.info(f"  Model (text): {TEXT_MODEL}")
    log.info(f"  Model (vision): {VISION_MODEL}")
    log.info(f"  RAG endpoint: {RAG_WEBHOOK}")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("rag", cmd_rag))

    # Media handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    # Text handler (last, catches all text)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Error handler
    app.add_error_handler(error_handler)

    log.info("Bot started — polling for updates...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
