# Trend-bias magnitude / time prior (SEM-028)

Frozen **before** either arm's holdout contrast was computed. This is **not**
SEM-027. Change any dimension → new `MC-*`.

`trend_bias` (FM-054) is a **sign**. It is used here as a prior on the **path
magnitude and realization time of a side that is already given**. It is not used to choose the side.

| Field | Frozen value |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Outcome surface | clean_labels `y_mfe_r` + `y_time_to_mfe` (TN_ENV_CLEAN_L2, max_forward=40) |
| Unit | one `(decision_ts, side)` row with finite `y_mfe_r` and `trend_bias ∈ {+1,−1}` |
| Agreement | `agree` iff `sign(trend_bias)` matches `side` (long↔+1, short↔−1). `trend_bias=0` dropped from PRIMARY |
| Arm S (SIZE / magnitude) | `y = y_mfe_r`. `contrast_S = E[y \| agree] − E[y \| disagree]` |
| Arm T (TIME) | `y = y_time_to_mfe` (drop nulls). `contrast_T = E[y \| agree] − E[y \| disagree]` |
| Success (per arm, diagnostic) | holdout n≥30 AND both agree/disagree cells n≥30 AND `sign(holdout contrast)==sign(train contrast)` |
| Holdout | same as MC-ASYM: first test timestamp `2025-12-24 19:15:00`. Embargo 96 bars. Purge train rows whose 40-bar horizon overlaps holdout start |
| F-086 | 236-bar stride holdout is **not** this split and stays unspent |
| Overlay k=0.5 | diagnostic only: weight `1+k` on agree, `1−k` on disagree. **Not** PRIMARY (k is frozen so it cannot be swept after seeing y) |
| Hour / session | F-066 OUT OF PATH for both gates |
| Not | a side picker, SEM-027 ΔMFE retune, CRT `TRADE_OPENED`, stream `outcome`, `y_R_net` book, G001, P-GOAL-04 |
| Kill | any outcome is registered; no retune of agree, y, k, split, or which arm after seeing holdout y |

Two arms are pre-registered together. Each is scored independently. Passing S
does not pass T. Passing T does not pass S.

This is an **information** object. `y_mfe_r` is path excursion, not book PnL.
`economic_claims_allowed` is false while mt00/mt01 are UNRUN. The `y_R_net`
size overlay is a different object: SEM-029 /
`docs/research/rnet_size_overlay_object.md`.
