"""Derive NEW descriptive information from the produced IC-003B shape-library data.

READ-ONLY over results/research/ic_003b/ + the ic_002 trajectories. Deterministic (seed 42).
Information-only (CLAUDE.md 6.5): every number is descriptive; NO edge claim, NO promotion. The honest
expectation is that these quantify the near-noise null rather than find edge.

Four derivations (owner-selected):
  D1  information content  - MI(shape;outcome) vs shuffle-null, Cramer's V, eta^2 of win by shape;
                             + per-summary-dim F-ratio (what the shapes separate on).
  D2  cross-representation concordance - Arm S (Euclidean) vs Arm T (DTW) assignment: ARI + AMI.
  D3  path morphology - per Arm-S-N4 shape, cluster-mean trajectory shape per channel.
  D4  shape-as-conditional-signal - tp_oos vs base rate, Wilson CI, BH-corrected, IS->OOS rank stability.

Writes results/research/ic_003b/DERIVED_INFORMATION.{json,md}.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score, mutual_info_score

from research.ic002_entry_evolution.io_util import load_batch
from research.ic003b_sequence_geometry.summarize import path_summary_matrix

SEED = 42
IC002 = Path("results/research/ic_002")
IC003B = Path("results/research/ic_003b")
OUT_JSON = IC003B / "DERIVED_INFORMATION.json"
OUT_MD = IC003B / "DERIVED_INFORMATION.md"
OOS_SPLIT = 0.3
D3_CHANNELS = ("body_ratio", "disp_strength", "rsi_14", "momentum_score", "ema_spread")
N_SHUFFLE = 200


# ---------- helpers ----------

def _load_assignment(arm: str, N: int) -> dict:
    p = IC003B / f"arm_{arm}_N{N}" / "assignment.jsonl"
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out[r["trade_id"]] = int(r["label"])
    return out


def _oos_mask(batch) -> np.ndarray:
    n = batch.Z.shape[0]
    order = sorted(range(n), key=lambda i: (batch.timestamps[i] or "", batch.entry_indices[i]))
    cut = int(round(n * (1 - OOS_SPLIT)))
    m = np.zeros(n, dtype=bool)
    m[np.array(order[cut:])] = True
    return m


def _cramers_v(labels: np.ndarray, outcomes: np.ndarray) -> float:
    ls = sorted(set(labels.tolist())); os_ = sorted(set(outcomes.tolist()))
    tab = np.zeros((len(ls), len(os_)), float)
    li = {v: i for i, v in enumerate(ls)}; oi = {v: i for i, v in enumerate(os_)}
    for l, o in zip(labels, outcomes):
        tab[li[l], oi[o]] += 1
    n = tab.sum()
    if n == 0 or min(tab.shape) < 2:
        return 0.0
    exp = np.outer(tab.sum(1), tab.sum(0)) / n
    chi2 = float(np.sum((tab - exp) ** 2 / np.where(exp == 0, 1, exp)))
    return math.sqrt(chi2 / (n * (min(tab.shape) - 1)))


def _mi_bits(labels: np.ndarray, outcomes: np.ndarray) -> float:
    # sklearn mutual_info_score returns nats; convert to bits
    return float(mutual_info_score(labels, outcomes) / math.log(2))


def _eta_sq_win(labels: np.ndarray, win: np.ndarray) -> float:
    """Fraction of win-indicator variance explained by shape membership (one-way eta^2)."""
    grand = win.mean()
    ss_tot = float(np.sum((win - grand) ** 2))
    if ss_tot == 0:
        return 0.0
    ss_between = 0.0
    for l in set(labels.tolist()):
        g = win[labels == l]
        ss_between += len(g) * (g.mean() - grand) ** 2
    return ss_between / ss_tot


def _wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _bh(pvals: list, alpha: float = 0.05):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    sig = [False] * m
    thr = 0.0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= (rank / m) * alpha:
            thr = rank
    for rank, i in enumerate(order, start=1):
        if rank <= thr:
            sig[i] = True
    return sig


def _spearman(a: list, b: list) -> float:
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        r = [0.0] * len(x)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = np.array(rank(a)), np.array(rank(b))
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


# ---------- derivations ----------

def d1_information_content() -> dict:
    rng = np.random.RandomState(SEED)
    out = {}
    for arm in ("S", "T"):
        for N in (4, 16, 8):
            b = load_batch(IC002, N)
            asg = _load_assignment(arm, N)
            labels = np.array([asg[t] for t in b.trade_ids])
            outcomes = np.array(list(b.outcomes))
            oos = _oos_mask(b)
            lab, oc = labels[oos], outcomes[oos]
            win = (oc == "TP_HIT").astype(float)
            mi = _mi_bits(lab, oc)
            null = [_mi_bits(lab, rng.permutation(oc)) for _ in range(N_SHUFFLE)]
            out[f"{arm}_N{N}"] = {
                "n_oos": int(oos.sum()),
                "k": int(len(set(lab.tolist()))),
                "mi_bits": round(mi, 6),
                "mi_null_mean_bits": round(float(np.mean(null)), 6),
                "mi_excess_over_null_bits": round(mi - float(np.mean(null)), 6),
                "cramers_v": round(_cramers_v(lab, oc), 4),
                "eta_sq_win_by_shape": round(_eta_sq_win(lab, win), 5),
                "base_tp_rate": round(float(win.mean()), 4),
            }
    # D1b: what the Arm-S N4 shapes separate on (per-summary-dim F-ratio)
    b = load_batch(IC002, 4)
    X = path_summary_matrix(np.asarray(b.Z, float))
    labels = np.array([_load_assignment("S", 4)[t] for t in b.trade_ids])
    grand = X.mean(0)
    fr = []
    for j in range(X.shape[1]):
        col = X[:, j]
        sst = float(np.sum((col - grand[j]) ** 2)) or 1.0
        ssb = sum(len(col[labels == l]) * (col[labels == l].mean() - grand[j]) ** 2 for l in set(labels.tolist()))
        fr.append(ssb / sst)
    stats = ["mean", "std", "first", "last", "min", "max", "slope"]
    fids = list(b.feature_ids)
    dim_names = [f"{fids[j // len(stats)]}::{stats[j % len(stats)]}" for j in range(X.shape[1])]
    top = sorted(zip(dim_names, fr), key=lambda kv: -kv[1])[:8]
    out["arm_S_N4_top_separating_dims"] = [{"dim": d, "variance_explained": round(v, 3)} for d, v in top]
    return out


def d2_cross_representation() -> dict:
    out = {}
    for N in (4, 16, 8):
        s, t = _load_assignment("S", N), _load_assignment("T", N)
        common = sorted(set(s) & set(t))
        ls = [s[k] for k in common]; lt = [t[k] for k in common]
        out[f"N{N}"] = {
            "n_common": len(common),
            "k_S": len(set(ls)), "k_T": len(set(lt)),
            "adjusted_rand_index": round(float(adjusted_rand_score(ls, lt)), 4),
            "adjusted_mutual_info": round(float(adjusted_mutual_info_score(ls, lt)), 4),
        }
    return out


def d3_path_morphology() -> dict:
    b = load_batch(IC002, 4)
    Z = np.asarray(b.Z, float)  # (n, N, D)
    labels = np.array([_load_assignment("S", 4)[t] for t in b.trade_ids])
    fids = list(b.feature_ids)
    ch_idx = {c: fids.index(c) for c in D3_CHANNELS if c in fids}
    out = {}
    for l in sorted(set(labels.tolist())):
        mean_path = Z[labels == l].mean(0)  # (N, D)
        shape = {}
        for c, j in ch_idx.items():
            series = mean_path[:, j]
            slope = float(series[-1] - series[0])
            rng = float(series.max() - series.min())
            # descriptor from slope vs range
            if abs(slope) < 0.15 * (rng if rng else 1.0):
                desc = "flat"
            elif slope > 0:
                desc = "rising"
            else:
                desc = "falling"
            # mean-reversion: end returns toward start relative to the extreme
            if rng and abs(series[-1] - series[0]) < 0.4 * rng and (series.max() - series[0]) > 0.5 * rng:
                desc = "mean-reverting"
            shape[c] = {"start": round(float(series[0]), 3), "end": round(float(series[-1]), 3),
                        "slope": round(slope, 3), "descriptor": desc}
        out[f"S_N4_k6_s{l:02d}"] = shape
    return out


def d4_shape_as_signal() -> dict:
    b = load_batch(IC002, 4)
    asg = _load_assignment("S", 4)
    labels = np.array([asg[t] for t in b.trade_ids])
    outcomes = np.array(list(b.outcomes))
    oos = _oos_mask(b); is_ = ~oos
    win_oos = (outcomes[oos] == "TP_HIT").astype(int); lab_oos = labels[oos]
    win_is = (outcomes[is_] == "TP_HIT").astype(int); lab_is = labels[is_]
    base = float(win_oos.mean())
    rows = []; pvals = []
    for l in sorted(set(labels.tolist())):
        k = int(win_oos[lab_oos == l].sum()); n = int((lab_oos == l).sum())
        p = k / n if n else 0.0
        lo, hi = _wilson(k, n)
        se = math.sqrt(base * (1 - base) / n) if n else 1.0
        z = (p - base) / se if se else 0.0
        # two-sided normal p-value
        pval = math.erfc(abs(z) / math.sqrt(2))
        rows.append({"shape_id": f"S_N4_k6_s{l:02d}", "n_oos": n, "tp_oos": round(p, 4),
                     "wilson95": [round(lo, 4), round(hi, 4)], "z_vs_base": round(z, 2), "p_two_sided": round(pval, 4)})
        pvals.append(pval)
    sig = _bh(pvals)
    for r, s in zip(rows, sig):
        r["bh_significant_0.05"] = bool(s)
    # IS->OOS tp rank stability
    tp_is = [float(win_is[lab_is == l].mean()) for l in sorted(set(labels.tolist()))]
    tp_oos = [r["tp_oos"] for r in rows]
    return {"base_tp_oos": round(base, 4), "shapes": rows,
            "is_oos_tp_rank_spearman": round(_spearman(tp_is, tp_oos), 3),
            "any_bh_significant": bool(any(sig))}


def main() -> None:
    res = {
        "authority": "descriptive / information-only (CLAUDE.md 6.5); NO edge claim; NO promotion",
        "source": "results/research/ic_003b/ (IC003B_PARTIAL) + results/research/ic_002/ trajectories",
        "seed": SEED,
        "D1_information_content": d1_information_content(),
        "D2_cross_representation_concordance": d2_cross_representation(),
        "D3_path_morphology_arm_S_N4": d3_path_morphology(),
        "D4_shape_as_conditional_signal_arm_S_N4": d4_shape_as_signal(),
    }
    OUT_JSON.write_text(json.dumps(res, indent=2, sort_keys=True), encoding="utf-8")
    _write_md(res)
    print(f"[ic003b-derive] wrote {OUT_JSON} and {OUT_MD}")
    _print_headlines(res)


def _write_md(res: dict) -> None:
    d1 = res["D1_information_content"]; d2 = res["D2_cross_representation_concordance"]
    d4 = res["D4_shape_as_conditional_signal_arm_S_N4"]
    L = []
    L.append("# IC-003B — Derived Information (measured)\n")
    L.append("> **Authority: NONE — descriptive / information-only (6.5).** No edge claim, no promotion. "
             "These numbers QUANTIFY the near-noise IC-003B library; they do not create a signal.\n")
    L.append("## D1 — Information content (shape -> outcome, OOS)\n")
    L.append("| unit | k | MI (bits) | MI null | excess | Cramer's V | eta^2 win |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for u, d in d1.items():
        if not u.startswith(("S_N", "T_N")):
            continue
        L.append(f"| {u} | {d['k']} | {d['mi_bits']} | {d['mi_null_mean_bits']} | "
                 f"{d['mi_excess_over_null_bits']} | {d['cramers_v']} | {d['eta_sq_win_by_shape']} |")
    L.append("\n**What the Arm-S N4 shapes separate on (top variance-explained dims):**")
    for t in d1["arm_S_N4_top_separating_dims"]:
        L.append(f"- `{t['dim']}` — {t['variance_explained']}")
    L.append("\n## D2 — Cross-representation concordance (Arm S Euclidean vs Arm T DTW)\n")
    L.append("| N | n_common | k_S | k_T | Adjusted Rand | AMI |")
    L.append("|---:|---:|---:|---:|---:|---:|")
    for n, d in d2.items():
        L.append(f"| {n[1:]} | {d['n_common']} | {d['k_S']} | {d['k_T']} | "
                 f"{d['adjusted_rand_index']} | {d['adjusted_mutual_info']} |")
    L.append("\n## D3 — Path morphology (Arm-S N4 cluster-mean trajectories)\n")
    for sid, ch in res["D3_path_morphology_arm_S_N4"].items():
        parts = ", ".join(f"{c}:{v['descriptor']}" for c, v in ch.items())
        L.append(f"- `{sid}` — {parts}")
    L.append("\n## D4 — Shape as conditional signal (OOS, Arm-S N4)\n")
    L.append(f"base tp_oos = {d4['base_tp_oos']} · IS->OOS tp rank Spearman = {d4['is_oos_tp_rank_spearman']} "
             f"· **any BH-significant: {d4['any_bh_significant']}**\n")
    L.append("| shape | n_oos | tp_oos | Wilson95 | z vs base | p | BH-sig |")
    L.append("|---|---:|---:|---|---:|---:|:--:|")
    for r in d4["shapes"]:
        L.append(f"| `{r['shape_id']}` | {r['n_oos']} | {r['tp_oos']} | {r['wilson95']} | "
                 f"{r['z_vs_base']} | {r['p_two_sided']} | {r['bh_significant_0.05']} |")
    L.append("\n> D4 caveat (E-001): any apparent separation is subject to multiple-comparisons + the "
             "IC-003B seed-fragility/near-noise caveat; it is a MEASUREMENT, never a signal to wire.")
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")


def _print_headlines(res: dict) -> None:
    d1 = res["D1_information_content"]["S_N4"]
    d2 = res["D2_cross_representation_concordance"]["N4"]
    d4 = res["D4_shape_as_conditional_signal_arm_S_N4"]
    print(f"  D1 S_N4: MI={d1['mi_bits']} bits (null {d1['mi_null_mean_bits']}), Cramer's V={d1['cramers_v']}, eta^2={d1['eta_sq_win_by_shape']}")
    print(f"  D2 N4: ARI={d2['adjusted_rand_index']} AMI={d2['adjusted_mutual_info']}")
    print(f"  D4: any BH-significant={d4['any_bh_significant']} | IS->OOS rank Spearman={d4['is_oos_tp_rank_spearman']}")


if __name__ == "__main__":
    main()
