#!/usr/bin/env python3
"""compare.py RUN_DIR: per-map side-by-side sheets and an automated difference check.

Columns: g14-ref (the reference, run_full.py --device g14 --package ref), deck-appimage, nova-appimage,
deck-flatpak, nova-flatpak. Needs numpy and Pillow.
Writes RUN_DIR/contactsheets/<map>.png, RUN_DIR/compare.json and RUN_DIR/compare.html.

Difference check (crude on purpose; the user judges): both shots are cut to the same 16:10 centre region (Nova's
screen is 4:3, so its sides keep and top/bottom lose a band), the top 15 percent and bottom 20 percent are left
out (HUD, letterbox), resized to 160x100 grey. Score = mean absolute difference (0-255) and a block SSIM. Timing
driven content (cutscene frame, bots, particles) differs between any two runs, so only large values are flags.
Also flagged on any shot: mostly black, a pink/magenta area, a nearly flat image.
"""
import argparse
import html
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import devices

RUN = None      # set by main()
COLS = ["g14-ref", "deck-appimage", "nova-appimage", "deck-flatpak", "nova-flatpak"]
MAPS = devices.SP + devices.MP
DIFF_FLAG = 45.0      # mean abs difference of the centre region against the reference
SSIM_FLAG = 0.25
PAIRS = [("deck-appimage", "g14-ref"), ("nova-appimage", "g14-ref"), ("deck-flatpak", "deck-appimage"),
         ("nova-flatpak", "nova-appimage"), ("deck-flatpak", "g14-ref"), ("nova-flatpak", "g14-ref")]


def load(col, name):
    p = RUN / "screenshots" / col / (name + ".png")
    return Image.open(p).convert("RGB") if p.exists() else None


def centre(img):
    w, h = img.size
    th = int(w * 10 / 16)
    if th < h:      # taller than 16:10 (the Nova): cut a band off top and bottom
        top = (h - th) // 2
        img = img.crop((0, top, w, top + th))
    h = img.size[1]
    img = img.crop((0, int(h * 0.15), w, int(h * 0.80)))
    return img.convert("L").resize((160, 100), Image.BILINEAR)


def block_ssim(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    c1, c2 = 6.5025, 58.5225
    scores = []
    for y in range(0, 96, 8):
        for x in range(0, 160, 8):
            p, q = a[y:y + 8, x:x + 8], b[y:y + 8, x:x + 8]
            mp, mq = p.mean(), q.mean()
            vp, vq = p.var(), q.var()
            cov = ((p - mp) * (q - mq)).mean()
            scores.append(((2 * mp * mq + c1) * (2 * cov + c2)) / ((mp ** 2 + mq ** 2 + c1) * (vp + vq + c2)))
    return float(np.mean(scores))


def sanity(img):
    arr = np.asarray(img.resize((320, 200)), dtype=np.int32)
    h = arr.shape[0]
    body = arr[int(h * 0.12):int(h * 0.88)]      # without letterbox bars
    lum = body.mean(axis=2)
    flags = []
    if (lum < 10).mean() > 0.7:
        flags.append("mostly black %.0f%%" % (100 * (lum < 10).mean()))
    magenta = ((body[..., 0] > 200) & (body[..., 1] < 70) & (body[..., 2] > 200)).mean()
    if magenta > 0.01:
        flags.append("pink area %.1f%%" % (100 * magenta))
    if body.std() < 6:
        flags.append("flat image (std %.1f)" % body.std())
    return flags


def montage(name, imgs):
    tw, th = 400, 260
    sheet = Image.new("RGB", (tw * len(COLS), th + 22), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, col in enumerate(COLS):
        d.text((i * tw + 4, 4), "%s %s" % (name, col), fill=(220, 220, 220))
        im = imgs.get(col)
        if im is not None:
            sheet.paste(im.resize((tw - 4, th - 4)), (i * tw + 2, 22))
    return sheet


def main():
    global RUN
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="a run directory written by run_full.py (screenshots/<column>/<map>.png)")
    RUN = Path(ap.parse_args().run_dir)
    out = RUN / "contactsheets"
    out.mkdir(exist_ok=True)
    result = {}
    for name in MAPS:
        imgs = {c: load(c, name) for c in COLS}
        have = {c: im for c, im in imgs.items() if im is not None}
        if not have:
            continue
        montage(name, imgs).save(out / (name + ".png"))
        entry = {"present": sorted(have), "pairs": {}, "flags": []}
        for c, im in have.items():
            for f in sanity(im):
                entry["flags"].append("%s: %s" % (c, f))
        for a, b in PAIRS:
            if a in have and b in have:
                ca, cb = centre(have[a]), centre(have[b])
                diff = float(np.abs(np.asarray(ca, dtype=np.float64) - np.asarray(cb, dtype=np.float64)).mean())
                ssim = block_ssim(ca, cb)
                entry["pairs"]["%s vs %s" % (a, b)] = {"mad": round(diff, 1), "ssim": round(ssim, 2)}
                if b == "g14-ref" and (diff > DIFF_FLAG or ssim < SSIM_FLAG):
                    entry["flags"].append("%s differs from the G14: mad %.1f ssim %.2f" % (a, diff, ssim))
                if b != "g14-ref" and (diff > DIFF_FLAG or ssim < SSIM_FLAG):
                    entry["flags"].append("%s differs from %s: mad %.1f ssim %.2f" % (a, b, diff, ssim))
        result[name] = entry
    (RUN / "compare.json").write_text(json.dumps(result, indent=1))
    css = ("body{font:13px system-ui;background:#111;color:#ddd;margin:12px}.flag{color:#fc6}.ok{color:#6c6}"
           "img{max-width:100%}small{color:#999}")
    rows = []
    for name, e in result.items():
        flags = ("".join("<div class=flag>%s</div>" % html.escape(f) for f in e["flags"])
                 or "<span class=ok>no flags</span>")
        pairs = "<br>".join("%s: mad %s, ssim %s" % (html.escape(k), v["mad"], v["ssim"])
                            for k, v in e["pairs"].items())
        rows.append("<h3>%s</h3><a href='contactsheets/%s.png'><img src='contactsheets/%s.png'></a><br>%s<br>"
                    "<small>%s</small>" % (name, name, name, flags, pairs))
    flagged = [n for n, e in result.items() if e["flags"]]
    page = ("<!doctype html><meta charset=utf-8><title>OpenCE compare</title><style>%s</style>"
            "<h2>%s: %d maps, %d flagged</h2>%s" % (css, html.escape(RUN.name), len(result), len(flagged),
                                                    "".join(rows)))
    (RUN / "compare.html").write_text(page)
    print("%d maps compared, %d flagged" % (len(result), len(flagged)))
    for n in flagged:
        for f in result[n]["flags"]:
            print("%-15s %s" % (n, f))


if __name__ == "__main__":
    main()
