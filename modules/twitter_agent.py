"""Autonomous Twitter agent for oudenOS promotion.

Runs 24/7 on VDS via PM2. Uses Playwright for all Twitter interactions.
Dual-LLM: Qwen + Gemini for varied content. Anti-ban rate limiting.

Safety rules:
- NEVER post anything embarrassing or wrong about OS/optimization topics
- NEVER engage on topics where we're not 100% sure of facts
- NEVER sound like AI. If in doubt, don't post.
- Bot/spam replies get ignored
- Every tweet/reply goes through virality + safety check before posting
"""
from __future__ import annotations

import json
import random
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from modules.config import ROOT
from modules import llm

AGENT_LOG = ROOT / "agent_log.json"
VOICE_PATH = ROOT / "voice_profile.json"
RELEASE_CACHE = ROOT / "latest_release.json"

# Rate limits (aggressive but safe for verified accounts)
MAX_TWEETS_PER_DAY = 25
MAX_REPLIES_PER_DAY = 80
MAX_LIKES_PER_DAY = 150
MAX_QUOTE_TWEETS_PER_DAY = 10
MIN_TWEET_INTERVAL_MINUTES = 20
MIN_REPLY_INTERVAL_MINUTES = 3
MIN_LIKE_INTERVAL_SECONDS = 12
MIN_QUOTE_INTERVAL_MINUTES = 30


# ─── Logging & rate limits ────────────────────────────────────────

def _load_log() -> dict:
    if AGENT_LOG.exists():
        return json.loads(AGENT_LOG.read_text())
    return {"tweets": [], "replies": [], "likes": [], "quotes": [], "skipped": []}


def _save_log(log: dict):
    # Keep log from growing forever - trim to last 7 days
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    for key in ["tweets", "replies", "likes", "quotes", "skipped"]:
        items = log.get(key, [])
        log[key] = [e for e in items if e.get("date", "") >= cutoff]
    AGENT_LOG.write_text(json.dumps(log, indent=2))


def _today_count(log: dict, key: str) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for e in log.get(key, []) if e.get("date", "").startswith(today))


def _last_action_time(log: dict, key: str) -> datetime | None:
    items = log.get(key, [])
    if not items:
        return None
    try:
        return datetime.fromisoformat(items[-1]["date"])
    except (KeyError, ValueError):
        return None


def _can_tweet(log: dict) -> bool:
    if _today_count(log, "tweets") >= MAX_TWEETS_PER_DAY:
        return False
    last = _last_action_time(log, "tweets")
    if last and datetime.now() - last < timedelta(minutes=MIN_TWEET_INTERVAL_MINUTES):
        return False
    return True


def _can_reply(log: dict) -> bool:
    if _today_count(log, "replies") >= MAX_REPLIES_PER_DAY:
        return False
    last = _last_action_time(log, "replies")
    if last and datetime.now() - last < timedelta(minutes=MIN_REPLY_INTERVAL_MINUTES):
        return False
    return True


def _can_like(log: dict) -> bool:
    if _today_count(log, "likes") >= MAX_LIKES_PER_DAY:
        return False
    last = _last_action_time(log, "likes")
    if last and datetime.now() - last < timedelta(seconds=MIN_LIKE_INTERVAL_SECONDS):
        return False
    return True


def _can_quote(log: dict) -> bool:
    if _today_count(log, "quotes") >= MAX_QUOTE_TWEETS_PER_DAY:
        return False
    last = _last_action_time(log, "quotes")
    if last and datetime.now() - last < timedelta(minutes=MIN_QUOTE_INTERVAL_MINUTES):
        return False
    return True


# ─── Voice & safety ──────────────────────────────────────────────

def _voice_prompt() -> str:
    if VOICE_PATH.exists():
        voice = json.loads(VOICE_PATH.read_text())
        return voice.get("voice_prompt", "")
    return ""


