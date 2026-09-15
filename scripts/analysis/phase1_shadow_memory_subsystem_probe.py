"""
phase1_shadow_memory_subsystem_probe.py
=======================================
MEASURE-ONLY probe (no src/ edits): census Phase-1 XAUUSD shadow displacement
memory funnel under locked object:

  Unresolved HTF displacement memory preserved through RANGE, reactivated by
  matching sweep (sweep.dir == pending_dir) before TTL expiry → shadow-resume
  EXPANSION (strength skipped).

economic_claims_allowed=false. No population expansion. No freeze work.
No OB/PDH/liquidity expansion.

Patches (process-local, originals restored in finally):
  StateMachine.reset_to_range
  StateMachine.try_range_to_shadow_pending
  StateMachine.try_shadow_pending_to_expansion
  CRTEngine.process_candle  (TTL-exhaustion + SHADOW_LEAK / failed resume)

Usage:
  set PYTHONPATH=D:\\Tradelatest
  .venv\\Scripts\\python.exe scripts/analysis/phase1_shadow_memory_subsystem_probe.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    CRTEngine, CRTState, Direction, StateMachine,
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
_OUT_DIR = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "event_census"
_ARTIFACT_JSON = _OUT_DIR / "memory_subsystem.json"
_ARTIFACT_MD = _OUT_DIR / "memory_subsystem.md"
_NOTE_MD = _ROOT / "docs" / "research" / "phase1_shadow_memory_subsystem_note.md"
_COLLAPSES = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "collapses.json"

_KNOWN_COLLAPSE_IDX = {1459, 2197, 2325, 10787, 24371, 37381}


from research.provenance import sha256_file as _sha256_file  # noqa: E402 — research-framework Phase 1 dedup


def _git_provenance() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_ROOT, text=True
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=_ROOT, text=True
        ).strip())
        return {"git_sha": sha, "tree_dirty": dirty}
    except Exception as e:
        return {"git_sha": None, "tree_dirty": None, "error": str(e)}


class _Probe:
    memories: list = []
    open_memory: dict | None = None
    n_created = 0
    n_expire_ttl = 0
    n_cleared_non_htf = 0
    n_shadow_pending = 0
    n_restore_ok = 0
    n_restore_fail = 0
    n_shadow_leak = 0
    n_eof_open = 0
    restore_records: list = []
    fail_records: list = []
    leak_records: list = []
    expire_records: list = []
    create_records: list = []
    shadow_pending_records: list = []
    # process_candle bookkeeping for TTL edge
    _pre_ttl = 0
    _pre_candle = None
    _pre_dir = None
    _pre_formed = 0
    _pre_created_idx = 0
    _pre_src = ""
    _pre_reason = ""
    _pre_state = None


def _close_open(outcome: str, candle_index: int, extra: dict | None = None) -> None:
    mem = _Probe.open_memory
    if mem is None:
        return
    mem["outcome"] = outcome
    mem["closed_idx"] = candle_index
    mem["bars_alive"] = (
        candle_index - mem["created_idx"] if mem.get("created_idx") is not None else None
    )
    if extra:
        mem.update(extra)
    _Probe.open_memory = None


def _install_patches():
    orig_reset = StateMachine.reset_to_range
    orig_to_shadow = StateMachine.try_range_to_shadow_pending
    orig_to_exp = StateMachine.try_shadow_pending_to_expansion
    orig_process = CRTEngine.process_candle

    def patched_reset(self, state, reason, candle=None, ev_logger=None):
        create_shadow = (
            state.current_state == CRTState.DISPLACEMENT
            and state.displacement_candle is not None
            and "HTF" in reason
        )
        ttl_before = state.pending_displacement_ttl
        if create_shadow:
            # Capture pre-mutation fields that reset will stash
            formed = state._displacement_entry_idx
            direction = state.direction
            src = state.active_range.htf_candle_id if state.active_range else ""
            age = (candle.index - formed) if candle else 0
            created_idx = candle.index if candle else state.current_candle_index
            cfg_ttl = self.config.pending_displacement_ttl_candles
        elif ttl_before > 0:
            # Will clear existing memory (non-HTF reset path)
            pass

        orig_reset(self, state, reason, candle, ev_logger)

        if create_shadow:
            _Probe.n_created += 1
            if _Probe.open_memory is not None:
                # Overwrite prior unresolved memory (rare; record)
                prev = _Probe.open_memory
                prev["outcome"] = "OVERWRITTEN_BY_NEW_MEMORY"
                prev["closed_idx"] = created_idx
                _Probe.open_memory = None
            mem = {
                "memory_id": _Probe.n_created,
                "created_idx": created_idx,
                "timestamp": str(getattr(candle, "timestamp", "")) if candle else "",
                "formed_idx": formed,
                "direction": direction.name if direction is not None else "NONE",
                "source_htf": src,
                "reason_created": reason,
                "age_at_reset": age,
                "ttl_initial": cfg_ttl,
                "outcome": "OPEN",
                "closed_idx": None,
                "bars_alive": None,
                "shadow_pending_idx": None,
                "restore_idx": None,
                "ttl_at_shadow_pending": None,
                "ttl_at_restore": None,
            }
            _Probe.open_memory = mem
            _Probe.memories.append(mem)
            _Probe.create_records.append({
                "memory_id": mem["memory_id"],
                "created_idx": created_idx,
                "formed_idx": formed,
                "direction": mem["direction"],
                "source_htf": src,
                "ttl_initial": cfg_ttl,
                "reason": reason,
            })
        elif ttl_before > 0 and not create_shadow:
            # Non-HTF reset expired/cleared existing shadow memory
            _Probe.n_cleared_non_htf += 1
            _close_open(
                "CLEARED_NON_HTF_RESET",
                candle.index if candle else -1,
                {"clear_reason": reason},
            )

    def patched_to_shadow(self, state, sweep, ev_logger=None):
        ttl_now = state.pending_displacement_ttl
        ok = orig_to_shadow(self, state, sweep, ev_logger)
        if ok:
            _Probe.n_shadow_pending += 1
            idx = sweep.candle.index if sweep.candle is not None else getattr(sweep, "candle_index", None)
            rec = {
                "shadow_pending_idx": idx,
                "timestamp": str(getattr(sweep.candle, "timestamp", "")) if sweep.candle else "",
                "sweep_dir": sweep.direction.name if sweep.direction else "NONE",
                "pending_dir": state.pending_displacement_dir.name
                if state.pending_displacement_dir else "NONE",
                "ttl_at_entry": ttl_now,
                "formed_idx": state.pending_displacement_formed_idx,
                "memory_id": _Probe.open_memory["memory_id"] if _Probe.open_memory else None,
            }
            _Probe.shadow_pending_records.append(rec)
            if _Probe.open_memory is not None:
                _Probe.open_memory["shadow_pending_idx"] = idx
                _Probe.open_memory["ttl_at_shadow_pending"] = ttl_now
        return ok

    def patched_to_exp(self, state, candle, ev_logger=None):
        ttl_remaining = state.pending_displacement_ttl
        formed = state.pending_displacement_formed_idx
        created_idx = (
            _Probe.open_memory["created_idx"] if _Probe.open_memory else state.pending_displacement_created_idx
        )
        direction = state.pending_displacement_dir
        src = state.pending_displacement_source_htf
        ok = orig_to_exp(self, state, candle, ev_logger)
        if ok:
            _Probe.n_restore_ok += 1
            bars_since_formed = candle.index - formed if formed else None
            bars_since_created = candle.index - created_idx if created_idx else None
            formed_to_collapse = candle.index - formed if formed else None
            rec = {
                "collapse_idx": candle.index,
                "timestamp": str(getattr(candle, "timestamp", "")),
                "formed_idx": formed,
                "created_idx": created_idx,
                "direction": direction.name if direction else "NONE",
                "source_htf": src,
                "ttl_remaining_at_restore": ttl_remaining,
                "bars_since_formed": bars_since_formed,
                "bars_since_memory_created": bars_since_created,
                "formed_idx_to_collapse_idx_distance": formed_to_collapse,
                "near_ttl_1": ttl_remaining == 1,
                "near_ttl_4": ttl_remaining == 4,
                "known_collapse": candle.index in _KNOWN_COLLAPSE_IDX,
                "memory_id": _Probe.open_memory["memory_id"] if _Probe.open_memory else None,
            }
            _Probe.restore_records.append(rec)
            _close_open(
                "RESTORED_TO_EXPANSION",
                candle.index,
                {
                    "restore_idx": candle.index,
                    "ttl_at_restore": ttl_remaining,
                },
            )
        else:
            _Probe.n_restore_fail += 1
            fail = {
                "candle_index": candle.index,
                "timestamp": str(getattr(candle, "timestamp", "")),
                "ttl_remaining": ttl_remaining,
                "formed_idx": formed,
                "reason": "try_shadow_pending_to_expansion_returned_false",
                "memory_id": _Probe.open_memory["memory_id"] if _Probe.open_memory else None,
            }
            _Probe.fail_records.append(fail)
            _close_open("RESTORE_FAILED", candle.index, {"fail": fail})
        return ok

    def patched_process(self, candle, htf_candle_id, parent_state=None, parent_objective=None, *args, **kwargs):
        st = self.state
        _Probe._pre_ttl = st.pending_displacement_ttl
        _Probe._pre_candle = st.pending_displacement_candle
        _Probe._pre_dir = st.pending_displacement_dir
        _Probe._pre_formed = st.pending_displacement_formed_idx
        _Probe._pre_created_idx = st.pending_displacement_created_idx
        _Probe._pre_src = st.pending_displacement_source_htf
        _Probe._pre_reason = st.pending_displacement_reason_created
        _Probe._pre_state = st.current_state

        action = orig_process(
            self, candle, htf_candle_id,
            parent_state=parent_state,
            parent_objective=parent_objective,
            *args, **kwargs,
        )

        # TTL exhaustion on RANGE branch: pending was live, now cleared, and we
        # did not enter SHADOW_PENDING / restore on this bar.
        act = (action or {}).get("action") if isinstance(action, dict) else None
        ttl_after = st.pending_displacement_ttl
        candle_after = st.pending_displacement_candle

        if (
            _Probe._pre_ttl > 0
            and _Probe._pre_candle is not None
            and ttl_after == 0
            and candle_after is None
            and act not in (
                "SHADOW_SWEEP_DETECTED",
                "SHADOW_EXPANSION_CONFIRMED",
                "SHADOW_LEAK",
            )
            and _Probe.open_memory is not None
            and _Probe.open_memory.get("outcome") == "OPEN"
        ):
            # Distinguish non-HTF clear (already closed in reset patch) vs TTL tick-out
            # If still OPEN here, this was the RANGE countdown hitting 0.
            _Probe.n_expire_ttl += 1
            exp = {
                "expire_idx": candle.index,
                "timestamp": str(getattr(candle, "timestamp", "")),
                "ttl_was": _Probe._pre_ttl,
                "formed_idx": _Probe._pre_formed,
                "created_idx": _Probe._pre_created_idx,
                "direction": _Probe._pre_dir.name if _Probe._pre_dir else "NONE",
                "source_htf": _Probe._pre_src,
                "bars_since_created": candle.index - _Probe._pre_created_idx
                if _Probe._pre_created_idx else None,
                "memory_id": _Probe.open_memory["memory_id"],
                "pre_state": _Probe._pre_state.name if _Probe._pre_state else None,
            }
            _Probe.expire_records.append(exp)
            _close_open("EXPIRED_TTL", candle.index, {"expire": exp})

        if act == "SHADOW_LEAK":
            _Probe.n_shadow_leak += 1
            leak = {
                "candle_index": candle.index,
                "timestamp": str(getattr(candle, "timestamp", "")),
                "ttl_pre": _Probe._pre_ttl,
                "formed_idx": _Probe._pre_formed,
                "memory_id": _Probe.open_memory["memory_id"] if _Probe.open_memory else None,
            }
            _Probe.leak_records.append(leak)
            if _Probe.open_memory is not None and _Probe.open_memory.get("outcome") == "OPEN":
                _close_open("SHADOW_LEAK", candle.index, {"leak": leak})

        return action

    StateMachine.reset_to_range = patched_reset
    StateMachine.try_range_to_shadow_pending = patched_to_shadow
    StateMachine.try_shadow_pending_to_expansion = patched_to_exp
    CRTEngine.process_candle = patched_process

    def restore():
        StateMachine.reset_to_range = orig_reset
        StateMachine.try_range_to_shadow_pending = orig_to_shadow
        StateMachine.try_shadow_pending_to_expansion = orig_to_exp
        CRTEngine.process_candle = orig_process

    return restore


def _rates(num: int, den: int) -> float | None:
    if den == 0:
        return None
    return round(num / den, 6)


def _build_artifact(csv_path: str, instrument: str, run_output: str) -> dict:
    if _Probe.open_memory is not None:
        _Probe.n_eof_open += 1
        _close_open("UNRESOLVED_AT_EOF", -1)

    n_created = _Probe.n_created
    n_expire = _Probe.n_expire_ttl
    n_shadow = _Probe.n_shadow_pending
    n_restore = _Probe.n_restore_ok

    # Load collapses for cross-check
    collapses = []
    if _COLLAPSES.exists():
        collapses = json.loads(_COLLAPSES.read_text(encoding="utf-8"))

    known6 = [r for r in _Probe.restore_records if r["collapse_idx"] in _KNOWN_COLLAPSE_IDX]
    ttl_dist = {}
    for r in _Probe.restore_records:
        k = r["ttl_remaining_at_restore"]
        ttl_dist[str(k)] = ttl_dist.get(str(k), 0) + 1

    outcome_counts = {}
    for m in _Probe.memories:
        outcome_counts[m["outcome"]] = outcome_counts.get(m["outcome"], 0) + 1

    artifact = {
        "artifact": "phase1_shadow_memory_subsystem_census",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "instrument": instrument,
        "csv_path": csv_path,
        "csv_sha256": _sha256_file(Path(csv_path)),
        "config_version": PROD_VERSION,
        "provenance": _git_provenance(),
        "locked_object": (
            "Unresolved HTF displacement memory preserved through RANGE, "
            "reactivated by matching sweep (sweep.dir == pending_dir) before "
            "TTL expiry → shadow-resume EXPANSION (strength skipped)."
        ),
        "economic_claims_allowed": False,
        "ttl_code_cites": {
            "CRTConfig_default": {
                "file": "src/config_layer/state_identity.py",
                "line": 250,
                "text": "pending_displacement_ttl_candles: int = 4",
            },
            "YAML_lifecycle": {
                "file": "configs/formulas/market_crt_states.yaml",
                "line": 351,
                "text": "pending_displacement_ttl_candles: 4",
            },
            "prod_config": {
                "file": "configs/production/v2_htfcrt_2026_08.json",
                "path": "crt_engine.pending_displacement_ttl_candles",
                "value": 4,
            },
            "assignment_on_create": {
                "file": "src/config_layer/crt_engine_v2.py",
                "line": 1901,
                "text": (
                    "state.pending_displacement_ttl = "
                    "self.config.pending_displacement_ttl_candles"
                ),
            },
            "create_gate": {
                "file": "src/config_layer/crt_engine_v2.py",
                "lines": "1892-1915",
                "condition": (
                    "current_state==DISPLACEMENT AND displacement_candle "
                    "is not None AND 'HTF' in reason"
                ),
            },
            "countdown": {
                "file": "src/config_layer/crt_engine_v2.py",
                "lines": "2961-2977",
                "note": (
                    "RANGE branch decrements pending_displacement_ttl when "
                    "candle.index != pending_displacement_created_idx; clears on 0."
                ),
            },
            "why_4": (
                "CRTConfig / market_crt_states lifecycle / v2_htfcrt_2026_08 pin "
                "pending_displacement_ttl_candles=4: candles a pending_displacement "
                "memory survives after an HTF reset (independent of "
                "backtest.htf_candles_per_range). Set to 0 to disable. Not derived "
                "in-engine; config default."
            ),
        },
        "funnel": {
            "n_memories_created": n_created,
            "n_expire_ttl_before_confirming_sweep": n_expire,
            "n_cleared_non_htf_reset": _Probe.n_cleared_non_htf,
            "n_enter_SHADOW_PENDING": n_shadow,
            "n_restore_try_shadow_pending_to_expansion_ok": n_restore,
            "n_restore_fail": _Probe.n_restore_fail,
            "n_shadow_leak": _Probe.n_shadow_leak,
            "n_unresolved_at_eof": _Probe.n_eof_open,
            "outcome_counts": outcome_counts,
            "rates": {
                "P_SHADOW_PENDING_given_memory_created": _rates(n_shadow, n_created),
                "P_restore_given_SHADOW_PENDING": _rates(n_restore, n_shadow),
                "P_expire_ttl_given_memory_created": _rates(n_expire, n_created),
                "P_cleared_non_htf_given_memory_created": _rates(
                    _Probe.n_cleared_non_htf, n_created
                ),
                "P_restore_given_memory_created": _rates(n_restore, n_created),
            },
        },
        "ttl_at_restore_distribution": ttl_dist,
        "known_6_restores": known6,
        "all_restores": _Probe.restore_records,
        "failed_resume_attempts": {
            "try_shadow_false": _Probe.fail_records,
            "shadow_leak": _Probe.leak_records,
            "note": (
                "Failed resumes are logged here if try_shadow_pending_to_expansion "
                "returns False or SHADOW_LEAK fires. TTL-exhaustion clears memory "
                "before a confirming sweep can arm SHADOW_PENDING (same-bar order: "
                "decrement then detect)."
            ),
        },
        "expire_sample": _Probe.expire_records[:50],
        "n_expire_records": len(_Probe.expire_records),
        "create_sample": _Probe.create_records[:50],
        "shadow_pending_records": _Probe.shadow_pending_records,
        "collapses_json_crosscheck": {
            "path": str(_COLLAPSES),
            "n": len(collapses),
            "candle_indices": [c.get("candle_index") for c in collapses],
            "probe_restore_indices": [r["collapse_idx"] for r in _Probe.restore_records],
            "indices_match": sorted(c.get("candle_index") for c in collapses)
            == sorted(r["collapse_idx"] for r in _Probe.restore_records),
        },
        "bt_summary_crosscheck": {
            "funnel_counts_SHADOW_PENDING_expected": 6,
            "probe_n_SHADOW_PENDING": n_shadow,
            "probe_n_restore": n_restore,
        },
        "run_output": run_output,
        "authority_disclaimer": {
            "economic_claims_allowed": False,
            "note": (
                "Descriptive census only. No economic claim, no Case reopen, "
                "no object widening, no freeze mutation."
            ),
        },
    }
    return artifact


def _render_md(a: dict) -> str:
    f = a["funnel"]
    r = f["rates"]
    lines = [
        "# Phase-1 shadow memory subsystem census",
        "",
        f"**Instrument:** {a['instrument']}  **Config:** {a['config_version']}  "
        f"**CSV SHA256:** {a['csv_sha256'][:16]}…",
        f"**generated_at (UTC):** {a['generated_at']}",
        f"**economic_claims_allowed:** {a['economic_claims_allowed']}",
        "",
        "## Locked object",
        "",
        a["locked_object"],
        "",
        "## Q1 — Why / where is pending_ttl = 4 set?",
        "",
        a["ttl_code_cites"]["why_4"],
        "",
        "| Cite | Location | Text |",
        "|---|---|---|",
    ]
    for key in (
        "CRTConfig_default",
        "YAML_lifecycle",
        "prod_config",
        "assignment_on_create",
        "create_gate",
        "countdown",
    ):
        c = a["ttl_code_cites"][key]
        loc = c.get("file", "")
        if "line" in c:
            loc += f":{c['line']}"
        elif "lines" in c:
            loc += f":{c['lines']}"
        elif "path" in c:
            loc += f" `{c['path']}`={c.get('value')}"
        text = c.get("text") or c.get("condition") or c.get("note") or ""
        lines.append(f"| {key} | `{loc}` | {text} |")

    lines += [
        "",
        "## Funnel (measured)",
        "",
        "| Stage | Count | Rate vs created |",
        "|---|---:|---:|",
        f"| Memories created (DISPLACEMENT HTF-reset → pending_*) | {f['n_memories_created']} | 1.000 |",
        f"| Expire TTL before confirming sweep | {f['n_expire_ttl_before_confirming_sweep']} | {r['P_expire_ttl_given_memory_created']} |",
        f"| Cleared by non-HTF reset | {f['n_cleared_non_htf_reset']} | {r['P_cleared_non_htf_given_memory_created']} |",
        f"| Enter SHADOW_PENDING | {f['n_enter_SHADOW_PENDING']} | {r['P_SHADOW_PENDING_given_memory_created']} |",
        f"| Restore OK (try_shadow_pending_to_expansion) | {f['n_restore_try_shadow_pending_to_expansion_ok']} | {r['P_restore_given_memory_created']} |",
        f"| Restore fail (try_shadow false) | {f['n_restore_fail']} | — |",
        f"| SHADOW_LEAK | {f['n_shadow_leak']} | — |",
        f"| Unresolved at EOF | {f['n_unresolved_at_eof']} | — |",
        "",
        "### Conditional rates",
        "",
        f"- P(SHADOW_PENDING | memory created) = **{r['P_SHADOW_PENDING_given_memory_created']}**",
        f"- P(restore | SHADOW_PENDING) = **{r['P_restore_given_SHADOW_PENDING']}**",
        f"- P(expire TTL | memory created) = **{r['P_expire_ttl_given_memory_created']}**",
        "",
        f"Outcome breakdown: `{f['outcome_counts']}`",
        "",
        "## Known-6 restores — TTL remaining / distances",
        "",
        "| collapse_idx | formed_idx | created_idx | ttl_remaining | bars_since_formed | bars_since_created | formed→collapse | near TTL=1? | near TTL=4? |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for rec in a["known_6_restores"]:
        lines.append(
            f"| {rec['collapse_idx']} | {rec['formed_idx']} | {rec['created_idx']} | "
            f"{rec['ttl_remaining_at_restore']} | {rec['bars_since_formed']} | "
            f"{rec['bars_since_memory_created']} | {rec['formed_idx_to_collapse_idx_distance']} | "
            f"{rec['near_ttl_1']} | {rec['near_ttl_4']} |"
        )
    lines += [
        "",
        f"**TTL-at-restore distribution (all restores):** `{a['ttl_at_restore_distribution']}`",
        "",
        "## Failed / false resume attempts",
        "",
        f"- try_shadow_pending_to_expansion returned False: **{len(a['failed_resume_attempts']['try_shadow_false'])}**",
        f"- SHADOW_LEAK: **{len(a['failed_resume_attempts']['shadow_leak'])}**",
        "",
        a["failed_resume_attempts"]["note"],
        "",
        "## Cross-checks",
        "",
        f"- collapses.json indices match probe restores: "
        f"**{a['collapses_json_crosscheck']['indices_match']}**",
        f"- bt funnel SHADOW_PENDING expected 6; probe={a['bt_summary_crosscheck']['probe_n_SHADOW_PENDING']}; "
        f"restores={a['bt_summary_crosscheck']['probe_n_restore']}",
        "",
        "## Authority",
        "",
        a["authority_disclaimer"]["note"],
    ]
    return "\n".join(lines) + "\n"


def _render_note(a: dict) -> str:
    f = a["funnel"]
    r = f["rates"]
    ttl_vals = [x["ttl_remaining_at_restore"] for x in a["known_6_restores"]]
    near1 = sum(1 for t in ttl_vals if t == 1)
    near4 = sum(1 for t in ttl_vals if t == 4)
    return "\n".join([
        "# Phase-1 SHADOW memory subsystem note",
        "",
        "**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · no Case reopen · no object widening · no freeze work · no OB/PDH/liquidity expansion",
        "",
        f"**Corpus:** Phase-1 XAUUSD · csv sha256 `{a['csv_sha256'][:16]}…` · config `{a['config_version']}`",
        f"**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_subsystem.json`",
        "",
        "## Locked object",
        "",
        a["locked_object"],
        "",
        "## Q1 — pending_ttl = 4",
        "",
        a["ttl_code_cites"]["why_4"],
        "",
        "Primary cites:",
        f"- `{a['ttl_code_cites']['CRTConfig_default']['file']}:{a['ttl_code_cites']['CRTConfig_default']['line']}`",
        f"- `{a['ttl_code_cites']['YAML_lifecycle']['file']}:{a['ttl_code_cites']['YAML_lifecycle']['line']}`",
        f"- `{a['ttl_code_cites']['prod_config']['file']}` → `{a['ttl_code_cites']['prod_config']['path']}=4`",
        f"- assignment `{a['ttl_code_cites']['assignment_on_create']['file']}:{a['ttl_code_cites']['assignment_on_create']['line']}` on HTF-DISPLACEMENT reset create gate (`crt_engine_v2.py:1892-1915`)",
        "",
        "## Funnel table",
        "",
        "| Stage | N |",
        "|---|---:|",
        f"| Created | {f['n_memories_created']} |",
        f"| Expire TTL before confirming sweep | {f['n_expire_ttl_before_confirming_sweep']} |",
        f"| Cleared non-HTF reset | {f['n_cleared_non_htf_reset']} |",
        f"| SHADOW_PENDING | {f['n_enter_SHADOW_PENDING']} |",
        f"| Restore → EXPANSION | {f['n_restore_try_shadow_pending_to_expansion_ok']} |",
        "",
        f"- P(SHADOW_PENDING \\| created) = **{r['P_SHADOW_PENDING_given_memory_created']}**",
        f"- P(restore \\| SHADOW_PENDING) = **{r['P_restore_given_SHADOW_PENDING']}**",
        f"- P(expire \\| created) = **{r['P_expire_ttl_given_memory_created']}**",
        "",
        "## Known-6 TTL-at-restore",
        "",
        f"TTL remaining values: `{ttl_vals}` · near TTL=1: **{near1}/6** · near TTL=4: **{near4}/6** · distribution `{a['ttl_at_restore_distribution']}`",
        "",
        "See `memory_subsystem.md` for per-row formed_idx → collapse_idx distances.",
        "",
        "## Failed resumes near expiry",
        "",
        f"try_shadow false={len(a['failed_resume_attempts']['try_shadow_false'])}; "
        f"SHADOW_LEAK={len(a['failed_resume_attempts']['shadow_leak'])}.",
        "",
        "## Blockers",
        "",
        "- Object scarcity unchanged: restores n=6 ≪ 30 (power floor from prior notes).",
        "- Non-HTF clears and TTL expires both terminate memory without SHADOW_PENDING; they are separate exit channels in the funnel.",
        "- Measure-only monkeypatch; production semantics unchanged.",
        "",
    ]) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", default=_DEFAULT_CSV)
    p.add_argument("--instrument", default=_DEFAULT_INSTRUMENT)
    p.add_argument(
        "--output",
        default=str(
            _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "memory_subsystem_probe_run"
        ),
    )
    args = p.parse_args()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.output).mkdir(parents=True, exist_ok=True)
    _NOTE_MD.parent.mkdir(parents=True, exist_ok=True)

    # reset class-level counters
    for attr, val in list(_Probe.__dict__.items()):
        if attr.startswith("_") and not attr.startswith("__"):
            continue
        if callable(val):
            continue
        if isinstance(val, list):
            setattr(_Probe, attr, [])
        elif isinstance(val, int):
            setattr(_Probe, attr, 0)
        elif val is None or attr == "open_memory":
            setattr(_Probe, attr, None)

    restore = _install_patches()
    try:
        crt_cfg = load_prod_config_from_registry(PROD_VERSION, args.instrument)
        cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
        cfg.instrument = args.instrument
        cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(args.instrument, 0.0001)
        loader = CandleLoader(args.csv, args.instrument)
        runner = BacktestRunner(
            cfg, csv_path=args.csv,
            overrides={"diagnostic": "phase1_shadow_memory_subsystem_probe"},
        )
        runner.run(loader.stream(), loader.count(), args.output)
    finally:
        restore()

    artifact = _build_artifact(args.csv, args.instrument, args.output)
    _ARTIFACT_JSON.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")
    md = _render_md(artifact)
    _ARTIFACT_MD.write_text(md, encoding="utf-8")
    note = _render_note(artifact)
    _NOTE_MD.write_text(note, encoding="utf-8")

    safe_print(md)
    safe_print(f"\nWrote: {_ARTIFACT_JSON}")
    safe_print(f"Wrote: {_ARTIFACT_MD}")
    safe_print(f"Wrote: {_NOTE_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
