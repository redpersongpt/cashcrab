"""Autonomous Twitter engagement agent.

Runs 24/7 via PM2. Playwright browser automation.
Triple-LLM: Codex (o4-mini) + Gemini Flash + Qwen with auto-fallback.
All product-specific config from config.json [agent] section.

Features:
- Original tweets, replies, quote tweets, threads
- Image attachment support
- Smart time-based scheduling (US/EU peaks)
- Follow strategy for niche growth
- Analytics tracking (what works, what doesn't)
- Cookie health monitoring
- Release announcement from GitHub API
- Bot/spam filtering, virality scoring, safety checks
"""
from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from modules.config import ROOT, optional_section
from modules import llm

AGENT_LOG = ROOT / "agent_log.json"
VOICE_PATH = ROOT / "voice_profile.json"
RELEASE_CACHE = ROOT / "latest_release.json"
ANALYTICS_PATH = ROOT / "agent_analytics.json"

# Rate limits (verified account, aggressive but safe)
MAX_TWEETS_PER_DAY = 25
MAX_REPLIES_PER_DAY = 80
MAX_LIKES_PER_DAY = 150
MAX_QUOTES_PER_DAY = 10
MAX_FOLLOWS_PER_DAY = 30
MAX_THREADS_PER_DAY = 3
MIN_TWEET_INTERVAL_MIN = 20
MIN_REPLY_INTERVAL_MIN = 3
MIN_LIKE_INTERVAL_SEC = 12
MIN_QUOTE_INTERVAL_MIN = 30
MIN_FOLLOW_INTERVAL_SEC = 60


def _cfg() -> dict:
    return optional_section("agent", {})

def _product() -> str:
    return _cfg().get("product_name", "")

def _url() -> str:
    return _cfg().get("product_url", "")

def _repo() -> str:
    return _cfg().get("github_repo", "")

def _topics() -> list[str]:
    return _cfg().get("tweet_topics", [])

def _searches() -> list[str]:
    return _cfg().get("search_queries", ["Windows slow", "PC optimization"])

def _keywords() -> list[str]:
    return _cfg().get("relevance_keywords", ["windows", "optimize", "performance"])

def _roast_triggers() -> list[str]:
    return _cfg().get("roast_triggers", [])

def _quote_triggers() -> list[str]:
    return _cfg().get("quote_triggers", [])

def _follow_targets() -> list[str]:
    return _cfg().get("follow_targets", [])

def _thread_topics() -> list[str]:
    return _cfg().get("thread_topics", [])

def _image_prompts() -> list[str]:
    return _cfg().get("image_prompts", [])


# ─── Logging ──────────────────────────────────────────────────────

def _load_log() -> dict:
    if AGENT_LOG.exists():
        try:
            return json.loads(AGENT_LOG.read_text())
        except Exception:
            pass
    return {"tweets": [], "replies": [], "likes": [], "quotes": [], "follows": [], "threads": [], "skipped": []}


def _save_log(log: dict):
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    for key in list(log.keys()):
        if isinstance(log[key], list):
            log[key] = [e for e in log[key] if e.get("date", "") >= cutoff]
    AGENT_LOG.write_text(json.dumps(log, indent=2))


def _today(log, key):
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for e in log.get(key, []) if e.get("date", "").startswith(today))


def _last(log, key):
    items = log.get(key, [])
    if not items:
        return None
    try:
        return datetime.fromisoformat(items[-1]["date"])
    except (KeyError, ValueError):
        return None


def _can(log, key, max_day, min_delta):
    if _today(log, key) >= max_day:
        return False
    last = _last(log, key)
    if last and datetime.now() - last < min_delta:
        return False
    return True


def can_tweet(log): return _can(log, "tweets", MAX_TWEETS_PER_DAY, timedelta(minutes=MIN_TWEET_INTERVAL_MIN))
def can_reply(log): return _can(log, "replies", MAX_REPLIES_PER_DAY, timedelta(minutes=MIN_REPLY_INTERVAL_MIN))
def can_like(log): return _can(log, "likes", MAX_LIKES_PER_DAY, timedelta(seconds=MIN_LIKE_INTERVAL_SEC))
def can_quote(log): return _can(log, "quotes", MAX_QUOTES_PER_DAY, timedelta(minutes=MIN_QUOTE_INTERVAL_MIN))
def can_follow(log): return _can(log, "follows", MAX_FOLLOWS_PER_DAY, timedelta(seconds=MIN_FOLLOW_INTERVAL_SEC))
def can_thread(log): return _can(log, "threads", MAX_THREADS_PER_DAY, timedelta(hours=4))


