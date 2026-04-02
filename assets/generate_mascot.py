#!/usr/bin/env python3
"""Generate CashCrab pixel art mascot."""

from PIL import Image, ImageDraw

SIZE = 48
SCALE = 12
FINAL = SIZE * SCALE

RED = (220, 55, 45)
DARK_RED = (165, 35, 30)
LIGHT_RED = (245, 115, 95)
GOLD = (241, 196, 15)
YELLOW = (255, 240, 100)
DARK_GOLD = (190, 150, 10)
BLACK = (25, 25, 25)
WHITE = (255, 255, 255)
PUPIL = (25, 25, 40)


def draw_crab():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = 24, 26

    # === BODY (clean, no highlight) ===
    d.ellipse([cx-13, cy-10, cx+13, cy+10], fill=RED, outline=BLACK)

    # === LEFT ARM + CLAW ===
    d.line([(cx-11, cy-3), (cx-15, cy-11)], fill=RED, width=2)
    # Pincer top
    d.ellipse([cx-21, cy-17, cx-13, cy-11], fill=RED, outline=BLACK)
    # Pincer bottom
    d.ellipse([cx-21, cy-13, cx-13, cy-7], fill=RED, outline=BLACK)
    # Coin
    d.ellipse([cx-20, cy-23, cx-14, cy-17], fill=GOLD, outline=DARK_GOLD)
    d.rectangle([cx-18, cy-21, cx-16, cy-19], fill=YELLOW)

    # === RIGHT ARM + CLAW ===
    d.line([(cx+11, cy-3), (cx+15, cy-11)], fill=RED, width=2)
    # Pincer top
    d.ellipse([cx+13, cy-17, cx+21, cy-11], fill=RED, outline=BLACK)
    # Pincer bottom
    d.ellipse([cx+13, cy-13, cx+21, cy-7], fill=RED, outline=BLACK)
    # Coin
    d.ellipse([cx+14, cy-23, cx+20, cy-17], fill=GOLD, outline=DARK_GOLD)
    d.rectangle([cx+16, cy-21, cx+18, cy-19], fill=YELLOW)

    # === EYES (closer together, rounder) ===
    # Left eye
    d.ellipse([cx-8, cy-7, cx-1, cy+1], fill=WHITE)
    d.ellipse([cx-6, cy-5, cx-3, cy-1], fill=PUPIL)
    d.point([cx-7, cy-6], fill=WHITE)  # shine

    # Right eye
    d.ellipse([cx+1, cy-7, cx+8, cy+1], fill=WHITE)
    d.ellipse([cx+3, cy-5, cx+6, cy-1], fill=PUPIL)
    d.point([cx+2, cy-6], fill=WHITE)

    # === SMILE ===
    d.line([(cx-3, cy+3), (cx-2, cy+4)], fill=BLACK)
    d.line([(cx-1, cy+4), (cx+1, cy+4)], fill=BLACK)
    d.line([(cx+2, cy+4), (cx+3, cy+3)], fill=BLACK)

    # === BELLY COIN ===
    d.ellipse([cx-3, cy+4, cx+3, cy+8], fill=GOLD, outline=DARK_GOLD)
    d.rectangle([cx-1, cy+5, cx+1, cy+7], fill=YELLOW)

    # === LEGS (3 pairs, solid dark red) ===
    # Inner pair (straight down)
    d.line([(cx-5, cy+9), (cx-7, cy+14)], fill=DARK_RED)
    d.line([(cx+5, cy+9), (cx+7, cy+14)], fill=DARK_RED)
    # Middle pair (angled)
    d.line([(cx-9, cy+8), (cx-13, cy+12)], fill=DARK_RED)
    d.line([(cx+9, cy+8), (cx+13, cy+12)], fill=DARK_RED)
    # Outer pair (wide angle)
    d.line([(cx-11, cy+6), (cx-16, cy+9)], fill=DARK_RED)
    d.line([(cx+11, cy+6), (cx+16, cy+9)], fill=DARK_RED)

    return img


def generate(output_path: str = "assets/cashcrab.png"):
    pixel_art = draw_crab()
    final = pixel_art.resize((FINAL, FINAL), Image.NEAREST)
    final.save(output_path)
    print(f"Mascot: {output_path} ({FINAL}x{FINAL})")

    small = pixel_art.resize((128, 128), Image.NEAREST)
    small.save(output_path.replace(".png", "_small.png"))
    return output_path


if __name__ == "__main__":
    generate()
