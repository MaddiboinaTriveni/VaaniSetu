"""
VaaniSetu — SMS / WhatsApp Fallback
Handles incoming WhatsApp messages (document photos) and replies with
plain-language legal summaries. Works on 2G feature phones via SMS.
"""
import logging
import httpx
import os
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM

logger = logging.getLogger(__name__)

TWILIO_AVAILABLE = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
                        and TWILIO_ACCOUNT_SID != "your_twilio_account_sid")


def _format_sms_message(summary: dict, target_lang: str = "telugu") -> str:
    """Format summary dict into a WhatsApp-friendly message."""
    urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
        summary.get("urgency", "medium"), "🟡"
    )

    lines = [
        "📜 *VaaniSetu Legal Summary*",
        "──────────────",
        f"{urgency_emoji} *Document:* {summary.get('document_type', 'Legal Notice')}",
        "",
        f"👥 *From/To:* {summary.get('parties', 'See document')}",
        "",
        f"⚠️ *What you must do:*\n{summary.get('action_required', 'Read carefully')}",
        "",
        f"❗ *If ignored:*\n{summary.get('consequence', 'Legal action may follow')}",
    ]

    if summary.get("key_date"):
        lines.append(f"\n📅 *Important date:* {summary['key_date']}")

    lines.extend([
        "",
        "──────────────",
        "📱 For voice explanation in your language, download the VaaniSetu app.",
        "📞 NALSA Legal Aid: 15100 (free)",
    ])

    return "\n".join(lines)[:1600]  # WhatsApp message limit


def send_whatsapp_summary(to_number: str, summary: dict, target_lang: str = "telugu") -> dict:
    """
    Send legal document summary via WhatsApp.

    Args:
        to_number: Recipient WhatsApp number (e.g. "whatsapp:+919876543210")
        summary: Summary dict from summarize module
        target_lang: Target language

    Returns:
        dict with: success, message_sid or error
    """
    if not TWILIO_AVAILABLE:
        logger.warning("Twilio not configured — SMS not sent (mock mode)")
        return {
            "success": False,
            "mock": True,
            "message": "Twilio credentials not configured. Add to .env file.",
            "formatted_message": _format_sms_message(summary, target_lang),
        }

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        message_body = _format_sms_message(summary, target_lang)

        # Ensure number has whatsapp: prefix
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        msg = client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number,
            body=message_body,
        )

        logger.info(f"WhatsApp sent: {msg.sid} → {to_number}")
        return {
            "success": True,
            "message_sid": msg.sid,
            "to": to_number,
            "status": msg.status,
        }

    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return {"success": False, "error": str(e)}


async def download_twilio_media(media_url: str) -> bytes:
    """Download media attachment from incoming WhatsApp message."""
    auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    async with httpx.AsyncClient() as client:
        resp = await client.get(media_url, auth=auth, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.content


def parse_webhook_form(form_data: dict) -> dict:
    """
    Parse Twilio WhatsApp webhook form data.

    Returns normalized dict with: from_number, body, media_url, has_media
    """
    return {
        "from_number": form_data.get("From", ""),
        "to_number": form_data.get("To", ""),
        "body": form_data.get("Body", "").strip(),
        "media_url": form_data.get("MediaUrl0", ""),
        "media_content_type": form_data.get("MediaContentType0", ""),
        "has_media": bool(form_data.get("MediaUrl0")),
        "num_media": int(form_data.get("NumMedia", "0")),
    }
