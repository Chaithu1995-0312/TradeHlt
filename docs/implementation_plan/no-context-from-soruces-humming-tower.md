# TV-Forensic ↔ Dataset-Identity ↔ Constructor Trace: end-to-end comparison harness

## Context

Four systems built over the last ten days have never been connected:

1. **R3 Dataset Identity** (shipped 2026-09-02) — `admit_csv_path` is now the corpus gate on every governed load, but it binds exactly **one** dataset: the frozen 2-year Phase-1 candidate ending **2026-05-21**.
2. **TV forensic** (`tools/tv_forensic/`, 122 sidecars) — already covers **2026-07-07 → 2026-08-06** XAUUSD M15 at ~100% bar coverage, with a per-bar `engine_vs_tv` OHLC diff in every sidecar (F-080).
3. **v3 bar-structure snapshot** — 122 structural fields per bar, OBSERVATION_ONLY, never run outside the frozen corpus.
4. **v4 dual-construction trace** — engine-vs-resolver state per bar plus the engine's gate trace; `enabled:false` in one non-active config, **never executed, no JSONL on disk**.

The gap this plan closes: the TV screenshot window is **entirely outside** the admitted corpus, so no screenshot has ever been compared against an *admitted* bar. And the two open questions from the constructor-architecture work — the UNATTRIBUTED 39,308-vs-21,745 RANGE disagreement, and "does the engine see structure where a human/LLM sees structure" — have no instrument that answers them on the same bars.

**Outcome:** a fresh MT5 fetch of the TV window, admitted through Dataset Identity, driven through both constructors, and compared bar-for-bar against TradingView and against an LLM's reading of the same screenshots — in one report that answers "the screenshot shows structure through *this* time; what did the engine say?"

### Blockers found (all verified from source, not assumed)

| # | Blocker | Evidence |
|---|---|---|
| B1 | `_validate_record` hard-pins **any** `symbol == "XAUUSD"` record to `PHASE1_SHA256` + `PHASE1_PHYSICAL_PATH` | `dataset_registry.py:160-167` |
| B2 | `admit_csv_path` picks `next(r for r in datasets if r["symbol"]=="XAUUSD")` — first match wins, undefined with two | `dataset_registry.py:292` |
| B3 | `is_xauusd_m15_request` returns True for **any** filename starting `XAUUSD_M15` → blanket rewrite to Phase-1 | `xauusd_phase1_candidate.py:200-215` |
| B4 | `volume_semantic` enum has no `TICK_VOLUME_APPROXIMATE` — F-099's actual verdict is not expressible | `dataset_identity.schema.json`, `additionalProperties:false` |
| B5 | `resolve_canonical` only has an enforcer branch for XAUUSD/M15-via-Phase-1 | `dataset_registry.py:243-254` |
| B6 | `run_crt_state_on_mt5_xauusd.py` uses `pd.read_csv` directly — **bypasses admission entirely** | `:35` `OHLCV_PATH` hardcoded |

### Decisions locked (user, this session)

- Generalize R3 to multi-dataset (not a passthrough workaround).
- Reuse the existing Jul 7 – Aug 6 shot set; no fresh Playwright capture.
- LLM narration is **descriptive only** — no kappa, no gate, no fidelity claim; it must not touch either frozen blind-label pre-registration.
- Drill through **both** constructors plus the snapshot.

---

## Phase 1 — Generalize R3 to multi-dataset

Goal: a second bound dataset can exist without weakening the Phase-1 pin and without changing behaviour for any current caller.

**`docs/governance/dataset_identity.schema.json`**
- Add `TICK_VOLUME_APPROXIMATE` to the `volume_semantic` enum, with a description citing F-099 (0.55–0.68% directional gap, `artifact_binding` BOUND 17/17, `H_REAL` REJECTED). This is the honest value for any MT5 record; do **not** relabel the Phase-1 record in this plan.
- Add optional `legacy_rewrite_target` (boolean) — marks the one record that absorbs bare `XAUUSD_M15*` requests. Optional so existing records stay valid.

