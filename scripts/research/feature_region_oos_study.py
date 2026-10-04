"""
feature_region_oos_study.py — Part 4A: do CRT feature regions persist out-of-sample? (measure-only)

Self-contained OOS harness (the orphaned ForwardTester is bypassed; the broken
ReplayMemoryEngine._assign_cluster is NOT used). Reuses discover_zones' own importable
functions so test-sample assignment matches exactly how the zones were built
(weighted-Euclidean to `center`, seed-deterministic K-Means).

Per instrument:
  1. load opportunities.jsonl (skip run_header; keep records with a `features` dict)
  2. temporal 70/30 split (sort by timestamp, no shuffle -> no lookahead)
  3. discover() zones on the TRAIN half only (research; never promotes a registry)
  4. assign each TEST record to its nearest train `center` (same weights + metric as _kmeans)
  5. per zone: retention = test_avg_rr / train_avg_rr; classify tier
  6. PCA(2) coords (matplotlib plot if available, else CSV) — secondary diagnostic
  7. emit per-instrument zone table + tier summary + go/no-go

Writes ONLY under results/feature_region_oos/. No config edit, no promotion, no schema change.
"""
from __future__ import annotations

import json
import statistics as _st
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "src")
sys.path.insert(0, "scripts/research")

import discover_zones as dz                              # noqa: E402  (discover, _vector_from_record, _load_records)
from features.feature_schema import CANONICAL_FEATURE_ORDER  # noqa: E402

N_CLUSTERS = 8
MIN_SAMPLES = 15
MIN_TEST_TRADES = 20          # ForwardTester.MIN_TEST_TRADES
TRAIN_SPLIT = 0.70            # ForwardTester.train_split
_DIM = len(CANONICAL_FEATURE_ORDER)
OUT = Path("results/feature_region_oos")


def _inv_std_weights(train_recs) -> list[float]:
    """Per-feature 1/std weights computed on TRAIN only (no test leakage).

    Delegates to discover_zones._inv_std_weights (single source of truth, also
    used by the --normalize CLI flag and consumed by ReplayMemoryEngine via the
    registry's stored feature_weights). weight_i = 1/std_i makes the weighted-
    Euclidean K-Means scale-invariant — otherwise raw OHLCV (~$100s) + volume
    dominate the O(0–1) geometry features and zones become price-era bands.
    """
    return dz._inv_std_weights(train_recs)


def _tier(retention: float) -> str:
    if retention >= 0.80:
        return "Strong"
    if retention >= 0.60:
        return "Usable"
    if retention >= 0.40:
        return "Weak"
    return "Collapse"


def _assign(vec, centers) -> int:
    """Nearest center by weighted-Euclidean — identical metric to discover_zones._kmeans."""
    best, best_d = 0, float("inf")
    for zid, c in centers:
        d = sum((vec[j] - c[j]) ** 2 for j in range(min(len(vec), len(c))))
        if d < best_d:
            best_d, best = d, zid
    return best


def study_instrument(instrument: str, opps_path: Path, normalize: bool = True) -> dict:
    recs = [r for r in dz._load_records(opps_path) if isinstance(r.get("features"), dict)]
    recs.sort(key=lambda r: str(r.get("timestamp", "")))
    n = len(recs)
    split = int(n * TRAIN_SPLIT)
    train_recs, test_recs = recs[:split], recs[split:]

    # Feature weights computed on TRAIN only. normalize=True → 1/std (scale-invariant,
    # geometry-driven clustering); False → equal weights (price-scale-dominated, diagnostic).
    weights = _inv_std_weights(train_recs) if normalize else [1.0] * _DIM

    # 3. discover zones on TRAIN only (write temp jsonl; discover() takes file paths)
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
        for r in train_recs:
            tf.write(json.dumps(r) + "\n")
        train_path = Path(tf.name)
    try:
        reg = dz.discover([train_path], n_clusters=N_CLUSTERS, min_samples=MIN_SAMPLES,
                          feature_weights=weights)
    finally:
        train_path.unlink(missing_ok=True)
    zones = reg["zones"]
    centers = [(z["zone_id"], z["center"]) for z in zones]
    train_by_zone = {z["zone_id"]: z for z in zones}

    # 4-5. assign TEST records, accumulate per-zone test RR
    test_rr: dict[int, list] = {z["zone_id"]: [] for z in zones}
    for r in test_recs:
        v = dz._vector_from_record(r, weights)
        if v is None or not centers:
            continue
        zid = _assign(v, centers)
        test_rr[zid].append(float(r.get("rr_achieved", 0.0) or 0.0))

    rows = []
    for z in zones:
        zid = z["zone_id"]
        tr_rr = z["mean_rr"]
        te = test_rr[zid]
        te_n = len(te)
        te_rr = round(_st.mean(te), 4) if te else 0.0
        retention = round(te_rr / tr_rr, 4) if tr_rr > 0 else 0.0
        tier = _tier(retention) if (tr_rr > 0 and te_n >= MIN_TEST_TRADES) else "insufficient"
        rows.append({
            "zone_id": zid, "train_n": z["n_samples"], "train_mean_rr": tr_rr,
            "train_tp_rate": z["tp_hit_rate"], "test_n": te_n, "test_mean_rr": te_rr,
            "retention": retention, "tier": tier,
        })

    # tier summary weighted by test trades (only zones meeting test_n + profitable-train gate)
    gated = [r for r in rows if r["tier"] != "insufficient"]
    tier_trades = {t: 0 for t in ("Strong", "Usable", "Weak", "Collapse")}
    for r in gated:
        tier_trades[r["tier"]] += r["test_n"]
    total_gated_trades = sum(tier_trades.values()) or 1
    persist_share = round((tier_trades["Strong"] + tier_trades["Usable"]) / total_gated_trades, 4)

    return {
        "instrument": instrument, "opportunities": str(opps_path),
        "n_records": n, "n_train": len(train_recs), "n_test": len(test_recs),
        "n_zones": len(zones), "n_zones_gated": len(gated),
        "tier_trade_counts": tier_trades, "persist_share": persist_share,
        "normalized": bool(normalize),
        "zones": rows,
    }


