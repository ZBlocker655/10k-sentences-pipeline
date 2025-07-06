# 🈸 Language Sentence Toolkit for 10,000 Sentences study method

**DIY language learning tools for building a personalized sentence-based study system.**

This project contains Python scripts that power a custom implementation of the [10,000 Sentences Method](https://langible.com/articles/10000-sentence-method) for language acquisition. It enables you to extract, translate, and study real-world sentences with audio playback — all using open tools and your own curated content.

## ✨ Features

- 📥 **Sentence Extraction** from Anki decks using the AnkiConnect API
- 🌐 **Batch Translation** of English sentences into your target language (e.g. Mandarin) using Google Translate (as embedded Google Sheets formula - no API charges)
- 🔊 **Text-to-Speech Audio Generation** via (TBD)
- 📄 **Google Sheets Integration** for lightweight study sessions
- 📁 **Google Drive Automation** for organizing sentence files and audio links
- 🧩 Support for both a large “primary” sentence deck and smaller topic-focused “language islands”

## 🔍 What this is for

A language learner who needs:

- A personalized sentence bank built from Anki decks or hand-written material
- High-quality target-language translations and audio
- A daily study system that works seamlessly on desktop or mobile
- A simple pipeline to get my sentences where I need them, and get them translated and produce audio files with a minimum of work.

## 🛠 Technologies

- **Python 3.11+**
- **Google Cloud APIs** (Sheets, Drive, TTS)
- **AnkiConnect (Local Web API)** - This is the desktop version of Anki running the AnkiConnect plugin

## 🛠 Developer Setup Instructions

This section guides you through setting up your local Python development environment for this project.

### 1. Prerequisites

- Python 3.12.6 or later installed and added to your system PATH
- Git (optional, for cloning this repo)
- VS Code (recommended) or any code editor of your choice

### 2. Create and Activate Virtual Environment

From the project root directory, run:

- On Windows (PowerShell):

  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1

### 🔐 Setting Up Google Cloud Service Account (for Beginners)

To authenticate your script with Google Sheets API, you'll need a **service account JSON key file**. Here's how to get one securely and store it properly:

---

### 1. Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the project dropdown (top-left), then click **"New Project"**.
3. Give it a name like `LanguageToolsProject`, then click **"Create"**.

### 2. Enable the Google Sheets API

1. With your project selected, go to the left menu:
   - **APIs & Services > Library**
2. Search for **Google Sheets API**.
3. Click it and then click **"Enable"**.
4. Do the same for **Google Drive API**.

### 3. Create a Service Account

1. Go to **APIs & Services > Credentials**.
2. Click **"Create Credentials"** > **"Service account"**.
3. Name it something like `automation-scripts`, then click **"Done"** (you can skip assigning roles).

### 4. Download the JSON Key File

1. In the list of service accounts, find yours and click the **three dots > Manage keys**.
2. Click **"Add key" > "Create new key"**.
3. Select **JSON** and click **"Create"**.
4. Your browser will download a `.json` file — this is your **private key**.

### 5. Grant Access to Your Google Drive Folders

To allow your service account to read from and write to your spreadsheets without needing to manually share each one, you can grant folder-level access. This is the recommended setup to streamline your workflow.

- Open Google Drive
- Identify your root project folder
- Choose the top-level folder in Google Drive that contains (or will contain) your sentence lists, translated sheets, audio files, or other pipeline artifacts.
- Right-click the folder → select Share
- In the “Add people and groups” field:
  - Paste your service account email address (looks like: your-bot@your-project.iam.gserviceaccount.com)
  - Set the access level to Editor
  - Click Send

---

### 📁 Where to Store the JSON Key

Place it in a local `.secrets/` folder in your project directory:

## 📦 Usage

### 🔹 Extracting Sentences with `anki_sentence_extractor.py`

This script extracts English sentences from a specified Anki deck via the AnkiConnect API, and writes them to a `.txt` file with one sentence per line.

#### Prerequisites

- Anki desktop is running
- [AnkiConnect](https://github.com/FooSoft/anki-connect) plugin is installed and enabled
- Your deck contains the English sentences in a specific field

#### Basic Usage

```bash
python anki_sentence_extractor.py --deck "MyDeckName" --field "English" --output "sentences.txt"
```

You can also omit the `--output` argument (default is `sentences.txt`).

#### Troubleshooting

If you get a result "✅ Found 0 notes.", try renaming your deck without spaces.

### 🔹 Translating English sentences into your target language with `translate_sheet_generator.py`

This tool creates a new Google Sheet that:

- Copies English sentences from a source Google Sheet
- Adds an auto-generated ID for each sentence
- Applies the `=GOOGLETRANSLATE()` formula to produce translations in the target language
- Waits for translations to complete
- Copies the translations to a permanent column and removes the formulas
- (Optionally) places the resulting spreadsheet in a specific Google Drive folder

#### ✅ Setup Instructions

1. **Enable Google APIs** in your Google Cloud project:
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)

2. **Create a Service Account**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project (or reuse one)
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > Service Account**
   - Download the JSON key and save it to your project in a `.secrets/` folder (e.g. `.secrets/gcloud-key.json`)

3. **Share the source sheet** with your service account:
   - Find your service account email (e.g. `my-bot@my-project.iam.gserviceaccount.com`)
   - Open the source Google Sheet in your browser
   - Click **Share** and add the email with **Editor** permissions

4. **Create a `.env` file** in your project root:

```env
GOOGLE_SERVICE_ACCOUNT_FILE=.secrets/gcloud-key.json
```

> ✅ You can copy from `.env.example`

---

#### 📦 Sample Usage

```bash
python translate_sheet_generator.py \
  --source_sheet_id 1A2B3C4D... \
  --source_tab_name Sheet1 \
  --dest_sheet_name _Primary_Mandarin \
  --target_lang zh-CN \
  --dest_folder_id 1XyZabc1234567890
```

#### Required Parameters

- `--source_sheet_id` — ID of the English-only source Google Sheet
- `--dest_sheet_name` — Name for the new translated spreadsheet
- `--target_lang` — Language code for translation (e.g. `zh-CN`, `fr`, `es`)

#### Optional Parameters

- `--source_tab_name` — Tab name inside the source sheet (defaults to `Sheet1`)
- `--target_font` — Font to apply to the translated column (optional, coming soon)
- `--dest_folder_id` — Folder ID in Google Drive to place the new sheet

---

Need help getting your folder ID? Just open the target folder in Google Drive and copy the ID from the URL:
```
https://drive.google.com/drive/folders/<FOLDER_ID>
```
