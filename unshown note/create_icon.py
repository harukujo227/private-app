"""Generate Private Notes app icon (.ico + tray PNG)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT_ICO = ROOT / "app.ico"
OUT_PNG = ROOT / "app.png"


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = max(1, size // 16)
    # Teal notepad card
    card = [margin, margin + size // 12, size - margin, size - margin]
    radius = max(2, size // 8)
    draw.rounded_rectangle(card, radius=radius, fill=(15, 118, 110, 255))

    # Lighter page
    inset = max(2, size // 10)
    page = [
        card[0] + inset,
        card[1] + inset,
        card[2] - inset,
        card[3] - inset,
    ]
    draw.rounded_rectangle(page, radius=max(1, radius // 2), fill=(236, 253, 245, 255))

    # Text lines
    line_color = (13, 148, 136, 255)
    left = page[0] + max(2, size // 12)
    right = page[2] - max(2, size // 12)
    top = page[1] + max(3, size // 8)
    gap = max(2, size // 10)
    thickness = max(1, size // 18)
    for i in range(3):
        y = top + i * gap
        if y + thickness >= page[3] - 2:
            break
        draw.rounded_rectangle(
            [left, y, right if i < 2 else left + (right - left) * 2 // 3, y + thickness],
            radius=thickness // 2,
            fill=line_color,
        )

    # Small lock badge (private)
    badge_r = max(3, size // 6)
    cx = card[2] - badge_r - margin // 2
    cy = card[3] - badge_r - margin // 2
    draw.ellipse(
        [cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r],
        fill=(4, 47, 46, 255),
    )
    # Lock body
    bw = max(2, badge_r // 2)
    bh = max(2, badge_r // 2)
    draw.rounded_rectangle(
        [cx - bw, cy - bh // 4, cx + bw, cy + bh],
        radius=max(1, bw // 3),
        fill=(204, 251, 241, 255),
    )
    # Lock shackle
    sh = max(1, badge_r // 3)
    draw.arc(
        [cx - bw + 1, cy - bh - sh, cx + bw - 1, cy - bh // 4 + sh],
        start=200,
        end=340,
        fill=(204, 251, 241, 255),
        width=max(1, size // 28),
    )
    return img


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [make_icon(s) for s in sizes]
    images[-1].save(OUT_PNG)
    images[0].save(OUT_ICO, formats=["ICO"], sizes=[(s, s) for s in sizes])
    # Pillow ICO: save from largest with append_images
    images[-1].save(
        OUT_ICO,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"Wrote {OUT_ICO} and {OUT_PNG}")


if __name__ == "__main__":
    main()
