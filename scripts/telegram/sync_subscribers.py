#!/usr/bin/env python3
"""
@Nomos42Picks subscriber sync — processes Stripe webhook events.

Reads pending/ events dropped by the Vercel webhook, invites users to the
private Telegram channel, and moves records to active/ or cancelled/.

Cron (every 5 min):
  */5 * * * * set -a && . /home/termius/mon-ipad/.env.local && set +a && \
    python3 /home/termius/mon-ipad/scripts/telegram/sync_subscribers.py \
    >> /home/termius/mon-ipad/logs/sync-subscribers.log 2>&1
"""

import json
import os
import shutil
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PENDING = ROOT / "data" / "subscribers" / "pending"
ACTIVE = ROOT / "data" / "subscribers" / "active"
CANCELLED = ROOT / "data" / "subscribers" / "cancelled"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_TELEGRAM_ID", "6582544948")
PICKS_CHANNEL = os.environ.get("PICKS_CHANNEL_ID", "@Nomos42Picks")

DRY_RUN = "--dry-run" in sys.argv

ACTIVATE_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
}
DEACTIVATE_EVENTS = {
    "customer.subscription.deleted",
    "invoice.payment_failed",
}
UPDATE_EVENTS = {
    "customer.subscription.updated",
}


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tg_api(method: str, params: dict) -> dict:
    if DRY_RUN:
        print(f"  [DRY] tg/{method} {params}")
        return {"ok": True, "result": {"dry": True}}
    if not BOT_TOKEN:
        return {"ok": False, "description": "no_bot_token"}
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=data), timeout=15
        ) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"ok": False, "description": str(e)}


def send_admin(text: str):
    tg_api("sendMessage", {
        "chat_id": ADMIN_ID,
        "text": text,
        "parse_mode": "HTML",
    })


def create_invite_link() -> str | None:
    result = tg_api("createChatInviteLink", {
        "chat_id": PICKS_CHANNEL,
        "member_limit": 1,
        "name": f"sub-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
    })
    if result.get("ok"):
        return result["result"].get("invite_link")
    print(f"  [WARN] invite link failed: {result.get('description')}", file=sys.stderr)
    return None


def get_chat_member(user_id: str) -> str | None:
    result = tg_api("getChatMember", {
        "chat_id": PICKS_CHANNEL,
        "user_id": user_id,
    })
    if result.get("ok"):
        return result["result"].get("status")
    return None


def ban_member(user_id: str) -> bool:
    result = tg_api("banChatMember", {
        "chat_id": PICKS_CHANNEL,
        "user_id": user_id,
    })
    return result.get("ok", False)


def strip_pii(event: dict) -> dict:
    safe = dict(event)
    email = safe.get("customer_email")
    if email and "@" in email:
        local, domain = email.rsplit("@", 1)
        safe["customer_email"] = f"{local[:2]}***@{domain}"
    return safe


def process_activate(filepath: Path, event: dict):
    tg_user = event.get("telegram_username")
    email = event.get("customer_email", "unknown")
    sub_id = event.get("subscription_id", "?")

    print(f"  [ACTIVATE] sub={sub_id} tg=@{tg_user} email={email}")

    invite_link = None
    if tg_user:
        invite_link = create_invite_link()

    safe = strip_pii(event)
    safe["processed_at"] = ts()
    safe["invite_link"] = invite_link
    safe["sync_status"] = "invite_sent" if invite_link else "no_tg_user"

    dest = ACTIVE / filepath.name
    dest.write_text(json.dumps(safe, indent=2))
    filepath.unlink()

    if invite_link and tg_user:
        send_admin(
            f"💰 <b>New subscriber!</b>\n"
            f"@{tg_user} — {sub_id}\n"
            f"Invite: {invite_link}"
        )
    elif not tg_user:
        send_admin(
            f"⚠️ <b>New subscriber — no Telegram username!</b>\n"
            f"Email: {email[:20]}… | sub: {sub_id}\n"
            f"Ask them to provide @username."
        )


def process_deactivate(filepath: Path, event: dict):
    sub_id = event.get("subscription_id", "?")
    tg_user = event.get("telegram_username")

    print(f"  [DEACTIVATE] sub={sub_id} tg=@{tg_user}")

    safe = strip_pii(event)
    safe["processed_at"] = ts()
    safe["sync_status"] = "cancelled"

    dest = CANCELLED / filepath.name
    dest.write_text(json.dumps(safe, indent=2))
    filepath.unlink()

    if sub_id != "?":
        for active_file in ACTIVE.glob("*.json"):
            try:
                active_evt = json.loads(active_file.read_text())
                if active_evt.get("subscription_id") == sub_id:
                    active_evt["cancelled_at"] = ts()
                    cancel_dest = CANCELLED / active_file.name
                    cancel_dest.write_text(json.dumps(active_evt, indent=2))
                    active_file.unlink()
                    print(f"    moved active/{active_file.name} → cancelled/")
            except Exception:
                pass

    send_admin(
        f"🚫 <b>Subscription cancelled</b>\n"
        f"@{tg_user or '?'} — {sub_id}"
    )


def process_update(filepath: Path, event: dict):
    status = event.get("status", "")
    sub_id = event.get("subscription_id", "?")

    print(f"  [UPDATE] sub={sub_id} status={status}")

    if status in ("canceled", "unpaid", "past_due"):
        process_deactivate(filepath, event)
    elif status == "active":
        process_activate(filepath, event)
    else:
        safe = strip_pii(event)
        safe["processed_at"] = ts()
        safe["sync_status"] = f"updated_{status}"
        dest = ACTIVE / filepath.name
        dest.write_text(json.dumps(safe, indent=2))
        filepath.unlink()


def main():
    PENDING.mkdir(parents=True, exist_ok=True)
    ACTIVE.mkdir(parents=True, exist_ok=True)
    CANCELLED.mkdir(parents=True, exist_ok=True)

    pending_files = sorted(PENDING.glob("*.json"))
    if not pending_files:
        return

    print(f"[{ts()}] Processing {len(pending_files)} pending event(s)...")

    for filepath in pending_files:
        try:
            event = json.loads(filepath.read_text())
        except Exception as e:
            print(f"  [ERROR] bad JSON in {filepath.name}: {e}", file=sys.stderr)
            continue

        event_type = event.get("event_type", "")
        print(f"  {filepath.name}: {event_type}")

        if event_type in ACTIVATE_EVENTS:
            process_activate(filepath, event)
        elif event_type in DEACTIVATE_EVENTS:
            process_deactivate(filepath, event)
        elif event_type in UPDATE_EVENTS:
            process_update(filepath, event)
        else:
            print(f"    [SKIP] unhandled event type: {event_type}")
            safe = strip_pii(event)
            safe["processed_at"] = ts()
            safe["sync_status"] = "skipped"
            dest = ACTIVE / filepath.name
            dest.write_text(json.dumps(safe, indent=2))
            filepath.unlink()

    active_count = len(list(ACTIVE.glob("*.json")))
    print(f"  Active subscribers: {active_count}")


if __name__ == "__main__":
    main()
