"""Visual CRT state-fidelity harness — mechanical integrity floor.

Pre-registration: docs/research/preregistration-visual-crt-state-fidelity.md

Why this file exists: "the HTML doesn't show the answers" is a claim about
generated output, not a property that holds just because the generator
intends it. Each floor is mutation-verified to fail against a leaky
surface or a degenerate scorer (CLAUDE.md E-001: a test that can't fail
isn't enforcement).

Covers:
  1. Labeling surfaces leak no timestamp, CRT noun, engine field, or manifest path.
  2. Sampling is deterministic under a fixed seed.
  3. Ground-truth join is timestamp-only (a candle_index offset cannot resolve).
  4. Config-consistency aborts when events and trace disagree.
  5. The scorer distinguishes perfect from random labels, and reports
     INSUFFICIENT below the minority-class floor.
  6. The real sampler refuses to emit items before the sealed SHA is recorded.
  7. Context windows never reach past the target bar.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research.visual_state_questions import (  # noqa: E402
    BANNED_SURFACE_TOKENS,
    CONTEXT_BARS,
    MIN_CELL_N,
    engine_to_visual,
)
from scripts.research.visual_state_sample import (  # noqa: E402
    assert_surface_blind,
    assert_user_predictions_sealed,
    recorded_seal_digest,
    run as run_sampler,
    verify_config_consistency,
)
from scripts.research.visual_state_score import (  # noqa: E402
    VERDICT,
    _kappa_cell,
    cohen_kappa,
    score,
)


N_BARS = 90
N_SWEEPS = 20


def _ts(i: int) -> str:
    # Sequential 15-minute bars starting 2026-07-07 08:00 (well inside a session).
    epoch = int(datetime(2026, 7, 7, 8, 0, tzinfo=timezone.utc).timestamp()) + i * 900
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _write_fixture(tmp: Path, *, disagree: bool = False, index_offset: int = 0) -> dict:
    csv_path = tmp / "ohlcv.csv"
    events_path = tmp / "events.jsonl"
    trace_path = tmp / "trace.jsonl"
    shots = tmp / "shots"
    shots.mkdir()

    rows = []
    for i in range(N_BARS):
        # Vary range so percentile matching has something to chew on.
        span = 2.0 + (i % 7)
        rows.append({
            "timestamp": _ts(i),
            "open": 2000 + i * 0.1,
            "high": 2000 + i * 0.1 + span,
            "low": 2000 + i * 0.1 - 0.2,
            "close": 2000 + i * 0.1 + 0.3,
            "volume": 100 + i,
        })
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("timestamp,open,high,low,close,volume\n")
        for r in rows:
            fh.write(
                f"{r['timestamp']},{r['open']},{r['high']},{r['low']},{r['close']},{r['volume']}\n"
            )

    # First eligible positive sits at CONTEXT_BARS so every sweep has a full window.
    sweep_idx = list(range(CONTEXT_BARS, CONTEXT_BARS + N_SWEEPS))
    ev_lines = []
    tr_lines = []
    sweep_set = set(sweep_idx)
    for i, r in enumerate(rows):
        is_sweep = i in sweep_set
        direction = "SHORT" if (i % 2 == 0) else "LONG"
        ev_state = "SWEEP" if is_sweep else None
        tr_state = "RANGE"
        if is_sweep:
            tr_state = "RANGE" if (disagree and i == sweep_idx[0]) else "SWEEP"
            ev_lines.append(json.dumps({
                "event": "STATE_TRANSITION",
                "timestamp": r["timestamp"],
                "candle_index": i + index_offset,
                "state_from": "RANGE",
                "state_to": "SWEEP",
                "direction": None,
                "price": None,
                "reason": f"fixture sweep {i}",
                "metadata": {},
            }))
            ev_lines.append(json.dumps({
                "event": "SWEEP",
                "timestamp": r["timestamp"],
                "candle_index": i + index_offset,
                "state_from": None,
                "state_to": None,
                "direction": direction,
                "price": r["high"] if direction == "SHORT" else r["low"],
                "reason": None,
                "metadata": {},
            }))
        tr_lines.append(json.dumps({
            "symbol": "FIXT",
            "timestamp": r["timestamp"],
            "bar_index": i,
            "raw_ohlcv": {
                "open": r["open"], "high": r["high"], "low": r["low"],
                "close": r["close"], "volume": r["volume"],
            },
            "features": {
                "session": float(i % 3),
                "candle_range": r["high"] - r["low"],
            },
            "warmup_complete": True,
            "crt": {
                "state_before": "RANGE",
                "state_after": tr_state,
                "action": "SWEEP_DETECTED" if is_sweep else "NONE",
                "direction": direction if is_sweep else "NONE",
                "warmup_complete": True,
            },
            "crt_inputs": {
                "active_range": {"h_ref": 2010.0, "l_ref": 1990.0},
            },
        }))
    events_path.write_text("\n".join(ev_lines) + "\n", encoding="utf-8")
    trace_path.write_text("\n".join(tr_lines) + "\n", encoding="utf-8")

    # Sidecar: 11 px/candle, offset_hours=0 so bar.t is the UTC epoch of _ts.
    bars = []
    x0, px = 40.0, 11.0
    for i, r in enumerate(rows):
        epoch = int(datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        ).timestamp())
        bars.append({
            "i": i, "t": epoch,
            "o": r["open"], "h": r["high"], "l": r["low"], "c": r["close"],
            "x": x0 + i * px,
        })
    width = int(x0 + N_BARS * px + 40)
    height = 240
    sidecar = {
        "shot": {"name": "fix_m15_legible_00", "interval": "15", "clock": "broker"},
        "saved": "fix_m15_legible_00.png",
        "clock": {"offset_hours": 0},
        "plot": {
            "rect": {"x": 30, "y": 20, "w": width - 50, "h": 180},
            "bar_spacing": px,
            "visible_price_range": {"from": 1980.0, "to": 2120.0},
            "price_calibration": [
                {"price": 1980.0, "y": 200.0},
                {"price": 2120.0, "y": 20.0},
            ],
        },
        "bars": bars,
    }
    (shots / "fix_m15_legible_00.json").write_text(
        json.dumps(sidecar), encoding="utf-8"
    )
    try:
        from PIL import Image
        Image.new("RGBA", (width, height), (0, 0, 0, 255)).save(shots / "fix_m15_legible_00.png")
        has_pil = True
    except ImportError:
        has_pil = False

    return {
        "csv": csv_path,
        "events": events_path,
        "trace": trace_path,
        "shots": shots,
        "has_pil": has_pil,
        "sweep_idx": sweep_idx,
        "rows": rows,
    }


class _Args:
    def __init__(self, tmp: Path, fx: dict, seed: int = 20260818, skip_render: bool = True):
        self.seed = seed
        self.out_dir = str(tmp / f"out_{seed}")
        self.events = str(fx["events"])
        self.trace = str(fx["trace"])
        self.csv = str(fx["csv"])
        self.shots_dir = str(fx["shots"])
        self.allow_unsealed = True
        self.skip_render = skip_render


def _run(tmp: Path, fx: dict, seed: int = 20260818, skip_render: bool = True) -> Path:
    return run_sampler(_Args(tmp, fx, seed=seed, skip_render=skip_render))


# ── engine map ────────────────────────────────────────────────────────────────

def test_engine_to_visual_maps_direction_not_state_name():
    assert engine_to_visual("SWEEP", "SHORT")["v1"] == "above"
    assert engine_to_visual("SWEEP", "LONG")["v1"] == "below"
    assert engine_to_visual("DISPLACEMENT", "LONG")["v2"] == "up"
    assert engine_to_visual("DISPLACEMENT", "SHORT")["v2"] == "down"
    assert engine_to_visual("EXPANSION", None)["v3"] == "yes"
    assert engine_to_visual("RETEST", None)["v4"] == "yes"
    silent = engine_to_visual(None, None)
    assert silent == {"v1": "neither", "v2": "neither", "v3": "no", "v4": "no"}


# ── 1. blinding ───────────────────────────────────────────────────────────────

def test_labeling_html_leaks_no_answer(tmp_path):
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for arm in ("arm1", "arm2"):
        html = (out / arm / "label.html").read_text(encoding="utf-8")
        brief = (out / arm / "brief.md").read_text(encoding="utf-8")
        assert_surface_blind(html, manifest["items"])
        assert_surface_blind(brief, manifest["items"])
        assert "manifest" not in html.lower()
        for tok in BANNED_SURFACE_TOKENS:
            assert tok not in html.lower()
            assert tok not in brief.lower()
        for it in manifest["items"]:
            assert it["timestamp"] not in html
            assert it["item_id"] in html


def test_leaky_surface_is_rejected_mutation(tmp_path):
    """Mutation verification: a surface that names the answer key MUST fail."""
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    leaky = (out / "arm1" / "label.html").read_text(encoding="utf-8")
    leaky += "\n<!-- sample_manifest.json 2026-07-07 08:00:00 SWEEP -->\n"
    with pytest.raises(AssertionError):
        assert_surface_blind(leaky, manifest["items"])


def test_context_window_never_reaches_past_target(tmp_path):
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for it in manifest["items"]:
        assert it["context_end_index"] == it["csv_index"]
        assert it["context_start_index"] == it["csv_index"] - CONTEXT_BARS + 1


# ── 2. determinism ────────────────────────────────────────────────────────────

def test_same_seed_is_deterministic(tmp_path):
    fx = _write_fixture(tmp_path)
    d1 = _run(tmp_path, fx, seed=99)
    d2 = run_sampler(_Args(tmp_path / "b", fx, seed=99, skip_render=True))
    m1 = json.loads((d1 / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((d2 / "manifest.json").read_text(encoding="utf-8"))
    ids1 = [it["item_id"] for it in m1["items"]]
    ids2 = [it["item_id"] for it in m2["items"]]
    assert ids1 == ids2
    assert [it["timestamp"] for it in m1["items"]] == [it["timestamp"] for it in m2["items"]]


# ── 3. join is timestamp, never index ─────────────────────────────────────────

def test_ground_truth_join_ignores_candle_index_offset(tmp_path):
    fx = _write_fixture(tmp_path, index_offset=74)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["join"] == "timestamp"
    positives = [it for it in manifest["items"] if it["role"] == "positive"]
    assert len(positives) == N_SWEEPS
    for it in positives:
        # csv_index is the raw row, NOT the offset engine index
        expected = next(
            i for i, r in enumerate(fx["rows"]) if r["timestamp"] == it["timestamp"]
        )
        assert it["csv_index"] == expected
        assert it["csv_index"] != expected + 74


# ── 4. config consistency ─────────────────────────────────────────────────────

def test_config_mismatch_aborts(tmp_path):
    fx = _write_fixture(tmp_path, disagree=True)
    from scripts.research.visual_state_sample import load_events, load_trace_by_ts
    events = load_events(fx["events"])
    trace = load_trace_by_ts(fx["trace"])
    with pytest.raises(SystemExit, match="config-consistency FAIL"):
        verify_config_consistency(events, trace)


def test_config_agreement_passes_on_fixture(tmp_path):
    fx = _write_fixture(tmp_path, disagree=False)
    from scripts.research.visual_state_sample import load_events, load_trace_by_ts
    meta = verify_config_consistency(load_events(fx["events"]), load_trace_by_ts(fx["trace"]))
    assert meta["disagreements"] == 0
    assert meta["shared_transition_timestamps"] == N_SWEEPS


# ── 5. scorer sanity ──────────────────────────────────────────────────────────

def test_scorer_perfect_labels_give_kappa_one():
    y = [-1, 0, 1] * MIN_CELL_N
    assert cohen_kappa(y, y, weights=None) == pytest.approx(1.0)
    assert cohen_kappa(y, y, weights="linear") == pytest.approx(1.0)
    cell = _kappa_cell(y, y, ordinal=True)
    assert cell["status"] == "SCORED"
    assert cell["kappa"] == pytest.approx(1.0)


def test_scorer_shuffled_labels_give_near_zero_kappa():
    import random
    rng = random.Random(0)
    y_true = [rng.choice([-1, 0, 1]) for _ in range(300)]
    y_pred = [rng.choice([-1, 0, 1]) for _ in range(300)]
    k = cohen_kappa(y_true, y_pred, weights=None)
    assert abs(k) < 0.15


def test_scorer_reports_insufficient_below_min_n():
    cell = _kappa_cell([1, -1], [1, -1], ordinal=False)
    assert cell["status"] == "INSUFFICIENT"
    assert cell["kappa"] is None
    # n large but minority thin
    y = [0] * (MIN_CELL_N + 5) + [1] * (MIN_CELL_N - 1)
    cell = _kappa_cell(y, y, ordinal=False)
    assert cell["status"] == "INSUFFICIENT"


def test_scorer_distinguishes_perfect_from_random_on_manifest(tmp_path):
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    # Perfect labels
    perfect = {
        it["item_id"]: {"item_id": it["item_id"], **it["answers"],
                        "v1_confidence": "HIGH", "evidence": "body"}
        for it in manifest["items"]
    }
    # Independent random labels
    import random
    rng = random.Random(1)
    opts = ["above", "below", "neither"]
    shuffled = {
        it["item_id"]: {
            "item_id": it["item_id"],
            "v1": rng.choice(opts),
            "v2": "neither",
            "v3": "no",
            "v4": "no",
        }
        for it in manifest["items"]
    }
    perfect_report = score(manifest, perfect, perfect)
    random_report = score(manifest, shuffled, shuffled)
    assert perfect_report["verdict"] == VERDICT
    p1 = perfect_report["arm1"]["questions"]["v1"]
    r1 = random_report["arm1"]["questions"]["v1"]
    if p1["status"] == "SCORED":
        assert p1["kappa"] == pytest.approx(1.0)
    if r1["status"] == "SCORED":
        assert abs(r1["kappa"]) < 0.25
    # Degenerate scorer mutation: if we claimed κ=1 on the shuffled arm, fail.
    if r1["status"] == "SCORED":
        assert r1["kappa"] != pytest.approx(1.0)


def test_build_confusion_is_used_not_reimplemented():
    import inspect
    import scripts.research.visual_state_score as scorer
    src = inspect.getsource(scorer)
    assert "from scripts.research.crt_state_confusion_matrix import build_confusion" in src
    assert "def build_confusion" not in src


# ── 6. seal gate ──────────────────────────────────────────────────────────────

def test_recorded_seal_digest_matches_sealed_file():
    """After seal: the prereg slot is a 64-hex digest of the sealed file on disk."""
    digest = recorded_seal_digest()
    assert digest is not None and len(digest) == 64
    sealed = ROOT / "docs" / "research" / "visual-crt-user-predictions.SEALED.md"
    import hashlib
    actual = hashlib.sha256(sealed.read_bytes()).hexdigest()
    assert digest == actual


def test_sampler_refuses_when_prereg_sha_slot_empty(tmp_path):
    fx = _write_fixture(tmp_path)
    args = _Args(tmp_path, fx)
    args.allow_unsealed = False
    empty_prereg = tmp_path / "empty_prereg.md"
    empty_prereg.write_bytes(b"SHA-256 at seal time: `<TO BE FILLED AFTER USER SEALS>`\n")
    import scripts.research.visual_state_sample as samp
    old = samp.PREREG
    samp.PREREG = empty_prereg
    try:
        with pytest.raises(SystemExit, match="SHA-256 slot is empty"):
            run_sampler(args)
    finally:
        samp.PREREG = old


def test_assert_seal_rejects_moved_file(tmp_path):
    prereg = tmp_path / "prereg.md"
    sealed = tmp_path / "sealed.md"
    sealed.write_bytes(b"prediction A\n")
    import hashlib
    digest = hashlib.sha256(b"prediction A\n").hexdigest()
    prereg.write_bytes(f"SHA-256 at seal time: `{digest}`\n".encode("utf-8"))
    assert assert_user_predictions_sealed(prereg, sealed) == digest
    sealed.write_bytes(b"prediction B\n")
    with pytest.raises(SystemExit, match="predictions moved"):
        assert_user_predictions_sealed(prereg, sealed)


# ── 7. sample composition / balance ───────────────────────────────────────────

def test_sample_has_positives_and_matched_controls(tmp_path):
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    roles = [it["role"] for it in manifest["items"]]
    assert roles.count("positive") == N_SWEEPS
    assert roles.count("control") == N_SWEEPS
    bal = manifest["control_balance"]
    assert bal["n_positives"] == N_SWEEPS
    assert bal["n_controls"] == N_SWEEPS
    # Balance is reported, not gated on a p-value.
    assert "positive_range_pct_mean" in bal
    assert "control_range_pct_mean" in bal


def test_filenames_are_opaque(tmp_path):
    fx = _write_fixture(tmp_path)
    out = _run(tmp_path, fx)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for it in manifest["items"]:
        assert it["item_id"].startswith("item_")
        assert it["timestamp"] not in it["item_id"]
        assert "2026" not in it["item_id"]


# ── 8. render path (Pillow) ───────────────────────────────────────────────────

def test_render_respects_px_floor_and_writes_both_arms(tmp_path):
    pytest.importorskip("PIL", reason="Pillow not installed")
    fx = _write_fixture(tmp_path)
    if not fx["has_pil"]:
        pytest.skip("Pillow not installed")
    out = _run(tmp_path, fx, skip_render=False)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for it in manifest["items"]:
        assert it["px_per_candle"] >= 8.0
        p1 = out / "arm1" / f"{it['item_id']}.png"
        p2 = out / "arm2" / f"{it['item_id']}.png"
        assert p1.is_file() and p2.is_file()
        assert p1.stat().st_size != p2.stat().st_size or p1.read_bytes() != p2.read_bytes()
