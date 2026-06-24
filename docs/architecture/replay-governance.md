# replay-governance.md

> **Purpose:** The determinism contract. Replay correctness is the #1 priority of this
> migration (above explainability, telemetry, advisory-AI). This doc states what makes a
> run reproducible, what guarantees exist today, and the register of replay risks that
> every future change must respect.
>
> Anchored to `v2_multi_2026_04`. Citations `file:line`.

---

## 1. The comparability contract

Two backtest runs are **exactly comparable** iff all of these match:
1. Same input CSV (M15 OHLCV).
2. Same `BacktestConfig` — especially `slippage_seed` (`backtest_v2.py:110`, loaded
   `:181`), capital, warmup, HTF settings.
3. Same production config version (`PROD_VERSION` / `ACTIVE_VERSION`).
4. Same `CRTConfig` / engine parameters.

Run artifacts that carry the comparison surface: `{instrument}_summary.json`
(`BacktestMetrics.to_dict`, records `config_version`), `{instrument}_trades.csv`,
`{instrument}_events.jsonl`. Comparison tooling diffs **payloads + metrics**, never
wall-clock fields.

---

## 2. Determinism guarantees in place today

| Guarantee | Evidence | Why deterministic |
|---|---|---|
| One bar at a time | candle loop `backtest_v2.py:~1518` | single iterator, no batch |
| Seeded slippage | `self._rng = random.Random(seed if seed != 0 else None)` (`:379`) | same seed → same slippage sequence (set `0` only for intentional randomness) |
| Timestamp-keyed features | `feature_ts_to_idx` populated `:1307`, looked up per bar | exact ts match, no index drift / off-by-one |
| Lag protection | `.shift(1)` at `feature_pipeline.py:180`, `:262-263`, `:359-360` | current-bar close not used as its own predictor |
| Gap handling | time-gap reset compares CSV timestamps, not wall-clock | depends only on data |
| No threading on hot path | spine is synchronous | no scheduling nondeterminism |
| No network on hot path | LLM is off the replay path entirely (see §4) | no external variance |

---

## 3. Replay-risk register

| Risk | Location | Verdict | Required guard |
|---|---|---|---|
| **`center=True` rolling swing detection** | `feature_pipeline.py:341-342` | **Backtest-valid, LIVE-UNSAFE.** Centered window peeks at future bars; safe only because the full series is precomputed identically each run (module docstring `:37-39` says so). | Before the feature pipeline runs in **live** mode, swing detection must switch to a causal (trailing) window. Document any live path that reuses this builder as a hard review-stop. |
| Wall-clock `run_id` | `datetime.now()` for output dir naming | **Safe** — affects artifact path only, never trade logic. | Keep out of any compared field. |
| Envelope `timestamp` / `event_id` / `generation` | `event_fabric.py:145-150` | **Not comparable** across runs by design. | Comparison tooling must key on payload + `schema_hash` + candle ts. |
| `schema_hash` is passive | `event_fabric.py:41-42` | **By design** — no runtime code enforces it. | Offline audit compares recorded `schema_hash` vs current `FEATURE_ORDER_HASH`; mismatch ⇒ records from a different schema. |
| Threaded `CognitiveBus` ordering | `cognitive/cognitive_bus.py` | Bus emission ordering may interleave | Bus must never feed back into a decision (it does not); never compare `generation` cross-run. |
| Dict / set iteration | session windows etc. | Safe on Py ≥ 3.7 (insertion-ordered) + static config | Keep config static during a run. |

---

## 4. LLM is off the replay path (non-negotiable)

No LLM call occurs inside the candle loop (`backtest_v2.py` ~`:1518-1993`). The fusion
LLM gate is an uncertainty-zone tie-breaker only and fails open to a neutral score;
`llm_scorer` returns `1.0` after the circuit opens. Therefore replay determinism does
**not** depend on any external model. See
[`llm-governance-layer.md`](llm-governance-layer.md) for the full isolation argument.

---

## 5. Telemetry-continuity rules (so runs stay comparable as the system evolves)

1. **No field removed without a superseding field** documented in
   [`event-taxonomy.md`](event-taxonomy.md) (old→new mapping).
2. **Every cross-component event uses `make_event_envelope`** so `schema_hash` travels
   with the data.
3. **New telemetry is additive** — Trd-M1 dual-writes (legacy `fusion_trades.jsonl`
   untouched; enveloped stream added) so existing comparisons keep working.
4. **The per-episode LLM log (`logs/llm_episodes.jsonl`) is a read-only projection** —
   it must be byte-identical across two identical (CSV+seed+config) runs, and must
   never influence a decision. Uses candle timestamps, not wall-clock.

---

## 6. The determinism acceptance gate (for any code change, incl. Trd-M1)

```
1. Baseline: run backtest on fixed CSV + fixed slippage_seed.
   Snapshot {instrument}_trades.csv + {instrument}_summary.json.
2. Apply change.
3. Re-run identical CSV + seed.
4. ASSERT trade ledger + summary are byte-identical.   ← replay preserved
5. ASSERT any new events are additive (no field loss). ← telemetry continuity
6. (Trd-M1 Part 2) ASSERT llm_episodes.jsonl byte-identical across the two runs,
   and every child_event_id resolves to a real firehose event.
```

A change that fails step 4 is rejected regardless of any other benefit.
