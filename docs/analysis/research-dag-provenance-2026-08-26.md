# Research Provenance DAG — can any architectural decision be traced back to its origin?

> **Point-in-time audit, 2026-08-26.** Not a living doc. Not current truth about anything except
> the state of the record on this date.
>
> **Authority:** research / governance only. Grants no production authority, no G001, no
> ontology node, no config change (CLAUDE.md §6.5). No finding is registered by this study.
>
> **Machine-readable artifact:** [`../governance/research_dag_provenance-2026-08-26.json`](../governance/research_dag_provenance-2026-08-26.json)
> (pointer: [`research_dag_provenance.LATEST.json`](../governance/research_dag_provenance.LATEST.json)) ·
> **Extractor:** [`scripts/analysis/research_dag_provenance.py`](../../scripts/analysis/research_dag_provenance.py) ·
> **Floor:** [`tests/test_research_dag_provenance.py`](../../tests/test_research_dag_provenance.py) (25 tests) ·
> **Change contract:** `CH-research-dag-provenance`

---

## 1. The question, and the rule that governs the answer

For every architectural decision in this repository's history, four questions:

1. what **hypothesis** originated it?
2. what **finding** originated it?
3. what **evidence** originated it?
4. what **measurement basis** originated it?

Each answer is one of three classes: **EXPLICIT** (the record names it and the name resolves),
**INFERRED** (the link exists only through a third artifact; neither endpoint cites the other),
**UNKNOWN** (the record does not carry the link).

**GAPS ARE THE RESULT.** No edge is backfilled, guessed, or filled from a sibling artifact. Where
the answer is UNKNOWN it is left UNKNOWN, and that is the finding rather than a defect in the
instrument. This is enforced mechanically: `test_unknown_edges_are_never_silently_populated`.

## 2. Headline

**1,170 decisions × 4 slots = 4,680 provenance edges.**

> The audit counts its own SESSION LOG entry as node 1,170. The corpus is the live record, and
> exempting this turn would have been exactly the kind of quiet exception the audit is measuring.

| Class | Edges | Share |
|---|---:|---:|
| EXPLICIT | 871 | **18.61 %** |
| INFERRED | 849 | **18.14 %** |
| UNKNOWN | 2,960 | **63.25 %** |

Read as one sentence: **fewer than one provenance link in five is explicitly recorded, and
almost two in three cannot be recovered from the record at all.**

The blended number hides the real structure, which is that the four slots are not remotely
comparable:

| Slot | EXPLICIT | INFERRED | UNKNOWN |
|---|---:|---:|---:|
| `originating_finding` | 37.01 % | 27.78 % | 35.21 % |
| `originating_evidence` | 36.07 % | 14.79 % | 49.15 % |
| `originating_hypothesis` | **1.37 %** | 30.00 % | 68.63 % |
| `originating_measurement_basis` | **0.00 %** | **0.00 %** | **100.00 %** |

The findings layer is the only one that half-works. The hypothesis layer is almost entirely
reconstructed after the fact. **The measurement-basis layer is not thin — it is empty.**

## 3. The DAG

```mermaid
graph RL
  subgraph DEC["DECISIONS · 1,170"]
    S["DECISION_SESSION<br/>1,052 entries<br/>2026-04-10 → 2026-08-26"]
    C["DECISION_CH<br/>88 build manifests"]
    P["DECISION_PROMOTION<br/>15 promotion-log events"]
    L["DECISION_CLOSURE<br/>15 closure surfaces"]
  end

  F["FINDING · F-001…F-094<br/>93 records"]
  E["EVIDENCE<br/>docs/analysis · results · tests<br/>scripts/analysis · scripts/research"]
  H["HYPOTHESIS · H-001…H-020<br/>20 records<br/><b>18 back-seeded 2026-07-03</b>"]
  M["MEASUREMENT BASIS<br/>15 MC-*/MP-* on disk<br/><b>0 with a proven run</b>"]
  X(["PRE_REGISTRY_ORIGIN<br/>197 decisions<br/>no H-* exists"])

  S -- "E2 · 433 explicit" --> F
  C -- "E1 · objective cites F-id" --> F
  S -- "I3 · 325 same-date only" -.-> F
  S -- "E2 · 422 explicit path" --> E
  C -- "E1 · affected_files" --> E
  S -- "I5 · 173 via a cited finding" -.-> E
  F -- "I1 · 130 registry back-seed" -.-> H
  F -- "I2 · 221 family judgement" -.-> H
  DEC -- "E2 · 16 direct H-id cites" --> H
  F x-- "U1 · Contract: UNKNOWN ×82" --x M
  DEC x-- "U4 · named, never executed ×56" --x M
  DEC -- "U2 · 803 no H reachable" --> X

  classDef dead fill:#00000000,stroke-dasharray:4 3;
  class M,X dead;
```

