import json
import os
from importlib.resources import files
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
DEV_ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / ".git").exists() else None


def _default_app_home() -> Path:
    env_home = os.getenv("CASHCRAB_HOME")
    if env_home:
        return Path(env_home).expanduser()

    if DEV_ROOT is not None:
        return DEV_ROOT

    if os.name == "nt":
        base = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "CashCrab"

    return Path.home() / ".cashcrab"


APP_HOME = _default_app_home()
APP_HOME.mkdir(parents=True, exist_ok=True)
ROOT = APP_HOME

CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config.example.json"

_cache: dict | None = None


def _default_config_text() -> str:
    repo_example = PACKAGE_ROOT / "config.example.json"
    if repo_example.exists():
        return repo_example.read_text(encoding="utf-8")

    try:
        return (files("modules.resources") / "config.example.json").read_text(encoding="utf-8")
    except Exception as exc:
        raise RuntimeError("Bundled config template was not found.") from exc


def ensure_bootstrap_files():
    example_text = _default_config_text()

    if not CONFIG_EXAMPLE_PATH.exists():
        CONFIG_EXAMPLE_PATH.write_text(example_text, encoding="utf-8")

    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(example_text, encoding="utf-8")

    for path in [ROOT / "tokens", ROOT / "output", ROOT / "shorts"]:
        path.mkdir(parents=True, exist_ok=True)

    try:
        from modules import agentpacks

        agentpacks.sync_workspace(ROOT / "codex-workspace")
    except Exception:
        pass


def load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    ensure_bootstrap_files()

    with open(CONFIG_PATH, encoding="utf-8") as f:
        _cache = json.load(f)
    return _cache


def save(cfg: dict) -> dict:
    global _cache
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    _cache = cfg
    return cfg


def update_section(name: str, updates: dict) -> dict:
    cfg = load()
    section_data = cfg.get(name, {})
    if not isinstance(section_data, dict):
        raise RuntimeError(f"'{name}' section in {CONFIG_PATH} is not an object.")
    section_data.update(updates)
    cfg[name] = section_data
    return save(cfg)


def section(name: str) -> dict:
    cfg = load()
    s = cfg.get(name)
    if s is None:
        raise RuntimeError(f"'{name}' section is missing from {CONFIG_PATH}.")
    return s


def optional_section(name: str, default=None):
    cfg = load()
    value = cfg.get(name)
    if value is None:
        return {} if default is None else default
    return value


def reload():
    global _cache
    _cache = None
    return load()
