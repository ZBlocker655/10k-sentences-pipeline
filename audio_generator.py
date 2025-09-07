#!/usr/bin/env python3
"""
audio_generator.py

Generate audio files for translated sentences using Google Cloud Text-to-Speech API,
upload to Google Drive, and update the source Google Sheet with hyperlinks.

Usage:
    python audio_generator.py --sheet_id SHEET_ID --source_tab_name TAB_NAME --dest_folder_id DRIVE_FOLDER_ID --voice_name VOICE_NAME [options]

See --help for full argument details.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
import time
import base64
import logging
from typing import List, Optional, Tuple
import random
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.cloud import texttospeech

# Load environment variables
load_dotenv()

SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
if not SERVICE_ACCOUNT_FILE or not os.path.exists(SERVICE_ACCOUNT_FILE):
    print("Error: GOOGLE_SERVICE_ACCOUNT_FILE is not set or the file does not exist.")
    sys.exit(1)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/cloud-platform'  # Added for TTS API
]

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_google_services():
    """Initialize and return Google services."""
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.getenv("GOOGLE_OAUTH_CLIENT_FILE"), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    sheets_service = build("sheets", "v4", credentials=creds)
    drive_service = build("drive", "v3", credentials=creds)
    tts_client = texttospeech.TextToSpeechClient(credentials=creds)
    return sheets_service, drive_service, tts_client

def read_sheet_column(sheets_service, spreadsheet_id: str, tab_name: str, column_letter: str, start_row: int, force_row_count: Optional[int] = None):
    """Read values from one column in a sheet starting at start_row.

    If force_row_count is provided, ensure the number of rows returned matches force_row_count,
    filling missing rows with empty strings if necessary.
    For text_col_values, trailing blank values are truncated.
    """
    range_end = f"{start_row + force_row_count - 1}" if force_row_count else ""
    range_name = f"{tab_name}!{column_letter}{start_row}:{column_letter}{range_end}"
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    # Flatten values, fill missing with empty strings
    column_values = [row[0] if row else '' for row in values]

    if force_row_count:
        # Ensure the list has exactly force_row_count rows
        while len(column_values) < force_row_count:
            column_values.append('')

    if force_row_count is None:  # Truncate trailing blank values for text_col_values
        while column_values and not column_values[-1].strip():
            column_values.pop()

    return column_values

def update_sheet_cells_with_retry(sheets_service, spreadsheet_id: str, tab_name: str, start_row: int,
                                   column_letter: str, values: List[str], max_retries=5):
    """Write values to a single column starting at start_row with retry logic."""
    range_name = f"{tab_name}!{column_letter}{start_row}:{column_letter}"
    body = {
        'values': [[v] for v in values]
    }

    def update():
        return sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='USER_ENTERED', body=body).execute()

    try:
        return exponential_backoff_retry(update, max_retries=max_retries)
    except HttpError as e:
        logger.error(f"Google Sheets API error while updating cells in range '{range_name}': {e.content}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error while updating cells in range '{range_name}': {e}", exc_info=True)

def ensure_column_header(sheets_service, spreadsheet_id: str, tab_name: str,
                         column_letter: str, header_name: str):
    """Ensure the first row of the column has the header_name."""
    range_name = f"{tab_name}!{column_letter}1"
    body = {'values': [[header_name]]}
    sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption='USER_ENTERED', body=body).execute()

def create_or_get_audio_folder(drive_service, parent_folder_id: str, sheet_name: str) -> str:
    """Create or find the audio folder named '{sheet_name}_Audio' under parent_folder_id."""
    folder_name = f"{sheet_name}_Audio"
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_folder_id}' in parents and trashed=false"
    response = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = response.get('files', [])
    if files:
        folder_id = files[0]['id']
    else:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')

    logger.info(f"Audio folder '{folder_name}' created or found with ID: {folder_id}")
    return folder_id

def get_mime_type(audio_encoding):
    """Return the MIME type for the given audio encoding."""
    mime_type_map = {
        'MP3': 'audio/mpeg',
        'OGG_OPUS': 'audio/ogg',
        'LINEAR16': 'audio/wav'
    }
    return mime_type_map.get(audio_encoding, 'audio/mpeg')

def upload_audio_file(drive_service, folder_id: str, filename: str, audio_content: bytes, audio_encoding: str) -> str:
    """Upload audio bytes as a file to Google Drive folder. Returns shareable link."""
    from googleapiclient.http import MediaInMemoryUpload

    mime_type = get_mime_type(audio_encoding)
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    media = MediaInMemoryUpload(audio_content, mimetype=mime_type, resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()

    logger.info(f"Uploaded file '{filename}' to folder ID: {folder_id}")

    # Return the webViewLink for inline playback
    return file.get('webViewLink')

def synthesize_speech(tts_client, text: str, voice_name: str, speaking_rate: float, audio_encoding: str) -> bytes:
    """Call Google TTS API to synthesize text to audio bytes."""
    # Extract language code from the voice name (e.g., "en-US" from "en-US-Wavenet-D")
    language_code = "-".join(voice_name.split("-")[:2])

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, name=voice_name)
    audio_config = texttospeech.AudioConfig(audio_encoding=getattr(texttospeech.AudioEncoding, audio_encoding),
                                            speaking_rate=speaking_rate)

    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    return response.audio_content

def exponential_backoff_retry(func, max_retries=5, base_delay=1.0, max_delay=16.0):
    """Retry a function with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            logger.warning(f"Retrying after {delay:.2f} seconds due to error: {e}")
            time.sleep(delay)

