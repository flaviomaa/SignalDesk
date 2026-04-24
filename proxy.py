import os
import json
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

BASEROW_BASE_URL = os.getenv("BASEROW_BASE_URL", "https://api.baserow.io")
BASEROW_API_TOKEN = os.getenv("BASEROW_API_TOKEN")
BASEROW_TABLE_ID = os.getenv("BASEROW_TABLE_ID")

OUTPUT_FILE = Path(__file__).resolve().parent / "dashboard_ready.json"


def ensure_config():
    missing = []

    if not ENV_PATH.exists():
        missing.append(".env not found")
    if not BASEROW_API_TOKEN:
        missing.append("BASEROW_API_TOKEN")
    if not BASEROW_TABLE_ID:
        missing.append("BASEROW_TABLE_ID")

    if missing:
        raise RuntimeError(f"Fehlende Konfiguration: {', '.join(missing)}")


def extract_value(value):
    if isinstance(value, dict):
        return (
            value.get("value")
            or value.get("name")
            or value.get("label")
            or value.get("title")
            or value.get("id")
        )
    return value


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def split_tags(tags):
    if not tags:
        return []
    if isinstance(tags, list):
        return [str(t).strip() for t in tags if str(t).strip()]
    return [t.strip() for t in str(tags).split(",") if t.strip()]


def clean_row(row):
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "dashboard_title": row.get("dashboard_title") or row.get("title"),
        "source": row.get("source"),
        "category": row.get("category"),
        "language": row.get("language"),
        "date": row.get("date"),
        "url": row.get("url") or row.get("link"),
        "summary": row.get("ai_summary"),
        "relevance_score": to_int(row.get("ai_relevance_score")),
        "priority": extract_value(row.get("ai_priority")),
        "tags": split_tags(row.get("ai_tags")),
        "status": extract_value(row.get("processing_status")),
        "processed_at": row.get("processed_at"),
        "is_new": row.get("is_new"),
        "error_message": row.get("error_message"),
    }


def fetch_and_clean_all_rows():
    ensure_config()

    url = f"{BASEROW_BASE_URL.rstrip('/')}/api/database/rows/table/{BASEROW_TABLE_ID}/"
    headers = {
        "Authorization": f"Token {BASEROW_API_TOKEN}"
    }

    page = 1
    size = 200
    cleaned_rows = []

    while True:
        params = {
            "user_field_names": "true",
            "page": page,
            "size": size
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        for row in results:
            cleaned_rows.append(clean_row(row))

        print(f"Seite {page}: {len(results)} Rows geladen und bereinigt")

        if not data.get("next"):
            break

        page += 1

    return cleaned_rows


def main():
    try:
        rows = fetch_and_clean_all_rows()

        output = {
            "meta": {
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "table_id": BASEROW_TABLE_ID,
                "total_rows": len(rows)
            },
            "results": rows
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"Insgesamt bereinigt: {len(rows)} Rows")
        print(f"Datei gespeichert: {OUTPUT_FILE}")
        print("Dashboard-ready Export erfolgreich erstellt")

    except Exception as e:
        print("Fehler beim Export")
        print(str(e))


if __name__ == "__main__":
    main()