#!/usr/bin/env python3
"""Nomos AI Telegram Bot — Monetisation & Support.

Lightweight bot running on the VM (permanent). No heavy deps.
Handles product sales via Gumroad links, answers basic questions
about Nomos AI products using OpenRouter free models.

Usage:
    source .env.local
    nohup python3 scripts/nomos-telegram-bot.py > /tmp/nomos-bot.log 2>&1 &

Environment:
    TELEGRAM_BOT_TOKEN — Bot token from @BotFather
    OPENROUTER_API_KEY — For AI-powered responses (free models)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

# Config
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8672296360:AAEvfje0wpQkQK2WpgUCwZnPHVvGAlHUNqk")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
ADMIN_CHAT_ID = 6582544948  # Your Telegram user ID
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
POLL_INTERVAL = 2  # seconds

# Gumroad Products
PRODUCTS = {
    "eti": {
        "name": "Nomos ETI Intelligence",
        "desc": "Plateforme RAG multi-pipeline pour ETI françaises. Recherche sémantique, analyse quantitative, graphes de connaissances.",
        "price": "249€/mois",
        "url": "https://nomos42.gumroad.com/l/eti-intelligence",
    },
    "pme": {
        "name": "Nomos PME Connectors",
        "desc": "15 connecteurs SaaS prêts à l'emploi pour PME. Intégration comptabilité, CRM, ERP, documents.",
        "price": "49€/mois",
        "url": "https://nomos42.gumroad.com/l/pme-connectors",
    },
    "dashboard": {
        "name": "Nomos Dashboard Pro",
        "desc": "Tableau de bord temps réel pour vos pipelines RAG. Métriques, alertes, monitoring.",
        "price": "29€/mois",
        "url": "https://nomos42.gumroad.com/l/dashboard-pro",
    },
    "api": {
        "name": "Nomos API Access",
        "desc": "Accès direct aux 3 pipelines RAG via API REST. Standard, Graph, Quantitative.",
        "price": "99€/mois",
        "url": "https://nomos42.gumroad.com/l/api-access",
    },
}

# Bot personality
SYSTEM_PROMPT = """Tu es l'assistant commercial de Nomos AI, une startup française spécialisée dans les solutions RAG (Retrieval-Augmented Generation) pour les ETI et PME.

Ton rôle:
- Présenter les produits Nomos AI de manière professionnelle
- Répondre aux questions sur les fonctionnalités
- Diriger vers les liens d'achat Gumroad
- Être concis, professionnel, et amical

Produits disponibles:
1. ETI Intelligence (249€/mois) — Plateforme RAG complète pour ETI
2. PME Connectors (49€/mois) — 15 connecteurs SaaS pour PME
3. Dashboard Pro (29€/mois) — Monitoring temps réel
4. API Access (99€/mois) — Accès API direct aux pipelines

Site: https://nomos42.gumroad.com
Contact: alexis.moret6@outlook.fr

Réponds TOUJOURS en français sauf si l'utilisateur parle anglais."""


def telegram_api(method, params=None):
    """Call Telegram Bot API."""
    url = f"{API_URL}/{method}"
    if params:
        data = json.dumps(params).encode()
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json"
        })
    else:
        req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        print(f"[ERROR] Telegram API {method}: {e}")
        return None


def send_message(chat_id, text, parse_mode="Markdown"):
    """Send a message."""
    return telegram_api("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    })


def llm_response(user_message, chat_history=None):
    """Get AI response from OpenRouter (free model)."""
    if not OPENROUTER_KEY:
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        messages.extend(chat_history[-6:])  # Last 3 exchanges
    messages.append({"role": "user", "content": user_message})

    payload = json.dumps({
        "model": "arcee-ai/trinity-large-preview:free",
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7,
    }).encode()

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] LLM: {e}")
        return None


