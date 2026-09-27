# DC-003 — Fail-closed trading pipeline (spine)

| Field | Value |
|---|---|
| **ID** | DC-003 |
| **Status** | final |
| **Domain** | trading-infra |
| **Sources** | ProjectDiscussion/Trading, LambdaTradingCore CANONICAL_OVERVIEW |
| **Frozen** | yes (User Final 2026-09-18) |

## Intention
Institutional automated trading that **defaults to no-trade** on any doubt.

## Bridge
Market data → features → advisory (Sherlock/Saul) → **Ultron risk** → **Jarvis permission** → execution launch.

## Decision (proposed — awaiting freeze)
Adopt this stage order as the **canonical spine** for all trading infra talk:
1. Capital pre-check  
2. Ingest + features  
3. Advisory signals (non-authoritative)  
4. Ultron risk (supreme for risk)  
5. Jarvis gate (permission)  
6. Separate execution worker (ECS/hot/shadow/dry)  

Advisory never overrides Ultron/Jarvis.

## Plug script (optional)
Later: `scripts_design/check_spine_docs.py` — verify docs mention stages.

## Out of scope
Strategy edge math; live keys; UI chrome.

## Open questions
Exact names Ultron vs ULTRON-CS-v1 — treat as one risk governor family until User renames.

---

## Grounding C (2026-09-18) — pack + chat + code

### Design pack
- `D:\ProjectDiscussion\Trading\CANONICAL_OVERVIEW.md` — fail-closed stages; Sherlock/Saul advisory; Ultron risk; Jarvis permission; ECS execution; Track A/B.
- `D:\ProjectDiscussion\LambdaTradingCore\CANONICAL_OVERVIEW.md` — same spine; Ultron supreme; advisory not authoritative; decision ≠ execution.

### ChatGPT export (`D:\chatgptviewer\conversations.json`, 374 convos)
Titles (direct): Ultron Logic Design; Sherlock Trading Module; Saul Goodman Prompt; Jarvis Trading Update; Jarvis Phase 5 Implementation; Jarvis Phase 9 Finalization; Jarvis vs Ultron Mindset; …
Snippet doctrine:
- Ultron = quant math / risk-chaos; no narrative authority.
- Sherlock = entry/compression intelligence (start of stack).
- Saul = exit-only / trap / crowd (never entries).
- Jarvis = obedience/gate; “max intelligence, zero authority” for Ultron-in-Jarvis framing.
- Phase 9: fail-closed; Sherlock/Saul wired into lambda; then backtest only.

### Implemented code (`D:\Chaithu\lambda_control_plane`)
| Artifact | Role |
|---|---|
| `lambda_function.py` | Orchestrator; comment: FAIL-CLOSED any failure = NO EXECUTION; imports UltronCS, JarvisGate, SherlockDetector, SaulDetector; ECS client |
| `ultron_cs_v1.py` | FROZEN chaos/risk governor; math-only; single risk authority |
| `jarvis_execution.py` | Permission enforcement only; NO calculations/overrides; optional Sherlock/Saul advisory inputs |
| `control_plane\track_b_gate.py` | Track B isolation; never writes Track A state |
| `trade_intelligence\engine\sherlock_*` / `saul_*` | Advisory detectors (imported) |

### Verdict
**DC-003 spine is TRIPLE-GROUNDED** (pack ≈ chat ≈ code). Safe to `final` after User OK.

### Residual gaps (not blockers)
- Chat used “Vidura” in some genai prompts; packs/code center Sherlock/Saul/Ultron/Jarvis — note alias, don’t invent fifth governor without freeze.
- `ENABLE_SHERLOCK_SCAN` env default false — eligibility scan optional at runtime.

---:
**Frozen by User** Final on 2026-09-18. Doctrine locked; edits need re-freeze.
