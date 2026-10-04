"""
M12B / F-054-SESSION-CERT — canonical FeaturePipeline `session` certification.

REWRITTEN 2026-07-31 (semantic layer audit, post-implementation revalidation): this probe was
last generated 2026-07-14 against the v3.0 3-value hour PARTITION ({0,1,2} = Asia/London/NY,
`0 if h<8 else 1 if h<16 else 2`). FM-052 was migrated to v4.0 on 2026-07-22
(SCHEMA-V4-VECTOR-MIGRATION) to a 5-value WINDOW model with real overlapping market sessions
(`features/session_classifier.py`) — this probe went stale against that migration and was never
updated, so `python session_certification.py` was silently REJECTing since 2026-07-22. Rewritten
here to certify the CURRENT model.

Governed identity: hour_of_day → window-model classification (ASIA/LONDON/NEWYORK/OVERLAP/CLOSED)
→ {0,1,2,3,4} int8, config-driven via `feature_pipeline.session_windows_utc` (defaults
ASIA=[0,9) LONDON=[7,16) NEWYORK=[12,21), half-open, precedence OVERLAP > NEWYORK > LONDON >
ASIA > CLOSED — see `features/session_classifier.py` module docstring for the full rationale).
DAG deps = [hour_of_day] (CORRECTED 2026-07-22, matches what the pipeline actually executes:
`compute_context` derives `session` from the `hour_of_day` COLUMN, not straight from `timestamp`
— see `market_ontology.yaml` FM-052 `depends_on` and `feature_dag_layers.py`'s `_NODES["session"]`,
both of which already agree on this). Does NOT certify SESSION_MAP / dashboard / CRT strings, but
DOES check SESSION_MAP for parity now that the v3.0 permutation debt this probe used to track is
RESOLVED (SESSION_MAP is unified with `session_classifier` as of the v4.0 migration; see the
`deferred_encoding_debts` field in `build_artifact` for the append-only record of that closure).
PRODUCTION_BEHAVIOR_CHANGED = NO (this probe certifies the ALREADY-migrated pipeline; it does not
change it).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

LEDGER = _ROOT / "docs" / "governance" / "feature_certification_ledger.jsonl"
EVIDENCE = _ROOT / "docs" / "governance" / "session_certification-2026-07-14.json"


# ── Independent oracle (explicit branches; no pipeline/SESSION_MAP) ─────────

# Hardcoded window bounds (independent of session_classifier.DEFAULT_SESSION_WINDOWS_UTC / config
# -- an oracle that imported those would not be independent). These are the production DEFAULTS;
# see the module docstring for the precedence rule this branch order encodes.
_ORACLE_ASIA = (0, 9)
_ORACLE_LONDON = (7, 16)
_ORACLE_NEWYORK = (12, 21)
# Ordinals: ASIA=0, LONDON=1, NEWYORK=2, OVERLAP=3, CLOSED=4 (SessionOrdinal, hardcoded here too).


def oracle_session_code_from_hour(hour: int) -> np.int8:
    """Explicit branch classification against the FM-052 v4.0 window model. Fails on
    out-of-domain hour. Precedence: OVERLAP (London&NY) > NEWYORK > LONDON > ASIA > CLOSED."""
    if not isinstance(hour, (int, np.integer)):
        raise TypeError(f"hour must be int, got {type(hour)}")
    h = int(hour)
    if not (0 <= h <= 23):
        raise ValueError(f"hour out of domain 0..23: {h}")
    in_asia = _ORACLE_ASIA[0] <= h < _ORACLE_ASIA[1]
    in_london = _ORACLE_LONDON[0] <= h < _ORACLE_LONDON[1]
    in_ny = _ORACLE_NEWYORK[0] <= h < _ORACLE_NEWYORK[1]
    if in_london and in_ny:
        return np.int8(3)  # OVERLAP
    if in_ny:
        return np.int8(2)  # NEWYORK
    if in_london:
        return np.int8(1)  # LONDON
    if in_asia:
        return np.int8(0)  # ASIA
    return np.int8(4)  # CLOSED


def oracle_session(timestamps) -> np.ndarray:
    """
    Independent certification oracle from raw timestamps only.

    Parse each timestamp → wall-clock hour → classify via explicit branches.
    """
    out = np.empty(len(timestamps), dtype=np.int8)
    for i, t in enumerate(timestamps):
        ts = pd.Timestamp(t)
        if pd.isna(ts):
            raise ValueError(
                "NaT/invalid timestamp: production fails at hour int8 cast; "
                "no soft invalid path for this quantity"
            )
        h = int(ts.to_pydatetime().hour)
        out[i] = oracle_session_code_from_hour(h)
    return out


def pipeline_session_from_timestamps(timestamps) -> np.ndarray:
    """Production path via FeaturePipeline.compute_context only."""
    from features.feature_pipeline import FeaturePipeline

    df = pd.DataFrame(
        {
            "timestamp": list(timestamps),
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 100.0,
        }
    )
    fp = FeaturePipeline(df)
    fp.compute_context()
    return fp.df["session"].to_numpy()


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
        "session": explicit["session"],
        "timestamp": explicit["timestamp"]["effective_state"],
        # CORRECTED 2026-07-31: session's DIRECT dependency is hour_of_day (see module docstring),
        # not timestamp -- the ordering-gate check in main() must verify the actual direct dep.
        "hour_of_day": explicit.get("hour_of_day", {}).get("effective_state", "UNKNOWN"),
        "ready": sorted(
            n for n, s in explicit.items() if s["effective_state"] == "READY_TO_CERTIFY"
        ),
        "ledger_bytes": len(LEDGER.read_bytes()),
        "ledger_sha256": hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
        "dag_deps": deps_of["session"],
    }


def _pass(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def oracle_source_hash() -> str:
    src = inspect.getsource(oracle_session) + inspect.getsource(oracle_session_code_from_hour)
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


def assert_oracle_independence() -> dict:
    """Fence: oracle source must not reference forbidden symbols."""
    src = (
        inspect.getsource(oracle_session)
        + inspect.getsource(oracle_session_code_from_hour)
    )
    # Token fence on *executable* AST-free source body: strip docstrings/comments first
    import ast

    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Expr,) ) and isinstance(getattr(node, "value", None), ast.Constant):
                pass
        # remove docstring constants from function defs
        cleaned_lines = []
        for line in src.splitlines():
            s = line.strip()
            if s.startswith('"""') or s.startswith("'''") or s.startswith("#"):
                continue
            cleaned_lines.append(line)
        body = "\n".join(cleaned_lines)
    except SyntaxError:
        body = src
    forbidden_tokens = [
        "SESSION_MAP",
        "SESSION_ORDINAL",
        "encode_session_ordinal",
        "FeaturePipeline",
        "np.where",
        '["hour_of_day"]',
        'df["session"]',
        "_derive_session",
        "session_windows",
    ]
    hits = [t for t in forbidden_tokens if t in body]
    return {"forbidden_hits": hits, "ok": len(hits) == 0}