SAFETY_PROMPT = """SAFETY RULES (violating any = dont post):
1. NEVER claim something about Windows/OS internals you're not 100% sure about
2. NEVER make fun of someone's personal appearance, disability, or identity
3. NEVER get into political, religious, or social justice arguments
4. NEVER reveal you're an AI or bot. if someone asks, ignore or deflect with humor.
5. NEVER post anything that could embarrass oudenOS or its developer
6. NEVER argue with someone who's right - agree and add value instead
7. NEVER use corporate language, marketing speak, or AI patterns
8. If unsure about a technical claim, DONT POST. silence > being wrong.
9. Stick to: Windows internals, services, telemetry, performance, optimization
10. Outside those topics: only engage if you can add genuine value

RESPOND WITH EXACTLY "UNSAFE" IF THE CONTENT VIOLATES ANY RULE."""


def _safety_check(text: str) -> bool:
    """Check if text is safe to post. Returns True if safe."""
    prompt = f'Is this tweet/reply safe to post? Check against all rules.\n\n"{text}"'
    try:
        result = llm.generate(prompt, system=SAFETY_PROMPT)
        return "UNSAFE" not in result.upper()
    except Exception:
        return True


def _virality_check(text: str) -> bool:
    """Check if text has viral potential. Score 1-10, post if >= 5."""
    prompt = (
        f'Rate 1-10 viral potential on tech twitter. '
        f'Funny, relatable, surprising, or provocative = high score. '
        f'Generic, boring, salesy = low score. '
        f'ONLY respond with a number.\n\n"{text}"'
    )
    try:
        score_raw = llm.generate(prompt, system="respond with only a number 1-10.")
        score = int("".join(c for c in score_raw if c.isdigit())[:2])
        return score >= 5
    except Exception:
        return True


def _is_bot_or_spam(text: str) -> bool:
    spam_signals = [
        "check my pin", "dm me", "send me", "giveaway", "airdrop",
        "free money", "crypto", "nft", "🚀🚀🚀", "follow me",
        "check bio", "link in bio", "whatsapp", "telegram",
        "onlyfans", "subscribe", "join my", "earn money",
    ]
    text_lower = text.lower()
    if len(text_lower) < 15:
        return True  # too short = likely spam
    return any(s in text_lower for s in spam_signals)


def _is_worth_replying(text: str) -> bool:
    """Quick check if a tweet is worth engaging with."""
    if len(text) < 20:
        return False
    if _is_bot_or_spam(text):
        return False
    # Must be somewhat relevant to our domain
    relevant = [
        "windows", "optimize", "debloat", "telemetry", "privacy",
        "performance", "bloat", "services", "ram", "cpu", "gpu",
        "fps", "gaming", "pc", "microsoft", "update", "slow",
        "linux", "open source", "rust", "tool",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in relevant)


def _should_roast(text: str) -> bool:
    roast_triggers = [
        "debloat script", "bat file", "powershell debloat",
        "windows is fine", "telemetry is necessary",
        "just reinstall", "windows is fast", "game bar is useful",
        "200 fps", "free fps", "make windows faster",
        "dont need to optimize", "optimization is snake oil",
        "windows doesnt spy", "microsoft respects privacy",
    ]
    text_lower = text.lower()
    return any(t in text_lower for t in roast_triggers)


def _should_quote_tweet(text: str) -> bool:
    """Check if a tweet is worth quote-tweeting (roastable or agreeable hot take)."""
    quote_worthy = [
        "debloat", "windows slow", "telemetry", "bloatware",
        "windows services", "game bar", "windows update",
        "microsoft spying", "windows privacy", "pc optimization",
        "fresh install slow", "ram usage", "task manager",
    ]
    text_lower = text.lower()
    return any(t in text_lower for t in quote_worthy) and len(text) > 30


# ─── Release checking ────────────────────────────────────────────

