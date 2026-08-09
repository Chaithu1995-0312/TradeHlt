# Pure-Claude Semantic Research Loop

## Context

**The ask:** OHLCV → deterministic semantic features → an LLM knowledge layer → Claude-authored semantic observations and hypotheses → validation through backtest/forward-walk → production-ready strategy rules, with trust escalating from untrusted LLM observation to qualified strategy.

**What's actually missing is small.** Exploration confirms four of the five layers already exist and are production-grade:

| Layer | Status | Where |
|---|---|---|
| 1. OHLCV → deterministic semantic labels | **COMPLETE**, shadow-only | `FeaturePipeline` → `FeatureStateEncoder` → `MarketContextBuilder` → `MarketShapeClassifier`, all driven by `configs/formulas/market_ontology.yaml` |
| 2. LLM knowledge layer | **MISSING** | — |
| 3a. Semantic observations (untrusted) | **MISSING** | closest analogue: `src/agent/findings_synthesizer.py` |
| 3b. Hypothesis → measurement | **COMPLETE**, frozen kernel | `research/contracts.py`, `registry.py`, `measurement/forward_walk.py`, `qualification.py` (M4, 7 gates) |
| 4. Trust / authority | **PRIMITIVES ONLY** | `hypothesis_registry.py` (authority pinned `"research"`), `closure_authority_index.json`, Authority Ladder, `test_epistemic_invariants.py` |
| 5. Production promotion | **COMPLETE** | `ConfigValidator` → `PromotionManager` |

So this is a **connective-tissue build**, not a new stack. The work is: a deterministic knowledge-pack builder, an untrusted observation ledger, a *mechanical* pre-registration gate, a cumulative multiple-testing budget with a sealed corpus slice, and a trust state machine — all additive, all research-authority-only.

**The honest expected outcome.** F-019…F-043 record ~15 registered falsifications of directional edge across crypto majors, FX, HTF, cross-sectional, carry, weekly-sweep and regime axes. The near-term value of this architecture is **throughput of falsification**, not an expected edge. M0 is designed to end in `REJECT` and still be a success.

**The one genuinely hard problem this plan must solve.** The M4 gate's Benjamini-Hochberg correction is scoped to a single run's cohort. An LLM that can author hypotheses cheaply turns that into a false-discovery engine, and worse — the LLM reads outcome statistics before writing `detect()`, which is researcher-degrees-of-freedom contamination that **no downstream test can detect**. The corpus split + cumulative budget below exist specifically for this.

### Decisions taken (user-confirmed)

1. **LLM runtime = the Claude Code session itself.** No API client, no key, no HTTP. The pipeline writes a knowledge-pack file; the session reads it and authors JSONL + a Python module. Follows the existing `src/control_plane/context_report.py` `provider="export"` precedent and CLAUDE.md §13.8 (Claude is sole code author).
2. **Three-way chronological corpus split with a sealed holdout.** DISCOVERY (LLM sees) / MEASURE (feeds the M4 IS/OOS split) / SEALED (never rendered into any pack; one-shot unseal per frozen hypothesis).
3. **M0 = thin end-to-end walking skeleton**, deliberately expected to REJECT.

### Flagged before starting

- **DOC_DRIFT (§6.2):** `CLAUDE.md` states the canonical vector is **38-dim**; exploration reports schema v4.0 is **39-dim** (`macd_hist` split into `macd_hist_raw` + `macd_hist_z`, `wick_size` → `candle_range`), with `SCHEMA_V3_FEATURE_DIM = 38` kept only as a compat sentinel. **Verify against `src/features/feature_schema.py` as M0 step 1** and fix `CLAUDE.md` in the same turn. Unambiguous DOC_DRIFT → auto-fix per the drift-protocol gate calibration.
- The on-disk trace corpus (`results/research/trace_corpus/xauusd/`, 23,447 rows) is **stale schema-v3**. Not needed for M0; rebuilt in M2.
- Corpus is the frozen XAUUSD Phase-1 candidate (`data/mt5/XAUUSD_M15.csv`, sha256 `4d73f5ce…`, 47,275 rows), guarded fail-closed by `src/data_ingestion/xauusd_phase1_candidate.py`. Standing mandate: **XAUUSD only** — never substitute a crypto major to make a demo produce events.

---

## Architecture

