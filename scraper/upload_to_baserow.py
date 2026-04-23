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


def get_headers():
    return {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json",
    }


def fetch_existing_rows(debug: bool = False) -> dict[str, int]:
    headers = get_headers()
    existing = {}
    next_url = f"{BASE_URL}/api/database/rows/table/{TABLE_ID}/?user_field_names=true&size=200"

    while next_url:
        response = requests.get(next_url, headers=headers, timeout=60)

        if response.status_code != 200:
            raise RuntimeError(
                f"Baserow Read API Fehler {response.status_code}: {response.text}"
            )

        payload = response.json()

        results = payload.get("results", [])
        if debug:
            print(f"[DEBUG] Gelesene Rows: {len(results)}")
            print(f"[DEBUG] Next URL: {payload.get('next')}")

        for row in results:
            row_id = row.get("id")
            ext_id = row.get("external_id")
            if row_id and ext_id:
                existing[str(ext_id)] = int(row_id)

        next_url = payload.get("next")

    return existing


def create_batch(rows: list[dict], debug: bool = False) -> dict:
    url = f"{BASE_URL}/api/database/rows/table/{TABLE_ID}/batch/?user_field_names=true"
    headers = get_headers()
    payload = {"items": rows}

    response = requests.post(url, headers=headers, json=payload, timeout=60)

    if debug:
        print("\n[DEBUG][CREATE] STATUS:", response.status_code)
        print("[DEBUG][CREATE] RESPONSE:")
        print(response.text[:4000])

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Baserow Create API Fehler {response.status_code}: {response.text}"
        )

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


def update_batch(rows: list[dict], debug: bool = False) -> dict:
    url = f"{BASE_URL}/api/database/rows/table/{TABLE_ID}/batch/?user_field_names=true"
    headers = get_headers()
    payload = {"items": rows}

    response = requests.patch(url, headers=headers, json=payload, timeout=60)

    if debug:
        print("\n[DEBUG][UPDATE] STATUS:", response.status_code)
        print("[DEBUG][UPDATE] RESPONSE:")
        print(response.text[:4000])

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"Baserow Update API Fehler {response.status_code}: {response.text}"
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

    print("[INFO] Lade bestehende Rows aus Baserow ...")
    existing_rows = fetch_existing_rows(debug=DEBUG)
    print(f"[INFO] Bereits vorhandene external_id: {len(existing_rows)}")

    total_processed = 0
    total_created = 0
    total_updated = 0

    for file_path in files:
        print(f"\n[VERARBEITE] {file_path.name}")
        data = load_json_file(file_path)

        if not isinstance(data, list):
            print(f"[SKIP] {file_path.name} ist keine Liste")
            continue

        if TEST_MODE:
            data = data[:TEST_LIMIT]

        rows_to_create = []
        rows_to_update = []

        for item in data:
            row = map_item_to_baserow(item, file_path.name)
            ext_id = row["external_id"]
            total_processed += 1

            if ext_id in existing_rows:
                row["id"] = existing_rows[ext_id]
                rows_to_update.append(row)
            else:
                rows_to_create.append(row)

        print(
            f"[INFO] Datei {file_path.name}: "
            f"{len(rows_to_create)} neu, {len(rows_to_update)} update"
        )

        if DEBUG and rows_to_create:
            print("[DEBUG] Erste Create-Row:")
            print(json.dumps(rows_to_create[0], ensure_ascii=False, indent=2)[:4000])

        if DEBUG and rows_to_update:
            print("[DEBUG] Erste Update-Row:")
            print(json.dumps(rows_to_update[0], ensure_ascii=False, indent=2)[:4000])

        for batch_index, batch in enumerate(chunked(rows_to_create, BATCH_SIZE), start=1):
            print(f"[CREATE] Batch {batch_index} mit {len(batch)} Rows")
            result = create_batch(batch, debug=DEBUG)

            try:
                for created in result.get("items", []):
                    created_id = created.get("id")
                    created_ext = created.get("external_id")
                    if created_id and created_ext:
                        existing_rows[str(created_ext)] = int(created_id)
            except Exception:
                pass

            total_created += len(batch)
            time.sleep(0.3)

        for batch_index, batch in enumerate(chunked(rows_to_update, BATCH_SIZE), start=1):
            print(f"[UPDATE] Batch {batch_index} mit {len(batch)} Rows")
            update_batch(batch, debug=DEBUG)
            total_updated += len(batch)
            time.sleep(0.3)

        print(
            f"[OK] {file_path.name}: "
            f"{len(rows_to_create)} erstellt, {len(rows_to_update)} aktualisiert"
        )

    print("\n[FERTIG]")
    print(f"[INFO] Insgesamt verarbeitet: {total_processed}")
    print(f"[INFO] Neu erstellt: {total_created}")
    print(f"[INFO] Aktualisiert: {total_updated}")


if __name__ == "__main__":
    main()