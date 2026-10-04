# GROK_BOT_CODING_GROK_CROSSLINK.md — read-only interface (STORY-81.3)

> **Grok Bot stance:** READ-ONLY. Cross-link + orient other LLMs. **Never own. Never edit.**  
> **Coding Grok stance:** owns `.grok/` + `grok/` as trader-analyst validation playground.  
> **Board decision already on file:** STORY-52.2 = `.grok/` is in coverage scope but treat as another agent's territory — monitor / cite, don't disturb.  
> **Date:** 2026-09-18

---

## 1. Two Grok surfaces (do not collapse)

| Surface | Who | Job | Grok Bot may |
|---|---|---|---|
| **This chat — Grok Bot** | Desktop assistant | Research, writing, multi-LLM track, light automation *docs* | Write under `multi_llm/GROK_BOT_*` |
| **Coding Grok** | In-repo Grok LLM lane | Trader/analyst reasoning; codebase as hallucination check | Read / summarize / point — **no writes** |

If a task needs changes inside `.grok/` or `grok/`, route to **User → coding Grok or Claude**, not Grok Bot.

---

## 2. Start here (coding Grok entry kit)

| Doc | Why open it |
|---|---|
| `.grok/GOAL.md` | Goal lock: earn money as trader-analyst; repo = validation base, not the strategy |
| `.grok/PLAYGROUND.md` | Authority / semantic-review contract; what coding Grok may and may not do |
| `.grok/PENDING.md` | Authoritative pending ledger (append / mark DONE in place — coding Grok's book) |
| `.grok/FOUR_TRACKS.md` | T1 lab inventory · T2 production control · T3 CRT CLOSED · T4 find edge (don't merge into one dial) |
| `.grok/HANDOFF_TO_CLAUDE.md` | 2026-08-25 handoff: map cards only; B-before-A path; no live / no mining |
| `.grok/HOW_INDEX.md` | Generated How-index (topics → Ins/Outs → files → Excels) — large |
| `.grok/CLOSURE_KPI.md` | GCMC / closure KPI pointer |
| `.grok/GROK_WINDOW_PARQUET_BINDING.md` | Window ↔ parquet binding note |

---

## 3. Folder map (census 2026-09-18)

### `.grok/` (~43 files)

| Kind | Examples |
|---|---|
| Doctrine | `GOAL.md`, `PLAYGROUND.md`, `PENDING.md`, `FOUR_TRACKS.md`, `HANDOFF_TO_CLAUDE.md` |
| Indexes / infra | `HOW_INDEX.md`, `INFRA.md`, `infra_file_citations.md`, Excel link workbooks |
| Generators (Claude board stories 52.3) | `_build_gcmc_v2.py`, `_build_how_index.py`, `_cite_remainder.py`, `_cite_unreferenced_spine.py`, `_link_infra_architecture.py` |
| Diagnostics (story 52.4) | `run_mc_crt_sb.py`, `run_mc_crt_sb_ns.py`, `run_mc_crt_sb_soff.py` + `ns_transition_dates/` |
| Other | `bot_drop/`, `rules/`, `workflows/`, `scratch-design-*`, parquet bot brief |

### `grok/` (~14 files)

Whole-codebase context toolchain (story 19.12 on Claude board):

- Canonical Knowledge Book PDFs (Grok / Claude / QuickStart / Research / ReviewDelta)
- Repository Encyclopedia PDF
- `Book_PDF_File_Coverage_Grok.xlsx` (+ builder scripts)
- Last major PDF build ~2026-08-07 → **stale vs active coverage xlsx** (flag only; fixing = coding Grok / Claude story)

---

## 4. Related queue stories (not Grok Bot's to execute)

| ID | Status | Note |
|---|---|---|
| STORY-52.2 | **done** | Decision: in scope for monitoring, don't disturb |
| STORY-52.1 | pending | Census `.grok/` vs findings — TruthConflict discipline |
| STORY-52.3 | pending | Own GCMC-v2 generator scripts (Claude board "own") |
| STORY-52.4 | pending | Own MC-CRT-SB diagnostic family |
| STORY-19.12 | pending | Own `grok/` book toolchain + staleness audit |
| STORY-11.9 | pending | Prove `grokconcated*` reconstructable |
| STORY-41.5 / 41.7 | pending | Walkthrough / architecture from handoff |
| **STORY-81.3** | **done (this doc)** | Grok Bot read-only cross-link only |

Grok Bot does **not** flip 52.x / 19.12 to in_progress or edit those trees.

---

## 5. Hard rules for Grok Bot (and other LLMs reading this)

1. **No edits** under `.grok/` or `grok/` from the Grok Bot lane.  
2. **No silent merge** of coding-Grok claims into `docs/current-findings.md` — use TruthConflict / User.  
3. Summarize for User by default; dig into PENDING/HOW_INDEX only when asked.  
4. Live rail / production seize: still refused (PLAYGROUND + FOUR_TRACKS T2).  
5. If User asks Grok Bot to "update Grok's pending" → that's Class B ownership transfer — confirm before any write.

---

## 6. One-glance handoff blurb (paste for other LLMs)

```
Coding Grok lives in .grok/ + grok/. Start: GOAL.md → PLAYGROUND.md → PENDING.md.
Grok Bot (multi_llm/GROK_BOT_*) is a different lane: docs/track only; read-only on coding Grok trees.
STORY-52.2: monitor, don't disturb. Implementation stories 52.3/52.4/19.12 are Claude/coding-Grok board.
```
