#!/usr/bin/env python3
"""Build site/ for resourcefootprints.com.

  pages/index.html         -> site/index.html     (licence text inlined)
  explorer_template.html   -> site/explorer.html  (explorer-data.json inlined)
  00-workflow coverage     -> site/coverage.html  (coverage_data.js inlined)

Every page is a fragment (<title>, <link>, <style>, then markup); this wraps
each in a full document with a shared head and nav bar. The coverage page is
read from 00-workflow/reference/coverage_page, which stays its single source.

    python build_site.py
"""
from pathlib import Path
import html
import json
import sys

HERE = Path(__file__).parent
SITE = HERE / "site"
COVERAGE_DIR = Path(r"D:\GitHub\EXIOBASE\00-workflow\reference\coverage_page")
LICENCE = Path(r"D:\indecol\Projects\MRIOs\EXIOBASE3\EXIOBASE_3_11_3\processed\zip\LICENSE.txt")
ORIGIN = "https://resourcefootprints.com"

PAGES = {
    "index": ("/", "Environmental and socio-economic footprints of 44 countries and five rest-of-world regions, 1995-2024, from the EXIOBASE multi-regional input-output database."),
    "explorer": ("/explorer", "Production, consumption and import-embodied greenhouse gas, energy, material, land, water, biodiversity, health and employment results by country and region, 1995-2024, split by resource group and traced through supply chains, from EXIOBASE 3.11.3."),
    "coverage": ("/coverage", "Which years of each EXIOBASE account rest on reported data and which are projected, and which impact assessment methods are available, for every release from 3.8.2 to 3.12."),
}
NAV_CSS = """<style>
.rf-nav{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 20px;padding:10px max(16px,calc((100% - 1500px) / 2 + 20px));border-bottom:1px solid rgba(127,137,139,.35);font:500 14px/1.4 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
.rf-nav a{color:inherit;text-decoration:none;opacity:.78}
.rf-nav a:hover,.rf-nav a[aria-current="page"]{opacity:1}
.rf-nav a[aria-current="page"]{text-decoration:underline;text-underline-offset:4px}
.rf-nav .rf-home{font-weight:600;opacity:1;margin-right:auto}
.rf-nav a:focus-visible{outline:2px solid currentColor;outline-offset:2px}
</style>"""


def nav(current):
    links = [("/explorer", "Footprint explorer", "explorer"), ("/coverage", "Data coverage", "coverage")]
    cur = ' aria-current="page"'
    items = "".join(f'<a href="{h}"{cur if k == current else ""}>{n}</a>' for h, n, k in links)
    home = cur if current == "index" else ""
    return f'<nav class="rf-nav" aria-label="Site"><a class="rf-home" href="/"{home}>Resource footprints</a>{items}</nav>\n'


def wrap(name, fragment, body_marker):
    path, desc = PAGES[name]
    i = fragment.index(body_marker)
    head_part, body_part = fragment[:i], fragment[i:]
    head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{ORIGIN}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Resource footprints">
<meta property="og:url" content="{ORIGIN}{path}">
<meta property="og:description" content="{html.escape(desc)}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#0d5f58">
<style>[hidden]{{display:none!important}}img{{max-width:100%}}</style>
"""
    return head + head_part + NAV_CSS + "\n</head>\n<body>\n" + nav(name) + body_part + "\n</body>\n</html>\n"


def write(name, text):
    out = SITE / f"{name}.html"
    if not text.rstrip().endswith("</html>") or "__EXIO_DATA__" in text or "__LICENCE__" in text:
        sys.exit(f"{name}: generated page looks broken")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {out.relative_to(HERE)}: {len(text):,} chars")


licence = html.escape(LICENCE.read_text(encoding="utf-8").strip())

# landing page
idx = (HERE / "pages" / "index.html").read_text(encoding="utf-8").replace("__LICENCE__", licence)
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

# coverage, from 00-workflow
cov = (COVERAGE_DIR / "exiobase_coverage.html").read_text(encoding="utf-8")
cov_data = (COVERAGE_DIR / "coverage_data.js").read_text(encoding="utf-8")
tag = '<script src="coverage_data.js"></script>'
if cov.count(tag) != 1 or not cov.startswith("<title>"):
    sys.exit("the 00-workflow coverage page changed shape; update build_site.py")
cov = cov.replace(tag, "<script>\n" + cov_data + "\n</script>")
cov = cov.replace(cov[:cov.index("</title>") + 8], "<title>Data coverage | Resource footprints</title>", 1)
write("coverage", wrap("coverage", cov, '<div class="wrap">'))
