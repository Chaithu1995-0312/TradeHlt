"""BC-4 residual attribution: what explains tick_volume vs len(copy_ticks_range)?

Rules: docs/research/preregistration-bc4-residual-attribution.md
Probe id: BC4-RESIDUAL-ATTRIBUTION-XAUUSD-MT5-V1

F-099 measured a consistent 0.548%-0.676% gap (diffs 45/46/52/31 on tick_volumes
6654/7478/9483/4924). This module decomposes that gap WITHIN the returned tick stream.

It cannot be decomposed ACROSS tick classes: COPY_TICKS_INFO == COPY_TICKS_ALL == 9535 and
COPY_TICKS_TRADE == 0 on the 22:45 bar (BC-4 Phase 0). Only one class is populated.

The candidate list below is FROZEN. No candidate may be added, tuned, or parameterised after
seeing discovery output; exact integer equality is required, with no tolerance band. Zero
survivors is UNATTRIBUTED -- a real outcome, not a prompt to widen the list.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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

PREREG = "docs/research/preregistration-bc4-residual-attribution.md"
PROBE_ID = "BC4-RESIDUAL-ATTRIBUTION-XAUUSD-MT5-V1"
DEFAULT_EVIDENCE_DIR = "docs/research-readiness/bc4_residual_attribution"

BAR_MINUTES = 15
BAR_SECONDS = BAR_MINUTES * 60
FRESHNESS_SECONDS = 3600  # F-099 Phase 0 bound: deeper copy_ticks_range calls hang

# MT5 tick flag bits (verified present on build 6140 via dir(MetaTrader5)).
TICK_FLAG_BID = 0x02
TICK_FLAG_ASK = 0x04
TICK_FLAG_LAST = 0x08
TICK_FLAG_VOLUME = 0x10

OUTCOME_ATTRIBUTED = "ATTRIBUTED"
OUTCOME_AMBIGUOUS = "AMBIGUOUS"
OUTCOME_UNATTRIBUTED = "UNATTRIBUTED"
OUTCOME_PENDING_HOLDOUT = "PENDING_HOLDOUT"
OUTCOME_INSUFFICIENT = "INSUFFICIENT"


# ── the frozen candidate counters ──────────────────────────────────────────────
# Each takes (ticks, bar_start_epoch) and returns an int count.
# ticks: list of dicts with keys time_msc, bid, ask, last, flags.


def _c0_len(ticks: list[dict], t0: int) -> int:
    """The V1 rule: raw len(). Known to overshoot; kept as the reference."""
    return len(ticks)


def _exclusive_upper(ticks: list[dict], t0: int) -> list[dict]:
    end_msc = (t0 + BAR_SECONDS) * 1000
    return [t for t in ticks if int(t["time_msc"]) < end_msc]


def _c1_exclusive_upper(ticks: list[dict], t0: int) -> int:
    """Tests whether copy_ticks_range's upper bound is inclusive."""
    return len(_exclusive_upper(ticks, t0))


def _c2_dedup_exact(ticks: list[dict], t0: int) -> int:
    """C1 + drop exact duplicates on (time_msc, bid, ask, last, flags)."""
    seen = set()
    n = 0
    for t in _exclusive_upper(ticks, t0):
        key = (int(t["time_msc"]), t["bid"], t["ask"], t["last"], int(t["flags"]))
        if key not in seen:
            seen.add(key)
            n += 1
    return n


def _price_changed(ticks: list[dict]) -> int:
    n = 0
    prev = None
    for t in ticks:
        cur = (t["bid"], t["ask"])
        if prev is None or cur != prev:
            n += 1
        prev = cur
    return n


def _c3_price_changed(ticks: list[dict], t0: int) -> int:
    """Ticks where (bid, ask) differs from the previous tick's (bid, ask)."""
    return _price_changed(ticks)


def _c4_flag_bid_or_ask(ticks: list[dict], t0: int) -> int:
    return sum(1 for t in ticks if int(t["flags"]) & (TICK_FLAG_BID | TICK_FLAG_ASK))


def _c5_flag_last(ticks: list[dict], t0: int) -> int:
    return sum(1 for t in ticks if int(t["flags"]) & TICK_FLAG_LAST)


