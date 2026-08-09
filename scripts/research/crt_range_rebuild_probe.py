"""
CRT range-rebuild edge probe (OBSERVATION_ONLY, research shadow)
================================================================
Classifies residual SWEEP↔RANGE disagreement after B1 by comparing:

  1. Engine-like active_range reconstructed from OHLCV + RESET events
     (mirrors crt_engine_v2: buffer append → on RESET rebuild from
     candle_buffer[-atr_period:] → detect_sweep geometry)
  2. CRTStateResolver range memory (h_ref/l_ref) after B1 htf_range path

Does NOT modify production spine, FeaturePipeline, or market_crt_states defaults.
Authority: research / documentation only.

Usage:
    python scripts/research/crt_range_rebuild_probe.py \\
        --ohlcv data/mt5/XAUUSD_M15.csv \\
        --events results/run_20260805_105350_XAUUSD/XAUUSD_events.jsonl \\
        --output reports/parity_experiment/range_rebuild_edge_probe.md
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

logger = logging.getLogger("RANGE_REBUILD_PROBE")


@dataclass
class RangeSnap:
    h_ref: float
    l_ref: float
    ready: bool
    source: str  # "seed" | "reset" | "carry" | "none"


@dataclass
class BarDiag:
    idx: int
    engine_state: str
    resolver_state: str
    eng_h: float
    eng_l: float
    res_h: float
    res_l: float
    eng_ready: bool
    res_ready: bool
    eng_sweep_sig: int  # +1/-1/0
    res_sweep_sig: int
    range_match: bool  # both ready and |dh|<eps and |dl|<eps
    high: float
    low: float
    close: float
    htf_id: str
    reset_this_bar: bool
    class_tag: str


def _detect_sweep(high: float, low: float, close: float, h_ref: float, l_ref: float) -> int:
    """Engine RangeDetector.detect_sweep geometry (strict close inequalities)."""
    swept_high = high > h_ref and close < h_ref
    swept_low = low < l_ref and close > l_ref
    if not swept_high and not swept_low:
        return 0
    if swept_high:
        return 1
    return -1


def _eps_equal(a: float, b: float, rel: float = 1e-9, abs_: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b), 1.0))


def load_ohlcv(path: Path):
    import pandas as pd
    import numpy as np

    df = pd.read_csv(path)
    rename = {
        c: c.lower()
        for c in df.columns
        if c.lower() in {"open", "high", "low", "close", "volume", "timestamp", "time"}
    }
    df = df.rename(columns=rename)
    df = df.copy()
    df["_src_idx"] = np.arange(len(df), dtype=np.int64)
    return df


def load_events(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_ord"] = i
            out.append(rec)
    return out


def _load_confusion_helpers():
    """Import reconstruct_engine_timeline without requiring scripts/ as a package."""
    import importlib.util

    path = _ROOT / "scripts" / "research" / "crt_state_confusion_matrix.py"
    name = "crt_state_confusion_matrix_probe"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # required before exec for @dataclass on 3.12+
    spec.loader.exec_module(mod)
    return mod


def reconstruct_engine_range_timeline(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
    events: list[dict[str, Any]],
    *,
    atr_period: int = 14,
    htf_candles: int = 4,
    warmup: int = 78,
    instrument: str = "XAUUSD",
) -> tuple[list[RangeSnap], list[int], dict[str, Any]]:
    """Replay engine-like range freezes over raw OHLCV indices.

    Alignment notes (from crt_engine_v2 + backtest_v2):
      * HTFBuilder pushes every bar; seed_candles = last completed HTF window.
      * After warmup, initialise_range(seed) freezes range from seed (size≈htf_candles).
      * process_candle appends to buffer then on RESET rebuilds from buffer[-atr_period:].
      * Events RESET candle_index is treated as the rebuild bar (state_from-guarded).

    Returns per-bar RangeSnap (length n), engine sweep signal per bar, meta.
    """
    cm = _load_confusion_helpers()
    timeline = cm.reconstruct_engine_timeline(events, len(highs))
    n = len(highs)
    enter = timeline.enter_states

    # RESET bars (HTF/gap/other) with state_from guard using running state
    resets_by_idx: dict[int, list[dict]] = defaultdict(list)
    for e in events:
        if e.get("event") != "RESET" or not e.get("state_to"):
            continue
        resets_by_idx[int(e["candle_index"])].append(e)

    ranges: list[RangeSnap] = [
        RangeSnap(0.0, 0.0, False, "none") for _ in range(n)
    ]
    eng_sig = [0] * n
    buffer: list[tuple[float, float, float, float]] = []
    cap = max(atr_period * 3, 48)
    h_ref = l_ref = 0.0
    ready = False
    source = "none"
    initialised = False
    cur_state = "RANGE"
    n_rebuild_reset = 0
    n_seed = 0

    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        buffer.append((o, h, l, c))
        if len(buffer) > cap:
            del buffer[: len(buffer) - cap]

        # Warmup: only fill buffer / HTF (backtest skips process until warmup done)
        if i < warmup:
            ranges[i] = RangeSnap(h_ref, l_ref, ready, "warmup")
            # still track state from timeline for post-warmup continuity
            cur_state = enter[i] if i < len(enter) else cur_state
            continue

        # Init once: freeze seed window = last htf_candles of buffer (seed_candles)
        if not initialised:
            if len(buffer) >= htf_candles:
                window = buffer[-htf_candles:]
                h_ref = max(b[1] for b in window)
                l_ref = min(b[2] for b in window)
                ready = h_ref > l_ref
                source = "seed"
                initialised = True
                n_seed += 1
            ranges[i] = RangeSnap(h_ref, l_ref, ready, source)
            eng_sig[i] = (
                _detect_sweep(h, l, c, h_ref, l_ref) if ready else 0
            )
            cur_state = enter[i] if i < len(enter) else cur_state
            continue

        # Apply RESET rebuilds that match running state (engine state_from)
        rebuilt = False
        if i in resets_by_idx:
            for e in resets_by_idx[i]:
                sf = e.get("state_from")
                if sf is not None and sf != cur_state:
                    continue
                window = buffer[-atr_period:] if len(buffer) >= atr_period else buffer[:]
                h_ref = max(b[1] for b in window)
                l_ref = min(b[2] for b in window)
                ready = h_ref > l_ref
                source = "reset"
                rebuilt = True
                n_rebuild_reset += 1
                break

        if not rebuilt and ready:
            source = "carry"

        ranges[i] = RangeSnap(h_ref, l_ref, ready, source)
        eng_sig[i] = _detect_sweep(h, l, c, h_ref, l_ref) if ready else 0
        # Advance running state to exit of this bar via enter[i+1] if available
        # enter[i] is state at bar open; after events, exit is enter of next or
        # reconstruct from timeline.exit_states if we re-run reconstruct.
        cur_state = timeline.exit_states[i] if i < len(timeline.exit_states) else cur_state

    meta = {
        "n_bars": n,
        "warmup": warmup,
        "atr_period": atr_period,
        "htf_candles": htf_candles,
        "n_seed": n_seed,
        "n_rebuild_reset": n_rebuild_reset,
        "n_ready": sum(1 for r in ranges if r.ready),
        "timeline_notes": timeline.reconstruction_notes,
    }
    return ranges, eng_sig, meta


def run_resolver_range_timeline(
    ohlcv_path: Path,
    *,
    config_path: Optional[Path] = None,
    instrument: str = "XAUUSD",
    htf_candles: int = 4,
    events: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[str], list[int], list[RangeSnap], list[int], dict[str, Any]]:
    """FeaturePipeline + CRTStateResolver; capture range memory each bar.

    When ``events`` is provided, inject engine RESET bars (B1b) so freezes
    follow the engine process_candle rebuild sequence.
    """
    import pandas as pd
    import numpy as np
    from features.feature_pipeline import FeaturePipeline
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.feature_schema import CANONICAL_FEATURES

    df = load_ohlcv(ohlcv_path)
    n_raw = len(df)
    pipe = FeaturePipeline(df)
    enriched, _ = pipe.run()
    source_indices = [int(v) for v in enriched["_src_idx"].tolist()]

    resolver = CRTStateResolver(config_path=config_path)
    thr = resolver._config.get("thresholds", {})
    rsi_ob = float(thr.get("rsi_overbought", 70.0))
    rsi_os = float(thr.get("rsi_oversold", 30.0))
    life = thr.get("lifecycle") or {}
    cph = int(life.get("htf_candles_per_range", htf_candles))

    engine_htf_ids = build_htf_id_timeline(
        n_raw, candles_per_htf=cph, instrument=instrument
    )

    # Engine RESET injection: events should already be remapped to raw rows
    # by the caller (main remaps via confusion-matrix helper).
    engine_reset_by_idx: dict[int, str] = {}
    if events:
        _cur = "RANGE"
        _by_idx: dict[int, list] = defaultdict(list)
        for e in events:
            if e.get("event") in ("STATE_TRANSITION", "RESET") and e.get("state_to"):
                _by_idx[int(e["candle_index"])].append(e)
        for i in range(n_raw):
            for e in _by_idx.get(i, []):
                if (
                    e.get("event") == "RESET"
                    and e.get("state_from") is not None
                    and e.get("state_from") != _cur
                ):
                    continue
                if e.get("event") == "RESET":
                    engine_reset_by_idx[i] = str(e.get("reason") or "engine_reset")
                _cur = str(e["state_to"])

    first_src = int(source_indices[0]) if source_indices else 0
    if getattr(resolver, "_sweep_geometry", "") == "htf_range" and first_src > 0:
        raw_o = df["open"].astype(float).tolist()
        raw_h = df["high"].astype(float).tolist()
        raw_l = df["low"].astype(float).tolist()
        raw_c = df["close"].astype(float).tolist()
        for i in range(first_src):
            resolver.seed_ohlc(
                raw_o[i], raw_h[i], raw_l[i], raw_c[i], htf_id=engine_htf_ids[i]
            )
        # Engine: no process_candle (hence no RESET rebuild) during warmup —
        # only initialise_range(seed_candles) once after warmup.
        resolver.finalize_seed_range()

    ts_col = None
    for cand in ("timestamp", "time", "datetime"):
        if cand in enriched.columns:
            ts_col = cand
            break
    if ts_col is not None:
        enriched = enriched.copy()
        enriched[ts_col] = pd.to_datetime(enriched[ts_col])

    states: list[str] = []
    res_ranges: list[RangeSnap] = []
    res_sig: list[int] = []

    for row_i, (_, row) in enumerate(enriched.iterrows()):
        fv: dict[str, float] = {}
        for name in CANONICAL_FEATURES:
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
        for name in ("retest_flag", "displacement_flag"):
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
            else:
                fv[name] = 0.0
        rsi = fv.get("rsi_14", 50.0)
        if rsi > rsi_ob:
            fv["rsi_state"] = 1.0
        elif rsi < rsi_os:
            fv["rsi_state"] = -1.0
        else:
            fv["rsi_state"] = 0.0

        ts = row[ts_col] if ts_col is not None else None
        if ts is not None and pd.isna(ts):
            ts = None
        src = source_indices[row_i]
        htf_id = engine_htf_ids[src] if 0 <= src < len(engine_htf_ids) else None

        eng_rst = src in engine_reset_by_idx
        eng_rsn = engine_reset_by_idx.get(src)

        st = resolver.resolve(
            fv,
            timestamp=ts,
            htf_id=htf_id,
            engine_reset=eng_rst,
            reset_reason=eng_rsn,
        )
        mem = resolver.memory
        states.append(st)
        res_ranges.append(
            RangeSnap(
                mem.range_h_ref,
                mem.range_l_ref,
                bool(mem.range_ready),
                "resolver",
            )
        )
        res_sig.append(
            _detect_sweep(
                float(fv.get("high", 0.0)),
                float(fv.get("low", 0.0)),
                float(fv.get("close", 0.0)),
                mem.range_h_ref,
                mem.range_l_ref,
            )
            if mem.range_ready
            else 0
        )

    meta = {
        "n_raw": n_raw,
        "n_resolved": len(states),
        "first_src": first_src,
        "sweep_geometry": getattr(resolver, "_sweep_geometry", None),
        "range_atr_period": getattr(resolver, "_range_atr_period", None),
        "resolver_counts": dict(Counter(states)),
        "lifecycle_stats": resolver.lifecycle_stats,
        "engine_reset_injection": len(engine_reset_by_idx),
    }
    return states, source_indices, res_ranges, res_sig, meta


def classify_bar(
    eng_state: str,
    res_state: str,
    eng_sig: int,
    res_sig: int,
    range_match: bool,
    eng_ready: bool,
    res_ready: bool,
) -> str:
    """Label residual mechanism for SWEEP-related disagreement."""
    if eng_state == res_state:
        if eng_state == "SWEEP":
            return "AGREE_SWEEP"
        return "AGREE_OTHER"

    # SWEEP cell residuals
    if eng_state == "SWEEP" and res_state == "RANGE":
        if not res_ready:
            return "E_SWEEP_R_RANGE__resolver_range_not_ready"
        if not eng_ready:
            return "E_SWEEP_R_RANGE__engine_range_not_ready"
        if not range_match:
            return "E_SWEEP_R_RANGE__range_ref_diverge"
        if eng_sig != 0 and res_sig == 0:
            return "E_SWEEP_R_RANGE__signal_diverge_same_refs"  # should be rare if refs match
        if eng_sig == 0 and res_sig == 0:
            return "E_SWEEP_R_RANGE__sticky_or_lifecycle"  # engine holding SWEEP, no founding sig
        if eng_sig != 0 and res_sig != 0:
            return "E_SWEEP_R_RANGE__both_signal_but_state_miss"  # funnel/transition
        return "E_SWEEP_R_RANGE__other"

    if eng_state == "RANGE" and res_state == "SWEEP":
        if not res_ready:
            return "E_RANGE_R_SWEEP__resolver_range_not_ready"
        if not range_match and eng_ready:
            return "E_RANGE_R_SWEEP__range_ref_diverge"
        if res_sig != 0 and eng_sig == 0:
            return "E_RANGE_R_SWEEP__resolver_fp_signal"
        if res_sig != 0 and eng_sig != 0:
            return "E_RANGE_R_SWEEP__both_signal_engine_not_in_sweep"  # engine in different state machine path
        if res_sig == 0:
            return "E_RANGE_R_SWEEP__sticky_resolver"
        return "E_RANGE_R_SWEEP__other"

    if eng_state == "SWEEP" or res_state == "SWEEP":
        return f"SWEEP_MIXED__eng_{eng_state}__res_{res_state}"
    return "NON_SWEEP_MISMATCH"


def build_report(
    diags: list[BarDiag],
    eng_meta: dict,
    res_meta: dict,
    *,
    ohlcv: str,
    events: str,
) -> tuple[str, dict]:
    total = len(diags)
    agree = sum(1 for d in diags if d.engine_state == d.resolver_state)
    range_ready_both = sum(1 for d in diags if d.eng_ready and d.res_ready)
    range_match_n = sum(1 for d in diags if d.range_match)
    class_counts = Counter(d.class_tag for d in diags)

    # SWEEP residual focus
    e_s_r_r = [d for d in diags if d.engine_state == "SWEEP" and d.resolver_state == "RANGE"]
    e_r_r_s = [d for d in diags if d.engine_state == "RANGE" and d.resolver_state == "SWEEP"]

    # Range ref error stats where both ready
    both = [d for d in diags if d.eng_ready and d.res_ready]
    if both:
        dh = [abs(d.eng_h - d.res_h) for d in both]
        dl = [abs(d.eng_l - d.res_l) for d in both]
        import statistics as st

        ref_stats = {
            "n_both_ready": len(both),
            "frac_exact_match": sum(1 for d in both if d.range_match) / len(both),
            "mean_abs_dh": st.mean(dh),
            "mean_abs_dl": st.mean(dl),
            "median_abs_dh": st.median(dh),
            "median_abs_dl": st.median(dl),
            "p90_abs_dh": sorted(dh)[int(0.9 * len(dh)) - 1] if dh else 0,
            "p90_abs_dl": sorted(dl)[int(0.9 * len(dl)) - 1] if dl else 0,
        }
    else:
        ref_stats = {}

    lines: list[str] = []
    a = lines.append
    a("# CRT Range-Rebuild Edge Probe (OBSERVATION_ONLY)")
    a("")
    a(f"> Generated: {__import__('datetime').datetime.now().isoformat()}")
    a(">")
    a("> **Authority:** research only. No production behavior change.")
    a("> Purpose: classify residual SWEEP↔RANGE cells after B1 as range-ref")
    a("> divergence vs sticky/lifecycle vs false-positive signal.")
    a("")
    a("## Inputs")
    a("")
    a(f"| Field | Value |")
    a(f"|-------|-------|")
    a(f"| OHLCV | `{ohlcv}` |")
    a(f"| Events | `{events}` |")
    a(f"| Aligned bars | **{total:,}** |")
    a(f"| Sweep geometry | `{res_meta.get('sweep_geometry')}` |")
    a(f"| range_atr_period | `{res_meta.get('range_atr_period')}` |")
    a("")
    a("## Agreement (aligned slice)")
    a("")
    a(f"- Exact state match: **{agree:,} / {total:,} ({100*agree/total:.2f}%)**")
    a(f"- Both ranges ready: **{range_ready_both:,}**")
    a(f"- Range refs match (both ready + eps): **{range_match_n:,}** "
      f"({100*range_match_n/range_ready_both:.2f}% of both-ready)" if range_ready_both else "- Range refs match: n/a")
    a("")
    a("## Active-range reference error (both ready)")
    a("")
    if ref_stats:
        a(f"| Stat | Value |")
        a(f"|------|------:|")
        for k, v in ref_stats.items():
            if isinstance(v, float):
                a(f"| {k} | {v:.6g} |")
            else:
                a(f"| {k} | {v} |")
    else:
        a("_No bars with both ranges ready._")
    a("")
    a("## SWEEP residual classification")
    a("")
    a(f"- Engine SWEEP → Resolver RANGE: **{len(e_s_r_r):,}**")
    a(f"- Engine RANGE → Resolver SWEEP: **{len(e_r_r_s):,}**")
    a("")
    a("### Class histogram (all aligned bars)")
    a("")
    a("| Class | N | % |")
    a("|-------|--:|--:|")
    for tag, n in class_counts.most_common():
        a(f"| `{tag}` | {n:,} | {100*n/total:.2f}% |")
    a("")
    a("### Interpretation guide")
    a("")
    a("| Class prefix | Meaning | Next lever |")
    a("|--------------|---------|------------|")
    a("| `range_ref_diverge` | h_ref/l_ref disagree | rebuild window / seed timing / protect-state carry |")
    a("| `sticky_or_lifecycle` | engine holds SWEEP without founding sig this bar | age/HTF exit parity |")
    a("| `resolver_fp_signal` | resolver detects HTF sweep, engine not in SWEEP | engine already in other state / reset race |")
    a("| `both_signal_engine_not_in_sweep` | geometry agrees, state machine disagrees | funnel / state legality |")
    a("| `resolver_range_not_ready` | resolver missing active_range | seed_ohlc coverage |")
    a("")
    a("## Sample bars (first 25 of each residual cell)")
    a("")

    def _sample_table(rows: list[BarDiag], title: str) -> None:
        a(f"### {title}")
        a("")
        a("| idx | eng | res | class | eng_h | res_h | eng_l | res_l | eng_sig | res_sig | reset |")
        a("|----:|-----|-----|-------|------:|------:|------:|------:|--------:|--------:|:-----:|")
        for d in rows[:25]:
            a(
                f"| {d.idx} | {d.engine_state} | {d.resolver_state} | `{d.class_tag}` | "
                f"{d.eng_h:.4f} | {d.res_h:.4f} | {d.eng_l:.4f} | {d.res_l:.4f} | "
                f"{d.eng_sweep_sig} | {d.res_sweep_sig} | {int(d.reset_this_bar)} |"
            )
        a("")

    _sample_table(e_s_r_r, "Engine SWEEP → Resolver RANGE")
    _sample_table(e_r_r_s, "Engine RANGE → Resolver SWEEP")

    a("## Engine reconstruction meta")
    a("")
    a("```json")
    a(json.dumps(eng_meta, indent=2))
    a("```")
    a("")
    a("## Resolver meta")
    a("")
    a("```json")
    a(json.dumps({k: v for k, v in res_meta.items() if k != "lifecycle_stats"}, indent=2, default=str))
    a("```")
    a("")
    a("## Vision dual-geometry note")
    a("")
    a("If `range_ref_diverge` dominates residual SWEEP cells, Vision/ontology should")
    a("register **two distinct sweep geometries** as separate nodes (HTF-range vs")
    a("last-swing), not one overloaded `liquidity_sweep` state. If sticky/lifecycle")
    a("dominates, the residual is state-machine memory, not geometry ontology.")
    a("")

    payload = {
        "authority": "research_only",
        "observation_only": True,
        "total": total,
        "agreement": agree,
        "agreement_rate": agree / total if total else 0.0,
        "class_counts": dict(class_counts),
        "ref_stats": ref_stats,
        "e_sweep_r_range": len(e_s_r_r),
        "e_range_r_sweep": len(e_r_r_s),
        "eng_meta": eng_meta,
        "res_meta": res_meta,
        "samples": {
            "e_sweep_r_range": [
                {
                    "idx": d.idx,
                    "class": d.class_tag,
                    "eng_h": d.eng_h,
                    "res_h": d.res_h,
                    "eng_l": d.eng_l,
                    "res_l": d.res_l,
                    "eng_sig": d.eng_sweep_sig,
                    "res_sig": d.res_sweep_sig,
                }
                for d in e_s_r_r[:100]
            ],
            "e_range_r_sweep": [
                {
                    "idx": d.idx,
                    "class": d.class_tag,
                    "eng_h": d.eng_h,
                    "res_h": d.res_h,
                    "eng_l": d.eng_l,
                    "res_l": d.res_l,
                    "eng_sig": d.eng_sweep_sig,
                    "res_sig": d.res_sweep_sig,
                }
                for d in e_r_r_s[:100]
            ],
        },
    }
    return "\n".join(lines) + "\n", payload


def main() -> None:
    parser = argparse.ArgumentParser(description="OBSERVATION_ONLY range-rebuild edge probe")
    parser.add_argument("--ohlcv", default="data/mt5/XAUUSD_M15.csv")
    parser.add_argument(
        "--events",
        default="results/run_20260805_105350_XAUUSD/XAUUSD_events.jsonl",
    )
    parser.add_argument("--config", default=None, help="Optional market_crt_states.yaml")
    parser.add_argument("--instrument", default="XAUUSD")
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--htf-candles", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=78)
    parser.add_argument(
        "--output",
        default="reports/parity_experiment/range_rebuild_edge_probe.md",
    )
    parser.add_argument(
        "--json-out",
        default="reports/parity_experiment/range_rebuild_edge_probe.json",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    )

    ohlcv_path = Path(args.ohlcv)
    events_path = Path(args.events)
    if not ohlcv_path.exists() or not events_path.exists():
        print("ERROR: missing ohlcv or events")
        sys.exit(1)

    df = load_ohlcv(ohlcv_path)
    opens = df["open"].astype(float).tolist()
    highs = df["high"].astype(float).tolist()
    lows = df["low"].astype(float).tolist()
    closes = df["close"].astype(float).tolist()
    events = load_events(events_path)
    cm = _load_confusion_helpers()
    events, remap_meta = cm.remap_event_indices_to_ohlcv(events, ohlcv_path)
    logger.info("Remapped event indices: %s", remap_meta)

    logger.info("Reconstructing engine-like range timeline…")
    eng_ranges, eng_sig, eng_meta = reconstruct_engine_range_timeline(
        opens,
        highs,
        lows,
        closes,
        events,
        atr_period=args.atr_period,
        htf_candles=args.htf_candles,
        warmup=args.warmup,
        instrument=args.instrument,
    )
    eng_meta["index_remap"] = remap_meta

    logger.info("Running resolver range timeline (engine RESET injection)…")
    cfg = Path(args.config) if args.config else None
    res_states, src_idx, res_ranges, res_sig, res_meta = run_resolver_range_timeline(
        ohlcv_path,
        config_path=cfg,
        instrument=args.instrument,
        htf_candles=args.htf_candles,
        events=events,
    )

    eng_tl = cm.reconstruct_engine_timeline(events, len(highs))
    enter = eng_tl.enter_states

    # RESET set for annotation
    reset_idx = {
        int(e["candle_index"])
        for e in events
        if e.get("event") == "RESET"
    }

    diags: list[BarDiag] = []
    for ri, src in enumerate(src_idx):
        if not (0 <= src < len(enter)):
            continue
        er = eng_ranges[src]
        rr = res_ranges[ri]
        range_match = (
            er.ready
            and rr.ready
            and _eps_equal(er.h_ref, rr.h_ref)
            and _eps_equal(er.l_ref, rr.l_ref)
        )
        eng_st = enter[src]
        res_st = res_states[ri]
        tag = classify_bar(
            eng_st,
            res_st,
            eng_sig[src],
            res_sig[ri],
            range_match,
            er.ready,
            rr.ready,
        )
        diags.append(
            BarDiag(
                idx=src,
                engine_state=eng_st,
                resolver_state=res_st,
                eng_h=er.h_ref,
                eng_l=er.l_ref,
                res_h=rr.h_ref,
                res_l=rr.l_ref,
                eng_ready=er.ready,
                res_ready=rr.ready,
                eng_sweep_sig=eng_sig[src],
                res_sweep_sig=res_sig[ri],
                range_match=range_match,
                high=highs[src],
                low=lows[src],
                close=closes[src],
                htf_id="",
                reset_this_bar=src in reset_idx,
                class_tag=tag,
            )
        )

    md, payload = build_report(
        diags, eng_meta, res_meta, ohlcv=str(ohlcv_path), events=str(events_path)
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    jout = Path(args.json_out)
    jout.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Report: {out}")
    print(f"JSON:   {jout}")
    print(f"agreement={payload['agreement']}/{payload['total']} ({100*payload['agreement_rate']:.2f}%)")
    print("top classes:")
    for k, v in Counter(payload["class_counts"]).most_common(12):
        print(f"  {v:6d}  {k}")
    print(
        f"SWEEP residual: eng→res RANGE={payload['e_sweep_r_range']}  "
        f"eng RANGE→res SWEEP={payload['e_range_r_sweep']}"
    )
    if payload.get("ref_stats"):
        rs = payload["ref_stats"]
        print(
            f"range match frac={rs.get('frac_exact_match', 0):.4f}  "
            f"mean|dh|={rs.get('mean_abs_dh', 0):.6g}  mean|dl|={rs.get('mean_abs_dl', 0):.6g}"
        )


if __name__ == "__main__":
    main()
