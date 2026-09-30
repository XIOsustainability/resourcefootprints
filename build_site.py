#!/usr/bin/env python3
"""Build site/ for resourcefootprints.com.

  pages/index.html         -> site/index.html     (licence text inlined)
  explorer_template.html   -> site/explorer.html  (explorer-data.json inlined)

Every page is a fragment (<title>, <link>, <style>, then markup); this wraps
each in a full document with a shared head and nav bar.

    python build_site.py
"""
from datetime import date
from pathlib import Path
import html
import json
import re
import sys

HERE = Path(__file__).parent
SITE = HERE / "site"
LICENCE = Path(r"D:\indecol\Projects\MRIOs\EXIOBASE3\EXIOBASE_3_11_3\processed\zip\LICENSE.txt")
ORIGIN = "https://resourcefootprints.com"

TODAY = date.today().isoformat()
PUBLISHER = {"@type": "Organization", "name": "XIO Sustainability Analytics A/S", "url": "https://xio-sa.com"}
INDICATORS = ["Greenhouse gas emissions (GWP100, IPCC AR6)", "Net energy use", "Material extraction (domestic extraction used)",
              "Land use", "Cropland", "Pasture and grassland", "Blue water consumption", "Water stress (AWARE)",
              "Biodiversity loss from land use (UNEP GLAM)", "Biodiversity loss from freshwater eutrophication (UNEP GLAM)",
              "Fine particulate matter health impacts (UNEP GLAM)", "Value added", "Employment (hours and persons)"]
# name -> (path, <title>, meta description, JSON-LD objects)
PAGES = {
    "index": ("/", "Resource footprints | Country environmental footprints from EXIOBASE",
              "Environmental and socio-economic footprints of 44 countries and five rest-of-world regions, 1995-2024, from the EXIOBASE multi-regional input-output database.",
              [{"@context": "https://schema.org", "@type": "WebSite", "name": "Resource footprints", "url": ORIGIN + "/",
                "description": "Environmental and socio-economic footprints of 49 world regions, 1995-2024, calculated with EXIOBASE.",
                "inLanguage": "en", "publisher": PUBLISHER},
               {"@context": "https://schema.org", **PUBLISHER}]),
    "explorer": ("/explorer", "Country footprint explorer, 1995-2024 | Resource footprints",
                 "Production-based, consumption-based and import-embodied GHG, energy, material, land, water, biodiversity, health and employment results for 49 regions, 1995-2024, from EXIOBASE 3.11.3.",
                 [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Footprint explorer",
                   "url": ORIGIN + "/explorer", "applicationCategory": "EducationalApplication", "operatingSystem": "Any",
                   "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                   "publisher": PUBLISHER},
                  {"@context": "https://schema.org", "@type": "Dataset",
                   "name": "Environmental and socio-economic footprints of 49 world regions, 1995-2024 (EXIOBASE 3.11.3)",
                   "description": "Production-based, consumption-based and import-embodied results for 44 countries and 5 rest-of-world regions, 1995-2024, from EXIOBASE 3.11.3, with sector groups as in UNEP IRP Global Resources Outlook 2024, Table A2.1.",
                   "url": ORIGIN + "/explorer", "creator": PUBLISHER, "isAccessibleForFree": True,
                   "isBasedOn": {"@type": "Dataset", "name": "EXIOBASE 3.11.3"},
                   "temporalCoverage": "1995/2024", "spatialCoverage": {"@type": "Place", "name": "World"},
                   "measurementTechnique": "Environmentally extended multi-regional input-output analysis",
                   "variableMeasured": INDICATORS,
                   "keywords": ["carbon footprint", "material footprint", "consumption-based accounting", "EXIOBASE",
                                "multi-regional input-output", "biodiversity footprint", "water footprint", "Global Resources Outlook"],
                   "license": {"@type": "CreativeWork", "name": "EXIOBASE licence (dual commercial and non-commercial)", "url": ORIGIN + "/#licence"},
                   "dateModified": TODAY}]),
}
NAV_CSS = """<style>
.rf-nav{border-bottom:1px solid rgba(127,137,139,.35);font:500 14px/1.4 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
.rf-nav-in{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 20px;max-width:var(--rf-w);margin:0 auto;padding:12px var(--rf-pad)}
.rf-nav a{color:inherit;text-decoration:none;opacity:.78}
.rf-nav a:hover,.rf-nav a[aria-current="page"]{opacity:1}
.rf-nav a[aria-current="page"]{text-decoration:underline;text-underline-offset:4px}
.rf-nav .rf-home{font-weight:600;opacity:1;margin-right:auto}
.rf-nav a:focus-visible{outline:2px solid currentColor;outline-offset:2px}
@media (max-width:520px){.rf-nav-in{padding:10px 16px}}
</style>"""
# content column of each page, so the nav lines up with it: (max-width incl. padding, side padding, space below)
NAV_FRAME = {"index": ("1120px", "20px", "0"), "explorer": ("1500px", "20px", "0")}


