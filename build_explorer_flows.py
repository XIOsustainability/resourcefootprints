#!/usr/bin/env python3
"""Resource-group, new-indicator and sankey data for the explorer, from the per-year MRIO.

For every year it reads x, Y, L and the intensities S (plus direct final-demand
flows F_Y) of the indicators below from the calculated pxp tree, and computes

  production by resource group    F = S * x, summed by (region, GRO group);
                                  households are F_Y of the region
  consumption by resource group   S_c L Y for origin clusters c = (origin region,
                                  GRO group), by product category of final demand
                                  and consuming region; households are F_Y

Groups are GRO 2024 Table A2.1 (gro2024_sector_groups.csv). Product categories
are exio_results' EXIOBASE20p_7ConsCat concordance (fractional weights; products
in none go to "Other").

Writes explorer-flows.json:
  rg[view][indicator][region] = {group: [years]}      view in {PBA, CBA}
  tot[indicator][region]      = {PBA, CBA, imp: [years]}
  comp[indicator][region]     = {category: [years]}, consumption by product category
                                of final demand, plus "Direct (households)" = F_Y
  sankey[year][indicator]     = {region: flat list over origin x group x category}
with origin = own region + 6 continents (each net of the own region).

It checks that consumption totals equal pymrio's D_cba_reg for every indicator
and year, and stops if they do not.

    python build_explorer_flows.py [release_folder] [first_year] [last_year]
"""
from pathlib import Path
import json
import sys
import time

import numpy as np
import pandas as pd

REL = sys.argv[1] if len(sys.argv) > 1 else "EXIOBASE_3_11_3"
Y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 1995
Y1 = int(sys.argv[3]) if len(sys.argv) > 3 else 2024
TREE = Path(rf"D:\indecol\Projects\MRIOs\EXIOBASE3\{REL}\calculated\impacts\parquet\pxp")
HERE = Path(__file__).parent
CATS_FILE = Path(r"D:\GitHub\EXIOBASE\exio_results\EXIOBASE20p_7ConsCat.txt")
SANKEY_YEARS = [1995, 2005, 2015, 2024]
OUT = HERE / "explorer-flows.json"

# indicator -> (extension, row selector)
IND = {
    "GWP100 - AR6 - total": ("climate", "GWP100 - AR6 - total"),
    "Energy use - Net": ("energy", "Energy use - Net"),
    "Domestic Extraction Used - Total": ("aggregates", "Domestic Extraction Used - Total"),
    "Land - Total": ("aggregates", "Land - Total"),
    "Water Consumption Blue - Total (excl. once-through)": ("aggregates", "Water Consumption Blue - Total (excl. once-through)"),
    "Water stress (AWARE)": ("water_scarcity", "prefix:Water Consumption Blue"),
    "Biodiversity loss, land use": ("glam_impacts", ("EQ Land use", "Terrestrial", "Damage")),
    "Biodiversity loss, freshwater eutrophication": ("glam_impacts", ("EQ Freshwater Eutrophication", "Freshwater", "Damage")),
    "PM health impacts": ("glam_impacts", ("HH Fine Particulate Matter Impacts", None, "Damage")),
    "Value Added - Total": ("aggregates", "Value Added - Total"),
    "Employment hours - Total": ("aggregates", "Employment hours - Total"),
}
GROUPS = ["biomass", "fossil resources", "metals", "non-metallic minerals", "remaining economy"]
CONT = {
    "Europe": ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE", "IT", "LT",
               "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK", "GB", "CH", "NO", "RU", "WE"],
    "Asia and Pacific": ["CN", "JP", "KR", "TW", "IN", "ID", "AU", "WA"],
    "North America": ["US", "CA"],
    "Latin America": ["MX", "BR", "WL"],
    "Africa": ["ZA", "WF"],
    "Middle East and Türkiye": ["TR", "WM"],
}
YEARS = list(range(Y0, Y1 + 1))


