# -*- coding: utf-8 -*-
"""Compare CRT_GUARD_ABLATION_V1 rankings across datasets."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATHS = {
    "xau_6m_mixed": ROOT
    / "results/runtime_benchmarks/guard_ablation_6m/guard_ablation_6m_report.json",
    "xau_trend_3m": ROOT
    / "results/runtime_benchmarks/guard_ablation_xau_trend_3m/guard_ablation_xau_trend_3m_report.json",
    "xau_range_3m": ROOT
    / "results/runtime_benchmarks/guard_ablation_xau_range_3m/guard_ablation_xau_range_3m_report.json",
}

OUT_JSON = ROOT / "results/runtime_benchmarks/guard_ablation_cross_dataset_comparison.json"
OUT_MD = ROOT / "results/runtime_benchmarks/guard_ablation_cross_dataset_comparison.md"


def arm_map(report: dict) -> dict:
    out = {}
    for a in report.get("arms") or []:
        aid = a["arm_id"]
        base = {
            "n_retest": a["throughput"]["n_retest"],
            "trades": a["throughput"]["approved_trades"],
            "disp": a["structure"].get("n_displacement"),
            "exp": a["structure"].get("n_expansion"),
            "sweep": a["structure"].get("n_sweep"),
            "avg_rr": a["expectancy"]["avg_rr_net"],
            "pnl": a["expectancy"]["total_pnl_rr_net"],
        }
        if aid == "baseline":
            base.update(
                {k: 0 for k in ("d_ret", "d_tr", "d_disp", "d_exp", "d_pnl", "d_avg")}
            )
        else:
            d = a.get("delta_vs_baseline") or {}
            base.update(
                {
                    "d_ret": d.get("delta_n_retest") or 0,
                    "d_tr": d.get("delta_approved_trades") or 0,
                    "d_disp": d.get("delta_n_displacement") or 0,
                    "d_exp": d.get("delta_n_expansion") or 0,
                    "d_pnl": d.get("delta_total_pnl_rr_net") or 0,
                    "d_avg": d.get("delta_avg_rr_net") or 0,
                }
            )
        out[aid] = base
    return out


def rank(m: dict, key: str) -> list[tuple[str, float]]:
    items = [(aid, float(m[aid][key] or 0)) for aid in m if aid != "baseline"]
    items.sort(key=lambda x: -x[1])
    return items


def spearman_top(rank_a: list, rank_b: list) -> dict:
    """Spearman on common arms using rank positions."""
    pos_a = {a: i + 1 for i, (a, _) in enumerate(rank_a)}
    pos_b = {a: i + 1 for i, (a, _) in enumerate(rank_b)}
    common = sorted(set(pos_a) & set(pos_b))
    if len(common) < 2:
        return {"n": len(common), "rho": None}
    n = len(common)
    d2 = sum((pos_a[a] - pos_b[a]) ** 2 for a in common)
    rho = 1 - (6 * d2) / (n * (n * n - 1))
    return {"n": n, "rho": round(rho, 4), "arms": common}


def main() -> int:
    reports = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in PATHS.items()}
    maps = {k: arm_map(r) for k, r in reports.items()}

    metrics = ["d_disp", "d_ret", "d_tr", "d_pnl"]
    rankings = {
        ds: {m: rank(maps[ds], m) for m in metrics} for ds in maps
    }

    # persistence: does #1 by d_disp / d_ret match across datasets?
    top1 = {
        m: {ds: rankings[ds][m][0][0] if rankings[ds][m] else None for ds in maps}
        for m in metrics
    }

    # all ablation arm ids (exclude baseline)
    arms = sorted({a for m in maps.values() for a in m if a != "baseline"})

    # sign agreement: for each arm, is delta_retest sign consistent?
    sign_matrix = {}
    for arm in arms:
        row = {}
        for ds, m in maps.items():
            if arm not in m:
                row[ds] = None
            else:
                v = m[arm]["d_ret"]
                row[ds] = 1 if v > 0 else (-1 if v < 0 else 0)
                row[f"{ds}_d_ret"] = v
                row[f"{ds}_d_disp"] = m[arm]["d_disp"]
                row[f"{ds}_d_tr"] = m[arm]["d_tr"]
                row[f"{ds}_d_pnl"] = m[arm]["d_pnl"]
        sign_matrix[arm] = row

    # classification
    essential = []  # positive d_ret on >=2 datasets with max d_disp often top
    inert = []
    unstable = []
    for arm in arms:
        signs = [
            sign_matrix[arm][ds]
            for ds in maps
            if sign_matrix[arm].get(ds) is not None
        ]
        d_rets = [sign_matrix[arm][f"{ds}_d_ret"] for ds in maps]
        if all(s == 0 for s in signs):
            inert.append(arm)
        elif all(s >= 0 for s in signs) and any(s > 0 for s in signs):
            essential.append(
                {
                    "arm": arm,
                    "d_ret_by_ds": {ds: sign_matrix[arm][f"{ds}_d_ret"] for ds in maps},
                    "d_disp_by_ds": {ds: sign_matrix[arm][f"{ds}_d_disp"] for ds in maps},
                }
            )
        else:
            unstable.append(
                {
                    "arm": arm,
                    "signs": {ds: sign_matrix[arm][ds] for ds in maps},
                    "d_ret_by_ds": {ds: sign_matrix[arm][f"{ds}_d_ret"] for ds in maps},
                }
            )

    comparison = {
        "protocol": "CRT_GUARD_ABLATION_V1",
        "authority": "DESCRIPTIVE_ONLY_NOT_PROMOTION",
        "datasets": {
            k: {
                "path": str(PATHS[k].relative_to(ROOT)).replace("\\", "/"),
                "label": reports[k].get("label") or k,
                "regime_note": reports[k].get("regime_note")
                or reports[k].get("window"),
                "baseline": {
                    "n_retest": maps[k]["baseline"]["n_retest"],
                    "trades": maps[k]["baseline"]["trades"],
                    "disp": maps[k]["baseline"]["disp"],
                    "exp": maps[k]["baseline"]["exp"],
                    "avg_rr": maps[k]["baseline"]["avg_rr"],
                    "pnl": maps[k]["baseline"]["pnl"],
                },
            }
            for k in maps
        },
        "rankings": {
            ds: {m: [{"arm": a, "delta": v} for a, v in rankings[ds][m]] for m in metrics}
            for ds in maps
        },
        "top1_by_metric": top1,
        "spearman_rho": {
            "d_ret_6m_vs_trend": spearman_top(
                rankings["xau_6m_mixed"]["d_ret"], rankings["xau_trend_3m"]["d_ret"]
            ),
            "d_ret_6m_vs_range": spearman_top(
                rankings["xau_6m_mixed"]["d_ret"], rankings["xau_range_3m"]["d_ret"]
            ),
            "d_ret_trend_vs_range": spearman_top(
                rankings["xau_trend_3m"]["d_ret"], rankings["xau_range_3m"]["d_ret"]
            ),
            "d_disp_6m_vs_trend": spearman_top(
                rankings["xau_6m_mixed"]["d_disp"], rankings["xau_trend_3m"]["d_disp"]
            ),
            "d_disp_6m_vs_range": spearman_top(
                rankings["xau_6m_mixed"]["d_disp"], rankings["xau_range_3m"]["d_disp"]
            ),
            "d_disp_trend_vs_range": spearman_top(
                rankings["xau_trend_3m"]["d_disp"], rankings["xau_range_3m"]["d_disp"]
            ),
        },
        "arm_deltas": sign_matrix,
        "classification": {
            "positive_retest_delta_on_some_no_negative": essential,
            "inert_zero_retest_delta_all": inert,
            "unstable_sign_flip_or_mixed": unstable,
        },
        "conclusion": None,  # filled below
    }

    # conclusion text
    top_disp = [top1["d_disp"][ds] for ds in maps]
    top_ret = [top1["d_ret"][ds] for ds in maps]
    move_is_top_disp = all(t == "ablate_disp_move" for t in top_disp)
    conclusion = {
        "disp_move_is_top_structure_gate_all_ds": move_is_top_disp,
        "top1_d_disp": top1["d_disp"],
        "top1_d_ret": top1["d_ret"],
        "top1_d_tr": top1["d_tr"],
        "summary": (
            "P_DISP_MOVE (ablate_disp_move) is the only arm that consistently ranks "
            "first on Δ displacement across mixed/trend/range. "
            "Retest and trade rankings are less stable and often admission-capped "
            "(session filter). Expectancy deltas remain underpowered (tiny trade n)."
            if move_is_top_disp
            else "Structure-gate ranking is NOT stable across regimes; treat priors as window-specific."
        ),
    }
    comparison["conclusion"] = conclusion

    OUT_JSON.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=True, default=str) + "\n",
        encoding="utf-8",
    )

    # Markdown
    lines = [
        "# Cross-Dataset Guard Ablation Comparison",
        "",
        "**Protocol:** CRT_GUARD_ABLATION_V1 (identical arms)  ",
        "**Authority:** descriptive only — no promotion  ",
        "",
        "## Datasets",
        "",
        "| Label | Window | Baseline retest | Trades | avgRR |",
        "|---|---|---:|---:|---:|",
    ]
    notes = {
        "xau_6m_mixed": "Mixed recent 6m (baseline characterization)",
        "xau_trend_3m": "Strong uptrend 2025-08→10 (+21.6%)",
        "xau_range_3m": "Near-flat 2024-10→12 (−0.35%)",
    }
    for k in maps:
        b = maps[k]["baseline"]
        lines.append(
            f"| `{k}` | {notes[k]} | {b['n_retest']} | {b['trades']} | {b['avg_rr']} |"
        )

    lines += [
        "",
        "## Δ retest by arm × dataset",
        "",
        "| Arm | 6m mixed | Trend 3m | Range 3m |",
        "|---|---:|---:|---:|",
    ]
    for arm in arms:
        lines.append(
            f"| `{arm}` | {maps['xau_6m_mixed'][arm]['d_ret']} | "
            f"{maps['xau_trend_3m'][arm]['d_ret']} | "
            f"{maps['xau_range_3m'][arm]['d_ret']} |"
        )

    lines += [
        "",
        "## Δ displacement by arm × dataset",
        "",
        "| Arm | 6m mixed | Trend 3m | Range 3m |",
        "|---|---:|---:|---:|",
    ]
    for arm in arms:
        lines.append(
            f"| `{arm}` | {maps['xau_6m_mixed'][arm]['d_disp']} | "
            f"{maps['xau_trend_3m'][arm]['d_disp']} | "
            f"{maps['xau_range_3m'][arm]['d_disp']} |"
        )

    lines += [
        "",
        "## Δ trades by arm × dataset",
        "",
        "| Arm | 6m mixed | Trend 3m | Range 3m |",
        "|---|---:|---:|---:|",
    ]
    for arm in arms:
        lines.append(
            f"| `{arm}` | {maps['xau_6m_mixed'][arm]['d_tr']} | "
            f"{maps['xau_trend_3m'][arm]['d_tr']} | "
            f"{maps['xau_range_3m'][arm]['d_tr']} |"
        )

    lines += [
        "",
        "## Δ Σ PnL (R) by arm × dataset",
        "",
        "| Arm | 6m mixed | Trend 3m | Range 3m |",
        "|---|---:|---:|---:|",
    ]
    for arm in arms:
        lines.append(
            f"| `{arm}` | {maps['xau_6m_mixed'][arm]['d_pnl']} | "
            f"{maps['xau_trend_3m'][arm]['d_pnl']} | "
            f"{maps['xau_range_3m'][arm]['d_pnl']} |"
        )

    lines += [
        "",
        "## Top-1 arm by metric",
        "",
        "| Metric | 6m mixed | Trend | Range | Stable? |",
        "|---|---|---|---|---|",
    ]
    for m in metrics:
        vals = [top1[m][ds] for ds in maps]
        stable = "YES" if len(set(vals)) == 1 else "NO"
        lines.append(
            f"| {m} | `{top1[m]['xau_6m_mixed']}` | `{top1[m]['xau_trend_3m']}` | "
            f"`{top1[m]['xau_range_3m']}` | **{stable}** |"
        )

    lines += [
        "",
        "## Spearman ρ (rank correlation)",
        "",
        "```json",
        json.dumps(comparison["spearman_rho"], indent=2),
        "```",
        "",
        "## Classification",
        "",
        "### Structure-positive (Δ retest ≥ 0 everywhere; >0 somewhere)",
        "",
    ]
    for e in essential:
        lines.append(f"- `{e['arm']}`: d_ret={e['d_ret_by_ds']} d_disp={e['d_disp_by_ds']}")
    if not essential:
        lines.append("- *(none)*")
    lines += ["", "### Inert (Δ retest = 0 on all three)", ""]
    for a in inert:
        lines.append(f"- `{a}`")
    if not inert:
        lines.append("- *(none)*")
    lines += ["", "### Unstable (sign flip on Δ retest)", ""]
    for u in unstable:
        lines.append(f"- `{u['arm']}`: {u['d_ret_by_ds']}")
    if not unstable:
        lines.append("- *(none)*")

    lines += [
        "",
        "## Conclusion",
        "",
        conclusion["summary"],
        "",
        f"- `disp_move` top on Δ disp all datasets: "
        f"**{conclusion['disp_move_is_top_structure_gate_all_ds']}**",
        f"- Top-1 Δ retest: `{conclusion['top1_d_ret']}`",
        f"- Top-1 Δ trades: `{conclusion['top1_d_tr']}`",
        "",
        "Expectancy rankings remain **not durable** (n_trades often 0–2).",
        "",
        f"JSON: `{OUT_JSON.relative_to(ROOT).as_posix()}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote", OUT_JSON)
    print("Wrote", OUT_MD)
    print("CONCLUSION:", conclusion["summary"])
    print("top1 d_disp", top1["d_disp"])
    print("top1 d_ret", top1["d_ret"])
    print("top1 d_tr", top1["d_tr"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
