# BitNet Qualification Protocol — `BN_QUAL_V1`

> **What this is.** The gate ladder BitNet must climb before any binding influence on the spine.
> Sibling of [`tradenet_qualification_protocol.md`](tradenet_qualification_protocol.md)
> (`TN_QUAL_V1`), whose structure and status vocabulary this reuses verbatim.
>
> **Created:** 2026-07-29 · **Status: OPEN at GATE-0.** `use_bitnet` remains `false`.
> Grants **no** authority (CLAUDE.md §6.5).
>
> **Why this exists.** BitNet already has a **negative** shadow result (F-055) that a formal gate
> should have caught *before* the measurement was framed as an enable/disable question. TradeNet
> had a protocol; BitNet did not. This closes that asymmetry.
>
> **Scope.** This protocol governs the **evidence-consumer redesign** proposed in
> [`bitnet-design-specification.md`](../architecture/bitnet-design-specification.md). It does
> **not** grant a path to re-enable the *current* raw-feature gate — that path is closed by F-055
> and stays closed.

---

## 0. Status vocabulary

Identical to `TN_QUAL_V1` §0. Reproduced for self-containment.

| Token | Meaning |
|---|---|
| **OPEN** | Gate incomplete; downstream gates forbidden. |
| **READY** | Mechanical prerequisites met; work may begin. |
| **PASS** | Criteria cleared with versioned evidence under a frozen `protocol_hash`. |
| **FAIL** | Criteria not met; remediate or stop (no silent weaken). |
| **INDETERMINATE** | Evidence unusable (contamination, underpower, harness bug). |
| **KEEP_CANDIDATE** | Offline discrimination survives prereg; **research-only**. |
| **RETIRE** | Clean-label evidence shows no usable discrimination. |
| **ACCEPTED** | Explicit leave-as-is for a **named scope** only. |
| **FEASIBLE_GO** / **FEASIBLE_DEFER** / **INFEASIBLE_STOP** | GATE-0 verdicts. |

---

## 1. Gate ladder (do not skip)

```text
GATE-A  Architecture decision — is the L3 redesign accepted at all?
   │
   ▼
GATE-0  Label feasibility (can an honest safety label be built?)
   │
   ▼
GATE-L  Authoritative labels + clean dataset on the EVIDENCE BUNDLE
   │
   ▼
GATE-O  Offline acceptance (discrimination on clean labels)
   │
   ▼
GATE-S  Shadow evaluation (score logged, zero decision weight)
   │
   ▼
GATE-P  Production (Channel A veto becomes binding)
```

| Gate | Unlocks | Does **not** unlock |
|---|---|---|
| **GATE-A** | MIAR amendment; dataset work | Any code on the spine |
| **GATE-0** | Funding for a clean-label builder | Train; KEEP/RETIRE; spine work |
| **GATE-L** | Offline training on clean y | Wire; economic claims |
| **GATE-O** | KEEP_CANDIDATE / RETIRE; shadow eligibility | Spine influence |
| **GATE-S** | Measured ΔG001 evidence | `use_bitnet=true` by default |
| **GATE-P** | Channel A binding veto | Multi-instrument rollout without per-instrument GATE-S |

**`BN_QUAL_V1` adds GATE-A ahead of `TN_QUAL_V1`'s ladder.** TradeNet's architectural slot was
never in dispute — only whether the model earned it. BitNet's *slot itself* is the open question,
so the architecture decision is gated first. Doing GATE-0 work before GATE-A would be building
labels for a layer that may not exist.

---

## 2. GATE-A — Architecture decision

**Question:** is BitNet-as-evidence-consumer accepted as the target design?

Required to PASS:

1. [`bitnet-design-specification.md`](../architecture/bitnet-design-specification.md) reviewed and
   accepted by the owner.
2. The `bitnet-cpp-specification` §8.2 *"new product decision"* clause explicitly satisfied and
   recorded — not assumed.
3. Relationship to HMF stated and agreed (topology §4: separate channels).
4. Relationship to the open CRT monolith ruling stated — GATE-A may PASS **independently** of that
   ruling, but must name the dependency.

**Forbidden at GATE-A:** any code change; any config change; enabling `use_bitnet`; deleting the
existing in-FSM call site before GATE-P.

---

## 3. GATE-0 — Label feasibility

The current label contract is `BITNET_LABEL_ATR_RACE_BULL_V1`: win if `high` reaches
`close + 2·ATR` before `low` reaches `close − 1·ATR` within 40 bars. It is **bullish-only** and
carries `economic_authority: DIAGNOSTIC_ONLY`.

Questions that must be answered with evidence:

1. **Is a bidirectional safety label constructible?** A bull-only label cannot supervise a veto
   that must fire on short setups too.
2. **Does "unsafe" have an honest definition distinct from "loses money"?** If unsafe ≡ negative
   expectancy, BitNet is a duplicate of the entry-information problem already falsified across
   F-019 … F-035, and the correct verdict is `INFEASIBLE_STOP`.
