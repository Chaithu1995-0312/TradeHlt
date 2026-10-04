> Created: 2026-06-01 · Updated: 2026-06-01 · Milestone: Trd-M6 (entry-gate / pre-work)

# Trd-M6 stays downstream — BNBUSDT instrument-scoped session promotion

## Context

**Why this exists.** Trd-M6 (Scenario-Aware Decisioning) is the first *capability* milestone on the
trading track; Trd-M0–M5 (all infrastructure) are complete as of 2026-06-01. Trd-M6 was **PARKED**
on 2026-06-01 ([roadmap.md §3](docs/architecture/roadmap.md), lines 73–125). Its entry gate needs
**both** halves: (1) infra — *done*; (2) an empirical-throughput floor — *partial*.

The BNBUSDT phase work (Phase 0→6e) settled the empirical question: the binding throughput
constraint is **RETEST→EXECUTION (11.2% approval)**, and the dominant killer there is the **SESSION
filter**, not the score threshold (134/135 retests pass scoring). Expanding sessions
(`+ASIA +OFF_SESSION`, "V3") lifts BNBUSDT **15→35 trades (+133%) with quality improved**
(PF 1.79→2.54, ROI +4.91%→+20.59%, DD flat). The cheap config levers are now **exhausted** for
BNBUSDT (Phase 6e re-confirmed `shadow_advisory_only=True`; flipping it collapses PF).

**The reframe that sets the sequence:** session expansion is **instrument-specific** — strongly
positive for BNBUSDT, rehabilitates SOLUSDT, **degrades ETHUSDT**, BTCUSDT unprofitable either way.
So (a) a *global* session change is wrong, and (b) the recovered BNBUSDT trades make Trd-M6
**optimization, not necessity**. The standing decision: **ship instrument-scoped session expansion
(cheap) first; Trd-M6 stays downstream/parked.**

**The feasibility gap this plan closes.** There is currently **no per-instrument session mechanism**.
`allowed_sessions` (engine_runner §) and `session_windows` are **global**, merged into every
`CRTConfig` at [production_config.py:255-266](src/config_layer/production_config.py). The
`per_instrument` key in the config only carries validation-summary scores, not session overrides. So
"instrument-scoped session expansion" requires a small additive enabling change before any promotion
can be both correct (BNBUSDT-only) and safe (ETH/BTC untouched).

**Intended outcome:** (A) the "Trd-M6 stays downstream" decision is codified as an unambiguous
entry-gate record, and (B) the BNBUSDT session expansion ships through the real
`ConfigValidator → PromotionManager` gate, instrument-scoped, with ETH/BTC provably unchanged.

---

## Part A — Codify the park (doc-only, additive)

Make the downstream decision and its precondition chain explicit so no future session re-opens it.

