# Session Conversation — Gaussian Implementation Design Theory

**Date:** 2026-09-23
**Branch:** `grokbotchanges`
**Active config:** `v2_htfcrt_2026_08`
**Mode:** plan mode (design discussion only — no code, config, or retrain executed)
**Model:** Claude Opus 5
**Plan file:** `C:\Users\Hi\.claude\plans\pure-chatgpt-model-response-recursive-lagoon.md`

> Verbatim record of the session: every user turn, every assistant turn, and the tool calls
> that produced the source-verified facts. Preserved so the investigation stands alone without
> the transcript.

---

## Turn 1 — User

> Pure chatgpt model response tone and discuss on theory of design by gathering schema from
> codebse and implementation_plan for implementation refernces only no multi agent
>
> Gaussian implementation design

**Interpretation:** design-theory discussion for the Gaussian engine, schema gathered directly
from the codebase and `docs/implementation_plan/` used as reference only. Explicit constraint:
**no multi-agent / no subagents** — this overrode the plan-mode workflow's default instruction
to launch Explore and Plan agents. All investigation was done inline.

---

## Investigation — Round 1

### 1.1 Locate the Gaussian surface

```bash
ls src/engines/
```

```
__init__.py              gaussian_engine.py            llm_engine.py
crt_engine.py            heuristic_gaussian_engine.py  ml_gaussian_engine.py
live_engine.py           rr_engine.py                  scoring_engine.py
tradenet_meta_engine.py  trap_validator_engine.py      zone_cluster_score.py
zone_gate_engine.py
```

File sizes:

| File | Lines |
|---|---|
| `src/engines/gaussian_engine.py` | 33 (back-compat shim only) |
| `src/engines/heuristic_gaussian_engine.py` | 375 |
| `src/engines/ml_gaussian_engine.py` | 259 |
| `src/config_layer/crt_gaussian_scorer.py` | 213 |

Gaussian-related implementation plans found:

```
1-does-rrfusionlayer-ever-cryptic-frost.md
create-a-new-engine-valiant-chipmunk.md
d-tradelatest-active-models-yaml-d-trad-async-tulip.md
resolverengine-design-only-eager-meadow.md
trace-activemodesls-yaml-and-production-starry-robin.md
trace-gaussian-trained-model-purrfect-map.md
xauusd-gaussian-toward-economics-2026-07-23.md
```

### 1.2 `gaussian_engine.py` is a shim

```python
from engines.heuristic_gaussian_engine import (
    HeuristicGaussianEngine, GaussianRegistry, GAUSSIAN_REGISTRY_PATH,
    GAUSSIAN_MODELS_DIR, _FALLBACK_PRIORITY, _normalize_registry_entry,
)
GaussianEngine = HeuristicGaussianEngine   # backward-compat alias
```

### 1.3 `HeuristicGaussianEngine` — the live kernel

`src/engines/heuristic_gaussian_engine.py:316-376`:

```python
ema_diff      = (ema_fast - ema_slow) / ema_slow
momentum_norm = math.tanh(momentum)
x             = (ema_diff + momentum_norm) / 2.0

mu    = self.mu
sigma = self.sigma
exponent = -((x - mu) ** 2) / (2 * sigma ** 2)
score    = math.exp(exponent)
```

Registry normalisation (`:46-57`) — the default that turns out to be load-bearing:

```python
def _normalize_registry_entry(version: str, entry: dict) -> dict:
    return {
        ...
        "mu":    float(entry.get("mu", 0.0)),
        "sigma": float(entry.get("sigma", 1.0)),
        ...
    }
```

### 1.4 `CRTGaussianScorer` — a structurally different model

`src/config_layer/crt_gaussian_scorer.py`:

```python
s_retest = self._gaussian(r, self.RETEST_MU, self.RETEST_S2)
s_body   = self._gaussian(b, self.BODY_MU,   self.BODY_S2)
s_disp   = self._gaussian(d, self.DISP_MU,   self.DISP_S2)
s_time   = math.exp(-self.decay_lambda * t)

final_score = (s_retest ** 0.35) * (s_body ** 0.30) * (s_disp ** 0.20) * (s_time ** 0.15)
p_win = 1.0 / (1.0 + math.exp(-self.SIGMOID_K * (score - self.SIGMOID_X0)))
```

