# F-041 — Close the ZoneGate finding (Phase-5 label verdict → manifest reconciliation)

## Context

F-041 (GOV, **OPEN**, Certain) records two facts that must not be conflated:

1. **CERTAIN (bookkeeping):** the runtime hard gate scores through `models/zone_registry.json`
   (8 gaussian zones, sha `e73e0893`), loaded directly from `engine_runner.zone_registry_path`.
   The version manifest `models/zone_gate_registry.json` has `active:true` → a *different*,
   pre-conversion file (`models/BNBUSDT/bnbusdt_training_20260524/zone_registry_BNBUSDT_202605_bnb_v1.json`,
   sha `aade29c4`) that nothing at runtime loads → an unreconciled §6.2 TruthConflict.
2. **OBSERVATION (pending Phase-5):** stored zone labels are ~98% SL-hit / 6-of-8 negative
   `mean_rr`. Whether that reflects **honest intrabar_fixed outcomes** or a **labeling artifact**
   is the explicit **Phase-5 Go/No-Go gate** — *not yet asserted*.

Two mechanisms found during exploration make both halves tractable:

- **Label provenance:** `scripts/research/discover_zones.py:129-130` reads `rr_achieved`/`outcome`
  straight from `opportunities_*.jsonl` — the exact stream **F-022** found only 36.8%
  self-consistent (SL_HIT stamped on paths that never touch the stop). So the stored labels
  inherit F-022 contamination *by construction*. Phase-5 is therefore a re-derivation test.
- **Manifest divergence cause:** the runtime file is `source=discover_zones_v1_converted_to_gaussian`
  — a zone_v1→v2_gaussian **conversion** wrote `models/zone_registry.json` directly and bypassed
  `register_zone_gate`/`promote_zone_gate`, so the manifest's `active` was never updated. The
  manifest is *stale*, not *authoritative* — runtime truth (§4.0 Tier-0 config) wins.

**Runtime caveat that scopes the verdict (do not overclaim):** the live gate is **purely
geometric** — `zone_gate_engine.py` scores weighted-Gaussian distance to zone centroids and
**never reads** `sl_hit_rate`/`mean_rr`/`tp_hit_rate` (sidecar metadata only). F-036 already
proved ZoneGate is `NON_PIVOTAL` (ΔG001≡0). So Phase-5 cannot claim labels "gate badly"; it can
only establish whether (a) the stored labels are honest, and (b) the zone *geometry* separates
honest expectancy at all. Authority: **research/docs + governance-hygiene only** (§6.5); no
architectural change rides on this.

**Intended outcome:** produce the deferred Phase-5 verdict with honest evidence, then reconcile
the stale manifest to runtime truth — moving F-041 from OPEN to a resolved/closed state (or a
sharpened OPEN if the evidence surprises us).

---

## Part A — Phase-5 label verification (research; run first)

**Goal:** decide the Go/No-Go — are the stored zone labels honest, and does zone geometry
separate honest expectancy?

**New reusable logic** — `src/research/zone_label_audit.py`:
- `assign_zone(vector_38, registry) -> zone_id` — assign each opportunity to a zone using the
  **runtime** geometry (max weighted-Gaussian score via the existing
  `src/bitnet/zone_cosine_searcher.py::compute_gaussian_score`, i.e. nearest active centroid),
  NOT the 35-dim raw KMeans. This guarantees the audit partitions members the way the live gate
  actually sees them.
- `honest_outcome(opportunity, candles) -> Outcome` — build a `research.contracts.Signal`
  (entry/atr/direction/entry_index from the opportunity record) and call the **unchanged**
  `src/research/measurement/forward_walk.py::forward_walk(..., exit_model="intrabar_fixed")` —
  the governing exit truth. Reuse the entry/ATR/direction extraction already proven in
  `scripts/analysis/bnbusdt_trade_anatomy.py` (F-022/F-024 re-derivation).
- `audit_zones(...) -> report` — per zone: `n`, stored `(sl_hit_rate, mean_rr)` vs **honest**
  `(sl_hit_rate, mean_rr)` re-derived under intrabar_fixed, the delta, and a
  sufficiency/consistency flag (reuse the `SufficiencyLevel`/`min_n=30` discipline from the
  metrics-oracle / insight-report pattern — below `min_n` makes **no** expectancy claim).

**Thin driver** — `scripts/research/zone_label_audit.py` (argparse wrapper only, per §3.3; no
business logic in the script):
- Inputs: `--registry models/zone_registry.json`,
  `--opportunities logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`,
  `--candles data/BNBUSDT_M15.csv` (the source run that built the zones — both confirmed on disk).
- Emits a deterministic JSON/markdown report under `docs/analysis/` (point-in-time study, not a
  living doc) + prints the verdict.

**Verdict logic (pre-registered before running — E-001):**
- **CONTAMINATED_LABELS** — stored `sl_hit_rate` ≫ honest `sl_hit_rate` (F-022 artifact
  confirmed): the "~98% SL-hit" was a stream artifact, not honest exit truth.
- **HONEST_LABELS** — stored ≈ honest: the zones genuinely sit in loss-dominated territory.
- **Cross-cut (the real Go/No-Go):** on **honest** relabels, does any well-powered zone (n≥30)
  clear `E>0` under intrabar_fixed+12bps? Expected NO (consistent with F-036 NON_PIVOTAL, F-023
  morphology≠expectancy, and the F-019…F-040 entry-null) → **label-quality is NOT the dominant
  ZoneGate defect; the entry-information null is.** If a zone *does* clear E>0, that is a rare
  candidate → route to the M4 `QualificationGate`, do **not** promote here (§6.5 Authority Ladder).

