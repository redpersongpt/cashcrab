import json
import time
import webbrowser
import hashlib
import base64
import secrets
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from modules.config import section, ROOT
from modules import ui

TOKENS_DIR = ROOT / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)

YT_TOKEN = TOKENS_DIR / "youtube.json"
TW_TOKEN = TOKENS_DIR / "twitter.json"
KEYS_FILE = TOKENS_DIR / "api_keys.json"

YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TW_SCOPES = ["tweet.read", "tweet.write", "users.read", "offline.access"]
TW_AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TW_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

_callback_result = {}


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        _callback_result["code"] = qs.get("code", [None])[0]
        _callback_result["error"] = qs.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        ok = _callback_result.get("code")
        body = "<h2>Authorized. Close this tab.</h2>" if ok else "<h2>Failed.</h2>"
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


# ── API Key Storage (Pexels, Google Places) ──────────

def store_api_key(service: str, key: str):
    keys = json.loads(KEYS_FILE.read_text()) if KEYS_FILE.exists() else {}
    keys[service] = key
    KEYS_FILE.write_text(json.dumps(keys, indent=2))


def get_api_key(service: str) -> str | None:
    if KEYS_FILE.exists():
        return json.loads(KEYS_FILE.read_text()).get(service)
    return None


def setup_api_keys():
    services = {
        "pexels": "Pexels (free stock video)",
        "google_places": "Google Places (lead finder)",
    }
    keys = json.loads(KEYS_FILE.read_text()) if KEYS_FILE.exists() else {}

    ui.info("API keys")
    ui.warn("Press Enter to keep the current value.")
    for svc, label in services.items():
        current = keys.get(svc, "")
        masked = f"...{current[-6:]}" if len(current) > 6 else "(not set)"
        val = ui.ask(f"{label} [{masked}]")
        if val:
            keys[svc] = val

    KEYS_FILE.write_text(json.dumps(keys, indent=2))
    ui.success(f"Saved keys to {KEYS_FILE}")


# ── YouTube OAuth2 ───────────────────────────────────

def youtube_login():
    cfg = section("youtube")
    secrets_file = cfg.get("client_secrets_file", "client_secrets.json")
    ui.info("Opening your browser for YouTube login...")
    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, YT_SCOPES)
    creds = flow.run_local_server(port=0)
    YT_TOKEN.write_text(creds.to_json())
    ui.success("YouTube is connected.")
    return creds


def youtube_credentials():
    creds = None
    if YT_TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(YT_TOKEN), YT_SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        YT_TOKEN.write_text(creds.to_json())
        return creds
    return youtube_login()


# ── Twitter OAuth 2.0 PKCE ───────────────────────────

def twitter_login():
    cfg = section("twitter")
    client_id = cfg["client_id"]
    client_secret = cfg.get("client_secret", "")
    port = cfg.get("oauth_port", 8189)
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    verifier, challenge = _pkce_pair()

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(TW_SCOPES),
        "state": secrets.token_urlsafe(32),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = TW_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    ui.info("Opening your browser for Twitter / X login...")
    ui.info(f"If the browser does not open, use this URL:\n{auth_url}")
    webbrowser.open(auth_url)

    _callback_result.clear()
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120
    server.handle_request()
    server.server_close()

    code = _callback_result.get("code")
    if not code:
        raise RuntimeError(f"Twitter auth failed: {_callback_result.get('error', 'timeout')}")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    auth = (client_id, client_secret) if client_secret else None
    if not client_secret:
        data["client_id"] = client_id

    resp = requests.post(TW_TOKEN_URL, data=data, auth=auth, timeout=15)
    resp.raise_for_status()
    tokens = resp.json()

    store = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "expires_at": time.time() + tokens.get("expires_in", 7200),
    }
    TW_TOKEN.write_text(json.dumps(store, indent=2))
    ui.success("Twitter / X is connected.")
    return store


def _twitter_refresh(store: dict) -> dict:
    cfg = section("twitter")
    client_id = cfg["client_id"]
    client_secret = cfg.get("client_secret", "")

    if not store.get("refresh_token"):
        return twitter_login()

    data = {"grant_type": "refresh_token", "refresh_token": store["refresh_token"]}
    auth = (client_id, client_secret) if client_secret else None
    if not client_secret:
        data["client_id"] = client_id

    resp = requests.post(TW_TOKEN_URL, data=data, auth=auth, timeout=15)
    if resp.status_code != 200:
        ui.warn("Saved Twitter token expired. Reconnecting...")
        return twitter_login()

    tokens = resp.json()
    store = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", store["refresh_token"]),
        "expires_at": time.time() + tokens.get("expires_in", 7200),
    }
    TW_TOKEN.write_text(json.dumps(store, indent=2))
    return store


def twitter_access_token() -> str:
    if not TW_TOKEN.exists():
        store = twitter_login()
    else:
        store = json.loads(TW_TOKEN.read_text())
    if time.time() > store.get("expires_at", 0) - 60:
        store = _twitter_refresh(store)
    return store["access_token"]


# ── Status ───────────────────────────────────────────

def status():
    rows = []

    if YT_TOKEN.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(YT_TOKEN), YT_SCOPES)
            status_text = "Connected" if creds.valid else "Expired (auto-refresh)"
            rows.append(("YouTube", status_text, str(YT_TOKEN)))
        except Exception:
            rows.append(("YouTube", "Corrupt token", "Run cashcrab -> Setup -> Connect YouTube"))
    else:
        rows.append(("YouTube", "Not connected", "Run cashcrab -> Setup -> Connect YouTube"))

    if TW_TOKEN.exists():
        try:
            s = json.loads(TW_TOKEN.read_text())
            rem = int((s.get("expires_at", 0) - time.time()) / 60)
            status_text = f"Connected ({rem}m left)" if rem > 0 else "Expired (auto-refresh)"
            rows.append(("Twitter / X", status_text, str(TW_TOKEN)))
        except Exception:
            rows.append(("Twitter / X", "Corrupt token", "Run cashcrab -> Setup -> Connect Twitter / X"))
    else:
        rows.append(("Twitter / X", "Not connected", "Run cashcrab -> Setup -> Connect Twitter / X"))

    keys = json.loads(KEYS_FILE.read_text()) if KEYS_FILE.exists() else {}
    pexels_value = keys.get("pexels", "")
    google_value = keys.get("google_places", "")
    rows.append(("Pexels key", "Set" if pexels_value else "Missing", f"...{pexels_value[-6:]}" if pexels_value else "Needed for stock footage"))
    rows.append(("Google Places key", "Set" if google_value else "Missing", f"...{google_value[-6:]}" if google_value else "Needed for lead finder"))

    cfg = section("llm")
    provider = cfg.get("provider", "g4f")
    model = cfg.get("model", "gpt-4o-mini")
    rows.append(("LLM", "Ready", f"{provider} / {model}"))

    ui.info("Setup status")
    ui.status_table(rows)


def revoke(service: str):
    targets = {"youtube": YT_TOKEN, "twitter": TW_TOKEN}
    path = targets.get(service)
    if not path:
        ui.fail(f"Unknown service: {service}")
        return
    if path.exists():
        path.unlink()
        ui.success(f"Removed saved login for {service}.")
    else:
        ui.warn(f"No saved login found for {service}.")
