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
    """Strict check for likes. Only like PERSONAL dev tweets, not brands."""
    if len(text) < 20 or _spam(text):
        return False
    lower = text.lower()

    # REJECT brands, promos, announcements
    reject = [
        "crypto", "nft", "giveaway", "follow me", "dm me", "pray", "god",
        "sports", "football", "basketball", "celebrity", "birthday",
        "twitter is cool", "follow back", "release notes", "changelog",
        "google play", "app store", "hiring", "join us", "apply now",
        "service center", "overseas", "artemis", "nasa",
        "connectors", "available on every", "create videos",
        "automate your", "boost your", "try our", "check out our",
        "introducing", "announcing", "launched", "just dropped",
        "alternative to", "subscribe", "sign up", "free trial",
        "tokens launched", "$1", "update:", "december update",
        "looking for an", "are you looking",
    ]
    if any(r in lower for r in reject):
        return False

    # Must contain FIRST PERSON or QUESTION (personal tweet, not brand)
    personal_signals = [
        "i ", "i'm", "i've", "my ", "me ", "we ",
        "?",  # questions are good
        "just built", "just made", "just learned", "just finished",
        "struggling", "finally", "anyone else", "am i the only",
        "hot take", "unpopular opinion", "be honest", "confession",
        "what's your", "what do you", "how do you", "which ",
    ]
    has_personal = any(p in lower for p in personal_signals)

    # Must be about dev/tech
    tech = [
        "code", "coding", "programming", "developer", "dev ",
        "javascript", "typescript", "python", "rust", "react",
        "windows", "linux", "pc", "laptop", "setup",
        "cpu", "gpu", "ram", "performance",
        "vscode", "terminal", "git", "docker",
        "framework", "open source",
    ]
    has_tech = any(t in lower for t in tech)

    return has_personal and has_tech


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


def _is_reply_worthy(tweet_text: str) -> bool:
    """Strict check: is this tweet something we should reply to as a dev?"""
    lower = tweet_text.lower()

    # HARD REJECT — never reply to these
    reject = [
        "crypto", "nft", "airdrop", "giveaway", "elon", "trump", "biden",
        "sports", "football", "basketball", "celebrity", "kardashian",
        "follow me", "check my", "dm me", "subscribe", "onlyfans",
        "good morning", "gm everyone", "happy birthday", "rip ",
        "pray for", "god is", "jesus", "allah", "bible",
        "twitter is cool", "follow back", "like and retweet",
        "hiring", "we are ", "join us", "apply now",
        "google play", "app store", "download our",
        "release notes", "changelog", "v0.", "v1.", "update:",
        "connectors", "integration", "available on every",
        "artemis", "launch", "nasa", "space",
        "inspired", "inspiring", "motivat",
    ]
    if any(r in lower for r in reject):
        return False

    # HARD REJECT — known bot/brand accounts topics
    brand_patterns = [
        "create videos", "automate your", "boost your",
        "try our", "check out our", "introducing our",
        "we are aware", "service center", "overseas",
    ]
    if any(b in lower for b in brand_patterns):
        return False

    # MUST be a PERSONAL tweet about dev/tech — not a brand announcement
    personal_dev_topics = [
        "i code", "i built", "i made", "i learned", "i hate",
        "i love", "i use", "i think", "i switched",
        "my setup", "my code", "my project", "my laptop", "my pc",
        "what language", "what framework", "best language", "best framework",
        "which ide", "which editor", "which os",
        "anyone else", "am i the only", "unpopular opinion",
        "hot take", "confession", "be honest",
        "how do you", "what do you", "do you prefer",
        "struggling with", "finally got", "just learned",
        "why is windows", "why does windows", "windows is so",
        "my windows", "fresh install", "task manager",
        "debloat", "bloatware", "telemetry", "services tab",
    ]
    return any(p in lower for p in personal_dev_topics)


