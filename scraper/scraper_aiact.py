from playwright.sync_api import sync_playwright
import json
import time
import os
import sys

import sys

try:
    # Verhindert UnicodeEncodeError: nicht darstellbare Zeichen werden ersetzt
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

ARCHIVE_URL = "https://artificialintelligenceact.substack.com/archive?sort=new"
OUTPUT_FILE = "aiact_all_articles.json"
PROFILE_DIR = "aiact_browser_profile"

def extract_article_links(page):
    seen_count = 0
    stable_count = 0

    for _ in range(100):
        page.mouse.wheel(0, 8000)
        page.wait_for_timeout(1500)

        current_links = page.query_selector_all("a[href^='https://artificialintelligenceact.substack.com/p/']")
        current_count = len(current_links)

        if current_count > seen_count:
            seen_count = current_count
            stable_count = 0
        else:
            stable_count += 1

        if stable_count >= 5:
            break

    href_seen = set()
    final_links = []

    for el in current_links:
        href = el.get_attribute("href")
        text = el.inner_text().strip()
        if href and not href.endswith("/comments") and href not in href_seen:
            href_seen.add(href)
            final_links.append((text, href))

    return final_links

def scrape_article(page, url):
    try:
        page.goto(url, timeout=60000)
        page.wait_for_timeout(2000)

        for _ in range(10):
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(500)

        title_el = page.query_selector("h1")
        date_el = page.query_selector("time")
        content_container = page.query_selector("div[data-testid='post-content']") or page.query_selector("article")

        content_text = content_container.inner_text().strip() if content_container else "Kein Inhalt gefunden"

        return {
            "title": title_el.inner_text().strip() if title_el else "Kein Titel",
            "url": url,
            "date": date_el.get_attribute("datetime") if date_el else "Unbekannt",
            "content": content_text
        }

    except Exception as e:
        print(f"⚠️ Fehler bei Artikel: {url}\n{e}")
        return None

def load_existing_urls():
    if not os.path.exists(OUTPUT_FILE):
        return set(), []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        existing_articles = json.load(f)
    existing_urls = {article["url"] for article in existing_articles}
    return existing_urls, existing_articles

def scrape_all_articles():
    with sync_playwright() as p:
        browser = p.firefox.launch_persistent_context(PROFILE_DIR, headless=False)
        page = browser.pages[0] if browser.pages else browser.new_page()

        existing_urls, existing_articles = load_existing_urls()

        page.goto(ARCHIVE_URL)
        links = extract_article_links(page)
        print(f"\n🔗 {len(links)} Artikel-Links extrahiert.\n")

        new_articles = []

        for i, (title, url) in enumerate(links, 1):
            if url in existing_urls:
                print(f"⏩ ({i}) Bereits vorhanden: {title}")
                continue

            print(f"🔎 ({i}) Scrape: {title}")
            article_data = scrape_article(page, url)
            if article_data:
                new_articles.append(article_data)

        all_articles = existing_articles + new_articles

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_articles, f, ensure_ascii=False, indent=2)

        print(f"\n✅ {len(new_articles)} neue Artikel gespeichert. Gesamt: {len(all_articles)}")
        browser.close()

if __name__ == "__main__":
    scrape_all_articles()
