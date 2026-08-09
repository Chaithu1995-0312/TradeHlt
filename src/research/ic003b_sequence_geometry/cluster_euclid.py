"""Arm S: Euclidean library on path-summary vectors (IC-003 v1 gates)."""
from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from research.ic003b_sequence_geometry.schema import (
    G1_SSE_RATIO_MAX,
    G2_SILHOUETTE_MIN,
    G3_OOS_Z_MAX,
    G4_MIN_N_IS,
    G4_MIN_N_OOS,
    K_GRID,
    N_INIT,
    SEED,
    SILHOUETTE_SUBSAMPLE,
)


def _time_split(timestamps: list[str], entry_indices: list[int], oos_split: float):
    order = sorted(
        range(len(entry_indices)),
        key=lambda i: (timestamps[i] or "", entry_indices[i]),
    )
    cut = int(round(len(order) * (1.0 - oos_split)))
    return order[:cut], order[cut:]


def _tp_rate(outcomes: list[str], idx: list[int]) -> float | None:
    if not idx:
        return None
    return sum(1 for i in idx if outcomes[i] == "TP_HIT") / len(idx)


def _outcome_mix(outcomes: list[str], idx: list[int]) -> dict[str, float]:
    c = Counter(outcomes[i] for i in idx)
    tot = max(sum(c.values()), 1)
    return {k: round(v / tot, 4) for k, v in sorted(c.items())}


