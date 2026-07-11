"""One-off script to generate PWA icons matching the app's dark-navy /
accent-blue palette (see :root in frontend/src/assets/main.css). Run once
locally with `python generate_icons.py`; not part of the build pipeline.
Outputs go to ../public/ so Vite copies them to dist/ as static assets."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PUBLIC_DIR = Path(__file__).parent.parent / "public"
ICONS_DIR = PUBLIC_DIR / "icons"

BG = (19, 27, 48, 255)       # --bg-card
ACCENT = (59, 130, 246, 255)  # --accent-blue


def make_icon(size, maskable=False, path=None):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Maskable icons need a safe-zone margin (~10%) since OS may crop to a circle.
    margin = int(size * 0.16) if maskable else 0
    radius = int(size * 0.22) if not maskable else 0
    box = [margin, margin, size - margin, size - margin]
    if maskable:
        draw.rectangle(box, fill=BG)
    else:
        draw.rounded_rectangle(box, radius=radius, fill=BG)

    font_size = int(size * 0.52)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", font_size)
    text = "F"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill=ACCENT)
    img.save(path)


make_icon(192, maskable=False, path=str(ICONS_DIR / "icon-192.png"))
make_icon(512, maskable=False, path=str(ICONS_DIR / "icon-512.png"))
make_icon(512, maskable=True, path=str(ICONS_DIR / "icon-maskable-512.png"))

# index.html has always referenced /favicon.ico but the file never existed
# (silent 404) — the PWA service worker's cache.addAll() for the app shell
# is all-or-nothing, so a missing favicon would break shell precaching too.
favicon = Image.open(ICONS_DIR / "icon-512.png")
favicon.save(PUBLIC_DIR / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
print("done")