def check_latest_release() -> dict | None:
    """Fetch latest oudenOS release from GitHub. Cache for 1 hour."""
    if RELEASE_CACHE.exists():
        cached = json.loads(RELEASE_CACHE.read_text())
        cached_at = cached.get("_cached_at", "")
        if cached_at:
            try:
                age = datetime.now() - datetime.fromisoformat(cached_at)
                if age < timedelta(hours=1):
                    return cached
            except ValueError:
                pass

    try:
        import httpx
        r = httpx.get(
            "https://api.github.com/repos/redpersongpt/oudenOS/releases/latest",
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            release = {
                "tag": data.get("tag_name", ""),
                "name": data.get("name", ""),
                "body": data.get("body", ""),
                "url": data.get("html_url", ""),
                "date": data.get("published_at", ""),
                "_cached_at": datetime.now().isoformat(),
            }
            RELEASE_CACHE.write_text(json.dumps(release, indent=2))
            return release
    except Exception:
        pass
    return None


def _release_tweet_needed(log: dict) -> str | None:
    """Check if there's a new release we haven't tweeted about."""
    release = check_latest_release()
    if not release or not release.get("tag"):
        return None

    tag = release["tag"]
    # Check if we already tweeted about this version
    for tweet in log.get("tweets", []):
        if tag in tweet.get("text", ""):
            return None

    return tag


# ─── Content generation ──────────────────────────────────────────

TWEET_TOPICS = [
    "windows default timer resolution is 15.6ms from 2001",
    "game bar records your screen by default eating gpu",
    "ndu.sys memory leak since 2018 microsoft wont fix",
    "RetailDemo service turns pc into best buy kiosk",
    "280 services on fresh windows you need 60",
    "70+ telemetry endpoints on first boot",
    "MapsBroker downloads offline maps on a desktop in 2026",
    "VBS/HVCI costs 5-15% cpu microsoft doesnt mention",
    "start menu suggestions are literally ads",
    "windows update restarts mid-work like it owns your pc",
    "oudenOS scans hardware before changing anything unlike random scripts",
    "oudenOS is 5mb. windows wastes 20gb on stuff you didnt ask for",
    "oudenOS has per-action rollback. bat files have prayer",
    "$0.99 one-time for deep tuning. no subscription. not a typo.",
    "windows ships with a service for fax machines. in 2026.",
    "your pc came with candy crush preinstalled on a $2000 machine",
    "SysMain prefetches apps to ram you never use on an nvme drive",
    "windows search indexes your entire disk so cortana can be 0.2s faster",
]

SEARCH_QUERIES = [
    "Windows slow", "debloat Windows", "Windows 11 bloat",
    "Windows telemetry", "PC optimization", "Windows services",
    "game bar fps", "Windows privacy", "Windows update annoying",
    "remove bloatware", "Windows RAM usage", "fresh Windows install slow",
    "Windows optimization tool", "Windows debloat tool",
    "make PC faster", "Windows 11 privacy", "Windows background processes",
    "task manager high cpu", "Windows high memory usage",
]


def generate_tweet(release_tag: str | None = None) -> str | None:
    vp = _voice_prompt()

    if release_tag:
        prompt = (
            f"oudenOS {release_tag} just dropped. write a tweet announcing it. "
            f"mention what oudenOS does (5mb, scans hardware, 280 services, rollback, open source). "
            f"include ouden.cc?v=2. under 270 chars. just the tweet."
        )
    else:
        topic = random.choice(TWEET_TOPICS)
        prompt = (
            f"write one tweet about: {topic}. "
            f"include ouden.cc?v=2. under 270 chars. "
            f"just the tweet text, nothing else. no quotes."
        )

    text = llm.generate(prompt, system=vp).strip().strip('"').strip("'")

    if len(text) > 280:
        text = text[:277]
    if not text or len(text) < 30:
        return None
    if not _safety_check(text):
        return None
    if not _virality_check(text):
        return None
    return text


def generate_reply(tweet_text: str) -> str | None:
    vp = _voice_prompt()

    if _should_roast(tweet_text):
        prompt = (
            f'someone tweeted: "{tweet_text}"\n\n'
            f"roast them with FACTS. only use windows facts you are 100% sure about. "
            f"if oudenOS is relevant mention it casually. "
            f"under 200 chars. just the reply. no quotes."
        )
    else:
        prompt = (
            f'someone tweeted: "{tweet_text}"\n\n'
            f"write a helpful casual reply. if oudenOS is relevant mention ouden.cc. "
            f"if not relevant dont force it. be genuinely helpful. "
            f"under 200 chars. just the reply. no quotes."
        )

    text = llm.generate(prompt, system=vp).strip().strip('"').strip("'")
    if not text or len(text) < 10 or len(text) > 280:
        return None
    if not _safety_check(text):
        return None
    if not _virality_check(text):
        return None
    return text


def generate_quote_tweet(original_text: str) -> str | None:
    """Generate a quote tweet comment."""
    vp = _voice_prompt()
    prompt = (
        f'quote tweet this: "{original_text}"\n\n'
        f"add your take. can be a roast, agreement, or adding context. "
        f"use real facts. mention oudenOS ONLY if it genuinely fits. "
        f"under 250 chars. just your comment. no quotes."
    )
    text = llm.generate(prompt, system=vp).strip().strip('"').strip("'")
    if not text or len(text) < 15 or len(text) > 280:
        return None
    if not _safety_check(text):
        return None
    if not _virality_check(text):
        return None
    return text


def generate_reply_to_mention(mention_text: str) -> str | None:
    vp = _voice_prompt()
    if _is_bot_or_spam(mention_text):
        return None

    prompt = (
        f'someone replied to our tweet: "{mention_text}"\n\n'
        f"reply naturally. helpful if real question. casual thanks if praise. "
        f"roast back with facts if trolling. NEVER be defensive or corporate. "
        f"if they say its AI or bot, deflect with humor dont confirm or deny. "
        f"under 180 chars. just the reply. no quotes."
    )
    text = llm.generate(prompt, system=vp).strip().strip('"').strip("'")
    if not text or len(text) < 5 or len(text) > 280:
        return None
    if not _safety_check(text):
        return None
    return text


# ─── Playwright UI helpers ────────────────────────────────────────

def _post_tweet_ui(page, text: str) -> bool:
    page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25000)
    time.sleep(3)
    compose = page.locator('[data-testid="tweetTextarea_0"]').first
    compose.click()
    time.sleep(0.5)
    for idx, line in enumerate(text.split("\n")):
        if idx > 0:
            page.keyboard.press("Enter")
        if line.strip():
            page.keyboard.type(line, delay=random.randint(8, 18))
    time.sleep(2)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(4)
    return True


