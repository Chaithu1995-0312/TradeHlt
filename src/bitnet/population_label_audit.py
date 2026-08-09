"""
population_label_audit.py
=========================
Governed population + label balance audit (read-only; does NOT modify CONTRACT-C).

Quantifies counts and class balance after each preprocessing stage used by the
CONTRACT-C trainer path (ATR-race bullish DIAGNOSTIC_ONLY by default), across
one or more OHLCV CSV datasets.

Stages (aligned with ``build_dataset_from_csv``):
  S0  raw_bars
  S1  after_feature_pipeline
  S2  eligible_index_window   (warmup .. n-max_fwd)
  S3  atr_positive
  S4  bar_filter_retest       (retest_depth > threshold)
  S5  labeled_resolved        (win/loss; timeouts excluded)
  S6  time_ordered_split      (train / holdout of S5)

Authority: research/docs only. No enable, no CONTRACT-C change.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from bitnet.label_contracts import get_label_contract

log = logging.getLogger("bitnet.population_label_audit")

AUDIT_PROTOCOL_ID = "BITNET_POPULATION_LABEL_AUDIT_V1"
DEFAULT_LABEL_CONTRACT_ID = "BITNET_LABEL_ATR_RACE_BULL_V1"
DEFAULT_BAR_FILTER = 0.05
DEFAULT_WARMUP = 60
DEFAULT_HOLDOUT = 0.25


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _balance_block(n: int, n_pos: int = 0, n_neg: int = 0, **extra: Any) -> Dict[str, Any]:
    """Class-balance summary. Labels only meaningful once n_pos+n_neg known."""
    labeled = n_pos + n_neg
    out: Dict[str, Any] = {
        "n": int(n),
        "n_pos": int(n_pos),
        "n_neg": int(n_neg),
        "n_labeled": int(labeled),
    }
    if labeled > 0:
        out["pos_rate"] = float(n_pos / labeled)
        out["neg_rate"] = float(n_neg / labeled)
        out["imbalance_ratio_pos_neg"] = (
            float(n_pos / n_neg) if n_neg > 0 else float("inf")
        )
        # majority baseline accuracy if always predict mode
        out["majority_class"] = "pos" if n_pos >= n_neg else "neg"
        out["majority_rate"] = float(max(n_pos, n_neg) / labeled)
    else:
        out["pos_rate"] = None
        out["neg_rate"] = None
        out["imbalance_ratio_pos_neg"] = None
        out["majority_class"] = None
        out["majority_rate"] = None
    out.update(extra)
    return out


def _label_one(
    i: int,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    atr: float,
    tp_m: float,
    sl_m: float,
    max_fwd: int,
) -> Optional[float]:
    """Return 1.0 win, 0.0 loss, or None timeout — same geometry as trainer."""
    close = float(closes[i])
    tp = close + atr * tp_m
    sl = close - atr * sl_m
    n = len(closes)
    for j in range(i + 1, min(i + max_fwd + 1, n)):
        if highs[j] >= tp:
            return 1.0
        if lows[j] <= sl:
            return 0.0
    return None


@dataclass
class AuditConfig:
    label_contract_id: str = DEFAULT_LABEL_CONTRACT_ID
    warmup: int = DEFAULT_WARMUP
    bar_filter_min_retest_depth: float = DEFAULT_BAR_FILTER
    holdout_fraction: float = DEFAULT_HOLDOUT
    # Optional: also report mirror short ATR race (diagnostic only; not CONTRACT-C)
    include_bearish_mirror_diagnostic: bool = True


def audit_csv(csv_path: str | Path, cfg: Optional[AuditConfig] = None) -> Dict[str, Any]:
    """
    Full stage funnel + balance for one CSV under the declared label contract.
    Does not write files; pure analysis.
    """
    import pandas as pd
    from features.feature_pipeline import FeaturePipeline

    cfg = cfg or AuditConfig()
    label = get_label_contract(cfg.label_contract_id)
    tp_m = float(label["tp_atr_mult"])
    sl_m = float(label["sl_atr_mult"])
    max_fwd = int(label["max_fwd"])

    path = Path(csv_path)
    if not path.exists():
        return {
            "path": str(path),
            "error": "file_not_found",
            "stages": {},
        }

    file_hash = _sha256_file(path)
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df = df.sort_values("timestamp")
    n_raw = len(df)
    t0 = str(df["timestamp"].iloc[0]) if n_raw else None
    t1 = str(df["timestamp"].iloc[-1]) if n_raw else None

    stages: Dict[str, Any] = {}
    stages["S0_raw_bars"] = _balance_block(
        n_raw,
        note="OHLCV rows; no labels yet",
        timestamp_min=t0,
        timestamp_max=t1,
    )

    if n_raw < cfg.warmup + max_fwd + 20:
        return {
            "path": str(path),
            "csv_sha256": file_hash,
            "error": "too_short",
            "label_contract_id": cfg.label_contract_id,
            "stages": stages,
        }

    try:
        pipe = FeaturePipeline(df)
        feat_df, _ = pipe.run()
    except Exception as exc:
        return {
            "path": str(path),
            "csv_sha256": file_hash,
            "error": f"feature_pipeline_failed: {exc}",
            "label_contract_id": cfg.label_contract_id,
            "stages": stages,
        }

    n_pipe = len(feat_df)
    stages["S1_after_feature_pipeline"] = _balance_block(
        n_pipe,
        note="After FeaturePipeline.finalize; still unlabeled",
        drop_from_raw=int(n_raw - n_pipe),
        drop_pct_from_raw=float((n_raw - n_pipe) / max(n_raw, 1)),
    )

    highs = feat_df["high"].to_numpy(dtype=np.float64)
    lows = feat_df["low"].to_numpy(dtype=np.float64)
    closes = feat_df["close"].to_numpy(dtype=np.float64)
    n = n_pipe

    # Index window
    i0, i1 = cfg.warmup, n - max_fwd
    n_window = max(0, i1 - i0)
    stages["S2_eligible_index_window"] = _balance_block(
        n_window,
        note=f"indices [{cfg.warmup}, {n - max_fwd}); unlabeled",
        warmup=cfg.warmup,
        max_fwd=max_fwd,
    )

    # Walk funnel with counters
    n_atr = 0
    n_retest = 0
    n_win = 0
    n_loss = 0
    n_timeout = 0
    n_atr_fail = 0
    n_retest_fail = 0

    # Diagnostic bearish mirror (not CONTRACT-C)
    n_win_bear = 0
    n_loss_bear = 0
    n_timeout_bear = 0

    retest_vals: List[float] = []

    for i in range(i0, i1):
        row = feat_df.iloc[i]
        atr = float(row.get("atr", 0.0) or 0.0)
        if atr <= 0:
            n_atr_fail += 1
            continue
        n_atr += 1
        retest = float(row.get("retest_depth", 0.0) or 0.0)
        retest_vals.append(retest)
        if retest <= cfg.bar_filter_min_retest_depth:
            n_retest_fail += 1
            continue
        n_retest += 1

        lab = _label_one(i, highs, lows, closes, atr, tp_m, sl_m, max_fwd)
        if lab is None:
            n_timeout += 1
        elif lab >= 0.5:
            n_win += 1
        else:
            n_loss += 1

        if cfg.include_bearish_mirror_diagnostic:
            # Mirror: SL above, TP below (bearish race)
            close = float(closes[i])
            tp_b = close - atr * tp_m
            sl_b = close + atr * sl_m
            lab_b = None
            for j in range(i + 1, min(i + max_fwd + 1, n)):
                if lows[j] <= tp_b:
                    lab_b = 1.0
                    break
                if highs[j] >= sl_b:
                    lab_b = 0.0
                    break
            if lab_b is None:
                n_timeout_bear += 1
            elif lab_b >= 0.5:
                n_win_bear += 1
            else:
                n_loss_bear += 1

    stages["S3_atr_positive"] = _balance_block(
        n_atr,
        note="Among S2: atr > 0",
        rejected_atr_le_0=n_atr_fail,
        retention_of_S2=float(n_atr / max(n_window, 1)),
    )

    stages["S4_bar_filter_retest"] = _balance_block(
        n_retest,
        note=(
            f"Among S3: retest_depth > {cfg.bar_filter_min_retest_depth} "
            f"(bar_filter_id retest_depth_gt threshold)"
        ),
        rejected_retest=n_retest_fail,
        retention_of_S3=float(n_retest / max(n_atr, 1)),
        retest_depth_mean=float(np.mean(retest_vals)) if retest_vals else None,
        retest_depth_p50=float(np.median(retest_vals)) if retest_vals else None,
        retest_depth_gt_filter_rate=float(n_retest / max(n_atr, 1)),
    )

    n_labeled = n_win + n_loss
    stages["S5_labeled_resolved"] = _balance_block(
        n_labeled,
        n_pos=n_win,
        n_neg=n_loss,
        note=(
            f"CONTRACT-C {cfg.label_contract_id}: timeouts dropped "
            f"(timeout_policy={label.get('timeout_policy')})"
        ),
        n_timeout_dropped=n_timeout,
        timeout_rate_of_S4=float(n_timeout / max(n_retest, 1)),
        retention_of_S4_after_timeout_drop=float(n_labeled / max(n_retest, 1)),
        label_contract=label,
    )

    # S6 split of labeled sequence in time order of discovery (index order)
    # Rebuild labels in order for split
    labels_in_order: List[float] = []
    for i in range(i0, i1):
        row = feat_df.iloc[i]
        atr = float(row.get("atr", 0.0) or 0.0)
        if atr <= 0:
            continue
        retest = float(row.get("retest_depth", 0.0) or 0.0)
        if retest <= cfg.bar_filter_min_retest_depth:
            continue
        lab = _label_one(i, highs, lows, closes, atr, tp_m, sl_m, max_fwd)
        if lab is None:
            continue
        labels_in_order.append(lab)

    y = np.asarray(labels_in_order, dtype=np.float64)
    n_lab = len(y)
    n_hold = max(1, int(n_lab * cfg.holdout_fraction)) if n_lab > 5 else 0
    n_train = n_lab - n_hold
    y_tr = y[:n_train] if n_train else y[:0]
    y_ho = y[n_train:] if n_hold else y[:0]

    def _split_bal(yy: np.ndarray, name: str) -> Dict[str, Any]:
        if len(yy) == 0:
            return _balance_block(0, note=name)
        n_p = int((yy >= 0.5).sum())
        n_n = int(len(yy) - n_p)
        return _balance_block(len(yy), n_pos=n_p, n_neg=n_n, note=name)

    stages["S6_time_ordered_split"] = {
        "holdout_fraction": cfg.holdout_fraction,
        "train": _split_bal(y_tr, "train prefix"),
        "holdout": _split_bal(y_ho, "holdout suffix"),
        "note": "Same split policy as CONTRACT-C trainer (time-ordered prefix train)",
    }

    funnel = {
        "S0_raw": n_raw,
        "S1_pipeline": n_pipe,
        "S2_window": n_window,
        "S3_atr": n_atr,
        "S4_retest": n_retest,
        "S5_labeled": n_labeled,
        "S5_timeouts": n_timeout,
        "frac_S5_of_S0": float(n_labeled / max(n_raw, 1)),
        "frac_S5_of_S4": float(n_labeled / max(n_retest, 1)),
    }

    diagnostic: Dict[str, Any] = {}
    if cfg.include_bearish_mirror_diagnostic:
        diagnostic["bearish_mirror_ATR_race"] = _balance_block(
            n_win_bear + n_loss_bear,
            n_pos=n_win_bear,
            n_neg=n_loss_bear,
            n_timeout=n_timeout_bear,
            note=(
                "NOT CONTRACT-C. Mirror short geometry for balance comparison only."
            ),
        )

    # Severity flags (descriptive, not CONTRACT-C changes)
    flags: List[str] = []
    if n_labeled > 0:
        pos_rate = n_win / n_labeled
        if pos_rate >= 0.95 or pos_rate <= 0.05:
            flags.append("EXTREME_IMBALANCE_ge_95pct_majority")
        elif pos_rate >= 0.85 or pos_rate <= 0.15:
            flags.append("SEVERE_IMBALANCE_ge_85pct_majority")
        elif pos_rate >= 0.70 or pos_rate <= 0.30:
            flags.append("MODERATE_IMBALANCE_ge_70pct_majority")
        else:
            flags.append("BALANCED_WITHIN_70_30")
    if n_labeled < 100:
        flags.append("LOW_LABELED_N_lt_100")
    if n_timeout / max(n_retest, 1) > 0.5:
        flags.append("HIGH_TIMEOUT_RATE_gt_50pct_of_S4")

    return {
        "path": str(path),
        "csv_sha256": file_hash,
        "label_contract_id": cfg.label_contract_id,
        "economic_authority": label.get("economic_authority"),
        "bar_filter_min_retest_depth": cfg.bar_filter_min_retest_depth,
        "warmup": cfg.warmup,
        "timestamp_min": t0,
        "timestamp_max": t1,
        "stages": stages,
        "funnel": funnel,
        "diagnostic_non_contract": diagnostic,
        "flags": flags,
        "error": None,
    }


def audit_many(
    csv_paths: Sequence[str | Path],
    cfg: Optional[AuditConfig] = None,
) -> Dict[str, Any]:
    """Audit multiple datasets; return combined report."""
    cfg = cfg or AuditConfig()
    per_file: List[Dict[str, Any]] = []
    for p in csv_paths:
        log.info("Auditing %s", p)
        per_file.append(audit_csv(p, cfg))

    # Cross-dataset summary on S5
    rows = []
    for r in per_file:
        if r.get("error"):
            rows.append({
                "path": r["path"],
                "error": r["error"],
            })
            continue
        s5 = r["stages"].get("S5_labeled_resolved", {})
        rows.append({
            "path": r["path"],
            "timestamp_min": r.get("timestamp_min"),
            "timestamp_max": r.get("timestamp_max"),
            "n_raw": r["stages"]["S0_raw_bars"]["n"],
            "n_S4": r["stages"]["S4_bar_filter_retest"]["n"],
            "n_S5": s5.get("n_labeled"),
            "n_pos": s5.get("n_pos"),
            "n_neg": s5.get("n_neg"),
            "pos_rate": s5.get("pos_rate"),
            "majority_rate": s5.get("majority_rate"),
            "timeouts": s5.get("n_timeout_dropped"),
            "flags": r.get("flags"),
            "frac_S5_of_S0": r["funnel"].get("frac_S5_of_S0"),
        })

    # Aggregate if any success
    ok = [r for r in per_file if not r.get("error")]
    agg = None
    if ok:
        tot_pos = sum(r["stages"]["S5_labeled_resolved"]["n_pos"] for r in ok)
        tot_neg = sum(r["stages"]["S5_labeled_resolved"]["n_neg"] for r in ok)
        tot = tot_pos + tot_neg
        agg = _balance_block(
            tot,
            n_pos=tot_pos,
            n_neg=tot_neg,
            note="Pooled S5 across successfully audited files",
            n_files=len(ok),
        )

    return {
        "protocol_id": AUDIT_PROTOCOL_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label_contract_id": cfg.label_contract_id,
        "authority": (
            "READ-ONLY audit. Does not modify CONTRACT-C, does not train, "
            "does not enable use_bitnet. Evidence for population/label redesign only."
        ),
        "config": {
            "warmup": cfg.warmup,
            "bar_filter_min_retest_depth": cfg.bar_filter_min_retest_depth,
            "holdout_fraction": cfg.holdout_fraction,
            "include_bearish_mirror_diagnostic": cfg.include_bearish_mirror_diagnostic,
        },
        "files": per_file,
        "cross_dataset_S5_summary": rows,
        "pooled_S5": agg,
        "recommendation_hint": (
            "If flags contain EXTREME_IMBALANCE or SEVERE_IMBALANCE on multiple "
            "files, do not run R3; redesign population/label under a NEW "
            "label_contract_id (do not silently edit ATR_RACE_BULL_V1 without versioning)."
        ),
    }


def write_audit_report(report: Mapping[str, Any], out_path: str | Path) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Human-readable companion
    md_path = path.with_suffix(".md")
    lines = [
        f"# Population / Label Audit",
        f"",
        f"- protocol: `{report.get('protocol_id')}`",
        f"- label_contract: `{report.get('label_contract_id')}`",
        f"- created: {report.get('created_at')}",
        f"",
        f"## Cross-dataset S5 (final labeled set)",
        f"",
        f"| path | n_S5 | pos | neg | pos_rate | majority_rate | flags |",
        f"|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report.get("cross_dataset_S5_summary") or []:
        if row.get("error"):
            lines.append(
                f"| `{row['path']}` | ERR | | | | | {row.get('error')} |"
            )
            continue
        flags = ",".join(row.get("flags") or [])
        lines.append(
            f"| `{Path(row['path']).name}` | {row.get('n_S5')} | {row.get('n_pos')} | "
            f"{row.get('n_neg')} | {row.get('pos_rate')} | {row.get('majority_rate')} | {flags} |"
        )
    pooled = report.get("pooled_S5") or {}
    lines.extend([
        f"",
        f"## Pooled S5",
        f"",
        f"- n_labeled: {pooled.get('n_labeled')}",
        f"- pos_rate: {pooled.get('pos_rate')}",
        f"- majority_rate: {pooled.get('majority_rate')}",
        f"",
        f"## Recommendation hint",
        f"",
        f"{report.get('recommendation_hint')}",
        f"",
        f"**CONTRACT-C not modified.**",
        f"",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Wrote %s and %s", path, md_path)
    return path
