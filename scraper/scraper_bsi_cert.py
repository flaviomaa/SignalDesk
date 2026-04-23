import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
import os
import sqlite3

SOURCE = "BSI-CERT"
RSS_URL = "https://wid.cert-bund.de/content/public/securityAdvisory/rss"
WEBHOOK_URL = None
OUTPUT_DIR = "output"
LOG_DIR = "log"
DB_PATH = "seen.db"
TODAY = datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"{SOURCE.lower().replace('-', '_')}_{TODAY}.json")
LOG_FILE = os.path.join(LOG_DIR, f"{SOURCE.lower().replace('-', '_')}_{TODAY}.log")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            link TEXT UNIQUE,
            seen_at TEXT
        )
    """)
    conn.commit()
    return conn

def is_seen(conn, source, link):
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_items WHERE source = ? AND link = ?", (source, link))
    return c.fetchone() is not None

def mark_as_seen(conn, source, link):
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
              (source, link, datetime.now().isoformat()))
    conn.commit()

def log_error(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message.strip() + "\n")

def extract_detail_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ComplianceBot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        content_blocks = soup.select("div.propertyBlock, div.col-md-12, div.accordion, div.panel-body, main")
        texts = [block.get_text(separator="\n", strip=True) for block in content_blocks if block]
        return "\n\n".join(texts).strip() if texts else "[Kein Inhalt gefunden]"
    except Exception as e:
        msg = f"[FEHLER] Detailabruf fehlgeschlagen für {url}: {e}"
        print(msg)
        log_error(msg)
        return "[Kein Inhalt gefunden]"

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
                date_str = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").date().isoformat()
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
                "content": content_clean
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
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"[GESPEICHERT] {OUTPUT_FILE}")
