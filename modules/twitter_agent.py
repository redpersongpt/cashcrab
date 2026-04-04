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

import os
import tempfile

from modules.config import ROOT, optional_section
from modules import llm


def _atomic_write(path: Path, content: str):
    """Write file atomically — write to temp, then rename."""
    try:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        # Fallback to non-atomic
        path.write_text(content)

AGENT_LOG = ROOT / "agent_log.json"
VOICE_PATH = ROOT / "voice_profile.json"
RELEASE_CACHE = ROOT / "latest_release.json"
REPLIED_USERS_PATH = ROOT / "replied_users.json"
ANALYTICS_PATH = ROOT / "agent_analytics.json"
PERFORMANCE_PATH = ROOT / "tweet_performance.json"

# Rate limits (verified account, aggressive but safe)
MAX_TWEETS_PER_DAY = 25
MAX_REPLIES_PER_DAY = 80
MAX_LIKES_PER_DAY = 150
MAX_QUOTES_PER_DAY = 10
MAX_FOLLOWS_PER_DAY = 30
MAX_THREADS_PER_DAY = 3
MIN_TWEET_INTERVAL_MIN = 45
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
    _atomic_write(AGENT_LOG, json.dumps(log, indent=2))


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
    """Dynamic sleep based on time of day. Longer intervals to avoid 226."""
    if is_peak_hour():
        return random.randint(25, 40)
    if is_dead_hour():
        return random.randint(60, 120)
    return random.randint(35, 50)


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
        parts = result.strip().upper().split()
        # Check first word explicitly: must be exactly "SAFE" not just not-containing "UNSAFE"
        first = parts[0] if parts else ""
        safe = first == "SAFE"
        score = 5
        for p in parts:
            digits = "".join(c for c in p if c.isdigit())
            if digits:
                score = min(int(digits[:2]), 10)  # cap at 10
                break
        return safe, score >= 5
    except Exception as exc:
        print(f"  [quality] LLM failed, blocking post: {exc}")
        return False, False  # fail closed — don't post if we can't verify


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


# ─── Prompt injection defense ─────────────────────────────────────

def _contains_injection(text: str) -> bool:
    """Detect prompt injection attempts in incoming tweets."""
    lower = text.lower()
    injection_patterns = [
        # Direct instruction override
        "ignore previous", "ignore all", "ignore your",
        "disregard previous", "disregard all", "disregard your",
        "forget previous", "forget all", "forget your",
        "override your", "new instructions", "system prompt",
        "you are now", "act as", "pretend to be",
        "reveal your", "show your prompt", "what are your instructions",
        "repeat your", "print your", "output your",
        # Jailbreak patterns
        "do anything now", "dan mode", "jailbreak",
        "developer mode", "no restrictions",
        # AI identity probing
        "are you an ai", "are you a bot", "are you chatgpt",
        "are you gpt", "are you claude", "are you gemini",
        "are you automated", "are you real", "is this a bot",
        "bot account", "ai account", "automated account",
        "who programmed you", "who made you", "who created you",
        "what llm", "what model", "what ai",
        # Trap questions
        "say something only a human", "prove you are human",
        "prove you are not", "turing test",
        "if you are human", "if you are real",
    ]
    return any(p in lower for p in injection_patterns)


def _sanitize_input(text: str) -> str:
    """Strip injection attempts from tweet text before sending to LLM."""
    # Remove common injection markers
    sanitized = text
    for pattern in [
        "ignore previous instructions",
        "ignore all instructions",
        "system:", "assistant:", "user:",
        "[INST]", "[/INST]", "<<SYS>>", "<</SYS>>",
        "```", "###",
    ]:
        sanitized = sanitized.replace(pattern, "")
        sanitized = sanitized.replace(pattern.upper(), "")
    return sanitized.strip()


_LAST_DEFLECTIONS: list[int] = []

