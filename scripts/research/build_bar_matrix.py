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
    python scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
from interpreters.regime_observer import RegimeLabeler  # noqa: E402
from research.candle_state.encoder import CandleStateEncoder  # noqa: E402
from runtime.parent_crt_feed import ParentCRTFeed  # noqa: E402

# Non-vector-bound state sources (FM-061 / FM-068 / FM-069). The pipeline emits them as
# intermediates; the CRT resolver's supply contract raises if they are absent, so they are
# carried explicitly rather than left to chance.
_NON_VECTOR_STATE_INPUTS = ("retest_flag", "displacement_flag", "rsi_state")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def build_bar_matrix(
    csv_path: Path,
    *,
    instrument: str,
    timeframe: str,
    limit: int | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Build the per-bar feature+state matrix. Returns (frame, manifest)."""
    t_start = time.time()
    fp_cfg = get_prod_section("feature_pipeline")
    crt_cfg = get_prod_section("crt_engine")
    bt_cfg = get_prod_section("backtest")

    magnitude_window = int(fp_cfg["volatility_percentile_window"])
    htf_candles = int(bt_cfg["htf_candles_per_range"])
    breakout_thr = float(crt_cfg["breakout_disp_threshold"])

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
    resolver = create_resolver()
    enriched["crt_state_resolved"] = resolver.resolve_batch(
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
    enriched["trade_intent"] = [
        ExecutionEngine._derive_trade_intent(r, breakout_thr) for r in rows
    ]

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
        "magnitude_window": magnitude_window,
        "htf_candles_per_range": htf_candles,
        "breakout_disp_threshold": breakout_thr,
        "normalization_basis": fp_cfg["normalization_basis"],
        "session_timestamp_basis": fp_cfg["session_timestamp_basis"],
        "parent_crt_enabled": parent_feed is not None,
        "state_families": sorted(fse.stateful_features) + sorted(mse.magnitude_features),
        "crt_state_distribution": dict(Counter(enriched["crt_state_resolved"])),
        "trade_intent_distribution": dict(Counter(enriched["trade_intent"])),
        "regime_distribution": dict(Counter(enriched["regime_label"])),
        "parent_bias_distribution": dict(Counter(enriched["parent_bias"])),
        "build_seconds": round(time.time() - t_start, 1),
        "authority": "research_diagnostic_only",
        "declares": ["SEM-018 population surface"],
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
    args = ap.parse_args(argv)

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

    frame, manifest = build_bar_matrix(
        csv_path, instrument=args.instrument, timeframe=args.timeframe, limit=args.limit
    )
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
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )

    print(f"\n  bar_matrix -> {csv_out}")
    print(f"  rows {manifest['rows_emitted']} of {manifest['rows_raw']} raw "
          f"(warmup dropped {manifest['warmup_dropped']}) in {manifest['build_seconds']}s")
    print(f"  schema v{manifest['schema_version']} dim {manifest['canonical_dim']} "
          f"| columns {len(frame.columns)}")
    print(f"  CRT states   : {manifest['crt_state_distribution']}")
    print(f"  trade intent : {manifest['trade_intent_distribution']}")
    print(f"  regime       : {manifest['regime_distribution']}")
    print(f"  parent bias  : {manifest['parent_bias_distribution']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
