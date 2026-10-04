# One Natural Home — collapsing duplicated truth across the three config layers

## Context

Someone joining this project in six months asks a simple question:

> **"Where do I go if I want to change one thing?"**

Today the honest answer is sometimes *"it depends."* A threshold exists in three
places. A feature formula is documented twice. A model's identity block repeats
runtime information.

That is not an architectural error. The three-layer separation is sound and
deliberate. What happened is ordinary entropy: over time, **documentation
accumulated implementation details**. The registry started as a pointer file and
slowly became a partial copy of the things it points at.

This is not a redesign. The goal is narrower and mechanical:

> **Every piece of information gets exactly one home. Every other file references it.**

The repo already demonstrates the target pattern — see "Precedent" below. This
plan applies that same discipline to the three blocks written before it existed.

---

## The three layers and what each owns

### WHAT — market knowledge · [`configs/formulas/market_ontology.yaml`](configs/formulas/market_ontology.yaml)

Answers: *what does this concept mathematically mean?*

What is `body_ratio`? How is `disp_strength` calculated? What is FM-021? Which
features depend on ATR? Which formulas are deprecated? What is a feature's
lifecycle?

Knows nothing about thresholds, runtime switches, production tuning, or model
versions. It defines market mathematics and nothing else.

### HOW — runtime behaviour · [`configs/production/<ACTIVE_VERSION>.json`](configs/production/v2_multi_2026_04.json)

Answers: *how should today's system behave?*

Thresholds, weights, enabled models, planner configuration, execution switches,
risk parameters, runtime paths.

**The only place that contains live numbers.** Changing a threshold means
changing exactly one file.

### WHO — model identity · [`active_models.yaml`](active_models.yaml)

Answers: *who is this model?* — not *how does it run*, not *how is a feature
calculated*.

Why was it created? What question was it designed to answer? What evidence
supports it? Which telemetry belongs to it? Which canonical features does it
consume? Is it enabled? Is it reachable? Which implementation owns it?

That is architectural identity, not implementation.

---

## Precedent — the pattern is already proven in-repo

The newest block in WHO, `crt.state_contracts`, was built to exactly this
standard and is **mechanically enforced at load time**:

- [`state_contract.py:98-101`](src/config_layer/state_contract.py:98) raises on any
  numeric value — literal message: *"thresholds/formulas forbidden"*
- [`state_contract.py:109`](src/config_layer/state_contract.py:109) rejects any entry
  containing `= * / ( )` or whitespace — formula-injection guard
- [`state_contract_loader.py`](src/config_layer/state_contract_loader.py) then validates
  every `required_fm` against the ontology + `FORMULA_REGISTRY`, and every
  `config_keys` entry against `CRTConfig` fields

So `state_contracts` already stores *only* references, and a test proves it
stays that way. The three leaks below are all in **older sibling blocks in the
same file** that predate this discipline. This plan does not invent a pattern —
it finishes applying one.

---

## Where the architecture leaks today

### Leak 1 — runtime values inside WHO

`crt.runtime.thresholds` stores 48 typed defaults. Measured against the active
config: **41 agree, 5 disagree.**

```
WHO   body_ratio_min = 0.70
HOW   body_ratio_min = 0.65      ← what actually runs
```

The 5 that disagree are exactly the hashed `params` block — the *tuned* knobs:

| knob | WHO | HOW (live) |
|---|---|---|
| `body_ratio_min` | 0.70 | 0.65 |
| `atr_multiplier_min` | 1.50 | 1.00 |
| `retest_depth_max` | 0.25 | 0.15 |
| `retest_atr_depth_fraction` | 0.50 | 0.30 |
| `expansion_atr_min_distance` | 0.20 | 0.30 |

**This is not drift.** [`test_active_models_registry.py:17`](tests/test_active_models_registry.py:17)
deliberately pins key existence and never values: *"yaml documents code defaults;
config holds tuned overrides."* The policy is stated and intentional.

The problem is that the policy makes the numbers **unverifiable by construction** —
48 values no test can ever confirm, in the file every session loads first. A reader
cannot tell which of the two numbers is authoritative without leaving the file.

