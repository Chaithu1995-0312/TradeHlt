# Edge Research Platform — Strong Testing Plan (H1–H3 + Real Market Outlets)

> **Status:** DESIGN (not implemented). Companion to  
> [`edge-research-platform-program.md`](edge-research-platform-program.md).  
> **Authority:** testing/process design only — grants **no** production or capital authority.  
> **Opened:** 2026-07-14 · **Program:** `EDGE_RESEARCH_PLATFORM`

---

## 0. Why this plan exists

Unit tests prove code branches. They do **not** prove:

- the agent reported a real run (H1),
- the agent interpreted the run correctly (H2),
- the run was the **intended** validation path with honest labels/costs (H3),
- research numbers survive **real market data / broker reality**.

This plan binds **pytest + real outlets** (Binance public API, MT5, control-plane UI via Playwright) into one trust ladder.

```text
Code unit tests (always CI)
        ↓
Contract / golden / determinism (CI)
        ↓
Network read-only market data (opt-in CI / nightly)
        ↓
Broker dry-run / analytics smoke (manual or gated)
        ↓
Shadow / paper path (owner grant)
        ↓
Tiny capital (only after FLOW_MATCHES_INTENT + economic survivor)
```

**Hard rules (inherit program §2 + §14):**

1. Every economic number starts as `UNTRUSTED_RAW`.
2. No finding upgrade from chat alone.
3. Real-market tests produce **on-disk artifacts** with provenance, not console-only claims.
4. Live order placement defaults **OFF** (`dry_run=true`); mutation tests are separate and owner-gated.
5. Never read or print `.env` secrets into logs/docs.

---

## 1. Threat model → test objectives

| Mode | Attack / failure | Test objective |
|---|---|---|
| **H1** | LLM invents “pytest green” / PF / trade counts | Every claim requires **artifact path + command provenance**; CI job publishes JUnit + hashed result bundle |
| **H2** | LLM misreads flags, instrument, gate-ON/OFF | Artifacts embed **machine-readable run manifest** (flags, ACTIVE_VERSION, instrument, lens); assertion helpers compare summary vs manifest |
| **H3** | Real run, wrong path / labels / costs | **Validation-path identity tests**: named entrypoint + config + label source must match work-item intent contract |
| **Market drift** | CSV corpus ≠ live feed schema/timezone | **Live feed vs frozen corpus schema/PIT gates** on Binance/MT5 pulls |
| **Execution gap** | Backtest fills ≠ broker | **Shadow / dry-run order intent vs MT5 state** (no size until grant) |
| **UI lie** | Control plane shows stale job status | **Playwright E2E** job submit → status → artifact link |

---

## 2. Test layers (pyramid)

| Layer | ID | Runs where | Real market? | Catches |
|---|---|---|---|---|
| **L0 Unit / pure** | `unit` | Every PR / CI | No (fixtures) | Logic bugs |
| **L1 Contract / golden** | `contract` | Every PR / CI | No (frozen vectors) | Schema, determinism, registry, formula parity |
| **L2 Research integrity** | `research_integrity` | Every PR + nightly | Frozen on-disk OHLCV/perp | Label/path identity, gate flags, no-lookahead |
| **L3 Network market-in** | `market_network` | Nightly / manual | **Yes — read-only** Binance/public REST (and optional exchange CCXT) | Feed shape, clock, gaps, symbol map |
| **L4 Broker analytics** | `broker_mt5_ro` | Manual / pre-release | **Yes — MT5 read-only** | Candle provider, deal reconstruct, verify reconcile |
| **L5 Execution dry-run** | `exec_dry_run` | Manual / owner | MT5 dry_run / paper | Order intent shape, clamp, kill-switch; **no real fills** |
| **L6 Control-plane UI** | `ui_playwright` | Nightly / manual | Localhost + optional job that hits read-only data | H2 on UI: wrong job, wrong command, stale status |
| **L7 Shadow economic** | `shadow_economic` | Owner grant only | Real data in, **no or micro risk** | Full path: opportunity → decision → planned order → outcome re-derive |
| **L8 Tiny capital** | `capital_micro` | Explicit owner + checklist | Real | Only after L7 survivor + `FLOW_MATCHES_INTENT` |

**CI default:** L0–L2 always.  
**Never in default CI:** L5 mutation, L7 economic promote, L8 capital.  
**Secrets:** L3 may use public endpoints only in CI; authenticated Binance/MT5 stay out of PR CI unless a locked runner exists.

---

## 3. pytest architecture (implementation target)

### 3.1 Markers (add to `pyproject.toml`)

