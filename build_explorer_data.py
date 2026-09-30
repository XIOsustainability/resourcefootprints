#!/usr/bin/env python3
"""Write explorer-data.json and explorer-sankey.json.

Inputs:
  <cache>/impacts_pba_cba.parquet   exio_results' region x year x indicator x account cache,
                                    plus population and GDP (the 18 headline indicators)
  explorer-flows.json               build_explorer_flows.py, from the per-year MRIO: resource
                                    groups, consumption by category, four further indicators
                                    (water stress, two biodiversity rows, PM health) and the
                                    sankey tensors

Only the 49 EXIOBASE regions are written; the page sums them into every group.
Checks, each of which stops the script:
  - the cached Global and Advanced rows equal the sum of their members;
  - for the indicators both sources carry, the flow pass's PBA / CBA / imports
    totals equal the cache (so both halves of the page describe one model);
  - consumption by category and by resource group each sum to the CBA total.

The cached "total non combustion" GHG row misses SF6, HFC, PFC and NF3 (the
characterisation table has no rule for the first three and an unescaped NF3
regex), so it is written as total minus combustion.

    python build_explorer_data.py [cache_dir]
"""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CACHE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"D:\indecol\Projects\MRIOs\EXIOBASE3\EXIOBASE_3_11_3\calculated\impacts\time_series\_data")
GROUPS_CSV = Path(r"D:\GitHub\EXIOBASE\exio_results\auxiliary\EXIOBASE30r_EUAdvEmer_list.csv")
FLOWS = HERE / "explorer-flows.json"
OUT = HERE / "explorer-data.json"
OUT_SANKEY = HERE / "site" / "explorer-sankey.json"
AGG = ["Advanced", "EmergingDeveloping", "Global"]
YEARS = list(range(1995, 2025))
NEW_IND = ["Water stress (AWARE)", "Biodiversity loss, land use",
           "Biodiversity loss, freshwater eutrophication", "PM health impacts"]

d = pd.read_parquet(CACHE / "impacts_pba_cba.parquet")
fl = json.loads(FLOWS.read_text(encoding="utf-8"))
grp = pd.read_csv(GROUPS_CSV)
advanced = grp.loc[grp.AdvEmerging == "Advanced", "EXIO3"].tolist()
eu = grp.loc[grp.EU == "EU", "EXIO3"].tolist()
regions = [r for r in d.exio_region.unique() if r not in AGG]
assert len(regions) == 49, len(regions)
assert sorted(fl["regions"]) == sorted(regions)
assert fl["years"] == YEARS, "flow pass years differ from the page's"

c = d[d.exio_region.isin(regions)]
key = ["indicator", "accounting", "year"]
for name, members in [("Global", regions), ("Advanced", advanced)]:
    s = c[c.exio_region.isin(members)].groupby(key).value.sum()
    g = d[d.exio_region == name].set_index(key).value
    r = (s / g).replace([np.inf, -np.inf], np.nan).dropna()
    if not np.allclose(r, 1.0, rtol=1e-9):
        sys.exit(f"{name} is not the sum of its members (ratio {r.min()}..{r.max()})")


def sig(x):
    return None if x is None or pd.isna(x) else (0 if x == 0 else float(f"{x:.5g}"))


values = {}
for (reg, ind, acc), g in c.groupby(["exio_region", "indicator", "accounting"]):
    values.setdefault(reg, {}).setdefault(acc, {})[ind] = [sig(v) for v in g.set_index("year").value.reindex(YEARS)]

TOT, COMB, NON = ("GWP100 - AR6 - total", "GWP100 - AR6 - total combustion",
                  "GWP100 - AR6 - total non combustion")
for reg in values:
    for acc in values[reg]:
        t, cb = values[reg][acc][TOT], values[reg][acc][COMB]
        values[reg][acc][NON] = [None if a is None or b is None else sig(a - b) for a, b in zip(t, cb)]

# cross-check the flow pass against the cache where both carry the indicator
worst = 0.0
for ind in fl["tot"]:
    if ind in NEW_IND:
        continue
    for reg in regions:
        for acc in ("PBA", "CBA", "imp"):
            a = np.array(fl["tot"][ind][reg][acc], float)
            b = np.array(values[reg][acc][ind], float)
            ok = np.isfinite(b) & (np.abs(b) > 0)
            if ok.any():
                worst = max(worst, float(np.max(np.abs(a[ok] / b[ok] - 1))))
if worst > 2e-3:
    sys.exit(f"flow pass disagrees with the cache (worst relative difference {worst:.2e})")
print(f"flow pass vs cache: worst relative difference {worst:.1e}")

for ind in NEW_IND:
    for reg in regions:
        for acc in ("PBA", "CBA", "imp"):
            values[reg][acc][ind] = fl["tot"][ind][reg][acc]

for ind, byreg in fl["comp"].items():
    for reg, cats in byreg.items():
        s = np.nansum([np.array(v, float) for v in cats.values()], axis=0)
        ref = np.array(fl["tot"][ind][reg]["CBA"], float)
        if np.nanmax(np.abs(s - ref) / np.maximum(np.abs(ref), 1e-30)) > 1e-3:
            sys.exit(f"categories do not sum to CBA for {ind} {reg}")

comp_by_region = {r: {ind: fl["comp"][ind][r] for ind in fl["comp"]} for r in regions}

macro = {}
for reg, g in c.drop_duplicates(["exio_region", "year"]).groupby("exio_region"):
    g = g.set_index("year").reindex(YEARS)
    macro[reg] = {k: [sig(v) for v in g[k]] for k in ["population", "gdp_ppp", "gdp_usd_constant"]}

units = d.drop_duplicates("indicator").set_index("indicator").unit.to_dict()
units.update({"Water stress (AWARE)": "Mm3 world-eq", "Biodiversity loss, land use": "PDF.yr",
              "Biodiversity loss, freshwater eutrophication": "PDF.yr", "PM health impacts": "DALY"})
out = dict(years=YEARS, regions=regions, values=values, macro=macro, units=units,
           advanced=advanced, eu=eu, comp=comp_by_region, cats=fl["cats"] + ["Direct (households)"],
           rg=fl["rg"], groups=fl["groups"], flow_indicators=fl["indicators"])
OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8", newline="\n")
sk = {k: fl[k] for k in ("sankey", "sankey_years", "origins", "groups", "cats", "indicators", "regions")}
OUT_SANKEY.write_text(json.dumps(sk, separators=(",", ":"), ensure_ascii=False), encoding="utf-8", newline="\n")
print(f"Wrote {OUT.name}: {OUT.stat().st_size:,} bytes; {OUT_SANKEY.name}: {OUT_SANKEY.stat().st_size:,} bytes")
