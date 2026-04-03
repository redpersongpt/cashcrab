#!/usr/bin/env python3
"""CashCrab Twitter Agent - 24/7 VDS runner (Hybrid mode).

HTTP API for reads (timeline, likes, notifications) - fast, no browser.
Playwright for writes (tweet, reply) - opens browser only when needed, closes after.
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


def post_with_playwright(cookies: dict, text: str, reply_to_url: str | None = None) -> bool:
    """Open browser, post tweet/reply, close browser. Minimizes memory usage."""
    import subprocess
    from playwright.sync_api import sync_playwright

    ct0, auth_token = cookies["ct0"], cookies["auth_token"]

    # Free RAM: stop heavy PM2 services temporarily
    subprocess.run(["pm2", "stop", "redcore-web", "cloud-api"], capture_output=True, timeout=10)
    time.sleep(2)

    try:
        result = _do_playwright_post(ct0, auth_token, text, reply_to_url)
    finally:
        # Restart services
        subprocess.run(["pm2", "start", "redcore-web", "cloud-api"], capture_output=True, timeout=10)

    return result


def _do_playwright_post(ct0: str, auth_token: str, text: str, reply_to_url: str | None = None) -> bool:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
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

        try:
            if reply_to_url:
                # Navigate to tweet, find reply box
                page.goto(reply_to_url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
            else:
                page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)

            # Dismiss overlays
            try:
                page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception:
                pass

            # Wait for compose area to be ready
            page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=30000)
            time.sleep(1)
            compose = page.locator('[data-testid="tweetTextarea_0"]').first
            compose.click(timeout=10000)
            time.sleep(0.5)

            for idx, line in enumerate(text.split("\n")):
                if idx > 0:
                    page.keyboard.press("Enter")
                if line.strip():
                    page.keyboard.type(line, delay=random.randint(8, 18))

            time.sleep(2)
            page.keyboard.press("Control+Enter")
            time.sleep(5)

            browser.close()
            return True

        except Exception as exc:
            print(f"  [playwright] error: {exc}")
            browser.close()
            return False


def main():
    print(f"[{datetime.now().isoformat()}] CashCrab Twitter Agent (Hybrid) starting...")
    print(f"  HTTP for reads, Playwright for writes. 24/7.")

    cookies = load_cookies()

    # Verify cookies work via HTTP
    from modules.http_twitter import HttpTwitter
    try:
        api = HttpTwitter()
        me = api.get_me()
        print(f"  Logged in as @{me.get('username', '?')} ({me.get('followers', 0)} followers)")
    except Exception as exc:
        print(f"  Cookie check failed: {exc}")
        return

    from modules.twitter_agent import run_cycle_hybrid, cycle_sleep_minutes

    cycle = 0
    while True:
        cycle += 1
        print(f"\n[{datetime.now().isoformat()}] === Cycle {cycle} ===")

        try:
            stats = run_cycle_hybrid(cookies, post_with_playwright)
            print(f"  Stats: {stats}")
        except Exception as exc:
            print(f"  Cycle error: {exc}")
            traceback.print_exc()

        sleep_min = cycle_sleep_minutes()
        print(f"  Next cycle in {sleep_min}m")
        time.sleep(sleep_min * 60)


if __name__ == "__main__":
    main()
