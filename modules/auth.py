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

    print("API Key Setup (Enter to skip):\n")
    for svc, label in services.items():
        current = keys.get(svc, "")
        masked = f"...{current[-6:]}" if len(current) > 6 else "(not set)"
        val = input(f"  {label} [{masked}]: ").strip()
        if val:
            keys[svc] = val

    KEYS_FILE.write_text(json.dumps(keys, indent=2))
    print(f"\nSaved to {KEYS_FILE}")


# ── YouTube OAuth2 ───────────────────────────────────

def youtube_login():
    cfg = section("youtube")
    secrets_file = cfg.get("client_secrets_file", "client_secrets.json")
    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, YT_SCOPES)
    creds = flow.run_local_server(port=0)
    YT_TOKEN.write_text(creds.to_json())
    print(f"  YouTube authorized.")
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

    print(f"  Opening browser for Twitter auth...")
    print(f"  Manual URL: {auth_url}\n")
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
    print(f"  Twitter authorized.")
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
        print("  Refresh failed, re-authenticating...")
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
    print("=== OAuth ===\n")

    if YT_TOKEN.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(YT_TOKEN), YT_SCOPES)
            print(f"  YouTube:  {'valid' if creds.valid else 'expired (auto-refresh)'}")
        except Exception:
            print("  YouTube:  corrupt (run: auth youtube)")
    else:
        print("  YouTube:  not linked")

    if TW_TOKEN.exists():
        try:
            s = json.loads(TW_TOKEN.read_text())
            rem = int((s.get("expires_at", 0) - time.time()) / 60)
            print(f"  Twitter:  {'valid (' + str(rem) + 'm left)' if rem > 0 else 'expired (auto-refresh)'}")
        except Exception:
            print("  Twitter:  corrupt (run: auth twitter)")
    else:
        print("  Twitter:  not linked")

    print("\n=== API Keys ===\n")
    if KEYS_FILE.exists():
        for svc, val in json.loads(KEYS_FILE.read_text()).items():
            masked = f"...{val[-6:]}" if len(val) > 6 else "(empty)"
            print(f"  {svc:16s} {masked}")
    else:
        print("  None stored (run: auth keys)")

    print("\n=== LLM ===\n")
    cfg = section("llm")
    provider = cfg.get("provider", "g4f")
    model = cfg.get("model", "gpt-4o-mini")
    print(f"  Provider: {provider} (uses subscription, no API key)")
    print(f"  Model:    {model}")


def revoke(service: str):
    targets = {"youtube": YT_TOKEN, "twitter": TW_TOKEN}
    path = targets.get(service)
    if not path:
        print(f"Unknown: {service}")
        return
    if path.exists():
        path.unlink()
        print(f"  {service} tokens removed.")
    else:
        print(f"  {service}: nothing to remove.")
