import os
import json
import sqlite3
import requests
import time
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from datetime import datetime
import sys

import sys

try:
    # Verhindert UnicodeEncodeError: nicht darstellbare Zeichen werden ersetzt
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

SOURCE = "LfD Berlin"
OUTPUT_DIR = "output"
SEEN_DB = "seen.db"
DATE_STR = datetime.now().strftime("%Y%m%d")
os.makedirs(OUTPUT_DIR, exist_ok=True)

conn = sqlite3.connect(SEEN_DB)
cur = conn.cursor()
cur.execute("""
    CREATE TABLE IF NOT EXISTS seen_items (
        source TEXT,
        link TEXT PRIMARY KEY,
        seen_at TEXT
    )
""")
conn.commit()

HEADERS = {"User-Agent": "Mozilla/5.0"}

def is_seen(link):
    cur.execute("SELECT 1 FROM seen_items WHERE link = ?", (link,))
    return cur.fetchone() is not None

def mark_seen(link):
    cur.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
                (SOURCE, link, datetime.now().isoformat()))
    conn.commit()

def extract_pdf_text(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(res.content)
        with fitz.open("temp.pdf") as doc:
            text = "\n\n".join(page.get_text().strip() for page in doc)
        os.remove("temp.pdf")
        return text.strip()
    except Exception as e:
        print(f"[WARN] PDF konnte nicht gelesen werden: {url} | {e}")
        return ""

def scrape_berlin():
    print("[INFO] Scrape: Pressemitteilungen LfD Berlin")
    url = "https://www.datenschutz-berlin.de/infothek/pressemitteilungen/"
    results = []

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"[ERROR] Hauptseite nicht erreichbar: {e}")
        return results

    entries = soup.select("li.causes-single-wrapper")
    print(f"[DEBUG] Gefundene Einträge: {len(entries)}")

    for entry in entries:
        link_tag = entry.find("a", href=True)
        title_tag = entry.find("h2")

        if not link_tag or not title_tag:
            continue

        link = link_tag["href"]
        if not link.startswith("http"):
            link = "https://www.datenschutz-berlin.de" + link

        title = title_tag.get_text(strip=True)

        if is_seen(link):
            continue

        print(f"[INFO] Verarbeite: {title}")
        content = ""
        date_str = ""

        if ".pdf" in link:
            content = extract_pdf_text(link)
            date_str = datetime.now().strftime("%Y-%m-%d")  # fallback
        else:
            try:
                r = requests.get(link, headers=HEADERS, timeout=10)
                r.raise_for_status()
                detail = BeautifulSoup(r.text, "html.parser")
                paragraphs = detail.select("main p, .ce-bodytext p, .text p, article p")
                content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

                # 📅 Datum extrahieren aus <time datetime="">
                time_tag = detail.find("time", {"datetime": True})
                if time_tag:
                    date_str = time_tag["datetime"]
                else:
                    date_str = datetime.now().strftime("%Y-%m-%d")  # fallback
            except Exception as e:
                print(f"[WARN] Detailseite nicht lesbar: {link} | {e}")
                content = f"[Kein Inhalt verfügbar für {title}]"
                date_str = datetime.now().strftime("%Y-%m-%d")

        results.append({
            "source": SOURCE,
            "section": "pressemitteilungen",
            "title": title,
            "link": link,
            "date": date_str,
            "content": content
        })

        mark_seen(link)
        time.sleep(0.2)

    return results

def main():
    print("[START] Starte Scraper für LfD Berlin...")
    entries = scrape_berlin()

    if entries:
        out_path = os.path.join(OUTPUT_DIR, f"berlin_{DATE_STR}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"[✅] {len(entries)} Einträge gespeichert in {out_path}")
    else:
        print("[ℹ️] Keine neuen Einträge gefunden.")

    conn.close()

if __name__ == "__main__":
    main()