def _c6_distinct_time_msc(ticks: list[dict], t0: int) -> int:
    return len({int(t["time_msc"]) for t in ticks})


def _c7_excl_and_price_changed(ticks: list[dict], t0: int) -> int:
    return _price_changed(_exclusive_upper(ticks, t0))


def _c8_excl_and_flag_bid_ask(ticks: list[dict], t0: int) -> int:
    return sum(
        1
        for t in _exclusive_upper(ticks, t0)
        if int(t["flags"]) & (TICK_FLAG_BID | TICK_FLAG_ASK)
    )


CANDIDATES: dict[str, Callable[[list[dict], int], int]] = {
    "C0_len": _c0_len,
    "C1_exclusive_upper": _c1_exclusive_upper,
    "C2_dedup_exact": _c2_dedup_exact,
    "C3_price_changed": _c3_price_changed,
    "C4_flag_bid_or_ask": _c4_flag_bid_or_ask,
    "C5_flag_last": _c5_flag_last,
    "C6_distinct_time_msc": _c6_distinct_time_msc,
    "C7_excl_and_price_changed": _c7_excl_and_price_changed,
    "C8_excl_and_flag_bid_ask": _c8_excl_and_flag_bid_ask,
}
FROZEN_CANDIDATE_IDS = tuple(CANDIDATES)


def score_bar(ticks: list[dict], bar_start_epoch: int) -> dict[str, int]:
    """Every frozen candidate's count for one bar. No selection happens here."""
    return {cid: fn(ticks, bar_start_epoch) for cid, fn in CANDIDATES.items()}


def survivors(bars: list[dict]) -> list[str]:
    """Candidates matching tick_volume EXACTLY on every bar. No tolerance band."""
    if not bars:
        return []
    out = []
    for cid in FROZEN_CANDIDATE_IDS:
        if all(b["candidates"].get(cid) == b["tick_volume"] for b in bars):
            out.append(cid)
    return out


def attribute(
    discovery_bars: list[dict], holdout_bars: Optional[list[dict]] = None
) -> dict[str, Any]:
    """Apply the frozen outcome rules. Discovery narrows; holdout confirms."""
    result: dict[str, Any] = {
        "frozen_candidates": list(FROZEN_CANDIDATE_IDS),
        "n_discovery_bars": len(discovery_bars),
        "n_holdout_bars": 0 if not holdout_bars else len(holdout_bars),
        "discovery_survivors": [],
        "holdout_survivors": [],
        "winner": None,
        "outcome": OUTCOME_INSUFFICIENT,
    }
    if not discovery_bars:
        result["reason"] = "no_discovery_bars"
        return result

    disc = survivors(discovery_bars)
    result["discovery_survivors"] = disc

    if not disc:
        result["outcome"] = OUTCOME_UNATTRIBUTED
        result["reason"] = "no_candidate_matches_every_discovery_bar"
        return result

    if not holdout_bars:
        result["outcome"] = OUTCOME_PENDING_HOLDOUT
        result["reason"] = "discovery_survivors_await_independent_holdout"
        return result

    hold = [c for c in survivors(holdout_bars) if c in disc]
    result["holdout_survivors"] = hold
    if len(hold) == 1:
        result["outcome"] = OUTCOME_ATTRIBUTED
        result["winner"] = hold[0]
        result["reason"] = "unique_candidate_matches_discovery_and_holdout"
    elif len(hold) > 1:
        result["outcome"] = OUTCOME_AMBIGUOUS
        result["reason"] = "holdout_could_not_separate_survivors"
    else:
        result["outcome"] = OUTCOME_UNATTRIBUTED
        result["reason"] = "discovery_survivors_failed_holdout"
    return result


# ── V2: the single discovery-generated candidate (prereg section 8.3) ──────────
# Kept OUT of CANDIDATES so V1's frozen list -- and its UNATTRIBUTED outcome -- stay
# byte-identical and reproducible. V1 tested BID|ASK (C4) and failed because that also
# counts bare-ASK ticks; the surviving hypothesis is BID only, one bit different.
V2_CANDIDATE_ID = "C9_flag_bid"
V2_MIN_HOLDOUT_BARS = 3

OUTCOME_ATTRIBUTED_V2 = "ATTRIBUTED_V2"
OUTCOME_UNATTRIBUTED_V2 = "UNATTRIBUTED_V2"