def _reply_tweet_ui(page, tweet_article, text: str) -> bool:
    tweet_article.locator('[data-testid="reply"]').first.click()
    time.sleep(2)
    compose = page.locator('[data-testid="tweetTextarea_0"]').first
    compose.click()
    time.sleep(0.3)
    page.keyboard.type(text, delay=random.randint(8, 15))
    time.sleep(1)
    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(3)
    return True


def _like_tweet_ui(tweet_article) -> bool:
    btn = tweet_article.locator('[data-testid="like"]').first
    if btn.count() > 0:
        btn.click()
        time.sleep(random.uniform(1, 3))
        return True
    return False


def _quote_tweet_ui(page, tweet_article, comment: str) -> bool:
    """Quote tweet via UI: click retweet menu -> Quote, then type comment."""
    # Click the retweet button to open menu
    rt_btn = tweet_article.locator('[data-testid="retweet"]').first
    if rt_btn.count() == 0:
        return False
    rt_btn.click()
    time.sleep(1.5)

    # Click "Quote" from the dropdown
    quote_option = page.locator('[data-testid="Dropdown"]').locator("text=Quote")
    if quote_option.count() == 0:
        # Try alternative selectors
        quote_option = page.get_by_role("menuitem").filter(has_text="Quote")
    if quote_option.count() == 0:
        page.keyboard.press("Escape")
        return False

    quote_option.click()
    time.sleep(2)

    # Type the quote comment
    compose = page.locator('[data-testid="tweetTextarea_0"]').first
    compose.click()
    time.sleep(0.3)
    page.keyboard.type(comment, delay=random.randint(8, 15))
    time.sleep(1)

    page.locator('[data-testid="tweetButton"]').click()
    time.sleep(4)
    return True


