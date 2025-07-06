"""
translate_sheet_generator.py

This script automates the creation of a translated Google Sheet from an English sentence source sheet.
It uses the built-in =GOOGLETRANSLATE() formula, waits for all formulas to resolve, and then copies
translated values into a permanent column. Optional font and formatting options can be applied.

Intended for use in the DIY 10,000 Sentences project.
"""

import os
import time
import argparse
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

# Load environment variables
load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Initialize Google APIs
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
sheets_service = build("sheets", "v4", credentials=creds)
drive_service = build("drive", "v3", credentials=creds)

def wait_for_translations(spreadsheet_id, sheet_name, formula_col_letter, start_row, num_rows):
    print("Waiting for Google Translate formulas to resolve...")
    while True:
        range_ = f"{sheet_name}!{formula_col_letter}{start_row}:{formula_col_letter}{start_row + num_rows - 1}"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_
        ).execute()
        values = result.get("values", [])

        if len(values) == num_rows and all(row and not row[0].startswith("=") for row in values):
            print("All translations completed.")
            return values

        print("...still waiting, sleeping 15 seconds")
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


def main():
    parser = argparse.ArgumentParser(description="Generate a translated Google Sheet using formulas.")
    parser.add_argument("--source_sheet_id", required=True)
    parser.add_argument("--source_tab_name", default="Sheet1")
    parser.add_argument("--dest_sheet_name", required=True)
    parser.add_argument("--target_lang", required=True, help="e.g. zh-CN")
    parser.add_argument("--target_font", required=False, help="Optional font for translated column")
    parser.add_argument("--font_size", required=False, type=int, help="Optional font size to apply to all columns")
    parser.add_argument("--dest_folder_id", required=False)
    args = parser.parse_args()

    source_range = f"{args.source_tab_name}!A1:A"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=args.source_sheet_id, range=source_range
    ).execute()
    english_sentences = result.get("values", [])
    num_rows = len(english_sentences)

    if num_rows == 0:
        print("No English sentences found in source tab.")
        return

    print(f"Fetched {num_rows} sentences. Creating destination sheet...")

    try:
        file_metadata = {
            "name": args.dest_sheet_name,
            "mimeType": "application/vnd.google-apps.spreadsheet"
        }
        if args.dest_folder_id:
            file_metadata["parents"] = [args.dest_folder_id]

        new_sheet = drive_service.files().create(body=file_metadata, fields="id").execute()
        dest_sheet_id = new_sheet["id"]
    except HttpError as e:
        print(f"Failed to create destination sheet: {e}")
        return

    rows = []
    for i, row in enumerate(english_sentences, start=1):
        sid = i
        english = row[0]
        formula = f'=GOOGLETRANSLATE(B{i+1}, "en", "{args.target_lang}")'
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

    wait_for_translations(dest_sheet_id, "Sheet1", "C", 2, num_rows)

    translations = [[cell[0]] for cell in wait_for_translations(dest_sheet_id, "Sheet1", "C", 2, num_rows)]
    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!D2:D",
        body={"values": translations},
        valueInputOption="RAW"
    ).execute()

    sheets_service.spreadsheets().values().update(
        spreadsheetId=dest_sheet_id,
        range="Sheet1!C2:C",
        body={"values": [[""] for _ in range(num_rows)]},
        valueInputOption="RAW"
    ).execute()

    # Get sheet ID for formatting
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=dest_sheet_id).execute()
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    # Apply font size to all columns A-D if given
    if args.font_size:
        for col_index in range(4):
            set_column_font_and_size(dest_sheet_id, sheet_id, col_index, font_size=args.font_size)

    # Apply font to translated column (D, index 3) if given
    if args.target_font:
        set_column_font_and_size(dest_sheet_id, sheet_id, 3, font_family=args.target_font)

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

    print(f"✅ Translation sheet created: https://docs.google.com/spreadsheets/d/{dest_sheet_id}")

if __name__ == "__main__":
    main()
