# RC-003 — are these a distinct object at all?

**Authorized by the Principal 2026-09-04**, following RC-002's `INSUFFICIENT EVIDENCE` closure
(`RC-002-DEC-CHATGPT-002`). **PL-0 · `economic_claims_allowed: false`.**

## Why this is not a continuation of RC-002

`RC-002-DEC-CHATGPT-002` requested **no grant** and set the condition for any follow-on: it must be a
**new evidence cycle**, because continuation smuggles in the premise that something is there to find.

So RC-003 does **not** ask what these bars are. It asks **whether they are a distinct market object
at all** — with `NOT_A_DISTINCT_OBJECT` a live, pre-registered outcome that the design expects to be
unable to reject.

## Shape of the cycle — no relay

The relay produced the design; re-running it on its own design risks self-confirmation. Principal's
decision: **build → freeze → approve → run.** Adversarial review is reserved for interpretation.

| Step | Artifact | Status |
|---|---|---|
| 1 | Additive resolver evidence capture (`crt_state_resolver.py`) | built, decision-neutrality proven |
| 2 | Frozen pre-registration | `docs/research/preregistration-rc003-distinct-object.md`, sha `0102f9dc…` |
| 3 | Driver | `src/research/rc003_distinct_object/driver.py` + thin wrapper `scripts/research/rc003_distinct_object.py` |
| 4 | Floor | `tests/research/test_rc003_distinct_object.py` |

**The pre-registration was frozen and its sha recorded while the driver did not yet exist** — the
F-083 ordering, provable rather than asserted. The driver verifies that sha at run time and aborts if
the frozen text changed.

## What it inherits from RC-002, and from whom

- **Grok** (`RC-002-PROP-GROK-001`) — the geometric falsifier and its kill map; the five candidates;
  `UNKNOWN` as the honest default.
- **Gemini** (`RC-002-CRIT-GEMINI-001`) — the duration test, the CONTINUATION control group, the
  power floor (150–200 raw per group), the corpus recommendation, the pre-registration minimum.
- **DeepSeek** (`RC-002-CRIT-DEEPSEEK-001`) — the contamination rule that governs which metrics are
  admissible at all: anything touching the sweep-vs-candle *direction* relationship is contaminated
  by the selection rule. Both RC-003 metrics are unsigned with respect to it.

## Two things RC-003 fixes that RC-002 could not

1. **The referent.** `range_h_ref` / `range_l_ref` — what `_detect_htf_range_sweep` actually tests
   against — existed as memory fields and were never exposed, so RC-002 could only proxy them. The
   additive capture emits them. **Both referents run, pre-registered, and their disagreement is a
   declared output**, not a robustness footnote.
2. **The corpus.** Moves to the Phase-1 **admitted** corpus (47,275 bars, sha `4d73f5ce…`), retiring
   the standing caveat that every number in this thread sat on a non-admitted one-month export.
   **Stated plainly in the pre-registration:** Phase-1 ends 2026-05-21 and RC-002's window is
   2026-07-07 → 08-06, so they do **not** overlap. The original 32 bars are not in this corpus. This
   is a **replication on a different population, not an extension** — which is what
   "must justify itself independently" requires.

## Also corrected in passing

The RC-002 harness recomputed `sweep_sig` by calling `_detect_htf_range_sweep` from **outside**,
**after** `resolve()` had already mutated memory. The new capture records it from inside, at the
moment the resolver uses it. Measured on the RC-002 window: **100% agreement on all 1,855 bars where
both are defined, zero disagreements** — but the outside method counted **203** non-zero signals to
the inside method's **202**. One bar had a computable signal that `resolve()` short-circuited before
ever consulting. Not a reversal; a precision gain, and it means "203 sweep events" was one too many.

## Run it

```bash
python scripts/research/rc003_distinct_object.py \
  --corpus data/mt5/XAUUSD_M15.csv \
  --out docs/research-readiness/rc003_distinct_object
```

## Stop conditions — binding, from the frozen text

- Raw n < 150 in either group → `INSUFFICIENT`, no claim.
- Primary null **and** duration null → `NOT_A_DISTINCT_OBJECT` is not rejected, identity stays
  `UNKNOWN`, **RC-003 closes and no further cycle opens on this population.**
- No secondary test may be fished from the results. D-16 holds: no directional expectancy on these
  bars.
- **A null is a result.** It is registered, not re-cut.

## Ceiling — unchanged at every outcome

No ontology edit, no new `CRTState`, no `when:` predicate, no retune of
`_displacement_entry_allowed`, no F-074 change, no config or `ACTIVE_VERSION` change. Even a decisive
positive earns *information*, never authority (§6.5).
