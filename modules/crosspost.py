"""Optional cross-posting helpers for generated Shorts."""

from __future__ import annotations

from modules.config import optional_section
from modules import ui


def publish_short(video_path: str, title: str, description: str = "", *,
                  tiktok_enabled: bool | None = None,
                  instagram_enabled: bool | None = None,
                  instagram_public_url: str | None = None) -> dict:
    cfg = optional_section("crosspost", {})
    tiktok_enabled = cfg.get("tiktok", False) if tiktok_enabled is None else tiktok_enabled
    instagram_enabled = cfg.get("instagram", False) if instagram_enabled is None else instagram_enabled

    results = {}

    if tiktok_enabled:
        try:
            from modules import tiktok

            ui.info("Cross-posting to TikTok...")
            results["tiktok"] = tiktok.upload(video_path, title)
        except Exception as exc:
            ui.fail(f"TikTok cross-post failed: {exc}")
            results["tiktok"] = {"error": str(exc)}

    if instagram_enabled:
        try:
            from modules import instagram

            ui.info("Cross-posting to Instagram Reels...")
            caption = description or title
            results["instagram"] = instagram.upload(video_path, caption=caption, public_url=instagram_public_url)
        except Exception as exc:
            ui.fail(f"Instagram cross-post failed: {exc}")
            results["instagram"] = {"error": str(exc)}

    return results
