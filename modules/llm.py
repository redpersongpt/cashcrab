import json
import random
import shlex
import shutil
import subprocess
import time

from g4f.client import Client as G4FClient

from modules.config import ROOT, section, optional_section

_client_cache = None


def qwen_cli_base_command() -> list[str]:
    cfg = section("llm")
    custom_command = cfg.get("command", "").strip()
    if custom_command:
        return shlex.split(custom_command)
    qwen_bin = shutil.which("qwen")
    if qwen_bin:
        return [qwen_bin]
    if shutil.which("npx"):
        return ["npx", "-y", "@qwen-code/qwen-code"]
    raise RuntimeError("Qwen Code CLI was not found.")


def qwen_auth_status() -> tuple[str, str]:
    try:
        result = subprocess.run(
            qwen_cli_base_command() + ["auth", "status"],
            check=False, capture_output=True, text=True, timeout=20,
        )
    except Exception as exc:
        return "Unavailable", str(exc)
    output = (result.stdout or result.stderr or "").strip()
    if "No authentication method configured" in output:
        return "Not connected", "Run cashcrab auth qwen"
    if result.returncode == 0:
        return "Connected", "Qwen OAuth ready"
    return "Unavailable", output or "Unknown"


def _client() -> tuple:
    global _client_cache
    cfg = section("llm")
    provider = cfg.get("provider", "qwen_code")
    model = cfg.get("model", "qwen3.5-plus")

    if provider == "qwen_code":
        return None, model, "qwen_code"
    if provider == "g4f":
        if _client_cache is None:
            _client_cache = G4FClient()
        return _client_cache, model, "g4f"
    if provider == "ollama":
        from openai import OpenAI
        base = cfg.get("base_url", "http://localhost:11434/v1")
        return OpenAI(api_key="ollama", base_url=base), model, "openai"
    from openai import OpenAI
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url")
    if not api_key:
        from modules.auth import get_api_key
        api_key = get_api_key(provider) or ""
    return OpenAI(api_key=api_key, **{"base_url": base_url} if base_url else {}), model, "openai"


# ─── Provider implementations ─────────────────────────────────────

def _generate_with_qwen(prompt: str, system: str, model: str, max_retries: int) -> str:
    cfg = section("llm")
    auth_type = cfg.get("auth_type", "qwen-oauth")
    timeout_sec = int(cfg.get("timeout_seconds", 60))
    workspace_dir = ROOT / "codex-workspace"

    command = qwen_cli_base_command() + [
        "--model", model, "--auth-type", auth_type,
        "--system-prompt", system, "--output-format", "text", prompt,
    ]
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True,
                timeout=timeout_sec,
                cwd=str(workspace_dir) if workspace_dir.exists() else None,
            )
            if result.returncode == 0:
                return (result.stdout or "").strip()
            raise RuntimeError((result.stderr or result.stdout or "").strip() or "Non-zero exit")
        except subprocess.TimeoutExpired:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Qwen timed out ({timeout_sec}s)")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            print(f"  Qwen error (retry {attempt+1}/{max_retries}): {exc}")
            time.sleep(2 ** attempt)
    return ""


def _generate_with_gemini(prompt: str, system: str, max_retries: int) -> str:
    gemini_bin = shutil.which("gemini")
    if not gemini_bin:
        raise RuntimeError("Gemini CLI not found")
    full_prompt = f"{system}\n\n{prompt}"
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                [gemini_bin, "-p", "respond with only the requested text. no markdown. no backticks."],
                input=full_prompt, check=False, capture_output=True, text=True, timeout=90,
            )
            lines = [l for l in (result.stdout or "").split("\n")
                     if not l.startswith(("Keychain", "Using FileKeychain", "Loaded cached"))]
            clean = "\n".join(lines).strip()
            if clean:
                return clean
            if result.returncode != 0:
                raise RuntimeError((result.stderr or "").strip()[:200] or "Gemini non-zero")
        except subprocess.TimeoutExpired:
            if attempt == max_retries - 1:
                raise RuntimeError("Gemini timed out (45s)")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return ""


def _generate_with_codex(prompt: str, system: str, max_retries: int) -> str:
    codex_bin = shutil.which("codex")
    if not codex_bin:
        raise RuntimeError("Codex CLI not found")
    full = f"{system}\n\n{prompt}\n\nRespond with ONLY the requested text. No markdown."
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                [codex_bin, "exec", "--model", "o4-mini",
                 "-c", "approval_policy=never", full],
                check=False, capture_output=True, text=True, timeout=30,
            )
            output = (result.stdout or "").strip()
            if output:
                return output
            if result.returncode != 0:
                raise RuntimeError((result.stderr or "").strip()[:200] or "Codex non-zero")
        except subprocess.TimeoutExpired:
            if attempt == max_retries - 1:
                raise RuntimeError("Codex timed out (30s)")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return ""


# ─── Main generate with triple-LLM fallback ──────────────────────

def _generate_with_g4f(prompt: str, system: str, max_retries: int) -> str:
    """Generate via g4f (free, no API key). Tries multiple free providers."""
    from g4f.client import Client as G4F

    # DDG (DuckDuckGo) is the most reliable free provider
    providers_to_try = [
        {"model": "gpt-4o-mini", "provider": "DDGS"},
        {"model": "gpt-4o-mini", "provider": None},
        {"model": "gpt-3.5-turbo", "provider": None},
    ]

    for provider_cfg in providers_to_try:
        for attempt in range(max_retries):
            try:
                client = G4F()
                kwargs = {
                    "model": provider_cfg["model"],
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                }
                if provider_cfg.get("provider"):
                    import g4f.Provider
                    kwargs["provider"] = getattr(g4f.Provider, provider_cfg["provider"], None)
                resp = client.chat.completions.create(**kwargs)
                text = (resp.choices[0].message.content or "").strip()
                if text:
                    return text
            except Exception as exc:
                if attempt == max_retries - 1:
                    break  # try next provider
                time.sleep(1)
    raise RuntimeError("g4f: all providers failed")


def generate(prompt: str, system: str = "You are a helpful assistant.", max_retries: int = 2) -> str:
    client, model, kind = _client()

    # On server: prefer g4f (no CLI overhead) with CLI fallbacks
    use_g4f = optional_section("agent", {}).get("prefer_g4f", False)
    gemini_on = optional_section("gemini", {}).get("enabled", False)
    codex_on = optional_section("codex_llm", {}).get("enabled", False)

    if kind == "qwen_code":
        # Build fallback chain: gemini first (works on VDS), then others
        providers = []
        if gemini_on and shutil.which("gemini"):
            providers.append("gemini")
        if use_g4f:
            providers.append("g4f")
        if codex_on and shutil.which("codex"):
            providers.append("codex")
        providers.append("qwen")

        for provider in providers:
            try:
                if provider == "g4f":
                    return _generate_with_g4f(prompt, system, max_retries)
                elif provider == "codex":
                    return _generate_with_codex(prompt, system, max_retries)
                elif provider == "gemini":
                    return _generate_with_gemini(prompt, system, max_retries)
                else:
                    return _generate_with_qwen(prompt, system, model, max_retries)
            except Exception as exc:
                print(f"  [{provider}] failed, trying next: {exc}")
                continue
        raise RuntimeError("All LLM providers failed")

    if kind == "qwen_code":
        return _generate_with_qwen(prompt, system, model, max_retries)

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return ""


def generate_json(
    prompt: str,
    system: str = "You are a helpful assistant. Always respond with valid JSON only, no markdown.",
) -> dict | list:
    raw = generate(prompt, system).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())
