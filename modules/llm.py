import json
import time

from g4f.client import Client as G4FClient

from modules.config import section

_client_cache = None


def _client() -> tuple:
    global _client_cache
    cfg = section("llm")
    provider = cfg.get("provider", "g4f")
    model = cfg.get("model", "gpt-4o-mini")

    if provider == "g4f":
        if _client_cache is None:
            _client_cache = G4FClient()
        return _client_cache, model, "g4f"

    if provider == "ollama":
        from openai import OpenAI
        base = cfg.get("base_url", "http://localhost:11434/v1")
        client = OpenAI(api_key="ollama", base_url=base)
        return client, model, "openai"

    from openai import OpenAI
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url")
    if not api_key:
        from modules.auth import get_api_key
        api_key = get_api_key(provider) or ""
    client = OpenAI(api_key=api_key, **{"base_url": base_url} if base_url else {})
    return client, model, "openai"


def generate(prompt: str, system: str = "You are a helpful assistant.",
             max_retries: int = 3) -> str:
    client, model, kind = _client()

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  LLM error (retry {attempt + 1}/{max_retries}): {e}")
            time.sleep(wait)
    return ""


def generate_json(prompt: str, system: str = "You are a helpful assistant. Always respond with valid JSON only, no markdown.") -> dict | list:
    raw = generate(prompt, system)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    return json.loads(raw)
