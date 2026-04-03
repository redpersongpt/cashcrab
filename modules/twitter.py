from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import tweepy

from modules.config import ROOT, section
from modules import llm, ui
from modules.auth import twitter_access_token, twitter_auth_mode

QUEUE_PATH = ROOT / "twitter_queue.json"

WORKFLOW_PRESETS = {
    "authority": [
        {
            "kind": "organic",
            "label": "Sharp take",
            "prompt": "Write a sharp operator take about {topic}. Make it feel earned, useful, and punchy.",
        },
        {
            "kind": "organic",
            "label": "Tactical tip",
            "prompt": "Write one tactical X post about {topic}. Give a concrete move people can use today.",
        },
        {
            "kind": "organic",
            "label": "Proof post",
            "prompt": "Write a short proof-driven post about {topic}. Mention a believable result or before/after shift without sounding fake.",
        },
    ],
    "launch": [
        {
            "kind": "organic",
            "label": "Tease",
            "prompt": "Write a teaser post for {topic}. Build curiosity without explaining everything.",
        },
        {
            "kind": "organic",
            "label": "Problem",
            "prompt": "Write a post that names the painful problem around {topic}. Keep it direct and specific.",
        },
        {
            "kind": "organic",
            "label": "Offer",
            "prompt": "Write a launch post for {topic}. Explain what is live now and why it matters.",
        },
        {
            "kind": "organic",
            "label": "CTA",
            "prompt": "Write a clean call-to-action post for {topic}. Make the next step obvious without sounding needy.",
        },
    ],
    "affiliate": [
        {
            "kind": "affiliate",
            "label": "Story angle",
            "prompt": "Create an affiliate-friendly post angle for {topic}. It should read like a useful recommendation, not an ad.",
        },
        {
            "kind": "affiliate",
            "label": "Proof angle",
            "prompt": "Create a proof-based affiliate post angle for {topic}. Show why the product is worth attention.",
        },
        {
            "kind": "affiliate",
            "label": "CTA angle",
            "prompt": "Create a CTA-driven affiliate post angle for {topic}. Keep it direct, short, and honest.",
        },
    ],
    "engagement": [
        {
            "kind": "organic",
            "label": "Debate starter",
            "prompt": "Write a debate-starting post about {topic}. It should invite replies without being stupid bait.",
        },
        {
            "kind": "organic",
            "label": "Question",
            "prompt": "Write a smart question post about {topic}. Make good people want to answer.",
        },
        {
            "kind": "organic",
            "label": "Reply bait",
            "prompt": "Write a concise post about {topic} that invites examples, opinions, or disagreement.",
        },
    ],
}


def _client():
    mode = twitter_auth_mode()
    if mode == "cookie":
        from modules.twikit_client import CookieTwitterClient
        return CookieTwitterClient()
    token = twitter_access_token()
    return tweepy.Client(access_token=token)


def _queue_payload() -> dict:
    return {"items": []}


def _load_queue() -> dict:
    if QUEUE_PATH.exists():
        payload = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload
    return _queue_payload()


def _save_queue(payload: dict) -> dict:
    QUEUE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_text(text: str, limit: int = 280) -> str:
    compact = re.sub(r"\s+", " ", (text or "")).strip()
    return compact[:limit]


def _new_queue_id() -> str:
    return f"twq-{uuid4().hex[:10]}"


def workflow_presets() -> list[str]:
    return list(WORKFLOW_PRESETS)


def queue_tweet(
    text: str,
    tweet_type: str = "organic",
    workflow: str = "manual",
    topic: str = "",
    scheduled_for: str | None = None,
    source: str = "manual",
) -> dict:
    normalized = _normalize_text(text)
    if not normalized:
        raise RuntimeError("Tweet text is empty.")

    payload = _load_queue()
    item = {
        "id": _new_queue_id(),
        "text": normalized,
        "type": tweet_type,
        "workflow": workflow,
        "topic": topic,
        "source": source,
        "status": "queued",
        "created_at": _now_iso(),
        "scheduled_for": scheduled_for or "",
        "posted_at": "",
        "tweet_id": "",
        "error": "",
    }
    payload["items"].append(item)
    _save_queue(payload)
    return item


def list_queue(status: str | None = "queued") -> list[dict]:
    items = _load_queue()["items"]
    if status is None:
        return items
    return [item for item in items if item.get("status") == status]


def queue_summary() -> dict:
    items = list_queue(status=None)
    summary = {
        "total": len(items),
        "queued": 0,
        "posted": 0,
        "failed": 0,
    }
    for item in items:
        state = item.get("status", "queued")
        summary[state] = summary.get(state, 0) + 1
    return summary


