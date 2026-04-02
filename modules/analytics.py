"""Event tracking, metrics refresh, and a simple terminal dashboard."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from modules.config import ROOT
from modules import ui

DB_PATH = ROOT / "analytics.json"


def _default_db() -> dict:
    return {
        "youtube": [],
        "twitter": [],
        "lead_searches": [],
        "lead_campaigns": [],
    }


def _normalize(data: dict) -> dict:
    normalized = _default_db()
    normalized["youtube"] = data.get("youtube", [])
    normalized["twitter"] = data.get("twitter", [])
    normalized["lead_searches"] = data.get("lead_searches", data.get("leads", []))
    normalized["lead_campaigns"] = data.get("lead_campaigns", [])
    return normalized


def _load() -> dict:
    if DB_PATH.exists():
        return _normalize(json.loads(DB_PATH.read_text()))
    return _default_db()


def _save(data: dict):
    DB_PATH.write_text(json.dumps(_normalize(data), indent=2, default=str))


def _upsert(items: list[dict], key: str, payload: dict):
    for item in items:
        if item.get(key) == payload.get(key):
            item.update(payload)
            return
    items.append(payload)


def track_youtube(title: str, video_id: str, topic: str = ""):
    data = _load()
    _upsert(
        data["youtube"],
        "video_id",
        {
            "video_id": str(video_id),
            "title": title,
            "topic": topic,
            "date": datetime.now().isoformat(),
            "metrics": {},
        },
    )
    _save(data)


def track_tweet(tweet_id: str, text: str, tweet_type: str = "organic"):
    data = _load()
    _upsert(
        data["twitter"],
        "tweet_id",
        {
            "tweet_id": str(tweet_id),
            "text": text[:280],
            "type": tweet_type,
            "date": datetime.now().isoformat(),
            "metrics": {},
        },
    )
    _save(data)


def track_lead_search(query: str, location: str, total: int, with_email: int):
    data = _load()
    data["lead_searches"].append(
        {
            "query": query,
            "location": location,
            "total": total,
            "with_email": with_email,
            "date": datetime.now().isoformat(),
        }
    )
    _save(data)


def track_lead_campaign(campaign_id: str, source: str, sent: int, opened: int = 0, replied: int = 0):
    data = _load()
    _upsert(
        data["lead_campaigns"],
        "campaign_id",
        {
            "campaign_id": campaign_id,
            "source": source,
            "sent": sent,
            "opened": opened,
            "replied": replied,
            "date": datetime.now().isoformat(),
        },
    )
    _save(data)


def update_lead_campaign(campaign_id: str, opened: int | None = None, replied: int | None = None):
    data = _load()
    for campaign in data["lead_campaigns"]:
        if campaign.get("campaign_id") == campaign_id:
            if opened is not None:
                campaign["opened"] = opened
            if replied is not None:
                campaign["replied"] = replied
            campaign["updated_at"] = datetime.now().isoformat()
            _save(data)
            return campaign
    raise RuntimeError(f"Campaign not found: {campaign_id}")


def refresh_youtube_metrics():
    data = _load()
    video_ids = [item.get("video_id") for item in data["youtube"] if item.get("video_id")]
    if not video_ids:
        return

    try:
        from modules.youtube import _service

        service = _service()
        fetched = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            resp = service.videos().list(
                part="statistics,snippet",
                id=",".join(batch),
                maxResults=50,
            ).execute()
            for item in resp.get("items", []):
                fetched[str(item["id"])] = {
                    "views": int(item.get("statistics", {}).get("viewCount", 0)),
                    "likes": int(item.get("statistics", {}).get("likeCount", 0)),
                    "comments": int(item.get("statistics", {}).get("commentCount", 0)),
                    "title": item.get("snippet", {}).get("title", ""),
                    "last_sync": datetime.now().isoformat(),
                }

        for record in data["youtube"]:
            metrics = fetched.get(record.get("video_id"))
            if metrics:
                record["metrics"] = metrics
                if metrics.get("title"):
                    record["title"] = metrics["title"]

        _save(data)
    except Exception:
        pass


def refresh_twitter_metrics():
    data = _load()
    tweet_ids = [item.get("tweet_id") for item in data["twitter"] if item.get("tweet_id")]
    if not tweet_ids:
        return

    try:
        from modules.twitter import _client

        client = _client()
        fetched = {}
        for i in range(0, len(tweet_ids), 100):
            batch = tweet_ids[i:i + 100]
            resp = client.get_tweets(
                ids=batch,
                tweet_fields=["public_metrics", "organic_metrics", "non_public_metrics", "created_at"],
                user_auth=False,
            )
            for tweet in resp.data or []:
                public = getattr(tweet, "public_metrics", {}) or {}
                organic = getattr(tweet, "organic_metrics", {}) or {}
                fetched[str(tweet.id)] = {
                    "likes": int(public.get("like_count", 0)),
                    "replies": int(public.get("reply_count", 0)),
                    "retweets": int(public.get("retweet_count", 0)),
                    "quotes": int(public.get("quote_count", 0)),
                    "impressions": int(organic.get("impression_count", 0)),
                    "last_sync": datetime.now().isoformat(),
                }

        for record in data["twitter"]:
            metrics = fetched.get(record.get("tweet_id"))
            if metrics:
                record["metrics"] = metrics

        _save(data)
    except Exception:
        pass


def export_csv(output_path: str | None = None) -> str:
    data = _load()
    output = Path(output_path) if output_path else (ROOT / "analytics_export.csv")

    rows = []
    for item in data["youtube"]:
        metrics = item.get("metrics", {})
        rows.append(
            {
                "type": "youtube",
                "id": item.get("video_id", ""),
                "name": item.get("title", ""),
                "date": item.get("date", ""),
                "metric_1": metrics.get("views", 0),
                "metric_2": metrics.get("likes", 0),
                "metric_3": metrics.get("comments", 0),
                "extra": item.get("topic", ""),
            }
        )
    for item in data["twitter"]:
        metrics = item.get("metrics", {})
        rows.append(
            {
                "type": "twitter",
                "id": item.get("tweet_id", ""),
                "name": item.get("text", ""),
                "date": item.get("date", ""),
                "metric_1": metrics.get("impressions", 0),
                "metric_2": metrics.get("likes", 0) + metrics.get("retweets", 0) + metrics.get("replies", 0),
                "metric_3": metrics.get("quotes", 0),
                "extra": item.get("type", ""),
            }
        )
    for item in data["lead_campaigns"]:
        rows.append(
            {
                "type": "lead_campaign",
                "id": item.get("campaign_id", ""),
                "name": item.get("source", ""),
                "date": item.get("date", ""),
                "metric_1": item.get("sent", 0),
                "metric_2": item.get("opened", 0),
                "metric_3": item.get("replied", 0),
                "extra": "",
            }
        )

    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["type", "id", "name", "date", "metric_1", "metric_2", "metric_3", "extra"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return str(output)


def dashboard():
    refresh_youtube_metrics()
    refresh_twitter_metrics()

    data = _load()
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    def recent(items):
        return [item for item in items if item.get("date", "") >= week_ago.isoformat()]

    yt_week = recent(data["youtube"])
    tw_week = recent(data["twitter"])
    search_week = recent(data["lead_searches"])
    campaign_week = recent(data["lead_campaigns"])

    yt_views = sum(item.get("metrics", {}).get("views", 0) for item in yt_week)
    yt_likes = sum(item.get("metrics", {}).get("likes", 0) for item in yt_week)
    tw_impressions = sum(item.get("metrics", {}).get("impressions", 0) for item in tw_week)
    tw_engagement = sum(
        item.get("metrics", {}).get("likes", 0)
        + item.get("metrics", {}).get("retweets", 0)
        + item.get("metrics", {}).get("replies", 0)
        + item.get("metrics", {}).get("quotes", 0)
        for item in tw_week
    )
    leads_found = sum(item.get("total", 0) for item in search_week)
    leads_with_email = sum(item.get("with_email", 0) for item in search_week)
    lead_sent = sum(item.get("sent", 0) for item in campaign_week)
    lead_opened = sum(item.get("opened", 0) for item in campaign_week)
    lead_replied = sum(item.get("replied", 0) for item in campaign_week)

    open_rate = (lead_opened / lead_sent * 100) if lead_sent else 0
    reply_rate = (lead_replied / lead_sent * 100) if lead_sent else 0

    rows = [
        ("YouTube Shorts", "Ready", f"{len(data['youtube'])} tracked"),
        ("YouTube views (7d)", "Ready", str(yt_views)),
        ("YouTube likes (7d)", "Ready", str(yt_likes)),
        ("Tweets tracked", "Ready", str(len(data["twitter"]))),
        ("Tweet impressions (7d)", "Ready", str(tw_impressions)),
        ("Tweet engagement (7d)", "Ready", str(tw_engagement)),
        ("Lead searches", "Ready", str(len(data["lead_searches"]))),
        ("Leads found (7d)", "Ready", f"{leads_found} ({leads_with_email} with email)"),
        ("Campaigns tracked", "Ready", str(len(data["lead_campaigns"]))),
        ("Lead open rate", "Ready", f"{open_rate:.1f}%"),
        ("Lead reply rate", "Ready", f"{reply_rate:.1f}%"),
    ]
    ui.info("Analytics dashboard")
    ui.status_table(rows)

    if yt_week:
        ui.info("Top recent Shorts")
        top_videos = sorted(yt_week, key=lambda item: item.get("metrics", {}).get("views", 0), reverse=True)[:5]
        for item in top_videos:
            ui.info(f"{item.get('title', 'Untitled')} -> {item.get('metrics', {}).get('views', 0)} views")

    if tw_week:
        ui.info("Recent tweets")
        top_tweets = sorted(
            tw_week,
            key=lambda item: (
                item.get("metrics", {}).get("likes", 0)
                + item.get("metrics", {}).get("retweets", 0)
                + item.get("metrics", {}).get("replies", 0)
            ),
            reverse=True,
        )[:5]
        for item in top_tweets:
            metrics = item.get("metrics", {})
            ui.info(
                f"{item.get('type', 'tweet').upper()} -> {metrics.get('impressions', 0)} impressions, "
                f"{metrics.get('likes', 0)} likes"
            )

    if campaign_week:
        ui.info("Lead campaigns")
        for item in campaign_week[-5:]:
            sent = item.get("sent", 0)
            opened = item.get("opened", 0)
            replied = item.get("replied", 0)
            ui.info(
                f"{item.get('campaign_id')} -> sent {sent}, opened {opened}, replied {replied}"
            )
