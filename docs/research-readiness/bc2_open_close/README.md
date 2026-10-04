# BC-2 open-vs-close label — live evidence

Live snapshots and the score for probe `BC2-OPEN-CLOSE-XAUUSD-MT5-V1`.

**Authoritative rules:** [`docs/research/preregistration-bc2-open-close-label.md`](../../research/preregistration-bc2-open-close-label.md)
(§1–§8 frozen 2026-09-02; §9 amendments 2026-09-03).

| File | Role |
|---|---|
| `snapshot_a.json` | Mid-interval capture — `fetched_at` inside the forming bar |
| `snapshot_b.json` | Post-close capture of the same bar |
| `score.json` | Verdict under the frozen §5 rules |

## What a verdict means

`OPEN` proves the MT5 `rates['time']` label is the bar **open** for this acquisition
family, and is the `executable_open_vs_close_label_proof` artifact named as ABSENT in
the Phase-1 G2 residual. `CLOSE` **contradicts** G-06 (G-06 *is* open-time labeling).
`OTHER` and `INSUFFICIENT` leave BC-2 UNPROVEN — they are real results and must not be
re-timed until they hit (§5, §6).

A verdict here is scoped to the **mt5 acquisition family**. It does not move
`OHLCV_CLOSURE_STATUS`, BC-1/BC-3/BC-4/BC-5/BC-6, APPROVED, or G001.

## Reproducing

```bash
python -m research.ohlcv_open_close_label capture --symbol XAUUSD --out <dir>/snapshot_a.json
# wait until fetched_at >= T_last_A + 16m
python -m research.ohlcv_open_close_label capture --symbol XAUUSD --out <dir>/snapshot_b.json
python -m research.ohlcv_open_close_label score --a <dir>/snapshot_a.json --b <dir>/snapshot_b.json
```

`snapshot_a` must land 2–13 minutes into the bar (the §4 margin excludes the first and
last 60s). Two hazards, both observed 2026-09-02: the first `copy_rates_from_pos` after
`symbol_select` can return a **cold cache** hours behind the live tick (the capture now
retries past it), and a capture at delta≈884s **misses** the 840s window edge.

Only a live pair carrying `executable_open_vs_close_label_proof: true` may be cited as
evidence. Synthetic fixtures score `source: synthetic` and are mechanically barred from
the proof flag (§9.3).