def nav(current):
    links = [("/explorer", "Footprint explorer", "explorer")]
    cur = ' aria-current="page"'
    items = "".join(f'<a href="{h}"{cur if k == current else ""}>{n}</a>' for h, n, k in links)
    home = cur if current == "index" else ""
    w, pad, gap = NAV_FRAME[current]
    return (f'<nav class="rf-nav" aria-label="Site" style="--rf-w:{w};--rf-pad:{pad};margin-bottom:{gap}">'
            f'<div class="rf-nav-in"><a class="rf-home" href="/"{home}>Resource footprints</a>{items}</div></nav>\n')


NOSCRIPT = {"explorer": '<noscript><p style="padding:16px 20px;max-width:70ch">The footprint explorer requires JavaScript. It shows production-based, consumption-based and import-embodied GHG, energy, material, land, water, water stress, biodiversity loss, PM health, value added and employment for 49 regions, 1995-2024, from EXIOBASE 3.11.3. Licence and notes: <a href="/">home page</a>.</p></noscript>\n'}


def wrap(name, fragment, body_marker):
    path, title, desc, ld = PAGES[name]
    i = fragment.index(body_marker)
    head_part, body_part = fragment[:i], fragment[i:]
    head_part = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", head_part, count=1, flags=re.S)
    url = ORIGIN + path
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(o, ensure_ascii=False)}</script>\n' for o in ld)
    head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="en" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Resource footprints">
<meta property="og:locale" content="en">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:image" content="{ORIGIN}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="World greenhouse gas emissions by resource group, from EXIOBASE">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(title)}">
<meta name="twitter:description" content="{html.escape(desc)}">
<meta name="twitter:image" content="{ORIGIN}/og-image.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#0d5f58">
{ld_html}
<style>[hidden]{{display:none!important}}img{{max-width:100%}}</style>
"""
    return head + head_part + NAV_CSS + "\n</head>\n<body>\n" + nav(name) + NOSCRIPT.get(name, "") + body_part + "\n</body>\n</html>\n"


def write(name, text):
    out = SITE / f"{name}.html"
    if not text.rstrip().endswith("</html>") or "__EXIO_DATA__" in text or "__LICENCE__" in text or "__FIGURES__" in text:
        sys.exit(f"{name}: generated page looks broken")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {out.relative_to(HERE)}: {len(text):,} chars")


licence = html.escape(LICENCE.read_text(encoding="utf-8").strip())

# landing page
from home_figures import render as render_figures
idx = (HERE / "pages" / "index.html").read_text(encoding="utf-8").replace("__LICENCE__", licence)
idx = idx.replace("__FIGURES__", render_figures(json.loads((HERE / "explorer-data.json").read_text(encoding="utf-8"))))
write("index", wrap("index", idx, '<div class="wrap">'))

# explorer
tpl = (HERE / "explorer_template.html").read_text(encoding="utf-8")
data = (HERE / "explorer-data.json").read_text(encoding="utf-8")
d = json.loads(data)
if len(d["regions"]) != 49 or "rg" not in d or "function refresh()" not in tpl or tpl.count("/*__DATA__*/") != 1:
    sys.exit("explorer inputs look broken")
if not (SITE / "explorer-sankey.json").exists():
    sys.exit("site/explorer-sankey.json missing; run build_explorer_data.py")
write("explorer", wrap("explorer", tpl.replace("/*__DATA__*/", "window.EXIO=" + data + ";"), '<div class="wrap">'))


# sitemap: the three real pages, extensionless, with today's build date
urls = "".join(f"  <url><loc>{ORIGIN}{p[0]}</loc><lastmod>{TODAY}</lastmod></url>\n" for p in PAGES.values())
(SITE / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                  + urls + "</urlset>\n", encoding="utf-8", newline="\n")
print("Wrote site/sitemap.xml")