# ─── Smart scheduling ────────────────────────────────────────────

def is_peak_hour() -> bool:
    """Check if current time is US/EU peak hours (more aggressive posting)."""
    utc_now = datetime.now(timezone.utc)
    hour = utc_now.hour
    # US peak: 13-17 UTC (9AM-1PM EST) and 22-02 UTC (6PM-10PM EST)
    # EU peak: 7-11 UTC (8AM-12PM CET)
    return hour in range(7, 12) or hour in range(13, 18) or hour in range(22, 24) or hour in range(0, 3)


def is_dead_hour() -> bool:
    """Check if it's low-activity hours (reduce posting)."""
    utc_now = datetime.now(timezone.utc)
    hour = utc_now.hour
    # Dead: 3-6 UTC (nobody's awake in US or EU)
    return hour in range(3, 7)


def cycle_sleep_minutes() -> int:
    """Dynamic sleep based on time of day."""
    if is_peak_hour():
        return random.randint(12, 20)
    if is_dead_hour():
        return random.randint(45, 90)
    return random.randint(20, 35)


# ─── Voice & safety ──────────────────────────────────────────────

def _voice() -> str:
    if VOICE_PATH.exists():
        try:
            return json.loads(VOICE_PATH.read_text()).get("voice_prompt", "")
        except Exception:
            pass
    return ""


def _check_quality(text: str) -> tuple[bool, bool]:
    """Combined safety + virality check in ONE LLM call. Returns (safe, viral)."""
    prompt = (
        f'Rate this tweet. Reply with exactly two words separated by space.\n'
        f'Word 1: SAFE or UNSAFE (wrong facts, personal attacks, AI-sounding, embarrassing = UNSAFE)\n'
        f'Word 2: a number 1-10 for viral potential (funny/relatable/surprising = high, boring/generic = low)\n\n'
        f'Example response: "SAFE 7" or "UNSAFE 3"\n\n'
        f'Tweet: "{text}"'
    )
    try:
        result = llm.generate(prompt, system="reply with exactly: SAFE/UNSAFE then a number 1-10. nothing else.")
        parts = result.strip().split()
        safe = "UNSAFE" not in parts[0].upper() if parts else True
        score = 5
        for p in parts:
            digits = "".join(c for c in p if c.isdigit())
            if digits:
                score = int(digits[:2])
                break
        return safe, score >= 5
    except Exception:
        return True, True


def _safe(text: str) -> bool:
    safe, _ = _check_quality(text)
    return safe


def _viral(text: str) -> bool:
    _, viral = _check_quality(text)
    return viral


def _safe_and_viral(text: str) -> bool:
    """Single LLM call for both checks. Use this instead of _safe() + _viral() separately."""
    safe, viral = _check_quality(text)
    return safe and viral


def _spam(text: str) -> bool:
    signals = ["check my pin", "dm me", "giveaway", "airdrop", "crypto", "nft",
               "follow me", "check bio", "link in bio", "whatsapp", "telegram",
               "onlyfans", "subscribe", "earn money", "free money"]
    t = text.lower()
    return len(t) < 15 or any(s in t for s in signals)


def _relevant(text: str) -> bool:
    if len(text) < 20 or _spam(text):
        return False
    return any(kw in text.lower() for kw in _keywords())


def _roastable(text: str) -> bool:
    return any(t in text.lower() for t in _roast_triggers())


def _quotable(text: str) -> bool:
    return any(t in text.lower() for t in _quote_triggers()) and len(text) > 30


# ─── Release checking ────────────────────────────────────────────

