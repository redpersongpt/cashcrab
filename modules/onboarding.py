"""AI-guided onboarding flows for first-time CashCrab users."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from rich import box
from rich.panel import Panel

from modules import ui
from modules.config import CONFIG_PATH, ROOT, load as load_config, save as save_config


GOALS = {
    "shorts": "Make and publish short-form videos",
    "social": "Post on X, TikTok, and Instagram",
    "leads": "Find leads and send outreach",
    "autopilot": "Run the full money loop",
}


SERVICES = {
    "youtube": {
        "label": "YouTube",
        "consumer_signup": "https://accounts.google.com/signup",
        "developer_setup": "https://console.cloud.google.com/apis/credentials",
        "owner_ready": lambda cfg: ((ROOT / cfg.get("youtube", {}).get("client_secrets_file", "client_secrets.json")).exists()
                                     or Path(cfg.get("youtube", {}).get("client_secrets_file", "client_secrets.json")).exists()),
        "connect": lambda: __import__("modules.auth", fromlist=["youtube_login"]).youtube_login(),
        "why": "Needed for Shorts uploads.",
    },
    "twitter": {
        "label": "Twitter / X",
        "consumer_signup": "https://x.com/i/flow/signup",
        "developer_setup": "https://developer.x.com/en/portal/dashboard",
        "owner_ready": lambda cfg: bool(cfg.get("twitter", {}).get("client_id")),
        "connect": lambda: __import__("modules.auth", fromlist=["twitter_login"]).twitter_login(),
        "why": "Needed for organic and affiliate posts.",
    },
    "tiktok": {
        "label": "TikTok",
        "consumer_signup": "https://www.tiktok.com/signup",
        "developer_setup": "https://developers.tiktok.com/",
        "owner_ready": lambda cfg: bool(cfg.get("tiktok", {}).get("client_key")),
        "connect": lambda: __import__("modules.tiktok", fromlist=["login"]).login(),
        "why": "Needed for TikTok cross-posting.",
    },
    "instagram": {
        "label": "Instagram",
        "consumer_signup": "https://www.instagram.com/accounts/emailsignup/",
        "developer_setup": "https://developers.facebook.com/apps/",
        "owner_ready": lambda cfg: bool(cfg.get("instagram", {}).get("app_id")),
        "connect": lambda: __import__("modules.instagram", fromlist=["login"]).login(),
        "why": "Needed for Instagram Reels publishing.",
    },
    "pexels": {
        "label": "Pexels",
        "consumer_signup": "https://www.pexels.com/join-consumer/",
        "developer_setup": "https://www.pexels.com/api/new/",
        "owner_ready": lambda cfg: bool(_token_value("pexels")),
        "connect": lambda: __import__("modules.auth", fromlist=["setup_api_keys"]).setup_api_keys(),
        "why": "Needed for stock footage in video generation.",
    },
    "google_places": {
        "label": "Google Places",
        "consumer_signup": "https://accounts.google.com/signup",
        "developer_setup": "https://developers.google.com/maps/documentation/places/web-service/get-api-key",
        "owner_ready": lambda cfg: bool(_token_value("google_places")),
        "connect": lambda: __import__("modules.auth", fromlist=["setup_api_keys"]).setup_api_keys(),
        "why": "Needed for lead finder.",
    },
}


def _token_value(name: str) -> str:
    tokens = CONFIG_PATH.parent / "tokens" / "api_keys.json"
    if not tokens.exists():
        return ""
    try:
        data = json.loads(tokens.read_text())
    except Exception:
        return ""
    return str(data.get(name, "") or "")


def _app_section() -> dict:
    cfg = load_config()
    section = cfg.get("app", {})
    if not isinstance(section, dict):
        section = {}
    return section


def _save_app_section(updates: dict):
    cfg = load_config()
    app = cfg.get("app", {})
    if not isinstance(app, dict):
        app = {}
    app.update(updates)
    cfg["app"] = app
    save_config(cfg)


def needs_onboarding() -> bool:
    return not bool(_app_section().get("onboarding_done"))


def _selected_services(goal: str) -> list[str]:
    if goal == "shorts":
        return ["youtube", "pexels"]
    if goal == "social":
        return ["twitter", "tiktok", "instagram"]
    if goal == "leads":
        return ["google_places"]
    return ["youtube", "twitter", "tiktok", "instagram", "pexels", "google_places"]


def _ai_setup_copy(goal: str, services: list[str]) -> str:
    labels = ", ".join(SERVICES[name]["label"] for name in services)
    fallback = (
        f"Goal: {GOALS[goal]}\n"
        f"Priority setup: {labels}\n"
        "Fastest path: connect Qwen first, then only the channels you actually plan to use today."
    )

    try:
        from modules import llm

        return llm.generate(
            (
                "Write a tight setup coach message for a first-time CashCrab user.\n"
                f"Goal: {GOALS[goal]}\n"
                f"Services: {labels}\n"
                "Rules: max 90 words, direct, useful, not cheesy."
            ),
            system="You are the setup brain of CashCrab. Keep the plan short and practical.",
        )
    except Exception:
        return fallback


def _show_plan(goal: str, services: list[str]):
    copy = _ai_setup_copy(goal, services)
    ui.console.print()
    ui.console.print(
        Panel(
            copy,
            title="[money]Qwen Setup Plan[/money]",
            border_style="hint",
            box=box.ROUNDED,
        )
    )


def _maybe_open(url: str, label: str):
    if ui.confirm(f"Open the browser page for {label}?", default=True):
        webbrowser.open(url)
        ui.success(f"Opened {label}.")


def _connect_qwen_first():
    from modules import llm
    from modules.auth import qwen_login

    status, _ = llm.qwen_auth_status()
    if status == "Connected":
        ui.success("Qwen is already connected.")
        return

    if ui.confirm("Connect Qwen now? This is the recommended brain.", default=True):
        qwen_login()


def _service_ready(service_name: str, cfg: dict) -> bool:
    try:
        from modules import backend

        if backend.enabled() and backend.service_ready(service_name):
            return True
    except Exception:
        pass

    try:
        return bool(SERVICES[service_name]["owner_ready"](cfg))
    except Exception:
        return False


def _guide_service(service_name: str, cfg: dict):
    service = SERVICES[service_name]
    ui.divider()
    ui.info(f"{service['label']}: {service['why']}")

    if ui.confirm(f"Do you already have a {service['label']} account?", default=True) is False:
        _maybe_open(service["consumer_signup"], f"{service['label']} sign-up")
        ui.info(f"Create the account, then come back. CashCrab will keep going after that.")

    if not _service_ready(service_name, cfg):
        ui.warn(f"{service['label']} still needs app-owner credentials or API access on this machine.")
        _maybe_open(service["developer_setup"], f"{service['label']} developer setup")
        return

    if ui.confirm(f"Connect {service['label']} now?", default=True):
        service["connect"]()


def run_ai_wizard():
    ui.clear()
    ui.banner()

    choice = ui.menu(
        "AI onboarding wizard",
        [
            GOALS["shorts"],
            GOALS["social"],
            GOALS["leads"],
            GOALS["autopilot"],
        ],
        back_label="Skip wizard for now",
    )

    if choice == 0:
        return

    goal = list(GOALS.keys())[choice - 1]
    services = _selected_services(goal)
    cfg = load_config()

    try:
        from modules import backend

        if backend.enabled():
            backend.sync_owner_config()
            cfg = load_config()
    except Exception:
        pass

    ui.info("Qwen will set the pace. You only answer the needed questions.")
    _show_plan(goal, services)
    _connect_qwen_first()

    for service_name in services:
        _guide_service(service_name, cfg)

    autopilot = ui.confirm("Enable autopilot-style setup hints in future sessions?", default=True)
    _save_app_section(
        {
            "onboarding_done": True,
            "goal": goal,
            "autopilot_mode": autopilot,
            "selected_services": services,
        }
    )
    ui.success("Wizard complete. CashCrab saved your setup path.")
