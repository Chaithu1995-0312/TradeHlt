# Re-draw the CRT state diagram against real bars

## Context

The shared diagram is a companion to
[`docs/implementation_plan/three-sheets-137-data-partitioned-otter.md`](docs/implementation_plan/three-sheets-137-data-partitioned-otter.md)
(CRT Resolver — Wiring Phase). Its closing caveat says the t0–t8 bar assignment is **illustrative**
while the predicate sets, counts and plan-item mapping are exact, and asks for a real bar range.

**Every load-bearing claim verified against source** (§6.8 — an external claim is a hypothesis until
reproduced): 9 resolver states with 6 `when:` / 3 `when: {}` ✅ · **`displacement_flag` gates exactly 4**
(SWEEP, DISPLACEMENT, EXPANSION, RANGE) ✅ · per-state counts 10·4·3·3·1·1 ✅ · 13 `when:`-named
features ✅ · `CRTState` 12 members ✅ · `volatility_regime` 30 / `volume_spike` 38 /
`change_of_character` 47 on the 48-dim v5.0 schema ✅. The concentration argument holds exactly.

---

## Resolved before planning: the three flags

### 1. Frame size — NOT a TruthConflict, and the confusion was mine

There is **one frame with two documented derivations**:

```
raw corpus  data/mt5/XAUUSD_M15.csv        47,275   (engine summary total_candles = 47,275)
  − 78  warmup head dropped by finalize()  47,197   (bar_matrix; _pos runs 78 … 47,274)
  − 40  forward label horizon              47,157   (oracle scan frame)
```

Both offsets are mechanical and already recorded (`build_bar_matrix.py:266` emits
`warmup_dropped`; the 40 is the scan's `purge_horizon`). **47,201 was never a frame size** — it is
the highest `candle_index` that happened to emit an *event*, necessarily ≤ 47,274. I reported it as
"candle_index range" in a sentence about corpus size, which invited exactly the reading it got.
**Correction is mine, not the repository's.** No holdout is at risk; the denominators to pin are
47,275 (raw) and 47,157 (scan frame), and they must be labelled with which one they are.

### 2. `results/` is gitignored — but `reports/` is not

`.gitignore` ignores `results` and `reports/dataset_integrity/` only. `reports/`, `ui_kits/**/vendor`
and root `*.dot` are all tracked. So the evidence fixture does **not** need a new home invented for
it — `reports/` is the existing convention for exactly this. Worth naming the asymmetry: two trees
holding the same class of generated artifact, one ignored and one committed.

### 3. The million-line diff is the branch, not this work

`main...HEAD` = 2,917 files, **+1,022,729 / −148,064**, dominated by committed generated artifacts:
`reports/crt_semantic_execution_reconstruction.json` (76,175), `pyan_call_flow.dot` (68,568),
`behavioral_constant_authority_trace-2026-07-11.json` (39,997), a vendored
`react-dom.development.js` (29,924), `mismatch_bars_baseline.csv` (16,918),
`folder_structure_clean.txt` (16,507). My 8 commits this session are **10,657 of that** — 1%.
Nothing is being staged from `results/`; the volume predates this branch's recent work.

---

## Source data (extracted read-only)

Run `results/g001_baseline_f074on/run_20260815_155428_XAUUSD` — full corpus, F-074 ON, 7,112 events.
**Exactly three trades exist in the whole corpus**; two stop out on the next bar (11364→11365,
11609→11610). One completes.

**Panel A — golden path, `idx 18007–18031`** (25 bars, 2025-02-25 10:15→16:15 broker):
RANGE →SWEEP(18007, @2931.92) →DISPLACEMENT(18008, body_ratio 0.815) →**EXPANSION(18012)**
→RETEST(18028, depth_abs 0.81 / ceiling 1.80450) →EXECUTION(18029, LONG @2934.39) →RESOLUTION(18030,
TP1) →TP2(18031). Seven of nine resolver states, the only TP2 in the corpus, and it maps 1:1 onto the
existing t0–t8 axis so the supply spine survives unchanged.

**Panel B — shadow branch, `idx 10782–10793`** (12 bars, 2024-11-04 08:00→10:45):
SWEEP→DISPLACEMENT(10782) →**RESET to RANGE(10785, HTF 000677→000678)** →**SHADOW_PENDING(10786,**
"Shadow resume: confirming sweep @2744.80 dir=SHORT"**)** →SWEEP(10787, "prior-window displacement
restored") →EXPANSION(10787, "displacement carried from prior HTF window") →RESET(10793, 1.618
extension hit). The shadow state visibly *rescues a displacement across an HTF boundary* — the exact
capability the declarative language cannot name.

---

## Step 1 — extract the per-bar engine ↔ resolver pair, with causes

`scripts/research/crt_state_confusion_matrix.py` already builds aligned per-bar `engine_states` /
`resolver_states` (`:602-620`) and supports `--injection none` (the F-069-honest mode), but its JSON
payload (`:919-944`) writes **aggregates only**. `scripts/research/crt_parity_classifier.py` already
holds the divergence taxonomy as `CATEGORY_PRECEDENCE` (8 members) plus the declared-negative
`DIVERGENCE_CODE_REJECT_REASON` table — the prototype of Step 1's `ResolverDivergenceCause`.

New observe-only `scripts/research/crt_state_window_trace.py` that **imports both modules** and
reuses `classify_mismatch` — do not reimplement the alignment or the classification. A second
implementation of the engine↔resolver mapping is the divergence class F-046/F-069 already record,
and re-deriving the cause table would be the FM-058/SP-001 error the classifier's own header warns
about.

- Args: `--ohlcv data/mt5/XAUUSD_M15.csv --events <run>/XAUUSD_events.jsonl --injection none
  --windows 18007:18031,10782:10793`.
- Emits per bar: `candle_index`, `timestamp`, `engine_state`, `resolver_state`, `agree`,
  **`divergence_code`** (a `CATEGORY_PRECEDENCE` member) and the transition reason.
- Writes a committed fixture to `reports/crt_window_trace_2026_08_22.json` carrying **run id, frame
  definition (raw 47,275 / warmup 78 / scan 47,157), bar count, and the raw event rows** for both
  windows — so the diagram rests on something a clone can check, not a gitignored local file.
- **SITS-register the same turn** (`script_census.py --write-stubs` → `seed_script_registry.py` →
  `generate_script_matrix.py`). That floor is already red on 21 unregistered scripts from concurrent
  sessions; this must not add a 22nd.

**Pre-registered predictions — this is the live test of the taxonomy, so they are written before the
run:**

| bar | expected divergence | expected code |
|---|---|---|
| 18012 EXPANSION | resolver reaches EXPANSION by declarative predicate, engine by the ATR-extension gate | `C-GEOMETRY` (F-069 Category C, 96.1% of residual) |
| 10786 SHADOW_PENDING | engine reaches a state `when: {}` cannot name, **via a memory mechanism** | `B-UNREACHABLE-STATE` — **but see below** |

**The predicted taxonomy gap.** `B-UNREACHABLE-STATE`'s own comment enumerates the three reasons it
covers — "EXECUTION lacks a `score` key at all; RESOLUTION and EXPIRED are `when: {}`" — and
**SHADOW_PENDING is not among them**, though it is equally `when: {}`. More substantively, the wiring
plan's prose names four dominating causes (predicate mismatch, continuous-gate failure,
**memory/sticky-dwell divergence**, geometry-construction divergence) and `CATEGORY_PRECEDENCE` has a
clean member for the last one only; the closest fit for a memory divergence is `C-PHASE-ERROR`, which
is defined as a *timing/phase offset* and means something else. If 10786 can only be labelled
`D-UNKNOWN` or forced into `C-PHASE-ERROR`, **the taxonomy is missing a memory/shadow-resume member
and Step 1 should land with it** — found for free, before Step 1 commits.

