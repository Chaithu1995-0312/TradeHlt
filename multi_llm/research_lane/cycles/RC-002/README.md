# RC-002 — Position B revisit (bridge operating sheet)

**You are the bridge.** No model calls another; you carry each package by hand.
**Promise rung: PL-0. `economic_claims_allowed: false`.** Nothing here promotes anything.

## The ambiguity

Two of your own recorded decisions conflict, and one rests on an interpretation Claude has
retracted:

- **F-074** (user-authorized 2026-08-13, `Certain`, implemented at 4 sites, floor-tested) —
  counter-directional `SWEEP -> DISPLACEMENT` is deliberately illegal.
- **Position B** (user-decided 2026-09-03) — occupancy is missing a construct for it.

Position B was taken on the claim that these bars are *reversals*. Measured: on 29 of 32 the
trend was **already** running the candle's way before it arrived (p ~ 4e-07 against a 47.86%
base rate). They look like trend **resumption after a counter-trend sweep**, not reversals.

Full evidence, including the parts that cut against the retraction:
[`EVIDENCE_DOSSIER.md`](EVIDENCE_DOSSIER.md).

## Run order — different roles, different package kinds, NO voting

`RESEARCH_ROLES.md`: *"Same problem -> different roles -> different package kinds. Never: four
models answer same prompt and vote."* Each model answers **one** question that no other model
is asked. Do not paste one model's answer into another as a prompt.

| # | Paste into | Prompt file | It fills | Its one question |
|---|---|---|---|---|
| 1 | **DeepSeek** | `proposals/deepseek/RC-002/PROMPT_FOR_DEEPSEEK.md` | `CRITIQUE.md` | Is the retraction itself sound, or an over-correction? |
| 2 | **Grok** | `proposals/grok/RC-002/PROMPT_FOR_GROK.md` | `PROPOSAL.md` | If not "reversal", what IS this population? (>=3 identities + `UNKNOWN`) |
| 3 | **Gemini** | `proposals/gemini/RC-002/PROMPT_FOR_GEMINI.md` | `CRITIQUE.md` | Does the base-rate control license the conclusion? (statistics only) |
| 4 | **ChatGPT** | `proposals/chatgpt/RC-002/PROMPT_FOR_CHATGPT.md` | `DECISION.md` | Close with exactly one of the ten verdicts + what Position B becomes. Draft only. |
| 5 | **You** | — | binding `DECISION` | Rule on Position B. |

**DeepSeek goes first on purpose:** if the retraction is defective, the rest is wasted.
**ChatGPT goes last and needs 1-3 pasted in** alongside its prompt — it is the only turn that
sees the others.

## Per turn

1. Paste `PROMPT_FOR_<MODEL>.md` **and** that folder's `CONTEXT_BUNDLE.md` (~73 KB, 8 curated
   docs — the dossier plus the governance contracts; no full-repo scan).
2. Paste the model's reply over the stub file, keeping the yaml block.
3. Capture verbatim: `python scripts/context/log_turn.py --actor <model> --story RC-002 --in resp.txt`
4. Append one ledger line per real package to `research_cycle_ledger.jsonl` (the four
   `*-INIT` lines already there are stubs, not the packages themselves).

## Regenerate any package

```bash
PYTHONPATH=src python scripts/multi_llm/initiate_plan.py \
  --model grok --cycle RC-002 --kind PROPOSAL \
  --manifest multi_llm/research_lane/context_manifest_rc002.json \
  --prompt multi_llm/research_lane/cycles/RC-002/prompts/ROLE_PROMPT_GROK.md \
  --focus "identity candidates for the 32-bar population"
```

## Watch for

- **Any model that answers another model's question.** Route it back; do not merge.
- **Any model that reuses the name `SweepReversal`** without arguing for it — it is recorded as
  a misnomer and Grok is explicitly forbidden from ratifying it by default.
- **Agreement being treated as evidence.** Three packages of three kinds are not three votes.
- **Any output above PL-0**, or any proposed code / `CRTState` / `when:` predicate / config
  change. All of that is out of scope for this cycle.
- **`UNKNOWN:` is a valid answer** and is preferred to an invented file, symbol, or number.

## Known gap this cycle does not close

Grok cannot legally appear as `next_actor` in `HANDOFF.md` —
`tests/test_handoff_state.py:_ROLES` is `{DeepSeek, Gemini, ChatGPT, Claude}`, with no Grok
seat, despite CLAUDE.md §13 and `RESEARCH_ROLES.md` both giving it one. Routed around here
(DeepSeek is first, and Grok's turn is carried by this ledger, whose `author_model` is
free-text). Recorded, not patched.
