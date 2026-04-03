#!/usr/bin/env python3
"""CashCrab Twitter Agent - 24/7 VDS runner.

PM2 compatible. Never crashes - catches all errors internally.
"""
from __future__ import annotations

import json
import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

COOKIES_PATH = Path(__file__).resolve().parent.parent / "tokens" / "twitter_cookies.json"


def load_cookies() -> dict:
    return json.loads(COOKIES_PATH.read_text())


def create_browser(pw, cookies):
    """Create a fresh browser + page. Returns (browser, page)."""
    ct0, auth_token = cookies["ct0"], cookies["auth_token"]

    browser = pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage",
              "--disable-gpu", "--single-process"],
    )
    ctx = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )
    ctx.add_cookies([
        {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
        {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
    ])
    page = ctx.new_page()

    # Navigate with generous timeout
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
    time.sleep(5)

    # Dismiss any overlays/popups
    try:
        # Cookie consent or other overlays
        for selector in ['[data-testid="sheetDialog"] [role="button"]', '[aria-label="Close"]']:
            btn = page.locator(selector).first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                time.sleep(1)
    except Exception:
        pass

    return browser, page


def main():
    from playwright.sync_api import sync_playwright

    print(f"[{datetime.now().isoformat()}] CashCrab Twitter Agent starting...")
    cookies = load_cookies()

    with sync_playwright() as pw:
        browser = None
        page = None

        # Initial browser setup
        try:
            browser, page = create_browser(pw, cookies)
            title = page.title()
            print(f"  Page: {title}")
            if "Login" in title or "Log in" in title:
                print("  ERROR: cookies expired.")
                return
            print(f"  Logged in. Running 24/7.\n")
        except Exception as exc:
            print(f"  Browser init failed: {exc}")
            return

        from modules.twitter_agent import run_cycle, cycle_sleep_minutes

        cycle = 0
        fails = 0

        while True:
            cycle += 1
            print(f"[{datetime.now().isoformat()}] === Cycle {cycle} ===")

            try:
                stats = run_cycle(page)
                print(f"  Stats: {stats}")
                fails = 0
            except Exception as exc:
                fails += 1
                print(f"  Cycle {cycle} error: {exc}")

                # Restart browser after 3 consecutive fails
                if fails >= 3:
                    print("  Restarting browser...")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    time.sleep(15)
                    try:
                        browser, page = create_browser(pw, cookies)
                        print("  Browser restarted OK")
                        fails = 0
                    except Exception as exc2:
                        print(f"  Browser restart failed: {exc2}")
                        print("  Waiting 5 min before retry...")
                        time.sleep(300)
                        try:
                            browser, page = create_browser(pw, cookies)
                            fails = 0
                        except Exception:
                            print("  FATAL: Cannot start browser. Exiting.")
                            return

            sleep_min = cycle_sleep_minutes()
            print(f"  Next cycle in {sleep_min}m\n")
            time.sleep(sleep_min * 60)


if __name__ == "__main__":
    main()
