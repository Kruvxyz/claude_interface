import os
from typing import Optional

import httpx
from dotenv import load_dotenv

from utils.schema import InboundMessage

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

PRIORITY_KEYWORDS = {"urgent", "דחוף", "asap", "emergency", "חשוב"}
BOT_MENTION_PREFIX = "@"


def parse_webhook(update: dict) -> InboundMessage:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        raise ValueError("No 'message' field in Telegram update")

    sender = msg["from"]
    chat = msg["chat"]
    chat_type = chat.get("type", "private")
    context_type = "group" if chat_type in ("group", "supergroup", "channel") else "private"
    group_id = str(chat["id"]) if context_type == "group" else None

    text_raw: str = msg.get("text") or msg.get("caption") or ""

    # Detect mention: Telegram sets entities with type="mention" or "text_mention"
    entities = msg.get("entities") or []
    is_mention = any(e.get("type") in ("mention", "text_mention") for e in entities)

    # Strip bot @username from text
    text = " ".join(
        word for word in text_raw.split()
        if not (word.startswith(BOT_MENTION_PREFIX) and len(word) > 1)
    ).strip()

    priority_flag = any(kw in text.lower() for kw in PRIORITY_KEYWORDS)

    # Media extraction
    media: Optional[dict] = None
    if msg.get("photo"):
        largest = max(msg["photo"], key=lambda p: p.get("file_size", 0))
        media = {"type": "image", "file_id": largest["file_id"], "mime": "image/jpeg"}
    elif msg.get("document"):
        doc = msg["document"]
        media = {"type": "document", "file_id": doc["file_id"], "mime": doc.get("mime_type")}
    elif msg.get("voice"):
        media = {"type": "voice", "file_id": msg["voice"]["file_id"], "mime": "audio/ogg"}
    elif msg.get("video"):
        media = {"type": "video", "file_id": msg["video"]["file_id"], "mime": "video/mp4"}

    return InboundMessage(
        channel="telegram",
        sender_id=str(sender["id"]),
        sender_role="unknown",          # resolve from DB later
        context_type=context_type,
        group_id=group_id,
        is_mention=is_mention,
        priority_flag=priority_flag,
        text=text,
        media=media,
        raw_timestamp=msg["date"],
    )


async def send_message(chat_id: str | int, text: str, parse_mode: str = "Markdown") -> dict:
    """POST a message to a Telegram chat via the Bot API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TELEGRAM_API_BASE}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_webhook_info() -> dict:
    """Fetch current webhook info from the Telegram Bot API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{TELEGRAM_API_BASE}/getWebhookInfo")
        response.raise_for_status()
        return response.json()


async def set_webhook(webhook_url: str) -> dict:
    """Register a webhook URL with the Telegram Bot API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TELEGRAM_API_BASE}/setWebhook",
            params={"url": webhook_url},
        )
        response.raise_for_status()
        return response.json()
