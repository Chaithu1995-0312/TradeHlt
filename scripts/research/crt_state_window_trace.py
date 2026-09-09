#!/usr/bin/env python3
"""Per-bar ENGINE vs RESOLVER state trace over named bar windows, with divergence causes.

WHY THIS EXISTS
---------------
`crt_state_confusion_matrix.py` already computes the aligned per-bar engine/resolver
series and `crt_parity_classifier.py` already holds the divergence taxonomy, but the
confusion matrix's JSON payload writes AGGREGATES only (counts, matrix, top confusions).
Nothing exposes the per-bar pair, which is what a traced diagram — or any human wanting
to look at one specific bar — actually needs.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not re-implement the alignment, the resolver run, or the cause classification.
Every real computation is imported:

    build_resolver_timeline / prepare_engine_context / _injection_maps_for_mode
        <- scripts/research/crt_state_confusion_matrix.py
    classify_mismatch / MismatchContext / CATEGORY_PRECEDENCE
        <- scripts/research/crt_parity_classifier.py

A second implementation of the engine<->resolver mapping is the exact divergence class
F-046 and F-069 already record, and re-deriving the cause table would be the FM-058 /
SP-001 "join is not identity" error that the classifier's own header warns about. The
only logic written here is the index zip (mirroring `build_confusion` lines 616-620
verbatim, referenced not reinvented) and the window slicing.

AUTHORITY
---------
OBSERVATION_ONLY. Reads OHLCV + an engine events.jsonl, writes one JSON report. Touches
no config, no model, no production path. Grants nothing (CLAUDE.md 6.5).

SCOPE CAVEAT CARRIED INTO THE OUTPUT
------------------------------------
Engine states come from ONE run's events.jsonl under whatever config produced it; the
resolver is the declarative `when:` machine. They are DIFFERENT CONSTRUCTIONS (F-069:
88.16% agreement, EXPANSION recall 10.77%), which is the entire reason this tool emits
both rather than one. The frame definition is recorded in the output so a reader never
has to guess which denominator a count belongs to.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def _load_sibling(name: str):
    """Import a sibling script by path (they are scripts, not a package)."""
    path = _HERE.parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_CM = _load_sibling("crt_state_confusion_matrix")
_CL = _load_sibling("crt_parity_classifier")
_CR = _load_sibling("crt_parity_report")


def _parse_windows(spec: str) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        lo, _, hi = chunk.partition(":")
        if not hi:
            raise ValueError(f"window {chunk!r} must be LO:HI")
        a, b = int(lo), int(hi)
        if b < a:
            raise ValueError(f"window {chunk!r} has HI < LO")
        out.append((a, b))
    if not out:
        raise ValueError("no windows parsed")
    return out


def _frame_definition(ohlcv_path: Path, source_indices: list[int]) -> dict[str, Any]:
    """Record WHICH denominator every count in this file belongs to.

    Four different bar counts circulate for XAUUSD M15 and they are all correct for
    their own frame; leaving that implicit is how a holdout gets cut against the wrong
    one. Written explicitly so it cannot be misread.
    """
    import pandas as pd

    raw_n = len(pd.read_csv(ohlcv_path, usecols=[0]))
    first_pos = source_indices[0] if source_indices else None
    return {
        "raw_corpus_bars": raw_n,
        "raw_corpus_path": str(ohlcv_path).replace("\\", "/"),
        "warmup_dropped": first_pos,
        "resolver_frame_bars": len(source_indices),
        "note": (
            "raw_corpus_bars is the only bar count for the FILE. The resolver frame is "
            "shorter because FeaturePipeline.finalize() drops a warmup head. A third "
            "figure (the oracle scan frame) subtracts a further forward-label horizon "
            "and is NOT used here. SEPARATELY from bar COUNTS there are two bar INDEX "
            "SPACES: an events.jsonl `candle_index` is the engine's own process_candle "
            "counter, NOT a raw CSV row -- see engine_to_raw_offset_measured. Conflating "
            "the two silently slices the wrong bars."
        ),
    }


def _engine_to_raw_offsets(events_path: Path, ohlcv_path: Path) -> dict[int, int]:
    """engine `candle_index` -> raw OHLCV row, by timestamp join.

    TWO INDEX SPACES EXIST AND THEY ARE NOT INTERCHANGEABLE. An events.jsonl
    `candle_index` comes from `process_candle`'s internal counter; the resolver and
    FeaturePipeline index raw CSV rows. `crt_state_confusion_matrix.remap_event_indices_
    to_ohlcv` already handles this internally, so its OUTPUT is raw-space -- which means a
    window quoted from a raw reading of events.jsonl is in the WRONG space for slicing it.
    That is a live footgun (it produced a silently wrong first run of this tool), so the
    space is an explicit argument here rather than an assumption.

    NOTE the offset is measured per run, never assumed: `remap_event_indices_to_ohlcv`'s
    docstring states "a constant +74 offset" for XAUUSD M15 MT5, but the 2026-08-15
    g001_baseline_f074on run measures **+62** (6,991 events; 121 further events at +0).
    The docstring figure is stale; this function reads the actual join.
    """
    import pandas as pd

    df = pd.read_csv(ohlcv_path)
    df.columns = [c.lower() for c in df.columns]
    ts_col = "timestamp" if "timestamp" in df.columns else "time"
    df[ts_col] = pd.to_datetime(df[ts_col])
    ts_to_raw = {pd.Timestamp(t): i for i, t in enumerate(df[ts_col])}
    out: dict[int, int] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        raw = ts_to_raw.get(pd.Timestamp(e["timestamp"]))
        if raw is not None and e.get("candle_index") is not None:
            out[int(e["candle_index"])] = int(raw)
    return out


def trace_windows(
    ohlcv_path: Path,
    events_path: Path,
    windows: list[tuple[int, int]],
    *,
    config_path: Path | None = None,
    injection: str = "none",
    engine_mode: str = "exit",
    htf_mode: str = "engine",
    instrument: str = "XAUUSD",
    window_space: str = "raw",
) -> dict[str, Any]:
    eng_to_raw = _engine_to_raw_offsets(events_path, ohlcv_path)
    if window_space == "engine":
        translated = []
        for lo, hi in windows:
            r_lo, r_hi = eng_to_raw.get(lo), eng_to_raw.get(hi)
            if r_lo is None or r_hi is None:
                raise ValueError(
                    f"engine-space window {lo}:{hi} has no timestamp join to a raw row "
                    f"(lo->{r_lo}, hi->{r_hi}); quote it in raw space instead"
                )
            translated.append((r_lo, r_hi))
        windows_raw = translated
    else:
        windows_raw = list(windows)

    ctx = _CM.prepare_engine_context(ohlcv_path, events_path)
    reset_map, state_to_map = _CM._injection_maps_for_mode(
        injection, ctx.engine_reset_by_idx, ctx.engine_state_to_by_idx
    )
    res_states, source_indices, res_meta = _CM.build_resolver_timeline(
        ohlcv_path,
        config_path,
        htf_mode=htf_mode,
        instrument=instrument,
        engine_reset_by_idx=reset_map,
        engine_state_to_by_idx=state_to_map,
    )
    engine_states = (
        ctx.timeline.enter_states if engine_mode == "enter" else ctx.timeline.exit_states
    )

    # Alignment — mirrors crt_state_confusion_matrix.build_confusion:616-620 exactly.
    pair_by_idx: dict[int, tuple[str, str]] = {}
    for res_i, src_i in enumerate(source_indices):
        if 0 <= src_i < len(engine_states):
            pair_by_idx[src_i] = (engine_states[src_i], res_states[res_i])

    # State marginals over the WHOLE aligned corpus, not the windows. The power gate in
    # classify_mismatch asks "how often does the engine reach this state at all", which
    # is a corpus property; computing it per-window would make every cell look starved.
    marginals: dict[str, tuple[int, int, int]] = {}
    for eng, res in pair_by_idx.values():
        e_n, r_n, tp = marginals.get(eng, (0, 0, 0))
        marginals[eng] = (e_n + 1, r_n, tp + (1 if eng == res else 0))
    for eng, res in pair_by_idx.values():
        e_n, r_n, tp = marginals.get(res, (0, 0, 0))
        marginals[res] = (e_n, r_n + 1, tp)

    # The classifier's A-/C- branches are DECLARED allowlists, not inference: C-GEOMETRY
    # fires only for pairs in `known_geometry_divergent_pairs`, B-NO-COUNTERPART only for
    # names in `engine_only_threshold_names`. Running with an empty context therefore
    # collapses almost everything to D-UNKNOWN and would look like a taxonomy gap when it
    # is really an under-configured run -- which is exactly what the first execution of
    # this script produced. Reuse crt_parity_report's canonical sets; do not re-author them.
    mm_ctx = _CL.MismatchContext(
        state_marginals=marginals,
        engine_only_threshold_names=_CR.ENGINE_ONLY_THRESHOLD_NAMES,
        known_geometry_divergent_pairs=_CR.KNOWN_GEOMETRY_DIVERGENT_PAIRS,
    )

    reason_by_idx: dict[int, str] = {}
    for ev in ctx.events:
        if ev.get("event") == "STATE_TRANSITION" and ev.get("reason"):
            reason_by_idx[int(ev["candle_index"])] = str(ev["reason"])

    out_windows = []
    for lo, hi in windows_raw:
        rows = []
        for idx in range(lo, hi + 1):
            if idx not in pair_by_idx:
                continue
            eng, res = pair_by_idx[idx]
            agree = eng == res
            row: dict[str, Any] = {
                "candle_index": idx,
                "engine_state": eng,
                "resolver_state": res,
                "agree": agree,
            }
            if (reason := reason_by_idx.get(idx)) is not None:
                row["engine_transition_reason"] = reason
            if not agree:
                cl = _CL.classify_mismatch(
                    eng, res,
                    {"engine_transition_reason": reason_by_idx.get(idx)},
                    mm_ctx,
                )
                row["divergence_code"] = cl.code
                row["divergence_category"] = cl.category
                row["divergence_summary"] = cl.summary
            rows.append(row)
        n_div = sum(1 for r in rows if not r["agree"])
        out_windows.append({
            "window_raw": f"{lo}:{hi}",
            "bars_in_window": len(rows),
            "bars_agree": len(rows) - n_div,
            "bars_divergent": n_div,
            "codes": sorted({r["divergence_code"] for r in rows if not r["agree"]}),
            "rows": rows,
        })

    return {
        "authority": "observation_only",
        "economic_claims_allowed": False,
        "engine_run": str(events_path.parent).replace("\\", "/"),
        "engine_mode": engine_mode,
        "injection": injection,
        "frame": _frame_definition(ohlcv_path, source_indices),
        "aligned_bars_total": len(pair_by_idx),
        "window_space_requested": window_space,
        "engine_to_raw_offset_measured": (
            sorted({r - e for e, r in eng_to_raw.items()})
        ),
        "taxonomy_members": list(_CL.CATEGORY_PRECEDENCE),
        "classifier_context_source": (
            "crt_parity_report.ENGINE_ONLY_THRESHOLD_NAMES + "
            "KNOWN_GEOMETRY_DIVERGENT_PAIRS (canonical, not re-authored here)"
        ),
        "retest_cascade_note": _CR.RETEST_CASCADE_NOTE,
        "d_unknown_caveat": (
            "D-UNKNOWN is the classifier's explicit fallthrough (\"investigated, never "
            "left silently unlabeled\"), NOT proof the taxonomy lacks a member. RETEST in "
            "particular is a DELIBERATE exclusion from the geometry set -- see "
            "retest_cascade_note -- so a RETEST D-UNKNOWN is a recorded choice, not a gap."
        ),
        "resolver_meta": res_meta,
        "windows": out_windows,
        "scope_caveat": (
            "engine_state and resolver_state are DIFFERENT CONSTRUCTIONS, not two "
            "measurements of one thing (F-069: 88.16% agreement, EXPANSION recall "
            "10.77%). Divergence is expected and is the subject, not an error."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ohlcv", required=True, type=Path)
    ap.add_argument("--events", required=True, type=Path)
    ap.add_argument("--windows", required=True,
                    help="comma-separated LO:HI raw candle-index ranges, e.g. 18007:18031,10782:10793")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--injection", default="none", choices=_CM.INJECTION_MODES)
    ap.add_argument("--engine-mode", default="exit", choices=("enter", "exit"))
    ap.add_argument("--htf-mode", default="engine")
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--window-space", default="raw", choices=("raw", "engine"),
                    help="index space of --windows. events.jsonl candle_index is ENGINE space; "
                         "the resolver/FeaturePipeline index RAW rows. Not interchangeable.")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()

    for p in (args.ohlcv, args.events):
        if not p.exists():
            print(f"[FATAL] missing {p}")
            return 2

    payload = trace_windows(
        args.ohlcv, args.events, _parse_windows(args.windows),
        config_path=args.config, injection=args.injection,
        engine_mode=args.engine_mode, htf_mode=args.htf_mode,
        instrument=args.instrument, window_space=args.window_space,
    )

    for w in payload["windows"]:
        print(f"\n  window {w['window_raw']}  bars={w['bars_in_window']} "
              f"agree={w['bars_agree']} divergent={w['bars_divergent']}  codes={w['codes']}")
        for r in w["rows"]:
            flag = "  " if r["agree"] else "!="
            code = r.get("divergence_code", "")
            print(f"    {flag} idx={r['candle_index']:6d}  engine={r['engine_state']:16s}"
                  f"resolver={r['resolver_state']:16s}{code}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nwritten: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
