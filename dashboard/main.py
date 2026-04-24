import os
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ENV_PATH = BASE_DIR.parent / ".env"

load_dotenv(dotenv_path=ENV_PATH, override=True)

app = FastAPI(title="SignalDesk Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

BASEROW_BASE_URL = os.getenv("BASEROW_BASE_URL", "https://api.baserow.io")
BASEROW_API_TOKEN = os.getenv("BASEROW_API_TOKEN")
BASEROW_TABLE_ID = os.getenv("BASEROW_TABLE_ID")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


def ensure_config():
    missing = []

    if not BASEROW_BASE_URL:
        missing.append("BASEROW_BASE_URL")
    if not BASEROW_API_TOKEN:
        missing.append("BASEROW_API_TOKEN")
    if not BASEROW_TABLE_ID:
        missing.append("BASEROW_TABLE_ID")

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing environment variables: {', '.join(missing)}"
        )


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


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


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

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Baserow request failed: {exc}"
            ) from exc

        data = response.json()
        results = data.get("results", [])

        for row in results:
            cleaned_rows.append(clean_row(row))

        if not data.get("next"):
            break

        page += 1

    cleaned_rows.sort(key=lambda x: x["date"] or "", reverse=True)
    return cleaned_rows


@app.get("/api/articles")
def articles():
    rows = fetch_and_clean_all_rows()
    return {
        "meta": {
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "table_id": BASEROW_TABLE_ID,
            "total_rows": len(rows)
        },
        "results": rows
    }


@app.get("/api/overview")
def overview():
    rows = fetch_and_clean_all_rows()
    today = datetime.now().date()

    sources = {row["source"] for row in rows if row.get("source")}
    processed = sum(1 for row in rows if row.get("status") == "done")

    new_today = 0
    for row in rows:
        dt = parse_date(row.get("date"))
        if dt and dt.date() == today:
            new_today += 1

    return {
        "totalArticles": len(rows),
        "newToday": new_today,
        "processed": processed,
        "activeSources": len(sources),
    }


@app.get("/api/source-distribution")
def source_distribution():
    rows = fetch_and_clean_all_rows()
    counter = Counter()

    for row in rows:
        source = row.get("source")
        if source:
            counter[source] += 1

    items = counter.most_common()
    return {
        "labels": [x[0] for x in items],
        "values": [x[1] for x in items]
    }


@app.get("/api/activity")
def activity():
    rows = fetch_and_clean_all_rows()
    grouped = defaultdict(int)

    for row in rows:
        dt = parse_date(row.get("date"))
        if dt:
            grouped[dt.date().isoformat()] += 1

    items = sorted(grouped.items(), key=lambda x: x[0])
    return {
        "labels": [x[0] for x in items],
        "values": [x[1] for x in items]
    }


@app.get("/api/pipeline")
def pipeline():
    return {
        "steps": [
            {"name": "Scrapers", "description": "Collect articles from sources"},
            {"name": "n8n", "description": "Orchestrates the workflow"},
            {"name": "Filter", "description": "Skips already processed rows"},
            {"name": "AI Analysis", "description": "Processes and enriches content"},
            {"name": "Storage", "description": "Writes data back to Baserow"},
            {"name": "Dashboard", "description": "Visualizes signals and trends"},
        ]
    }