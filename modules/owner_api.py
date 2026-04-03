"""Owner-side backend/proxy service for CashCrab."""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _client_token_valid(handler: BaseHTTPRequestHandler) -> bool:
    expected = _env("CASHCRAB_CLIENT_TOKEN")
    if not expected:
        return True
    header = handler.headers.get("Authorization", "")
    return header == f"Bearer {expected}"


def _youtube_client_secrets() -> dict | None:
    path = _env("CASHCRAB_YOUTUBE_CLIENT_SECRETS_FILE")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _bootstrap_payload() -> dict:
    return {
        "backend": {
            "enabled": True,
            "use_owner_proxy": True,
            "use_owner_oauth_exchange": True,
        },
        "youtube": {
            "client_secrets_json": _youtube_client_secrets(),
        },
        "twitter": {
            "client_id": _env("CASHCRAB_TWITTER_CLIENT_ID"),
            "client_secret": _env("CASHCRAB_TWITTER_CLIENT_SECRET"),
        },
        "tiktok": {
            "client_key": _env("CASHCRAB_TIKTOK_CLIENT_KEY"),
            "client_secret": _env("CASHCRAB_TIKTOK_CLIENT_SECRET"),
        },
        "instagram": {
            "app_id": _env("CASHCRAB_INSTAGRAM_APP_ID"),
            "app_secret": _env("CASHCRAB_INSTAGRAM_APP_SECRET"),
            "facebook_page_id": _env("CASHCRAB_FACEBOOK_PAGE_ID"),
            "public_base_url": _env("CASHCRAB_PUBLIC_BASE_URL"),
        },
        "capabilities": {
            "youtube": {"ready": _youtube_client_secrets() is not None},
            "twitter": {"ready": bool(_env("CASHCRAB_TWITTER_CLIENT_ID"))},
            "tiktok": {"ready": bool(_env("CASHCRAB_TIKTOK_CLIENT_KEY") and _env("CASHCRAB_TIKTOK_CLIENT_SECRET"))},
            "instagram": {"ready": bool(_env("CASHCRAB_INSTAGRAM_APP_ID") and _env("CASHCRAB_INSTAGRAM_APP_SECRET"))},
            "pexels": {"ready": bool(_env("CASHCRAB_PEXELS_API_KEY"))},
            "google_places": {"ready": bool(_env("CASHCRAB_GOOGLE_PLACES_API_KEY"))},
        },
    }


def status_payload() -> dict:
    return _bootstrap_payload()


def _choose_instagram_account(access_token: str) -> dict:
    graph_version = _env("CASHCRAB_INSTAGRAM_GRAPH_VERSION", "v23.0")
    page_id = _env("CASHCRAB_FACEBOOK_PAGE_ID")

    def graph_url(path: str) -> str:
        return f"https://graph.facebook.com/{graph_version}/{path.lstrip('/')}"

    if page_id:
        resp = requests.get(
            graph_url(page_id),
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username}",
                "access_token": access_token,
            },
            timeout=20,
        )
        resp.raise_for_status()
        page = resp.json()
        ig = page.get("instagram_business_account")
        if not ig:
            raise RuntimeError("Configured Facebook page is not linked to an Instagram business account.")
        return {
            "facebook_page_id": page["id"],
            "facebook_page_name": page.get("name", ""),
            "page_access_token": page.get("access_token", access_token),
            "instagram_account_id": ig["id"],
            "instagram_username": ig.get("username", ""),
        }

    resp = requests.get(
        graph_url("me/accounts"),
        params={
            "fields": "id,name,access_token,instagram_business_account{id,username}",
            "access_token": access_token,
        },
        timeout=20,
    )
    resp.raise_for_status()
    for page in resp.json().get("data", []):
        ig = page.get("instagram_business_account")
        if ig:
            return {
                "facebook_page_id": page["id"],
                "facebook_page_name": page.get("name", ""),
                "page_access_token": page.get("access_token", access_token),
                "instagram_account_id": ig["id"],
                "instagram_username": ig.get("username", ""),
            }

    raise RuntimeError("No Facebook page with a linked Instagram business account was found.")