def gen_reply(tweet_text: str) -> str | None:
    vp = _voice()

    # GATE 1: Is this tweet about dev/tech/windows?
    if not _is_reply_worthy(tweet_text):
        return None

    # GATE 2: LLM relevance check - is this a tweet we can add value to?
    check_prompt = (
        f'Can a developer who knows Windows internals and programming '
        f'add genuine value to this conversation? Not by promoting a product, '
        f'but by sharing knowledge or opinion?\n\n'
        f'Tweet: "{tweet_text[:200]}"\n\nYES or NO only.'
    )
    try:
        check = llm.generate(check_prompt, system="reply YES or NO. one word.")
        if "NO" in check.upper():
            return None
    except Exception:
        return None

    # GATE 3: Is this specifically about Windows optimization? (determines if we can mention product)
    is_windows_help = any(w in tweet_text.lower() for w in [
        "debloat", "optimize windows", "windows slow", "windows bloat",
        "remove bloatware", "windows services", "windows telemetry",
        "clean windows", "speed up windows", "windows optimization",
    ])

    # Generate reply
    if is_windows_help:
        prompt = (
            f'someone needs help with windows: "{tweet_text[:200]}"\n\n'
            f'give a specific helpful tip. you can casually mention oudenOS (ouden.cc) '
            f'as one option but give real advice first. under 200 chars.'
        )
    elif _roastable(tweet_text):
        prompt = (
            f'someone tweeted a bad take: "{tweet_text[:200]}"\n\n'
            f'roast them with facts. be funny. do NOT mention any product. under 180 chars.'
        )
    else:
        prompt = (
            f'someone tweeted: "{tweet_text[:200]}"\n\n'
            f'reply to what THEY said. be specific to their point. '
            f'do NOT mention oudenOS or any product. just be a helpful dev. under 180 chars.'
        )

    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 10 or len(text) > 280:
        return None

    # GATE 4: Hard reject spam/AI patterns in output
    text_lower = text.lower()
    spam_patterns = [
        "kills 220", "kills 280", "blocks 70", "280 services",
        "220 services", "70 telemetry", "70 endpoints",
        "github.com/redpersongpt", "oudenOS kills", "oudenOS blocks",
        "oudenOS does this", "oudenOS fixes", "oudenOS can",
        "check out oudenOS", "try oudenOS",
        "here's why", "did you know", "introducing",
        "as a developer", "in my experience",
    ]
    if any(p.lower() in text_lower for p in spam_patterns):
        return None

    # If oudenOS/ouden.cc mentioned but tweet wasn't about windows help → reject
    if not is_windows_help and ("oudenos" in text_lower or "ouden.cc" in text_lower):
        return None

    # Reject if reply is too generic / template
    generic = [
        "windows defaults are", "windows is just", "windows ships with",
        "fresh windows", "microsoft doesnt", "microsoft knows",
    ]
    if sum(1 for g in generic if g in text_lower) >= 2:
        return None

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
    time.sleep(5)
    _dismiss_overlays(page)
    c = page.locator('[data-testid="tweetTextarea_0"]').first
    c.click()
    time.sleep(0.5)
    for idx, line in enumerate(text.split("\n")):
        if idx > 0: page.keyboard.press("Enter")
        if line.strip(): page.keyboard.type(line, delay=random.randint(8, 18))
    time.sleep(2)
    # Use Ctrl+Enter shortcut instead of clicking button (faster, more reliable)
    page.keyboard.press("Control+Enter")
    time.sleep(5)


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
    page.locator('[data-testid="tweetButton"]').click(force=True, timeout=30000)
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
    page.locator('[data-testid="tweetButton"]').click(force=True, timeout=30000)
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
    """Like + reply to relevant tweets from HomeTimeline via HTTP API."""
    from modules.http_twitter import HttpTwitter
    api = HttpTwitter()

    tweets = api.home_timeline(30)
    if not tweets:
        print("  [engage] no timeline tweets")
        return 0

    print(f"  [engage] {len(tweets)} timeline tweets")
    liked = 0
    replied = 0

    for t in tweets:
        if not can_like(log) and not can_reply(log):
            break
        if not _relevant(t["text"]):
            continue
        if _spam(t["text"]):
            continue

        # Like via HTTP (fast, no Playwright)
        if can_like(log):
            try:
                if api.like(t["id"]):
                    log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "tid": t["id"]})
                    liked += 1
                    track_action("like")
                    print(f"  [like] @{t['user']}: {t['text'][:50]}...")
            except Exception:
                pass
            time.sleep(random.uniform(2, 6))

        # Reply via Playwright (HTTP gives 226)
        if can_reply(log) and random.random() < 0.50 and page:
            reply = gen_reply(t["text"])
            if reply:
                try:
                    print(f"  [reply] {reply[:60]}...")
                    # Navigate to tweet and reply
                    page.goto(f"https://x.com/i/status/{t['id']}", wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3)
                    _dismiss_overlays(page)
                    reply_box = page.locator('[data-testid="tweetTextarea_0"]').first
                    if reply_box.count() > 0:
                        reply_box.click()
                        time.sleep(0.5)
                        page.keyboard.type(reply, delay=random.randint(8, 15))
                        time.sleep(1)
                        page.locator('[data-testid="tweetButton"]').click()
                        time.sleep(3)
                        log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": t["text"][:100], "r": reply[:200]})
                        replied += 1
                        track_action("reply")
                except Exception as exc:
                    print(f"  [reply] fail: {exc}")
            time.sleep(random.uniform(5, 15))

    if liked:
        print(f"  [engage] liked {liked}")
    return replied


