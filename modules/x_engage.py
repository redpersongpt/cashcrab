"""X/Twitter engagement automation - voice analysis, auto-engage, thought leader agent.

Adapted from XActions best features for CashCrab.
Uses tweepy v2 API + Qwen LLM for intelligent engagement.
"""

from __future__ import annotations

import json
import math
import random
import time
from datetime import datetime
from pathlib import Path

import tweepy

from modules.config import ROOT, section, optional_section
from modules import llm, ui
from modules.auth import twitter_access_token

VOICE_PATH = ROOT / "voice_profile.json"
ENGAGE_LOG_PATH = ROOT / "engage_log.json"

# ---------------------------------------------------------------------------
# Tweepy client helpers
# ---------------------------------------------------------------------------

def _client() -> tweepy.Client:
    token = twitter_access_token()
    return tweepy.Client(access_token=token)


def _bearer_client() -> tweepy.Client | None:
    """App-only client using bearer token for read-heavy ops (if configured)."""
    cfg = section("twitter")
    bearer = cfg.get("bearer_token", "")
    if not bearer:
        return None
    return tweepy.Client(bearer_token=bearer)


def _read_client() -> tweepy.Client:
    """Best available client for reading. Bearer > user token."""
    bc = _bearer_client()
    return bc if bc else _client()


# ---------------------------------------------------------------------------
# Voice Analyzer - build a writing style profile from your tweets
# ---------------------------------------------------------------------------

def analyze_voice(count: int = 50) -> dict:
    """Fetch your recent tweets and build a voice profile with Qwen."""
    client = _read_client()

    me = client.get_me(user_fields=["username", "description", "public_metrics"])
    if not me or not me.data:
        raise RuntimeError("Could not fetch your X profile. Check your auth token.")

    user_id = me.data.id
    username = me.data.username
    bio = me.data.description or ""
    ui.info(f"Analyzing @{username}'s voice ({count} tweets)...")

    tweets_resp = client.get_users_tweets(
        user_id,
        max_results=min(count, 100),
        tweet_fields=["public_metrics", "created_at"],
        exclude=["retweets", "replies"],
    )

    if not tweets_resp or not tweets_resp.data:
        raise RuntimeError("No tweets found. Post some tweets first.")

    tweets = tweets_resp.data
    texts = [t.text for t in tweets]
    sample = "\n---\n".join(texts[:30])

    prompt = (
        f"Analyze this Twitter user's writing voice from their tweets.\n"
        f"Username: @{username}\n"
        f"Bio: {bio}\n\n"
        f"Their tweets:\n{sample}\n\n"
        "Return a JSON object with:\n"
        '- "tone": primary tone (e.g. "casual-sharp", "professional", "witty-provocative")\n'
        '- "style_notes": 3-5 specific style observations\n'
        '- "vocabulary": 10 words/phrases they use often\n'
        '- "content_pillars": 3-5 topics they post about most\n'
        '- "avg_length": estimated average tweet length\n'
        '- "emoji_usage": "none", "minimal", "moderate", "heavy"\n'
        '- "hashtag_style": "none", "light", "moderate"\n'
        '- "voice_prompt": a system prompt that would make an LLM write EXACTLY like this person\n'
        "Return ONLY valid JSON."
    )

    profile = llm.generate_json(prompt, system="You are a writing style analyst. Return only valid JSON.")

    profile["username"] = username
    profile["tweet_count_analyzed"] = len(texts)
    profile["analyzed_at"] = datetime.now().isoformat(timespec="seconds")
    profile["bio"] = bio

    VOICE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    ui.success(f"Voice profile saved: {VOICE_PATH}")
    ui.info(f"  Tone: {profile.get('tone', 'unknown')}")
    ui.info(f"  Pillars: {', '.join(profile.get('content_pillars', []))}")
    return profile


def load_voice() -> dict | None:
    """Load saved voice profile."""
    if VOICE_PATH.exists():
        return json.loads(VOICE_PATH.read_text(encoding="utf-8"))
    return None


def generate_in_voice(topic: str, voice: dict | None = None) -> str:
    """Generate a tweet matching your voice profile."""
    voice = voice or load_voice()
    if not voice:
        raise RuntimeError("No voice profile found. Run 'Analyze my voice' first.")

    voice_prompt = voice.get("voice_prompt", "Write like a sharp, engaging Twitter user.")
    tone = voice.get("tone", "casual")
    pillars = ", ".join(voice.get("content_pillars", []))
    avg_len = voice.get("avg_length", 150)

    prompt = (
        f"Write a tweet about: {topic}\n"
        f"Match this exact voice/tone: {tone}\n"
        f"Their usual topics: {pillars}\n"
        f"Target length: ~{avg_len} chars\n"
        "Rules:\n"
        "- Sound EXACTLY like the person, not like an AI\n"
        "- Under 270 characters\n"
        "- No 'As someone who...' or AI patterns\n"
        "- Match their emoji and hashtag habits"
    )

    from modules.twitter import _normalize_text
    return _normalize_text(llm.generate(prompt, system=voice_prompt))


