import random
import time

import tweepy

from modules.config import section
from modules import llm
from modules.auth import twitter_access_token


def _client() -> tweepy.Client:
    token = twitter_access_token()
    return tweepy.Client(token)


def post_tweet(text: str) -> str:
    client = _client()
    resp = client.create_tweet(text=text[:280])
    tweet_id = resp.data["id"]
    print(f"  Posted tweet: {tweet_id}")
    return tweet_id


def post_affiliate(product: dict | None = None) -> str:
    cfg = section("twitter")
    products = cfg.get("products", [])

    if not product and not products:
        print("No products configured.")
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

    return post_tweet(text)


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

    return post_tweet(text)


def run_batch(count: int = 1, affiliate_ratio: float = 0.3):
    print(f"Posting {count} tweet(s) (affiliate ratio: {affiliate_ratio:.0%})...")

    for i in range(count):
        try:
            if random.random() < affiliate_ratio:
                print(f"[{i+1}/{count}] Affiliate tweet:")
                post_affiliate()
            else:
                print(f"[{i+1}/{count}] Organic tweet:")
                post_organic()

            if i < count - 1:
                wait = random.randint(60, 180)
                print(f"  Waiting {wait}s...")
                time.sleep(wait)
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(30)
