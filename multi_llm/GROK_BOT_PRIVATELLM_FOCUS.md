# GROK_BOT_PRIVATELLM_FOCUS.md

> **Focus lock (User 2026-09-18):** PrivateLLM only — **AWS not yet.**  
> **Path:** `D:\Chaithu\PrivateLLM`  
> **Role:** Trader Bot supervises; Claude implements code when ticketed.

---

## 1. What it is

PrivateLLM = **“no idea lost”** design-memory engine.

- **MODE-1:** every query re-reads raw markdown in `docs/` (not vibes/summaries).
- Corpus already loaded as **10 batch files** (~12.4 MB markdown) + raw `conversations.json` (~44 MB) + `intent_graph.sqlite` (~16.5 MB).
- Vector index present (`vector/index.faiss` ~65 MB) and **`enable_vectors: true`** in `config/app.json` (MODE-1 still canonical; vectors = recall aid).

---

## 2. Truth vs stale map

`IMPLEMENTATION_REALITY_MAP.md` is **behind the code**.

| Phase | Folder | Reality now |
|---|---|---|
| 1 MODE-1 core | `src/` | **Functional** — `main.py` → `query_handler` + multi-LLM adapter |
| 2 Vectors | `vector/` | **Built** — FAISS + metadata on disk; enabled in config |
| 3 Bricks | `bricks/` | **More than scaffold** — extractor/repo + `store.sqlite` (~24 KB) |
| 4 Analysis | `analysis/` | **More than scaffold** — gap/timeline/queries have real logic (not empty stubs) |
| 5 Governance | `governance/` | **Still scaffold** — `NotImplementedError("Phase-5")` |
| 6 UI | `ui/` | **Partial** — Streamlit `conversation_browser.py`; web/CLI advanced stubby |
| 7 Automation | `automation/` | **Scaffold** |

**Env:** `.env` has key *slots* for OpenAI/Anthropic/Gemini (names only checked). **No `venv` / `.venv` on disk** — need create before run.

**Default LLM:** `gpt-4o-mini` via `OPENAI_API_KEY`.

---

## 3. Complexity (PrivateLLM slice only)

| Slice | Complexity | Notes |
|---|---|---|
| Stand up venv + one MODE-1 query on `docs/` | **Low–med** | ~1–2 hrs if API key works |
| Refresh reality map + runbook | **Low** | Docs drift fix |
| Brick extract over 44MB conversations | **High** | Cost/tokens; needs batch strategy |
| Gap report from bricks (Phase 4) | **Med** | After bricks populated |
| Phase 5 freeze governance | **Med–high** | Greenfield relative to current stubs |
| Wire to Tradelatest / Reel | **Later** | Out of PrivateLLM-only focus |

**Supervision absorb (me):** ~80% of PrivateLLM *design/ops* board.  
**Code completion (Claude):** Phase 5–7 + any extractor bugs.

---

## 4. Reuse plan (no new microservice)

```
chatgptviewer / conversations.json
        │  (already ingested artifacts present)
        ▼
docs/Batch_*  + intent_graph.sqlite  + vector/index.faiss
        │
        ▼
MODE-1 CLI (src/main.py)  ←── primary user surface now
        │
        ├─ bricks/store.sqlite   (intent atoms)
        └─ analysis/*            (gaps / timeline)  → governance later
```

Do **not** start AWS, n8n, or new services until MODE-1 query loop is proven on this machine.

---

## 5. Start order (PrivateLLM)

1. Create `venv` + `pip install -r requirements.txt`  
2. Confirm `OPENAI_API_KEY` works (tiny probe) — **User OK for spend**  
3. Run MODE-1: `python src/main.py "What decisions about trading control plane were frozen?"` against `docs/`  
4. Open Streamlit browser if useful: `ui/conversation_browser.py`  
5. Brick census: how many rows in `bricks/store.sqlite` / intent graph — then gap report  
6. Rewrite `IMPLEMENTATION_REALITY_MAP.md` to match code (supervision hygiene)  
7. Only then: Phase-5 freeze design ticket for Claude  

---

## 6. Blockers / Class B

- OK to create venv + install deps on `D:\Chaithu\PrivateLLM`?  
- OK to spend OpenAI credits for probe + first MODE-1 query?  
- Prefer OpenAI (current default) or switch Claude/Gemini for MODE-1?

---

## 7. Out of scope until you say

AWS / lambda_control_plane deploy · Tradelatest :8787 · Instagram Reel · new microservices