Two unconditional `print()` calls sit on the scoring path at `:104` and `:138`.

`extract_features` (`:178-213`) returns `None` unless both `state.displacement_candle` and
`state.retest_candle` exist — **the RETEST-only domain constraint.**

### 1.5 Active config

```bash
cat configs/production/ACTIVE_VERSION   # -> v2_htfcrt_2026_08
```

```json
"gaussian_scorer": {
  "retest_mu": 0.237, "retest_s2": 0.04,
  "body_mu":   0.847, "body_s2":   0.021,
  "disp_mu":   2.177, "disp_s2":   1.196,
  "sigmoid_k": 4.5,   "sigmoid_x0": 0.5,
  "execute_p": 0.5,   "decay_lambda": 0.0
}
```

```
engine_runner.gaussian_impl = "heuristic"

fusion_engine weights:
  weight_crt 0.4 | weight_gaussian 0.2 | weight_zone_gate 0.2 | weight_rr 0.2
```

**Note the asymmetry:** the scorer *not* in the fusion slot is the one with real
non-default parameters.

### 1.6 Registry state — the decisive check

```bash
python -X utf8 -c "
import json
r=json.load(open('models/gaussian_registry.json'))
ent=[k for k in r if not k.startswith('__')]
print('entries:',len(ent))
for inst,ver in r.get('__active__',{}).items():
    if inst=='canonical_schema_version_at_stamp': continue
    print(inst,'->',ver,'| present_as_entry=',ver in r)
print('any entry with mu?',   [k for k in ent if isinstance(r[k],dict) and 'mu'    in r[k]])
print('any entry with sigma?',[k for k in ent if isinstance(r[k],dict) and 'sigma' in r[k]])
"
```

```
entries: 14
ETHUSDT -> v5_auto_2026_06_eth       | present_as_entry= True
BNBUSDT -> p5_20260524T120449        | present_as_entry= True
XAUUSD  -> xauusd_nb_20260722T194904Z| present_as_entry= True

any entry with mu?    []
any entry with sigma? []
non-dict entries: ['_schema_v4_note']
```

**Result: 0 of 14 entries carry `mu` or `sigma`.** All three `__active__` pointers resolve to
entries that exist — so the registry load *succeeds* and still yields μ=0, σ=1. The live score
is `exp(-x²/2)` on every instrument. This is F-060, re-verified from the artifact rather than
repeated from the finding.

### 1.7 MIAR — the declared intent

`docs/governance/miar_registry.json`, entry `gaussian`:

```json
{
  "id": "gaussian",
  "intent": "How statistically conformant is this market state to previously observed market states (EMA/momentum axis)?",
  "hypothesis": "EMA-spread and momentum composite proximity tracks historical success.",
  "inputs": ["ema_fast", "ema_slow", "momentum_score"],
  "outputs": ["ema_momentum_kernel_score"],
  "semantic_meaning": "Statistical conformity score (not calibrated probability; not entry permission)",
  "consumer": ["fusion weight_gaussian", "DecisionEngine p_win (reinterpretation)"],
  "authority_boundary": "Advisory fusion vote only",
  "explicit_non_goals": [
    "never decide whether to trade",
    "never determine entries alone",
    "never classify CRT structure",
    "never claim probability without calibration"
  ],
  "falsification": "Kernel information-inert / non-pivotal (F-060)",
  "implementation_status": "EXECUTABLE",
  "alignment": "SEMANTIC_DRIFT",
  "stage": "market_understanding",
  "stage_order": 2
}
```

`MODEL_INTENT_AUTHORITY_REGISTER.md` §1 vocabulary rule:

> Calling Gaussian output a probability of win → Call it a **score** (kernel conformity)
> unless calibrated as probability

§3.4 `consumer` row:

> Fusion (`weight_gaussian`); misused as DecisionEngine `p_win` (**forbidden reinterpretation**)

### 1.8 Canonical feature surface

```bash
python -X utf8 -c "
import sys; sys.path.insert(0,'src')
from features.feature_schema import CANONICAL_FEATURES, SCHEMA_VERSION
print('SCHEMA_VERSION',SCHEMA_VERSION,'n=',len(CANONICAL_FEATURES))
"
```