```toml
[tool.pytest.ini_options]
markers = [
  "unit: pure logic, no network",
  "contract: golden/schema/determinism",
  "research_integrity: validation-path and label integrity",
  "market_network: read-only live market HTTP",
  "broker_mt5_ro: requires running MT5 terminal, read-only",
  "exec_dry_run: MT5/Telegram dry_run paths",
  "ui_playwright: control plane browser E2E",
  "shadow_economic: owner-gated shadow measurement",
  "capital_micro: owner-gated real capital — never default",
  "slow: long-running",
]
```

### 3.2 Selection recipes

```bash
# PR / local default (no network, no broker)
pytest -m "not market_network and not broker_mt5_ro and not exec_dry_run and not ui_playwright and not shadow_economic and not capital_micro"

# Nightly market-in (public)
pytest -m "market_network" --maxfail=5

# Pre-release broker truth
pytest -m "broker_mt5_ro"   # or: python tests/manual/live_smoke.py

# UI
pytest -m "ui_playwright" --browser chromium

# Forbidden unless owner env set
# RUN_CAPITAL_MICRO=1 pytest -m capital_micro
```

### 3.3 Artifact contract (every L2+)

Each non-unit test that produces economic or market claims writes:

```text
results/test_runs/<run_id>/
  run_manifest.json      # provenance
  assertions.json        # machine outcomes
  raw/                   # optional feed samples (redacted)
  RUN_SHA256.txt         # hash of manifest+assertions
```

**`run_manifest.json` minimum fields**

| Field | Purpose (H1/H2/H3) |
|---|---|
| `run_id`, `timestamp_utc` | Identity |
| `command`, `argv`, `cwd` | H1: real invocation |
| `git_sha`, `branch` | Reproducibility |
| `ACTIVE_VERSION`, `config_hash` | H3: config identity |
| `validation_lens` | e.g. `crt_only_gate_off` \| `fusion_gate_on` |
| `exit_model`, `cost_model_bps` | H3: economic identity |
| `label_source` | e.g. `forward_walk_intrabar_fixed` \| `opportunity_stream` |
| `instruments`, `timeframe`, `data_source` | H2: no instrument swap |
| `network` | `none` \| `binance_public` \| `mt5` \| `mixed` |
| `dry_run` | must be `true` unless L8 |
| `intended_work_item_id` | links to program WI |
| `validation_flow_review` | starts `UNTRUSTED_RAW` |

**Assertion helper (anti-H2):**  
`assert_summary_matches_manifest(summary_dict, manifest)` — fails if instrument/lens/cost in prose-facing summary ≠ manifest.

---

## 4. Real market outlets — what to test

### 4.1 Binance (and public crypto) — L3 `market_network`

**Existing surfaces to wrap (do not reinvent first):**

- Control-plane / fetcher paths using `exchange=binance` (registry already exposes binance/bybit/…)
- `src/inout/perp_funding_fetcher.py` / funding+basis corpus patterns
- Historical candle fetch used by research scripts

**Test packs**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **BN-SCHEMA-01** | Public klines for `BNBUSDT` M15 (last N bars) | Columns + dtypes match OHLCV contract; timestamps UTC monotonic |
| **BN-PIT-01** | Fetch “as of” boundary | No bar with open time > request watermark |
| **BN-GAP-01** | Gap/missing bar report | Missing ratio logged; hard fail only if policy threshold exceeded |
| **BN-PARITY-01** | Live pull vs on-disk `data/*_M15.csv` overlap window | Overlap equality within declared tolerance (float/ts) |
| **BN-FUND-01** | Funding/premium endpoints (if used) | Schema + no-lookahead join key to spot bars |
| **BN-FAIL-01** | Force bad symbol / timeout | Fail-closed; no invented bars; artifact records ERROR |

**Auth:** PR CI uses **public** endpoints only. Private account endpoints (if ever) = separate marker + secret store, not this program’s first ship.

**H3 guard:** BN-* tests assert `data_source=binance_public` in manifest and **never** claim “backtest edge.”

---

### 4.2 MT5 — L4 `broker_mt5_ro` + L5 `exec_dry_run`

**Existing assets (reuse):**

| Asset | Role |
|---|---|
| `tests/mt5_analytics/*` | Fixture + reconstruct + verify reconcile |
| `tests/manual/live_smoke.py` | Real terminal smoke (not collected by default) |
| `src/live/mt5_bridge.py` | Orders; dry_run sentinel already tested unit-side |
| `src/runtime/live_engine_hook.py` | Live spine consumer |
| `src/data_ingestion/historical_fetcher.py` | MT5 candle path when enabled |
| `tests/test_live_integration.py` | dry_run / disabled bridges (no terminal) |

