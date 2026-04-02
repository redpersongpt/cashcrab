"""Simple event tracking + terminal dashboard."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from modules.config import ROOT
from modules import ui

DB_PATH = ROOT / "analytics.json"


def _load() -> dict:
    if DB_PATH.exists():
        return json.loads(DB_PATH.read_text())
    return {"youtube": [], "twitter": [], "leads": []}


def _save(data: dict):
    DB_PATH.write_text(json.dumps(data, indent=2, default=str))


def track_youtube(title: str, video_id: str, topic: str = ""):
    data = _load()
    data["youtube"].append({
        "title": title, "video_id": video_id, "topic": topic,
        "date": datetime.now().isoformat(),
    })
    _save(data)


def track_tweet(tweet_id: str, text: str, tweet_type: str = "organic"):
    data = _load()
    data["twitter"].append({
        "tweet_id": tweet_id, "text": text[:200], "type": tweet_type,
        "date": datetime.now().isoformat(),
    })
    _save(data)


def track_leads(query: str, location: str, total: int, with_email: int):
    data = _load()
    data["leads"].append({
        "query": query, "location": location,
        "total": total, "with_email": with_email,
        "date": datetime.now().isoformat(),
    })
    _save(data)


def dashboard():
    data = _load()
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    yt = data.get("youtube", [])
    tw = data.get("twitter", [])
    ld = data.get("leads", [])

    def recent(items):
        return [i for i in items if i.get("date", "") >= week_ago.isoformat()]

    yt_week = recent(yt)
    tw_week = recent(tw)
    ld_week = recent(ld)

    tw_aff = [t for t in tw_week if t.get("type") == "affiliate"]
    tw_org = [t for t in tw_week if t.get("type") != "affiliate"]

    total_leads = sum(l.get("total", 0) for l in ld_week)
    email_leads = sum(l.get("with_email", 0) for l in ld_week)

    rows = [
        ("Shorts this week", "Ready", str(len(yt_week))),
        ("Tweets this week", "Ready", f"{len(tw_week)} total"),
        ("Affiliate tweets", "Ready", str(len(tw_aff))),
        ("Helpful tweets", "Ready", str(len(tw_org))),
        ("Leads this week", "Ready", str(total_leads)),
        ("Leads with email", "Ready", str(email_leads)),
        ("All-time Shorts", "Ready", str(len(yt))),
        ("All-time tweets", "Ready", str(len(tw))),
        ("Lead searches", "Ready", str(len(ld))),
    ]
    ui.info("Analytics")
    ui.status_table(rows)

    if yt_week:
        ui.info("Recent uploads")
        for v in yt_week[-5:]:
            ui.info(f"{v['date'][:10]}  {v['title']}")

    if tw_week:
        ui.info("Recent tweets")
        for t in tw_week[-5:]:
            tag = "[AFF]" if t.get("type") == "affiliate" else "[ORG]"
            ui.info(f"{t['date'][:10]}  {tag} {t['text'][:60]}...")