def pick(ext_frame, sel):
    """Return one row (as numpy) of an S or F_Y frame for a row selector."""
    if isinstance(sel, str) and sel.startswith("prefix:"):
        p = sel[len("prefix:"):]
        rows = [r for r in ext_frame.index if str(r).startswith(p)]
        assert rows, p
        return ext_frame.loc[rows].sum(axis=0).to_numpy()
    if isinstance(sel, tuple):
        idx = ext_frame.index
        hit = [i for i, r in enumerate(idx) if r[0] == sel[0] and r[2] == sel[2]
               and ((sel[1] is None and pd.isna(r[1])) or r[1] == sel[1])]
        assert len(hit) == 1, (sel, hit)
        return ext_frame.iloc[hit[0]].to_numpy()
    return ext_frame.loc[sel].to_numpy()


def sig(a):
    return [None if not np.isfinite(v) else (0 if v == 0 else float(f"{v:.4g}")) for v in np.asarray(a, float)]


gmap = pd.read_csv(HERE / "gro2024_sector_groups.csv").set_index("product")["group_2024"]
cc = pd.read_csv(CATS_FILE, sep="\t", index_col=0)
CATS = list(cc.columns) + ["Other"]
cc["Other"] = (1 - cc.sum(axis=1)).clip(lower=0)

first = TREE / str(YEARS[0])
x0 = pd.read_parquet(first / "x.parquet")
regions = list(dict.fromkeys(x0.index.get_level_values(0)))
products = list(dict.fromkeys(x0.index.get_level_values(1)))
assert len(regions) == 49 and len(products) == 200
reg_of = np.array([regions.index(r) for r in x0.index.get_level_values(0)])
grp_of = np.array([GROUPS.index(gmap[p]) for p in x0.index.get_level_values(1)])
W = cc.reindex(x0.index.get_level_values(1)).to_numpy()          # 9800 x 7 category weights
assert np.allclose(W.sum(axis=1), 1.0), "category weights do not sum to 1"
cont_of_reg = np.array([next(i for i, (k, v) in enumerate(CONT.items()) if r in v) for r in regions])
NR, NG, NC, NK = 49, len(GROUPS), len(CATS), len(CONT)
nclu = NR * NG
clu = reg_of * NG + grp_of                                         # origin cluster of each column

rg = {v: {k: {r: {g: [] for g in GROUPS + ["households"]} for r in regions} for k in IND} for v in ("PBA", "CBA")}
tot = {k: {r: {"PBA": [], "CBA": [], "imp": []} for r in regions} for k in IND}
comp = {k: {r: {c: [] for c in CATS + ["Direct (households)"]} for r in regions} for k in IND}
sankey = {}