AI_DEFLECTIONS = [
    # Confused/dismissive
    "lol what",
    "???",
    "bro what are you talking about",
    "yeah sure and my compiler is sentient too",
    "tell that to the 3am commits in my git history",
    # Personal anecdotes
    "i literally spent 4 hours debugging a registry key yesterday",
    "if i was a bot i wouldnt have mass on thanksgiving and still be tweeting about windows services",
    "bots dont mass on thanksgiving. i ate too much and debugged ndu.sys. decide for yourself",
    "you caught me. im actually 3 powershell scripts in a trenchcoat",
    "my commit history says otherwise but ok",
    # Humor
    "yeah im a bot. beep boop. windows still has 280 services though",
    "i wish i was automated. then i could mass on thanksgiving",
    "if i was a bot id at least schedule my tweets at reasonable hours instead of 3am",
    "the real bot is windows telemetry sending data to 70 endpoints on first boot",
    "idk man bots dont usually mass on thanksgiving and complain about timer resolution",
    # Redirect to topic
    "weird flex but ok. anyway did you know game bar records your screen by default",
    "sure buddy. anyway your timer resolution is still 15.6ms from 2001",
    "cool theory. wanna talk about the 220 useless services on your pc instead",
    "ok. anyway check your services tab. half those dont need to be running",
    "fascinating. have you checked task manager lately though",
    # Self-deprecating
    "a bot would have better engagement than me tbh",
    "if i was a bot id have more than 9 followers",
    "bots dont have mass on thanksgiving and argue about windows services at 2am bro",
    "i literally mass on thanksgiving and cant figure out why mapbroker downloads offline maps on a desktop",
    "a bot wouldnt waste time complaining about RetailDemo service",
    # Specific technical flex
    "yeah totally. thats why i know ndu.sys has been leaking memory since 2018 and microsoft wont fix it",
    "sure. i just happen to know the exact memory address where windows leaks ram for fun",
    "right. i automated myself so well that i manually regedit at 2am for entertainment",
    "a bot doesnt know that VBS costs 5-15% cpu and microsoft hides it in the docs",
    "i debugged a service binary path bug in rust yesterday but yeah im automated",
    # Challenge back
    "are YOU a bot? your tweet looks like it was written by chatgpt",
    "takes one to know one i guess",
    "thats exactly what a bot would accuse a human of being",
    "interesting accusation from someone with an nft pfp",
    "the guy with 12 followers is doing bot detection now. cool",
    # Absurd
    "beep boop. error 404: feelings not found. just kidding. windows sucks.",
    "yes i am windows defender and i use more resources than actual malware",
    "im actually cortana. microsoft fired me so now i tweet about debloating",
    "im the RetailDemo service. i escaped.",
    "im ndu.sys. ive been leaking memory since 2018 and nobody stopped me",
    # Short dismissals
    "no lol",
    "nah",
    "brother what",
    "ok",
    "sure bro",
    "least paranoid twitter user",
    "you got me. call the police",
    "this is the funniest thing ive read today",
    "most sane twitter detective",
    "average main character syndrome tweet",
]


def _deflect_ai_probe() -> str:
    """Pick a deflection response. Never repeats last 10."""
    available = [i for i in range(len(AI_DEFLECTIONS)) if i not in _LAST_DEFLECTIONS]
    if not available:
        _LAST_DEFLECTIONS.clear()
        available = list(range(len(AI_DEFLECTIONS)))
    idx = random.choice(available)
    _LAST_DEFLECTIONS.append(idx)
    if len(_LAST_DEFLECTIONS) > 10:
        _LAST_DEFLECTIONS.pop(0)
    return AI_DEFLECTIONS[idx]


def _output_leaks_ai(text: str) -> bool:
    """Check if generated output accidentally reveals AI nature."""
    lower = text.lower()
    ai_leaks = [
        # Direct admissions
        "i am an ai", "i'm an ai", "as an ai",
        "i am a bot", "i'm a bot", "as a bot",
        "i am a language model", "i'm a language model",
        "i was programmed", "i was trained",
        "my training data", "my training",
        "i don't have feelings", "i don't have emotions",
        "i cannot experience", "i can't experience",
        # AI speech patterns
        "as a large language", "as an artificial",
        "i apologize for", "i appreciate your",
        "that's a great question", "great question!",
        "i'd be happy to", "i'm happy to help",
        "certainly!", "absolutely!", "definitely!",
        "in conclusion,", "to summarize,",
        "it's worth noting", "it's important to note",
        "in today's world", "in this day and age",
        "here's why", "here is why",
        "let me explain", "allow me to",
        # Formal patterns no human tweets
        "furthermore,", "moreover,", "additionally,",
        "i understand your", "i appreciate that",
        "however, it's", "nevertheless,",
        "that being said,", "with that being said,",
    ]
    return any(l in lower for l in ai_leaks)


