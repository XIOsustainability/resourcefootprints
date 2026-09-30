"""Static SVG figures for the landing page, computed from explorer-data.json.

Each function returns (title, caption, svg). Colours are CSS variables defined
on the landing page, so the figures follow its light and dark themes.
"""
import html

GRP = [("biomass", "Biomass", "var(--s1)"), ("fossil resources", "Fossil resources", "var(--s2)"),
       ("metals", "Metals", "var(--s3)"), ("non-metallic minerals", "Non-metallic minerals", "var(--s4)"),
       ("remaining economy", "Remaining economy", "var(--rest)"), ("households", "Households (direct)", "var(--s5)")]
MAT = [("Domestic Extraction Used - Primary Crops", "Primary crops", "var(--s1)"),
       ("Domestic Extraction Used - Crop residues", "Crop residues", "var(--s3)"),
       ("Domestic Extraction Used - Forestry", "Forestry", "var(--s6)"),
       ("Domestic Extraction Used - Non-Metallic Minerals", "Non-metallic minerals", "var(--s4)"),
       ("Domestic Extraction Used - Metal Ores", "Metal ores", "var(--s2)")]
ADV_NAME = "Advanced economies"
EME_NAME = "Emerging and developing"


def _sum(d, regs, acc, ind):
    n = len(d["years"])
    out = []
    for t in range(n):
        vals = [d["values"][r][acc][ind][t] for r in regs]
        out.append(None if any(v is None for v in vals) else sum(vals))
    return out


def _pop(d, regs):
    n = len(d["years"])
    return [None if any(d["macro"][r]["population"][t] is None for r in regs)
            else sum(d["macro"][r]["population"][t] for r in regs) for t in range(n)]


def _fmt(v, dec=0):
    return f"{v:,.{dec}f}"


def ghg_by_group(d):
    yrs, regs = d["years"], d["regions"]
    t = yrs.index(max(yrs))
    tot = {g: sum(d["rg"]["PBA"]["GWP100 - AR6 - total"][r][g][t] or 0 for r in regs) for g, _, _ in GRP}
    T = sum(tot.values())
    W, x = 340, 0.0
    bars, legend = [], []
    for i, (g, name, col) in enumerate(GRP):
        w = W * tot[g] / T
        bars.append(f'<rect x="{x:.1f}" y="8" width="{max(0, w - 2):.1f}" height="34" rx="3" fill="{col}"/>')
        x += w
        row, colx = divmod(i, 2)
        lx, ly = colx * 172, 66 + row * 24
        legend.append(f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" rx="2" fill="{col}"/>'
                      f'<text x="{lx + 17}" y="{ly}" class="lab">{html.escape(name)} <tspan class="num">{100 * tot[g] / T:.0f}%</tspan></text>')
    svg = (f'<svg viewBox="0 0 340 134" role="img" aria-label="World greenhouse gas emissions {yrs[t]} by sector group">'
           + "".join(bars) + "".join(legend) + "</svg>")
    return (f"World GHG emissions by sector group, {yrs[t]}",
            f"{T / 1e12:.1f} Gt CO₂-eq, production-based. Sector groups as in the Global Resources Outlook 2024.", svg)


