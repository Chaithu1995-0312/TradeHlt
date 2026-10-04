"""
bitnet/forward_tester.py
=========================
Forward (out-of-sample) validation for zone registry.

Compares zone performance on training vs. test data to detect overfitting.

Design
------
  - Train/test split is temporal: first train_split% for discovery,
    remaining for validation. Never random shuffle (preserves time order).
  - A zone is flagged as "degraded" if test_avg_rr < train_avg_rr × DEGRADATION_THRESHOLD
  - Zones with insufficient test-set trades are flagged "insufficient_data"
    (not rejected — may pass once more data accumulates)

Usage
-----
    from bitnet.forward_tester import ForwardTester, run_forward_test

    # Full forward test
    tester  = ForwardTester(train_split=0.70)
    results = tester.validate(zones, X, y_rr, y_win)

    # One-shot convenience
    results = run_forward_test(zones, X, y_rr, y_win, output_path="models/fwd_test.json")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Tuple

log = logging.getLogger("ForwardTester")


class ForwardTester:
    """
    Out-of-sample validator for BitNet zone candidates.

    Parameters
    ----------
    train_split          : fraction of data used for discovery (default 0.70)
    degradation_threshold: test_rr must be >= this fraction of train_rr (default 0.60)
    min_test_trades      : minimum trades in test split for reliable estimate (default 20)
    """

    DEGRADATION_THRESHOLD = 0.60
    MIN_TEST_TRADES       = 20

    def __init__(self, train_split: float = 0.70):
        if not 0.5 <= train_split <= 0.90:
            raise ValueError(f"train_split must be in [0.5, 0.9], got {train_split}")
        self.train_split = train_split

    # ── Data splitting ────────────────────────────────────────────────────

    def split(
        self,
        X:    List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> Tuple[tuple, tuple]:
        """
        Temporal train/test split (no shuffle — preserves time order).

        Returns
        -------
        (X_train, rr_train, win_train), (X_test, rr_test, win_test)
        """
        n         = len(X)
        split_idx = int(n * self.train_split)

        train = (X[:split_idx],  y_rr[:split_idx],  y_win[:split_idx])
        test  = (X[split_idx:],  y_rr[split_idx:],  y_win[split_idx:])

        log.info(
            f"Forward split: n={n} | train={split_idx} ({self.train_split:.0%}) "
            f"| test={n - split_idx} ({1 - self.train_split:.0%})"
        )
        return train, test

    # ── Validation ────────────────────────────────────────────────────────

    def validate(
        self,
        zones,
        X:    List[List[float]],
        y_rr: List[float],
        y_win: List[int],
    ) -> List[dict]:
        """
        Validate each zone on held-out test data and compare to train performance.

        Parameters
        ----------
        zones  : list of ZoneResult objects from BitNetSearchEngine.run_search()
        X      : full feature matrix (time-ordered)
        y_rr   : full RR targets
        y_win  : full win labels

        Returns
        -------
        List[dict] — one entry per zone with keys:
            zone_id, status, train, test, rr_retention
        """
        from bitnet.zone_cosine_searcher import _evaluate_subset

        (X_tr, rr_tr, win_tr), (X_te, rr_te, win_te) = self.split(X, y_rr, y_win)

        results     = []
        n_passed    = 0
        n_degraded  = 0
        n_insuff    = 0

        for i, zone in enumerate(zones):
            cand = zone.candidate

            train_m = _evaluate_subset(X_tr, rr_tr, win_tr, cand)
            test_m  = _evaluate_subset(X_te, rr_te, win_te, cand)

            # ── Status determination ────────────────────────────────────
            if test_m["trade_count"] < self.MIN_TEST_TRADES:
                status = "insufficient_test_data"
                n_insuff += 1
            elif train_m["avg_rr"] <= 0:
                status = "train_not_profitable"
            elif test_m["avg_rr"] < train_m["avg_rr"] * self.DEGRADATION_THRESHOLD:
                status = "degraded"
                n_degraded += 1
            else:
                status = "passed"
                n_passed += 1

            rr_retention = (
                test_m["avg_rr"] / train_m["avg_rr"]
                if train_m["avg_rr"] > 0 else 0.0
            )

            entry = {
                "zone_id":      f"zone_{i + 1:03d}",
                "status":       status,
                "train":        train_m,
                "test":         test_m,
                "rr_retention": round(rr_retention, 4),
            }
            results.append(entry)

            log.info(
                f"  Zone {i + 1:03d}: {status:<26} | "
                f"train_rr={train_m['avg_rr']:+.3f} "
                f"test_rr={test_m['avg_rr']:+.3f} "
                f"retention={rr_retention:.2f}"
            )

        print(
            f"\n  Forward test: {n_passed} passed | "
            f"{n_degraded} degraded | {n_insuff} insufficient data"
        )
        return results

    # ── Filtering convenience ─────────────────────────────────────────────

    @staticmethod
    def filter_passed(
        zones,
        fwd_results: List[dict],
    ) -> List:
        """
        Return only zones whose forward test status is 'passed'.

        Parameters
        ----------
        zones       : original list of ZoneResult objects
        fwd_results : output of ForwardTester.validate()

        Returns
        -------
        Filtered list of ZoneResult objects (same type, same order).
        """
        passed_ids = {r["zone_id"] for r in fwd_results if r["status"] == "passed"}
        return [
            z for i, z in enumerate(zones)
            if f"zone_{i + 1:03d}" in passed_ids
        ]


# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def run_forward_test(
    zones,
    X:            List[List[float]],
    y_rr:         List[float],
    y_win:        List[int],
    train_split:  float = 0.70,
    output_path:  str   = "models/forward_test_results.json",
) -> List[dict]:
    """
    One-shot forward test + save results to JSON.

    Parameters
    ----------
    zones        : ZoneResult list from BitNetSearchEngine.run_search()
    X            : full feature matrix
    y_rr         : full RR targets
    y_win        : full win labels
    train_split  : train fraction (default 0.70)
    output_path  : where to save JSON results

    Returns
    -------
    List of per-zone forward test result dicts.
    """
    tester  = ForwardTester(train_split=train_split)
    results = tester.validate(zones, X, y_rr, y_win)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    log.info(f"Forward test results saved → {output_path}")
    return results