def c9_flag_bid(ticks: list[dict], t0: int) -> int:
    """count(ticks where flags & TICK_FLAG_BID)."""
    return sum(1 for t in ticks if int(t["flags"]) & TICK_FLAG_BID)


def score_v2(holdout_bars: list[dict]) -> dict[str, Any]:
    """Test C9_flag_bid on holdout bars ONLY. No candidate search, no tolerance band."""
    result: dict[str, Any] = {
        "v2_candidate": V2_CANDIDATE_ID,
        "v2_min_holdout_bars": V2_MIN_HOLDOUT_BARS,
        "v2_n_holdout_bars": len(holdout_bars),
        "v2_table": [],
        "v2_outcome": OUTCOME_PENDING_HOLDOUT,
    }
    for b in holdout_bars:
        got = b["candidates"].get(V2_CANDIDATE_ID)
        result["v2_table"].append(
            {
                "T": b["T"],
                "tick_volume": b["tick_volume"],
                V2_CANDIDATE_ID: got,
                "exact": got == b["tick_volume"],
            }
        )
    if len(holdout_bars) < V2_MIN_HOLDOUT_BARS:
        result["v2_reason"] = "below_min_holdout_bars"
        return result
    if all(row["exact"] for row in result["v2_table"]):
        result["v2_outcome"] = OUTCOME_ATTRIBUTED_V2
        result["v2_reason"] = "exact_match_on_every_holdout_bar"
    else:
        result["v2_outcome"] = OUTCOME_UNATTRIBUTED_V2
        result["v2_reason"] = "holdout_mismatch_discovery_pattern_did_not_generalise"
    return result


# ── live capture ───────────────────────────────────────────────────────────────
def capture_tick_bars(
    symbol: str = "XAUUSD", n_recent_bars: int = 4, raw_sample: int = 40
) -> ProbeSnapshot:
    """Capture recently-closed bars with their FULL tick arrays scored per candidate.

    Candidate counts are computed here (deterministically, from the frozen list) rather
    than dumping ~9,500 ticks/bar into the evidence artifact. A small raw_sample is kept
    per bar for inspection.
    """
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ProbeError(f"MT5_UNAVAILABLE: import failed: {exc}") from exc
    if not mt5.initialize():
        raise ProbeError(f"MT5_UNAVAILABLE: initialize failed: {mt5.last_error()}")
    try:
        if not mt5.symbol_select(symbol, True):
            raise ProbeError(f"MT5_UNAVAILABLE: symbol_select: {mt5.last_error()}")
        terminal = terminal_provenance(mt5)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None or not getattr(tick, "time", None):
            raise ProbeError("clock=unavailable: symbol_info_tick.time missing")
        fetched_at = datetime.fromtimestamp(int(tick.time), tz=timezone.utc)
        wall_now = datetime.now(timezone.utc)

        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, n_recent_bars + 2)
        if rates is None or len(rates) == 0:
            raise ProbeError("empty_rates")
        closed = [r for r in rates if int(r["time"]) + BAR_SECONDS <= int(tick.time)]

        bars: list[dict] = []
        for r in closed[-n_recent_bars:]:
            t0 = int(r["time"])
            T = datetime.fromtimestamp(t0, tz=timezone.utc)
            close_t = T + timedelta(minutes=BAR_MINUTES)
            # same nominal clock basis on both sides (F-066)
            age = (fetched_at - close_t).total_seconds()
            if age < 0 or age > FRESHNESS_SECONDS:
                continue
            raw = mt5.copy_ticks_range(symbol, T, close_t, mt5.COPY_TICKS_ALL)
            if raw is None or len(raw) == 0:
                continue
            ticks = [
                {
                    "time_msc": int(x["time_msc"]),
                    "bid": float(x["bid"]),
                    "ask": float(x["ask"]),
                    "last": float(x["last"]),
                    "flags": int(x["flags"]),
                }
                for x in raw
            ]
            bars.append(
                {
                    "T": T.isoformat(),
                    "bar_start_epoch": t0,
                    "tick_volume": int(r["tick_volume"]),
                    "real_volume": int(r["real_volume"]),
                    "n_raw_ticks": len(ticks),
                    "candidates": {
                        **score_bar(ticks, t0),
                        V2_CANDIDATE_ID: c9_flag_bid(ticks, t0),
                    },
                    "flag_histogram": _flag_histogram(ticks),
                    "raw_sample": ticks[:raw_sample],
                }
            )

        return ProbeSnapshot(
            fetched_at=fetched_at,
            symbol=symbol,
            source=SOURCE_LIVE,
            clock_basis=CLOCK_BASIS,
            terminal=terminal,
            wall_clock_skew_seconds=(wall_now - fetched_at).total_seconds(),
            payload={"bars": bars},
        )
    finally:
        mt5.shutdown()


