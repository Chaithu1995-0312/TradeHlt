# y_R_net size overlay on independent entry (SEM-029)

Frozen **before** the holdout overlay delta was computed. This is **not**
SEM-028 (path MFE / time) and **not** SEM-027 (ΔMFE). Change any dimension →
new `MC-*`.

Side is **given by the ledger**. `trend_bias` only weights that side. It does
not choose the entry and does not choose the side.

| Field | Frozen value |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Outcome surface | clean_labels `y_R_net` (TN_ENV_CLEAN_L2 primary walk `rr_achieved − cost_r`) |
| Cost | protocol `COST_BPS=12` already subtracted inside stored `y_R_net`. F-082: ~11× punitive vs measured XAUUSD broker. **Not** SEM-015. Do not retune cost after seeing y |
| Independent entry | every `(decision_ts, side)` row on that surface. Both sides exist at each timestamp. Not CRT `TRADE_OPENED`, not SEM-012, not SEM-026 |
| Unit | one row with finite `y_R_net` and `trend_bias ∈ {+1,−1}` |
| Agreement | `agree` iff `sign(trend_bias)` matches `side` (same rule as SEM-028). `trend_bias=0` dropped from PRIMARY |
| Overlay | `k=0.5` frozen. `w = 1+k` if agree else `1−k` |
| PRIMARY | `overlay_delta = E[w · y_R_net] − E[y_R_net]` |
| Success (diagnostic) | holdout agree and disagree cells n≥30 AND `sign(holdout overlay_delta)==sign(train overlay_delta)` |
| Holdout | same as MC-ASYM: first test timestamp `2025-12-24 19:15:00`. Embargo 96 bars. Purge train rows whose 40-bar horizon overlaps holdout start |
| F-086 | 236-bar stride holdout is **not** this split and stays unspent |
| Hour / session | F-066 OUT OF PATH |
| Not | a side picker, E>0 gate, long_only beat, SEM-015, G001, P-GOAL-04, live size overlay |
| Kill | any outcome is registered; no retune of k, y, agree, cost, split after seeing holdout y |

`E>0` is **not** the gate. F-086 already said this every-bar population does not
mark a profitable entry. The question is whether overweighting the agreeing
side **lifts** stored R-net relative to equal size, with the same sign on
holdout.

This is still an **information** object. `economic_claims_allowed` is false
while mt00/mt01 are UNRUN. P-GOAL-04 is not opened.
