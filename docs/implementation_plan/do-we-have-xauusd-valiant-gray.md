# Register F-089 — the parent-CRT bias gate is decision-neutral on XAUUSD

## Context

**What prompted this.** The question "are those state transitions prod active version or independent?"
Verifying the answer (they ARE `ACTIVE_VERSION = v2_htfcrt_2026_08`, loaded through
`load_prod_config_from_registry` with `verify_hash=True`) surfaced something unplanned: the
5,269-event CRT state sequence is **byte-identical** to the older `v2_multi_2026_04` run.

**Why that is not trivial.** The two registry configs have **identical `params`** (same
`config_hash` `7de09f62…` — `parent_crt` is a non-`params` section, hash-neutral per §6.5) and no
differing top-level keys. The single behavioural difference is `parent_crt.enabled`: **true** on
the active config, **false** on the old one. So this is a clean natural A/B of the F-075 gate.

**Measured result (already obtained, read-only):**

| Check | Result |
|---|---|
| State sequence (STATE_TRANSITION + RESET, n=5,269) | **byte-identical**, sha `4f09654ac8f50700` both |
| Full event profile | identical across all 10 event kinds |
| Trades | 3 opened / 1 TP1 / 1 TP2 / 2 stopped — identical |
| `FILTER_REJECTED` timestamps | **same set**, 19 vs 19, none only-in-one |
| Rejection **reasons** that differ | **exactly 4** |

```
2025-01-31 21:00  off_session -> Against parent-timeframe bias (LONG)
2025-07-10 20:15  off_session -> Against parent-timeframe bias (SHORT)
2026-02-19 11:30  off_session -> Against parent-timeframe bias (LONG)
2026-03-18 11:30  off_session -> Against parent-timeframe bias (SHORT)
```

**The claim:** arming `parent_crt` fires 4 times over the full 2-year corpus and every one of those
4 candidates was **already** being rejected by the off-session filter. It changes the *reason*,
never the *outcome*. This refines F-075 — which records the gate as "reachable on the armed
config" — with the measured next step: reachable, fires, and **non-pivotal**. Same shape as F-036
(zone tunable-but-inert) and F-070 (fusion vetoes 0/30). *Reachable ≠ pivotal.*

**User decisions:** record it properly as a finding with a reproducible probe; **XAUUSD only** (per
the standing instruction never to swap in other instruments to force events).

**Explicitly NOT claimed:** that `parent_crt` should be disabled, that it is inert on any other
instrument or corpus, or anything economic. n=4 gate firings supports no economic claim whatever.

---

## Work

### 1. `scripts/research/parent_crt_pivotality_probe.py` — the reproducible probe

Must be **self-contained from a clean clone** — it may not depend on the gitignored
`results/research/_spine_entries/…` artifact I compared by hand.

Design: run the spine twice through the **governed registry loader**, once per config version, and
diff. Reuse — do not reimplement — `charts.crt_overlay.run_spine_for_states(instrument, csv_path,
version=...)`, which already takes an explicit `version`, rebinds `PROD_VERSION` in both modules,
and restores in `finally`. Cache dirs are already version-scoped, so the two runs cannot collide.

Three **blocking validity gates**, in this order, before any verdict is emitted:

1. **Configs differ ONLY in `parent_crt.enabled`** — assert identical `params`, identical
   `config_hash`, no differing top-level keys. Without this the A/B is confounded, and a future
   config edit would silently turn this probe into a comparison of two unrelated things.
2. **Non-vacuity** — assert the gate actually fired (≥1 `FILTER_REJECTED` carrying a parent-bias
   reason) on the gate-ON arm. A gate that never fires is *untested*, not *neutral* (the F-070
   guard).
3. **Corpus identity** — assert the Phase-1 sha256, so a drifted corpus fails closed rather than
   producing a comparison of different data.

Then compare: state-sequence sha, per-event-kind counts, trade counts, and the
`FILTER_REJECTED` timestamp→reason map. Emit `PIVOTAL` / `DECISION_NEUTRAL` / `VACUOUS` /
`INVALID_AB` plus counts to stdout and a JSON artifact. `--json <path>` optional; read-only w.r.t.
all governed state (no config write, `ACTIVE_VERSION` untouched).

### 2. `tests/test_parent_crt_pivotality.py` — floor

Unit-level, no spine run (the probe itself is minutes-long):
- the config-equivalence gate rejects a confounded pair (differing `params`);
- the non-vacuity gate returns `VACUOUS` when no parent-bias rejection is present;
- reason-only differences classify `DECISION_NEUTRAL`;
- an outcome difference (extra/missing rejection timestamp, or differing trade counts) classifies
  `PIVOTAL` — i.e. the probe *can* fail, per the E-001 "a test that can't fail isn't enforcement"
  lesson;
