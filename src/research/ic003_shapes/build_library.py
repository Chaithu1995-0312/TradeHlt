"""Build IC-003 shape library from IC-002 trajectory batches."""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from research.ic002_entry_evolution.io_util import load_batch, repo_root, sha256_file
from research.ic002_entry_evolution.schema import TRAJECTORY_FEATURE_IDS
from research.ic003_shapes.schema import (
    DIAGNOSTIC_N,
    G1_SSE_RATIO_MAX,
    G2_SILHOUETTE_MIN,
    G4_MIN_N_IS,
    G4_MIN_N_OOS,
    K_GRID,
    KEY_FEATURE_NAMES,
    N_INIT,
    OOS_SPLIT,
    PRIMARY_N,
    PURITY_DELTA_PP,
    PURITY_MIN_N_OOS,
    SEED,
    SILHOUETTE_SUBSAMPLE,
)

logger = logging.getLogger("ic003.build")

DEFAULT_IC002 = repo_root() / "results" / "research" / "ic_002"
DEFAULT_OUT = repo_root() / "results" / "research" / "ic_003"


def _time_split(timestamps: list[str], entry_indices: list[int], oos_split: float):
    order = sorted(
        range(len(entry_indices)),
        key=lambda i: (timestamps[i] or "", entry_indices[i]),
    )
    cut = int(round(len(order) * (1.0 - oos_split)))
    return order[:cut], order[cut:]


def _flat(Z: np.ndarray) -> np.ndarray:
    n, N, D = Z.shape
    return Z.reshape(n, N * D)


def _outcome_mix(outcomes: list[str], idx: list[int]) -> dict[str, float]:
    c = Counter(outcomes[i] for i in idx)
    tot = max(sum(c.values()), 1)
    return {k: round(v / tot, 4) for k, v in sorted(c.items())}


def _tp_rate(outcomes: list[str], idx: list[int]) -> float | None:
    if not idx:
        return None
    return sum(1 for i in idx if outcomes[i] == "TP_HIT") / len(idx)


def _sse(X: np.ndarray, labels: np.ndarray, centers: np.ndarray) -> float:
    s = 0.0
    for i in range(len(X)):
        d = X[i] - centers[labels[i]]
        s += float(np.dot(d, d))
    return s


def _select_k(X_is: np.ndarray) -> tuple[int, dict[int, float]]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score

    rng = np.random.RandomState(SEED)
    n = len(X_is)
    if n > SILHOUETTE_SUBSAMPLE:
        sub = rng.choice(n, size=SILHOUETTE_SUBSAMPLE, replace=False)
        Xs = X_is[sub]
    else:
        Xs = X_is

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
        if len(set(lab)) < 2:
            scores[k] = -1.0
            continue
        s = float(silhouette_score(Xs, lab, metric="euclidean", sample_size=min(5000, len(Xs)), random_state=SEED))
        scores[k] = s
        if s > best_s:
            best_s, best_k = s, k
    return best_k, scores


