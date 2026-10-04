# Plan — CRT SM Closure Acknowledgement (read-only turn)

## Context

The user issued a **closure directive**, not an implementation request: read
`docs/handover/CRT_SM_INFRA_CONTEXT_PACKET.md` (r3 · `CP-CRT-SM-INFRA-2026-08-06`), accept the CRT
state machine / thresholds / feature-formation rules as **frozen**, acknowledge the Config
Construction Protocol P0–P3 as shipped, and return a ≤200-word confirmation. Explicit constraint:
**propose no changes** to the state machine, thresholds, or construction protocol.

No code or config change is therefore in scope. The only write this turn requires is the §6
mandatory SESSION LOG entry to `assistant_project.md` (blocked by plan mode).

## Verification performed (read-only)

| Claim | Verdict | Evidence |
|---|---|---|
| Packet r3 canonical, ACTIVE_VERSION pinned | CONFIRMED | `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04` |
| 39-dim vector; FM-027/028 not vector slots | CONFIRMED | `len(CANONICAL_FEATURES)==39`; `displacement_retrace`/`displacement_atr_ratio` absent |
| P0 protocol frozen | CONFIRMED | `docs/governance/CRT_CONFIG_CONSTRUCTION_PROTOCOL.md` (frozen 2026-08-06) |
| P1 provenance stamps | CONFIRMED *with precision* | `src/config_layer/crt_config_provenance.py` — **side registry keyed by `id(cfg)`**, not a `CRTConfig` field; unstamped ⇒ `UNKNOWN` |
| P2 BacktestRunner fail-closed | CONFIRMED | `assert_product_crt_config` at `src/runtime/backtest_v2.py:1753`; escape hatch `allow_router_crt_config` at `:181` |
| **P3 CI guardrail + `crt_config_baseline.json`** | **NOT FOUND** | see TruthConflict below |
| P2.5 live-hook dict bypass | CONFIRMED | `live_engine_hook.py:889` `engine_config.get("crt_engine", {})` — raw dict, no stamp, no product gate |

## TruthConflict (§6.2 rule 3 — surfaced, not resolved)

- **Source A (user directive):** P3 CI guardrail runs a nightly census; new `ROUTER_BASE` call sites
  fail PRs unless listed in `crt_config_baseline.json`.
- **Source B (repository):**
  - No `crt_config_baseline.json` exists (filesystem search + content grep both empty).
  - Neither CI workflow invokes the census — `.github/workflows/governance.yml` runs only
    `check_governance_invariants.py --all`; `erp-test-harness.yml` runs a path-scoped pytest subset.
  - `check_governance_invariants.py` GREEN_FLOOR contains no reference to
    `tests/test_crt_config_provenance.py` or the census.
  - `scripts/governance/crt_config_construction_census.py` self-declares `"phase": "P1_OBSERVE"` and
    *"Does not fail-closed."*
  - The authoritative protocol §7 lists **P3 as "Optional"**, not shipped.
- **Impact:** P0–P2 closure stands unchanged. The claim that a *new* `ROUTER_BASE` call site is
  mechanically blocked is not currently true — enforcement is per-call-site at the BacktestRunner
  boundary (P2), with no repo-wide ratchet.
- **Recommendation:** none proposed (directive forbids protocol changes). User decision only:
  either correct the P3 status in the record, or authorize P3 in a separate turn.

## Deliverable

1. The ≤200-word closure confirmation (already emitted in-chat).
2. Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (§6 mandate) — **the only file
   write**, recording closure acceptance + the P3 TruthConflict.

## Verification

`python -m pytest tests/test_crt_config_provenance.py -q` (read-only re-confirmation of P1/P2
floors; not required for the log append).
