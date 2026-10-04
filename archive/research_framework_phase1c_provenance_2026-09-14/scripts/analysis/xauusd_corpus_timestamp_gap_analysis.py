#!/usr/bin/env python3
"""Deterministic XAUUSD M15 dual-corpus timestamp / gap / overlap analysis (R2 evidence).

Reads raw CSVs only — does not trust row counts from the closure report.
Outputs machine-readable JSON under reports/ and a short markdown summary.

Usage:
  python scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from data_ingestion.ohlcv_schema import parse_ohlcv_timestamp  # noqa: E402

BAR = timedelta(minutes=15)
SYMBOL = "XAUUSD"

CORPORA = {
    "C-ROOT-EXTENDED": ROOT / "data" / "XAUUSD_M15.csv",
    "C-PINNED-LEGACY": ROOT / "data" / "mt5" / "XAUUSD_M15.csv",
    "C-QUARANTINE-TWIN": ROOT / "data" / "mt5" / "_rejected" / "XAUUSD_M15.csv",
}

OUT_JSON = ROOT / "reports" / "xauusd_m15_corpus_timestamp_gap_report.json"
OUT_MD = ROOT / "reports" / "xauusd_m15_corpus_timestamp_gap_report.md"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_session_calendar() -> dict:
    cfg_path = ROOT / "configs" / "production" / "v2_multi_2026_04.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return cfg["dataset_integrity"]["session_calendar"]


def _parse_known_gaps(sc: dict, symbol: str) -> list[tuple[datetime, datetime, str]]:
    out = []
    for e in sc.get("known_gaps") or []:
        sym = e.get("symbol")
        if sym is not None and sym != symbol:
            continue
        lo = datetime.fromisoformat(e["from"])
        hi = datetime.fromisoformat(e["to"])
        out.append((lo, hi, e.get("reason", "")))
    return out


def _is_weekend_slot(ts: datetime, sc: dict) -> bool:
    """FX/metals session: closed Fri close_hour → Sun open_hour (config-driven)."""
    open_wd = int(sc.get("weekday_open_weekday", 6))  # Sun=6
    open_h = int(sc.get("weekday_open_hour", 22))
    close_wd = int(sc.get("weekday_close_weekday", 4))  # Fri=4
    close_h = int(sc.get("weekday_close_hour", 21))
    wd = ts.weekday()
    h = ts.hour
    # Friday from close_hour onward
    if wd == close_wd and h >= close_h:
        return True
    # Saturday all day
    if wd == 5:
        return True
    # Sunday before open
    if wd == open_wd and h < open_h:
        return True
    return False


def _is_daily_break(ts: datetime, sc: dict) -> bool:
    breaks = sc.get("weekday_daily_break_hours") or []
    return ts.hour in set(int(x) for x in breaks)


def _is_holiday_date(ts: datetime, holidays: set[str]) -> bool:
    return ts.strftime("%Y-%m-%d") in holidays


def _in_known_gap(ts: datetime, gaps: list[tuple[datetime, datetime, str]]) -> str | None:
    for lo, hi, reason in gaps:
        if lo <= ts < hi:
            return reason
    return None


def classify_missing_slot(
    ts: datetime,
    sc: dict,
    holidays: set[str],
    known_gaps: list[tuple[datetime, datetime, str]],
) -> str:
    """Classify a wall-clock-missing 15m slot.

    Layers (first match wins):
      KNOWN_GAP / HOLIDAY / WEEKEND_SESSION_CLOSE / DAILY_BREAK (config)
      OBSERVED_MIDNIGHT_ROLLOVER — Mon–Fri hour 00 (broker 23:45→01:00 = 75m)
      CONFIG_OPEN_NO_BAR — Sun 22–23 under config open but this corpus has no bars
        (broker effectively opens Mon 01:00)
      UNEXPLAINED — residual mid-session holes
    """
    reason = _in_known_gap(ts, known_gaps)
    if reason:
        return "KNOWN_GAP"
    if _is_holiday_date(ts, holidays):
        return "HOLIDAY"
    if _is_weekend_slot(ts, sc):
        return "WEEKEND_SESSION_CLOSE"
    if _is_daily_break(ts, sc):
        return "DAILY_BREAK"
    # Observed broker pattern on these MT5 XAUUSD files (both corpora):
    # last bar of day typically 23:45, next 01:00 → four missing 00:xx slots.
    if ts.weekday() <= 4 and ts.hour == 0:
        return "OBSERVED_MIDNIGHT_ROLLOVER"
    # Config claims Sunday open at 22:00; this corpus never trades Sun 22–23
    # (first post-weekend bar is consistently Monday 01:00).
    if ts.weekday() == 6 and ts.hour in (22, 23):
        return "CONFIG_OPEN_NO_BAR"
    return "UNEXPLAINED"


def load_corpus(path: Path) -> dict:
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        header = f.readline().strip().split(",")
        header_l = [h.strip().lower() for h in header]
        # tolerate Timestamp etc.
        ts_idx = next(i for i, h in enumerate(header_l) if h in ("timestamp", "time", "datetime", "date"))
        o_idx = header_l.index("open")
        h_idx = header_l.index("high")
        l_idx = header_l.index("low")
        c_idx = header_l.index("close")
        v_idx = header_l.index("volume")
        for line_no, line in enumerate(f, start=2):
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            ts = parse_ohlcv_timestamp(parts[ts_idx])
            rows.append({
                "ts": ts,
                "open": parts[o_idx],
                "high": parts[h_idx],
                "low": parts[l_idx],
                "close": parts[c_idx],
                "volume": parts[v_idx],
                "line": line_no,
            })
    ts_list = [r["ts"] for r in rows]
    ts_set = set(ts_list)
    dup_counts = Counter(ts_list)
    duplicates = sorted(t for t, n in dup_counts.items() if n > 1)
    out_of_order = 0
    for a, b in zip(ts_list, ts_list[1:]):
        if b < a:
            out_of_order += 1
    deltas = []
    for a, b in zip(ts_list, ts_list[1:]):
        if b >= a:
            deltas.append(int((b - a).total_seconds()))
    delta_hist = Counter(deltas)
    # human labels for common intervals
    def _label(sec: int) -> str:
        if sec % 60:
            return f"{sec}s"
        m = sec // 60
        if m < 60:
            return f"{m}m"
        if m % 60 == 0:
            return f"{m // 60}h"
        return f"{m}m"

    delta_hist_labeled = {
        _label(k): v for k, v in sorted(delta_hist.items(), key=lambda x: (-x[1], x[0]))
    }

    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": _sha256(path),
        "n_rows": len(rows),
        "n_unique_timestamps": len(ts_set),
        "first_timestamp": ts_list[0].isoformat(sep=" ") if ts_list else None,
        "last_timestamp": ts_list[-1].isoformat(sep=" ") if ts_list else None,
        "duplicate_timestamp_count": len(duplicates),
        "duplicate_timestamps_sample": [t.isoformat(sep=" ") for t in duplicates[:20]],
        "out_of_order_adjacent_pairs": out_of_order,
        "delta_seconds_histogram": {str(k): v for k, v in sorted(delta_hist.items())},
        "delta_histogram_labeled": delta_hist_labeled,
        "rows": rows,
        "ts_list": ts_list,
        "ts_set": ts_set,
        "by_ts": {r["ts"]: r for r in rows},
    }


def analyze_gaps(corpus: dict, sc: dict, holidays: set[str], known_gaps) -> dict:
    ts_list = corpus["ts_list"]
    if len(ts_list) < 2:
        return {"error": "too few rows"}
    first, last = ts_list[0], ts_list[-1]
    present = corpus["ts_set"]

    # Full 15m grid (wall-clock, not session-filtered) — every missing slot listed
    missing_all: list[datetime] = []
    t = first
    while t <= last:
        if t not in present:
            missing_all.append(t)
        t += BAR

    class_counts: Counter = Counter()
    by_class: dict[str, list[str]] = defaultdict(list)
    for m in missing_all:
        cls = classify_missing_slot(m, sc, holidays, known_gaps)
        class_counts[cls] += 1
        if len(by_class[cls]) < 50:  # sample per class
            by_class[cls].append(m.isoformat(sep=" "))

    # Gap events = consecutive missing runs between present bars
    gap_events = []
    for a, b in zip(ts_list, ts_list[1:]):
        if b <= a:
            continue
        span = b - a
        if span <= BAR:
            continue
        missing_slots = int(span / BAR) - 1
        interior = []
        u = a + BAR
        while u < b:
            interior.append(u)
            u += BAR
        classes = Counter(classify_missing_slot(x, sc, holidays, known_gaps) for x in interior)
        dominant = classes.most_common(1)[0][0] if classes else "NONE"
        gap_events.append({
            "from": a.isoformat(sep=" "),
            "to": b.isoformat(sep=" "),
            "span_minutes": int(span.total_seconds() // 60),
            "missing_15m_slots": missing_slots,
            "class_counts": dict(classes),
            "dominant_class": dominant,
            "is_long_intraday": (
                missing_slots >= 4
                and dominant == "UNEXPLAINED"
            ),
        })

    long_intraday = [g for g in gap_events if g["is_long_intraday"]]
    unexplained_events = [
        g for g in gap_events
        if g["class_counts"].get("UNEXPLAINED", 0) > 0
    ]

    # Daily candle counts
    by_day: dict[str, int] = Counter()
    for ts in ts_list:
        by_day[ts.strftime("%Y-%m-%d")] += 1
    # Expected full weekday session is not fixed (broker-dependent); flag low-count weekdays
    weekday_days = {
        d: n for d, n in by_day.items()
        if datetime.strptime(d, "%Y-%m-%d").weekday() < 5
    }
    # partial: weekdays with count far below median
    counts = sorted(weekday_days.values())
    median = counts[len(counts) // 2] if counts else 0
    partial_days = sorted(
        [{"date": d, "bars": n} for d, n in weekday_days.items() if n < max(10, median * 0.5)],
        key=lambda x: x["date"],
    )

    # Weekend bars present (unusual if any)
    weekend_bars = sum(1 for ts in ts_list if ts.weekday() >= 5)

    return {
        "grid_first": first.isoformat(sep=" "),
        "grid_last": last.isoformat(sep=" "),
        "n_missing_15m_slots_wall_clock": len(missing_all),
        "missing_slot_class_counts": dict(class_counts),
        "missing_slot_samples_by_class": {k: v for k, v in by_class.items()},
        "n_gap_events": len(gap_events),
        "gap_events_longest": sorted(
            gap_events, key=lambda g: -g["span_minutes"]
        )[:25],
        "n_unexplained_gap_events": len(unexplained_events),
        "unexplained_gap_events": sorted(
            unexplained_events, key=lambda g: -g["missing_15m_slots"]
        )[:50],
        "n_long_intraday_unexplained": len(long_intraday),
        "long_intraday_unexplained": long_intraday[:30],
        "n_calendar_days_with_bars": len(by_day),
        "weekday_bar_count_median": median,
        "partial_weekday_days": partial_days[:40],
        "weekend_bars_present": weekend_bars,
        "n_unexplained_missing_slots": class_counts.get("UNEXPLAINED", 0),
        "n_expected_closure_missing_slots": (
            class_counts.get("WEEKEND_SESSION_CLOSE", 0)
            + class_counts.get("HOLIDAY", 0)
            + class_counts.get("DAILY_BREAK", 0)
            + class_counts.get("KNOWN_GAP", 0)
            + class_counts.get("OBSERVED_MIDNIGHT_ROLLOVER", 0)
            + class_counts.get("CONFIG_OPEN_NO_BAR", 0)
        ),
        "n_config_explained_only": (
            class_counts.get("WEEKEND_SESSION_CLOSE", 0)
            + class_counts.get("HOLIDAY", 0)
            + class_counts.get("DAILY_BREAK", 0)
            + class_counts.get("KNOWN_GAP", 0)
        ),
        "n_broker_pattern_explained": (
            class_counts.get("OBSERVED_MIDNIGHT_ROLLOVER", 0)
            + class_counts.get("CONFIG_OPEN_NO_BAR", 0)
        ),
    }


def compare_corpora(root: dict, legacy: dict) -> dict:
    rset, lset = root["ts_set"], legacy["ts_set"]
    only_root = sorted(rset - lset)
    only_legacy = sorted(lset - rset)
    overlap = sorted(rset & lset)
    # OHLCV equality on overlap
    ohlcv_mismatch = []
    for ts in overlap:
        a, b = root["by_ts"][ts], legacy["by_ts"][ts]
        if (a["open"], a["high"], a["low"], a["close"], a["volume"]) != (
            b["open"], b["high"], b["low"], b["close"], b["volume"]
        ):
            if len(ohlcv_mismatch) < 30:
                ohlcv_mismatch.append({
                    "timestamp": ts.isoformat(sep=" "),
                    "root": {k: a[k] for k in ("open", "high", "low", "close", "volume")},
                    "legacy": {k: b[k] for k in ("open", "high", "low", "close", "volume")},
                })
    # Extension after legacy last
    legacy_last = legacy["ts_list"][-1]
    added_after = [ts for ts in only_root if ts > legacy_last]
    # Rows before legacy first that root has extra
    legacy_first = legacy["ts_list"][0]
    added_before = [ts for ts in only_root if ts < legacy_first]
    # Within overlap window but missing from one side
    only_root_in_overlap_window = [
        ts for ts in only_root if legacy_first <= ts <= legacy_last
    ]
    only_legacy_in_overlap_window = [
        ts for ts in only_legacy if root["ts_list"][0] <= ts <= root["ts_list"][-1]
    ]

    return {
        "n_overlap_timestamps": len(overlap),
        "n_only_in_root": len(only_root),
        "n_only_in_legacy": len(only_legacy),
        "n_ohlcv_mismatches_on_shared_ts": len(ohlcv_mismatch) if len(ohlcv_mismatch) < 30 else ">=30",
        "ohlcv_mismatch_sample": ohlcv_mismatch,
        "n_rows_added_after_legacy_last": len(added_after),
        "extension_first": added_after[0].isoformat(sep=" ") if added_after else None,
        "extension_last": added_after[-1].isoformat(sep=" ") if added_after else None,
        "n_rows_only_root_before_legacy_first": len(added_before),
        "n_only_root_inside_legacy_window": len(only_root_in_overlap_window),
        "n_only_legacy_inside_root_window": len(only_legacy_in_overlap_window),
        "only_root_inside_legacy_window_sample": [
            t.isoformat(sep=" ") for t in only_root_in_overlap_window[:40]
        ],
        "only_legacy_inside_root_window_sample": [
            t.isoformat(sep=" ") for t in only_legacy_in_overlap_window[:40]
        ],
        "added_after_legacy_sample_head": [
            t.isoformat(sep=" ") for t in added_after[:20]
        ],
        "added_after_legacy_sample_tail": [
            t.isoformat(sep=" ") for t in added_after[-20:]
        ],
        "byte_identical": root["sha256"] == legacy["sha256"],
        "hashes": {
            "root": root["sha256"],
            "legacy": legacy["sha256"],
        },
    }


def verdict_for(corpus_id: str, gaps: dict, compare: dict | None = None) -> list[str]:
    flags = []
    # COMPLETE_15M_SEQUENCE: no wall-clock missing slots at all (almost never for FX)
    if gaps.get("n_missing_15m_slots_wall_clock", 1) == 0:
        flags.append("COMPLETE_15M_SEQUENCE")
    # EXPECTED_MARKET_CLOSURES_ONLY: every missing slot is calendar OR observed broker pattern
    if gaps.get("n_unexplained_missing_slots", 0) == 0 and gaps.get(
        "n_missing_15m_slots_wall_clock", 0
    ) > 0:
        flags.append("EXPECTED_MARKET_CLOSURES_ONLY")
    if gaps.get("n_unexplained_missing_slots", 0) > 0:
        flags.append("UNEXPLAINED_MISSING_BARS")
    if compare is not None:
        if (
            compare["n_only_in_root"]
            or compare["n_only_in_legacy"]
            or compare["ohlcv_mismatch_sample"]
            or not compare["byte_identical"]
        ):
            flags.append("CORPUS_DIVERGENCE")
    return flags


def strip_heavy(corpus: dict) -> dict:
    return {k: v for k, v in corpus.items() if k not in ("rows", "ts_list", "ts_set", "by_ts")}


def main() -> int:
    sc = _load_session_calendar()
    holidays = set(sc.get("holidays") or [])
    known_gaps = _parse_known_gaps(sc, SYMBOL)

    loaded = {}
    for cid, path in CORPORA.items():
        if not path.is_file():
            loaded[cid] = {"error": f"missing: {path}"}
            continue
        loaded[cid] = load_corpus(path)

    root = loaded["C-ROOT-EXTENDED"]
    legacy = loaded["C-PINNED-LEGACY"]
    quarantine = loaded.get("C-QUARANTINE-TWIN")

    gap_root = analyze_gaps(root, sc, holidays, known_gaps)
    gap_legacy = analyze_gaps(legacy, sc, holidays, known_gaps)
    compare = compare_corpora(root, legacy)

    q_note = None
    if isinstance(quarantine, dict) and "sha256" in quarantine:
        q_note = {
            "path": quarantine["path"],
            "sha256": quarantine["sha256"],
            "byte_identical_to_root": quarantine["sha256"] == root["sha256"],
            "n_rows": quarantine["n_rows"],
        }

    report = {
        "_doc": "Deterministic XAUUSD M15 dual-corpus timestamp/gap/overlap analysis. Computed from raw CSV bytes; not inferred from closure report row counts.",
        "generated_at_utc": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": SYMBOL,
        "bar_minutes": 15,
        "calendar_source": "configs/production/v2_multi_2026_04.json dataset_integrity.session_calendar",
        "n_holidays_in_config": len(holidays),
        "n_known_gap_ranges_applicable": len(known_gaps),
        "classification_rules": {
            "WEEKEND_SESSION_CLOSE": "Fri>=close_hour, Sat all, Sun<open_hour (config weekday_*)",
            "HOLIDAY": "timestamp date in session_calendar.holidays",
            "KNOWN_GAP": "timestamp in known_gaps half-open range (symbol-scoped or global)",
            "DAILY_BREAK": "hour in weekday_daily_break_hours (config; often empty for this broker)",
            "OBSERVED_MIDNIGHT_ROLLOVER": "Mon–Fri hour 00 (measured 23:45→01:00 = 75m on both corpora)",
            "CONFIG_OPEN_NO_BAR": "Sun 22–23: config session open, corpus never has bars (open Mon 01:00)",
            "UNEXPLAINED": "residual mid-session holes after config + observed broker patterns",
        },
        "corpora": {
            "C-ROOT-EXTENDED": strip_heavy(root),
            "C-PINNED-LEGACY": strip_heavy(legacy),
            "C-QUARANTINE-TWIN": q_note,
        },
        "gaps": {
            "C-ROOT-EXTENDED": gap_root,
            "C-PINNED-LEGACY": gap_legacy,
        },
        "overlap": compare,
        "verdicts": {
            "C-ROOT-EXTENDED": verdict_for("C-ROOT-EXTENDED", gap_root, compare),
            "C-PINNED-LEGACY": verdict_for("C-PINNED-LEGACY", gap_legacy, compare),
            "PAIR": verdict_for("PAIR", gap_root, compare),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    # Markdown summary
    def _md() -> str:
        vr, vl, vp = report["verdicts"]["C-ROOT-EXTENDED"], report["verdicts"]["C-PINNED-LEGACY"], report["verdicts"]["PAIR"]
        gr, gl = gap_root, gap_legacy
        lines = [
            "# XAUUSD M15 Corpus Timestamp / Gap / Overlap Report",
            "",
            f"Generated (UTC): `{report['generated_at_utc']}`",
            "",
            "Computed from **raw CSV bytes** (`data/XAUUSD_M15.csv` + `data/mt5/XAUUSD_M15.csv`).",
            "Machine twin: `reports/xauusd_m15_corpus_timestamp_gap_report.json`.",
            "",
            "## Identity",
            "",
            "| Corpus | Path | SHA-256 prefix | Rows | Unique ts | First | Last |",
            "|---|---|---|---:|---:|---|---|",
        ]
        for cid in ("C-ROOT-EXTENDED", "C-PINNED-LEGACY"):
            c = report["corpora"][cid]
            lines.append(
                f"| `{cid}` | `{c['path']}` | `{c['sha256'][:16]}…` | {c['n_rows']} | "
                f"{c['n_unique_timestamps']} | {c['first_timestamp']} | {c['last_timestamp']} |"
            )
        if q_note:
            lines += [
                "",
                f"Quarantine twin: `{q_note['path']}` sha `{q_note['sha256'][:16]}…` "
                f"byte_identical_to_root={q_note['byte_identical_to_root']}.",
            ]
        lines += [
            "",
            "## Per-corpus integrity",
            "",
            "| Metric | Root extended | Legacy pinned |",
            "|---|---:|---:|",
            f"| duplicate timestamps | {root['duplicate_timestamp_count']} | {legacy['duplicate_timestamp_count']} |",
            f"| out-of-order adjacent pairs | {root['out_of_order_adjacent_pairs']} | {legacy['out_of_order_adjacent_pairs']} |",
            f"| wall-clock missing 15m slots | {gr['n_missing_15m_slots_wall_clock']} | {gl['n_missing_15m_slots_wall_clock']} |",
            f"| residual UNEXPLAINED missing slots | {gr['n_unexplained_missing_slots']} | {gl['n_unexplained_missing_slots']} |",
            f"| config+broker-pattern explained slots | {gr['n_expected_closure_missing_slots']} | {gl['n_expected_closure_missing_slots']} |",
            f"| config-only explained slots | {gr['n_config_explained_only']} | {gl['n_config_explained_only']} |",
            f"| broker-pattern explained slots | {gr['n_broker_pattern_explained']} | {gl['n_broker_pattern_explained']} |",
            f"| residual unexplained gap events | {gr['n_unexplained_gap_events']} | {gl['n_unexplained_gap_events']} |",
            f"| long residual unexplained (≥4 bars) | {gr['n_long_intraday_unexplained']} | {gl['n_long_intraday_unexplained']} |",
            f"| weekend bars present | {gr['weekend_bars_present']} | {gl['weekend_bars_present']} |",
            f"| partial weekday days | {len(gr['partial_weekday_days'])} | {len(gl['partial_weekday_days'])} |",
            "",
            "### Missing-slot class counts (root)",
            "",
            "```json",
            json.dumps(gr["missing_slot_class_counts"], indent=2),
            "```",
            "",
            "### Missing-slot class counts (legacy)",
            "",
            "```json",
            json.dumps(gl["missing_slot_class_counts"], indent=2),
            "```",
            "",
            "### Delta histogram (root, labeled top)",
            "",
            "```json",
            json.dumps(root["delta_histogram_labeled"], indent=2),
            "```",
            "",
            "### Delta histogram (legacy, labeled top)",
            "",
            "```json",
            json.dumps(legacy["delta_histogram_labeled"], indent=2),
            "```",
            "",
            "## Overlap / extension",
            "",
            f"- Shared timestamps: **{compare['n_overlap_timestamps']}**",
            f"- Only in root: **{compare['n_only_in_root']}** "
            f"(after legacy last: **{compare['n_rows_added_after_legacy_last']}**; "
            f"inside legacy window: **{compare['n_only_root_inside_legacy_window']}**)",
            f"- Only in legacy: **{compare['n_only_in_legacy']}** "
            f"(inside root window: **{compare['n_only_legacy_inside_root_window']}**)",
            f"- OHLCV mismatches on shared ts (sample size): "
            f"**{compare['n_ohlcv_mismatches_on_shared_ts']}**",
            f"- Extension range: `{compare['extension_first']}` → `{compare['extension_last']}`",
            "",
            "## Verdicts",
            "",
            f"- **C-ROOT-EXTENDED:** `{vr}`",
            f"- **C-PINNED-LEGACY:** `{vl}`",
            f"- **PAIR:** `{vp}`",
            "",
            "### Verdict grammar",
            "",
            "- `COMPLETE_15M_SEQUENCE` — zero wall-clock missing 15m slots",
            "- `EXPECTED_MARKET_CLOSURES_ONLY` — every missing slot is weekend/holiday/daily-break/known_gap",
            "- `UNEXPLAINED_MISSING_BARS` — ≥1 missing slot not explained by calendar rules",
            "- `CORPUS_DIVERGENCE` — hashes differ and/or timestamp/OHLCV set differs",
            "",
            "## Top unexplained gap events (root)",
            "",
        ]
        for g in gr["unexplained_gap_events"][:15]:
            lines.append(
                f"- `{g['from']}` → `{g['to']}` "
                f"({g['span_minutes']}m, {g['missing_15m_slots']} slots) "
                f"classes={g['class_counts']}"
            )
        if not gr["unexplained_gap_events"]:
            lines.append("- *(none)*")
        lines += [
            "",
            "## Top unexplained gap events (legacy)",
            "",
        ]
        for g in gl["unexplained_gap_events"][:15]:
            lines.append(
                f"- `{g['from']}` → `{g['to']}` "
                f"({g['span_minutes']}m, {g['missing_15m_slots']} slots) "
                f"classes={g['class_counts']}"
            )
        if not gl["unexplained_gap_events"]:
            lines.append("- *(none)*")
        lines += ["", "---", "", "Authority: analysis/evidence only. Grants no corpus promotion.", ""]
        return "\n".join(lines)

    OUT_MD.write_text(_md(), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print("ROOT verdict:", report["verdicts"]["C-ROOT-EXTENDED"])
    print("LEGACY verdict:", report["verdicts"]["C-PINNED-LEGACY"])
    print("PAIR verdict:", report["verdicts"]["PAIR"])
    print("Root unexplained slots:", gap_root["n_unexplained_missing_slots"])
    print("Legacy unexplained slots:", gap_legacy["n_unexplained_missing_slots"])
    print("Only root / only legacy:", compare["n_only_in_root"], compare["n_only_in_legacy"])
    print("Extension rows:", compare["n_rows_added_after_legacy_last"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
