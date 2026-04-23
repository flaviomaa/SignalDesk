import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import sqlite3
from urllib.parse import urljoin
import fitz  # PyMuPDF

# -------- Einstellungen --------
SOURCE = "BayLDA"
BASE_URL = "https://www.lda.bayern.de"
START_URL = "https://www.lda.bayern.de/de/pressemitteilungen.html"
OUTPUT_DIR = "output"
LOG_DIR = "log"
DB_PATH = "seen.db"
TODAY = datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"{SOURCE.lower()}_{TODAY}.json")
LOG_FILE = os.path.join(LOG_DIR, f"{SOURCE.lower()}_{TODAY}.log")
SAVE_JSON = os.getenv("SAVE_JSON", "true").lower() == "true"
WEBHOOK_URL = None  # optional eintragen

# -------- Setup --------
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

def extract_pdf_text(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        with open("temp_baylda.pdf", "wb") as f:
            f.write(resp.content)
        with fitz.open("temp_baylda.pdf") as doc:
            text = "\n".join(page.get_text() for page in doc)
        os.remove("temp_baylda.pdf")
        return text.strip()
    except Exception as e:
        msg = f"[FEHLER] PDF-Download/Extraktion fehlgeschlagen: {url} – {e}"
        print(msg)
        log_error(msg)
        return "[Fehler beim Extrahieren des PDF-Inhalts]"

def send_to_webhook(entry):
    if not WEBHOOK_URL:
        return
    try:
        response = requests.post(WEBHOOK_URL, json=entry, timeout=5)
        response.raise_for_status()
        print(f"[WEBHOOK] Gesendet: {entry['title']}")
    except Exception as e:
        msg = f"[FEHLER] Webhook-Sendung fehlgeschlagen für {entry['title']}: {e}"
        print(msg)
        log_error(msg)

def scrape_baylda(conn):
    results = []
    seen_links = set()

    try:
        resp = requests.get(START_URL, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Alle PDF-Links extrahieren
        items = soup.select("a[href$='.pdf']")
        print(f"[INFO] {len(items)} PDF-Links gefunden (ungefiltert).")

        for i, tag in enumerate(items, 1):
            href = tag.get("href")
            if not href or not href.endswith(".pdf"):
                continue

            pdf_link = urljoin(BASE_URL, href.strip())

            # Doppelte vermeiden
            if pdf_link in seen_links:
                continue
            seen_links.add(pdf_link)

            title = tag.get_text(strip=True)
            print(f"[DEBUG] Prüfe Link: {pdf_link}")

            if is_seen(conn, SOURCE, pdf_link):
                print(f"[ÜBERSPRUNGEN] Bereits bekannt: {title}")
                continue

            try:
                content = extract_pdf_text(pdf_link)

                entry = {
                    "source": SOURCE,
                    "title": title,
                    "link": pdf_link,
                    "date": datetime.now().date().isoformat(),
                    "content": content
                }

                results.append(entry)
                mark_as_seen(conn, SOURCE, pdf_link)
                send_to_webhook(entry)

            except Exception as e:
                msg = f"[WARNUNG] Fehler bei Eintrag {i}: {e}"
                print(msg)
                log_error(msg)
                continue

    except Exception as e:
        msg = f"[FEHLER] Fehler beim Abrufen der Startseite: {e}"
        print(msg)
        log_error(msg)

    return results

if __name__ == "__main__":
    print(f"[START] Starte {SOURCE}-Scraper...")
    conn = init_db()
    result = scrape_baylda(conn)
    print(f"[ERGEBNIS] {len(result)} neue Einträge verarbeitet.")

    if SAVE_JSON and result:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[GESPEICHERT] {OUTPUT_FILE}")
    else:
        print("[INFO] Keine neuen Einträge – JSON-Datei nicht gespeichert.")
