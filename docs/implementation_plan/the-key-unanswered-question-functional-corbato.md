# Executor Assessment — External AI-Stack Proposal (Dify / LangChain / Hermes / n8n / DuckDB / LiteLLM / Qdrant / Ollama)

## Context

Another model in the multi-LLM loop (§13) produced a "recommended stack" memo proposing you
layer Dify + LangChain + Hermes-concepts + n8n + DuckDB + LiteLLM + Qdrant + Ollama + MCP on top
of the Tradelatest / mt5_analytics ecosystem. Per **§13.8** that memo is *input to Claude, not
authority* — it's a recommendation the evidence settles. You asked for an **Executor assessment
first** (verify claims → score against frozen doctrine → per-tool verdict), with **target use not
yet decided**. This file is that verdict, not a build plan. Nothing here is executed.

The memo's own headline reframing is correct and worth keeping: *"deterministic workflow >
autonomous exploration"* and *"use each tool for one responsibility only."* The problem is it
mis-states what already exists and recommends architecture ahead of a proven bottleneck — which
**§6.5 Authority Ladder** (information ≠ value ≠ authority ≠ **architecture**) and the §6.1
"no premature framework" guardrail explicitly forbid.

---

## 1. Fact-check — what the memo claims vs. repo reality

| Memo claim | Reality (evidence) | Verdict |
|---|---|---|
| "You already have MT5 → JSONL → **Parquet** → Dashboard" | Live artifact is **JSONL + `manifest.json` (sha256)** only. `mt5_analytics/storage/partition_writer.py:1-11` = *"idempotent, date-partitioned **JSONL** writer."* **Zero** `import duckdb` / `to_parquet` / `.parquet` anywhere in `mt5_analytics/` (grep empty). | **FALSE** — no Parquet/DuckDB pipeline exists |
| DuckDB/Parquet are net-new tools to add | Already **declared optional deps** (`pyproject.toml:18-26`, `mt5_analytics` extra: pyarrow, duckdb, streamlit) — for *"later phases (storage, dashboard, research)"* but **not wired**. | Declared-not-used |
| A dashboard exists | **TRUE** — `mt5_analytics/ui/streamlit_dashboard.py` (Streamlit, read-only, consumes JSONL via `dashboard_data`). Not the control plane, not over Parquet. | TRUE (Streamlit) |
| n8n is a "new suggested tool beyond your list" | **Already a pending backlog epic** — `multi_llm/build_queue.jsonl` Epic 6 "n8n Integration" (STORY-6.1…6.5 conf 70–90 + STORY-9.3 tests), scoped into `src/control_plane/` webhook receiver. | Not new — on roadmap |
| Add LangChain / Dify / LiteLLM / Qdrant / Ollama / Hermes | **Zero footprint** in code or deps (grep). All net-new, all long-running services. | Net-new heavy |
| "Existing deterministic Intent→Plan→Tools→Execution resembles an agent framework already" | **TRUE** — `src/agent/tool_registry.py` + `plan_compiler.py` `PLAN_REGISTRY` + `IntentRouter`; deterministic by design (CLAUDE.md §3.3: *"do not route planning through the LLM"*). | TRUE — argues *against* adding another orchestrator |

**Bottom line:** the memo recommends "adopting" DuckDB/Parquet (partly already sanctioned but
inert) while calling the pipeline "done," presents an already-planned tool (n8n) as novel, and
bolts on 6 net-new server-grade dependencies with no stated consumer.

---

## 2. Doctrine scorecard

| Doctrine | Bearing on the proposal |
|---|---|
| **§4 "No database / no broker / file-backed"** | Dify, n8n, Qdrant, Ollama, LiteLLM are **long-running services** (Docker/servers) → against the file-backed posture. **DuckDB is the one exception** — embedded, file-backed, queries JSONL/Parquet in-process; already a declared dep. Not a violation. |
| **§4 "control plane is stdlib-only, localhost, no auth"** | Adding Dify/n8n web layers conflicts with stdlib minimalism. n8n was accepted *only* as a webhook receiver bolted to the existing control plane (Epic 6), not as a replacement. |
| **§6.1 no-premature-framework + §6.5 Authority Ladder** | Adding a tool = **increasing architecture**, the top rung. Doctrine: architecture is justified only by a **demonstrated consumer with measured benefit** — not "it'd be nice." "Target use not decided" ⇒ by doctrine, **build nothing yet.** |
| **§13 multi-LLM is hand-operated by design** | User=Bridge copy-paste is intentional. The *one* genuine friction the memo names (copy-paste toil) is real — but the repo already chose **n8n**, not Dify/LangChain, to address it. |
| **§6.5 "CONFIG_DRIVEN grants tunability, never authority"** | Same logic: a capability existing (Streamlit, DuckDB dep) grants *usage*, never a mandate to expand the stack. |

