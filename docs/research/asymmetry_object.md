# Same-timestamp directional asymmetry (SEM-027)

Frozen **before** the holdout contrast was computed. The 2026-08-24 full-sample
atlas is hypothesis-generating and is **not** this contract's success gate.
Change any dimension → new `MC-*`.

| Field | Frozen value |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Outcome surface | clean_labels `y_mfe_r` (TN_ENV_CLEAN_L2 `horizon_excursion`, exit-agnostic, max_forward=40) |
| Unit | one **timestamp** that has both `side=long` and `side=short` |
| y | `ΔMFE = y_mfe_r(long) − y_mfe_r(short)` at that timestamp |
| t=0 state | stored `features.trend_bias` (FM-054) known on the bar |
| PRIMARY | `contrast = E[ΔMFE \| trend_bias=+1] − E[ΔMFE \| trend_bias=−1]` |
| Success (diagnostic) | holdout `n_pairs >= 30` AND both trend_bias cells `n>=30` AND `sign(holdout contrast) == sign(train contrast)` |
| Holdout | last 20% of corpus bars: first test timestamp `2025-12-24 19:15:00` (idx 37820). Embargo 96 bars. Purge train pairs whose 40-bar horizon overlaps the holdout start. |
| F-086 | 236-bar **stride** holdout is **not** this split and stays unspent |
| Hour / session | F-066 OUT OF PATH for the success gate. Reported as diagnostic cells only |
| Not | a trade, CRT `TRADE_OPENED`, stream `outcome`, win rate, G001 |
| Kill | any outcome is registered; no retune of which states after seeing holdout y |

This is an **information** object. ΔMFE is path excursion, not book PnL.
`economic_claims_allowed` is false while mt00/mt01 are UNRUN.
