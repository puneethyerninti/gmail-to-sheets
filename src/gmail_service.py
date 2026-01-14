"""
Gmail service helpers.

Handles OAuth authentication (InstalledAppFlow) and Gmail operations:
- listing unread messages
- fetching full messages
- marking messages as read

Tokens are stored in config.TOKEN_PATH; DO NOT COMMIT token/state/credentials.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

import config

logger = logging.getLogger(__name__)


def _load_credentials() -> Credentials:
    """
    Load OAuth credentials. Refresh if expired, otherwise run installed-app flow.
    Saves token to TOKEN_PATH for reuse on next run.
    """
    token_path = Path(config.TOKEN_PATH)
    creds: Optional[Credentials] = None

    # Load existing token.json if exists
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.SCOPES)
        logger.debug("Loaded existing token from %s", token_path)

    # If no valid creds -> refresh or new login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            logger.info("Running OAuth InstalledAppFlow (browser will open)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CLIENT_SECRETS_FILE,
                config.SCOPES,
            )
            creds = flow.run_local_server(port=0)

        # Save token for future runs
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Saved token to %s (DO NOT COMMIT)", token_path)

    return creds


def authenticate_gmail():
    """
    Build and return authenticated Gmail API service.
    """
    creds = _load_credentials()
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def fetch_unread_message_ids(service, max_results: int = 50) -> List[str]:
    """
    Fetch unread message IDs from INBOX.
    """
    try:
        response = (
            service.users()
            .messages()
            .list(
                userId="me",
                labelIds=["INBOX"],
                q="is:unread",
                maxResults=max_results,
            )
            .execute()
        )
    except HttpError as err:
        logger.error("Failed to list unread messages: %s", err)
        raise

    messages = response.get("messages", [])
    ids = [m["id"] for m in messages]
    logger.info("Fetched %d unread message IDs", len(ids))
    return ids


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def get_message(service, msg_id: str) -> Dict:
    """
    Get full Gmail message by ID.
    """
    try:
        message = (
            service.users()
            .messages()
            .get(userId="me", id=msg_id, format="full")
            .execute()
        )
        return message
    except HttpError as err:
        logger.error("Failed to fetch message %s: %s", msg_id, err)
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def mark_as_read(service, msg_id: str) -> None:
    """
    Mark Gmail message as read by removing the UNREAD label.
    """
    try:
        (
            service.users()
            .messages()
            .modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]})
            .execute()
        )
        logger.debug("Marked message %s as read", msg_id)
    except HttpError as err:
        logger.error("Failed to mark message %s as read: %s", msg_id, err)
        raise