for yr in YEARS:
    t0 = time.time()
    d = TREE / str(yr)
    x = pd.read_parquet(d / "x.parquet").iloc[:, 0].to_numpy()
    Yf = pd.read_parquet(d / "Y.parquet")
    assert list(Yf.index) == list(x0.index)
    Yreg = Yf.T.groupby(level=0, sort=False).sum().T.reindex(columns=regions).to_numpy()   # 9800 x 49
    L = pd.read_parquet(d / "L.parquet").to_numpy()
    cache = {}
    Srows, FYreg = [], []
    for k, (ext, sel) in IND.items():
        if ext not in cache:
            S = pd.read_parquet(d / ext / "S.parquet")
            FY = pd.read_parquet(d / ext / "F_Y.parquet")
            FYr = FY.T.groupby(level=0, sort=False).sum().T.reindex(columns=regions)
            cache[ext] = (S, FYr, pd.read_parquet(d / ext / "D_cba_reg.parquet").reindex(columns=regions))
        S, FYr, Dc = cache[ext]
        Srows.append(pick(S, sel))
        FYreg.append(pick(FYr, sel))
    Srows = np.vstack(Srows)                                       # nind x 9800
    FYreg = np.vstack(FYreg)                                       # nind x 49
    nind = len(IND)
    # origin-cluster intensity matrix: (nind * nclu) x 9800, sparse by construction
    Sc = np.zeros((nind * nclu, 9800))
    for j in range(nind):
        Sc[j * nclu + clu, np.arange(9800)] = Srows[j]
    M = Sc @ L                                                     # (nind*nclu) x 9800
    del Sc
    # flows[ind, cluster, category, consumer]
    flows = np.empty((nind, nclu, NC, NR))
    for c in range(NC):
        flows[:, :, c, :] = (M @ (Yreg * W[:, [c]])).reshape(nind, nclu, NR)
    del M
    flows = flows.reshape(nind, NR, NG, NC, NR)                    # ind, origin region, group, cat, consumer
    prod = np.zeros((nind, NR, NG))
    F = Srows * x
    for j in range(nind):
        np.add.at(prod[j], (reg_of, grp_of), F[j])
    for j, k in enumerate(IND):
        ext = IND[k][0]
        cba = flows[j].sum(axis=(0, 1, 2)) + FYreg[j]
        ref = pick(cache[ext][2], IND[k][1])
        err = np.abs(cba - ref) / np.maximum(np.abs(ref), 1e-9 * np.abs(ref).max())
        if err.max() > 1e-6:
            sys.exit(f"{yr} {k}: consumption total differs from D_cba_reg (max rel {err.max():.2e})")
        dom = np.array([flows[j, r, :, :, r].sum() for r in range(NR)])
        for r, rn in enumerate(regions):
            byg_c = flows[j, :, :, :, r].sum(axis=(0, 2))
            byc = flows[j, :, :, :, r].sum(axis=(0, 1))
            for ci, cname in enumerate(CATS):
                comp[k][rn][cname].append(byc[ci])
            comp[k][rn]["Direct (households)"].append(FYreg[j, r])
            for gi, gname in enumerate(GROUPS):
                rg["PBA"][k][rn][gname].append(prod[j, r, gi])
                rg["CBA"][k][rn][gname].append(byg_c[gi])
            rg["PBA"][k][rn]["households"].append(FYreg[j, r])
            rg["CBA"][k][rn]["households"].append(FYreg[j, r])
            tot[k][rn]["PBA"].append(prod[j, r].sum() + FYreg[j, r])
            tot[k][rn]["CBA"].append(cba[r])
            tot[k][rn]["imp"].append(cba[r] - FYreg[j, r] - dom[r])
    if yr in SANKEY_YEARS:
        sk = {}
        for j, k in enumerate(IND):
            per = {}
            for r, rn in enumerate(regions):
                f = flows[j, :, :, :, r]                           # origin region, group, cat
                own = f[r]
                cont = np.zeros((NK, NG, NC))
                np.add.at(cont, cont_of_reg, f)
                cont[cont_of_reg[r]] -= own
                arr = np.concatenate([own[None], cont])            # (1+NK) x NG x NC
                per[rn] = sig(arr.ravel()) + sig([FYreg[j, r]])
            sk[k] = per
        sankey[str(yr)] = sk
    del flows, L
    print(f"{yr}: {time.time() - t0:.1f}s", flush=True)

out = {
    "years": YEARS, "regions": regions, "groups": GROUPS + ["households"], "cats": CATS,
    "origins": ["Own country"] + list(CONT), "sankey_years": [y for y in SANKEY_YEARS if y in YEARS],
    "indicators": list(IND),
    "rg": {v: {k: {r: {g: sig(s) for g, s in d3.items()} for r, d3 in d2.items()} for k, d2 in d1.items()}
           for v, d1 in rg.items()},
    "tot": {k: {r: {a: sig(s) for a, s in d3.items()} for r, d3 in d2.items()} for k, d2 in tot.items()},
    "comp": {k: {r: {c: sig(s) for c, s in d3.items()} for r, d3 in d2.items()} for k, d2 in comp.items()},
    "sankey": sankey,
}
OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8", newline="\n")
print(f"Wrote {OUT.name}: {OUT.stat().st_size:,} bytes")