def run_battery() -> dict:
    from features.feature_schema import SESSION_MAP

    results: dict = {}
    all_ok = True

    # ── Exhaustive 24-hour ──────────────────────────────────────────────────
    # v4.0 buckets: ASIA h0-6 (7h), LONDON h7-11 (5h), OVERLAP h12-15 (4h), NEWYORK h16-20 (5h),
    # CLOSED h21-23 (3h) -- ground-truth re-derived from features.session_classifier and
    # cross-checked against classify_session_feature(h) for h in range(24) directly.
    hours = list(range(24))
    stamps_24 = [datetime(2024, 6, 1, h, 30, 0) for h in hours]
    o24 = oracle_session(stamps_24)
    expected = np.array(
        [0] * 7 + [1] * 5 + [3] * 4 + [2] * 5 + [4] * 3, dtype=np.int8
    )
    exh = {
        "24h_exact_vector": _pass(bool(np.array_equal(o24, expected))),
        "dtype_int8": _pass(o24.dtype == np.int8),
        "domain_subset": _pass(bool(set(int(x) for x in o24).issubset({0, 1, 2, 3, 4}))),
        "all_codes_reachable": _pass(set(int(x) for x in o24) == {0, 1, 2, 3, 4}),
        "no_gap_overlap_count": _pass(
            int((o24 == 0).sum()) == 7
            and int((o24 == 1).sum()) == 5
            and int((o24 == 3).sum()) == 4
            and int((o24 == 2).sum()) == 5
            and int((o24 == 4).sum()) == 3
        ),
    }
    transitions = {
        "07": int(oracle_session_code_from_hour(7)) == 1,
        "08": int(oracle_session_code_from_hour(8)) == 1,
        "09": int(oracle_session_code_from_hour(9)) == 1,
        "15": int(oracle_session_code_from_hour(15)) == 3,
        "16": int(oracle_session_code_from_hour(16)) == 2,
        "17": int(oracle_session_code_from_hour(17)) == 2,
        "23": int(oracle_session_code_from_hour(23)) == 4,
        "00": int(oracle_session_code_from_hour(0)) == 0,
    }
    exh["transitions"] = _pass(all(transitions.values()))
    exh["transition_detail"] = {k: int(oracle_session_code_from_hour(int(k))) for k in ["7", "8", "9", "15", "16", "17", "23", "0"]}
    # fix keys - use proper
    exh["transition_detail"] = {
        "07": int(oracle_session_code_from_hour(7)),
        "08": int(oracle_session_code_from_hour(8)),
        "09": int(oracle_session_code_from_hour(9)),
        "15": int(oracle_session_code_from_hour(15)),
        "16": int(oracle_session_code_from_hour(16)),
        "17": int(oracle_session_code_from_hour(17)),
        "23": int(oracle_session_code_from_hour(23)),
        "00": int(oracle_session_code_from_hour(0)),
    }
    results["boundary"] = exh
    all_ok &= all(v == "PASS" for k, v in exh.items() if isinstance(v, str))

    # ── Timestamp forms ─────────────────────────────────────────────────────
    forms = [
        datetime(2024, 1, 1, 3, 0),
        pd.Timestamp("2024-01-01 10:00:00"),
        "2024-01-01 20:15:00",
        pd.Timestamp(datetime(2024, 1, 1, 7, 59)),
        pd.Timestamp(datetime(2024, 1, 1, 8, 0)),
    ]
    o_f = oracle_session(forms)
    p_f = pipeline_session_from_timestamps(forms)
    form_parity = bool(np.array_equal(o_f, p_f)) and o_f.dtype == np.int8 and p_f.dtype == np.int8

    nat_oracle = False
    try:
        oracle_session([pd.NaT])
    except ValueError:
        nat_oracle = True
    nat_pipe = False
    try:
        pipeline_session_from_timestamps([pd.NaT])
    except Exception:
        nat_pipe = True

    results["timestamp_forms"] = {
        "parity": _pass(form_parity),
        "nat_oracle_raises": _pass(nat_oracle),
        "nat_pipeline_raises": _pass(nat_pipe),
        "oracle_values": [int(x) for x in o_f],
        "pipeline_values": [int(x) for x in p_f],
    }
    all_ok &= form_parity and nat_oracle and nat_pipe

    # ── Timezone ────────────────────────────────────────────────────────────
    naive = datetime(2024, 1, 1, 15, 0)
    utc_ts = pd.Timestamp("2024-01-01 15:00:00", tz="UTC")
    # wall hour 15 in both → session 3 (OVERLAP: 15 is inside both LONDON [7,16) and NEWYORK [12,21))
    o_naive = int(oracle_session([naive])[0])
    o_utc = int(oracle_session([utc_ts])[0])
    # pipeline: DatetimeIndex UTC works. Inline reference re-derives the v4.0 window model
    # directly (not imported from session_classifier, to stay an independent check).
    def _v4_from_hour(h: int) -> int:
        in_a, in_l, in_n = 0 <= h < 9, 7 <= h < 16, 12 <= h < 21
        if in_l and in_n:
            return 3
        if in_n:
            return 2
        if in_l:
            return 1
        if in_a:
            return 0
        return 4

    p_utc = int(
        pd.Series(pd.DatetimeIndex([utc_ts])).dt.hour.map(_v4_from_hour)
        .astype(np.int8).iloc[0]
    )
    # production compute_context on tz-aware column may fail; test oracle wall-hour claim
    tz_results = {
        "naive_15_session3_overlap": _pass(o_naive == 3),
        "utc_aware_15_session3_overlap": _pass(o_utc == 3),
        "no_force_utc_shift_claim": _pass(o_naive == o_utc == 3),
        "observed": {
            "naive_hour_wall": 15,
            "utc_aware_hour_wall": 15,
            "session_code": o_utc,
            "policy": "NO timezone conversion; wall-clock hour of stored datetime",
        },
    }
    # offset string: if parseable as single tz
    try:
        o_off = int(oracle_session([pd.Timestamp("2024-01-01 15:00:00+00:00")])[0])
        tz_results["offset_plus0_15"] = _pass(o_off == 3)
        all_ok &= o_off == 3
    except Exception as e:
        tz_results["offset_plus0_15"] = f"FAIL:{e}"
        all_ok = False
    results["timezone"] = tz_results
    all_ok &= o_naive == 3 and o_utc == 3

    # ── Pipeline parity exhaustive + boundary ───────────────────────────────
    p24 = pipeline_session_from_timestamps(stamps_24)
    pipe_exh = bool(np.array_equal(o24, p24)) and p24.dtype == np.int8
    boundary_stamps = [
        datetime(2024, 3, 1, h, 0) for h in [7, 8, 9, 15, 16, 17, 23, 0]
    ]
    o_b = oracle_session(boundary_stamps)
    p_b = pipeline_session_from_timestamps(boundary_stamps)
    pipe_b = bool(np.array_equal(o_b, p_b))

    # representative longer series
    series = [datetime(2024, 2, 1) + timedelta(hours=i) for i in range(72)]
    o_s = oracle_session(series)
    p_s = pipeline_session_from_timestamps(series)
    pipe_s = bool(np.array_equal(o_s, p_s))

    results["pipeline_parity"] = {
        "exhaustive_24h": _pass(pipe_exh),
        "boundary_heavy": _pass(pipe_b),
        "representative_72h": _pass(pipe_s),
        "max_abs_err_72h": int(np.max(np.abs(o_s.astype(int) - p_s.astype(int)))) if len(o_s) else 0,
    }
    all_ok &= pipe_exh and pipe_b and pipe_s

    # ── PIT ─────────────────────────────────────────────────────────────────
    full = oracle_session(series)
    prefix_ok = True
    for cut in (12, 24, 48):
        if not np.array_equal(oracle_session(series[:cut]), full[:cut]):
            prefix_ok = False
    fut_base = oracle_session(series[:40])
    mut = list(series)
    for j in range(40, 72):
        mut[j] = datetime(2099, 1, 1, 3, 0)  # Asia
    fut_ok = np.array_equal(oracle_session(mut[:40]), fut_base)

    # same-bar sensitivity: change one hour across a boundary; a same-bucket second element
    # must not move (proves the classification is per-bar, not smeared across the batch).
    base_row = [datetime(2024, 5, 1, 6, 0), datetime(2024, 5, 1, 3, 0)]
    a = oracle_session(base_row)
    sens = list(base_row)
    sens[0] = datetime(2024, 5, 1, 7, 0)  # 6 ASIA → 7 LONDON (crosses the ASIA/LONDON boundary)
    b = oracle_session(sens)
    sens_ok = int(a[0]) == 0 and int(b[0]) == 1 and int(a[1]) == int(b[1]) == 0

    det_ok = np.array_equal(oracle_session(series), oracle_session(series))

    results["pit"] = {
        "prefix_invariance": _pass(prefix_ok),
        "future_mutation": _pass(fut_ok),
        "same_bar_sensitivity": _pass(sens_ok),
        "determinism": _pass(det_ok),
    }
    all_ok &= prefix_ok and fut_ok and sens_ok and det_ok

    # ── Encoding isolation / parity ─────────────────────────────────────────
    # PURPOSE CHANGED 2026-07-31: this block used to PROVE a known permutation bug
    # (SESSION_MAP["asian"]==2.0 while the pipeline emitted Asia=0 -- the M16-WU-SESSION-ENCODING
    # debt). That debt is RESOLVED as of the v4.0 migration: SESSION_MAP is now derived from the
    # single-owner session_classifier.SESSION_NAME_TO_ORDINAL (feature_schema.py:155-163), so it
    # necessarily agrees with the pipeline. The assertion direction is deliberately flipped from
    # "prove divergence" to "prove parity" -- reverting this flip would silently resurrect the old
    # (already-fixed) bug as an expected outcome.
    indep = assert_oracle_independence()
    asia_hour = 3
    canon = int(oracle_session_code_from_hour(asia_hour))
    map_asian = float(SESSION_MAP["asian"])
    isolation = {
        "oracle_source_forbidden_clean": _pass(indep["ok"]),
        "forbidden_hits": indep["forbidden_hits"],
        "asia_hour3_canonical_0": _pass(canon == 0),
        "SESSION_MAP_asian_is_0": _pass(map_asian == 0.0),
        "canonical_eq_SESSION_MAP_asian": _pass(canon == int(map_asian)),
        "parity": {
            "hour": asia_hour,
            "canonical_pipeline_code": canon,
            "SESSION_MAP_asian": map_asian,
        },
    }
    results["encoding_isolation"] = isolation
    all_ok &= indep["ok"] and canon == 0 and map_asian == 0.0 and canon == int(map_asian)

    results["overall_verdict"] = "CERTIFIED" if all_ok else "REJECT"
    results["all_probes_pass"] = all_ok
    results["oracle_source_sha256"] = oracle_source_hash()
    return results


