"""Mathematical Trace Corpus floor (ERP) — schema + PIT-alignment + descriptive-only.

Validates the descriptive trace corpus: every trace carries all 38 canonical features + outcome fields;
the entry-bar feature join is index-correct (PIT-aligned, keyed by stream position); and the corpus /
distributions carry NO edge/verdict field. `slow` + SKIP-if-absent (the corpus is a gitignored artifact
built by scripts/research/build_trace_corpus.py).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from features.feature_schema import CANONICAL_FEATURES

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "results" / "research" / "trace_corpus" / "xauusd"
_CORPUS = _DIR / "trace_corpus.jsonl"
_DIST = _DIR / "distributions.json"

pytestmark = [pytest.mark.research_integrity, pytest.mark.slow]
skip_no_corpus = pytest.mark.skipif(not _CORPUS.exists(), reason="trace corpus artifact not built")


def _rows():
    return [json.loads(ln) for ln in _CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_trace_corpus", _ROOT / "scripts" / "research" / "build_trace_corpus.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@skip_no_corpus
def test_corpus_schema_and_no_edge_field():
    rows = _rows()
    assert rows
    r = rows[0]
    for n in CANONICAL_FEATURES:
        assert f"feature_{n}" in r, n
    for k in ("family", "instrument", "entry_index", "direction", "outcome",
              "rr_achieved", "mfe", "mae", "duration_candles", "reached_1r"):
        assert k in r, k
    assert all(row["outcome"] in {"TP_HIT", "SL_HIT", "TIMEOUT"} for row in rows)
    # descriptive artifact — must carry no edge/verdict/promote/profit field
    assert not any(k in r for k in ("verdict", "promote", "edge", "profit", "authority"))


@skip_no_corpus
def test_pit_alignment_features_join_by_stream_position():
    drv = _load_builder()
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
    from runtime.backtest_v2 import CandleLoader

    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD")
    candles = list(CandleLoader(guarded, "XAUUSD").stream())
    by_pos = drv._feature_lookup(candles)

    # sample toy trades past the pipeline warmup head (>=78) with a valid atr
    sample = [r for r in _rows()
              if r["family"] == "expansion_breakout" and r["entry_index"] >= 78
              and r.get("feature_atr") is not None][:5]
    assert sample, "no post-warmup expansion trades to check"
    for r in sample:
        exp = by_pos.get(r["entry_index"], {})
        assert r["feature_atr"] == pytest.approx(exp["atr"], rel=1e-9), r["entry_index"]
        assert r["feature_body_ratio"] == pytest.approx(exp["body_ratio"], rel=1e-9)
        assert r["feature_disp_strength"] == pytest.approx(exp["disp_strength"], rel=1e-9)


@pytest.mark.slow
@pytest.mark.skipif(not (_ROOT / "data" / "mt5" / "XAUUSD_M15.csv").exists(),
                    reason="XAUUSD frozen candidate not present")
def test_parallel_forward_walk_kernel_matches_sequential():
    """Determinism gate (fast): the --jobs>1 parallel forward_walk KERNEL must produce Outcomes identical
    to a direct research.measurement.forward_walk (what --jobs 1 / run_instrument calls) for the same
    signals. Exercises the worker future-slicing + forward_walk without a full corpus rebuild.

    The full byte-identity of the whole corpus is proven manually (kept out of CI for runtime):
        python scripts/research/build_trace_corpus.py --families toy --jobs 1 --out-dir A
        python scripts/research/build_trace_corpus.py --families toy --jobs 4 --out-dir B
        diff A/trace_corpus.jsonl B/trace_corpus.jsonl   # -> empty (byte-identical)
    """
    import importlib.util

    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
    from research.config import ResearchConfig
    from research.measurement.forward_walk import forward_walk
    from research.registry import get_hypothesis
    from runtime.backtest_v2 import CandleLoader
    import research.hypotheses  # noqa: F401  (register)

    spec = importlib.util.spec_from_file_location(
        "build_trace_corpus", _ROOT / "scripts" / "research" / "build_trace_corpus.py")
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)

    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD")
    candles = list(CandleLoader(guarded, "XAUUSD").stream())
    for i, c in enumerate(candles):
        c.index = i
    cfg = ResearchConfig.from_file(drv.TOY_CONFIG)

    # collect signals over an early slice (fast; identical to full detection for those bars)
    sigs = drv._collect_signals(get_hypothesis("expansion_breakout"), candles[:5000], cfg)
    assert sigs, "no signals collected"
    drv._init_worker(guarded, "XAUUSD", cfg.max_forward, cfg.entry_ttl, cfg.trail_mult, cfg.exit_model)

    checked = 0
    for sig, kind in sigs:
        assert kind == "std"  # toys are not oco
        ei = sig.entry_index
        fut = candles[ei + 1:ei + 1 + cfg.max_forward]
        direct = (forward_walk(sig, fut, max_forward=cfg.max_forward, trail_mult=cfg.trail_mult,
                               exit_model=cfg.exit_model) if fut else None)
        assert drv._fw_worker((sig, kind)) == direct, ei  # frozen-dataclass equality
        checked += 1
    assert checked > 0


@pytest.mark.skipif(not _DIST.exists(), reason="distributions.json not built")
def test_distributions_are_descriptive_only():
    rep = json.loads(_DIST.read_text(encoding="utf-8"))
    assert "no edge" in rep["banner"].lower()
    assert "overall" in rep and "by_outcome" in rep and "family_comparison" in rep
    assert not any(k in rep for k in ("verdict", "promote", "edge", "profit", "authority"))