```
data/mt5/XAUUSD_M15.csv  (frozen, SHA-pinned)
   │
   ├─ corpus_split.py ──► DISCOVERY 50% │ MEASURE 30% │ SEALED 20% (newest)
   │                          │              │             │
   │              (sealed_guard refuses any pack touching SEALED)
   │                          ▼
   │   FeaturePipeline → FeatureStateEncoder → MarketContext → MarketShape
   │                          ▼
   └─ pack_builder.py ──► results/research/knowledge/xauusd/knowledge_pack.md
                              ▼
                   ┌──────────────────────────┐
                   │  CLAUDE CODE SESSION     │  ← the "LLM layer". No API.
                   │  reads pack, authors:    │
                   │   • observation JSONL    │
                   │   • hypothesis .py       │
                   └──────────────────────────┘
                              ▼
   T0  logs/semantic_observations.jsonl        authority NONE, status "untrusted"
                              ▼  freeze (thresholds must == canonical research_config)
   T1  docs/research/preregistration/generated/<id>.prereg.json   protocol_hash, frozen
                              ▼  codegen + leak tripwire + provenance header
   T2  src/research/hypotheses/generated/<name>.py    registered by import
                              ▼  UNCHANGED M4 gate on MEASURE slice
   T3  results/research/qualification/generated/...   PROMOTE | REJECT | INSUFFICIENT
                              ▼  one-shot unseal, alpha spent from budget ledger
   T4  SEALED confirmation                     ← first rung with research authority
                              ▼  existing path, human APPROVE
   T5  ConfigValidator → PromotionManager      ← only rung with production authority
```

The frozen measurement kernel (`contracts.py`, `qualification.py`, `forward_walk.py`) is **not modified**. Generated hypotheses enter it as ordinary `Hypothesis` Protocol objects — the same door `expansion_breakout` uses.

---

## M0 — Thin end-to-end walking skeleton

**Exit criterion:** `data/trust_ladder.jsonl` shows `OBS-0001` at `T3_MEASURED` with a real M4 verdict; the full provenance chain (module → prereg → observation → knowledge pack → corpus SHA) resolves mechanically; every artifact is byte-identical on rerun; sealed slice provably untouched.

### Step 0 — Construction Protocol classification (mandatory, before code)

`docs/governance/change_contracts.json` has **no class covering a new research/LLM subsystem**; its `_doc` says to extend classes and `tests/test_construction_protocol.py` together.

- Add change class `RESEARCH_SUBSYSTEM_ADDITION` — `authorities_to_inspect`: ontology, research config, hypothesis registry, findings; `required_checks`: the `CONSTRUCTION_FLOOR` set plus the new test floor; `rollback_boundary`: delete the new package + generated dir (no production surface touched); `completion_criteria`: sealed slice unread, authority NONE everywhere, determinism proven.
- Add the matching case to `tests/test_construction_protocol.py`.
- Write `docs/governance/build_manifests/CH-SEM-001.impact.json`; run `python scripts/governance/construction_protocol.py validate-impact <manifest>`.

### Step 1 — Corpus split + sealed guard

**`src/research/knowledge/corpus_split.py`**

```python
DISCOVERY, MEASURE, SEALED = "DISCOVERY", "MEASURE", "SEALED"
DEFAULT_FRACTIONS = (0.50, 0.30, 0.20)   # chronological; SEALED is the NEWEST tail

@dataclass(frozen=True)
class CorpusSplit:
    path: str; instrument: str; sha256: str; rows: int
    discovery: tuple[int, int]      # [start, end) raw row indices
    measure:   tuple[int, int]
    sealed:    tuple[int, int]
    def canonical(self) -> dict: ...
    def sha256_id(self) -> str: ...
    def slice_of(self, index: int) -> str: ...

def build_split(path, *, fractions=DEFAULT_FRACTIONS) -> CorpusSplit   # verifies file SHA, fail-closed
```

**`src/research/knowledge/sealed_guard.py`**

```python
class SealedSliceViolation(RuntimeError): ...
def assert_not_sealed(split: CorpusSplit, *, end_index: int) -> None
def assert_pack_scope(split: CorpusSplit, frame_end: int) -> None   # called by pack_builder
```

XAUUSD 47,275 rows → DISCOVERY ≈ 23,637 / MEASURE ≈ 14,183 / SEALED ≈ 9,455. Sealed is newest — closest to live, the honest holdout.