# ---------------------------------------------------------------------------
# Engagement Scoring - score tweets for engagement value
# ---------------------------------------------------------------------------

def _score_tweet_for_engage(tweet, user_metrics: dict | None = None) -> int:
    """Score a tweet 0-100 for engagement priority (adapted from XActions)."""
    score = 50
    metrics = getattr(tweet, "public_metrics", None) or {}

    likes = metrics.get("like_count", 0)
    replies = metrics.get("reply_count", 0)
    retweets = metrics.get("retweet_count", 0)

    # Sweet spot: some engagement but not viral (more likely to notice you)
    total = likes + replies + retweets
    if 5 <= total <= 100:
        score += 15
    elif total < 5:
        score += 5
    elif total > 500:
        score -= 10

    # Smaller accounts are more likely to engage back
    if user_metrics:
        followers = user_metrics.get("followers_count", 0)
        if 500 <= followers <= 10000:
            score += 15
        elif 10000 < followers <= 50000:
            score += 10
        elif followers > 100000:
            score -= 5
        elif followers < 100:
            score -= 5

        # Good follower/following ratio = real account
        following = user_metrics.get("following_count", 1)
        ratio = followers / max(following, 1)
        if ratio > 1.5:
            score += 5

    # Recency bonus
    created = getattr(tweet, "created_at", None)
    if created:
        hours_old = (datetime.now(created.tzinfo) - created).total_seconds() / 3600
        if hours_old < 1:
            score += 15
        elif hours_old < 6:
            score += 10
        elif hours_old < 24:
            score += 5
        elif hours_old > 72:
            score -= 10

    return max(0, min(100, score))


# ---------------------------------------------------------------------------
# Engagement log
# ---------------------------------------------------------------------------

def _load_engage_log() -> list:
    if ENGAGE_LOG_PATH.exists():
        return json.loads(ENGAGE_LOG_PATH.read_text(encoding="utf-8"))
    return []


def _save_engage_log(log: list):
    ENGAGE_LOG_PATH.write_text(json.dumps(log[-500:], indent=2), encoding="utf-8")


def _already_engaged(tweet_id: str) -> bool:
    log = _load_engage_log()
    return any(e.get("tweet_id") == tweet_id for e in log)


def _log_engagement(tweet_id: str, action: str, text: str = ""):
    log = _load_engage_log()
    log.append({
        "tweet_id": tweet_id,
        "action": action,
        "text": text[:200],
        "at": datetime.now().isoformat(timespec="seconds"),
    })
    _save_engage_log(log)


# ---------------------------------------------------------------------------
# Search & Engage
# ---------------------------------------------------------------------------

def search_and_engage(
    keywords: list[str],
    max_likes: int = 10,
    max_replies: int = 3,
    reply_threshold: int = 70,
    like_threshold: int = 50,
) -> dict:
    """Search for tweets by keywords, score them, like/reply intelligently."""
    client = _client()
    read_client = _read_client()

    stats = {"searched": 0, "liked": 0, "replied": 0, "skipped": 0}
    voice = load_voice()

    for keyword in keywords:
        ui.info(f"Searching: {keyword}")

        try:
            results = read_client.search_recent_tweets(
                query=f"{keyword} -is:retweet lang:en",
                max_results=20,
                tweet_fields=["public_metrics", "created_at", "author_id"],
                expansions=["author_id"],
                user_fields=["public_metrics"],
            )
        except Exception as exc:
            ui.warn(f"Search failed for '{keyword}': {exc}")
            continue

        if not results or not results.data:
            ui.warn(f"No results for '{keyword}'")
            continue

        # Build author metrics lookup
        author_metrics = {}
        if results.includes and "users" in results.includes:
            for u in results.includes["users"]:
                author_metrics[u.id] = getattr(u, "public_metrics", None) or {}

        for tweet in results.data:
            stats["searched"] += 1
            tid = str(tweet.id)

            if _already_engaged(tid):
                stats["skipped"] += 1
                continue

            user_m = author_metrics.get(tweet.author_id)
            score = _score_tweet_for_engage(tweet, user_m)

            # Like
            if score >= like_threshold and stats["liked"] < max_likes:
                try:
                    client.like(tweet.id)
                    _log_engagement(tid, "like", tweet.text)
                    stats["liked"] += 1
                    ui.info(f"  Liked (score {score}): {tweet.text[:80]}...")
                    time.sleep(random.uniform(3, 8))
                except Exception as exc:
                    ui.warn(f"  Like failed: {exc}")

            # Reply with AI
            if score >= reply_threshold and stats["replied"] < max_replies:
                try:
                    reply_text = _generate_reply(tweet.text, voice)
                    client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet.id)
                    _log_engagement(tid, "reply", reply_text)
                    stats["replied"] += 1
                    ui.info(f"  Replied (score {score}): {reply_text[:80]}")
                    time.sleep(random.uniform(10, 25))
                except Exception as exc:
                    ui.warn(f"  Reply failed: {exc}")

        # Delay between keyword searches
        time.sleep(random.uniform(5, 15))

    ui.success(
        f"Engagement done: {stats['searched']} searched, "
        f"{stats['liked']} liked, {stats['replied']} replied, "
        f"{stats['skipped']} skipped"
    )
    return stats


