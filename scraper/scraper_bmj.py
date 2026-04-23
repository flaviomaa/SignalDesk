import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as date_parser
import json
import re
import os
import sqlite3

# -------- Einstellungen --------
SOURCE = "BMJ"
WEBHOOK_URL = None
OUTPUT_DIR = "output"
LOG_DIR = "log"
DB_PATH = "seen.db"
TODAY = datetime.now().strftime("%Y%m%d")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, f"{SOURCE.lower()}_{TODAY}.json")
LOG_FILE = os.path.join(LOG_DIR, f"{SOURCE.lower()}_{TODAY}.log")
SAVE_JSON = os.getenv("SAVE_JSON", "true").lower() == "true"

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
    c.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)", (source, link, datetime.now().isoformat()))
    conn.commit()

def log_error(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message.strip() + "\n")

def fetch_bmj_rss():
    url = "https://www.bmj.de/SiteGlobals/Functions/RSSNewsfeed/DE/RSSNewsfeed/RSSNewsfeedGesetzgebungsverfahren.xml?nn=149890"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ComplianceBot/1.0)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        msg = f"[FEHLER] Abruf des RSS-Feeds fehlgeschlagen: {e}"
        print(msg)
        log_error(msg)
        return None

def parse_rss_feed(xml_data):
    try:
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        print(f"[INFO] {len(items)} <item>-Einträge im RSS-Feed gefunden.")
        return items
    except Exception as e:
        msg = f"[FEHLER] Fehler beim Parsen des RSS-Feeds: {e}"
        print(msg)
        log_error(msg)
        return []

def extract_detail_content(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ComplianceBot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        main = soup.select_one("div.text, div.bmj-article-content, main")
        return main.get_text(strip=True, separator="\n") if main else ""
    except Exception as e:
        msg = f"[FEHLER] Detailabruf fehlgeschlagen für {url}: {e}"
        print(msg)
        log_error(msg)
        return ""

def clean_text(raw):
    if not raw:
        return ""
    text = raw
    text = re.sub(r"^Navigationspfad.*?Gesetzgebungsverfahren\nGesetz\n", "", text, flags=re.DOTALL)
    text = re.sub(r"(Details verbergen|Zeige Dokumente an|Weitere Details.*?\n|Synopse.*?)\n", "", text, flags=re.DOTALL)
    text = re.sub(r"(RefE\n:.*?\n)+", "", text)
    text = re.sub(r"PDF,\n.*?barrierefrei⁄barrierearm,\n", "", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

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

def parse_items(items, conn):
    result = []
    for i, item in enumerate(items, start=1):
        try:
            title = item.find("title").text.strip()
            link = item.find("link").text.strip()
            if is_seen(conn, SOURCE, link):
                print(f"[ÜBERSPRUNGEN] Bereits bekannt: {title}")
                continue

            pub_date_raw = item.find("pubDate").text.strip() if item.find("pubDate") is not None else None
            pub_date = date_parser.parse(pub_date_raw).date().isoformat() if pub_date_raw else None

            content_raw = extract_detail_content(link)
            content_clean = clean_text(content_raw)

            entry = {
                "source": SOURCE,
                "title": title,
                "link": link,
                "date": pub_date,
                "content": content_clean
            }

            result.append(entry)
            mark_as_seen(conn, SOURCE, link)
            send_to_webhook(entry)

        except Exception as e:
            msg = f"[WARNUNG] Fehler bei Eintrag {i}: {e}"
            print(msg)
            log_error(msg)
            continue
    return result

if __name__ == "__main__":
    print(f"[START] Starte {SOURCE}-Scraper...")
    conn = init_db()
    xml_data = fetch_bmj_rss()
    if xml_data:
        items = parse_rss_feed(xml_data)
        result = parse_items(items, conn)
        print(f"[ERGEBNIS] {len(result)} neue Einträge verarbeitet.")

        if SAVE_JSON and result:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"[GESPEICHERT] {OUTPUT_FILE}")
        else:
            print("[INFO] Keine neuen Einträge – JSON-Datei nicht gespeichert.")
    else:
        print("[ABBRUCH] Keine Daten geladen.")