> **Reuse note:** carry a `_pos` column *before* `FeaturePipeline.run()` — the pipeline drops the 78-row warmup **and resets the index**, so pipeline row `i` ≠ raw bar `i`. Precedent: `scripts/research/build_trace_corpus.py:54-65`, `src/research/shape_statistics.py`.

### Step 2 — Knowledge pack builder (minimal for M0)

**`src/research/knowledge/pack_builder.py`** — deterministic, read-only, DISCOVERY slice only.

```python
PACK_VERSION = "1.0"
MAX_PACK_CHARS = 120_000        # hard cap; deterministic truncation by count rank

def build_pack(split: CorpusSplit, *, cfg: dict) -> KnowledgePack
def render_markdown(pack: KnowledgePack) -> str      # what Claude reads
def pack_hash(pack: KnowledgePack) -> str            # sha256 over canonical JSON
```

M0 pack sections (no conditional base rates yet — those land in M2):

1. **Provenance header** — corpus SHA, split boundaries, feature-schema version + hash, `PACK_VERSION`, `pack_hash`. No wall-clock in the body; timestamps go to a sibling `*_manifest.json` (existing convention).
2. **Vocabulary** — rendered *from the ontology*, not hand-written: the 15 stateful identities / 36 state names via `FeatureStateEncoder`, the coarse `MarketShape` names from `configs/formulas/market_shapes.yaml`, the 9 `CRTState` members, `CandleStateEncoder` tokens, `RegimeLabeler` C|N|E. **This is what stops the LLM inventing vocabulary** — it can only speak in registered terms.
3. **Frequency tables** — per-feature state occupancy; coarse shape counts; top-N fine `MS-<hash>` contexts with counts and `MarketContext.describe()` renderings.
4. **Already falsified** — injected verbatim from the F-019…F-043 rows of `docs/current-findings.md` (via `scripts/governance/export_findings.py` output). Cheap, and the single highest-value section: it stops the LLM re-proposing dead classes.
5. **Representative episodes** — k compact bar tables per top context.

Output: `results/research/knowledge/xauusd/knowledge_pack.{md,json}` + `knowledge_pack_manifest.json`.

Driver: **`scripts/research/build_knowledge_pack.py`**.

### Step 3 — Observation ledger (T0, untrusted)

**`src/research/knowledge/observation.py`** — modeled on `src/governance/hypothesis_registry.py` (strict field set, unknown keys rejected, pinned literals raise).

```python
_REQUIRED = ("id","kind","created","author","pack_hash","statement","ontology_refs",
             "proposed_mechanism","falsifier","status","authority","trust_rung","notes")
_ID_RE = re.compile(r"^OBS-\d{4}$")
AUTHORITY = "NONE"        # pinned literal — validate_record raises on anything else
STATUS    = "untrusted"   # pinned literal

class ObservationLedger:
    def append(self, record: dict) -> None      # validates, then appends
    def validate_record(self, record: dict) -> None
    def load(self) -> list[dict]
```

Validation that does real work:
- `ontology_refs` must resolve against `market_ontology.yaml` + `market_shapes.yaml` — **fail-closed**. An observation citing an invented `FM-999` is rejected at the door.
- `pack_hash` must match an existing knowledge-pack manifest.
- `authority` / `status` / `trust_rung` are pinned literals → **an observation cannot escalate itself**; escalation is only ever derived by `trust.py` from downstream evidence.
- `proposed_mechanism == ""` is legal but records `UNEXPLAINED` (mirrors `contracts.py:35` — held with suspicion).

Artifact: `logs/semantic_observations.jsonl` (RUNTIME tier — high-volume, append-only, never authority).

### Step 4 — Mechanical pre-registration (T1)

This closes the documented gap: *"nothing mechanically blocks a run whose thresholds differ from its prereg."*

**`src/research/knowledge/preregistration.py`** — wraps the already-built-but-unwired `src/research/experiment_spec.py` (`ExperimentSpec`, `authority` frozen at `"NONE"`, deterministic `sha256()`), plus the freeze/hash idiom from `src/research/episodes/protocol.py` (`compute_protocol_hash`, `freeze_block`).

```python
def build_prereg(observation, split, *, hypothesis_name, gate) -> dict
def protocol_hash(prereg: dict) -> str
def freeze(prereg: dict, out_dir: Path) -> Path
def validate_frozen(prereg: dict) -> list[str]   # [] == valid
```

