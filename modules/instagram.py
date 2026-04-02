"""Instagram Reels publishing via Meta Graph API."""

from __future__ import annotations

import json
import time
import webbrowser
import secrets
from pathlib import Path
from http.server import HTTPServer

import requests

from modules.config import section
from modules.auth import _CallbackHandler, _callback_result, TOKENS_DIR
from modules import ui

IG_TOKEN = TOKENS_DIR / "instagram.json"
IG_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
    "business_management",
]


def _cfg() -> dict:
    return section("instagram")


def _version() -> str:
    return _cfg().get("graph_version", "v23.0")


def _graph_url(path: str) -> str:
    return f"https://graph.facebook.com/{_version()}/{path.lstrip('/')}"


def _dialog_url() -> str:
    return f"https://www.facebook.com/{_version()}/dialog/oauth"


def connection_status() -> str:
    if not IG_TOKEN.exists():
        return "Not connected"
    try:
        store = json.loads(IG_TOKEN.read_text())
        rem = int((store.get("expires_at", 0) - time.time()) / 60)
        username = store.get("instagram_username", "")
        suffix = f" as @{username}" if username else ""
        return f"Connected{suffix}" if rem > 0 else "Expired (reconnect)"
    except Exception:
        return "Corrupt token"


def _choose_instagram_account(access_token: str) -> dict:
    cfg = _cfg()
    page_id = cfg.get("facebook_page_id", "")

    if page_id:
        resp = requests.get(
            _graph_url(page_id),
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username}",
                "access_token": access_token,
            },
            timeout=15,
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
        _graph_url("me/accounts"),
        params={
            "fields": "id,name,access_token,instagram_business_account{id,username}",
            "access_token": access_token,
        },
        timeout=15,
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


def login() -> dict:
    cfg = _cfg()
    app_id = cfg["app_id"]
    app_secret = cfg["app_secret"]
    port = cfg.get("oauth_port", 8191)
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(IG_SCOPES),
        "state": secrets.token_urlsafe(32),
    }
    auth_url = _dialog_url() + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    ui.info("Opening your browser for Instagram / Meta login...")
    ui.info(f"If the browser does not open, use this URL:\n{auth_url}")
    webbrowser.open(auth_url)

    _callback_result.clear()
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120
    server.handle_request()
    server.server_close()

    code = _callback_result.get("code")
    if not code:
        raise RuntimeError(f"Instagram auth failed: {_callback_result.get('error', 'timeout')}")

    short = requests.get(
        _graph_url("oauth/access_token"),
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    short.raise_for_status()
    short_token = short.json()["access_token"]

    long_lived = requests.get(
        _graph_url("oauth/access_token"),
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    long_lived.raise_for_status()
    token_data = long_lived.json()

    account = _choose_instagram_account(token_data["access_token"])
    store = {
        "access_token": token_data["access_token"],
        "expires_at": time.time() + token_data.get("expires_in", 60 * 24 * 60 * 60),
        **account,
    }
    IG_TOKEN.write_text(json.dumps(store, indent=2))
    ui.success(f"Instagram is connected as @{store.get('instagram_username', 'unknown')}.")
    return store


def _store() -> dict:
    if not IG_TOKEN.exists():
        return login()

    store = json.loads(IG_TOKEN.read_text())
    if time.time() > store.get("expires_at", 0) - 3600:
        ui.warn("Saved Instagram token is expiring soon. Reconnecting...")
        return login()
    return store


def _public_video_url(file_path: str, public_url: str | None = None) -> str:
    if public_url:
        return public_url

    cfg = _cfg()
    base = cfg.get("public_base_url", "").rstrip("/")
    if base:
        return f"{base}/{Path(file_path).name}"

    raise RuntimeError(
        "Instagram publishing needs a public video URL. Provide --public-url or set instagram.public_base_url."
    )


def publish_from_url(video_url: str, caption: str) -> dict:
    store = _store()
    ig_user_id = store["instagram_account_id"]
    access_token = store.get("page_access_token", store["access_token"])

    create_resp = requests.post(
        _graph_url(f"{ig_user_id}/media"),
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],
            "share_to_feed": "true",
            "access_token": access_token,
        },
        timeout=30,
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    ui.info("Waiting for Instagram to process the Reel...")
    for _ in range(30):
        status_resp = requests.get(
            _graph_url(creation_id),
            params={"fields": "status_code,status,error_message", "access_token": access_token},
            timeout=15,
        )
        status_resp.raise_for_status()
        payload = status_resp.json()
        status_code = payload.get("status_code", "")

        if status_code in {"FINISHED", "PUBLISHED"}:
            break
        if status_code in {"ERROR", "EXPIRED"}:
            raise RuntimeError(payload.get("error_message", f"Instagram processing failed: {status_code}"))
        time.sleep(5)
    else:
        raise RuntimeError("Instagram processing timed out.")

    publish_resp = requests.post(
        _graph_url(f"{ig_user_id}/media_publish"),
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]

    permalink = ""
    details_resp = requests.get(
        _graph_url(media_id),
        params={"fields": "permalink", "access_token": access_token},
        timeout=15,
    )
    if details_resp.ok:
        permalink = details_resp.json().get("permalink", "")

    if permalink:
        ui.success(f"Instagram Reel published: {permalink}")
    else:
        ui.success(f"Instagram Reel published: {media_id}")
    return {"id": media_id, "permalink": permalink}


def upload(file_path: str, caption: str, public_url: str | None = None) -> dict:
    video_url = _public_video_url(file_path, public_url)
    ui.info(f"Publishing to Instagram using public video URL:\n{video_url}")
    return publish_from_url(video_url, caption)


def upload_latest(caption: str, folder: str | None = None, public_url: str | None = None) -> dict:
    cfg = section("youtube")
    target_dir = Path(folder or cfg.get("shorts_folder", "./shorts"))
    videos = sorted(target_dir.glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not videos:
        raise RuntimeError(f"No videos found in {target_dir}")
    latest = videos[0]
    return upload(str(latest), caption=caption, public_url=public_url)
