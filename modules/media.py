"""Generate infographic images + upload to Twitter via API.

Creates dark-themed fact cards, before/after comparisons, and stat graphics.
Uses PIL for image generation, curl_cffi for upload.
"""
from __future__ import annotations

import json
import random
import io
from pathlib import Path

from modules.config import ROOT

FONTS_AVAILABLE = False
try:
    from PIL import Image, ImageDraw, ImageFont
    FONTS_AVAILABLE = True
except ImportError:
    pass


# ─── Colors ───────────────────────────────────────────────────────

BG = (10, 10, 10)
ACCENT = (245, 245, 247)
DIM = (134, 134, 139)
GREEN = (48, 209, 88)
RED = (255, 69, 58)
BLUE = (10, 132, 255)


def _font(size: int):
    """Get a font. Falls back to default if custom not available."""
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono-Regular.otf",
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ─── Image generators ────────────────────────────────────────────

def make_fact_card(title: str, fact: str, footer: str = "ouden.cc") -> bytes:
    """Create a dark fact card image (1200x675)."""
    if not FONTS_AVAILABLE:
        return b""

    img = Image.new("RGB", (1200, 675), BG)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = _font(36)
    draw.text((60, 50), title.upper(), fill=RED, font=title_font)

    # Fact text (word wrap)
    fact_font = _font(28)
    words = fact.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=fact_font)
        if bbox[2] > 1080:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)

    y = 140
    for line in lines:
        draw.text((60, y), line, fill=ACCENT, font=fact_font)
        y += 42

    # Footer
    footer_font = _font(20)
    draw.text((60, 620), footer, fill=DIM, font=footer_font)

    # Arc logo hint
    draw.arc([1080, 580, 1160, 660], start=-50, end=260, fill=DIM, width=3)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def make_before_after(before_label: str, before_val: str, after_label: str, after_val: str, title: str = "") -> bytes:
    """Create a before/after comparison card."""
    if not FONTS_AVAILABLE:
        return b""

    img = Image.new("RGB", (1200, 675), BG)
    draw = ImageDraw.Draw(img)

    if title:
        title_font = _font(30)
        draw.text((60, 40), title, fill=ACCENT, font=title_font)

    # Before box
    draw.rounded_rectangle([50, 120, 580, 380], radius=16, fill=(30, 10, 10), outline=RED, width=2)
    label_font = _font(22)
    val_font = _font(48)
    draw.text((80, 140), "BEFORE", fill=RED, font=label_font)
    draw.text((80, 190), before_label, fill=DIM, font=_font(18))
    draw.text((80, 250), before_val, fill=RED, font=val_font)

    # After box
    draw.rounded_rectangle([620, 120, 1150, 380], radius=16, fill=(10, 30, 10), outline=GREEN, width=2)
    draw.text((650, 140), "AFTER", fill=GREEN, font=label_font)
    draw.text((650, 190), after_label, fill=DIM, font=_font(18))
    draw.text((650, 250), after_val, fill=GREEN, font=val_font)

    # Arrow
    draw.text((590, 220), "→", fill=DIM, font=_font(40))

    # Footer
    draw.text((60, 620), "ouden.cc", fill=DIM, font=_font(20))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def make_stat_card(stats: list[tuple[str, str, tuple]]) -> bytes:
    """Create a stats card with big numbers. stats = [(value, label, color), ...]"""
    if not FONTS_AVAILABLE:
        return b""

    img = Image.new("RGB", (1200, 675), BG)
    draw = ImageDraw.Draw(img)

    x_positions = [100, 450, 800]
    for i, (val, label, color) in enumerate(stats[:3]):
        x = x_positions[i]
        draw.text((x, 180), val, fill=color, font=_font(72))
        draw.text((x, 280), label, fill=DIM, font=_font(20))

    draw.text((60, 620), "ouden.cc", fill=DIM, font=_font(20))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─── Pre-made infographics ────────────────────────────────────────

INFOGRAPHICS = [
    lambda: make_before_after("Stock Windows idle RAM", "4.1 GB", "After cleanup", "1.9 GB", "RAM usage at idle"),
    lambda: make_before_after("Default timer resolution", "15.6ms", "After oudenOS", "0.5ms", "Input timing"),
    lambda: make_before_after("Boot time stock", "47 sec", "After cleanup", "11 sec", "Boot time (same SSD)"),
    lambda: make_before_after("Services running", "280+", "After oudenOS", "~60", "Windows services"),
    lambda: make_before_after("Telemetry endpoints", "70+", "After blocking", "0", "Microsoft endpoints"),
    lambda: make_stat_card([("280+", "services running", RED), ("70+", "telemetry endpoints", RED), ("4.1GB", "RAM at idle", RED)]),
    lambda: make_stat_card([("~60", "services needed", GREEN), ("0", "endpoints blocked", GREEN), ("1.9GB", "RAM after", GREEN)]),
    lambda: make_stat_card([("5MB", "oudenOS size", GREEN), ("20GB", "Windows bloat", RED), ("8", "hardware profiles", BLUE)]),
    lambda: make_fact_card("DID YOU KNOW", "Windows has a fax machine service running on your gaming rig right now. In 2026. Check services.msc"),
    lambda: make_fact_card("DID YOU KNOW", "Xbox Game Bar records your screen by default. Eating GPU cycles. You never asked for it."),
    lambda: make_fact_card("DID YOU KNOW", "Windows phones home to 70+ Microsoft endpoints on first boot. Before you even open a browser."),
    lambda: make_fact_card("DID YOU KNOW", "RetailDemo service turns your PC into a Best Buy display kiosk. Its on every Windows install."),
    lambda: make_fact_card("DID YOU KNOW", "NDU.sys has been leaking memory since 2018. Microsoft knows. 7 years. Still shipping it."),
    lambda: make_fact_card("WINDOWS FACT", "Your timer resolution is 15.6ms. From 2001. Your 240Hz monitor runs on 20-year-old timing."),
    lambda: make_fact_card("WINDOWS FACT", "A fresh Windows install uses 4GB RAM at idle. Thats not your apps. Thats 220 services."),
]


def get_random_infographic() -> bytes:
    """Generate a random infographic."""
    fn = random.choice(INFOGRAPHICS)
    return fn()


# ─── Upload to Twitter ────────────────────────────────────────────

def upload_media(session, ct0: str, image_bytes: bytes) -> str | None:
    """Upload image to Twitter. Returns media_id or None."""
    if not image_bytes:
        return None

    headers = {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "referer": "https://x.com/",
    }

    try:
        # INIT
        r1 = session.post("https://upload.x.com/i/media/upload.json", data={
            "command": "INIT",
            "total_bytes": len(image_bytes),
            "media_type": "image/png",
        }, headers=headers)

        if r1.status_code not in (200, 201, 202):
            return None

        media_id = r1.json().get("media_id_string", "")
        if not media_id:
            return None

        # APPEND
        r2 = session.post("https://upload.x.com/i/media/upload.json", data={
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": "0",
        }, files={"media_data": ("image.png", image_bytes, "image/png")}, headers=headers)

        # FINALIZE
        r3 = session.post("https://upload.x.com/i/media/upload.json", data={
            "command": "FINALIZE",
            "media_id": media_id,
        }, headers=headers)

        if r3.status_code in (200, 201):
            return media_id
    except Exception:
        pass

    return None
