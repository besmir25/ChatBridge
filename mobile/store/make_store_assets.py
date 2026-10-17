"""Makes the Google Play feature graphic (1024 x 500). Run from the project root:  python mobile/store/make_store_assets.py"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import make_icons

W, H = 1024, 500
a, b = (45, 212, 191), (96, 165, 250)          # the app's teal to blue
img = Image.new("RGB", (W, H))
px = img.load()
for y in range(H):
    for x in range(W):
        t = (x / W * 0.7 + y / H * 0.3)
        px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

icon = make_icons.full_icon(make_icons.OPTIONS["c"]).resize((250, 250), Image.LANCZOS)
mask = Image.new("L", (250, 250), 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, 249, 249), radius=62, fill=255)
tile = Image.new("RGB", (290, 290), (255, 255, 255))                 # a white tile so the icon stands out from the gradient
tmask = Image.new("L", (290, 290), 0)
ImageDraw.Draw(tmask).rounded_rectangle((0, 0, 289, 289), radius=76, fill=255)
img.paste(tile, (70, 105), tmask)
img.paste(icon, (90, 125), mask)

d = ImageDraw.Draw(img)
def font(name, size):
    for path in (r"C:\Windows\Fonts\%s.ttf" % name, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()
ink = (6, 32, 29)
d.text((380, 120), "ChatBridge", font=font("segoeuib", 78), fill=ink)
d.text((384, 224), "Move any AI chat, or just part of it,", font=font("segoeui", 34), fill=ink)
d.text((384, 270), "to another AI app.", font=font("segoeui", 34), fill=ink)
d.text((384, 352), "Private  \u00b7  No account  \u00b7  Free", font=font("segoeuib", 30), fill=ink)
out = os.path.join(HERE, "feature-graphic.png")
img.save(out)
print("wrote", out, img.size)
