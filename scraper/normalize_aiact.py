import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPER_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT))
from schema import normalize_batch

INPUT_FILE = SCRAPER_DIR / "aiact_all_articles.json"
OUTPUT_DIR = SCRAPER_DIR / "output" / "normalized"
OUTPUT_FILE = OUTPUT_DIR / "normalized_aiact_all_articles.json"


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("[VERARBEITE] aiact_all_articles.json...")

    if not INPUT_FILE.exists():
        print(f"[FEHLER] Datei nicht gefunden: {INPUT_FILE}")
        return

    try:
        data = load_json_file(INPUT_FILE)
    except Exception as e:
        print(f"[FEHLER] Fehler beim Lesen: {e}")
        return

    if not isinstance(data, list):
        print("[FEHLER] aiact_all_articles.json ist keine JSON-Liste.")
        return

    normalized = normalize_batch(data)
    save_json_file(normalized, OUTPUT_FILE)

    print(f"[OK] {len(normalized)} Einträge normalisiert -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()