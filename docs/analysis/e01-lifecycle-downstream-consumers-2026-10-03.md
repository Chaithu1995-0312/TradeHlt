# E01 lifecycle sweep: C1–C7 full corpus + downstream consumers (2026-10-03)

> Point-in-time diagnostic evidence for **F-112** (`docs/current-findings.md`), the follow-up to
> `docs/analysis/e01-lifecycle-shadow-impact-2026-10-03.md`. **Not** activation evidence, not an
> economic finding, not a revalidation of any downstream finding.

## Identity
- Corpus: `data/mt5/XAUUSD_M15.csv`, 47,275 rows, 47,197 after the pipeline's 78-bar warmup,
  sha256 `4d73f5cebe33ec91…`.
- ACTIVE `v2_htfcrt_2026_08` (`sweep_semantics = latest_unconsumed`) vs non-promoted SHADOW
  `v2_htfcrt_e01lifecycle_shadow_2026_10` (`e01_lifecycle`). params `config_hash` `7de09f62…` in both.
- Code: `semanticos_impl` @ `f2e44ae` + the uncommitted CH-e01-lifecycle-sweep-identity tree.
- Run artifacts (session scratch, not tracked):
  - Step A ACTIVE: `run_20261003_110720_…_v2_htfcrt_2026_08_7de09f62`.
  - Step A SHADOW: `run_20261003_110727_…_v2_htfcrt_e01lifecycle_shadow_2026_10_7de09f62`.
  - Step B: the script in the Appendix (`consumers_ab.py`), 516 s.

## Step A: Semantic OS C1–C7 integration checks, both arms
Command: `scripts/governance/semantic_os_integration.py --csv data/mt5/XAUUSD_M15.csv
[--version v2_htfcrt_e01lifecycle_shadow_2026_10]`. Replay gate PASS in both arms (7,113 events).

| Check / concept | ACTIVE | SHADOW |
|---|---|---|
| C1 MKT-P01 | 2,888 AGREE | identical |
| C2 MKT-E01 (engine sweep) | 1,798 AGREE / 11 UNEXPLAINED / 1,026 NOT_CHECKABLE | identical |
| C3 MKT-E04, TRS-01 | 399 / 399 AGREE | identical |
| C4 MKT-E11 / MKT-E12 / TRS-03 | 101+36 EXP / 63+2 UNEXPL / 73+123 EXP | identical |
| C5 TRS-04 / TRS-05 / TRS-06 | 3 AGREE + 3 EXP / 3 AGREE / 6 AGREE | identical |
| C6 DEX-05 | 3 AGREE | identical |
| C7 MKT-E01 (sweep slots) | 6,348 AGREE / 75 EXP / **12,424 UNEXPLAINED** | 10,066 AGREE / 45 EXP / **0 UNEXPLAINED** |
| C7 MKT-C04 (`double_sweep`) | 1,203 AGREE / 2,358 EXP / 1 UNEXPLAINED | **1,713 AGREE** |
| C7 C01 / C03 / C06 / C07 / E08 / L01 | 18,754 / 1+3 UNEXPL / 1 / 2,985 / 26,451 / 12,730 | identical |

ACTIVE C7 E01 UNEXPLAINED by mechanism (all 12,424 classified):
- 4,437: the slot fires on a level already BROKEN.
- 4,269: the slot re-fires on a level already SWEPT.
- 3,662: an older ACTIVE level was swept that the slot never tests.
- 56: UPPER-first precedence.

The single ACTIVE C04 row is bar 18 (start of corpus). It is unclassified.

**Pre-registered (written before results):**
- P-A1, C1–C4 identical between arms: **PASS**.
- P-A2, C5/C6 checkable with TRS-06 AGREE: **PASS**.
- P-A3, SHADOW 0 E01/C04 UNEXPLAINED: **PASS**.

**UNEXPLAINED in both arms (independent of this change; read, not classified here):**
- C2 at 11 bars (5397, 5858, 10754, 20451, 23685, 29810, 33149, 35220, 39842, 41298, 42344). On each
  bar both edges are GP-04 sweeps, but the engine records only UPPER.
