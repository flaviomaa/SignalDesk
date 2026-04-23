import feedparser
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from pathlib import Path

# Pfade
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "eurlex_test_output.txt"

# EUR-Lex RSS Feed (Serie L oder C)
FEED_URL = "https://eur-lex.europa.eu/DE/display-feed.rss?rssId=222"  # Serie L

# Lade Feed
feed = feedparser.parse(FEED_URL)
if not feed.entries:
    print("⚠️ Keine Einträge im Feed gefunden.")
    exit()

# Nur der erste Eintrag
entry = feed.entries[0]
title = entry.title
link = entry.link
date = entry.published

# Inhalt laden (HTML oder PDF)
try:
    response = requests.get(link, timeout=15)
    content_type = response.headers.get("Content-Type", "")

    if "pdf" in content_type:
        pdf_path = BASE_DIR / "temp_test.pdf"
        with open(pdf_path, "wb") as f:
            f.write(response.content)

        with fitz.open(pdf_path) as doc:
            full_text = "\n".join(page.get_text() for page in doc)
        pdf_path.unlink()
    else:
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        full_text = "\n".join(p.get_text(strip=True) for p in paragraphs)

except Exception as e:
    full_text = f"[Fehler beim Abrufen: {e}]"

# In Datei schreiben
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(f"Titel: {title}\n")
    f.write(f"Link: {link}\n")
    f.write(f"Datum: {date}\n\n")
    f.write(full_text)

print(f"✅ Artikel gespeichert in {OUTPUT_FILE}")
