"""Draws the ChatBridge app icon (a teal-to-blue rounded square with a two-way arrow) into assets/chatbridge.ico."""
import os

from PIL import Image, ImageDraw

SIZE = 1024
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(here, "assets"), exist_ok=True)

# diagonal gradient, teal (top-left) to blue (bottom-right)
img = Image.new("RGBA", (SIZE, SIZE))
px = img.load()
a, b = (45, 212, 191), (96, 165, 250)
for y in range(SIZE):
    for x in range(SIZE):
        t = (x + y) / (2 * SIZE)
        px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=SIZE // 4, fill=255)
img.putalpha(mask)

d = ImageDraw.Draw(img)
ink, w = (6, 32, 29, 255), SIZE // 14
x0, x1, ya, yb = int(SIZE * .24), int(SIZE * .76), int(SIZE * .40), int(SIZE * .62)
head = int(SIZE * .10)
d.line((x0, ya, x1, ya), fill=ink, width=w)                                          # top arrow, pointing right
d.polygon([(x1 + head, ya), (x1 - head // 2, ya - head), (x1 - head // 2, ya + head)], fill=ink)
d.line((x0, yb, x1, yb), fill=ink, width=w)                                          # bottom arrow, pointing left
d.polygon([(x0 - head, yb), (x0 + head // 2, yb - head), (x0 + head // 2, yb + head)], fill=ink)

img.save(os.path.join(here, "assets", "chatbridge.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
img.resize((512, 512), Image.LANCZOS).save(os.path.join(here, "assets", "chatbridge.png"))
for s in (48, 96, 144, 192):   # crisp logos for the installer window at different screen scalings
    img.resize((s, s), Image.LANCZOS).save(os.path.join(here, "assets", f"installer-logo-{s}.png"))
os.makedirs(os.path.join(here, "extension", "icons"), exist_ok=True)
for s in (16, 48, 128):
    img.resize((s, s), Image.LANCZOS).save(os.path.join(here, "extension", "icons", f"{s}.png"))
print("icon written")
