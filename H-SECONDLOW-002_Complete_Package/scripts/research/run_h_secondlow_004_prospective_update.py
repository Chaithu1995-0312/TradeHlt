#!/usr/bin/env python3
"""H-SECONDLOW-004 v0.2 — prospective dual-track update (protocol v1.1)."""

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

from research.secondlow_v1.corpus import CANONICAL_CORPUS_SHA256_PREFIX, CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import detect_independent_events, load_ohlcv, sha256_prefix

DEPTH_THRESHOLD = 1.0
N_BOOT = 5000
SEED = 42
PRIOR_MU = 0.0
PRIOR_SD = 2.0

PREREG = _REPO / "H-SECONDLOW-002_Complete_Package/preregistration-H-SECONDLOW-004-v0.2.md"
LEDGER = _REPO / "data/secondlow_prospective_events.jsonl"
UPDATE_LOG = _REPO / "data/secondlow_prospective_update_log.jsonl"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/h_secondlow_004_v02"


def _load_ledger_times() -> set[pd.Timestamp]:
    times: set[pd.Timestamp] = set()
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            times.add(pd.Timestamp(json.loads(line)["purge_time"]))
    return times


def bootstrap_median_diff(exposed: np.ndarray, reference: np.ndarray) -> dict:
    rng = np.random.default_rng(SEED)
    obs = float(np.median(exposed) - np.median(reference)) if len(exposed) and len(reference) else float("nan")
    if len(exposed) == 0 or len(reference) == 0:
        return {"observed": obs, "ci_low": None, "ci_high": None, "n_boot": 0}
    stats_arr = np.empty(N_BOOT)
    for i in range(N_BOOT):
        e = rng.choice(exposed, size=len(exposed), replace=True)
        r = rng.choice(reference, size=len(reference), replace=True)
        stats_arr[i] = np.median(e) - np.median(r)
    return {
        "observed": obs,
        "ci_low": float(np.percentile(stats_arr, 2.5)),
        "ci_high": float(np.percentile(stats_arr, 97.5)),
        "n_boot": N_BOOT,
        "seed": SEED,
    }


def pooled_mean_se(exposed: np.ndarray, reference: np.ndarray) -> tuple[float, float]:
    if len(exposed) == 0 or len(reference) == 0:
        return float("nan"), float("nan")
    mu = float(np.mean(exposed) - np.mean(reference))
    se = math.sqrt(float(np.var(exposed, ddof=1)) / len(exposed) + float(np.var(reference, ddof=1)) / len(reference))
    return mu, se


def bayesian_update(prior_mu: float, prior_sd: float, data_mu: float, data_se: float) -> dict:
    v0, vd = prior_sd**2, data_se**2
    prec = 1 / v0 + 1 / vd
    post_var = 1 / prec
    post_mu = (prior_mu / v0 + data_mu / vd) * post_var
    post_sd = math.sqrt(post_var)
    p_pos = float(1 - stats.norm.cdf(0, post_mu, post_sd))
    ci_low = post_mu - 1.96 * post_sd
    ci_high = post_mu + 1.96 * post_sd
    return {
        "prior_mu": prior_mu,
        "prior_sd": prior_sd,
        "posterior_mu": round(post_mu, 4),
        "posterior_sd": round(post_sd, 4),
        "p_effect_positive": round(p_pos, 4),
        "credible_interval_95": [round(ci_low, 4), round(ci_high, 4)],
    }


def evaluate_rules(n_exp: int, boot: dict, bayes: dict) -> tuple[str, list[str]]:
    triggered: list[str] = []
    ci_lo, ci_hi = boot.get("ci_low"), boot.get("ci_high")
    p_pos = bayes["p_effect_positive"]
    mu_post = bayes["posterior_mu"]

    f_stop = n_exp >= 12 and ci_hi is not None and ci_hi < 0
    b_stop = n_exp >= 12 and p_pos < 0.10 and mu_post < -0.5
    if f_stop:
        triggered.append("F-STOP")
    if b_stop:
        triggered.append("B-STOP")
    if f_stop or b_stop:
        return "ARCHIVE_REVIEW", triggered

    f_t3 = n_exp >= 15 and ci_lo is not None and ci_lo > 0.3
    b_t3 = (
        n_exp >= 15
        and p_pos > 0.70
        and bayes["posterior_sd"] < 0.8
        and bayes["credible_interval_95"][0] > 0
    )
    if f_t3 and b_t3:
        triggered.extend(["F-TIER3", "B-TIER3"])
        return "SHADOW_CANDIDATE", triggered

    f_t2 = n_exp >= 8 and ci_lo is not None and ci_lo > 0
    b_t2 = n_exp >= 8 and p_pos > 0.60 and bayes["posterior_sd"] < 1.0
    if f_t2 and b_t2:
        triggered.extend(["F-TIER2", "B-TIER2"])
        return "TIER2_CONTINUE", triggered

    if n_exp >= 8 and ci_lo is not None and ci_hi is not None and ci_lo < 0 < ci_hi:
        triggered.append("F-WATCH")
    if 0.10 <= p_pos <= 0.60:
        triggered.append("B-WATCH")

    return "WATCH", triggered


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
    bayes = bayesian_update(PRIOR_MU, PRIOR_SD, mean_diff, mean_se)

    n_exp = int(len(exposed))
    n_ref = int(len(reference))
    tier_status, rules = evaluate_rules(n_exp, boot, bayes)

    n_lines = 0
    if UPDATE_LOG.exists():
        n_lines = sum(1 for ln in UPDATE_LOG.read_text(encoding="utf-8").splitlines() if ln.strip())
    update_id = f"prospective_update_{n_lines:03d}"

    snapshot = {
        "update_id": update_id,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "hypothesis_id": "H-SECONDLOW-004",
        "hypothesis_version": "0.2",
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
        "bayesian": bayes,
        "tier_status": tier_status,
        "tier_label": "Tier 1" if n_exp < 8 else ("Tier 2" if n_exp < 15 else "Tier 3"),
        "rules_triggered": rules,
        "corpus_hash_prefix": sha256_prefix(corpus),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT / "prospective_update_001.json"
    report_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    ev.to_csv(OUTPUT / "prospective_event_table.csv", index=False)

    UPDATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with UPDATE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, separators=(",", ": ")) + "\n")

    print(json.dumps(snapshot, indent=2))
    print(f"\nWrote {report_path}")
    print(f"Appended {UPDATE_LOG}")


if __name__ == "__main__":
    main()