#!/usr/bin/env python3
"""CashCrab Twitter Agent - 24/7 VDS runner.

Runs as PM2 process. Playwright browser loops forever.
All product-specific config comes from config.json.

Usage:
    pm2 start scripts/agent_runner.py --name twitter-agent --interpreter .venv/bin/python3
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

from playwright.sync_api import sync_playwright

COOKIES_PATH = Path(__file__).resolve().parent.parent / "tokens" / "twitter_cookies.json"


def load_cookies() -> dict:
    return json.loads(COOKIES_PATH.read_text())


def main():
    print(f"[{datetime.now().isoformat()}] CashCrab Twitter Agent starting...")
    print(f"  24/7 mode. Rate limits enforced internally.")

    cookies = load_cookies()
    ct0 = cookies["ct0"]
    auth_token = cookies["auth_token"]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        ctx.add_cookies([
            {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
        ])
        page = ctx.new_page()

        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        title = page.title()
        print(f"  Page title: {title}")
        if "Login" in title or "Log in" in title:
            print("  ERROR: Not logged in. Check cookies.")
            browser.close()
            sys.exit(1)

        print(f"  Logged in. Agent loop starting.\n")

        from modules.twitter_agent import run_cycle

        cycle = 0
        consecutive_errors = 0

        while True:
            cycle += 1
            print(f"[{datetime.now().isoformat()}] === Cycle {cycle} ===")

            try:
                stats = run_cycle(page)
                print(f"  Results: {stats}")
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                print(f"  Cycle error: {exc}")
                traceback.print_exc()

                if consecutive_errors >= 5:
                    print("  Too many errors, restarting browser...")
                    try:
                        browser.close()
                    except Exception:
                        pass
                    time.sleep(10)
                    browser = p.chromium.launch(
                        headless=True,
                        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                    )
                    ctx = browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                        viewport={"width": 1920, "height": 1080},
                    )
                    ctx.add_cookies([
                        {"name": "ct0", "value": ct0, "domain": ".x.com", "path": "/"},
                        {"name": "auth_token", "value": auth_token, "domain": ".x.com", "path": "/"},
                    ])
                    page = ctx.new_page()
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                    time.sleep(3)
                    consecutive_errors = 0
                    print("  Browser restarted.")

            from modules.twitter_agent import cycle_sleep_minutes
            sleep_min = cycle_sleep_minutes()
            print(f"  Next cycle in {sleep_min} min...\n")
            time.sleep(sleep_min * 60)


if __name__ == "__main__":
    main()
