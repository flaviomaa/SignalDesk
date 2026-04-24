import os
import json
import glob
import hashlib
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from dotenv import load_dotenv
import requests

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

BASEROW_BASE_URL = os.getenv("BASEROW_BASE_URL", "https://api.baserow.io")
BASEROW_API_TOKEN = os.getenv("BASEROW_API_TOKEN")
BASEROW_TABLE_ID = os.getenv("BASEROW_TABLE_ID")

HEADERS = {
    "Authorization": f"Token {BASEROW_API_TOKEN}",
    "Content-Type": "application/json",
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "fbclid", "gclid", "mc_cid", "mc_eid"
}


def ensure_config():
    missing = []
    if not BASEROW_API_TOKEN:
        missing.append("BASEROW_API_TOKEN")
    if not BASEROW_TABLE_ID:
        missing.append("BASEROW_TABLE_ID")
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS]
        filtered.sort()
        query = urlencode(filtered)
        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:
        return url.strip().lower()


def normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.strip().lower().split())


def make_external_id(source: str, url: str, title: str, date: str) -> str:
    source_n = normalize_text(source)
    url_n = normalize_url(url)
    title_n = normalize_text(title)
    date_n = normalize_text(date)

    if source_n and url_n:
        raw = f"url::{source_n}::{url_n}"
    else:
        raw = f"title::{source_n}::{title_n}::{date_n}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def fetch_all_baserow_rows():
    rows = []
    page = 1
    while True:
        url = f"{BASEROW_BASE_URL.rstrip('/')}/api/database/rows/table/{BASEROW_TABLE_ID}/"
        params = {"user_field_names": "true", "size": 200, "page": page}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("results", [])
        rows.extend(batch)
        if not data.get("next"):
            break
        page += 1
    return rows


def existing_keys_from_baserow(rows):
    """
    Baut drei Mengen:
    - by_external_id: externe IDs (Hash)
    - by_source_url: (source, url) normalisiert
    - by_source_title_date: (source, title/dashboard_title, date) normalisiert
    """
    by_external_id = set()
    by_source_url = set()
    by_source_title_date = set()

    for row in rows:
        source = row.get("source") or row.get("Source") or ""
        url = row.get("url") or row.get("URL") or row.get("link") or row.get("Link") or ""
        title = row.get("dashboard_title") or row.get("title") or row.get("Title") or ""
        date = row.get("date") or row.get("Date") or ""
        external_id = row.get("external_id") or row.get("External ID") or ""

        source_n = normalize_text(source)
        url_n = normalize_url(url)
        title_n = normalize_text(title)
        date_n = normalize_text(date)

        if external_id:
            by_external_id.add(str(external_id).strip())

        if source_n and url_n:
            by_source_url.add((source_n, url_n))

        if source_n and title_n:
            by_source_title_date.add((source_n, title_n, date_n))

    return by_external_id, by_source_url, by_source_title_date


def map_entry_to_baserow(entry):
    source = entry.get("source", "")
    title = entry.get("title", "")
    url = entry.get("url") or entry.get("link") or ""
    date = entry.get("date", "")
    content = entry.get("content", "")

    external_id = make_external_id(source, url, title, date)

    return {
        "title": title,
        "source": source,
        "category": entry.get("category", ""),
        "language": entry.get("language", ""),
        "date": date,
        "link": url,
        "url": url,
        "content": content,
        "section": entry.get("section", ""),
        "external_id": external_id,
        "processing_status": "pending",
        "is_new": True,
        # Folgende Felder bewusst leer lassen — werden vom LLM/Backend angereichert:
        # "scraped_at", "import_file", "ai_summary", "ai_relevance_score",
        # "ai_priority", "ai_tags", "processed_at", "error_message"
    }


