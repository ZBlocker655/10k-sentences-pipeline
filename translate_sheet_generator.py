"""
translate_sheet_generator.py

This script automates the creation of a translated Google Sheet from an English sentence source sheet.
It uses the built-in =GOOGLETRANSLATE() formula, waits for all formulas to resolve, and then copies
translated values into a permanent column. Optional font and formatting options can be applied.

Intended for use in the DIY 10,000 Sentences project.
"""

import os
import sys
import time
import argparse
import json
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

# Load environment variables
load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def is_valid_token_file(file_path):
    """Check if the token file contains valid OAuth JSON credentials."""
    try:
        with open(file_path, 'r', encoding='utf-8') as token_file:
            json.load(token_file)
        return True
    except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError):
        return False


def get_google_credentials():
    """Create credentials from a service account when available, otherwise OAuth."""
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if service_account_file:
        if not os.path.exists(service_account_file):
            raise RuntimeError(
                f"GOOGLE_SERVICE_ACCOUNT_FILE points to a missing file: {service_account_file}"
            )
        return service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=SCOPES,
        )

    oauth_client_file = os.getenv("GOOGLE_OAUTH_CLIENT_FILE")
    if not oauth_client_file:
        raise RuntimeError(
            "Set GOOGLE_SERVICE_ACCOUNT_FILE for service-account auth or "
            "GOOGLE_OAUTH_CLIENT_FILE for OAuth."
        )
    if not os.path.exists(oauth_client_file):
        raise RuntimeError(
            f"GOOGLE_OAUTH_CLIENT_FILE points to a missing file: {oauth_client_file}"
        )

    creds = None
    token_path = "token.json"
    legacy_token_path = "token.pickle"

    if os.path.exists(token_path) and is_valid_token_file(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    elif os.path.exists(legacy_token_path) and is_valid_token_file(legacy_token_path):
        creds = Credentials.from_authorized_user_file(legacy_token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
            flow = InstalledAppFlow.from_client_secrets_file(oauth_client_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    missing_scopes = set(SCOPES) - set(creds.scopes or [])
    if missing_scopes:
        raise RuntimeError(
            "OAuth credentials were granted without the required scopes: "
            f"{', '.join(sorted(missing_scopes))}. Delete token.json and re-authorize, "
            "or configure GOOGLE_SERVICE_ACCOUNT_FILE instead."
        )

    return creds

def get_google_services():
    """Initialize and return Google services."""
    creds = get_google_credentials()
    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    return sheets_service, drive_service

sheets_service = None
drive_service = None

def wait_for_translations(spreadsheet_id, sheet_name, formula_col_letter, start_row, num_rows):
    print("Waiting for Google Translate formulas to resolve...")
    while True:
        range_ = f"{sheet_name}!{formula_col_letter}{start_row}:{formula_col_letter}{start_row + num_rows - 1}"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_
        ).execute()
        values = result.get("values", [])

        pending_rows = 0
        for row in values:
            if not row:
                pending_rows += 1
                continue

            cell_value = str(row[0]).strip()
            if not cell_value or cell_value == "Loading..." or cell_value.startswith("="):
                pending_rows += 1

        if len(values) == num_rows and pending_rows == 0:
            print("All translations completed.")
            return values

        print(f"...still waiting on {max(num_rows - len(values), pending_rows)} rows, sleeping 15 seconds")
        time.sleep(15)


def set_column_font_and_size(spreadsheet_id, sheet_id, column_index, font_family=None, font_size=None):
    requests = []
    if font_family:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": column_index,
                    "endColumnIndex": column_index + 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontFamily": font_family
                        }
                    }
                },
                "fields": "userEnteredFormat.textFormat.fontFamily"
            }
        })
    if font_size:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startColumnIndex": column_index,
                    "endColumnIndex": column_index + 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {
                            "fontSize": font_size
                        }
                    }
                },
                "fields": "userEnteredFormat.textFormat.fontSize"
            }
        })

    if requests:
        body = {"requests": requests}
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body=body).execute()


def auto_resize_columns(spreadsheet_id, sheet_id, start_column_index, end_column_index):
    """
    Auto resize columns in the given sheet from start_column_index (inclusive)
    to end_column_index (exclusive). Zero-based indices.
    """
    requests = [{
        "autoResizeDimensions": {
            "dimensions": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": start_column_index,
                "endIndex": end_column_index
            }
        }
    }]
    body = {"requests": requests}
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body).execute()


def delete_column(spreadsheet_id, sheet_id, column_index):
    """
    Delete a single column from the sheet.
    column_index is zero-based.
    """
    requests = [{
        "deleteDimension": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": column_index,
                "endIndex": column_index + 1
            }
        }
    }]
    body = {"requests": requests}
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body).execute()


def freeze_top_row(spreadsheet_id, sheet_id):
    requests = [{
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {
                    "frozenRowCount": 1
                }
            },
            "fields": "gridProperties.frozenRowCount"
        }
    }]
    body = {"requests": requests}
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body).execute()

def set_row_font(spreadsheet_id, sheet_id, row_index, font_family):
    requests = [{
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row_index,
                "endRowIndex": row_index + 1,
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {
                        "fontFamily": font_family
                    }
                }
            },
            "fields": "userEnteredFormat.textFormat.fontFamily"
        }
    }]
    body = {"requests": requests}
    sheets_service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body).execute()


