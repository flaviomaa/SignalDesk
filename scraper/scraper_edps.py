import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import os
import fitz  # PyMuPDF
from datetime import datetime
import time
import sys 

import sys

try:
    # Verhindert UnicodeEncodeError: nicht darstellbare Zeichen werden ersetzt
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

SOURCE = "EDPS"
OUTPUT_DIR = "output"
SEEN_DB = "seen.db"
DATE_STR = datetime.now().strftime("%Y%m%d")

SECTIONS = {
    "news": "https://www.edps.europa.eu/press-publications/press-news/news_en?page={}",
    "press": "https://www.edps.europa.eu/press-publications/press-news/press-releases_en?page={}",
    "publications": "https://www.edps.europa.eu/press-publications/publications_en?page={}"
}

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def is_seen(link):
    cur.execute("SELECT 1 FROM seen_items WHERE link = ?", (link,))
    return cur.fetchone() is not None

def mark_seen(link):
    cur.execute("INSERT OR IGNORE INTO seen_items (source, link, seen_at) VALUES (?, ?, ?)",
                (SOURCE, link, datetime.now().isoformat()))
    conn.commit()

def clean_paragraphs(blocks):
    return "\n\n".join(p.get_text(strip=True) for p in blocks if p.get_text(strip=True))

def extract_pdf_text(pdf_url):
    try:
        res = requests.get(pdf_url, headers=HEADERS)
        res.raise_for_status()
        with open("temp.pdf", "wb") as f:
            f.write(res.content)
        with fitz.open("temp.pdf") as doc:
            text = "\n\n".join(page.get_text().strip() for page in doc)
        os.remove("temp.pdf")
        return text.strip()
    except Exception as e:
        print(f"[WARN] PDF konnte nicht gelesen werden: {pdf_url} | {e}")
        return ""

def scrape_news_or_press(url, section):
    print(f"[INFO] Lade Seite: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    articles = soup.select("article.node")
    entries = []

    for art in articles:
        title_tag = art.select_one("h3.node__title")
        link_tag = art.select_one("div.field--name-field-edpsweb-news-link a[href]") or art.select_one("h3.node__title a[href]")
        date_tag = art.select_one("time.datetime")
        body_blocks = art.select("div.field--name-field-edpsweb-body p")

        if not title_tag or not link_tag or not date_tag:
            continue

        title = title_tag.get_text(strip=True)
        raw_link = link_tag["href"]
        link = raw_link if raw_link.startswith("http") else "https://www.edps.europa.eu" + raw_link
        date = date_tag.get_text(strip=True)
        content = clean_paragraphs(body_blocks)

        # Wenn kein brauchbarer Text, aber PDF vorhanden → Text aus PDF extrahieren
        if len(content.strip()) < 50:
            pdf_tag = art.select_one("a[href$='.pdf']")
            if pdf_tag:
                pdf_url = pdf_tag["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = "https://www.edps.europa.eu" + pdf_url
                content = extract_pdf_text(pdf_url)

        if not content:
            continue

        if is_seen(link):
            continue

        entries.append({
            "source": SOURCE,
            "section": section,
            "title": title,
            "link": link,
            "date": date,
            "content": content
        })

        mark_seen(link)
        time.sleep(0.5)

    return entries

def scrape_publications(url):
    print(f"[INFO] Lade Seite: {url}")
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"[ERROR] {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    articles = soup.select("div#block-edpsweb-news-side article.node")
    entries = []

    for art in articles:
        title_tag = art.select_one("h3.node__title a span")
        link_tag = art.select_one("h3.node__title a[href]")
        date_tag = art.select_one("time.datetime")
        body_blocks = art.select("div.field--name-field-edpsweb-news-intro p")

        if not title_tag or not link_tag or not date_tag:
            continue

        title = title_tag.get_text(strip=True)
        raw_link = link_tag["href"]
        link = raw_link if raw_link.startswith("http") else "https://www.edps.europa.eu" + raw_link
        date = date_tag.get_text(strip=True)
        content = clean_paragraphs(body_blocks)

        if len(content.strip()) < 50:
            pdf_tag = art.select_one("a[href$='.pdf']")
            if pdf_tag:
                pdf_url = pdf_tag["href"]
                if not pdf_url.startswith("http"):
                    pdf_url = "https://www.edps.europa.eu" + pdf_url
                content = extract_pdf_text(pdf_url)

        if not content:
            continue

        if is_seen(link):
            continue

        entries.append({
            "source": SOURCE,
            "section": "publications",
            "title": title,
            "link": link,
            "date": date,
            "content": content
        })

        mark_seen(link)
        time.sleep(0.5)

    return entries

def scrape_all():
    all_entries = []

    for page in range(10):  # News
        url = SECTIONS["news"].format(page)
        result = scrape_news_or_press(url, "news")
        if not result:
            break
        all_entries.extend(result)

    for page in range(10):  # Press
        url = SECTIONS["press"].format(page)
        result = scrape_news_or_press(url, "press")
        if not result:
            break
        all_entries.extend(result)

    for page in range(5):  # Publications
        url = SECTIONS["publications"].format(page)
        result = scrape_publications(url)
        if not result:
            break
        all_entries.extend(result)

    return all_entries

def save_output(entries):
    if entries:
        path = os.path.join(OUTPUT_DIR, f"edps_{DATE_STR}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
        print(f"[✅] {len(entries)} neue Einträge gespeichert in {path}")
    else:
        print("[ℹ️] Keine neuen Einträge gefunden.")

def main():
    print("[START] Starte EDPS-Scraper...")
    entries = scrape_all()
    save_output(entries)
    conn.close()

if __name__ == "__main__":
    main()