```
SCHEMA_VERSION 6.0 n= 48
```

Full order: `open, high, low, close, volume, volume_ratio, double_sweep, ema_fast, ema_slow,
ema_spread, trend_bias, trend_strength_z, momentum_score, atr, volatility_ratio, rsi_14,
macd_line, macd_signal, macd_hist_raw, macd_hist_z, sweep_detected, liquidity_sweep,
break_of_structure, swing_high, swing_low, higher_high, lower_low, body_size, candle_range,
body_ratio, volatility_regime, session, hour_of_day, disp_strength, retest_depth,
candles_since_sweep, liquidity_distance, liquidity_pressure_score, volume_spike,
order_block_distance, fvg_distance, breaker_distance, mitigation_block_distance, pdh_distance,
pdl_distance, eqh_distance, eql_distance, change_of_character`

### 1.9 The `p_win` reinterpretation, in source

`src/core/engine_runner.py:1017-1020`:

```python
# Step 7: DecisionEngine — FINAL authority
selected = gate_result.get("selected", {})
p_win = _safe_float(
    engine_results.get("gaussian", {}).get("score"), 0.5
)
```

`src/core/decision_engine.py`:

```
:100  self.p_win_threshold = _require_decision_cfg(config, "p_win_threshold")
:150  if float(p_win) < float(p_win_threshold):
:170  confidence = max(0.0, min(1.0, float(p_win)))
```

### 1.10 `GaussianAdapter` docstring vs actual wiring

`src/core/fusion_engine.py:222-239`:

```python
class GaussianAdapter:
    """
    Thin adapter so FusionEngine doesn't care which scorer generation is active.
    Accepts CRTGaussianScorer, CRTCalibratedScorer, or any object with .compute().
    """
```

`src/core/engine_runner.py:411-413`:

```python
# Wrap GaussianEngine in GaussianAdapter so FusionEngine.evaluate()
self._gaussian_adapter = GaussianAdapter(self.gaussian)   # <- the HEURISTIC engine
```

### 1.11 Implementation plan read for reference

`docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md` — the ML arm already
ran end to end:

| Phase | Outcome |
|---|---|
| E0 | SHIPPED — 3,247 units (2,980 train + 267 oos), dim 39, score fails 0 |
| E1 | SHIPPED — OOS top_decile E[R] **−0.451** (n=174), all_units **−0.532**, random **−0.638**; verdict `SKILL_SIGNAL_RESEARCH_ONLY` (top beats controls but all E[R] < 0) |
| E2 | SHIPPED — M4 `any_PROMOTE=False`; `nb_top_decile` **REJECT** at gate2_expectancy E[R] = −0.25; `all_units` REJECT at −0.96 |
| E3 | Not reached |

Header rule from that doc, carried forward: **`REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY`.**

---

## Turn 1 — Assistant response

**Scope:** design theory for the `gaussian` slot — read the actual schema (MIAR intent, config,
registry, feature surface, call sites) and the existing implementation plan for reference only.
No subagents, no code.

### 1. Start from the contract, not the code

The schema is unusually explicit here, which makes the design question tractable. MIAR locks
the Gaussian to one canonical question:

> *How statistically **conformant** is this market state to previously observed market states?*

Stage `market_understanding`, order 2 — after CRT, before ZoneGate. Output is
`ema_momentum_kernel_score ∈ [0,1]`, and MIAR is emphatic that it is a **score**, not a
probability. The non-goals are enumerated: never decide whether to trade, never determine
entries alone, never classify CRT structure, never claim probability without calibration.
Alignment is flagged `SEMANTIC_DRIFT`.

So the target object is a *descriptive conformity measure over a reference population, with no
decision authority*. That framing does most of the design work, because it immediately tells
you what the current code is not.

### 2. "Gaussian" currently names three incompatible objects

This is the finding that reframes the whole design, and it's visible only by reading all three
files side by side:

**(a) `HeuristicGaussianEngine`** — the live one. Computes
`x = (ema_diff + tanh(momentum_score))/2`, then `exp(-(x-μ)²/2σ²)`. μ/σ come from
`GaussianRegistry`, whose `_normalize_registry_entry` defaults to `mu=0.0, sigma=1.0`. Verified
on disk: **0 of 14 registry entries carry a `mu` or `sigma` key.** All three `__active__`
pointers resolve to entries that exist — so the load *succeeds* and still produces
`exp(-x²/2)`. No learned parameter reaches the score on any instrument.