3. **Is the label derivable via `forward_walk(intrabar_fixed)`** rather than from the
   `opportunities.jsonl` stream? F-022 established that stream is a *detection* stream, only
   36.8 % self-consistent. F-041B and F-045 both show contamination flipping conclusions.
4. **Is there enough signal per instrument?** F-019 recorded 5–13 spine entries per instrument —
   below any trainable threshold. State-level labels (not trade-level) may be required.

Verdict rules mirror `TN_QUAL_V1` §2.2.

> **Question 2 is the one most likely to stop this program**, and stopping there would be a
> **high-ROI null** (CLAUDE.md §6.1), not a failure.

---

## 4. GATE-L — Clean labels on the evidence bundle

**Forbidden as primary `y`:** `opportunities.jsonl` `outcome` / `rr_achieved` (F-022);
`rr_model.json` training labels (F-045); any label whose provenance is a stored field rather than
a re-derived forward walk.

**Required:** labels re-derived through `forward_walk(intrabar_fixed)` with declared costs;
bidirectional; feature matrix built from the **L2 evidence bundle** (§3.1 of the design spec), not
from raw candles. PIT-honest — no centered-swing contamination (F-051).

---

## 5. GATE-O — Offline acceptance

Metrics mirror `TN_QUAL_V1` §6: AUC vs a shuffle control, rank-IC, top/bottom-decile separation,
time-series CV (never random-split).

`BN_QUAL_V1` **additional** requirements, both specific to a safety layer:

- **Asymmetry check.** A veto is only useful if the bottom decile is genuinely worse than
  baseline. Top-decile lift is irrelevant and must **not** be reported as success.
- **Non-redundancy vs `UltronRiskGate`.** Rejections must not be substantially the same set the
  risk gate already rejects. A second safety authority that fires on the same candidates earns
  nothing. This check has no `TN_QUAL_V1` analogue — TradeNet had no incumbent to duplicate.

---

## 6. GATE-S — Shadow

Runs through `scripts/research/model_shadow_protocol.py`.

**Invariants:**

1. Score computed and logged; **zero** decision weight.
2. Score stamped into `TradeProvenanceV1` on every candidate.
3. `use_bitnet` stays `false`. The shadow arm must not run through the in-FSM call site.
4. Both arms measured on identical corpora with identical costs and exits.

**PASS criteria:**

- ΔG001 > 0 pooled, **and** no instrument materially harmed.
- n ≥ 30 per arm. F-055 was underpowered at n < 30 and is explicitly *not* a template for
  sufficiency.
- Because vetoes only remove trades, the report must show the **removed** set was worse than the
  retained set — not merely that fewer trades were taken.

---

## 7. GATE-P — Production

Channel A becomes binding. Checklist mirrors `TN_QUAL_V1` §8.2, plus:

- The in-FSM call site in `crt_engine_v2` is **removed**, not merely bypassed.
- `model-responsibility-matrix.md` R6 (mutate CRT state) flips 🟡 → ➖ with the removal as evidence.
- Config-declared enable flag with a strict `_require` read — no silent default (CLAUDE.md §6.5).
- Per-instrument GATE-S PASS before per-instrument enablement.

---

## 8. Current status

```text
BITNET_SPINE_STATUS        = IN_FSM_GATE      # current placement, not the target
BITNET_LINEAGE_STATUS      = INERT + CONDITIONAL_SKEW
BITNET_QUAL_PROTOCOL       = BN_QUAL_V1
BITNET_GATE_A_STATUS       = OPEN             # design spec PROPOSED, not accepted
BITNET_GATE_0_STATUS       = BLOCKED_UNTIL_A
BITNET_GATE_L_STATUS       = BLOCKED_UNTIL_0
BITNET_GATE_O_STATUS       = BLOCKED_UNTIL_L
BITNET_GATE_S_STATUS       = BLOCKED_UNTIL_O
BITNET_GATE_P_STATUS       = BLOCKED_UNTIL_S
BITNET_USE_FLAG            = false            # unchanged, all gates
BITNET_PRIOR_SHADOW        = F-055 NEGATIVE   # raw-feature design, deltaE = -0.133R, 0/4 improved
```

**Nothing has been run under this protocol.** F-055 predates it and measured the *current*
design, not the proposed one — it is the motivation for this ladder, not evidence within it.

---

## 9. Forbidden substitutions

1. Re-enabling the **current** raw-feature gate under this protocol. Closed by F-055.
2. Treating F-055 as GATE-S evidence for the redesign — different input space, different layer.
3. Transferring weights from the 6-input model to an evidence-bundle model.
4. Reporting top-decile lift as safety-layer success (§5).
5. Skipping GATE-A because the code change looks small.
6. Weakening a threshold to obtain a PASS. Remediate or stop.
