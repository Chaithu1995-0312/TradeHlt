# Architecture Memory Policy

> **Authority:** This is the repository memory hierarchy contract.
> **Last generation:** 2026-08-07
> **Does not grant write authority** over production config, models, or promotion gates.

---

## Repository Memory Philosophy

`CLAUDE.md` is the project **bootloader**, not the complete documentation.

Keep `CLAUDE.md` concise and stable.

Detailed architectural knowledge belongs in companion memory documents under `docs/memory/`.

Never duplicate large architectural explanations inside `CLAUDE.md`.

---

## Memory Hierarchy

```
CLAUDE.md                          ← bootloader / navigation / operating rules
    ↓
Companion Memory Documents         ← docs/memory/*-memory.md (context indexes)
    ↓
Deep companions (architecture/, reference/, topics/, governance/)
    ↓
Repository Source Code             ← ultimate authority
```

Memory documents **summarize and index** the code.

**The source code always wins** if documentation and implementation differ.

---

## When starting a task

Do not assume all required knowledge is already loaded.

1. Determine which subsystem the task belongs to.
2. Read **only** the relevant companion memory document(s) before inspecting code.
3. Follow that document’s **Reading order** into source and deep companions.
4. Avoid loading unrelated memory.

| Task domain | Load first |
|---|---|
| Agent / modes / tools | [`agent-memory.md`](agent-memory.md) |
| Runtime / backtest / live | [`runtime-memory.md`](runtime-memory.md) |
| Features / schema / pipeline | [`feature-memory.md`](feature-memory.md) |
| Engines / scoring | [`engine-memory.md`](engine-memory.md) |
| Governance / promotion | [`governance-memory.md`](governance-memory.md) |
| Cross-cutting architecture / spine | [`architecture-memory.md`](architecture-memory.md) |

Index: [`README.md`](README.md).

---

## Memory document shape

Each `docs/memory/*-memory.md` contains **only**:

* Purpose  
* Responsibilities  
* Runtime role  
* Entry points  
* Exit points  
* Important contracts  
* Reading order  
* Related documents  
* Known coverage  
* Last generation timestamp  

They are **navigation aids**, not replacements for source code.

---

## Code-First Rule

Memory documents are secondary.

When implementation details, behavior, algorithms, thresholds, or execution order are required:

1. Read the relevant memory document.  
2. Identify the authoritative source files.  
3. Inspect the source code.  
4. Treat the **code** as the final authority.

Never infer implementation solely from memory documents.

---

## Documentation Maintenance

Whenever a significant architectural change is introduced:

* Update **only** the affected memory document(s).  
* Keep `CLAUDE.md` unchanged unless the repository structure or memory hierarchy changes.  
* Do not duplicate information across multiple memory documents.  
* Prefer linking to existing deep companions (`docs/architecture/*`, `docs/reference/*`, `docs/topics/*`) rather than copying their content.

Objective: **minimize context size** while maximizing navigability and architectural awareness.

---

## Goal

| Layer | Use for |
|---|---|
| `CLAUDE.md` | Navigate the repository; operating rules; findings index |
| Memory documents | Gain subsystem context |
| Source code | Establish truth |