`validate_frozen` enforces, mechanically:
- recomputed `protocol_hash` == stored value (no post-hoc edits);
- `frozen is True`, `authority == "RESEARCH_ONLY"`, `grants_production_authority is False`;
- **`gate` block equals the canonical values loaded from `configs/research/research_config.json`, and `gate_source_sha256` equals that config's `ResearchConfig.sha256`** — a divergent-threshold run is refused, not merely noticed;
- `observation_id` resolves in the observation ledger and its hash matches;
- `corpus_split` matches a `CorpusSplit.sha256_id()` recomputed from the pinned file.

Frozen file: `docs/research/preregistration/generated/<OBS-id>.prereg.json` — **committed**, matching the existing `docs/research/*.json` prereg-twin convention (`protocol_hash`, `frozen`, `authority: RESEARCH_ONLY`, frozen gate thresholds, `closure_rule`, `falsification_conditions`).

### Step 5 — Claude-authored hypothesis module (T2)

Claude writes one module at `src/research/hypotheses/generated/<name>.py`. New `generated/__init__.py` imports each module (registration-by-import); `src/research/hypotheses/__init__.py` gains **one line**: `from . import generated`.

Every generated module must carry a provenance header and the shared leak tripwire:

```python
OBSERVATION_ID = "OBS-0001"
PREREG_ID      = "PREREG-OBS-0001"
PROTOCOL_HASH  = "sha256:..."

@register_hypothesis
class <Name>:
    name = "gen:<name>"; family = "generated"
    economic_rationale = "<from the observation's proposed_mechanism>"
    def detect(self, window, features, ctx):
        leak_guard.assert_no_outcome_keys(features, ctx)
        ...
```

**`src/research/knowledge/leak_guard.py`** generalizes the existing tripwire in `src/research/hypotheses/market_shape_hypothesis.py:27,51-57`:

```python
FORBIDDEN = ("outcome","rr_achieved","mfe","mae","rr","time_to_tp","time_to_failure","reached_1r")
class OutcomeLeakError(RuntimeError): ...
def assert_no_outcome_keys(features: Mapping, ctx: Mapping) -> None
```

### Step 6 — Measurement driver (T3)

**`scripts/research/qualify_generated.py`** — copies the `scripts/research/qualify_shape_xauusd.py` shape (which already carries the 0-bps sensitivity twin), and **adds no statistics**. It:

1. loads the frozen prereg, runs `validate_frozen` → **refuses to run on any error**;
2. restricts the corpus to the **MEASURE** slice (asserts via `sealed_guard`);
3. runs the unchanged `HypothesisRunner.collect` → `EdgeAggregator.aggregate` → `evaluate_pre_bh` → `benjamini_hochberg` → `finalize`;
4. writes `results/research/qualification/generated/<id>.json` + a separate manifest.

Controls are the existing ones (`always_long`, `random_uniform`, `random_biased_70`); the winning control is selected exactly as the existing drivers do.

### Step 7 — Trust ladder state machine

**`src/research/knowledge/trust.py`** — deliberately mirrors the repo's `VALID_TRANSITIONS` idiom from `src/config_layer/state_identity.py`.

```python
RUNGS = ("T0_OBSERVATION","T1_PREREGISTERED","T2_IMPLEMENTED",
         "T3_MEASURED","T4_CONFIRMED","T5_QUALIFIED")
LEGAL_TRANSITIONS = {  # strictly linear — no skipping, no back-dating
    "T0_OBSERVATION":  {"T1_PREREGISTERED"},
    "T1_PREREGISTERED":{"T2_IMPLEMENTED"},
    "T2_IMPLEMENTED":  {"T3_MEASURED"},
    "T3_MEASURED":     {"T4_CONFIRMED"},     # only if verdict == PROMOTE
    "T4_CONFIRMED":    {"T5_QUALIFIED"},     # only via ConfigValidator/PromotionManager
    "T5_QUALIFIED":    set(),
}
RUNG_AUTHORITY = {  # Authority Ladder levels per build_g001_consumer_attribution.py:33
    "T0_OBSERVATION": 0, "T1_PREREGISTERED": 0, "T2_IMPLEMENTED": 0,
    "T3_MEASURED": 0,          # information only — a measured REJECT/PROMOTE is not value
    "T4_CONFIRMED": 1,         # ECONOMIC_USEFULNESS_MEASURED
    "T5_QUALIFIED": 2,         # AUTHORITY_EARNED — granted by the EXISTING gate, not here
}

def resolve_rung(observation_id: str) -> dict   # DERIVES rung from evidence artifacts
def resolve_all() -> list[dict]                 # → data/trust_ladder.jsonl (GENERATED tier)
```

