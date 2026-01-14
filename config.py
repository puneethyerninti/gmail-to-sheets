# config.py — edit before running
SPREADSHEET_ID = "114nS9ZZEkv_J9BGgfshCq0rz1v8qJ_-5cVCoU4zJtjw"  # edit this
SHEET_NAME = "Sheet1"
TOKEN_PATH = "src/token.json"
STATE_PATH = "src/state.json"
CLIENT_SECRETS_FILE = "credentials/credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets"
]
# Optional subject filter: set to a substring to only process emails whose subject contains it
SUBJECT_FILTER = SUBJECT_FILTER = "TEST"
  # e.g. "Invoice"
# State persistence mode: "local" (default) or "sheet"
STATE_PERSISTENCE_MODE = "local"