def clear_queue(status: str | None = None) -> int:
    payload = _load_queue()
    items = payload["items"]
    if status is None:
        removed = len(items)
        payload["items"] = []
    else:
        payload["items"] = [item for item in items if item.get("status") != status]
        removed = len(items) - len(payload["items"])
    _save_queue(payload)
    return removed


def show_queue(status: str | None = "queued"):
    items = list_queue(status=status)
    summary = queue_summary()
    ui.status_table(
        [
            ("Queued", "Ready", str(summary.get("queued", 0))),
            ("Posted", "Ready", str(summary.get("posted", 0))),
            ("Failed", "Ready", str(summary.get("failed", 0))),
        ]
    )
    if not items:
        ui.warn("No X posts match that filter yet.")
        return

    for index, item in enumerate(items, 1):
        when = item.get("scheduled_for") or "now"
        ui.info(
            f"{index}. [{item.get('workflow', 'manual')}/{item.get('type', 'organic')}] "
            f"{item.get('text', '')}  (schedule: {when})"
        )


def export_queue(output_path: str | Path | None = None) -> str:
    items = list_queue(status=None)
    output = Path(output_path) if output_path else (ROOT / "x-queue.md")
    lines = ["# CashCrab X Queue", ""]

    if not items:
        lines.append("_Queue is empty._")
    else:
        for item in items:
            lines.append(f"## {item.get('workflow', 'manual')} · {item.get('status', 'queued')}")
            lines.append(f"- id: `{item.get('id', '')}`")
            lines.append(f"- type: `{item.get('type', 'organic')}`")
            lines.append(f"- topic: `{item.get('topic', '') or 'n/a'}`")
            lines.append(f"- schedule: `{item.get('scheduled_for', '') or 'now'}`")
            lines.append(f"- text: {item.get('text', '')}")
            lines.append("")

    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    ui.success(f"Exported X queue to {output}")
    return str(output)


def _schedule_iso(index: int, spacing_minutes: int) -> str:
    if index <= 0:
        return ""
    scheduled = datetime.now() + timedelta(minutes=spacing_minutes * index)
    return scheduled.isoformat(timespec="seconds")


def _pick_product(product: dict | None = None) -> dict:
    cfg = section("twitter")
    products = cfg.get("products", [])

    if product:
        return product
    if not products:
        raise RuntimeError("No affiliate products are configured yet.")
    return random.choice(products)


def generate_affiliate_draft(product: dict | None = None, angle: str = "") -> str:
    chosen = _pick_product(product)
    name = chosen["name"]
    url = chosen["url"]
    keywords = chosen.get("keywords", [])

    extra_angle = f"\nAngle: {angle}" if angle else ""
    prompt = (
        f"Write a short, engaging X post promoting this product: {name}\n"
        f"Include the link exactly: {url}\n"
        f"Keywords: {', '.join(keywords)}{extra_angle}\n"
        "Rules:\n"
        "- Under 260 characters total before adding the link buffer\n"
        "- Must include #ad for FTC compliance\n"
        "- Conversational, not salesy\n"
        "- Include 1-2 relevant hashtags besides #ad\n"
        "- Sound like a sharp operator recommending something that actually helps"
    )
    text = _normalize_text(llm.generate(prompt, system="You are a social media copywriter."))

    if "#ad" not in text.lower():
        text = _normalize_text(f"{text} #ad")
    if url not in text:
        text = _normalize_text(f"{text} {url}")
    return text


def generate_organic_draft(topic: str | None = None, angle: str = "") -> str:
    cfg = section("twitter")
    niche_keywords = []
    for product in cfg.get("products", []):
        niche_keywords.extend(product.get("keywords", []))

    chosen_topic = topic or (random.choice(niche_keywords) if niche_keywords else "technology")
    extra_angle = f"\nAngle: {angle}" if angle else ""
    prompt = (
        f"Write an engaging X post about: {chosen_topic}{extra_angle}\n"
        "Rules:\n"
        "- Under 270 characters\n"
        "- Add value with a tip, fact, or useful take\n"
        "- 1-2 relevant hashtags\n"
        "- No links\n"
        "- Conversational tone\n"
        "- No emojis unless unavoidable"
    )
    return _normalize_text(llm.generate(prompt, system="You are a social media expert building an audience."))


def draft_post(
    topic: str | None = None,
    tweet_type: str = "organic",
    angle: str = "",
    product: dict | None = None,
) -> str:
    if tweet_type == "affiliate":
        return generate_affiliate_draft(product=product, angle=angle or topic or "")
    return generate_organic_draft(topic=topic, angle=angle)