- C4 MKT-E12 at bars 18798 and 37041. The engine says EXPIRED; the contract says ACTIVE.
- C7 MKT-C03 at bars 529, 10927 and 46840. `trend_bias` = 0 while the contract gives ±1. These are
  **not** warmup bars, which is relevant to the open C03 warmup rule.

**Check gap (reported, not fixed):** C5 TRS-06 accepts TP1 at *any* declared intent multiple. It
does not check that the multiple matches the intent the engine derived. Related: the
`RETEST_REPLAY.tp1_mult` telemetry records the base multiplier.

## Step B: downstream consumers
Two FeaturePipeline frames over the full corpus, with the active `feature_pipeline` section, differing
only in `sweep_semantics`. Asserted: the 43 slots outside the five below are identical on every bar.
The script wrote nothing to the repo's `logs/`: `repo_logs_changed = []`, and EngineRunner's
enveloped-telemetry writer was silenced.

### B0. Input shift (47,197 bars)
| Slot | Bars changed | Share | Non-zero ACTIVE → SHADOW | Transitions |
|---|---:|---:|---|---|
| `liquidity_sweep` | 6,235 | 13.2% | 7,542 → 5,033 | 1→0 2,301 · −1→0 2,022 · 0→−1 926 · 0→1 888 · 1→−1 74 · −1→1 24 |
| `sweep_detected` | 6,137 | 13.0% | 7,542 → 5,033 | 1→0 4,323 · 0→1 1,814 |
| `double_sweep` | 2,359 | 5.0% | 3,052 → 1,713 | 1→0 1,849 · 0→1 510 |
| `candles_since_sweep` | 33,687 | 71.4% | — | (counter reset points moved) |
| **`retest_depth` (FM-021)** | **8,213** | **17.4%** | 27,405 → 24,876 | — |

**`retest_depth` moves transitively.** `retest_flag` reads `liquidity_sweep != 0`
(`feature_pipeline.py` `compute_structure_liquidity`), and FM-021 is gated on `retest_flag`.
- **The Step 6 registration did not declare this.** It named only the four sweep identities FM-090..093.
- **The Step 6 parity tests did not cover it.** They checked the four sweep slots only. On the live
  path, `runtime/live_rail_feeder.py` takes `retest_depth` from a rolling-window FeaturePipeline,
  while `core/feature_store.py` carries the lifecycle only for the four sweep slots. In `e01_lifecycle`
  mode, live `retest_depth` may therefore differ from batch: **UNVERIFIED**, not tested.

### B1. Live-rail planner + GateIntelligence
Inputs and coverage:
- `ExecutionPlannerV1_2.plan` with `planner_config_from_production(active, "XAUUSD")`, run on every
  bar × {LONG, SHORT}, 94,394 calls per arm.
- The engine result is forced to `execute`, so this measures the planner's own intent + gate stage.
- Features are the canonical frame columns, as `live_path_replay.py --feature-source canonical` uses.

| | ACTIVE | SHADOW |
|---|---:|---:|
| `execute` (gate approved) | 2,077 | 1,382 |
| `reject_gate` | 92,313 | 93,006 |
| `reject_unknown_intent` | 4 | 6 |
| intent LIQ_SWEEP | 17,878 | 11,936 |
| intent REVERSAL / CONTINUATION | 34,293 / 34,293 | 37,208 / 37,208 |
| intent PULLBACK / BREAKOUT | 5,534 / 2,392 | 5,492 / 2,544 |

- **Approval flips:** 1,146 approved → rejected and 451 rejected → approved, net −695 (−33%).
- **Intent and score:** intent score changed on 19,818 calls; maximum |Δ final score| = 0.40.
- **Mechanism, read from the flip examples:** a LIQ_SWEEP intent scores 0.5·sweep + 0.5·double_sweep.
  When the lifecycle consumes a level, `double_sweep` (intent 1.0 → 0.5) or `sweep_detected`
  (LIQ_SWEEP → CONTINUATION/REVERSAL, intent → 0) drops, taking the score below the 0.55 threshold.
