# Language Sentence Toolkit for 10,000 Sentences Method

This repository contains Python scripts designed to help language learners build a personalized sentence-based study system. The tools enable you to extract, translate, and study real-world sentences with audio playback using open tools and curated content.

## Features

- Extract sentences from Anki decks using the AnkiConnect API.
- Batch translate sentences into your target language using Google Sheets.
- Generate audio files for sentences using Google Cloud Text-to-Speech.
- Integrate with Google Sheets for lightweight study sessions.
- Automate file organization and audio links with Google Drive.

## Technologies

- Python 3.11+
- Google Cloud APIs (Sheets, Drive, Text-to-Speech)
- AnkiConnect (Local Web API)

## Setup Instructions

### Python Environment

- Install Python 3.11 or later.
- Set up a virtual environment:

    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
    ```

- Install dependencies

    ```bash
     pip install -r requirements.txt
     ```

### Google Cloud Service Account

- Create a Google Cloud project and enable the necessary APIs:
  - Google Sheets API
  - Google Drive API
  - Google Text-to-Speech API
- Create a service account and download the JSON key file.
- Share your Google Drive folder with the service account email.
- Store the JSON key file securely in your project directory (e.g., `.secrets/gcloud-key.json`).
- Add the following to a `.env` file:

 ```env
 GOOGLE_SERVICE_ACCOUNT_FILE=.secrets/gcloud-key.json
 ```

## Usage

### Extracting Sentences with `anki_sentence_extractor.py`

This script extracts English sentences from a specified Anki deck via the AnkiConnect API and writes them to a `.txt` file.

#### Example Usage of `anki_sentence_extractor.py`

```bash
python anki_sentence_extractor.py --deck "MyDeckName" --field "English" --output "sentences.txt"
```

### Translating Sentences with `translate_sheet_generator.py`

This script creates a new Google Sheet that translates English sentences into your target language using the `=GOOGLETRANSLATE()` formula.

#### Example Usage of `translate_sheet_generator.py`

```bash
python translate_sheet_generator.py \
  --source_sheet_id <SOURCE_SHEET_ID> \
  --source_tab_name Sheet1 \
  --dest_sheet_name Translations \
  --target_lang zh-CN \
  --dest_folder_id <DRIVE_FOLDER_ID>
```

### Generating Audio with `audio_generator.py`

This script generates audio files for translated sentences using Google Cloud Text-to-Speech, uploads them to Google Drive, and updates the source Google Sheet with hyperlinks.

#### Example Usage of `audio_generator.py`

```bash
python audio_generator.py \
  --sheet_id <SHEET_ID> \
  --source_tab_name Sentences \
  --dest_folder_id <DRIVE_FOLDER_ID> \
  --voice_name en-US-Wavenet-D \
  --text_column C \
  --audio_link_column D \
  --id_column A \
  --start_row 2 \
  --speaking_rate 1.0 \
  --audio_encoding MP3
```

## Notes

- Ensure your Google Cloud service account has access to the necessary APIs and shared Google Drive folders.
- The scripts are designed to work with specific column structures in Google Sheets. Refer to the script documentation for details.
- Use the `Verify Code` task in VS Code to check code formatting and linting.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