And the "code defaults" justification no longer holds: those values are a verbatim
copy of the `CRTConfig` dataclass field defaults —
[`state_identity.py:90-105`](src/config_layer/state_identity.py:90) declares
`body_ratio_min = 0.70`, `atr_multiplier_min = 1.50`, `retest_depth_max = 0.25`,
`expansion_atr_min_distance = 0.20`, `retest_atr_depth_fraction = 0.50`. The code
default already has a home. **Removing the YAML copy loses no information.**

The same numbers appear a *third* time in `crt.runtime.detection.*.defaults`
(9 values across the displacement / expansion / retest / expired blocks).

### Leak 2 — formula knowledge inside WHO

`feature_lineage` carries 38 rows, each with a `formula` string. **21 of those 38
names already have a formula in the ontology**, and WHO's copies are lossy
paraphrases:

| | WHO says | WHAT says |
|---|---|---|
| `atr` | `ATR(14)/close` | `SMA(atr_period) of true_range … NOT Wilder` |
| `session` | `hour buckets Asia/London/NY` | explicit cutoffs + `config_keys` + the 4-way collision note |
| `disp_strength` | `body_size/(atr*close) clip[0,3]` | same, with config-key tokens for the clip bounds |

`"ATR(14)"` is precisely the ambiguity the ontology's `IND-001`
`false_claims_corrected` block exists to kill ("production ATR == SMA-of-TR, NOT
Wilder — do not silently substitute"). WHO reintroduces it, in a file loaded
earlier.

Instead of restating the mathematics, the row should point at it:

```yaml
- {index: 32, name: disp_strength, fm_id: FM-020, crt_state: RETEST, ...}
```

The ontology already owns the explanation. One place to improve documentation.

### Leak 3 — relationship lists repeated

Two blocks inside WHO answer the same question:

```
crt.state_contracts.SWEEP.config_keys   →  body_ratio_min, ...   (41 keys total)
crt.detection.displacement.config_keys  →  body_ratio_min, ...   (10 keys total)
```

The detection set is a subset of the contract set, re-listed per state. Only one
should own it; the other should reference it.

---

## What is *not* duplication — preserve this distinction

**Identity is not configuration.** These are different facts and neither replaces
the other:

```
CRT consumes body_ratio_min     ← identity   (belongs in WHO, stays)
body_ratio_min = 0.65           ← configuration (belongs in HOW, only there)
```

Keeping the config *key names* in WHO is the whole point — that is the reference
that links the layers. What leaves is the `default:` value beside the name.

Two more things that look like duplication and are not:

- **`params` (5 keys) vs `crt_engine` (45 keys)** — the key sets are **disjoint**.
  `CRTConfig` is assembled from their union. This is a split, not a copy. (The
  real defect in that area is F-057: a *third* source, the hardcoded
  `market_router` profiles, wins on the programmatic `BacktestRunner` path. Out of
  scope here.)
- **Ontology `indicator_identities` (IND-001/002) vs `rolling_indicators`
  (FM-041/042)**, and **`migration_candidates` (FM-030/031) vs `derived_metrics`
  (FM-022/023)** — retained superseded records under §6.2 rule 4 (append
  discipline, never delete truth). These stay. They are correctly labelled
  "descriptive history only."

---

## The design direction

| Layer | Owns |
|---|---|
| **WHAT** | mathematical definitions, formulas, dependencies, feature lifecycle |
| **HOW** | every runtime value, threshold, weight, switch, path |
| **WHO** | model identity, intent, ownership, evidence, feature *references*, runtime *references* |

What disappears: duplicate thresholds, duplicate formulas, duplicate config-key
lists. What remains are references.

```
WHO   uses: FM-020, body_ratio_min
        ↓                ↓
WHAT  FM-020 = ...   HOW  body_ratio_min = 0.65
```

Every question then has exactly one authoritative answer:

- *What does it mean?* → WHAT
- *What value does production use?* → HOW
- *Who uses it and why?* → WHO

---

## Implementation

Scope is **one file** (`active_models.yaml`) plus its guard tests. No runtime
surface: nothing under `src/` reads any of the three leaked fields — verified by
grep across `state_contract_loader.py`, `state_contract.py`, `state_topology.py`,
`model_resolver.py`, `model_paths.py`. Only two tests read them, and only for key
existence.

### Step 1 — Leak 1: drop stored values, keep the names

In [`active_models.yaml`](active_models.yaml):

- `crt.runtime.thresholds` — replace each `{ type: …, default: … }` map with a
  plain key list under a renamed `config_keys:` block. The `type:` field goes too;
  `CRTConfig`'s annotations already declare it.
- `crt.runtime.detection.*.defaults` — delete the 4 blocks outright. Each detection
  block already carries `config_keys`, which is the reference that survives.
- Leave `session_windows` / `allowed_sessions` as key names only.

Result: ~48 unverifiable numbers removed; `state_identity.py` becomes the single
answer for "what does the code default to," the active config the single answer for
"what runs."

### Step 2 — Leak 2: reference the ontology instead of paraphrasing it

In `feature_lineage.features`, replace the `formula:` string with `fm_id:` for the
21 rows that resolve to a registered ontology entry. For the 17 that do not yet
have an FM id (raw passthroughs and unregistered structure flags), keep the
`formula:` string and mark them — that gap is itself useful signal about ontology
coverage, so surface it rather than hiding it.

Keep everything else in the row untouched: `index`, `name`, `provenance`,
`crt_state`, `consumers`, `fusion_weight`, `role`. Those are identity.

### Step 3 — Leak 3: one owner for config-key lists

Make `crt.state_contracts.*.config_keys` the sole owner (it is already the
load-validated block). Remove `config_keys` from `crt.runtime.detection.*`, whose
per-state keys are a subset. Detection blocks keep `method`, `file_line`, `logic`,
`ohlcv_inputs` — the things only they own.

### Step 4 — retarget the guards

- [`test_active_models_registry.py:255`](tests/test_active_models_registry.py:255)
  `test_yaml_config_keys_exist_in_schema` — currently reads `thresholds` keys and
  `detection.*.config_keys`. Point it at the new `config_keys` block +
  `state_contracts`. The assertion itself (every declared key resolves to a
  `CRTConfig` field / `params` / `crt_engine`) is unchanged and still the right one.
- [`test_active_models_registry.py:288`](tests/test_active_models_registry.py:288)
  `test_feature_lineage_fields_and_provenance_resolve` — add: if a row has `fm_id`,
  it must resolve in `FORMULA_REGISTRY`; a row may not carry both `fm_id` and
  `formula`.
- **New floor** — assert no numeric literal survives anywhere under `crt.runtime`
  outside `state_contracts`. This is the generalisation of the existing
  `state_contract.py:98` rule from one block to the whole WHO layer, and it is what
  stops the leak from reopening.
- Update the file-header comment in `test_active_models_registry.py:17` — the
  "yaml documents code defaults" rationale no longer applies once the defaults are
  gone.

### Step 5 — record the decision

Per §6.2 rule 4 / the Documentation Drift Protocol: this changes no conclusion and
no runtime value, so it is an unambiguous `DOC_DRIFT` auto-fix class — but the
*rule change* (WHO may not store values) is a durable doctrine addition. Record it
in `docs/topics/model-intent-and-feature-ownership.md` (the human-source the
lineage block already names) and append the SESSION LOG entry.

---

## Verification

Byte-level proof that nothing behavioural moved — the point of the change is that
this is impossible to get wrong, and these commands demonstrate it.

Guards, before and after:

```bash
python -m pytest tests/test_active_models_registry.py tests/test_crt_state_invariants.py tests/test_ontology_config_parity.py tests/test_doc_citations.py -q
```

The state-contract loader still builds (proves the reference graph still resolves):

```bash
python -c "from src.config_layer.state_contract_loader import load_state_contracts; b=load_state_contracts(); print(len(b.contracts), 'contracts OK')"
```

Runtime is untouched — the config the engine actually reads is not edited, so the
config hash must be unchanged and a backtest must be byte-identical:

```bash
python -c "import json;d=json.load(open('configs/production/v2_multi_2026_04.json'));print(d['config_hash'])"
```

```bash
python scripts/analysis/behavior_census.py
```

Full regression before closing:

```bash
python -m pytest tests/ -q
```
