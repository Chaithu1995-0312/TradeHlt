"""Arm T: DTW + k-medoids on 3-channel paths."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from research.ic003b_sequence_geometry.dtw import (
    dtw_euclidean,
    dtw_to_medoids,
    pairwise_dtw,
    sakoe_chiba_radius,
)
from research.ic003b_sequence_geometry.schema import (
    DTW_IS_SUBSAMPLE_MAX,
    G1_T_RATIO_MAX,
    G2_T_SILHOUETTE_MIN,
    G4_MIN_N_IS,
    G4_MIN_N_OOS,
    K_GRID,
    SEED,
)


def _time_split(timestamps: list[str], entry_indices: list[int], oos_split: float):
    order = sorted(
        range(len(entry_indices)),
        key=lambda i: (timestamps[i] or "", entry_indices[i]),
    )
    cut = int(round(len(order) * (1.0 - oos_split)))
    return order[:cut], order[cut:]


def _pam(D: np.ndarray, k: int, max_iter: int = 15) -> np.ndarray:
    """Simple PAM k-medoids; returns medoid indices into D."""
    n = D.shape[0]
    rng = np.random.RandomState(SEED)
    medoids = np.sort(rng.choice(n, size=k, replace=False))
    for _ in range(max_iter):
        # assign
        labels = np.argmin(D[:, medoids], axis=1)
        new_medoids = medoids.copy()
        improved = False
        for ci, m in enumerate(medoids):
            members = np.where(labels == ci)[0]
            if len(members) == 0:
                continue
            # pick member minimizing total distance to other members
            best = m
            best_cost = np.sum(D[m, members])
            for cand in members:
                cost = np.sum(D[cand, members])
                if cost < best_cost - 1e-12:
                    best_cost = cost
                    best = cand
                    improved = True
            new_medoids[ci] = best
        new_medoids = np.unique(new_medoids)
        # refill if collapsed
        while len(new_medoids) < k:
            extra = rng.randint(0, n)
            if extra not in new_medoids:
                new_medoids = np.sort(np.append(new_medoids, extra))
        if not improved and np.array_equal(np.sort(new_medoids), np.sort(medoids)):
            break
        medoids = np.sort(new_medoids)
    return medoids


def _silhouette_precomputed(D: np.ndarray, labels: np.ndarray) -> float:
    from sklearn.metrics import silhouette_score

    if len(set(labels.tolist())) < 2:
        return -1.0
    return float(silhouette_score(D, labels, metric="precomputed"))


def run_arm_t(
    seqs: np.ndarray,
    timestamps: list[str],
    entry_indices: list[int],
    trade_ids: list[str],
    outcomes: list[str],
    N: int,
    *,
    oos_split: float = 0.3,
    role: str = "primary",
) -> dict[str, Any]:
    """
    seqs: (n, N, 3) path channels.
    """
    seqs = np.nan_to_num(np.asarray(seqs, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    is_idx, oos_idx = _time_split(timestamps, entry_indices, oos_split)
    if len(is_idx) < max(K_GRID) + 10:
        return {"N": N, "arm": "T", "role": role, "verdict": "INSUFFICIENT"}

    radius = sakoe_chiba_radius(N)
    rng = np.random.RandomState(SEED)
    is_arr = np.array(is_idx, dtype=int)
    if len(is_arr) > DTW_IS_SUBSAMPLE_MAX:
        sub_local = rng.choice(len(is_arr), size=DTW_IS_SUBSAMPLE_MAX, replace=False)
        sub_idx = is_arr[sub_local]
    else:
        sub_idx = is_arr

    seqs_sub = seqs[sub_idx]
    D = pairwise_dtw(seqs_sub, radius=radius)

    # k selection on subsample distance matrix
    best_k, best_sil = K_GRID[0], -1.0
    sil_by_k: dict[int, float] = {}
    for k in K_GRID:
        if len(sub_idx) <= k:
            continue
        med = _pam(D, k)
        labels = np.argmin(D[:, med], axis=1)
        s = _silhouette_precomputed(D, labels)
        sil_by_k[k] = s
        if s > best_sil:
            best_sil, best_k = s, k

    medoids_local = _pam(D, best_k)
    medoid_global = sub_idx[medoids_local]
    medoid_seqs = seqs[medoid_global]

    # assign all
    labels_all, dist_all = dtw_to_medoids(seqs, medoid_seqs, radius=radius)

    # G1_T: within / pairwise mean on subsample
    labels_sub = labels_all[sub_idx]
    within = []
    for ci in range(best_k):
        members = np.where(labels_sub == ci)[0]
        if len(members) == 0:
            continue
        mloc = int(np.where(medoids_local == medoids_local[ci])[0][0]) if False else ci
        # distance of members to their medoid in D
        # map: members are indices into sub; medoid local index
        med_l = medoids_local[ci]
        within.extend(D[members, med_l].tolist())
    mean_within = float(np.mean(within)) if within else 1.0
    # mean pairwise upper triangle of D
    iu = np.triu_indices(len(sub_idx), k=1)
    mean_pair = float(np.mean(D[iu])) if len(iu[0]) else 1.0
    g1_ratio = mean_within / mean_pair if mean_pair > 0 else 1.0
    g1_ok = g1_ratio <= G1_T_RATIO_MAX

    labels_sub_final = np.argmin(D[:, medoids_local], axis=1)
    sil = _silhouette_precomputed(D, labels_sub_final)
    g2_ok = sil >= G2_T_SILHOUETTE_MIN

    is_set, oos_set = set(is_idx), set(oos_idx)
    shapes = []
    g3_ok = True
    g4_ok = True
    purity = []
    global_tp = sum(1 for o in outcomes if o == "TP_HIT") / max(len(outcomes), 1)

    for c in range(best_k):
        members = [i for i in range(len(labels_all)) if int(labels_all[i]) == c]
        mem_is = [i for i in members if i in is_set]
        mem_oos = [i for i in members if i in oos_set]
        if len(mem_is) < G4_MIN_N_IS or len(mem_oos) < G4_MIN_N_OOS:
            g4_ok = False

        is_d = dist_all[mem_is] if mem_is else np.array([0.0])
        oos_d = dist_all[mem_oos] if mem_oos else np.array([0.0])
        mu = float(np.median(is_d))
        mad = float(np.median(np.abs(is_d - mu))) if len(is_d) else 1.0
        scale = max(float(np.std(is_d)) if len(is_d) > 1 else 0.0, 1.4826 * mad, 1e-3)
        if mem_oos:
            z = (float(np.median(oos_d)) - mu) / scale
            if z > 2.0:
                g3_ok = False
        else:
            z = 0.0

        tp_oos = (
            sum(1 for i in mem_oos if outcomes[i] == "TP_HIT") / len(mem_oos)
            if mem_oos
            else None
        )
        if (
            tp_oos is not None
            and len(mem_oos) >= 50
            and abs(tp_oos - global_tp) * 100 >= 10
        ):
            purity.append(f"T_N{N}_k{best_k}_s{c:02d}: tp_oos={tp_oos:.3f}")

        shapes.append(
            {
                "shape_id": f"T_N{N}_k{best_k}_s{c:02d}",
                "arm": "T",
                "N": N,
                "k": best_k,
                "cluster": c,
                "n_is": len(mem_is),
                "n_oos": len(mem_oos),
                "medoid_trade_id": trade_ids[int(medoid_global[c])],
                "outcome_mix_oos": dict(
                    Counter(outcomes[i] for i in mem_oos)
                ),
                "tp_rate_oos": tp_oos,
                "g3_z": round(z, 4),
            }
        )

    geometry_ok = g1_ok and g2_ok and g3_ok and g4_ok
    verdict = "LIBRARY_OK" if geometry_ok else "LIBRARY_FAIL"
    if role == "diagnostic":
        verdict = (
            verdict + "_DIAGNOSTIC" if verdict != "INSUFFICIENT" else verdict
        )

    return {
        "N": N,
        "arm": "T",
        "role": role,
        "k_star": best_k,
        "silhouette_by_k": {str(k): round(v, 4) for k, v in sil_by_k.items()},
        "n_subsample": int(len(sub_idx)),
        "radius": radius,
        "gates": {
            "G1_T": {"ratio": round(g1_ratio, 4), "ok": g1_ok, "max": G1_T_RATIO_MAX},
            "G2_T": {"silhouette": round(sil, 4), "ok": g2_ok, "min": G2_T_SILHOUETTE_MIN},
            "G3_T": {"ok": g3_ok},
            "G4": {"ok": g4_ok},
            "G5": {"ok": True},
        },
        "verdict": verdict,
        "purity_notes": purity,
        "shapes": shapes,
        "labels": labels_all.tolist(),
        "medoid_indices": medoid_global.tolist(),
    }
