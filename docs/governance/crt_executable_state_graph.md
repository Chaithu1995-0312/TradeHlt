# CRT Executable State Graph — Phase 3

**Program:** CRT Closure (audit-first)  
**Phase:** 3 of 8  
**Status:** **PASS**  
**Twin:** [`crt_executable_state_graph.json`](crt_executable_state_graph.json)  
**Source:** `src/config_layer/crt_engine_v2.py` (`VALID_TRANSITIONS` L1075, `StateMachine` L1088, `process_candle` L2257)

---

## Verdict

| Field | Value |
|---|---|
| **CRT_STATE_GRAPH_STATUS** | **COMPLETE_AND_PARITY_CHECKED** |
| Governed states | **9** (matches `CRTState`) |
| Hidden states | **none** |
| Ungoverned `_transition` targets | **none** |
| Force-reset side-channel | **documented** (`reset_to_range` bypasses `VALID_TRANSITIONS`) |
| Intended double-transition | **documented** (shadow path) |

---

## Legal transition map (`VALID_TRANSITIONS`)

```text
RANGE ──────────► SWEEP
  │                 │
  │                 ├──► DISPLACEMENT ──► EXPANSION ──► RETEST ──► EXECUTION ──► RESOLUTION ──► RANGE*
  │                 │                      │              │
  │                 │                      ├──► EXPIRED ──► RANGE* (soft archive)
  │                 │                      └──► RANGE*
  │                 └──► EXPANSION (shadow hop only)
  │                 └──► RANGE*
  └──► SHADOW_PENDING ──► SWEEP ──► EXPANSION (same call, two hops)
                      └──► RANGE*
```

`RANGE*` = often via **`reset_to_range` force assign**, not `_transition`.

---

## Golden path (production)

```text
RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION → RESOLUTION → RANGE
```

Plus branches:

| Branch | Path |
|---|---|
| Shadow | `RANGE → SHADOW_PENDING → SWEEP → EXPANSION → …` (skips strength re-check) |
| TTL | `EXPANSION → EXPIRED → RANGE` |
| Filters / timeout | `RETEST → RANGE` (zone, session, soft-conf fail, advisory) |
| Sweep age | `SWEEP → RANGE` |
| Resets | any → RANGE via `ResetLogic` / gap / filters |

---

## Critical runtime facts (code, not docs)

### 1. Force-reset is a first-class mechanism

`StateMachine.reset_to_range` (L1439) **does not** call `_transition`. It assigns `current_state = RANGE` and clears caches. Therefore:

- Many edges to RANGE are **cleanup**, not legal-map hops.
- `VALID_TRANSITIONS[*]→RANGE` lists remain true for legality, but runtime cleanup is broader.

### 2. Soft-conf is flag-driven, not `elif s == RETEST`

After retest, state becomes `RETEST` and `evaluating_soft_conf=True`. Further soft-conf work is under:

```text
elif self.state.evaluating_soft_conf:   # L2592
```

There is **no** dedicated `elif s == RETEST` branch.

### 3. EXECUTION is trade-driven

Open trade handling (L2303) runs **before** state-branch elifs. Close → `EXECUTION→RESOLUTION` then immediate `reset_to_range`.

### 4. Same-candle order rules (governed)

| ID | Rule |
|---|---|
| ORD-RESET-FALLTHROUGH | After reset, RANGE branch may still fire same candle |
| ORD-RETEST-BEFORE-TTL | EXPANSION tries retest before TTL expire |
| ORD-SHADOW-DOUBLE-TRANSITION | SHADOW_PENDING→SWEEP→EXPANSION in one method |
| ORD-ACTIVE-TRADE-BEFORE-SM | Trade exit before SM branch |

### 5. Prod-inactive but code-present

`SHADOW_ADVISORY_BLOCK` requires `shadow_advisory_only=true` — **false** on `v2_multi_2026_04` → code-reachable, prod-inactive.

---

## Per-state process_candle dispatch

| State | Dispatch |
|---|---|
| RANGE | L2334 elif |
| SHADOW_PENDING | L2398 elif |
| SWEEP | L2456 elif |
| DISPLACEMENT | L2493 elif |
| EXPANSION | L2498 elif |
| EXPIRED | L2587 elif |
| RETEST | via `evaluating_soft_conf` L2592 |
| EXECUTION | via `active_trade` L2303 |
| RESOLUTION | transient; cleared by reset L2326 |

---

## Machine checks (enforced by test)

1. Graph state set == `CRTState` names (exactly 9).  
2. Graph `VALID_TRANSITIONS` == code `VALID_TRANSITIONS`.  
3. Every `_transition` method target is legal in `VALID_TRANSITIONS` for its `from` state.  
4. Shadow double-hop targets (`SWEEP`, `EXPANSION`) are legal.  
5. Force-reset semantics file asserts `bypasses_valid_transitions: true`.  
6. Historical: no `CANCELLED` / `RESOLVED` states.

Test: `tests/test_crt_executable_state_graph.py`

---

## Findings

No new finding. Graph confirms known architecture; force-reset and soft-conf flag dispatch are **documented truths**, not defects, unless later phases show unintended candidates.

---

## Phase 3 return

```text
CRT_STATE_GRAPH_STATUS = COMPLETE_AND_PARITY_CHECKED
PHASE3_STATUS = PASS
ARTIFACTS = docs/governance/crt_executable_state_graph.{json,md}
TEST = tests/test_crt_executable_state_graph.py
NEXT = await Phase 4 authorization (diversion census)
```
