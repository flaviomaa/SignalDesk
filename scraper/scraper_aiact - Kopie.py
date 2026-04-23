from playwright.sync_api import sync_playwright
import json
import time

ARCHIVE_URL = "https://artificialintelligenceact.substack.com/archive?sort=new"
OUTPUT_FILE = "aiact_all_articles.json"
PROFILE_DIR = "aiact_browser_profile"

def extract_article_links(page):
    seen_count = 0
    stable_count = 0

    for _ in range(100):  # max 100 Scrolls
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
        content_container = page.query_selector("div[data-testid='post-content']")

        if not content_container:
            content_container = page.query_selector("article")

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

def scrape_all_articles():
    with sync_playwright() as p:
        browser = p.firefox.launch_persistent_context(PROFILE_DIR, headless=False)
        page = browser.pages[0] if browser.pages else browser.new_page()

        # Schritt 1: Links extrahieren
        page.goto(ARCHIVE_URL)
        links = extract_article_links(page)
        print(f"\n✅ {len(links)} eindeutige Artikel-Links gefunden.\n")

        # Schritt 2: Jeden Artikel besuchen und scrapen
        results = []
        for i, (title, url) in enumerate(links, 1):
            print(f"🔎 ({i}/{len(links)}): {title}")
            article_data = scrape_article(page, url)
            if article_data:
                results.append(article_data)

        # Schritt 3: Speichern
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n✅ Alle Artikel gespeichert in '{OUTPUT_FILE}'.")
        browser.close()

if __name__ == "__main__":
    scrape_all_articles()