def _check_release() -> dict | None:
    repo = _repo()
    if not repo:
        return None
    if RELEASE_CACHE.exists():
        try:
            cached = json.loads(RELEASE_CACHE.read_text())
            if datetime.now() - datetime.fromisoformat(cached.get("_at", "2000-01-01")) < timedelta(hours=1):
                return cached
        except Exception:
            pass
    try:
        import httpx
        r = httpx.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=10)
        if r.status_code == 200:
            d = r.json()
            rel = {"tag": d.get("tag_name", ""), "name": d.get("name", ""),
                   "body": d.get("body", ""), "_at": datetime.now().isoformat()}
            RELEASE_CACHE.write_text(json.dumps(rel, indent=2))
            return rel
    except Exception:
        pass
    return None


def _new_release(log: dict) -> str | None:
    rel = _check_release()
    if not rel or not rel.get("tag"):
        return None
    tag = rel["tag"]
    if any(tag in t.get("text", "") for t in log.get("tweets", [])):
        return None
    return tag


# ─── Content generation ──────────────────────────────────────────

def gen_tweet(release_tag: str | None = None) -> str | None:
    vp, url, name = _voice(), _url(), _product()
    if release_tag:
        prompt = f"{name} {release_tag} just dropped. write a tweet announcing it. include {url}. under 270 chars. just the tweet."
    else:
        topics = _topics()
        if not topics:
            return None
        prompt = f"write one tweet about: {random.choice(topics)}. include {url}. under 270 chars. just the tweet, no quotes."
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if len(text) > 280: text = text[:277]
    if not text or len(text) < 30:
        return None
    if not _safe(text) or not _viral(text):
        return None
    return text


def gen_reply(tweet_text: str) -> str | None:
    vp, url, name = _voice(), _url(), _product()
    if _roastable(tweet_text):
        prompt = f'someone tweeted: "{tweet_text}"\n\nroast them with FACTS you are 100% sure about. mention {name} only if natural. under 200 chars. just the reply, no quotes.'
    else:
        prompt = f'someone tweeted: "{tweet_text}"\n\nhelpful casual reply. mention {url} if relevant, dont force it. under 200 chars. just the reply, no quotes.'
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 10 or len(text) > 280:
        return None
    # Skip safety/virality for replies (too slow, 1 LLM call is enough)
    return text


def gen_quote(original: str) -> str | None:
    vp, name = _voice(), _product()
    prompt = f'quote tweet: "{original}"\n\nadd your take. roast, agree, or add context. mention {name} ONLY if natural. under 250 chars. no quotes.'
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 15 or len(text) > 280:
        return None
    # Only safety check for quotes (public visibility), skip virality
    if not _safe(text):
        return None
    return text


def gen_mention_reply(mention: str) -> str | None:
    if _spam(mention):
        return None
    vp = _voice()
    prompt = f'someone replied to us: "{mention}"\n\nreply naturally. helpful if question, casual thanks if praise, roast back if trolling. if they say AI, deflect with humor. under 180 chars. no quotes.'
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 5 or len(text) > 280:
        return None
    # No extra checks for mention replies (speed > perfection)
    return text


def gen_thread() -> list[str] | None:
    """Generate a multi-tweet thread."""
    topics = _thread_topics()
    if not topics:
        topics = _topics()
    if not topics:
        return None
    vp, url = _voice(), _url()
    topic = random.choice(topics)
    prompt = (
        f"write a 4-tweet thread about: {topic}\n"
        f"tweet 1: hook (wild fact or question)\n"
        f"tweet 2-3: value (specific details, examples)\n"
        f"tweet 4: conclusion + {url}\n"
        f"each tweet under 270 chars. separate with ---\n"
        f"no numbering like 1/ or Thread:. just the tweets."
    )
    raw = llm.generate(prompt, system=vp)
    parts = [p.strip().strip('"\'') for p in raw.split("---") if p.strip()]
    if len(parts) < 3:
        return None
    parts = [p for p in parts[:5] if len(p) > 20 and len(p) <= 280]
    if len(parts) < 3:
        return None
    if not _safe(parts[0]) or not _viral(parts[0]):
        return None
    return parts


# ─── Analytics ────────────────────────────────────────────────────

def _load_analytics() -> dict:
    if ANALYTICS_PATH.exists():
        try:
            return json.loads(ANALYTICS_PATH.read_text())
        except Exception:
            pass
    return {"daily": {}, "total_tweets": 0, "total_replies": 0, "total_likes": 0}