def synthesize_speech_with_retry(tts_client, text, voice_name, speaking_rate, audio_encoding):
    try:
        return exponential_backoff_retry(lambda: synthesize_speech(tts_client, text, voice_name, speaking_rate, audio_encoding))
    except HttpError as e:
        logger.error(f"Google TTS API error while synthesizing speech for text '{text[:40]}...': {e.content}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error while synthesizing speech for text '{text[:40]}...': {e}", exc_info=True)
        return None

def upload_audio_file_with_retry(drive_service, folder_id, filename, audio_content, audio_encoding):
    try:
        return exponential_backoff_retry(lambda: upload_audio_file(drive_service, folder_id, filename, audio_content, audio_encoding))
    except HttpError as e:
        logger.error(f"Google Drive API error while uploading file '{filename}': {e.content}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error while uploading file '{filename}': {e}", exc_info=True)
        return None

def find_rows_needing_audio(audio_column_values, text_column_values, start_row):
    """Return absolute row numbers for rows needing audio files."""
    rows_needing_audio = []
    for idx, (audio_link, text) in enumerate(zip(audio_column_values, text_column_values)):
        if not text.strip():
            logger.warning(f"Row {start_row + idx} has empty or missing text. Skipping.")
            continue
        if not audio_link.strip():
            rows_needing_audio.append(start_row + idx)  # Absolute row number
    return rows_needing_audio

def process_row(row_num, text, tts_client, drive_service, sheets_service, audio_folder_id, args):
    """Process a single row: synthesize audio, upload it, and update the sheet."""
    if not text.strip():
        logger.warning(f"Row {row_num} text is empty, skipping.")
        return

    logger.info(f"Synthesizing audio for row {row_num}: {text[:40]}...")

    try:
        audio_content = synthesize_speech_with_retry(tts_client, text, args.voice_name, args.speaking_rate, args.audio_encoding)
        if not audio_content:
            return
    except Exception as e:
        logger.error(f"Error synthesizing speech at row {row_num}: {e}", exc_info=True)
        return

    # Get sentence ID for the file name
    id_range = f"{args.source_tab_name}!{args.id_column}{row_num}:{args.id_column}{row_num}"
    id_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=args.sheet_id, range=id_range
    ).execute()
    sentence_id = id_result.get("values", [[]])[0][0] if id_result.get("values") else ""

    if not sentence_id.strip():
        logger.error(f"Row {row_num} is missing a sentence ID. Skipping.")
        return

    # Update the filename generation logic in process_row
    filename = f"sentence_{int(sentence_id):06}.mp3"

    try:
        link = upload_audio_file_with_retry(drive_service, audio_folder_id, filename, audio_content, args.audio_encoding)
        if not link:
            return
        logger.info(f"Uploaded audio for row {row_num}, link: {link}")
    except Exception as e:
        logger.error(f"Error uploading audio file at row {row_num}: {e}", exc_info=True)
        return

    # Update sheet with hyperlink formula
    hyperlink_formula = f'=HYPERLINK("{link}", "{filename}")'
    update_sheet_cells_with_retry(sheets_service, args.sheet_id, args.source_tab_name, row_num, args.audio_link_column, [hyperlink_formula])

