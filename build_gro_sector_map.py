#!/usr/bin/env python3
"""Transcribe GRO 2024 Table A2.1 into gro2024_sector_groups.csv.

Source: UNEP IRP, Global Resources Outlook 2024, Methodological Annexes,
Annex 2 "From sectors to provisioning systems", Table A2.1, which assigns each
EXIOBASE3 industry to a resource group ("sector grouping GRO 2024") and a
provisioning system. The text dump of that table is gro_annex2_raw.txt (pypdf
extract of annex pages 6-11). This script parses it, matches each row to the
163 EXIOBASE industry names, and writes one row per EXIOBASE product (pxp)
through the product-to-industry concordance, which is one-to-one.

    python build_gro_sector_map.py <annex2_raw.txt>
"""
from pathlib import Path
import difflib
import re
import sys

import pandas as pd

HERE = Path(__file__).parent
RAW = Path(sys.argv[1])  # pypdf text of annex pages 6-11; not committed (UNEP text)
CONC = Path(r"D:\GitHub\EXIOBASE\00-concordances-public\concordances\exiobase\exiobase3p_exiobase3i.csv")
OUT = HERE / "gro2024_sector_groups.csv"

GROUPS = ["biomass", "fossil resources", "metals", "non-metallic minerals", "remaining economy"]
PROV = ["Water, sewage, health", "Built environment", "Energy\\*", "Food", "Clothing", "Mobility", "Other", "Education"]
g = "(" + "|".join(GROUPS) + ")"
ROW = re.compile(rf"^(?P<name>.+?)\s+{g}\s+{g}\s+(?P<prov>{'|'.join(PROV)})$")

text = RAW.read_text(encoding="utf-8")
text = text[text.index("Cultivation of paddy rice"):text.index("Households households households")]
lines = [l.strip() for l in text.splitlines()
         if l.strip() and not l.startswith(("===", "METHODOLOGICAL", "Global Resources Outlook"))
         and not re.fullmatch(r"\d+ \d+", l.strip())]
rows, buf = [], ""
for l in lines:
    buf = (buf + " " + l).strip()
    m = ROW.match(buf)
    if m:
        rows.append({"gro_name": m["name"], "group_2019": m.group(2), "group_2024": m.group(3),
                     "provisioning": m["prov"].replace("*", "")})
        buf = ""
assert not buf, f"unparsed tail: {buf!r}"
gro = pd.DataFrame(rows)
print(f"parsed {len(gro)} GRO rows")


def norm(s):
    s = re.sub(r"\(\d+\)", "", s.lower())
    s = s.replace("preciuos", "precious").replace("slugde", "sludge")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


conc = pd.read_csv(CONC)
inds = conc.drop_duplicates("target_name")[["target_code", "target_name"]]
key = {norm(n): n for n in inds.target_name}
match = {}
for n in gro.gro_name:
    k = norm(n)
    if k in key:
        match[n] = key[k]
    else:
        c = difflib.get_close_matches(k, key.keys(), n=1, cutoff=0.85)
        if c:
            match[n] = key[c[0]]
            print(f"  fuzzy: {n!r} -> {key[c[0]]!r}")
        else:
            print(f"  UNMATCHED GRO row: {n!r}")
gro["industry"] = gro.gro_name.map(match)
missing = sorted(set(inds.target_name) - set(gro.industry.dropna()))
for m in missing:
    print(f"  EXIOBASE industry with no GRO row: {m!r}")
if gro.industry.isna().any() or missing or gro.industry.duplicated().any():
    sys.exit("mapping incomplete, see above")

out = conc.merge(gro, left_on="target_name", right_on="industry", how="left")
out = out.rename(columns={"source_code": "product_code", "source_name": "product",
                          "target_code": "industry_code", "target_name": "industry_name"})
out = out[["product_code", "product", "industry_code", "industry_name", "gro_name",
           "group_2024", "group_2019", "provisioning"]]
out.to_csv(OUT, index=False, encoding="utf-8", lineterminator="\n")
print(f"Wrote {OUT.name}: {len(out)} products, groups: {out.group_2024.value_counts().to_dict()}")
