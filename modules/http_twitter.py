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
}


class HttpTwitter:
    def __init__(self):
        cookies = json.loads(COOKIES_PATH.read_text())
        self._ct0 = cookies["ct0"]
        self._at = cookies["auth_token"]
        self._session = Session(impersonate="chrome120")
        self._session.cookies.set("ct0", self._ct0, domain=".x.com")
        self._session.cookies.set("auth_token", self._at, domain=".x.com")

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
        r = self._session.post(
            f"https://x.com/i/api/graphql/{QID['FavoriteTweet']}/FavoriteTweet",
            json={"variables": {"tweet_id": tweet_id}, "queryId": QID["FavoriteTweet"]},
            headers=self._headers(),
        )
        return r.status_code == 200 and "Done" in r.text

    def create_tweet(self, text: str, reply_to: str | None = None) -> str | None:
        """Post a tweet or reply. Returns tweet ID or None."""
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
        if r.status_code != 200:
            return None

        data = r.json()
        if "errors" in data:
            err = data["errors"][0].get("message", "")
            raise RuntimeError(f"CreateTweet: {err[:150]}")

        return (
            data.get("data", {})
            .get("create_tweet", {})
            .get("tweet_results", {})
            .get("result", {})
            .get("rest_id", "")
        ) or None

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
                        "likes": leg.get("favorite_count", 0),
                        "replies": leg.get("reply_count", 0),
                        "retweets": leg.get("retweet_count", 0),
                        "followers": uleg.get("followers_count", 0),
                    })
        return tweets