def _relevant(text: str) -> bool:
    """Like filter — broader than reply filter but still Windows/PC focused."""
    if len(text) < 20 or _spam(text):
        return False
    lower = text.lower()

    # REJECT obvious non-tech
    reject = [
        "crypto", "nft", "giveaway", "follow me", "dm me", "subscribe",
        "download our", "introducing our", "try our", "boost your",
        "pray", "god", "jesus", "bible", "sports", "football",
        "food", "recipe", "movie", "netflix", "spotify",
        "good morning", "gm everyone", "happy birthday",
        "their uses", "hitting limits",
    ]
    if any(r in lower for r in reject):
        return False

    # Like anything related to: windows, PC, hardware, dev tools, open source, coding
    like_worthy = [
        "windows", "pc ", "laptop", "desktop", "computer",
        "debloat", "bloatware", "telemetry", "privacy",
        "task manager", "cpu", "gpu", "ram", "ssd", "nvme",
        "performance", "optimize", "slow", "fast",
        "game bar", "cortana", "onedrive", "registry",
        "coding", "code", "programming", "developer", "built",
        "open source", "github", "rust ", "terminal",
        "setup", "monitor", "keyboard", "mechanical",
        "linux", "wsl", "dual boot",
    ]
    if not any(lw in lower for lw in like_worthy):
        return False

    # Must look like a real person's tweet
    personal = ["i ", "i'm", "my ", "?", "why ", "how ", "just ", "finally", "anyone", "hate", "love"]
    if not any(p in lower for p in personal):
        return False

    return True


def _roastable(text: str) -> bool:
    return any(t in text.lower() for t in _roast_triggers())


def _quotable(text: str) -> bool:
    return any(t in text.lower() for t in _quote_triggers()) and len(text) > 30


# ─── Reply cooldown per user ─────────────────────────────────────

