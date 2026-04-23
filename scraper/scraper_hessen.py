import sys
import os
import re
import json
import time
import sqlite3
from datetime import datetime

import feedparser
import requests
from bs4 import BeautifulSoup

try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

SOURCE = "EDPB"
RSS_URL = "https://www.edpb.europa.eu/feed/news_en"
TODAY = datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = f"output/edpb_{TODAY}.json"
DB_PATH = "seen.db"
SAVE_JSON = True
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

ERROR_LOG = "scraper_errors.log"


def log_error(message):
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} | {message}\n")
    except Exception:
        pass


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS seen_items (
            source TEXT NOT NULL,
            link TEXT NOT NULL,
            PRIMARY KEY (source, link)
        )
    """)
    conn.commit()
    return conn


def is_seen(conn, source, link):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen_items WHERE source = ? AND link = ?", (source, link))
    return cur.fetchone() is not None


def mark_as_seen(conn, source, link):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO seen_items (source, link) VALUES (?, ?)",
        (source, link)
    )
    conn.commit()


def extract_detail_content(url):
    for attempt in range(3):
        try:
            time.sleep(2 + attempt * 2)

            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            content_blocks = soup.select(
                ".field--name-body p, .news-content p, article p, main p"
            )
            if content_blocks:
                return "\n".join(p.get_text(strip=True) for p in content_blocks)

            alt = soup.find("article") or soup.find("main")
            return alt.get_text(strip=True, separator="\n") if alt else ""

        except requests.HTTPError as e:
            status = getattr(e.response, "status_code", None)

            if status == 429 and attempt < 2:
                wait_s = 5 + attempt * 5
                msg = f"[WARNUNG] 429 bei {url} - warte {wait_s}s und versuche erneut..."
                print(msg)
                log_error(msg)
                time.sleep(wait_s)
                continue

            msg = f"[FEHLER] Detailabruf fehlgeschlagen für {url}: {e}"
            print(msg)
            log_error(msg)
            return ""

        except Exception as e:
            msg = f"[FEHLER] Detailabruf fehlgeschlagen für {url}: {e}"
            print(msg)
            log_error(msg)
            return ""

    return ""


def clean_text(raw):
    return re.sub(r"\n{2,}", "\n", raw.strip()) if raw else ""


def send_to_webhook(entry):
    if not WEBHOOK_URL:
        return

    try:
        resp = requests.post(WEBHOOK_URL, json=entry, timeout=5)
        resp.raise_for_status()
        print(f"[WEBHOOK] Gesendet: {entry['title']}")
    except Exception as e:
        msg = f"[FEHLER] Webhook-Sendung fehlgeschlagen für {entry['title']}: {e}"
        print(msg)
        log_error(msg)


def fetch_and_parse_feed(conn):
    parsed = feedparser.parse(RSS_URL)
    print(f"[INFO] {len(parsed.entries)} Einträge im RSS-Feed gefunden.")

    results = []

    for i, entry in enumerate(parsed.entries, start=1):
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                continue

            if is_seen(conn, SOURCE, link):
                print(f"[ÜBERSPRUNGEN] Bereits bekannt: {title}")
                continue

            pub = entry.get("published", None)
            if pub:
                try:
                    date_str = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
                except ValueError:
                    if entry.get("published_parsed"):
                        date_str = datetime(*entry.published_parsed[:6]).date().isoformat()
                    else:
                        date_str = None
            elif entry.get("published_parsed"):
                date_str = datetime(*entry.published_parsed[:6]).date().isoformat()
            else:
                date_str = None

            content_raw = extract_detail_content(link)
            content_clean = clean_text(content_raw)

            result = {
                "source": SOURCE,
                "title": title,
                "link": link,
                "date": date_str,
                "content": content_clean,
            }

            results.append(result)
            mark_as_seen(conn, SOURCE, link)
            send_to_webhook(result)

        except Exception as e:
            msg = f"[WARNUNG] Fehler bei Eintrag {i}: {e}"
            print(msg)
            log_error(msg)
            continue

    return results


if __name__ == "__main__":
    print(f"[START] Starte {SOURCE}-Scraper...")
    conn = init_db()
    entries = fetch_and_parse_feed(conn)
    print(f"[ERGEBNIS] {len(entries)} neue Einträge verarbeitet.")

    if SAVE_JSON and entries:
        os.makedirs("output", exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"[GESPEICHERT] {OUTPUT_FILE}")
    else:
        print("[INFO] Keine neuen Einträge - JSON-Datei nicht gespeichert.")