Solid = EXPLICIT · dashed = INFERRED · `x--x` = the link is declared but does not carry.

## 4. Classifier

Ordered rules, first match wins, each edge records the `rule_id` and a **`witness`** — the literal
field or matched substring that justified the verdict, so every classification is auditable back
to a byte in a named file.

| Rule | Class | Fires when | Count |
|---|---|---|---:|
| `E1_STRUCTURED_FIELD` | EXPLICIT | dst named in a dedicated field (`Contract:`, `affected_files[]`, `objective`, `authoritative_artifact`) **and** it resolves | 82 |
| `E2_INLINE_CITATION` | EXPLICIT | dst id/path cited verbatim in the body **and** it resolves | 789 |
| `I1_HYPOTHESIS_BACKSEED` | INFERRED | reached only via `hypothesis_registry.findings[]` | 130 |
| `I2_FAMILY_JUDGEMENT` | INFERRED | reached only via a `research_family_registry` cell `claims[]` | 221 |
| `I3_DATE_COLOCATION` | INFERRED | decision and finding share a date; neither cites the other | 325 |
| `I4_FILE_OVERLAP` | INFERRED | manifest declares only non-evidence-class tracked paths | **0** |
| `I5_VIA_CITED_FINDING` | INFERRED | evidence reached one hop through a cited finding | 173 |
| `U1_DECLARED_UNKNOWN` | UNKNOWN | the slot field literally reads `UNKNOWN` | 380 |
| `U2_NO_CANDIDATE` | UNKNOWN | no rule produced any candidate | 2,317 |
| `U3_DANGLING_CITATION` | UNKNOWN | cited, but nothing resolves | 207 |
| `U4_DECLARED_NOT_EXECUTED` | UNKNOWN | a basis is named but no run is proven | 56 |

`I4` fires **zero** times on the real corpus and is reported as zero rather than dropped —
every manifest declares at least one evidence-class file, so the rule is defined but unexercised.
It is kept reachable by a synthetic fixture so it cannot rot into dead code.

Three precedence decisions do real work:

- **A dangling citation never scores EXPLICIT.** Citation is not traceability. But a bad citation
  beside a good one does not erase the good one — the resolvable link wins and the dangling id is
  recorded in `dangling_also_cited`, so neither is hidden.
- **A manifest listing its own path is bookkeeping, not evidence.** `docs/governance/build_manifests/`
  is excluded from evidence candidates, and so is the node's own `source_path`.
- **`src/` and `configs/` are change targets, not evidence.** Including them would have inflated
  the evidence slot with the files a decision *edited* rather than the artifacts that *justified* it.

## 5. Where the mass sits

### By decision type

| Type | Decisions | EXPLICIT | INFERRED | UNKNOWN |
|---|---:|---:|---:|---:|
| `DECISION_CLOSURE` | 15 | 31.67 % | 21.67 % | 46.67 % |
| `DECISION_CH` | 88 | 28.12 % | 11.93 % | 59.94 % |
| `DECISION_SESSION` | 1,052 | 17.87 % | 18.85 % | 63.28 % |
| `DECISION_PROMOTION` | 15 | **1.67 %** | 1.67 % | **96.67 %** |

The promotion log — the only surface that changes what production actually runs — is the least
traceable object in the repository. Its lines carry three fields (`event`, `reason`, `timestamp`)
and nothing that binds a promotion to the evidence it was promoted on.

### By era, and across the Gate-6 boundary

| Era | Decisions | EXPLICIT | INFERRED | UNKNOWN |
|---|---:|---:|---:|---:|
| E1 Foundation & enhancement | 16 | 0.00 % | 0.00 % | **100.00 %** |
| E2 Agent + sprints + integration | 57 | 7.02 % | 0.00 % | 92.98 % |
| E3 CRT optimization Phases 0–6 | 17 | 1.47 % | 0.00 % | 98.53 % |
| E4 Governance + dual-track | 3 | 8.33 % | 0.00 % | 91.67 % |
| E5 Research-falsification + config-first | 154 | 23.54 % | 21.27 % | 55.19 % |
| POST_ERA_5 (2026-06-27 →) | 863 | 18.45 % | 20.31 % | 61.24 % |
| UNDATED (no parseable `Date:`) | 60 | 29.58 % | 7.08 % | 63.33 % |