def _save_analytics(data: dict):
    ANALYTICS_PATH.write_text(json.dumps(data, indent=2))


def track_action(action_type: str, detail: str = ""):
    analytics = _load_analytics()
    today = datetime.now().strftime("%Y-%m-%d")
    day = analytics.setdefault("daily", {}).setdefault(today, {})
    day[action_type] = day.get(action_type, 0) + 1
    analytics[f"total_{action_type}s"] = analytics.get(f"total_{action_type}s", 0) + 1
    # Trim older than 30 days
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    analytics["daily"] = {k: v for k, v in analytics["daily"].items() if k >= cutoff}
    _save_analytics(analytics)


# ─── Cookie health ────────────────────────────────────────────────

def check_cookie_health(page) -> bool:
    """Verify cookies are still valid by checking page state."""
    try:
        title = page.title()
        if "Login" in title or "Log in" in title:
            print("  [ALERT] Cookies expired! Agent cannot continue.")
            return False
        return True
    except Exception:
        return False


# ─── Playwright UI actions ────────────────────────────────────────

def _dismiss_overlays(page):
    """Dismiss any popups, cookie banners, or overlays blocking interaction."""
    try:
        for selector in [
            '[data-testid="twc-cc-mask"]',
            '[data-testid="sheetDialog"] [role="button"]',
            '[aria-label="Close"]',
            '[data-testid="app-bar-close"]',
            'div[role="dialog"] button',
        ]:
            el = page.locator(selector).first
            if el.count() > 0 and el.is_visible():
                el.click(timeout=3000)
                time.sleep(0.5)
    except Exception:
        pass
    # Also try pressing Escape
    try:
        page.keyboard.press("Escape")
        time.sleep(0.3)
    except Exception:
        pass


def _post(page, text: str):
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    _dismiss_overlays(page)
    c = page.locator('[data-testid="tweetTextarea_0"]').first
    c.click()
    time.sleep(0.5)
    for idx, line in enumerate(text.split("\n")):
        if idx > 0: page.keyboard.press("Enter")
        if line.strip(): page.keyboard.type(line, delay=random.randint(8, 18))
    time.sleep(2)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(4)


def _post_with_image(page, text: str, image_path: str):
    """Post tweet with an image attachment."""
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    c = page.locator('[data-testid="tweetTextarea_0"]').first
    c.click()
    time.sleep(0.5)
    for idx, line in enumerate(text.split("\n")):
        if idx > 0: page.keyboard.press("Enter")
        if line.strip(): page.keyboard.type(line, delay=random.randint(8, 18))
    time.sleep(1)
    # Upload image via file input
    file_input = page.locator('input[type="file"][accept*="image"]').first
    if file_input.count() > 0:
        file_input.set_input_files(image_path)
        time.sleep(3)  # wait for upload
    time.sleep(1)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(5)


def _reply(page, article, text: str):
    _dismiss_overlays(page)
    article.locator('[data-testid="reply"]').first.click()
    time.sleep(2)
    _dismiss_overlays(page)
    c = page.locator('[data-testid="tweetTextarea_0"]').first
    c.click()
    time.sleep(0.3)
    page.keyboard.type(text, delay=random.randint(8, 15))
    time.sleep(1)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(3)


def _like(page, article):
    _dismiss_overlays(page)
    btn = article.locator('[data-testid="like"]').first
    if btn.count() > 0:
        btn.click()
        time.sleep(random.uniform(1, 3))


def _quote(page, article, comment: str) -> bool:
    _dismiss_overlays(page)
    rt = article.locator('[data-testid="retweet"]').first
    if rt.count() == 0: return False
    rt.click()
    time.sleep(1.5)
    qo = page.get_by_role("menuitem").filter(has_text="Quote")
    if qo.count() == 0:
        page.keyboard.press("Escape")
        return False
    qo.click()
    time.sleep(2)
    c = page.locator('[data-testid="tweetTextarea_0"]').first
    c.click()
    time.sleep(0.3)
    page.keyboard.type(comment, delay=random.randint(8, 15))
    time.sleep(1)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(4)
    return True


