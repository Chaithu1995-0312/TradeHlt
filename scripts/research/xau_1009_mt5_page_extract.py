"""XAUUSD research helper, 2026-10-09.

Exploratory helper: reads the data embedded in a saved XAUUSD Bar Features page (path as argv[1]) and prints the values used on the Cards vs MT5 comparison page.
Rule frozen and result logged in assistant_project.md SESSION LOG, 2026-10-09.
"""
import json, sys
p = sys.argv[1]
line = open(p, encoding="utf-8").read().splitlines()[142]
s = line[line.index("{"):]
D, _ = json.JSONDecoder().raw_decode(s)
print("top keys", list(D.keys()))
m = D["meta"]; print("meta", {k: v for k, v in m.items() if k != "features"}); print("n_features", len(m["features"]))
for k in ("hammer", "shooting_star", "doji_material", "engulfing_bull", "inside_bar", "fvg_present", "change_of_character"):
    print("has", k, k in m["features"])
F = D["rows"]; print("features type", type(F).__name__, (list(F.keys())[:10] if isinstance(F, dict) else len(F)))
rows = F["rows"] if isinstance(F, dict) and "rows" in F else F
cols = D["meta"]["features"]
print("rows type", type(rows).__name__, len(rows)); print("first row sample", str(rows[0])[:400]); print("last row", str(rows[-1])[:1500])
# structure counts
def col(name):
    if isinstance(rows[0], dict): return [r.get(name) for r in rows]
    i = cols.index(name) + 1; return [r[i] for r in rows]
for name in ("higher_high", "lower_low", "break_of_structure", "change_of_character", "sweep_detected", "liquidity_sweep", "double_sweep"):
    try:
        v = col(name); nz = [i for i, x in enumerate(v) if x not in (0, 0.0, None, False)]
        print(name, "nonzero", len(nz), "last idx", nz[-1] if nz else None, "vals", sorted(set(v))[:6])
    except Exception as e: print(name, "ERR", e)
z = D["smc_z"]; print("smc last t", z["t"][-1], "last z", z["z"][-1]); print("smc parity", z["parity_mismatch"])
print("last day", D["amd"]["days"][-1])
print("last AMD state", D["amd"]["states"][-1])
for side in ("long", "short"):
    tr = D["oracle"][side]["trades"]; R = [t["R"] for t in tr]
    print("oracle", side, "n", len(tr), "R min/max", min(R), max(R), "net_lot sum", round(sum(t["net_lot"] for t in tr), 1))
zf = D[[k for k in D if "zone" in k.lower() and isinstance(D[k], dict) and "zones_full" in D[k]][0]] if any(isinstance(D[k], dict) and "zones_full" in D[k] for k in D) else None
def find(d, key, path=""):
    if isinstance(d, dict):
        for k, v in d.items():
            if k == key: yield path + "/" + k, v
            yield from find(v, key, path + "/" + k)
for pth, v in find(D, "zones_full"):
    print("zones_full at", pth, "bars", v["bars"], "win", v["win_rate"])
    for side in ("long", "short"):
        for r in v[side]["profile"][:6]: print(" ", side, r["feature"], "s+0", round(r["s+0"], 3), "base", round(r["base"], 3), "auc", round(r["auc"], 3))
for pth, v in find(D, "zone_edge"):
    print("zone_edge at", pth, "base", json.dumps(v["base"])[:600])
for pth, v in find(D, "now"):
    print("now at", pth, v["bar"], v["close"]); [print("  ", r["f"], r["v"], "pct", round(r["pct"], 1)) for r in v["rows"]]
for pth, v in find(D, "timeout_share"): print("timeout_share", pth, v)

last = rows[-1]
print("LAST ROW by name:"); [print("  ", n, last[i+1]) for i, n in enumerate(cols)]
for name in ("higher_high","lower_low","break_of_structure","change_of_character","liquidity_sweep","sweep_detected"):
    v = col(name); nz=[(rows[i][0], v[i]) for i,x in enumerate(v) if x not in (0,0.0,None)]
    print(name, "count", len(nz), "last3", nz[-3:])
import datetime as dt
print("LAST24", json.dumps([[r[0][11:], r[1], r[2], r[3], r[4], col_bos, col_ll, col_hh] for r, col_bos, col_ll, col_hh in zip(rows[-24:], col("break_of_structure")[-24:], col("lower_low")[-24:], col("higher_high")[-24:])]))
print("type2 time", dt.datetime.utcfromtimestamp(1791378000), "t0", dt.datetime.utcfromtimestamp(1791342000), "first", dt.datetime.utcfromtimestamp(1790557200))
print("disp==mom rows", sum(1 for a,b in zip(col("disp_strength"), col("momentum_score")) if abs(a-abs(b))<1e-9), "of", len(rows))
