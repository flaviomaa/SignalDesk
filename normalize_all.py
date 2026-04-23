import os
import json
import sys

from schema import normalize_batch, save_normalized_json

OUTPUT_DIR = "output"
NORMALIZED_DIR = "output/normalized"


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not os.path.isdir(OUTPUT_DIR):
        print(f"[FEHLER] Ordner '{OUTPUT_DIR}' nicht gefunden.")
        sys.exit(1)

    os.makedirs(NORMALIZED_DIR, exist_ok=True)

    for filename in sorted(os.listdir(OUTPUT_DIR)):
        if filename.endswith(".json") and not filename.startswith("normalized_"):
            input_path = os.path.join(OUTPUT_DIR, filename)
            output_filename = f"normalized_{filename}"
            output_path = os.path.join(NORMALIZED_DIR, output_filename)

            print(f"\n[VERARBEITE] {filename}...")
            raw_data = load_json_file(input_path)

            if isinstance(raw_data, list):
                normalized = normalize_batch(raw_data)
                save_normalized_json(normalized, output_path)
                print(f"  {len(normalized)} Eintraege normalisiert.")
            else:
                print(f"  [SKIP] {filename} ist keine Liste.")

    if os.path.exists("aiact_all_articles.json"):
        print(f"\n[VERARBEITE] aiact_all_articles.json...")
        raw_data = load_json_file("aiact_all_articles.json")
        if isinstance(raw_data, list):
            normalized = normalize_batch(raw_data)
            save_normalized_json(
                normalized,
                os.path.join(NORMALIZED_DIR, "normalized_aiact_all_articles.json")
            )
            print(f"  {len(normalized)} Eintraege normalisiert.")

    print("\n[OK] Alle Dateien normalisiert.")


if __name__ == "__main__":
    main()