"""SpineProjector — the accepted-trade ledger → SPINE_TRADE episodes.

OFFLINE ONLY. This reads `{INSTRUMENT}_trades.csv` after the fact; nothing in
`TradeJournal` or the backtest hot loop ever writes an episode (substrate §15).

TWO LEDGER FACTS THIS PROJECTOR HAD TO BE BUILT AROUND
------------------------------------------------------
1. **The per-trade path oracle is not persisted.** `TradePathStats` (`mfe_price`,
   `mae_price`, `bars_to_peak`, `bars_to_trough`) is computed in the hot loop and
   attached to `TradeRecord.path`, but `TradeJournal.to_csv_rows()` never emits it —
   it survives only as AGGREGATE percentiles in `{INSTRUMENT}_summary.json` under
   `distribution.metrics_v2.survival`. So a per-trade MFE/MAE parity check is not
   executable against existing artifacts. `probe_ledger()` reports this rather than
   letting a caller assume the field exists; `aggregate_path_parity()` does the
   strongest check the data actually supports.

2. **`candle_idx` is offset +1 from `opened_at`.** Measured uniformly across all 11
   trades of the reference run. The join is therefore keyed on the TIMESTAMP, which
   is unambiguous and loader-independent; `candle_idx` is carried as advisory
   metadata with its observed offset, so a future drift is visible rather than silent.

LABEL PARITY WITH THE SPINE IS NOT EXPECTED — AND THAT IS NOT A DEFECT
----------------------------------------------------------------------
The spine exits on a MULTI-LEVEL, STOP-MOVING model: TP1/TP2 with
`partial_tp_fraction` (F-056), plus a stop that ratchets — reference trade CRT-0002
closes `STOPPED` at **+0.70R**. OE_L1's policy set is single-TP by construction (the
B2 non-goal: expressing multi-level exits would require a second exit kernel, which
substrate §18 rates CRITICAL). So a `LabelSet` over a SPINE_TRADE episode answers
"what would this geometry have done under a single-TP policy", NOT "what the spine
did". The ledger's own outcome is preserved verbatim under `metadata.ledger`.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable, Sequence

from research.episodes.builder import _norm_ts, build_episode
from research.episodes.protocol import MAX_FORWARD
from research.episodes.schema import EntrySnapshot, OpportunityEpisode

POPULATION = "SPINE_TRADE"

# Ledger columns the projector needs to build an episode.
REQUIRED_COLUMNS = ("trade_id", "direction", "entry_raw", "sl", "opened_at")
# Present and preserved, but not canonical episode fields.
LEDGER_DIAGNOSTIC_COLUMNS = ("tp1", "tp2", "exit_fill", "exit_reason", "duration_candles",
                             "pnl_rr_raw", "pnl_rr_net", "candle_idx", "closed_at",
                             "config_version", "session", "risk_score")
# The per-trade path oracle the plan's blocking floor wanted. Absent by construction.
PATH_ORACLE_COLUMNS = ("mfe_price", "mae_price", "bars_to_peak", "bars_to_trough")


def _f(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def read_ledger(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def probe_ledger(rows: Sequence[dict[str, str]]) -> dict[str, Any]:
    """Report what the ledger can and cannot support. Never synthesizes a field.

    Run this BEFORE building a corpus: it is the difference between "the parity
    floor passed" and "the parity floor was silently skipped".
    """
    cols = set(rows[0]) if rows else set()
    missing_required = [c for c in REQUIRED_COLUMNS if c not in cols]
    path_oracle = [c for c in PATH_ORACLE_COLUMNS if c in cols]

    return {
        "n_rows": len(rows),
        "n_columns": len(cols),
        "required_present": not missing_required,
        "missing_required": missing_required,
        "path_oracle_present": bool(path_oracle),
        "path_oracle_columns_found": path_oracle,
        "per_trade_path_parity_executable": bool(path_oracle),
        "diagnostics_present": sorted(c for c in LEDGER_DIAGNOSTIC_COLUMNS if c in cols),
        "note": (
            "TradePathStats is computed in the hot loop but not emitted by "
            "TradeJournal.to_csv_rows(); it survives only as aggregate percentiles in "
            "{INSTRUMENT}_summary.json -> distribution.metrics_v2.survival. Per-trade "
            "MFE/MAE parity is therefore NOT executable against this artifact."
        ) if not path_oracle else "per-trade path oracle available",
    }


def project_trade(
    row: dict[str, str],
    candles: Sequence,
    ts_to_idx: dict[str, int],
    *,
    instrument: str,
    max_forward: int = MAX_FORWARD,
    protocol_hash: str | None = None,
    cache_derived: bool = True,
    **build_kwargs: Any,
) -> tuple[OpportunityEpisode | None, str | None]:
    """Project one ledger row. Returns (episode, skip_reason)."""
    missing = [c for c in REQUIRED_COLUMNS if not row.get(c)]
    if missing:
        return None, f"missing_columns:{'|'.join(missing)}"

    direction = str(row["direction"]).strip().lower()
    if direction not in ("long", "short"):
        return None, "bad_direction"

    entry_price, sl = _f(row["entry_raw"]), _f(row["sl"])
    if entry_price is None or sl is None or abs(entry_price - sl) <= 0:
        return None, "bad_geometry"

    ts = _norm_ts(row["opened_at"])
    idx = ts_to_idx.get(ts)
    if idx is None:
        return None, "no_candle_ts"
    if idx + 1 >= len(candles):
        return None, "no_future_bars"

    # Single TP by contract: the spine's TP2 is preserved as a diagnostic, never
    # folded into the canonical geometry (OE_L1 is single-TP — see module docstring).
    tp1 = _f(row.get("tp1"))

    ledger: dict[str, Any] = {c: row[c] for c in LEDGER_DIAGNOSTIC_COLUMNS if c in row}
    ledger["_warning"] = (
        "Spine outcome under a MULTI-LEVEL, STOP-MOVING exit model (TP1/TP2 + "
        "partial_tp_fraction, F-056). Not comparable to an OE_L1 single-TP LabelSet."
    )
    declared_idx = _f(row.get("candle_idx"))
    if declared_idx is not None:
        # Advisory only. Measured uniformly +1 on the reference run; carried so a
        # future change of convention shows up in the corpus instead of silently.
        ledger["candle_idx_offset_vs_timestamp"] = int(declared_idx) - idx

    entry = EntrySnapshot(
        bar_index=idx,
        timestamp=ts,
        direction=direction,
        entry_price=entry_price,
        sl_price=sl,
        tp_price=tp1,
        atr_entry=_f(row.get("live_atr")),
        engine_scores=None,
        feature_vector=None,     # joined by bar_index on demand
        generator_config=None,
    )

    try:
        ep = build_episode(
            instrument=instrument,
            population=POPULATION,
            entry=entry,
            candles=candles,
            max_forward=max_forward,
            metadata={"ledger": ledger, "trade_id": row.get("trade_id", "")},
            cache_derived=cache_derived,
            protocol_hash=protocol_hash,
            **build_kwargs,
        )
    except ValueError as exc:
        return None, f"build_error:{type(exc).__name__}"
    return ep, None


def project_ledger(
    rows: Iterable[dict[str, str]],
    candles: Sequence,
    ts_to_idx: dict[str, int],
    *,
    instrument: str,
    max_forward: int = MAX_FORWARD,
    protocol_hash: str | None = None,
    cache_derived: bool = True,
    **build_kwargs: Any,
) -> tuple[list[OpportunityEpisode], dict[str, int]]:
    episodes: list[OpportunityEpisode] = []
    skips: dict[str, int] = {}
    for row in rows:
        ep, reason = project_trade(
            row, candles, ts_to_idx, instrument=instrument, max_forward=max_forward,
            protocol_hash=protocol_hash, cache_derived=cache_derived, **build_kwargs,
        )
        if reason is not None:
            key = reason.split(":")[0]
            skips[key] = skips.get(key, 0) + 1
            continue
        assert ep is not None
        episodes.append(ep)
    return episodes, skips


# ─────────────────────────────────────────────────────────────────
# PARITY — the strongest check the persisted data supports
# ─────────────────────────────────────────────────────────────────
def entry_geometry_parity(episodes: Sequence[OpportunityEpisode],
                          rows: Sequence[dict[str, str]],
                          candles: Sequence) -> dict[str, Any]:
    """Every projected entry must reproduce its ledger row exactly.

    This is what validates the JOIN — that episode i really is trade i, anchored on
    the right bar. It is a precondition for any downstream path claim.
    """
    by_id = {r["trade_id"]: r for r in rows}
    mismatches: list[dict[str, Any]] = []

    for ep in episodes:
        r = by_id.get(ep.metadata.get("trade_id", ""))
        if r is None:
            mismatches.append({"episode_id": ep.episode_id, "reason": "no_ledger_row"})
            continue
        e = ep.entry
        checks = {
            "direction": e.direction == str(r["direction"]).lower(),
            "entry_price": e.entry_price == _f(r["entry_raw"]),
            "sl_price": e.sl_price == _f(r["sl"]),
            "timestamp": e.timestamp == _norm_ts(r["opened_at"]),
            # the join itself: t=0 must BE the bar the ledger names
            "anchor_bar": _norm_ts(getattr(candles[e.bar_index], "timestamp", "")) ==
                          _norm_ts(r["opened_at"]),
        }
        failed = [k for k, ok in checks.items() if not ok]
        if failed:
            mismatches.append({"trade_id": r["trade_id"], "failed": failed})

    return {"n": len(episodes), "n_mismatch": len(mismatches),
            "mismatches": mismatches[:10], "ok": not mismatches}


def aggregate_path_parity(episodes: Sequence[OpportunityEpisode],
                          rows: Sequence[dict[str, str]],
                          survival: dict[str, Any],
                          *, tol: float = 1e-6) -> dict[str, Any]:
    """Episode-derived MFE/MAE percentiles vs `metrics_v2.survival` from the summary.

    This is a WEAKER check than the per-trade floor the plan asked for, because the
    per-trade oracle is not persisted (see `probe_ledger`). It is reported as such:
    an aggregate agreement over n=11 is corroboration, not proof.

    Excursions are truncated at each trade's realized `duration_candles`, because
    `TradePathStats` stopped tracking at close while an episode keeps walking.
    """
    from research.episodes.schema import resolved_derived

    by_id = {r["trade_id"]: r for r in rows}
    mfe_rr: list[float] = []
    mae_rr: list[float] = []
    peaks: list[int] = []

    for ep in episodes:
        r = by_id.get(ep.metadata.get("trade_id", ""))
        if r is None:
            continue
        dur = int(_f(r.get("duration_candles")) or 0)
        if dur <= 0:
            continue
        derived = resolved_derived(ep)
        risk = ep.entry.risk_distance
        best_mfe, best_mae, peak_bar = 0.0, 0.0, 0
        for step, d in zip(ep.steps, derived):
            if d is None or step.obs.t > dur:
                continue
            if d.mfe_raw > best_mfe:
                best_mfe, peak_bar = d.mfe_raw, step.obs.t
            best_mae = min(best_mae, d.mae_raw)
        mfe_rr.append(best_mfe / risk)
        mae_rr.append(best_mae / risk)
        peaks.append(peak_bar)

    def _pct(xs: list[float], p: float) -> float | None:
        if not xs:
            return None
        s = sorted(xs)
        k = max(0, min(len(s) - 1, int(round((len(s) - 1) * p))))
        return s[k]

    derived_stats = {
        "mfe_rr_p50": _pct(mfe_rr, 0.50),
        "mfe_rr_p90": _pct(mfe_rr, 0.90),
        "mae_rr_p50": _pct(mae_rr, 0.50),
        "mae_rr_p90": _pct(mae_rr, 0.90),
        "median_bars_to_peak": _pct([float(p) for p in peaks], 0.50),
    }
    comparison = {
        k: {"episode_derived": derived_stats[k],
            "ledger_summary": survival.get(k),
            "delta": (None if derived_stats[k] is None or survival.get(k) is None
                      else round(derived_stats[k] - float(survival[k]), 8))}
        for k in derived_stats
    }
    agree = [k for k, v in comparison.items()
             if v["delta"] is not None and abs(v["delta"]) <= tol]

    return {
        "n": len(mfe_rr),
        "strength": "AGGREGATE_ONLY — per-trade oracle not persisted (see probe_ledger)",
        "comparison": comparison,
        "n_agree": len(agree),
        "n_compared": sum(1 for v in comparison.values() if v["delta"] is not None),
        "agreeing_keys": agree,
    }