def load_local_entries():
    """
    Lädt alle JSON-Listen aus ./output/*.json (alle Scraper),
    und hängt sie zu einer großen Liste zusammen.
    """
    entries = []
    for path in glob.glob(str(OUTPUT_DIR / "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                entries.extend(data)
        except Exception as e:
            print(f"[WARN] Could not read {path}: {e}")
    return entries


def dedupe_entries(entries, existing_external_ids, existing_source_urls, existing_source_title_dates):
    """
    Nimmt alle lokalen Entries und filtert:
    - gegen Baserow (external_id, source+url, source+title+date)
    - gegen sich selbst (lokale Duplikate)
    """
    new_rows = []
    local_external_ids = set()
    local_source_urls = set()
    local_source_title_dates = set()

    skipped = {
        "existing_external_id": 0,
        "existing_source_url": 0,
        "existing_source_title_date": 0,
        "local_duplicate": 0,
    }

    for entry in entries:
        row = map_entry_to_baserow(entry)

        source_n = normalize_text(row.get("source", ""))
        url_n = normalize_url(row.get("url", ""))
        # für die Duplikat-Logik verwenden wir weiterhin "title", aber das Feld
        # wird nicht nach Baserow geschrieben (nur dashboard_title).
        title_n = normalize_text(entry.get("title", ""))
        date_n = normalize_text(row.get("date", ""))
        external_id = row["external_id"]

        source_url_key = (source_n, url_n) if source_n and url_n else None
        source_title_date_key = (source_n, title_n, date_n) if source_n and title_n else None

        if external_id in existing_external_ids:
            skipped["existing_external_id"] += 1
            continue

        if source_url_key and source_url_key in existing_source_urls:
            skipped["existing_source_url"] += 1
            continue

        if source_title_date_key and source_title_date_key in existing_source_title_dates:
            skipped["existing_source_title_date"] += 1
            continue

        if (
            external_id in local_external_ids or
            (source_url_key and source_url_key in local_source_urls) or
            (source_title_date_key and source_title_date_key in local_source_title_dates)
        ):
            skipped["local_duplicate"] += 1
            continue

        new_rows.append(row)
        local_external_ids.add(external_id)
        if source_url_key:
            local_source_urls.add(source_url_key)
        if source_title_date_key:
            local_source_title_dates.add(source_title_date_key)

    return new_rows, skipped


def create_rows(rows):
    if not rows:
        print("[INFO] No new rows to upload.")
        return

    url = f"{BASEROW_BASE_URL.rstrip('/')}/api/database/rows/table/{BASEROW_TABLE_ID}/batch/"
    payload = {"items": rows}

    resp = requests.post(
        url,
        headers=HEADERS,
        params={"user_field_names": "true"},
        json=payload,
        timeout=60,
    )

    if not resp.ok:
        print("[ERROR] Status:", resp.status_code)
        print("[ERROR] Response:", resp.text)

    resp.raise_for_status()
    print(f"[OK] Uploaded {len(rows)} new rows to Baserow.")


def main():
    ensure_config()

    print("[1/4] Loading local scraper output...")
    local_entries = load_local_entries()
    print(f"[INFO] Local entries found: {len(local_entries)}")

    print("[2/4] Loading existing Baserow rows...")
    existing_rows = fetch_all_baserow_rows()
    print(f"[INFO] Existing Baserow rows: {len(existing_rows)}")

    print("[3/4] Building duplicate indexes...")
    existing_external_ids, existing_source_urls, existing_source_title_dates = existing_keys_from_baserow(existing_rows)

    print("[4/4] Filtering new rows...")
    new_rows, skipped = dedupe_entries(
        local_entries,
        existing_external_ids,
        existing_source_urls,
        existing_source_title_dates,
    )

    print("[INFO] Skip stats:", skipped)
    print(f"[INFO] New rows to upload: {len(new_rows)}")

    # Zum Debuggen kannst du hier erst einmal nur die erste Row testen:
    # create_rows(new_rows[:1])
    create_rows(new_rows)


if __name__ == "__main__":
    main()