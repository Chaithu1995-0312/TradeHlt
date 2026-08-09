"""Arm C: PCA continuum diagnostic."""
from __future__ import annotations

from typing import Any

import numpy as np

from research.ic003b_sequence_geometry.schema import (
    CONTINUUM_CUMVAR_MIN,
    CONTINUUM_MAX_SIL,
    K_GRID,
    PCA_N_COMP,
    SEED,
)


def _pca_report(X: np.ndarray, name: str) -> dict[str, Any]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    X = np.nan_to_num(np.asarray(X, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    Xs = StandardScaler().fit_transform(X)
    n_comp = min(PCA_N_COMP, Xs.shape[0] - 1, Xs.shape[1])
    if n_comp < 1:
        return {"name": name, "error": "too_few_dims"}
    pca = PCA(n_components=n_comp, random_state=SEED)
    scores = pca.fit_transform(Xs)
    cumvar = float(np.sum(pca.explained_variance_ratio_[: min(4, n_comp)]))
    # silhouette of KMeans on PC scores
    max_sil = -1.0
    sil_by_k = {}
    for k in K_GRID:
        if len(scores) <= k:
            continue
        km = MiniBatchKMeans(n_clusters=k, random_state=SEED, n_init=5, batch_size=1024)
        lab = km.fit_predict(scores)
        if len(set(lab.tolist())) < 2:
            sil_by_k[k] = -1.0
            continue
        s = float(
            silhouette_score(
                scores, lab, sample_size=min(5000, len(scores)), random_state=SEED
            )
        )
        sil_by_k[k] = s
        max_sil = max(max_sil, s)
    return {
        "name": name,
        "n_components": n_comp,
        "explained_variance_ratio": [round(float(x), 4) for x in pca.explained_variance_ratio_],
        "cumvar_4": round(cumvar, 4),
        "max_kmeans_silhouette_on_pcs": round(max_sil, 4),
        "silhouette_by_k": {str(k): round(v, 4) for k, v in sil_by_k.items()},
        "cumvar_ge_half": cumvar >= CONTINUUM_CUMVAR_MIN,
        "max_sil_lt_threshold": max_sil < CONTINUUM_MAX_SIL,
    }


def run_arm_c(X_flat: np.ndarray, X_sum: np.ndarray) -> dict[str, Any]:
    r_flat = _pca_report(X_flat, "M-FLAT")
    r_sum = _pca_report(X_sum, "Arm_S")
    both_continuum = (
        r_flat.get("cumvar_ge_half")
        and r_flat.get("max_sil_lt_threshold")
        and r_sum.get("cumvar_ge_half")
        and r_sum.get("max_sil_lt_threshold")
    )
    either_discrete = (
        (r_flat.get("max_kmeans_silhouette_on_pcs") or -1) >= CONTINUUM_MAX_SIL
        or (r_sum.get("max_kmeans_silhouette_on_pcs") or -1) >= CONTINUUM_MAX_SIL
    )
    flags = []
    if both_continuum:
        flags.append("CONTINUUM_NOTE")
    if either_discrete:
        flags.append("DISCRETE_HINT")
    return {
        "arm": "C",
        "reprs": {"M-FLAT": r_flat, "Arm_S": r_sum},
        "flags": flags,
        "CONTINUUM_NOTE": both_continuum,
        "DISCRETE_HINT": either_discrete,
    }