**Read-only pack (L4)**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **MT5-CONN-01** | `initialize` + account metadata **redacted** | Connect or clean SKIP if no terminal (exit 0 for smoke) |
| **MT5-BARS-01** | Candle provider returns M15 for configured symbol | Schema + monotonic ts; count > 0 |
| **MT5-DEAL-01** | Reconstruct closed positions (N days) | Episodes valid under position schema |
| **MT5-VERIFY-01** | Reconcile MT5 truth ↔ analytics artifacts | Diff within policy; report written |
| **MT5-NO-MUTATE-01** | Introspect: execution mutation attrs not called | Same spirit as `live_smoke` check (6) |
| **MT5-FX-CSV-01** | Optional: live M15 vs `data/mt5/*` sample | Overlap parity / schema |

**Dry-run execution pack (L5)** — still **no real orders**

| Test ID | Behavior | Pass criteria |
|---|---|---|
| **MT5-DRY-01** | `MT5Bridge(dry_run=True).send_order(...)` | Sentinel ticket; no `order_send` to terminal |
| **MT5-DRY-02** | Lot clamp min/max | Out-of-range clamped |
| **MT5-HOOK-01** | `live_engine_hook` path with dry_run bridges | Structured result keys present; `mt5_ticket` dry-run consistent |
| **MT5-KILL-01** | Kill switch trips on large loss register | No further orders |

**Capital micro (L8)** — **not designed as automated green-path**

- Explicit checklist doc + human confirm
- Hard env: `RUN_CAPITAL_MICRO=1` AND `OWNER_CAPITAL_ACK=1`
- Max notional / max trades / time box in config
- Kill switch armed; Telegram alert required if enabled

---

### 4.3 Playwright — control plane UI (L6)

**Why Playwright (not “more unit tests”):**  
H2 often happens at the **operator surface** — wrong command selected, wrong params, job shows SUCCESS while artifact is empty.

**Scope:** `localhost:8787` control plane only (stdlib HTTP UI). No external trading website automation in v1 (Binance website scraping is out of scope; use REST).

| Test ID | Flow | Pass criteria |
|---|---|---|
| **UI-BOOT-01** | Open control plane root | UI loads; command catalog non-empty |
| **UI-CATALOG-01** | Catalog vs `registry.py` sample commands | Critical commands present (backtest, validate, fetch) |
| **UI-JOB-01** | Submit **read-only** / safe command (e.g. list commands / dry health) | Job id returned; status terminal SUCCESS/FAILED recorded |
| **UI-ARTIFACT-01** | Job that writes a known path | UI/API exposes path; file exists; manifest hash check |
| **UI-PARAM-01** | Invalid param rejected | Client-side or API error; no silent default that changes instrument |
| **UI-H2-01** | Deliberate mismatch: display instrument vs job argv | Test **fails** if UI summary ≠ argv (guardrail for future bugs) |

**Stack suggestion:** `pytest-playwright` (or Playwright Python) behind `ui_playwright` marker; start control plane as session fixture or require pre-started server.

**Security:** tests bind `127.0.0.1` only; no tunnel.

---

### 4.4 Optional later outlets (design placeholders)

| Outlet | Use | Priority |
|---|---|---|
| Bybit / OKX public REST | Cross-check crypto OHLCV | After BN pack stable |
| Binance WebSocket book ticker | Microstructure research only | After WS-OI design |
| Telegram dry_run | Alert path L5 | Already partial unit coverage |
| Paper account MT5 | L7 shadow | Owner |

---

## 5. Validation-path identity framework (core H3 harness)

### 5.1 Intent contract file (per work item)

```json
{
  "work_item_id": "WI-00N",
  "intended_entrypoint": "src/runtime/backtest_v2.py",
  "required_env": {"BACKTEST_ENGINE_GATE": "0"},
  "forbidden_env": {},
  "validation_lens": "crt_only_gate_off",
  "exit_model": "intrabar_fixed",
  "cost_model_bps": 12,
  "label_source": "forward_walk",
  "instruments": ["BNBUSDT"],
  "allow_network": false,
  "allow_broker": false
}
```

### 5.2 Tests

| Test ID | Asserts |
|---|---|
| **VP-01** | Runner records env/lens into `run_manifest.json` |
| **VP-02** | If actual lens ≠ intent contract → **FAIL** (H3) |
| **VP-03** | If `label_source=opportunity_stream` while intent says `forward_walk` → **FAIL** |
| **VP-04** | Economic assertions refuse to run unless manifest present |
| **VP-05** | Agent-facing “summary.md” must be generated **from** assertions.json (not free text) to reduce H2 |