---

## 3. Per-tool verdict (Executor recommendation)

| Tool | Memo said | Executor verdict | Why |
|---|---|---|---|
| **DuckDB** | (bundled) | **ADOPT-WHEN-NEEDED** — read-only query over existing JSONL | Only doctrine-clean item: embedded, file-backed, already a declared dep, zero new service. The natural "ask questions over trade history" substrate. |
| **Streamlit dashboard** | implied new | **ALREADY EXISTS — extend, don't re-import** | `streamlit_dashboard.py` is live and read-only. Any "dashboard" work extends this. |
| **n8n** | "new tool" | **DEFER to Epic 6** — do not re-scope | Already planned as a control-plane webhook receiver. Not a Claude decision to re-open now. |
| **Hermes *concepts*** (persistent memory / skill files) | adopt ideas | **ALREADY PRESENT** — `~/.claude/…/memory/` + `MEMORY.md` + findings registry + Portable Mind (`scripts/context/build_context.py`, `pack_story.py`) | You already have the learning-loop. Importing "Hermes" adds nothing; avoid its self-modifying autonomous loops (memo agrees). |
| **LangChain** | partial (RAG/tools) | **REJECT for orchestration; MAYBE thin RAG only** | Deterministic `PLAN_REGISTRY` already is the tool layer; a 2nd orchestrator = duplication (the memo's own stated #1 risk). If retrieval is ever needed, a ~100-line stdlib+DuckDB path beats the dependency. |
| **Dify** | YES (high) | **REJECT** | Heavy Docker platform; duplicates control-plane + agent layer; violates stdlib/file-backed posture. No consumer identified. |
| **LiteLLM** | suggested | **REJECT (now)** | A model gateway matters only at multi-provider scale you don't run. `llm_inference_client` + BitNet/Groq/llama.cpp already cover the tie-breaker path. Revisit only if provider-fanout becomes real. |
| **Qdrant** | suggested | **REJECT** | Server-grade vector DB for a corpus that fits in memory; DuckDB + brute-force cosine covers any near-term retrieval. |
| **Ollama** | suggested | **REJECT (now)** | Local model server; overlaps existing llama.cpp/BitNet GGUF integration. No gap. |
| **AutoGPT** | NO | **REJECT — agree with memo** | Unbounded autonomous loops are the antithesis of the governance/audit posture. |
| **MCP** | suggested | **NEUTRAL / already available** | This harness already speaks MCP; not a repo dependency to "adopt." |

---

## 4. The actual recommendation

**Adopt nothing net-new right now.** By §6.1/§6.5 and your own "target use not decided," the
correct Executor answer is to *not* buy architecture ahead of a proven bottleneck. The repo already
holds the minimal-viable answer to every real need the memo raises:

- **"Ask questions over trade/findings history"** → JSONL truth + **DuckDB (already a declared
  dep)** for read-only SQL + existing **Streamlit** dashboard. No Dify/LangChain/Qdrant required.
- **"Persistent memory / skills"** → already exists (`MEMORY.md`, findings registry, Portable Mind).
- **"Reduce multi-LLM copy-paste"** → already scoped as **n8n Epic 6**; don't fork it into Dify.

**If** you later want to act, the single smallest doctrine-clean step is a **read-only DuckDB query
helper over the existing `mt5_analytics` JSONL partitions** (activates a dep you already declared,
adds no service, no schema change, `dashboard_data`-style CI-tested loader). That is the only
candidate worth a build plan — and only once you name the question you want it to answer.

---

## 5. Verification (for whatever does get built later)

Any adoption must clear the same gates the memo bypassed:
- **No new long-running service** unless it passes §4 (file-backed / localhost / no-auth-surface).
- **Named consumer + measured benefit** before it earns architecture authority (§6.5 ladder).
- **`pytest` green** + the Streamlit-free data layer stays CI-tested (mirror `dashboard_data`).
- **SESSION LOG + doc-drift decision** per §6 / §6.2 for any code that lands.

## Open decision for the user
Pick the **one question you'd want to ask over your own trade history** (or confirm "none yet").
That single use-case is the only thing that would justify turning any of this into a build plan —
and if the answer is "none yet," the correct action is to ship nothing and revisit when a real
question strains the current JSONL+Streamlit path.