def validate_input_parameters(args):
    """Validate input parameters to ensure they are valid and accessible."""
    if args.speaking_rate <= 0:
        logger.error("The --speaking_rate parameter must be greater than 0.")
        sys.exit(1)

def validate_sheet_structure(sheets_service, spreadsheet_id, tab_name, text_column, audio_link_column, id_column):
    """Validate that the sheet has the expected structure with required columns."""
    # Fetch the header values for the specified columns
    text_header_range = f"{tab_name}!{text_column}1"
    audio_link_header_range = f"{tab_name}!{audio_link_column}1"
    id_header_range = f"{tab_name}!{id_column}1"

    text_header_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=text_header_range
    ).execute()
    audio_link_header_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=audio_link_header_range
    ).execute()
    id_header_result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=id_header_range
    ).execute()

    text_header = text_header_result.get("values", [[]])[0][0] if text_header_result.get("values") else ""
    audio_link_header = audio_link_header_result.get("values", [[]])[0][0] if audio_link_header_result.get("values") else ""
    id_header = id_header_result.get("values", [[]])[0][0] if id_header_result.get("values") else ""

    # Validate that the headers are not empty
    if not text_header.strip():
        logger.error(f"The text column '{text_column}' is missing a header in the sheet '{tab_name}'.")
        sys.exit(1)

    if not audio_link_header.strip():
        logger.error(f"The audio link column '{audio_link_column}' is missing a header in the sheet '{tab_name}'.")
        sys.exit(1)

    if not id_header.strip():
        logger.error(f"The ID column '{id_column}' is missing a header in the sheet '{tab_name}'.")
        sys.exit(1)

    # Validate that the headers contain the expected values
    if text_header.lower() != "translation":
        logger.error(f"The text column header in '{tab_name}' must be 'translation', but found '{text_header}'.")
        sys.exit(1)

    if audio_link_header.lower() != "audio_file":
        logger.error(f"The audio link column header in '{tab_name}' must be 'audio_file', but found '{audio_link_header}'.")
        sys.exit(1)

    if id_header.lower() != "sentence_id":
        logger.error(f"The ID column header in '{tab_name}' must be 'sentence_id', but found '{id_header}'.")
        sys.exit(1)

    logger.info(f"Sheet '{tab_name}' structure validated successfully. Text column header: '{text_header}', Audio link column header: '{audio_link_header}', ID column header: '{id_header}'.")

def get_spreadsheet_title(sheets_service, spreadsheet_id):
    """Retrieve the title of the spreadsheet (file name)."""
    spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return spreadsheet.get('properties', {}).get('title', 'Untitled_Sheet')

# Add a test function to verify authentication and SCOPES
def test_google_services(sheets_service, drive_service, tts_client, sheet_id):
    """Test Google services authentication and SCOPES."""
    try:
        # Test Sheets API
        sheets_service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        logger.info("Google Sheets API is working correctly.")

        # Test Drive API
        drive_service.files().list(pageSize=1).execute()
        logger.info("Google Drive API is working correctly.")

        # Test TTS API
        synthesis_input = texttospeech.SynthesisInput(text="Test audio")
        voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Wavenet-D")
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        logger.info("Google Text-to-Speech API is working correctly.")

    except Exception as e:
        logger.error(f"Error during Google services test: {e}", exc_info=True)

