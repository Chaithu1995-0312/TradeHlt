"""dimensional_mix_shadow_diagnostic.py — measure the FM-022/023 -> FM-030/031 correction on the spine.

WHAT THIS IS
------------
A book-level A/B of the production CRT spine under the two registered normalization bases:

    LEGACY    configs/production/v2_multi_2026_04.json          feature_pipeline.normalization_basis = "atr_relative"
              -> FM-022 ema_spread = (ema_fast-ema_slow)/atr,  FM-023 momentum_score = close_delta/atr
    CORRECTED configs/production/v2_multi_dimfix_shadow_2026_07.json                        = "atr_absolute"
              -> FM-030                    /(atr*close),       FM-031                      /(atr*close)

The two production configs differ in EXACTLY that one value (verified by key diff). In particular
the `engine_runner.dual_engine` thresholds are deliberately NOT recalibrated in the corrected arm:
recalibrating them here would confound "the identity changed" with "the thresholds changed".

WHY IT MATTERS (F-061)
----------------------
Legacy == corrected * `close`, because the numerator is absolute price and `atr` is close-relative
(atr_14_raw/close). So the defect's magnitude is the instrument's price level, and the thresholds
tuned for a dimensionless O(1) quantity (trend_strength_threshold 0.15 / momentum_threshold 0.3)
stop binding on crypto. Measured on the real corpora:

    detect_regime -> "trend"          BNB 98.86%   BTC 99.94%   EURUSD 54.57%
    breakout score pinned at 1.0      BNB 99.99%   BTC 100.00%  EURUSD 11.58%
    corrected -> "trend"              BNB 52.70%   BTC 52.75%   EURUSD 50.11%

GATE-ON IS MANDATORY
--------------------
`detect_regime` / `breakout_engine` live inside `EngineRunner.run()`, which the gate-OFF research
path never calls (F-037; code default is ON per F-058 but `.env` may set it to 0). This driver
forces BACKTEST_ENGINE_GATE=1 BEFORE importing the spine adapter — the F-036 re-measurement method.
Without it the A/B would be vacuous.

READING THE RESULT
------------------
The entry sets ARE nested for this change: corrected is a strict SUBSET of legacy.

  SUPERSEDED 2026-07-22 (§6.2 rule 4 — the original claim is kept here because it explains why the
  code was shaped this way). This driver was modelled on `bitnet_shadow_diagnostic.py` and inherited
  its caveat: "entry sets are NOT nested — a reject resets the CRT state machine, so the trajectory
  diverges in both directions (removed != added)." That is TRUE for BitNet, which vetoes INSIDE
  `UltronRiskEngine.approve_with_soft_conf` (crt_engine_v2.py:1960) and therefore perturbs the state
  machine itself. It is FALSE here, and the difference is structural, not empirical: CRT never reads
  `ema_spread` / `momentum_score`, so its trajectory is invariant under the basis change and the
  regime layer acts as a PURE DOWNSTREAM VETO.

Measured on BNBUSDT (2026-07-22): `total_setups` 13 in BOTH arms (CRT identical), approvals 11 ->
7, zero additions, surviving trades byte-identical SL geometry, and the 4 dropped trades map exactly
onto 4 new regime-layer rejections. This is a better-controlled experiment than the BitNet shape
assumed — a clean subset with no confounding divergence. `nested` is reported per instrument; if it
ever comes back False, the structural assumption above has broken and the result needs re-reading.

Prior (F-019...F-043): entry information on these instruments is null, so expect NO economic
improvement. The spine yields ~5-13 entries per instrument, so per-instrument n is almost
certainly < 30 -> INSUFFICIENT, and no economic claim may be made either way. The F-061 mechanism
finding (saturation) is arithmetic and stands independently of whatever this returns.

SCOPE / AUTHORITY
-----------------
Research authority ONLY (CLAUDE.md §6.5). No promotion, no ACTIVE_VERSION change. A positive result
here would NOT by itself authorize activation — that needs demonstrated G001 improvement plus a
recalibration of the dual_engine thresholds, which is a separate program.

USAGE
-----
    python scripts/research/dimensional_mix_shadow_diagnostic.py                    # BNBUSDT
    python scripts/research/dimensional_mix_shadow_diagnostic.py --instruments BNBUSDT ETHUSDT
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# MUST precede the spine-adapter import: backtest_v2 reads BACKTEST_ENGINE_GATE at construction
# time, and the consumers under test (detect_regime / breakout_engine) only execute inside
# EngineRunner.run(). See F-036 (same technique, inverted) and F-037/F-058.
os.environ["BACKTEST_ENGINE_GATE"] = "1"

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from research.adapters.spine_signal_source import ProductionSpineSource, SpineEntry  # noqa: E402

_REGIME_LOG = Path("logs/regime_classifications.jsonl")


def _utcnow() -> str:
    """ISO-Z timestamp in the same format the event envelope stamps."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

