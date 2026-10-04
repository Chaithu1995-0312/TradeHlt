"""Grain catalog for the XAUUSD parquet evidence layer.

JSONL remains the system of record (`utils.parquet_store`). Parquet is a derived
projection. This module names what each projection *is*, what grain it sits on,
and which joins are legal. It does not load data and does not train anything.

SCOPE — one program's 4 fixed exemplars, not a general join registry.
-----------------------------------------------------------------------
`SURFACES` pins each id to ONE canonical jsonl path (this evidence program's specific
94k-bar opportunities/clean_labels ledger + one specific `run_20260822_162108_XAUUSD` spine
run). That model does not fit `crt_construction` / `bar_structure`
(`src/runtime/crt_construction_trace.py` / `bar_structure_snapshot.py`): they are per-RUN
trace sidecars with many instances on disk and no canonical exemplar — pinning one path here
would misrepresent it as "the" file, the exact category error `scripts/analysis/query_trace.py
--run-dir` exists to prevent. Their join legality is enforced there instead, by
`query_trace.assert_view_lineage` — a stronger, per-run check read from the LIVE `run_id` /
`corpus_sha256` columns in the opened views, not a static allow-list. Do not add them to
`LEGAL_JOINS` for that reason; `assert_join` is scoped to this module's 4 objects only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet

_REPO = Path(__file__).resolve().parents[3]


class IllegalJoinError(ValueError):
    """Raised when two surfaces do not share a grain and must not be 1:1 joined."""


@dataclass(frozen=True)
class Surface:
    id: str
    role: str
    grain: str
    jsonl: Path
    meaning: str
    identity_keys: tuple[str, ...]
    authority: str
    notes: tuple[str, ...]


# Default XAUUSD projections (the four files named by the user). Override in DriverConfig.
SURFACES: dict[str, Surface] = {
    "opportunities": Surface(
        id="opportunities",
        role="decision_ledger",
        grain="bar_x_direction",
        jsonl=_REPO / "logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl",
        meaning=(
            "Market + structural + behavioral state, trade geometry, and a STREAM "
            "realized outcome. This is a decision ledger, not a CRT TRADE_OPENED book. "
            "On the current file, n equals unique timestamps × 2 sides."
        ),
        identity_keys=("timestamp", "instrument", "direction"),
        authority="GEOMETRY_AND_STATE_ONLY — stream outcome is F-022 contaminated",
        notes=(
            "Do not treat `outcome` / `rr_achieved` as governing y.",
            "Not the later spine run (events/telemetry).",
        ),
    ),
    "clean_labels": Surface(
        id="clean_labels",
        role="outcome_surface",
        grain="bar_x_direction",
        jsonl=_REPO / "results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.jsonl",
        meaning=(
            "Same opportunity identity, re-derived path labels (forward_walk "
            "intrabar_fixed, protocol TN_ENV_CLEAN_L2), TP1/TP2, MFE/MAE, timing, "
            "feature vector. This is the governing outcome surface for this grain."
        ),
        identity_keys=("decision_ts", "instrument", "side"),
        authority="GOVERNING_Y — stream fields stay diagnostics only",
        notes=(
            "y_R_net uses protocol COST_BPS=12 (F-082: punitive vs measured XAUUSD broker).",
            "PIT_UNCLEAN_STORED_FEATURES (F-051).",
            "tp1_reward_mult is a frozen 2R geometry on this corpus.",
        ),
    ),
    "events": Surface(
        id="events",
        role="state_machine_journal",
        grain="crt_spine_run",
        jsonl=(
            _REPO / "results/research/_spine_entries/XAUUSD__v2_multi_2026_04"
            / "run_20260822_162108_XAUUSD/XAUUSD_events.jsonl"
        ),
        meaning="CRT state transitions and event history for one BacktestRunner run.",
        identity_keys=("timestamp", "candle_index", "event"),
        authority="PROCESS_JOURNAL — not a trade ledger",
        notes=(
            "Different grain from the 94k bar×direction ledger.",
            "TRADE_OPENED count on this run is a process fact, not an economic sample.",
        ),
    ),
    "telemetry": Surface(
        id="telemetry",
        role="decision_flight_recorder",
        grain="crt_spine_run",
        jsonl=(
            _REPO / "results/research/_spine_entries/XAUUSD__v2_multi_2026_04"
            / "run_20260822_162108_XAUUSD/XAUUSD_crt_telemetry.jsonl"
        ),
        meaning="Candidate lifecycle diagnostics (death, reject, age, score distance).",
        identity_keys=("kind", "candle_index", "timestamp"),
        authority="PROCESS_DIAGNOSTIC — not an outcome surface",
        notes=(
            "Same spine run as events. Not 1:1 with opportunities/clean_labels.",
        ),
    ),
}


LEGAL_JOINS: FrozenSet[FrozenSet[str]] = frozenset({
    frozenset({"opportunities", "clean_labels"}),
    frozenset({"events", "telemetry"}),
})


OHLC_LEVEL_FEATURES = frozenset({
    "open", "high", "low", "close", "volume",
    "ema_fast", "ema_slow", "swing_high", "swing_low",
})

# Known representational defects — still enumerated, never used as skill evidence.
CONTAMINATED_FEATURES = {
    "momentum_score": "F-061/F-064 dimensional mix; |tanh| saturates on XAUUSD",
    "ema_spread": "F-061/F-064 dimensional mix vs atr_relative identity",
}


def assert_join(*surface_ids: str) -> None:
    """Refuse a 1:1 join that would invent a shared lifecycle the files do not have."""
    key = frozenset(surface_ids)
    if len(key) < 2:
        return
    if key not in LEGAL_JOINS:
        roles = ", ".join(
            f"{i}={SURFACES[i].grain}" if i in SURFACES else i for i in sorted(key)
        )
        raise IllegalJoinError(
            f"illegal evidence join {{{', '.join(sorted(key))}}} ({roles}). "
            "The 94k bar×direction ledger does not share identity with the later "
            "CRT spine journal. Query each grain separately."
        )


def identity_tuple(row: dict, surface_id: str) -> tuple:
    surf = SURFACES[surface_id]
    if surface_id == "opportunities":
        side = str(row.get("direction") or row.get("side") or "").lower()
        ts = str(row.get("timestamp") or row.get("decision_ts") or "")
        inst = str(row.get("instrument") or "")
        return (ts, inst, side)
    if surface_id == "clean_labels":
        side = str(row.get("side") or row.get("direction") or "").lower()
        ts = str(row.get("decision_ts") or row.get("timestamp") or "")
        inst = str(row.get("instrument") or "")
        return (ts, inst, side)
    return tuple(str(row.get(k) or "") for k in surf.identity_keys)