---

## Step 2 — re-draw as an Artifact

Same six-lane layout. Four changes:

1. **M15 track splits into `ENGINE` and `RESOLVER (injection=none)` sub-rows** over one bar axis.
   This is the same construction at a different zoom as the comparison-surface lane at the bottom,
   where the engine row is already the blue anchor — the top of the diagram becomes a rendering of
   the surface at the bottom.
2. **Each divergent bar carries its `CATEGORY_PRECEDENCE` code**, not a generic "differs" tick, so
   the diagram is a worked example of the Step 1 taxonomy rather than an ad-hoc annotation.
3. **Panel B added** beneath Panel A, sharing the legend, with its own short axis. It earns the space
   by showing a *different kind* of divergence — 18012 is "both constructions ran and disagree",
   10786 is "the engine reached a state the language cannot name" — which map to different causes and
   different plan items (Steps 5/6 vs Step 7).
4. **`EXPIRED` is marked observed-zero, not drawn as a path.** 0 emissions this epoch (consistent
   with F-068). In an illustrative diagram a plausible alternate terminal is fine; in a traced one it
   would assert a transition that never fires. Its absence is itself evidence for the Step 7
   memory-grammar design.

**SHADOW_PENDING's grey is re-captioned, not recoloured** — grey on the RESOLVER row (`when: {}`,
unnameable), solid on the ENGINE row (6 corpus emissions, one inside Panel B). The caption must carry
both scope facts: bars are ENGINE emissions from one F-074-ON run, and the predicate lanes describe
the RESOLVER, a different construction — which is why there are two rows.

Everything else — supply spine, amber built-but-unlinked boxes, plan-item row, count summary —
carries over unchanged, since all of it verified.

---

## Consequence to record for Step 2 of the wiring plan

**The pre-registered tuning-phase selection rule cannot be anchored on trade outcomes.** n=3 trades
corpus-wide, n=1 completed walk. It has to be a **state-agreement** rule. That rule is committed
before the first comparison and is meant to be unrevisable afterward, so this belongs in the wiring
plan now, not after. Out of scope to write here — flagged for that document.

## Verification

```bash
python -m pytest tests/governance/test_crt_divergence_taxonomy.py tests/test_script_registry.py tests/test_doc_citations.py tests/test_current_findings.py -q
```

- **Determinism:** run the extractor twice, assert byte-identical output.
- **Round-trip:** Panel A's engine row must reproduce the seven transitions tabled above directly
  from `XAUUSD_events.jsonl` — every number in this plan came from that file and must survive.
- **Non-vacuity:** assert the resolver row is **not** identical to the engine row over Panel A. If it
  were, the dual row is decoration and F-069 is contradicted.
- **Taxonomy coverage:** assert every emitted `divergence_code` is a real `CATEGORY_PRECEDENCE`
  member, and record explicitly whether 10786 landed on `D-UNKNOWN`.
- `test_script_registry` must not gain a new unregistered path.

Close with the §6 SESSION LOG entry in `assistant_project.md`.

## Out of scope

- Any edit to `market_crt_states.yaml`, the resolver, or the engine. This is measurement and drawing;
  the Step 3e / Step 7 wiring work is not authorised here.
- **Registering `ResolverDivergenceCause`** — that is Step 1 of the wiring plan. This work *tests* the
  prototype taxonomy and reports gaps; it does not land the enum.
- Re-closing CRT (stays OPEN per F-074), and any claim about whether the wiring plan is correct.
