import os

import httpx
from dotenv import load_dotenv

from utils.schema import InboundMessage

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_API_BASE = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}"

PRIORITY_KEYWORDS = {"urgent", "דחוף", "asap", "emergency", "חשוב"}


def parse_whatsapp_webhook(form: dict) -> InboundMessage:
    """
    Parse an incoming Twilio WhatsApp webhook (application/x-www-form-urlencoded).

    Key fields Twilio sends:
      From        — "whatsapp:+972501234567"
      To          — "whatsapp:+14155238886"  (your Twilio number)
      Body        — message text
      NumMedia    — number of media attachments
      MediaUrl0   — URL of first media item
      MediaContentType0 — MIME type of first media item
      ProfileName — sender's WhatsApp display name
    """
    raw_from: str = form.get("From", "")
    sender_id = raw_from.removeprefix("whatsapp:").strip()

    text = form.get("Body", "").strip()
    priority_flag = any(kw in text.lower() for kw in PRIORITY_KEYWORDS)

    # Twilio WA webhooks are always 1-to-1 (no native group support via API)
    context_type = "private"

    # Media extraction (Twilio supports up to 10 items; we capture the first)
    media = None
    if int(form.get("NumMedia", 0)) > 0:
        media = {
            "type": form.get("MediaContentType0", "").split("/")[0] or "file",
            "url": form.get("MediaUrl0"),
            "mime": form.get("MediaContentType0"),
        }

    return InboundMessage(
        channel="whatsapp",
        sender_id=sender_id,
        sender_role="unknown",      # resolve from DB later
        context_type=context_type,
        group_id=None,
        is_mention=False,           # WA via Twilio has no mention concept
        priority_flag=priority_flag,
        text=text,
        media=media,
        raw_timestamp=0,            # Twilio does not send a message timestamp in the webhook body
    )


async def get_account_info() -> dict:
    """Fetch Twilio account info to verify credentials are valid."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{TWILIO_API_BASE}.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        )
        response.raise_for_status()
        return response.json()


async def send_whatsapp_message(recipient_number: str, sender_number: str, text: str) -> dict:
    """Send a WhatsApp message via the Twilio API.

    Args:
        recipient_number: recipient in E.164 format, e.g. "+972501234567"
        sender_number:    your Twilio WhatsApp number, e.g. "+14155238886"
        text:             message body
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TWILIO_API_BASE}/Messages.json",
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            data={
                "From": f"whatsapp:{sender_number}",
                "To": f"whatsapp:{recipient_number}",
                "Body": text,
            },
        )
        response.raise_for_status()
        return response.json()
