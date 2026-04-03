#!/usr/bin/env python3
"""CashCrab Twitter Agent - 24/7 VDS runner.

Pure HTTP. No Playwright. Uses curl_cffi for Chrome TLS impersonation.
"""
from __future__ import annotations

import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    print(f"[{datetime.now().isoformat()}] CashCrab Twitter Agent starting...")
    print(f"  Pure HTTP mode (curl_cffi). No browser needed.")

    from modules.http_twitter import HttpTwitter
    try:
        api = HttpTwitter()
        me = api.get_me()
        print(f"  Logged in as @{me.get('username', '?')} ({me.get('followers', 0)} followers)")
    except Exception as exc:
        print(f"  Login failed: {exc}")
        return

    from modules.twitter_agent import run_cycle_http, cycle_sleep_minutes

    cycle = 0
    consecutive_errors = 0

    while True:
        cycle += 1
        print(f"\n[{datetime.now().isoformat()}] === Cycle {cycle} ===")

        try:
            stats = run_cycle_http()
            print(f"  Stats: {stats}")
            consecutive_errors = 0
        except Exception as exc:
            consecutive_errors += 1
            print(f"  Cycle error: {exc}")
            if consecutive_errors >= 5:
                print("  Too many errors. Sleeping 30 min before retry...")
                time.sleep(1800)
                consecutive_errors = 0
                continue

        sleep_min = cycle_sleep_minutes()
        print(f"  Next cycle in {sleep_min}m")
        time.sleep(sleep_min * 60)


if __name__ == "__main__":
    main()
