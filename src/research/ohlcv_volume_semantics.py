"""BC-4 volume-semantics scorer: does MT5 `volume` count ticks?

Rules: docs/research/preregistration-bc4-volume-semantics.md
Test 1 (semantic identity) needs a LIVE tick capture within the freshness window (section 3.1).
Test 2 (artifact binding) needs only M15 rate bars and can run against any capture that includes
timestamps sampled across the frozen corpus range.

Depends on BC-2/F-098: the tick window [T, T+15m) is only well-defined because T is proven to be
the bar OPEN, not the close.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Optional

from research.ohlcv_probe_report import (
    CLOCK_BASIS,
    SOURCE_LIVE,
    SOURCE_SYNTHETIC,
    ProbeError,
    ProbeSnapshot,
    aware_utc,
    base_report,
    staleness_reason,
    terminal_provenance,
)

PREREG = "docs/research/preregistration-bc4-volume-semantics.md"
PROBE_ID = "BC4-VOLUME-SEMANTIC-XAUUSD-MT5-V1"

BAR_MINUTES = 15
FRESHNESS_SECONDS = 3600  # section 3.1: tick history reliable only within ~1h on this terminal
MIN_TEST1_BARS = 3
TEST1_EXACT_MATCH_THRESHOLD = 0.90
TEST2_BOUND_THRESHOLD = 0.99
DEFAULT_TEST2_SAMPLE = 20

VERDICT_CONFIRMED = "TICK_VOLUME_CONFIRMED"
VERDICT_APPROXIMATE = "TICK_VOLUME_APPROXIMATE"
VERDICT_CONTRADICTED = "TICK_VOLUME_CONTRADICTED"
VERDICT_INSUFFICIENT = "INSUFFICIENT"

BINDING_BOUND = "BOUND"
BINDING_UNCONFIRMED = "UNCONFIRMED"
BINDING_CONTRADICTED = "CONTRADICTED"
BINDING_NOT_TESTED = "NOT_TESTED"

H_REAL_REJECTED = "REJECTED"
H_REAL_NOT_REJECTED = "NOT_REJECTED"
H_REAL_NOT_TESTED = "NOT_TESTED"

DEFAULT_EVIDENCE_DIR = "docs/research-readiness/bc4_volume_semantics"

FROZEN_CORPUS_START = datetime(2024, 5, 22, 1, 0, 0, tzinfo=timezone.utc)
FROZEN_CORPUS_END = datetime(2026, 5, 21, 23, 45, 0, tzinfo=timezone.utc)


def _score_test1(
    bars: list[dict], *, now_broker: datetime, freshness_seconds: int = FRESHNESS_SECONDS
) -> dict[str, Any]:
    """bars: [{"T": datetime, "tick_volume": int, "real_volume": int, "ticks_all": int|None}]."""
    scored = []
    for b in bars:
        close_t = b["T"] + timedelta(minutes=BAR_MINUTES)
        age = (now_broker - close_t).total_seconds()
        if age < 0 or age > freshness_seconds:
            continue
        if b.get("ticks_all") is None:
            continue
        scored.append(b)

    if len(scored) < MIN_TEST1_BARS:
        return {
            "volume_semantic_verdict": VERDICT_INSUFFICIENT,
            "test1_reason": "insufficient_fresh_bars",
            "test1_n_scored": len(scored),
            "test1_diffs": [],
            "h_real_status": H_REAL_NOT_TESTED,
        }

    diffs = [b["ticks_all"] - b["tick_volume"] for b in scored]
    exact = sum(1 for d in diffs if d == 0)
    rate = exact / len(scored)
    med = median(diffs)

    real_vols = [b.get("real_volume") for b in scored if b.get("real_volume") is not None]
    if real_vols and all(v == 0 for v in real_vols) and all(b["tick_volume"] > 0 for b in scored):
        h_real = H_REAL_REJECTED
    elif real_vols:
        h_real = H_REAL_NOT_REJECTED
    else:
        h_real = H_REAL_NOT_TESTED

    if rate >= TEST1_EXACT_MATCH_THRESHOLD and med == 0:
        verdict = VERDICT_CONFIRMED
        reason = "exact_match_rate_and_median_pass"
    elif all(d >= 0 for d in diffs) and (sum(diffs) / len(diffs)) < 0.20 * (
        sum(b["tick_volume"] for b in scored) / len(scored) or 1
    ):
        # small, directionally-consistent gap (ticks_all >= tick_volume) -- ADIFFERENT verdict,
        # never silently folded into CONFIRMED (prereg section 4, rule 3)
        verdict = VERDICT_APPROXIMATE
        reason = "small_directional_gap"
    else:
        verdict = VERDICT_CONTRADICTED
        reason = "exact_match_rate_or_median_fail"

    return {
        "volume_semantic_verdict": verdict,
        "test1_reason": reason,
        "test1_n_scored": len(scored),
        "test1_exact_match_rate": rate,
        "test1_median_diff": med,
        "test1_diffs": diffs,
        "h_real_status": h_real,
    }


def _score_test2(sampled: list[dict]) -> dict[str, Any]:
    """sampled: [{"T": datetime, "frozen_volume": int, "refetched_tick_volume": int|None}]."""
    usable = [s for s in sampled if s.get("refetched_tick_volume") is not None]
    if not usable:
        return {
            "artifact_binding": BINDING_NOT_TESTED,
            "test2_reason": "no_refetched_bars",
            "test2_n_sampled": 0,
        }
    diffs = [s["refetched_tick_volume"] - s["frozen_volume"] for s in usable]
    exact = sum(1 for d in diffs if d == 0)
    rate = exact / len(usable)
    result: dict[str, Any] = {
        "test2_n_sampled": len(usable),
        "test2_exact_match_rate": rate,
        "test2_diffs": diffs,
    }
    if rate >= TEST2_BOUND_THRESHOLD:
        result["artifact_binding"] = BINDING_BOUND
        result["test2_reason"] = "exact_match_rate_pass"
        return result
    # systematic offset/scale check
    nonzero = [d for d in diffs if d != 0]
    if nonzero and len(set(nonzero)) == 1:
        result["artifact_binding"] = BINDING_CONTRADICTED
        result["test2_reason"] = f"constant_offset_{nonzero[0]}"
        return result
    ratios = [
        s["refetched_tick_volume"] / s["frozen_volume"]
        for s in usable
        if s["frozen_volume"] not in (0, None)
    ]
    if ratios and len(set(round(r, 6) for r in ratios)) == 1 and round(ratios[0], 6) != 1.0:
        result["artifact_binding"] = BINDING_CONTRADICTED
        result["test2_reason"] = f"constant_scale_{ratios[0]:.6f}"
        return result
    result["artifact_binding"] = BINDING_UNCONFIRMED
    result["test2_reason"] = "mismatches_no_systematic_pattern"
    return result


def score_volume_semantics(
    snap_a: ProbeSnapshot,
    *,
    now_broker: Optional[datetime] = None,
    repo_root: Optional[Path] = None,
    verify_admitted: bool = True,
) -> dict[str, Any]:
    """snap_a.payload carries {"test1_bars": [...], "test2_samples": [...]}."""
    report = base_report(
        PROBE_ID, snap_a=snap_a, prereg=PREREG, repo_root=repo_root, verify_admitted=verify_admitted
    )

    stale = staleness_reason(snap_a, "a")
    if stale:
        report.update(
            {
                "volume_semantic_verdict": VERDICT_INSUFFICIENT,
                "test1_reason": stale,
                "artifact_binding": BINDING_NOT_TESTED,
                "test2_reason": "skipped_stale_feed",
                "h_real_status": H_REAL_NOT_TESTED,
                "executable_volume_semantic_proof": False,
            }
        )
        return report

    now = aware_utc(now_broker) if now_broker is not None else aware_utc(snap_a.fetched_at)
    t1 = _score_test1(snap_a.payload.get("test1_bars", []), now_broker=now)
    t2 = _score_test2(snap_a.payload.get("test2_samples", []))
    report.update(t1)
    report.update(t2)

    report["executable_volume_semantic_proof"] = bool(
        report["volume_semantic_verdict"] in (VERDICT_CONFIRMED, VERDICT_APPROXIMATE)
        and report["source_a"] == SOURCE_LIVE
        and report["admitted_sha256_match"] is True
    )
    return report


def capture_bc4_snapshot(
    symbol: str = "XAUUSD",
    n_recent_bars: int = 4,
    test2_sample: int = DEFAULT_TEST2_SAMPLE,
    sync_retries: int = 4,
) -> ProbeSnapshot:
    """Live capture for both Test 1 (recent ticks) and Test 2 (sampled historical rebars).

    Test 1 is scoped to bars within FRESHNESS_SECONDS of capture time (prereg section 3.1) --
    older copy_ticks_range calls were observed to hang indefinitely on this terminal rather
    than error, so this function never requests ticks outside that window.
    """
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ProbeError(f"MT5_UNAVAILABLE: MetaTrader5 import failed: {exc}") from exc
    if not mt5.initialize():
        raise ProbeError(f"MT5_UNAVAILABLE: initialize failed: {mt5.last_error()}")
    try:
        if not mt5.symbol_select(symbol, True):
            raise ProbeError(f"MT5_UNAVAILABLE: symbol_select {symbol}: {mt5.last_error()}")
        terminal = terminal_provenance(mt5)

        tick = None
        rates = None
        for _ in range(max(1, sync_retries)):
            tick = mt5.symbol_info_tick(symbol)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, max(n_recent_bars, 3) + 1)
            if tick is None or not getattr(tick, "time", None):
                time.sleep(2)
                continue
            if rates is None or len(rates) == 0:
                time.sleep(2)
                continue
            gap = int(tick.time) - int(rates[-1]["time"])
            if 0 <= gap < BAR_MINUTES * 60:
                break
            time.sleep(2)
        if tick is None or not getattr(tick, "time", None):
            raise ProbeError("clock=unavailable: symbol_info_tick.time missing")
        if rates is None or len(rates) == 0:
            raise ProbeError("empty_rates")

        wall_now = datetime.now(timezone.utc)
        fetched_at = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)

        # Test 1: only CLOSED bars (drop the still-forming last row), within the freshness window.
        test1_bars = []
        closed = [r for r in rates if int(r["time"]) + BAR_MINUTES * 60 <= int(tick.time)]
        for r in closed[-n_recent_bars:]:
            T = datetime.fromtimestamp(int(r["time"]), tz=timezone.utc)
            close_t = T + timedelta(minutes=BAR_MINUTES)
            # Both sides must be on the SAME nominal clock basis (F-066): fetched_at
            #             and bar timestamps are both broker-server seconds mislabeled UTC.
            #             Comparing against TRUE wall clock here would show every bar as
            #             hours in the future at a positive broker offset and exclude all of
            #             them -- observed 2026-09-02, fixed before the first real capture.
            age = (fetched_at - close_t).total_seconds()
            entry = {
                "T": T.isoformat(),
                "tick_volume": int(r["tick_volume"]),
                "real_volume": int(r["real_volume"]),
                "ticks_all": None,
            }
            if 0 <= age <= FRESHNESS_SECONDS:
                ticks = mt5.copy_ticks_range(symbol, T, close_t, mt5.COPY_TICKS_ALL)
                entry["ticks_all"] = None if ticks is None else len(ticks)
            test1_bars.append(entry)

        # Test 2: sample bars across the frozen corpus range using rate bars only (no ticks).
        test2_samples = []
        span = FROZEN_CORPUS_END - FROZEN_CORPUS_START
        step = span / max(test2_sample - 1, 1)
        def _snap_to_lattice(dt: datetime) -> datetime:
            # M15 rate bars exist only at exact 15-minute lattice points; the raw
            # step*i arithmetic below produces fractional-second targets that can
            # never match a real bar (observed: 1/20 samples matched before this fix).
            epoch = int(dt.timestamp())
            epoch -= epoch % (BAR_MINUTES * 60)
            return datetime.fromtimestamp(epoch, tz=timezone.utc)

        targets = [
            _snap_to_lattice(FROZEN_CORPUS_START + step * i) for i in range(test2_sample)
        ]
        for target in targets:
            window_start = target - timedelta(hours=1)
            r2 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, window_start, target + timedelta(minutes=BAR_MINUTES))
            match = None
            if r2 is not None:
                for row in r2:
                    if int(row["time"]) == int(target.timestamp()):
                        match = int(row["tick_volume"])
                        break
            test2_samples.append(
                {"T": target.isoformat(), "refetched_tick_volume": match}
            )

        return ProbeSnapshot(
            fetched_at=fetched_at,
            symbol=symbol,
            source=SOURCE_LIVE,
            clock_basis=CLOCK_BASIS,
            terminal=terminal,
            wall_clock_skew_seconds=(wall_now - fetched_at).total_seconds(),
            payload={"test1_bars": test1_bars, "test2_samples": test2_samples},
        )
    finally:
        mt5.shutdown()


def snap_to_dict(snap: ProbeSnapshot) -> dict:
    return {
        "fetched_at": aware_utc(snap.fetched_at).isoformat(),
        "symbol": snap.symbol,
        "clock_basis": snap.clock_basis,
        "source": snap.source,
        "terminal": snap.terminal,
        "wall_clock_skew_seconds": snap.wall_clock_skew_seconds,
        "payload": snap.payload,
    }


def snap_from_dict(raw: dict) -> ProbeSnapshot:
    skew = raw.get("wall_clock_skew_seconds")
    return ProbeSnapshot(
        fetched_at=datetime.fromisoformat(raw["fetched_at"]),
        symbol=str(raw.get("symbol") or "XAUUSD"),
        source=str(raw.get("source") or SOURCE_SYNTHETIC),
        clock_basis=str(raw.get("clock_basis") or CLOCK_BASIS),
        terminal=raw.get("terminal"),
        wall_clock_skew_seconds=None if skew is None else float(skew),
        payload=raw.get("payload") or {},
    )


def _payload_bars_from_iso(payload: dict) -> dict:
    out = dict(payload)
    bars = []
    for b in payload.get("test1_bars", []):
        bb = dict(b)
        bb["T"] = datetime.fromisoformat(b["T"])
        bars.append(bb)
    out["test1_bars"] = bars
    samples = []
    for s in payload.get("test2_samples", []):
        ss = dict(s)
        # Test 2 scoring compares to the FROZEN csv volume, not the raw sample dict; the CLI
        # path fills frozen_volume separately (see main()).
        samples.append(ss)
    out["test2_samples"] = samples
    return out


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="BC-4 volume-semantics probe.")
    sub = p.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture", help="Write one MT5 snapshot JSON (Test1 + Test2 payload).")
    cap.add_argument("--symbol", default="XAUUSD")
    cap.add_argument("--out", required=True)
    sc = sub.add_parser("score", help="Score a captured snapshot against the admitted CSV.")
    sc.add_argument("--snapshot", required=True)
    sc.add_argument("--admitted-csv", default="data/mt5/XAUUSD_M15.csv")
    sc.add_argument("--out", default=f"{DEFAULT_EVIDENCE_DIR}/score.json")
    args = p.parse_args(argv)

    if args.cmd == "capture":
        try:
            snap = capture_bc4_snapshot(args.symbol)
        except ProbeError as exc:
            payload = {"ok": False, "error": str(exc)}
            _write_json(Path(args.out), payload)
            print(json.dumps(payload))
            return 2
        payload = {"ok": True, **snap_to_dict(snap)}
        _write_json(Path(args.out), payload)
        print(json.dumps({"ok": True, "out": args.out, "fetched_at": payload["fetched_at"]}))
        return 0

    raw = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
    if raw.get("ok") is False:
        report = base_report(PROBE_ID, prereg=PREREG)
        report.update(
            {
                "volume_semantic_verdict": VERDICT_INSUFFICIENT,
                "test1_reason": "snapshot_capture_failed",
                "artifact_binding": BINDING_NOT_TESTED,
                "h_real_status": H_REAL_NOT_TESTED,
                "executable_volume_semantic_proof": False,
            }
        )
        _write_json(Path(args.out), report)
        print(json.dumps(report, indent=2))
        return 1

    snap = snap_from_dict(raw)
    parsed_payload = _payload_bars_from_iso(snap.payload)
    snap = ProbeSnapshot(
        fetched_at=snap.fetched_at,
        symbol=snap.symbol,
        source=snap.source,
        clock_basis=snap.clock_basis,
        terminal=snap.terminal,
        wall_clock_skew_seconds=snap.wall_clock_skew_seconds,
        payload=parsed_payload,
    )

    # fill frozen_volume for Test 2 from the admitted CSV by exact timestamp match
    import csv as _csv

    frozen_by_ts: dict[str, int] = {}
    admitted_path = Path(args.admitted_csv)
    if admitted_path.is_file():
        with admitted_path.open(newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                frozen_by_ts[row["timestamp"]] = int(float(row["volume"]))
    for s in snap.payload["test2_samples"]:
        # snap.payload's test2_samples T is still the raw ISO string here
        # (_payload_bars_from_iso deliberately leaves it, per its own docstring).
        ts_key = datetime.fromisoformat(s["T"]).strftime("%Y-%m-%d %H:%M:%S")
        if ts_key in frozen_by_ts:
            s["frozen_volume"] = frozen_by_ts[ts_key]
    snap.payload["test2_samples"] = [
        s for s in snap.payload["test2_samples"] if "frozen_volume" in s
    ]

    report = score_volume_semantics(snap)
    _write_json(Path(args.out), report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
