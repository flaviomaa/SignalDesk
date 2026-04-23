import os
import re
import json
import sqlite3
import requests
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import parsedate_to_datetime
from playwright.sync_api import sync_playwright

# -------- Einstellungen --------
SOURCES = {
    "EURLEX-L": "https://eur-lex.europa.eu/DE/display-feed.rss?rssId=222",
    "EURLEX-C": "https://eur-lex.europa.eu/DE/display-feed.rss?rssId=221",
}
WEBHOOK_URL = None
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "log"
DB_PATH = BASE_DIR / "seen.db"
TODAY = datetime.now().strftime("%Y%m%d")
SAVE_JSON = True
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ComplianceBot/1.0)"}

# -------- Setup --------
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
    return conn.execute("SELECT 1 FROM seen_items WHERE source = ? AND link = ?", (source, link)).fetchone() is not None

def mark_as_seen(conn, source, link):
    conn.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
                 (source, link, datetime.now().isoformat()))
    conn.commit()

def log_error(source, message):
    log_path = os.path.join(LOG_DIR, f"{source.lower()}_{TODAY}.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message.strip() + "\n")

def extract_pdf_text(pdf_url):
    try:
        resp = requests.get(pdf_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(resp.content)
        with fitz.open("temp.pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
        os.remove("temp.pdf")
        return text.strip()
    except Exception as e:
        return f"[Fehler beim Laden des PDFs: {e}]"

def extract_content_playwright(url):
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=15000)
            page.wait_for_timeout(3000)

            # HTML-Volltext suchen
            content_elem = page.query_selector("div.oj-htmlSection, div.texte, article, main, section")
            if content_elem:
                content = content_elem.inner_text().strip()
                if content:
                    return {"type": "html", "text": content}

            # PDF-Link erkennen
            pdf_link = page.get_attribute("a[href$='.pdf']", "href")
            if pdf_link:
                if not pdf_link.startswith("http"):
                    base = re.match(r"^(https://[^/]+)", url).group(1)
                    pdf_link = base + pdf_link
                content = extract_pdf_text(pdf_link)
                return {"type": "pdf", "text": content}

            return {"type": "none", "text": "[Kein Inhalt extrahierbar]"}
        except Exception as e:
            return {"type": "error", "text": f"[Fehler beim Laden der Seite: {e}]"}
        finally:
            browser.close()

def send_to_webhook(entry):
    if not WEBHOOK_URL:
        return
    try:
        response = requests.post(WEBHOOK_URL, json=entry, timeout=5)
        response.raise_for_status()
        print(f"[WEBHOOK] Gesendet: {entry['title']}")
    except Exception as e:
        print(f"[FEHLER] Webhook-Sendung fehlgeschlagen für {entry['title']}: {e}")

def process_feed(source, url, conn):
    print(f"[INFO] Verarbeite {source}...")
    entries = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        import feedparser
        feed = feedparser.parse(resp.content)

        for item in feed.entries[:15]:  # begrenzt auf 15 Einträge
            title = item.get("title", "").strip()
            link = item.get("link", "").strip().replace("/./", "/")
            if not title or not link or is_seen(conn, source, link):
                continue

            pub_date = item.get("published", "")
            try:
                date_str = parsedate_to_datetime(pub_date).date().isoformat()
            except:
                date_str = datetime.now().date().isoformat()

            content_obj = extract_content_playwright(link)
            content_text = content_obj["text"]
            content_type = content_obj["type"]

            if not content_text or content_text.startswith("[Fehler"):
                log_error(source, f"[WARNUNG] Kein Inhalt für: {title}")
                continue

            entry = {
                "source": source,
                "title": title,
                "link": link,
                "date": date_str,
                "content": content_text,
                "content_type": content_type
            }

            entries.append(entry)
            mark_as_seen(conn, source, link)
            send_to_webhook(entry)

    except Exception as e:
        log_error(source, f"[FEHLER] Fehler beim Feed: {e}")
    return entries

if __name__ == "__main__":
    print("[START] Starte EUR-Lex-Scraper mit Playwright + PDF-Support...")
    conn = init_db()
    all_results = []

    for src, feed_url in SOURCES.items():
        result = process_feed(src, feed_url, conn)
        print(f"[{src}] {len(result)} neue Einträge verarbeitet.")
        all_results.extend(result)

        if SAVE_JSON and result:
            output_file = os.path.join(OUTPUT_DIR, f"{src.lower()}_{TODAY}.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"[GESPEICHERT] {output_file}")

    if not all_results:
        print("[INFO] Keine neuen Einträge – nichts gespeichert.")
