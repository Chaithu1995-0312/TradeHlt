# Close the three real gaps in the Monthly TV ↔ Active Production comparison

## Context

The monthly comparison report **already exists** and is registered:
[reports/monthly_tv_vs_active_production_semantic_comparison.md](reports/monthly_tv_vs_active_production_semantic_comparison.md)
+ `.json` twin (2026-08-16), cited as Notes in F-074/F-075/F-076/F-077/F-078. It carries the
11-dimension table with verdicts and §6.8 tags, and its own lines 7–10 already disclaim the
Jul 15/20 episode work.

Three premise corrections verified against disk before planning (§6.2 rule 3 — surfaced, not
silently adopted):

| Claim | Verified truth |
|---|---|
| "Monthly report still missing" | Exists, 12.9 KB, registered in 5 findings |
| "Episode comparison used `v2_multi_2026_04` / schema v4.0 / 39 features" | `configs/production/ACTIVE_VERSION` = `v2_htfcrt_2026_08`; that string appears in **zero** TV/forensic artifacts. Schema is **v5.0 / 48** (`feature_schema.py:141,292`, F-076) |
| "Comparison is the missing deliverable" | The report is done; its *inputs* are incomplete — see below |

What is actually missing, and what this plan closes:

1. **TV coverage is 5 of ~22 trading days.** `01_h4_july_macro` (Jul 1→Aug 7) and
   `02_h4_july_setup` (Jul 10→Aug 1) — the only month-spanning shots — are defined in
   `shot_plan.json` but have no PNG and no sidecar. Jul 7–14 and Aug 1–6 have zero TV capture.
2. **H4 shots can never reconcile.** `capture_tv.py:391` gates the OHLC diff on
   `interval == "15"` because `engine_data.diff_table:288` hardcodes `cursor += timedelta(minutes=15)`.
   Both H4 sidecars carry `NOT_APPLICABLE` structurally, so any *new* macro H4 shot would too.
3. **SMC row 8 is presence-only.** The report states plainly that a human-eye check that a
   detected order block / FVG matches what is visible was not performed.

Outcome: the report's TradingView side becomes genuinely month-wide, H4 shots carry real
reconciliation verdicts, and row 8 upgrades from `TEST/CONTRACT GAP` to a verified row — or the
gaps are recorded as measured failures. No production behavior changes.

---

## Pre-registration (E-001 ritual — fix verdict rules BEFORE running)

Written into the manifest before any capture, so a result cannot be reverse-fitted:

- **H4 grid alignment is MEASURED, never assumed.** TradingView's `OANDA:XAUUSD` H4 bars are
  exchange-session anchored; the engine's are calendar-true broker-time buckets, and the resolved
  broker offset is **+3** (odd), so broker 00:00/04:00/08:00 map to UTC 21:00/01:00/05:00. The
  grids may not align 1:1. Candidate anchors are scored by actual OHLC agreement exactly as
  `resolve_offset` does, and **fail closed**: if no anchor is decisive, the sidecar keeps
  `status: NOT_APPLICABLE` with `reason: H4_GRID_UNRESOLVED`. An unresolved grid is a recorded
  absence, not a pass.
- **MATCH threshold is inherited, not re-chosen:** `MATCH_TOLERANCE = 3.0`,
  `DECISIVE_RATIO = 5.0` (`engine_data.py:24-25`). H4 bars aggregate 16 M15 bars, so absolute
  error scales — the H4 tolerance is stated as `16 × MATCH_TOLERANCE` **or** the tolerance is
  applied to the *mean* per-child error, decided and written down before the first H4 diff runs,
  never after seeing the number.
- **Corpus boundary is declared up front:** `data/XAUUSD_M15.csv` starts **2026-07-07 01:00**.
  `h4_july_macro` requests Jul 1 → Aug 7, so **Jul 1–6 has no engine bars at all**. That shot's
  reconciliation can cover Jul 7 onward only; the pre-corpus span is reported as
  `NO_ENGINE_BAR`, never silently dropped from the denominator.
