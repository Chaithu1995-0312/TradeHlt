# OHLCV Corpus Mutation Freeze (R0)

| Field | Value |
|---|---|
| Freeze ID | `OHLCV-CORPUS-FREEZE-2026-07-10` |
| Effective | 2026-07-10 |
| Mechanical pin | [`ohlcv-corpus-freeze-pin-2026-07-10.json`](ohlcv-corpus-freeze-pin-2026-07-10.json) |
| Authority table | [`corpus_authority_decisions.jsonl`](corpus_authority_decisions.jsonl) |
| Doctrine | [`CORPUS_AUTHORITY.md`](CORPUS_AUTHORITY.md) |
| Trigger | PASS-B BC-5 silent replacement of hash-pinned XAUUSD canonical corpus |
| Scope | Process + mechanical pin guard — **not** load-time admission (R3) |

---

## Why this freeze exists

PASS B proved that a hash-pinned canonical corpus can be replaced by bytes that are
byte-identical to a strict-gate **quarantined** artifact while the pin stays stale
and no promotion decision is recorded (`OHLCV_CLOSURE_STATUS` blocker **BC-5**).

Remediation itself can change the evidence substrate while it is being fixed.
Until each logical corpus has a recorded authority decision, mutation is forbidden.

---

## Forbidden without a recorded authority decision

The following are **prohibited** unless a matching row in
`corpus_authority_decisions.jsonl` has `decision_status` ∈
`{APPROVED, REJECTED, QUARANTINED}` and explicitly covers the new bytes
(`approved_sha256` or a candidate hash named in the decision evidence):

1. **Canonical corpus replacement** — overwrite of any `data/{SYMBOL}_{TIMEFRAME}.csv`
   root file (or any path listed in the freeze pin).
2. **Root-file overwrite from fetch scripts** — writing fetch output onto a freeze-pinned path.
3. **Corpus promotion** — treating a provider/quarantine/archive file as the new canonical.
4. **Quarantine → canonical movement** — copying/moving `_rejected/` bytes to root or
   to a path consumers treat as authoritative.
5. **HANDOFF pin changes** — edits to `HANDOFF.md` `standing_rules.canonical_corpus`
   hash/path without a decision record.
6. **Silent research-pin updates** — changing `src/research/secondlow_v1/corpus.py`
   (or equivalent) hash prefixes without a decision record.

---

## Allowed without a new decision

- Read-only analysis, census regenerate/`--check`, integrity reports that do not rewrite corpora.
- Retention of existing quarantine/archive trees as-is.
- Documentation of candidates and adjudication packages (this remediation slice).
- Adding or updating **authority decision records** and freeze policy itself.
- Non-pinned scratch paths **only** when explicitly labeled non-authoritative and not
  consumed by governed research/backtest paths (prefer provider trees + explicit names).

---

## Mechanical enforcement

`tests/test_ohlcv_corpus_freeze.py` verifies that every path in
`ohlcv-corpus-freeze-pin-2026-07-10.json` still has the pinned SHA-256 on disk.

Drift is allowed **only** when a non-`UNRESOLVED` decision record for that
`logical_corpus_id` lists the new hash as the approved (or explicitly rejected/
quarantined) target. `UNRESOLVED` never authorizes mutation.

This is **not** a `CandleLoader.stream()` admission gate. That is R3.

---

## Waiver procedure (post-decision apply)

1. Record / update the authority decision row (status ≠ `UNRESOLVED`).
2. Perform the single authorized byte/path change (if any).
3. Update the freeze pin to the new hashes in the **same** change set.
4. Align HANDOFF / research pins / CORPUS_POLICY in that same change set.
5. Re-run freeze + authority + SECONDLOW regression tests.

---

## Explicit non-goals (this freeze)

- Does not choose which XAUUSD bytes are authoritative (see R2 adjudication).
- Does not implement binding manifest or load-time hash verification.
- Does not ban synthetic corpora; undeclared synthetic lineage remains a G-10
  contract contradiction until declared (see `CORPUS_AUTHORITY.md`).
