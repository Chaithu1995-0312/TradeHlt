# Mother-range inside-close trade object (SEM-026)

Frozen **before** any `y_R_gross` was computed. Change any dimension → new `MC-*`.

| Field | Frozen value |
|---|---|
| Corpus | `data/mt5/XAUUSD_M15.csv` sha256 `4d73f5ce…` |
| Blocking | **calendar** `x=16` (4H floor). Not positional (phase-drifts on this corpus). |
| Mother | Block *i*: `H1=max(high)`, `L1=min(low)`, `R1=H1−L1` |
| Test | Block *i+1*: `C2` = close of that block's **last** bar |
| Inside | `L1 <= C2 <= H1` |
| InsideScore | `(C2−L1)/R1` |
| Big-mother | `R1 > 1.5 * mean(R of 20 prior mother blocks)` (prior only) |
| Skip | not inside · not big · `InsideScore == 0.5` · `R1 <= 0` · risk `<= 0` |
| Direction | `InsideScore < 0.5` → **LONG** (fade up); `> 0.5` → **SHORT** (fade down) |
| Entry | `C2` (known at test-block close = t=0) |
| SL | LONG `L1`; SHORT `H1` |
| TP | LONG `H1`; SHORT `L1` |
| Walk | `forward_walk.intrabar_fixed`, horizon 40, SL-before-TP |
| Cost | named `none_gross` for gross; net diagnostic SEM-015 measured components |
| Fill | `sem016_adverse` (`stop_slippage=0.09`, `model_gaps=True`) |
| Duplicate | one open trade at a time |
| Holdout | last 20% of corpus bars by index: first test bar `2025-12-24 19:15:00` (idx 37820). Embargo 96 bars. F-086's 236-bar **stride** holdout is **not** this split and stays unspent. |
| Success (diagnostic) | holdout `n >= 30` AND gross mean > 0 AND PF > 1 AND beats `long_only`. Still not economic while `economic_claims_allowed` is false. |
| Kill | any outcome is registered; no retune |

Not CRT. Not SEM-011. Not identity L5 (those 4 rows are engine closes).
