"""TikTok Content Posting API integration."""

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

TT_TOKEN = TOKENS_DIR / "tiktok.json"
TT_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TT_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TT_SCOPES = "user.info.basic,video.publish,video.upload"


def connection_status() -> str:
    if not TT_TOKEN.exists():
        return "Not connected"
    try:
        store = json.loads(TT_TOKEN.read_text())
        rem = int((store.get("expires_at", 0) - time.time()) / 60)
        return f"Connected ({rem}m left)" if rem > 0 else "Expired (auto-refresh)"
    except Exception:
        return "Corrupt token"


def login():
    cfg = section("tiktok")
    client_key = cfg["client_key"]
    client_secret = cfg["client_secret"]
    port = cfg.get("oauth_port", 8190)
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    state = secrets.token_urlsafe(32)
    params = {
        "client_key": client_key,
        "scope": TT_SCOPES,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
    }
    url = TT_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    ui.info("Opening your browser for TikTok login...")
    ui.info(f"If the browser does not open, use this URL:\n{url}")
    webbrowser.open(url)

    _callback_result.clear()
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 120
    server.handle_request()
    server.server_close()

    code = _callback_result.get("code")
    if not code:
        raise RuntimeError(f"TikTok auth failed: {_callback_result.get('error', 'timeout')}")

    resp = requests.post(
        TT_TOKEN_URL,
        json={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=15,
    )
    resp.raise_for_status()
    tokens = resp.json()

    store = {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "open_id": tokens.get("open_id", ""),
        "expires_at": time.time() + tokens.get("expires_in", 86400),
    }
    TT_TOKEN.write_text(json.dumps(store, indent=2))
    ui.success("TikTok is connected.")
    return store


def _get_token() -> str:
    if not TT_TOKEN.exists():
        return login()["access_token"]

    store = json.loads(TT_TOKEN.read_text())
    if time.time() > store.get("expires_at", 0) - 60:
        cfg = section("tiktok")
        resp = requests.post(
            TT_TOKEN_URL,
            json={
                "client_key": cfg["client_key"],
                "client_secret": cfg["client_secret"],
                "grant_type": "refresh_token",
                "refresh_token": store["refresh_token"],
            },
            timeout=15,
        )
        if resp.status_code != 200:
            ui.warn("Saved TikTok token expired. Reconnecting...")
            return login()["access_token"]
        tokens = resp.json()
        store["access_token"] = tokens["access_token"]
        store["refresh_token"] = tokens.get("refresh_token", store["refresh_token"])
        store["expires_at"] = time.time() + tokens.get("expires_in", 86400)
        TT_TOKEN.write_text(json.dumps(store, indent=2))

    return store["access_token"]


def upload(file_path: str, title: str, privacy: str | None = None) -> dict:
    cfg = section("tiktok")
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    file_size = Path(file_path).stat().st_size
    privacy = privacy or cfg.get("privacy_level", "SELF_ONLY")

    init_resp = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {
                "title": title[:150],
                "privacy_level": privacy,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        },
        timeout=15,
    )
    init_resp.raise_for_status()
    init_data = init_resp.json().get("data", {})
    upload_url = init_data.get("upload_url", "")
    publish_id = init_data.get("publish_id", "")

    if not upload_url:
        raise RuntimeError(f"TikTok init failed: {init_resp.text}")

    ui.info(f"Uploading to TikTok: {Path(file_path).name}")
    with open(file_path, "rb") as f:
        up_resp = requests.put(
            upload_url,
            headers={
                "Content-Range": f"bytes 0-{file_size-1}/{file_size}",
                "Content-Type": "video/mp4",
            },
            data=f,
            timeout=120,
        )
    up_resp.raise_for_status()

    ui.success(f"TikTok upload submitted: {publish_id}")
    return {"publish_id": publish_id}


def upload_latest(folder: str | None = None, title: str | None = None) -> dict:
    cfg = section("youtube")
    target_dir = Path(folder or cfg.get("shorts_folder", "./shorts"))
    videos = sorted(target_dir.glob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not videos:
        raise RuntimeError(f"No videos found in {target_dir}")
    latest = videos[0]
    final_title = title or latest.stem.replace("_", " ").replace("-", " ").title()
    return upload(str(latest), final_title)
