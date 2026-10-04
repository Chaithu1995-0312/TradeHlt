# L-003I baseline direction / base-rate inversion (derive from L-003H JSON)
# NO src edits; NO commit; measurement-only artifact writer.
from __future__ import annotations

import json
import statistics as stats
from datetime import datetime, timezone
from pathlib import Path

COMMIT = "d7c25f6e55616261b8b229b000875abd3bd315eb"
SRC_JSON = Path("docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json")


def other_bucket(state: str) -> str:
    return state if state in ("JOINT_STATE_SL_TP", "BOTH_SL", "BOTH_TP") else "OTHER"


def safe_div(a, b):
    return (a / b) if b else None


def compute_from_bjr(bjr: dict, n_total: int) -> dict:
    joint_n = bjr.get("JOINT_STATE_SL_TP", {}).get("n", 0)
    ta1 = te1 = seb1 = 0
    ta1_j1 = ta1_j0 = ta0_j1 = ta0_j0 = 0
    te1_j1 = te1_j0 = te0_j1 = te0_j0 = 0
    seb1_j1 = seb1_j0 = seb0_j1 = seb0_j0 = 0
    mix = {"JOINT_STATE_SL_TP": 0, "BOTH_SL": 0, "BOTH_TP": 0, "OTHER": 0}
    mix_full: dict[str, int] = {}

    for st, m in bjr.items():
        n = m["n"]
        ta = m["trail_activated_n"]
        te = m["trail_exit_n"]
        seb = m["scanner_exit_before_oracle_tp_n"]
        is_joint = st == "JOINT_STATE_SL_TP"
        if is_joint:
            ta1_j1 += ta
            ta0_j1 += n - ta
            te1_j1 += te
            te0_j1 += n - te
            seb1_j1 += seb
            seb0_j1 += n - seb
        else:
            ta1_j0 += ta
            ta0_j0 += n - ta
            te1_j0 += te
            te0_j0 += n - te
            seb1_j0 += seb
            seb0_j0 += n - seb
        mix[other_bucket(st)] += ta
        mix_full[st] = mix_full.get(st, 0) + ta
        ta1 += ta
        te1 += te
        seb1 += seb

    ta0 = n_total - ta1
    te0 = n_total - te1
    seb0 = n_total - seb1
    p_joint = joint_n / n_total

    p_j_ta1 = safe_div(ta1_j1, ta1)
    p_j_ta0 = safe_div(ta0_j1, ta0)
    p_j_te1 = safe_div(te1_j1, te1)
    p_j_te0 = safe_div(te0_j1, te0)
    p_j_seb1 = safe_div(seb1_j1, seb1)
    p_j_seb0 = safe_div(seb0_j1, seb0)

    def lift(p):
        return None if p is None or p_joint == 0 else p / p_joint

    mix_frac = {k: safe_div(v, ta1) for k, v in mix.items()}
    mix_full_frac = {k: safe_div(v, ta1) for k, v in mix_full.items()}

    return {
        "n": n_total,
        "p_joint_base_rate": p_joint,
        "joint_n": joint_n,
        "primary_inversion": {
            "P_joint_given_trail_activated_1": p_j_ta1,
            "P_joint_given_trail_activated_0": p_j_ta0,
            "P_joint_given_trail_exit_1": p_j_te1,
            "P_joint_given_trail_exit_0": p_j_te0,
            "P_joint_given_seb_1": p_j_seb1,
            "P_joint_given_seb_0": p_j_seb0,
            "lift_vs_base_trail_activated_1": lift(p_j_ta1),
            "lift_vs_base_trail_activated_0": lift(p_j_ta0),
            "lift_vs_base_trail_exit_1": lift(p_j_te1),
            "lift_vs_base_trail_exit_0": lift(p_j_te0),
            "lift_vs_base_seb_1": lift(p_j_seb1),
            "lift_vs_base_seb_0": lift(p_j_seb0),
            "n_trail_activated_1": ta1,
            "n_trail_activated_0": ta0,
            "n_trail_exit_1": te1,
            "n_trail_exit_0": te0,
            "n_seb_1": seb1,
            "n_seb_0": seb0,
        },
        "confusion_style_counts": {
            "trail_activated_x_joint": {
                "ta1_joint1": ta1_j1,
                "ta1_joint0": ta1_j0,
                "ta0_joint1": ta0_j1,
                "ta0_joint0": ta0_j0,
                "note": "contingency counts only; not predictor-of-edge language",
            },
            "trail_exit_x_joint": {
                "te1_joint1": te1_j1,
                "te1_joint0": te1_j0,
                "te0_joint1": te0_j1,
                "te0_joint0": te0_j0,
            },
            "seb_x_joint": {
                "seb1_joint1": seb1_j1,
                "seb1_joint0": seb1_j0,
                "seb0_joint1": seb0_j1,
                "seb0_joint0": seb0_j0,
            },
        },
        "among_trail_activated_1_joint_state_mix": {
            "counts": mix,
            "fractions": mix_frac,
            "counts_full_state": mix_full,
            "fractions_full_state": mix_full_frac,
            "critical_note": (
                "BOTH_TP also had 100% trail_activated in L-003H; among activations "
                "BOTH_SL is plurality and JOINT is ~half — activation alone does not imply JOINT"
            ),
        },
        "descriptive_precision_recall_trail_exit_as_joint_detector": {
            "precision_P_joint_given_trail_exit": p_j_te1,
            "recall_P_trail_exit_given_joint": safe_div(te1_j1, joint_n),
            "disclaimer": "label-association stats only, not trading performance",
        },
    }


