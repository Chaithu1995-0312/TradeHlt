# Setup overlay + run unit — spec (EPIC-83 / STORY-83.3)

Created: 2026-09-27
Updated: 2026-09-27

**Status: SPEC ONLY.** No code, no behaviour change, no new layer, no new doctrine.
**Authority: NONE** (CLAUDE.md §6.5). This document describes; it grants nothing, promotes nothing,
and measures nothing.

- Base commit: `d318f13` (`grokbotchanges`). Worktree: `D:\Tradelatest-wt-wpC-setup-spec`, branch `lane/wpC-setup-spec`.
- Owned file: **this document only**. No other file was edited to write it.
- Every factual claim below cites `file:line`, or the exact command and its output. Anything not
  re-verified in the session that produced this spec is listed under §11.

Environment checks run before writing (outputs quoted in §11):
`git -C <wt> rev-parse --abbrev-ref HEAD`; `configs/production/ACTIVE_VERSION`;
`PYTHONPATH=<wt>\src python -c "import runtime.backtest_v2 as m; print(m.__file__)"`;
sha256 + line count of `data/mt5/XAUUSD_M15.csv`.

---

## 1. The problem this spec solves

Today the codebase is one thing used two ways: a research lab and a production rail, separated by
nothing but which config file is pointed at and which driver script is run. The target shape is:

- **Setup** = the v5 shadow config + a small, declared overlay.
- **The lab** runs **N Setups** through the **same** L0–L9 path — a layer is never re-implemented for research.
- **Production** = **one promoted Setup**.

This document specifies (a) the overlay and (b) the run unit. It does not build either. The layer
names used here are the identity-contract names
(`docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md:65-72`); the `L0`–`L9` numbers are used only
where they are already a runtime trace index (`src/runtime/layer_trace.py:83`, `:88-95`), never as a
claim that `L(n+1)` is computed from `L(n)` (`CANONICAL_LAYER_IDENTITY_CONTRACT.md:63`).

---

## 2. Definitions (every term maps onto vocabulary that already exists)

| Term | Definition | Where it already lives |
|---|---|---|
| **Setup** | The v5 shadow config **plus** the declared overlay of §3. A value, not an authority. | v5 file `configs/production/v5_htfcrt_sot_dual_k23_2026_09.json` (planned, S1/WP-E — **absent at BASE**, verified: `Get-ChildItem configs\production -Filter '*v5*'` → empty) |
| **Overlay** | The named keys of §3.3. Each key's DEFAULT equals today's behaviour exactly. | New keys, declared in the v5 file only (§3.2) |
| **Overlay key at default** | Byte-for-byte today's behaviour, including all downstream identity stamps. | §8 |
| **Decider** | The authority that **founds** a setup. `engine` = today. `resolver` = "mode C" (§5). | Founding site `src/config_layer/crt_engine_v2.py:3596-3601` |
| **Run unit** | One `ExperimentSpec` = N Setups × corpus (§7). | `src/research/experiment_spec.py:116-166` |
| **Promoted Setup** | Exactly one Setup, chosen at S5 by hand registration. Not specified here. | — |

Non-goals (explicit): no new layer; no new measurement basis; no change to
`src/governance/measurement_basis.py`; no config file other than the v5 shadow; no promotion path;
no re-implementation of any layer by research.

---

## 3. The overlay (S3)

### 3.1 What the overlay is

Seven keys. One already exists today (`sl_anchor`) and three more are the K23 switches F1/F2/F4 —
all four are live config keys; three are new (`target_policy`, `trade_ttl_candles`, `decider`). Every
one of them is declared, type-checked, and **defaulted to today's behaviour**, so "all keys at
default" is the v5 rail itself (§8).

### 3.2 The key table

`Section` gives **both** placement options — see §3.3 for the choice, left open in §10 Q1.

| # | Key | Section (Option A) | Section (Option B) | Type | Allowed values | **DEFAULT (= today's behaviour)** |
|---|---|---|---|---|---|---|
| 1 | `sl_anchor` | `backtest` (exists) | `backtest` (exists) | str | `displacement` \| `sweep_extreme` | `"displacement"` |
| 2 | `target_policy` | `setup` (new) | `backtest` | str | `fixed_r` \| `structural_tp2` | `"fixed_r"` |
| 3 | `trade_ttl_candles` | `setup` (new) | `backtest` | int \| null | `>= 1` \| `null` | `null` (= no time-stop) |
| 4 | `decider` | `setup` (new) | `backtest` | str | `engine` \| `resolver` | `"engine"` |
| 5 | `retrace_reset_pct` (K23 F1) | `crt_engine` (exists) | `crt_engine` | float | `(0, 1]` | `0.5` |
| 6 | `session_window_basis` (K23 F2) | `backtest` (exists) | `backtest` | str | `broker_static` \| `exchange_local` | `"broker_static"` |
| 7 | `htf_reset_exempt_sweep` (K23 F4) | `backtest` (exists) | `backtest` | bool | `true` \| `false` | `false` |

Keys 5–7 are the K23 switches and must **not** be re-declared under new names: the overlay lists
them because a Setup has to be able to state them, and they already are config keys (§3.4).

### 3.3 Where the three new keys are declared — **both options, no recommendation**

**Option A — one new top-level `setup` section** holding keys 2–4 (`setup.target_policy`,
`setup.trade_ttl_candles`, `setup.decider`).
Precedent for a declared top-level section read by the run and tolerated when absent:
`LayerTraceConfig.from_prod_config` (`src/runtime/layer_trace.py:118-130`), read at
`src/runtime/backtest_v2.py:2700-2760`; strict-key precedent inside a *present* section:
`layer_trace.py:96-105`, `backtest_v2.py:136-145`.

**Option B — spread over the existing `backtest` section, K23-style**
(`backtest.target_policy`, `backtest.trade_ttl_candles`, `backtest.decider`).
Precedent: K23 F2/F4 are exactly this shape — optional keys in `backtest`, threaded into the engine
as constructor kwargs (`backtest_v2.py:272-284` → `:2997-3004`).

Facts that hold for **either** option (so the choice is cheap to change):

- **Hash-neutral.** `config_hash` is computed over the `params` block only
  (`src/config_layer/production_config.py:89-92`), so a section outside `params` cannot move it.
  Two independent precedents say the same in prose: the k23 shadow's own note — *"params block
  untouched, so config_hash is unchanged"* (`configs/production/v2_htfcrt_k23_shadow_2026_09.json:1099`)
  — and the v3 parity harness — *"v3 differs from v2 only by three new hash-neutral top-level
  sections"* (`scripts/analysis/v3_config_parity.py:16-17`).