**What mechanically prevents rung-skipping:** `resolve_rung` never accepts a claimed rung. It walks the evidence — observation record → frozen prereg file (hash-valid) → generated module (provenance header matching) → qualification report (prereg hash matching) → budget ledger unseal entry. A rung whose predecessor evidence is absent or hash-mismatched is not emitted. `data/trust_ladder.jsonl` is GENERATED (derived, never hand-edited), matching the `data/findings.jsonl` pattern.

### M0 test floor — `tests/research/knowledge/`

| File | Asserts |
|---|---|
| `test_corpus_split.py` | deterministic boundaries; fractions sum; SHA fail-closed on a mutated file |
| `test_sealed_guard.py` | **behavioral** — `pack_builder` raises `SealedSliceViolation` when handed the full corpus |
| `test_pack_builder.py` | byte-identical on rerun; `MAX_PACK_CHARS` respected; vocabulary matches the ontology exactly (no invented terms) |
| `test_observation_ledger.py` | pinned-literal violations raise; unresolvable `ontology_refs` rejected; unknown keys rejected |
| `test_preregistration.py` | **behavioral** — a prereg with one gate threshold mutated fails `validate_frozen`; a post-hoc edited body fails the hash check |
| `test_leak_guard.py` | **behavioral** — every registered `gen:*` hypothesis raises when `detect()` is fed a features dict containing `rr_achieved` |
| `test_generated_provenance.py` | every generated module's `PREREG_ID`/`PROTOCOL_HASH` resolve to a frozen prereg whose `observation_id` resolves in the ledger |
| `test_trust_ladder.py` | `LEGAL_TRANSITIONS` is linear and total over `RUNGS`; a fabricated T4 with no unseal record resolves back to T3 |

Tests are **behavioral, not grep** — per the E-001 lesson recorded in `tests/governance/test_epistemic_invariants.py` ("a test that cannot fail is not enforcement").

### M0 governance close-out (same turn, per §6.6 / §6.2)

