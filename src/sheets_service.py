"""
Google Sheets helper functions.

Provides:
- OAuth authentication (InstalledAppFlow) using the same token.json as Gmail
- Append rows to a Google Sheet tab

NOTE:
- Do NOT commit credentials.json / token.json / state.json
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, List, Sequence, Optional

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

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), config.SCOPES)
        logger.debug("Loaded existing token for Sheets from %s", token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token for Sheets...")
            creds.refresh(Request())
        else:
            logger.info("Running OAuth flow for Sheets (browser will open)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                config.CLIENT_SECRETS_FILE,
                config.SCOPES,
            )
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Saved token to %s (DO NOT COMMIT)", token_path)

    return creds


def authenticate_sheets():
    """
    Build and return authenticated Sheets API client.
    """
    creds = _load_credentials()
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=6))
def append_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    rows: Sequence[Sequence[str]],
) -> None:
    """
    Append rows to a sheet tab.

    Args:
        service: Sheets API service instance.
        spreadsheet_id: Target spreadsheet ID.
        sheet_name: Name of the sheet tab.
        rows: List of rows. Each row: [From, Subject, Date, Content]
    """
    if not rows:
        logger.info("No rows to append")
        return

    range_notation = f"{sheet_name}!A:D"
    body = {"values": [list(r) for r in rows]}

    try:
        (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_notation,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        logger.info("Appended %d rows to %s", len(rows), range_notation)
    except HttpError as err:
        logger.error("Failed to append rows: %s", err)
        raise


# Optional: sheet-based state storage helpers (bonus/upgrade)
# Implement these if you want STATE_PERSISTENCE_MODE = "sheet"
# def read_processed_ids_from_sheet(service, spreadsheet_id: str, tab_name: str = "State") -> List[str]:
#     raise NotImplementedError
#
# def write_processed_ids_to_sheet(service, spreadsheet_id: str, ids: Iterable[str], tab_name: str = "State") -> None:
#     raise NotImplementedError