def _do_mentions(page, log) -> int:
    """Check notifications via HTTP, reply via Playwright."""
    from modules.http_twitter import HttpTwitter
    api = HttpTwitter()

    notifs = api.notifications()
    print(f"  [mentions] {len(notifs)} notifications")
    replied = 0

    for n in notifs[:8]:
        if not can_reply(log):
            break
        if _spam(n["text"]):
            continue

        reply = gen_mention_reply(n["text"])
        if reply and page:
            try:
                print(f"  [mention] replying: {reply[:60]}...")
                page.goto(f"https://x.com/i/status/{n['id']}", wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
                _dismiss_overlays(page)
                reply_box = page.locator('[data-testid="tweetTextarea_0"]').first
                if reply_box.count() > 0:
                    reply_box.click()
                    time.sleep(0.5)
                    page.keyboard.type(reply, delay=random.randint(8, 15))
                    time.sleep(1)
                    page.locator('[data-testid="tweetButton"]').click(force=True, timeout=30000)
                    time.sleep(4)
                    log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": n["text"][:100], "r": reply[:200], "src": "mention"})
                    replied += 1
                    track_action("reply")
            except Exception as exc:
                print(f"  [mention] fail: {exc}")
        time.sleep(random.uniform(8, 15))

    return replied


def _do_browse(page, log) -> int:
    """Like relevant timeline tweets via HTTP API (fast, no Playwright)."""
    from modules.http_twitter import HttpTwitter
    api = HttpTwitter()

    tweets = api.home_timeline(30)
    print(f"  [browse] {len(tweets)} tweets")
    liked = 0
    kws = _keywords()

    for t in tweets:
        if not can_like(log):
            break
        if any(kw in t["text"].lower() for kw in kws):
            try:
                if api.like(t["id"]):
                    log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "src": "tl"})
                    liked += 1
                    track_action("like")
            except Exception:
                pass
            time.sleep(random.uniform(2, 5))

    if liked:
        print(f"  [browse] liked {liked}")
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


# ─── Pure HTTP cycle (no Playwright) ──────────────────────────────

def run_cycle_http() -> dict:
    """Full cycle using only HTTP API (curl_cffi). No browser needed."""
    from modules.http_twitter import HttpTwitter

    log = _load_log()
    stats = {"tweets": 0, "replies": 0, "likes": 0}
    api = HttpTwitter()

    # Release check
    new_rel = _new_release(log)
    if new_rel and can_tweet(log):
        text = gen_tweet(release_tag=new_rel)
        if text:
            try:
                print(f"  [release] {text[:60]}...")
                tid = api.create_tweet(text)
                if tid:
                    log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200], "type": "release", "id": tid})
                    stats["tweets"] += 1
                    track_action("tweet")
                    print(f"  [release] POSTED {tid}")
            except Exception as exc:
                print(f"  [release] error: {exc}")
            time.sleep(random.uniform(5, 15))

    # Activities
    if is_peak_hour():
        activities = ["tweet", "like", "like", "reply", "reply", "reply", "like"]
    elif is_dead_hour():
        activities = ["like"]
    else:
        activities = ["tweet", "like", "like", "reply", "reply"]

    random.shuffle(activities)

    for activity in activities:
        try:
            if activity == "tweet" and can_tweet(log):
                text = gen_tweet()
                if text:
                    print(f"  [tweet] {text[:60]}...")
                    tid = api.create_tweet(text)
                    if tid:
                        log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200], "id": tid})
                        stats["tweets"] += 1
                        track_action("tweet")
                        print(f"  [tweet] POSTED {tid}")

            elif activity == "like" and can_like(log):
                tweets = api.home_timeline(30)
                kws = _keywords()
                for t in tweets:
                    if not can_like(log):
                        break
                    if any(kw in t["text"].lower() for kw in kws):
                        try:
                            if api.like(t["id"]):
                                log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "tid": t["id"]})
                                stats["likes"] += 1
                                track_action("like")
                                print(f"  [like] @{t['user']}: {t['text'][:50]}...")
                        except Exception:
                            pass
                        time.sleep(random.uniform(2, 6))

            elif activity == "reply" and can_reply(log):
                tweets = api.home_timeline(30)
                for t in tweets:
                    if not can_reply(log):
                        break
                    if not _relevant(t["text"]) or _spam(t["text"]):
                        continue
                    if not t.get("user") or not t.get("id"):
                        continue
                    if random.random() > 0.50:
                        continue

                    reply = gen_reply(t["text"])
                    if reply:
                        try:
                            print(f"  [reply] to @{t['user']}: {reply[:60]}...")
                            rid = api.create_tweet(reply, reply_to=t["id"])
                            if rid:
                                log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": t["text"][:100], "r": reply[:200], "user": t["user"], "id": rid})
                                stats["replies"] += 1
                                track_action("reply")
                                print(f"  [reply] POSTED {rid}")
                        except Exception as exc:
                            print(f"  [reply] error: {exc}")
                        time.sleep(random.uniform(10, 25))
                        break

        except Exception as exc:
            print(f"  [{activity}] error: {exc}")

        time.sleep(random.uniform(5, 15))

    _save_log(log)
    return stats