**(b) `CRTGaussianScorer`** — a structurally different model: four Gaussian kernels over
retrace/body/displacement plus time decay, combined as a weighted geometric mean, then a
sigmoid to `p_win`. Its parameters *are* declared and non-default in the active config's
`gaussian_scorer` section. The irony is architectural: the scorer with real empirical
parameters isn't in the fusion slot, and `GaussianAdapter`'s own docstring says it accepts
`CRTGaussianScorer` — while `engine_runner.py:413` actually wraps the heuristic engine.

**(c) `MLGaussianEngine`** — GaussianNB over the canonical vector. A class-conditional Gaussian
genuinely *is* a density over previously observed states, so this is the only one of the three
that literally answers the MIAR question. It's config-gated off.

These are not versions of one another. One is a 1-D trend conformity kernel, one is a
setup-quality scorer with a probability head, one is a generative density model.

### 3. Four questions that must be answered before any math is written

**Reference population.** "Previously observed states" is nowhere defined in code. All bars?
CRT-committed bars? Winning trades? This single choice decides whether the engine stays
MIAR-legal — a density over all bars is honest conformity, a density over winners is an
outcome model smuggled into a descriptive Stage-1 slot. F-060's third leg is exactly this
failure: the builder of record is `phase5_calibration.py`, training on raw `rr_achieved` from
the F-022 stream.

**Dimensionality.** The canonical surface is **48 dims at `SCHEMA_VERSION 6.0`** (verified by
import). Scaling a kernel up to the vector walks into F-044's proof: for a rank-*k* Mahalanobis
form, in-distribution `E[d²] = k`, so `exp(-d²/2)` floors at `exp(-k/2)`. At rank 27 that was
~1.4e-6 and *not one training point* cleared a 0.3 threshold. The same algebra applies. Any
density-based Gaussian above ~4 dims needs a dof-aware mapping — χ² survival function or
`d²/dof` — designed in from the start, not patched later.

**Output type and reader.** `engine_runner.py:1017-1020` does
`p_win = engine_results["gaussian"]["score"]` and hands it to `DecisionEngine`, which
thresholds it against `p_win_threshold` and returns it as `confidence`. A Stage-1 descriptive
conformity number is the gating probability for the final approve/reject. MIAR names this path
a *"forbidden reinterpretation"* in two separate places. This is a contract defect independent
of what the kernel computes.

**Basis degeneracy.** `momentum_score` carries the FM-022/023 dimensional mix (F-061/F-064):
`legacy ≡ corrected × close`. `|tanh(momentum_score)| > 0.999` on 99.70–99.81% of XAUUSD bars.
The live `x` is dominated by a saturated term — which is the mechanical reason F-060 measured
score ≈ 0.8825 with std 3e-3. **Fitting μ/σ on the current basis is fitting noise around a
constant.**

### 4. The options and what each actually trades

| | Option | Buys | Costs |
|---|---|---|---|
| **A** | Populate `mu`/`sigma`, keep the 2-feature kernel | Cheap, additive, hash-neutral; turns a constant into a kernel | Fits a saturated input; requires `normalization_basis: corrected` first or it's cosmetic; doesn't close SEMANTIC_DRIFT |
| **B** | Re-found as a density/novelty model on a declared population | Only option that literally answers the MIAR question | Needs the reference population as an ontology node, shrunk covariance, dof-aware mapping; largest surface |
| **C** | Promote `CRTGaussianScorer` into the slot | Already parameterised and empirically calibrated | Answers a *different* question — it's a MIAR intent edit, not a code change; and it emits `p_win`, legitimising the reinterpretation rather than fixing it |
| **D** | Retire the slot | Honest under §6.5 — F-060 measured all 3 ablation cells byte-identical across four majors, gate-ON | Touches `EXPECTED_ENGINES` and forces renormalising `weight_gaussian: 0.2`; n=26 proves non-pivotality, not worthlessness |

### 5. What the theory implies about ordering

