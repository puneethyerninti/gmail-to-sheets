"""Email parsing utilities for Gmail message resources."""
from __future__ import annotations

import base64
import logging
from email.utils import parsedate_to_datetime
from typing import Dict, Optional

import html2text
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _decode_body(data: Optional[str]) -> str:
    """Decode a base64url-encoded message body safely."""
    if not data:
        return ""
    try:
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to decode body: %s", exc)
        return ""


def _html_to_text(html: str) -> str:
    """Convert HTML content to plain text using html2text with BeautifulSoup fallback."""
    if not html:
        return ""
    try:
        return html2text.HTML2Text(bodywidth=0).handle(html).strip()
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n").strip()


def _extract_body_from_payload(payload: Dict) -> str:
    """Recursively extract the most useful body text.

    Prefers text/plain parts; falls back to HTML parts if needed.
    """
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    if payload.get("parts"):
        # Multipart: search for the best candidate
        texts = []
        htmls = []
        for part in payload.get("parts", []):
            content = _extract_body_from_payload(part)
            part_mime = part.get("mimeType", "")
            if part_mime.startswith("text/plain"):
                texts.append(content)
            elif part_mime.startswith("text/html"):
                htmls.append(content)
        if texts:
            return "\n\n".join([t for t in texts if t])
        if htmls:
            return "\n\n".join([_html_to_text(h) for h in htmls if h])
        return ""

    if mime_type.startswith("text/plain"):
        return _decode_body(data).strip()

    if mime_type.startswith("text/html"):
        return _html_to_text(_decode_body(data))

    return ""


def _extract_header(headers, name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def parse_message(message: Dict) -> Dict[str, str]:
    """Parse a Gmail message resource into a simplified dict.

    Args:
        message: Gmail API message resource (format="full").

    Returns:
        Dict with keys: id, from, subject, date, body.
    """
    payload = message.get("payload", {})
    headers = payload.get("headers", [])

    from_header = _extract_header(headers, "From")
    subject_header = _extract_header(headers, "Subject")
    date_header = _extract_header(headers, "Date")

    try:
        date_iso = parsedate_to_datetime(date_header).isoformat()
    except Exception:  # pragma: no cover - fallback for malformed dates
        logger.warning("Could not parse date header: %s", date_header)
        date_iso = ""

    body_text = _extract_body_from_payload(payload)

    parsed = {
        "id": message.get("id", ""),
        "from": from_header,
        "subject": subject_header,
        "date": date_iso,
        "body": body_text,
    }
    return parsed
