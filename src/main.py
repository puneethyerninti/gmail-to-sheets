"""Main orchestration script to sync unread Gmail messages into Google Sheets.

Steps:
1. Load local state (processed IDs) from state.json (default).
2. Authorize Gmail and Sheets via OAuth InstalledAppFlow (tokens stored at TOKEN_PATH).
3. Fetch unread INBOX messages, filter by SUBJECT_FILTER if set.
4. Parse sender, subject, date, and body to rows.
5. Append rows to the target sheet and mark processed messages as read.
6. Update state with processed message IDs and last_run timestamp.

Note: Do NOT commit credentials, token, or state files.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import config
from src.email_parser import parse_message
from src.gmail_service import (
    authenticate_gmail,
    fetch_unread_message_ids,
    get_message,
    mark_as_read,
)
from src.sheets_service import authenticate_sheets, append_rows


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_state(path: Path) -> Dict:
    if not path.exists():
        return {"processed_ids": [], "last_run": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to read state file, starting fresh: %s", exc)
        return {"processed_ids": [], "last_run": None}


def save_state(path: Path, state: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.info("State saved to %s (DO NOT COMMIT)", path)


def should_skip_subject(subject: str) -> bool:
    if not config.SUBJECT_FILTER:
        return False
    return config.SUBJECT_FILTER.lower() not in (subject or "").lower()


def main() -> int:
    # --- Validate config ---
    if not config.SPREADSHEET_ID or "REPLACE_WITH" in config.SPREADSHEET_ID:
        logger.error("SPREADSHEET_ID is not set in config.py")
        return 1

    state_path = Path(config.STATE_PATH)
    state = load_state(state_path)

    if config.STATE_PERSISTENCE_MODE == "sheet":
        logger.warning(
            "STATE_PERSISTENCE_MODE='sheet' is selected, but this repo currently "
            "implements only local JSON state (state.json). Keeping local state."
        )

    # --- Authenticate ---
    try:
        gmail = authenticate_gmail()
        sheets = authenticate_sheets()
    except Exception as exc:
        logger.error("Authentication failed: %s", exc)
        return 1

    # --- Fetch unread messages ---
    try:
        unread_ids = fetch_unread_message_ids(gmail, max_results=100)
    except Exception as exc:
        logger.error("Failed to fetch unread messages: %s", exc)
        return 1

    processed_ids = set(state.get("processed_ids", []))
    new_ids = [mid for mid in unread_ids if mid not in processed_ids]
    logger.info(
        "%d total unread; %d new after de-duplication",
        len(unread_ids),
        len(new_ids),
    )

    rows: List[List[str]] = []
    ids_to_mark_read: List[str] = []

    # --- Parse and prepare sheet rows ---
    for msg_id in new_ids:
        try:
            raw_message = get_message(gmail, msg_id)
            parsed = parse_message(raw_message)
        except Exception as exc:
            logger.error("Skipping message %s due to error: %s", msg_id, exc)
            continue

        if should_skip_subject(parsed.get("subject", "")):
            logger.info("Skipping message %s due to subject filter", msg_id)
            continue

        row = [
            parsed.get("from", ""),
            parsed.get("subject", ""),
            parsed.get("date", ""),
            parsed.get("body", ""),
        ]
        rows.append(row)
        ids_to_mark_read.append(msg_id)

    # --- Append to Sheets + mark read ---
    if rows:
        try:
            append_rows(sheets, config.SPREADSHEET_ID, config.SHEET_NAME, rows)
        except Exception as exc:
            logger.error("Failed to append rows: %s", exc)
            return 1

        # Mark messages as read only after successful append
        for msg_id in ids_to_mark_read:
            try:
                mark_as_read(gmail, msg_id)
            except Exception as exc:
                logger.error("Failed to mark %s as read: %s", msg_id, exc)

        processed_ids.update(ids_to_mark_read)
        state["processed_ids"] = list(processed_ids)
        logger.info("Appended %d rows to sheet", len(rows))
    else:
        logger.info("No new messages to append")

    # --- Save state ---
    state["last_run"] = datetime.utcnow().isoformat()
    save_state(state_path, state)

    logger.info(
        "Run complete. Appended %d rows. Tracking %d processed IDs.",
        len(rows),
        len(processed_ids),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