The dependencies are strict: you can't fit the model until the reference population is
declared, and you can't measure the fit until the basis is de-saturated. So the sequence is
forced — sever the `p_win` contract first (cheapest, highest severity, correct under *every*
option), declare the population as an ontology node, measure under `corrected`, *then* choose A
or B with a dof-aware mapping, and only then attempt ΔG001 via the F-036/F-070 byte-diff
method.

One thing worth stating plainly: `xauusd-gaussian-toward-economics-2026-07-23.md` already ran
the ML arm end to end. E0/E1/E2 all shipped; M4 returned **0 PROMOTE**, `nb_top_decile` REJECT
at E[R] = −0.25. That plan's own header rule is the right frame for anything downstream here:
`REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY`.

---

## Turn 2 — Clarifying questions and user answers

**Q1 — Direction:** Which of A/B/C/D should be developed further?
**Answer: B — density/novelty re-found.**

**Q2 — `p_win` sever treatment:** own authorised turn / fold into chosen option / design
discussion only?
**Answer, verbatim:**

> Desing discssion only for now and i need all 3 gaussian as parallel models doing with their
> own instructions on backtest and will monitor outputs let know any ambugity

**Three instructions extracted:**
1. Develop Option B.
2. `p_win` sever stays at theory level — documented, not scoped.
3. **New requirement:** all three Gaussians run as parallel models in backtest, each under its
   own contract, outputs monitored. Flag any ambiguity.

---

## Investigation — Round 2 (triggered by the parallel-models requirement)

### 2.1 Does EngineRunner even run in backtest?

```bash
python -X utf8 -c "
import json
c=json.load(open('configs/production/v2_htfcrt_2026_08.json'))
print('backtest.engine_gate_enabled =', c.get('backtest',{}).get('engine_gate_enabled'))
"
```

```
backtest.engine_gate_enabled = True
```

Yes — F-070's epoch. Relevant `backtest_v2.py` lines:

```
3064:  # ── EngineRunner gate (live-mode pipeline wired into backtest) ────────
3074:  _gps_bt("backtest"), "engine_gate_enabled", "backtest"
3113:  from core.engine_runner import EngineRunner as _ER
3586:  # ── EngineRunner gate (adapter / fusion / dual / decision) ──
3587:  _engine_vetoed = False
3704:  note=f"veto_mode=post_commit engine_gate_enabled=true decision={_decision}"
```

### 2.2 The blocking structural fact — what guards the call site

Walked the enclosing block structure backwards from the gate at line 3586:

```bash
python -X utf8 -c "
from pathlib import Path
L=Path('src/runtime/backtest_v2.py').read_text(encoding='utf-8',errors='replace').splitlines()
gate=3585
base=len(L[gate])-len(L[gate].lstrip())
cur=base
for i in range(gate,3200,-1):
    s=L[i]
    if not s.strip(): continue
    ind=len(s)-len(s.lstrip())
    if ind<cur and s.strip().startswith(('if ','for ','elif ','else','while ','try','with ','def ')):
        print(i+1,'|',s.rstrip()[:160]); cur=ind
    if cur<=12: break
"
```

```
gate indent 16
3419 |             if "TRADE_OPENED" in action and engine.state.active_trade:
```

**Decisive.** All four engines — Gaussian included — are evaluated only on bars where the CRT
state machine has already committed a trade. Measured population on that path (F-070): 30
committed entries across all four crypto majors combined (BNB 13, ETH 5, BTC 5, SOL 7); XAUUSD
thinner still.

### 2.3 The existing shadow pattern (precedent for Host 1)

`src/core/engine_runner.py:739-752`:

```python
# Shadow ML comparison (shadow_ml mode only).
# Heuristic score already in gaussian_result["score"] → enters fusion unchanged.
# ML score attached under ["shadow"] → logged to engines_raw, never in fusion.
if self.gaussian_shadow is not None:
    try:
        _sh = self.gaussian_shadow.compute(input_data, direction=_gauss_dir)
        gaussian_result["shadow"] = {
            "score":     _sh["score"],
            "reason":    _sh.get("reason", "shadow_ml"),
            "meta":      _sh.get("meta", {}),
            "delta":     round(_sh["score"] - gaussian_result["score"], 4),
            "agreement": bool((_sh["score"] >= 0.5) == (gaussian_result["score"] >= 0.5)),
        }
    except Exception as _se:
        logger.debug("EngineRunner: shadow gaussian compute failed — %s", _se)
```

