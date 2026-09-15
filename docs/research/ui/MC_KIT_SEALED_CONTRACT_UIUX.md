# Sealed-Contract Kit — UI/UX design (on `ui_kits`)

**Status:** DESIGN ONLY · no `mc_kit` implementation in this doc · no economic authority  
**Lane:** `research.mc_kit` (candidate B) · frontier F-086…F-097  
**Surfaces:** extend Ops Dashboard **Research** + Control Plane **Explorer/Agent** patterns from `ui_kits/`

## Goal

Make sealed MC-contract work **operable** in the existing operator chrome: default the governed steps (split / embargo / purge / controls / gate / artifacts), expose the 8 explicit cross-contract differences as named parameters (never silently unify), and prove “next contract = `TradeContractSpec` + detector” with Step-0 byte parity.

## Placement on `ui_kits`

| ui_kits home | Role for this lane |
|---|---|
| `ui_kits/crt_dashboard/` → sidebar **RESEARCH** | Primary home: Sealed Contracts registry, Step-0 gate, Spec composer, ROI |
| `ui_kits/crt_dashboard/` → **Backtests** lab pattern | Reuse dense KPI/table chrome for metrics/ledger compare |
| `ui_kits/control_plane/` → **Launcher / Inspector** | Optional: run Step-0 / migrate jobs as commands; inspect artifacts/monitors |
| `ui_kits/control_plane/` → **Explorer** | Map kit modules ↔ `src/research/*` drivers (LLM nav sibling) |

Do **not** invent a third product shell. One Research sub-nav item: **Sealed Contracts**.

## Information architecture (4 screens)

### 1. Contract Registry (`/research/sealed-contracts`)
- Table of in-scope contracts (trade + prior): mother_range, sujan_crt, asymmetry, magnitude_prior, rnet_overlay, mother_range_prior, visual_crt_prior.
- Columns: shape (trade|prior), sealed artifacts present?, corpus pin (`XAUUSD_M15` reviewed), Step-0 reproduces?, wall time, SHA match (metrics / ledger / split / fingerprint).
- Top ROI strip (non-economic): net LOC estimate, marginal next-contract LOC, “F-083 recurrence path closed for *new* contracts”, `economic_claims_allowed=false`.
- Kill criterion banner: **&lt;3 Step-0 reproduces → stop; ROI unverifiable**.

### 2. Step-0 Baseline Gate (`/research/sealed-contracts/step0`)
- Run-all / run-one into scratch dir; byte-compare to committed `docs/research-readiness/…`.
- Per-artifact traffic lights; exclude non-reproducers as **drift** (not auto-fixed).
- Explicit: `.git/index.lock` untouched; no commits; no corpus/finding edits.

### 3. Spec + Detector Composer (`/research/sealed-contracts/new`)
- Form = `TradeContractSpec` fields: contract_id, sem_id, corpus, instrument, horizon, split, cost, adverse, controls, gate.
- **Difference chips** (always visible; recorded, not fixed):
  1. long_only basis: `gross` | `net`
  2. zero_risk: `raise` | `tp_mult_1`
  3. volume: `required` | `zero_default`
  4. corpus sha: `hardcoded` | `computed`
  5. split scheme: timestamp holdout+suppression | index-fraction+embargo+purge | timestamp+embargo/purge window
  6. verdict vocab: trade vs prior labels
  7. `finalize_run`: off for trade drivers (user-gated separate) | on for priors
  8. JSON serialization: indent/default/sort_keys (byte identity)
- Detector panel: only research-specific code (target 60–120 LOC). Preview `run_trade_contract(spec, detect, row_extra)`.

### 4. Kit Primitives Map (`/research/sealed-contracts/kit`)
- Cards for `bars / trade / stats / splits / controls / gate / artifacts / spec` + `costs.xau_measured_cost_model()`.
- Pipeline viz: validate_dataset → load_bars → detect → split → Signal → forward_walk+AdverseFill → net_rr → stats → controls → gate → artifacts.
- Link each primitive to “absorbs MR/SUJ/prior duplicate” tags (AST fingerprints from measurement).

## UX principles (operator-grade)

1. **Governed by default** — split/embargo/purge/controls/gate are kit defaults; authors cannot omit them by forgetting.
2. **Differences as parameters** — never silent merge of gross/net, volume, sha, split, verdict, finalize_run, JSON options.
3. **Byte-identity as truth** — green only when SHA matches Step-0 baseline on the reviewed corpus.
4. **Fail closed** — missing reviewed corpus / non-reproducing baseline → exclude or stop; no soft “close enough.”
5. **No economic chrome** — no G001, no promote; claim_class stays diagnostic.
6. **Reuse ui_kits visual language** — navy `#0f1724`, panels `#122033`, teal `#0ea5a3`, monospace paths/IDs, status pills.

## User flows

1. **Open lane** → Registry shows 7 contracts + ROI strip.  
2. **Run Step-0** → parity table; if &lt;3 green, stop.  
3. **Migrate one driver** (ops/dev, not forced in UI) → re-run → SHA == Step-0 or revert.  
4. **New contract** → Composer: pick parameter variants + paste detector → dry-run acceptance (Step-4 style) against a known template.  
5. **Inspect kit** → Primitives map for LLM/human navigation (tie to `docs/UI_LLM_NAVIGATION.md` later as `view_id=sealed_contracts`).

## Out of scope in UI (same as plan)

visual_crt driver/controls/measure, context_attribution, rc003_distinct_object; behavioral “fixes” for differences 1–8 (surface only); commits while index.lock held.

## Success criteria for the design

- Operator can see which contracts are parity-safe before any migration.  
- Next-contract cost is visible as spec+detector, not a 400-line driver.  
- F-083 class gaps are structurally hard to reintroduce in the composer.  
- LLM nav can later add edges: sealed_contracts → `src/research/mc_kit/*` → prior drivers.

## Related

- Measurement/plan context: user sealed-contract kit design (2026-09-14)  
- Visual system: `ui_kits/crt_dashboard`, `ui_kits/control_plane`  
- Prior UI nav: `docs/UI_LLM_NAVIGATION.md`