**E-001 pre-registration guards (must pass before registering any finding):**
1. Artifact for every claim = `file:line` in the emitted report.
2. INSUFFICIENT (n<30) zones make no expectancy claim (zone_5 n=172, zone_6 n=1,162 are the
   small ones — flag, don't infer).
3. Statistical ≠ economic (Authority-Ladder L1 vs L2): a label-honesty delta is L1 information,
   never "edge."
4. Phrase the verdict only after seeing raw honest counts.

---

## Part B — Manifest reconciliation (governance-hygiene; gated on Part A + user approval)

The manifest is stale bookkeeping; runtime config is Tier-0 truth (§4.0). Reconcile the manifest
**to** runtime, not vice-versa. Options, to present to the user with Part A's verdict:

- **B1 (recommended):** register the converted runtime file as a proper version and promote it,
  so `zone_gate_registry.json.active` → `models/zone_registry.json` (sha `e73e0893`) — the file
  that actually loads. Use the existing `core.model_registry::register_zone_gate` /
  `promote_zone_gate` (the same API `discover_zones.py` calls) so the conversion step no longer
  bypasses registration. Adds a manifest entry; no runtime behavior change (config already loads
  this file), hash-neutral for the production config.
- **B2 (fallback):** add an explicit `note`/advisory marker on the manifest stating it is not the
  runtime source (runtime is config-driven), leaving the surfaced conflict documented.

**Gate (§6.2 DDP):** editing `models/` governance artifacts requires **user approval** — do not
auto-apply. Present B1 vs B2 with the verdict; the user picks.

---

## Documentation / findings sync (same-turn obligations, §6.2)

- **`docs/current-findings.md` F-041** — set the Phase-5 result: fill `Validated`/`Revalidate-by`,
  cite honest-relabel `Evidence`, and if the verdict confirms "labels contaminated + geometry
  doesn't separate honest expectancy," record it as resolving the OBSERVATION half and (post-B)
  the bookkeeping half → move toward closure. **Never delete**; supersede in place.
- **`CLAUDE.md` Repository Truths Index** — the F-041 row must stay in sync
  (`tests/test_current_findings.py` enforces both directions).
- **`docs/topics/model-intent-and-feature-ownership.md`** — update the ZoneGate row
  (line ~125) and the Challenges/Ambiguities Discussion entries (lines 163-165) with the verdict;
  bump `Updated:` (Topic Sync Mandate §6.4, `tests/test_topic_docs.py`).
- **`active_models.yaml`** ZoneGate `evidence.conflicts` — reflect F-041 resolution
  (`tests/test_active_models_registry.py`).

---

## Critical files

| Role | Path |
|---|---|
| Reuse — exit truth | `src/research/measurement/forward_walk.py` (`forward_walk`, `exit_model="intrabar_fixed"`) — **unchanged** |
| Reuse — zone geometry | `src/bitnet/zone_cosine_searcher.py::compute_gaussian_score` |
| Reuse — re-derivation pattern | `scripts/analysis/bnbusdt_trade_anatomy.py` (F-022/F-024) |
| Reuse — sufficiency gating | metrics-oracle / insight-report `SufficiencyLevel` (min_n=30) |
| New — audit logic | `src/research/zone_label_audit.py` |
| New — thin driver | `scripts/research/zone_label_audit.py` |
| New — tests | `tests/test_zone_label_audit.py` |
| Registry API (Part B) | `src/core/model_registry.py` (`register_zone_gate`/`promote_zone_gate`) |
| Runtime zone data | `models/zone_registry.json` (read-only in Part A) |
| Manifest (Part B, gated) | `models/zone_gate_registry.json` |

---

## Verification

1. **Determinism:** run the driver twice on the fixed source JSONL + candles → byte-identical
   report (KMeans assignment is seeded; forward_walk is deterministic). This is the research
   equivalent of the parity gate.
2. **No-lookahead:** `forward_walk` already asserts every future bar `.index >
   signal.entry_index` (raises otherwise) — inherited for free; add one test that a leaked bar
   raises.
3. **Unit tests** (`tests/test_zone_label_audit.py`): (a) `assign_zone` picks the max-Gaussian
   zone on a synthetic 3-zone registry; (b) honest relabel of a hand-built SL-first path returns
   `SL_HIT`; (c) a sub-`min_n` zone yields `expectancy=None` (no claim); (d) report schema
   stable.
4. **Sanity cross-check:** honest zone-0 (n=20,708) SL-hit rate should land near the F-022-implied
   *true* rate, materially below the stored 0.9865 if CONTAMINATED — the headline number of the
   verdict.
5. **Doc floors:** `pytest tests/test_current_findings.py tests/test_topic_docs.py
   tests/test_active_models_registry.py` green after the sync edits.
6. **SESSION LOG** (§6/§7.4) appended to `assistant_project.md` with the Belief/ROI/Goal line.

---

## Risks / guards

- **Over-claiming that labels "break" the gate** — they don't; the gate is geometric and F-036
  NON_PIVOTAL. Keep the verdict scoped to label-honesty + geometry-separation. (E-001 guard 3.)
- **35-dim vs 38-dim mismatch** — `discover_zones` KMeans is 35-dim; the runtime file is 38-dim
  gaussian. Assign via the 38-dim runtime geometry (`compute_gaussian_score`) so the audit matches
  what the live gate sees; do not re-cluster.
- **Data drift** — the audit is scoped to the *exact* source run
  (`bnbusdt_training_20260524`); a different opportunities file would not reproduce the stored
  zones. Preflight-assert the run_id in the JSONL `run_header` matches the manifest path.
- **Part B is user-gated** — no `models/` edit or finding downgrade without approval (§6.2 DDP).
