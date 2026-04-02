#!/usr/bin/env python3
"""Generate the GitHub social preview image (1280x640)."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
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
PANEL = (13, 19, 34)
PANEL_EDGE = (44, 58, 93)

ASSETS = os.path.dirname(os.path.abspath(__file__))


def _fonts():
    try:
        return {
            "title": ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 62),
            "sub": ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24),
            "tag": ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20),
            "code": ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", 16),
            "tiny": ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16),
        }
    except (IOError, OSError):
        fallback = ImageFont.load_default()
        return {
            "title": fallback,
            "sub": fallback,
            "tag": fallback,
            "code": fallback,
            "tiny": fallback,
        }


def _terminal_panel(img: Image.Image, draw: ImageDraw.ImageDraw, fonts: dict):
    panel_box = (752, 166, 1234, 578)
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle(
        [panel_box[0] + 16, panel_box[1] + 18, panel_box[2] + 16, panel_box[3] + 18],
        radius=28,
        fill=(0, 0, 0, 120),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(shadow)

    draw.rounded_rectangle(panel_box, radius=28, fill=PANEL, outline=PANEL_EDGE, width=2)
    draw.rounded_rectangle((752, 166, 1234, 222), radius=28, fill=DARK)
    draw.rectangle((752, 194, 1234, 222), fill=DARK)

    for i, color in enumerate(((255, 99, 99), (255, 205, 74), (94, 255, 153))):
        x = 782 + i * 24
        draw.ellipse((x, 186, x + 12, 198), fill=color)

    draw.text((842, 184), "INSTALL CASHCRAB", fill=WHITE, font=fonts["tiny"])

    draw.text((778, 250), "$ curl -fsSL raw.githubusercontent.com/...", fill=MONEY, font=fonts["code"])
    draw.text((778, 276), "$   redpersongpt/cashcrab/main/scripts/install.sh | bash", fill=MONEY, font=fonts["code"])
    draw.text((778, 302), "$ cashcrab", fill=WHITE, font=fonts["code"])
    draw.text((778, 350), "PS> irm raw.githubusercontent.com/...", fill=HOT, font=fonts["code"])
    draw.text((778, 376), "PS>   redpersongpt/cashcrab/main/scripts/install.ps1 | iex", fill=HOT, font=fonts["code"])
    draw.text((778, 402), "PS> cashcrab", fill=WHITE, font=fonts["code"])

    draw.text((778, 458), "Global command", fill=WHITE, font=fonts["tag"])
    draw.text((936, 458), "private venv", fill=GRAY, font=fonts["tag"])
    draw.text((1066, 458), "menu-first", fill=GRAY, font=fonts["tag"])

    draw.text((778, 504), "Installs from GitHub and drops `cashcrab` into your user PATH.", fill=GRAY, font=fonts["tiny"])
    draw.text((778, 530), "No project-local repo setup required after install.", fill=GRAY, font=fonts["tiny"])


def generate(output_path: str = "assets/social_preview.png"):
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=BG_SOFT, width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=BG_SOFT, width=1)

    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([22, 74, 460, 544], fill=(40, 220, 130, 54))
    gdraw.ellipse([0, 52, 470, 560], fill=(170, 35, 50, 120))
    glow = glow.filter(ImageFilter.GaussianBlur(20))
    img.alpha_composite(glow)

    draw.ellipse([18, 78, 452, 540], fill=(155, 28, 49))

    # Load and paste mascot
    mascot_path = os.path.join(ASSETS, "cashcrab.png")
    if os.path.exists(mascot_path):
        mascot = Image.open(mascot_path)
        mascot = mascot.resize((330, 330), Image.NEAREST)
        img.alpha_composite(mascot, (68, 148))

    fonts = _fonts()

    draw.text((434, 122), "CashCrab", fill=WHITE, font=fonts["title"])
    draw.text((434, 194), "Install once. Run from any terminal.", fill=MONEY, font=fonts["sub"])
    draw.text((434, 230), "A colorful CLI for Shorts, X posting, and lead gen.", fill=GRAY, font=fonts["tag"])

    features = ["YouTube Shorts", "Twitter / X", "Lead Gen", "Global Install"]
    x_pos = 434
    for feat in features:
        bbox = draw.textbbox((0, 0), feat, font=fonts["tag"])
        tw = bbox[2] - bbox[0]
        pill_w = tw + 24

        draw.rounded_rectangle(
            [x_pos, 286, x_pos + pill_w, 324],
            radius=8, fill=DARK, outline=HOT, width=2,
        )
        draw.text((x_pos + 12, 293), feat, fill=WHITE, font=fonts["tag"])
        x_pos += pill_w + 12

    draw.text(
        (434, 364),
        "Run `cashcrab` directly after install. No local repo needed.",
        fill=WHITE, font=fonts["tag"],
    )
    draw.text(
        (434, 398),
        "Private user-level install, menu-first UX, official APIs.",
        fill=GRAY, font=fonts["tag"],
    )

    _terminal_panel(img, draw, fonts)

    draw.rectangle([0, H - 4, W, H], fill=ACCENT)

    img.convert("RGB").save(output_path)
    print(f"Social preview saved: {output_path} ({W}x{H})")


if __name__ == "__main__":
    generate()
