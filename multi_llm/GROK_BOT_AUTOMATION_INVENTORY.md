# GROK_BOT_AUTOMATION_INVENTORY.md — runbook map (STORY-81.5)

> **Owner:** Grok Bot — inventory / docs / runbooks only (spec).  
> **Implements code:** Claude (Executor).  
> **Not in scope:** .grok/ coding-Grok playground.  
> **Census date:** 2026-09-18 (DESKTOP machine, `D:\Tradelatest`).  
> **Companion:** [GROK_BOT_HARD_CONSTRAINTS.md](GROK_BOT_HARD_CONSTRAINTS.md), [GROK_BOT_TRACK.md](GROK_BOT_TRACK.md).

---

## 1. Surfaces (what exists)

| Path | Role | Size (approx) | Grok Bot stance |
|---|---|---|---|
| `scripts/` | Main automation + research/ops Python | ~457 `.py` (+295 `.pyc`), 20 theme subdirs | **Primary inventory** — document; do not rewrite |
| `hooks/` | Tracked git hooks (CLAUDE.md §6) | 3 files (`pre-commit`, `commit-msg`, README) | Document activate recipe; Claude owns hook logic |
| `agent-tools/` | Ad-hoc agent dump/scratch | 1 `.txt` JSON-ish research dump | Treat as **scratch**, not a tool API |
| `manual_tools/` | Demo-only MT5 trade generator | 1 `trade_generator.py` | **Dangerous if misused** — DEMO invariants; doc only |
| `tools/` | Replay / patch / forensic utilities | ~24 `.py` + `tv_forensic/` media/json heavy | Inventory entrypoints; Claude implements changes |

---

## 2. `scripts/` map (by subdirectory)

| Subdir | `.py` count | Purpose (from layout + samples) | Typical consumer |
|---|---:|---|---|
| `research/` | 175 | Largest bucket — research probes / CRT / analysis scripts | Research lane / Claude |
| `analysis/` | 156 | Analysis utilities | Research / reporting |
| `governance/` | 38 | Epistemic / CRT adjudication / coverage / MSIP builders | Hooks + CI + governance docs |
| `data/` | 22 | Data prep / ingest helpers | Pipelines |
| `maintenance/` | 15 | **Hook backends**: `check_governance_invariants.py`, `check_session_log_commit.py`, `check_consolidation_due.py`, cleanup | `hooks/` + CI |
| `training/` | 13 | Training / auto-train adjacent | ML lane |
| `context/` | 5 | Context compile / pack helpers (multi-LLM portable mind) | multi_llm cycle |
| `misc/` | 5 | Misc one-offs | ad-hoc |
| `evaluation/` | 4 | Eval harnesses | Research |
| `export/` | 3 | Export helpers | Ops |
| `groq_bridge/` | 3 | Groq LLM bridge (prepare / ingest / apply suggestions) | Multi-LLM bridge |
| `backtest/` | 2 | Backtest runners/helpers | Research |
| `control_plane/` | 1 | `run_server.py` — control-plane server entry | Automation / n8n-adjacent |
| `live/` | 1 | `run_live_rail.py` — live rail entry (**governed**) | Live — fail-closed; no casual run |
| `multi_llm/` | 1 | `initiate_plan.py` | multi_llm orchestration |
| `metrics/` | 1 | Metrics helper | Ops |
| `portfolio/` | 1 | Portfolio helper | Research |
| `probes/` | 0 | Empty placeholder | — |
| `tmp/` | 0 | Empty / scratch | ignore |

### Top-level `scripts/*.py` (notable)

| File | Notes |
|---|---|
| `validate_integration.py` | Integration validation entry |
| `auto_train_from_opportunities.py` | Auto-train from opportunities |
| `build_consolidated_docs.py` | Doc consolidation |
| `rag_index.py` | RAG index build |
| `update_config_hash.py` | Config hash maintenance |
| `_gate5_compliance_pass.py` | Gate 5 compliance / UNKNOWN census |
| `tmp_*` / `_tmp_*` | One-shot / scratch — prefer archive over reuse |

