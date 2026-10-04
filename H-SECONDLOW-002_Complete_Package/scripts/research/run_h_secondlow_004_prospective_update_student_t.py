#!/usr/bin/env python3
"""H-SECONDLOW-004 v0.2 — Student-t Bayesian prospective update (protocol v1.2 exploratory).

Governance tier gates remain on the Normal conjugate track (protocol v1.1).
This script appends a decision-support snapshot with bayesian_model=student_t.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import detect_independent_events, load_ohlcv, sha256_prefix

# Import shared helpers from the v1.1 dual-track script.
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from run_h_secondlow_004_prospective_update import (  # noqa: E402
    DEPTH_THRESHOLD,
    LEDGER,
    OUTPUT,
    PREREG,
    PRIOR_MU,
    PRIOR_SD,
    UPDATE_LOG,
    _load_ledger_times,
    bayesian_update,
    bootstrap_median_diff,
    evaluate_rules,
    pooled_mean_se,
)

STUDENT_T_DF = 4.0
GRID_LO = -12.0
GRID_HI = 12.0
GRID_N = 12001


def bayesian_update_student_t(
    prior_mu: float,
    prior_sd: float,
    data_mu: float,
    data_se: float,
    *,
    df: float = STUDENT_T_DF,
    grid_lo: float = GRID_LO,
    grid_hi: float = GRID_HI,
    grid_n: int = GRID_N,
) -> dict:
    """Normal prior × Student-t likelihood on batch mean difference (numerical grid)."""
    if not math.isfinite(data_mu) or not math.isfinite(data_se) or data_se <= 0:
        return {
            "bayesian_model": "student_t",
            "prior_mu": prior_mu,
            "prior_sd": prior_sd,
            "likelihood_df": df,
            "data_mu": data_mu,
            "data_se": data_se,
            "posterior_mu": None,
            "posterior_sd": None,
            "p_effect_positive": None,
            "credible_interval_95": [None, None],
            "grid_lo": grid_lo,
            "grid_hi": grid_hi,
            "grid_n": grid_n,
            "update_skipped": True,
        }

    grid = np.linspace(grid_lo, grid_hi, grid_n)
    log_prior = stats.norm.logpdf(grid, prior_mu, prior_sd)
    log_like = stats.t.logpdf(data_mu, df, loc=grid, scale=data_se)
    log_post = log_prior + log_like
    log_post -= np.max(log_post)
    post = np.exp(log_post)
    from numpy import trapezoid as _trapz
    norm = _trapz(post, grid)
    post /= norm

    mu_post = float(_trapz(grid * post, grid))
    mu2_post = float(_trapz(grid**2 * post, grid))
    var_post = max(mu2_post - mu_post**2, 0.0)
    sd_post = math.sqrt(var_post)

    mask = grid >= 0
    p_pos = float(_trapz(post[mask], grid[mask]))

    cdf = np.cumsum((post[:-1] + post[1:]) / 2.0 * np.diff(grid))
    cdf = np.concatenate([[0.0], cdf])
    cdf /= cdf[-1]
    ci_low = float(np.interp(0.025, cdf, grid))
    ci_high = float(np.interp(0.975, cdf, grid))

    return {
        "bayesian_model": "student_t",
        "prior_mu": prior_mu,
        "prior_sd": prior_sd,
        "likelihood_df": df,
        "data_mu": round(data_mu, 4),
        "data_se": round(data_se, 4),
        "posterior_mu": round(mu_post, 4),
        "posterior_sd": round(sd_post, 4),
        "p_effect_positive": round(p_pos, 4),
        "credible_interval_95": [round(ci_low, 4), round(ci_high, 4)],
        "grid_lo": grid_lo,
        "grid_hi": grid_hi,
        "grid_n": grid_n,
        "update_skipped": False,
    }


def main() -> None:
    if "APPROVED" not in PREREG.read_text(encoding="utf-8"):
        raise SystemExit("Prereg not APPROVED — abort.")

    ledger_times = _load_ledger_times()
    if not ledger_times:
        raise SystemExit("Prospective ledger empty.")

    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=True)

    rows = []
    for e in events:
        if e.purge_time not in ledger_times:
            continue
        if e.close_disp_atr is None:
            raise SystemExit(f"Missing post window for ledger event {e.purge_time}")
        group = "EXPOSED" if e.purge_depth_atr >= DEPTH_THRESHOLD else "REFERENCE"
        rows.append(
            {
                "purge_time": e.purge_time,
                "group": group,
                "purge_depth_atr": round(e.purge_depth_atr, 4),
                "pre_2h_return_atr": round(e.pre_2h_return_atr, 4),
                "close_disp_atr": round(e.close_disp_atr, 4),
            }
        )

    if len(rows) != len(ledger_times):
        raise SystemExit(f"Ledger has {len(ledger_times)} events, matched {len(rows)}")

    ev = pd.DataFrame(rows)
    exposed = ev[ev["group"] == "EXPOSED"]["close_disp_atr"].to_numpy()
    reference = ev[ev["group"] == "REFERENCE"]["close_disp_atr"].to_numpy()

    boot = bootstrap_median_diff(exposed, reference)
    mean_diff, mean_se = pooled_mean_se(exposed, reference)
    bayes_normal = bayesian_update(PRIOR_MU, PRIOR_SD, mean_diff, mean_se)
    bayes_student_t = bayesian_update_student_t(PRIOR_MU, PRIOR_SD, mean_diff, mean_se)

    n_exp = int(len(exposed))
    n_ref = int(len(reference))
    tier_status, rules = evaluate_rules(n_exp, boot, bayes_normal)

    n_lines = 0
    if UPDATE_LOG.exists():
        n_lines = sum(1 for ln in UPDATE_LOG.read_text(encoding="utf-8").splitlines() if ln.strip())
    update_id = f"prospective_update_{n_lines:03d}"

    snapshot = {
        "update_id": update_id,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "hypothesis_id": "H-SECONDLOW-004",
        "hypothesis_version": "0.2",
        "protocol_appendix": "v1.2-exploratory",
        "starting_prior": "A",
        "n_prospective_events": len(rows),
        "n_prospective_exposed": n_exp,
        "n_prospective_reference": n_ref,
        "batch_n_exposed": n_exp,
        "batch_n_reference": n_ref,
        "batch_mean_diff": round(mean_diff, 4),
        "batch_se": round(mean_se, 4),
        "frequentist": {
            "median_diff": round(boot["observed"], 4),
            "median_exposed": round(float(np.median(exposed)), 4) if n_exp else None,
            "median_reference": round(float(np.median(reference)), 4) if n_ref else None,
            "bootstrap_ci_95": [boot["ci_low"], boot["ci_high"]],
            "n_boot": boot["n_boot"],
            "seed": boot["seed"],
        },
        "bayesian_normal_v11": {
            **bayes_normal,
            "bayesian_model": "normal_conjugate",
            "governance_primary": True,
        },
        "bayesian": bayes_student_t,
        "tier_status": tier_status,
        "tier_label": "Tier 1" if n_exp < 8 else ("Tier 2" if n_exp < 15 else "Tier 3"),
        "tier_governance_track": "normal_conjugate_v11",
        "rules_triggered": rules,
        "corpus_hash_prefix": sha256_prefix(corpus),
        "note": "Student-t track is decision-support only; tier gates use bayesian_normal_v11 per protocol v1.1.",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / f"{update_id}_student_t.json"
    report_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with UPDATE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, separators=(",", ": ")) + "\n")

    print(json.dumps(snapshot, indent=2))
    print(f"\nWrote {report_path}")
    print(f"Appended {UPDATE_LOG}")


if __name__ == "__main__":
    main()