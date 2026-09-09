"""BC-2 executable open-vs-close label scorer.

Rules: docs/research/preregistration-bc2-open-close-label.md
Live MT5 capture is optional. Synthetic scoring never flips G-06.

The discriminator is the SIGN of ``fetched_at_A - T_last``. Mutation of bar T is a
liveness precondition (it proves the bar was still forming), and the 15-minute
lattice check is a shape guard. See the prereg amendment (section 9) for the
emission-layer contract this module implements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

BAR_MINUTES = 15
MARGIN_SECONDS = 60
LATTICE_SECONDS = BAR_MINUTES * 60
DATASET_ID = "XAUUSD_MT5_PHASE1_20260521"
ADMITTED_SHA256 = (
    "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
)
ADMITTED_PATH = "data/mt5/XAUUSD_M15.csv"
PREREG = "docs/research/preregistration-bc2-open-close-label.md"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Amendment 9.1 (D5). Offset-tolerant: MT5 server time runs ~UTC+2/+3 (F-066), so a
# HEALTHY terminal shows a legitimate skew of a few hours (measured 2026-09-02:
# -10799s == UTC+3 exactly). A tight threshold would reject a live feed. 6h clears
# any plausible broker offset and still catches the weeks-stale terminal that
# .grok/PENDING.md warns about.
STALE_THRESHOLD_SECONDS = 6 * 3600

# Clock vocabulary is the token the dataset identity record already declares
# (docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json). MT5 epochs are
# broker-server seconds; the "+00:00" suffix on persisted stamps is NOMINAL (F-066).
CLOCK_BASIS = "broker_local"

SOURCE_LIVE = "live_mt5"
SOURCE_SYNTHETIC = "synthetic"

VERDICT_OPEN = "OPEN"
VERDICT_CLOSE = "CLOSE"
VERDICT_OTHER = "OTHER"
VERDICT_INSUFFICIENT = "INSUFFICIENT"

# G-06 is "open-time labeling" (docs/governance/ohlcv-closure-report-2026-07-10.md:52).
# A CLOSE verdict therefore CONTRADICTS G-06; it does not grant it (prereg section 6).
G06_PROVEN = "PROVEN"
G06_CONTRADICTED = "CONTRADICTED"
G06_UNPROVEN = "UNPROVEN"


@dataclass(frozen=True)
class BarSnap:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class FetchSnap:
    fetched_at: datetime
    symbol: str
    bars: tuple[BarSnap, ...]
    clock: str = "mt5_tick"
    # Fail-closed: only capture_mt5_snapshot may claim a live source.
    source: str = SOURCE_SYNTHETIC
    clock_basis: str = CLOCK_BASIS
    terminal: Optional[dict] = None
    # Measured AT CAPTURE TIME and stored in the snapshot. Scoring a snapshot days
    # later must not re-measure skew against the scoring clock.
    wall_clock_skew_seconds: Optional[float] = None


class LabelProbeError(RuntimeError):
    pass


def _aware_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def on_m15_lattice(ts: datetime) -> bool:
    t = _aware_utc(ts)
    return t.second == 0 and t.microsecond == 0 and t.minute % BAR_MINUTES == 0


def _last(snap: FetchSnap) -> Optional[BarSnap]:
    if not snap.bars:
        return None
    return snap.bars[-1]


def _find(snap: FetchSnap, ts: datetime) -> Optional[BarSnap]:
    target = _aware_utc(ts)
    for b in snap.bars:
        if _aware_utc(b.timestamp) == target:
            return b
    return None


def _mutated(a: BarSnap, b: BarSnap) -> bool:
    return (a.high, a.low, a.close, a.volume) != (b.high, b.low, b.close, b.volume)


@lru_cache(maxsize=4)
def _sha256_of(path: str) -> Optional[str]:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_admitted_artifact(
    repo_root: Optional[Path] = None,
) -> tuple[bool, Optional[bool]]:
    """Hash the admitted canonical CSV.

    Returns ``(present, match)``. ``match`` is None when the file is absent — the
    report must not assert a binding it could not check.
    """
    root = repo_root or REPO_ROOT
    digest = _sha256_of(str(root / ADMITTED_PATH))
    if digest is None:
        return False, None
    return True, digest == ADMITTED_SHA256


def _base_report(
    snap_a: Optional[FetchSnap] = None,
    snap_b: Optional[FetchSnap] = None,
    *,
    repo_root: Optional[Path] = None,
    verify_admitted: bool = True,
) -> dict[str, Any]:
    """The ONE report shape. Every exit path returns this key set (D2)."""
    if verify_admitted:
        present, match = verify_admitted_artifact(repo_root)
    else:
        present, match = False, None
    return {
        "probe_id": "BC2-OPEN-CLOSE-XAUUSD-MT5-V1",
        "dataset_id": DATASET_ID,
        "admitted_sha256": ADMITTED_SHA256,
        "admitted_path": ADMITTED_PATH,
        "admitted_artifact_present": present,
        "admitted_sha256_match": match,
        "prereg": PREREG,
        "verdict": VERDICT_INSUFFICIENT,
        "reason": "",
        "candidate": None,
        "delta_seconds_a": None,
        "clock_a": snap_a.clock if snap_a else None,
        "clock_b": snap_b.clock if snap_b else None,
        "clock_basis": snap_a.clock_basis if snap_a else CLOCK_BASIS,
        "source_a": snap_a.source if snap_a else None,
        "source_b": snap_b.source if snap_b else None,
        "wall_clock_skew_seconds_a": snap_a.wall_clock_skew_seconds if snap_a else None,
        "wall_clock_skew_seconds_b": snap_b.wall_clock_skew_seconds if snap_b else None,
        "stale_threshold_seconds": STALE_THRESHOLD_SECONDS,
        "terminal_a": snap_a.terminal if snap_a else None,
        "terminal_b": snap_b.terminal if snap_b else None,
        # The frozen dataset record carries no terminal identity, so a family match
        # cannot be VERIFIED here — only recorded for a future comparison.
        "producer_family_match": "UNVERIFIED_NO_RECORDED_TERMINAL",
        "g06_mt5": G06_UNPROVEN,
        "grants_g06_mt5": False,
        "executable_open_vs_close_label_proof": False,
        "ohlcv_closure": "UNCHANGED",
    }


def _finalize(report: dict[str, Any]) -> dict[str, Any]:
    """Derive the G-06 tri-state and the proof flag from the verdict (D1, D3)."""
    verdict = report["verdict"]
    if verdict == VERDICT_OPEN:
        report["g06_mt5"] = G06_PROVEN
    elif verdict == VERDICT_CLOSE:
        report["g06_mt5"] = G06_CONTRADICTED
    else:
        report["g06_mt5"] = G06_UNPROVEN
    report["grants_g06_mt5"] = report["g06_mt5"] == G06_PROVEN
    report["executable_open_vs_close_label_proof"] = bool(
        verdict in (VERDICT_OPEN, VERDICT_CLOSE)
        and report["source_a"] == SOURCE_LIVE
        and report["source_b"] == SOURCE_LIVE
        and report["admitted_sha256_match"] is True
    )
    return report


def _staleness_reason(snap: FetchSnap, which: str) -> Optional[str]:
    """Amendment 9.1. One-directional: may only downgrade to INSUFFICIENT."""
    if snap.source != SOURCE_LIVE:
        return None  # synthetic fixtures carry no wall clock
    if snap.wall_clock_skew_seconds is None:
        return f"stale_feed_unmeasured_{which}"
    if abs(float(snap.wall_clock_skew_seconds)) > STALE_THRESHOLD_SECONDS:
        return f"stale_feed_{which}"
    return None


def classify_label_pair(
    snap_a: FetchSnap,
    snap_b: FetchSnap,
    *,
    margin_seconds: int = MARGIN_SECONDS,
    repo_root: Optional[Path] = None,
    verify_admitted: bool = True,
) -> dict[str, Any]:
    """Score two snapshots. First matching frozen rule wins (prereg section 5)."""
    report = _base_report(
        snap_a, snap_b, repo_root=repo_root, verify_admitted=verify_admitted
    )
    if snap_a.clock != "mt5_tick" or snap_b.clock != "mt5_tick":
        report["reason"] = "clock=unavailable"
        return _finalize(report)
    last_a = _last(snap_a)
    if last_a is None:
        report["reason"] = "empty_rates_a"
        return _finalize(report)
    if not snap_b.bars:
        report["reason"] = "empty_rates_b"
        return _finalize(report)
    for snap, which in ((snap_a, "a"), (snap_b, "b")):
        stale = _staleness_reason(snap, which)
        if stale:
            report["reason"] = stale
            return _finalize(report)

    t_a = _aware_utc(snap_a.fetched_at)
    t_b = _aware_utc(snap_b.fetched_at)
    t_bar = _aware_utc(last_a.timestamp)
    delta = (t_a - t_bar).total_seconds()
    report["delta_seconds_a"] = delta
    bar_s = float(LATTICE_SECONDS)
    margin = float(margin_seconds)
    open_cand = margin < delta < (bar_s - margin)
    close_cand = margin < (-delta) < (bar_s - margin)
    if not open_cand and not close_cand:
        report["reason"] = "not_mid_interval"
        return _finalize(report)
    report["candidate"] = "open" if open_cand else "close"

    if open_cand:
        need_b = t_bar + timedelta(seconds=bar_s + margin)
    else:
        need_b = t_bar + timedelta(seconds=margin)
    if t_b < need_b:
        report["reason"] = "not_post_close"
        return _finalize(report)

    if not on_m15_lattice(last_a.timestamp):
        report["verdict"] = VERDICT_OTHER
        report["reason"] = "t_not_on_m15_lattice"
        return _finalize(report)

    bar_b = _find(snap_b, last_a.timestamp)
    if bar_b is None:
        report["verdict"] = VERDICT_OTHER
        report["reason"] = "t_missing_in_b"
        return _finalize(report)
    if not _mutated(last_a, bar_b):
        report["reason"] = "no_mutation"
        return _finalize(report)

    if open_cand:
        report["verdict"] = VERDICT_OPEN
        report["reason"] = "open_candidate_and_mutation"
        return _finalize(report)
    report["verdict"] = VERDICT_CLOSE
    report["reason"] = "close_candidate_and_mutation"
    return _finalize(report)


def snap_from_dict(raw: dict) -> FetchSnap:
    fetched = datetime.fromisoformat(raw["fetched_at"])
    bars = []
    for row in raw["bars"]:
        ts = datetime.fromisoformat(row["timestamp"])
        bars.append(
            BarSnap(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
        )
    skew = raw.get("wall_clock_skew_seconds")
    return FetchSnap(
        fetched_at=fetched,
        symbol=str(raw.get("symbol") or "XAUUSD"),
        bars=tuple(bars),
        clock=str(raw.get("clock") or "mt5_tick"),
        # Fail-closed: a file that does not declare a live source is synthetic.
        source=str(raw.get("source") or SOURCE_SYNTHETIC),
        clock_basis=str(raw.get("clock_basis") or CLOCK_BASIS),
        terminal=raw.get("terminal"),
        wall_clock_skew_seconds=None if skew is None else float(skew),
    )


def snap_to_dict(snap: FetchSnap) -> dict:
    def _iso(ts: datetime) -> str:
        # NOTE (F-066): the "+00:00" suffix is NOMINAL. MT5 epochs are broker-server
        # seconds; clock_basis names the real basis.
        return _aware_utc(ts).isoformat()

    return {
        "fetched_at": _iso(snap.fetched_at),
        "symbol": snap.symbol,
        "clock": snap.clock,
        "clock_basis": snap.clock_basis,
        "source": snap.source,
        "terminal": snap.terminal,
        "wall_clock_skew_seconds": snap.wall_clock_skew_seconds,
        "bars": [
            {
                "timestamp": _iso(b.timestamp),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in snap.bars
        ],
    }


def capture_mt5_snapshot(
    symbol: str = "XAUUSD", n_bars: int = 5, sync_retries: int = 4
) -> FetchSnap:
    """Live capture. Fail closed if MetaTrader5 or the tick clock is missing.

    The first ``copy_rates_from_pos`` after ``symbol_select`` can return a COLD
    CACHE whose newest bar is hours old (observed 2026-09-02: 5099s behind a live
    tick). That scores ``not_mid_interval`` — a correct rejection, but
    indistinguishable from a closed market. Retry until the returned window
    reaches the live tick.
    """
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise LabelProbeError(
            f"MT5_UNAVAILABLE: MetaTrader5 import failed: {exc}"
        ) from exc
    if not mt5.initialize():
        err = mt5.last_error()
        raise LabelProbeError(f"MT5_UNAVAILABLE: initialize failed: {err}")
    try:
        if not mt5.symbol_select(symbol, True):
            raise LabelProbeError(
                f"MT5_UNAVAILABLE: symbol_select {symbol}: {mt5.last_error()}"
            )
        ti = mt5.terminal_info()
        ai = mt5.account_info()
        terminal = {
            "company": getattr(ti, "company", None) if ti else None,
            "name": getattr(ti, "name", None) if ti else None,
            "build": getattr(ti, "build", None) if ti else None,
            "connected": getattr(ti, "connected", None) if ti else None,
            # server identifies the broker feed; the account LOGIN is deliberately
            # not recorded — nothing in the inference needs it.
            "server": getattr(ai, "server", None) if ai else None,
        }

        tick = None
        rates = None
        for _ in range(max(1, sync_retries)):
            tick = mt5.symbol_info_tick(symbol)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, n_bars)
            if tick is None or not getattr(tick, "time", None):
                time.sleep(2)
                continue
            if rates is None or len(rates) == 0:
                time.sleep(2)
                continue
            gap = int(tick.time) - int(rates[-1]["time"])
            if 0 <= gap < LATTICE_SECONDS:
                break
            time.sleep(2)

        if tick is None or not getattr(tick, "time", None):
            raise LabelProbeError("clock=unavailable: symbol_info_tick.time missing")
        if rates is None or len(rates) == 0:
            raise LabelProbeError("empty_rates")

        wall_now = datetime.now(timezone.utc)
        fetched_at = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
        bars = []
        for r in rates:
            ts = datetime.fromtimestamp(int(r["time"]), tz=timezone.utc)
            bars.append(
                BarSnap(
                    timestamp=ts,
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=float(r["tick_volume"]),
                )
            )
        bars.sort(key=lambda b: b.timestamp)
        return FetchSnap(
            fetched_at=fetched_at,
            symbol=symbol,
            bars=tuple(bars),
            clock="mt5_tick",
            source=SOURCE_LIVE,
            clock_basis=CLOCK_BASIS,
            terminal=terminal,
            wall_clock_skew_seconds=(wall_now - fetched_at).total_seconds(),
        )
    finally:
        mt5.shutdown()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


DEFAULT_EVIDENCE_DIR = "docs/research-readiness/bc2_open_close"


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="BC-2 open-vs-close label probe (preregistered; live MT5 optional)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture", help="Write one MT5 snapshot JSON.")
    cap.add_argument("--symbol", default="XAUUSD")
    cap.add_argument("--out", required=True)
    sc = sub.add_parser("score", help="Score two snapshot JSON files.")
    sc.add_argument("--a", required=True)
    sc.add_argument("--b", required=True)
    sc.add_argument("--out", default=f"{DEFAULT_EVIDENCE_DIR}/score.json")
    sc.add_argument(
        "--require-verdict",
        action="store_true",
        help="Exit 1 unless the pair scores OPEN or CLOSE (default: 0 on any scored pair).",
    )
    args = p.parse_args(argv)

    if args.cmd == "capture":
        try:
            snap = capture_mt5_snapshot(args.symbol)
        except LabelProbeError as exc:
            payload = {"ok": False, "error": str(exc)}
            _write_json(Path(args.out), payload)
            print(json.dumps(payload))
            return 2
        payload = {"ok": True, **snap_to_dict(snap)}
        _write_json(Path(args.out), payload)
        print(
            json.dumps(
                {
                    "ok": True,
                    "out": args.out,
                    "fetched_at": payload["fetched_at"],
                    "last_bar": (
                        payload["bars"][-1]["timestamp"] if payload["bars"] else None
                    ),
                    "wall_clock_skew_seconds": payload["wall_clock_skew_seconds"],
                }
            )
        )
        return 0

    raw_a = json.loads(Path(args.a).read_text(encoding="utf-8"))
    raw_b = json.loads(Path(args.b).read_text(encoding="utf-8"))
    if raw_a.get("ok") is False or raw_b.get("ok") is False:
        report = _finalize(_base_report())
        report["reason"] = "snapshot_capture_failed"
    else:
        report = classify_label_pair(snap_from_dict(raw_a), snap_from_dict(raw_b))
    if args.out:
        _write_json(Path(args.out), report)
    print(json.dumps(report, indent=2))
    if args.require_verdict and report["verdict"] not in (VERDICT_OPEN, VERDICT_CLOSE):
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