Selector (`:301-341`): `gaussian_impl` ∈ `heuristic` | `ml` | `shadow_ml`. Persistence sink:
`engines_raw` via `src/core/collector.py:137`.

### 2.4 Existing test surface

```
tests/test_crt_gaussian_scorer_direction_compat.py
tests/test_gaussian_impl_switch.py
tests/test_gaussian_live_parameterization.py
tests/test_gaussian_nb_schema_contract.py
tests/test_gaussian_registry_retry_cache.py
tests/test_gaussian_update_pipeline.py
tests/test_xauusd_gaussian_econ_ledger_e1.py
tests/test_xauusd_gaussian_econ_units_e0.py
tests/test_xauusd_gaussian_m4_e2.py
```

---

## Turn 2 — Assistant response

**Option B taken as the direction, `p_win` held at theory level.** The parallel-models
requirement turned up one blocking structural fact and two design ambiguities that can't be
resolved without a decision.

### The constraint that decides the shape of the harness

`backtest.engine_gate_enabled` is `true` on the active config, so EngineRunner genuinely runs
in backtest. But the call site is guarded:

> `src/runtime/backtest_v2.py:3419` — `if "TRADE_OPENED" in action and engine.state.active_trade:`
> … enclosing the EngineRunner gate at `:3586` (`veto_mode=post_commit`).

**All four engines are evaluated only on bars where CRT already committed a trade.** F-070
counted 30 committed entries across all four crypto majors combined; XAUUSD is thinner.

So if the three Gaussians go where the Gaussian currently lives, you'd be monitoring three
models on **n ≈ 3–30** — below every power floor in the repo. Not a reason not to do it, but it
answers a narrower question than "monitor outputs" implies.

There are two hosts and they answer different things. **Host 1** extends the existing
`shadow_ml` pattern inside EngineRunner — that tells you what each model *would have said on
the trades you actually took*. **Host 2** is a standalone per-bar harness scoring all three on
every bar's canonical vector — the F-086/F-097 shape, 47k bars / 94k bar×direction units. That
tells you how the three models *behave and whether they agree*. Only Host 2 has the power to
monitor anything; only Host 1 is decision-relevant.

### Two things that make "all 3 in parallel" not constructible as stated

**Domain disjointness.** `CRTGaussianScorer.extract_features` (`:178-213`) returns `None`
unless both `displacement_candle` and `retest_candle` exist — it is a **RETEST-bar-only**
model. The heuristic needs 3 features and works on any bar; ML/B need the full vector and work
on any bar. So a per-bar panel is necessarily **ragged**: three columns, one populated only on
its natural domain. The temptation will be to fill the gap with a neutral 0.5 — that's the
F-079/F-085 silent-gap class, where a skipped measurement becomes indistinguishable from an
absent one. Recommendation: absent-and-explicitly-typed.

**Scale incomparability.** The heuristic emits `exp(-x²/2)`, the CRT scorer emits a weighted
geometric mean plus a `p_win` sigmoid, ML emits `sigmoid(expected_rr)`, and B would emit a χ²
tail. The existing shadow block computes `delta = shadow − production` and
`agreement = (both ≥ 0.5)` — both are scale assumptions that don't hold across these three. The
comparison metric has to be declared before the first run, not picked after seeing output.

### On Option B specifically

Four constraints it has to satisfy by construction, in dependency order: a **declared reference
population** as an ontology node before any math (this is what keeps it a conformity model
rather than an outcome model smuggled into a descriptive slot); a **dof-aware mapping** from
the first line, because F-044 already proved `exp(-d²/2)` floors at `exp(-k/2)` and no training
point cleared the threshold at rank 27; an explicit **covariance conditioning** choice with the
effective dof recorded alongside the score; and **basis de-saturation**, since
`|tanh(momentum_score)| > 0.999` on 99.7%+ of XAUUSD bars.

The pleasing part: the dof-aware constraint forces B's output to be a tail probability, which
is a *conformity* quantity, not a win probability — so B is MIAR-legal by construction rather
than by discipline.

### Ambiguities needing a decision