- corpus-sha mismatch fails closed.

### 3. `docs/current-findings.md` — add F-089

Next free id (F-088 is the highest). Fields per the house block format:

```
Type:          ARCHITECTURE
Family:        RF-HTF          (same family as F-075)
Contract:      UNKNOWN
Status:        VALIDATED
Confidence:    Certain
Validated:     2026-08-22
Revalidate-by: 2027-02-22
Supersedes:    —
Reversal:      — refines F-075, reverses nothing
```

**Confidence note (judgment call, flagged deliberately):** `Certain`, because the claim is a
deterministic, reproducible byte-comparison — not an inference. The neighbours F-036 and F-070 sit
at `Likely`, but each embeds an inferred *driver*; this one will not. Any generalisation beyond
"this corpus, these two configs" is excluded in the finding text rather than absorbed into a
softer grade.

**Evidence must cite TRACKED paths only** — `tests/test_current_findings.py:280-313` reads
`git ls-files` and the fix is *"`git add`-ing the path, not widening the ratchet"*. `results/` and
`data/` are gitignored, so cite: the probe script, `src/charts/crt_overlay.py`,
`configs/production/v2_htfcrt_2026_08.json`, `configs/production/v2_multi_2026_04.json`,
`src/config_layer/parent_crt.py`, and the new test. **The probe script and `src/charts/` must be
`git add`ed** (targeted paths only — never `git add -A`, per the concurrent-sessions constraint)
or the findings floor fails. Staging is sufficient; `git ls-files` reads the index.

### 4. Sync the surfaces that are mechanically enforced

- **`CLAUDE.md` §6.2 Repository Truths Index** — add the F-089 row. `test_current_findings.py:244`
  enforces the index and the living doc agree on every non-terminal id, both directions.
- **`data/findings.jsonl`** — regenerate via `python scripts/governance/export_findings.py`
  (GENERATED artifact; never hand-edited).
- **SITS** — register the probe the same turn: `script_census.py --write-stubs` → add an OVERLAY in
  `scripts/governance/seed_script_registry.py` → `seed_script_registry.py` →
  `scripts/analysis/generate_script_matrix.py` (note: it lives under `scripts/analysis/`, not
  `scripts/governance/`). Do **not** hand-edit the stubs JSONL.
- **`docs/current-findings.md` F-075** — append a pointer line noting F-089 measured its gate as
  non-pivotal on XAUUSD. Append-only; do not rewrite or downgrade F-075 (§6.2 rule 4).
- **`reports/xauusd_visual_pass.md`** — add the measurement to §4, since that report's funnel
  numbers came from this exact run.
- **`assistant_project.md`** — SESSION LOG entry (§6).

---

## Verification

1. `venv/Scripts/python.exe -m pytest tests/test_parent_crt_pivotality.py -q` — floor green.
2. `venv/Scripts/python.exe -m pytest tests/test_current_findings.py -q` — findings contract,
   index sync, and the tracked-evidence gate all green.
3. `venv/Scripts/python.exe scripts/research/parent_crt_pivotality_probe.py --instrument XAUUSD`
   → expect `DECISION_NEUTRAL`, `reasons_changed=4`, `outcomes_changed=0`, state-sequence shas
   equal. First run is slow (two full spine passes); subsequent runs hit the version-scoped cache.
4. `venv/Scripts/python.exe -m pytest tests/test_script_registry.py tests/test_script_matrix_sync.py -q`
   — SITS floors stay green (they are green today, 52/52).
5. `git ls-files scripts/research/parent_crt_pivotality_probe.py` returns the path — the evidence
   gate's actual condition.

## Known-red, not mine, not touched

The construction floor is RED with 7 failures that predate this work and are unrelated to it:
`test_geometry_census` ×2 / `test_gate2b_closure` ×2 / `test_feature_math_lint` — all driven by 88
unregistered derivations in `msip_1_verification_package/` plus removed ones in
`feature_pipeline.py`/`crt_feature_builder.py`/`strategy_backtest.py`; `test_active_models_registry`
(file was already dirty at session start); `test_session_log` (37 entries vs a cap of 30 — needs
`rotate_session_log.py`, deferred because ~15 concurrent sessions append to that file and a bulk
rewrite could drop their entries). **I will not regenerate the geometry census** — doing so would
absorb 88 unadjudicated foreign derivations into a governance artifact.
