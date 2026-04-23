import os
import json
import time
import hashlib
from pathlib import Path

import requests


BASE_URL = "https://api.baserow.io"
API_TOKEN = os.getenv("BASEROW_API_TOKEN")
TABLE_ID = os.getenv("BASEROW_TABLE_ID")

NORMALIZED_DIR = Path(__file__).resolve().parent / "output" / "normalized"


def build_external_id(item: dict) -> str:
    raw = "|".join(
        [
            str(item.get("source", "")),
            str(item.get("title", "")),
            str(item.get("link", "")),
            str(item.get("date", "")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def map_item_to_baserow(item: dict, import_file: str) -> dict:
    return {
        "title": item.get("title", ""),
        "source": item.get("source", ""),
        "category": item.get("category", ""),
        "language": item.get("language", ""),
        "date": item.get("date", ""),
        "link": item.get("link", ""),
        "url": item.get("url", ""),
        "content": item.get("content", ""),
        "section": item.get("section", ""),
        "scraped_at": item.get("scraped_at", ""),
        "is_new": bool(item.get("is_new", True)),
        "import_file": import_file,
        "external_id": build_external_id(item),
    }


def upload_batch(rows: list[dict], debug: bool = False) -> dict:
    url = f"{BASE_URL}/api/database/rows/table/{TABLE_ID}/batch/?user_field_names=true"
    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"items": rows}

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if debug:
        print("\n[DEBUG] STATUS:", response.status_code)
        print("[DEBUG] RESPONSE:")
        print(response.text[:4000])

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Baserow API Fehler {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


def main():
    DEBUG = False
    TEST_MODE = False
    TEST_LIMIT = 3
    BATCH_SIZE = 25

    if not API_TOKEN:
        raise RuntimeError("BASEROW_API_TOKEN ist nicht gesetzt.")

    if not TABLE_ID:
        raise RuntimeError("BASEROW_TABLE_ID ist nicht gesetzt.")

    if not NORMALIZED_DIR.exists():
        raise RuntimeError(f"Ordner nicht gefunden: {NORMALIZED_DIR}")

    files = sorted(NORMALIZED_DIR.glob("normalized_*.json"))

    if not files:
        raise RuntimeError(f"Keine normalized_*.json in {NORMALIZED_DIR} gefunden.")

    print(f"[INFO] Verwende Ordner: {NORMALIZED_DIR}")
    print(f"[INFO] Table ID: {TABLE_ID}")
    print(f"[INFO] Dateien gefunden: {len(files)}")

    total_rows_sent = 0

    for file_path in files:
        print(f"\n[VERARBEITE] {file_path.name}")
        data = load_json_file(file_path)

        if not isinstance(data, list):
            print(f"[SKIP] {file_path.name} ist keine Liste")
            continue

        if TEST_MODE:
            data = data[:TEST_LIMIT]

        rows = [map_item_to_baserow(item, file_path.name) for item in data]

        if not rows:
            print(f"[SKIP] {file_path.name} enthält keine Rows")
            continue

        print(f"[INFO] Rows vorbereitet: {len(rows)}")

        if DEBUG:
            print("[DEBUG] Erste Row, die gesendet wird:")
            print(json.dumps(rows[0], ensure_ascii=False, indent=2)[:4000])

        uploaded_for_file = 0

        for batch_index, batch in enumerate(chunked(rows, BATCH_SIZE), start=1):
            print(f"[UPLOAD] Batch {batch_index} mit {len(batch)} Rows")

            result = upload_batch(batch, debug=DEBUG)

            if DEBUG:
                print("[DEBUG] Parsed JSON response:")
                print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])

            uploaded_for_file += len(batch)
            total_rows_sent += len(batch)

            time.sleep(0.3)

        print(f"[OK] {file_path.name}: {uploaded_for_file} Rows gesendet")

    print(f"\n[FERTIG] Insgesamt {total_rows_sent} Rows gesendet.")


if __name__ == "__main__":
    main()