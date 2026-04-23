import os
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="SignalDesk Dashboard")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

BASEROW_BASE_URL = os.getenv("BASEROW_BASE_URL")
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


def baserow_rows():
    ensure_config()

    headers = {"Authorization": f"Token {BASEROW_API_TOKEN}"}
    page = 1
    size = 200
    all_rows = []

    while True:
        url = f"{BASEROW_BASE_URL.rstrip('/')}/api/database/rows/table/{BASEROW_TABLE_ID}/"
        params = {
            "user_field_names": "true",
            "size": size,
            "page": page,
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
        all_rows.extend(results)

        if not data.get("next"):
            break

        page += 1

    return all_rows


def safe_get(row, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def stringify_value(value):
    if value is None:
        return None

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(
                    str(
                        item.get("value")
                        or item.get("name")
                        or item.get("label")
                        or item.get("id")
                        or ""
                    ).strip()
                )
            else:
                parts.append(str(item).strip())
        parts = [p for p in parts if p]
        return ", ".join(parts) if parts else None

    if isinstance(value, dict):
        for key in ("value", "name", "label", "title", "id"):
            if value.get(key) not in (None, ""):
                return str(value.get(key)).strip()
        return str(value)

    return str(value).strip()


def pick_text(row, *keys):
    return stringify_value(safe_get(row, *keys))


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_status_value(status):
    if isinstance(status, bool):
        return "processed" if status else "unknown"

    if status is None:
        return "unknown"

    s = str(status).strip().lower()

    if s in {"processed", "done", "completed", "complete", "analyzed", "analysed", "true"}:
        return "processed"

    if s in {"error", "failed", "failure"}:
        return "error"

    return "unknown"


@app.get("/api/overview")
def overview():
    rows = baserow_rows()
    today = datetime.now().date()

    sources = set()
    processed = 0
    new_today = 0

    for row in rows:
        source = pick_text(row, "Source", "source", "Quelle", "quelle")
        if source:
            sources.add(source)

        status = safe_get(row, "Status", "status", "Processed", "processed")
        if normalize_status_value(status) == "processed":
            processed += 1

        dt = parse_date(safe_get(row, "Date", "date", "Published At", "published_at"))
        if dt and dt.date() == today:
            new_today += 1

    return {
        "totalArticles": len(rows),
        "newToday": new_today,
        "processed": processed,
        "activeSources": len(sources),
    }


@app.get("/api/articles")
def articles():
    rows = baserow_rows()
    items = []

    for row in rows:
        items.append({
            "title": pick_text(row, "Title", "title", "Name", "name"),
            "source": pick_text(row, "Source", "source", "Quelle", "quelle"),
            "date": pick_text(row, "Date", "date", "Published At", "published_at"),
            "status": safe_get(row, "Status", "status", "Processed", "processed"),
            "url": pick_text(row, "URL", "url", "Link", "link"),

            "priority": pick_text(
                row,
                "Priority", "priority",
                "Prio", "prio",
                "Priorität", "prioritaet",
                "AI Priority", "ai_priority"
            ),
            "relevance": pick_text(
                row,
                "Relevance", "relevance",
                "Relevant", "relevant",
                "Relevanz", "relevanz",
                "AI Relevance", "ai_relevance"
            ),
            "summary": pick_text(
                row,
                "Summary", "summary",
                "Kurzfassung", "kurzfassung",
                "Zusammenfassung", "zusammenfassung",
                "Description", "description",
                "AI Summary", "ai_summary"
            ),
            "score": pick_text(
                row,
                "Score", "score",
                "Rating", "rating",
                "Risk Score", "risk_score",
                "AI Score", "ai_score"
            ),
            "category": pick_text(
                row,
                "Category", "category",
                "Topic", "topic",
                "Kategorie", "kategorie"
            ),
            "tags": pick_text(
                row,
                "Tags", "tags",
                "Keywords", "keywords",
                "Schlagwörter", "schlagwoerter",
                "AI Tags", "ai_tags"
            ),

            "debug_keys": sorted(list(row.keys()))
        })

    items.sort(key=lambda x: x["date"] or "", reverse=True)
    return {"results": items}


@app.get("/api/source-distribution")
def source_distribution():
    rows = baserow_rows()
    counter = Counter()

    for row in rows:
        source = pick_text(row, "Source", "source", "Quelle", "quelle")
        if source:
            counter[source] += 1

    items = counter.most_common()
    return {
        "labels": [x[0] for x in items],
        "values": [x[1] for x in items]
    }


@app.get("/api/activity")
def activity():
    rows = baserow_rows()
    grouped = defaultdict(int)

    for row in rows:
        dt = parse_date(safe_get(row, "Date", "date", "Published At", "published_at"))
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