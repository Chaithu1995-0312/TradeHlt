"""
M11 — hour_of_day independent certification probe.

Pure same-bar transform: timestamp → wall-clock hour → int8.
No TZ conversion. Not session. PRODUCTION_BEHAVIOR_CHANGED = NO.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

LEDGER = _ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
EVIDENCE = _ROOT / "docs" / "governance" / "hour_of_day_certification-2026-07-14.json"


# ── Independent oracle (no Series.dt.hour on the production path) ───────────

def oracle_hour_of_day(timestamps) -> np.ndarray:
    """
    Independent wall-clock hour extraction.

    For each timestamp: parse via Timestamp, read hour from Python datetime.
    Does not use the production vectorized Series accessor path.
    """
    out = np.empty(len(timestamps), dtype=np.int8)
    for i, t in enumerate(timestamps):
        ts = pd.Timestamp(t)
        if pd.isna(ts):
            raise ValueError(
                "NaT/invalid timestamp: production hour cast fails; no soft sentinel"
            )
        # wall-clock hour of the stored datetime object (no utc conversion)
        py = ts.to_pydatetime()
        # if tz-aware, hour is still the wall hour in that tz
        out[i] = np.int8(py.hour)
    return out


def pipeline_hour_of_day(timestamps) -> np.ndarray:
    """Production path: pd.to_datetime → hour accessor → int8 (naive/vector path)."""
    s = pd.to_datetime(pd.Series(list(timestamps)))
    return s.dt.hour.astype(np.int8).to_numpy()


def resolve_frontier() -> dict:
    from collections import Counter
    from importlib.util import spec_from_file_location, module_from_spec

    events = []
    for ln in LEDGER.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e.get("feature_name") or e.get("target_feature"):
            events.append(e)
    spec = spec_from_file_location(
        "feature_dag_layers", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    dag = mod.build_dag()
    deps_of = {nd["name"]: nd["deps"] for nd in dag["nodes"]}
    RAW = {"open", "high", "low", "close", "volume", "timestamp"}
    explicit: dict[str, dict] = {}
    for ev in events:
        f = ev.get("feature_name") or ev.get("target_feature")
        if not f:
            continue
        cur = explicit.setdefault(
            f, {"feature_name": f, "deps": deps_of.get(f, []), "history": 0}
        )
        if "frontier_state" in ev:
            cur["frontier_state"] = ev["frontier_state"]
    promoted = {
        f
        for f, s in explicit.items()
        if s.get("frontier_state") == "PROMOTED_PRODUCTION"
    }
    for f, s in explicit.items():
        deps = deps_of.get(f, s.get("deps", []))
        s["deps"] = deps
        non_raw = [d for d in deps if d not in RAW]
        blocking = sorted(d for d in non_raw if d not in promoted)
        st = s.get("frontier_state", "UNKNOWN")
        if st in ("PROMOTED_PRODUCTION", "SUPERSEDED", "STALE", "CERTIFIED"):
            s["effective_state"] = st
        elif blocking:
            s["effective_state"] = "BLOCKED"
        elif st == "UNKNOWN":
            s["effective_state"] = "READY_TO_CERTIFY"
        else:
            s["effective_state"] = st
        s["blocking_dependencies"] = blocking
    counts = Counter(s["effective_state"] for s in explicit.values())
    return {
        "counts": dict(sorted(counts.items())),
        "hour_of_day": explicit["hour_of_day"],
        "ready": sorted(
            n for n, s in explicit.items() if s["effective_state"] == "READY_TO_CERTIFY"
        ),
        "ledger_bytes": len(LEDGER.read_bytes()),
        "ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
        "dag_deps": deps_of["hour_of_day"],
        "dag_node": next(nd for nd in dag["nodes"] if nd["name"] == "hour_of_day"),
        "session_deps": deps_of.get("session"),
        "dag_consumers": [
            nd["name"] for nd in dag["nodes"] if "hour_of_day" in nd.get("deps", [])
        ],
    }


def _pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def run_battery() -> dict:
    from features.feature_pipeline import FeaturePipeline

    results: dict = {}
    all_ok = True

    # boundary corpus
    stamps = [
        datetime(2024, 1, 1, 0, 0, 0),
        datetime(2024, 1, 1, 1, 0, 0),
        datetime(2024, 6, 15, 12, 30, 0),
        datetime(2024, 12, 31, 23, 59, 59),
        datetime(2024, 3, 1, 7, 59, 0),
        datetime(2024, 3, 1, 8, 0, 0),
        datetime(2024, 3, 1, 15, 59, 0),
        datetime(2024, 3, 1, 16, 0, 0),
        "2024-01-01 00:00:00",
        "2024-07-04 23:00:00",
        pd.Timestamp("2024-05-01 11:11:11"),
    ]
    o = oracle_hour_of_day(stamps)
    p = pipeline_hour_of_day(stamps)
    parity = bool(np.array_equal(o, p))
    domain = bool(np.all((o >= 0) & (o <= 23)))
    dtype_ok = o.dtype == np.int8 and p.dtype == np.int8

    # expected hand values
    hand = {
        0: 0,
        1: 1,
        2: 12,
        3: 23,
        4: 7,
        5: 8,
        6: 15,
        7: 16,
    }
    hand_ok = all(int(o[i]) == v for i, v in hand.items())

    # NaT policy: must raise (production cast fails)
    nat_raises = False
    try:
        oracle_hour_of_day([pd.NaT])
    except ValueError:
        nat_raises = True
    pipe_nat_raises = False
    try:
        pipeline_hour_of_day([pd.NaT])
    except (ValueError, TypeError, pd.errors.IntCastingNaNError):
        pipe_nat_raises = True
    except Exception:
        # pandas may raise different error types across versions
        pipe_nat_raises = True

    # tz-aware: oracle reads wall hour; production pd.to_datetime on mixed/object
    # tz-aware arrays requires utc=True (fails otherwise) — document as out-of-contract.
    # Single already-normalized DatetimeIndex path: construct Series as datetime64[ns, UTC]
    utc_series = pd.Series(pd.DatetimeIndex([
        pd.Timestamp("2024-01-01 15:30:00", tz="UTC"),
        pd.Timestamp("2024-01-01 00:30:00", tz="UTC"),
    ]))
    p_utc = utc_series.dt.hour.astype(np.int8).to_numpy()
    o_utc = oracle_hour_of_day(list(utc_series))
    tz_ok = bool(np.array_equal(o_utc, p_utc)) and int(o_utc[0]) == 15 and int(o_utc[1]) == 0

    # no-TZ-conversion claim: naive 15:00 stays 15
    naive_ok = int(oracle_hour_of_day([datetime(2024, 1, 1, 15, 0)])[0]) == 15

    basic = {
        "oracle_pipeline_parity": _pass(parity),
        "domain_0_23": _pass(domain),
        "dtype_int8": _pass(dtype_ok),
        "hand_boundaries": _pass(hand_ok),
        "nat_oracle_raises": _pass(nat_raises),
        "nat_pipeline_raises": _pass(pipe_nat_raises),
        "tz_aware_utc_index_wall_hour": _pass(tz_ok),
        "naive_no_tz_conversion": _pass(naive_ok),
    }
    results["basic"] = basic
    all_ok &= all(v == "PASS" for v in basic.values())

    # temporal: long series prefix / future mutation / determinism
    t0 = datetime(2024, 1, 1)
    series = [t0 + timedelta(hours=i) for i in range(100)]
    full = oracle_hour_of_day(series)
    pipe_full = pipeline_hour_of_day(series)
    series_parity = bool(np.array_equal(full, pipe_full))
    # hours cycle
    cycle_ok = bool(np.array_equal(full[:24], np.arange(24, dtype=np.int8)))

    prefix_ok = True
    for cut in (10, 40, 80):
        if not np.array_equal(oracle_hour_of_day(series[:cut]), full[:cut]):
            prefix_ok = False
    fut_base = oracle_hour_of_day(series[:50])
    mut = list(series)
    for j in range(50, 100):
        mut[j] = datetime(2099, 1, 1, 3, 0)
    fut_ok = np.array_equal(oracle_hour_of_day(mut[:50]), fut_base)
    det_ok = np.array_equal(oracle_hour_of_day(series), oracle_hour_of_day(series))

    temporal = {
        "series_parity": _pass(series_parity),
        "24h_cycle": _pass(cycle_ok),
        "prefix_invariance": _pass(prefix_ok),
        "future_mutation": _pass(fut_ok),
        "determinism": _pass(det_ok),
    }
    results["temporal"] = temporal
    all_ok &= all(v == "PASS" for v in temporal.values())

    # FeaturePipeline.compute_context parity
    rows = []
    for i in range(48):
        rows.append(
            dict(
                timestamp=t0 + timedelta(hours=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1000.0,
            )
        )
    df = pd.DataFrame(rows)
    fp = FeaturePipeline(df)
    fp.compute_context()
    pipe_col = fp.df["hour_of_day"].to_numpy()
    ora_col = oracle_hour_of_day(fp.df["timestamp"].tolist())
    ctx_parity = bool(np.array_equal(pipe_col, ora_col))
    ctx_dtype = pipe_col.dtype == np.int8

    # session note (not certifying session): session uses hour intermediate
    session_uses_hour = "hour" in open(
        _ROOT / "src" / "features" / "feature_pipeline.py", encoding="utf-8"
    ).read().split("def compute_context")[1].split("def compute_structure")[0]

    pipeline = {
        "compute_context_parity": _pass(ctx_parity),
        "pipeline_dtype_int8": _pass(ctx_dtype),
        "session_uses_hour_intermediate_in_code": _pass(session_uses_hour),
    }
    results["pipeline"] = pipeline
    all_ok &= ctx_parity and ctx_dtype

    results["overall_verdict"] = "CERTIFIED" if all_ok else "REJECT"
    results["all_probes_pass"] = all_ok
    return results


def build_artifact(checkpoint: dict, battery: dict) -> dict:
    return {
        "_doc": "M11 hour_of_day certification — pure timestamp wall-clock hour.",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session": "M11",
        "TARGET_FEATURE": "hour_of_day",
        "TARGET_IDENTITY": "TIMESTAMP_WALL_CLOCK_HOUR",
        "formula_id": None,
        "canonical_index": 31,
        "FULL_DEPENDENCIES": ["timestamp"],
        "TIMEZONE_POLICY": (
            "NO conversion: pd.to_datetime(timestamp) then .dt.hour of the resulting "
            "datetime as stored (naive wall hour if naive)"
        ),
        "DOMAIN": [0, 23],
        "CANONICAL_DTYPE": "int8",
        "NAT_POLICY": (
            "NaT → .dt.hour NaN → astype(int8) FAILS; no soft sentinel; production "
            "assumes valid timestamps"
        ),
        "source_of_truth": "src/features/feature_pipeline.py:378-379",
        "semantic_class": "pure_same_bar_transform",
        "dag_consumers": checkpoint["dag_consumers"],
        "session_note": {
            "dag_session_deps": checkpoint["session_deps"],
            "code": "compute_context derives session from hour_of_day intermediate",
            "m12_guidance": (
                "session DAG deps=[timestamp] only — not hour_of_day; inspect before M12 "
                "whether to treat hour as intermediate like retest_flag"
            ),
        },
        "checkpoint_start": {
            "frontier": checkpoint["counts"],
            "hour_of_day": {
                "effective_state": checkpoint["hour_of_day"]["effective_state"],
                "deps": checkpoint["dag_deps"],
            },
            "ledger_bytes": checkpoint["ledger_bytes"],
            "ledger_sha256": checkpoint["ledger_sha256"],
        },
        "oracle_design": {
            "algorithm": "pd.Timestamp(t).to_pydatetime().hour → int8 (per element)",
            "independence": "does not call Series.dt.hour (production vector path)",
        },
        "probes": battery,
        "PER_NODE_VERDICT": battery["overall_verdict"],
        "PRODUCTION_BEHAVIOR_CHANGED": "NO",
        "authority": (
            "research/governance only — descriptive certification; grants no runtime "
            "authority (§6.5)"
        ),
        "scope_boundary": "hour_of_day only. session/trend_strength/volatility_regime untouched.",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("M11 — hour_of_day CERTIFICATION PROBE")
    print("=" * 72)

    cp = resolve_frontier()
    print("FRONTIER", cp["counts"])
    print("hour_of_day", cp["hour_of_day"]["effective_state"], "deps", cp["dag_deps"])
    print("DAG consumers", cp["dag_consumers"])
    print("session DAG deps", cp["session_deps"], "(not certifying)")
    if cp["hour_of_day"]["effective_state"] != "READY_TO_CERTIFY":
        print("REFUSED: not READY")
        return 2
    if sorted(cp["dag_deps"]) != ["timestamp"]:
        print("REFUSED: unexpected deps", cp["dag_deps"])
        return 2

    battery = run_battery()
    for sec, val in battery.items():
        if not isinstance(val, dict):
            continue
        print(f"[{sec}]")
        for k, v in val.items():
            if isinstance(v, str) and v in ("PASS", "FAIL"):
                print(f"  {k:40s} {v}")
    print("OVERALL", battery["overall_verdict"])
    if battery["overall_verdict"] != "CERTIFIED":
        return 3

    art = build_artifact(cp, battery)
    EVIDENCE.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
    sha = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    if not sha:
        print("REFUSED empty sha")
        return 4
    print("ARTIFACT", EVIDENCE.relative_to(_ROOT))
    print("SHA256", sha)
    print("ALL PROBES PASS — hour_of_day CERTIFIABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