def _follow_user(page, article) -> bool:
    """Follow the author of a tweet."""
    follow_btn = article.locator('[data-testid="placementTracking"] [role="button"]').filter(has_text="Follow").first
    if follow_btn.count() > 0:
        follow_btn.click()
        time.sleep(random.uniform(1, 3))
        return True
    return False


def _post_thread(page, tweets: list[str]):
    """Post a thread as a reply chain."""
    # Post first tweet
    _post(page, tweets[0])
    time.sleep(3)

    # Navigate to own profile to find the tweet and reply to it
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)

    # For subsequent tweets, use the compose reply flow
    for i, tweet in enumerate(tweets[1:], 1):
        # Go back to compose, Twitter keeps the thread context
        time.sleep(2)
        c = page.locator('[data-testid="tweetTextarea_0"]').first
        c.click()
        time.sleep(0.3)
        # Add thread tweet via "Add another tweet" button
        add_btn = page.locator('[data-testid="addButton"]')
        if add_btn.count() > 0:
            add_btn.click()
            time.sleep(1)
        # Type in the new textarea
        new_c = page.locator('[data-testid="tweetTextarea_0"]').last
        new_c.click()
        time.sleep(0.3)
        for idx, line in enumerate(tweet.split("\n")):
            if idx > 0: page.keyboard.press("Enter")
            if line.strip(): page.keyboard.type(line, delay=random.randint(8, 15))
        time.sleep(1)

    # Post all at once
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(5)


# ─── Main cycle ───────────────────────────────────────────────────

def run_cycle(page) -> dict:
    log = _load_log()
    stats = {"tweets": 0, "replies": 0, "likes": 0, "quotes": 0, "follows": 0, "threads": 0}

    # Cookie health check
    if not check_cookie_health(page):
        return stats

    # Release check
    new_rel = _new_release(log)
    if new_rel and can_tweet(log):
        try:
            text = gen_tweet(release_tag=new_rel)
            if text:
                print(f"  [release] {text[:60]}...")
                _post(page, text)
                log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200], "type": "release"})
                stats["tweets"] += 1
                track_action("tweet")
        except Exception as exc:
            print(f"  [release] error: {exc}")
        time.sleep(random.uniform(10, 20))

    # Build activity list based on time of day
    if is_peak_hour():
        activities = ["tweet", "engage", "engage", "engage", "reply_mentions",
                      "browse_like", "quote", "thread", "follow"]
    elif is_dead_hour():
        activities = ["browse_like", "engage"]
    else:
        activities = ["tweet", "engage", "engage", "reply_mentions", "browse_like", "quote"]

    random.shuffle(activities)

    for activity in activities:
        try:
            if activity == "tweet" and can_tweet(log):
                text = gen_tweet()
                if text:
                    print(f"  [tweet] {text[:60]}...")
                    _post(page, text)
                    log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200]})
                    stats["tweets"] += 1
                    track_action("tweet")

            elif activity == "thread" and can_thread(log):
                parts = gen_thread()
                if parts:
                    print(f"  [thread] {len(parts)} tweets: {parts[0][:50]}...")
                    _post_thread(page, parts)
                    log.setdefault("threads", []).append({"date": datetime.now().isoformat(), "count": len(parts), "hook": parts[0][:100]})
                    stats["threads"] += 1
                    track_action("thread")

            elif activity == "engage" and can_reply(log):
                stats["replies"] += _do_engage(page, log)

            elif activity == "reply_mentions" and can_reply(log):
                stats["replies"] += _do_mentions(page, log)

            elif activity == "browse_like" and can_like(log):
                stats["likes"] += _do_browse(page, log)

            elif activity == "quote" and can_quote(log):
                stats["quotes"] += _do_quote(page, log)

            elif activity == "follow" and can_follow(log):
                stats["follows"] += _do_follow(page, log)

        except Exception as exc:
            print(f"  [{activity}] error: {exc}")

        time.sleep(random.uniform(6, 20))

    _save_log(log)
    return stats