def _generate_reply(tweet_text: str, voice: dict | None = None) -> str:
    """Generate a contextual reply using Qwen."""
    voice_prompt = "You are a sharp, helpful Twitter user who adds value in replies."
    if voice:
        voice_prompt = voice.get("voice_prompt", voice_prompt)

    prompt = (
        f"Write a short reply to this tweet:\n\n\"{tweet_text}\"\n\n"
        "Rules:\n"
        "- Under 200 characters\n"
        "- Add genuine value: insight, question, or agreement with nuance\n"
        "- NEVER be generic ('Great point!', 'So true!')\n"
        "- Sound human, not AI\n"
        "- No hashtags in replies\n"
        "- No emojis unless it fits naturally"
    )
    from modules.twitter import _normalize_text
    return _normalize_text(llm.generate(prompt, system=voice_prompt), limit=280)


# ---------------------------------------------------------------------------
# Thought Leader Agent - autonomous engagement loop
# ---------------------------------------------------------------------------

ACTIVITY_TYPES = [
    "search_engage",    # Search keywords and engage
    "post_original",    # Post original content
    "browse_and_like",  # Browse feed and like good stuff
]


def thought_leader_cycle(
    keywords: list[str] | None = None,
    duration_minutes: int = 30,
    max_posts: int = 2,
    max_likes: int = 15,
    max_replies: int = 5,
) -> dict:
    """Run one cycle of the thought leader agent.

    Rotates through activity types with randomized timing and anti-detection pauses.
    """
    cfg = optional_section("twitter") or {}
    engage_cfg = cfg.get("engage", {})

    if not keywords:
        # Pull keywords from products + engage config
        keywords = engage_cfg.get("keywords", [])
        for product in cfg.get("products", []):
            keywords.extend(product.get("keywords", []))
    keywords = list(set(keywords)) or ["tech", "AI", "productivity"]

    voice = load_voice()
    stats = {"posts": 0, "likes": 0, "replies": 0, "cycles": 0}
    start = time.time()
    end_time = start + (duration_minutes * 60)

    ui.info(f"Thought Leader agent started ({duration_minutes} min, keywords: {', '.join(keywords[:5])})")

    while time.time() < end_time:
        activity = random.choice(ACTIVITY_TYPES)
        stats["cycles"] += 1

        try:
            if activity == "search_engage":
                # Pick 1-2 random keywords per cycle
                cycle_keywords = random.sample(keywords, min(2, len(keywords)))
                result = search_and_engage(
                    keywords=cycle_keywords,
                    max_likes=min(5, max_likes - stats["likes"]),
                    max_replies=min(2, max_replies - stats["replies"]),
                )
                stats["likes"] += result.get("liked", 0)
                stats["replies"] += result.get("replied", 0)

            elif activity == "post_original" and stats["posts"] < max_posts:
                topic = random.choice(keywords)
                if voice:
                    text = generate_in_voice(topic, voice)
                else:
                    from modules.twitter import generate_organic_draft
                    text = generate_organic_draft(topic=topic)

                from modules.twitter import score_content, post_tweet
                score = score_content(text)
                if score["score"] >= 50:
                    post_tweet(text)
                    stats["posts"] += 1
                    ui.info(f"  Posted (score {score['score']}): {text[:80]}...")
                else:
                    ui.warn(f"  Draft rejected (score {score['score']}), regenerating next cycle")

            elif activity == "browse_and_like":
                _browse_and_like(max_count=min(3, max_likes - stats["likes"]))
                stats["likes"] += min(3, max_likes - stats["likes"])

        except Exception as exc:
            ui.warn(f"  Activity '{activity}' failed: {exc}")

        # Check caps
        if stats["likes"] >= max_likes and stats["replies"] >= max_replies and stats["posts"] >= max_posts:
            ui.info("All caps reached, ending early.")
            break

        # Anti-detection: random pause 30s-3min between activities
        pause = random.uniform(30, 180)
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        actual_pause = min(pause, remaining)
        ui.info(f"  Pausing {int(actual_pause)}s before next activity...")
        time.sleep(actual_pause)

    elapsed = int((time.time() - start) / 60)
    ui.success(
        f"Thought Leader cycle done ({elapsed} min): "
        f"{stats['posts']} posts, {stats['likes']} likes, "
        f"{stats['replies']} replies in {stats['cycles']} activities"
    )
    return stats