- **Context:**
  - The planner is reachable only on the live rail: F-073, there is no production live rail; F-103,
    the backtest never imports the planner.
  - F-109 found its gate hostile to CRT entries on XAUUSD.
  - These are per-bar hypothetical calls, not trades.

### B2. EngineRunner fusion gate (the backtest's post-commit veto)
Setup:
- `EngineRunner.run` with the active `engine_runner` section, on every bar × {LONG, SHORT}.
- The input is built like `backtest_v2`'s `_feat_map_er`, with two declared deviations: `atr` =
  canonical atr × close (FM-074), not `engine.state.atr_abs`; and no orchestrator consensus score or
  belief registry.
- The backtest veto rule is applied, including `backtest.bypass_zone_invalid = true`.

Results:
- Decision flips 0, reason flips 0, veto flips 0 (36,794 vetoes in each arm), selected-engine flips 0.
- Score differs on 48 of 94,394 calls, max |Δ| 0.045.
- **Non-informative by construction.** Every call is rejected at either:
  - the adapter: `invalid_session` 0.0 = 24,714 and 4.0 = 12,016; or
  - the DecisionEngine's first check, `feature_cluster_similarity_invalid` (57,600), which the
    backtest bypasses. Because this rejection fires first (`decision_engine.py:158`), the
    score-threshold and p_win checks are never reached. A small score change therefore cannot reach
    a decision on this path.
  - Plus 64 `ultron_gate:regime_range_no_direction`.
  - P-B3 is scored PASS, but it shows the gate cannot see the change, not that the change is harmless.

### B3. Trained artifacts not reachable on the active config
Verified in `configs/production/v2_htfcrt_2026_08.json` and source:
- `rr_fusion.enabled = false`.
- `use_bitnet = false`.
- TradeNet is unwired (F-005).
- ZoneGate scores every in-session bar `valid = False` (B2 above), so its sweep dimensions decide
  nothing on this path.
- `crt_gaussian_scorer` reads `candles_since_sweep` only as a fallback after `retest_index`. Its effect
  on the 3 trades is already covered: the backtest A/B showed identical `S_score`.
- `engines/live_engine.py:1036` reads `candles_since_sweep` on the legacy live path (F-073, no
  production rail).
- Each would see the B0 input shift if wired. No scoring was done.

**Pre-registered:**
- P-B1, material `sweep_detected` shift: **PASS** (13.0%).
- P-B2, LIQ_SWEEP counts change: **PASS** (−33%).
- P-B3, small fusion deltas with few or no flips: **PASS, non-informative** (see B2).

## Findings to name for revalidation if activated (named, not revalidated)
These findings cite these slots in their text. Whether each one's *evidence values* would move is
UNVERIFIED per finding:
- **Directly consume slot values:**
  - F-106: engine SWEEP vs `sweep_detected` overlap 927/1792.
  - F-107: `candles_since_sweep` 47,183/47,183.
  - F-108 and F-109: planner intent counts and LIQ_SWEEP. B1 shows these move.
  - F-054: certification of FM-021 and the sweep slots. FM-090..093 are uncertified.
- **Mention `retest_depth` / FM-021 / FM-065 / liq_sweep in a naming or other context; check each:**
  F-023, F-038, F-047, F-050, F-063, F-064, F-072.
- **Whole-vector consumers that do not name the slots; check each:** F-086, F-097, F-036, F-041,
  F-045, F-059.

## Status
Diagnostic evidence only. The producer fix:
- leaves C1–C6 identical and clears every E01/C04 UNEXPLAINED row;
- reaches the CRT TP1-intent path (prior doc);
- materially changes the live-rail planner's intent and gate decisions;
- is invisible to the backtest fusion gate, because that gate never reaches its score checks.