def _get_tweet_url(tweet_article) -> str:
    """Extract tweet URL from article for logging."""
    links = tweet_article.locator('a[href*="/status/"]')
    for j in range(links.count()):
        href = links.nth(j).get_attribute("href") or ""
        if "/status/" in href:
            return f"https://x.com{href}"
    return ""


# ─── Main agent loop ─────────────────────────────────────────────

def run_cycle(page) -> dict:
    log = _load_log()
    stats = {"tweets": 0, "replies": 0, "likes": 0, "quotes": 0, "skipped": 0}

    # Check for new release first
    new_release = _release_tweet_needed(log)
    if new_release and _can_tweet(log):
        try:
            result = _do_release_tweet(page, log, new_release)
            stats["tweets"] += result
        except Exception as exc:
            print(f"  [release] error: {exc}")
        time.sleep(random.uniform(10, 20))

    # Randomize activity order for natural behavior
    activities = [
        "tweet", "engage", "engage",  # engage twice for more replies
        "reply_mentions", "browse_like", "quote_engage",
    ]
    random.shuffle(activities)

    for activity in activities:
        try:
            if activity == "tweet" and _can_tweet(log):
                result = _do_tweet(page, log)
                stats["tweets"] += result

            elif activity == "engage" and _can_reply(log):
                result = _do_engage(page, log)
                stats["replies"] += result

            elif activity == "reply_mentions" and _can_reply(log):
                result = _do_reply_mentions(page, log)
                stats["replies"] += result

            elif activity == "browse_like" and _can_like(log):
                result = _do_browse_like(page, log)
                stats["likes"] += result

            elif activity == "quote_engage" and _can_quote(log):
                result = _do_quote_engage(page, log)
                stats["quotes"] += result

        except Exception as exc:
            print(f"  [{activity}] error: {exc}")

        time.sleep(random.uniform(8, 25))

    _save_log(log)
    return stats


def _do_release_tweet(page, log: dict, tag: str) -> int:
    text = generate_tweet(release_tag=tag)
    if not text:
        return 0
    print(f"  [release] posting {tag}: {text[:60]}...")
    _post_tweet_ui(page, text)
    log.setdefault("tweets", []).append({
        "date": datetime.now().isoformat(), "text": text[:200], "type": "release"
    })
    return 1


def _do_tweet(page, log: dict) -> int:
    text = generate_tweet()
    if not text:
        log.setdefault("skipped", []).append({
            "date": datetime.now().isoformat(), "reason": "failed_gen_or_safety"
        })
        return 0
    print(f"  [tweet] posting: {text[:60]}...")
    _post_tweet_ui(page, text)
    log.setdefault("tweets", []).append({
        "date": datetime.now().isoformat(), "text": text[:200]
    })
    return 1


def _do_engage(page, log: dict) -> int:
    query = random.choice(SEARCH_QUERIES)
    print(f"  [engage] searching: {query}")

    page.goto(
        f"https://x.com/search?q={query}&src=typed_query&f=live",
        wait_until="domcontentloaded", timeout=25000,
    )
    time.sleep(4)

    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    if count < 2:
        return 0

    replied = 0
    for i in range(min(10, count)):
        if not _can_reply(log) and not _can_like(log):
            break

        article = articles.nth(i)
        text_el = article.locator('[data-testid="tweetText"]').first
        if text_el.count() == 0:
            continue
        tweet_text = text_el.inner_text()

        if not _is_worth_replying(tweet_text):
            continue

        # Like relevant tweets
        if _can_like(log):
            try:
                _like_tweet_ui(article)
                log.setdefault("likes", []).append({
                    "date": datetime.now().isoformat(), "query": query
                })
            except Exception:
                pass

        # Reply (70% chance for relevant tweets)
        if _can_reply(log) and random.random() < 0.70:
            reply = generate_reply(tweet_text)
            if reply:
                try:
                    print(f"  [engage] replying: {reply[:60]}...")
                    _reply_tweet_ui(page, article, reply)
                    log.setdefault("replies", []).append({
                        "date": datetime.now().isoformat(),
                        "to_text": tweet_text[:100],
                        "reply": reply[:200],
                    })
                    replied += 1
                except Exception:
                    pass

        time.sleep(random.uniform(4, 12))

    return replied


