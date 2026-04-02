#!/usr/bin/env python3
"""Generate GitHub social preview image (1280x640)."""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1280, 640
BG = (17, 24, 39)          # dark navy
ACCENT = (231, 76, 60)     # crab red
GOLD = (241, 196, 15)      # coin gold
WHITE = (255, 255, 255)
GRAY = (156, 163, 175)
DARK = (31, 41, 55)

ASSETS = os.path.dirname(os.path.abspath(__file__))


def generate(output_path: str = "assets/social_preview.png"):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle grid pattern
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(25, 32, 48), width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(25, 32, 48), width=1)

    # Load and paste mascot
    mascot_path = os.path.join(ASSETS, "cashcrab.png")
    if os.path.exists(mascot_path):
        mascot = Image.open(mascot_path)
        mascot = mascot.resize((280, 220), Image.NEAREST)
        img.paste(mascot, (80, 200), mascot)

    # Title
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        tag_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except (IOError, OSError):
        title_font = ImageFont.load_default()
        sub_font = title_font
        tag_font = title_font

    # "CashCrab" title
    draw.text((420, 140), "CashCrab", fill=WHITE, font=title_font)

    # Tagline
    draw.text((420, 230), "Your claws on autopilot.", fill=GOLD, font=sub_font)

    # Feature pills
    features = [
        "YouTube Shorts",
        "Twitter Affiliate",
        "Lead Gen",
        "Zero AI Cost",
    ]

    x_pos = 420
    for feat in features:
        bbox = draw.textbbox((0, 0), feat, font=tag_font)
        tw = bbox[2] - bbox[0]
        pill_w = tw + 24

        draw.rounded_rectangle(
            [x_pos, 300, x_pos + pill_w, 340],
            radius=8, fill=DARK, outline=ACCENT, width=1,
        )
        draw.text((x_pos + 12, 306), feat, fill=WHITE, font=tag_font)
        x_pos += pill_w + 12

    # Bottom tagline
    draw.text(
        (420, 400),
        "Official APIs  |  g4f (free AI)  |  edge-tts  |  OAuth2",
        fill=GRAY, font=tag_font,
    )
    draw.text(
        (420, 440),
        "$0 per video. No Selenium. No broken schedulers.",
        fill=GRAY, font=tag_font,
    )

    # Accent line
    draw.rectangle([0, H - 4, W, H], fill=ACCENT)

    img.save(output_path)
    print(f"Social preview saved: {output_path} ({W}x{H})")


if __name__ == "__main__":
    generate()
