"""HTTP-based Twitter client for VDS (no Playwright needed for reads).

Uses cookie auth + GraphQL API for:
- HomeTimeline (read tweets)
- FavoriteTweet (like)
- Viewer (get own profile)
- Notifications

CreateTweet and Reply require Playwright (anti-bot error 226 via HTTP).
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from modules.config import ROOT

COOKIES_PATH = ROOT / "tokens" / "twitter_cookies.json"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

FEATURES = {
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

# Query IDs (update if Twitter changes them)
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
        self._http = httpx.Client(timeout=15, headers={
            "authorization": f"Bearer {BEARER}",
            "x-csrf-token": self._ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "content-type": "application/json",
            "cookie": f"ct0={self._ct0}; auth_token={self._at}",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "referer": "https://x.com/",
        })

    def get_me(self) -> dict:
        r = self._http.get(
            f"https://x.com/i/api/graphql/{QID['Viewer']}/Viewer",
            params={
                "variables": json.dumps({"withCommunitiesMemberships": False}),
                "features": json.dumps(FEATURES),
            },
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
        r = self._http.get(
            f"https://x.com/i/api/graphql/{QID['HomeTimeline']}/HomeTimeline",
            params={
                "variables": json.dumps({"count": count, "includePromotedContent": False, "latestControlAvailable": True}),
                "features": json.dumps(FEATURES),
            },
        )
        if r.status_code != 200:
            return []
        return self._parse_timeline(r.json(), ["data", "home", "home_timeline_urt", "instructions"])

    def like(self, tweet_id: str) -> bool:
        r = self._http.post(
            f"https://x.com/i/api/graphql/{QID['FavoriteTweet']}/FavoriteTweet",
            json={"variables": {"tweet_id": tweet_id}, "queryId": QID["FavoriteTweet"]},
        )
        return r.status_code == 200 and "Done" in r.text

    def notifications(self) -> list[dict]:
        """Get recent notifications with tweet data."""
        r = self._http.get("https://x.com/i/api/2/notifications/all.json")
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
