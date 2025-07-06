"""
anki_sentence_extractor.py

Extracts English sentences from a specified Anki deck using AnkiConnect.
Allows configuration of the deck name and the field containing English text.
Outputs file containing extracted sentences, one per line.
"""

import argparse
import json
import requests
from pathlib import Path

ANKI_CONNECT_URL = "http://localhost:8765"


def invoke(action, **params):
    payload = {"action": action, "version": 6, "params": params}
    response = requests.post(ANKI_CONNECT_URL, json=payload)
    response_json = response.json()

    # Debug: print full top-level JSON response structure
    #print("📦 AnkiConnect response:")
    #for key in response_json:
    #    print(f"  {key}: {type(response_json[key]).__name__}")

    if response_json.get("error") is not None:
        raise Exception(response_json["error"])
    return response_json["result"]


def extract_sentences(deck_name, field_name):
    print(f"🔍 Searching for notes in deck '{deck_name}'...")
    note_ids = invoke("findNotes", query=f'deck:"{deck_name}"')
    print(f"✅ Found {len(note_ids)} notes.")

    print("📋 Fetching note data...")
    notes = invoke("notesInfo", notes=note_ids)

    sentences = []
    for note in notes:
        fields = note.get("fields", {})
        if field_name in fields:
            sentence = fields[field_name].get("value", "").strip()
            if sentence:
                sentences.append(sentence)

    print(f"✅ Extracted {len(sentences)} sentences from field '{field_name}'.")
    return sentences


def write_sentences(sentences, output_path):
    print(f"💾 Writing to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for sentence in sentences:
            f.write(f"{sentence}\n")
    print("✅ Done.")


def debug_list_decks():
    decks = invoke("deckNames")
    print("🗂 Available decks:", decks)


def main():
    parser = argparse.ArgumentParser(description="Extract English sentences from Anki deck using AnkiConnect.")
    parser.add_argument("--deck", required=True, help="Name of the Anki deck")
    parser.add_argument("--field", required=True, help="Name of the field containing the English sentence")
    parser.add_argument("--output", default="sentences.txt", help="Output .txt file path")

    args = parser.parse_args()

    #debug_list_decks()
    sentences = extract_sentences(args.deck, args.field)
    write_sentences(sentences, Path(args.output))


if __name__ == "__main__":
    main()
