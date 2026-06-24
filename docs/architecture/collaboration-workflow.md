# collaboration-workflow.md

> **Who this is for:** *you* — the human owner of Tradelatest. This is the plain-language
> map of **how Claude and you work together**, **how every change is tracked**, and **how
> you replay and verify what changed**. The deep, LLM-facing detail lives in the linked docs;
> this page just ties it together so you never have to hunt for it.

---

## 1. How we work together

The operating rule (Claude follows this every turn):

- **Claude acts on its own** when it's ~100% sure and the work is reversible — docs, additive
  code, analysis, running tests. You'll see what it did and can always redirect.
- **Claude stops to involve you** only on the ambiguous or judgment parts — irreversible
  actions, shared-state changes, or "which way do you want this?" decisions.
- **Momentum first.** The independent parts keep moving while one open question waits on you;
  the whole task never freezes over a single unknown.
- **Plain language.** The point comes first, in everyday words. Technical detail stays
  available but secondary.

This is the same rule recorded in Claude's memory and in [`CLAUDE.md`](../../CLAUDE.md) §5/§7.

---

## 2. The turn loop (what every response does)

From [`CLAUDE.md`](../../CLAUDE.md) §7, in plain words:

1. **Orient** — say, in one line, what's in scope.
2. **Probe** — ask 1–2 sharp questions *only if* something's genuinely unclear.
3. **Implement / discuss** — do the work, concretely.
4. **Self-document** — append a dated entry to the session log (see §3).

You can also drive this loop with one-word **triggers** (`Continue`, `Validate`, …) — see §6.

---

## 3. How every change is tracked (three dated layers)

Every change leaves a trail in three places, and **each layer carries a date**:

```
  PLAN                       COMMIT                      SESSION LOG
  docs/plans/*.md      →     git commit            →     assistant_project.md
  "what we'll do"            "the code change"           "the dated journal entry"
  Created/Updated date       commit date + scope         mandatory Date: field
```

| Layer | Where | What it answers | Timestamp |
|---|---|---|---|
| **Plan** | [`docs/plans/`](../plans/) | *What are we about to do, and why?* | `> Created: … · Updated: …` header (see §5) |
| **Commit** | git history | *What code actually changed?* | commit date + `feat/fix/test(scope)` message |
| **Session log** | [`assistant_project.md`](../../assistant_project.md) | *What happened this turn, and what's next?* | mandatory `Date:` field — [`CLAUDE.md`](../../CLAUDE.md) §6 |

The session log is the journal you skim to catch up; the plan is the intent; the commit is
the proof. Read them newest-first.

---

## 4. The "explain every change" contract

Whenever Claude implements something, it explains it back to you in the same shape, in plain
words:

- **What changed** — the files/behavior, one line.
- **Why** — the reason, tied to a goal or your request.
- **Blast radius** — what else this could touch (who depends on it).
- **How to replay / verify** — the exact step you'd run to confirm it (see §5).

…then it logs the same thing to [`assistant_project.md`](../../assistant_project.md). If any
of those four are missing, the change isn't done.

---

## 5. How you replay & verify a change

"Replay" here means: **run the same input twice and prove you get the same output.** That's the
core safety net — a change is only safe if it doesn't silently move the numbers. The
authoritative gate is [`replay-governance.md`](replay-governance.md) §6; the plain recipe:

1. **Snapshot before** — capture the current baseline:
   `python src/runtime/baseline_capture.py --label <name>`
   (writes a manifest with the schema hash + config SHA-256 to `results/baseline/`). See
   [`baseline_capture.py`](../../src/runtime/baseline_capture.py).
2. **Make the change.**
3. **Re-run** the *same* backtest CSV with the *same* `slippage_seed`.
4. **Assert the trade ledger + summary are byte-identical** to the before-run. New telemetry
   may be *added*, but nothing existing may change or disappear.
5. **Score the Five Governance Questions** (from the [`assistant_project.md`](../../assistant_project.md)
   doctrine header):
   1. Does replay stay deterministic?
   2. Is telemetry still comparable across runs?
   3. Can this be audited later?
   4. Can an LLM reason about this event?
   5. Is execution authority still isolated?

A change that fails step 4 is rejected no matter what else it improves. For trade-level
checks, [`scripts/misc/trade_replay_validator.py`](../../scripts/misc/trade_replay_validator.py)
re-derives each trade's RR candle-by-candle (tolerance `MAX_RR_DELTA = 0.05`). Every promotion
is also appended to the audit trail [`configs/promotion_log.jsonl`](../../configs/promotion_log.jsonl).

---

## 6. Quick reference — the trigger words

One-word commands that drive the loop. Full spec + compositions in
[`trigger-vocabulary.md`](trigger-vocabulary.md).

| Trigger | Does | Read-only? |
|---|---|---|
| **Orient** / **Status** | One-screen state report (plan + log + memory) | yes |
| **Map** | Locate where a change lands (which service/seam) | yes |
| **Continue** | Resume the active work and advance the next step | no |
| **Next step** | Do the next discrete step inside the current milestone | no |
| **Next plan** | Validate the milestone, then enter the next one | no |
| **Plan** | Enter plan mode → design → write a plan to `docs/plans/` | no (plan only) |
| **Implement** | Turn an approved plan into code, then auto-Validate | no |
| **Validate** | Run tests + the replay check + the Five Questions | yes |
| **Audit** | Re-check the docs against the code; fix docs only | docs only |
| **Log** | Append the dated session-log entry | append-only |

Composition example: `Continue = Orient → Map → Next step → Validate → Log`.

---

## 7. Where this fits

This doc is the human-facing front door to the working agreement. Its machinery lives in:
[`CLAUDE.md`](../../CLAUDE.md) (operating manual), [`trigger-vocabulary.md`](trigger-vocabulary.md)
(the loop), [`replay-governance.md`](replay-governance.md) (the verify gate),
[`assistant_project.md`](../../assistant_project.md) (doctrine + session log), and
[`goal.md`](goal.md) (the north star everything is measured against).
