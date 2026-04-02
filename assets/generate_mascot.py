#!/usr/bin/env python3
"""Generate CashCrab pixel art mascot."""

from PIL import Image, ImageDraw

SCALE = 16

C = {
    ".": None,
    "R": (231, 76, 60),
    "D": (192, 57, 43),
    "O": (230, 126, 34),
    "G": (241, 196, 15),
    "Y": (247, 220, 111),
    "K": (30, 30, 30),
    "W": (255, 255, 255),
    "E": (200, 200, 210),
    "P": (185, 145, 20),
    "S": (44, 62, 80),
    "M": (243, 156, 18),
    "B": (169, 50, 38),
}

# 34 wide x 24 tall
# Symmetric around column 17
GRID = [
    ".....GG..................GG.....",  # 0  left coin   right coin
    "....GYYG................GYYG...",  # 1
    "....GPSG................GPSG...",  # 2  $ on coins
    ".....GG..................GG....",  # 3
    "....KRK................KRK.....",  # 4  claw tips
    "...KRRK................KRRK....",  # 5
    "...KRRRK..............KRRRK....",  # 6
    "....KRRRK............KRRRK.....",  # 7
    ".....KRRK..KKKKKK..KRRK.......",  # 8  arms reach body
    "......KKK.KRRRRRRK.KKK........",  # 9
    "..........KRRRRRRRRK...........",  # 10
    ".........KRRRRRRRRRRK..........",  # 11
    "........KRRRRRRRRRRRRK.........",  # 12
    "........KRRWWRRRRWWRRK.........",  # 13 eyes
    "........KRWKWRRRRWKWRK.........",  # 14 pupils
    "........KRRWWRRRRWWRRK.........",  # 15
    "........KRRRRRKKRRRRRK.........",  # 16 smile
    ".......KRRRRRRRRRRRRRRK........",  # 17
    ".......KRRRRRGGGGRRRRRRK.......",  # 18 gold belly
    ".......KRRRRGMMMGRRRRRK........",  # 19
    ".......KRRRRRGGGGRRRRRK........",  # 20
    "........KRRRRRRRRRRRRK.........",  # 21
    ".........KKRRRRRRRRKKK.........",  # 22
    "..........KKKKKKKKKK...........",  # 23
    ".........KK.KK..KK.KK.........",  # 24
    "........KK..KK..KK..KK........",  # 25
]


def generate(output_path: str = "assets/cashcrab.png", scale: int = SCALE):
    h = len(GRID)
    w = max(len(row) for row in GRID)

    img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y, row in enumerate(GRID):
        for x, ch in enumerate(row):
            color = C.get(ch)
            if color:
                draw.rectangle(
                    [x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1],
                    fill=(*color, 255),
                )

    img.save(output_path)
    print(f"Mascot saved: {output_path} ({img.width}x{img.height})")

    small = img.resize((128, 128), Image.NEAREST)
    small.save(output_path.replace(".png", "_small.png"))

    return output_path


if __name__ == "__main__":
    generate()
