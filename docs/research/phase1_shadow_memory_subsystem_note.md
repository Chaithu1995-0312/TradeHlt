# Phase-1 SHADOW memory subsystem note

**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · no Case reopen · no object widening · no freeze work · no OB/PDH/liquidity expansion

**Corpus:** Phase-1 XAUUSD · csv sha256 `4d73f5cebe33ec91...` · config `v2_htfcrt_2026_08`
**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_subsystem.json`

## Locked object

Unresolved HTF displacement memory preserved through RANGE, reactivated by matching sweep (sweep.dir == pending_dir) before TTL expiry → shadow-resume EXPANSION (strength skipped).

## Q1 - pending_ttl = 4

CRTConfig / market_crt_states lifecycle / v2_htfcrt_2026_08 pin pending_displacement_ttl_candles=4: candles a pending_displacement memory survives after an HTF reset (independent of backtest.htf_candles_per_range). Set to 0 to disable. Not derived in-engine; config default.

Primary cites:
- `src/config_layer/state_identity.py:250`
- `configs/formulas/market_crt_states.yaml:351`
- `configs/production/v2_htfcrt_2026_08.json` -> `crt_engine.pending_displacement_ttl_candles=4`
- assignment `src/config_layer/crt_engine_v2.py:1901` on HTF-DISPLACEMENT reset create gate (`crt_engine_v2.py:1892-1915`)

## Funnel table

| Stage | N |
|---|---:|
| Created | 69 |
| Expire TTL before confirming sweep | 45 |
| Cleared non-HTF reset | 17 |
| SHADOW_PENDING | 6 |
| Restore -> EXPANSION | 6 |

- P(SHADOW_PENDING | created) = **0.086957**
- P(restore | SHADOW_PENDING) = **1.0**
- P(expire | created) = **0.652174**

## Known-6 TTL-at-restore

TTL remaining values: `[3, 1, 1, 3, 3, 1]` · near TTL=1: **3/6** · near TTL=4: **0/6** · distribution `{'3': 3, '1': 3}`

See `memory_subsystem.md` for per-row formed_idx -> collapse_idx distances.

## Failed resumes near expiry

try_shadow false=0; SHADOW_LEAK=0.

## Blockers

- Object scarcity unchanged: restores n=6 << 30 (power floor from prior notes).
- Non-HTF clears and TTL expires both terminate memory without SHADOW_PENDING; they are separate exit channels in the funnel.
- One memory overwritten by a newer HTF-DISPLACEMENT create before resolution (n=1).
- Measure-only monkeypatch; production semantics unchanged.