def _do_engage(page, log) -> int:
    queries = _searches()
    if not queries: return 0
    q = random.choice(queries)
    print(f"  [engage] {q}")
    page.goto(f"https://x.com/search?q={q}&src=typed_query&f=live", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    _dismiss_overlays(page)
    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    if count < 2: return 0
    replied = 0
    for i in range(min(10, count)):
        if not can_reply(log) and not can_like(log): break
        art = articles.nth(i)
        tel = art.locator('[data-testid="tweetText"]').first
        if tel.count() == 0: continue
        text = tel.inner_text()
        if not _relevant(text): continue
        if can_like(log):
            try:
                _like(page, art)
                log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "q": q})
                track_action("like")
            except Exception: pass
        if can_reply(log) and random.random() < 0.70:
            reply = gen_reply(text)
            if reply:
                try:
                    print(f"  [reply] {reply[:60]}...")
                    _reply(page, art, reply)
                    log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": text[:100], "r": reply[:200]})
                    replied += 1
                    track_action("reply")
                except Exception: pass
        time.sleep(random.uniform(4, 12))
    return replied


def _do_mentions(page, log) -> int:
    print("  [mentions] checking...")
    page.goto("https://x.com/notifications/mentions", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    articles = page.locator('article[data-testid="tweet"]')
    replied = 0
    for i in range(min(8, articles.count())):
        if not can_reply(log): break
        art = articles.nth(i)
        tel = art.locator('[data-testid="tweetText"]').first
        if tel.count() == 0: continue
        text = tel.inner_text()
        if _spam(text): continue
        reply = gen_mention_reply(text)
        if reply:
            try:
                print(f"  [mention] {reply[:60]}...")
                _reply(page, art, reply)
                log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": text[:100], "r": reply[:200], "src": "mention"})
                replied += 1
                track_action("reply")
            except Exception: pass
        time.sleep(random.uniform(8, 18))
    return replied


def _do_browse(page, log) -> int:
    print("  [browse] timeline...")
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    articles = page.locator('article[data-testid="tweet"]')
    liked = 0
    kws = _keywords()
    for i in range(min(20, articles.count())):
        if not can_like(log): break
        art = articles.nth(i)
        tel = art.locator('[data-testid="tweetText"]').first
        if tel.count() == 0: continue
        text = tel.inner_text().lower()
        if any(kw in text for kw in kws):
            try:
                _like(page, art)
                log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "src": "tl"})
                liked += 1
                track_action("like")
            except Exception: pass
            time.sleep(random.uniform(2, 5))
    return liked


def _do_quote(page, log) -> int:
    qs = _cfg().get("quote_queries", _searches()[:3])
    q = random.choice(qs)
    print(f"  [quote] {q}")
    page.goto(f"https://x.com/search?q={q}&src=typed_query&f=top", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)
    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    if count < 3: return 0
    for i in random.sample(range(min(8, count)), min(3, count)):
        if not can_quote(log): break
        art = articles.nth(i)
        tel = art.locator('[data-testid="tweetText"]').first
        if tel.count() == 0: continue
        text = tel.inner_text()
        if not _quotable(text): continue
        comment = gen_quote(text)
        if comment:
            try:
                print(f"  [quote] {comment[:60]}...")
                if _quote(page, art, comment):
                    log.setdefault("quotes", []).append({"date": datetime.now().isoformat(), "orig": text[:100], "c": comment[:200]})
                    track_action("quote")
                    return 1
            except Exception as exc:
                print(f"  [quote] fail: {exc}")
        break
    return 0


def _do_follow(page, log) -> int:
    """Follow relevant users from search results."""
    targets = _follow_targets()
    if not targets:
        targets = _searches()
    q = random.choice(targets)
    print(f"  [follow] searching: {q}")
    page.goto(f"https://x.com/search?q={q}&src=typed_query&f=user", wait_until="domcontentloaded", timeout=60000)
    time.sleep(4)

    # Find follow buttons on the page
    follow_btns = page.locator('[data-testid$="-follow"]')
    followed = 0
    for i in range(min(5, follow_btns.count())):
        if not can_follow(log): break
        try:
            btn = follow_btns.nth(i)
            btn_text = btn.inner_text().lower()
            if "follow" in btn_text and "following" not in btn_text:
                btn.click()
                time.sleep(random.uniform(2, 5))
                log.setdefault("follows", []).append({"date": datetime.now().isoformat(), "q": q})
                followed += 1
                track_action("follow")
        except Exception:
            pass
    return followed