def post_tweet(text: str, tweet_type: str = "organic") -> str:
    client = _client()
    resp = client.create_tweet(text=_normalize_text(text))
    tweet_id = resp.data["id"]
    ui.success(f"Tweet posted: {tweet_id}")
    try:
        from modules import analytics, notify

        analytics.track_tweet(tweet_id=tweet_id, text=text, tweet_type=tweet_type)
        notify.tweet_posted(tweet_id=tweet_id, text=text)
    except Exception:
        pass
    return tweet_id


def post_affiliate(product: dict | None = None) -> str:
    return post_tweet(generate_affiliate_draft(product=product), tweet_type="affiliate")


def post_organic(topic: str | None = None) -> str:
    return post_tweet(generate_organic_draft(topic=topic), tweet_type="organic")


def build_workflow_queue(
    preset: str,
    topic: str,
    count: int | None = None,
    spacing_minutes: int = 45,
) -> list[dict]:
    steps = WORKFLOW_PRESETS.get(preset)
    if not steps:
        supported = ", ".join(workflow_presets())
        raise RuntimeError(f"Unknown X workflow preset '{preset}'. Try one of: {supported}")

    target_count = count or len(steps)
    items = []
    for index in range(target_count):
        step = steps[index % len(steps)]
        prompt = step["prompt"].format(topic=topic)
        if step["kind"] == "affiliate":
            text = generate_affiliate_draft(angle=prompt)
        else:
            text = generate_organic_draft(topic=topic, angle=prompt)
        items.append(
            queue_tweet(
                text=text,
                tweet_type=step["kind"],
                workflow=preset,
                topic=topic,
                scheduled_for=_schedule_iso(index, spacing_minutes),
                source="workflow",
            )
        )
    ui.success(f"Queued {len(items)} X posts for the '{preset}' workflow.")
    return items


def post_queued(limit: int = 1, include_scheduled: bool = False) -> list[dict]:
    payload = _load_queue()
    now = datetime.now()
    posted = []

    for item in payload["items"]:
        if len(posted) >= limit:
            break
        if item.get("status") != "queued":
            continue

        scheduled_for = item.get("scheduled_for")
        if scheduled_for and not include_scheduled:
            try:
                if datetime.fromisoformat(scheduled_for) > now:
                    continue
            except ValueError:
                pass

        try:
            text = item.get("text", "")
            item_type = item.get("type", "organic")

            if item_type == "thread" and " ||| " in text:
                thread_texts = [t.strip() for t in text.split(" ||| ") if t.strip()]
                tweet_ids = post_thread(thread_texts, tweet_type="organic")
                tweet_id = tweet_ids[0] if tweet_ids else ""
            else:
                tweet_id = post_tweet(text, tweet_type=item_type)

            item["status"] = "posted"
            item["tweet_id"] = tweet_id
            item["posted_at"] = _now_iso()
            item["error"] = ""
            posted.append({"queue_id": item["id"], "tweet_id": tweet_id, "text": text})
        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            item["posted_at"] = ""

    _save_queue(payload)

    if not posted:
        ui.warn("No queued X posts were due to post.")
    else:
        ui.success(f"Posted {len(posted)} queued X post(s).")
    return posted


def score_content(text: str) -> dict:
    """Rule-based tweet performance scoring (0-100). No LLM cost."""
    score = 50
    reasons: list[str] = []

    words = text.split()
    length = len(text)

    # Length sweet spot: 70-200 chars
    if 70 <= length <= 200:
        score += 10
        reasons.append("+10 optimal length")
    elif length < 40:
        score -= 10
        reasons.append("-10 too short")
    elif length > 260:
        score -= 5
        reasons.append("-5 near limit")

    # Starts with "You" → engagement hook
    if text.strip().lower().startswith("you"):
        score += 10
        reasons.append("+10 starts with 'You'")
    elif text.strip().lower().startswith("i "):
        score -= 5
        reasons.append("-5 starts with 'I'")

    # Question mark → invites reply
    if "?" in text:
        score += 15
        reasons.append("+15 question")

    # Call to action
    cta_patterns = ["reply", "comment", "share", "retweet", "bookmark", "follow", "check out", "try", "dm me"]
    if any(p in text.lower() for p in cta_patterns):
        score += 10
        reasons.append("+10 CTA detected")

    # Numbers / stats → credibility
    if re.search(r"\d+", text):
        score += 5
        reasons.append("+5 has numbers")

    # Emoji count: 1-3 is good, 4+ is bad
    emoji_count = len(re.findall(r"[\U0001f600-\U0001f9ff\U0001fa00-\U0001faff\u2600-\u26ff\u2700-\u27bf]", text))
    if 1 <= emoji_count <= 3:
        score += 5
        reasons.append("+5 good emoji count")
    elif emoji_count > 3:
        score -= 5
        reasons.append("-5 too many emojis")

    # Line breaks → readability
    if "\n" in text:
        score += 5
        reasons.append("+5 line breaks")

    # Hashtag check: 1-2 good, 3+ bad
    hashtag_count = len(re.findall(r"#\w+", text))
    if 1 <= hashtag_count <= 2:
        score += 5
        reasons.append("+5 good hashtag count")
    elif hashtag_count > 3:
        score -= 10
        reasons.append("-10 hashtag spam")

    # All caps words (shouting)
    caps_words = [w for w in words if w.isupper() and len(w) > 2]
    if len(caps_words) > 2:
        score -= 5
        reasons.append("-5 too many ALL CAPS")

    score = max(0, min(100, score))
    tier = "fire" if score >= 80 else "good" if score >= 60 else "mid" if score >= 40 else "weak"
    return {"score": score, "tier": tier, "reasons": reasons}