**`src/data_ingestion/dataset_registry.py`** — three surgical changes:
- `_validate_record`: scope the Phase-1 sha/path assertion from `raw["symbol"] == "XAUUSD"` to `raw["dataset_id"] == "XAUUSD_MT5_PHASE1_20260521"`. For every other record, verify the declared `canonical_artifact.sha256` against a **recomputed** hash of the declared path (fail-closed) — the pin becomes per-record instead of per-symbol.
- `admit_csv_path`: replace first-XAUUSD-wins with explicit resolution order —
  1. repo-relative posix path exactly matches a record's `canonical_artifact.path` → admit that record (hash-verify);
  2. path is in any record's `forensic_paths` → reject with the existing FORENSIC message;
  3. `is_xauusd_m15_request` **and** exactly one bound record carries `legacy_rewrite_target:true` → rewrite to Phase-1 (preserves today's behaviour verbatim);
  4. otherwise unbound passthrough.
  Raise `DatasetAdmissionError` if step 3 finds more than one legacy target — ambiguity must fail closed, never silently pick.
- `resolve_canonical`: add a generic branch (recompute sha, compare to record, verify row count and first/last timestamp) so non-Phase-1 records have an enforcer instead of falling through to `no admission enforcer`.

**`docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json`** — add `legacy_rewrite_target: true` only. Nothing else on that record changes; its sha, path, `decision_status` and `explicitly_not` stay exactly as frozen.

**`tests/test_dataset_registry.py`** — extend, never weaken. All 16 existing tests must stay green unmodified (that is the proof the rewrite path is behaviour-preserving). Add: two-record registry loads; explicit-path request admits the *new* record and is not rewritten; bare `XAUUSD_M15.csv` still rewrites to Phase-1; a second `legacy_rewrite_target` fails closed; a record whose declared sha ≠ recomputed sha fails closed; `TICK_VOLUME_APPROXIMATE` validates and a bogus enum value still fails closed.

---

## Phase 2 — Fetch and admit the TV window

**Fetch** via the existing strict path — do not write a new fetcher:

```bash
python scripts/data/fetch_and_verify_mt5.py --symbols XAUUSD --timeframes M15 --start 2026-07-07 --end 2026-08-07 --out data/mt5
```

This already runs `dataset_integrity.validate_dataset` with the `strict_fetch` override and quarantines to `data/mt5/_rejected/` on any tradable-bar gap. Rename the output to a window-scoped name (e.g. `data/mt5/XAUUSD_M15_20260707_20260806.csv`) so it is addressable by explicit path — resolution step 1 above, not the legacy rewrite.

**Clock provenance**: declare the new file in `configs/data_provenance/ohlcv_clock_registry.json` as `MT5_SERVER_NY_DST`, following the 2026-08-30 precedent — the declaration is path-keyed, so a fresh path inherits nothing and the gate will refuse the run until it exists. Record the terminal identity (build, skew) captured during the BC-2/BC-4 probes rather than re-deriving.

**New record** `docs/governance/datasets/XAUUSD_MT5_TVWINDOW_20260707_20260806.json`:
- `clock_basis: broker_local` (F-066 — the stamps are broker time; do **not** launder to UTC)
- `volume_semantic: TICK_VOLUME_APPROXIMATE` + `is_synthetic: false` (F-099)
- `decision_status: UNRESOLVED` — this window has never been through Phase-1 validation
- `explicitly_not`: all four bans, as the validator requires
- M15 canonical + H1/H4/D1/W1/MN1 as direct `ParentCandleBuilder` projections (star, MN1 never from W1)
- `forensic_paths`: `data/XAUUSD_M15.csv` (the old one-month export covering the same span — it must not be mistaken for this corpus)
- notes stating plainly: not APPROVED, `OHLCV_CLOSURE_STATUS` unchanged `BLOCKED:BC-1..BC-6`, and that BC-2/BC-4 evidence attaches to `4d73f5ce` only and does **not** transfer to this hash.

Add the row to `docs/governance/dataset_identity_registry.json`.

**Independent-refetch check** (free, and the first real one): the TV sidecars were built against `data/XAUUSD_M15.csv` for the same window. Diff the new fetch against it. Byte-identity is not expected or required — report the delta. A large delta is itself a finding about fetch reproducibility; a small one strengthens every downstream comparison.

---

## Phase 3 — Consumption trace: who, how, why, and the drill

Two things: a **static** trace and a **live** drill. Both go in the report.

**Static trace** — reconstruct and verify from source (the existing narrative in `docs/implementation_plan/i-want-to-check-graceful-fog.md` is a starting point, not evidence; re-verify each hop). The spine:

`CSV → CandleLoader.__init__ → admit_csv_path (R3) → dataset_integrity L1/L2/L3 → stream() → Candle → CRTEngine.process_candle → StateMachine (8 try_* methods) → ExecutionEngine → events/telemetry/trades`

with the second, parallel consumer:

`CSV → FeaturePipeline.run() → 48-dim vector + enriched columns → FeatureStateEncoder → CRTStateResolver.resolve() → resolver occupancy`

Per hop record: **who** (module:symbol), **how** (which columns/fields it actually reads), **why** (what decision it feeds), and **what it discards**. Two facts to state explicitly because they are load-bearing and counter-intuitive: the CRT state machine runs on its own ontology-routed candle geometry, not the 48-dim vector (the vector is pulled only inside the `TRADE_OPENED` branch); and `crt_state_resolver` is a *different construction*, not a mistuned copy.

**Live drill** — one run under `v4_dual_construction_2026_09` with `bar_structure_snapshot.enabled` and `crt_construction_trace.enabled` forced true, in an isolated config root via `src/utils/isolated_config_root.py` (`build_config_root` + `run_backtest`), following `scripts/research/emit_bar_structure_snapshots.py` verbatim as the pattern. `ACTIVE_VERSION` is never touched; verify it reads `v2_htfcrt_2026_08` before and after.

This single run yields, joinable on `run_id` + `bar_index`:
- `events.jsonl` / `crt_telemetry.jsonl` / `trades.csv` — engine occupancy and trades
- `bar_structure_snapshot` JSONL — 122 structural fields per bar
- `crt_construction_trace` JSONL — engine state, resolver state, and the engine's gate trace per bar

**Decision-neutrality proof, required before the report is trusted**: run the same corpus under `v2_htfcrt_2026_08` with both emitters off, and assert `events.jsonl` / `crt_telemetry.jsonl` byte-identical to the emitters-on arm. Reuse `v3_config_parity.py`'s `compare()` / `_compare_trades()` by import — do not re-implement the diff.

**Injection guard**: `crt_construction_trace` hard-pins `injection="none"`. If measured engine↔resolver agreement lands far above F-069's 88.16% on this corpus, treat it as a defect in the harness, not a finding.

---

## Phase 4 — Three-way comparison

New script `scripts/research/tv_structure_comparison.py` (read-only over artifacts; SITS-register it: `script_census.py --write-stubs` → real overlay in `seed_script_registry.py` → seed → `generate_script_matrix.py`).

**Arm 1 — bars vs TradingView.** Join TV sidecar `bars[]` to the admitted corpus on broker timestamp. Deduplicate across overlapping shots on `(interval, broker_ts)` exactly as `scripts/research/tv_engine_odds.py` already does — reuse its `collect_unique_bars` rather than writing a second deduper. Report per-field deltas, coverage denominator, and the daily-open exception F-080 already characterised (do not re-derive it; check it still holds and say so).

**Arm 2 — engine vs resolver.** From the construction trace: agreement rate, per-state confusion matrix, and the bidirectional EXPANSION signature (`EXPANSION→RANGE` under-fire vs `RANGE→EXPANSION` over-fire) that distinguishes a different construction from a mistuned threshold. This is the first per-bar measurement of that split on a corpus outside the frozen candidate.

**Arm 3 — LLM narration.** For each shot, feed the **existing PNG** (`tools/tv_forensic/shots/*.png` — already rasterized; `blind_label_rasterize.py` was for the SVG stimulus and is not needed) with the shot's broker-time window, and ask for a structured reading: ordered `{from_ts, to_ts, label}` segments plus `last_structure_seen` and its timestamp. Constraints that must hold:
- **Blind**: the prompt carries the image and the window only — never engine states, never resolver states, never the sidecar JSON.
- **Not scored**: no kappa, no pass/fail, no threshold. Recorded as a third column beside engine and resolver.
- **Not under either frozen registration**: state this in the report header. Both blind-label preregs are frozen and one is halted at its own gate; nothing here amends or reports under them.

**Arm 4 — the "till this time" question.** This is your example, made mechanical. For each shot window, extract the last structural event from all three sources — engine (`crt_construction_trace.engine_state` transitions), resolver (same file, `ontology_state`), LLM (`last_structure_seen`) — and tabulate: *screenshot shows structure through T_llm; engine's last transition was T_eng (state S); resolver's was T_res (state S')*. Classify each shot AGREE / TIMING_DIVERGENT / STATE_DIVERGENT / ABSENT.

---

## Phase 5 — Report

`reports/tv_dataset_constructor_comparison_<window>.md`, sections in this order:

1. **Provenance** — dataset_id, sha256, rows, range, clock basis, volume semantic, admission decision, and explicitly whether the path was **rewritten** (the silent-redirect class from 2026-08-30 must be visible, not inferable). Print the **resolved** path, never only the requested one.
2. **Integrity** — L1/L2/L3 result, tradable-gap list, refetch delta vs `data/XAUUSD_M15.csv`.
3. **Consumption trace** — the who/how/why table plus a worked per-bar drill for a handful of named bars, from raw CSV row through to engine state, resolver state, and the 122 snapshot fields.
4. **Arm 1** bars vs TV. **5.** Arm 2 engine vs resolver. **6.** Arm 3 narration. **7.** Arm 4 the "till this time" table.
8. **Scope ceiling** — one instrument, one window, one config epoch; `economic_claims_allowed: false`; no G001; no promotion; `OHLCV_CLOSURE_STATUS` unchanged; BC-2/BC-4 evidence does not transfer to this hash.

---

## Verification

- `pytest tests/test_dataset_registry.py` — all 16 existing tests green **unmodified**, plus the new ones.
- `pytest tests/test_corpus_authority_decisions.py tests/test_xauusd_phase1*.py` — freeze tokens still green; if a token needs re-pinning, do it explicitly with the reason, never by deleting the assertion.
- Emitters-on vs emitters-off byte-identity on `events.jsonl` and `crt_telemetry.jsonl` (the decision-neutrality proof).
- Non-vacuity: snapshot row count == corpus bar count; construction-trace row count == corpus bar count; TV join coverage denominator printed, not assumed.
- `configs/production/ACTIVE_VERSION` reads `v2_htfcrt_2026_08` on disk after every run.
- SITS chain run for the new script; grandfather pin resynced by the established house pattern.

**Pre-existing failures to leave untouched and name in the report** (all confirmed not ours): `test_ohlcv_corpus_freeze` drift on untracked `data/XAUUSD_M15.csv`; `test_session_log` count bound (the rotator is recorded as unsafe — do not run it); `test_current_findings` naming only F-096 and stale F-001…F-012 revalidate-by dates.

## Explicitly out of scope

No `APPROVED` decision on any dataset. No flip of `OHLCV_CLOSURE_STATUS`. No R3b global unbound-reject. No `ACTIVE_VERSION` change, no promotion, no `params` edit. No fresh Playwright capture. No amendment to either blind-label pre-registration. No fix to `run_crt_state_on_mt5_xauusd.py`'s admission bypass (B6) — recorded as a finding in the report, remediated under its own authorization.