def main():
    parser = argparse.ArgumentParser(description="Generate audio files from translated sentences and update Google Sheet.")
    parser.add_argument('--sheet_id', required=True, help='Google Sheet ID')
    parser.add_argument('--source_tab_name', required=True, help='Sheet tab name inside the spreadsheet')
    parser.add_argument('--text_column', default='C', help='Column letter with translated text (default: C)')
    parser.add_argument('--start_row', type=int, default=2, help='Row number to start reading text from (default: 2)')
    parser.add_argument('--audio_link_column', default='D', help='Column letter for audio hyperlinks (default: D)')
    parser.add_argument('--dest_folder_id', required=True, help='Google Drive folder ID where audio subfolder will be created')
    parser.add_argument('--voice_name', required=True, help='Google TTS voice name (e.g., zh-CN-Wavenet-A)')
    parser.add_argument('--speaking_rate', type=float, default=1.0, help='Speaking rate multiplier (default 1.0)')
    parser.add_argument('--audio_encoding', default='MP3', choices=['MP3', 'OGG_OPUS', 'LINEAR16'], help='Audio encoding format (default MP3)')
    parser.add_argument('--max_rows', type=int, default=None, help='Maximum number of rows to process (default: no limit)')
    parser.add_argument('--id_column', default='A', help='Column letter for sentence IDs (default: A)')

    args = parser.parse_args()

    # Validate input parameters
    validate_input_parameters(args)

    # Initialize Google services
    sheets_service, drive_service, tts_client = get_google_services()

    # DEBUG: Test Google services
    logger.info("Testing Google services...")
    test_google_services(sheets_service, drive_service, tts_client, args.sheet_id)

    # Get spreadsheet title for folder naming
    spreadsheet_title = get_spreadsheet_title(sheets_service, args.sheet_id)

    # Ensure audio column header exists
    ensure_column_header(sheets_service, args.sheet_id, args.source_tab_name, args.audio_link_column, 'audio_file')

    # Read translated text column (excluding header)
    text_col_values = read_sheet_column(sheets_service, args.sheet_id, args.source_tab_name,
                                        args.text_column, args.start_row)
    # Read existing audio links column (excluding header)
    audio_col_values = read_sheet_column(sheets_service, args.sheet_id, args.source_tab_name,
                                         args.audio_link_column, args.start_row, force_row_count=len(text_col_values))

    # Ensure the audio column has the same number of rows as the text column
    if len(audio_col_values) != len(text_col_values):
        logger.error(f"Audio column '{args.audio_link_column}' has {len(audio_col_values)} rows, but text column '{args.text_column}' has {len(text_col_values)} rows. They must match.")
        sys.exit(1)

    # Find rows missing audio
    rows_to_process = find_rows_needing_audio(audio_col_values, text_col_values, args.start_row)

    if not rows_to_process:
        logger.info("No rows found that require audio generation. Exiting.")
        sys.exit(0)

    logger.info(f"Found {len(rows_to_process)} rows needing audio.")

    # Create or get audio folder using spreadsheet title
    audio_folder_id = create_or_get_audio_folder(drive_service, args.dest_folder_id, spreadsheet_title)
    logger.info(f"Audio files will be uploaded to folder ID: {audio_folder_id}")

    # Limit rows to process if max_rows is specified
    if args.max_rows is not None:
        rows_to_process = rows_to_process[:args.max_rows]
        logger.info(f"Limiting processing to the first {args.max_rows} rows.")

    # Validate sheet structure
    validate_sheet_structure(sheets_service, args.sheet_id, args.source_tab_name, args.text_column, args.audio_link_column, args.id_column)

    # Process each row
    for row_num in rows_to_process:
        # Get text to synthesize
        idx = row_num - args.start_row
        text = text_col_values[idx]
        process_row(row_num, text, tts_client, drive_service, sheets_service, audio_folder_id, args)

    logger.info("Audio generation complete.")

# Call the test function in main() for debugging purposes
if __name__ == "__main__":
    main()