LEGACY_CONFIG = "configs/research/research_config_spine_majors.json"         # atr_relative
CORRECTED_CONFIG = "configs/research/research_config_spine_dimfix_shadow.json"  # atr_absolute
# Single-coin default (2026-07-22). The question this driver answers is MECHANISM — does the
# config-gated identity execute, and does it move the decision surface — not economics. Per-instrument
# spine throughput is 5-13 entries, far below MIN_SAMPLES, so additional instruments buy no economic
# authority and cost ~18 min each. BNBUSDT is the reference instrument: it carries the parity proof
# (gate-ON approved_trades=11, ledger 9bcba138…) and exhibits the saturation most clearly.
DEFAULT_INSTRUMENTS = ["BNBUSDT"]

MIN_SAMPLES = 30   # matches the M4 qualification gate; below this we make no economic claim


def _rr(entry: SpineEntry) -> float:
    """Spine's own realized net RR for this entry (governed ledger truth, no re-derived exits)."""
    return float(entry.meta.get("backtest_pnl_rr_net", 0.0))


def _stats(entries: list[SpineEntry]) -> dict:
    n = len(entries)
    if n == 0:
        return {"n": 0, "expectancy_rr": None, "win_rate": None, "profit_factor": None, "sum_rr": 0.0}
    rrs = [_rr(e) for e in entries]
    wins = [r for r in rrs if r > 0]
    losses = [r for r in rrs if r < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    return {
        "n": n,
        "expectancy_rr": round(sum(rrs) / n, 4),
        "win_rate": round(len(wins) / n, 4),
        "profit_factor": (round(pf, 4) if pf != float("inf") else "inf"),
        "sum_rr": round(sum(rrs), 4),
    }


def _power(n: int) -> str:
    return "POWERED" if n >= MIN_SAMPLES else "INSUFFICIENT"


def _regime_change_events(start_iso: str, end_iso: str) -> dict:
    """Count REGIME_CLASSIFICATION events in a wall-clock window (the Q3 instrument).

    `engine_runner` emits this stream ON CHANGE ONLY (`:843-849`), so the event count IS the
    discrimination measure: a layer that never changes its label emits exactly one event (the
    initial `null -> <regime>`). The stream carries no run id, so runs are separated by their
    wall-clock window; `instrument` is empty in the envelope.
    """
    counts: dict[str, int] = {}
    total = 0
    if not _REGIME_LOG.is_file():
        return {"total": None, "by_regime": {}, "note": "stream absent"}
    with _REGIME_LOG.open(encoding="utf-8") as fh:
        for line in fh:
            if '"REGIME_CLASSIFICATION"' not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = rec.get("timestamp", "")
            if start_iso <= ts < end_iso:
                total += 1
                r = str(rec.get("payload", {}).get("regime", "?"))
                counts[r] = counts.get(r, 0) + 1
    return {"total": total, "by_regime": counts}


def _geometry_identical(legacy: dict, corrected: dict, shared_keys) -> bool:
    """Do the SURVIVING entries keep identical trade geometry across the two arms?

    If True, the basis change only ADMITTED/REJECTED trades — it did not move entry/SL/TP on the
    ones that survived, which is what isolates the effect to the regime gate.
    """
    for k in shared_keys:
        a, b = legacy[k], corrected[k]
        if (a.entry, a.direction, a.risk_distance, a.reward_distance, a.timestamp) != \
           (b.entry, b.direction, b.risk_distance, b.reward_distance, b.timestamp):
            return False
    return True


def _verdict(legacy: dict, corrected: dict, n_removed: int, n_added: int) -> tuple[str, float | None]:
    """Book-level verdict. Power gates the ECONOMIC reading, never the structural one."""
    delta = None
    if legacy["expectancy_rr"] is not None and corrected["expectancy_rr"] is not None:
        delta = round(corrected["expectancy_rr"] - legacy["expectancy_rr"], 4)

    if not n_removed and not n_added:
        # Structural claim, valid at any n: the correction changed no entry at all.
        return "DECISION_INERT", delta
    if min(legacy["n"], corrected["n"]) < MIN_SAMPLES:
        # Entries moved, but the book is too small to read economically (§6.5 / E-001).
        return "INSUFFICIENT", delta
    if delta is None:
        return "UNDETERMINED", delta
    if delta > 1e-9:
        return "IMPROVES", delta
    if delta < -1e-9:
        return "DEGRADES", delta
    return "NEUTRAL", delta


# ONE source per arm for the whole process. `ProductionSpineSource` caches per INSTANCE
# (`self._cache` keyed by (instrument, prod_version)), so constructing a second instance re-runs
# the backtest from scratch — a ~9-minute penalty per extra construction. Build them once.
_LEGACY_SRC = ProductionSpineSource(config_path=LEGACY_CONFIG)
_CORRECTED_SRC = ProductionSpineSource(config_path=CORRECTED_CONFIG)


def diagnose(instrument: str) -> tuple[dict, dict, dict]:
    """Return (report, legacy_entries, corrected_entries) — entries reused for the pooled book."""
    # Wall-clock brackets around each arm let _regime_change_events attribute the shared
    # append-only REGIME_CLASSIFICATION stream to the right run (it carries no run id).
    _t0 = _utcnow()
    legacy = _LEGACY_SRC.entries(instrument)        # {research_index: SpineEntry}
    _t1 = _utcnow()
    corrected = _CORRECTED_SRC.entries(instrument)
    _t2 = _utcnow()

    l_keys, c_keys = set(legacy), set(corrected)
    removed_keys = l_keys - c_keys                 # present under legacy, gone under the correction
    added_keys = c_keys - l_keys                   # newly formed once the trajectory diverged

    s_legacy = _stats([legacy[k] for k in sorted(l_keys)])
    s_corrected = _stats([corrected[k] for k in sorted(c_keys)])
    s_removed = _stats([legacy[k] for k in sorted(removed_keys)])
    s_added = _stats([corrected[k] for k in sorted(added_keys)])

    verdict, delta = _verdict(s_legacy, s_corrected, len(removed_keys), len(added_keys))

    report = {
        "instrument": instrument,
        "n_legacy": len(legacy), "n_corrected": len(corrected),
        "n_removed": len(removed_keys), "n_added": len(added_keys),
        "kept": len(l_keys & c_keys),
        "removed_research_indices": sorted(removed_keys),
        "added_research_indices": sorted(added_keys),
        "legacy_book": s_legacy, "corrected_book": s_corrected,
        "removed": s_removed, "added": s_added,
        "book_delta_expectancy": delta,
        "power": _power(min(s_legacy["n"], s_corrected["n"])),
        "verdict": verdict,
        # ── the four implementation-validation fields (2026-07-22) ─────────────────────────
        # Structural, not economic: each is valid at any n, unlike expectancy.
        "nested": bool(c_keys <= l_keys),                       # corrected ⊆ legacy?
        "dropped_research_indices": sorted(removed_keys),
        "surviving_trades_geometry_identical": _geometry_identical(
            legacy, corrected, sorted(l_keys & c_keys)
        ),
        "regime_change_events": {
            "legacy": _regime_change_events(_t0, _t1),
            "corrected": _regime_change_events(_t1, _t2),
            "_doc": "REGIME_CLASSIFICATION is emitted ON CHANGE ONLY, so total==1 means the regime "
                    "label never changed for the whole backtest (a literal constant).",
        },
    }
    return report, legacy, corrected


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="FM-030/031 dimensional-mix shadow diagnostic (corrected vs legacy basis, gate-ON)."
    )
    ap.add_argument("--instruments", nargs="*", default=DEFAULT_INSTRUMENTS)
    ap.add_argument("--out", default="reports/analysis/dimensional_mix_shadow_diagnostic.json")
    args = ap.parse_args(argv)

    results = []
    pooled_legacy: list[SpineEntry] = []
    pooled_corrected: list[SpineEntry] = []

    for inst in args.instruments:
        print(f"[RUN] {inst}: legacy (atr_relative) vs corrected (atr_absolute), gate-ON ...", flush=True)
        r, legacy_entries, corrected_entries = diagnose(inst)
        results.append(r)
        print(
            f"  {inst}: n_legacy={r['n_legacy']} n_corrected={r['n_corrected']} "
            f"kept={r['kept']} removed={r['n_removed']} added={r['n_added']} "
            f"| E_legacy={r['legacy_book']['expectancy_rr']} E_corrected={r['corrected_book']['expectancy_rr']} "
            f"delta={r['book_delta_expectancy']} | {r['verdict']} ({r['power']})",
            flush=True,
        )
        # reuse the SAME dicts diagnose() already computed — never re-enter entries() on a fresh
        # source, which would silently re-run the whole backtest
        pooled_legacy.extend(legacy_entries.values())
        pooled_corrected.extend(corrected_entries.values())

    s_pl, s_pc = _stats(pooled_legacy), _stats(pooled_corrected)
    pool_delta = None
    if s_pl["expectancy_rr"] is not None and s_pc["expectancy_rr"] is not None:
        pool_delta = round(s_pc["expectancy_rr"] - s_pl["expectancy_rr"], 4)

    report = {
        "kind": "fm030_031_dimensional_mix_shadow_diagnostic",
        "program": "FM-030-031-DIMENSIONAL-MIX-MIGRATION",
        "legacy_config": LEGACY_CONFIG,
        "corrected_config": CORRECTED_CONFIG,
        "engine_gate": "BACKTEST_ENGINE_GATE=1 (forced) — detect_regime/breakout_engine only run "
                       "inside EngineRunner.run(); gate-OFF would make this A/B vacuous (F-037/F-058)",
        "thresholds_recalibrated": False,
        "scope": "research-authority-only; no promotion; ACTIVE_VERSION unchanged; "
                 "FM-030/031 stay active:false in the ontology",
        "note": "Entry sets ARE nested for this change (corrected is a strict SUBSET of legacy) — "
                "CRT never consumes FM-022/023, so its trajectory is invariant and the regime layer "
                "acts as a pure downstream veto. This SUPERSEDES the inherited BitNet-shaped caveat "
                "('NOT nested, removed != added'), which is true for a veto INSIDE the CRT state "
                "machine but false here; see the module docstring for the kept original. Check the "
                "per-instrument `nested` flag — False would mean that structural assumption broke. "
                f"Per-instrument n < {MIN_SAMPLES} => INSUFFICIENT, no economic claim (§6.5 / E-001).",
        "per_instrument": results,
        "pooled": {
            "legacy_book": s_pl, "corrected_book": s_pc,
            "book_delta_expectancy": pool_delta,
            "power": _power(min(s_pl["n"], s_pc["n"])),
        },
        "totals": {
            "n_legacy": sum(r["n_legacy"] for r in results),
            "n_corrected": sum(r["n_corrected"] for r in results),
            "n_removed": sum(r["n_removed"] for r in results),
            "n_added": sum(r["n_added"] for r in results),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n===== POOLED (book-level A/B) =====")
    t = report["totals"]
    print(f"  spine entries: legacy={t['n_legacy']}  corrected={t['n_corrected']}  "
          f"(removed={t['n_removed']}, added={t['n_added']})")
    print(f"  E_legacy   : {s_pl['expectancy_rr']}  (PF {s_pl['profit_factor']}, WR {s_pl['win_rate']}, n {s_pl['n']})")
    print(f"  E_corrected: {s_pc['expectancy_rr']}  (PF {s_pc['profit_factor']}, WR {s_pc['win_rate']}, n {s_pc['n']})")
    print(f"  book delta expectancy (corrected - legacy): {pool_delta}   [{report['pooled']['power']}]")
    print(f"\n[OK] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