- **`ConfigBuilder` is unaffected.** It validates only *override keys against `CRTConfig` field
  names* (`src/config_layer/config_builder.py:51-53`, `:102-106`); it does not police top-level
  sections. Neither option requires a `CRTConfig` field, and neither trips the "unknown keys raise
  ValueError" rule (`config_builder.py:83`).
- **Names are free.** Verified against the v5 base candidate: `Select-String` for
  `"target_policy" | "decider" | "setup" | "trade_ttl_candles" | "structural_tp2" | "sl_anchor"` over
  `configs/production/v2_htfcrt_k23_shadow_2026_09.json` returns **only** `:516 "sl_anchor":
  "sweep_extreme"`. Repo-wide, `target_policy`, `trade_ttl_candles` and `structural_tp2` have **no
  hits** in `src/ configs/ tests/ docs/`.
- **Do NOT name the Setup's identity `setup_id`.** That identifier is already allocated to a
  different object — the CRT setup/cycle grouping used as a measurement population unit:
  `configs/research/measurement_contracts/instances/MC-CRT-SB-XAUUSD-M15-V1.json:32`,
  `docs/governance/measurement_contract.schema.json:125`, `docs/governance/MEASUREMENT_CONTRACT.md:53`.
  The identity contract is explicit that this freeze allocates no such id for our object:
  *"A setup / cycle (RANGE→…→RESOLUTION) is a derived grouping of occupancies, not a primary object
  of this freeze. No canonical `setup_id` is allocated here. Engine `Trade.id` is L4 lineage, not
  L3."* (`docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md:358`). Reusing it would be a register
  collapse of the class named at `CANONICAL_LAYER_IDENTITY_CONTRACT.md:74`. The overlay's identity
  name is therefore left open (§10 Q6); the *object* is specified in §4.

### 3.4 Consumer sites, key by key

**1 · `sl_anchor` — exists today; no new code required.**
- Read and validated: `src/runtime/backtest_v2.py:337-343` (raises unless `displacement` | `sweep_extreme`).
- Field default `:278`; full-prod read `:362-390`; stamped `:1545`, `:1607`.
- Threaded to the engine: `:2997-3004` — `CRTEngine(..., sl_anchor=self.cfg.sl_anchor)`; and to the journal `:3043`.
- Consuming guard: `src/config_layer/crt_engine_v2.py:2331-2337` (`ExecutionEngine.__init__` raises on anything else).
- Consuming formula: `:2446-2454` — LONG `sl = sweep_event.candle.low - sl_atr_buffer*atr`, SHORT `sl = sweep_event.candle.high + sl_atr_buffer*atr`. Legacy branch: `:2455-2464` (`displacement_candle.low/high ∓ sl_atr_buffer*atr`).
- Identity consequence: `TradeJournal.__init__` stamps `reference_level = SL_ANCHOR_REFERENCE_LEVEL[sl_anchor]` (`backtest_v2.py:1200`; map `:181-184`) → `displacement_extreme` | `sweep_extreme`, both members of `REFERENCE_LEVELS` (`src/governance/measurement_basis.py:57-64`). This is what makes cross-anchor R ranking illegal (§7.3).
- Oracle counterpart (research side only): `src/research/oracle/labeler.py:89`, `:106`.

**2 · `target_policy` — new.** Consuming site: `ExecutionEngine.build_trade`,
`src/config_layer/crt_engine_v2.py:2489-2503`. Today's `fixed_r` branch **is** those lines:
`risk_dist = abs(entry - sl)`; `_tp1_mult = getattr(config, f"tp1_atr_multiplier_{intent}", config.tp1_atr_multiplier)`;
`_tp2_mult = config.tp2_atr_multiplier`; `tp1 = entry ± _tp1_mult*risk_dist`; `tp2 = entry ± _tp2_mult*risk_dist`.
Intent comes from `_derive_trade_intent` (`:2382-2419`, reading the CRT-local `cached_features` dict).
`fixed_r` is therefore today's behaviour by construction: TP1 = `tp1_atr_multiplier_<intent>` × R,
TP2 = `tp2_atr_multiplier` × R (values `configs/production/v2_htfcrt_k23_shadow_2026_09.json:237-242`:
1.0 / 2.0, breakout 1.5, pullback 0.8, liq_sweep 1.2, reversal 1.0).

`structural_tp2` = opposite side of the active range. `active_range` is bound at `:2430`
(`rng = state.active_range`), and its geometry is `M15StructuralLiquidityRange.h_ref` / `.l_ref`
(`src/config_layer/m15_structural_range.py:40-41`; `Range` **is** that type, `crt_engine_v2.py:49`).
So LONG → `tp2 = rng.h_ref`, SHORT → `tp2 = rng.l_ref`. Whether TP1 also moves is §10 Q2.

Downstream consumers that inherit the change: `update_trade` `:2564` (`hit_tp2`), `:2568-2577`
(runner 50 % PnL); ledger reason via `_resolve_exit` `backtest_v2.py:1675-1683`;
`Trade.risk_reward_tp1` `:225-229`; hit counters `backtest_v2.py:1742-1743`.

**Gap the implementation must close:** there is **no inverted-TP guard** today — `build_trade` guards
only the stop (`:2470-2488`). A structural TP2 can land on the wrong side of entry (a LONG whose
entry is already above `h_ref`; a range narrower than the risk leg), and nothing rejects it today.
That is a decision, not an oversight to patch silently (§10 Q2).

**3 · `trade_ttl_candles` — new.** The carrier field already exists and is **inert**:
`Trade.open_candle_index: int = 0  # [P1] candle index at open, for time-stop tracking`
(`crt_engine_v2.py:217`). `git grep -n open_candle_index -- src` returns that single line and nothing
else — never assigned, never read. A TTL would set it at construction (`:2521-2535`) or at open
(`open_trade` `:2544-2547`) and compare it in the per-bar exit resolution: `_resolve_exit`
(`backtest_v2.py:1635-1684`, called at `:4039`) and/or `ExecutionEngine.update_trade` (`:2549-2608`),
which today takes `(trade, current_price)` and has **no** candle argument — the TTL needs the candle
index plumbed to whichever of the two is chosen (§10 Q3).

Outcome `TIMEOUT` already has an authority on the research side:
`src/research/oracle/multi_tp_walk.py:71` (`OUT_TIMEOUT = "TIMEOUT"`), vocabulary `:68-71`,
`OracleOutcome.outcome` `:82`, `forward_walk.py:214`. The **ledger** has no `TIMEOUT` exit_reason yet
(`_resolve_exit` emits `TP1`/`TP2`/`STOPPED`/`TP1_BE_STOP`/`TP1_TP2`/`STOPPED_STRUCTURAL`/`TP1_STRUCTURAL_STOP`,
`:1661-1684`), so this key adds the fourth canonical outcome name to the CRT rail (§10 Q3).
Pricing at expiry already has a menu: `TIMEOUT_MARK_TO_CLOSE` | `TIMEOUT_TRAIL`
(`multi_tp_walk.py:63-65`, applied `:350-356`).