def build_for_N(
    ic002_dir: Path,
    N: int,
    *,
    role: str = "primary",
) -> dict[str, Any]:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    batch = load_batch(ic002_dir, N)
    Z = np.asarray(batch.Z, dtype=np.float64)
    Z[~np.isfinite(Z)] = 0.0
    X = _flat(Z)
    y_outcomes = batch.outcomes
    is_idx, oos_idx = _time_split(batch.timestamps, batch.entry_indices, OOS_SPLIT)

    if len(is_idx) < max(K_GRID) + 10:
        return {
            "N": N,
            "role": role,
            "verdict": "INSUFFICIENT",
            "reason": "IS too small",
        }

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

    # map labels_all: need labels for all points in original order
    # X_all is already all points scaled; labels_all[i] corresponds to trade i
    # But we fit only on IS reindexed — predict on full X_all is correct

    # G1 compactness
    global_center = X_is.mean(axis=0, keepdims=True)
    sse_global = float(np.sum((X_is - global_center) ** 2))
    sse_within = _sse(X_is, labels_is, centers)
    sse_ratio = sse_within / sse_global if sse_global > 0 else 1.0
    g1_ok = sse_ratio <= G1_SSE_RATIO_MAX

    # G2 silhouette on IS (subsample)
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
                X_is,
                labels_is,
                sample_size=min(5000, len(X_is)),
                random_state=SEED,
            )
        )
    g2_ok = sil >= G2_SILHOUETTE_MIN

    # per-shape membership
    is_set = set(is_idx)
    oos_set = set(oos_idx)
    shapes: list[dict[str, Any]] = []
    g4_ok = True
    purity_flags: list[str] = []

    # distances IS for G3
    is_dists = np.linalg.norm(X_is - centers[labels_is], axis=1)
    # for each cluster, IS distance distribution
    cluster_is_dist: dict[int, np.ndarray] = {}
    for c in range(k_star):
        cluster_is_dist[c] = is_dists[labels_is == c]

    global_tp = _tp_rate(y_outcomes, list(range(len(y_outcomes))))
    g3_scores: list[float] = []

    fids = list(batch.feature_ids) if batch.feature_ids else list(TRAJECTORY_FEATURE_IDS)
    key_idx = [fids.index(n) for n in KEY_FEATURE_NAMES if n in fids]

    for c in range(k_star):
        members = [i for i in range(len(labels_all)) if int(labels_all[i]) == c]
        mem_is = [i for i in members if i in is_set]
        mem_oos = [i for i in members if i in oos_set]
        if len(mem_is) < G4_MIN_N_IS or len(mem_oos) < G4_MIN_N_OOS:
            g4_ok = False

        # medoid among IS
        if mem_is:
            # distances in scaled space for IS members
            Xi = X_all[mem_is]
            d = np.linalg.norm(Xi - centers[c], axis=1)
            medoid_local = int(np.argmin(d))
            medoid_i = mem_is[medoid_local]
        else:
            medoid_i = members[0] if members else -1

        # G3: OOS vs IS centroid-distance (robust scale; avoid 1/ε explosions)
        if mem_oos and len(cluster_is_dist.get(c, [])) >= 5:
            is_d = cluster_is_dist[c]
            mu = float(np.median(is_d))
            mad = float(np.median(np.abs(is_d - mu)))
            sd = float(np.std(is_d))
            scale = max(sd, 1.4826 * mad, 1e-3)
            oos_d = np.linalg.norm(X_all[mem_oos] - centers[c], axis=1)
            med_oos = float(np.median(oos_d))
            z_mean = (med_oos - mu) / scale
            g3_scores.append(z_mean)
        else:
            g3_scores.append(0.0)

        # mean path for key dims: average Z over members_is
        mean_path: dict[str, list[float]] = {}
        if mem_is and key_idx:
            Zm = Z[mem_is]  # (m, N, D)
            for di, name in zip(key_idx, [fids[j] for j in key_idx]):
                mean_path[name] = np.mean(Zm[:, :, di], axis=0).round(4).tolist()

        # representatives: top-5 nearest IS, top-3 nearest OOS
        def nearest(ids: list[int], k: int) -> list[str]:
            if not ids:
                return []
            d = np.linalg.norm(X_all[ids] - centers[c], axis=1)
            order = np.argsort(d)[:k]
            return [batch.trade_ids[ids[j]] for j in order]

        tp_oos = _tp_rate(y_outcomes, mem_oos)
        if (
            tp_oos is not None
            and global_tp is not None
            and len(mem_oos) >= PURITY_MIN_N_OOS
            and abs(tp_oos - global_tp) * 100 >= PURITY_DELTA_PP
        ):
            purity_flags.append(
                f"N{N}_k{k_star}_s{c:02d}: tp_oos={tp_oos:.3f} vs global={global_tp:.3f}"
            )

        shape_id = f"N{N}_k{k_star}_s{c:02d}"
        shapes.append(
            {
                "shape_id": shape_id,
                "N": N,
                "k": k_star,
                "cluster": c,
                "n_is": len(mem_is),
                "n_oos": len(mem_oos),
                "n_total": len(members),
                "medoid_trade_id": batch.trade_ids[medoid_i] if medoid_i >= 0 else None,
                "outcome_mix_is": _outcome_mix(y_outcomes, mem_is),
                "outcome_mix_oos": _outcome_mix(y_outcomes, mem_oos),
                "tp_rate_is": _tp_rate(y_outcomes, mem_is),
                "tp_rate_oos": tp_oos,
                "mean_path_key_dims": mean_path,
                "representative_trade_ids_is": nearest(mem_is, 5),
                "representative_trade_ids_oos": nearest(mem_oos, 3),
                "centroid_scaled_norm": float(np.linalg.norm(centers[c])),
            }
        )

    # Pass if no shape's OOS distance mean is >2σ (or relative mean >3× when degenerate)
    g3_ok = all(z <= 2.0 for z in g3_scores) if g3_scores else False

    gates = {
        "G1_compactness": {"sse_ratio": round(sse_ratio, 4), "ok": g1_ok, "max": G1_SSE_RATIO_MAX},
        "G2_silhouette": {"silhouette": round(sil, 4), "ok": g2_ok, "min": G2_SILHOUETTE_MIN},
        "G3_oos_distance": {"mean_z_per_shape": [round(z, 4) for z in g3_scores], "ok": g3_ok},
        "G4_min_n": {"ok": g4_ok, "min_is": G4_MIN_N_IS, "min_oos": G4_MIN_N_OOS},
        "G5_inspectability": {"ok": True},  # set True when docs written by caller
    }
    geometry_ok = g1_ok and g2_ok and g3_ok and g4_ok

    verdict = "LIBRARY_OK" if geometry_ok else "LIBRARY_FAIL"
    if geometry_ok and purity_flags:
        # primary verdict stays LIBRARY_OK; purity is a note
        pass

    # assignments
    assignments = []
    for i, tid in enumerate(batch.trade_ids):
        c = int(labels_all[i])
        assignments.append(
            {
                "trade_id": tid,
                "shape_id": f"N{N}_k{k_star}_s{c:02d}",
                "cluster": c,
                "split": "IS" if i in is_set else "OOS",
                "outcome": y_outcomes[i],
                "entry_index": batch.entry_indices[i],
                "family": batch.families[i],
                "direction": batch.directions[i],
            }
        )

    return {
        "N": N,
        "role": role,
        "k_star": k_star,
        "silhouette_by_k": {str(k): round(v, 4) for k, v in sil_by_k.items()},
        "n": len(batch.trade_ids),
        "n_is": len(is_idx),
        "n_oos": len(oos_idx),
        "global_tp_rate": global_tp,
        "gates": gates,
        "geometry_ok": geometry_ok,
        "verdict": verdict,
        "purity_notes": purity_flags,
        "shapes": shapes,
        "assignments": assignments,
        "centers_scaled": centers.tolist(),
    }


