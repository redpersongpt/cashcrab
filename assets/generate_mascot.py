#!/usr/bin/env python3
"""Generate the CashCrab mascot and supporting PNG assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 48
FINAL = 576

OUTLINE = (16, 22, 42, 255)
SHELL_DARK = (103, 18, 31, 255)
SHELL_MID = (187, 38, 56, 255)
SHELL_LIGHT = (255, 102, 112, 255)
SHELL_HOT = (255, 165, 155, 255)
MONEY = (94, 255, 153, 255)
MONEY_SOFT = (46, 177, 102, 255)
GOLD = (255, 205, 74, 255)
GOLD_DARK = (173, 115, 22, 255)
BG = (10, 14, 28, 255)
BG_SOFT = (26, 34, 59, 255)


def _rect(draw: ImageDraw.ImageDraw, box, fill, outline=OUTLINE):
    draw.rectangle(box, fill=fill, outline=outline)


def _ellipse(draw: ImageDraw.ImageDraw, box, fill, outline=OUTLINE):
    draw.ellipse(box, fill=fill, outline=outline)


def _poly(draw: ImageDraw.ImageDraw, points, fill, outline=OUTLINE):
    draw.polygon(points, fill=fill, outline=outline)


def draw_crab() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Money shards / aura behind the character.
    for shard in [
        (7, 8, 9, 12),
        (12, 4, 13, 8),
        (15, 6, 17, 10),
        (31, 5, 33, 9),
        (35, 3, 36, 7),
        (39, 8, 41, 12),
    ]:
        _rect(d, shard, MONEY_SOFT, outline=MONEY_SOFT)

    # Head / mask.
    _rect(d, (18, 4, 29, 14), SHELL_DARK)
    _rect(d, (19, 5, 28, 13), SHELL_MID, outline=None)
    _rect(d, (20, 6, 23, 8), MONEY, outline=MONEY)
    _rect(d, (24, 6, 27, 8), MONEY, outline=MONEY)
    _rect(d, (20, 9, 21, 12), SHELL_DARK, outline=SHELL_DARK)
    _rect(d, (24, 9, 25, 12), SHELL_DARK, outline=SHELL_DARK)
    _rect(d, (28, 9, 28, 12), SHELL_DARK, outline=SHELL_DARK)

    # Shoulder spikes.
    _poly(d, [(12, 11), (15, 7), (16, 12)], SHELL_DARK)
    _poly(d, [(35, 11), (32, 7), (31, 12)], SHELL_DARK)

    # Big shoulders.
    _ellipse(d, (7, 13, 19, 24), SHELL_DARK)
    _ellipse(d, (29, 13, 41, 24), SHELL_DARK)
    _ellipse(d, (9, 15, 18, 23), SHELL_MID, outline=None)
    _ellipse(d, (30, 15, 39, 23), SHELL_MID, outline=None)

    # Flexed arms.
    _poly(d, [(12, 21), (17, 18), (20, 22), (18, 30), (13, 33), (9, 28)], SHELL_DARK)
    _poly(d, [(36, 21), (31, 18), (28, 22), (30, 30), (35, 33), (39, 28)], SHELL_DARK)
    _poly(d, [(13, 22), (17, 20), (18, 28), (14, 31), (11, 27)], SHELL_MID, outline=None)
    _poly(d, [(35, 22), (31, 20), (30, 28), (34, 31), (37, 27)], SHELL_MID, outline=None)

    # Claws near the waist.
    _ellipse(d, (8, 29, 17, 37), SHELL_DARK)
    _ellipse(d, (10, 34, 18, 41), SHELL_DARK)
    _ellipse(d, (30, 29, 39, 37), SHELL_DARK)
    _ellipse(d, (29, 34, 37, 41), SHELL_DARK)
    _rect(d, (11, 31, 15, 35), SHELL_MID, outline=None)
    _rect(d, (32, 31, 36, 35), SHELL_MID, outline=None)

    # Torso.
    _poly(d, [(16, 14), (31, 14), (34, 22), (31, 34), (16, 34), (13, 22)], SHELL_DARK)
    _poly(d, [(18, 16), (29, 16), (31, 22), (29, 31), (18, 31), (16, 22)], SHELL_MID, outline=None)
    _ellipse(d, (15, 18, 23, 26), SHELL_LIGHT)
    _ellipse(d, (24, 18, 32, 26), SHELL_LIGHT)
    _poly(d, [(20, 25), (27, 25), (29, 31), (24, 33), (18, 31)], SHELL_DARK)

    # Core coin.
    _ellipse(d, (20, 20, 27, 27), GOLD, outline=GOLD_DARK)
    _rect(d, (22, 21, 22, 25), MONEY, outline=MONEY)
    _rect(d, (21, 23, 23, 23), MONEY, outline=MONEY)
    _rect(d, (25, 21, 25, 25), MONEY, outline=MONEY)
    _rect(d, (24, 23, 26, 23), MONEY, outline=MONEY)

    # Waist and legs.
    _rect(d, (19, 34, 28, 36), SHELL_DARK)
    _poly(d, [(18, 35), (22, 36), (21, 43), (16, 47), (12, 43), (13, 37)], SHELL_DARK)
    _poly(d, [(29, 35), (25, 36), (26, 43), (31, 47), (35, 43), (34, 37)], SHELL_DARK)
    _poly(d, [(18, 37), (21, 38), (19, 43), (16, 45), (14, 41)], SHELL_MID, outline=None)
    _poly(d, [(29, 37), (26, 38), (28, 43), (31, 45), (33, 41)], SHELL_MID, outline=None)
    _rect(d, (14, 46, 18, 47), SHELL_MID)
    _rect(d, (29, 46, 33, 47), SHELL_MID)

    # Hot highlights.
    for box in [
        (10, 16, 12, 18),
        (35, 16, 37, 18),
        (15, 20, 16, 22),
        (31, 20, 32, 22),
        (21, 18, 22, 20),
        (25, 18, 26, 20),
    ]:
        _rect(d, box, SHELL_HOT, outline=None)

    return img


def _save_scaled(sprite: Image.Image, output: Path, size: int):
    sprite.resize((size, size), Image.NEAREST).save(output)


def _render_banner(sprite: Image.Image, output: Path):
    canvas = Image.new("RGBA", (256, 195), BG)
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((20, 10, 236, 180), fill=(26, 210, 120, 40))
    g.ellipse((40, 0, 220, 170), fill=(255, 60, 75, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(glow)

    scaled = sprite.resize((156, 156), Image.NEAREST)
    canvas.alpha_composite(scaled, (50, 20))
    canvas.save(output)


def generate(output_path: str = "assets/cashcrab.png"):
    sprite = draw_crab()
    assets_dir = Path(output_path).resolve().parent
    assets_dir.mkdir(parents=True, exist_ok=True)

    _save_scaled(sprite, assets_dir / "cashcrab.png", FINAL)
    _save_scaled(sprite, assets_dir / "cashcrab_hires.png", 320)
    _save_scaled(sprite, assets_dir / "cashcrab_small.png", 128)
    _save_scaled(sprite, assets_dir / "cashcrab_48x48.png", 48)
    _render_banner(sprite, assets_dir / "cashcrab_banner.png")

    print(f"Generated CashCrab assets in {assets_dir}")
    return str(assets_dir / "cashcrab.png")


if __name__ == "__main__":
    generate()
