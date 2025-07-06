# 🈸 Language Sentence Toolkit for 10,000 Sentences study method

**DIY language learning tools for building a personalized sentence-based study system.**

This project contains Python scripts that power a custom implementation of the 10,000 Sentences Method for language acquisition. It enables you to extract, translate, and study real-world sentences with audio playback — all using open tools and your own curated content.

## ✨ Features

- 📥 **Sentence Extraction** from Anki decks using the AnkiConnect API
- 🌐 **Batch Translation** of English sentences into your target language (e.g. Mandarin) using OpenAI or Google Translate
- 🔊 **Text-to-Speech Audio Generation** via Google Cloud or ElevenLabs
- 📄 **Google Sheets Integration** for lightweight study sessions
- 📁 **Google Drive Automation** for organizing sentence files and audio links
- 🧩 Support for both a large “primary” sentence deck and smaller topic-focused “language islands”

## 🔍 What this is for

I am a hobbyist language learner who needs:

- A personalized sentence bank built from Anki decks or hand-written material
- High-quality target-language translations and audio
- A daily study system that works seamlessly on desktop or mobile
- A simple pipeline to get my sentences where I need them, and get them translated and produce audio files with a minimum of work.

## 🛠 Technologies

- **Python 3.11+**
- **Google Cloud APIs** (Sheets, Drive, TTS)
- **AnkiConnect (Local Web API)** - This is the desktop version of Anki running the AnkiConnect plugin
- **OpenAI GPT API** - You will need your own OpenAI key
- **Google Translate or other translation tools**
- Optional/maybe: **Google Colab** for running translation/audio batches in the cloud

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

## 📦 Usage

### 🔹 Extracting Sentences with `anki_sentence_extractor.py`

This script extracts English sentences from a specified Anki deck via the AnkiConnect API, and writes them to a tab-delimited `.txt` file with numeric IDs.

#### Prerequisites

- Anki desktop is running
- [AnkiConnect](https://github.com/FooSoft/anki-connect) plugin is installed and enabled
- Your deck contains the English sentences in a specific field

#### Basic Usage

```bash
python anki_sentence_extractor.py --deck "MyDeckName" --field "English" --output "sentences.txt" --start-id 1
```

You can also omit the `--output` and `--start-id` arguments (default=1).

```bash
python anki_sentence_extractor.py --deck "MyDeckName" --field "English"
```

#### Troubleshooting

If you get a result "✅ Found 0 notes.", try renaming your deck without spaces.
