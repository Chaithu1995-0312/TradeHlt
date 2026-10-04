"""build_bar_matrix.py — Stage 0 of the profitable-entry oracle program (SEM-018).

Emits ONE ROW PER BAR carrying every feature and state the repository declares, so the
outcome-first labeler has a single aligned surface to join against. No such artifact
exists today: every consumer recomputes the pipeline, and the per-bar CRT state, the
semantic state families, the parent/HTF dimension and the regime label each live in a
different script at a different cadence and a different schema version.

Scope is the inventory in `docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx`:
48 decision-vector slots, the 19 ontology feature-state families, the CRT resolver
states, and the parent/HTF machine states. Nothing outside it, nothing inside it skipped.

FAIL CLOSED, DO NOT WARN
------------------------
Every canonical key is asserted present on every row, and the run RAISES on a miss.
`FeaturePipeline.finalize()`'s own survivorship check logs an ERROR and continues; that
is the F-085 failure mode (a reduced dict flowing silently because the guard was
unreachable) and this program does not inherit it.

POINT-IN-TIME
-------------
Two places where a careless join would leak the future, both handled:

  * `_pos` is attached BEFORE the pipeline runs. `finalize()` drops the warmup head and
    resets the index, so positional alignment afterwards is meaningless. Every downstream
    series is aligned by `_pos`, never by row order.
  * `MagnitudeStateEncoder` ranks a value against whatever series it is handed and has no
    notion of time. Handing it the full corpus would rank every bar against its own
    future. It gets a bounded TRAILING window instead, sized by
    `feature_pipeline.volatility_percentile_window` so the basis matches FM-050.

Research-only. Reads the active production config; writes nothing but its own artifact.

Usage:
    python scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15 \
        --lt-id lt_20260922_044800_XAUUSD

IDENTITY JOIN (CH-oracle-join-spine)
-------------------------------------
`--lt-id` is REQUIRED (never auto-picks "the latest" run) unless `--no-trace-join` is
passed. Stamps `lt_id` / `trace_id` / `bar_open_ts` / `engine_state_after` onto every row,
inherited from the shared layer trace's L3 rows for that ONE run — never minted. Every
miss case is a declared status or a refusal, never a silent skip: an absent `lt_id`
refuses and lists the ids present; a matrix bar with no L3 row refuses unless
`--allow-unjoined-bars`; an L3 bar with no matrix row refuses unless
`--allow-trace-only-bars`. `crt_state_resolved` is renamed `ontology_state`;
`engine_state_after` (the CRT engine's own state) is new — the two are DIFFERENT
quantities (F-069) and must never be read as one field.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle, ExecutionEngine  # noqa: E402
from config_layer.production_config import get_prod_section  # noqa: E402
from data_ingestion.corpus_gate import admit_corpus  # noqa: E402
from features.crt_state_resolver import build_htf_id_timeline, create_resolver  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import (  # noqa: E402
    CANONICAL_FEATURES,
    FEATURE_ORDER_HASH,
    SCHEMA_HASH,
    SCHEMA_VERSION,
)
from features.feature_states import FeatureStateEncoder  # noqa: E402
from features.magnitude_states import MagnitudeStateEncoder  # noqa: E402
from features.market_context import MarketContextBuilder  # noqa: E402
from governance.identity_spine import normalize_bar_ts, resolve_bar  # noqa: E402
from interpreters.regime_observer import RegimeLabeler  # noqa: E402
from research.candle_state.encoder import CandleStateEncoder  # noqa: E402
from research.provenance import sha256_file as _sha256  # noqa: E402 — research-framework Phase 4 dedup
from runtime.layer_trace import LayerTraceConfig  # noqa: E402
from runtime.parent_crt_feed import ParentCRTFeed  # noqa: E402

DEFAULT_LAYER_TRACE_PATH = _ROOT / "results" / "layer_trace" / "XAUUSD_layer_trace.jsonl"


# --------------------------------------------------------------------------- #
# CH-oracle-join-spine: fail-closed identity join against the shared layer trace.
# Every miss case below is a declared status or a refusal, never a silent skip —
# the repo's own recurring failure class (F-056/F-079/F-083/F-085): a validation
# never run must never look identical to one that passed.
# --------------------------------------------------------------------------- #
class LtIdNotFound(RuntimeError):
    """--lt-id not present in the shared layer-trace file."""


class FrozenPkMismatch(RuntimeError):
    """A trace row's (instrument, timeframe, corpus_sha256) disagrees with the matrix's."""


class DuplicateTraceBar(RuntimeError):
    """Two L3 rows under the same lt_id resolve to the same bar_open_ts.

    mint_run_id has 1-second resolution (layer_trace.py) — two runs of the same
    instrument starting in the same UTC second mint the SAME lt_id into the SAME
    shared append-only file. Never first-wins/last-wins; this is a real collision.
    """


class UnjoinedMatrixBars(RuntimeError):
    """A matrix bar has no L3 row under the requested lt_id (a partial walk)."""


class TraceMatrixCoverageMismatch(RuntimeError):
    """An L3 bar under the requested lt_id has no corresponding matrix row."""


def _stream_jsonl(path: Path):
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _engine_state_name(output_hash) -> Optional[str]:
    """L3's `output_hash` on a CRT row is `str(CRTState.<NAME>)` == "CRTState.<NAME>"
    (`runtime.layer_trace.LayerTraceEmitter.emit(..., output_hash=curr_state)`, serialized
    via `json.dumps(..., default=str)` over a plain `Enum` — measured, not assumed). Strip
    the class-name prefix so `engine_state_after` sits in the SAME bare-name format as
    `ontology_state`, never a mismatched pair that reads as a formatting bug forever.
    """
    if output_hash is None:
        return None
    s = str(output_hash)
    return s.split(".", 1)[1] if s.startswith("CRTState.") else s


def _load_l3_map(
    trace_path: Path,
    lt_id: str,
    *,
    instrument: str,
    timeframe: str,
    corpus_sha256: str,
) -> tuple[dict[str, tuple[str, Optional[str]]], dict]:
    """One streaming pass over the SHARED layer-trace file, filtered to `lt_id`'s L3 rows.

    L3 is authoritative for this join (module docstring: emitted exactly once per bar,
    the only layer carrying the engine's own state; L4 is config-conditional NOT_REACHED,
    L5/L6/L8 are sparse by design, L0/L1/L7 are run-scoped with bar_ts=None).

    Returns ``({bar_open_ts: (trace_id, engine_state_after)}, stats)``. Never loads the
    file into memory — streamed line by line. Raises rather than silently accepting a
    row whose declared frozen PK disagrees with the matrix being built.
    """
    if not trace_path.exists():
        raise RuntimeError(f"build_bar_matrix: layer-trace file not found: {trace_path}")
    seen_run_ids: set[str] = set()
    m: dict[str, tuple[str, Optional[str]]] = {}
    l3_rows_this_lt = 0
    run_scoped_rows_ignored = 0
    for rec in _stream_jsonl(trace_path):
        rid = str(rec.get("run_id") or "")
        seen_run_ids.add(rid)
        if rid != lt_id or rec.get("layer") != "L3":
            continue
        pk = resolve_bar(rec)
        if pk is None:          # run-scoped row (bar_ts=None) — not a bar, never joins on one
            run_scoped_rows_ignored += 1
            continue
        rec_inst, rec_tf, bar_open_ts, rec_corpus = pk
        if (rec_inst, rec_tf, rec_corpus) != (instrument, timeframe, corpus_sha256):
            raise FrozenPkMismatch(
                f"build_bar_matrix: trace row frozen PK ({rec_inst!r}, {rec_tf!r}, "
                f"{rec_corpus!r}) != matrix's ({instrument!r}, {timeframe!r}, "
                f"{corpus_sha256!r}) for lt_id={lt_id}"
            )
        l3_rows_this_lt += 1
        if bar_open_ts in m:
            raise DuplicateTraceBar(
                f"build_bar_matrix: duplicate bar_open_ts {bar_open_ts!r} for lt_id={lt_id}"
            )
        m[bar_open_ts] = (str(rec.get("trace_id") or ""), _engine_state_name(rec.get("output_hash")))
    if lt_id not in seen_run_ids:
        raise LtIdNotFound(
            f"build_bar_matrix: lt_id {lt_id!r} not found in {trace_path}. "
            f"Available run_ids: {sorted(seen_run_ids)}"
        )
    return m, {
        "l3_rows_this_lt": l3_rows_this_lt,
        "unique_bar_open_ts": len(m),
        "run_scoped_rows_ignored": run_scoped_rows_ignored,
    }


def _join_trace_identity(
    enriched: pd.DataFrame,
    *,
    lt_id: Optional[str],
    layer_trace_path: Path,
    instrument: str,
    timeframe: str,
    corpus_sha256: str,
    no_trace_join: bool,
    allow_unjoined_bars: bool,
    allow_trace_only_bars: bool,
) -> dict:
    """Stamp lt_id / trace_id / bar_open_ts / engine_state_after / trace_join_status /
    instrument / timeframe / corpus_sha256 onto `enriched` IN PLACE (inherited from L3,
    never minted). Returns the manifest fragment.

    A value is NEVER blank; it is `JOINED` or a named non-value (`NOT_JOINED` /
    `DECLINED`) — mirrors `layer_trace.py`'s own `NOT_REACHED` discipline.
    """
    n = len(enriched)
    bar_open_ts_col = [normalize_bar_ts(ts) for ts in enriched["timestamp"]]
    enriched["bar_open_ts"] = bar_open_ts_col
    enriched["instrument"] = instrument
    enriched["timeframe"] = timeframe
    enriched["corpus_sha256"] = corpus_sha256

    if no_trace_join:
        enriched["lt_id"] = lt_id or "NOT_JOINED"
        enriched["trace_id"] = "NOT_JOINED"
        enriched["engine_state_after"] = "NOT_JOINED"
        enriched["trace_join_status"] = "DECLINED"
        return {
            "lt_id": lt_id, "trace_source_path": None, "trace_join_status": "DECLINED",
            "l3_rows_this_lt": 0, "unique_bar_open_ts": 0,
            "rows_with_trace_id": 0, "rows_without_trace_id": n,
            "trace_bar_ts_absent_from_matrix": 0, "run_scoped_rows_ignored": 0,
            "trace_id_copied_from": "L3.trace_id", "engine_state_after_copied_from": "L3.output_hash",
        }

    m, stats = _load_l3_map(
        layer_trace_path, lt_id,
        instrument=instrument, timeframe=timeframe, corpus_sha256=corpus_sha256,
    )
    trace_ids, engine_states, statuses = [], [], []
    unjoined_ts = []
    for ts in bar_open_ts_col:
        hit = m.get(ts)
        if hit is None:
            unjoined_ts.append(ts)
            trace_ids.append("NOT_JOINED")
            engine_states.append("NOT_JOINED")
            statuses.append("NO_L3_ROW")
        else:
            trace_ids.append(hit[0])
            engine_states.append(hit[1] if hit[1] is not None else "NOT_JOINED")
            statuses.append("JOINED")
    if unjoined_ts and not allow_unjoined_bars:
        raise UnjoinedMatrixBars(
            f"build_bar_matrix: {len(unjoined_ts)} of {n} matrix bars have no L3 row for "
            f"lt_id={lt_id} (first 5 bar_open_ts: {unjoined_ts[:5]}). Pass "
            "--allow-unjoined-bars to accept a partial walk, or check the lt_id."
        )
    matrix_ts_set = set(bar_open_ts_col)
    trace_only_ts = sorted(ts for ts in m if ts not in matrix_ts_set)
    if trace_only_ts and not allow_trace_only_bars:
        raise TraceMatrixCoverageMismatch(
            f"build_bar_matrix: {len(trace_only_ts)} L3 bars for lt_id={lt_id} have no "
            f"matrix row (first 5: {trace_only_ts[:5]}). Pass --allow-trace-only-bars "
            "to accept it."
        )
    enriched["lt_id"] = lt_id
    enriched["trace_id"] = trace_ids
    enriched["engine_state_after"] = engine_states
    enriched["trace_join_status"] = statuses
    return {
        "lt_id": lt_id,
        "trace_source_path": str(layer_trace_path).replace("\\", "/"),
        "trace_join_status": "PARTIAL" if unjoined_ts else "COMPLETE",
        "l3_rows_this_lt": stats["l3_rows_this_lt"],
        "unique_bar_open_ts": stats["unique_bar_open_ts"],
        "rows_with_trace_id": n - len(unjoined_ts),
        "rows_without_trace_id": len(unjoined_ts),
        "trace_bar_ts_absent_from_matrix": len(trace_only_ts),
        "run_scoped_rows_ignored": stats["run_scoped_rows_ignored"],
        "trace_id_copied_from": "L3.trace_id",
        "engine_state_after_copied_from": "L3.output_hash",
    }

# Non-vector-bound state sources (FM-061 / FM-068 / FM-069). The pipeline emits them as
# intermediates; the CRT resolver's supply contract raises if they are absent, so they are
# carried explicitly rather than left to chance.
_NON_VECTOR_STATE_INPUTS = ("retest_flag", "displacement_flag", "rsi_state")


def _code_identity() -> dict:
    """HEAD sha + whether tracked files differ from it. `None` = git unavailable, not clean."""
    def _run(*args: str):
        try:
            out = subprocess.run(
                ["git", *args], cwd=_ROOT, capture_output=True, text=True, timeout=60
            )
        except Exception:  # noqa: BLE001 — provenance is best-effort, never blocks a build
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    sha = _run("rev-parse", "HEAD")
    status = _run("status", "--porcelain", "--untracked-files=no")
    return {"git_sha": sha, "tree_dirty": None if status is None else bool(status)}


def _load_candles(df: pd.DataFrame) -> list:
    """Raw candle series, indexed by ORIGINAL row position.

    Producers with internal clocks (the parent feed, the regime labeller, the HTF id
    timeline) must see every bar including warmup, or their phase drifts against the
    engine. They are aligned back onto the surviving rows by `_pos` afterwards.
    """
    # Column zip, not itertuples: itertuples renames any leading-underscore column
    # (`_pos` becomes a positional alias), which would silently break the join key.
    return [
        Candle(
            timestamp=ts,
            open=float(o),
            high=float(h),
            low=float(lo),
            close=float(c),
            volume=float(v),
            index=int(p),
        )
        for ts, o, h, lo, c, v, p in zip(
            df["timestamp"], df["open"], df["high"], df["low"],
            df["close"], df["volume"], df["_pos"],
        )
    ]


def _default_layer_trace_path(instrument: str) -> Path:
    """Resolved from the active production config, never hardcoded (`LayerTraceConfig`
    already owns `output_dir`/`filename_suffix` — reuse it rather than a second literal)."""
    cfg = LayerTraceConfig.from_prod_config()
    if cfg is None:
        raise RuntimeError(
            "build_bar_matrix: layer_trace is disabled in the active production config "
            "(layer_trace.enabled=false) -- no shared trace file to join against. Pass "
            "--no-trace-join to build without an identity join."
        )
    return _ROOT / cfg.output_dir / f"{instrument}{cfg.filename_suffix}"


def build_bar_matrix(
    csv_path: Path,
    *,
    instrument: str,
    timeframe: str,
    limit: int | None = None,
    lt_id: str | None = None,
    layer_trace_path: Path | None = None,
    no_trace_join: bool = False,
    allow_unjoined_bars: bool = False,
    allow_trace_only_bars: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Build the per-bar feature+state matrix. Returns (frame, manifest)."""
    t_start = time.time()
    fp_cfg = get_prod_section("feature_pipeline")
    crt_cfg = get_prod_section("crt_engine")
    bt_cfg = get_prod_section("backtest")

    magnitude_window = int(fp_cfg["volatility_percentile_window"])
    htf_candles = int(bt_cfg["htf_candles_per_range"])
    # EPIC-84 O1: the same per-symbol resolution the CRT engine and planner use
    from config_layer.production_config import resolve_breakout_disp_threshold
    breakout_thr = resolve_breakout_disp_threshold(crt_cfg, instrument, get_prod_section("params"))

    # Admission BEFORE any content is read: identity (dataset_id + hash) -> sequence
    # (L3 validate_dataset) -> D-1..D-4 plausibility. Previously a bare `pd.read_csv`,
    # which made this matrix's provenance coincidental rather than declared (F-039: the
    # L3 gate is NOT universal, and a permissive stream is the sole net removed).
    # `write_report=False` is mandatory -- the fingerprint slot is {symbol}_{tf}.json, so
    # data/mt5/XAUUSD_M15.csv and the forensic data/XAUUSD_M15.csv COLLIDE on one report
    # (corpus_gate.py docstring); the admission is carried in this run's manifest instead.
    adm = admit_corpus(csv_path, instrument, write_report=False)
    csv_path = Path(adm.filepath)

    # Declared-vs-recomputed, the dataset_registry.py:139 pattern. The gate's hash and this
    # manifest's hash must describe the same bytes, or the artifact is unattributable.
    corpus_sha256 = _sha256(csv_path)
    # The gate reports `sha256:<hex>`; this manifest has always stored bare hex. Compare
    # the digests, not the labels -- and keep the bare form so the field stays joinable to
    # the trace streams' own `corpus_sha256`.
    declared = (adm.file_hash or "").split(":")[-1]
    if declared and declared != corpus_sha256:
        raise RuntimeError(
            f"build_bar_matrix: admission file_hash {adm.file_hash} != recomputed "
            f"{corpus_sha256} for {csv_path}"
        )

    raw = pd.read_csv(csv_path, parse_dates=["timestamp"])
    if limit:
        raw = raw.head(limit)
    raw = raw.reset_index(drop=True)
    raw["_pos"] = range(len(raw))
    n_raw = len(raw)

    # ── A. canonical 48-dim vector ───────────────────────────────────────────────
    enriched, vectors = FeaturePipeline(raw.copy()).run()
    if "_pos" not in enriched.columns:
        raise RuntimeError("build_bar_matrix: `_pos` did not survive the pipeline")
    missing = [c for c in CANONICAL_FEATURES if c not in enriched.columns]
    if missing:
        raise RuntimeError(f"build_bar_matrix: canonical columns absent: {missing}")
    if enriched[list(CANONICAL_FEATURES)].isna().any().any():
        raise RuntimeError("build_bar_matrix: NaN present in a canonical column")
    for col in _NON_VECTOR_STATE_INPUTS:
        if col not in enriched.columns:
            raise RuntimeError(
                f"build_bar_matrix: pipeline did not emit `{col}`; the CRT resolver's "
                "supply contract cannot be satisfied and states would silently never fire"
            )
    if vectors.shape[1] != len(CANONICAL_FEATURES):
        raise RuntimeError(f"build_bar_matrix: vector width {vectors.shape[1]}")

    n_rows = len(enriched)
    pos = enriched["_pos"].astype(int).tolist()
    if pos != sorted(pos) or len(set(pos)) != len(pos):
        raise RuntimeError("build_bar_matrix: `_pos` is not strictly increasing and unique")

    rows = enriched.to_dict("records")
    # The pipeline block (every FeaturePipeline column + `_pos`), before any state/CRT column is
    # appended below. Written on its own as `features.parquet` / `features.xlsx`.
    feature_cols = list(enriched.columns)

    # ── B. absolute ATR (FM-074). Canonical `atr` is close-relative (FM-041). ─────
    enriched["atr_abs"] = enriched["atr"] * enriched["close"]

    # ── C. declared discrete state families ──────────────────────────────────────
    fse = FeatureStateEncoder()
    mse = MagnitudeStateEncoder(state_encoder=fse)
    mcb = MarketContextBuilder(encoder=fse)

    vector_states = [fse.classify(r) for r in rows]

    # TRAILING window only — see the module docstring. Ranking against the whole corpus
    # would make every magnitude state a function of its own future.
    atr_series = enriched["atr"].tolist()
    mom_series = enriched["momentum_score"].tolist()
    magnitude_states = []
    for i, r in enumerate(rows):
        lo = max(0, i - magnitude_window + 1)
        magnitude_states.append(
            mse.classify_features(
                r,
                series_context={
                    "atr": atr_series[lo : i + 1],
                    "momentum_score": mom_series[lo : i + 1],
                },
            )
        )

    for fam in sorted(fse.stateful_features):
        enriched[f"state__{fam}"] = [vs.get(fam) for vs in vector_states]
    for fam in sorted(mse.magnitude_features):
        enriched[f"state__{fam}"] = [ms.get(fam) for ms in magnitude_states]

    enriched["context_hash"] = [
        mcb.build_with_magnitude(vector_states[i], magnitude_states[i]).context_hash
        for i in range(n_rows)
    ]

    # ── D. per-bar CRT state (declarative resolver, NOT the engine) ──────────────
    # F-069 measured ~88% agreement with the engine and only ~11% EXPANSION recall, on a
    # workflow this program treats as unverified. Stage 0.5 re-measures rather than
    # importing that number. A pattern keyed on a resolved state is a statement about the
    # resolver until that re-measurement says otherwise.
    htf_timeline = build_htf_id_timeline(
        n_raw, candles_per_htf=htf_candles, instrument=instrument
    )
    htf_aligned = [htf_timeline[p] for p in pos]
    resolver = create_resolver(instrument=instrument)
    # C2 (CH-oracle-join-spine): `ontology_state` (this column) and `engine_state_after`
    # (stamped below by the trace join) are DIFFERENT quantities that must never share a
    # column name again (F-069: divergent construction, not a lag). Both names are reused
    # verbatim from `runtime/crt_construction_trace.py`, which already emits exactly these
    # two producer-qualified fields for these two producers — never invent a third pair.
    enriched["ontology_state"] = resolver.resolve_batch(
        rows, enriched["timestamp"].tolist(), htf_ids=htf_aligned
    )
    enriched["htf_window_id"] = htf_aligned

    # ── E. parent / HTF dimension (F-075 / F-078) ───────────────────────────────
    # Advances only on a parent close, so it is forward-filled between closes: the bias a
    # bar trades under is the one established by the last COMPLETED parent.
    candles = _load_candles(raw)
    parent_feed = ParentCRTFeed.from_prod_config()
    p_state, p_bias, p_htf, p_obj = [], [], [], []
    if parent_feed is None:
        p_state = p_bias = p_htf = p_obj = [None] * n_raw
    else:
        for c in candles:
            parent_feed.push(c)
            p_state.append(parent_feed.state.value if parent_feed.state else None)
            p_bias.append(parent_feed.bias.value if parent_feed.bias else None)
            p_htf.append(parent_feed.htf_state.value if parent_feed.htf_state else None)
            obj = parent_feed.objective
            p_obj.append(obj.status.value if obj and obj.status else None)
    enriched["parent_track_state"] = [p_state[p] for p in pos]
    enriched["parent_bias"] = [p_bias[p] for p in pos]
    enriched["htf_state"] = [p_htf[p] for p in pos]
    enriched["objective_status"] = [p_obj[p] for p in pos]

    # ── F. candle state (4 orthogonal axes) + volatility regime ─────────────────
    cse = CandleStateEncoder()
    window = 60  # covers the encoder's longest lookback (volume_window=50)
    cs_dir, cs_vol, cs_str, cs_trend = [], [], [], []
    for p in pos:
        st = cse.encode(candles[max(0, p - window + 1) : p + 1])
        cs_dir.append(st.direction)
        cs_vol.append(st.vol)
        cs_str.append(st.structure)
        cs_trend.append(st.trend)
    enriched["candle_direction"] = cs_dir
    enriched["candle_vol"] = cs_vol
    enriched["candle_structure"] = cs_str
    enriched["candle_trend"] = cs_trend

    regime = RegimeLabeler().label_series(candles)
    enriched["regime_label"] = [regime[p] for p in pos]

    # ── G. trade intent — selects tp1_atr_multiplier_<intent> downstream ────────
    # EPIC-84 A3b: one intent PER SIDE (pullback is direction-aware). The engine's strict
    # intent contract is fed EXPLICITLY here: an every-bar matrix has no engine RETEST cache,
    # so FM-027/FM-028 are proxied by the pipeline's FM-021 retest_depth / FM-020
    # disp_strength -- the same quantities the removed engine-side aliases used to supply.
    from config_layer.crt_engine_v2 import Direction as _Dir

    def _intent_inputs(r):
        return {
            "displacement_retrace": r["retest_depth"],      # proxy (FM-021 for FM-027)
            "displacement_atr_ratio": r["disp_strength"],   # proxy (FM-020 for FM-028)
            "body_ratio": r["body_ratio"],
            "double_sweep": r["double_sweep"],
            "sweep_detected": r["sweep_detected"],
            "candles_since_sweep": r["candles_since_sweep"],
            "momentum_score": r["momentum_score"],
        }

    _inputs = [_intent_inputs(r) for r in rows]
    enriched["trade_intent_long"] = [
        ExecutionEngine._derive_trade_intent(x, breakout_thr, _Dir.LONG) for x in _inputs
    ]
    enriched["trade_intent_short"] = [
        ExecutionEngine._derive_trade_intent(x, breakout_thr, _Dir.SHORT) for x in _inputs
    ]

    # ── H. join spine (CH-oracle-join-spine): lt_id/trace_id/bar_open_ts/
    # engine_state_after inherited from L3 — never minted. `bar_idx` is deliberately NOT
    # written: `l3.bar_idx == matrix._pos` is asserted only internally by the join (both
    # equal 78 today, the measured warmup), never promoted to a column — writing it would
    # invite the DENY_RAW_INDEX join (`identity_spine.JOIN_TABLE`).
    resolved_lt_id = lt_id
    if not no_trace_join and resolved_lt_id is None:
        raise RuntimeError(
            "build_bar_matrix: --lt-id is required unless --no-trace-join is passed "
            "(never auto-picks 'the latest' run)"
        )
    resolved_trace_path = layer_trace_path or (
        _default_layer_trace_path(instrument) if not no_trace_join else None
    )
    join_manifest = _join_trace_identity(
        enriched,
        lt_id=resolved_lt_id,
        layer_trace_path=resolved_trace_path,
        instrument=instrument,
        timeframe=timeframe,
        corpus_sha256=corpus_sha256,
        no_trace_join=no_trace_join,
        allow_unjoined_bars=allow_unjoined_bars,
        allow_trace_only_bars=allow_trace_only_bars,
    )

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument,
        "timeframe": timeframe,
        "corpus_path": str(csv_path).replace("\\", "/"),
        "corpus_sha256": corpus_sha256,
        # Admission provenance (corpus_gate). `bound=False` means path passthrough: no
        # dataset_id, no hash verification -- the run is unattributable and must be
        # reported as such rather than silently trusted.
        "admission": {
            "dataset_id": adm.dataset_id,
            "bound": adm.bound,
            "rewritten": adm.rewritten,
            "decision": adm.decision,
            "plausibility": adm.plausibility,
        },
        "rows_raw": n_raw,
        "rows_emitted": n_rows,
        "warmup_dropped": n_raw - n_rows,
        "schema_version": SCHEMA_VERSION,
        "schema_hash": SCHEMA_HASH,
        "feature_order_hash": FEATURE_ORDER_HASH,
        "canonical_dim": len(CANONICAL_FEATURES),
        "feature_column_count": len(feature_cols),
        "feature_columns": feature_cols,
        **_code_identity(),
        "magnitude_window": magnitude_window,
        "htf_candles_per_range": htf_candles,
        "breakout_disp_threshold": breakout_thr,
        "normalization_basis": fp_cfg["normalization_basis"],
        "session_timestamp_basis": fp_cfg["session_timestamp_basis"],
        "parent_crt_enabled": parent_feed is not None,
        "state_families": sorted(fse.stateful_features) + sorted(mse.magnitude_features),
        "ontology_state_distribution": dict(Counter(enriched["ontology_state"])),
        "trade_intent_distribution": {
            "long": dict(Counter(enriched["trade_intent_long"])),
            "short": dict(Counter(enriched["trade_intent_short"])),
        },
        "regime_distribution": dict(Counter(enriched["regime_label"])),
        "parent_bias_distribution": dict(Counter(enriched["parent_bias"])),
        "build_seconds": round(time.time() - t_start, 1),
        "authority": "research_diagnostic_only",
        "declares": ["SEM-018 population surface"],
        # C2 (CH-oracle-join-spine): the two columns are DIFFERENT quantities that must
        # never be read as one field again (F-069). Self-describing on the artifact, not
        # only in a doc — a reader of just this JSON still gets the distinction.
        "state_column_semantics": {
            "ontology_state": {
                "producer_module": "features.crt_state_resolver.CRTStateResolver",
                "producer_callable": "resolve_batch",
                "construction": "declarative predicate + sticky dwell over the ontology",
                "finding_ref": "F-069",
                "forbidden_claim": "CC-L3-FORBIDDEN-JOIN",
            },
            "engine_state_after": {
                "producer_module": "config_layer.crt_engine_v2",
                "producer_callable": "process_candle (curr_state)",
                "construction": "the CRT state machine's own transition, read from the "
                                 "L3 layer-trace row's output_hash",
                "finding_ref": "F-069",
                "forbidden_claim": "CC-L3-FORBIDDEN-JOIN",
            },
        },
        **join_manifest,
        "known_contaminated_inputs": {
            "session": (
                "feature_pipeline.session_timestamp_basis is "
                f"{fp_cfg['session_timestamp_basis']}; on MT5 corpora the raw timestamp is "
                "broker-server time, so session/hour_of_day may be mislabelled. Any "
                "session-keyed result must be reported under both bases."
            ),
            "ema_spread_momentum_score": (
                "feature_pipeline.normalization_basis is "
                f"{fp_cfg['normalization_basis']}; FM-022/FM-023 emit a price-scaled "
                "quantity, so these two slots saturate and will look uninformative for a "
                "mechanical reason rather than a market one."
            ),
        },
    }
    return enriched, manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--csv", default=None, help="defaults to data/mt5/<INST>_<TF>.csv")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--limit", type=int, default=None, help="first N raw bars (smoke runs)")
    ap.add_argument(
        "--xlsx", action="store_true",
        help="also write features.xlsx (pipeline block only; needs openpyxl, takes minutes)",
    )
    ap.add_argument(
        "--lt-id", default=None,
        help="REQUIRED unless --no-trace-join: the layer-trace run_id to join against "
             "(CH-oracle-join-spine). Never auto-picks 'the latest' -- omitting it refuses.",
    )
    ap.add_argument(
        "--layer-trace-path", default=None,
        help="override the shared layer-trace file (defaults to the active config's "
             "layer_trace.output_dir / {instrument}{filename_suffix})",
    )
    ap.add_argument(
        "--no-trace-join", action="store_true",
        help="declared escape hatch: skip the identity join entirely. Every row gets "
             "trace_join_status=DECLINED and NOT_JOINED identity columns. --lt-id is not "
             "required with this flag.",
    )
    ap.add_argument(
        "--allow-unjoined-bars", action="store_true",
        help="accept a partial walk: matrix bars with no L3 row under --lt-id get "
             "trace_join_status=NO_L3_ROW instead of refusing the whole build.",
    )
    ap.add_argument(
        "--allow-trace-only-bars", action="store_true",
        help="accept L3 bars under --lt-id that have no corresponding matrix row.",
    )
    args = ap.parse_args(argv)

    if not args.no_trace_join and not args.lt_id:
        print("[FATAL] --lt-id is required unless --no-trace-join is passed "
              "(never auto-picks 'the latest' run).")
        try:
            _, stats = _load_l3_map(
                _default_layer_trace_path(args.instrument), "__probe_unused__",
                instrument=args.instrument, timeframe=args.timeframe, corpus_sha256="",
            )
        except LtIdNotFound as exc:
            print(f"        {exc}")
        except Exception:  # noqa: BLE001 — this is a best-effort hint, not the real error
            pass
        return 2

    csv_path = Path(args.csv) if args.csv else (
        _ROOT / "data" / "mt5" / f"{args.instrument}_{args.timeframe}.csv"
    )
    if not csv_path.exists():
        print(f"[FATAL] corpus not found: {csv_path}")
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT / "results" / "research" / "bar_matrix" / f"{args.instrument}_{args.timeframe}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        frame, manifest = build_bar_matrix(
            csv_path, instrument=args.instrument, timeframe=args.timeframe, limit=args.limit,
            lt_id=args.lt_id,
            layer_trace_path=Path(args.layer_trace_path) if args.layer_trace_path else None,
            no_trace_join=args.no_trace_join,
            allow_unjoined_bars=args.allow_unjoined_bars,
            allow_trace_only_bars=args.allow_trace_only_bars,
        )
    except (LtIdNotFound, FrozenPkMismatch, DuplicateTraceBar,
            UnjoinedMatrixBars, TraceMatrixCoverageMismatch) as exc:
        print(f"[FATAL] {exc}")
        return 2
    # CSV is canonical: parquet is an OPTIONAL convenience here, not a dependency
    # (`build_trace_corpus.py` established that). pyarrow ships only in the `[parquet]`
    # extra, so the engine may legitimately be absent -- a missing optional writer must not
    # lose the artifact, and `parquet_written` records which way it went so a skipped write
    # is never mistaken for a completed one.
    csv_out = out_dir / "bar_matrix.csv"
    frame.to_csv(csv_out, index=False)
    manifest["artifact_path"] = str(csv_out).replace("\\", "/")
    try:
        frame.to_parquet(out_dir / "bar_matrix.parquet", index=False)
        manifest["parquet_written"] = True
    except Exception as exc:  # noqa: BLE001 — CSV is canonical
        manifest["parquet_written"] = False
        manifest["parquet_skipped_reason"] = str(exc).splitlines()[0]
    features = frame[manifest["feature_columns"]]
    try:
        features.to_parquet(out_dir / "features.parquet", index=False)
        manifest["features_parquet_written"] = True
    except Exception as exc:  # noqa: BLE001 — CSV is canonical
        manifest["features_parquet_written"] = False
        manifest["features_parquet_skipped_reason"] = str(exc).splitlines()[0]
    if args.xlsx:
        try:
            if len(features) > 1_048_575:  # Excel sheet limit, header row included
                raise ValueError(f"{len(features)} rows exceed the Excel sheet limit")
            features.to_excel(out_dir / "features.xlsx", index=False, sheet_name="features")
            manifest["features_xlsx_written"] = True
        except Exception as exc:  # noqa: BLE001 — optional convenience copy
            manifest["features_xlsx_written"] = False
            manifest["features_xlsx_skipped_reason"] = str(exc).splitlines()[0]
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    print(f"\n  bar_matrix -> {csv_out}")
    print(f"  rows {manifest['rows_emitted']} of {manifest['rows_raw']} raw "
          f"(warmup dropped {manifest['warmup_dropped']}) in {manifest['build_seconds']}s")
    print(f"  schema v{manifest['schema_version']} dim {manifest['canonical_dim']} "
          f"| columns {len(frame.columns)} | feature block {manifest['feature_column_count']}")
    print(f"  features.parquet written={manifest['features_parquet_written']} "
          f"| features.xlsx written={manifest.get('features_xlsx_written', 'not requested')}")
    print(f"  ontology states : {manifest['ontology_state_distribution']}")
    print(f"  trace join   : {manifest['trace_join_status']} "
          f"(lt_id={manifest['lt_id']}, joined={manifest.get('rows_with_trace_id', 0)}, "
          f"unjoined={manifest.get('rows_without_trace_id', 0)})")
    print(f"  trade intent : {manifest['trade_intent_distribution']}")
    print(f"  regime       : {manifest['regime_distribution']}")
    print(f"  parent bias  : {manifest['parent_bias_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
