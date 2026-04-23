import json
from pathlib import Path

from schema import normalize_batch

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "scraper" / "output"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_file(path: Path) -> None:
    try:
        data = load_json_file(path)
    except Exception as e:
        print(f"[SKIP] Fehler beim Lesen von {path.name}: {e}")
        return

    if not isinstance(data, list):
        print(f"[SKIP] {path.name} ist keine JSON-Liste")
        return

    normalized = normalize_batch(data)

    out_path = NORMALIZED_DIR / f"normalized_{path.name}"
    save_json_file(normalized, out_path)

    print(f"[OK] {path.name}: {len(normalized)} Einträge -> {out_path}")


def main():
    if not OUTPUT_DIR.exists():
        print(f"[FEHLER] output-Ordner nicht gefunden: {OUTPUT_DIR}")
        return

    files = sorted(
        p for p in OUTPUT_DIR.glob("*.json")
        if p.is_file() and not p.name.startswith("normalized_")
    )

    if not files:
        print("[FEHLER] Keine JSON-Dateien in output gefunden.")
        return

    for path in files:
        normalize_file(path)

    extra = ROOT / "aiact_all_articles.json"
    if extra.exists():
        normalize_file(extra)

    print("[OK] Normalisierung abgeschlossen.")


if __name__ == "__main__":
    main()