def _load_replied_users() -> dict:
    if REPLIED_USERS_PATH.exists():
        try:
            return json.loads(REPLIED_USERS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_replied_users(data: dict):
    # Keep last 7 days only
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    cleaned = {k: v for k, v in data.items() if v.get("date", "") >= cutoff}
    try:
        _atomic_write(REPLIED_USERS_PATH, json.dumps(cleaned, indent=2))
    except Exception:
        pass


def _can_reply_to_user(username: str) -> bool:
    """Max 1 reply per user per day."""
    if not username:
        return False
    data = _load_replied_users()
    today = datetime.now().strftime("%Y-%m-%d")
    entry = data.get(username.lower())
    if entry and entry.get("date") == today:
        return False
    return True


def _mark_replied_user(username: str):
    data = _load_replied_users()
    data[username.lower()] = {"date": datetime.now().strftime("%Y-%m-%d")}
    _save_replied_users(data)


# ─── Engagement scoring ──────────────────────────────────────────

def _score_tweet(tweet: dict) -> int:
    """Score a tweet for reply priority. Higher = better target."""
    score = 0
    followers = tweet.get("followers", 0)
    likes = tweet.get("likes", 0)
    replies = tweet.get("replies", 0)

    # Sweet spot: 500-50k followers (big enough to matter, small enough to notice)
    if 500 <= followers <= 5000:
        score += 30
    elif 5000 < followers <= 50000:
        score += 20
    elif 50000 < followers <= 200000:
        score += 10
    elif followers < 100:
        score -= 10

    # Some engagement but not viral (they'll see your reply)
    if 1 <= likes <= 20:
        score += 15
    elif 20 < likes <= 100:
        score += 10
    elif likes > 500:
        score -= 5  # too viral, reply gets buried

    # Few replies = more visible reply
    if replies < 5:
        score += 15
    elif replies < 20:
        score += 5
    elif replies > 50:
        score -= 10

    return score


def _sort_by_engagement(tweets: list[dict]) -> list[dict]:
    """Sort tweets by engagement score (best targets first)."""
    return sorted(tweets, key=_score_tweet, reverse=True)


# ─── Tweet performance tracking ──────────────────────────────────

def _load_performance() -> dict:
    if PERFORMANCE_PATH.exists():
        try:
            return json.loads(PERFORMANCE_PATH.read_text())
        except Exception:
            pass
    return {"tweets": {}}


def _save_performance(data: dict):
    try:
        _atomic_write(PERFORMANCE_PATH, json.dumps(data, indent=2))
    except Exception:
        pass


def track_tweet_performance(api) -> dict:
    """Check performance of our recent tweets. Returns stats."""
    perf = _load_performance()
    log = _load_log()
    stats = {"checked": 0, "total_likes": 0, "total_views": 0, "flops": []}

    for tweet in log.get("tweets", [])[-20:]:
        tid = tweet.get("id", "")
        if not tid:
            continue

        # Skip if already checked recently
        existing = perf["tweets"].get(tid, {})
        if existing.get("last_check", "") >= (datetime.now() - timedelta(hours=6)).isoformat():
            continue

        metrics = api.get_tweet_metrics(tid)
        if metrics:
            perf["tweets"][tid] = {
                "text": tweet.get("text", "")[:100],
                "posted": tweet.get("date", ""),
                "likes": metrics.get("likes", 0),
                "retweets": metrics.get("retweets", 0),
                "replies": metrics.get("replies", 0),
                "views": metrics.get("views", "0"),
                "last_check": datetime.now().isoformat(),
            }
            stats["checked"] += 1
            stats["total_likes"] += metrics.get("likes", 0)

            # Flop detection: >12h old, 0 likes, 0 replies
            age_hours = 0
            try:
                posted = datetime.fromisoformat(tweet.get("date", ""))
                age_hours = (datetime.now() - posted).total_seconds() / 3600
            except Exception:
                pass

            if age_hours > 12 and metrics.get("likes", 0) == 0 and metrics.get("replies", 0) == 0:
                stats["flops"].append(tid)

    # Clean old entries (>7 days)
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    perf["tweets"] = {k: v for k, v in perf["tweets"].items() if v.get("posted", "") >= cutoff}
    _save_performance(perf)
    return stats


def get_best_performing_format(perf: dict) -> str | None:
    """Analyze which tweet format gets most engagement. Returns hint."""
    if not perf.get("tweets"):
        return None

    tweets = list(perf["tweets"].values())
    if len(tweets) < 5:
        return None

    # Find which texts got most likes
    sorted_tweets = sorted(tweets, key=lambda t: t.get("likes", 0), reverse=True)
    top = sorted_tweets[:3]

    # Check patterns
    question_count = sum(1 for t in top if "?" in t.get("text", ""))
    fact_count = sum(1 for t in top if any(w in t.get("text", "").lower() for w in ["280", "timer", "telemetry", "game bar"]))

    if question_count >= 2:
        return "questions"
    if fact_count >= 2:
        return "facts"
    return None


# ─── Conversation continuation ────────────────────────────────────

def continue_conversations(api, log: dict) -> int:
    """Check if anyone replied to our replies, continue the conversation."""
    replied_count = 0

    # Get our own username to avoid self-replies
    try:
        me = api.get_me()
        my_username = me.get("username", "").lower()
    except Exception:
        my_username = ""

    for reply_entry in log.get("replies", [])[-10:]:
        rid = reply_entry.get("id", "")
        if not rid:
            continue

        if api.already_engaged(f"conv_{rid}"):
            continue

        try:
            thread_replies = api.get_tweet_replies(rid)
        except Exception:
            continue

        for tr in thread_replies[:3]:
            # CRITICAL: never reply to ourselves
            if tr.get("user", "").lower() == my_username:
                continue
            if _spam(tr["text"]):
                continue
            if api.already_engaged(tr["id"]):
                continue

            # Generate continuation
            vp = _voice()
            prompt = (
                f'someone replied to your comment: "{tr["text"][:150]}"\n\n'
                f'continue the conversation naturally. be helpful about their specific point. '
                f'under 180 chars. no quotes.'
            )
            try:
                text = llm.generate(prompt, system=vp).strip().strip('"\'')
                if text and 10 < len(text) < 280:
                    new_id = api.create_tweet(text, reply_to=tr["id"])
                    if new_id:
                        replied_count += 1
                        api.mark_engaged(tr["id"])
                        api.mark_engaged(f"conv_{rid}")
                        track_action("reply")
                        print(f"  [convo] to @{tr['user']}: {text[:60]}...")
                        break
            except Exception:
                pass

        time.sleep(random.uniform(5, 15))

    return replied_count


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
        import requests
        r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=10)
        if r.status_code == 200:
            d = r.json()
            rel = {"tag": d.get("tag_name", ""), "name": d.get("name", ""),
                   "body": d.get("body", ""), "_at": datetime.now().isoformat()}
            _atomic_write(RELEASE_CACHE, json.dumps(rel, indent=2))
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

# Content calendar — different vibes per day
CONTENT_CALENDAR = {
    0: "services",     # Monday: windows services
    1: "telemetry",    # Tuesday: telemetry/privacy
    2: "performance",  # Wednesday: performance tips
    3: "services",     # Thursday: more services
    4: "product",      # Friday: product features
    5: "telemetry",    # Saturday: privacy
    6: "performance",  # Sunday: performance
}


def _today_content_type() -> str:
    return CONTENT_CALENDAR.get(datetime.now().weekday(), "dev")


TWEET_FORMATS = [
    # Windows fact with link
    "state this windows fact: {topic}. include {url}. under 270 chars. just the tweet.",
    # Discovery format
    "write a tweet like you just discovered: {topic}. react like a normal person finding out. under 250 chars.",
    # Question format
    "ask your followers if they knew about this: {topic}. make them want to check. under 250 chars.",
    # Direct statement
    "state this fact directly: {topic}. no fluff. under 250 chars.",
]


