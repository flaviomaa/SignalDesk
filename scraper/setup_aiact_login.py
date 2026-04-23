# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright
import os

PROFILE_DIR = os.path.abspath("aiact_browser_profile")
LOGIN_URL = "https://artificialintelligenceact.substack.com/archive?sort=new"

with sync_playwright() as p:
    browser = p.firefox.launch_persistent_context(
        PROFILE_DIR,
        headless=False
    )

    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto(LOGIN_URL, wait_until="domcontentloaded")

    print("\nBrowser is open.")
    print("1. Log in if needed")
    print("2. Check if the page loads normally")
    print("3. Then press ENTER here in the console\n")
    input()

    browser.close()
    print("Profile saved in:", PROFILE_DIR)