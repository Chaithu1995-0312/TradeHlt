"""Program 12 Slice 2 runner. Research only.

The CLI writes ``ladder_bars.csv`` and declares its clock. This module does not
call declare_in_process, admit_csv_path, or CandleLoader. It does not edit
configs/production. Journal pnl_rr is not ladder y.

Below n_clusters 30 the returned report has no mean, no CI, and no expectancy.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

from research.costs import xau_measured_cost_model
from research.measurement.forward_walk import AdverseFill
from research.oracle.multi_tp_walk import multi_tp_walk
from research.timeframe_ladder.clusters import assign_clusters
from research.timeframe_ladder.config_clone import bind_research_config, build_clone, knob_specs, load_crt_config
from research.timeframe_ladder.controls import (
    N_CLUSTERS_MIN,
    cluster_bootstrap_mean_ci,
    passive_drift_r,
    percentile_rank,
    random_entry_means,
    random_seeds,
    verdict,
)
from research.timeframe_ladder.parity import (
    DECLARED_PARENT_END,
    DECLARED_PARENT_N,
    DECLARED_PARENT_PATH,
    DECLARED_PARENT_START,
    load_ohlcv_csv,
)
from research.timeframe_ladder.stop_floor import apply_stop_floor

# Sealed with MC-LADDER-XAUUSD-HTF-V1 before any Step 2 result was read.
EXPECTED_PARENT_SHA256 = "478b075150935c950ccc749925709db783e337c55c886d6dda1e3ee8b9692c5b"
PROJECTED_CSV_NAME = "ladder_bars.csv"
_ADVERSE = AdverseFill(stop_slippage=0.090, model_gaps=True)


class ParentWindowError(RuntimeError):
    """The file on disk is not the sealed one-month parent."""


def parent_file_identity(path: str | Path) -> dict:
    """Hash the file bytes and read n / first / last. No corpus admission."""
    path = Path(path)
    raw = path.read_bytes()
    candles = load_ohlcv_csv(path)
    first = candles[0].timestamp if candles else None
    last = candles[-1].timestamp if candles else None
    return {
        "path": DECLARED_PARENT_PATH,
        "n": len(candles),
        "first": first.strftime("%Y-%m-%d %H:%M:%S") if first else None,
        "last": last.strftime("%Y-%m-%d %H:%M:%S") if last else None,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "nbytes": len(raw),
    }


def assert_declared_parent(identity: dict) -> None:
    """Refuse a parent that is not the sealed Slice 2/3 window."""
    want_first = DECLARED_PARENT_START.strftime("%Y-%m-%d %H:%M:%S")
    want_last = DECLARED_PARENT_END.strftime("%Y-%m-%d %H:%M:%S")
    problems = []
    if identity.get("path") != DECLARED_PARENT_PATH:
        problems.append(f"path {identity.get('path')!r}")
    if identity.get("n") != DECLARED_PARENT_N:
        problems.append(f"n {identity.get('n')!r}")
    if identity.get("first") != want_first:
        problems.append(f"first {identity.get('first')!r}")
    if identity.get("last") != want_last:
        problems.append(f"last {identity.get('last')!r}")
    if identity.get("sha256") != EXPECTED_PARENT_SHA256:
        problems.append(f"sha256 {identity.get('sha256')!r}")
    if problems:
        raise ParentWindowError(
            "parent window does not match the sealed one-month slice: " + "; ".join(problems)
        )


def _side(direction: object) -> str:
    name = str(direction or "").strip().lower()
    if name in ("long", "buy"):
        return "long"
    if name in ("short", "sell"):
        return "short"
    raise ValueError(f"direction must be long or short, got {direction!r}")


def _f(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def funnel_counts(events: list[dict], n_journal: int) -> dict:
    """State entries plus the journal trade count. Counts only."""

    def _n(state: str) -> int:
        return sum(
            1
            for ev in events
            if ev.get("event") == "STATE_TRANSITION" and ev.get("state_to") == state
        )

    return {
        "SWEEP": _n("SWEEP"),
        "DISPLACEMENT": _n("DISPLACEMENT"),
        "EXPANSION": _n("EXPANSION"),
        "RETEST": _n("RETEST"),
        "TRADE_OPENED": sum(1 for ev in events if ev.get("event") == "TRADE_OPENED"),
        "journal_trades": int(n_journal),
    }


def latest_sweep_index(events: list[dict], entry_index: int) -> int | None:
    """Most recent SWEEP transition at or before the entry bar."""
    best: int | None = None
    for ev in events:
        if ev.get("event") != "STATE_TRANSITION" or ev.get("state_to") != "SWEEP":
            continue
        idx = ev.get("candle_index")
        if idx is None:
            continue
        idx = int(idx)
        if idx <= entry_index and (best is None or idx > best):
            best = idx
    return best


def _index_for_timestamp(candles, opened_at: str) -> int | None:
    text = str(opened_at).replace("T", " ")[:19]
    for candle in candles:
        if candle.timestamp.strftime("%Y-%m-%d %H:%M:%S") == text:
            return int(candle.index)
    return None


def _event_prices(ev: dict) -> dict | None:
    meta = ev.get("metadata")
    if not isinstance(meta, dict):
        return None
    entry = _f(meta.get("price"))
    sl = _f(meta.get("sl"))
    tp1 = _f(meta.get("tp1"))
    tp2 = _f(meta.get("tp2"))
    if None in (entry, sl, tp1, tp2) or ev.get("candle_index") is None:
        return None
    return {
        "entry": entry,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "entry_index": int(ev["candle_index"]),
        "direction": meta.get("direction"),
    }


def walk_journal(candles, events: list[dict], journal_rows: list[dict], *, ttl: int) -> dict:
    """Research walk. Structural prices come from TRADE_OPENED metadata.

    Journal ``sl`` is the fill-adjusted engine floor. It is used only when no
    matching event exists. ``live_atr`` <= 0 is counted and not walked.
    ``candle_idx`` on the journal is the 1-based loop counter and is not an
    entry index.
    """
    opened: dict[str, dict] = {}
    for ev in events:
        if ev.get("event") != "TRADE_OPENED":
            continue
        meta = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
        key = meta.get("id")
        if key is None or str(key) in opened:
            continue
        opened[str(key)] = ev

    cost = xau_measured_cost_model()
    rows: list[dict] = []
    notes: list[str] = []
    n_floored = 0
    n_atr_unpublished = 0
    n_price_fallback = 0
    n_walk_failed = 0
    n_diagnostic_failed = 0

    for row in journal_rows:
        trade_id = str(row.get("trade_id", ""))
        atr = _f(row.get("live_atr"))
        if atr is None or atr <= 0:
            n_atr_unpublished += 1
            notes.append(f"{trade_id}: live_atr missing or not positive; R not published")
            continue
        ev = opened.get(trade_id)
        prices = _event_prices(ev) if ev is not None else None
        if prices is None:
            n_price_fallback += 1
            notes.append(f"{trade_id}: no TRADE_OPENED metadata; journal prices used")
            entry_index = _index_for_timestamp(candles, str(row.get("opened_at", "")))
            if entry_index is None:
                n_walk_failed += 1
                notes.append(f"{trade_id}: opened_at did not match a projected bar")
                continue
            try:
                direction = _side(row.get("direction"))
            except ValueError as exc:
                n_walk_failed += 1
                notes.append(f"{trade_id}: {exc}")
                continue
            structural = {
                "entry": _f(row.get("entry_raw")),
                "sl": _f(row.get("sl")),
                "tp1": _f(row.get("tp1")),
                "tp2": _f(row.get("tp2")),
            }
            if any(v is None for v in structural.values()):
                n_walk_failed += 1
                notes.append(f"{trade_id}: journal price missing")
                continue
        else:
            try:
                direction = _side(prices["direction"] or row.get("direction"))
            except ValueError as exc:
                n_walk_failed += 1
                notes.append(f"{trade_id}: {exc}")
                continue
            entry_index = prices["entry_index"]
            structural = {
                "entry": prices["entry"],
                "sl": prices["sl"],
                "tp1": prices["tp1"],
                "tp2": prices["tp2"],
            }
        try:
            floored = apply_stop_floor(
                structural["entry"], structural["sl"], structural["tp1"], structural["tp2"],
                atr, direction,
            )
        except ValueError as exc:
            n_walk_failed += 1
            notes.append(f"{trade_id}: {exc}")
            continue
        if floored["floored"]:
            n_floored += 1
        future = [c for c in candles if int(c.index) > int(entry_index)]
        try:
            outcome = multi_tp_walk(
                floored["entry"], floored["direction"], floored["sl"], floored["tp1"], floored["tp2"],
                future,
                partial_fraction=0.5,
                tie_break="production",
                trail_fraction=0.5,
                max_forward=int(ttl),
                adverse_fill=_ADVERSE,
                entry_index=int(entry_index),
            )
        except ValueError as exc:
            n_walk_failed += 1
            notes.append(f"{trade_id}: walk {exc}")
            continue
        if floored["floored"]:
            try:
                multi_tp_walk(
                    structural["entry"], direction, structural["sl"], structural["tp1"], structural["tp2"],
                    future,
                    partial_fraction=0.5,
                    tie_break="production",
                    trail_fraction=0.5,
                    max_forward=int(ttl),
                    adverse_fill=_ADVERSE,
                    entry_index=int(entry_index),
                )
            except ValueError as exc:
                n_diagnostic_failed += 1
                notes.append(f"{trade_id}: diagnostic walk {exc}")
        net = cost.net_rr(
            outcome.rr_gross,
            floored["entry"],
            floored["risk"],
            exit_kind=outcome.exit_kind,
            direction=floored["direction"],
            nights_held=0,
        )
        duration = int(outcome.duration_candles)
        exit_idx = int(entry_index) + duration
        mark = next((c.close for c in candles if int(c.index) == exit_idx), None)
        if duration == 0:
            passive = 0.0
        elif mark is None:
            passive = None
            notes.append(f"{trade_id}: exit bar {exit_idx} missing; drift not computed")
        else:
            passive = passive_drift_r(floored["entry"], mark, floored["risk"], floored["direction"])
        rows.append({
            "trade_id": trade_id,
            "entry_idx": int(entry_index),
            "exit_idx": exit_idx,
            "sweep_idx": latest_sweep_index(events, int(entry_index)),
            "direction": floored["direction"],
            "holding": duration,
            "risk": floored["risk"],
            "net_r": float(net),
            "passive_r": passive,
            "floored": bool(floored["floored"]),
            "price_source": "event_metadata" if prices is not None else "journal_fallback",
        })

    return {
        "rows": rows,
        "n_journal": len(journal_rows),
        "n_floored": n_floored,
        "n_atr_unpublished": n_atr_unpublished,
        "n_price_fallback": n_price_fallback,
        "n_walk_failed": n_walk_failed,
        "n_diagnostic_failed": n_diagnostic_failed,
        "notes": notes,
    }


def _control_kwargs(rows: list[dict], candles) -> dict:
    """CI inputs. Called only after the cluster floor is met."""
    ids = assign_clusters(rows)
    groups: dict[int, list[float]] = {}
    long_groups: dict[int, list[float]] = {}
    short_groups: dict[int, list[float]] = {}
    for row, cid in zip(rows, ids):
        if row.get("passive_r") is None:
            return {
                "ci_low_vs_drift": None,
                "random_percentile": None,
                "long_ci_low": None,
                "short_ci_low": None,
            }
        delta = float(row["net_r"]) - float(row["passive_r"])
        groups.setdefault(cid, []).append(delta)
        side_map = long_groups if row["direction"] == "long" else short_groups
        side_map.setdefault(cid, []).append(delta)

    def _low(grouped: dict[int, list[float]]) -> float | None:
        if not grouped:
            return None
        return float(cluster_bootstrap_mean_ci(list(grouped.values()))["low"])

    closes = [float(c.close) for c in candles]
    templates = [
        {"direction": row["direction"], "holding": int(row["holding"]), "risk": float(row["risk"])}
        for row in rows
    ]
    try:
        samples = random_entry_means(closes, templates, random_seeds())
        crt_mean = sum(float(r["net_r"]) for r in rows) / len(rows)
        rank = percentile_rank(crt_mean, samples)
    except ValueError:
        rank = None
    return {
        "ci_low_vs_drift": _low(groups),
        "random_percentile": rank,
        "long_ci_low": _low(long_groups),
        "short_ci_low": _low(short_groups),
    }


def assemble_report(
    *,
    timeframe: str,
    parent: dict,
    projected_n: int,
    funnel: dict,
    walk: dict,
    candles,
) -> dict:
    """Public report. Omits every R aggregate while expectancy_published is false."""
    rows = list(walk["rows"])
    n = 0 if not rows else len(set(assign_clusters(rows)))
    controls = None
    if n >= N_CLUSTERS_MIN and rows:
        controls = _control_kwargs(rows, candles)
        label = verdict(n_clusters=n, **controls)
    else:
        label = verdict(n_clusters=n)
    report = {
        "timeframe": timeframe,
        "status": "OK",
        "parent_path": parent["path"],
        "parent_n": parent["n"],
        "parent_first": parent["first"],
        "parent_last": parent["last"],
        "parent_sha256": parent["sha256"],
        "projected_n": int(projected_n),
        "funnel": funnel,
        "n_journal": walk["n_journal"],
        "n_walked": len(rows),
        "n_clusters": n,
        "n_floored": walk["n_floored"],
        "n_atr_unpublished": walk["n_atr_unpublished"],
        "n_price_fallback": walk["n_price_fallback"],
        "n_walk_failed": walk["n_walk_failed"],
        "n_diagnostic_failed": walk["n_diagnostic_failed"],
        "controls_applicable": bool(label["expectancy_published"]),
        "verdict": label["verdict"],
        "failing_condition": label["failing_condition"],
        "expectancy_published": bool(label["expectancy_published"]),
        "cost_model_id": "component_measured.v1",
        "cluster_floor": N_CLUSTERS_MIN,
        "notes": list(walk["notes"]),
    }
    if label["expectancy_published"] and controls is not None:
        report["control"] = controls
    return _without_unpublished_r(report)


def _without_unpublished_r(report: dict) -> dict:
    if report.get("expectancy_published"):
        return report
    report.pop("control", None)
    blob = json.dumps(report)
    for token in ('"mean_r"', '"net_r"', '"gross_r"', '"ci_low', '"random_percentile"'):
        if token in blob:
            raise RuntimeError(f"unpublished report still carries {token}")
    return report


def _plumbing(timeframe: str, message: str) -> dict:
    return {
        "timeframe": timeframe,
        "status": "PLUMBING_FAILURE",
        "error": message,
        "expectancy_published": False,
        "controls_applicable": False,
    }


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_artifacts(output_dir: Path) -> tuple[list[dict], list[dict]]:
    events_paths = sorted(output_dir.rglob("*_events.jsonl"), key=lambda p: p.stat().st_mtime)
    trade_paths = sorted(output_dir.rglob("*_trades.csv"), key=lambda p: p.stat().st_mtime)
    events = _read_jsonl(events_paths[-1]) if events_paths else []
    if not trade_paths:
        return events, []
    with trade_paths[-1].open(encoding="utf-8", newline="") as fh:
        trades = list(csv.DictReader(fh))
    return events, trades


def execute_timeframe(
    timeframe: str,
    candles,
    csv_path: str | Path,
    output_dir: str | Path,
    *,
    parent: dict,
) -> dict:
    """Run one projected series. Imports the backtest stack only inside this function."""
    if os.environ.get("BACKTEST_ENGINE_GATE") is not None:
        return _plumbing(
            timeframe,
            "BACKTEST_ENGINE_GATE is set; the sealed clone keeps engine_gate_enabled false "
            "and this run does not apply that override.",
        )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = Path(csv_path)
    try:
        from runtime.backtest_v2 import BacktestConfig, BacktestRunner

        if os.environ.get("BACKTEST_ENGINE_GATE") is not None:
            return _plumbing(
                timeframe,
                "BACKTEST_ENGINE_GATE became set while importing the runner; run refused.",
            )
        clone = build_clone(timeframe)
        ttl = int(dict(knob_specs(timeframe))[("setup", "trade_ttl_candles")])
        crt = load_crt_config(clone, output_dir / "_registry")
        with bind_research_config(clone):
            cfg = BacktestConfig.from_prod_config(
                "XAUUSD",
                pip_size=0.01,
                crt_config=crt,
                scorer_mode="calibrated",
                allow_router_crt_config=False,
                strategy_id="",
            )
            runner = BacktestRunner(cfg, csv_path=str(csv_path))
            admitted = Path(str(runner.csv_path)).name
            if admitted != PROJECTED_CSV_NAME:
                return _plumbing(
                    timeframe,
                    f"admission kept {admitted!r}; the projected file must stay {PROJECTED_CSV_NAME}",
                )
            runner.run(iter(candles), len(candles), output_dir=str(output_dir))
        events, trades = _read_artifacts(output_dir)
        walk = walk_journal(candles, events, trades, ttl=ttl)
        funnel = funnel_counts(events, len(trades))
        return assemble_report(
            timeframe=timeframe,
            parent=parent,
            projected_n=len(candles),
            funnel=funnel,
            walk=walk,
            candles=candles,
        )
    except Exception as exc:  # noqa: BLE001 — a failed run is a plumbing result, not a verdict
        return _plumbing(timeframe, f"{type(exc).__name__}: {exc}")


def format_funnel_line(report: dict) -> str:
    if report.get("status") != "OK":
        return f"{report.get('timeframe')} status=PLUMBING_FAILURE error={report.get('error')}"
    funnel = report.get("funnel") or {}
    return (
        f"{report['timeframe']} projected_n={report['projected_n']} "
        f"SWEEP={funnel.get('SWEEP')} DISPLACEMENT={funnel.get('DISPLACEMENT')} "
        f"EXPANSION={funnel.get('EXPANSION')} RETEST={funnel.get('RETEST')} "
        f"TRADE_OPENED={funnel.get('TRADE_OPENED')} journal={funnel.get('journal_trades')} "
        f"n_walked={report['n_walked']} n_clusters={report['n_clusters']} "
        f"verdict={report['verdict']} expectancy_published={str(report['expectancy_published']).lower()}"
    )


def render_funnel_markdown(payload: dict) -> str:
    """Counts and the pre-registered label. No R aggregate unless the floor is met."""
    parent = payload["parent"]
    lines = [
        "# Program 12 Slice 2 funnel",
        "",
        "Lane: measurement / evidence. `economic_claims_allowed` is false. No G001.",
        "Ladder corpus = the one-month slice (pre-registration §17, 2026-10-06).",
        "Depth caveat stands. Path A long fetch stays deferred. D1 is not in this slice.",
        "Native H4/D1 from 1998 stay on disk for F-080 parity.",
        "",
        f"- Parent: `{parent['path']}`",
        f"- Bars: {parent['n']}",
        f"- First: {parent['first']}",
        f"- Last: {parent['last']}",
        f"- sha256: `{parent['sha256']}`",
        "- Contract: `MC-LADDER-XAUUSD-HTF-V1`",
        "- Cost ruler on the research walk: `component_measured.v1` (SEM-015). Journal pnl is a different ruler.",
        "",
    ]
    for report in payload["timeframes"]:
        lines.append(f"## {report.get('timeframe')}")
        lines.append("")
        if report.get("status") != "OK":
            lines.append("- Status: PLUMBING_FAILURE")
            lines.append(f"- Error: {report.get('error')}")
            lines.append("- expectancy_published: false")
            lines.append("")
            continue
        funnel = report["funnel"]
        lines.append(f"- Status: {report['status']}")
        lines.append(f"- Projected bars: {report['projected_n']}")
        lines.append(
            "- Funnel: "
            f"SWEEP {funnel['SWEEP']}, DISPLACEMENT {funnel['DISPLACEMENT']}, "
            f"EXPANSION {funnel['EXPANSION']}, RETEST {funnel['RETEST']}, "
            f"TRADE_OPENED {funnel['TRADE_OPENED']}, journal {funnel['journal_trades']}"
        )
        lines.append(f"- Walked (R computed, not printed): {report['n_walked']}")
        lines.append(f"- Clusters: {report['n_clusters']} (floor {report['cluster_floor']})")
        lines.append(f"- Stop floor widened: {report['n_floored']}")
        lines.append(f"- ATR unpublished: {report['n_atr_unpublished']}")
        lines.append(f"- Journal price fallback: {report['n_price_fallback']}")
        lines.append(f"- Walk failures: {report['n_walk_failed']}")
        lines.append(f"- Verdict: {report['verdict']}")
        lines.append(f"- Failing condition: {report['failing_condition']}")
        lines.append(f"- expectancy_published: {str(report['expectancy_published']).lower()}")
        lines.append(f"- Controls used as a gate: {str(report['controls_applicable']).lower()}")
        if report.get("notes"):
            lines.append("- Notes:")
            for note in report["notes"]:
                lines.append(f"  - {note}")
        lines.append("")
    lines.append(
        "A cluster count under 30 is INSUFFICIENT. This page records the funnel and "
        "whether the ladder ran. It is not an E[R] result."
    )
    lines.append("")
    text = "\n".join(lines)
    if '"mean_r"' in text or " mean_r" in text:
        raise RuntimeError("funnel markdown carried a mean")
    return text
