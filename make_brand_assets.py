#!/usr/bin/env python3
"""Write site/og-image.png (1200x630), site/favicon-32.png and site/apple-touch-icon.png.

The share card carries one real figure: world greenhouse gas emissions in the
latest year of explorer-flows.json, split by the resource group of the sector
where they occur. Uses the Inter variable font from vector_website/fonts.

    python make_brand_assets.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SITE = HERE / "site"
FONT = Path(r"D:\GitHub\vector_website\fonts\Inter-Variable.ttf")
GROUND, INK, INK2, ACCENT, PALE = "#f3f5f4", "#121a1c", "#4c5659", "#0d5f58", "#dcefec"
GROUPS = [("biomass", "Biomass", "#2a78d6"), ("fossil resources", "Fossil resources", "#eb6834"),
          ("metals", "Metals", "#1baf7a"), ("non-metallic minerals", "Non-metallic minerals", "#eda100"),
          ("remaining economy", "Remaining economy", "#c3cbca"), ("households", "Households (direct)", "#e87ba4")]


def font(size, weight="Regular"):
    f = ImageFont.truetype(str(FONT), size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


d = json.loads((HERE / "explorer-flows.json").read_text(encoding="utf-8"))
k, yr = "GWP100 - AR6 - total", d["years"][-1]
t = d["years"].index(yr)
tot = {g: sum(d["rg"]["PBA"][k][r][g][t] or 0 for r in d["regions"]) for g, _, _ in GROUPS}
T = sum(tot.values())

W, H = 1200, 630
im = Image.new("RGB", (W, H), GROUND)
dr = ImageDraw.Draw(im)
dr.rectangle([0, 0, W, 10], fill=ACCENT)
dr.text((72, 78), "Resource footprints", font=font(76, "Bold"), fill=INK)
dr.text((72, 180), "Environmental footprints of 49 world regions, 1995-2024,", font=font(34), fill=INK2)
dr.text((72, 224), "calculated with the EXIOBASE input-output database", font=font(34), fill=INK2)
dr.text((72, 330), f"World greenhouse gas emissions {yr}, {T / 1e12:.1f} Gt CO2-eq, by where they occur",
        font=font(26, "SemiBold"), fill=INK)
x, y0, y1, w = 72, 380, 440, W - 144
for g, _, col in GROUPS:
    seg = w * tot[g] / T
    dr.rounded_rectangle([x, y0, x + seg - 4, y1], radius=4, fill=col)
    x += seg
lx, ly = 72, 470
for g, name, col in GROUPS:
    label = f"{name} {100 * tot[g] / T:.0f}%"
    dr.rounded_rectangle([lx, ly + 6, lx + 18, ly + 24], radius=3, fill=col)
    dr.text((lx + 28, ly), label, font=font(24), fill=INK2)
    lx += 36 + dr.textlength(label, font=font(24))
    if lx > W - 300:
        lx, ly = 72, ly + 40
dr.text((72, H - 64), "resourcefootprints.com", font=font(26, "SemiBold"), fill=ACCENT)
im.save(SITE / "og-image.png", optimize=True)


def icon(size):
    s = 8
    big = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    g = ImageDraw.Draw(big)
    u = size * s / 32
    g.rounded_rectangle([0, 0, size * s - 1, size * s - 1], radius=int(6 * u), fill=ACCENT)
    for bx, by, bw in [(6, 18, 4), (12, 12, 4), (18, 8, 4), (24, 14, 3)]:
        g.rounded_rectangle([bx * u, by * u, (bx + bw) * u, 26 * u], radius=int(u), fill=PALE)
    return big.resize((size, size), Image.LANCZOS)


icon(32).save(SITE / "favicon-32.png")
icon(180).convert("RGB").save(SITE / "apple-touch-icon.png")
print(f"og-image.png: world GHG {yr} {T / 1e12:.2f} Gt; icons written")
