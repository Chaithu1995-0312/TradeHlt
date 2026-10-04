"""opportunity_bands.py — Phase-1 arithmetic derivation over one SEM-037 kernel row.

Computes the layered-outcome-ontology fields (plan: docs/implementation_plan/
i-have-everything-i-crispy-dawn.md) for one row of `opportunities.jsonl`:
`exit_mechanism`, `trail_state`, `risk_distance`, `mfe_r`/`mae_r`, `exit_bounded_capture`
+ its state/band, `rr_band`. Pure arithmetic on already-stored fields — no re-simulation
of the SEM-037 kernel, no re-derivation from OHLC. Governed by CC-OPP-BAND-RESTATEMENT
(CAN) / CC-OPP-BAND-NOT-ECONOMIC (CANNOT), `docs/governance/jsonl_claim_catalog.yaml`.

STRUCTURAL vs BEHAVIORAL (CLAUDE.md 6.5): TRAIL_MULT below is not a new threshold this
module invents — it is opportunity_scanner.py's own `_simulate(trail_mult: float = 0.5)`
kernel parameter (SEM-037 `formula`), named here so it is traceable rather than a bare
literal. Every genuinely BEHAVIORAL threshold (the band edges, the capture-guard
epsilons) lives in configs/research/band_tables.json and is read through
`research.band_tables`, never hardcoded here.

FORBIDDEN AS CANONICAL (mirrors src/research/episodes/protocol.py's own tuple): this
module reads `outcome`/`rr_achieved`/`mfe`/`mae` from the F-022 stream, which is exactly
what CC-F022-CONTAMINATED refuses an ECONOMIC reading of — this module computes
NUMBER-WORD restatements only (CC-OPP-BAND-RESTATEMENT) and asserts nothing about
profitability, win rate, or trade quality.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research.band_tables import classify, classify_capture, load_band_table

#: opportunity_scanner.py:55 `_simulate(..., trail_mult: float = 0.5)` — SEM-037's own
#: documented kernel parameter, not a new threshold. The arming identity this module
#: relies on (mfe_r >= TRAIL_MULT <=> the trail activated) was verified to machine
#: precision on the reference run: max unarmed mfe_r = 0.499923, min armed = 0.500000.
TRAIL_MULT = 0.5

#: The only three outcome literals opportunity_scanner.py emits (opportunity_scanner.py:
#: 111, 120, 130, 144; counter seeded at :188). A fourth would mean the source stream's
#: contract changed and this module's derivation is no longer known to be exact.
_KNOWN_OUTCOMES = frozenset({"TP_HIT", "SL_HIT", "TIMEOUT"})

_EXIT_MECHANISM_BASIS = "EXIT_TRUNCATED"  # SEM-020 v2 required input; declared once, see the header
_BAND_TABLE_ID = "BT-RR-ECON-V1"
_CAPTURE_TABLE_ID = "BT-CAPTURE-V1"


class OpportunityBandsError(ValueError):
    """A source row violates the SEM-037 kernel contract this module derives from.

    Fail closed (CLAUDE.md 6.5 no-silent-defaults rule) — never guess a label for a
    row whose outcome or rr_achieved falls outside what SEM-037 documents.
    """


@dataclass(frozen=True)
class DerivedBands:
    """One row's Phase-1 derived fields. Every field here is CC-OPP-BAND-RESTATEMENT
    admissible; none of them may be read as CC-OPP-BAND-NOT-ECONOMIC's forbidden claim."""

    exit_mechanism: str
    trail_state: str
    risk_distance: float
    mfe_r: float
    mae_r: float
    exit_bounded_capture: float | None
    capture_state: str
    rr_band: str


