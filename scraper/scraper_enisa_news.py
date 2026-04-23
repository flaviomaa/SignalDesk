import requests
from bs4 import BeautifulSoup
import json
import os
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin

BASE_URL = "https://www.enisa.europa.eu/news"
SOURCE = "ENISA-News"
OUTPUT_DIR = "output"
DB_PATH = "seen.db"
MAX_PAGES = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_items (
            source TEXT,
            link TEXT,
            seen_at TEXT,
            PRIMARY KEY (source, link)
        )
    """)
    conn.commit()
    return conn

def already_seen(conn, link):
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_items WHERE source=? AND link=?", (SOURCE, link))
    return c.fetchone() is not None

def mark_as_seen(conn, link):
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
              (SOURCE, link, datetime.now(timezone.utc).isoformat()))
    conn.commit()

def extract_article_data(article):
    try:
        title_tag = article.find("h3").find("a")
        link = urljoin(BASE_URL, title_tag.get("href").strip())
        title = title_tag.get_text(strip=True)

        date_tag = article.find("time")
        date_str = date_tag.get("datetime") if date_tag else ""
        date = date_str.split("T")[0] if "T" in date_str else date_str

        teaser = article.find("div", class_="content").get_text(strip=True)

        return {
            "source": SOURCE,
            "title": title,
            "link": link,
            "date": date,
            "content": teaser
        }
    except Exception as e:
        print(f"[ERROR] Artikel konnte nicht gelesen werden: {e}")
        return None

def scrape():
    print(f"[START] Starte {SOURCE}-Scraper...")
    conn = init_db()
    collected = []

    for page in range(MAX_PAGES):
        url = f"{BASE_URL}?page={page}"
        print(f"[INFO] Rufe Seite auf: {url}")
        res = requests.get(url)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = soup.select("div.publication-content")

        for article in articles:
            data = extract_article_data(article)
            if data and not already_seen(conn, data["link"]):
                collected.append(data)
                mark_as_seen(conn, data["link"])
                print(f"[NEU] {data['title']}")
            else:
                print(f"[SKIP] Bekannt oder fehlerhaft: {data['title'] if data else 'N/A'}")

    if collected:
        filename = os.path.join(OUTPUT_DIR, f"enisa_news_{datetime.now().strftime('%Y%m%d')}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(collected, f, ensure_ascii=False, indent=2)
        print(f"[DONE] {len(collected)} neue Artikel gespeichert: {filename}")
    else:
        print("[DONE] Keine neuen Artikel.")

if __name__ == "__main__":
    scrape()
