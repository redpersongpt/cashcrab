#!/usr/bin/env python3
"""Generate the GitHub social preview image (1280x640)."""

from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1280, 640
BG = (10, 14, 28)
BG_SOFT = (24, 30, 52)
ACCENT = (214, 52, 68)
HOT = (255, 115, 125)
GOLD = (255, 205, 74)
MONEY = (94, 255, 153)
WHITE = (255, 255, 255)
GRAY = (156, 163, 175)
DARK = (20, 26, 44)

ASSETS = os.path.dirname(os.path.abspath(__file__))


def generate(output_path: str = "assets/social_preview.png"):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Subtle grid pattern
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=BG_SOFT, width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=BG_SOFT, width=1)

    draw.ellipse([30, 90, 420, 520], fill=(40, 220, 130))
    draw.ellipse([10, 70, 440, 540], fill=(170, 35, 50))

    # Load and paste mascot
    mascot_path = os.path.join(ASSETS, "cashcrab.png")
    if os.path.exists(mascot_path):
        mascot = Image.open(mascot_path)
        mascot = mascot.resize((320, 320), Image.NEAREST)
        img.paste(mascot, (52, 150), mascot)

    # Title
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 76)
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        tag_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except (IOError, OSError):
        title_font = ImageFont.load_default()
        sub_font = title_font
        tag_font = title_font

    # "CashCrab" title
    draw.text((430, 130), "CashCrab", fill=WHITE, font=title_font)

    # Tagline
    draw.text((430, 225), "Menu-first money tools for the terminal.", fill=MONEY, font=sub_font)

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
            radius=8, fill=DARK, outline=HOT, width=2,
        )
        draw.text((x_pos + 12, 306), feat, fill=WHITE, font=tag_font)
        x_pos += pill_w + 12

    # Bottom tagline
    draw.text(
        (420, 400),
        "Colorful CLI  |  Official APIs  |  g4f  |  edge-tts  |  OAuth2",
        fill=GRAY, font=tag_font,
    )
    draw.text(
        (420, 440),
        "Run cashcrab. Pick a number. Ship content.",
        fill=GRAY, font=tag_font,
    )

    # Accent line
    draw.rectangle([0, H - 4, W, H], fill=ACCENT)

    img.save(output_path)
    print(f"Social preview saved: {output_path} ({W}x{H})")


if __name__ == "__main__":
    generate()