def fetch_english_sentences(source_sheet_id, source_tab_name):
    print(f"Fetching English sentences from {source_sheet_id} - {source_tab_name}...")
    source_range = f"{source_tab_name}!A1:A"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=source_sheet_id, range=source_range
    ).execute()
    english_sentences = result.get("values", [])
    num_rows = len(english_sentences)

    if num_rows == 0:
        print("No English sentences found in source tab.")
        return None, 0

    print(f"Fetched {num_rows} sentences.")
    return english_sentences, num_rows


def create_destination_sheet(dest_sheet_name, dest_folder_id):
    try:
        file_metadata = {
            "name": dest_sheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet"
        }
        if dest_folder_id:
            file_metadata["parents"] = [dest_folder_id]

        new_sheet = drive_service.files().create(
            body=file_metadata,
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return new_sheet["id"]
    except HttpError as e:
        error_message = f"Failed to create destination sheet: {e}"
        if e.resp is not None and e.resp.status == 403 and b"insufficient" in e.content.lower():
            error_message += (
                " OAuth credentials did not include usable Drive access. "
                "Re-authorize with a Drive-capable OAuth client or configure "
                "GOOGLE_SERVICE_ACCOUNT_FILE as documented in the README."
            )
        print(error_message)
        return None


def populate_destination_sheet(dest_sheet_id, english_sentences, target_lang, num_rows):
    rows = []
    for i, row in enumerate(english_sentences, start=1):
        sid = i
        english = row[0]
        formula = f'=GOOGLETRANSLATE(B{i+1}, "en", "{target_lang}")'
        rows.append([sid, english, formula])

    value_range = {
        "range": "Sheet1!A2:C",
        "majorDimension": "ROWS",
        "values": rows
    }

    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!A2:C",
        body=value_range,
        valueInputOption="USER_ENTERED"
    ).execute()

    # Copy raw translations from column C to D
    translations = [[cell[0]] for cell in wait_for_translations(dest_sheet_id, "Sheet1", "C", 2, num_rows)]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!D2:D",
        body={"values": translations},
        valueInputOption="RAW"
    ).execute()

    # Clear column C (raw translations) to avoid continuous use of formulas
    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!C2:C",
        body={"values": [[""] for _ in range(num_rows)]},
        valueInputOption="RAW"
    ).execute()


def apply_sheet_formatting(dest_sheet_id, sheet_id, num_rows, font_size, target_font):
    # Apply font size to all columns A-D if given
    if font_size:
        for col_index in range(4):
            set_column_font_and_size(dest_sheet_id, sheet_id, col_index, font_size=font_size)

    # Apply font to translated column (D, index 3) if given
    if target_font:
        set_column_font_and_size(dest_sheet_id, sheet_id, 3, font_family=target_font)

    # Auto resize columns B and D
    try:
        auto_resize_columns(dest_sheet_id, sheet_id, 1, 2)  # B
        auto_resize_columns(dest_sheet_id, sheet_id, 3, 4)  # D
    except HttpError as e:
        print(f"Failed to auto-resize columns: {e}")

    delete_column(dest_sheet_id, sheet_id, 2)  # column C is index 2

    header_values = [["sentence_id", "sentence", "translation"]]

    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!A1:C1",
        body={"values": header_values},
        valueInputOption="RAW"
    ).execute()

    # Freeze top row
    freeze_top_row(dest_sheet_id, sheet_id)

    # Set monospace font on the top row (row index 0)
    set_row_font(dest_sheet_id, sheet_id, 0, "Courier New")


def main():
    global sheets_service, drive_service

    parser = argparse.ArgumentParser(description="Generate a translated Google Sheet using formulas.")
    parser.add_argument("--source_sheet_id", required=True)
    parser.add_argument("--source_tab_name", default="Sheet1")
    parser.add_argument("--dest_sheet_name", required=True)
    parser.add_argument("--target_lang", required=True, help="e.g. zh-CN")
    parser.add_argument("--target_font", required=False, help="Optional font for translated column")
    parser.add_argument("--font_size", required=False, type=int, help="Optional font size to apply to all columns")
    parser.add_argument("--dest_folder_id", required=False)
    args = parser.parse_args()

    try:
        sheets_service, drive_service = get_google_services()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    english_sentences, num_rows = fetch_english_sentences(args.source_sheet_id, args.source_tab_name)
    if num_rows == 0:
        return

    dest_sheet_id = create_destination_sheet(args.dest_sheet_name, args.dest_folder_id)
    if not dest_sheet_id:
        return

    populate_destination_sheet(dest_sheet_id, english_sentences, args.target_lang, num_rows)

    print(f"Applying formatting to destination sheet...")

    # Get sheet ID for formatting
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=dest_sheet_id).execute()
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    apply_sheet_formatting(dest_sheet_id, sheet_id, num_rows, args.font_size, args.target_font)

    print(f"✅ Translation sheet created: https://docs.google.com/spreadsheets/d/{dest_sheet_id}")

if __name__ == "__main__":
    main()
