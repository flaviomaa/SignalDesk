import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import json
import sqlite3
import time
import os

SOURCE = "ENISA-Publications"
BASE_URL = "https://www.enisa.europa.eu/publications?page="
OUTPUT_DIR = "output"
SEEN_DB = "seen.db"
MAX_PAGES = 3

def get_seen_links():
    conn = sqlite3.connect(SEEN_DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS seen_items (source TEXT, link TEXT, seen_at TEXT)")
    conn.commit()
    c.execute("SELECT link FROM seen_items WHERE source=?", (SOURCE,))
    rows = c.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def add_seen_link(link):
    conn = sqlite3.connect(SEEN_DB)
    c = conn.cursor()
    c.execute("INSERT INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
              (SOURCE, link, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def scrape_enisa_publications():
    print("[START] Starte ENISA-Publications-Scraper...")
    seen_links = get_seen_links()
    new_entries = []

    for page in range(MAX_PAGES):
        url = BASE_URL + str(page)
        print(f"[INFO] Rufe Seite auf: {url}")
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")

        entries = soup.select(".publications-item")
        for entry in entries:
            link_tag = entry.select_one(".publication-image a")
            if not link_tag or not link_tag.has_attr("href"):
                continue
            link = "https://www.enisa.europa.eu" + link_tag["href"]

            if link in seen_links:
                continue

            title_tag = entry.select_one(".publication-content h3 a")
            title = title_tag.text.strip() if title_tag else "No Title"

            date_tag = entry.select_one("time")
            date = date_tag["datetime"] if date_tag and "datetime" in date_tag.attrs else "No Date"

            content_tag = entry.select_one(".publication-content .content")
            content = content_tag.text.strip() if content_tag else ""

            entry_data = {
                "source": SOURCE,
                "title": title,
                "link": link,
                "date": date,
                "content": content
            }

            new_entries.append(entry_data)
            add_seen_link(link)
            print(f"[NEU] {title}")

        time.sleep(1)

    if new_entries:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"{OUTPUT_DIR}/enisa_publications_{ts}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(new_entries, f, ensure_ascii=False, indent=2)
        print(f"[DONE] {len(new_entries)} neue Publikationen gespeichert: {filename}")
    else:
        print("[DONE] Keine neuen Publikationen gefunden.")

if __name__ == "__main__":
    scrape_enisa_publications()