- Register new semantic concepts as canonical ontology nodes (or explicit `UNKNOWN_*` nodes with the `epistemic` block) in `configs/formulas/market_ontology.yaml` — **never a TODO**.
- Write `docs/governance/build_manifests/CH-SEM-001.completion.json`; run `construction_protocol.py validate-completion`.
- Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md`.
- File the finding only if something was actually validated or overturned.

---

## M1 — Cumulative multiple-testing budget + sealed unseal (T4)

The scarce resource is the sealed slice. Discovery and MEASURE runs stay unlimited (exploration; within-run cohort BH already handles them). **Unseals are budgeted.**

**`src/research/knowledge/budget.py`** → append-only `docs/governance/discovery_budget.jsonl` (committed; precedent: `docs/governance/geometry_census.jsonl`).

```python
ALPHA_TOTAL = 0.05
K_MAX = 20                       # pre-declared max unseals; Bonferroni α_i = ALPHA_TOTAL / K_MAX
def reserve(prereg_id: str, *, projected_n: int) -> dict   # power pre-check; may REFUSE
def spend(prereg_id: str, *, p_value: float, verdict: str) -> dict
def remaining() -> dict
```

Three rules that make this honest:

1. **One unseal per prereg hash, ever.** A second attempt is refused. Re-freezing under a new id is legal but spends new budget — and the ledger records the lineage, so serial re-freezing is visible.
2. **Spending is irreversible regardless of outcome.** An `INSUFFICIENT` sealed result still spends its α. Otherwise peeking is free and the budget is theatre.
3. **Power pre-check refuses before spending.** The prereg declares the observed firing rate on DISCOVERY; projected sealed `n` is computed from it. If projected `n < 30` the unseal is **REFUSED and no α is spent** — a guaranteed-`INSUFFICIENT` peek teaches nothing and reveals nothing, so it must not cost. (This matters: XAUUSD rare-geometry hypotheses will hit it.)

The T4 report also records the **selection ratio** — how many discovery-stage observations were considered per unseal — so a `PROMOTE` is never read without knowing the search breadth behind it.

**Exit:** a hypothesis reaches `T4_CONFIRMED` or is refused, with the budget ledger showing the spend and the trust resolver deriving T4 only from a valid unseal record.

## M2 — Knowledge pack depth

Conditional base rates for top-N contexts via `horizon_excursion` (exit-agnostic) and `forward_walk(intrabar_fixed)` at canonical 1.0/2.0 ATR geometry — **every conditional row printed adjacent to its unconditional baseline and its `n`**, so no number can be read without its control. Shape→shape and CRT state→state transition matrices. Rebuild the trace corpus at schema v4 (`scripts/research/build_trace_corpus.py`). All DISCOVERY-slice only; all labeled DESCRIPTIVE / non-promotable.

## M3 — Throughput

Batch: one pack → N observations → N generated hypotheses measured as a **single cohort** so the existing BH correction applies across them rather than being diluted by serial single-hypothesis runs. Resolver reports cohort size and selection ratio per verdict.

## M4 — Agent-surface integration (optional)

Register `knowledge.build_pack`, `observation.append`, `prereg.freeze`, `qualify.generated`, `trust.resolve` as tools in `src/agent/modes/` + `PLAN_REGISTRY`. Write tools inherit the existing allowlist → path-guard → `y/N` confirm chain. Only worth doing once M0–M2 are stable. Note the existing doc drift here (agent docs say 20 tools/14 intents; reality is 25/17).

---

## Verification

**Per-milestone floor:**
```bash
python -m pytest tests/research/knowledge/ -q
```

**M0 end-to-end (the real proof):**
```bash
python scripts/research/build_knowledge_pack.py --instrument XAUUSD --out results/research/knowledge/xauusd
```
```bash
python scripts/research/qualify_generated.py --prereg docs/research/preregistration/generated/PREREG-OBS-0001.prereg.json
```
```bash
python -c "from research.knowledge.trust import resolve_all; [print(r) for r in resolve_all()]"
```

**Determinism** (existing convention — no wall-clock in artifact bodies):
```bash
python scripts/research/build_knowledge_pack.py --instrument XAUUSD --out /tmp/pack_b && diff results/research/knowledge/xauusd/knowledge_pack.md /tmp/pack_b/knowledge_pack.md
```

**Governance floor:**
```bash
python scripts/governance/construction_protocol.py check
```

**Sealed-slice integrity** — the assertion that matters most: grep every emitted pack + qualification artifact for any row index ≥ `split.sealed[0]`, and assert the budget ledger contains no unseal record. Covered behaviorally by `test_sealed_guard.py`, and re-run as a manual check at M0 exit.

---

## Critical files

**New** — `src/research/knowledge/{corpus_split,sealed_guard,pack_builder,observation,preregistration,leak_guard,trust,budget}.py`; `src/research/hypotheses/generated/`; `scripts/research/{build_knowledge_pack,qualify_generated}.py`; `tests/research/knowledge/`.

**Modified (minimal, additive)** — `src/research/hypotheses/__init__.py` (one import line); `docs/governance/change_contracts.json` + `tests/test_construction_protocol.py` (new change class); `configs/formulas/market_ontology.yaml` (new semantic nodes); `CLAUDE.md` (38→39-dim drift fix, pending verification).

**Reused, not modified** — `research/contracts.py`, `qualification.py`, `measurement/forward_walk.py`, `runner.py`, `registry.py`, `experiment_spec.py`, `episodes/protocol.py`, `features/{feature_pipeline,feature_states,market_context,market_shape}.py`, `governance/hypothesis_registry.py`.

## Risks

| Risk | Mitigation |
|---|---|
| Sealed slice too small for rare geometries (n<30) | M1 power pre-check refuses the unseal without spending α; hypothesis stays at T3 |
| LLM invents vocabulary not in the ontology | Pack renders vocabulary *from* the ontology; `ontology_refs` validation is fail-closed |
| Generated `detect()` leaks future data | `leak_guard` tripwire + behavioral test per generated module + measurement on unseen slices |
| Serial re-freezing to dodge the budget | Budget ledger is append-only and records prereg lineage; selection ratio is reported with every verdict |
| Subsystem drifts toward implied authority | `authority` pinned literal at every layer; `RUNG_AUTHORITY` caps T0–T3 at Ladder level 0; production authority reachable only through the existing `ConfigValidator` → `PromotionManager` gate |
