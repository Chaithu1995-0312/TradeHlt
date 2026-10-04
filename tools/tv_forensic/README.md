# TradingView forensic capture

Standalone Playwright tool. Opens a public TradingView chart, frames an exact date
window, saves a clean candle screenshot, and writes a sidecar JSON that says
*exactly* what is on screen — resolved clock, achieved window, every bar with its
pixel x, a price→pixel calibration, and a per-bar engine-vs-TradingView diff.

Nothing here touches the trading engine. It only reads `data/XAUUSD_M15.csv`.

## Setup (once)

```powershell
python -m pip install -r tools/tv_forensic/requirements.txt
python -m playwright install chromium
```

## Run

```powershell
python tools/tv_forensic/capture_tv.py --preset jul28-long
python tools/tv_forensic/annotate.py --all
```

Shots land in `tools/tv_forensic/shots/` as `<name>.png` + `<name>.json`, and the
annotator adds `<name>_ANNOTATED.png` + `<name>_ANNOTATED.json`.

Other entry points:

```powershell
# one-off window (broker clock by default)
python tools/tv_forensic/capture_tv.py --symbol OANDA:XAUUSD --interval 15 `
    --from "2026-07-28 03:45" --to "2026-07-30 08:00" --name my_shot

# print engine CSV bars for a broker-time range
python tools/tv_forensic/capture_tv.py --dump-engine-bars "2026-07-30 06:00" "2026-07-30 09:00"

# fail instead of skipping when an event falls outside the frame
python tools/tv_forensic/annotate.py --shot 04_m15_jul28_forensic --strict
```

`--headed` shows the browser. `--via-ui` frames with the Go-to-date dialog instead
of the widget API.

## The clock rule (read this before editing shot_plan.json)

Engine timestamps are **broker** (MT5 server) time. TradingView is driven in UTC.

Write every window in `shot_plan.json` using the engine's own timestamps and leave
`"clock": "broker"`. **Do not hand-convert times in that file.** The offset is
resolved at runtime by measurement: each run takes the engine bars behind the
known events, tries every hour offset from −12 to +12, and keeps the one whose
OHLC actually matches TradingView's. It refuses to continue unless the winner
beats the runner-up by 5×.

For the Jul 2026 window that resolves to **UTC+3**, mean abs error 0.371 against a
runner-up of 38.679. It is measured rather than hardcoded because per F-066 the
MT5 server tracks *US* DST, so the offset is +3 in summer and +2 in winter.

This is not a style preference. Shot 04 previously ran `03:00 → 09:00` as if those
broker strings were UTC, so RANGE / SWEEP / DISPLACEMENT fell before the left edge
of the capture — and the old annotator drew them at the edge anyway, labelled
"01:00 UTC cluster". The picture asserted a mapping onto candles that were not in
it. One clock, resolved once, removes that whole class.

## What the sidecar gives you

The screenshot is the illustration; the sidecar is the evidence.

- `clock` — resolved offset plus the match errors that justify it
- `window.requested` / `window.achieved` — capture fails if they disagree
- `plot` — canvas rect, bar spacing, price→pixel calibration
- `bars` — every visible bar: time, OHLC, and page-pixel x
- `engine_events` — each event's UTC, x, `in_frame`, engine OHLC vs TV OHLC
- `engine_vs_tv` — per-bar diff table + summary (M15 shots only)

Current agreement on the Jul 28→30 M15 window: mean abs error 0.39 over 202 bars.
One bar diverges — broker `2026-07-30 01:00`, open differs by 5.82 with H/L/C
agreeing inside 0.3. That is an OANDA-vs-broker daily-rollover difference, not a
clock error.

Note the feeds are different brokers: `OANDA:XAUUSD` is a close proxy for the
engine's feed (~0.1–0.5 spread), not the same ticks.

## Events on coarser timeframes

Engine events carry M15 timestamps. On a 4H chart an event usually falls *inside*
a candle rather than on its open, so it is mapped to the containing candle and the
table marks that row `~` — the OHLC shown is the whole 4H candle, not the M15 bar.

## Files

| File | Role |
|---|---|
| `capture_tv.py` | entry point: clock calibration, framing, screenshot, sidecar |
| `tv_bridge.py` | verified `window.TradingViewApi` calls (framing, bars, geometry) |
| `engine_data.py` | engine CSV, offset resolution, engine-vs-TV diff |
| `annotate.py` | draws events from the sidecar; refuses off-frame events |
| `ui_fallback.py` | the original Go-to-date dialog path, behind `--via-ui` |
| `shot_plan.json` | shots, presets, engine events |

**Superseded, kept only for reference** (untracked, so not deleted automatically —
remove when you are sure nothing else refers to them):
`annotate_engine_events.py`, `annotate_shot05.py`, `annotate_shot06.py` are
replaced by `annotate.py`; `_dump_jul28_bars.py`, `_dump_jul30_bars.py` are
replaced by `--dump-engine-bars`; `_probe_*.py` were exploratory.

## Why not the shared layout URL

`https://in.tradingview.com/chart/Io3C5clp/` returns "Chart Not Found" without its
owner's login. The public Superchart needs no login and exposes the same widget
API:

`https://www.tradingview.com/chart/?symbol=OANDA:XAUUSD&interval=15`

Verified on that build: `setSymbol` / `setResolution` / `setTimezone` /
`removeAllStudies` / `requestMoreData` / `zoomToBarsRange(from, to)` all work.
`setVisibleRange` and `setVisibleTimeRange` both throw `Not implemented`, and
`zoomToBarsRange({from, to})` is a silent no-op — positional args only.
