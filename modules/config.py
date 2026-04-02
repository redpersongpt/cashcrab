import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG_PATH = ROOT / "config.json"

_cache: dict | None = None


def load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} was not found.")
        print("Copy config.example.json to config.json, then open CashCrab again.")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        _cache = json.load(f)
    return _cache


def section(name: str) -> dict:
    cfg = load()
    s = cfg.get(name)
    if s is None:
        print(f"Error: '{name}' section is missing from config.json.")
        sys.exit(1)
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