- **SMC verification separates two claims:** a *mechanical* check (verifiable — e.g. the
  `pdh_distance` reference level equals the max of the prior day's TV bars in the sidecar) and a
  *visual* check (human judgment). Mechanical failures are defects; visual mismatch alone is
  `INSUFFICIENT EVIDENCE` pending user adjudication, not a defect.
- **Verdict vocabulary is the closed §6.8 set.** No row says "bug" without naming a contract.

`TASK_CLASS = OBSERVATION_ONLY` (`docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md:59-73`).

---

## Workstream A — H4 reconciliation (do this FIRST)

Ordered first deliberately: without it, every new H4 macro shot from Workstream B is captured
permanently unreconcilable, and re-capturing later is wasted browser work.

**Constraint to honor:** `engine_data.py:103-109` explicitly forbids re-implementing HTF
aggregation inside this tool ("duplicating HTF aggregation here would be a second, unverified
reimplementation of the same geometry the codebase's own doctrine warns against"). So do not
write new aggregation math — reuse the canonical builder.

1. **New `tools/tv_forensic/htf_bars.py`** — the only file that bridges the tool to `src/`.
   - Imports `ParentCandleBuilder` from [src/features/parent_candle.py](src/features/parent_candle.py:62)
     and `period_key`/`period_start` from `features.calendar_periods`. Uses the `sys.path`
     bootstrap pattern already in [scripts/research/htf_parent_telemetry_extract.py](scripts/research/htf_parent_telemetry_extract.py).
   - `aggregate_engine_bars(engine_bars, rule="H4") -> dict[datetime, Bar]`: feeds the M15
     `Bar`s through `ParentCandleBuilder` in chronological order, converts each closed parent
     back to `engine_data.Bar`. No-lookahead is inherited from the builder (only closed periods
     are ever exposed, `parent_candle.py:99-105`).
   - `resolve_htf_anchor(...)`: scores candidate grid anchors by OHLC agreement against the
     sidecar's TV bars, returning a decisive/not-decisive result mirroring
     [OffsetResult.decisive](tools/tv_forensic/engine_data.py:51) — including its D-2 anchor-floor
     rule (winner must match every usable anchor).
   - Optional-import guard: if `src/` is unimportable, callers fall back to today's
     `NOT_APPLICABLE` rather than crashing (matches the tool's existing Pillow/Playwright pattern).

2. **Generalize `engine_data.diff_table`** — add `step_minutes: int = 15`, replacing the
   hardcoded increment at `:288`. Default preserves current behavior exactly.

3. **Rewire `capture_tv.py:391-426`** into three branches: M15 → unchanged; supported HTF rule
   with a decisive anchor → real `OK`/`DIVERGENT` status; anything else → `NOT_APPLICABLE` with
   a specific reason (`H4_GRID_UNRESOLVED`, `SRC_UNAVAILABLE`, or the existing interval reason).

4. **Byte-identity gate (non-negotiable).** Extend
   `tests/test_tv_forensic_smoke.py::test_engine_data_decisive_reproduces_all_real_captured_shots`
   to assert the 5 existing M15 sidecars reproduce **exactly** under the refactor. Add H4 cases:
   aggregation correctness against a hand-checked parent, anchor resolution decisive/not-decisive
   branches, and fail-closed on `src/` absence.

5. **Backfill** the two existing H4 sidecars (`03_h4_jul27_31`, `09_h4_jul15_20`) from their own
   stored `bars` — deterministic, zero new capture, exactly the D-1 backfill precedent. Preserve
   originals as `*_PRE_H4RECON.json` (§6.2 rule 4).

---

## Workstream B — capture the missing month

Two tiers, because reconciliation and legibility have different needs. OHLC reconciliation reads
TV bars from the `tv_bridge` API into `bars_by_epoch` — **not** from pixels — so a dense wide
window still reconciles at full fidelity; only the *visual* dimension needs a readable frame.

1. **Reconciliation tier** — new wide M15 shots in `shot_plan.json` covering the two blind spans:
   `m15_jul07_14` (2026-07-07 01:00 → 2026-07-14 23:45) and `m15_aug01_06`
   (2026-08-01 00:00 → 2026-08-06 23:45), both `clock: broker`, plus a new preset
   `month-fill`. These close rows 1–2 across the whole corpus.
2. **Visual tier** — run the existing `--preset macro`, which already contains
   `h4_july_macro` + `h4_july_setup` + `h4_jul27_31`. With Workstream A landed these produce real
   H4 verdicts instead of `NOT_APPLICABLE`.
3. **Known risk to check, not assume:** `frame_shot`'s two-sided achieved-vs-requested assertion
   (`capture_tv.py:212-224`) may reject a 5-week window if `zoomToBarsRange` silently clamps. If
   it raises on `h4_july_macro`, report the framing failure and fall back to the `--via-ui`
   Go-to-date path; do not loosen the assertion — it is the guard that caught shot 04's original
   mis-framing.
4. Capture launches Playwright against tradingview.com (read-only page loads, writes only under
   `tools/tv_forensic/shots/`). Verified available: `playwright.sync_api` importable, chromium-1234
   present, Pillow 12.2.0.

---

## Workstream C — SMC visual verification (report row 8)

**New `scripts/research/smc_visual_verification.py`** (read-only; writes only under
`results/monthly_tv_semantic_report/`).

- `results/monthly_tv_semantic_report/smc_feature_month.json` stores only `{timestamp, value}`
  per hit — normalized distances, no price levels, so nothing drawable. Get real levels by
  calling the canonical detectors directly: [find_active_order_block](src/features/smc/order_block.py:55),
  [find_active_fvg](src/features/smc/fvg.py:40), [find_active_breaker](src/features/smc/breaker.py:25),
  [find_active_mitigation_block](src/features/smc/mitigation.py:25), plus
  `pdh_pdl_distance`/`eqh_eql_distance` in `levels.py`. Each returns a `Zone`
  (`_geometry.py:33`) carrying price edges. Reuse — do not re-derive.
- **Mechanical layer (verifiable):** for each feature with an independently checkable reference,
  assert it against the sidecar's own TV bars — e.g. the PDH/PDL level equals the prior day's
  max/min of TV bars; an FVG's edges equal the gap between the recorded bar pair; a `Zone` marked
  active is not already mitigated per `is_mitigated`. Emit pass/fail per instance.
- **Visual layer:** render zones onto the shot PNG reusing `annotate.py`'s `Frame`
  (`annotate.py:65`, price→y via the sidecar's `plot.price_calibration`), `dash_h`, `font`, and
  `stagger` — note `stagger` keys on `(event, broker)` post-D-6, so distinct zones at one price
  will not collapse onto a shared row. Output `<shot>_SMC_ANNOTATED.png`, one per feature family
  to keep frames readable.
- Deliverable for the user: annotated PNGs plus a per-feature mechanical pass/fail table. Row 8
  upgrades only for the claims mechanically proven; anything resting on eyeball judgment is
  presented for adjudication, not self-certified.

---

## Governance (required, not optional)

- **BUILD_IMPACT_MANIFEST first** — `docs/governance/build_manifests/CH-monthly-tv-coverage-h4-recon.impact.json`,
  modeled on `CH-crt-semantic-execution-reconstruction.impact.json` (report-only precedent) and
  `CH-parent-crt-caller-wire.impact.json` (fuller pair). Change classes:
  `SCRIPT_LIFECYCLE_CHANGE` (new script under `scripts/research/`) + `DOCUMENTATION_ONLY`
  (report edits). Mandatory fields per `construction_protocol.py:45-48`; any `unknowns` entry
  must be non-blocking or it halts.
  Validate: `python scripts/governance/construction_protocol.py validate-impact <manifest>`.
- **SITS registration** for the new script, same turn (`docs/reference/conventions.md` §2.1):
  `script_census.py --write-stubs` → **add a Python overlay in `seed_script_registry.py` with a
  real `purpose`** (stubs alone fail the PR-3 ratchet) → `seed_script_registry.py` →
  `generate_script_matrix.py`.
- **§6.7 grounding** — every repo path/symbol the updated report cites must return `GROUNDED`:
  `python scripts/governance/query_semantic_os.py --ground --kind IMPLEMENTATION --token <path> --symbol <Name>`
  and `--kind EVIDENCE --token F-0NN` for each finding.
- **Findings** — update the report + `.json` twin in place; append Notes to F-075 (H4 shots now
  reconciled / coverage closed), F-076 (row 8 outcome), F-079 (its `NOT_APPLICABLE` D-1 marker is
  now a real branch, not a permanent terminus). Register a **new F-id only if** H4 reconciliation
  finds genuine divergence — pre-registered as the sole condition, so a null result cannot be
  inflated into a finding. Never delete a superseded claim (§6.2 rule 4).
- **Untracked-tree note:** `reports/monthly_tv_*` and all of `tools/tv_forensic/` are currently
  untracked (review defect D-3). Flag for the user; do **not** `git add -A` — ~15 concurrent
  Claude sessions run against this repo.
- **Two logs** — codebase log `assistant_project.md` per §6.

---

## Verification

```bash
python -m pytest tests/test_tv_forensic_smoke.py -q
```

1. **Byte-identity** — the 5 existing M15 sidecars reproduce exactly under the refactored
   `diff_table` (the extended regression test). This is the pass/fail gate on Workstream A.
2. **Non-vacuity** — H4 diff must actually compare bars: assert `summary.compared > 0` on the
   backfilled H4 sidecars. A `compared: 0` "clean" result is the silent-gap failure F-079 exists
   to prevent.
3. **Coverage arithmetic** — regenerate
   `results/monthly_tv_semantic_report/ohlc_clock_reconciliation.json` and confirm
   `shots_never_captured` shrinks to `[]` and `unreconciled_shots` shrinks to `[]` (or names
   exactly which grid failed to resolve, with its reason).
4. **Full-month claim check** — the report's Coverage table must state the new true numbers
   (trading days covered / ~22) computed from the sidecars on disk, not asserted.
5. **Read-only posture** — verify by directory listing that nothing under `configs/`, `src/`,
   `data/`, or `configs/production/ACTIVE_VERSION` changed; only `tools/tv_forensic/shots/`,
   `results/monthly_tv_semantic_report/`, `reports/`, the new script, and tests.
6. `python scripts/governance/construction_protocol.py validate-completion <manifest>` —
   re-executes required checks; it never trusts logs.
7. Broader floors touched by the new script:
   `python -m pytest tests/test_script_registry.py tests/test_script_matrix_sync.py tests/test_current_findings.py -q`

---

## Out of scope

- **No production behavior change.** No `ACTIVE_VERSION` edit, no `parent_crt.objective_gate`
  flip, no model retrain (F-076's 6 stale families stay stale), no promotion. Grants no G001 and
  no authority (§6.5).
- **No economic claim.** Report row 11 stays `NOT ADMISSIBLE` — nothing here powers the n=2
  RETEST corpus.
- **CRT closure stays `REOPENED`.** Closure criteria are code-internal; this touches none.
- **Romeo/Sujan equivalence (F-077) stays NOT established** — better TV coverage does not
  adjudicate a semantic non-equivalence. The crosswalk machine-twin is a separate deliverable the
  user did not select.