`docs/timeline.md`'s era list stops at 2026-06-26, so 863 of 1,170 decisions — 74 % of the corpus —
fall outside every declared era. The label is `POST_ERA_5`, not a sixth era invented here.

**Gate 6 (BUILD_IMPACT_MANIFEST, 2026-07-08) did not move the explicit rate.**

| | Decisions | EXPLICIT | INFERRED | UNKNOWN |
|---|---:|---:|---:|---:|
| pre-Gate-6 | 307 | 17.67 % | 15.23 % | 67.10 % |
| post-Gate-6 | 803 | **18.15 %** | 20.08 % | 61.77 % |

UNKNOWN fell 5.3 pp, but essentially all of that went to **INFERRED** (+4.9 pp), not to EXPLICIT
(+0.5 pp). The formal manifest regime made links more *derivable*; it did not make them
*recorded*.

## 6. The terminus — tracing back to the earliest hypotheses

The `H-*` registry begins **2026-07-03**, and 18 of its 20 records were authored on that single
day about work already completed. Tracing backwards therefore does not arrive at hypotheses; it
arrives at a wall.

| Backward reachability to an `H-*` | Decisions |
|---|---:|
| Explicit `H-id` cited | **16** |
| Reached only via the registry's back-seed (`I1`) | 130 |
| Reached only as a family-level *question* (`I2`) | 221 |
| No hypothesis reachable at all | **803** |

**197 decisions predate the first hypothesis and have no `H-*` reachable.** What they *do* carry
is programme labels, extracted from their own text and never invented:

`Phase 1` ×17 · `Phase 2` ×12 · `Phase 3` ×12 · `Phase 5` ×11 · `Phase 4` ×9 · `Phase 6` ×7 ·
`Sprint 6` ×5 · `Phase 0` ×5 · `Phase 3b` ×5 · `Phase 5a` ×5 · `Sprint 4/5/7` ×4 each ·
`Phase 8` ×4 · `Phase 2b` ×4 · `Phase 9A` ×3 · `Phase 4b` ×3 · `Sprint 2/3` ×3 each ·
`ENHANCEMENT_IMPLEMENTATION_PLAN` ×2 · `Phase 0b` ×2 · `Phase 5c` ×2 · `Sprint 1` ×2 ·
`Program 1` · `Phase 5b` · `Phase 6b` · `Phase 7` · `Phase 9B` · `Trd-M6`.

These are the **actual** earliest origins: numbered execution phases and sprints, with no
falsifiable statement attached to any of them. The oldest layer of the architecture was built
against a plan, not against a hypothesis — which is a legitimate way to build software and an
illegitimate basis for a research claim. The distinction matters only where those decisions are
later cited as evidence.

## 7. Structural gaps found (recorded, not filled)

1. **The measurement layer has never executed.** `configs/research/measurement_result_log.jsonl`
   contains only its meta line, `sealed_pass_bound: 0`. Fifteen `MC-*`/`MP-*` contracts exist on
   disk; **zero** have a proven run. Every `originating_measurement_basis` edge in the repository
   is therefore UNKNOWN — 1,170 of 1,170.
2. **82 findings declare `Contract: UNKNOWN`**; 2 terminal findings (F-003, F-007) carry no
   `Contract` field at all; 9 name one. Of those 9, **6 are bare sha256 strings** (F-081, F-090…F-094)
   that resolve to no sealed instance on disk — only F-082 (`MP-METALS-MT5`), F-083 and F-084
   (`MC-VCRT-XAUUSD-M15-V1/V2`) name a resolvable id, and none of the three has an execution record.
3. **The GENERATED findings export drops the two fields this audit needed.**
   `governance.findings_export._FIELDS` omits **`Contract`** and **`Family`**, so
   `data/findings.jsonl` — the machine-readable findings view named in CLAUDE.md §2 as a truth
   artifact — cannot answer "what measurement basis?" or "what research family?" at all. This
   extractor reads both from the authoritative doc instead, and says so rather than working
   around it silently. *Not fixed here: editing the exporter is outside this change contract.*
4. **207 dangling citations** — a name is given and nothing resolves: 193 on evidence, 11 on
   measurement basis, 3 on findings. A further 151 dangling references appear *beside* a
   resolvable one (146 evidence, 5 finding) and are recorded rather than absorbed. Separately,
   **39 of 374** finding `evidence_paths` refs are not git-tracked, so they point at nothing from
   any other clone.
5. **47 of 88 build manifests have no completion record.** `validate-impact` was run; whether
   `validate-completion` ever passed is not recoverable from the manifest directory.
