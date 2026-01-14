# gmail-to-sheets
**Author:** Puneeth Yerninti

Sync unread Gmail messages into a Google Sheet using OAuth 2.0 (installed app flow). No service accounts, append-only writes, duplicate-safe via Gmail message IDs, and processed messages are marked as read.

## Architecture
- Data flow (append-only): Gmail INBOX (unread) → Python parser → Sheets append → mark read → state.json updates.
- Persistence: local `src/state.json` by default; optional sheet-based state (see comments in code).

ASCII view:
```
+----------+     OAuth2      +-------------+    Rows    +---------+
|  Gmail   | <-------------> | Python App  | ------->   | Sheets  |
| INBOX    |  Tokens (local) | (src.main)  |            |  Tab    |
+----------+                 |             | <-------   +---------+
    | Unread IDs             |  state.json |   Mark as read
    v                        +-------------+
```

Add a small hand-drawn PNG of this architecture to `proof/` after you run it.

## Features
- OAuth InstalledAppFlow with token reuse (stored at `src/token.json`).
- Fetch unread INBOX messages, parse sender/subject/date/body.
- Append to a target sheet tab; prevent duplicates via Gmail message IDs.
- Mark processed messages as read.
- Local state persistence (`src/state.json`) with clear hook to switch to sheet-based state.
- Lightweight retries via `tenacity` on Gmail/Sheets calls.

## Setup (one-time)
1. Create a Google Cloud project.
2. Enable **Gmail API** and **Google Sheets API**.
3. Configure OAuth consent screen (External, testing is fine during dev).
4. Create OAuth Client ID (Desktop app) and download `credentials.json` into `credentials/` (do NOT commit).
5. Clone this repo and `cd gmail-to-sheets`.
6. Create a virtualenv: `python -m venv venv` and activate it.
7. Install deps: `pip install -r requirements.txt`.
8. Set your sheet target in [config.py](config.py): `SPREADSHEET_ID` and optionally `SHEET_NAME`, `SUBJECT_FILTER`.
9. Run once interactively to authorize: `python -m src.main` (browser opens for consent; token saved to `src/token.json`).
10. Open your sheet and verify new rows.

## OAuth Flow (Installed App)
- Uses `google-auth-oauthlib` `InstalledAppFlow` with scopes Gmail modify + Sheets.
- First run opens browser; on success, tokens written to `src/token.json` (refresh token included). Do NOT commit.
- Subsequent runs silently refresh using the stored refresh token.

## Duplicate Prevention
- Gmail message IDs are globally unique and stable; they are stored in `src/state.json` under `processed_ids`.
- Each run fetches unread IDs, then ignores any already in state before appending.
- Only after a successful Sheets append do we mark those messages as read and record their IDs.

## State Persistence
- Default: local JSON at `src/state.json` (fast, simple for single-machine use; chosen to keep runs self-contained without extra Sheets round-trips). Do NOT commit.
- Optional: sheet-based state for multi-runner setups. Hooks are stubbed in [src/sheets_service.py](src/sheets_service.py) and referenced in [src/main.py](src/main.py). Implement by reading/writing IDs to a dedicated tab (e.g., State!A:A) and flip `STATE_PERSISTENCE_MODE` in [config.py](config.py).

## Running (manual)
- Activate venv and run: `python -m src.main`.
- Logs show counts appended and skipped.
- Subject filtering: set `SUBJECT_FILTER = "Invoice"` to process only matching subjects (case-insensitive).

## Headless / Scheduled
- Windows Task Scheduler, cron, or a lightweight GitHub Action can invoke `python -m src.main`.
- Ensure the machine has the saved `src/token.json` and `src/state.json` (or implement sheet state) before headless runs.

## Proof of Execution
Place evidence in `proof/`:
- Screenshot of Gmail unread INBOX (showing messages to be pulled).
- Screenshot of Google Sheet tab showing at least 5 appended rows.
- Screenshot/video of first OAuth consent screen and terminal output.
- Screenshot of a second run showing "Appended 0 rows" / "No new messages to append".
- Hand-drawn architecture PNG.
- Mandatory 2–3 min demo video covering setup, first run, sheet result, and duplicate-safe second run.

## Challenge & Solution
- Challenge: Many emails are HTML-only, causing blank bodies.
- Solution: Prefer `text/plain` parts; fall back to `text/html` and convert with `html2text` (BeautifulSoup backup) to keep readable text.

## Limitations
- Local state is per-machine; switch to sheet-based state for multi-runner reliability.
- Very large or attachment-heavy emails are not downloaded; only the text parts are parsed.
- Sheets cell limits still apply; prune old rows or archive if needed.

## Post-submission Modifications (examples)
- Add a Dockerfile wrapping `python -m src.main` with mounted credentials/state.
- Add GitHub Action that runs nightly with cached `token.json` + `state.json` secrets.
- Add a subject regex filter or label filter to narrow processing.
- Write tests around `email_parser` with sample MIME payloads.

## Security
- `.gitignore` already excludes credentials, tokens, and state files. Keep them local.
- Never commit `credentials/credentials.json`, `src/token.json`, or `src/state.json`.

## Quickstart Commands
```
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m src.main
```