def pct(x):
    return "n/a" if x is None else f"{100 * x:.2f}%"


def f4(x):
    return "n/a" if x is None else f"{x:.4f}"


def main() -> None:
    src = json.loads(SRC_JSON.read_text(encoding="utf-8"))
    assert src["git_commit_sha"] == COMMIT
    assert src["aggregate"]["n"] == 559768

    now = datetime.now(timezone.utc)
    run_id = f"l003i_trail_baseline_inversion_{now.strftime('%Y%m%d_%H%M%S')}"
    generated_at = now.isoformat().replace("+00:00", "Z")

    agg = compute_from_bjr(src["aggregate"]["by_joint_state_replay"], src["aggregate"]["n"])
    instruments = list(src["per_instrument"].keys())
    per = {
        inst: compute_from_bjr(payload["by_joint_state_replay"], payload["n"])
        for inst, payload in src["per_instrument"].items()
    }

    loio = []
    for holdout in instruments:
        pooled: dict = {}
        n_pool = 0
        for inst in instruments:
            if inst == holdout:
                continue
            bjr = src["per_instrument"][inst]["by_joint_state_replay"]
            n_pool += src["per_instrument"][inst]["n"]
            for st, m in bjr.items():
                if st not in pooled:
                    pooled[st] = {
                        "n": 0,
                        "trail_activated_n": 0,
                        "trail_exit_n": 0,
                        "scanner_exit_before_oracle_tp_n": 0,
                    }
                for k in (
                    "n",
                    "trail_activated_n",
                    "trail_exit_n",
                    "scanner_exit_before_oracle_tp_n",
                ):
                    pooled[st][k] += m[k]
        c = compute_from_bjr(pooled, n_pool)
        loio.append(
            {
                "holdout": f"holdout_{holdout}",
                "n_train": n_pool,
                "P_joint_given_trail_activated_1": c["primary_inversion"][
                    "P_joint_given_trail_activated_1"
                ],
                "P_joint_given_trail_exit_1": c["primary_inversion"][
                    "P_joint_given_trail_exit_1"
                ],
                "P_joint_given_seb_1": c["primary_inversion"]["P_joint_given_seb_1"],
                "p_joint_base_rate": c["p_joint_base_rate"],
            }
        )

    def col(key):
        return [x[key] for x in loio if x[key] is not None]

    loio_summary = {
        "per_holdout": loio,
        "P_joint_given_trail_activated_1": {
            "mean": stats.mean(col("P_joint_given_trail_activated_1")),
            "std": stats.pstdev(col("P_joint_given_trail_activated_1")),
            "range": [
                min(col("P_joint_given_trail_activated_1")),
                max(col("P_joint_given_trail_activated_1")),
            ],
        },
        "P_joint_given_trail_exit_1": {
            "mean": stats.mean(col("P_joint_given_trail_exit_1")),
            "std": stats.pstdev(col("P_joint_given_trail_exit_1")),
            "range": [
                min(col("P_joint_given_trail_exit_1")),
                max(col("P_joint_given_trail_exit_1")),
            ],
        },
    }

    pi = agg["primary_inversion"]
    mixf = agg["among_trail_activated_1_joint_state_mix"]["fractions"]
    baseline_story = (
        "BASELINE_WEAKENS_TRAIL_AS_JOINT_MARKER: among trail_activated=1, JOINT is only "
        f"{mixf['JOINT_STATE_SL_TP']:.4f} (~{100 * mixf['JOINT_STATE_SL_TP']:.1f}%) while BOTH_SL is "
        f"{mixf['BOTH_SL']:.4f}; P(JOINT|trail_activated)={pi['P_joint_given_trail_activated_1']:.4f} "
        f"vs base {agg['p_joint_base_rate']:.4f} (lift {pi['lift_vs_base_trail_activated_1']:.3f}). "
        "Trail activation is necessary-looking for JOINT (recall-side from H) but not precise for JOINT; "
        "BOTH_TP also 100% activated. trail_exit lifts slightly more than activation alone; "
        "seb is near-certain for JOINT when true but is path-timing not causation."
    )

    out = {
        "finding_id": "L-003I",
        "version": "L-003I.v1",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "git_commit_sha": COMMIT,
        "branch": "feature/trace-parquet-duckdb-query",
        "status": "MEASURED",
        "title": "BASELINE_DIRECTION_MEASURED",
        "doctrine": "Observation → Measurement → Evidence → Promotion",
        "questions_answered": [
            "P(JOINT_STATE_SL_TP | trail_activated) and related Bayes-facing conditionals on the L-003H replay universe",
            "Base-rate / precision side of trail markers vs P(trail|JOINT) from L-003H",
            "Among trail_activated=1, joint-state mix (JOINT vs BOTH_SL vs BOTH_TP)",
        ],
        "questions_NOT_answered": [
            "Whether trail causes JOINT / label mismatch",
            "Counterfactual without-trail world",
            "Promotion / economic edge claims",
        ],
        "path_semantics": {
            "Path_plus_TrailLogic_to_scanner": "trailing walk (trail_mult=0.5) → scanner_outcome_replay",
            "Path_plus_FixedLogic_to_oracle": "intrabar_fixed walk → oracle_outcome_replay",
            "explicit": "No counterfactual without-trail world constructed; conditionals are associations within dual-path replay labels",
        },
        "flags": {
            "promotion": False,
            "l003_frozen": False,
            "attribution_unblocked": False,
            "economic_claims": False,
            "registry_edits": False,
            "causal_language_upgrade": False,
        },
        "data_reuse": {
            "source_finding": "L-003H",
            "source_run_id": src["run_id"],
            "source_json": str(SRC_JSON).replace("\\", "/"),
            "method": "Derived contingency / Bayes inversion from L-003H aggregate + per-instrument by_joint_state_replay counters; no new candle replay",
            "n_universe": 559768,
            "instruments": instruments,
        },
        "wording": {
            "finding_title": "BASELINE_DIRECTION_MEASURED",
            "lean_retained": "LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP",
            "lean_note": "Do NOT upgrade to causality; baseline direction shows trail markers are not precise for JOINT despite near-certain activation inside JOINT",
            "baseline_direction_story": baseline_story,
        },
        "aggregate": agg,
        "per_instrument": per,
        "loio_stability": loio_summary,
        "parent_links": {
            "L-003H": "docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md",
            "L-003F": "docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md",
        },
        "reproducibility": {
            "script_note": "scripts/research/l003i_trail_baseline_inversion.py derives from L-003H JSON counters; l003h replay not re-executed",
            "commit": COMMIT,
        },
    }

    jpath = Path("docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json")
    jpath.write_text(json.dumps(out, indent=2), encoding="utf-8")

    cc = agg["confusion_style_counts"]
    mix = agg["among_trail_activated_1_joint_state_mix"]
    pr = agg["descriptive_precision_recall_trail_exit_as_joint_detector"]

    lines = []
    a = lines.append
    a("# L-003I — Trail baseline direction / base-rate inversion")
    a("")
    a("**Status:** MEASURED (falsification-oriented observation)")
    a("**Title:** `BASELINE_DIRECTION_MEASURED`")
    a("**L-003 remains NOT frozen** — attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)")
    a(f"**Date (UTC):** {generated_at}")
    a(f"**Branch pin:** `feature/trace-parquet-duckdb-query` @ `{COMMIT}`")
    a(f"**run_id:** `{run_id}`")
    a("**version / doctrine:** `L-003I.v1`")
    a("")
    a("Machine-readable: `docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json`.")
    a("")
    a("## Banner / discipline")
    a("")
    a("**Observation → Measurement → Evidence → Promotion.**")
    a("")
    a("- **Question:** Given L-003H measured P(trail_activated | JOINT)=1.0, what is the **inverse** base-rate direction P(JOINT | trail_activated) (and siblings)?")
    a("- **Method:** Bayes-facing contingency tables derived from the same L-003H replay universe counters (n=559,768); no new candle replay; no `src/` edits.")
    a("- **NOT answered:** trail *causes* JOINT / label mismatch; counterfactual without-trail world; promotion.")
    a("- **Lean retained (not upgraded):** `LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP`")
    a("")
    a("## Path semantics (explicit)")
    a("")
    a("- **Path + TrailLogic → scanner:** trailing walk (`trail_mult=0.5`) → `scanner_outcome_replay`")
    a("- **Path + FixedLogic → oracle:** `intrabar_fixed` walk → `oracle_outcome_replay`")
    a("- No counterfactual without-trail world is constructed. Conditionals are associations within dual-path replay labels.")
    a("")
    a("## Universe")
    a("")
    a(f"n = **559,768** (BNB+BTC+ETH+SOL), reused from L-003H run `{src['run_id']}`.")
    a(f"Base rate P(JOINT_STATE_SL_TP) = **{pct(agg['p_joint_base_rate'])}** (n_joint={agg['joint_n']:,}).")
    a("")
    a("## A. Primary inversion (aggregate)")
    a("")
    a("| Conditional | Estimate | Lift vs base (~31.53%) |")
    a("|---|---:|---:|")
    a(f"| P(JOINT \\| trail_activated=1) | {pct(pi['P_joint_given_trail_activated_1'])} | {f4(pi['lift_vs_base_trail_activated_1'])}× |")
    a(f"| P(JOINT \\| trail_activated=0) | {pct(pi['P_joint_given_trail_activated_0'])} | {f4(pi['lift_vs_base_trail_activated_0'])}× |")
    a(f"| P(JOINT \\| trail_exit=1) | {pct(pi['P_joint_given_trail_exit_1'])} | {f4(pi['lift_vs_base_trail_exit_1'])}× |")
    a(f"| P(JOINT \\| trail_exit=0) | {pct(pi['P_joint_given_trail_exit_0'])} | {f4(pi['lift_vs_base_trail_exit_0'])}× |")
    a(f"| P(JOINT \\| seb=1) | {pct(pi['P_joint_given_seb_1'])} | {f4(pi['lift_vs_base_seb_1'])}× |")
    a(f"| P(JOINT \\| seb=0) | {pct(pi['P_joint_given_seb_0'])} | {f4(pi['lift_vs_base_seb_0'])}× |")
    a("")
    a(f"Factor margins: n(trail_activated=1)={pi['n_trail_activated_1']:,}; n(trail_exit=1)={pi['n_trail_exit_1']:,}; n(seb=1)={pi['n_seb_1']:,}.")
    a("")
    a("## B. Confusion-style 2×2 counts (contingency language only)")
    a("")
    a("**Do NOT call trail a predictor of edge.** Cells are co-occurrence counts.")
    a("")
    a("### trail_activated × JOINT")
    a("")
    a("|  | JOINT=1 | JOINT=0 |")
    a("|---|---:|---:|")
    a(f"| trail_activated=1 | {cc['trail_activated_x_joint']['ta1_joint1']:,} | {cc['trail_activated_x_joint']['ta1_joint0']:,} |")
    a(f"| trail_activated=0 | {cc['trail_activated_x_joint']['ta0_joint1']:,} | {cc['trail_activated_x_joint']['ta0_joint0']:,} |")
    a("")
    a("### trail_exit × JOINT")
    a("")
    a("|  | JOINT=1 | JOINT=0 |")
    a("|---|---:|---:|")
    a(f"| trail_exit=1 | {cc['trail_exit_x_joint']['te1_joint1']:,} | {cc['trail_exit_x_joint']['te1_joint0']:,} |")
    a(f"| trail_exit=0 | {cc['trail_exit_x_joint']['te0_joint1']:,} | {cc['trail_exit_x_joint']['te0_joint0']:,} |")
    a("")
    a("### seb × JOINT")
    a("")
    a("|  | JOINT=1 | JOINT=0 |")
    a("|---|---:|---:|")
    a(f"| seb=1 | {cc['seb_x_joint']['seb1_joint1']:,} | {cc['seb_x_joint']['seb1_joint0']:,} |")
    a(f"| seb=0 | {cc['seb_x_joint']['seb0_joint1']:,} | {cc['seb_x_joint']['seb0_joint0']:,} |")
    a("")
    a("## C. Among trail_activated=1 — joint-state mix (critical base-rate story)")
    a("")
    a(f"n(trail_activated=1) = {pi['n_trail_activated_1']:,}.")
    a("")
    a("| joint_state bucket | n among ta=1 | fraction |")
    a("|---|---:|---:|")
    a(f"| BOTH_SL | {mix['counts']['BOTH_SL']:,} | {pct(mix['fractions']['BOTH_SL'])} |")
    a(f"| JOINT_STATE_SL_TP | {mix['counts']['JOINT_STATE_SL_TP']:,} | {pct(mix['fractions']['JOINT_STATE_SL_TP'])} |")
    a(f"| BOTH_TP | {mix['counts']['BOTH_TP']:,} | {pct(mix['fractions']['BOTH_TP'])} |")
    a(f"| OTHER | {mix['counts']['OTHER']:,} | {pct(mix['fractions']['OTHER'])} |")
    a("")
    a(
        f"**Critical:** L-003H already showed BOTH_TP also has 100% trail_activated. "
        f"Among activations, BOTH_SL is the plurality (~{pct(mix['fractions']['BOTH_SL'])}); "
        f"JOINT is only ~{pct(mix['fractions']['JOINT_STATE_SL_TP'])}. Activation alone does **not** select JOINT."
    )
    a("")
    a("## D. Precision / recall style (descriptive label-association only)")
    a("")
    a('Treating `trail_exit` as a descriptive "detector" of JOINT (NOT trading performance):')
    a("")
    a(f"- **precision** = P(JOINT | trail_exit=1) = {pct(pr['precision_P_joint_given_trail_exit'])}")
    a(f"- **recall** = P(trail_exit | JOINT) = {pct(pr['recall_P_trail_exit_given_joint'])} (matches L-003H ~1.0)")
    a("")
    a("These are **label-association stats**, not trading performance / edge claims.")
    a("")
    a("## E. LOIO stability of inversion conditionals")
    a("")
    a("| holdout | n_train | P(JOINT|ta=1) | P(JOINT|te=1) |")
    a("|---|---:|---:|---:|")
    for row in loio_summary["per_holdout"]:
        a(
            f"| {row['holdout']} | {row['n_train']:,} | "
            f"{pct(row['P_joint_given_trail_activated_1'])} | "
            f"{pct(row['P_joint_given_trail_exit_1'])} |"
        )
    a("")
    a(
        f"LOIO P(JOINT|ta=1): mean={pct(loio_summary['P_joint_given_trail_activated_1']['mean'])}, "
        f"std={loio_summary['P_joint_given_trail_activated_1']['std']:.6f}, "
        f"range=[{pct(loio_summary['P_joint_given_trail_activated_1']['range'][0])}, "
        f"{pct(loio_summary['P_joint_given_trail_activated_1']['range'][1])}]."
    )
    a(
        f"LOIO P(JOINT|te=1): mean={pct(loio_summary['P_joint_given_trail_exit_1']['mean'])}, "
        f"std={loio_summary['P_joint_given_trail_exit_1']['std']:.6f}, "
        f"range=[{pct(loio_summary['P_joint_given_trail_exit_1']['range'][0])}, "
        f"{pct(loio_summary['P_joint_given_trail_exit_1']['range'][1])}]."
    )
    a("")
    a("## F. Baseline-direction reading (wording discipline)")
    a("")
    a(baseline_story)
    a("")
    a("- Keep lean: **LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP** (from L-003H exit-timing / trail_exit differentiation vs BOTH_TP).")
    a("- Do **not** upgrade to causality.")
    a("- Baseline direction **weakens** any reading that treats trail_activated as approximately identifying JOINT; it **leaves intact** the H finding that within JOINT, trail/exit timing patterns differ from BOTH_TP (seb / trail_exit), and that JOINT is trail-activated at 100% while BOTH_SL is ~50%.")
    a("")
    a("## Per-instrument snapshot (P(JOINT|ta=1) / P(JOINT|te=1) / P(JOINT|seb=1))")
    a("")
    for inst, c in per.items():
        pii = c["primary_inversion"]
        a(
            f"- **{inst}** n={c['n']:,}; "
            f"P(J|ta)={pct(pii['P_joint_given_trail_activated_1'])}; "
            f"P(J|te)={pct(pii['P_joint_given_trail_exit_1'])}; "
            f"P(J|seb)={pct(pii['P_joint_given_seb_1'])}; "
            f"base={pct(c['p_joint_base_rate'])}"
        )
    a("")
    a("## Flags")
    a("")
    a("- `promotion`: False")
    a("- `l003_frozen`: False")
    a("- `attribution_unblocked`: False")
    a("- `economic_claims`: False")
    a("- `registry_edits`: False")
    a("- `causal_language_upgrade`: False")
    a("")
    a("## Reproducibility")
    a("")
    a("- Derived from: `docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json` (L-003H counters)")
    a("- Derivation script: `scripts/research/l003i_trail_baseline_inversion.py`")
    a("- Parent measurement script (not re-run): `scripts/research/l003h_trail_exit_transition_replay.py`")
    a(f"- Commit: `{COMMIT}`")
    a("")
    a("## Parent links")
    a("")
    a("- L-003H: `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md`")
    a("- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`")
    a("")

    mdpath = Path("docs/governance/ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md")
    mdpath.write_text("\n".join(lines), encoding="utf-8")

    hpath = Path("docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md")
    hmd = hpath.read_text(encoding="utf-8")
    if "L-003I baseline direction" not in hmd:
        pointer = (
            "\n\n## Follow-on: L-003I baseline direction\n\n"
            "User review of L-003H noted missing baseline direction (P(JOINT|trail_*) vs P(trail|JOINT)). "
            "See `docs/governance/ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md` / "
            "`docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json` "
            f"(run_id `{run_id}`, title BASELINE_DIRECTION_MEASURED). "
            "Lean not upgraded to causality.\n"
        )
        hpath.write_text(hmd.rstrip() + pointer, encoding="utf-8")

    impact = {
        "finding_id": "L-003I",
        "version": "L-003I.v1",
        "run_id": run_id,
        "generated_at_utc": generated_at,
        "git_commit_sha": COMMIT,
        "title": "BASELINE_DIRECTION_MEASURED",
        "summary": {
            "P_JOINT_given_trail_activated": pi["P_joint_given_trail_activated_1"],
            "P_JOINT_given_trail_exit": pi["P_joint_given_trail_exit_1"],
            "P_JOINT_given_seb": pi["P_joint_given_seb_1"],
            "base_rate_JOINT": agg["p_joint_base_rate"],
            "among_ta1_JOINT_frac": mix["fractions"]["JOINT_STATE_SL_TP"],
            "among_ta1_BOTH_SL_frac": mix["fractions"]["BOTH_SL"],
            "among_ta1_BOTH_TP_frac": mix["fractions"]["BOTH_TP"],
            "baseline_effect_on_trail_story": "WEAKENS_precision_of_trail_activated_as_JOINT_marker; RETAINS_L003H_lean_on_exit_timing_pattern",
        },
        "flags": out["flags"],
        "artifacts": [
            "docs/governance/ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md",
            "docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json",
        ],
    }
    ipath = Path("docs/governance/analytics_trail_baseline_inversion_l003i_impact-2026-09-07.json")
    ipath.write_text(json.dumps(impact, indent=2), encoding="utf-8")

    # also persist script itself for reproducibility (already this file)
    print("run_id", run_id)
    print("P(J|ta)=", pi["P_joint_given_trail_activated_1"])
    print("P(J|te)=", pi["P_joint_given_trail_exit_1"])
    print("P(J|seb)=", pi["P_joint_given_seb_1"])
    print("base=", agg["p_joint_base_rate"])
    print("mix_ta1", mix["fractions"])
    print("wrote", jpath, mdpath, ipath)


if __name__ == "__main__":
    main()