def ghg_per_capita(d):
    yrs, regs = d["years"], d["regions"]
    adv = d["advanced"]
    eme = [r for r in regs if r not in adv]
    series = []
    for name, members, col in [(ADV_NAME, adv, "var(--s1)"), (EME_NAME, eme, "var(--s2)")]:
        v, p = _sum(d, members, "CBA", "GWP100 - AR6 - total"), _pop(d, members)
        series.append((name, col, [None if a is None or b is None else a / b / 1e3 for a, b in zip(v, p)]))
    last = max(i for i in range(len(yrs)) if all(s[2][i] is not None for s in series))
    hi = max(max(x for x in s[2][:last + 1] if x is not None) for s in series)
    top = (int(hi / 5) + 1) * 5
    L, R, T_, B, W, H = 30, 92, 8, 22, 340, 150
    sx = lambda i: L + (W - L - R) * i / last
    sy = lambda v: T_ + (H - T_ - B) * (1 - v / top)
    g = []
    for v in range(0, top + 1, 5):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="grid"/>'
                 f'<text x="{L - 6}" y="{sy(v) + 4:.1f}" class="num" text-anchor="end">{v}</text>')
    for i in (0, last):
        g.append(f'<text x="{sx(i):.1f}" y="{H - 4}" class="num" text-anchor="middle">{yrs[i]}</text>')
    for name, col, s in series:
        pts = " ".join(f"{sx(i):.1f},{sy(s[i]):.1f}" for i in range(last + 1))
        g.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" stroke-linejoin="round"/>')
        g.append(f'<circle cx="{sx(last):.1f}" cy="{sy(s[last]):.1f}" r="3" fill="{col}"/>')
        g.append(f'<text x="{sx(last) + 7:.1f}" y="{sy(s[last]) + 4:.1f}" class="lab">{"Advanced" if name == ADV_NAME else "Emerging"} <tspan class="num">{s[last]:.1f}</tspan></text>')
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Consumption-based GHG per person">' + "".join(g) + "</svg>"
    return (f"Consumption-based GHG per person, {yrs[0]}-{yrs[last]}",
            "t CO₂-eq per person. Advanced economies and emerging and developing economies (IMF groups).", svg)


def materials(d):
    yrs, regs = d["years"], d["regions"]
    n = len(yrs)
    total = _sum(d, regs, "PBA", "Domestic Extraction Used - Total")
    parts = [(name, col, _sum(d, regs, "PBA", ind)) for ind, name, col in MAT]
    rest = [total[t] - sum(p[2][t] for p in parts) for t in range(n)]
    layers = parts + [("Other, incl. fossil fuels and grazing", "var(--rest)", rest)]
    top_v = max(total) / 1e6
    top = (int(top_v / 25) + 1) * 25
    L, R, T_, B, W, H = 30, 8, 8, 22, 340, 150
    sx = lambda i: L + (W - L - R) * i / (n - 1)
    sy = lambda v: T_ + (H - T_ - B) * (1 - v / top)
    g = []
    for v in range(0, top + 1, 25):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="grid"/>'
                 f'<text x="{L - 6}" y="{sy(v) + 4:.1f}" class="num" text-anchor="end">{v}</text>')
    base = [0.0] * n
    for name, col, s in layers:
        topl = [base[t] + s[t] / 1e6 for t in range(n)]
        up = " ".join(f"{sx(t):.1f},{sy(topl[t]):.1f}" for t in range(n))
        dn = " ".join(f"{sx(t):.1f},{sy(base[t]):.1f}" for t in reversed(range(n)))
        g.append(f'<polygon points="{up} {dn}" fill="{col}" stroke="var(--surface)" stroke-width="1"/>')
        base = topl
    cf = yrs.index(2021)
    g.append(f'<rect x="{sx(cf):.1f}" y="{T_}" width="{sx(n - 1) - sx(cf):.1f}" height="{H - T_ - B}" fill="var(--surface)" opacity=".45"/>')
    for i in (0, n - 1):
        g.append(f'<text x="{sx(i):.1f}" y="{H - 4}" class="num" text-anchor="{"start" if i == 0 else "end"}">{yrs[i]}</text>')
    legend = "".join(f'<span><i style="background:{col}"></i>{html.escape(name)}</span>' for name, col, _ in layers)
    svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="World material extraction by type">' + "".join(g) + "</svg>"
    return (f"World material extraction by type, {yrs[0]}-{yrs[-1]}",
            f"Gt per year. {total[-1] / 1e6:.0f} Gt in {yrs[-1]}. Shaded: 2021-{yrs[-1]}, carried forward.",
            svg + f'<div class="leg">{legend}</div>')


def render(d):
    out = []
    for fn in (ghg_by_group, ghg_per_capita, materials):
        title, cap, svg = fn(d)
        out.append(f'<a class="fig" href="/explorer"><h2>{html.escape(title)}</h2>{svg}<p>{html.escape(cap)}</p></a>')
    return '<div class="figs">' + "".join(out) + "</div>"