Default `null` = no time-stop = today. Verified: no trade time-stop exists anywhere in `src/`. The
only `ttl`-named quantities are CRT-*state* TTLs (`pending_displacement_ttl_candles`,
`src/config_layer/state_identity.py:249`) and the planner's `ttl_<intent>_sec`
(`configs/production/v2_htfcrt_k23_shadow_2026_09.json:61-73`).

Side effect the key must answer for: `wins`/`losses` are **R-signed, not exit-signed** —
`m.wins = sum(1 for t in trades if t.pnl_rr_net > 0)`, `m.losses = sum(1 for t in trades if t.pnl_rr_net <= 0)`
(`backtest_v2.py:1740-1741`), and `win_rate = wins/(wins+losses)` (`:1554-1557`). A TIMEOUT that
closes flat therefore counts as a **loss** today (§10 Q3).

**4 · `decider` — new.** See §5.

### 3.5 The K23 switches, as they exist today (keys and current values)

| K23 | Key | Active value | k23 shadow value | Consumed at |
|---|---|---|---|---|
| F1 | `crt_engine.retrace_reset_pct` | `0.5` (`configs/production/v2_htfcrt_2026_08.json:244`) | `0.618` (`v2_htfcrt_k23_shadow_2026_09.json:245`) | `ResetLogic.should_reset`, `crt_engine_v2.py:2684-2690` (`retrace >= self.config.retrace_reset_pct`) |
| F2 | `backtest.session_window_basis` (+ `backtest.exchange_session_windows`) | absent → `"broker_static"` | `"exchange_local"` + TOKYO 09:00-18:00 Asia/Tokyo, LONDON 08:00-17:00 Europe/London, NEWYORK 08:00-17:00 America/New_York (`:498-515`) | load + fail-closed requirement `backtest_v2.py:344-360`; engine `:2997-3003`; session stats `:4407-4413`; `crt_engine_v2.py:1976`, `:2022-2023` (session filter **and** `score_time` share the same windows) |
| F3 | `backtest.sl_anchor` | absent → `"displacement"` | `"sweep_extreme"` (`:516`) | key #1 above |
| F4 | `backtest.htf_reset_exempt_sweep` | absent → `false` | `true` (`:517`) | `ResetLogic.__init__` `crt_engine_v2.py:2645-2649`, rule `:2672-2673`; threaded `backtest_v2.py:330-336`, `:2999` |

F1 lives under `crt_engine`; F2/F3/F4 under `backtest`. A Setup that states F1 therefore already
touches **two** sections — which is why "move everything into one section" is not one of the options
in §3.3: it would require re-declaring F1, and §3.2 forbids duplicate keys.

### 3.6 Load rules

1. **Absent key = the DEFAULT in §3.2.** Present key = strictly validated; a bad value raises **at
   load**, never at first use (precedent: `backtest_v2.py:337-360`).
2. **No silent defaults for a present key.** A partially written section fails rather than
   half-applying; the strict-reader idiom is `backtest_v2.py:136-145` (`_require_bt_cfg`) and
   `runtime/layer_trace.py:96-105` (`_require`).
3. **The overlay never guesses.** `null` means "no time-stop", not "pick a value" (key 3); `0.5`,
   `broker_static`, `displacement`, `false` are the **declared** legacy values, not fallbacks.
4. **Grants no authority.** The overlay is read into an execution-side value object (§4) consumed by
   the engine and the runner. Nothing here can promote; `ACTIVE_VERSION` is resolved read-only by
   `src/config_layer/production_config.py:57`, `:60-79` and is not part of this spec.

### 3.7 Stamping — the run must describe itself

Every overlay key with a non-default value must appear in the run's own stamp set, or a parity diff
cannot see what ran. This is the K23 precedent, verbatim in intent: `htf_reset_exempt_sweep`,
`sl_anchor` and `session_window_basis` are `BacktestMetrics` fields *"stamped so a run is
self-describing"* (`backtest_v2.py:1544-1546`), emitted in `to_dict()` (`:1606-1608`) and threaded
into `MetricsEngine.compute` (`:4204-4211`). `target_policy` and `trade_ttl_candles` change the
ledger, so a run that does not stamp them is not reproducible from its own outputs.

---

## 4. Where the Setup object lives (execution side)

**Location.** `src/config_layer/setup.py` — new file, execution-side (WP-K owns `config_layer/*setup*`).
There is no existing module to copy: `git ls-files -- src/config_layer` lists 35 files and none matches
`setup` (`state_identity.py:253` and `config_validator.py:44` use the *word* "setup" in prose only).

**Shape.** A frozen value object with the seven fields of §3.2, built from the resolved production
config by a `from_prod_config()` classmethod — exactly the idiom of `LayerTraceConfig.from_prod_config`
(`src/runtime/layer_trace.py:108-130`): read once, frozen, never re-read mid-run.

