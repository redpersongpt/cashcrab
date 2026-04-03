"""Cookie-based Twitter client using direct HTTP API.

Drop-in replacement for tweepy.Client when OAuth tokens are unavailable.
Uses browser cookies (ct0 + auth_token) with Twitter's internal API.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from modules.config import ROOT

COOKIES_PATH = ROOT / "tokens" / "twitter_cookies.json"

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# Query IDs extracted from x.com JS bundle — these rotate, update if broken
_QID = {
    "CreateTweet": "IceLmZOK75drD8mMwcJoUA",
    "FavoriteTweet": "lI07N6Otwv1PhnEgXILM7A",
    "UserTweets": "78bXcjBXrR1q_uIdj22zhQ",
    "SearchTimeline": "g7SDsWwiaaKtRjngIIq-mA",
    "HomeTimeline": "CjPlrHqm60wc8h8z6QNKyA",
    "Viewer": "_8ClT24oZ8tpylf_OSuNdg",
    "UserByScreenName": "IGgvgiOx4QZndDHuD3x9TQ",
}

def _gql(op: str) -> str:
    return f"https://x.com/i/api/graphql/{_QID[op]}/{op}"

API_NOTIFICATIONS = "https://x.com/i/api/2/notifications/all.json"


@dataclass
class TweetData:
    id: str
    text: str
    author_id: str | None = None
    public_metrics: dict = field(default_factory=dict)
    created_at: Any = None


@dataclass
class UserData:
    id: str
    username: str
    description: str = ""
    public_metrics: dict = field(default_factory=dict)


@dataclass
class TweepyLikeResponse:
    data: dict = field(default_factory=dict)


@dataclass
class TweepyResponse:
    data: Any = None
    includes: dict | None = None


class CookieTwitterClient:
    """Sync HTTP client that mimics tweepy.Client interface using cookies."""

    def __init__(self):
        cookies = self._load_cookies()
        self._ct0 = cookies["ct0"]
        self._auth_token = cookies["auth_token"]
        self._http = httpx.Client(
            headers=self._build_headers(),
            timeout=30.0,
            follow_redirects=True,
        )
        self._me: UserData | None = None
        self._pw_browser = None
        self._pw_context = None
        self._pw_page = None

    def _load_cookies(self) -> dict:
        if not COOKIES_PATH.exists():
            raise RuntimeError(
                "No Twitter cookies found. Run cookie extraction first."
            )
        data = json.loads(COOKIES_PATH.read_text())
        if not data.get("ct0") or not data.get("auth_token"):
            raise RuntimeError("Invalid Twitter cookies. Re-extract them.")
        return data

    def _build_headers(self) -> dict:
        return {
            "authorization": f"Bearer {BEARER_TOKEN}",
            "x-csrf-token": self._ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "cookie": f"ct0={self._ct0}; auth_token={self._auth_token}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "referer": "https://x.com/",
            "origin": "https://x.com",
        }

    def _check_response(self, resp: httpx.Response, action: str):
        if resp.status_code == 403:
            raise RuntimeError(f"Twitter {action} forbidden (403). Cookies may be expired. Re-extract them.")
        if resp.status_code == 429:
            raise RuntimeError(f"Twitter rate limit hit during {action}. Wait a few minutes.")
        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.json().get("errors", [{}])[0].get("message", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f"Twitter {action} failed ({resp.status_code}): {detail}")

    def _ensure_browser(self):
        """Lazy-init a Playwright browser for write operations (anti-bot bypass)."""
        if self._pw_page is not None:
            return

        from playwright.sync_api import sync_playwright
        import time

        self._pw = sync_playwright().start()
        self._pw_browser = self._pw.chromium.launch(headless=True)
        self._pw_context = self._pw_browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        self._pw_context.add_cookies([
            {"name": "ct0", "value": self._ct0, "domain": ".x.com", "path": "/"},
            {"name": "auth_token", "value": self._auth_token, "domain": ".x.com", "path": "/"},
        ])
        self._pw_page = self._pw_context.new_page()
        self._pw_page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

    def _close_browser(self):
        if self._pw_browser:
            self._pw_browser.close()
            self._pw.stop()
            self._pw_browser = None
            self._pw_context = None
            self._pw_page = None

    def create_tweet(self, text: str = "", **kwargs) -> TweepyResponse:
        import time

        reply_to = kwargs.get("in_reply_to_tweet_id")

        self._ensure_browser()
        page = self._pw_page

        if reply_to:
            # Navigate to the tweet to reply
            page.goto(f"https://x.com/i/status/{reply_to}", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)
            # Click reply button
            reply_btn = page.locator('[data-testid="reply"]').first
            if reply_btn.count() > 0:
                reply_btn.click()
                time.sleep(1)
        else:
            # Navigate to compose
            page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)

        # Type the tweet (use .first because compose page has 2 textareas)
        compose = page.locator('[data-testid="tweetTextarea_0"]').first
        compose.click()
        time.sleep(0.5)

        # Type text in chunks to avoid detection
        for char in text:
            page.keyboard.type(char, delay=20)
        time.sleep(1)

        # Capture the tweet ID from the response
        tweet_id = ""
        def capture_tweet(response):
            nonlocal tweet_id
            if "CreateTweet" in response.url and response.status == 200:
                try:
                    data = response.json()
                    tweet_id = (
                        data.get("data", {})
                        .get("create_tweet", {})
                        .get("tweet_results", {})
                        .get("result", {})
                        .get("rest_id", "")
                    )
                except Exception:
                    pass

        page.on("response", capture_tweet)

        # Click tweet/reply button
        if reply_to:
            btn = page.locator('[data-testid="tweetButton"]')
        else:
            btn = page.locator('[data-testid="tweetButton"]')
        btn.click()
        time.sleep(3)

        page.remove_listener("response", capture_tweet)

        return TweepyResponse(data={"id": tweet_id})

    def like(self, tweet_id) -> TweepyLikeResponse:
        import time

        self._ensure_browser()
        page = self._pw_page

        # Navigate to the tweet
        page.goto(f"https://x.com/i/status/{tweet_id}", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)

        # Click the like button
        like_btn = page.locator('[data-testid="like"]').first
        if like_btn.count() > 0:
            like_btn.click()
            time.sleep(1)

        return TweepyLikeResponse(data={"liked": True})

    def get_me(self, **kwargs) -> TweepyResponse:
        if self._me:
            return TweepyResponse(data=self._me)

        # Use Viewer GraphQL endpoint
        variables = {"withCommunitiesMemberships": False}
        features = {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }
        resp = self._http.get(
            _gql("Viewer"),
            params={
                "variables": json.dumps(variables),
                "features": json.dumps(features),
            },
        )
        self._check_response(resp, "get_me")

        viewer_data = resp.json()
        user_result = (
            viewer_data.get("data", {})
            .get("viewer", {})
            .get("user_results", {})
            .get("result", {})
        )
        legacy = user_result.get("legacy", {})
        core = user_result.get("core", {})

        self._me = UserData(
            id=user_result.get("rest_id", ""),
            username=core.get("screen_name", "") or legacy.get("screen_name", ""),
            description=legacy.get("description", ""),
            public_metrics={
                "followers_count": legacy.get("followers_count", 0),
                "following_count": legacy.get("friends_count", 0),
                "tweet_count": legacy.get("statuses_count", 0),
            },
        )
        return TweepyResponse(data=self._me)

    def get_users_tweets(self, user_id, **kwargs) -> TweepyResponse:
        max_results = kwargs.get("max_results", 40)
        variables = {
            "userId": str(user_id),
            "count": max_results,
            "includePromotedContent": False,
            "withQuickPromoteEligibilityTweetFields": False,
            "withVoice": False,
            "withV2Timeline": True,
        }
        features = {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "communities_web_enable_tweet_community_results_fetch": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }

        resp = self._http.get(
            _gql("UserTweets"),
            params={
                "variables": json.dumps(variables),
                "features": json.dumps(features),
            },
        )
        self._check_response(resp, "get_users_tweets")
        return self._parse_timeline_response(resp.json())

    def search_recent_tweets(self, query: str, **kwargs) -> TweepyResponse:
        max_results = kwargs.get("max_results", 20)
        variables = {
            "rawQuery": query,
            "count": max_results,
            "querySource": "typed_query",
            "product": "Latest",
        }
        features = {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "communities_web_enable_tweet_community_results_fetch": True,
            "articles_preview_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }

        resp = self._http.get(
            _gql("SearchTimeline"),
            params={
                "variables": json.dumps(variables),
                "features": json.dumps(features),
            },
        )
        self._check_response(resp, "search")
        return self._parse_timeline_response(resp.json())

    def get_home_timeline(self, **kwargs) -> TweepyResponse:
        max_results = kwargs.get("max_results", 20)
        variables = {
            "count": max_results,
            "includePromotedContent": False,
            "latestControlAvailable": True,
            "withCommunity": True,
        }
        features = {
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "communities_web_enable_tweet_community_results_fetch": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }

        resp = self._http.get(
            _gql("HomeTimeline"),
            params={
                "variables": json.dumps(variables),
                "features": json.dumps(features),
            },
        )
        self._check_response(resp, "home_timeline")
        return self._parse_timeline_response(resp.json())

    def _parse_timeline_response(self, data: dict) -> TweepyResponse:
        tweets = []
        users_map = {}

        instructions = self._find_instructions(data)
        for instruction in instructions:
            entries = instruction.get("entries", [])
            for entry in entries:
                tweet_data = self._extract_tweet_from_entry(entry)
                if tweet_data:
                    tweets.append(tweet_data[0])
                    if tweet_data[1]:
                        users_map[tweet_data[1].id] = tweet_data[1]

        includes = {"users": list(users_map.values())} if users_map else None
        return TweepyResponse(data=tweets if tweets else None, includes=includes)

    def _find_instructions(self, data: dict) -> list:
        # Navigate various response shapes
        for path in [
            ["data", "user", "result", "timeline_v2", "timeline", "instructions"],
            ["data", "search_by_raw_query", "search_timeline", "timeline", "instructions"],
            ["data", "home", "home_timeline_urt", "instructions"],
        ]:
            obj = data
            for key in path:
                obj = obj.get(key, {}) if isinstance(obj, dict) else {}
            if isinstance(obj, list):
                return obj
        return []

    def _extract_tweet_from_entry(self, entry: dict) -> tuple[TweetData, UserData | None] | None:
        content = entry.get("content", {})
        item_content = content.get("itemContent", {})
        if not item_content:
            # Try nested items
            items = content.get("items", [])
            if items:
                item_content = items[0].get("item", {}).get("itemContent", {})

        tweet_result = (
            item_content
            .get("tweet_results", {})
            .get("result", {})
        )

        if not tweet_result or tweet_result.get("__typename") not in ("Tweet", "TweetWithVisibilityResults"):
            return None

        if tweet_result.get("__typename") == "TweetWithVisibilityResults":
            tweet_result = tweet_result.get("tweet", tweet_result)

        legacy = tweet_result.get("legacy", {})
        core = tweet_result.get("core", {})
        user_results = core.get("user_results", {}).get("result", {})
        user_legacy = user_results.get("legacy", {})

        tweet_id = tweet_result.get("rest_id", "")
        text = legacy.get("full_text", "")
        author_id = user_results.get("rest_id")

        created_at_str = legacy.get("created_at", "")
        created_at = None
        if created_at_str:
            try:
                created_at = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            except (ValueError, TypeError):
                pass

        tweet = TweetData(
            id=tweet_id,
            text=text,
            author_id=author_id,
            public_metrics={
                "like_count": legacy.get("favorite_count", 0),
                "reply_count": legacy.get("reply_count", 0),
                "retweet_count": legacy.get("retweet_count", 0),
            },
            created_at=created_at,
        )

        user = None
        if author_id and user_legacy:
            user = UserData(
                id=author_id,
                username=user_legacy.get("screen_name", ""),
                description=user_legacy.get("description", ""),
                public_metrics={
                    "followers_count": user_legacy.get("followers_count", 0),
                    "following_count": user_legacy.get("friends_count", 0),
                    "tweet_count": user_legacy.get("statuses_count", 0),
                },
            )

        return tweet, user


# ---------------------------------------------------------------------------
# Cookie extraction and persistence
# ---------------------------------------------------------------------------

def extract_cookies_from_chrome() -> dict:
    """Extract Twitter cookies from Chromium-based browsers (macOS)."""
    import sqlite3
    import tempfile
    import shutil
    import platform

    if platform.system() != "Darwin":
        return {}

    browsers = [
        (
            Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser/Default/Cookies",
            "Brave Safe Storage",
            "Brave",
        ),
        (
            Path.home() / "Library/Application Support/Google/Chrome/Default/Cookies",
            "Chrome Safe Storage",
            "Chrome",
        ),
        (
            Path.home() / "Library/Application Support/Microsoft Edge/Default/Cookies",
            "Microsoft Edge Safe Storage",
            "Microsoft Edge",
        ),
        (
            Path.home() / "Library/Application Support/Vivaldi/Default/Cookies",
            "Vivaldi Safe Storage",
            "Vivaldi",
        ),
        (
            Path.home() / "Library/Application Support/Arc/User Data/Default/Cookies",
            "Arc Safe Storage",
            "Arc",
        ),
    ]

    for cookie_db, keychain_svc, keychain_acct in browsers:
        if not cookie_db.exists():
            continue
        result = _try_extract_from_chromium_db(cookie_db, keychain_svc, keychain_acct)
        if result.get("ct0") and result.get("auth_token"):
            return result

    return {}


def _try_extract_from_chromium_db(cookie_db: Path, keychain_svc: str, keychain_acct: str) -> dict:
    import sqlite3
    import subprocess
    import tempfile
    import shutil

    tmp = tempfile.mktemp(suffix=".db")
    shutil.copy2(str(cookie_db), tmp)

    try:
        kc_result = subprocess.run(
            ["security", "find-generic-password", "-w", "-s", keychain_svc, "-a", keychain_acct],
            capture_output=True, text=True, timeout=30,
        )
        if kc_result.returncode != 0:
            return {}

        key_password = kc_result.stdout.strip()
        aes_key = _derive_chromium_key(key_password)

        conn = sqlite3.connect(tmp)
        cursor = conn.cursor()

        results = {}
        for name in ("ct0", "auth_token"):
            cursor.execute(
                "SELECT encrypted_value, value FROM cookies "
                "WHERE (host_key LIKE '%x.com' OR host_key LIKE '%twitter.com') AND name = ?",
                (name,),
            )
            row = cursor.fetchone()
            if row:
                encrypted_value, plain_value = row
                if plain_value:
                    results[name] = plain_value
                elif encrypted_value:
                    decrypted = _decrypt_chromium_cookie(encrypted_value, aes_key)
                    if decrypted:
                        results[name] = decrypted

        conn.close()
        return results
    except Exception:
        return {}
    finally:
        Path(tmp).unlink(missing_ok=True)


def _derive_chromium_key(key_password: str) -> bytes:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1003,
    )
    return kdf.derive(key_password.encode("utf-8"))


def _decrypt_chromium_cookie(encrypted_value: bytes, aes_key: bytes) -> str | None:
    if not encrypted_value:
        return None

    if encrypted_value[:3] != b"v10":
        return None

    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        ciphertext = encrypted_value[3:]
        iv = b" " * 16

        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()

        padding_len = decrypted[-1]
        if isinstance(padding_len, int) and 1 <= padding_len <= 16:
            decrypted = decrypted[:-padding_len]

        return decrypted.decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_cookies_manual() -> dict:
    from modules import ui

    ui.info("Manual cookie extraction from your browser:")
    ui.info("1. Open x.com in your browser (make sure you're logged in)")
    ui.info("2. Open DevTools (F12) -> Application -> Cookies -> https://x.com")
    ui.info("3. Copy the values of 'ct0' and 'auth_token'")
    ui.divider()

    ct0 = ui.ask("ct0 cookie value")
    auth_token = ui.ask("auth_token cookie value")

    if not ct0 or not auth_token:
        raise RuntimeError("Both ct0 and auth_token are required.")

    return {"ct0": ct0, "auth_token": auth_token}


def save_cookies_for_twikit(ct0: str, auth_token: str) -> Path:
    """Save cookies as simple JSON dict."""
    COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIES_PATH.write_text(
        json.dumps({"ct0": ct0, "auth_token": auth_token}, indent=2),
        encoding="utf-8",
    )
    return COOKIES_PATH


def cookies_available() -> bool:
    return COOKIES_PATH.exists()
