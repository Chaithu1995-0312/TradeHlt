# STORY — Parameter Usage Audit (declare / actual / fallback)

| Field | Value |
|---|---|
| **ID** | STORY-PARAM-AUDIT-01 |
| **Status** | in_progress (P1 started) |
| **Type** | Measurement only — **no remediation** |
| **Opened** | 2026-09-19 |
| **Owner** | Grok Bot (Trader Bot lane) |
| **Parallel** | HTF semantic cross-tab (P-S1) |

## Decisions locked (P-S1–P-S5)
## Policy lock (2026-09-19 User)

**No fallbacks or defaults.** Parameters bind only from declared/loaded config. Missing key = fail-closed refuse. .get(name, fallback), dataclass field defaults, and hardcoded constants that shadow declare are **defects**, not tuning knobs.

First deep-dive: `body_ratio_min` — authority **0.65** (prod JSON + YAML thresholds). Illegal 0.70 sites: `state_identity.CRTConfig` default, `crt_state_resolver` `thr.get(..., 0.70)`, YAML prose example. Detail: `multi_llm/parameter_usage_audit/body_ratio_min_bind.md`.


| Ask | Decision |
|---|---|
| P-S1 | Run **in parallel** with HTF closure |
| P-S2 | Include **P1 + P2** (read sites + fallback mismatch) |
| P-S3 | Include **P3 only for Tier-1/2** candidates |
| P-S4 | Open Jira/story **now** |
| P-S5 | **No governed fixes** until P3 quantifies impact |

## Drift classes

Clean · Dead · Decorative · Duplicated · Masked · Overloaded · Mis-labeled · **Shadowed** (binds; upstream limiter always preempts)

## Scope

1. **P1** — every declared threshold/param → `file:line` read sites  
2. **P2** — YAML declared value vs `.get(name, fallback)` mismatches  
3. **P3** — replay alternate values for Tier-1/2 only; measure output delta  

**Out of scope:** changing any parameter, threshold, or behavior.

## Deliverables

- `docs/architecture/parameter_usage_audit.md`
- `docs/architecture/parameter_usage_audit.json`
- Working copies: `multi_llm/parameter_usage_audit/`

## Success criterion

For every key under YAML `thresholds:` / CRT threshold inventory: **read by which file:line, or dead** (and fallback mismatch if any).

## P1 progress (2026-09-19)

- Scanned **1113** Python files; inventoried **51** params (seed + YAML harvest).
- Status counts: read 25 · duplicated_fallback_mismatch 18 · dead_candidate 5 · unreferenced_hint 3
- High-signal mismatches (Tier-1 candidates for P3):  
  - `body_ratio_min` declared **0.65** vs fallback **0.70**  
  - `atr_multiplier_min` declared **1.0** vs fallback **1.5**  
  - `expansion_atr_min_distance` declared **0.30** vs fallback **0.20**  
  - `retest_depth_max` declared **0.15** vs fallback **0.25**  
- Dead candidates of interest: `max_displacement_age_candles`, `retest_atr_depth_fraction`


## Policy lock (2026-09-19 User)

**No fallbacks or defaults.** Parameters bind only from declared/loaded config. Missing key = fail-closed refuse. .get(name, fallback), dataclass field defaults, and hardcoded constants that shadow declare are **defects**, not tuning knobs.

First deep-dive: `body_ratio_min` — authority **0.65** (prod JSON + YAML thresholds). Illegal 0.70 sites: `state_identity.CRTConfig` default, `crt_state_resolver` `thr.get(..., 0.70)`, YAML prose example. Detail: `multi_llm/parameter_usage_audit/body_ratio_min_bind.md`.

## Next

- Clean noise keys from YAML meta (`kind`/`note`/`ref`/`schema`) in inventory  
- Confirm bind vs Shadowed for clock vs age params (needs P3 or path proof)  
- Do **not** change thresholds