"""Full HTTP Twitter client using curl_cffi (Chrome TLS impersonation).

No Playwright needed. Bypasses Cloudflare + Error 226.
Uses cookie auth + Chrome TLS fingerprint via curl_cffi.
"""
from __future__ import annotations

import json
from pathlib import Path

from curl_cffi.requests import Session

from modules.config import ROOT

COOKIES_PATH = ROOT / "tokens" / "twitter_cookies.json"
ENGAGED_PATH = ROOT / "engaged_ids.json"
BLACKLIST_PATH = ROOT / "blacklist.json"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

FEATURES = {
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "articles_preview_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

QID = {
    "HomeTimeline": "CjPlrHqm60wc8h8z6QNKyA",
    "FavoriteTweet": "lI07N6Otwv1PhnEgXILM7A",
    "Viewer": "_8ClT24oZ8tpylf_OSuNdg",
    "CreateTweet": "IceLmZOK75drD8mMwcJoUA",
    "UserTweets": "78bXcjBXrR1q_uIdj22zhQ",
}


class HttpTwitter:
    def __init__(self):
        cookies = json.loads(COOKIES_PATH.read_text())
        self._ct0 = cookies["ct0"]
        self._at = cookies["auth_token"]
        self._session = Session(impersonate="chrome120")
        self._session.cookies.set("ct0", self._ct0, domain=".x.com")
        self._session.cookies.set("auth_token", self._at, domain=".x.com")
        self._daily_limit_hit = False
        self._engaged_ids: dict[str, bool] = self._load_engaged()
        self._blacklist: set[str] = self._load_blacklist()

    def _headers(self) -> dict:
        return {
            "authorization": f"Bearer {BEARER}",
            "x-csrf-token": self._ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "referer": "https://x.com/",
            "origin": "https://x.com",
        }

    def _refresh_ct0(self, response):
        """Auto-refresh ct0 from response cookies."""
        try:
            if not hasattr(response, 'cookies'):
                return
            for name, value in response.cookies.items():
                if name == 'ct0' and value and value != self._ct0:
                    self._ct0 = value
                    self._session.cookies.set("ct0", self._ct0, domain=".x.com")
                    cookies = json.loads(COOKIES_PATH.read_text())
                    cookies["ct0"] = self._ct0
                    COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
                    break
        except Exception as exc:
            print(f"  [ct0] refresh failed: {exc}")

    def _load_engaged(self) -> dict:
        if ENGAGED_PATH.exists():
            try:
                data = json.loads(ENGAGED_PATH.read_text())
                if isinstance(data, dict):
                    return data
                return {k: True for k in data} if isinstance(data, list) else {}
            except Exception:
                pass
        return {}

    def _save_engaged(self):
        # Keep last 300 entries
        keys = list(self._engaged_ids.keys())
        if len(keys) > 300:
            self._engaged_ids = {k: True for k in keys[-300:]}
        try:
            ENGAGED_PATH.write_text(json.dumps(list(self._engaged_ids.keys())))
        except Exception:
            pass

    def _load_blacklist(self) -> set:
        if BLACKLIST_PATH.exists():
            try:
                return {u.lower() for u in json.loads(BLACKLIST_PATH.read_text())}
            except Exception:
                pass
        return set()

    def is_blacklisted(self, username: str) -> bool:
        return username.lower() in self._blacklist

    def already_engaged(self, tweet_id: str) -> bool:
        return tweet_id in self._engaged_ids

    def mark_engaged(self, tweet_id: str):
        self._engaged_ids[tweet_id] = True
        if len(self._engaged_ids) > 500:
            keys = list(self._engaged_ids.keys())
            self._engaged_ids = {k: True for k in keys[-300:]}
        self._save_engaged()

    @property
    def can_post(self) -> bool:
        return not self._daily_limit_hit

    def get_me(self) -> dict:
        r = self._session.get(
            f"https://x.com/i/api/graphql/{QID['Viewer']}/Viewer",
            params={
                "variables": json.dumps({"withCommunitiesMemberships": False}),
                "features": json.dumps(FEATURES),
            },
            headers=self._headers(),
        )
        if r.status_code != 200:
            return {}
        user = r.json().get("data", {}).get("viewer", {}).get("user_results", {}).get("result", {})
        core = user.get("core", {})
        legacy = user.get("legacy", {})
        return {
            "id": user.get("rest_id", ""),
            "username": core.get("screen_name", ""),
            "followers": legacy.get("followers_count", 0),
            "tweets": legacy.get("statuses_count", 0),
        }

    def home_timeline(self, count: int = 20) -> list[dict]:
        r = self._session.get(
            f"https://x.com/i/api/graphql/{QID['HomeTimeline']}/HomeTimeline",
            params={
                "variables": json.dumps({"count": count, "includePromotedContent": False, "latestControlAvailable": True}),
                "features": json.dumps(FEATURES),
            },
            headers=self._headers(),
        )
        if r.status_code != 200:
            return []
        return self._parse_timeline(r.json(), ["data", "home", "home_timeline_urt", "instructions"])

    def like(self, tweet_id: str) -> bool:
        if self.already_engaged(tweet_id):
            return False
        try:
            r = self._session.post(
                f"https://x.com/i/api/graphql/{QID['FavoriteTweet']}/FavoriteTweet",
                json={"variables": {"tweet_id": tweet_id}, "queryId": QID["FavoriteTweet"]},
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code == 200 and "Done" in (r.text or ""):
                self.mark_engaged(tweet_id)
                return True
        except Exception:
            pass
        return False

    def create_tweet(self, text: str, reply_to: str | None = None, max_retries: int = 2) -> str | None:
        """Post a tweet or reply. Returns tweet ID or None. Retries on transient 226."""
        if self._daily_limit_hit:
            return None

        variables = {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
        }
        if reply_to:
            variables["reply"] = {
                "in_reply_to_tweet_id": reply_to,
                "exclude_reply_user_ids": [],
            }

        r = self._session.post(
            f"https://x.com/i/api/graphql/{QID['CreateTweet']}/CreateTweet",
            json={"variables": variables, "features": FEATURES, "queryId": QID["CreateTweet"]},
            headers=self._headers(),
        )
        self._refresh_ct0(r)

        if r.status_code != 200:
            return None

        try:
            data = r.json()
        except Exception:
            return None

        if "errors" in data:
            errors = data.get("errors", [{}])
            err = errors[0].get("message", "") if errors else ""
            code = errors[0].get("code", 0) if errors else 0
            if code == 344 or "daily limit" in err.lower():
                self._daily_limit_hit = True
                print("  [LIMIT] Daily tweet limit reached. Switching to like-only mode.")
                return None
            if code == 226 and max_retries > 0:
                # Transient anti-bot — exponential backoff retry
                wait = (3 - max_retries) * 15 + 10  # 10s, 25s
                print(f"  [226] Anti-bot triggered. Waiting {wait}s and retrying...")
                import time
                time.sleep(wait)
                return self.create_tweet(text, reply_to, max_retries - 1)
            raise RuntimeError(f"CreateTweet: {err[:150]}")

        tweet_id = (
            data.get("data", {})
            .get("create_tweet", {})
            .get("tweet_results", {})
            .get("result", {})
            .get("rest_id", "")
        )
        if tweet_id:
            self.mark_engaged(tweet_id)
        return tweet_id or None

    def retweet(self, tweet_id: str) -> bool:
        """Retweet a tweet."""
        if self._daily_limit_hit or self.already_engaged(tweet_id):
            return False
        try:
            r = self._session.post(
                "https://x.com/i/api/graphql/ojPdsZsimiJrUGLR1sjUtA/CreateRetweet",
                json={"variables": {"tweet_id": tweet_id, "dark_request": False}, "queryId": "ojPdsZsimiJrUGLR1sjUtA"},
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code == 200:
                data = r.json()
                if "errors" not in data:
                    self.mark_engaged(tweet_id)
                    return True
        except Exception:
            pass
        return False

    def quote_tweet(self, tweet_id: str, comment: str) -> str | None:
        """Quote tweet. Returns new tweet ID or None."""
        if self._daily_limit_hit or self.already_engaged(tweet_id):
            return None
        variables = {
            "tweet_text": comment,
            "attachment_url": f"https://twitter.com/i/status/{tweet_id}",
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
        }
        try:
            r = self._session.post(
                f"https://x.com/i/api/graphql/{QID['CreateTweet']}/CreateTweet",
                json={"variables": variables, "features": FEATURES, "queryId": QID["CreateTweet"]},
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code != 200:
                return None
            data = r.json()
            if "errors" in data:
                err = data.get("errors", [{}])[0].get("message", "")
                if "daily limit" in err.lower():
                    self._daily_limit_hit = True
                return None
            tid = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {}).get("rest_id", "")
            if tid:
                self.mark_engaged(tweet_id)
            return tid or None
        except Exception:
            return None

    def send_webhook(self, text: str, webhook_url: str | None = None):
        """Send notification to Discord/Slack webhook."""
        if not webhook_url:
            return
        try:
            import requests
            requests.post(webhook_url, json={"content": text}, timeout=5)
        except Exception:
            pass

    def notifications(self) -> list[dict]:
        r = self._session.get(
            "https://x.com/i/api/2/notifications/all.json",
            headers=self._headers(),
        )
        if r.status_code != 200 or not r.content:
            return []
        data = r.json()
        tweets = data.get("globalObjects", {}).get("tweets", {})
        users = data.get("globalObjects", {}).get("users", {})
        results = []
        for tid, t in tweets.items():
            uid = t.get("user_id_str", "")
            u = users.get(uid, {})
            results.append({
                "id": tid,
                "text": t.get("full_text", ""),
                "user": u.get("screen_name", ""),
                "likes": t.get("favorite_count", 0),
                "replies": t.get("reply_count", 0),
            })
        return results

    def follow(self, user_id: str) -> bool:
        """Follow a user by ID."""
        if self.already_engaged(f"follow_{user_id}"):
            return False
        r = self._session.post(
            "https://x.com/i/api/1.1/friendships/create.json",
            data={"user_id": user_id},
            headers={**self._headers(), "content-type": "application/x-www-form-urlencoded"},
        )
        self._refresh_ct0(r)
        if r.status_code == 200:
            self.mark_engaged(f"follow_{user_id}")
            return True
        return False

    def get_own_tweets(self, user_id: str, count: int = 10) -> list[dict]:
        """Get own tweets for performance tracking."""
        r = self._session.get(
            f"https://x.com/i/api/graphql/{QID.get('UserTweets', '78bXcjBXrR1q_uIdj22zhQ')}/UserTweets",
            params={
                "variables": json.dumps({"userId": user_id, "count": count, "includePromotedContent": False, "withQuickPromoteEligibilityTweetFields": False, "withVoice": False, "withV2Timeline": True}),
                "features": json.dumps(FEATURES),
            },
            headers=self._headers(),
        )
        self._refresh_ct0(r)
        if r.status_code != 200:
            return []
        # Try both timeline paths
        for path in [
            ["data", "user", "result", "timeline_v2", "timeline", "instructions"],
            ["data", "user", "result", "timeline", "timeline", "instructions"],
        ]:
            result = self._parse_timeline(r.json(), path)
            if result:
                return result
        return []

    def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet."""
        r = self._session.post(
            "https://x.com/i/api/graphql/VaenaVgh5q5ih7kvyVjgtg/DeleteTweet",
            json={"variables": {"tweet_id": tweet_id, "dark_request": False}, "queryId": "VaenaVgh5q5ih7kvyVjgtg"},
            headers=self._headers(),
        )
        self._refresh_ct0(r)
        return r.status_code == 200

    def get_tweet_replies(self, tweet_id: str) -> list[dict]:
        """Get replies to a specific tweet (for conversation tracking)."""
        try:
            r = self._session.get(
                f"https://x.com/i/api/graphql/oPRG-p-gbWDkVBBjCfnDsA/TweetDetail",
                params={
                    "variables": json.dumps({"focalTweetId": tweet_id, "with_rux_injections": False, "rankingMode": "Relevance", "includePromotedContent": False, "withCommunity": True, "withQuickPromoteEligibilityTweetFields": True, "withBirdwatchNotes": True, "withVoice": True}),
                    "features": json.dumps(FEATURES),
                },
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code != 200:
                return []
            data = r.json()
            replies = []
            for inst in data.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", []):
                for entry in inst.get("entries", []):
                    items = entry.get("content", {}).get("items", [])
                    for item in items:
                        result = item.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                        if result.get("__typename") == "TweetWithVisibilityResults":
                            result = result.get("tweet", result)
                        leg = result.get("legacy", {})
                        core = result.get("core", {}).get("user_results", {}).get("result", {})
                        text = leg.get("full_text", "")
                        tid = result.get("rest_id", "")
                        if text and tid and tid != tweet_id:
                            replies.append({
                                "id": tid,
                                "text": text,
                                "user": core.get("core", {}).get("screen_name", "") or core.get("legacy", {}).get("screen_name", ""),
                                "in_reply_to": leg.get("in_reply_to_status_id_str", ""),
                            })
            return replies
        except Exception:
            return []

    def get_follower_ids(self, user_id: str, count: int = 20) -> list[str]:
        """Get recent follower user IDs."""
        try:
            r = self._session.get(
                "https://x.com/i/api/graphql/rRXFSG5vR6drKr5M37YOTw/Followers",
                params={
                    "variables": json.dumps({"userId": user_id, "count": count, "includePromotedContent": False}),
                    "features": json.dumps(FEATURES),
                },
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code != 200:
                return []
            data = r.json()
            ids = []
            for inst in data.get("data", {}).get("user", {}).get("result", {}).get("timeline", {}).get("timeline", {}).get("instructions", []):
                for entry in inst.get("entries", []):
                    result = entry.get("content", {}).get("itemContent", {}).get("user_results", {}).get("result", {})
                    uid = result.get("rest_id", "")
                    if uid:
                        ids.append(uid)
            return ids
        except Exception:
            return []

    def get_tweet_metrics(self, tweet_id: str) -> dict:
        """Get engagement metrics for a specific tweet."""
        try:
            r = self._session.get(
                f"https://x.com/i/api/graphql/oPRG-p-gbWDkVBBjCfnDsA/TweetDetail",
                params={
                    "variables": json.dumps({"focalTweetId": tweet_id, "with_rux_injections": False, "rankingMode": "Relevance", "includePromotedContent": False}),
                    "features": json.dumps(FEATURES),
                },
                headers=self._headers(),
            )
            self._refresh_ct0(r)
            if r.status_code != 200:
                return {}
            data = r.json()
            for inst in data.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", []):
                for entry in inst.get("entries", []):
                    result = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                    if result.get("__typename") == "TweetWithVisibilityResults":
                        result = result.get("tweet", result)
                    if result.get("rest_id") == tweet_id:
                        leg = result.get("legacy", {})
                        return {
                            "likes": leg.get("favorite_count", 0),
                            "retweets": leg.get("retweet_count", 0),
                            "replies": leg.get("reply_count", 0),
                            "views": result.get("views", {}).get("count", "0"),
                        }
            return {}
        except Exception:
            return {}

    def _parse_timeline(self, data: dict, path: list[str]) -> list[dict]:
        obj = data
        for key in path:
            obj = obj.get(key, {}) if isinstance(obj, dict) else {}
        if not isinstance(obj, list):
            return []
        tweets = []
        for inst in obj:
            for entry in inst.get("entries", []):
                result = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                if result.get("__typename") == "TweetWithVisibilityResults":
                    result = result.get("tweet", result)
                leg = result.get("legacy", {})
                core = result.get("core", {}).get("user_results", {}).get("result", {})
                text = leg.get("full_text", "")
                tid = result.get("rest_id", "")
                if text and tid:
                    ucore = core.get("core", {})
                    uleg = core.get("legacy", {})
                    tweets.append({
                        "id": tid,
                        "text": text,
                        "user": ucore.get("screen_name", "") or uleg.get("screen_name", ""),
                        "user_id": core.get("rest_id", ""),
                        "likes": leg.get("favorite_count", 0),
                        "replies": leg.get("reply_count", 0),
                        "retweets": leg.get("retweet_count", 0),
                        "followers": uleg.get("followers_count", 0),
                    })
        return tweets
