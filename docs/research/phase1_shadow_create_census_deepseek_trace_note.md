# Phase-1 shadow CREATE census — DeepSeek-lane evidence trace

**Lane:** DEEPSEEK_EVIDENCE · **parallel lane:** GROK_ANALYSIS (same census, different method)
**session_run_id / parent_run_id:** `run_20260909_202201` · **source_run_id:** `run_20260906_013609`

**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · authority: none · no promotion

Unit = **CREATE** of HTF-displacement pending memory (n=69), NOT SHADOW→EXP restore (n=6).
The bottleneck is no longer object discovery; it is **which state bundle inside the 69 creations
carries the economic signal.** This note is the DeepSeek-lane verdict on that question, recorded as
**DeepSeek evidence** so the parallel Grok analysis can be cross-checked lane-to-lane.

## Question (frozen)

For each of the 69 creates, attach every keyword / state / threshold / formula output / FM-state /
SEM-state / T1 state / T3 state / parent CRT / session / direction to a forward outcome (H20
`close_at_horizon` · SEM-015 TIMEOUT · Always-Long control), compute expectancy vs the control, and
rank by **expectancy lift** — then name the state bundle that carries the signal.

## Headline H20 (memory_dir, on the same 69 creates + 4 no-direction)

| Arm | n | E | PF | WR | power |
|---|---:|---:|---:|---:|---:|
| memory_dir | 65 | -0.1577 | 0.885 | 0.569 | WEAK |
| trendbias_dir | 69 | +0.4924 | 1.494 | 0.522 | WEAK |
| always_long | 69 | +0.5650 | 1.591 | 0.609 | WEAK |

Lift = E(memory_dir | bucket) − E(always_long | same creates).

## DeepSeek trace — the state bundle that carries the signal

### 1. Only three state-style bundles show POSITIVE lift vs control

| Bundle | n | E | E_AL | lift | PF | power |
|---|---:|---:|---:|---:|---:|---:|
| t1_t3 = DISAGREE | 15 | +1.5017 | -0.2505 | **+1.7522** | 4.591 | INSUFFICIENT |
| session = LONDON_NY_OVERLAP_13_17 | 10 | +2.2483 | +1.0606 | **+1.1877** | 68.0 | INSUFFICIENT |
| atr_tercile = T2_MID | 20 | +0.2897 | -0.1563 | +0.4459 | 1.314 | INSUFFICIENT |

The largest growers — outcome=CLEARED_OR_OVERWRITTEN (+2.328) and outcome=RESTORED_TO_EXPANSION
(+1.844) — are **POST-HOC funnel outcomes, not pre-trade state bundles.** They are the *result* of
the memory lifecycle, not a condition an entry could select on. DeepSeek self-corrects here: do NOT
rank those two as the signal bundle. They are diagnostics only.

### 2. The strongest pre-trade co-occurring bundle

| Bundle | n | H20 memory_dir mean |
|---|---:|---:|
| ALL 69 (65 with dir) | 65 | -0.1577 |
| t1_t3 DISAGREE | 15 | +1.5017 |
| session LONDON_NY_OVERLAP | 10 | +2.2483 |
| **DISAGREE × LONDON_NY_OVERLAP** | **5** | **+3.5086** |

`created_idx` {7105, 9393, 10785, 16529, 21393} — the same 5 candles carry both states.

### 3. Power honesty (the binding constraint)

Every positive-lift cell is **n < 30 → INSUFFICIENT.** The only n ≥ 30 cells in the census
(AGREE n=50, RANGE_C1 n=45, EXPIRED_TTL n=45, pending_SHORT n=39, age_1 n=30) all carry
**NEGATIVE** lift (−1.447, −0.715, −2.128, −1.218, −0.574). So the signal, if real, lives in the
sparse positive-tag rows, which is exactly where the census has no power to certify it.

## DeepSeek verdict

- **Candidate signal bundle:** `t1_t3 = DISAGREE` (n=15, H20 memory_dir E=+1.50), reinforced by
  `session = LONDON_NY_OVERLAP_13_17` (n=10, E=+2.25); the co-occurrence `DISAGREE × LONDON_NY_OVERLAP`
  reaches E=+3.51 but at **n=5**.
- **Not the signal:** the two largest lift rows are funnel **outcome** tags (post-hoc), excluded by
  self-correction. `parent_crt=DISTRIBUTION_C3` (−2.175) and `session=ASIA_0_8` (−2.655) are the
  strongest anti-signal tags.
- **Power:** INSUFFICIENT across every positive cell. No bundle inside the 69 meets the n≥30 floor;
  the census cannot certify an economic signal, only name the candidate and its n.
- **Call:** CONSISTENT_WITH_CASE_A_DIRECTION_ONLY (interpretive) — the directional memory tag
  (pending_dir vs trend_bias) echoes the four-arm replay's Case-A pattern, but nothing promotes.

economic_claims_allowed = false. This is evidence, not a promotion.

## Cross-lane note (Grok parallel)

This is the **DeepSeek lane**. Grok is running the same 69-create census under a different method;
where Grok's verdict differs on *which bundle carries the signal*, record the `TruthConflict`
(source A: deepseek_trace.json, source B: <grok artifact>) and do not silently resolve it.

## Artifacts

- `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/census.json` (row-level, 69 rows)
- `results/analysis/phase1_resolver_replay/run_20260909_202201/create_economic_census/deepseek_trace.json` (this verdict)
- This note: `docs/research/phase1_shadow_create_census_deepseek_trace_note.md`

## Provenance

- run_id: `run_20260909_202201` · source_run_id: `run_20260906_013609`
- csv_sha256: `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`
- cost: SEM-015 (component_measured.v1, MEASURED) · config_version: `v2_htfcrt_2026_08`
- git_sha: `61094ea6ff4fc6736b27e171b0141623f27955a5` tree_dirty=`True`

## Forbidden-work confirmation

No continuous_disp flip, no CHoCH, no occupancy reopen, no parity optimize, no April reclassify,
no TV forensic adjudicator, no economic promotion, no TTL flip. Messured before promote.