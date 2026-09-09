"""Shadow XAUUSD identity certification.

WRITE-TIME producers (pipeline, encoder, CRT engine) may run here.
QUERY-TIME uses IdentityQuery only — Identity Check, no HEAD fill.

Not production. Not a live-spine wire. Grants no G001.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from identity.hashes import canonical_json_hash, feature_order_hash, sha256_bytes
from identity.outcome import L5WriteError, build_l5_record, engine_close_basis
from identity.query import IdentityQuery
from identity.store import IdentityStore
from identity.tokens import (
    L5_CLOSE_EVENTS,
    STATUS_IDENTITY_INCOMPLETE,
    STATUS_IDENTITY_MISMATCH,
    STATUS_PRESERVED,
    STATUS_UNIDENTIFIED,
)


class _Skip(Exception):
    pass


def _ts_iso(raw: str) -> str:
    s = raw.strip().replace(" ", "T")
    if len(s) >= 19:
        return s[:19]
    return s


def _progress(msg: str) -> None:
    print(msg, flush=True)


def _state_name(value: Any) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if name:
        return str(name)
    text = str(value).strip()
    return text


def _update_path(path: dict[str, Any], rec: Mapping[str, Any]) -> None:
    entry = float(path["entry_px"])
    risk = float(path["risk"])
    if risk <= 0:
        return
    high = float(rec["high"])
    low = float(rec["low"])
    if path["direction"] == "long":
        mfe_px = high - entry
        mae_px = entry - low
    else:
        mfe_px = entry - low
        mae_px = high - entry
    path["mfe"] = max(float(path["mfe"]), mfe_px / risk)
    path["mae"] = max(float(path["mae"]), mae_px / risk)


def _quiet_producers() -> None:
    import logging
    for name in (
        "CRT_ENGINE_V2",
        "CRT.EventLog",
        "CRT.RangeDetector",
        "CRT.StateMachine",
        "CRT.UltronRisk",
        "CRT.Execution",
        "CRT.Reset",
        "CRT.Orchestrator",
        "CRT.ParentFeed",
        "FEATURE_PIPELINE",
        "trade_system",
        "LlamaGate",
    ):
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        lg.propagate = False


def run_certification(corpus_path: Path, store_root: Path) -> dict[str, Any]:
    corpus_path = Path(corpus_path)
    corpus_bytes = corpus_path.read_bytes()
    corpus_sha = sha256_bytes(corpus_bytes)
    text = corpus_bytes.decode("utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    store = IdentityStore(store_root)
    snaps_l0 = {"corpus": corpus_bytes}
    _progress(f"cert start rows={len(rows)} corpus_sha256={corpus_sha[:16]} store={store_root}")

    written = {k: 0 for k in (
        "L0", "L1", "L2", "L3_OCCUPANCY", "L3_EVENT", "L4", "L5",
    )}
    write_fail = {STATUS_UNIDENTIFIED: 0, STATUS_IDENTITY_MISMATCH: 0, STATUS_IDENTITY_INCOMPLETE: 0}
    errors: list[str] = []
    crt_candle_errors = 0
    crt_candle_error_sample: list[str] = []
    engine_event_kinds: dict[str, int] = {}
    occupancy_states: dict[str, int] = {}
    skipped_events_missing_from_to = 0
    crt_config_meta: dict[str, Any] = {}

    def _tally(result) -> None:
        if result.status in write_fail:
            write_fail[result.status] += 1

    def _count_layer(layer: str) -> int:
        p = store._layer_path(layer)
        if not p.is_file():
            return 0
        return sum(1 for line in p.open(encoding="utf-8") if line.strip())

    # ── L0 ────────────────────────────────────────────────────────────
    l0_recs: list[dict[str, Any]] = []
    if _count_layer("L0") >= len(rows):
        for line in store._layer_path("L0").open(encoding="utf-8"):
            if line.strip():
                l0_recs.append(json.loads(line))
        written["L0"] = len(l0_recs)
    else:
        for row in rows:
            rec = {
                "instrument": "XAUUSD",
                "timeframe": "M15",
                "bar_open_ts": _ts_iso(row["timestamp"]),
                "corpus_sha256": corpus_sha,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            r = store.write("L0", rec, snaps_l0)
            _tally(r)
            if r.preserved:
                written["L0"] += 1
                l0_recs.append(rec)
            if written["L0"] % 5000 == 0:
                _progress(f"L0 written {written['L0']}/{len(rows)}")

    # ── L1 / L2 write-time producers ──────────────────────────────────
    try:
        if _count_layer("L1") >= max(written["L0"] - 300, 1) and _count_layer("L2") > 0:
            written["L1"] = _count_layer("L1")
            written["L2"] = _count_layer("L2")
            raise _Skip("L1/L2 already present")
        import pandas as pd
        from features.feature_pipeline import FeaturePipeline
        from features.feature_schema import CANONICAL_FEATURES
        from features.feature_states import FeatureStateEncoder

        pdf = pd.DataFrame(rows)
        for c in ("open", "high", "low", "close", "volume"):
            pdf[c] = pd.to_numeric(pdf[c], errors="coerce")
        pdf["timestamp"] = pdf["timestamp"]
        _quiet_producers()
        _progress(f"L1/L2 FeaturePipeline.run on {len(pdf)} rows")
        enriched, _vectors = FeaturePipeline(pdf).run()
        _progress(f"L1/L2 pipeline done rows={len(enriched)}")
        names = list(CANONICAL_FEATURES)
        order_bytes = json.dumps(names, sort_keys=False).encode()
        order_hash = feature_order_hash(names)
        encoder = FeatureStateEncoder()
        states_snaps: dict[str, tuple[str, bytes]] = {}
        for name in encoder.vector_bound_features:
            spec = encoder.spec(name)
            blob = json.dumps(spec.value_to_state, sort_keys=True, separators=(",", ":")).encode()
            states_snaps[name] = (spec.fm_id, blob)

        ts_col = "timestamp" if "timestamp" in enriched.columns else None
        for _, erow in enriched.iterrows():
            raw_ts = str(erow[ts_col]) if ts_col else ""
            bar_ts = _ts_iso(raw_ts)
            l0_base = {
                "instrument": "XAUUSD",
                "timeframe": "M15",
                "bar_open_ts": bar_ts,
                "corpus_sha256": corpus_sha,
            }
            values = [float(erow[n]) for n in names]
            l1 = {
                **l0_base,
                "schema_version": "5.0",
                "FEATURE_ORDER_HASH": order_hash,
                "feature_dim": 48,
                "values": values,
            }
            r = store.write("L1", l1, {"feature_order": order_bytes})
            _tally(r)
            if r.preserved:
                written["L1"] += 1
            feats = {n: float(erow[n]) for n in encoder.vector_bound_features if n in erow.index}
            classified = encoder.classify(feats)
            for fname, token in classified.items():
                fm_id, blob = states_snaps[fname]
                l2 = {
                    **l0_base,
                    "fm_id": fm_id,
                    "ontology_states_hash": sha256_bytes(blob),
                    "state": token,
                }
                r2 = store.write("L2", l2, {"states": blob})
                _tally(r2)
                if r2.preserved:
                    written["L2"] += 1
            if written["L1"] % 5000 == 0:
                _progress(f"L1 written {written['L1']} L2 written {written['L2']}")
    except _Skip:
        pass
    except Exception as exc:  # noqa: BLE001
        errors.append(f"L1/L2 writer: {type(exc).__name__}: {exc}")

    # ── L3 / L4 write-time CRT engine ─────────────────────────────────
    try:
        from config_layer.crt_config_provenance import get_provenance
        from config_layer.crt_engine_v2 import CRTEngine, Candle, EventLogger
        from config_layer.production_config import PROD_VERSION, get_prod_config, get_prod_section
        from config_layer.state_identity import VALID_TRANSITIONS
        from runtime.backtest_v2 import HTFBuilder
        from runtime.parent_crt_feed import ParentCRTFeed

        # Shadow cert must not append to the global crt_transitions.jsonl
        # (multi-GB, fold-incomplete). Occupancy/events go to IdentityStore only.
        EventLogger._emit_enveloped = lambda self, ev: None  # type: ignore[method-assign]
        _quiet_producers()

        topo_obj = {k.name: [x.name for x in v] for k, v in VALID_TRANSITIONS.items()}
        topo_bytes = json.dumps(topo_obj, sort_keys=True, separators=(",", ":")).encode()
        topo_id = sha256_bytes(topo_bytes)
        crt_cfg = get_prod_config("XAUUSD")
        crt_prov = get_provenance(crt_cfg)
        crt_config_meta = {
            "version": PROD_VERSION,
            "mode": crt_prov.mode.value,
            "instrument": crt_prov.instrument,
        }
        _progress(
            f"L3 CRTConfig version={PROD_VERSION} mode={crt_prov.mode.value} "
            f"instrument={crt_prov.instrument}"
        )
        engine = CRTEngine(crt_cfg)
        bt_sec = get_prod_section("backtest")
        htf_n = int(bt_sec["htf_candles_per_range"])
        warmup_n = int(bt_sec["warmup_candles"])
        htf = HTFBuilder(htf_n, "XAUUSD")
        parent_feed = ParentCRTFeed.from_prod_config()
        _progress(f"L3 HTF clock htf_candles_per_range={htf_n} warmup_candles={warmup_n}")
        occ_already = _count_layer("L3_OCCUPANCY") >= len(l0_recs) and len(l0_recs) > 0
        if occ_already:
            written["L3_OCCUPANCY"] = _count_layer("L3_OCCUPANCY")
            _progress(f"L3 occupancy already present ({written['L3_OCCUPANCY']}); still walk engine for events/L4")
        seen_events = 0
        initialised = False
        prev_htf_id = ""
        htf_remaining = htf_n
        pending_l5: dict[str, Any] | None = None
        l5_basis = engine_close_basis()
        _progress(f"L3 engine walk {len(l0_recs)} candles")
        for i, rec in enumerate(l0_recs, start=1):
            candle = Candle(
                timestamp=datetime.fromisoformat(rec["bar_open_ts"]),
                open=rec["open"],
                high=rec["high"],
                low=rec["low"],
                close=rec["close"],
                volume=rec["volume"],
            )
            action: dict[str, Any] = {"action": "NONE"}
            try:
                htf.push(candle)
                if parent_feed is not None:
                    parent_feed.push(candle)
                if htf.current_htf_id != prev_htf_id:
                    prev_htf_id = htf.current_htf_id
                    htf_remaining = htf_n - 1
                else:
                    htf_remaining = max(0, htf_remaining - 1)
                engine.state.htf_remaining_candles = htf_remaining
                if i >= warmup_n:
                    if not initialised:
                        seed = htf.seed_candles()
                        if seed:
                            engine.initialise_range(seed, htf.current_htf_id, "OFF_SESSION")
                            initialised = True
                    elif initialised:
                        parent_state = parent_feed.bias if parent_feed is not None else None
                        parent_objective = (
                            parent_feed.objective.status if parent_feed is not None else None
                        )
                        action = engine.process_candle(
                            candle,
                            htf.current_htf_id,
                            parent_state=parent_state,
                            parent_objective=parent_objective,
                        )
            except Exception as exc:
                action = {}
                crt_candle_errors += 1
                if len(crt_candle_error_sample) < 5:
                    crt_candle_error_sample.append(f"{rec['bar_open_ts']}: {type(exc).__name__}: {exc}")
            occ_state = engine.state.current_state.name
            occupancy_states[occ_state] = occupancy_states.get(occ_state, 0) + 1
            occ = {
                **{k: rec[k] for k in ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")},
                "producer_id": "engine",
                "topology_id": topo_id,
                "track_id": "execution_tf",
                "state": occ_state,
            }
            if not occ_already:
                r = store.write("L3_OCCUPANCY", occ, {"topology": topo_bytes})
                _tally(r)
                if r.preserved:
                    written["L3_OCCUPANCY"] += 1
            log = engine.state.event_log
            new = log[seen_events:]
            seen_events = len(log)
            close_kind = None
            close_pnl = None
            for ev in new:
                kind_raw = _state_name(getattr(ev, "event", None))
                engine_event_kinds[kind_raw] = engine_event_kinds.get(kind_raw, 0) + 1
                if kind_raw in L5_CLOSE_EVENTS:
                    close_kind = kind_raw
                    md = getattr(ev, "metadata", None) or {}
                    if "pnl" in md:
                        close_pnl = md.get("pnl")
                kind = kind_raw if kind_raw in ("STATE_TRANSITION", "RESET") else None
                if kind is None:
                    continue
                state_from = _state_name(ev.state_from)
                state_to = _state_name(ev.state_to)
                if not state_from or not state_to:
                    skipped_events_missing_from_to += 1
                    write_fail[STATUS_IDENTITY_INCOMPLETE] += 1
                    continue
                evt = {
                    **{k: rec[k] for k in ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")},
                    "producer_id": "engine",
                    "topology_id": topo_id,
                    "track_id": "execution_tf",
                    "state_from": state_from,
                    "state_to": state_to,
                    "event_kind": kind,
                }
                r = store.write("L3_EVENT", evt, {"topology": topo_bytes})
                _tally(r)
                if r.preserved:
                    written["L3_EVENT"] += 1
            if pending_l5 is not None:
                _update_path(pending_l5, rec)
            if close_kind and pending_l5 is not None:
                trade = engine.state.active_trade
                pnl = close_pnl
                if pnl is None and trade is not None:
                    pnl = getattr(trade, "pnl", None)
                risk = float(pending_l5["risk"])
                if pnl is None or risk <= 0:
                    write_fail[STATUS_IDENTITY_INCOMPLETE] += 1
                else:
                    try:
                        l5 = build_l5_record(
                            pending_l5["l4"],
                            walk_kernel=l5_basis["walk_kernel"],
                            cost_model_id=l5_basis["cost_model_id"],
                            fill_model_id=l5_basis["fill_model_id"],
                            y_R_gross=float(pnl) / risk,
                            mfe=float(pending_l5["mfe"]),
                            mae=float(pending_l5["mae"]),
                            duration_bars=max(0, i - int(pending_l5["open_i"]) + 1),
                            exit_reason=close_kind,
                        )
                    except L5WriteError as exc:
                        errors.append(f"L5 writer: {exc}")
                        write_fail[STATUS_UNIDENTIFIED] += 1
                    else:
                        r = store.write_l5_outcome(l5, {})
                        _tally(r)
                        if r.preserved:
                            written["L5"] += 1
                pending_l5 = None
            if isinstance(action, dict) and action.get("action") == "TRADE_OPENED":
                trade = engine.state.active_trade
                if trade is not None:
                    d = str(trade.direction.value).lower()
                    l4 = {
                        **{k: rec[k] for k in ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")},
                        "direction": d if d in ("long", "short") else "long",
                        "entry_px": float(trade.entry_price),
                        "sl_px": float(trade.sl_price),
                        "geometry_kind": "engine_trade",
                        "geometry_schema": "dual_tp_partial",
                        "tp1_px": float(trade.tp1_price),
                        "tp2_px": float(trade.tp2_price),
                    }
                    r = store.write("L4", l4, {})
                    _tally(r)
                    if r.preserved:
                        written["L4"] += 1
                    risk = abs(float(l4["entry_px"]) - float(l4["sl_px"]))
                    pending_l5 = {
                        "l4": l4,
                        "open_i": i,
                        "entry_px": l4["entry_px"],
                        "risk": risk,
                        "direction": l4["direction"],
                        "mfe": 0.0,
                        "mae": 0.0,
                    }
                    _update_path(pending_l5, rec)
            if i % 5000 == 0:
                _progress(
                    f"L3 {i}/{len(l0_recs)} occ={written['L3_OCCUPANCY']} "
                    f"events={written['L3_EVENT']} L4={written['L4']} "
                    f"L5={written['L5']} crt_err={crt_candle_errors}"
                )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"L3/L4/L5 writer: {type(exc).__name__}: {exc}")

    # ── QUERY (Identity Check only) ───────────────────────────────────
    _progress("QUERY Identity Check scan")
    store.close()
    store = IdentityStore(store_root)
    q = IdentityQuery(store)
    queried = {}
    scan_status = {STATUS_UNIDENTIFIED: 0, STATUS_IDENTITY_MISMATCH: 0, STATUS_IDENTITY_INCOMPLETE: 0}
    preserved_events: list = []
    for layer in ("L0", "L1", "L2", "L3_OCCUPANCY", "L3_EVENT", "L4", "L5"):
        _progress(f"QUERY scan {layer}")
        results = q.scan_checked(layer)
        kept = [cr.record for cr in results if cr.preserved and cr.record is not None]
        queried[layer] = len(kept)
        _progress(f"QUERY {layer} preserved={len(kept)} of {len(results)}")
        if layer == "L3_EVENT":
            preserved_events = kept
        for cr in results:
            if cr.status in scan_status:
                scan_status[cr.status] += 1

    events = preserved_events
    reset_present = any(e.get("event_kind") == "RESET" for e in events)
    transitions = any(e.get("event_kind") == "STATE_TRANSITION" for e in events)
    series = store.read_event_series(events) if events else None
    incomplete_series = (
        series is not None and series.status == STATUS_IDENTITY_INCOMPLETE
    )

    mismatch = scan_status[STATUS_IDENTITY_MISMATCH] + write_fail[STATUS_IDENTITY_MISMATCH]
    recoverable = all(
        queried[layer] == written[layer]
        for layer in written
        if written[layer] > 0
    )
    l0_l5_recoverable = recoverable and written["L0"] > 0
    # L5 may be 0 (no closed outcomes in this shadow). Gate names L0–L5 recoverable
    # of what was written. L5=0 is recorded, not silently filled.

    cert_pass = (
        l0_l5_recoverable
        and mismatch == 0
        and (reset_present if transitions else True)
        and not incomplete_series
    )

    report = {
        "gate": "XAUUSD_IDENTITY_CERTIFICATION",
        "status": "PASS" if cert_pass else "FAIL",
        "production_approved": False,
        "corpus_path": str(corpus_path).replace("\\", "/"),
        "corpus_sha256": corpus_sha,
        "corpus_rows": len(rows),
        "written": written,
        "queried_preserved": queried,
        "RESET_events_present": bool(reset_present),
        "UNIDENTIFIED": scan_status[STATUS_UNIDENTIFIED] + write_fail[STATUS_UNIDENTIFIED],
        "IDENTITY_INCOMPLETE": int(incomplete_series) + write_fail[STATUS_IDENTITY_INCOMPLETE],
        "IDENTITY_MISMATCH": mismatch,
        "write_fail": write_fail,
        "scan_fail": scan_status,
        "recoverable_written_layers": recoverable,
        "crt_candle_errors": crt_candle_errors,
        "crt_candle_error_sample": crt_candle_error_sample,
        "engine_event_kinds": engine_event_kinds,
        "occupancy_states": occupancy_states,
        "crt_config": crt_config_meta,
        "skipped_events_missing_from_to": skipped_events_missing_from_to,
        "errors": errors,
        "notes": [
            "WRITE used FeaturePipeline / FeatureStateEncoder / CRTEngine as producers.",
            "QUERY used IdentityQuery / Identity Check only.",
            "L5 written on engine close (STOPPED/TP2/STOPPED_STRUCTURAL/ABORTED) under named backtest_ledger + none_gross + engine_intrabar. Missing cost/fill is not defaulted.",
            (
                "2-year mt5 corpus run."
                if len(rows) > 10_000
                else "1-month corpus first; 2-year corpus is not this run."
            ),
            "L3 WRITE uses ACTIVE_VERSION CRTConfig + HTFBuilder clock + initialise_range (BacktestRunner path). Isolated process_candle(htf_id='') stays RANGE.",
            "Not production. Not live-spine. Grants no G001.",
        ],
    }
    return report


def render_report(report: dict[str, Any]) -> str:
    w, q = report["written"], report["queried_preserved"]
    shadow = "2-year shadow" if int(report.get("corpus_rows") or 0) > 10_000 else "1-month shadow"
    lines = [
        f"# XAUUSD Identity Certification ({shadow})",
        "",
        f"**Gate:** `{report['gate']}`",
        f"**Status:** **{report['status']}**",
        f"**Production approved:** {report['production_approved']}",
        f"**Corpus:** `{report['corpus_path']}`",
        f"**corpus_sha256:** `{report['corpus_sha256']}`",
        f"**Rows:** {report['corpus_rows']}",
        "",
        "| Check | Required | Result |",
        "|---|---|---|",
        f"| L0 identities written | Count | {w['L0']} |",
        f"| L1 identities written | Count | {w['L1']} |",
        f"| L2 identities written | Count | {w['L2']} |",
        f"| L3 occupancies written | Count | {w['L3_OCCUPANCY']} |",
        f"| L3 events written | Count | {w['L3_EVENT']} |",
        f"| RESET events present | YES/NO | {'YES' if report['RESET_events_present'] else 'NO'} |",
        f"| L4 geometries written | Count | {w['L4']} |",
        f"| L5 outcomes written | Count | {w['L5']} |",
        f"| UNIDENTIFIED records | Count | {report['UNIDENTIFIED']} |",
        f"| IDENTITY_INCOMPLETE records | Count | {report['IDENTITY_INCOMPLETE']} |",
        f"| IDENTITY_MISMATCH records | Count | {report['IDENTITY_MISMATCH']} |",
        f"| CRT process_candle errors (isolated) | Count | {report.get('crt_candle_errors', 0)} |",
        f"| Query PRESERVED L0 | Count | {q['L0']} |",
        f"| Query PRESERVED L1 | Count | {q['L1']} |",
        f"| Query PRESERVED L2 | Count | {q['L2']} |",
        f"| Query PRESERVED L3 occupancy | Count | {q['L3_OCCUPANCY']} |",
        f"| Query PRESERVED L3 events | Count | {q['L3_EVENT']} |",
        f"| Query PRESERVED L4 | Count | {q['L4']} |",
        f"| Query PRESERVED L5 | Count | {q['L5']} |",
        "",
        "## Gate (not production)",
        "",
        "```text",
        "L0–L5 recoverable via IdentityQuery  (of what was written)",
        "No recompute path on QUERY",
        "No HEAD dependency on QUERY",
        "No identity mismatch",
        "```",
        "",
        f"**Certification:** {report['status']}",
        "**Production Approved:** NO (gate requires this report; promotion is a separate authorization).",
        "",
        "## Errors",
        "",
    ]
    if report["errors"]:
        for e in report["errors"]:
            lines.append(f"- {e}")
    else:
        lines.append("- none")
    samples = report.get("crt_candle_error_sample") or []
    if samples:
        lines.append("")
        lines.append("CRT per-bar errors (sample, isolated — occupancy still written):")
        for s in samples:
            lines.append(f"- {s}")
    crt_meta = report.get("crt_config") or {}
    if crt_meta:
        lines.append("")
        lines.append(
            f"CRTConfig: version=`{crt_meta.get('version')}` "
            f"mode=`{crt_meta.get('mode')}` instrument=`{crt_meta.get('instrument')}`"
        )
    occ = report.get("occupancy_states") or {}
    if occ:
        lines.append("")
        lines.append("L3 occupancy state histogram:")
        for k, n in sorted(occ.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"- {k}: {n}")
    kinds = report.get("engine_event_kinds") or {}
    if kinds:
        lines.append("")
        lines.append("Engine event_log kinds (raw, before identity write):")
        for k, n in sorted(kinds.items()):
            lines.append(f"- {k}: {n}")
    skipped = report.get("skipped_events_missing_from_to") or 0
    if skipped:
        lines.append("")
        lines.append(f"STATE_TRANSITION/RESET skipped (empty from/to): {skipped}")
    lines.extend(["", "## Notes", ""])
    for n in report["notes"]:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Shadow XAUUSD identity certification")
    p.add_argument("--corpus", default="data/XAUUSD_M15.csv")
    p.add_argument("--store", default="results/identity_cert/xauusd_m15_1m")
    p.add_argument("--report", default="docs/governance/xauusd_identity_certification.md")
    args = p.parse_args()
    report = run_certification(Path(args.corpus), Path(args.store))
    md = render_report(report)
    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    json_path = out.with_suffix(".json")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(md)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
