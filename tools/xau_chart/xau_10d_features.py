"""Fetch XAUUSD M15 from 2026-09-28 via MT5, run the production FeaturePipeline, dump post-warmup features."""
import json, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

OUT = Path(__file__).parent

if not mt5.initialize():
    raise SystemExit(f"MT5 init failed {mt5.last_error()}")
mt5.symbol_select("XAUUSD", True)
_start = datetime(2026, 9, 28, tzinfo=timezone.utc)
# MT5 bar times are broker-server time (UTC+3 here) stamped as if UTC, so "now in UTC" would
# cut off the newest ~3 hours. Ask past the server clock instead.
_end = datetime.now(timezone.utc) + timedelta(days=1)
r = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M15, _start, _end)
# Candles for the multi-timeframe chart, same window, straight from the terminal.
TFS = {"M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "M30": mt5.TIMEFRAME_M30,
       "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}
candles = {}
for name, tf in TFS.items():
    rr = mt5.copy_rates_range("XAUUSD", tf, _start, _end)
    candles[name] = [[int(x["time"]), float(x["open"]), float(x["high"]), float(x["low"]),
                      float(x["close"]), int(x["tick_volume"])] for x in rr]
    print(name, len(candles[name]))
# D1_AMD needs the previous full day's PDH/PDL for 09-28, so classify from a few days earlier.
_amd_raw = mt5.copy_rates_range("XAUUSD", mt5.TIMEFRAME_M15, datetime(2026, 9, 1, tzinfo=timezone.utc), _end)
mt5.shutdown()

sys.path.insert(0, str(OUT))
import amd_state  # noqa: E402
from features.broker_clock import mt5_server_to_utc  # noqa: E402
from research.secondlow_v1.detector import compute_true_range_atr  # noqa: E402
_a = pd.DataFrame(_amd_raw)
_a["timestamp"] = pd.to_datetime(_a["time"], unit="s")
_a["utc"] = mt5_server_to_utc(_a["timestamp"])
_a["atr"] = compute_true_range_atr(_a)  # not used by the v2 gates (D1_ATR); kept for reference
_states, _trig, _info = amd_state.run(_a)
_win0 = int(datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp())
_ep = _a["time"].astype(int).tolist()
amd = {
    "states": [[_ep[i], _states[i]] for i in range(len(_a)) if _ep[i] >= _win0 and _states[i]],
    "days": [{**{k: (float(v) if isinstance(v, (int, float)) and k not in ("start", "end", "asia_end", "anchor") else v)
                 for k, v in di.items() if k not in ("start", "end", "asia_end", "anchor", "events")},
              "t0": _ep[di["start"]], "t1": _ep[di["end"]],
              "asia_t1": _ep[di["asia_end"]] if di["asia_end"] is not None else None,
              "anchor_t": _ep[di["anchor"]] if di["anchor"] is not None else None,
              "events": [[e[0], _ep[e[1]], e[2]] for e in di["events"]]}
             for di in _info if _ep[di["end"]] >= _win0],
    "triggers": [{**tr, "t": (_ep[tr["t"]] if tr["t"] is not None else None)} for tr in _trig],
}
for dd in amd["days"]:
    print("AMD", dd["day"], "D1_ATR", round(dd["D1_ATR"], 2), "P0", dd["P0"], "PDH", dd["PDH"], "PDL", dd["PDL"], [(e[0], datetime.fromtimestamp(e[1], timezone.utc).strftime("%H:%M"), e[2]) for e in dd["events"]])
raw = pd.DataFrame(r)
raw["timestamp"] = pd.to_datetime(raw["time"], unit="s")
raw = raw.rename(columns={"tick_volume": "volume"})[["timestamp", "open", "high", "low", "close", "volume"]]
raw = raw[raw["timestamp"] >= "2026-09-28"].reset_index(drop=True)
raw["_pos"] = range(len(raw))
print("raw bars", len(raw), raw.timestamp.iloc[0], "->", raw.timestamp.iloc[-1])

enriched, vectors = FeaturePipeline(raw.copy()).run()
first_pos = int(enriched["_pos"].iloc[0])
print("warmup dropped", first_pos, "| first post-warmup bar", enriched["timestamp"].iloc[0], "| rows", len(enriched))

# ── SMC zone prices ($) on the same trailing window the pipeline uses + parity check ─────────
import smc_zone_prices as SZ  # noqa: E402
_zp, _k, _mw = SZ.zone_prices(raw)
_FEAT = {"ob": "order_block_distance", "fvg": "fvg_distance", "brk": "breaker_distance", "mit": "mitigation_block_distance"}
_mis = {kk: 0 for kk in SZ.KINDS}
for _p, (_, _row) in zip(enriched["_pos"].astype(int), enriched.iterrows()):
    _re = SZ.parity(_zp[_p], float(_row["close"]), float(_row["atr"]) * float(_row["close"]))
    for kk, f in _FEAT.items():
        if abs(_re[kk] - float(_row[f])) > 1e-4:
            _mis[kk] += 1
print("SMC zone parity (k", _k, "window", _mw, ") mismatches vs pipeline over", len(enriched), "rows:", _mis)
_r2 = lambda v: round(float(v), 2)
smc_z = {"k": _k, "max_window": _mw, "parity_mismatch": _mis, "rows": len(enriched),
         "t": [int(x.timestamp()) for x in raw["timestamp"]],
         "z": [{kk: (None if z is None else [_r2(z[0]), _r2(z[1]), bool(z[2]), int(z[3])]) for kk, z in rec.items() if kk in SZ.KINDS}
               | {kk: (None if rec[kk] is None else [_r2(rec[kk][0]), _r2(rec[kk][1]), int(rec[kk][2])]) for kk in ("rb_bear", "rb_bull")}
               for rec in _zp]}

cols = ["timestamp"] + list(CANONICAL_FEATURES)
tbl = enriched[cols].copy()
tbl["timestamp"] = tbl["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
tbl.to_csv(OUT / "xau_10d_features.csv", index=False)

# ── Hindsight oracle: sequential, largest-TP trades (user spec 2026-10-07) ─────────────────
# Entry at bar i close. Future = bars i+1..end (no horizon cap). TP = furthest price reached
# in the trade direction; j = FIRST bar that reaches it. SL = tightest stop that survives up to
# AND INCLUDING bar j (same-bar ambiguity resolved stop-first, so bar j's own extreme counts),
# never on the wrong side of entry, minus one tick. A trade is kept only if
# (TP distance - round-trip cost) > 0; otherwise no trade from bar i, try i+1.
# Next entry = close of the TP bar j. LOOKAHEAD BY CONSTRUCTION — oracle, never a signal.
from research.costs import xau_measured_cost_model  # noqa: E402
_COST = xau_measured_cost_model()
COST_TP = _COST.cost_price(exit_kind="TP_HIT")   # entry leg + limit exit leg, $/oz; swap excluded (UNMEASURED)
TICK = 0.01
m15 = candles["M15"]


def oracle_chain(direction: str) -> tuple[list, int]:
    trades, skipped, i, n = [], 0, 0, len(m15)
    while i < n - 1:
        entry = m15[i][4]
        fut = m15[i + 1:]
        if direction == "long":
            best = max(x[2] for x in fut)
            j = next(k for k, x in enumerate(fut) if x[2] == best)
            worst = min(x[3] for x in fut[: j + 1])
            tp, sl = best, min(entry, worst) - TICK
        else:
            best = min(x[3] for x in fut)
            j = next(k for k, x in enumerate(fut) if x[3] == best)
            worst = max(x[2] for x in fut[: j + 1])
            tp, sl = best, max(entry, worst) + TICK
        reward, risk = abs(tp - entry), abs(entry - sl)
        net = reward - COST_TP
        if net <= 0:
            skipped += 1
            i += 1
            continue
        jb = i + 1 + j
        trades.append({
            "dir": direction, "entry_t": m15[i][0], "exit_t": m15[jb][0], "entry": entry,
            "sl": round(sl, 2), "tp": tp, "risk": round(risk, 2), "reward": round(reward, 2),
            "R": round(reward / risk, 2), "bars": jb - i, "cost": round(COST_TP, 3),
            "net_oz": round(net, 2), "net_lot": round(net * 100, 2), "skipped_before": skipped,
        })
        skipped = 0
        i = jb
    return trades, skipped


oracle = {}
for _d in ("long", "short"):
    _t, _tail = oracle_chain(_d)
    oracle[_d] = {"trades": _t, "skipped_at_end": _tail}
    print(_d, "trades", len(_t), "| net $/oz", round(sum(x["net_oz"] for x in _t), 2))
    for x in _t:
        print("  ", datetime.fromtimestamp(x["entry_t"], timezone.utc).strftime("%m-%d %H:%M"), "->",
              datetime.fromtimestamp(x["exit_t"], timezone.utc).strftime("%m-%d %H:%M"),
              "E", x["entry"], "SL", x["sl"], "TP", x["tp"], "R", x["R"], "bars", x["bars"], "net/oz", x["net_oz"])

payload = {
    "amd": amd,
    "smc_z": smc_z,
    "oracle": oracle,
    "cost": {"round_trip_tp_exit": round(COST_TP, 3), "source": _COST.source,
             "components": "half-spread 0.045 + commission 0.040 + entry slip 0.090 + exit half-spread 0.045 + commission 0.040; swap not charged (unmeasured)"},
    "meta": {
        "symbol": "XAUUSD", "timeframe": "M15", "clock": "MT5 broker-server time, bar open",
        "raw_bars": len(raw), "raw_first": str(raw.timestamp.iloc[0]), "raw_last": str(raw.timestamp.iloc[-1]),
        "warmup_bars": first_pos, "rows": len(tbl), "first_post_warmup": tbl["timestamp"].iloc[0],
        "features": list(CANONICAL_FEATURES),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    },
    "candles": candles,
    "epoch": [int(t.timestamp()) for t in enriched["timestamp"]],
    "rows": [[row[0]] +[None if pd.isna(v) else round(float(v), 6) for v in row[1:]]
             for row in tbl.itertuples(index=False)],
}
(OUT / "xau_10d_features.json").write_text(json.dumps(payload), encoding="utf-8")
print("first row:")
print(tbl.iloc[0].to_string())
