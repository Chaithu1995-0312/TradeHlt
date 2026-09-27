# GROK_BOT_STORY62_WEBHOOK_SPEC.md — draft contract for STORY-6.2

> **Status:** SPEC DRAFT (Grok Bot). **Not implemented by this lane.**  
> **Implementer:** Claude (Executor), when User schedules STORY-6.2.  
> **Authority for intent:** `docs/implementation_plan/FULL_BUILD_SPECIFICATION.md` § Epic 6 / Story 6.2.  
> **Date:** 2026-09-18

---

## 0. Ambiguity note (Class A — resolved for this draft)

| Source | Says |
|---|---|
| `build_queue.jsonl` STORY-6.2 | Thin ownership census; lists `results/tuner/BNBUSDT/checkpoint.json`, `src/control_plane/registry.py`, `src/control_plane/server.py` |
| `FULL_BUILD_SPECIFICATION.md` Story 6.2 | Real contract: add `POST /api/run-stage` + `POST /api/claude-gate` |

**Disposition:** Prefer the **build spec** for the HTTP contract. Treat the BNBUSDT checkpoint path as a *sample artifact consumer*, not the feature definition. If User wants queue text rewritten, that is a separate hygiene story (append-only comment / new story — do not silently rewrite history).

**Path drift:** Spec examples also mention Docker port **8787** and `scripts/control_plane/run_server.py`. Live entrypoint today: `scripts/control_plane/run_server.py` → `src.control_plane.server.run_server` default **127.0.0.1:8787**. Draft targets the **live** module paths.

---

## 1. Goal

n8n (localhost) can trigger control-plane stages and Claude-gate decisions over HTTP without replacing the existing dashboard UI.

Prerequisite context: Epic 6.1 (n8n compose) may be incomplete — receiver should still be testable with `curl` against a running control plane.

---

## 2. Endpoints (from build spec)

### 2.1 `POST /api/run-stage`

**Auth / bind:** localhost-only (same as current control plane). No token in v1. If ever exposed beyond loopback → **Class B** (User must decide auth) — fail closed until then.

**Request JSON:**

```json
{
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "workdir": "/tmp/tradelatest/BNBUSDT/run_001",
  "config": { "n_iter": 100, "seed": 42, "workers": 4 }
}
```

**Success JSON:**

```json
{
  "status": "success",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "metrics": {
    "expectancy": -0.02,
    "trades": 47,
    "win_rate": 0.41,
    "max_drawdown": -0.15
  },
  "config_hash": "sha256:…",
  "artifacts": ["results/tuner/BNBUSDT/checkpoint.json"],
  "duration_seconds": 342,
  "error": null
}
```

**Error JSON:**

```json
{
  "status": "error",
  "stage": "tuning",
  "instrument": "BNBUSDT",
  "error": "No data found for BNBUSDT",
  "error_type": "DataNotFoundError",
  "duration_seconds": 2,
  "artifacts": []
}
```

### 2.2 `POST /api/claude-gate`

**Request JSON:** stage + instrument + config + backtest_results + findings[]  
**Response JSON:** `action` ∈ `tweak|promote|escalate|skip`, confidence, optional tweak object, findings_referenced, next_action  

(See FULL_BUILD_SPECIFICATION Story 6.2 for full examples.)

**Note:** STORY-7.1 (Claude Gate Webhook Handler) overlaps — 6.2 may stub the route and 7.1 deepen Claude integration. **Class B if both claim the same handler:** User/Claude pick one owner story before coding.

---

## 3. Files Claude will likely touch

| Path | Role |
|---|---|
| `src/control_plane/server.py` | Route dispatch (large existing stdlib HTTP server) |
| `src/control_plane/registry.py` | Stage → CommandSpec mapping |
| `scripts/control_plane/run_server.py` | Process entry (host/port) |
| tests (new) | Contract tests for both POSTs (success + error shapes) |

---

## 4. Non-goals (this draft)

- Implementing routes (Claude)
- Docker compose (STORY-6.1)
- Parallel workdirs (STORY-6.3)
- Exporting n8n workflow JSON (STORY-6.4)
- Exposing ports beyond localhost

---

## 5. Suggested acceptance checks (for Claude later)

1. `curl -s localhost:8787/api/run-stage` with sample body returns JSON with required keys.  
2. Unknown `stage` → `status=error` + stable `error_type` (no stack trace leak).  
3. Binding remains 127.0.0.1 by default.  
4. Unit tests pin request/response schema.  
5. No promotion / live side effects from `run-stage` without existing governance gates.

---

## 6. Open questions for User (Class B — do not guess)

1. Should `POST /api/claude-gate` land in **6.2** or wait for **7.1**?  
2. Sync vs async `run-stage` (spec shows sync with `duration_seconds` — confirm OK for long tuners)?  
3. Is `workdir` mandatory in v1 or optional default under `results/`?

Until answered, Claude should implement **only** what User schedules; this draft is advisory.