### 5.3 Relation to program trust tokens

```text
L0–L1 green     → code health only
L2 VP-* green   → FLOW_REVIEWED possible
L2 + reviewed intent match → FLOW_MATCHES_INTENT (research evidence only)
L7 survivor     → AUTHORITY_ELIGIBLE candidate (still not auto-promote)
```

---

## 6. Anti-hallucination test pack (H1/H2 directly)

| Test ID | Idea |
|---|---|
| **AH-01** | Fixture: fake LLM summary with wrong PF; `assert_summary_matches_manifest` must fail |
| **AH-02** | Fixture: missing `run_manifest` → economic claim helper raises |
| **AH-03** | Fixture: tool timeout / empty stdout → status ERROR, no default success |
| **AH-04** | Session log / program JSON must not gain fabricated metrics without artifact path (doc test optional) |
| **AH-05** | Golden: known command produces known manifest fields for BNBUSDT dry backtest (small fixture CSV) |

These are **pure CI** tests — no network.

---

## 7. Mapping to workstreams

| Workstream | Required layers before “validated” |
|---|---|
| **WS-OUTCOME-FACTORY** | L0–L2 + VP-* + AH-*; BN-PARITY on any live refresh of corpus |
| **WS-OI-PATH-ABSTAIN** | L3 for OI/funding feeds; L2 path identity; no L8 |
| **WS-ENGINE-DEMOTION** | L1–L2 incremental-value harness; dual-lens explicit (gate on/off) |
| **WS-SHADOW-LIVE** | L4 + L5 + L7; UI optional; L8 only after grant |
| **Control plane ops** | L6 Playwright for operator truth |

---

## 8. Implementation phases (design → build order)

### Phase T0 — Scaffold (no network) — **DONE 2026-07-16** (WI-003)

1. ✅ pytest markers added to `pyproject.toml` (§3.1; additive, no `--strict-markers`).
2. ✅ `src/utils/run_manifest.py` (build/write/read/hash; **fail-closed** on missing field).
   *Home changed from `tests/support/` → `src/utils/` so producers (not only tests) can emit manifests.*
3. ✅ `src/utils/validation_contract.py` — `assert_summary_matches_manifest` + `require_manifest`
   + `classify_run_status` + `validate_manifest_against_intent` + `summary_from_assertions`.
4. ✅ `tests/harness/`: AH-01..05 (`test_anti_hallucination.py`) + VP-01..05 (`test_validation_path.py`)
   + manifest round-trip (`test_run_manifest.py`) + intent fixture (`fixtures/intent_WI-002.json`).
   **AH-05 is a real golden** over the story-library driver (`scripts/research/story_library_build.py`),
   now the first real `run_manifest` producer.
5. ✅ CI: `.github/workflows/erp-test-harness.yml` runs a **path-scoped green subset** (harness +
   story goldens) — NOT the whole suite (the full suite is intentionally red, F-018). `governance.yml`
   untouched.

**Exit:** ✅ green subset CI passes (56 tests); inventing metrics without a manifest hard-fails in
`build_manifest` / `require_manifest` / `assert_summary_matches_manifest`.

### Phase T1 — **DELIVERED as OFFLINE local-corpus variant 2026-07-16** (owner redirect; WI-004)

