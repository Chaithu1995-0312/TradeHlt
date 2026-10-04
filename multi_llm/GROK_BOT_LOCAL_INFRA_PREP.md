# GROK_BOT_LOCAL_INFRA_PREP.md — local plane only

> **From boards:** `design_cards/boards/infra-design-01..04`  
> **Date:** 2026-09-18  
> **Hard:** no AWS deploy · no terraform apply · no Hot / live orders · no fake edge claims

## 1. What “prepare” means now

Stand up **decision-plane scaffolding** on the laptop so DryRun + Shadow can run later — **not** production trading.

| Allowed now | Blocked |
|---|---|
| Boot / verify Tradelatest control plane `:8787` | AWS `lambda_control_plane` deploy |
| DryRun / Shadow mode policy | Hot / live broker / ECS launch |
| Read LCP as doctrine (schemas, spine) | Duplicate LCP as second Lambda stack in TL |
| Freeze design cards DC-003/004 | Claim measurable edge from infra alone |

## 2. Architecture (board 1)

```
[Design memory]  chatgptviewer + ProjectDiscussion + design_cards
       ↓
[Supervisor]     Grok Bot (boards, claims, track)
       ↓
[Local plane]    Tradelatest src/control_plane → 127.0.0.1:8787
       ✗
[AWS / Hot]      DEFERRED
```

## 3. Spine (board 2 = DC-003/004)

Ingest → Features → Ultron (math) → Sherlock/Saul (advisory) → Jarvis (permission) → ALLOW/DENY  
**Decision ≠ execution.** Fail-closed: any failure → NO EXECUTION.  
Execution (when present) = separate process; modes DryRun / Shadow only.

## 4. Modes (board 3)

1. **DryRun** — simulate, no broker  
2. **Shadow** — observe/compare, no live orders  
3. **Hot** — NOT YET

Checklist strip: boot `:8787` · freeze DC-003/004 · LCP read-only · no terraform apply

## 5. Prep steps (docs / ops — no live)

| # | Step | Owner | Status |
|---|---|---|---|
| P0 | Boards saved + tracked | Grok Bot | **done** |
| P1 | User `final DC-003 DC-004` | User | **done** 2026-09-18 |
| P2 | Boot-check `:8787` (health only) | Grok Bot + User PC | **done 2026-09-18** (HTTP 200; see boards/bootcheck-8787-RESULT.md) |
| P3 | Mode lock note in configs / runbook (Hot denied) | Grok Bot draft | **done** — [MODE_LOCK.md](MODE_LOCK.md) + board 04 |
| P4 | Thin DryRun plug script after freezes | Grok Bot | **done** — `scripts_design/dry_run_plug.py` |
| P5 | AWS revisit | User gate only | deferred |

## 6. Boot-check sketch (P2)

```text
cd D:\Tradelatest
# activate project venv if present
python -m src.control_plane.server   # or project’s documented entry
# expect listen 127.0.0.1:8787 — dashboard/API only, not broker
```

**Confirmed:** with `PYTHONPATH=D:\Tradelatest;D:\Tradelatest\src`,

```text
python -c "from src.control_plane.server import run_server; run_server('127.0.0.1', 8787)"
```

returns HTTP 200 on `/`. Prefer this over `python -m src.control_plane.server` (runpy warning / flaky). Stopped after check — not left running.

## 7. Out of scope

Live orders, AWS credentials exercise, terraform apply, PrivateLLM bulk boot, income Reel until handle/UPI.

## 8. Next

1. User freezes DC-003/004 (or edits boards).  
2. P4: thin DryRun plug **after** freezes (or Claude ticket for mode enum if you want code gate first).  
3. AWS remains User-gated.
