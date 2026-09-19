# body_ratio_min — bind path (P2 deep dive)

**Policy (User 2026-09-19):** **No fallbacks or defaults.** Declared config is the only authority. Missing key = fail-closed (refuse), not `.get(..., 0.70)`.

## Authorities found (measurement)

| Layer | Value | Role |
|---|---|---|
| `configs/production/v2_htfcrt_2026_08.json` | **0.65** | Production CRTConfig HOW (engine path) |
| `configs/formulas/market_crt_states.yaml` `thresholds.body_ratio_min` | **0.65** | WHO declare |
| YAML prose (line ~184) | 0.70 | Doc drift (not a bind) |
| `CRTConfig` dataclass default (`state_identity.py`) | **0.70** | **Forbidden default** |
| `crt_state_resolver.py` `thr.get("body_ratio_min", 0.70)` | **0.70** | **Forbidden fallback** |
| `visual_crt/driver.py` `BODY_RATIO_MIN` | 0.65 | Research constant (parallel lane) |

## Runtime bind (trading engine)

- Guard `G_SWEEP_DISP_BODY` in `crt_engine_v2.py` uses **`self.config.body_ratio_min`** (`config_source: CRTConfig`).
- Production JSON sets **0.65** → when prod config loads, engine runs **0.65**.
- Resolver continuous path uses **`thr.get(..., 0.70)`** → if `thresholds` map omits the key, silently runs **0.70** (policy violation under no-fallback rule).

## Drift class

- **Duplicated** + **Mis-labeled** prose (0.70 in YAML comment vs 0.65 declare).
- Dataclass default / `.get` fallback = **policy violations** (not alternate tunables).
- Not Shadowed: when CRTConfig is loaded, 0.65 binds and is used.

## Fix stance (P-S5 + User rule)

- **Do not tune** 0.65 vs 0.70 — authority is **0.65**.
- Remediation (later, gated): remove dataclass default; replace `.get(..., 0.70)` with required key / fail-closed; align prose to 0.65.
- **No code change in this pass** unless User orders the fail-closed patch.

## Success for this param

Declared 0.65 is the only legal value; any path that invents 0.70 without an explicit loaded key is a defect.