Owner redirected T1 from live Binance to the **local OHLCV already in `data/`, XAUUSD**, and asked for
**certify → research**. Delivered offline (no network):
1. ✅ **Certify** `scripts/research/certify_xauusd_corpus.py` — loads XAUUSD **only** via
   `guard_xauusd_csv_path()` → the Phase-1 frozen candidate `data/mt5/XAUUSD_M15.csv`
   (`verify_phase1_frozen_candidate`), runs `dataset_integrity.validate_dataset` (decision **WARN** —
   recorded, honest: gold's residual gaps) + the schema contract, and stamps a `run_manifest`
   (`network=none`, `data_source=local_csv_mt5`). Corpus stays `FROZEN_CANDIDATE` — no promotion.
2. ✅ **Research** `scripts/research/qualify_xauusd.py` — thin, **non-promotable** M4 pass
   (`HypothesisRunner` + `forward_walk(intrabar_fixed)`) on the certified frozen candidate, two families:
   **toy** (expansion_breakout / mean_reversion) both **REJECT** (well-powered n=8k/15k, PF≈0.27) and
   **spine** (production `v2_multi_2026_04`, config `research_config_spine_xauusd.json`) **INSUFFICIENT**
   (n=1, throughput-starved) — consistent with F-035/F-029. Lens recorded truthfully (`fusion_gate_on`
   from runtime `.env`). `UNTRUSTED_RAW`; no edge claim; `ACTIVE_VERSION` untouched.
3. ✅ Tests `tests/research/test_xauusd_corpus_certification.py` (fast, in CI subset) +
   `test_xauusd_qualification_smoke.py` (`slow`, opt-in); both SKIP-if-corpus-absent.

**Exit:** ✅ certify + research drivers run; certify test green in the harness CI subset (58 total);
artifacts + manifests under `results/test_runs/`. **Deferred:** the live Binance `market_network`
variant (BN-SCHEMA/PIT/GAP/FAIL) — not built this pass.

### Phase T2 — MT5 promote smoke into markers

1. Wrap or twin `tests/manual/live_smoke.py` checks as `broker_mt5_ro` tests with SKIP if no terminal.
2. Keep mutation impossible by default.
3. Document pre-release: `pytest -m broker_mt5_ro` + live_smoke.

**Exit:** Same guarantees as live_smoke, collectable, artifacted.

### Phase T3 — Playwright control plane

1. Add dev optional dep `playwright` / `pytest-playwright` (optional extra, not hard prod dep).
2. UI-BOOT, UI-JOB, UI-ARTIFACT against localhost.
3. Nightly or manual.

**Exit:** Operator cannot be shown SUCCESS without artifact existence check.

### Phase T4 — Shadow economic harness (owner)

1. Single scripted path: frozen opportunities → engines → dry plan → forward_walk outcomes.
2. Full manifest + dual-lens options.
3. Still `UNTRUSTED_RAW` until human sets `FLOW_MATCHES_INTENT`.

**Exit:** Reproducible shadow bundle; no capital.

### Phase T5 — Capital micro (checklist only until needed)

Do **not** automate green CI. Checklist in program work item when a survivor exists.

---

## 9. CI / scheduling matrix

| Pipeline | Markers | Frequency |
|---|---|---|
| PR | `unit`, `contract`, `research_integrity`, `AH-*`, `VP-*` (fixture) | Every push |
| Nightly | + `market_network` | Daily |
| Pre-release human | + `broker_mt5_ro`, `exec_dry_run`, `ui_playwright` | Before any live claim |
| Owner only | `shadow_economic` | After design freeze |
| Never auto | `capital_micro` | Explicit dual env ack |

---

## 10. What this plan deliberately does **not** do

- Does not claim Playwright on binance.com (fragile, ToS risk) — use **API**.
- Does not enable live orders in CI.
- Does not treat L0–L2 green as economic edge.
- Does not replace M4 / qualification science — it **certifies the instrument**.
- Does not trust backtests until validation path matches intent (program §2).

---

## 11. Success criteria for “strong testing” (program-level)

| Criterion | Met when |
|---|---|
| H1 resisted | No economic claim accepted without `run_manifest` + artifact hash |
| H2 resisted | Summary≠manifest fails tests; UI argv≠display fails UI-H2 |
| H3 resisted | VP-* fails on lens/label/cost mismatch |
| Real market-in | Nightly BN-* or documented manual green within SLA |
| Broker truth | Pre-release MT5-RO green or explicit SKIP with reason |
| Capital safety | L8 impossible without dual env + owner checklist |

---

## 12. Open design choices (owner)

1. Nightly runner host (local Windows with MT5 vs Linux CI without MT5)?
2. Playwright as optional extra vs separate package?
3. Should BN-PARITY hard-fail on any drift or WARN + ticket?
4. Who signs `FLOW_MATCHES_INTENT` on shadow bundles (U-013)?

---

## 13. Next implementation grant (suggested)

**Minimal first ship (T0 only)** after owner says implement:

- markers + run_manifest helpers + AH/VP fixture tests  
- no Binance/MT5/Playwright code yet  

Then T1 (Binance public) as first **real market-out** proof.

---

## 14. Traceability

| Program concept | This plan |
|---|---|
| TP-BACKTEST-VALIDATION-GATE | VP-*, L2, manifests |
| TP-TOOL-HALLUCINATION H1/H2/H3 | AH-*, UI-H2, artifact hash |
| WS-OUTCOME-FACTORY | T0 + T1 + VP label_source |
| WS-SHADOW-LIVE | T2 + T4 + T5 |
| F-010 / F-037 / F-022 | Lenses + label_source + live gap tests |