def _pca_coords(opps_path: Path, instrument: str, weights, max_pts: int = 4000) -> None:
    """Secondary diagnostic: PCA(2) of features colored by outcome. matplotlib optional."""
    try:
        from sklearn.decomposition import PCA
    except Exception as exc:                       # pragma: no cover
        print(f"  [pca] sklearn unavailable: {exc}")
        return
    recs = [r for r in dz._load_records(opps_path) if isinstance(r.get("features"), dict)]
    step = max(1, len(recs) // max_pts)
    sample = recs[::step]
    X = [dz._vector_from_record(r, weights) for r in sample]
    X = [x for x in X if x is not None]
    outcomes = [r.get("outcome", "?") for r in sample][:len(X)]
    coords = PCA(n_components=2, random_state=1337).fit_transform(X)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cmap = {"TP_HIT": "tab:green", "SL_HIT": "tab:red", "TIMEOUT": "tab:gray"}
        fig, ax = plt.subplots(figsize=(7, 6))
        for oc in cmap:
            pts = [coords[i] for i, o in enumerate(outcomes) if o == oc]
            if pts:
                ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=4, alpha=0.4,
                           c=cmap[oc], label=oc)
        ax.legend(); ax.set_title(f"{instrument} feature space (PCA), colored by outcome")
        fig.savefig(OUT / f"{instrument}_pca.png", dpi=110)
        plt.close(fig)
        print(f"  [pca] wrote {OUT / f'{instrument}_pca.png'}")
    except Exception:
        import csv as _csv
        with (OUT / f"{instrument}_pca_coords.csv").open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh); w.writerow(["pc1", "pc2", "outcome"])
            for i in range(len(X)):
                w.writerow([round(float(coords[i][0]), 5), round(float(coords[i][1]), 5), outcomes[i]])
        print(f"  [pca] matplotlib unavailable -> wrote coords CSV ({len(X)} pts)")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instrument", required=True)
    ap.add_argument("--opportunities", required=True, help="path to opportunities.jsonl")
    ap.add_argument("--no-normalize", action="store_true", help="equal weights (price-scale-dominated; diagnostic only)")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    res = study_instrument(args.instrument, Path(args.opportunities), normalize=not args.no_normalize)
    _pca_coords(Path(args.opportunities), args.instrument, _inv_std_weights([r for r in dz._load_records(Path(args.opportunities)) if isinstance(r.get('features'),dict)]) if not args.no_normalize else [1.0]*_DIM)
    (OUT / f"{args.instrument}_oos.json").write_text(json.dumps(res, indent=2), encoding="utf-8")

    print(f"\n=== OOS persistence — {res['instrument']} "
          f"(n={res['n_records']}, train={res['n_train']}, test={res['n_test']}) ===")
    print(f"  zones={res['n_zones']} gated(test_n>={MIN_TEST_TRADES} & train_rr>0)={res['n_zones_gated']}")
    print(f"  {'zone':>4} {'tr_n':>6} {'tr_rr':>7} {'tp%':>6} {'te_n':>5} {'te_rr':>7} {'reten':>7}  tier")
    for r in sorted(res["zones"], key=lambda x: -x["retention"]):
        print(f"  {r['zone_id']:>4} {r['train_n']:>6} {r['train_mean_rr']:>7.3f} "
              f"{r['train_tp_rate']:>6.2f} {r['test_n']:>5} {r['test_mean_rr']:>7.3f} "
              f"{r['retention']:>7.3f}  {r['tier']}")
    print(f"  tier trade-counts: {res['tier_trade_counts']}  | persist_share="
          f"{res['persist_share']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
