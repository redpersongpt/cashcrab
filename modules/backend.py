"""Owner backend client for zero-friction onboarding."""

from __future__ import annotations

import json
from pathlib import Path

import requests

from modules.config import CONFIG_PATH, ROOT, load as load_config, save as save_config


def _cfg() -> dict:
    cfg = load_config().get("backend", {})
    return cfg if isinstance(cfg, dict) else {}


def enabled() -> bool:
    cfg = _cfg()
    return bool(cfg.get("enabled") and cfg.get("base_url"))


def _base_url() -> str:
    cfg = _cfg()
    base = str(cfg.get("base_url", "")).strip().rstrip("/")
    if not base:
        raise RuntimeError("Owner backend is not configured.")
    return base


def _headers() -> dict:
    cfg = _cfg()
    token = str(cfg.get("client_token", "")).strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(path: str, timeout: int = 20) -> dict:
    resp = requests.get(f"{_base_url()}{path}", headers=_headers(), timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict, timeout: int = 30) -> dict:
    resp = requests.post(f"{_base_url()}{path}", headers=_headers(), json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def health() -> dict:
    return _get("/v1/health")


def bootstrap() -> dict:
    return _get("/v1/bootstrap")


def sync_owner_config() -> dict:
    payload = bootstrap()
    cfg = load_config()

    backend_payload = payload.get("backend", {})
    if backend_payload:
        cfg["backend"] = {**cfg.get("backend", {}), **backend_payload}

    if payload.get("youtube", {}).get("client_secrets_json"):
        secrets_path = ROOT / "client_secrets.json"
        secrets_path.write_text(
            json.dumps(payload["youtube"]["client_secrets_json"], indent=2),
            encoding="utf-8",
        )
        cfg.setdefault("youtube", {})["client_secrets_file"] = str(secrets_path)

    twitter = payload.get("twitter", {})
    if twitter:
        cfg.setdefault("twitter", {}).update(
            {
                "client_id": twitter.get("client_id", cfg.get("twitter", {}).get("client_id", "")),
                "client_secret": twitter.get("client_secret", cfg.get("twitter", {}).get("client_secret", "")),
            }
        )

    tiktok = payload.get("tiktok", {})
    if tiktok:
        cfg.setdefault("tiktok", {}).update(
            {
                "client_key": tiktok.get("client_key", cfg.get("tiktok", {}).get("client_key", "")),
                "client_secret": tiktok.get("client_secret", cfg.get("tiktok", {}).get("client_secret", "")),
            }
        )

    instagram = payload.get("instagram", {})
    if instagram:
        cfg.setdefault("instagram", {}).update(
            {
                "app_id": instagram.get("app_id", cfg.get("instagram", {}).get("app_id", "")),
                "app_secret": instagram.get("app_secret", cfg.get("instagram", {}).get("app_secret", "")),
                "facebook_page_id": instagram.get(
                    "facebook_page_id",
                    cfg.get("instagram", {}).get("facebook_page_id", ""),
                ),
                "public_base_url": instagram.get(
                    "public_base_url",
                    cfg.get("instagram", {}).get("public_base_url", ""),
                ),
            }
        )

    save_config(cfg)
    return payload


def capabilities() -> dict:
    try:
        return bootstrap().get("capabilities", {})
    except Exception:
        return {}


def service_ready(service_name: str) -> bool:
    caps = capabilities()
    service = caps.get(service_name, {})
    return bool(service.get("ready"))


def pexels_search_videos(query: str, count: int = 5) -> list[dict]:
    data = _post("/v1/proxy/pexels/videos/search", {"query": query, "count": count})
    return data.get("videos", [])


def google_places_search(query: str, location: str, radius: int) -> list[dict]:
    data = _post(
        "/v1/proxy/google-places/search",
        {"query": query, "location": location, "radius": radius},
        timeout=60,
    )
    return data.get("results", [])


def exchange_tiktok_code(code: str, redirect_uri: str) -> dict:
    return _post("/v1/oauth/tiktok/exchange", {"code": code, "redirect_uri": redirect_uri})


def refresh_tiktok_token(refresh_token: str) -> dict:
    return _post("/v1/oauth/tiktok/refresh", {"refresh_token": refresh_token})


def exchange_instagram_code(code: str, redirect_uri: str) -> dict:
    return _post("/v1/oauth/instagram/exchange", {"code": code, "redirect_uri": redirect_uri}, timeout=60)


def status() -> tuple[str, str]:
    if not enabled():
        return "Disabled", "Set backend.base_url and backend.client_token to use owner-side setup."
    try:
        payload = health()
        label = payload.get("status", "ok")
        return "Connected", label
    except Exception as exc:
        return "Unavailable", str(exc)