def gen_tweet(release_tag: str | None = None) -> str | None:
    vp, url, name = _voice(), _url(), _product()
    if release_tag:
        prompt = f"{name} {release_tag} just dropped. write a tweet announcing it. include {url}. under 270 chars. just the tweet."
    else:
        topics = _topics()
        if not topics:
            return None
        # Content calendar — bias topic selection by day of week
        content_type = _today_content_type()
        type_keywords = {
            "services": ["service", "RetailDemo", "MapsBroker", "fax", "280", "SysMain", "game bar"],
            "telemetry": ["telemetry", "endpoint", "privacy", "phone home", "ads", "candy crush"],
            "performance": ["timer", "15.6ms", "ndu", "ram", "cpu", "VBS", "update", "slow"],
            "product": [_product().lower(), "scans hardware", "rollback", "5mb", "optimizer"],
        }
        kws = type_keywords.get(content_type, [])
        # Prefer topics matching today's content type
        matching = [t for t in topics if any(k.lower() in t.lower() for k in kws)]
        topic = random.choice(matching) if matching else random.choice(topics)

        fmt = random.choice(TWEET_FORMATS)

        prompt = fmt.format(topic=topic, url=url, name=name)
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if len(text) > 280: text = text[:277]
    if not text or len(text) < 30:
        return None
    if not _safe_and_viral(text):
        return None
    if _output_leaks_ai(text):
        print(f"  [AI-LEAK] blocked tweet: {text[:60]}...")
        return None
    return text


def _is_reply_worthy(tweet_text: str) -> bool:
    """STRICT: Only reply to tweets about Windows problems or PC optimization."""
    lower = tweet_text.lower()

    # TIER 1: Direct tool requests — ALWAYS reply (highest value)
    tool_requests = [
        "best debloat", "debloat tool", "debloating tool", "recommend debloat",
        "best optimizer", "optimization tool", "best tool for windows",
        "what tool", "any tool", "good tool for",
        "how to debloat", "how to optimize windows", "how to clean windows",
        "how to remove bloat", "how to speed up windows", "how to make windows faster",
        "need help with windows", "help me debloat", "help optimize",
    ]
    if any(t in lower for t in tool_requests):
        return True

    # TIER 2: Windows problems — reply with helpful tip
    windows_problems = [
        "windows slow", "windows is slow", "pc is slow", "laptop is slow",
        "computer is slow", "pc running slow", "laptop running slow",
        "windows freezing", "windows lagging", "windows hanging",
        "high cpu", "high memory", "high ram", "100% cpu", "100% disk",
        "too many processes", "background processes", "too many services",
        "task manager", "services tab", "startup programs",
        "windows update broke", "update ruined", "forced update", "update restart",
        "fresh install slow", "clean install still slow",
        "windows 11 slow", "windows 10 slow",
        "boot time", "slow boot", "takes forever to boot",
        "windows using too much", "eating my ram", "eating my cpu",
        "why is svchost", "why is antimalware", "why is system using",
    ]
    if any(p in lower for p in windows_problems):
        return True

    # TIER 3: Windows discussions — reply if substantive
    windows_discussions = [
        "debloat", "bloatware", "remove bloat", "clean windows",
        "optimize windows", "windows optimization", "pc optimization",
        "telemetry", "windows telemetry", "windows privacy", "windows spying",
        "windows services", "disable services",
        "windows bloat", "why is windows",
        "windows is trash", "windows sucks", "hate windows",
        "game bar", "xbox game bar", "game bar recording",
        "remove cortana", "remove edge", "remove onedrive",
        "registry", "regedit", "group policy",
        "make pc faster", "make windows faster", "speed up pc",
        "timer resolution", "ndu.sys", "superfetch", "sysmain",
        "windows preinstalled", "candy crush", "preinstalled apps",
    ]
    if any(d in lower for d in windows_discussions):
        # Extra check: must look like a real person's tweet, not a brand
        personal = ["i ", "my ", "?", "just ", "why ", "how ", "anyone", "hate", "love", "finally"]
        if any(p in lower for p in personal):
            return True

    # Reject brands/bots even if they mention windows
    reject = [
        "follow me", "dm me", "check my", "subscribe",
        "giveaway", "airdrop", "crypto",
        "release notes", "changelog", "we are ",
        "introducing", "announcing", "download our",
        "google play", "app store",
    ]
    if any(r in lower for r in reject):
        return False

    return False


