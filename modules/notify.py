"""Discord/Slack webhook notifications."""

import requests

from modules.config import section


def _webhooks() -> dict:
    try:
        cfg = section("notifications")
    except SystemExit:
        return {}
    return {
        "discord": cfg.get("discord_webhook", ""),
        "slack": cfg.get("slack_webhook", ""),
    }


def send(message: str, title: str = "CashCrab"):
    hooks = _webhooks()

    discord_url = hooks.get("discord")
    if discord_url:
        try:
            requests.post(discord_url, json={"content": f"**{title}**\n{message}"}, timeout=5)
        except Exception:
            pass

    slack_url = hooks.get("slack")
    if slack_url:
        try:
            requests.post(slack_url, json={"text": f"*{title}*\n{message}"}, timeout=5)
        except Exception:
            pass


def youtube_uploaded(title: str, video_id: str):
    send(f"Uploaded: {title}\nhttps://youtube.com/shorts/{video_id}", title="YouTube Short")


def tweet_posted(tweet_id: str, text: str):
    preview = text[:100] + ("..." if len(text) > 100 else "")
    send(f"Posted: {preview}\nhttps://x.com/i/status/{tweet_id}", title="Tweet")


def leads_found(query: str, location: str, count: int, with_email: int):
    send(f"Found {count} businesses ({with_email} with email)\n{query} in {location}", title="Leads")


def error(action: str, err: str):
    send(f"Failed: {action}\n{err}", title="Error")