def _do_reply_mentions(page, log: dict) -> int:
    print("  [mentions] checking...")
    page.goto("https://x.com/notifications/mentions", wait_until="domcontentloaded", timeout=25000)
    time.sleep(4)

    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    if count == 0:
        return 0

    replied = 0
    for i in range(min(8, count)):
        if not _can_reply(log):
            break

        article = articles.nth(i)
        text_el = article.locator('[data-testid="tweetText"]').first
        if text_el.count() == 0:
            continue
        mention_text = text_el.inner_text()

        if _is_bot_or_spam(mention_text):
            continue

        reply = generate_reply_to_mention(mention_text)
        if reply:
            try:
                print(f"  [mentions] replying: {reply[:60]}...")
                _reply_tweet_ui(page, article, reply)
                log.setdefault("replies", []).append({
                    "date": datetime.now().isoformat(),
                    "to_text": mention_text[:100],
                    "reply": reply[:200],
                    "source": "mention",
                })
                replied += 1
            except Exception:
                pass

        time.sleep(random.uniform(8, 18))

    return replied


def _do_browse_like(page, log: dict) -> int:
    print("  [browse] timeline...")
    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
    time.sleep(4)

    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    liked = 0

    relevant_keywords = [
        "windows", "optimize", "debloat", "telemetry", "privacy",
        "performance", "open source", "rust", "developer", "pc",
        "gaming", "fps", "ram", "cpu", "gpu", "linux", "microsoft",
        "bloat", "services", "update", "tool",
    ]

    for i in range(min(20, count)):
        if not _can_like(log):
            break

        article = articles.nth(i)
        text_el = article.locator('[data-testid="tweetText"]').first
        if text_el.count() == 0:
            continue
        tweet_text = text_el.inner_text().lower()

        if any(kw in tweet_text for kw in relevant_keywords):
            try:
                _like_tweet_ui(article)
                log.setdefault("likes", []).append({
                    "date": datetime.now().isoformat(), "source": "timeline"
                })
                liked += 1
            except Exception:
                pass
            time.sleep(random.uniform(2, 5))

    return liked


def _do_quote_engage(page, log: dict) -> int:
    """Find tweets worth quote-tweeting and add our take."""
    query = random.choice(["Windows bloat", "debloat Windows", "Windows telemetry", "PC optimization", "Windows slow"])
    print(f"  [quote] searching: {query}")

    page.goto(
        f"https://x.com/search?q={query}&src=typed_query&f=top",
        wait_until="domcontentloaded", timeout=25000,
    )
    time.sleep(4)

    articles = page.locator('article[data-testid="tweet"]')
    count = articles.count()
    if count < 3:
        return 0

    quoted = 0
    # Pick from top tweets (more visibility)
    candidates = list(range(min(8, count)))
    random.shuffle(candidates)

    for i in candidates[:4]:
        if not _can_quote(log):
            break

        article = articles.nth(i)
        text_el = article.locator('[data-testid="tweetText"]').first
        if text_el.count() == 0:
            continue
        tweet_text = text_el.inner_text()

        if not _should_quote_tweet(tweet_text):
            continue

        comment = generate_quote_tweet(tweet_text)
        if comment:
            try:
                print(f"  [quote] quoting: {comment[:60]}...")
                success = _quote_tweet_ui(page, article, comment)
                if success:
                    log.setdefault("quotes", []).append({
                        "date": datetime.now().isoformat(),
                        "original": tweet_text[:100],
                        "comment": comment[:200],
                    })
                    quoted += 1
            except Exception as exc:
                print(f"  [quote] failed: {exc}")

        time.sleep(random.uniform(10, 25))
        break  # max 1 quote per cycle to stay natural

    return quoted
