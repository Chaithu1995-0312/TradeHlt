# Session Documentation-Drift Audit — 2026-07-19

Point-in-time record (§6.2 rule 5 — `docs/analysis/` is the home for non-living, session-scoped
documents). Consolidates every documented-vs-actual mismatch surfaced across this session, its
resolution, and the prevention shipped. Living conclusions live in
[`docs/current-findings.md`](../current-findings.md); this is the audit trail.

## Root cause (one sentence)

Every wrong call this session came from **repeating a claim read from a comment / note / status
line instead of verifying it against code.** Each was fixed the same way: grep/read the source. A
comment is *data*, not truth.

## Ledger

### Corrected this turn (were still OPEN)
| # | Drift | Location | Resolution |
|---|---|---|---|
| B1 | Stale docstring "Swing detection uses center=True … for live inference replace with a trailing-only swing detector" — contradicts the shipped FC1-A causal binding | `src/features/feature_pipeline.py:43-44` | Rewrote to reflect FC1-A: production binds causal-delayed (`.shift(k)`); centered is research/legacy; no separate live detector needed. History noted inline. |
| B2 | FM-052 `note` said "cutoffs remain hardcoded … so no config_key" while the entry declares `config_keys` and the formula uses the tokens | `configs/formulas/market_ontology.yaml` (session/FM-052) | Corrected the note; the false clause removed and paraphrased (not re-typed) so the guard below stays green. |
| B3 | Tracker self-contradiction: `:102` "never ran / PAUSED" vs `:1121` "already ran §13" | `docs/implementation_plan/feature-layer-tracking-2026-07-19.md` | Reconciled `:102` to "RAN 2026-07-19 (§13), 0 trades off-session, closable"; PAUSED history preserved. |
| B4 | §6.3 citation drift surfaced by the gate: `live_engine_hook.py:523 · process` — the T-11 edit moved `process` to `:646` and didn't sync the citation | `docs/architecture/entry-exit-map.md:29,63` | Updated both `:523 · process` → `:646 · process` (sole `def process`); `test_doc_citations` green. Pre-existing (from earlier-session T-11 work), caught this turn. |

### Already reconciled before this turn — verified, no action (the discipline in action)
| # | Item | State found |
|---|---|---|
| A1 | T-9 "MACD deferred to B2/B3" | Ontology comment corrected inline (`market_ontology.yaml:578`) AND tracker already marked **DONE 2026-07-20** (§20). Re-verified before "fixing" — correcting it would have repeated the very mistake this task targets. |
| A2 | FM-050 `depends_on` false lineage (`atr` → `true_range`) | Already corrected in the ontology (`:502`,`:509`) with a clear note. The "false lineage claim, not the two my plan anticipated" — recorded here as the E-001 lesson; no new tracker line (avoids redundant doc surface, §6.2 rule 5). |

### My own overclaims — CORRECTED at source earlier this session (listed for completeness)
- "warmup drops 6.4% / 254 rows" → **78 rows / 1.98%** (SF-006, source + finding corrected).
- "two partial-TP blend sites" → **three** (`backtest_v2.py:2426` missed; caught only by a source-grep assertion).
- "the XAUUSD window is a good parity gate" → **0 trades** (all off-session) → false-green trap; switched to BNBUSDT.
- "byte-identity is sufficient" → it only proves neutrality on paths the corpus **exercises**.

### Findings recorded this turn (Findings-Mandate catch-up — §6.2)
Three real architecture/governance findings from this session had never been written into the
record. Now minted as durable F-ids (indexed in CLAUDE.md + enforced by `test_current_findings`):
- **F-056** (ARCH, VALIDATED) — `backtest_v2` three undeclared trade-affecting constants; the
  `partial_tp_fraction` read-then-discard config illusion; REMEDIATED.
- **F-057** (ARCH, OPEN) — CRTConfig programmatic-path split-brain (`market_router` 0.08 vs JSON 0.30).
- **F-058** (GOV, OPEN) — `BACKTEST_ENGINE_GATE` code default ON vs documented OFF; TruthConflict.

## Prevention shipped

`tests/test_ontology_config_parity.py` **Rule F** (`test_note_does_not_deny_a_declared_config_binding`):
an entry that declares `config_key`/`config_keys` may not carry a `note` claiming "no config_key".
This is the exact gap FM-052 slipped through — Rule D checks only that tokens *resolve*, Rule E only
inspects the *formula*; nothing checked a **note** *negating* a declared binding. Proven RED against
the pre-fix FM-052 wording, then green.

Deferred (recorded, not built this pass): a `depends_on`-vs-code check (would have caught FM-050's
`atr`/`true_range`) and a tracker-status-vs-source lint (would have caught T-9/T-12). See the plan.
