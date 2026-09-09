"""
shadow_cross_range_restoration_probe.py
========================================
MEASURE-ONLY probe (READ-ONLY w.r.t. src/): does a CRT SHADOW_PENDING->EXPANSION
restoration (StateMachine.try_shadow_pending_to_expansion, crt_engine_v2.py:1070-1094)
resurrect a displacement candle from a DIFFERENT HTF range than the one currently
active ("cross-range restoration"), and does the resulting episode end up rejected by
the "inverted SL" guard in ExecutionEngine.build_trade (crt_engine_v2.py:2379-2390)
more often than a same-range restoration does?

Plan: C:\\Users\\Hi\\.claude\\plans\\continuation-context-crt-jazzy-avalanche.md

Context: reset_to_range (crt_engine_v2.py:1836-1915) stashes the displacement
candle's source-range HTF id into state.pending_displacement_source_htf when an HTF
reset fires mid-DISPLACEMENT; try_shadow_pending_to_expansion later restores that
stale candle without ever comparing its source HTF to the CURRENT
state.active_range.htf_candle_id. That comparison currently only reaches a transient
action["shadow_source_htf"] dict key (crt_engine_v2.py:3089) that no backtest driver
persists anywhere. Separately, the inverted-SL rejection (crt_engine_v2.py:2379-2390)
returns None with only a log.warning -- no EngineEvent, no integrity event, no
telemetry candidate-closure -- so it is invisible to every existing JSONL sink. Two
already-known cross-range instances (n=2, purely suggestive) coincided with an
inverted-stop outcome; this probe measures the real counts across the full corpus.

This script makes ZERO edits to src/config_layer/crt_engine_v2.py. It monkeypatches
three class methods in this process only:
  StateMachine.try_shadow_pending_to_expansion  -- captures shadow_source_htf /
                                                    active_range_htf at restore time
                                                    (Bucket A: same/cross-range)
  ExecutionEngine.build_trade                   -- classifies the eventual outcome by
                                                    return value + an independent
                                                    from-state recomputation of the
                                                    inverted-SL guard condition
                                                    (Bucket B), cross-checked against
                                                    the real log.warning emitted on
                                                    the SAME call
  StateMachine.reset_to_range                   -- closes out an episode that died
                                                    before build_trade was ever reached
Every patch calls the original first and returns its real, unmodified result -- no
engine behavior is changed. Originals are restored in a `finally:` block.

Per the standing instruction, this probe runs on XAUUSD only (data/mt5/XAUUSD_M15.csv).

This is evidence collection only (Authority Ladder, CLAUDE.md Sec 6.5): the output
artifact reports counts, registers no finding, changes no config, and makes no
economic or causal claim.

Usage:
  python scripts/analysis/shadow_cross_range_restoration_probe.py
  python scripts/analysis/shadow_cross_range_restoration_probe.py --csv <path> --instrument XAUUSD
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import (  # noqa: E402
    Direction, ExecutionEngine, StateMachine,
)
from config_layer.production_config import (  # noqa: E402
    PROD_VERSION, load_prod_config_from_registry,
)
from runtime.backtest_v2 import (  # noqa: E402
    BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner,
)
from utils.console_safe import safe_print  # noqa: E402

_DEFAULT_CSV = str(_ROOT / "data" / "mt5" / "XAUUSD_M15.csv")
_DEFAULT_INSTRUMENT = "XAUUSD"
_OUT_DIR = _ROOT / "results" / "analysis"
_ARTIFACT_JSON = _OUT_DIR / "shadow_cross_range_restoration.LATEST.json"
_ARTIFACT_MD = _OUT_DIR / "shadow_cross_range_restoration.LATEST.md"

_BUCKETS = ("SAME_RANGE", "CROSS_RANGE", "UNKNOWN")
_OUTCOMES = (
    "TRADE_OPENED", "INVERTED_STOP_REJECTED", "RESET_BEFORE_EXECUTION",
    "BUILD_TRADE_NONE_OTHER", "UNRESOLVED_AT_EOF", "UNRESOLVED_PRIOR_EPISODE_OVERWRITTEN",
)

# The two already-known cross-range episodes from the manual investigation that
# preceded this probe -- used as a hard sanity replay (see _sanity_check_known_n2).
_KNOWN_CROSS_RANGE_EPISODES = [
    {"candle_index": 65, "shadow_formed_idx": 62,
     "shadow_source_htf": "XAUUSD-HTF-000015", "active_range_htf": "XAUUSD-HTF-000016",
     "direction": "SHORT"},
    {"candle_index": 384, "shadow_formed_idx": 381,
     "shadow_source_htf": "XAUUSD-HTF-000095", "active_range_htf": "XAUUSD-HTF-000096",
     "direction": "LONG"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Pure bucketing function -- shared by the live patch and the post-run
# self-consistency re-derivation, and unit-tested directly in isolation
# (see tests/test_shadow_cross_range_probe.py).
# ─────────────────────────────────────────────────────────────────────────────

def bucket_shadow_cross_range(shadow_source_htf, active_range_htf) -> str:
    if not shadow_source_htf or not active_range_htf:
        return "UNKNOWN"
    if shadow_source_htf == active_range_htf:
        return "SAME_RANGE"
    return "CROSS_RANGE"


# ─────────────────────────────────────────────────────────────────────────────
# Monkeypatches (process-local only -- no edit to src/ on disk)
# ─────────────────────────────────────────────────────────────────────────────

class _ProbeState:
    open_episode: dict | None = None
    episodes: list = []
    n_restorations_total: int = 0
    n_overwritten: int = 0
    n_log_handler_disagreements: int = 0


class _WarningCapture(logging.Handler):
    """Captures WARNING+ records emitted on the logger during one build_trade call."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages: list = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _install_patches() -> tuple:
    """Returns (restore_fn,). Patches StateMachine.try_shadow_pending_to_expansion,
    ExecutionEngine.build_trade, and StateMachine.reset_to_range on the class objects."""
    orig_try_shadow = StateMachine.try_shadow_pending_to_expansion
    orig_build_trade = ExecutionEngine.build_trade
    orig_reset_to_range = StateMachine.reset_to_range

    exec_logger = logging.getLogger("CRT.Execution")
    orig_exec_logger_level = exec_logger.level
    # Ensure the inverted-SL warning is actually emitted to handlers regardless of
    # ambient logging config -- restored in _restore() below.
    exec_logger.setLevel(logging.WARNING)

    def patched_try_shadow(self, state, candle, ev_logger=None):
        shadow_source_htf = state.pending_displacement_source_htf or None
        active_range_htf = (
            state.active_range.htf_candle_id if state.active_range is not None else None
        )
        pending_formed_idx = state.pending_displacement_formed_idx
        pending_dir = state.pending_displacement_dir

        ok = orig_try_shadow(self, state, candle, ev_logger)  # real transition, unmodified

        if ok:
            _ProbeState.n_restorations_total += 1
            bucket = bucket_shadow_cross_range(shadow_source_htf, active_range_htf)
            episode = {
                "candle_index": candle.index,
                "timestamp": str(getattr(candle, "timestamp", "")),
                "shadow_source_htf": shadow_source_htf,
                "active_range_htf": active_range_htf,
                "shadow_cross_range": bucket,
                "shadow_formed_idx": pending_formed_idx,
                "direction": pending_dir.name if pending_dir is not None else "NONE",
                "outcome": "PENDING",
                "reset_reason": None,
                "resolved_at_candle_index": None,
                "log_handler_cross_check": None,
            }
            if _ProbeState.open_episode is not None:
                # A prior episode never resolved before this new restore -- this
                # falsifies the single-episode-at-a-time assumption. Record loudly
                # instead of silently overwriting it.
                prev = _ProbeState.open_episode
                prev["outcome"] = "UNRESOLVED_PRIOR_EPISODE_OVERWRITTEN"
                _ProbeState.episodes.append(prev)
                _ProbeState.n_overwritten += 1
            _ProbeState.open_episode = episode
        return ok

    def patched_build_trade(self, state, risk_engine=None):
        # Independently recompute the inverted-SL guard condition from `state`,
        # mirroring crt_engine_v2.py:2361-2390 exactly, BEFORE calling the original --
        # this lets us positively confirm *why* a None return happened rather than
        # inferring it, distinguishing the guard from the three earlier None-return
        # branches (missing range/sweep, missing displacement, direction NONE).
        direction = state.direction
        predicted_inverted = False
        if (
            state.active_range is not None
            and state.sweep_event is not None
            and state.displacement_candle is not None
            and direction != Direction.NONE
            and state.retest_candle is not None
        ):
            atr = state.atr_abs
            entry = state.retest_candle.close
            buf = self.config.sl_atr_buffer
            if direction == Direction.LONG:
                predicted_sl = state.displacement_candle.low - buf * atr
                predicted_inverted = predicted_sl >= entry
            elif direction == Direction.SHORT:
                predicted_sl = state.displacement_candle.high + buf * atr
                predicted_inverted = predicted_sl <= entry

        handler = _WarningCapture()
        exec_logger.addHandler(handler)
        try:
            trade = orig_build_trade(self, state, risk_engine)  # unmodified real call
        finally:
            exec_logger.removeHandler(handler)

        episode = _ProbeState.open_episode
        if episode is not None:
            if trade is None:
                outcome = "INVERTED_STOP_REJECTED" if predicted_inverted else "BUILD_TRADE_NONE_OTHER"
            else:
                outcome = "TRADE_OPENED"

            log_says_inverted = any("inverted SL" in m for m in handler.messages)
            if trade is None:
                cross_check = "INVERTED_STOP_REJECTED" if log_says_inverted else "BUILD_TRADE_NONE_OTHER"
            else:
                cross_check = "TRADE_OPENED"
            if cross_check != outcome:
                _ProbeState.n_log_handler_disagreements += 1

            episode["outcome"] = outcome
            episode["log_handler_cross_check"] = cross_check
            episode["resolved_at_candle_index"] = state.current_candle_index
            _ProbeState.episodes.append(episode)
            _ProbeState.open_episode = None
        return trade  # unchanged -- live behavior is not altered

    def patched_reset_to_range(self, state, reason, candle=None, ev_logger=None):
        episode = _ProbeState.open_episode
        if episode is not None:
            episode["outcome"] = "RESET_BEFORE_EXECUTION"
            episode["reset_reason"] = reason
            episode["resolved_at_candle_index"] = candle.index if candle is not None else None
            _ProbeState.episodes.append(episode)
            _ProbeState.open_episode = None
        return orig_reset_to_range(self, state, reason, candle, ev_logger)  # unmodified

    StateMachine.try_shadow_pending_to_expansion = patched_try_shadow
    ExecutionEngine.build_trade = patched_build_trade
    StateMachine.reset_to_range = patched_reset_to_range

    def _restore():
        StateMachine.try_shadow_pending_to_expansion = orig_try_shadow
        ExecutionEngine.build_trade = orig_build_trade
        StateMachine.reset_to_range = orig_reset_to_range
        exec_logger.setLevel(orig_exec_logger_level)

    return (_restore,)


