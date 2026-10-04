# Phase-1 SHADOW memory create / expire note

**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · no Case reopen · no object widening · no freeze work · no TTL flip

**Corpus:** Phase-1 XAUUSD · csv sha256 `4d73f5cebe33ec91…` · config `v2_htfcrt_2026_08`
**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_create_expire.json`
**Mined from:** prior `memory_subsystem.json` + `structure_context.json` (no full BT re-run)

## Locked object

Unresolved HTF displacement memory preserved through RANGE, reactivated by matching sweep (sweep.dir == pending_dir) before TTL expiry → shadow-resume EXPANSION (strength skipped).

## Q1 — Create reasons (69)

Sole path: `crt_engine_v2.py:1892-1915` — **both** DISPLACEMENT (with displacement_candle) **and** `"HTF" in reason`.

| Reason class | Sample N | All-69 inferred |
|---|---:|---:|
| HTF_CHANGED_WHILE_DISPLACEMENT | 50 | 69 |
| Other | 0 | 0 |

Prior probe capped `create_sample` at 50; funnel still reports 69 creates. Reason class does not bifurcate — there is no DISPLACEMENT-only create channel.

## Q2 — Expire concentration (45)

- **Direction:** SHORT 30 / LONG 15
- **Session (broker-local hour buckets):** NY_17_22=16, ASIA_0_8=11, LONDON_8_13=10, OVERLAP_13_17=5, OFFHOURS_22_24=3
- **Parent CRT:** not on expire rows; **source_htf:** 45 unique
- **Bars-to-expire:** 45/45 at bars_since_created=4 (ttl_was=1, pre_state=RANGE)
- **Formed near TTL:** age_at_reset modal=1 (20/45)

## Q3 — Restores vs expires

- Restores LONG-heavy (4/6) vs expires SHORT-heavy (30/45)
- Restores age_at_reset modal=3 (4/6) vs expires modal=1 (20/45)
- Restores resolve at bars_since_created ∈ {2,4}; expires always 4
- Parent CRT (restores only): track/htf_state from structure_context — see JSON for per-row

## Non-claims

- No economic performance claim.
- No recommendation to change TTL.
- Session buckets are descriptive broker-local hour bins, not corrected UTC session labels.