def _sse(X: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> float:
    s = 0.0
    for i in range(len(X)):
        d = X[i] - centers[int(labels[i])]
        s += float(np.dot(d, d))
    return s


def _select_k(X_is: np.ndarray) -> tuple[int, dict[int, float]]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score

    rng = np.random.RandomState(SEED)
    n = len(X_is)
    Xs = X_is
    if n > SILHOUETTE_SUBSAMPLE:
        Xs = X_is[rng.choice(n, size=SILHOUETTE_SUBSAMPLE, replace=False)]
    scores: dict[int, float] = {}
    best_k, best_s = K_GRID[0], -1.0
    for k in K_GRID:
        if len(Xs) <= k:
            continue
        km = MiniBatchKMeans(
            n_clusters=k,
            random_state=SEED,
            n_init=N_INIT,
            batch_size=min(1024, len(Xs)),
        )
        lab = km.fit_predict(Xs)
        if len(set(lab.tolist())) < 2:
            scores[k] = -1.0
            continue
        s = float(
            silhouette_score(
                Xs, lab, sample_size=min(5000, len(Xs)), random_state=SEED
            )
        )
        scores[k] = s
        if s > best_s:
            best_s, best_k = s, k
    return best_k, scores


def run_arm_s(
    X: np.ndarray,
    timestamps: list[str],
    entry_indices: list[int],
    trade_ids: list[str],
    outcomes: list[str],
    N: int,
    *,
    oos_split: float = 0.3,
    role: str = "primary",
) -> dict[str, Any]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    X = np.nan_to_num(np.asarray(X, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    is_idx, oos_idx = _time_split(timestamps, entry_indices, oos_split)
    if len(is_idx) < max(K_GRID) + 10:
        return {"N": N, "arm": "S", "role": role, "verdict": "INSUFFICIENT"}

    scaler = StandardScaler()
    X_is = scaler.fit_transform(X[is_idx])
    X_all = scaler.transform(X)

    k_star, sil_by_k = _select_k(X_is)
    km = MiniBatchKMeans(
        n_clusters=k_star,
        random_state=SEED,
        n_init=N_INIT,
        batch_size=min(2048, len(X_is)),
    )
    labels_is = km.fit_predict(X_is)
    centers = km.cluster_centers_
    labels_all = km.predict(X_all)

    global_center = X_is.mean(axis=0, keepdims=True)
    sse_global = float(np.sum((X_is - global_center) ** 2))
    sse_within = _sse(X_is, labels_is, centers)
    sse_ratio = sse_within / sse_global if sse_global > 0 else 1.0
    g1_ok = sse_ratio <= G1_SSE_RATIO_MAX

    rng = np.random.RandomState(SEED)
    if len(X_is) > SILHOUETTE_SUBSAMPLE:
        sub = rng.choice(len(X_is), size=SILHOUETTE_SUBSAMPLE, replace=False)
        sil = float(
            silhouette_score(
                X_is[sub],
                labels_is[sub],
                sample_size=min(5000, len(sub)),
                random_state=SEED,
            )
        )
    else:
        sil = float(
            silhouette_score(
                X_is, labels_is, sample_size=min(5000, len(X_is)), random_state=SEED
            )
        )
    g2_ok = sil >= G2_SILHOUETTE_MIN

    is_set, oos_set = set(is_idx), set(oos_idx)
    is_dists = np.linalg.norm(X_is - centers[labels_is], axis=1)
    cluster_is_dist = {c: is_dists[labels_is == c] for c in range(k_star)}

    shapes = []
    g3_scores = []
    g4_ok = True
    purity = []
    global_tp = _tp_rate(outcomes, list(range(len(outcomes))))

    for c in range(k_star):
        members = [i for i in range(len(labels_all)) if int(labels_all[i]) == c]
        mem_is = [i for i in members if i in is_set]
        mem_oos = [i for i in members if i in oos_set]
        if len(mem_is) < G4_MIN_N_IS or len(mem_oos) < G4_MIN_N_OOS:
            g4_ok = False

        if mem_is:
            d = np.linalg.norm(X_all[mem_is] - centers[c], axis=1)
            medoid_i = mem_is[int(np.argmin(d))]
        else:
            medoid_i = members[0] if members else -1

        if mem_oos and len(cluster_is_dist.get(c, [])) >= 5:
            is_d = cluster_is_dist[c]
            mu = float(np.median(is_d))
            mad = float(np.median(np.abs(is_d - mu)))
            sd = float(np.std(is_d))
            scale = max(sd, 1.4826 * mad, 1e-3)
            oos_d = np.linalg.norm(X_all[mem_oos] - centers[c], axis=1)
            z_mean = (float(np.median(oos_d)) - mu) / scale
            g3_scores.append(z_mean)
        else:
            g3_scores.append(0.0)

        tp_oos = _tp_rate(outcomes, mem_oos)
        if (
            tp_oos is not None
            and global_tp is not None
            and len(mem_oos) >= 50
            and abs(tp_oos - global_tp) * 100 >= 10
        ):
            purity.append(f"S_N{N}_k{k_star}_s{c:02d}: tp_oos={tp_oos:.3f} vs {global_tp:.3f}")

        def nearest(ids: list[int], kk: int) -> list[str]:
            if not ids:
                return []
            d = np.linalg.norm(X_all[ids] - centers[c], axis=1)
            return [trade_ids[ids[j]] for j in np.argsort(d)[:kk]]

        shapes.append(
            {
                "shape_id": f"S_N{N}_k{k_star}_s{c:02d}",
                "arm": "S",
                "N": N,
                "k": k_star,
                "cluster": c,
                "n_is": len(mem_is),
                "n_oos": len(mem_oos),
                "medoid_trade_id": trade_ids[medoid_i] if medoid_i >= 0 else None,
                "outcome_mix_is": _outcome_mix(outcomes, mem_is),
                "outcome_mix_oos": _outcome_mix(outcomes, mem_oos),
                "tp_rate_oos": tp_oos,
                "representative_trade_ids_is": nearest(mem_is, 5),
                "representative_trade_ids_oos": nearest(mem_oos, 3),
            }
        )

    g3_ok = all(z <= G3_OOS_Z_MAX for z in g3_scores) if g3_scores else False
    geometry_ok = g1_ok and g2_ok and g3_ok and g4_ok
    verdict = "LIBRARY_OK" if geometry_ok else "LIBRARY_FAIL"
    if role == "diagnostic":
        verdict = verdict + "_DIAGNOSTIC" if verdict != "INSUFFICIENT" else verdict

    return {
        "N": N,
        "arm": "S",
        "role": role,
        "k_star": k_star,
        "silhouette_by_k": {str(k): round(v, 4) for k, v in sil_by_k.items()},
        "n": len(trade_ids),
        "n_is": len(is_idx),
        "n_oos": len(oos_idx),
        "gates": {
            "G1": {"sse_ratio": round(sse_ratio, 4), "ok": g1_ok, "max": G1_SSE_RATIO_MAX},
            "G2": {"silhouette": round(sil, 4), "ok": g2_ok, "min": G2_SILHOUETTE_MIN},
            "G3": {"z": [round(z, 4) for z in g3_scores], "ok": g3_ok},
            "G4": {"ok": g4_ok},
            "G5": {"ok": True},
        },
        "verdict": verdict,
        "purity_notes": purity,
        "shapes": shapes,
        "labels": labels_all.tolist(),
    }