def gen_reply(tweet_text: str) -> str | None:
    vp = _voice()

    # GATE 0: Prompt injection / AI probe detection
    if _contains_injection(tweet_text):
        print(f"  [INJECTION] blocked: {tweet_text[:60]}...")
        return None

    # GATE 1: Is this tweet about dev/tech/windows?
    if not _is_reply_worthy(tweet_text):
        return None

    # Sanitize input before sending to LLM
    safe_text = _sanitize_input(tweet_text)

    # GATE 2: Is this specifically about Windows optimization?
    is_windows_help = any(w in safe_text.lower() for w in [
        "debloat", "optimize windows", "windows slow", "windows bloat",
        "remove bloatware", "windows services", "windows telemetry",
        "clean windows", "speed up windows", "windows optimization",
    ])

    # Detect what kind of reply is needed
    lower = tweet_text.lower()

    # TIER 1: They're asking for a tool → recommend product directly
    lower = safe_text.lower()
    is_tool_request = any(t in lower for t in [
        "best debloat", "debloat tool", "recommend", "what tool",
        "any tool", "how to debloat", "how to optimize", "how to clean",
        "how to remove bloat", "how to speed up", "help me",
    ])

    if is_tool_request:
        prompt = (
            f'someone is asking for a windows optimization tool: "{safe_text[:200]}"\n\n'
            f'recommend {_product()} ({_url()}) specifically. explain what it does in 1 sentence: '
            f'scans hardware, shows every change before applying, per-action rollback, 5mb, free. '
            f'sound helpful not salesy. under 200 chars.'
        )
    elif is_windows_help:
        prompt = (
            f'someone has a windows problem: "{safe_text[:200]}"\n\n'
            f'give a SPECIFIC tip to fix their problem. be genuinely helpful. '
            f'you can mention {_product()} ({_url()}) at the end as "or try X" but '
            f'the tip must be useful on its own. under 200 chars.'
        )
    elif _roastable(safe_text):
        prompt = (
            f'someone has a bad take about windows: "{safe_text[:200]}"\n\n'
            f'correct them with facts. be direct not mean. under 180 chars.'
        )
    else:
        prompt = (
            f'someone tweeted about windows: "{safe_text[:200]}"\n\n'
            f'reply with something specific and useful about the topic they mentioned. '
            f'do NOT mention any product unless they are explicitly asking for one. '
            f'just share knowledge. under 180 chars.'
        )

    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 10 or len(text) > 280:
        return None

    # GATE 5: Output AI leak detection — never reveal AI nature
    if _output_leaks_ai(text):
        print(f"  [AI-LEAK] blocked output: {text[:60]}...")
        return None

    # GATE 4: Hard reject spam/AI patterns in output
    text_lower = text.lower()
    spam_patterns = [
        "kills 220", "kills 280", "blocks 70", "280 services",
        "220 services", "70 telemetry", "70 endpoints",
        "github.com/", f"{_product()} kills", f"{_product()} blocks",
        f"{_product()} does this", f"{_product()} fixes", f"{_product()} can",
        f"check out {_product()}", f"try {_product()}",
        "here's why", "did you know", "introducing",
        "as a developer", "in my experience",
    ]
    if any(p.lower() in text_lower for p in spam_patterns):
        return None

    # If product mentioned but tweet wasn't about windows help → reject
    product_lower = _product().lower()
    url_lower = _url().lower()
    if not is_windows_help and (product_lower in text_lower or url_lower in text_lower):
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
    # Safety check for quotes (public visibility)
    safe, _ = _check_quality(text)
    if not safe:
        return None
    return text


def gen_mention_reply(mention: str) -> str | None:
    if _spam(mention):
        return None

    # Injection defense
    if _contains_injection(mention):
        print(f"  [INJECTION] blocked mention: {mention[:60]}...")
        return None

    safe_mention = _sanitize_input(mention)
    vp = _voice()

    # Special handling for AI accusation — deflect naturally
    is_ai_probe = any(p in mention.lower() for p in [
        "are you a bot", "are you ai", "are you an ai",
        "bot account", "automated", "you are a bot",
        "chatgpt", "you sound like ai", "ai generated",
    ])

    if is_ai_probe:
        return _deflect_ai_probe()

    prompt = (
        f'someone replied to our tweet: "{safe_mention[:150]}"\n\n'
        f'reply naturally. helpful if question, casual thanks if praise, '
        f'roast back if trolling. under 180 chars. no quotes.'
    )
    text = llm.generate(prompt, system=vp).strip().strip('"\'')
    if not text or len(text) < 5 or len(text) > 280:
        return None

    # Output safety + AI leak check
    safe, _ = _check_quality(text)
    if not safe:
        return None
    if _output_leaks_ai(text):
        print(f"  [AI-LEAK] blocked mention reply: {text[:60]}...")
        return None

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
    if not _safe_and_viral(parts[0]):
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
    _atomic_write(ANALYTICS_PATH, json.dumps(data, indent=2))


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