6. **60 session-log entries have no parseable `Date:` line**, so they cannot be placed in any era
   or joined to a same-day finding. Parse coverage is otherwise 1,052 of 1,053 loose markers
   (99.91 %); the single unparsed marker is reported, never absorbed.

## 8. Surfaced as TruthConflicts — NOT resolved here (§6.2 rule 3)

Each needs a user gate before any doc or code is edited.

**TC-1 · `docs/knowledge-map.md` overstates the SESSION LOG's citation discipline.**
Source A: knowledge-map.md — "Every entry is dated and cites the plan it executed, the analysis it
produced, and the finding it validated." Source B: this audit — 51 % of entries cite no typed ID
of any kind, 63.27 % of session-decision provenance edges are UNKNOWN, and 60 entries have no
parseable date. Impact: the doc describes a traversal that succeeds for a minority of entries.
Classification candidate: `DOC_DRIFT`. Recommendation: replace the universal claim with the
measured rate and cite this artifact.

**TC-2 · `assistant_project.md`'s doctrine header claims a scope the file does not hold.**
Source A: the header — "the permanent record of every session decision since April 2026."
Source B: the hot file's earliest entry is 2026-06-15; everything before it lives in
`docs/analysis/session-log-archive/`. Impact: a reader trusting the header would conclude the
April–June record is missing rather than archived. Classification candidate: `DOC_DRIFT` (scope
sentence). Recommendation: one clause naming the archive.

**TC-3 · Running the documented rotation remedy on `assistant_project.md` today would fuse 90
entries into the doctrine preamble.**
Source A: `rotate_session_log.py:_MARKER_RE` recognises only the `📝` and `??` marker forms.
Source B: the hot file carries 77 emoji-prefixed and **90 bare** `SESSION LOG ENTRY` markers
(168 total by a loose scan).

Measured, not inferred — a read-only probe calling the rotator's own `parse_log`/`render`:

```
markers in file (loose scan)          : 168
entries the rotator parses            :  78
markers swallowed into the PREAMBLE   :  90
rotator conservation guard would PASS : True
--keep 20 would rewrite the live file with 20 delimited entries
and a doctrine preamble grown from ~53 to 1,194 lines
```

**The conservation guard does not protect against this**, because it counts markers with the same
blind regex it parses with (78 == 78, so the abort never fires). No content would be deleted, but
90 entries would stop being addressable as entries — losing their `---` delimiters and merging
into the header block.

`tests/test_session_log.py::test_session_log_entry_count_is_bounded` is consequently **red and
tells you to run exactly this command** (78 emoji-visible entries against a cap of 30; it was
already red at HEAD with 77). *The rotator was deliberately NOT run in this turn.* Classification
candidate: `TEST / CONTRACT GAP`. Fix belongs in a separate authorized turn — widen `_MARKER_RE`
**and** make the conservation guard count with a regex independent of the parser's.

**TC-4 · The findings export field gap (§7.3).** Classification candidate: `TEST / CONTRACT GAP`
— `_FIELDS` and the findings-doc schema have diverged since the 2026-08-06 measurement-contract
work added `Contract:`/`Family:`, and no test compares them.

## 9. Scope and limits

- **This measures the RECORD, not the reasoning.** A decision can have been well-founded and
  poorly recorded. UNKNOWN means the link is unrecoverable from the artifacts, not that the work
  was unjustified. Nothing here downgrades any finding.
- **"Architectural decision" is defined by enumeration**, not judgement: every SESSION LOG entry,
  every build manifest, every promotion-log event, every closure surface. A session entry that
  recorded no architectural decision still consumes 4 slots and contributes UNKNOWN mass. The
  denominators are honest about what was counted; they are not a claim that all 1,170 units are
  equally consequential.
- **The evidence slot depends on a prefix convention** (§4). Widening it to `src/` would raise the
  explicit rate and mean less.
- **`I3_DATE_COLOCATION` is the weakest inference in the set** — same-day co-occurrence is
  suggestive, nothing more. It accounts for 325 of 849 INFERRED edges; if it were reclassified as
  UNKNOWN the overall UNKNOWN rate would rise to roughly 70 %.
- One instrument, one repository, one date. Re-running after any record-system change will move
  these numbers.

## 10. Reproduce

```bash
python scripts/analysis/research_dag_provenance.py --date 2026-08-26
```

Two runs on the same `--date` are byte-identical (`--date` is the payload's only clock). The floor
runs with `python -m pytest tests/test_research_dag_provenance.py`.
