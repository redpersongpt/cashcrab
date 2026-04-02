import json
import shlex
import shutil
import subprocess
import time

from g4f.client import Client as G4FClient

from modules.config import ROOT, section

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

    raise RuntimeError("Qwen Code CLI was not found. Install Node/npm or switch llm.provider to g4f, ollama, or an OpenAI-compatible provider.")


def qwen_auth_status() -> tuple[str, str]:
    try:
        result = subprocess.run(
            qwen_cli_base_command() + ["auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return "Unavailable", str(exc)

    output = (result.stdout or result.stderr or "").strip()
    if "No authentication method configured" in output:
        return "Not connected", "Run cashcrab auth qwen"
    if result.returncode == 0:
        return "Connected", "Qwen OAuth ready"
    return "Unavailable", output or "Unknown Qwen auth status"


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


def _generate_with_qwen(prompt: str, system: str, model: str, max_retries: int) -> str:
    cfg = section("llm")
    auth_type = cfg.get("auth_type", "qwen-oauth")
    timeout_seconds = int(cfg.get("timeout_seconds", 180))
    workspace_dir = ROOT / "codex-workspace"

    command = qwen_cli_base_command() + [
        "--model",
        model,
        "--auth-type",
        auth_type,
        "--system-prompt",
        system,
        "--output-format",
        "text",
        prompt,
    ]

    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(workspace_dir) if workspace_dir.exists() else None,
            )
            if result.returncode == 0:
                return (result.stdout or "").strip()

            error = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(error or "Qwen Code returned a non-zero exit code.")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Qwen generation failed: {exc}") from exc
            wait = 2 ** attempt
            print(f"  Qwen error (retry {attempt + 1}/{max_retries}): {exc}")
            time.sleep(wait)

    return ""


def generate(prompt: str, system: str = "You are a helpful assistant.", max_retries: int = 3) -> str:
    client, model, kind = _client()

    if kind == "qwen_code":
        return _generate_with_qwen(prompt, system, model, max_retries)

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
        except Exception as exc:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  LLM error (retry {attempt + 1}/{max_retries}): {exc}")
            time.sleep(wait)
    return ""


def generate_json(
    prompt: str,
    system: str = "You are a helpful assistant. Always respond with valid JSON only, no markdown.",
) -> dict | list:
    raw = generate(prompt, system)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    return json.loads(raw)