def post_thread(texts: list[str], tweet_type: str = "organic") -> list[str]:
    """Post a thread (list of tweets as a reply chain)."""
    if not texts:
        raise RuntimeError("Thread is empty.")

    client = _client()
    tweet_ids = []

    for index, text in enumerate(texts):
        normalized = _normalize_text(text)
        if not normalized:
            continue

        kwargs = {"text": normalized}
        if tweet_ids:
            kwargs["in_reply_to_tweet_id"] = tweet_ids[-1]

        resp = client.create_tweet(**kwargs)
        tid = resp.data["id"]
        tweet_ids.append(tid)
        ui.step(index + 1, len(texts), f"Thread {index + 1}/{len(texts)} posted")

        try:
            from modules import analytics, notify
            analytics.track_tweet(tweet_id=tid, text=normalized, tweet_type=tweet_type)
            if index == 0:
                notify.tweet_posted(tweet_id=tid, text=f"[THREAD {len(texts)} tweets] {normalized}")
        except Exception:
            pass

        if index < len(texts) - 1:
            time.sleep(random.uniform(2, 5))

    ui.success(f"Thread posted: {len(tweet_ids)} tweets")
    return tweet_ids


def generate_thread(topic: str, count: int = 4) -> list[str]:
    """Generate a thread with Qwen/LLM. Returns list of tweet texts."""
    prompt = (
        f"Write a Twitter/X thread about: {topic}\n"
        f"Exactly {count} tweets.\n"
        "Rules:\n"
        "- First tweet is the hook (curiosity, bold claim, or question)\n"
        "- Middle tweets deliver value (tips, insights, examples)\n"
        "- Last tweet is a CTA or summary\n"
        "- Each tweet UNDER 270 characters\n"
        "- No numbering like '1/' or 'Thread:'\n"
        "- Conversational, not robotic\n"
        "- Return ONLY the tweets, separated by ---"
    )
    raw = llm.generate(prompt, system="You are a viral Twitter thread writer.")
    parts = [p.strip() for p in raw.split("---") if p.strip()]
    return [_normalize_text(p) for p in parts[:count]]


def queue_thread(
    topic: str,
    count: int = 4,
    scheduled_for: str | None = None,
) -> dict:
    """Generate and queue a thread."""
    texts = generate_thread(topic, count)
    payload = _load_queue()
    item = {
        "id": _new_queue_id(),
        "text": " ||| ".join(texts),
        "type": "thread",
        "workflow": "thread",
        "topic": topic,
        "source": "thread-gen",
        "status": "queued",
        "created_at": _now_iso(),
        "scheduled_for": scheduled_for or "",
        "posted_at": "",
        "tweet_id": "",
        "error": "",
        "thread_count": len(texts),
    }
    payload["items"].append(item)
    _save_queue(payload)
    ui.success(f"Thread queued: {len(texts)} tweets about '{topic}'")
    for i, t in enumerate(texts, 1):
        ui.info(f"  {i}. {t}")
    return item


def run_batch(count: int = 1, affiliate_ratio: float = 0.3):
    ui.info(f"Posting {count} tweet(s). Affiliate ratio: {affiliate_ratio:.0%}")

    for index in range(count):
        try:
            if random.random() < affiliate_ratio:
                ui.step(index + 1, count, "Posting an affiliate tweet")
                post_affiliate()
            else:
                ui.step(index + 1, count, "Posting a helpful tweet")
                post_organic()

            if index < count - 1:
                wait = random.randint(60, 180)
                ui.info(f"Waiting {wait} seconds before the next tweet...")
                time.sleep(wait)
        except Exception as exc:
            ui.fail(str(exc))
            time.sleep(30)