# ─── Hybrid cycle (HTTP reads + Playwright writes) ────────────────

def run_cycle_hybrid(cookies: dict, pw_post_fn) -> dict:
    """Main cycle for VDS: HTTP for reads, Playwright for writes.

    Args:
        cookies: dict with ct0 and auth_token
        pw_post_fn: callable(cookies, text, reply_to_url=None) -> bool
    """
    from modules.http_twitter import HttpTwitter

    log = _load_log()
    stats = {"tweets": 0, "replies": 0, "likes": 0}
    api = HttpTwitter()

    # Release check
    new_rel = _new_release(log)
    if new_rel and can_tweet(log):
        text = gen_tweet(release_tag=new_rel)
        if text:
            print(f"  [release] {text[:60]}...")
            if pw_post_fn(cookies, text):
                log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200], "type": "release"})
                stats["tweets"] += 1
                track_action("tweet")
            time.sleep(random.uniform(5, 15))

    # Build activities
    if is_peak_hour():
        activities = ["tweet", "like_timeline", "like_timeline", "reply_timeline", "reply_timeline", "like_timeline"]
    elif is_dead_hour():
        activities = ["like_timeline"]
    else:
        activities = ["tweet", "like_timeline", "like_timeline", "reply_timeline"]

    random.shuffle(activities)

    for activity in activities:
        try:
            if activity == "tweet" and can_tweet(log):
                text = gen_tweet()
                if text:
                    print(f"  [tweet] {text[:60]}...")
                    if pw_post_fn(cookies, text):
                        log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200]})
                        stats["tweets"] += 1
                        track_action("tweet")

            elif activity == "like_timeline" and can_like(log):
                tweets = api.home_timeline(30)
                kws = _keywords()
                for t in tweets:
                    if not can_like(log):
                        break
                    if any(kw in t["text"].lower() for kw in kws):
                        try:
                            if api.like(t["id"]):
                                log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "tid": t["id"]})
                                stats["likes"] += 1
                                track_action("like")
                                print(f"  [like] @{t['user']}: {t['text'][:50]}...")
                        except Exception:
                            pass
                        time.sleep(random.uniform(2, 6))

            elif activity == "reply_timeline" and can_reply(log):
                tweets = api.home_timeline(30)
                for t in tweets:
                    if not can_reply(log):
                        break
                    if not _relevant(t["text"]) or _spam(t["text"]):
                        continue
                    if not t.get("user"):
                        continue
                    if random.random() > 0.40:
                        continue

                    reply = gen_reply(t["text"])
                    if reply:
                        # Post as @mention tweet (compose/post with @username prefix)
                        mention_text = f"@{t['user']} {reply}"
                        print(f"  [reply] {mention_text[:70]}...")
                        if pw_post_fn(cookies, mention_text):
                            log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": t["text"][:100], "r": reply[:200], "user": t["user"]})
                            stats["replies"] += 1
                            track_action("reply")
                        time.sleep(random.uniform(10, 25))
                        break  # max 1 reply per sub-cycle

        except Exception as exc:
            print(f"  [{activity}] error: {exc}")

        time.sleep(random.uniform(5, 15))

    _save_log(log)
    return stats