def _flag_histogram(ticks: list[dict]) -> dict[str, int]:
    hist: dict[str, int] = {}
    for t in ticks:
        key = str(int(t["flags"]))
        hist[key] = hist.get(key, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))


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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def build_report(
    disc: ProbeSnapshot,
    hold: Optional[ProbeSnapshot] = None,
    *,
    repo_root: Optional[Path] = None,
    verify_admitted: bool = True,
) -> dict[str, Any]:
    report = base_report(
        PROBE_ID,
        snap_a=disc,
        snap_b=hold,
        prereg=PREREG,
        repo_root=repo_root,
        verify_admitted=verify_admitted,
    )
    stale = staleness_reason(disc, "a") or (staleness_reason(hold, "b") if hold else None)
    if stale:
        report.update({"outcome": OUTCOME_INSUFFICIENT, "reason": stale})
        return report

    disc_bars = disc.payload.get("bars", [])
    hold_bars = hold.payload.get("bars", []) if hold else None
    report.update(attribute(disc_bars, hold_bars))
    report["discovery_table"] = [
        {
            "T": b["T"],
            "tick_volume": b["tick_volume"],
            "candidates": b["candidates"],
            "flag_histogram": b.get("flag_histogram"),
        }
        for b in disc_bars
    ]
    if hold_bars:
        report["holdout_table"] = [
            {"T": b["T"], "tick_volume": b["tick_volume"], "candidates": b["candidates"]}
            for b in hold_bars
        ]
    if hold_bars:
        report.update(score_v2(hold_bars))
    report["flag_vocabulary_discovery"] = sorted(
        {k for b in disc_bars for k in (b.get("flag_histogram") or {})}, key=int
    )
    report["flag_vocabulary_holdout"] = sorted(
        {k for b in (hold_bars or []) for k in (b.get("flag_histogram") or {})}, key=int
    )
    report["discovery_fetched_at"] = aware_utc(disc.fetched_at).isoformat()
    report["holdout_fetched_at"] = (
        aware_utc(hold.fetched_at).isoformat() if hold else None
    )
    # An ATTRIBUTED outcome is citable only from independent LIVE captures.
    report["independent_captures"] = bool(
        hold is not None
        and disc.source == SOURCE_LIVE
        and hold.source == SOURCE_LIVE
        and aware_utc(disc.fetched_at) != aware_utc(hold.fetched_at)
    )
    return report


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description="BC-4 residual attribution probe.")
    sub = p.add_subparsers(dest="cmd", required=True)
    cap = sub.add_parser("capture", help="Capture one set of tick-scored bars.")
    cap.add_argument("--symbol", default="XAUUSD")
    cap.add_argument("--out", required=True)
    sc = sub.add_parser("attribute", help="Apply the frozen outcome rules.")
    sc.add_argument("--discovery", required=True)
    sc.add_argument("--holdout", default="")
    sc.add_argument("--out", default=f"{DEFAULT_EVIDENCE_DIR}/attribution.json")
    args = p.parse_args(argv)

    if args.cmd == "capture":
        try:
            snap = capture_tick_bars(args.symbol)
        except ProbeError as exc:
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
                    "n_bars": len(snap.payload.get("bars", [])),
                }
            )
        )
        return 0

    disc = snap_from_dict(json.loads(Path(args.discovery).read_text(encoding="utf-8")))
    hold = None
    if args.holdout:
        hold = snap_from_dict(json.loads(Path(args.holdout).read_text(encoding="utf-8")))
    report = build_report(disc, hold)
    _write_json(Path(args.out), report)
    print(json.dumps({k: v for k, v in report.items() if k != "discovery_table"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
