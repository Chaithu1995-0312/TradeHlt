#!/usr/bin/env python3
"""RUN1 FVG join - corpus-aligned cross-emit. Fail-closed on alignment."""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

FVG_FIELDS = [
    "fvg_present",
    "fvg_bullish",
    "fvg_high",
    "fvg_low",
    "fvg_mid",
    "fvg_formed_at_index",
    "fvg_age_bars",
    "fvg_width_atr",
    "fvg_inside",
    "fvg_distance",
    "fvg_window_truncated",
]

SNAP_PATH = Path(r"D:\Tradelatest\logs\bar_structure\XAUUSD_bar_structure.jsonl")
MANIFEST_PATH = Path(r"D:\Tradelatest\logs\bar_structure\XAUUSD_bar_structure.parquet.manifest.json")
RUN_DIR = Path(r"D:\Tradelatest\results\run_20260916_225925_XAUUSD")
OUT_DIR = Path(r"D:\Tradelatest\multi_llm\bridge_layer")
TRACK_PATH = Path(r"D:\Tradelatest\multi_llm\GROK_BOT_TRACK.md")

CONTENT_RUN_ID = "run_20260916_172925"
FOLDER_RUN_ID = "run_20260916_225925_XAUUSD"
RUN_CONFIG = "v2_htfcrt_2026_08"
SNAP_EMIT_RUN_ID = "run_20260829_105725"
SNAP_CONFIG = "v3_unified_market_structure_2026_09"
EXPECTED_CORPUS_SHA = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
EXPECTED_ROWS = 47275


def null_fvg():
    return {
        "fvg_present": False,
        "fvg_bullish": None,
        "fvg_high": None,
        "fvg_low": None,
        "fvg_mid": None,
        "fvg_formed_at_index": None,
        "fvg_age_bars": None,
        "fvg_width_atr": None,
        "fvg_inside": None,
        "fvg_distance": 0.0,
        "fvg_window_truncated": None,
    }


def coerce_fvg(row: dict) -> dict:
    """Extract fvg_* only; apply row-0 / missing null semantics."""
    out = null_fvg()
    present = row.get("fvg_present")
    if present is None and all(row.get(k) is None for k in FVG_FIELDS if k != "fvg_present"):
        # missing block -> null semantics
        return out
    if present is None:
        present = False
    out["fvg_present"] = bool(present)
    for k in FVG_FIELDS:
        if k == "fvg_present":
            continue
        if k == "fvg_distance" and row.get(k) is None and not out["fvg_present"]:
            out[k] = 0.0
            continue
        if k in row:
            out[k] = row[k]
    if not out["fvg_present"] and out.get("fvg_distance") is None:
        out["fvg_distance"] = 0.0
    return out


def load_snapshot():
    by_bar = {}
    by_ts = {}
    meta = {}
    n = 0
    fvg_key_seen = set()
    with SNAP_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            n += 1
            if n == 1:
                meta = {
                    "run_id": o.get("run_id"),
                    "config_version": o.get("config_version"),
                    "corpus_sha256": o.get("corpus_sha256"),
                    "instrument": o.get("instrument"),
                    "schema_version": o.get("schema_version"),
                    "all_fvg_keys_in_row0": sorted(k for k in o.keys() if k.startswith("fvg_")),
                }
            bi = o.get("bar_index")
            eng = o.get("engine_candle_index")
            ts = o.get("timestamp")
            fvg = coerce_fvg(o)
            for k in FVG_FIELDS:
                if k in o:
                    fvg_key_seen.add(k)
            rec = {
                "bar_index": bi,
                "engine_candle_index": eng,
                "timestamp": ts,
                **fvg,
            }
            by_bar[int(bi)] = rec
            if ts is not None:
                by_ts[str(ts)] = rec
    return by_bar, by_ts, meta, n, sorted(fvg_key_seen)


def load_events():
    path = RUN_DIR / "XAUUSD_events.jsonl"
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_trades():
    path = RUN_DIR / "XAUUSD_trades.csv"
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_summary():
    with (RUN_DIR / "XAUUSD_summary.json").open(encoding="utf-8") as f:
        return json.load(f)