def _browse_and_like(max_count: int = 3):
    """Browse the home timeline and like relevant tweets."""
    client = _client()
    read_client = _read_client()

    try:
        me = read_client.get_me()
        if not me or not me.data:
            return

        # Get home timeline (reverse chronological)
        timeline = client.get_home_timeline(
            max_results=20,
            tweet_fields=["public_metrics", "created_at"],
        )
    except Exception as exc:
        ui.warn(f"  Browse failed: {exc}")
        return

    if not timeline or not timeline.data:
        return

    liked = 0
    for tweet in timeline.data:
        if liked >= max_count:
            break
        tid = str(tweet.id)
        if _already_engaged(tid):
            continue

        score = _score_tweet_for_engage(tweet)
        if score >= 55:
            try:
                client.like(tweet.id)
                _log_engagement(tid, "like", tweet.text)
                liked += 1
                time.sleep(random.uniform(2, 6))
            except Exception:
                pass

    if liked:
        ui.info(f"  Browsed feed, liked {liked} tweets")


# ---------------------------------------------------------------------------
# Find engagement targets (accounts to follow/engage with)
# ---------------------------------------------------------------------------

def find_targets(
    keywords: list[str],
    min_followers: int = 500,
    max_followers: int = 50000,
    limit: int = 20,
) -> list[dict]:
    """Find accounts worth engaging with based on keywords and follower range."""
    read_client = _read_client()
    targets = []

    for keyword in keywords:
        try:
            results = read_client.search_recent_tweets(
                query=f"{keyword} -is:retweet lang:en",
                max_results=50,
                tweet_fields=["public_metrics", "author_id"],
                expansions=["author_id"],
                user_fields=["public_metrics", "username", "description"],
            )
        except Exception as exc:
            ui.warn(f"Search failed for '{keyword}': {exc}")
            continue

        if not results or not results.includes or "users" not in results.includes:
            continue

        seen_ids = {t["user_id"] for t in targets}
        for user in results.includes["users"]:
            if str(user.id) in seen_ids:
                continue
            metrics = getattr(user, "public_metrics", None) or {}
            followers = metrics.get("followers_count", 0)

            if min_followers <= followers <= max_followers:
                targets.append({
                    "user_id": str(user.id),
                    "username": user.username,
                    "description": getattr(user, "description", "") or "",
                    "followers": followers,
                    "following": metrics.get("following_count", 0),
                    "tweet_count": metrics.get("tweet_count", 0),
                })
                seen_ids.add(str(user.id))

        if len(targets) >= limit:
            break

    targets.sort(key=lambda t: t["followers"], reverse=True)
    targets = targets[:limit]

    ui.success(f"Found {len(targets)} engagement targets")
    for t in targets[:10]:
        ui.info(f"  @{t['username']} ({t['followers']:,} followers) - {t['description'][:60]}")

    return targets


# ---------------------------------------------------------------------------
# Engagement stats summary
# ---------------------------------------------------------------------------

def engagement_summary() -> dict:
    """Show engagement activity summary."""
    log = _load_engage_log()
    if not log:
        ui.warn("No engagement activity yet.")
        return {"total": 0}

    likes = sum(1 for e in log if e.get("action") == "like")
    replies = sum(1 for e in log if e.get("action") == "reply")

    # Last 24h
    now = datetime.now()
    recent = [
        e for e in log
        if (now - datetime.fromisoformat(e.get("at", now.isoformat()))).total_seconds() < 86400
    ]
    recent_likes = sum(1 for e in recent if e.get("action") == "like")
    recent_replies = sum(1 for e in recent if e.get("action") == "reply")

    summary = {
        "total": len(log),
        "total_likes": likes,
        "total_replies": replies,
        "last_24h_likes": recent_likes,
        "last_24h_replies": recent_replies,
    }

    ui.status_table([
        ("Total likes", "Ready", str(likes)),
        ("Total replies", "Ready", str(replies)),
        ("24h likes", "Ready", str(recent_likes)),
        ("24h replies", "Ready", str(recent_replies)),
    ])

    return summary
