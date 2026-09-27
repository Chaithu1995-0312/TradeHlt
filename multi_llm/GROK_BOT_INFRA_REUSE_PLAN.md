# GROK_BOT_INFRA_REUSE_PLAN.md — reuse before invent

> Trader Bot primary. Edge = goal. Infra = fail-closed scaffolding.  
> **Policy:** do not greenfield microservices while these already exist.  
> **Date:** 2026-09-18

---

## 1. What you already have (reuse catalog)

### A. AWS trading control plane (richest)
**Path:** `D:\Chaithu\lambda_control_plane`

| Piece | Role | Reuse? |
|---|---|---|
| Lambda orchestrator (`lambda_function.py` / handlers) | Pipeline: ingest → features → ULTRON risk → JARVIS gate → ECS launch | **Primary** trading infra |
| DynamoDB risk/state stores | Fail-closed state | Yes |
| EventBridge schedulers (tf/yaml) | Reset / regime timers | Yes |
| SNS trade-exit events (tf/yaml) | Event bus slice | Yes |
| Dockerfiles (regime updater, reset scheduler) | Sidecar workers | Yes |
| `build-lambda-layer.ps1` / `build-lambda-package.ps1` | Deploy packaging | Yes |
| Dominance / heartbeat / genai journal / sherlock | Satellite services | Selective |
| Canon docs (`CANONICAL_SYSTEM_OVERVIEW.md`, reality maps) | Truth of what is vs aspirational | **Read first** |

**Shape:** Lambda micro-orchestrator + ECS execution + DynamoDB — already a microservice-ish plane.

### B. Tradelatest local control plane
**Path:** `D:\Tradelatest`

| Piece | Role | Reuse? |
|---|---|---|
| Stdlib HTTP control plane `:8787` | Local command registry / dashboard API | **Primary** laptop + Reel demo |
| Dockerfile (health `:8788` + plane) | Containerized local stack | Yes |
| Hooks + governance scripts | Fail-closed commit gates | Yes |
| STORY-6.2 webhook draft | n8n → plane contract (spec only) | Draft ready; Claude implements |

### C. Design-memory services
| Path | Role | Reuse? |
|---|---|---|
| `D:\chatgptdocs` + `docker-compose.yml` (Postgres `nexus`) | Chat/design corpus DB | Yes for PrivateLLM / supervision |
| `D:\chatgptviewer` (62–72MB JSON) | Raw intention archive | Yes (read) |
| `D:\Chaithu\PrivateLLM` | MODE-1 reasoner + bricks pipeline | Yes for “no idea lost” |
| `D:\ProjectDiscussion\*` packs | Distilled driver designs | Yes (docs) |

### D. Agent runtimes
| Path | Role | Reuse? |
|---|---|---|
| `D:\jarvis_runtime_system` + `JarvisUI` | Agent runtime/UI | Bridge later |
| LCP `jarvis_execution.py` | Gate name in AWS plane | Already inside A |

---

## 2. Target infra map (reuse wiring — not new platforms)

```
[Design memory]     chatgptdocs Postgres + chatgptviewer + PrivateLLM
        │
        ▼
[Supervisor]        Grok Bot (this lane) — boards, claims, tickets
        │
        ├────────► [Local plane]  Tradelatest :8787  (demo / laptop / STORY-6.x)
        │
        └────────► [AWS plane]    lambda_control_plane → DynamoDB / EventBridge / SNS / ECS
                                      (real trading control — fail-closed)
```

**Rule:** Local plane for demos & development. AWS LCP for institutional pipeline. Do not duplicate LCP inside Tradelatest as a second Lambda stack.

---

## 3. Complexity & completion

| Workstream | Complexity | Est. to “usable reuse” | Blocker |
|---|---|---|---|
| Document + board this catalog | Low | **Done (this file)** | — |
| Bring up `chatgptdocs` Postgres compose | Low | 30–60 min | Docker running |
| Dry-run Tradelatest control plane `:8787` | Low–med | 1–2 hrs | deps/venv |
| Inventory LCP Lambdas vs AWS account reality | Med | half day | AWS credentials / which account |
| Wire STORY-6.2 webhook into local plane | Med | Claude ticket | Your approve implement |
| Re-deploy LCP layer + one Lambda | Med–high | 1–2 days | AWS + secrets — **User auth** |
| Full multi-symbol / Sherlock-Saul gaps | High | weeks | Product decisions |

---

## 4. Start order (recommended) — **updated 2026-09-18**

> Active path: [GROK_BOT_LOCAL_INFRA_PREP.md](GROK_BOT_LOCAL_INFRA_PREP.md) + boards in `design_cards/boards/`.  
> **AWS deploy / Hot = off until User gate.**


1. **Freeze catalog** (this doc) — no new microservice names until gaps prove need.  
2. **Local:** verify Tradelatest control plane boots (demo + Reel path).  
3. **Memory:** `docker compose up` in `chatgptdocs` for nexus Postgres.  
4. **AWS:** read `CANONICAL_TECHNICAL_REALITY.md` + `infrastructure/DEPLOYMENT.md` → checklist of what is already deployed vs zip-only.  
5. **Only then** create *new* service if a missing bridge is proven (likely: thin webhook adapter — already sketched as STORY-6.2).

---

## 5. What I will / won’t do

| Will | Won’t |
|---|---|
| Own reuse board + tickets for Claude | Blindly `terraform apply` / deploy Lambda without your OK |
| Map LCP phases ↔ Tradelatest plane | Claim live edge from infra standing up |
| Prep Reel using **local** plane | Open live orders via JARVIS/ECS |

---

## 6. Next ask (pick one)

**A.** Boot-check Tradelatest `:8787` locally  
**B.** Start `chatgptdocs` Postgres compose  
**C.** Deep-read LCP deployment reality → deployed-vs-zip matrix  
**D.** Draft Claude ticket for STORY-6.2 webhook on local plane  

Default if no reply: **C then A** (know AWS asset inventory, then local demo plane).

---:
**2026-09-18:** User chose prepare infra without AWS live trading; image boards frozen into `design_cards/boards/`; see LOCAL_INFRA_PREP.

