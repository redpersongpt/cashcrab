#!/usr/bin/env python3
"""Local tweet proxy — runs on your Mac, VDS calls it to post tweets.

Your Mac has residential IP → no 226 error.
VDS calls this HTTP endpoint to post tweets through your IP.

Usage:
    python3 scripts/tweet_proxy.py

VDS agent calls: POST http://YOUR_MAC_IP:9876/tweet
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

PORT = 9876
COOKIES_PATH = Path(__file__).parent.parent / "tokens" / "twitter_cookies.json"

FEATURES = {"communities_web_enable_tweet_community_results_fetch":True,"c9s_tweet_anatomy_moderator_badge_enabled":True,"responsive_web_edit_tweet_api_enabled":True,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,"view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,"responsive_web_twitter_article_tweet_consumption_enabled":True,"tweet_awards_web_tipping_enabled":False,"creator_subscriptions_quote_tweet_preview_enabled":False,"longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":True,"articles_preview_enabled":True,"rweb_video_timestamps_enabled":True,"rweb_tipjar_consumption_enabled":True,"responsive_web_graphql_exclude_directive_enabled":True,"verified_phone_label_enabled":False,"freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":False,"responsive_web_graphql_timeline_navigation_enabled":True,"responsive_web_enhance_cards_enabled":False}


class TweetProxy(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/tweet":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        text = body.get("text", "")
        reply_to = body.get("reply_to")

        if not text:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{"error":"no text"}')
            return

        try:
            from curl_cffi.requests import Session

            cookies = json.loads(COOKIES_PATH.read_text())
            s = Session(impersonate="chrome131")
            s.cookies.set("ct0", cookies["ct0"], domain=".x.com")
            s.cookies.set("auth_token", cookies["auth_token"], domain=".x.com")

            variables = {
                "tweet_text": text,
                "dark_request": False,
                "media": {"media_entities": [], "possibly_sensitive": False},
                "semantic_annotation_ids": [],
            }
            if reply_to:
                variables["reply"] = {"in_reply_to_tweet_id": reply_to, "exclude_reply_user_ids": []}

            r = s.post("https://x.com/i/api/graphql/IceLmZOK75drD8mMwcJoUA/CreateTweet",
                json={"variables": variables, "features": FEATURES, "queryId": "IceLmZOK75drD8mMwcJoUA"},
                headers={
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                    "x-csrf-token": cookies["ct0"],
                    "x-twitter-auth-type": "OAuth2Session",
                    "content-type": "application/json",
                    "referer": "https://x.com/",
                    "origin": "https://x.com/",
                })

            data = r.json()
            if "errors" in data:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"error": data["errors"][0].get("message", "")[:100]}).encode())
            else:
                tid = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {}).get("rest_id", "")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"tweet_id": tid}).encode())
                print(f"POSTED: {tid} — {text[:50]}")

        except Exception as exc:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)[:100]}).encode())

    def log_message(self, *args):
        pass  # silent


if __name__ == "__main__":
    print(f"Tweet proxy running on port {PORT}")
    print(f"VDS should call: POST http://YOUR_MAC_IP:{PORT}/tweet")
    HTTPServer(("0.0.0.0", PORT), TweetProxy).serve_forever()