1. **roadmap.md §3 entry-gate status** — add a dated line stating the operative decision in one place:
   *"Trd-M6 stays downstream. Precondition before un-parking = the instrument-scoped session
   promotions (BNBUSDT #1, SOLUSDT #2) + Part 4A per-instrument OOS confirmation ship first. 35 @
   PF 2.54 clears the *spirit* of the throughput floor for BNBUSDT; literal ≥40 needs upstream
   detection supply, which is **not** Trd-M6."* Supersede, don't delete prior text.

2. **[user-progress-registry.md](docs/governance/user-progress-registry.md)** — set the `Trd-M6` row
   `Progress = BLOCKED`, `Blocked By = "instrument-scoped session promotion (#1/#2) + Part 4A OOS"`,
   `Next Action = "ship BNBUSDT session promotion"`, bump `Last Reviewed`.

3. **Topic sync (§6.1)** — if a `docs/topics/` doc owns the session-filter or governance-promotion
   concept, bump its `Updated:` and note the instrument-scoped override in its Discussion block.

4. **SESSION LOG (§6)** + **MEMORY** — append the entry-gate decision; add/update a memory pointer
   (the `project_phase6*` chain) recording "Trd-M6 downstream; #1 = BNBUSDT session promotion."

No code changes in Part A. This is the "park-spec" half of the deliverable.

---

## Part B — Executable BNBUSDT sequencing (the pre-work that precedes Trd-M6)

### B1 — Enabling change: per-instrument session override (additive, config-driven)

The one small code change that makes instrument-scoped promotion possible. Follows the existing
no-magic-numbers / config-section convention.

- **Config:** add an optional `engine_runner.allowed_sessions_overrides` map (and optional
  `session_windows_overrides`) keyed by instrument, e.g.
  `"allowed_sessions_overrides": { "BNBUSDT": ["london","new_york","overlap","asia","off_session"] }`.
  Absent key ⇒ instrument falls back to the global `allowed_sessions` (zero behavior change for
  ETH/BTC/EUR/etc.).
- **Resolver:** in the CRT config-build path at
  [production_config.py:255-266](src/config_layer/production_config.py), after pulling the global
  `allowed_sessions`, look up `allowed_sessions_overrides.get(instrument)` (the `instrument` arg is
  already in scope — it is passed straight into `ConfigBuilder.build(instrument, ...)` at line 266)
  and, when present, use it instead. Apply the same normalization already used
  (`str(s).upper().replace("_", "")`). Mirror for `session_windows_overrides` via `_coerce_crt_engine`.
- **Consumers unaffected:** `CRTEngineV2` and `backtest_v2._session()`
  ([backtest_v2.py:2304-2309](src/runtime/backtest_v2.py)) keep reading the resolved
  `session_windows` / `allowed_sessions` off `CRTConfig` — no call-site change.
- **Tests:** add a unit test asserting (i) override applied for the named instrument, (ii) global
  fallback unchanged for an instrument with no override key, (iii) normalization parity.

### B2 — Config selection sweep (V0→V4; choice deferred to here)

Use the existing measure-only harness `scripts/analysis/session_sweep.py` (fixed seed) to re-run
V0 (baseline hard-gate) → V4 for BNBUSDT under the override mechanism and **pick the session set at
execution time**. V0 must reproduce the baseline exactly (15 trades / PF 1.7929 / ROI +4.91%) as a
hard gate before trusting any expansion row. Record the chosen set + table in a dated
`docs/analysis/` note. (Empirical front-runner is V3 = all sessions: 35 trades / PF 2.54; V1 =
+ASIA only: 23 / PF 2.54 is the conservative alternative — the operator selects here.)

### B3 — Validate through the real gate (`ConfigValidator`)

Run `python src/config_layer/config_validator.py validate-prod --data-dir data/` (or
`promotion_manager … validate` with `--instruments`) on the candidate config carrying the BNBUSDT
override. **Two must-pass checks:** (1) `ValidationReport.decision == "APPROVE"` (hard gates: ≥10
trades, ≤35% DD, fitness ≥0.15); (2) a **non-regression proof for ETH/BTC** — their per-instrument
metrics are byte-for-byte unchanged vs the current prod config, demonstrating the override is truly
scoped. If ETH/BTC drift at all, B1 has a leak — stop and fix before promoting.

### B4 — Promote (governed)

Promote via `PromotionManager` to a new version (e.g. `v2_bnb_sessions_2026_06`), then re-hash:
`python scripts/maintenance/_compute_hash.py`. Promotion fails unless B3 returned APPROVE. Confirms:
SHA-256 hash, `configs/promotion_log.jsonl` PROMOTED line, archived prior version. This is the
"#1 BNBUSDT session promotion" the Master Sequencing names.

### B5 — Downstream queue (named, not executed here)

After #1 ships: **#2** SOLUSDT session validation + promotion (same B1–B4 path, its own override
key); **#3** Part 4A per-instrument OOS confirmation (SOL/ETH/BTC) + ReplayMemory schema repair;
**#4** master decision on instrument-scoped vs any global change. **Trd-M6 is downstream of all of
these** and stays parked until they clear.

---

## Critical files

| File | Role in this plan |
| --- | --- |
| [docs/architecture/roadmap.md](docs/architecture/roadmap.md) §3 | A1 — entry-gate decision record |
| [docs/governance/user-progress-registry.md](docs/governance/user-progress-registry.md) | A2 — Trd-M6 row → BLOCKED |
| [src/config_layer/production_config.py:255-295](src/config_layer/production_config.py) | B1 — override resolver (the one code edit point) |
| [configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json) engine_runner § | B1 — `allowed_sessions_overrides` key |
| [src/runtime/backtest_v2.py:2304-2309](src/runtime/backtest_v2.py) | B1 — consumer (read-only, confirm no change) |
| `scripts/analysis/session_sweep.py` | B2 — existing measure-only sweep harness (reuse) |
| [src/config_layer/config_validator.py](src/config_layer/config_validator.py) | B3 — mandatory pre-promotion gate |
| [src/governance/promotion_manager.py:264](src/governance/promotion_manager.py) (`promote_direct`) | B4 — governed promotion |

## Verification (end-to-end)

1. **B1 unit:** `pytest tests/ -k session_override` — override-applied / global-fallback / normalization.
2. **Regression suite:** `pytest` (expect the established 1211-pass baseline; no new failures).
3. **B2 determinism gate:** session_sweep V0 row == baseline (15 / PF 1.7929 / ROI +4.91%) bit-exact.
4. **B3 scoping proof:** ConfigValidator report shows APPROVE **and** ETH/BTC per-instrument metrics
   identical to current prod (the instrument-scoping correctness test).
5. **B4 governance:** `promotion_log.jsonl` shows a PROMOTED line for the new version; config hash
   recomputed; prior version archived.
6. **Five Governance Questions** scored for the promotion; SESSION LOG appended (§6).

## Out of scope (explicit)

- Any Trd-M6 scenario logic (the consumer at `UltronRiskGate` / in-trade management, the
  `market_state_cluster_engine.py` prior) — **parked**, gated behind B5.
- Global session changes (degrades ETHUSDT) — forbidden; overrides are per-instrument only.
- Flipping `shadow_advisory_only` (Phase 6e re-confirmed it stays `True`).
- Chasing the literal ≥40-trade floor (needs upstream detection supply, not in this plan).
