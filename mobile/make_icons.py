"""Draws the phone app icons. Run from the project root:
    python mobile/make_icons.py preview        -> mobile/icon-preview.png   (three options, as Android crops them)
    python mobile/make_icons.py build <a|b|c>  -> writes the Android launcher icons for that option
The artwork stays inside the middle 60% so it survives every shape Android crops icons to."""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
S, SS = 1024, 4          # icon size, supersampling

OPTIONS = {
    "a": {"name": "A. Day: indigo",        "bg": (91, 91, 214),  "fg": (255, 255, 255), "note": "matches the light look"},
    "b": {"name": "B. Night: mint on dark", "bg": (14, 17, 22),  "fg": (61, 219, 176),  "note": "matches the night look"},
    "c": {"name": "C. Family: teal to blue", "bg": ((45, 212, 191), (96, 165, 250)), "fg": (6, 32, 29), "note": "same colors as the Windows app"},
}


def background(spec):
    if isinstance(spec[0], int):
        return Image.new("RGBA", (S, S), spec + (255,))
    img = Image.new("RGBA", (S, S))
    px, (a, b) = img.load(), spec
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    return img


def arrows(color):
    """Two-way arrows with round ends, on a transparent canvas (the foreground layer)."""
    big = S * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(big * 0.062)
    x0, x1 = int(big * 0.27), int(big * 0.73)
    ya, yb = int(big * 0.405), int(big * 0.595)
    head = int(big * 0.075)
    col = color + (255,)

    def arrow(y, x_from, x_to):
        d.line((x_from, y, x_to, y), fill=col, width=w)
        sgn = 1 if x_to > x_from else -1
        d.line((x_to - sgn * head, y - head, x_to, y), fill=col, width=w)
        d.line((x_to - sgn * head, y + head, x_to, y), fill=col, width=w)
        for (cx, cy) in ((x_from, y), (x_to, y), (x_to - sgn * head, y - head), (x_to - sgn * head, y + head)):
            d.ellipse((cx - w // 2, cy - w // 2, cx + w // 2, cy + w // 2), fill=col)
    arrow(ya, x0, x1)
    arrow(yb, x1, x0)
    return img.resize((S, S), Image.LANCZOS)


def full_icon(opt):
    base = background(opt["bg"]).copy()
    base.alpha_composite(arrows(opt["fg"]))
    return base


def masked(img, shape, size):
    m = Image.new("L", (S * 2, S * 2), 0)
    d = ImageDraw.Draw(m)
    box = (0, 0, S * 2 - 1, S * 2 - 1)
    if shape == "circle":
        d.ellipse(box, fill=255)
    else:
        d.rounded_rectangle(box, radius=int(S * 2 * 0.24), fill=255)
    m = m.resize((size, size), Image.LANCZOS)
    out = img.resize((size, size), Image.LANCZOS)
    out.putalpha(m)
    return out


def preview():
    f = lambda sz, bold=False: ImageFont.truetype(r"C:\Windows\Fonts\segoeui%s.ttf" % ("b" if bold else ""), sz)
    W, H = 3 * 330 + 40, 520
    sheet = Image.new("RGBA", (W, H), (246, 244, 240, 255))
    d = ImageDraw.Draw(sheet)
    for i, (key, opt) in enumerate(OPTIONS.items()):
        x = 20 + i * 330
        ic = full_icon(opt)
        sheet.alpha_composite(masked(ic, "squircle", 180), (x + 5, 30))
        sheet.alpha_composite(masked(ic, "circle", 130), (x + 195, 55))
        sheet.alpha_composite(masked(ic, "squircle", 64), (x + 40, 240))
        sheet.alpha_composite(masked(ic, "squircle", 40), (x + 125, 252))
        d.text((x + 5, 330), opt["name"], font=f(22, True), fill=(30, 30, 30, 255))
        d.text((x + 5, 362), opt["note"], font=f(18), fill=(110, 105, 98, 255))
        # how it looks on a dark and a light home screen
        for j, bgc in enumerate(((22, 24, 30, 255), (230, 232, 238, 255))):
            d.rounded_rectangle((x + 5 + j * 150, 410, x + 145 + j * 150, 500), radius=14, fill=bgc)
            sheet.alpha_composite(masked(ic, "squircle", 56), (x + 47 + j * 150, 427))
    sheet.convert("RGB").save(os.path.join(HERE, "icon-preview.png"))
    print("wrote mobile/icon-preview.png")


def build(key):
    opt = OPTIONS[key]
    res = os.path.join(HERE, "android", "app", "src", "main", "res")
    legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    fg_size = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
    ic = full_icon(opt)
    fg = arrows(opt["fg"])
    for dens, px in legacy.items():
        folder = os.path.join(res, "mipmap-" + dens)
        os.makedirs(folder, exist_ok=True)
        masked(ic, "squircle", px).save(os.path.join(folder, "ic_launcher.png"))
        masked(ic, "circle", px).save(os.path.join(folder, "ic_launcher_round.png"))
        fg.resize((fg_size[dens], fg_size[dens]), Image.LANCZOS).save(os.path.join(folder, "ic_launcher_foreground.png"))
    # the adaptive icon: a flat colour (or the gradient picture) behind the arrows
    anydpi = os.path.join(res, "mipmap-anydpi-v26")
    os.makedirs(anydpi, exist_ok=True)
    bg_png = isinstance(opt["bg"][0], tuple)
    if bg_png:
        for dens, px in fg_size.items():
            background(opt["bg"]).resize((px, px), Image.LANCZOS).save(os.path.join(res, "mipmap-" + dens, "ic_launcher_background.png"))
    else:
        values = os.path.join(res, "values")
        os.makedirs(values, exist_ok=True)
        with open(os.path.join(values, "ic_launcher_background.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#%02X%02X%02X</color>\n</resources>\n' % opt["bg"])
    bg_ref = "@mipmap/ic_launcher_background" if bg_png else "@color/ic_launcher_background"
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
           f'    <background android:drawable="{bg_ref}"/>\n    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n</adaptive-icon>\n')
    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        with open(os.path.join(anydpi, name), "w", encoding="utf-8") as f:
            f.write(xml)
    # drop the template's old vector icon files so they don't shadow ours
    for stale in (os.path.join(res, "drawable-v24", "ic_launcher_foreground.xml"), os.path.join(res, "drawable", "ic_launcher_background.xml")):
        if os.path.exists(stale):
            os.remove(stale)
    ic.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "icon-512.png"))   # the picture the Play Store asks for
    print("built icon option", key)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build" and len(sys.argv) > 2 and sys.argv[2] in OPTIONS:
        build(sys.argv[2])
    else:
        preview()