def build_artifact(checkpoint: dict, battery: dict) -> dict:
    from features.feature_schema import CANONICAL_FEATURES

    return {
        "_doc": "M12B canonical FeaturePipeline session certification ONLY.",
        "schema_version": "2.0",  # 2.0 (2026-07-31): rewritten for FM-052 v4.0 (was 1.0, v3.0-era)
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "session_program": "M12B",
        "TARGET_FEATURE": "session",
        "checkpoint": checkpoint["counts"],
        "intended_quantity": (
            "int8 canonical FM-052 v4.0 session code: a window model over "
            "feature_pipeline.session_windows_utc (defaults ASIA=[0,9) LONDON=[7,16) "
            "NEWYORK=[12,21), half-open, precedence OVERLAP(London&NY) > NEWYORK > LONDON > "
            "ASIA > CLOSED) applied to hour_of_day, NOT the v3.0 3-value hour partition; "
            "invalid/NaT timestamps fail upstream during hour_of_day int8 cast; no "
            "session-specific fallback"
        ),
        "dependency_classification": "EXECUTABLE_REUSE_HOUR_OF_DAY_IDENTITY",
        "CURRENT_DAG_DEPS": ["hour_of_day"],
        "IMPLEMENTATION_REUSE": "hour_of_day column",
        "EXECUTABLE_DATAFLOW_DEPENDENCY": "hour_of_day column",
        "GOVERNED_SEMANTIC_ROOT": "hour_of_day (itself timestamp wall-clock hour)",
        "CERTIFICATION_AUTHORITY_DEPENDENCY": "hour_of_day (CORRECTED 2026-07-31: was 'timestamp only', "
        "which contradicted the DAG's own declared session.depends_on=[hour_of_day] -- both the "
        "ontology (FM-052) and feature_dag_layers.py already agreed on hour_of_day before this "
        "probe was rewritten to match)",
        "exact_piecewise_function": {
            "0": "0<=h<9 and not (7<=h<16 and 12<=h<21)",
            "1": "7<=h<16 and not (12<=h<21)",
            "2": "12<=h<21 and not (7<=h<16)",
            "3": "7<=h<16 and 12<=h<21",
            "4": "not (0<=h<9) and not (7<=h<16) and not (12<=h<21)",
            "labels": {"0": "ASIA", "1": "LONDON", "2": "NEWYORK", "3": "OVERLAP", "4": "CLOSED"},
        },
        "boundary_table": {
            str(h): int(oracle_session_code_from_hour(h)) for h in range(24)
        },
        "dtype": "int8",
        "domain": [0, 1, 2, 3, 4],
        "timezone_semantics": "NO timezone conversion; wall-clock hour of stored datetime",
        "invalid_timestamp_policy": (
            "NaT/invalid fails at hour extraction/int8 cast; no session soft path"
        ),
        "oracle_implementation_identity_hash": battery["oracle_source_sha256"],
        "oracle_independence_statement": (
            "oracle_session uses per-element Timestamp→pydatetime.hour and explicit "
            "if/elif branches over hardcoded window bounds only; no FeaturePipeline, np.where, "
            "SESSION_MAP, SESSION_ORDINAL, CRT/live/backtest session helpers, pipeline columns, "
            "or the live feature_pipeline.session_windows_utc config"
        ),
        "probes": battery,
        "deferred_encoding_debts": [
            "RESOLVED 2026-07-22 (v4.0 migration): SESSION_MAP london=0/newyork=1/asian=2 no "
            "longer permutes the pipeline's Asia=0/London=1/NY=2 -- SESSION_MAP is now derived "
            "from the single-owner session_classifier.SESSION_NAME_TO_ORDINAL, so it and the "
            "pipeline necessarily agree (see the encoding_isolation/parity probe above, which "
            "asserts parity rather than the old divergence).",
            "dashboard SESSION_LABELS 1.0/2.0/3.0 vs pipeline 0/1/2/3/4 -- STILL OPEN, not "
            "re-audited by this rewrite.",
            "CRT/live/backtest string or config-window session paths not certified here -- "
            "STILL OPEN; this probe certifies only the canonical FeaturePipeline column.",
        ],
        "PER_NODE_VERDICT": battery["overall_verdict"],
        "PRODUCTION_BEHAVIOR_CHANGED": "NO",
        "CANONICAL_VECTOR_DIMENSION": len(CANONICAL_FEATURES),
        "authority": (
            "research/governance only — descriptive certification; grants no runtime authority (§6.5)"
        ),
        "scope_boundary": (
            "canonical FeaturePipeline session only; trend_strength/volatility_regime untouched"
        ),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 72)
    print("M12B — session CERTIFICATION PROBE")
    print("=" * 72)

    cp = resolve_frontier()
    print("FRONTIER", cp["counts"])
    print("session", cp["session"]["effective_state"], "deps", cp["dag_deps"])
    print("hour_of_day", cp["hour_of_day"])
    # session is typically already PROMOTED_PRODUCTION (re-certified 2026-07-31 against the
    # corrected FM-052 v4.0 witness) -- this probe is idempotent re-verification, not a one-shot
    # pre-certification gate, so both READY_TO_CERTIFY and an already-settled state are accepted.
    if cp["session"]["effective_state"] not in ("READY_TO_CERTIFY", "CERTIFIED", "PROMOTED_PRODUCTION"):
        print("REFUSED: session not READY/CERTIFIED/PROMOTED", cp["session"]["effective_state"])
        return 2
    if cp["dag_deps"] != ["hour_of_day"]:
        print("REFUSED: deps", cp["dag_deps"])
        return 2
    if cp["hour_of_day"] != "PROMOTED_PRODUCTION":
        print("REFUSED: hour_of_day (session's direct dependency) not promoted")
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
    print("ALL PROBES PASS — session CERTIFIABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
