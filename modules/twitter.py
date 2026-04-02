import random
import time

import tweepy

from modules.config import section
from modules import llm
from modules.auth import twitter_access_token
from modules import ui


def _client() -> tweepy.Client:
    token = twitter_access_token()
    return tweepy.Client(access_token=token)


def post_tweet(text: str, tweet_type: str = "organic") -> str:
    client = _client()
    resp = client.create_tweet(text=text[:280])
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
    cfg = section("twitter")
    products = cfg.get("products", [])

    if not product and not products:
        ui.warn("No affiliate products are configured yet.")
        return ""

    if not product:
        product = random.choice(products)

    name = product["name"]
    url = product["url"]
    keywords = product.get("keywords", [])

    prompt = (
        f"Write a short, engaging tweet promoting this product: {name}\n"
        f"Include the link: {url}\n"
        f"Keywords: {', '.join(keywords)}\n"
        f"Rules:\n"
        f"- Under 260 characters total (leave room for link)\n"
        f"- Must include #ad for FTC compliance\n"
        f"- Conversational, not salesy\n"
        f"- Include 1-2 relevant hashtags besides #ad\n"
        f"- Include the product link exactly as given"
    )

    text = llm.generate(prompt, system="You are a social media copywriter.")

    if "#ad" not in text.lower():
        text = text.rstrip() + " #ad"

    if url not in text:
        text = text.rstrip() + f" {url}"

    return post_tweet(text, tweet_type="affiliate")


def post_organic(topic: str | None = None) -> str:
    cfg = section("twitter")
    niche_keywords = []
    for p in cfg.get("products", []):
        niche_keywords.extend(p.get("keywords", []))

    if not topic:
        topic = random.choice(niche_keywords) if niche_keywords else "technology"

    text = llm.generate(
        f"Write an engaging tweet about: {topic}\n"
        f"Rules:\n"
        f"- Under 270 characters\n"
        f"- Add value (tip, fact, or hot take)\n"
        f"- 1-2 relevant hashtags\n"
        f"- No links\n"
        f"- Conversational tone",
        system="You are a social media expert building an audience."
    )

    return post_tweet(text, tweet_type="organic")


def run_batch(count: int = 1, affiliate_ratio: float = 0.3):
    ui.info(f"Posting {count} tweet(s). Affiliate ratio: {affiliate_ratio:.0%}")

    for i in range(count):
        try:
            if random.random() < affiliate_ratio:
                ui.step(i + 1, count, "Posting an affiliate tweet")
                post_affiliate()
            else:
                ui.step(i + 1, count, "Posting a helpful tweet")
                post_organic()

            if i < count - 1:
                wait = random.randint(60, 180)
                ui.info(f"Waiting {wait} seconds before the next tweet...")
                time.sleep(wait)
        except Exception as e:
            ui.fail(str(e))
            time.sleep(30)