class _OwnerHandler(BaseHTTPRequestHandler):
    server_version = "CashCrabOwner/0.1"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/v1/health":
            _json_response(self, 200, {"status": "ok", "time": int(time.time())})
            return

        if not _client_token_valid(self):
            _json_response(self, 401, {"error": "Unauthorized"})
            return

        if parsed.path == "/v1/bootstrap":
            _json_response(self, 200, _bootstrap_payload())
            return

        _json_response(self, 404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if not _client_token_valid(self):
            _json_response(self, 401, {"error": "Unauthorized"})
            return

        try:
            payload = _read_json(self)
            if parsed.path == "/v1/proxy/pexels/videos/search":
                self._pexels_search(payload)
                return
            if parsed.path == "/v1/proxy/google-places/search":
                self._google_places_search(payload)
                return
            if parsed.path == "/v1/oauth/tiktok/exchange":
                self._tiktok_exchange(payload)
                return
            if parsed.path == "/v1/oauth/tiktok/refresh":
                self._tiktok_refresh(payload)
                return
            if parsed.path == "/v1/oauth/instagram/exchange":
                self._instagram_exchange(payload)
                return
            _json_response(self, 404, {"error": "Not found"})
        except requests.HTTPError as exc:
            detail = exc.response.text if exc.response is not None else str(exc)
            _json_response(self, 502, {"error": detail})
        except Exception as exc:
            _json_response(self, 500, {"error": str(exc)})

    def log_message(self, *_args):
        if _bool_env("CASHCRAB_OWNER_VERBOSE", False):
            super().log_message(*_args)

    def _pexels_search(self, payload: dict):
        api_key = _env("CASHCRAB_PEXELS_API_KEY")
        if not api_key:
            raise RuntimeError("CASHCRAB_PEXELS_API_KEY is not configured.")
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={
                "query": payload.get("query", ""),
                "per_page": int(payload.get("count", 5)),
                "orientation": "portrait",
                "size": "medium",
            },
            timeout=20,
        )
        resp.raise_for_status()
        videos = []
        for item in resp.json().get("videos", []):
            files = item.get("video_files", [])
            hd = [f for f in files if f.get("height", 0) >= 1080 and f.get("file_type") == "video/mp4"]
            if not files:
                continue
            selected = hd[0] if hd else files[0]
            videos.append(
                {
                    "id": item.get("id"),
                    "duration": item.get("duration"),
                    "url": selected.get("link", ""),
                    "width": selected.get("width"),
                    "height": selected.get("height"),
                }
            )
        _json_response(self, 200, {"videos": videos})

    def _google_places_search(self, payload: dict):
        api_key = _env("CASHCRAB_GOOGLE_PLACES_API_KEY")
        if not api_key:
            raise RuntimeError("CASHCRAB_GOOGLE_PLACES_API_KEY is not configured.")

        query = payload.get("query", "")
        location = payload.get("location", "")
        radius = int(payload.get("radius", 5000))

        geocode_resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": location, "key": api_key},
            timeout=15,
        )
        geocode_resp.raise_for_status()
        results = geocode_resp.json().get("results", [])
        if not results:
            _json_response(self, 200, {"results": []})
            return

        loc = results[0]["geometry"]["location"]
        lat, lng = loc["lat"], loc["lng"]
        places_resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={
                "query": f"{query} near {location}",
                "location": f"{lat},{lng}",
                "radius": radius,
                "key": api_key,
            },
            timeout=20,
        )
        places_resp.raise_for_status()

        businesses = []
        for place in places_resp.json().get("results", []):
            place_id = place["place_id"]
            detail = requests.get(
                "https://maps.googleapis.com/maps/api/place/details/json",
                params={
                    "place_id": place_id,
                    "fields": "name,formatted_phone_number,website,formatted_address,rating,user_ratings_total",
                    "key": api_key,
                },
                timeout=20,
            ).json().get("result", {})
            businesses.append(
                {
                    "name": detail.get("name", place.get("name", "")),
                    "address": detail.get("formatted_address", ""),
                    "phone": detail.get("formatted_phone_number", ""),
                    "website": detail.get("website", ""),
                    "rating": detail.get("rating", ""),
                    "reviews": detail.get("user_ratings_total", ""),
                    "email": "",
                }
            )

        _json_response(self, 200, {"results": businesses})

    def _tiktok_exchange(self, payload: dict):
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            json={
                "client_key": _env("CASHCRAB_TIKTOK_CLIENT_KEY"),
                "client_secret": _env("CASHCRAB_TIKTOK_CLIENT_SECRET"),
                "code": payload.get("code", ""),
                "grant_type": "authorization_code",
                "redirect_uri": payload.get("redirect_uri", ""),
            },
            timeout=20,
        )
        resp.raise_for_status()
        _json_response(self, 200, resp.json())

    def _tiktok_refresh(self, payload: dict):
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            json={
                "client_key": _env("CASHCRAB_TIKTOK_CLIENT_KEY"),
                "client_secret": _env("CASHCRAB_TIKTOK_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": payload.get("refresh_token", ""),
            },
            timeout=20,
        )
        resp.raise_for_status()
        _json_response(self, 200, resp.json())

    def _instagram_exchange(self, payload: dict):
        graph_version = _env("CASHCRAB_INSTAGRAM_GRAPH_VERSION", "v23.0")
        app_id = _env("CASHCRAB_INSTAGRAM_APP_ID")
        app_secret = _env("CASHCRAB_INSTAGRAM_APP_SECRET")

        def graph_url(path: str) -> str:
            return f"https://graph.facebook.com/{graph_version}/{path.lstrip('/')}"

        short = requests.get(
            graph_url("oauth/access_token"),
            params={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": payload.get("redirect_uri", ""),
                "code": payload.get("code", ""),
            },
            timeout=20,
        )
        short.raise_for_status()
        short_token = short.json()["access_token"]

        long_lived = requests.get(
            graph_url("oauth/access_token"),
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
            timeout=20,
        )
        long_lived.raise_for_status()
        token_data = long_lived.json()
        account = _choose_instagram_account(token_data["access_token"])

        _json_response(
            self,
            200,
            {
                "access_token": token_data["access_token"],
                "expires_in": token_data.get("expires_in", 60 * 24 * 60 * 60),
                **account,
            },
        )


def run_server(host: str = "127.0.0.1", port: int = 8787):
    server = ThreadingHTTPServer((host, port), _OwnerHandler)
    print(f"CashCrab owner API listening on http://{host}:{port}")
    server.serve_forever()