Two Step 6 gaps are now recorded: the undeclared transitive `retest_depth` change, and an untested
live parity for `retest_depth`. No activation, system-wide-risk or economic conclusion.

## Addendum (same day): FM-021 gap closed (CH-e01-lifecycle-retest-identity)
- **Declared.** FM-094 `retest_flag_e01` (structural_states) and FM-095 `retest_depth_e01`
  (derived_metrics) are now registered in `configs/formulas/market_ontology.yaml`.
  - Both are `active: false`, with `config_key feature_pipeline.sweep_semantics`.
  - They use the same formulas and impl as FM-061 / FM-021, fed by FM-090.
  - The ontology closure of the four sweep slots is exactly FM-061 + FM-021. That matches B0's
    assertion that the other 43 vector slots are identical.
- **Live parity measured, not just argued.**
  - The "rolling-window" description above was wrong: `runtime/live_rail_feeder.py` keeps every
    pushed bar and re-runs the full pipeline each bar.
  - `tests/test_e01_sweep_semantics.py::test_live_feeder_matches_batch_at_every_prefix` shows
    `retest_depth` and the four sweep slots equal batch at all 90 ready prefixes, in both modes.
  - `test_retest_flag_follows_the_selected_sweep_identity` pins FM-094's formula to the code.
- **No emitted value changed.** The only `src/` edit is a comment; the XAUUSD vector regression passes.