def eval_offset(events, by_bar, offset, index_field="candle_index"):
    """bar_index = candle_index + offset. Score timestamp matches."""
    matched = 0
    mismatched = 0
    oob = 0
    samples = []
    for e in events:
        ci = e.get(index_field)
        if ci is None:
            continue
        bi = int(ci) + offset
        ts_e = str(e.get("timestamp"))
        rec = by_bar.get(bi)
        if rec is None:
            oob += 1
            continue
        ts_s = str(rec["timestamp"])
        ok = ts_e == ts_s
        if ok:
            matched += 1
        else:
            mismatched += 1
            if len(samples) < 5:
                samples.append({"event_ts": ts_e, "snap_ts": ts_s, "candle_index": ci, "bar_index": bi})
    total = matched + mismatched + oob
    rate = matched / total if total else 0.0
    return {
        "offset": offset,
        "formula": f"bar_index = {index_field} + ({offset})",
        "matched": matched,
        "mismatched": mismatched,
        "oob": oob,
        "total": total,
        "match_rate": rate,
        "mismatch_samples": samples,
    }


def eval_ts_direct(events, by_ts):
    matched = 0
    missing = 0
    for e in events:
        ts = str(e.get("timestamp"))
        if ts in by_ts:
            matched += 1
        else:
            missing += 1
    total = matched + missing
    return {
        "method": "timestamp_equality",
        "matched": matched,
        "missing": missing,
        "total": total,
        "match_rate": matched / total if total else 0.0,
    }


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def main():
    print("Loading snapshot...")
    by_bar, by_ts, snap_meta, n_snap, fvg_keys_seen = load_snapshot()
    print(f"  rows={n_snap} unique_bar={len(by_bar)} unique_ts={len(by_ts)}")
    print(f"  snap_meta={snap_meta}")
    print(f"  fvg_keys_seen={fvg_keys_seen}")

    events = load_events()
    trades = load_trades()
    summary = load_summary()
    print(f"  events={len(events)} trades={len(trades)}")

    # Alignment hypotheses from prior forensic (+1/-62) plus identity and ts-direct
    # Prior: event.candle_index - bar = -62 => bar = candle_index + 62
    # Prior: trade.candle_idx - bar = 1 => bar = candle_idx - 1
    offsets_to_try = [0, 1, -1, 62, -62, 63, -63]
    event_offset_results = [eval_offset(events, by_bar, off) for off in offsets_to_try]
    event_offset_results.sort(key=lambda r: (-r["match_rate"], r["mismatched"], abs(r["offset"])))
    ts_direct = eval_ts_direct(events, by_ts)

    print("\n=== Event offset trials ===")
    for r in event_offset_results:
        print(f"  offset={r['offset']:+d} match={r['matched']}/{r['total']} rate={r['match_rate']:.6f} mism={r['mismatched']} oob={r['oob']}")
    print(f"  ts_direct match={ts_direct['matched']}/{ts_direct['total']} rate={ts_direct['match_rate']:.6f}")

    best_event = event_offset_results[0]
    # Prefer timestamp-direct if perfect / better; else best offset if high enough
    join_method = None
    event_match_rate = None
    event_offset = None
    unjoinable = False
    unjoinable_reason = None

    if ts_direct["match_rate"] >= 0.999 and ts_direct["matched"] == ts_direct["total"]:
        join_method = "timestamp_equality"
        event_match_rate = ts_direct["match_rate"]
        # still compute modal offset for documentation via best offset among ts-matched
        event_offset = best_event["offset"] if best_event["match_rate"] >= 0.99 else None
    elif best_event["match_rate"] >= 0.99:
        join_method = f"candle_index_plus_{best_event['offset']}"
        event_match_rate = best_event["match_rate"]
        event_offset = best_event["offset"]
    else:
        unjoinable = True
        unjoinable_reason = {
            "message": "timestamp/index alignment failed fail-closed threshold (>=0.99)",
            "best_offset_trial": best_event,
            "ts_direct": ts_direct,
            "all_offset_trials": event_offset_results,
        }

    # Trade offset trials using opened_at vs snapshot ts, and candle_idx
    trade_offset_results = []
    for off in offsets_to_try:
        matched = mism = oob = 0
        samples = []
        for t in trades:
            ci = int(t["candle_idx"])
            bi = ci + off
            rec = by_bar.get(bi)
            ts_t = str(t["opened_at"])
            if rec is None:
                oob += 1
                continue
            if str(rec["timestamp"]) == ts_t:
                matched += 1
            else:
                mism += 1
                if len(samples) < 3:
                    samples.append({"opened_at": ts_t, "snap_ts": rec["timestamp"], "candle_idx": ci, "bar_index": bi})
        total = matched + mism + oob
        trade_offset_results.append({
            "offset": off,
            "formula": f"bar_index = candle_idx + ({off})",
            "matched": matched,
            "mismatched": mism,
            "oob": oob,
            "total": total,
            "match_rate": matched / total if total else 0.0,
            "mismatch_samples": samples,
        })
    trade_offset_results.sort(key=lambda r: (-r["match_rate"], abs(r["offset"])))
    print("\n=== Trade offset trials (opened_at vs snap ts) ===")
    for r in trade_offset_results:
        print(f"  offset={r['offset']:+d} match={r['matched']}/{r['total']} rate={r['match_rate']:.6f}")

    # Also trade via timestamp
    trade_ts_matched = sum(1 for t in trades if str(t["opened_at"]) in by_ts)
    print(f"  trade ts_direct {trade_ts_matched}/{len(trades)}")

    if unjoinable:
        report = {
            "status": "UNJOINABLE",
            "reason": unjoinable_reason,
            "provenance": {
                "kind": "corpus_aligned_cross_emit_join",
                "run1_folder": str(RUN_DIR),
                "content_run_id": CONTENT_RUN_ID,
                "run1_config": RUN_CONFIG,
                "snapshot_path": str(SNAP_PATH),
                "snapshot_emit_run_id": snap_meta.get("run_id") or SNAP_EMIT_RUN_ID,
                "snapshot_config": snap_meta.get("config_version") or SNAP_CONFIG,
                "corpus_sha256": snap_meta.get("corpus_sha256"),
                "expected_corpus_sha256": EXPECTED_CORPUS_SHA,
                "corpus_sha_match": snap_meta.get("corpus_sha256") == EXPECTED_CORPUS_SHA,
                "note": "Do NOT treat snapshot crt_state_* as Run1 state (different config/engine).",
            },
            "alignment_trials": {
                "events_offsets": event_offset_results,
                "events_ts_direct": ts_direct,
                "trades_offsets": trade_offset_results,
            },
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "RUN1_FVG_JOIN.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        (OUT_DIR / "RUN1_FVG_JOIN.md").write_text(
            "# RUN1 FVG JOIN — UNJOINABLE\n\nAlignment failed fail-closed. See RUN1_FVG_JOIN.json.\n",
            encoding="utf-8",
        )
        print("\nUNJOINABLE — wrote report only")
        print(json.dumps(unjoinable_reason, indent=2)[:2000])
        return

    # Resolve FVG for an event
    def fvg_for_event(e):
        if join_method == "timestamp_equality":
            rec = by_ts.get(str(e["timestamp"]))
        else:
            bi = int(e["candle_index"]) + event_offset
            rec = by_bar.get(bi)
        if rec is None:
            return None, null_fvg()
        return rec["bar_index"], {k: rec[k] for k in FVG_FIELDS}

    def fvg_for_trade_entry(t):
        # Prefer timestamp if that's the chosen method, else best trade offset
        if join_method == "timestamp_equality" or trade_ts_matched == len(trades):
            rec = by_ts.get(str(t["opened_at"]))
            if rec:
                return rec["bar_index"], {k: rec[k] for k in FVG_FIELDS}, "opened_at_timestamp"
        best_toff = trade_offset_results[0]
        if best_toff["match_rate"] >= 0.99:
            bi = int(t["candle_idx"]) + best_toff["offset"]
            rec = by_bar.get(bi)
            if rec:
                return rec["bar_index"], {k: rec[k] for k in FVG_FIELDS}, best_toff["formula"]
        # fallback try ts
        rec = by_ts.get(str(t["opened_at"]))
        if rec:
            return rec["bar_index"], {k: rec[k] for k in FVG_FIELDS}, "opened_at_timestamp_fallback"
        return None, null_fvg(), "unmapped"

    def fvg_for_trade_exit(t):
        closed = t.get("closed_at")
        if not closed:
            return None, None, None
        rec = by_ts.get(str(closed))
        if rec:
            return rec["bar_index"], {k: rec[k] for k in FVG_FIELDS}, "closed_at_timestamp"
        return None, null_fvg(), "unmapped_exit"

    # Build event join rows
    event_join = []
    present_count = 0
    by_type = Counter()
    by_type_present = Counter()
    distances = []
    unmapped_events = 0
    for e in events:
        bi, fvg = fvg_for_event(e)
        if bi is None and join_method == "timestamp_equality" and str(e["timestamp"]) not in by_ts:
            unmapped_events += 1
        row = {
            "event": e.get("event"),
            "timestamp": e.get("timestamp"),
            "candle_index": e.get("candle_index"),
            "mapped_bar_index": bi,
            "state_from": e.get("state_from"),
            "state_to": e.get("state_to"),
            "direction": e.get("direction"),
            "price": e.get("price"),
            "reason": e.get("reason"),
            "run_id": e.get("run_id"),
            **fvg,
        }
        # flatten metadata id if present
        md = e.get("metadata") or {}
        if isinstance(md, dict) and "id" in md:
            row["metadata_id"] = md["id"]
        else:
            row["metadata_id"] = None
        event_join.append(row)
        et = e.get("event") or "UNKNOWN"
        by_type[et] += 1
        if fvg.get("fvg_present"):
            present_count += 1
            by_type_present[et] += 1
            d = fvg.get("fvg_distance")
            if d is not None:
                try:
                    distances.append(float(d))
                except (TypeError, ValueError):
                    pass

    # Trade join
    trade_join = []
    trades_entry_present = 0
    best_trade_formula = trade_offset_results[0]["formula"] if trade_offset_results[0]["match_rate"] >= 0.99 else "opened_at_timestamp"
    for t in trades:
        bi, fvg, how = fvg_for_trade_entry(t)
        ebi, efvg, ehow = fvg_for_trade_exit(t)
        if fvg.get("fvg_present"):
            trades_entry_present += 1
        row = dict(t)  # keep all original trade cols
        row["mapped_entry_bar_index"] = bi
        row["entry_fvg_join_key"] = how
        for k, v in fvg.items():
            row[f"entry_{k}"] = v
        if ebi is not None and efvg is not None:
            row["mapped_exit_bar_index"] = ebi
            row["exit_fvg_join_key"] = ehow
            for k, v in efvg.items():
                row[f"exit_{k}"] = v
        trade_join.append(row)

    distances_sorted = sorted(distances)
    census = {
        "events_total": len(event_join),
        "events_fvg_present_true": present_count,
        "events_fvg_present_pct": round(100.0 * present_count / len(event_join), 4) if event_join else 0.0,
        "events_unmapped": unmapped_events,
        "fvg_present_rate_by_event_type": {
            et: {
                "total": by_type[et],
                "fvg_present": by_type_present[et],
                "pct": round(100.0 * by_type_present[et] / by_type[et], 4) if by_type[et] else 0.0,
            }
            for et in sorted(by_type.keys())
        },
        "fvg_distance_when_present": {
            "n": len(distances_sorted),
            "min": distances_sorted[0] if distances_sorted else None,
            "median": statistics.median(distances_sorted) if distances_sorted else None,
            "p90": percentile(distances_sorted, 0.90) if distances_sorted else None,
        },
        "trades_total": len(trade_join),
        "trades_fvg_present_at_entry": trades_entry_present,
    }

    # Write CSV events
    event_cols = [
        "event", "timestamp", "candle_index", "mapped_bar_index",
        "state_from", "state_to", "direction", "price", "reason", "run_id", "metadata_id",
    ] + FVG_FIELDS
    events_csv = OUT_DIR / "RUN1_FVG_EVENTS.csv"
    with events_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=event_cols, extrasaction="ignore")
        w.writeheader()
        for row in event_join:
            w.writerow(row)

    # Write CSV trades
    trade_cols = list(trades[0].keys()) if trades else []
    extra = (
        ["mapped_entry_bar_index", "entry_fvg_join_key"]
        + [f"entry_{k}" for k in FVG_FIELDS]
        + ["mapped_exit_bar_index", "exit_fvg_join_key"]
        + [f"exit_{k}" for k in FVG_FIELDS]
    )
    trade_cols = trade_cols + [c for c in extra if c not in trade_cols]
    trades_csv = OUT_DIR / "RUN1_FVG_TRADES.csv"
    with trades_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=trade_cols, extrasaction="ignore")
        w.writeheader()
        for row in trade_join:
            w.writerow(row)

    provenance = {
        "kind": "corpus_aligned_cross_emit_join",
        "not_same_run_emit": True,
        "run1": {
            "folder": str(RUN_DIR),
            "folder_run_id": FOLDER_RUN_ID,
            "content_run_id": CONTENT_RUN_ID,
            "config": RUN_CONFIG,
            "instrument": "XAUUSD",
            "total_candles": summary.get("total_candles"),
            "authority": "Run1 state/events/trades remain authoritative for lifecycle; snapshot crt_state_* NOT used",
        },
        "snapshot": {
            "path": str(SNAP_PATH),
            "manifest": str(MANIFEST_PATH),
            "emit_run_id": snap_meta.get("run_id") or SNAP_EMIT_RUN_ID,
            "config": snap_meta.get("config_version") or SNAP_CONFIG,
            "corpus_sha256": snap_meta.get("corpus_sha256"),
            "expected_corpus_sha256": EXPECTED_CORPUS_SHA,
            "corpus_sha_match": snap_meta.get("corpus_sha256") == EXPECTED_CORPUS_SHA,
            "rows": n_snap,
            "expected_rows": EXPECTED_ROWS,
            "fvg_fields_carried": FVG_FIELDS,
            "fvg_keys_present_in_snapshot": fvg_keys_seen,
            "row0_null_semantics": "missing fvg_* treated as fvg_present=false / fvg_distance=0.0",
        },
        "caveats": [
            "Cross-emit join: snapshot from run_20260829_105725 / v3_unified_market_structure_2026_09; Run1 is run_20260916_172925 / v2_htfcrt_2026_08.",
            "Only fvg_* geometry fields joined; snapshot crt_state_* intentionally excluded.",
            "Census is measurement-only; no trading edge interpretation.",
            "Alignment verified by timestamp equality / offset trial match rate; fail-closed if <0.99.",
        ],
    }

    report = {
        "status": "JOINED",
        "generated_at_local": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z") or datetime.now().isoformat(),
        "provenance": provenance,
        "join_key": {
            "events": {
                "method": join_method,
                "offset": event_offset,
                "match_rate": event_match_rate,
                "ts_direct": ts_direct,
                "best_offset_trial": best_event,
                "all_offset_trials": event_offset_results,
            },
            "trades": {
                "entry_method_preferred": best_trade_formula if trade_offset_results[0]["match_rate"] >= 0.99 else "opened_at_timestamp",
                "ts_direct_matched": trade_ts_matched,
                "ts_direct_total": len(trades),
                "best_offset_trial": trade_offset_results[0],
                "all_offset_trials": trade_offset_results,
                "exit_method": "closed_at_timestamp",
            },
        },
        "row_counts": {
            "snapshot_bars": n_snap,
            "events_in": len(events),
            "events_joined": len(event_join),
            "trades_in": len(trades),
            "trades_joined": len(trade_join),
        },
        "census": census,
        "outputs": {
            "json": str(OUT_DIR / "RUN1_FVG_JOIN.json"),
            "md": str(OUT_DIR / "RUN1_FVG_JOIN.md"),
            "events_csv": str(events_csv),
            "trades_csv": str(trades_csv),
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "RUN1_FVG_JOIN.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md_lines = [
        "# RUN1 FVG JOIN",
        "",
        "**Status:** JOINED (corpus-aligned cross-emit; not same-run emit)",
        "",
        "## Provenance",
        f"- Run1 folder: `{RUN_DIR}` (content `{CONTENT_RUN_ID}`, config `{RUN_CONFIG}`)",
        f"- Snapshot: `{SNAP_PATH}` (emit `{snap_meta.get('run_id')}`, config `{snap_meta.get('config_version')}`)",
        f"- corpus_sha256 match: `{snap_meta.get('corpus_sha256') == EXPECTED_CORPUS_SHA}`",
        "- Carried fields: **fvg_*** geometry only. Snapshot `crt_state_*` excluded.",
        "- Run1 events/trades/state remain lifecycle authority.",
        "",
        "## Join key",
        f"- Events: `{join_method}` (match_rate={event_match_rate})",
        f"- Event offset (if applicable): `{event_offset}`",
        f"- Trades entry: timestamp `opened_at` / best offset `{trade_offset_results[0]['formula']}` rate={trade_offset_results[0]['match_rate']}",
        f"- Trades exit: `closed_at` timestamp",
        "",
        "## Row counts",
        f"- Events joined: {len(event_join)}",
        f"- Trades joined: {len(trade_join)}",
        "",
        "## Census (measurement only)",
        f"- Events with fvg_present: {present_count}/{len(event_join)} ({census['events_fvg_present_pct']}%)",
        f"- Trades with fvg_present at entry: {trades_entry_present}/{len(trade_join)}",
        f"- Distance when present: min={census['fvg_distance_when_present']['min']}, median={census['fvg_distance_when_present']['median']}, p90={census['fvg_distance_when_present']['p90']}",
        "",
        "### By event type",
    ]
    for et, info in census["fvg_present_rate_by_event_type"].items():
        md_lines.append(f"- `{et}`: {info['fvg_present']}/{info['total']} ({info['pct']}%)")
    md_lines += [
        "",
        "## Outputs",
        f"- `{OUT_DIR / 'RUN1_FVG_JOIN.json'}`",
        f"- `{OUT_DIR / 'RUN1_FVG_JOIN.md'}`",
        f"- `{events_csv}`",
        f"- `{trades_csv}`",
        "",
        "## Caveats",
    ]
    for c in provenance["caveats"]:
        md_lines.append(f"- {c}")
    md_lines.append("")
    (OUT_DIR / "RUN1_FVG_JOIN.md").write_text("\n".join(md_lines), encoding="utf-8")

    # Optional stamp on GROK_BOT_TRACK.md
    if TRACK_PATH.exists():
        stamp = (
            f"\n- [{datetime.now().strftime('%Y-%m-%d %H:%M IST')}] "
            f"RUN1 FVG join: events method={join_method} rate={event_match_rate}; "
            f"events {len(event_join)} trades {len(trade_join)}; "
            f"fvg_present events={present_count} trades_entry={trades_entry_present}; "
            f"outputs under multi_llm/bridge_layer/RUN1_FVG_*.\n"
        )
        with TRACK_PATH.open("a", encoding="utf-8") as f:
            f.write(stamp)

    print("\n=== DONE ===")
    print(json.dumps({
        "status": "JOINED",
        "join_method": join_method,
        "event_match_rate": event_match_rate,
        "event_offset": event_offset,
        "events": len(event_join),
        "trades": len(trade_join),
        "census_headline": {
            "events_fvg_present_pct": census["events_fvg_present_pct"],
            "trades_fvg_present_at_entry": trades_entry_present,
            "distance": census["fvg_distance_when_present"],
        },
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