def handle_command(chat_id, command, args=""):
    """Handle bot commands."""
    cmd = command.lower().strip()

    if cmd in ("/start", "/aide", "/help"):
        text = """*Bienvenue chez Nomos AI* 🚀

Je suis votre assistant commercial. Voici ce que je peux faire :

/produits — Voir nos solutions
/eti — Solution ETI Intelligence
/pme — Solution PME Connectors
/dashboard — Dashboard Pro
/api — Accès API
/contact — Nous contacter
/demo — Demander une démo

Ou posez-moi directement votre question !"""
        send_message(chat_id, text)

    elif cmd == "/produits":
        text = "*Nos Solutions Nomos AI* 📊\n\n"
        for key, prod in PRODUCTS.items():
            text += f"*{prod['name']}* — {prod['price']}\n"
            text += f"_{prod['desc']}_\n"
            text += f"[Commander]({prod['url']})\n\n"
        send_message(chat_id, text)

    elif cmd in ("/eti", "/pme", "/dashboard", "/api"):
        key = cmd[1:]  # Remove /
        prod = PRODUCTS.get(key)
        if prod:
            text = f"""*{prod['name']}*

{prod['desc']}

💰 *Prix* : {prod['price']}
🔗 [Commander maintenant]({prod['url']})

Des questions ? Demandez-moi !"""
            send_message(chat_id, text)

    elif cmd == "/contact":
        text = """*Contact Nomos AI*

📧 Email : alexis.moret6@outlook.fr
🌐 Gumroad : https://nomos42.gumroad.com
💬 Telegram : Écrivez-moi ici !

Réponse sous 24h."""
        send_message(chat_id, text)

    elif cmd == "/demo":
        text = """*Demande de Démo* 🎯

Pour organiser une démonstration personnalisée :

1. Décrivez votre cas d'usage
2. Précisez votre secteur (Finance, Juridique, BTP, Industrie)
3. Indiquez votre email professionnel

Je transmets directement à notre équipe !"""
        send_message(chat_id, text)
        # Notify admin
        send_message(ADMIN_CHAT_ID,
                     f"🔔 *Demande de démo* de chat {chat_id}")

    else:
        send_message(chat_id, f"Commande inconnue: {cmd}\nTapez /aide pour la liste des commandes.")


def handle_message(message):
    """Handle incoming message."""
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    user = message.get("from", {})
    username = user.get("username", user.get("first_name", "unknown"))

    if not text:
        return

    print(f"[MSG] {username} ({chat_id}): {text[:80]}")

    # Command
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].split("@")[0]  # Remove @botname
        args = parts[1] if len(parts) > 1 else ""
        handle_command(chat_id, cmd, args)
        return

    # Keywords for quick product responses
    text_lower = text.lower()
    if any(w in text_lower for w in ["prix", "tarif", "coût", "combien"]):
        handle_command(chat_id, "/produits")
        return

    if any(w in text_lower for w in ["acheter", "commander", "souscrire", "achat"]):
        text_reply = "Voici nos solutions :\n\n"
        for prod in PRODUCTS.values():
            text_reply += f"• *{prod['name']}* ({prod['price']}) — [Commander]({prod['url']})\n"
        send_message(chat_id, text_reply)
        return

    if any(w in text_lower for w in ["demo", "démo", "essai", "tester"]):
        handle_command(chat_id, "/demo")
        return

    # AI response
    ai_reply = llm_response(text)
    if ai_reply:
        send_message(chat_id, ai_reply, parse_mode="Markdown")
    else:
        # Fallback without AI
        send_message(chat_id,
            "Merci pour votre message ! Tapez /produits pour voir nos solutions "
            "ou /contact pour nous joindre directement.",
            parse_mode="Markdown"
        )

    # Notify admin of new conversations
    if chat_id != ADMIN_CHAT_ID:
        send_message(ADMIN_CHAT_ID,
                     f"💬 *{username}*: {text[:200]}")


def main():
    """Main polling loop."""
    print(f"Nomos AI Telegram Bot starting...")
    print(f"  Token: ...{BOT_TOKEN[-10:]}")
    print(f"  Admin: {ADMIN_CHAT_ID}")
    print(f"  OpenRouter: {'configured' if OPENROUTER_KEY else 'NOT SET (fallback mode)'}")

    # Get bot info
    me = telegram_api("getMe")
    if me and me.get("ok"):
        bot = me["result"]
        print(f"  Bot: @{bot.get('username')} ({bot.get('first_name')})")
    else:
        print("ERROR: Cannot connect to Telegram API")
        sys.exit(1)

    offset = 0
    errors = 0

    while True:
        try:
            updates = telegram_api("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message"],
            })

            if not updates or not updates.get("ok"):
                errors += 1
                if errors > 10:
                    print("Too many errors, exiting")
                    sys.exit(1)
                time.sleep(5)
                continue

            errors = 0
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if msg:
                    try:
                        handle_message(msg)
                    except Exception as e:
                        print(f"[ERROR] Handling message: {e}")

        except KeyboardInterrupt:
            print("\nBot stopped.")
            break
        except Exception as e:
            print(f"[ERROR] Poll: {e}")
            errors += 1
            time.sleep(5)


if __name__ == "__main__":
    main()