## Appendix: `consumers_ab.py` (scratch instrument, reproduced verbatim)
```python
"""E01 lifecycle downstream-consumer A/B (OBSERVATION_ONLY; no src/ or config edit).

Two FeaturePipeline frames over the same corpus, identical except feature_pipeline.sweep_semantics
(ARM A = latest_unconsumed, the ACTIVE value; ARM B = e01_lifecycle). For every bar x {LONG, SHORT}:
  B0  input shift on the four sweep slots (and an assertion that the other 44 slots are identical)
  B1  ExecutionPlannerV1_2.plan (intent classifier + GateIntelligence), active planner config
  B2  EngineRunner.run (the fusion gate the backtest runs at TRADE_OPENED), active engine_runner config,
      input dict built the way backtest_v2 builds _feat_map_er
Usage: consumers_ab.py <out_json> [--limit N] [--skip-engine]
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import core.engine_runner as _er_mod  # noqa: E402
from config_layer.execution_planner import ExecutionPlannerV1_2, planner_config_from_production  # noqa: E402
from config_layer.production_config import PROD_VERSION, get_full_config_dict, get_prod_section  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

# EngineRunner appends curated telemetry to the SHARED repo logs/; silence it (observation must not
# write into other sessions' streams). Any other write is caught by the logs/ snapshot check below.
_er_mod._emit_enveloped_jsonl = lambda *a, **k: None

SWEEP = ("liquidity_sweep", "sweep_detected", "double_sweep", "candles_since_sweep",
         # FM-021, moves TRANSITIVELY: retest_flag reads liquidity_sweep != 0 (feature_pipeline.py
         # compute_structure_liquidity). Found by this script's own assert on the first trial.
         "retest_depth")
CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
out_path = Path(sys.argv[1])
limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
skip_engine = "--skip-engine" in sys.argv


def logs_snapshot():
    d = ROOT / "logs"
    return {p.name: p.stat().st_size for p in d.rglob("*") if p.is_file()} if d.exists() else {}


logs_before = logs_snapshot()
t0 = time.time()
raw = pd.read_csv(CSV)
print(f"[ab] PROD_VERSION={PROD_VERSION} csv={CSV} rows={len(raw)}", flush=True)
fp = dict(get_prod_section("feature_pipeline"))
assert fp["sweep_semantics"] == "latest_unconsumed", fp["sweep_semantics"]
frames = {}
for arm, sem in (("A", "latest_unconsumed"), ("B", "e01_lifecycle")):
    cache = out_path.parent / f"ab_frame_{arm}.pkl"   # scratch cache, keyed by arm (same corpus+config)
    if cache.exists():
        df, vec = pd.read_pickle(cache)
    else:
        df, vec = FeaturePipeline(raw, cfg={**fp, "sweep_semantics": sem}).run()
        pd.to_pickle((df, vec), cache)
    frames[arm] = (df.reset_index(drop=True), np.asarray(vec, dtype=float))
    print(f"[ab] arm {arm} ({sem}) frame rows={len(df)} vec={frames[arm][1].shape} t={time.time()-t0:.0f}s", flush=True)

dfA, vA = frames["A"]
dfB, vB = frames["B"]
assert len(dfA) == len(dfB) and vA.shape == vB.shape
assert (dfA["timestamp"].astype(str).values == dfB["timestamp"].astype(str).values).all()
sweep_idx = [CANONICAL_FEATURES.index(k) for k in SWEEP]
other = [i for i in range(vA.shape[1]) if i not in sweep_idx]
same_other = np.array_equal(np.nan_to_num(vA[:, other], nan=-9e9), np.nan_to_num(vB[:, other], nan=-9e9))
diff_cols = [CANONICAL_FEATURES[i] for i in other
             if not np.array_equal(np.nan_to_num(vA[:, i], nan=-9e9), np.nan_to_num(vB[:, i], nan=-9e9))]
assert same_other, f"non-sweep slots differ: {diff_cols}"

n = len(dfA) if limit is None else min(limit, len(dfA))
res = {"prod_version": PROD_VERSION, "csv": str(CSV), "csv_rows": len(raw), "frame_rows": len(dfA),
       "bars_evaluated": n, "non_sweep_slots_identical": bool(same_other), "B0": {}}

# ── B0 input shift ─────────────────────────────────────────────────────────────────────────
for k, i in zip(SWEEP, sweep_idx):
    a, b = vA[:n, i], vB[:n, i]
    ch = a != b
    trans = Counter((float(x), float(y)) for x, y in zip(a[ch], b[ch])) if k != "candles_since_sweep" else None
    res["B0"][k] = {"changed": int(ch.sum()), "share": round(float(ch.mean()), 6),
                    "nonzero_A": int((a != 0).sum()), "nonzero_B": int((b != 0).sum())}
    if trans is not None:
        res["B0"][k]["transitions"] = {f"{x:g}->{y:g}": c for (x, y), c in sorted(trans.items())}
print("[ab] B0", json.dumps(res["B0"]), flush=True)

# ── B1 planner + gate ──────────────────────────────────────────────────────────────────────
full = get_full_config_dict()
pcfg = planner_config_from_production(full, "XAUUSD")
planner = ExecutionPlannerV1_2(pcfg)
PKEYS = ("close", "high", "low", "atr", "body_ratio", "disp_strength", "sweep_detected", "double_sweep",
         "retest_depth", "candles_since_sweep", "ema_fast", "ema_slow", "momentum_score")
OPT = ("volume", "swing_high", "swing_low", "higher_high", "lower_low")
missing_cols = [k for k in PKEYS if k not in dfA.columns]
res["B1_missing_frame_columns"] = missing_cols


def pfeats(df, r):
    row = df.iloc[r]
    f = {k: float(row[k]) for k in PKEYS}
    f["sweep_detected"] = bool(f["sweep_detected"])
    f["double_sweep"] = bool(f["double_sweep"])
    f["candles_since_sweep"] = int(f["candles_since_sweep"])
    for k in OPT:
        if k in df.columns:
            f[k] = float(row[k])
    if "volume_ratio" in df.columns and float(row["volume_ratio"]) > 0:
        f["volume_ma20"] = float(row["volume"]) / float(row["volume_ratio"])
    return f


def plan(f, d):
    out = planner.plan({"decision": "execute", "selected_direction": d, "confidence": 0.0, "regime": "na"},
                       f, {"symbol": "XAUUSD", "signal": "BUY" if d == 1 else "SELL", "score": 0.0})
    g = out.get("gate") or {}
    return (out.get("decision"), out.get("trade_intent") or (out.get("trace") or {}).get("intent"),
            g.get("approved"), (g.get("components") or {}).get("intent_score"),
            (g.get("components") or {}).get("liquidity_score"), g.get("final_score"))


b1 = {"decisions_A": Counter(), "decisions_B": Counter(), "intent_A": Counter(), "intent_B": Counter(),
      "intent_flips": Counter(), "decision_flips": Counter(), "approved_flips": Counter(),
      "intent_score_delta_nonzero": 0, "final_score_delta_nonzero": 0, "max_abs_final_delta": 0.0}
flip_examples = []
if not missing_cols:
    for r in range(n):
        fa, fb = pfeats(dfA, r), pfeats(dfB, r)
        for d in (1, -1):
            pa, pb = plan(fa, d), plan(fb, d)
            b1["decisions_A"][pa[0]] += 1; b1["decisions_B"][pb[0]] += 1
            b1["intent_A"][str(pa[1])] += 1; b1["intent_B"][str(pb[1])] += 1
            if pa[1] != pb[1]:
                b1["intent_flips"][f"{pa[1]}->{pb[1]}"] += 1
            if pa[0] != pb[0]:
                b1["decision_flips"][f"{pa[0]}->{pb[0]}"] += 1
                if len(flip_examples) < 25:
                    flip_examples.append({"ts": str(dfA["timestamp"].iloc[r]), "dir": d, "A": pa, "B": pb})
            if pa[2] != pb[2]:
                b1["approved_flips"][f"{pa[2]}->{pb[2]}"] += 1
            if (pa[3] or 0) != (pb[3] or 0):
                b1["intent_score_delta_nonzero"] += 1
            if (pa[5] or 0) != (pb[5] or 0):
                b1["final_score_delta_nonzero"] += 1
                b1["max_abs_final_delta"] = max(b1["max_abs_final_delta"], abs((pa[5] or 0) - (pb[5] or 0)))
res["B1"] = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in b1.items()}
res["B1"]["decision_flip_examples"] = flip_examples
print(f"[ab] B1 done t={time.time()-t0:.0f}s", json.dumps({k: res['B1'][k] for k in ('decisions_A', 'decisions_B', 'intent_flips', 'decision_flips', 'approved_flips')}), flush=True)

# ── B2 EngineRunner (fusion gate) ──────────────────────────────────────────────────────────
if not skip_engine:
    from core.engine_runner import EngineRunner
    er_cfg = dict(get_prod_section("engine_runner"))
    er_cfg.setdefault("fusion_engine", dict(get_prod_section("fusion_engine")))
    for k, v in dict(get_prod_section("decision_engine")).items():
        er_cfg.setdefault(k, v)
    er_cfg["instrument"] = "XAUUSD"
    runners = {"A": EngineRunner(dict(er_cfg)), "B": EngineRunner(dict(er_cfg))}

    def er_input(df, vec, r, d):
        row = df.iloc[r]
        m = {name: vec[r][i] for i, name in enumerate(CANONICAL_FEATURES)}
        for k in ("close", "high", "low", "open", "volume"):
            m.setdefault(k, float(row[k]))
        # backtest passes engine.state.atr_abs (price units); per bar outside the engine the closest
        # declared quantity is FM-074 atr_absolute = atr * close (declared deviation).
        m.setdefault("atr", float(vec[r][CANONICAL_FEATURES.index("atr")]) * float(row["close"]))
        m.setdefault("timestamp", str(row["timestamp"]))
        m["_data_integrity"] = "real"
        m["direction"] = m["signal_dir"] = m["trade_direction"] = d
        return m

    # Backtest veto rule (backtest_v2 ~:4098): a REJECT/HOLD vetoes unless the reason is
    # feature_cluster_similarity_invalid and backtest.bypass_zone_invalid is true.
    bypass_zone = bool(get_prod_section("backtest")["bypass_zone_invalid"])

    def veto(res_):
        dec = str(res_.get("decision") or res_.get("status", "")).upper()
        if dec not in ("REJECT", "REJECTED", "HOLD"):
            return False
        return not (bypass_zone and "feature_cluster_similarity_invalid" in str(res_.get("reason")))

    b2 = {"decision_A": Counter(), "decision_B": Counter(), "decision_flips": Counter(),
          "reason_A": Counter(), "reason_flips": Counter(), "veto_A": 0, "veto_B": 0, "veto_flips": Counter(),
          "score_delta_nonzero": 0, "max_abs_score_delta": 0.0, "selected_engine_flips": Counter(),
          "bypass_zone_invalid": bypass_zone}
    ex2 = []
    for r in range(n):
        for d in (1, -1):
            ctx = {"instrument": "XAUUSD", "timeframe": "M15", "strategy_consensus_direction": d}
            ra = runners["A"].run(er_input(dfA, vA, r, d), context=dict(ctx)) or {}
            rb = runners["B"].run(er_input(dfB, vB, r, d), context=dict(ctx)) or {}
            da = str(ra.get("decision") or ra.get("status", "")); db = str(rb.get("decision") or rb.get("status", ""))
            b2["decision_A"][da] += 1; b2["decision_B"][db] += 1
            b2["reason_A"][f"{ra.get('reject_stage')}:{str(ra.get('reason'))[:60]}"] += 1
            va, vb = veto(ra), veto(rb)
            b2["veto_A"] += va; b2["veto_B"] += vb
            if va != vb:
                b2["veto_flips"][f"{va}->{vb}"] += 1
            if da != db or str(ra.get("reason")) != str(rb.get("reason")) or va != vb:
                if da != db:
                    b2["decision_flips"][f"{da}->{db}"] += 1
                else:
                    b2["reason_flips"][f"{ra.get('reject_stage')}:{ra.get('reason')} -> {rb.get('reject_stage')}:{rb.get('reason')}"[:160]] += 1
                if len(ex2) < 25:
                    ex2.append({"ts": str(dfA["timestamp"].iloc[r]), "dir": d,
                                "A": [da, ra.get("reject_stage"), ra.get("reason"), ra.get("score")],
                                "B": [db, rb.get("reject_stage"), rb.get("reason"), rb.get("score")]})
            sa, sb = ra.get("score"), rb.get("score")
            if sa != sb:
                b2["score_delta_nonzero"] += 1
                try:
                    b2["max_abs_score_delta"] = max(b2["max_abs_score_delta"], abs(float(sa) - float(sb)))
                except (TypeError, ValueError):
                    pass
            if ra.get("selected_engine") != rb.get("selected_engine"):
                b2["selected_engine_flips"][f"{ra.get('selected_engine')}->{rb.get('selected_engine')}"] += 1
        if r and r % 5000 == 0:
            print(f"[ab] B2 bar {r}/{n} t={time.time()-t0:.0f}s", flush=True)
    res["B2"] = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in b2.items()}
    res["B2"]["decision_flip_examples"] = ex2
    res["B2"]["sample_result_keys"] = sorted(ra.keys())
    res["B2"]["atr_basis_deviation"] = "atr = canonical atr * close (FM-074), not engine.state.atr_abs"
    res["B2"]["context_deviation"] = "no StrategyOrchestrator consensus score, no belief_registry"
    print(f"[ab] B2 done t={time.time()-t0:.0f}s", json.dumps({k: res['B2'][k] for k in ('decision_A', 'decision_flips', 'reason_flips', 'veto_A', 'veto_B', 'veto_flips', 'score_delta_nonzero', 'selected_engine_flips')}), flush=True)

logs_after = logs_snapshot()
res["repo_logs_changed"] = sorted(k for k in set(logs_before) | set(logs_after) if logs_before.get(k) != logs_after.get(k))
res["elapsed_s"] = round(time.time() - t0, 1)
out_path.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
print(f"[ab] wrote {out_path} repo_logs_changed={res['repo_logs_changed']} elapsed={res['elapsed_s']}s", flush=True)
```