---

## 3. `hooks/` — activate + behaviour

**Activate (per clone):**

```sh
git config core.hooksPath hooks
```

| Hook | Blocks? | Calls | What it enforces |
|---|---|---|---|
| `pre-commit` | Yes (path-scoped) | `scripts/maintenance/check_governance_invariants.py` | Curated green floor on governed paths |
| `commit-msg` | Yes (on `src/**` / `configs/production/**`) | `scripts/maintenance/check_session_log_commit.py` | Same-day SESSION LOG or `[nolog]` |
| `commit-msg` advisory | Never | `scripts/maintenance/check_consolidation_due.py` | Consolidation nudge |

Full detail: `hooks/README.md`. Hook == CI by construction (`.github/workflows/governance.yml`).

---

## 4. `tools/` entrypoints

| Item | Role |
|---|---|
| `btcusdt_crt_v3_replay.py` | BTCUSDT CRT v3 replay (owned as coverage story STORY-80.1 elsewhere) |
| `_finalize_*_alerts.py` / `_patch_*.py` | Alert/contract patch helpers (underscore = local/one-shot flavour) |
| `tv_forensic/` | TradingView forensic tree (png/json heavy) — evidence lab, not production rail |
| `cpp/` / `oss_lab/` | Small native / OSS lab sidecars |

---

## 5. `manual_tools/trade_generator.py`

- **DEMO-ONLY** MT5 tiny-trade generator for broker-semantics validation.
- Hard safety: DEMO mode re-check, account fingerprint pin, lot cap, magic cleanup.
- **Grok Bot must not run this against live.** Doc / point Claude or User at it only.

---

## 6. `agent-tools/`

Single UUID-named `.txt` payload (research hypothesis JSON fragment). **Not** a stable CLI. If agents need a real tools package later, open a new story — do not promote this dump.

---

## 7. Related queue (automation-ish, not owned by Grok Bot)

| ID | Title | Note |
|---|---|---|
| STORY-6.2 | n8n Webhook Receiver in Control Plane | Claude implements; Grok Bot may draft contract |
| STORY-6.3 | Parallel Workdir Isolation for Scripts | Claude |
| STORY-6.4 | n8n Workflow JSON Export | Claude |
| STORY-7.1 | Claude Gate Webhook Handler | Claude |
| STORY-13.23 | [DECISION] capture_tv.py automation-evasion edit | User decision |
| STORY-80.1 | Own `tools/btcusdt_crt_v3_replay.py` | Coverage ownership |

---

## 8. Ambiguity caught this census (Class A vs B)

| Item | Class | Disposition |
|---|---|---|
| `agent-tools/` is a tools package vs scratch dump | **A** | Resolved by content: one research dump file → scratch |
| Whether Grok Bot may *run* `manual_tools/trade_generator.py` | **B** (safety/intent) | Default **no** until User authorizes a DEMO run with fingerprint |
| Whether `scripts/live/run_live_rail.py` is callable from this lane | **B** | Fail closed — live rail stays Claude/User gated |
| `probes/` and `tmp/` empty — delete vs keep | **B** (repo hygiene preference) | Leave untouched; report only |

---

## 9. Recommended next automation docs (optional follow-ups)

1. One-pager runbook: **activate hooks** — DONE `multi_llm/GROK_BOT_HOOKS_ONEPAGER.md`.
2. Spec stub for STORY-6.2 webhook contract — DONE `multi_llm/GROK_BOT_STORY62_WEBHOOK_SPEC.md`.
3. `scripts/research/` vs `scripts/analysis/` ownership note (Class B if User wants a merge policy).

---

*Census method: directory listing + README/docstring skim on DESKTOP. Not a full AST/call-graph. Re-run when folder layout changes materially.*