1. **Is B the third model or a fourth?** {heuristic, CRT-scorer, ML} with B replacing ML later,
   or {heuristic, CRT-scorer, B} with ML retired — different harnesses.
2. **Host 1, Host 2, or both?**
3. **Does the fusion input change?** Keeping heuristic authoritative and shadowing the other two
   is byte-identical. Making all three purely observational moves the `weight_gaussian: 0.2`
   input and therefore the ledger.
4. **Persistence sink** — `engines_raw` (existing) or a new JSONL? A new stream is a governed
   claim surface and needs a `CC-*` class before anything asserts what it proves.

Minor but real: `CRTGaussianScorer` has unconditional `print()` at `:104` and `:138`. On a
47k-bar harness that's ~94k stdout lines.

---

## Turn 3 — User

> Add the entire conversation into md file and add inside userinvestigation folder

Folder verified to exist (`D:\Tradelatest\userinvestigation`, 5 files) with the convention
`session_conversation_YYYYMMDD_HHMM.{html,jsonl}` already in use — this `.md` matches it.
Written with the Write tool rather than a Bash heredoc per CLAUDE.md §1.6.

---

## Summary of source-verified facts established this session

| # | Fact | Evidence |
|---|---|---|
| 1 | 0 of 14 `gaussian_registry.json` entries carry `mu`/`sigma`; all 3 `__active__` pointers resolve | direct JSON inspection |
| 2 | Live Gaussian score is therefore `exp(-x²/2)` on every instrument — load succeeds, no learned parameter reaches the score | `heuristic_gaussian_engine.py:46-57, 316-376` |
| 3 | "Gaussian" names three structurally incompatible objects (trend kernel / setup scorer + p_win head / density classifier) | three source files read side by side |
| 4 | `GaussianAdapter` docstring names `CRTGaussianScorer`; `engine_runner.py:413` wraps the heuristic engine | `fusion_engine.py:222-239` vs `engine_runner.py:411-413` |
| 5 | `engine_runner.py:1017-1020` feeds `gaussian.score` as `DecisionEngine` `p_win` — MIAR's named "forbidden reinterpretation" | source + MIAR §3.4 |
| 6 | Canonical surface is 48 dims at `SCHEMA_VERSION 6.0` | `from features.feature_schema import ...` |
| 7 | **EngineRunner in backtest is guarded by `if "TRADE_OPENED" in action and engine.state.active_trade:`** — all four engines evaluated only on CRT-committed bars | `backtest_v2.py:3419` enclosing `:3586` |
| 8 | `CRTGaussianScorer` is RETEST-bar-only — `extract_features` returns `None` without displacement + retest candles | `crt_gaussian_scorer.py:178-213` |
| 9 | The three model outputs are scale-incomparable; existing `delta`/`agreement` metric does not transfer | `engine_runner.py:745-749` |
| 10 | The ML arm's economic program already closed: M4 **0 PROMOTE**, `nb_top_decile` REJECT at E[R] = −0.25 | `xauusd-gaussian-toward-economics-2026-07-23.md` §E2 |

## Open decisions carried forward

1. Is B the third model or a fourth (does ML stay or retire)?
2. Host 1 (EngineRunner shadow, n≈30, decision-relevant) / Host 2 (per-bar, n≈47k, powered) / both?
3. Does the fusion input change, or does heuristic stay authoritative (byte-identity)?
4. Persistence sink — `engines_raw` vs a new `CC-*`-catalogued JSONL?
5. Reference population for B — blocking for B, must be an ontology node before any math.
6. Comparison metric, declared before the first run.
7. `CRTGaussianScorer`'s missing domain — absent/typed (recommended) vs neutral fill (silent-gap class).
8. `CRTGaussianScorer`'s two unconditional `print()` calls.

## Held at theory level by explicit user decision

- The `p_win` sever (`engine_runner.py:1017-1020`). Documented as a named contract defect. No
  change scoped, no authorised turn opened.

## Anti-scope

- No retrain on F-022-derived labels.
- No `gaussian_impl=ml` flip — that program ran end to end and returned 0 PROMOTE.
- No probability language in any output contract.
- No authority claim from a parallel-observation run. Agreement between three models is
  information about the models, not about the market (§6.5 rung 1).