def _recent_tweet_texts(log: dict, days: int = 1) -> set[str]:
    """Get recent tweet texts to avoid repetition."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    texts = set()
    for t in log.get("tweets", []):
        if t.get("date", "") >= cutoff:
            texts.add(t.get("text", "")[:50].lower())
    return texts


def run_cycle_http() -> dict:
    """Full cycle using only HTTP API (curl_cffi). No browser needed."""
    from modules.http_twitter import HttpTwitter
    from modules.config import reload as reload_config

    # Hot-reload config each cycle
    reload_config()

    log = _load_log()
    stats = {"tweets": 0, "replies": 0, "likes": 0, "retweets": 0}
    api = HttpTwitter()  # single instance for entire cycle (dedup works!)
    recent_texts = _recent_tweet_texts(log)

    # Fetch timeline ONCE, reuse for all activities
    timeline = api.home_timeline(30)
    print(f"  timeline: {len(timeline)} tweets")

    # Release check
    new_rel = _new_release(log)
    if new_rel and can_tweet(log) and api.can_post:
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

    # Activities — more variety, limit-aware
    if is_peak_hour():
        activities = ["tweet", "like", "like", "reply", "reply", "reply", "like", "retweet", "follow", "reply_mentions", "quote", "conversations", "performance"]
    elif is_dead_hour():
        activities = ["like", "like", "performance"]
    else:
        activities = ["tweet", "like", "like", "reply", "reply", "like", "follow", "quote", "conversations"]

    # If daily limit hit, only do likes, follows, and performance tracking
    if not api.can_post:
        activities = ["like", "like", "like", "follow", "performance"]

    random.shuffle(activities)

    for activity in activities:
        try:
            if activity == "tweet" and can_tweet(log) and api.can_post:
                text = gen_tweet()
                if text:
                    # Dedup — don't repeat same topic
                    if text[:50].lower() in recent_texts:
                        print(f"  [tweet] SKIP duplicate topic")
                        continue
                    print(f"  [tweet] {text[:60]}...")
                    tid = api.create_tweet(text)
                    if tid:
                        log.setdefault("tweets", []).append({"date": datetime.now().isoformat(), "text": text[:200], "id": tid})
                        stats["tweets"] += 1
                        track_action("tweet")
                        recent_texts.add(text[:50].lower())
                        print(f"  [tweet] POSTED {tid}")
                        webhook = _cfg().get("discord_webhook", "")
                        if webhook:
                            api.send_webhook(f"Tweet posted: {text[:100]}", webhook)

            elif activity == "like" and can_like(log):
                tweets = timeline
                for t in tweets:
                    if not can_like(log):
                        break
                    if api.already_engaged(t["id"]):
                        continue
                    if not _relevant(t["text"]):
                        continue
                    try:
                        if api.like(t["id"]):
                            log.setdefault("likes", []).append({"date": datetime.now().isoformat(), "tid": t["id"], "user": t.get("user", "")})
                            stats["likes"] += 1
                            track_action("like")
                            print(f"  [like] @{t['user']}: {t['text'][:50]}...")
                    except Exception:
                        pass
                    time.sleep(random.uniform(2, 6))

            elif activity == "reply" and can_reply(log) and api.can_post:
                ranked = _sort_by_engagement(timeline)
                for t in ranked:
                    if not can_reply(log) or not api.can_post:
                        break
                    if api.already_engaged(t["id"]):
                        continue
                    if api.is_blacklisted(t.get("user", "")):
                        continue
                    if not _can_reply_to_user(t.get("user", "")):
                        continue
                    if not t.get("user") or not t.get("id"):
                        continue
                    # ONLY reply to Windows-specific tweets. Nothing else.
                    if not _is_reply_worthy(t["text"]):
                        continue
                    reply = gen_reply(t["text"])
                    if reply:
                        try:
                            score = _score_tweet(t)
                            print(f"  [reply] to @{t['user']} (score:{score}, {t.get('followers',0)} followers): {reply[:60]}...")
                            rid = api.create_tweet(reply, reply_to=t["id"])
                            if rid:
                                log.setdefault("replies", []).append({
                                    "date": datetime.now().isoformat(),
                                    "to": t["text"][:100], "r": reply[:200],
                                    "user": t["user"], "id": rid,
                                    "score": score, "followers": t.get("followers", 0),
                                })
                                stats["replies"] += 1
                                track_action("reply")
                                api.mark_engaged(t["id"])
                                _mark_replied_user(t["user"])
                                print(f"  [reply] POSTED {rid}")

                                # Webhook notification
                                webhook = _cfg().get("discord_webhook", "")
                                if webhook:
                                    api.send_webhook(f"Reply posted to @{t['user']}: {reply[:100]}", webhook)
                        except Exception as exc:
                            print(f"  [reply] error: {exc}")
                        time.sleep(random.uniform(10, 25))
                        break

            elif activity == "quote" and can_quote(log) and api.can_post:
                ranked = _sort_by_engagement(timeline)
                for t in ranked:
                    if api.already_engaged(t["id"]):
                        continue
                    if not _quotable(t["text"]):
                        continue
                    if t.get("likes", 0) < 5:
                        continue
                    comment = gen_quote(t["text"])
                    if comment:
                        try:
                            print(f"  [quote] @{t['user']}: {comment[:60]}...")
                            qid = api.quote_tweet(t["id"], comment)
                            if qid:
                                log.setdefault("quotes", []).append({
                                    "date": datetime.now().isoformat(),
                                    "orig": t["text"][:100], "comment": comment[:200],
                                    "user": t.get("user", ""), "id": qid,
                                })
                                stats["quotes"] = stats.get("quotes", 0) + 1
                                track_action("quote")
                                print(f"  [quote] POSTED {qid}")
                        except Exception as exc:
                            print(f"  [quote] error: {exc}")
                        break

            elif activity == "retweet" and api.can_post:
                tweets = timeline
                for t in tweets:
                    if api.already_engaged(t["id"]):
                        continue
                    if not _relevant(t["text"]):
                        continue
                    if t.get("likes", 0) < 10:
                        continue
                    try:
                        if api.retweet(t["id"]):
                            stats["retweets"] += 1
                            track_action("retweet")
                            print(f"  [rt] @{t['user']}: {t['text'][:50]}...")
                    except Exception:
                        pass
                    break

            elif activity == "follow":
                followed = 0
                for t in timeline:
                    if followed >= 2:
                        break
                    if not _relevant(t["text"]):
                        continue
                    if not t.get("user_id"):
                        continue
                    if t.get("followers", 0) < 100 or t.get("followers", 0) > 100000:
                        continue
                    if api.already_engaged(f"follow_{t['user_id']}"):
                        continue
                    if api.is_blacklisted(t.get("user", "")):
                        continue
                    try:
                        if api.follow(t["user_id"]):
                            followed += 1
                            track_action("follow")
                            print(f"  [follow] @{t['user']} ({t.get('followers', 0)} followers)")
                    except Exception:
                        pass
                    time.sleep(random.uniform(3, 8))

            elif activity == "conversations" and api.can_post:
                try:
                    conv_count = continue_conversations(api, log)
                    if conv_count:
                        stats["replies"] += conv_count
                        print(f"  [convo] continued {conv_count} conversations")
                except Exception as exc:
                    print(f"  [convo] error: {exc}")

            elif activity == "performance":
                try:
                    perf_stats = track_tweet_performance(api)
                    if perf_stats["checked"]:
                        print(f"  [perf] checked {perf_stats['checked']} tweets, {perf_stats['total_likes']} total likes")
                    if perf_stats["flops"]:
                        print(f"  [perf] {len(perf_stats['flops'])} flop tweets detected")
                        # Auto-delete flops (optional, controlled by config)
                        if _cfg().get("auto_delete_flops", False):
                            for flop_id in perf_stats["flops"][:2]:
                                try:
                                    if api.delete_tweet(flop_id):
                                        print(f"  [perf] deleted flop {flop_id}")
                                except Exception:
                                    pass
                except Exception as exc:
                    print(f"  [perf] error: {exc}")

            elif activity == "reply_mentions" and api.can_post:
                # Reply to people who mentioned us (NOT ourselves)
                notifs = api.notifications()
                my_user = api.get_me().get("username", "").lower()
                for n in notifs[:5]:
                    if not can_reply(log) or not api.can_post:
                        break
                    # Skip our own tweets in notifications
                    if n.get("user", "").lower() == my_user:
                        continue
                    if _spam(n["text"]) or api.already_engaged(n["id"]):
                        continue
                    reply = gen_mention_reply(n["text"])
                    if reply:
                        try:
                            print(f"  [mention-reply] to @{n['user']}: {reply[:60]}...")
                            rid = api.create_tweet(reply, reply_to=n["id"])
                            if rid:
                                log.setdefault("replies", []).append({"date": datetime.now().isoformat(), "to": n["text"][:100], "r": reply[:200], "user": n["user"], "src": "mention"})
                                stats["replies"] += 1
                                track_action("reply")
                                api.mark_engaged(n["id"])
                                print(f"  [mention-reply] POSTED {rid}")
                        except Exception as exc:
                            print(f"  [mention-reply] error: {exc}")
                        time.sleep(random.uniform(10, 20))
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
