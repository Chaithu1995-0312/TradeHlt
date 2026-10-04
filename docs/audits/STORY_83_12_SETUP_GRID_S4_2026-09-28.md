# STORY-83.12 (WP-L) — the first S4 grid: `sl_anchor x target_policy`, TTL on

Scope: this document reports one mechanical run of `scripts/research/setup_grid_s4.py`
(EPIC-83, S4 run unit) at HEAD `8073f619`. **Authority: NONE** (CLAUDE.md §6.5 Authority Ladder)
— this is a comparison arm, not an economic claim, not a G001 input, not a promotion input.

Evidence tags: **RUNTIME** = observed by running the script; **STATIC** = read from source;
**DOC** = stated in a prior doc, not re-verified here.

---

## What ran (RUNTIME)

Grid per the user's Q8 decision (`setup-overlay-spec-2026-09.md §10`): `sl_anchor` ∈
{`displacement`, `sweep_extreme`} × `target_policy` ∈ {`fixed_r`, `structural_tp2`}, 4 arms,
`trade_ttl_candles=20` (a first-pass exploratory value informed by F-024's median/p90 trade
duration, **not** a tuned number — recorded plainly as UNVERIFIED-as-a-choice) on every arm.
`decider` stays `"engine"` on every arm (Q8: out of this first grid; `"resolver"` isn't
implemented yet — STORY-83.11b). K23 F1/F2 (`retrace_reset_pct`, `session_window_basis`) are
also out of this grid per Q8, left at v5's default on every arm.

Each arm ran in its own isolated config root (`src/utils/isolated_config_root.py`, the
proven v3/v5-parity mechanism) pinned to `v5_htfcrt_sot_dual_k23_2026_09`, `ACTIVE_VERSION`
never touched. Corpus: **the short-window fixture**
(`data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv`), per the 2026-09-28 hard constraint
(`feedback_parity_checks_short_date_window.md`) and this spec's own §7.2 standing rule
("time-range subset first, full corpus after"). The full 47k-bar corpus was **not** run —
`--full-corpus` opts in explicitly and was not used here.

Raw output: `results/setup_grid_s4/20260927T214806Z/report.json`.

## Result: all 4 arms are vacuous on this window (RUNTIME)

| Arm | trades | net % | R net |
|---|---|---|---|
| `displacement__fixed_r` | 0 | 0.0 | 0.0 |
| `displacement__structural_tp2` | 0 | 0.0 | 0.0 |
| `sweep_extreme__fixed_r` | 0 | 0.0 | 0.0 |
| `sweep_extreme__structural_tp2` | 0 | 0.0 | 0.0 |

Zero trades on the ~1-month window on every arm. This matches STORY-83.6's own prior finding
on the same window ("trade ledger 0 vs 0 trades — vacuous on this window") and STORY-83.10's
finding that XAUUSD trades are rare overall (3 in the full 2-year corpus). **No ranking,
economic, or preference claim is made here** — a 0-trade population cannot support one. This
report is evidence the MECHANISM works, not evidence about which arm is better.

## What the run proves (RUNTIME) — the mechanism, not an economic result

Every arm's config was verified to actually carry the overlay it was assigned
(`target_policy_stamped` / `trade_ttl_candles_stamped` in each arm's own summary, read back —
not assumed):

```
displacement__fixed_r          config_version=v5_htfcrt_sot_dual_k23_2026_09 target_policy=fixed_r          ttl=20
displacement__structural_tp2   config_version=v5_htfcrt_sot_dual_k23_2026_09 target_policy=structural_tp2   ttl=20
sweep_extreme__fixed_r         config_version=v5_htfcrt_sot_dual_k23_2026_09 target_policy=fixed_r          ttl=20
sweep_extreme__structural_tp2  config_version=v5_htfcrt_sot_dual_k23_2026_09 target_policy=structural_tp2   ttl=20
```

The §7.3 ranking gate (`governance.measurement_basis.can_compare`) was **called, not
re-implemented**, and produced exactly the verdicts the spec predicts:

| a | b | verdict |
|---|---|---|
| `displacement__fixed_r` | `displacement__structural_tp2` | `ALLOW_SAME_BASIS` |
| `sweep_extreme__fixed_r` | `sweep_extreme__structural_tp2` | `ALLOW_SAME_BASIS` |
| any `displacement__*` | any `sweep_extreme__*` | `DENY_REFERENCE_LEVEL_MISMATCH` |

Within one `sl_anchor`, the two `target_policy` arms share `reference_level` and are
comparable. Across `sl_anchor`, `reference_level` differs (`displacement_extreme` vs
`sweep_extreme`) and the gate correctly refuses — exactly the SEM-017 rule §7.3 documents
("reference level moves risk_distance, hence every R on the row"). All four arms share the
same equity basis by construction (`risk_pct_per_trade=0.01`, `sizing_mode=fixed_investment_inr`,
`per_trade_investment_inr=10000.0` — the script never mutates sizing), so a money-basis
ranking across all 4 arms is licensed by §7.3's own rule even though this run has nothing to
rank.

## Known limitations of this run (STATIC + RUNTIME)

- **Vacuous population.** See above — the real test of `structural_tp2`/TTL behaviour under
  live trading conditions needs either a longer window or the full corpus; deferred, not run,
  per the current hard constraint on full-corpus runs.
- **`decider="resolver"` is out of scope** for this grid (STORY-83.11b, not implemented).
- **`trade_ttl_candles=20` is a placeholder**, chosen for this first pass, not derived from any
  optimization or backtest evidence.
- **`corpus_read_lint`**: `setup_grid_s4.py:99`'s `csv.DictReader` read of each arm's own
  `*_trades.csv` (a RESULT file this run just produced, not a source corpus) is flagged
  `UNKNOWN` by the lint tool. Same classification as the existing precedent
  (`scripts/research/parity_v5.py:241`, "reads result CSVs") — not added to
  `docs/governance/corpus_read_allowlist.json` (never hand-edited; this is not a corpus-gate
  violation, it reads the script's own just-written output). `test_corpus_read_lint.py` was
  already RED before this change (35 pre-existing unrelated sites); this adds one more UNKNOWN
  of the same non-corpus class, not a new corpus-gate bypass.

## Next step

Re-run with `--full-corpus` once the user wants that evidence (a multi-minute run, per the
hard constraint — requires explicit ask). A non-vacuous population is required before any
ranking or preference statement about `target_policy`/`sl_anchor`/`trade_ttl_candles` can be
made.