# ─────────────────────────────────────────────────────────────────────────────
# Provenance (matches scripts/analysis/soft_conf_ema_double_update_probe.py)
# ─────────────────────────────────────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_provenance() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
    except Exception:
        sha = None
    try:
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=str(_ROOT), text=True
        ).strip())
    except Exception:
        dirty = None
    return {
        "git_sha": sha,
        "tree_dirty": dirty,
        "note": (
            "tree_dirty=true means untracked/uncommitted files exist alongside git_sha "
            "-- git_sha does not fully characterise what ran; treat as best-effort "
            "provenance, not a clean pin."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Contingency table + self-consistency + known-n2 sanity check
# ─────────────────────────────────────────────────────────────────────────────

def _build_contingency(episodes: list) -> dict:
    table = {b: {o: 0 for o in _OUTCOMES} for b in _BUCKETS}
    for ep in episodes:
        table[ep["shadow_cross_range"]][ep["outcome"]] += 1
    return table


def _self_consistency_check(episodes: list) -> dict:
    mismatches = []
    for ep in episodes:
        recomputed = bucket_shadow_cross_range(ep["shadow_source_htf"], ep["active_range_htf"])
        if recomputed != ep["shadow_cross_range"]:
            mismatches.append({
                "candle_index": ep["candle_index"],
                "live_bucket": ep["shadow_cross_range"],
                "recomputed_bucket": recomputed,
            })
    return {"n_mismatches": len(mismatches), "mismatches": mismatches}


def _sanity_check_known_n2(episodes: list) -> dict:
    observed = [
        {
            "candle_index": ep["candle_index"],
            "shadow_formed_idx": ep["shadow_formed_idx"],
            "shadow_source_htf": ep["shadow_source_htf"],
            "active_range_htf": ep["active_range_htf"],
            "direction": ep["direction"],
        }
        for ep in episodes if ep["shadow_cross_range"] == "CROSS_RANGE"
    ]
    expected_set = {tuple(sorted(e.items())) for e in _KNOWN_CROSS_RANGE_EPISODES}
    observed_set = {tuple(sorted(o.items())) for o in observed}
    reproduced = expected_set.issubset(observed_set)
    return {
        "expected": _KNOWN_CROSS_RANGE_EPISODES,
        "observed_cross_range_episodes": observed,
        "reproduced": reproduced,
        "detail": (
            "Every known n=2 cross-range episode from the manual investigation must "
            "appear in the probe's own CROSS_RANGE bucket. reproduced=false means the "
            "probe is instrumenting the wrong moment relative to state mutation and "
            "must be fixed before this artifact is trusted."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", default=_DEFAULT_CSV)
    p.add_argument("--instrument", default=_DEFAULT_INSTRUMENT)
    p.add_argument(
        "--output",
        default=str(_ROOT / "results" / "analysis" / "shadow_cross_range_probe_run"),
    )
    args = p.parse_args()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    (restore,) = _install_patches()
    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, args.instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = args.instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(args.instrument, 0.0001)
        loader = CandleLoader(args.csv, args.instrument)
        runner = BacktestRunner(
            cfg, csv_path=args.csv,
            overrides={"diagnostic": "shadow_cross_range_restoration_probe"},
        )
        runner.run(loader.stream(), loader.count(), args.output)
    finally:
        restore()

    episodes = list(_ProbeState.episodes)
    if _ProbeState.open_episode is not None:
        ep = _ProbeState.open_episode
        ep["outcome"] = "UNRESOLVED_AT_EOF"
        episodes.append(ep)

    contingency = _build_contingency(episodes)
    self_check = _self_consistency_check(episodes)
    sanity = _sanity_check_known_n2(episodes)

    artifact = {
        "artifact": "shadow_cross_range_restoration_probe",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "csv_path": args.csv,
        "csv_sha256": _sha256_file(Path(args.csv)),
        "config_version": PROD_VERSION,
        "provenance": _git_provenance(),
        "contingency_table": contingency,
        "n_restorations_total": _ProbeState.n_restorations_total,
        "n_overwritten_unresolved_prior_episode": _ProbeState.n_overwritten,
        "n_log_handler_disagreements": _ProbeState.n_log_handler_disagreements,
        "episodes": episodes,
        "self_consistency_check": self_check,
        "known_n2_sanity_check": sanity,
        "authority_disclaimer": {
            "economic_claims_allowed": False,
            "n_too_small_for_inference": True,
            "note": (
                "Reports observed counts only. Makes no claim that cross-range "
                "restoration causes or correlates with inverted-stop outcomes. "
                "Not a finding -- no G001, no promotion."
            ),
        },
        "caveats": {
            "pending_displacement_source_htf_ordering": (
                "reset_to_range stamps pending_displacement_source_htf from "
                "state.active_range.htf_candle_id AFTER the caller (process_candle) "
                "has already reassigned active_range to the post-reset range -- this "
                "field may not faithfully record the range the displacement actually "
                "formed under. Known pre-existing imprecision, not fixed by this probe."
            ),
        },
    }

    with open(_ARTIFACT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, default=str)

    md = _render_md(artifact)
    with open(_ARTIFACT_MD, "w", encoding="utf-8") as f:
        f.write(md)

    safe_print(md)
    safe_print(f"\nArtifact: {_ARTIFACT_JSON.relative_to(_ROOT)}")

    if self_check["n_mismatches"] > 0:
        safe_print(f"\nERROR: self-consistency check found {self_check['n_mismatches']} mismatches.")
        return 1
    if not sanity["reproduced"]:
        safe_print("\nERROR: known n=2 cross-range sanity check did not reproduce.")
        return 1
    return 0


def _render_md(a: dict) -> str:
    ct = a["contingency_table"]
    lines = [
        "# Shadow Cross-Range Restoration Probe",
        "",
        f"**Instrument:** {a['instrument']}  **Config:** {a['config_version']}  "
        f"**CSV SHA256:** {a['csv_sha256'][:16]}...",
        f"**git_sha:** {a['provenance']['git_sha']}  **tree_dirty:** {a['provenance']['tree_dirty']}",
        "",
        "## Contingency table (bucket x outcome)",
        "",
        "| Bucket | " + " | ".join(_OUTCOMES) + " |",
        "|---" * (len(_OUTCOMES) + 1) + "|",
    ]
    for b in _BUCKETS:
        row = [str(ct[b][o]) for o in _OUTCOMES]
        lines.append(f"| {b} | " + " | ".join(row) + " |")
    lines += [
        "",
        f"- n_restorations_total: {a['n_restorations_total']}",
        f"- n_overwritten_unresolved_prior_episode: {a['n_overwritten_unresolved_prior_episode']}",
        f"- n_log_handler_disagreements: {a['n_log_handler_disagreements']}",
        "",
        "## Self-consistency",
        f"- n_mismatches: {a['self_consistency_check']['n_mismatches']}",
        "",
        "## Known n=2 sanity replay",
        f"- reproduced: {a['known_n2_sanity_check']['reproduced']}",
        "",
        "## Authority disclaimer",
        a["authority_disclaimer"]["note"],
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