**Dependency direction: research imports execution; execution never imports research.**
Verified, not assumed: `git grep -n 'from research\.\|import research\b' -- src/':!src/research'`
→ **0 hits**. So `src/research/**` and `scripts/research/**` may import the Setup without creating the
reverse edge, which is the direction recorded in the plan ("research may import execution. Execution
must not import research directly").

**Relation to `ProductionBundle` — different questions, do not merge.**

| | `ProductionBundle` | Setup |
|---|---|---|
| Answers | *which checkpoint actually reaches a decision* (Selected vs Enabled) | *how the CRT rail is parameterised* (stop anchor, target, TTL, decider) |
| Built from | registry `__active__` + `active_models.yaml` identity + config enable flags; read-only reconciliation, divergences reported never raised | the v5 config's declared overlay keys (§3) |
| Config reads | only the two `_CONFIG_ENABLE_KEY` paths (`production_bundle.py:62-68`) | the overlay keys, by definition |
| Authority | `meta.authority = "NONE"` (`:271`) | NONE (this spec adds none) |

Composition rule: neither is a field of the other, and a run needs both — the bundle says what
executes, the Setup says what the rail does with it. If a later step wants one object, **compose**
(e.g. a `Setup` carrying a loaded bundle) rather than copying the bundle's divergence logic
(`production_bundle.py:184-265`), which is the part that must stay single-copy.

**Empirical status.** Nothing reads a Setup today — the module does not exist. Whether either of the
two new behaviour keys (`target_policy`, `trade_ttl_candles`) ends up needing a `CRTConfig` field
rather than a constructor kwarg is **UNVERIFIED**; §3.3 shows it does not, if Option A or B is used as
written, and the K23 F2/F3/F4 precedent is kwarg-only (`backtest_v2.py:2997-3004`).

---

## 5. Decider = resolver ("mode C")

**What changes.** Today the engine founds the setup: `process_candle` runs the state machine, calls
`self.sm.try_retest_to_execution(...)`, then `trade = self.executor.build_trade(self.state, self.risk)`
and `self.executor.open_trade(...)` (`src/config_layer/crt_engine_v2.py:3596-3601`). With
`decider = "resolver"`, the **founding decision** comes from `CRTStateResolver`, and the engine keeps
geometry and exits.

**The four objects handed over, and where the resolver holds them today.**

| Object | Resolver carrier (verified) | Engine field that consumes it |
|---|---|---|
| active range | `CRTStateMemory.range_h_ref` / `range_l_ref` / `range_ready` / `range_htf_id` (`crt_state_resolver.py:170-176`) | `state.active_range` → `rng` (`crt_engine_v2.py:2430`); `h_ref` / `l_ref` are what `structural_tp2` needs (§3.4 key 2) |
| sweep event | `sweep_candle_index` (`:146`) — **index only**; the swept wick must be materialised from the bar stream | `state.sweep_event.candle.low` / `.high` (`:2452-2454`) |
| displacement candle | `displacement_candle_index` (`:147`), `displacement_candle_close` (`:148`), `displacement_direction` (`:149`) | `state.displacement_candle.low` / `.high` / `.open` (`:2457`, `:2464`, `:2532`) |
| retest candle | `retest_candle_index` (`:150`) — **index only** | `state.retest_candle.close` — **this is the entry price** (`:2434`) |

The resolver's memory is therefore *indexes plus one close*, not candles. The handover must be
materialised from the **same bar stream, by index** (the plan records the same: "Full candles come
from the bar stream by index"). Note `displacement_direction` is `+1 / -1` (`:149`) while the engine
uses the `Direction` enum (`state.direction`, `:2431`) — the mapping is part of the handover contract,
not an implicit conversion.

Fields the engine reads that the resolver does **not** own, and that therefore stay engine-side:
`state.atr_abs` (`:2433`), `state.direction` (`:2431`), `state.cached_features` (`:2493` — the
CRT-local 6-key dict, `_derive_trade_intent` `:2382-2419`), `state.risk_score` (`:2510`).

**Hard constraint: engine-oracle injection OFF.**

`CRTStateResolver.resolve()` accepts `engine_reset` and `engine_state_to`, both documented
"Research-shadow only", and applies them as its **last** stage so they override every other outcome
(`src/features/crt_state_resolver.py:517-527` signature + docstring; application `:703-716`). The
reason is recorded in the resolver's own site list: the four injection sites are `stage 4` —
"engine-oracle injection overrode everything (diagnostic modes only)" (`:248-251`). Running mode C
with injection ON would feed the engine's answer back into the resolver that is supposed to decide —
a loop.

Injection OFF means: call `resolve(features, timestamp, htf_id=...)` and leave both kwargs at their
defaults. A caller in the tree already does exactly this and labels it:
`scripts/research/link001_choch_measurement.py:105` — `engine_reset=False, engine_state_to=None,  # injection=none`.
Callers that **do** inject, and must not be reused as the mode-C resolver driver:
`scripts/research/crt_state_confusion_matrix.py:486`, `crt_state_window_trace.py:183`,
`crt_variant_surface.py:244` (all three build the injected map at their `build_engine_state_to_map`).

**What the engine keeps.** Geometry (`build_trade` `:2421-2542`: `risk_dist`, `sl_atr_buffer`,
`tp1`/`tp2`, `risk_pct`), exits (`update_trade` `:2549-2608`, `close_structural` `:2610-2634`), and the
reset rules (`ResetLogic` `:2643-2700+`). Mode C changes *who founds the setup*, not *what a trade is* —
so the L4 Geometry and L5 Outcome identities are untouched by the switch itself.

**Two preconditions mode C inherits (both already on the record).**

1. **One number, two tracks.** Before mode C is parity-shaped, the resolver's thresholds must read the
   production keys instead of its own literals. Today, e.g., it reads
   `int(life.get("pending_displacement_ttl_candles", 4))` (`crt_state_resolver.py:916-917`, applied
   `:1044`) — a silent-default read — while production is also `4` (`state_identity.py:249`). That is
   the P-1 reduction (WP-J), and it is a precondition, not a follow-up: mode C makes the resolver's
   thresholds *execution-relevant*, so two copies of one number become two behaviours.
2. **Bar/window join.** The resolver can run offline and be cached (`results/…/states.csv`,
   `src/charts/resolver_overlay.py:124`, `:169`) or run inside the walk. Which one mode C uses decides
   the join key (same bar vs window) and the cost of an N-Setup lab run — §10 Q4.

**Expected divergence, already on the record.** Mode C will *not* reproduce the engine's founding
decisions, and that is not a defect to tune away: F-069 (`docs/current-findings.md:879`) finds that
`CRTStateResolver` cannot reach engine parity through configuration alone, because EXPANSION entry is a
structurally different construction. A mode-C arm therefore produces a **comparison** (§7.3), never a
parity claim (§8).

**Not in scope here.** Modes A (veto at `TRADE_OPENED`) and B (a `risk_score` term) are recorded in the
plan as alternatives and are *not* specified by this document; only mode C is.

---

## 6. Trade TTL — the contract (consumer sites in §3.4 key 3)

**6.1 The requirement.** `trade_ttl_candles = N` (int, `N >= 1`) means: a trade opened on bar index
`i` is closed no later than bar `i + N`, at that bar's close, with `exit_reason = "TIMEOUT"` and
outcome `TIMEOUT`. `null` (the default) means there is no time-stop — today.

**6.2 Two candidate seams — one must be chosen (§10 Q3).**

| Seam | Change | Consequence |
|---|---|---|
| Engine-side (preferred by symmetry) | `ExecutionEngine.update_trade` (`crt_engine_v2.py:2549-2608`) gains the candle index, compares `open_candle_index + N` | One decision. Engine state, `events.jsonl`, and the ledger agree; the resolver track sees the same exit. Cost: it is a behaviour-bearing edit inside the hot file, so it must be inside the §8 parity envelope. |
| Ledger-side | `_resolve_exit` (`backtest_v2.py:1635-1684`) closes the trade on age | Engine states keep showing the trade as open while the ledger says `TIMEOUT` — the two-track divergence this repository already treats as a defect class (F-069 is the named instance of the resolver/engine split). Not recommended, but recorded because it is the smaller diff. |

**6.3 Index basis, and one implementation trap.**
- The engine's walk index is `EngineState.current_candle_index`, incremented **before** assignment each
  bar (`crt_engine_v2.py:250`, `:2992-2994`), so the first walked bar has index **1** — index 0 never
  occurs. That is why `Trade.open_candle_index: int = 0` (`:217`) is inert today *and* why 0 is
  available as an "unset" marker; if the implementation relies on that, it must say so explicitly
  rather than let a default that happens to be unreachable carry the meaning.
- The ledger's own basis is `TradeRecord.candle_open` / `candle_close` (`backtest_v2.py:457-458`) and
  `duration_candles = candle_close - candle_open` (`:4065`, property `:550`), so "N candles" in the
  overlay and `duration_candles` in the report are the same unit — but the report unit is inclusive of
  the exit bar, and the overlay is not. Define which one `N` counts (§10 Q3).
- `TIMEOUT` must also be reflected wherever exit reasons are enumerated; the hit counters are already
  exit-string based (`:1742-1743`), so they need no change, while `wins`/`losses` are R-signed
  (`:1740-1741`) and therefore need the §10 Q3 decision.

**6.4 Parity.** With `trade_ttl_candles = null`, no code path may change: the key must be provably
inert per §8, which for this key means the ledger and the engine event stream are byte-identical to
the same Setup without the key present.

---

## 7. The run unit (S4): one `ExperimentSpec` = N Setups × corpus

### 7.1 What the run unit is today (verified, unchanged)

`src/research/experiment_spec.py:116-166`:

- `ExperimentSpec` is a frozen dataclass with `experiment_id`, `kind` (closed set `KINDS`, `:46-55`),
  `corpus: tuple[CorpusSpec, ...]` (`:122`), `model_selection` (`:123`), `output` (`:124`), and two
  **pointers**: `measurement_config` (`:126`) and `production_config_ref` (`:127`, "production version
  (None = ACTIVE_VERSION)").
- `authority` is frozen at `"NONE"` — construction rejects anything else (`:129`, `:131-135`).
- `CorpusSpec` (`:63-77`) carries `path` (repo-relative), `instrument`, `sha256` (`None` = deliberately
  unpinned, recorded as such) and `rows` — the corpus pin is **data**, not a hardcoded constant
  (design rule `:17-18`).
- Identity is deterministic: `canonical()` + `sha256()` over canonical JSON (`:150-166`), so an
  experiment's provenance is a value (mirrors `ResearchConfig.sha256`).
- Design rules it states for itself (`:11-27`): **references, never redefines**; corpus pins live in
  the spec; **compared against the `ProductionBundle`, not the registry** (`:19-21` — this is the exact
  seam that ties §4 to §7); authority frozen at NONE.
- **Users today: zero executable consumers.** Verified with
  `git grep -n experiment_spec -- src scripts tests docs`: hits are the module itself,
  `tests/test_experiment_spec.py`, and generated/inventory docs (`docs/CODEBASE_SEMANTIC_NAMES.*`,
  `docs/architecture/code-map.generated.md`, `parameter_usage_audit.json`,
  `docs/book/encyclopedia/*`, `docs/governance/build_manifests/CH-oss-lab-scaffold.impact.json`).
  No `src/` or `scripts/` code imports it.

### 7.2 One spec = N Setups × corpus

Today the spec can already express **N corpora** (a tuple) but only **one** production config (a single
`production_config_ref`). The minimal extension that stays inside the module's own rules is:

- `production_config_ref` becomes a **tuple of Setup references** (a new field is equally acceptable;
  what matters is that the shape is a tuple, not a string). Each reference names a v5-family config
  file; the **overlay is the file's own content**, never a second inlined parameter set — inlining
  would create the "second config system" the module's docstring explicitly rejects (`:13-16`).
- A Setup is identified by **(config version string, config sha256)**. Both are recoverable today: the
  run stamps `config_version` on every trade row and the summary (`backtest_v2.py:1603`), and the full
  config is dumped per run (`:2985-2994`). No new identity system is needed.
- The cardinality is `N × |corpus|` **arms**, one process each, each with its own `OutputSpec`
  (`:100-113`) — no arm may share an output directory or carry state into another.
- `ExperimentSpec.sha256()` already hashes the whole canonical dict (`:150-166`), so the tuple is
  covered by the spec's identity with no change to the hashing rule.
- `kind` for the S4 grid is `"comparison"` (`:46-55`); the TTL on/off arm of the same Setup is
  `"ablation"`. This label is **descriptive only** — the module says reducers key off outputs, never
  off the label (`:44-45`) — so it changes nothing mechanically.

**Corpus pin for this program.** XAUUSD M15 only. Verified on disk:
`data/mt5/XAUUSD_M15.csv` — 2,715,565 bytes; 47,276 lines counted three agreeing ways
(`Measure-Object -Line`, `(Get-Content).Count`, `[IO.File]::ReadAllLines().Count`) = **47,275 data
rows + 1 header**; SHA256 = `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56`.
Standing rule for every arm: **time-range subset first, full corpus after**.

### 7.3 Required report fields — and the ranking gate

Each arm's report carries, taken from that run's **own** summary (never recomputed by the report — a
second implementation of an outcome is a different object, the class `measurement_basis.py:26-27`
names):

| Required | Existing field | Source |
|---|---|---|
| net % | `total_return_pct` (and `annualized_return_pct`) | `backtest_v2.py:1595-1596` |
| max drawdown | `max_drawdown_pct` (money basis) and `max_drawdown_rr` | `:1583`, `:1582`; computed `:1747-1748` |
| trade count | `approved_trades`, `total_setups`, `rejected_trades` / `approval_rate` | `:1574-1577` |
| win rate | `win_rate` | `:1578`; property `:1554-1557`; inputs `:1740-1741` |
| R per variant (same basis only) | `total_pnl_rr_net`, `avg_rr_net` | `:1581`, `:1579`; sum `:1745` |
| equity basis | `risk_pct_per_trade` / `sizing_mode` + `per_trade_investment_inr`; `capital_curve`; per-trade `capital_before`/`capital_after` | `configs/production/v2_htfcrt_k23_shadow_2026_09.json:489`, `:496-497`; `backtest_v2.py:1592`, `:467-468` |

**Fixed-`risk_pct` rule.** Every arm inside one comparison must declare the same risk basis, and that
basis must be stamped in the arm's output; otherwise "net %" is a different ruler per arm and the
comparison is exactly the defect §7.3's gate exists to prevent.

**The ranking gate — kept, not changed.**

`src/governance/measurement_basis.py:can_compare` (`:222-242`) walks `BASIS_AXES` (`:72`) and returns
the first disagreement using `COMPARE_TABLE` (`:208-219`): `walk_kernel` first, then
`reference_level` → **`DENY_REFERENCE_LEVEL_MISMATCH`**, rationale *"SEM-017: reference level moves
risk_distance, hence every R on the row"* (`:211-212`).

Our two stop anchors are two different `reference_level` values **by construction**:
`TradeJournal.__init__` stamps `reference_level = SL_ANCHOR_REFERENCE_LEVEL[sl_anchor]`
(`backtest_v2.py:1200`; map `:181-184`) → `displacement_extreme` | `sweep_extreme`. So any two arms
differing in stop anchor are denied by the gate *before* any number is looked at. **This is correct and
must stay**:

- The R denominator is the risk leg itself — `BACKTEST_RISK_DENOM_ID = "entry_fill_to_sl__v1"`
  (`backtest_v2.py:168`), computed as `abs(entry_price_fill − sl_price)/pip_size` (`:1359-1361`).
  Moving the stop therefore changes **the unit**, not only the outcome. Ranking raw R across anchors
  would rank denominators.
- The five axes are not advisory: `can_compare` is the single fail-closed gate shared by producers and
  readers, and `basis_from_row` (`:167-186`) turns any blank/unknown axis into `UNSTAMPED`, never a
  guess.

Consequences for the report:

1. **Cross-anchor ranking uses money/rate units**: net %, max DD, trade count, win rate — at a fixed
   risk basis.
2. **R is reported per variant under its own basis** and may be compared **within** one anchor.
3. Every reported R row must carry its five basis columns so a reader can re-run `can_compare`
   themselves. The verdict is never summarised away into one number.
4. The gate is **called**, never re-implemented: no second copy of `COMPARE_TABLE` or of the axis
   vocabularies (`AXIS_VOCAB` `:75-81`, `REFERENCE_LEVELS` `:57-64`).

### 7.4 How the arms actually execute (existing mechanism, no new tool)

Each arm runs in its own isolated ROOT: a real copy of `configs/` (with its own one-line
`ACTIVE_VERSION`) plus directory junctions to `data/`, `models/`, `src/`, `scripts/`
(`LINKED_TREES`, `scripts/analysis/v3_config_parity.py:66-68`), with the subprocess `cwd` set to that
root. The reason is the same one the v3 harness documents: `PROD_VERSION` is resolved **once at import**
from a **relative** pointer path (`production_config.py:57`, `:82`), so flipping the shared pointer in
place would be visible to every concurrent process in the repository
(`v3_config_parity.py:31-43`).

This is the pre-existing, proven way to run a config that is **not** `ACTIVE_VERSION` — it is why the
lab can run N Setups with **no promotion and no pointer change**, which is the S5 boundary. The S4
driver is a new script and therefore falls under the SITS floor
(`tests/test_script_registry.py`, enforced by `scripts/governance/construction_protocol.py:164-186`);
it is owned by WP-L, not by this spec.

---

## 8. Parity rule — the overlay at defaults is inert

**Statement.** With every overlay key at its §3.2 default, an arm must be indistinguishable from the
same Setup *without* the overlay. Five surfaces, compared by bytes:

1. **ledger** — `*_trades.csv` (every column) and `*_summary.json`
2. **engine states** — `*_events.jsonl` (plus `*_crt_telemetry.jsonl`)
3. **resolver states** — `states.csv` (`src/charts/resolver_overlay.py:124`, `:169`)
4. **oracle labels** — `labels.csv` + its sidecar `manifest.json`
   (`src/governance/measurement_basis.py:12-18`)
5. **layer_trace joins** — `*_layer_trace.jsonl`, one row per (bar, layer) carrying `trace_id`
   (`src/runtime/layer_trace.py:16-18`, `:73-74`)

**Two claims, mirroring the existing harness** (`scripts/analysis/v3_config_parity.py:9-29`):

**P-1 — cross-file inertness.** v5 vs v5 + overlay-at-defaults: identical on every field **except**
`run_id` and `config_version`. Both carve-outs are declared and justified, never convenient:

- `run_id` is ignored because every core output now carries one minted per run
  (`v3_config_parity.py:12-14`);
- `config_version` legitimately differs because the ledger stamps the config each run ran under — two
  different configs *sharing* a stamp would be a provenance defect (`:20-23`).

These are carve-outs, not tolerances. If any other field moves, the overlay is **not** inert and the
claim fails. The fifth surface is included deliberately: `layer_trace` is observation-only and
decision-neutral *by construction* (`layer_trace.py:27-29`), and its neutrality is proven by the same
ON-vs-OFF byte comparison (`:30-38`) — so it is a claim to check, not a property to assume. The same
applies to the resolver stream: with `decider` at default the resolver is still run and its
`states.csv` must be identical, because the resolver's inputs did not change.

**P-2 — liveness (the sibling of inertness).** Every **non-default** value must move at least one of
the five surfaces. The doctrine already exists in-tree: *"a link whose stream is bit-identical to its
base is dead code"* (`scripts/research/crt_variant_surface.py:24-26`). An arm that changes nothing is
reported as **INERT** — never as "no effect", which is a different statement.

**Scope limit — parity does not hold across `decider`, and must not be claimed there.** F-069
(`docs/current-findings.md:879`, *"CRTStateResolver cannot reach engine parity through configuration
alone — EXPANSION entry uses a structurally different construction, not a mistuned threshold"*)
establishes that the resolver track is not the engine track under any threshold choice. Therefore:

- P-1/P-2 apply to the overlay at defaults and to **every key except `decider`**;
- `decider = "resolver"` is *expected* to move trades. The correct output is a §7.3 comparison arm, not
  a parity failure;
- this is precisely why `decider`'s default is `"engine"` and why mode C is a separate arm rather than
  the new baseline.

**Harness ownership — a gap this spec does not assign.** The plan gives `scripts/research/parity_v5.py`
to WP-F (v5 vs active) and the S4 driver to WP-L; the script that proves the §8 P-1/P-2 claims for the
overlay is not owned by WP-C. It must be **named before WP-K's change lands**, because §8 is the
acceptance evidence for "defaults are inert" (§10 Q7).

**Shadow requirement.** Both arms must run the same code. No arm may execute a research
re-implementation of a layer (§1); here that is not just a design rule but a measurement requirement —
otherwise the comparison measures the re-implementation, not the Setup.

---

## 9. Acceptance checks

### 9.1 For this document's own change (doc-only)

```
PYTHONPATH=<wt>\src python -m pytest -q tests/test_doc_citations.py tests/test_topic_docs.py tests/test_current_findings.py
```

Expected: all pass. That is the `DOCUMENTATION_ONLY` floor
(`docs/governance/change_contracts.json:116-123`), and the class is only valid while **no** `src/`,
`configs/` or `models/` file changed — the validator enforces exactly that pairing
(`scripts/governance/construction_protocol.py:157-162`).

### 9.2 For WP-K (the overlay code)

| # | Check | Command / action | Passes when |
|---|---|---|---|
| 1 | loads at defaults | `PYTHONPATH=<wt>\src python -c "from config_layer.setup import Setup; print(Setup.from_prod_config('v5_htfcrt_sot_dual_k23_2026_09'))"` | prints `fixed_r` / `None` / `engine` (§3.2 key 2–4), no exception |
| 2 | fail-closed | set `target_policy` to a bogus value | raises **at load**, message names the key (§3.6 rule 1) |
| 3 | defaults inert | the §8 P-1 harness, two arms | every field identical except `run_id` and `config_version` |
| 4 | non-default live | one arm per non-default key | ≥ 1 of the 5 surfaces differs; otherwise report **INERT** (§8 P-2) |
| 5 | stamping | inspect `*_summary.json` of each arm | every non-default overlay key appears with its value (§3.7) |
| 6 | gate intact | the command in §9.3 | DENY across anchors, ALLOW within one |
| 7 | no pointer change | `git -C <wt> diff --stat` | `configs/production/ACTIVE_VERSION` never appears |
| 8 | dependency direction | `git grep -n 'from research\.' -- src/':!src/research'` | 0 hits (true today; must stay true) |

### 9.3 The §7.3 gate, checkable standalone — executed for this spec

```
PYTHONPATH=<wt>\src python -c "from governance.measurement_basis import Basis, can_compare,
TIE_BREAK_PRODUCTION; b=dict(walk_kernel='backtest_ledger', cost_model_id='backtest_g1g2_v2',
fill_model_id='engine_intrabar', tie_break=TIE_BREAK_PRODUCTION); a=Basis(reference_level='displacement_extreme', **b);
c=Basis(reference_level='sweep_extreme', **b); print(can_compare(a, c)); print(can_compare(a, a))"
```

Observed (verbatim output in §11): `DENY_REFERENCE_LEVEL_MISMATCH` across the two anchors, with the
SEM-017 rationale; `ALLOW_SAME_BASIS` for a basis against itself. **Limitation, stated plainly:** this
demonstrates the gate's behaviour on the two `reference_level` values the engine actually stamps
(`backtest_v2.py:181-184`) — it is not a comparison of two real arms' rows. It is a check that the gate
still separates the anchors, not evidence about any Setup's performance.

### 9.4 For WP-L (the lab)

- Two constructions of the same spec dict give the same `ExperimentSpec.sha256()` (§7.1).
- N Setups × M corpora produces exactly N × M arms, each with its own output directory (§7.2).
- Every arm's report carries the §7.3 fields **and** the five basis columns, so a reader can re-run
  `can_compare` without re-running the arm.

---

## 10. Open questions — **user decisions, deliberately not answered here**

**Q1. Where do the three new keys live?** Option A (one new `setup` section) or Option B (spread over
`backtest`, K23-style) — §3.3. Both are hash-neutral and `ConfigBuilder`-safe; the choice is about how a
Setup reads, and whether `backtest` should keep absorbing rail knobs.

**Q2. `structural_tp2` semantics.** (a) Does TP1 stay R-based while only TP2 becomes structural, or do
both move? (b) What happens when the opposite range side is **not** beyond entry (a LONG whose entry is
already at/above `h_ref`), or is closer than the risk leg — reject the trade, fall back to `fixed_r`, or
clamp? There is no inverted-TP guard today (§3.4 key 2). (c) Is the range the one frozen at build time
(`state.active_range`, `crt_engine_v2.py:2430`), bearing in mind the engine already protects an open
trade from a reset (`ResetLogic`, `:2661-2665`)?

**Q3. Trade TTL.** (a) the value of `N`; (b) which seam (§6.2); (c) the price at expiry — bar close
(`TIMEOUT_MARK_TO_CLOSE`) or trail (`TIMEOUT_TRAIL`), both of which already exist in the oracle
(`multi_tp_walk.py:63-65`); (d) whether `N` counts the entry bar and/or the exit bar (§6.3 off-by-one);
(e) whether a flat/zero `TIMEOUT` counts as a **loss** in `win_rate` — today `pnl_rr_net <= 0` is a loss
(`backtest_v2.py:1740-1741`), so a time-stopped trade that closed exactly flat is already a loss.

**Q4. Decider scope.** (a) Does the mode-C resolver run **inside** the walk or from a cached `states.csv`?
(b) Is `decider` a per-arm switch only, or may one arm emit both ledgers? (c) If offline, what is the
join key (same bar vs window)?

**Q5. What is the "fixed `risk_pct`"?** `backtest.risk_pct_per_trade` is a fraction
(`configs/production/v2_htfcrt_k23_shadow_2026_09.json:489`, `0.01`) while `sizing_mode =
"fixed_investment_inr"` + `per_trade_investment_inr` (`:496-497`) is a money basis. Both exist; the
comparison unit must name one (§7.3).

**Q6. The overlay's identity name.** Not `setup_id` (§3.3). What is it, and is it registered anywhere at
S5, or is "(config version, config sha256)" the whole identity?

**Q7. Who owns the §8 parity harness** for the overlay, and when is it named? It is not WP-C's file and
the plan does not currently assign it (§8).

**Q8. What is in the first grid?** The S4 brief is "stop anchor × target, TTL on" — is `decider` in that
first grid? Are `retrace_reset_pct` and `session_window_basis` in it? Full cross-product, or one key at
a time?

**Q9. Does a Setup re-state the K23 keys or inherit them?** i.e. is F1/F2/F4 part of the Setup's own
declaration (the §3.2 reading), or is v5's K23 value simply the baseline that a Setup may override?

### Decisions (user, 2026-09-28)

| Q | Decision |
|---|---|
| Q1 | **Option A** — one new top-level `setup` section holds keys 2–4. `backtest` stays K23-only; a Setup is a distinct concept. |
| Q2a | Only TP2 moves; TP1 stays R-based (`tp1_atr_multiplier_<intent>`). |
| Q2b | An inverted/degenerate structural TP2 **rejects the trade** (same treatment as any other pre-trade geometry rejection). No silent fallback to `fixed_r`. |
| Q2c | The range frozen at build time (`state.active_range`), consistent with `ResetLogic`'s existing protection of an open trade from a reset. |
| Q3a | `N` value: not fixed here — start the config at a placeholder (`null`/inert) until a real value is chosen via the S4 grid or a direct decision. |
| Q3b | Engine-side seam (`ExecutionEngine.update_trade`, §6.2 table row 1) — one decision, engine/ledger/resolver stay in agreement. |
| Q3c | `TIMEOUT_MARK_TO_CLOSE` — matches "default = today's behaviour" (today there is no trail-to-expiry to default to); `TIMEOUT_TRAIL` stays available as an explicit non-default choice. |
| Q3d | `N` counts the entry bar, not the exit bar — TTL of `N` forces closure going into bar `entry_idx + N` if still open (matches `pending_displacement_ttl_candles`'s counting convention, F-068). |
| Q3e | A flat/zero TIMEOUT counts as a loss — no exemption from the existing `pnl_rr_net <= 0` rule. |
| Q4a | Cached `states.csv` (offline resolver run), not an in-walk resolver call. |
| Q4b | Per-arm switch only — one arm, one decider. |
| Q4c | Join key = same bar (timestamp). |
| Q5 | `backtest.risk_pct_per_trade` (the fraction) is the comparison unit — not `sizing_mode="fixed_investment_inr"`. |
| Q6 | No separate `setup_id`. Identity = `(config version, config sha256)`. Not registered anywhere until S5. |
| Q7 | WP-K owns the §8 parity harness — whoever builds the overlay proves it inert. |
| Q8 | First grid = `sl_anchor × target_policy`, TTL on, everything else at default. `decider`, `retrace_reset_pct`, `session_window_basis` are separate axes, not in the first grid. |
| Q9 | Inherit. A Setup only declares what it overrides from v5's K23 baseline; K23 keys are not re-stated. |

**Scope decision (user, 2026-09-28):** STORY-83.11 (WP-K) implements all three new behaviours —
`target_policy`, `trade_ttl_candles`, `decider = "resolver"` (mode C) — in one story, one worktree,
one PR, per the master plan's WP-K row. Assignee: Claude, direct in-session (not relayed).

---

## 11. Verified / UNVERIFIED ledger

### 11.1 Commands run for this spec, with their outputs

| # | Command (run from the worktree) | Output |
|---|---|---|
| 1 | `git rev-parse --abbrev-ref HEAD` | `lane/wpC-setup-spec` |
| 2 | `git log --oneline -1` | `d318f13b (HEAD -> lane/wpC-setup-spec, …) chore: snapshot working tree before multi-LLM build (S0-S5)` |
| 3 | `Get-Content configs/production/ACTIVE_VERSION` | `v2_htfcrt_2026_08` |
| 4 | `PYTHONPATH=<wt>\src python -c "import runtime.backtest_v2 as m; print(m.__file__)"` | `D:\Tradelatest-wt-wpC-setup-spec\src\runtime\backtest_v2.py` |
| 5 | sha256 + line count of `data/mt5/XAUUSD_M15.csv` | bytes `2715565`; lines `47276` by three agreeing methods (`Measure-Object -Line`, `(Get-Content).Count`, `[IO.File]::ReadAllLines().Count`) → **47,275 data rows + 1 header**; SHA256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| 6 | `Get-ChildItem configs\production -Filter '*v5*'` | empty — v5 not built at BASE |
| 7 | `git grep -n open_candle_index -- src` | one hit: `src/config_layer/crt_engine_v2.py:217` |
| 8 | `git grep -n 'from research\.\|import research\b' -- src/':!src/research'` | **0** hits |
| 9 | `git grep -n experiment_spec -- src scripts tests docs` | the module itself, `tests/test_experiment_spec.py`, and generated/inventory docs — **no** `src/` or `scripts/` consumer |
| 10 | `Select-String` for `"target_policy"\|"decider"\|"setup"\|"trade_ttl_candles"\|"structural_tp2"\|"sl_anchor"` over `configs/production/v2_htfcrt_k23_shadow_2026_09.json` | only `516: "sl_anchor": "sweep_extreme"` |
| 11 | `git grep -n retrace_reset_pct -- src configs` | active `v2_htfcrt_2026_08.json:244 = 0.5`; shadow `v2_htfcrt_k23_shadow_2026_09.json:245 = 0.618`; consumer `src/config_layer/crt_engine_v2.py:2689` |
| 12 | `git grep -n F-069 -- docs/current-findings.md` | `:879` — "CRTStateResolver cannot reach engine parity through configuration alone …" |
| 13 | `git ls-files -- src/config_layer` | 35 files; none matches `setup` |
| 14 | the `can_compare` check of §9.3 | `('DENY_REFERENCE_LEVEL_MISMATCH', "reference_level differs: 'displacement_extreme' vs 'sweep_extreme' (SEM-017: reference level moves risk_distance, hence every R on the row)")`, then `('ALLOW_SAME_BASIS', 'all five axes agree')` |

Every `file:line` in this document was read from **this** worktree at `d318f13` in the session that wrote
it; no citation was carried over from another tree, and no id was invented.

### 11.2 UNVERIFIED

1. **The v5 config itself.** It does not exist at BASE (row 6), so its sections, its hash, and whether
   the chosen overlay option lands cleanly in it are **UNVERIFIED** until S1/WP-E builds it. §3.3's
   "hash-neutral" claim is verified for the **mechanism** (`config_hash` covers `params` only,
   `production_config.py:89-92`), not for the not-yet-written file.
2. **Whether a `CRTConfig` field is needed** for `target_policy` / `trade_ttl_candles` instead of a
   constructor kwarg — **UNVERIFIED** (§4). §3.3 shows it is not needed if Option A or B is used as
   written; the K23 precedent is kwarg-only.
3. **The §6.2 engine/ledger desynchronisation claim** is a prediction read from the call sites (the
   engine owns the trade status; `_resolve_exit` only prices the close), not a measurement —
   **UNVERIFIED empirically**.
4. **No real-arm parity has been run** (§8 P-1/P-2) for any Setup, because no v5 and no overlay code
   exist. The rule is specified here; its evidence is owed by WP-K/WP-L.
5. Numbers reported by the read-only Grok audits (`docs/audits/RESEARCH_*_CENSUS_2026-09-27.md`) are
   **not** relied on anywhere in this document — no unverified runtime figure is reused.

### 11.3 What this document does not do

- It writes no code and changes no behaviour.
- It introduces no layer, no id, no formula and no registry.
- It does not modify `measurement_basis.py`; it keeps `DENY_REFERENCE_LEVEL_MISMATCH` as a feature (§7.3).
- It proposes no config file other than the v5 shadow, and it never touches
  `configs/production/ACTIVE_VERSION`.
- It resolves none of the §10 questions — those are the user's.