def _exit_mechanism(outcome: str, rr_achieved: float) -> str:
    if outcome == "TP_HIT":
        return "TP_EXIT"
    if outcome == "TIMEOUT":
        return "TIMEOUT_EXIT"
    if outcome == "SL_HIT":
        if abs(rr_achieved + 1.0) < 1e-9:
            return "ORIGINAL_STOP_EXIT"
        if rr_achieved > -1.0:
            return "TRAIL_STOP_EXIT"
        # rr_achieved < -1.0 on an SL_HIT means SEM-016 adverse fill is in play, which
        # SEM-037's own arming identity does not cover (its validation_rules say so
        # explicitly) — fail closed rather than silently mislabel it ORIGINAL_STOP_EXIT.
        raise OpportunityBandsError(
            f"SL_HIT with rr_achieved={rr_achieved!r} < -1.0 — outside the SEM-037 "
            "never-armed atom; this row was not produced by the documented kernel "
            "(or an adverse-fill model is active) and cannot be classified as exact.")
    raise OpportunityBandsError(f"unknown outcome literal {outcome!r} (known: {sorted(_KNOWN_OUTCOMES)})")


def derive_row_bands(
    row: dict[str, Any],
    *,
    econ_table: dict[str, Any] | None = None,
    capture_table: dict[str, Any] | None = None,
) -> DerivedBands:
    """Derive every Phase-1 field for one opportunities.jsonl data row (not the
    run_header line). Pure function: same row -> same DerivedBands, always.

    econ_table / capture_table may be pre-loaded by the caller (e.g. a script
    processing 94k rows should load once, not once per row); defaults load them.
    """
    econ = econ_table if econ_table is not None else load_band_table(_BAND_TABLE_ID)
    cap = capture_table if capture_table is not None else load_band_table(_CAPTURE_TABLE_ID)

    outcome = row["outcome"]
    if outcome not in _KNOWN_OUTCOMES:
        raise OpportunityBandsError(f"unknown outcome literal {outcome!r} (known: {sorted(_KNOWN_OUTCOMES)})")
    rr = float(row["rr_achieved"])
    entry, sl = float(row["entry"]), float(row["sl"])
    risk_distance = abs(entry - sl)
    if risk_distance <= 0:
        raise OpportunityBandsError(f"non-positive risk_distance ({risk_distance!r}) — entry={entry!r} sl={sl!r}")

    mfe_r = float(row["mfe"]) / risk_distance
    mae_r = float(row["mae"]) / risk_distance

    exit_mechanism = _exit_mechanism(outcome, rr)
    trail_state = "TRAIL_ARMED" if mfe_r >= TRAIL_MULT else "TRAIL_NEVER_ARMED"

    capture_state, capture_value = classify_capture(mfe_r, rr, cap)
    rr_band = classify(rr, econ)

    return DerivedBands(
        exit_mechanism=exit_mechanism,
        trail_state=trail_state,
        risk_distance=risk_distance,
        mfe_r=round(mfe_r, 6),
        mae_r=round(mae_r, 6),
        exit_bounded_capture=None if capture_value is None else round(capture_value, 6),
        capture_state=capture_state,
        rr_band=rr_band,
    )


def sidecar_header(*, source_path: str, source_run_id: str, source_trace_id: str) -> dict[str, Any]:
    """The provenance header line every sidecar file must lead with (F-079/F-083/F-085's
    silent-gap lesson: never let a derived artifact be ambiguous about what produced it,
    under what claim authority, and against which band-table version)."""
    return {
        "type": "sidecar_header",
        "generator": "scripts/research/derive_opportunity_rr_bands.py",
        "source_path": source_path,
        "source_run_id": source_run_id,
        "source_trace_id": source_trace_id,
        "band_table_id": _BAND_TABLE_ID,
        "capture_table_id": _CAPTURE_TABLE_ID,
        "mfe_basis": _EXIT_MECHANISM_BASIS,
        "cost_basis": "NONE",
        "governed_by_cc": "CC-OPP-BAND-RESTATEMENT",
        "refused_by_cc": "CC-OPP-BAND-NOT-ECONOMIC",
        "catalog_stream_status": "CONTAMINATED",
        "meaning_authority": "INVENTORY_NOT_MARKET",
    }