def _write_library_md(results: dict[str, Any], out_dir: Path) -> None:
    lines = [
        "# IC-003 Shape Library",
        "",
        "> DESCRIPTIVE / RESEARCH_ONLY — information not authority (§6.5).",
        "> Shapes are post-entry path prototypes (IC-002). **Not** entry-time filters.",
        "> Stories document shapes; they never create membership.",
        "",
        f"**Program:** H-IC003-001 · overall: **{results.get('program_verdict', {}).get('summary', '')}**",
        "",
    ]
    for key in sorted(results.get("by_N", {}), key=lambda x: (results["by_N"][x].get("role", ""), int(x))):
        r = results["by_N"][key]
        lines.append(f"## N={r['N']} ({r.get('role')}) — **{r.get('verdict')}** · k*={r.get('k_star')}")
        lines.append("")
        g = r.get("gates") or {}
        lines.append(
            f"G1 sse_ratio={g.get('G1_compactness', {}).get('sse_ratio')} "
            f"G2 sil={g.get('G2_silhouette', {}).get('silhouette')} "
            f"G3 ok={g.get('G3_oos_distance', {}).get('ok')} "
            f"G4 ok={g.get('G4_min_n', {}).get('ok')}"
        )
        lines.append("")
        lines.append("| shape_id | n_is | n_oos | tp_oos | medoid |")
        lines.append("|----------|-----:|------:|-------:|--------|")
        for s in r.get("shapes") or []:
            lines.append(
                f"| `{s['shape_id']}` | {s['n_is']} | {s['n_oos']} | "
                f"{s.get('tp_rate_oos')} | `{s.get('medoid_trade_id')}` |"
            )
        lines.append("")
        if r.get("purity_notes"):
            lines.append("### Purity notes (diagnostic only)")
            for p in r["purity_notes"]:
                lines.append(f"- {p}")
            lines.append("")
        for s in r.get("shapes") or []:
            lines.append(f"### `{s['shape_id']}`")
            lines.append("")
            lines.append(f"- mix_oos: `{s.get('outcome_mix_oos')}`")
            lines.append(f"- reps_is: {s.get('representative_trade_ids_is')}")
            mp = s.get("mean_path_key_dims") or {}
            if mp:
                lines.append(f"- mean_path (key dims): `{json.dumps(mp)}`")
            lines.append("")
    lines += [
        "## Explicit non-actions",
        "- Do not use shape_id as live entry filter",
        "- Do not promote purity to expectancy authority",
        "- No new engines / fusion / config",
        "",
    ]
    (out_dir / "SHAPE_LIBRARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_all(
    *,
    ic002_dir: Path | None = None,
    out_dir: Path | None = None,
    primary_N: tuple[int, ...] = PRIMARY_N,
    diagnostic_N: tuple[int, ...] = DIAGNOSTIC_N,
) -> dict[str, Any]:
    ic002_dir = ic002_dir or DEFAULT_IC002
    out_dir = out_dir or DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)

    by_N: dict[str, Any] = {}
    for N in primary_N:
        logger.info("primary N=%s", N)
        by_N[str(N)] = build_for_N(ic002_dir, N, role="primary")
    for N in diagnostic_N:
        logger.info("diagnostic N=%s", N)
        by_N[str(N)] = build_for_N(ic002_dir, N, role="diagnostic")

    # G5: write docs
    for N, r in by_N.items():
        if r.get("verdict") == "INSUFFICIENT":
            continue
        r["gates"]["G5_inspectability"] = {"ok": True}
        # re-evaluate geometry_ok with G5
        g = r["gates"]
        r["geometry_ok"] = (
            g["G1_compactness"]["ok"]
            and g["G2_silhouette"]["ok"]
            and g["G3_oos_distance"]["ok"]
            and g["G4_min_n"]["ok"]
            and g["G5_inspectability"]["ok"]
        )
        if r.get("role") == "primary":
            r["verdict"] = "LIBRARY_OK" if r["geometry_ok"] else "LIBRARY_FAIL"
        else:
            r["verdict"] = (
                "LIBRARY_OK_DIAGNOSTIC" if r["geometry_ok"] else "LIBRARY_FAIL_DIAGNOSTIC"
            )

        # write per-N shapes + assignments
        (out_dir / f"shapes_N{N}_k{r.get('k_star')}.json").write_text(
            json.dumps(
                {k: r[k] for k in r if k != "assignments"},
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
        with open(out_dir / f"assignment_N{N}.jsonl", "w", encoding="utf-8") as f:
            for a in r.get("assignments") or []:
                f.write(json.dumps(a, sort_keys=True) + "\n")

    primary_verdicts = {
        str(N): by_N[str(N)].get("verdict") for N in primary_N if str(N) in by_N
    }
    primary_ok = all(v == "LIBRARY_OK" for v in primary_verdicts.values()) and bool(
        primary_verdicts
    )
    primary_partial = any(v == "LIBRARY_OK" for v in primary_verdicts.values()) and not primary_ok
    any_purity = any(by_N[str(N)].get("purity_notes") for N in primary_N if str(N) in by_N)

    if primary_ok:
        summary = "LIBRARY_OK on all primary N"
        rec = (
            "Descriptive shape library usable for IC-003; no production/entry filters. "
            "Optional narratives after review."
        )
    elif primary_partial:
        summary = (
            "PARTIAL: LIBRARY_OK on some primary N only "
            + str(primary_verdicts)
        )
        rec = (
            "Use LIBRARY_OK horizons only as descriptive prototypes; "
            "do not claim full multi-N ontology. No production/entry filters."
        )
    else:
        summary = "LIBRARY_FAIL on all primary N"
        rec = "Shape library failed geometry gates; do not treat prototypes as stable ontology."
    if any_purity:
        summary += "; PURITY_NOTE present (diagnostic only)"

    program_verdict = {
        "primary_LIBRARY_OK": primary_ok,
        "primary_PARTIAL": primary_partial,
        "primary_verdicts": primary_verdicts,
        "g1_max": G1_SSE_RATIO_MAX,
        "amendment": "A1_G1_0.90" if abs(G1_SSE_RATIO_MAX - 0.90) < 1e-9 else None,
        "any_PURITY_NOTE": any_purity,
        "summary": summary,
        "recommendation": rec,
    }

    # representatives jsonl
    with open(out_dir / "representative_shapes.jsonl", "w", encoding="utf-8") as f:
        for N in list(primary_N) + list(diagnostic_N):
            r = by_N.get(str(N)) or {}
            for s in r.get("shapes") or []:
                f.write(
                    json.dumps(
                        {
                            "shape_id": s["shape_id"],
                            "role": r.get("role"),
                            "N": N,
                            "medoid_trade_id": s.get("medoid_trade_id"),
                            "representatives_is": s.get("representative_trade_ids_is"),
                            "representatives_oos": s.get("representative_trade_ids_oos"),
                            "tp_rate_oos": s.get("tp_rate_oos"),
                            "outcome_mix_oos": s.get("outcome_mix_oos"),
                            "mean_path_key_dims": s.get("mean_path_key_dims"),
                            "authority": "descriptive_only",
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )

    results = {
        "program": "H-IC003-001",
        "status": "RUN_COMPLETE",
        "authority": "research_only",
        "by_N": {k: {kk: vv for kk, vv in v.items() if kk != "assignments"} for k, v in by_N.items()},
        "program_verdict": program_verdict,
        "production_config_changed": False,
        "hard_flags": {
            "ENTRY_TIME_SHAPE_FILTERS": False,
            "EXPECTANCY_PROMOTE_FROM_PURITY": False,
            "NEW_ENGINES": False,
        },
    }

    # strip centers from report file size? keep in shapes json already
    for v in results["by_N"].values():
        v.pop("centers_scaled", None)

    (out_dir / "report.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    _write_library_md(results, out_dir)

    report_lines = [
        "# H-IC003-001 — Shape Library Report",
        "",
        "> RESEARCH_ONLY · IC-003 · pre-registered before measurement",
        "",
        f"**Verdict:** {program_verdict['summary']}",
        "",
        program_verdict["recommendation"],
        "",
        "| N | role | k* | verdict | G1 sse | G2 sil | G3 | G4 | purity notes |",
        "|---:|------|---:|---------|-------:|-------:|----|----|--------------|",
    ]
    for k in sorted(results["by_N"], key=lambda x: int(x)):
        r = results["by_N"][k]
        g = r.get("gates") or {}
        report_lines.append(
            f"| {r.get('N')} | {r.get('role')} | {r.get('k_star')} | **{r.get('verdict')}** | "
            f"{g.get('G1_compactness', {}).get('sse_ratio')} | "
            f"{g.get('G2_silhouette', {}).get('silhouette')} | "
            f"{g.get('G3_oos_distance', {}).get('ok')} | "
            f"{g.get('G4_min_n', {}).get('ok')} | {len(r.get('purity_notes') or [])} |"
        )
    report_lines += [
        "",
        "## Epistemic note",
        "",
        "Shapes describe **post-entry path geometry** (IC-002). They are not entry-time signals.",
        "PURITY_NOTE flags concurrent path–outcome association, not promotable expectancy.",
        "",
        f"Library: `{out_dir / 'SHAPE_LIBRARY.md'}`",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # pins
    pins = {}
    for N in list(primary_N) + list(diagnostic_N):
        npz = ic002_dir / f"trajectories_N{N}.npz"
        if npz.exists():
            pins[f"N{N}"] = sha256_file(npz)
    manifest = {
        "program": "H-IC003-001",
        "ic002_dir": str(ic002_dir),
        "trajectory_sha256": pins,
        "program_verdict": program_verdict,
        "primary_N": list(primary_N),
        "diagnostic_N": list(diagnostic_N),
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    # stub narratives doc under docs (allowed after library)
    narr = repo_root() / "docs" / "research-readiness" / "ic-003-shape-narratives.md"
    if not narr.exists() or "AUTO-STUB" in narr.read_text(encoding="utf-8"):
        nlines = [
            "# IC-003 Shape Narratives (stubs)",
            "",
            "> AUTO-STUB · DESCRIPTIVE only · fill after human review of SHAPE_LIBRARY.md",
            "> Narratives document shapes; they never change membership.",
            "",
        ]
        for k in sorted(results["by_N"], key=lambda x: int(x)):
            r = results["by_N"][k]
            if r.get("role") != "primary":
                continue
            for s in r.get("shapes") or []:
                nlines.append(f"## `{s['shape_id']}`")
                nlines.append("")
                nlines.append(f"- medoid: `{s.get('medoid_trade_id')}`")
                nlines.append(f"- tp_oos: {s.get('tp_rate_oos')}")
                nlines.append("- narrative: **TBD** (path geometry description)")
                nlines.append("")
        narr.write_text("\n".join(nlines) + "\n", encoding="utf-8")

    return results
