"""K23 table inference (pre-registration v1, sections 4-8).

Cells = (heuristic, bin, direction). Statistics S1 (vs direction-matched pooled base) and S2
(vs pooled long-only control), joint block bootstrap under two block schemes (A episode,
B fixed 40-bar), reported CI = the lower of the two lower bounds, reported p = the larger p.
BH-FDR over eligible discovery cells. Holdout read only after discovery verdicts exist.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import sparse

from .heuristics import DISCRETE_IDS, HEURISTIC_IDS, episode_ids

B_DRAWS = 2000
SEED = 20260925
Q_FDR = 0.05
MIN_UNITS, MIN_EPISODES = 300, 30
HOLD_MIN_UNITS, HOLD_MIN_EPISODES = 100, 10
BLOCK_B = 40
EMBARGO = 96
DISC_FRAC = 0.70
DIRS = ("long", "short")


def split_masks(n: int) -> tuple[np.ndarray, np.ndarray]:
    cut = int(n * DISC_FRAC)
    disc = np.zeros(n, bool)
    hold = np.zeros(n, bool)
    disc[:cut] = True
    hold[cut + EMBARGO:] = True
    return disc, hold


def heuristic_columns(h: pd.DataFrame) -> list[tuple[int, str, str]]:
    """(id, column, direction-or-'*'). h19 is per direction; every other heuristic is per bar."""
    cols = []
    for i in HEURISTIC_IDS:
        if i == 19:
            cols += [(19, "h19_long", "long"), (19, "h19_short", "short")]
        else:
            cols.append((i, f"h{i}", "*"))
    return cols


def build_cells(h: pd.DataFrame, disc: np.ndarray, valid: dict[str, np.ndarray]) -> list[dict]:
    """Bin edges are fitted on the discovery partition only. Returns cell descriptors with a
    full-length boolean membership mask (over all bars) restricted to valid-y units."""
    cells: list[dict] = []
    for hid, col, dfix in heuristic_columns(h):
        x = h[col].to_numpy(dtype=float)
        finite = np.isfinite(x)
        if hid in DISCRETE_IDS:
            lv = np.round(x, 6)
            levels = np.unique(lv[disc & finite])
            binidx = np.full(len(x), -1)
            for k, v in enumerate(levels):
                binidx[finite & (lv == v)] = k
            labels = [f"={v:g}" for v in levels]
        else:
            edges = np.unique(np.quantile(x[disc & finite], [0.25, 0.5, 0.75]))
            binidx = np.where(finite, np.digitize(x, edges), -1)
            nb = len(edges) + 1
            los = ["-inf"] + [f"{e:.6g}" for e in edges]
            his = [f"{e:.6g}" for e in edges] + ["inf"]
            labels = [f"[{a},{b})" for a, b in zip(los, his)]
        for d in DIRS:
            if dfix not in ("*", d):
                continue
            for k, lab in enumerate(labels):
                cells.append({"h": hid, "col": col, "bin": lab, "dir": d,
                              "mask": (binidx == k) & valid[d]})
    return cells


def _block_ids(scheme: str, state: np.ndarray, bars: np.ndarray) -> np.ndarray:
    raw = episode_ids(state)[bars] if scheme == "A" else bars // BLOCK_B
    return np.unique(raw, return_inverse=True)[1]


class Partition:
    """Bars of one partition plus its two block schemes and bootstrap weights (fixed seed)."""

    def __init__(self, bars: np.ndarray, state: np.ndarray, code: int):
        self.bars = bars
        self.scheme = {}
        for si, s in enumerate(("A", "B")):
            bi = _block_ids(s, state, bars)
            nb = int(bi.max()) + 1
            rng = np.random.default_rng(SEED + 100 * code + si)
            W = rng.multinomial(nb, np.full(nb, 1.0 / nb), size=B_DRAWS).astype(np.float64)
            Bm = sparse.csr_matrix((np.ones(len(bars)), (np.arange(len(bars)), bi)), shape=(len(bars), nb))
            self.scheme[s] = {"bi": bi, "nb": nb, "W": W, "Bm": Bm}


def _boot(part: Partition, cells: list[dict], y: dict[str, np.ndarray], valid: dict[str, np.ndarray],
          need_ci: bool = True) -> dict:
    """Point estimates + two-scheme bootstrap stats for the cells of ONE partition."""
    bars = part.bars
    out = {"n": [], "cm": [], "S1": [], "S2": [], "base": [], "long": [],
           "S1_lo": [], "S1_p": [], "S2_lo": [], "cm_lo": [], "n_ep": []}
    yb = {d: y[d][bars] for d in DIRS}
    vb = {d: valid[d][bars] for d in DIRS}
    yv = {d: np.where(vb[d], yb[d], 0.0) for d in DIRS}
    base_pt = {d: yv[d][vb[d]].sum() / vb[d].sum() for d in DIRS}
    long_pt = base_pt["long"]
    cm_mask = np.stack([c["mask"][bars] for c in cells], axis=1)
    ncell = len(cells)
    n_units = cm_mask.sum(0)
    dirs_of = np.array([c["dir"] for c in cells])
    ysel = np.where(dirs_of[None, :] == "long", yv["long"][:, None], yv["short"][:, None])
    sums = (cm_mask * ysel).sum(0)
    cm_pt = np.where(n_units > 0, sums / np.maximum(n_units, 1), np.nan)
    base_c = np.where(dirs_of == "long", base_pt["long"], base_pt["short"])
    res = {"n": n_units, "cm": cm_pt, "base": base_c, "S1": cm_pt - base_c, "S2": cm_pt - long_pt}
    # distinct episodes with units in the cell (scheme A)
    biA = part.scheme["A"]["bi"]
    res["n_ep"] = np.array([len(np.unique(biA[cm_mask[:, j]])) for j in range(ncell)])
    if not need_ci:
        return res
    lo1 = np.full(ncell, np.inf); lo2 = np.full(ncell, np.inf); lom = np.full(ncell, np.inf)
    p1 = np.zeros(ncell)
    Cs = sparse.csr_matrix(cm_mask.astype(np.float64))
    for s in ("A", "B"):
        sc = part.scheme[s]
        Bm, W = sc["Bm"], sc["W"]
        Nc = np.asarray((Bm.T @ Cs).todense())
        SYc = np.asarray((Bm.T @ sparse.csr_matrix(cm_mask * ysel)).todense())
        num, den = W @ SYc, W @ Nc
        with np.errstate(divide="ignore", invalid="ignore"):
            cmb = num / den
            baseb = {}
            for d in DIRS:
                Bd = np.asarray(Bm.T @ vb[d].astype(np.float64)).ravel()
                Sd = np.asarray(Bm.T @ (yv[d] * vb[d])).ravel()
                baseb[d] = (W @ Sd) / (W @ Bd)
        base_b = np.where(dirs_of[None, :] == "long", baseb["long"][:, None], baseb["short"][:, None])
        S1b = cmb - base_b
        S2b = cmb - baseb["long"][:, None]
        lo1 = np.minimum(lo1, np.nanpercentile(S1b, 2.5, axis=0))
        lo2 = np.minimum(lo2, np.nanpercentile(S2b, 2.5, axis=0))
        lom = np.minimum(lom, np.nanpercentile(cmb, 2.5, axis=0))
        fin = np.isfinite(S1b).sum(0)
        pj = (1.0 + np.nansum(S1b <= 0.0, axis=0)) / (fin + 1.0)
        p1 = np.maximum(p1, pj)
    res.update({"S1_lo": lo1, "S2_lo": lo2, "cm_lo": lom, "S1_p": p1})
    return res


def bh_pass(p: np.ndarray, q: float = Q_FDR) -> tuple[np.ndarray, np.ndarray]:
    """BH step-up. Returns (reject mask, adjusted q-values)."""
    m = len(p)
    order = np.argsort(p)
    ranked = p[order] * m / (np.arange(m) + 1.0)
    qadj = np.minimum.accumulate(ranked[::-1])[::-1]
    qadj = np.minimum(qadj, 1.0)
    out_q = np.empty(m); out_q[order] = qadj
    return out_q <= q, out_q


def discovery_table(part: Partition, cells: list[dict], y: dict, valid: dict) -> pd.DataFrame:
    r = _boot(part, cells, y, valid)
    df = pd.DataFrame({
        "h": [c["h"] for c in cells], "bin": [c["bin"] for c in cells], "dir": [c["dir"] for c in cells],
        "n": r["n"], "n_ep": r["n_ep"], "cell_mean": r["cm"], "base": r["base"],
        "S1": r["S1"], "S1_lo": r["S1_lo"], "S1_p": r["S1_p"],
        "S2": r["S2"], "S2_lo": r["S2_lo"], "cm_lo": r["cm_lo"],
    })
    df["eligible"] = (df["n"] >= MIN_UNITS) & (df["n_ep"] >= MIN_EPISODES)
    df["q"] = np.nan
    df["bh"] = False
    e = df["eligible"].to_numpy()
    if e.any():
        rej, q = bh_pass(df.loc[e, "S1_p"].to_numpy())
        df.loc[e, "q"] = q
        df.loc[e, "bh"] = rej
    return df


def holdout_table(part: Partition, cells: list[dict], y: dict, valid: dict) -> pd.DataFrame:
    r = _boot(part, cells, y, valid, need_ci=False)
    return pd.DataFrame({"h_n": r["n"], "h_n_ep": r["n_ep"], "h_cell_mean": r["cm"],
                         "h_S1": r["S1"], "h_S2": r["S2"]})


def assign_tiers(disc: pd.DataFrame, hold: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([disc.reset_index(drop=True), hold.reset_index(drop=True)], axis=1)
    hold_ok = (df["h_n"] >= HOLD_MIN_UNITS) & (df["h_n_ep"] >= HOLD_MIN_EPISODES)
    info_disc = df["eligible"] & df["bh"] & (df["S1_lo"] > 0)
    info = info_disc & hold_ok & (df["h_S1"] > 0)
    cons = (info & (df["cell_mean"] > 0) & (df["cm_lo"] > 0) & (df["S2_lo"] > 0)
            & (df["h_cell_mean"] > 0) & (df["h_S2"] > 0))
    df["tier"] = np.where(cons, "CONSUMABLE", np.where(info, "INFORMATION",
                 np.where(info_disc & ~hold_ok, "HOLDOUT_INSUFFICIENT", "NO_CLAIM")))
    df.loc[~df["eligible"], "tier"] = "INSUFFICIENT"
    return df


def planted_gate(part: Partition, cells: list[dict], y: dict, valid: dict, disc_df: pd.DataFrame,
                 hold_part: Partition, deltas=(0.30, 0.10), n_cells: int = 5) -> list[dict]:
    """Plant +delta in a few eligible cells (all bars, so holdout confirms) and require recovery."""
    elig = np.flatnonzero(disc_df["eligible"].to_numpy())
    order = elig[np.argsort(-disc_df["n"].to_numpy()[elig], kind="stable")]
    picks = [int(order[i]) for i in np.linspace(0, len(order) - 1, n_cells).astype(int)]
    results = []
    for delta in deltas:
        for j in picks:
            yp = {d: y[d].copy() for d in DIRS}
            d = cells[j]["dir"]
            yp[d] = np.where(cells[j]["mask"], yp[d] + delta, yp[d])
            dd = discovery_table(part, cells, yp, valid)
            hh = holdout_table(hold_part, cells, yp, valid)
            t = assign_tiers(dd, hh)
            results.append({"delta": delta, "cell": j, "h": cells[j]["h"], "bin": cells[j]["bin"], "dir": d,
                            "tier": str(t.loc[j, "tier"]), "S1_lo": float(t.loc[j, "S1_lo"]),
                            "bh": bool(t.loc[j, "bh"])})
    return results


def permutation_gate(part: Partition, cells: list[dict], y: dict, valid: dict, state: np.ndarray,
                     n_perm: int = 200) -> dict:
    """Permute whole-episode y-vectors within discovery (blocks intact) and count BH passes."""
    bars = part.bars
    ep = episode_ids(state)[bars]
    uniq = np.unique(ep)
    segs = {u: np.flatnonzero(ep == u) for u in uniq}
    rng = np.random.default_rng(SEED + 999)
    passes = []
    for _ in range(n_perm):
        order = rng.permutation(uniq)
        idx = np.concatenate([segs[u] for u in order])
        yp = {}
        for d in DIRS:
            arr = y[d].copy()
            arr[bars] = y[d][bars][idx]
            yp[d] = arr
        dd = discovery_table(part, cells, yp, valid)
        passes.append(int((dd["bh"] & (dd["S1_lo"] > 0)).sum()))
    passes = np.array(passes)
    return {"n_perm": n_perm, "mean_bh_passes": float(passes.mean()),
            "share_zero": float((passes == 0).mean()), "max": int(passes.max())}
