"""smc_visual_verification.py — close report row 8's open item on the SMC features.

WHAT THIS CLOSES
----------------
`reports/monthly_tv_vs_active_production_semantic_comparison.md` row 8 records the
9 SMC features (schema v5.0, canonical indices 39-47, F-076) as PRESENT but states
plainly that the check performed was presence + plausible firing RATES only:

    "It does NOT constitute a human-eye visual confirmation that a specific
     detected order block or FVG lines up with what a trader would mark on the
     Jul 15/20/28-30 charts ... left as a follow-up, not claimed as done here."

`results/monthly_tv_semantic_report/smc_feature_month.json` cannot answer it: it
stores only `{timestamp, value}` per hit — the tanh-bounded, ATR-normalized
DISTANCE — with no price level, so there is nothing to draw or check against a
chart. This script recovers the underlying `Zone` geometry by calling the same
`features.smc` detectors production calls, then does two SEPARATE things.

TWO CLAIMS, NEVER BLENDED (pre-registered, CH-monthly-tv-coverage-h4-recon)
--------------------------------------------------------------------------
MECHANICAL — independently verifiable arithmetic on the zone geometry (an FVG's
edges must BE the 3-candle gap; an order block's edges must BE its origin
candle's range; an "active" zone must not have been touched since it was
confirmed; PDH/PDL must equal the prior calendar day's true high/low recomputed
from raw rows without going through ParentCandleBuilder). A mechanical failure
is a defect and is reported as one.

VISUAL — the annotated PNG. Human judgment. A visual mismatch alone is
INSUFFICIENT EVIDENCE pending user adjudication, NOT a defect. This script never
self-certifies the visual claim; it renders the evidence and stops.

PARITY GATE (runs first, and everything else depends on it)
-----------------------------------------------------------
Zone geometry is only trustworthy if this script's trailing window is built the
way `FeaturePipeline.compute_smc_features` builds it (same `swing_window`, same
`smc_max_window`, same ABSOLUTE atr = `atr * close` per F-072/FM-074, same
incremental D1 `ParentCandleBuilder`). Rather than assert that by inspection, the
recomputed distances are compared against the pipeline's OWN stored values in
`smc_feature_month.json`. If they disagree, the run ABORTS — a zone extracted
from a differently-built window would be evidence about this script, not about
production.

WHAT THIS IS NOT
----------------
Not a new capture (no Playwright, no network — reads existing sidecars). Not a
wiring change: F-076's finding that all 6 consuming model families are stale and
these features reach no decision path is untouched. Grants no G001 and no
authority (CLAUDE.md 6.5).

USAGE
-----
    python scripts/research/smc_visual_verification.py
    python scripts/research/smc_visual_verification.py --shot 07_m15_jul15_episode
    python scripts/research/smc_visual_verification.py --no-render
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT / "tools" / "tv_forensic")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

from engine_data import MATCH_TOLERANCE as ED_MATCH_TOLERANCE  # noqa: E402

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from config_layer.production_config import get_prod_section  # noqa: E402
from features.parent_candle import ParentCandleBuilder  # noqa: E402
from features.smc._geometry import Zone, is_mitigated  # noqa: E402
from features.smc.breaker import breaker_distance, find_active_breaker  # noqa: E402
from features.smc.fvg import find_active_fvg, fvg_distance  # noqa: E402
from features.smc.levels import eqh_eql_distance, pdh_pdl_distance  # noqa: E402
from features.smc.mitigation import (  # noqa: E402
    find_active_mitigation_block,
    mitigation_block_distance,
)
from features.smc.order_block import find_active_order_block, order_block_distance  # noqa: E402

SHOTS_DIR = _ROOT / "tools" / "tv_forensic" / "shots"
OUT_DIR = _ROOT / "results" / "monthly_tv_semantic_report"
MONTH_JSON = OUT_DIR / "smc_feature_month.json"
DEFAULT_CSV = _ROOT / "data" / "XAUUSD_M15.csv"

#: zone-producing features -> (detector, colour). The 4 that yield a drawable
#: price zone; pdh/pdl/eqh/eql are levels (handled separately) and
#: change_of_character is pure algebra over existing columns (no geometry).
ZONE_FEATURES = {
    "order_block_distance": "order_block",
    "fvg_distance": "fvg",
    "breaker_distance": "breaker",
    "mitigation_block_distance": "mitigation",
}

ZONE_COLOURS = {
    "order_block": (25, 90, 185),
    "fvg": (170, 90, 0),
    "breaker": (190, 30, 30),
    "mitigation": (120, 40, 140),
}


@dataclass
class Check:
    feature: str
    timestamp: str
    kind: str
    passed: bool
    detail: str

    def as_dict(self) -> dict:
        return {
            "feature": self.feature, "timestamp": self.timestamp,
            "check": self.kind, "passed": self.passed, "detail": self.detail,
        }


# ─────────────────────────────────────────────────────────── production mirror


def load_bars(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def compute_atr_absolute(df: pd.DataFrame, period: int) -> list[float]:
    """Wilder-free SMA(true_range) — the same `atr` the pipeline emits, but kept
    in PRICE UNITS. The pipeline stores `atr` close-relative and multiplies by
    close at the SMC call site (F-072/FM-074 `atr_absolute`); computing the
    absolute form directly is the identical quantity by that identity."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean().fillna(0.0).tolist()


def scan(df: pd.DataFrame, k: int, max_window: int, atr_period: int):
    """Replay the pipeline's SMC loop, keeping the ZONES it throws away.

    Deliberately the same shape as `FeaturePipeline.compute_smc_features`: a
    trailing `Candle` window bounded by `smc_max_window`, a parallel D1
    `ParentCandleBuilder`, absolute ATR. Only the retention differs.
    """
    atr_abs = compute_atr_absolute(df, atr_period)
    ts = df["timestamp"].tolist()
    o, h, low_, c = (df[x].tolist() for x in ("open", "high", "low", "close"))

    window: list[Candle] = []
    d1 = ParentCandleBuilder("D1", keep=2)
    rows = []

    for i in range(len(df)):
        candle = Candle(
            timestamp=ts[i].to_pydatetime(), open=float(o[i]), high=float(h[i]),
            low=float(low_[i]), close=float(c[i]), volume=0.0, index=i,
        )
        window.append(candle)
        if len(window) > max_window:
            window = window[-max_window:]
        d1.push(candle)

        a = float(atr_abs[i])
        pdh, pdl = pdh_pdl_distance(float(c[i]), d1.parent_history, a)
        eqh, eql = eqh_eql_distance(window, k, a)
        rows.append({
            "i": i,
            "timestamp": ts[i].strftime("%Y-%m-%d %H:%M:%S"),
            "close": float(c[i]),
            "atr_abs": a,
            "d1_history": list(d1.parent_history),
            "window": list(window),
            "zones": {
                "order_block": find_active_order_block(window, k),
                "fvg": find_active_fvg(window),
                "breaker": find_active_breaker(window, k),
                "mitigation": find_active_mitigation_block(window, k),
            },
            "values": {
                "order_block_distance": order_block_distance(window, k, a),
                "fvg_distance": fvg_distance(window, a),
                "breaker_distance": breaker_distance(window, k, a),
                "mitigation_block_distance": mitigation_block_distance(window, k, a),
                "pdh_distance": pdh, "pdl_distance": pdl,
                "eqh_distance": eqh, "eql_distance": eql,
            },
        })
    return rows


def parity_gate(rows: list[dict], month: dict, tol: float = 2e-3) -> tuple[bool, list[str]]:
    """Do the recomputed distances match the pipeline's own stored values?

    Compared against `smc_feature_month.json`'s `hits_by_shot` — the pipeline's
    output, not this script's. Disagreement means the window construction here
    diverged from production, so no zone it produced could be trusted.
    """
    by_ts = {r["timestamp"]: r for r in rows}
    problems, compared = [], 0
    for feat, blob in month.get("per_feature", {}).items():
        if feat not in ZONE_FEATURES and feat not in (
            "pdh_distance", "pdl_distance", "eqh_distance", "eql_distance"
        ):
            continue
        hits = blob.get("hits_by_shot") or {}
        if isinstance(hits, str):          # tolerate a repr-serialized blob
            continue
        for shot, entries in hits.items():
            for e in entries[:40]:         # a sample per shot is plenty
                row = by_ts.get(e["timestamp"])
                if row is None:
                    continue
                got = row["values"].get(feat)
                if got is None:
                    continue
                compared += 1
                if abs(got - float(e["value"])) > tol:
                    problems.append(
                        f"{feat} @ {e['timestamp']} ({shot}): recomputed {got:.6f} "
                        f"vs pipeline {float(e['value']):.6f}"
                    )
    if compared == 0:
        problems.append("parity gate compared 0 values — cannot vouch for any zone")
    return not problems, problems[:20]


# ─────────────────────────────────────────────────────────── mechanical checks


def check_fvg(row: dict, zone: Zone) -> Check:
    """An FVG's edges must BE the 3-candle gap: `[bars[i-1].high, bars[i+1].low]`
    for a bullish gap. Recomputed straight from raw OHLC."""
    bars = row["window"]
    pos = next((p for p, b in enumerate(bars) if b.index == zone.formed_at_index), None)
    if pos is None or pos == 0 or pos + 1 >= len(bars):
        return Check("fvg_distance", row["timestamp"], "gap_geometry", False,
                     "formation candle not in window with both neighbours")
    prev_b, next_b = bars[pos - 1], bars[pos + 1]
    if zone.bullish:
        ok = (abs(zone.low - prev_b.high) < 1e-9 and abs(zone.high - next_b.low) < 1e-9
              and prev_b.high < next_b.low)
        want = f"[{prev_b.high}, {next_b.low}]"
    else:
        ok = (abs(zone.high - prev_b.low) < 1e-9 and abs(zone.low - next_b.high) < 1e-9
              and prev_b.low > next_b.high)
        want = f"[{next_b.high}, {prev_b.low}]"
    return Check("fvg_distance", row["timestamp"], "gap_geometry", ok,
                 f"zone [{zone.low}, {zone.high}] vs 3-candle gap {want}"
                 + ("" if ok else "  MISMATCH"))


def check_zone_is_a_real_candle_range(feature: str, row: dict, zone: Zone) -> Check:
    """Order-block / breaker / mitigation zones are candle-derived: the zone's
    edges must coincide with an actual bar's geometry at its formation index.

    WHICH geometry differs by family, and that difference is documented, not
    incidental. Order blocks and breakers use the origin candle's full RANGE
    (high/low). A mitigation block is explicitly "the body-only inner zone of the
    most recent OB origin" (`features/smc/mitigation.py:26`) — `max(open, close)`
    / `min(open, close)`.

    CORRECTED (2026-08-17): this check originally asserted high/low for all three
    and produced 66 `origin_candle` failures, every one of them on
    `mitigation_block_distance` and none on the other two — the signature of a
    wrong expectation, not a wrong implementation. The zone always sat strictly
    INSIDE the bar range, which is what a body is. Second overclaim caught by the
    same discipline as the first; both are recorded rather than quietly amended.
    """
    bars = row["window"]
    origin = next((b for b in bars if b.index == zone.formed_at_index), None)
    if origin is None:
        return Check(feature, row["timestamp"], "origin_candle", False,
                     f"formation index {zone.formed_at_index} not in window")

    if feature == "mitigation_block_distance":
        want_hi, want_lo = max(origin.open, origin.close), min(origin.open, origin.close)
        what = "origin BODY"
    else:
        want_hi, want_lo = origin.high, origin.low
        what = "origin RANGE"

    ok = abs(zone.high - want_hi) < 1e-9 and abs(zone.low - want_lo) < 1e-9
    return Check(feature, row["timestamp"], "origin_candle", ok,
                 f"zone [{zone.low}, {zone.high}] vs {what} [{want_lo}, {want_hi}] "
                 f"@ {origin.timestamp:%Y-%m-%d %H:%M}" + ("" if ok else "  MISMATCH"))


def check_causal(feature: str, row: dict, zone: Zone) -> Check:
    ok = zone.formed_at_index <= row["i"]
    return Check(feature, row["timestamp"], "causality", ok,
                 f"formed_at_index {zone.formed_at_index} vs current bar {row['i']}"
                 + ("" if ok else "  FUTURE ZONE — LOOKAHEAD"))


def check_fvg_unfilled(row: dict, zone: Zone) -> Check:
    """An active FVG must be unfilled — checked over the detector's OWN documented
    mitigation window, recomputed here from raw bars.

    CORRECTED (2026-08-17, pre-registration ritual): the first version of this
    check asserted simply "the current bar must not overlap the zone" and failed
    197 times across every shot. That was a defect in the CHECK, not in the code.
    `find_active_fvg` documents that the gap-closing candle (`i+1`) does NOT fill
    the gap and scans `bars[formed_pos+2:]`; `find_active_order_block` likewise
    measures mitigation from the confirming BREAK candle, not the origin, because
    "the break candle itself almost always geometrically overlaps the origin's
    range." A naive current-bar overlap test contradicts both contracts and
    measures a rule neither detector claims to follow. Reporting those 197 as
    defects would have been an overclaim against explicitly documented behaviour
    (CLAUDE.md 6.8: rule out an incomplete contract before concluding "defect").

    This form is still independent — the fill window is recomputed from raw bars
    rather than by re-calling the detector — but it now tests the contract that
    actually exists.
    """
    bars = row["window"]
    pos = next((p for p, b in enumerate(bars) if b.index == zone.formed_at_index), None)
    if pos is None:
        return Check("fvg_distance", row["timestamp"], "unfilled", False,
                     "formation candle not in window")
    later = bars[pos + 2:]
    filler = next((b for b in later if is_mitigated(zone, b)), None)
    ok = filler is None
    return Check("fvg_distance", row["timestamp"], "unfilled", ok,
                 f"zone [{zone.low}, {zone.high}] over {len(later)} post-formation bars"
                 + ("" if ok else
                    f"  FILLED at {filler.timestamp:%Y-%m-%d %H:%M} but reported active"))


def note_mitigation_not_auditable(feature: str, row: dict, zone: Zone) -> Check:
    """Recorded, not silently skipped (the D-1 failure class).

    For order-block / breaker / mitigation zones the mitigation window starts at
    the CONFIRMING BREAK candle, and `Zone` exposes only `formed_at_index` (the
    origin) — not the break index. So an INDEPENDENT mitigation audit is not
    constructible without reimplementing `_find_break_events`, which is exactly
    the duplicate-geometry the repo's doctrine forbids. This is a contract gap in
    `Zone`'s surface, not evidence either way about the detector, and it is
    reported as such rather than being quietly dropped from the check list.
    """
    return Check(feature, row["timestamp"], "mitigation_audit_unavailable", True,
                 "SKIPPED-BY-CONTRACT: Zone exposes formed_at_index (origin) but not the "
                 "confirming break index, so mitigation state cannot be audited "
                 "independently without duplicating _find_break_events")


def check_pdh_pdl(row: dict, df: pd.DataFrame) -> list[Check]:
    """PDH/PDL must equal the PRIOR calendar day's true high/low — recomputed by
    grouping raw rows on the broker date, deliberately WITHOUT going through
    `ParentCandleBuilder`, so the check is independent of the thing it checks."""
    hist = row["d1_history"]
    if not hist:
        return []
    parent = hist[-1]
    day = parent.timestamp.strftime("%Y-%m-%d")
    same = df[df["timestamp"].dt.strftime("%Y-%m-%d") == day]
    if same.empty:
        return [Check("pdh_distance", row["timestamp"], "prior_day_levels", False,
                      f"no raw rows for D1 parent day {day}")]
    hi, lo = float(same["high"].max()), float(same["low"].min())
    ok_h = abs(parent.high - hi) < 1e-9
    ok_l = abs(parent.low - lo) < 1e-9
    return [
        Check("pdh_distance", row["timestamp"], "prior_day_levels", ok_h,
              f"D1 parent {day} high {parent.high} vs raw-row max {hi}"),
        Check("pdl_distance", row["timestamp"], "prior_day_levels", ok_l,
              f"D1 parent {day} low {parent.low} vs raw-row min {lo}"),
    ]


def check_within_tv_range(
    feature: str, row: dict, zone: Zone, tv_lo: float, tv_hi: float,
    start: datetime, end: datetime,
) -> Check:
    """Cross-check against the chart: a zone whose prices sit outside the range
    TradingView actually printed could never line up visually.

    ONLY MEANINGFUL WHEN THE ZONE FORMED IN FRAME. The SMC detectors run on a
    trailing `smc_max_window` (100) window, so at a shot's opening bars the
    active zone routinely originates from candles BEFORE the capture starts, at
    prices the screenshot never shows. That is the window reaching back, not a
    misplaced zone.

    CORRECTED (2026-08-17): the first version omitted this gate and produced 18
    failures — all of them in the 5 NARROWEST shots (a 1.25-hour and a 3-hour
    window among them) and ZERO in the three widest, which is the trailing-window
    signature rather than a defect signature. Third and last overclaim of this
    same shape caught in this script; the skip is REPORTED (below), never silently
    dropped from the totals.
    """
    origin = next((b for b in row["window"] if b.index == zone.formed_at_index), None)
    if origin is None or not (start <= origin.timestamp <= end):
        where = f"{origin.timestamp:%Y-%m-%d %H:%M}" if origin else "unknown"
        return Check(feature, row["timestamp"], "within_tv_price_range", True,
                     f"SKIPPED-BY-CONSTRUCTION: zone formed at {where}, outside the "
                     f"captured frame — the trailing smc_max_window reaches back "
                     f"before this shot starts, so its prices need not be on screen")
    # Cross-feed comparison: the zone's edges are ENGINE-feed prices, the frame's
    # min/max are OANDA's. A zone edge that IS the window's extreme bar therefore
    # differs by the spread between the two feeds — `engine_data`'s module note
    # records that as "~0.1-0.5 total absolute error across O/H/L/C" and encodes
    # it as MATCH_TOLERANCE (an L1 sum over 4 fields). The per-field bound is
    # derived from that same constant rather than invented here, so this stays a
    # real test: the earlier genuinely off-chart zones missed by ~23-39 points and
    # would still fail loudly.
    slack = ED_MATCH_TOLERANCE / 4.0
    over_hi = max(0.0, zone.high - tv_hi)
    under_lo = max(0.0, tv_lo - zone.low)
    excess = max(over_hi, under_lo)
    ok = excess <= slack
    detail = f"zone [{zone.low}, {zone.high}] vs TV [{tv_lo}, {tv_hi}]"
    if excess > 0:
        detail += f"  (outside by {excess:.3f}, cross-feed slack {slack:.3f})"
    return Check(feature, row["timestamp"], "within_tv_price_range", ok,
                 detail + ("" if ok else "  OFF-CHART despite forming in frame"))


# ────────────────────────────────────────────────────────────────── rendering


def render(shot_stem: str, sidecar: dict, marks: list[dict]) -> Path | None:
    """Draw the zones onto the shot PNG. Reuses annotate.py's Frame/dash_h/font
    so pixel geometry comes from the sidecar's own calibration, never remeasured."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("  (Pillow absent — skipping render)")
        return None
    import annotate as an

    png = SHOTS_DIR / f"{shot_stem}.png"
    if not png.exists():
        return None
    img = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(img)
    fr = an.Frame(sidecar)
    f_small = an.font(14)
    f_bold = an.font(15, bold=True)

    drawn = 0
    for m in marks:
        colour = ZONE_COLOURS[m["kind"]]
        for edge in ("low", "high"):
            price = m[edge]
            if not fr.price_visible(price):
                continue
            y = fr.y_of(price)
            an.dash_h(d, fr.left, fr.right, y, colour, w=2)
            drawn += 1
        if fr.price_visible(m["high"]):
            label = f"{m['kind']} @ {m['timestamp'][5:16]}"
            y = fr.y_of(m["high"])
            d.text((fr.left + 6, y - 17), label, fill=colour, font=f_bold)

    if not drawn:
        return None
    # Bottom-left: TradingView paints its own symbol/OHLC overlay across the top
    # of the plot, and a legend at fr.top lands right on top of it.
    legend_h = 18 + len(ZONE_COLOURS) * 16
    legend_y = fr.bottom - legend_h - 10
    d.rectangle(
        [fr.left + 2, legend_y - 4, fr.left + 190, legend_y + legend_h + 2],
        fill=(255, 255, 255), outline=(180, 180, 180),
    )
    d.text((fr.left + 6, legend_y), "SMC zone verification (edges dashed)",
           fill=(20, 20, 20), font=f_bold)
    for i, (kind, colour) in enumerate(ZONE_COLOURS.items()):
        d.text((fr.left + 6, legend_y + 18 + i * 16), f"— {kind}", fill=colour, font=f_small)

    out = SHOTS_DIR / f"{shot_stem}_SMC_ANNOTATED.png"
    img.save(out)
    return out


# ─────────────────────────────────────────────────────────────────────── main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--shot", action="append", help="limit to these shot stems")
    ap.add_argument("--no-render", action="store_true", help="mechanical checks only")
    ap.add_argument("--per-shot-samples", type=int, default=6,
                    help="zone instances sampled per feature per shot")
    args = ap.parse_args(argv)

    fp = get_prod_section("feature_pipeline")
    k = int(fp["swing_window"])
    max_window = int(fp["smc_max_window"])
    atr_period = int(fp["atr_period"])
    print(f"config: swing_window={k} smc_max_window={max_window} atr_period={atr_period}")

    df = load_bars(args.csv)
    print(f"corpus: {len(df)} bars from {args.csv}")
    rows = scan(df, k, max_window, atr_period)

    if not MONTH_JSON.exists():
        print(f"FATAL: {MONTH_JSON} absent — parity gate cannot run")
        return 2
    month = json.loads(MONTH_JSON.read_text(encoding="utf-8"))
    ok, problems = parity_gate(rows, month)
    print(f"parity gate vs pipeline output: {'PASS' if ok else 'FAIL'}")
    if not ok:
        for p in problems:
            print(f"  {p}")
        print("ABORTING: recomputed windows differ from production; zones would be "
              "evidence about this script, not about the pipeline.")
        return 2

    by_ts = {r["timestamp"]: r for r in rows}
    sidecars = [
        p for p in sorted(SHOTS_DIR.glob("*.json"))
        if not p.stem.endswith("_ANNOTATED") and "_PRE_" not in p.stem
        and (not args.shot or p.stem in args.shot)
    ]

    checks: list[Check] = []
    per_shot: dict[str, dict] = {}
    rendered: list[str] = []

    for path in sidecars:
        doc = json.loads(path.read_text(encoding="utf-8"))
        start = datetime.strptime(doc["shot"]["start"], "%Y-%m-%d %H:%M")
        end = datetime.strptime(doc["shot"]["end"], "%Y-%m-%d %H:%M")
        bars = doc.get("bars") or []
        if not bars:
            continue
        tv_lo = min(b["l"] for b in bars)
        tv_hi = max(b["h"] for b in bars)

        in_window = [
            r for r in rows
            if start <= datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S") <= end
        ]
        marks, seen = [], {}
        shot_checks: list[Check] = []

        for r in in_window:
            for feature, kind in ZONE_FEATURES.items():
                zone = r["zones"][kind]
                if zone is None:
                    continue
                key = (kind, zone.formed_at_index, zone.high, zone.low)
                if key in seen:
                    continue
                if len([m for m in marks if m["kind"] == kind]) >= args.per_shot_samples:
                    continue
                seen[key] = True

                shot_checks.append(check_causal(feature, r, zone))
                shot_checks.append(
                    check_within_tv_range(feature, r, zone, tv_lo, tv_hi, start, end)
                )
                if kind == "fvg":
                    shot_checks.append(check_fvg(r, zone))
                    shot_checks.append(check_fvg_unfilled(r, zone))
                else:
                    shot_checks.append(check_zone_is_a_real_candle_range(feature, r, zone))
                    shot_checks.append(note_mitigation_not_auditable(feature, r, zone))

                marks.append({
                    "kind": kind, "timestamp": r["timestamp"],
                    "high": zone.high, "low": zone.low,
                    "bullish": zone.bullish, "formed_at_index": zone.formed_at_index,
                })

        for r in in_window[:: max(1, len(in_window) // 5 or 1)][:5]:
            shot_checks.extend(check_pdh_pdl(r, df))

        checks.extend(shot_checks)
        failed = [c for c in shot_checks if not c.passed]
        per_shot[path.stem] = {
            "bars_in_window": len(in_window),
            "zone_instances_checked": len(marks),
            "checks": len(shot_checks),
            "failed": len(failed),
            "tv_price_range": [tv_lo, tv_hi],
        }
        print(f"  {path.stem}: {len(marks)} zones, {len(shot_checks)} checks, "
              f"{len(failed)} FAILED")

        if not args.no_render and marks:
            out = render(path.stem, doc, marks)
            if out:
                rendered.append(out.name)
                per_shot[path.stem]["annotated_png"] = out.name

    failed = [c for c in checks if not c.passed]
    # Skips are counted and named, never folded into the pass total silently —
    # a "passed" that was never actually evaluated is the D-1 failure class.
    skipped = [c for c in checks if c.passed and c.detail.startswith("SKIPPED-BY-")]
    skip_kinds: dict[str, int] = {}
    for c in skipped:
        skip_kinds[c.kind] = skip_kinds.get(c.kind, 0) + 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "kind": "smc_visual_verification",
        "scope": (
            "Report row 8 follow-up. MECHANICAL checks are verifiable and their "
            "failures are defects. The VISUAL claim is NOT self-certified here — "
            "the annotated PNGs are rendered for human adjudication."
        ),
        "config": {"swing_window": k, "smc_max_window": max_window,
                   "atr_period": atr_period},
        "corpus": {"csv": str(args.csv).replace("\\", "/"), "bars": len(df)},
        "parity_gate_vs_pipeline": "PASS",
        "mechanical": {
            "checks_run": len(checks),
            "evaluated": len(checks) - len(skipped),
            "passed": len(checks) - len(failed) - len(skipped),
            "failed": len(failed),
            "skipped_by_construction": len(skipped),
            "skipped_by_kind": skip_kinds,
            "skip_reasons": {
                "within_tv_price_range": (
                    "zone formed outside the captured frame (trailing smc_max_window "
                    "reaches back before the shot start), so its prices need not be on screen"
                ),
                "mitigation_audit_unavailable": (
                    "Zone exposes formed_at_index (origin) but not the confirming break "
                    "index, so mitigation state is not independently auditable without "
                    "duplicating _find_break_events — a contract gap in Zone's surface"
                ),
            },
            "failures": [c.as_dict() for c in failed[:50]],
        },
        "visual": {
            "status": "RENDERED_PENDING_HUMAN_ADJUDICATION",
            "annotated_pngs": rendered,
        },
        "per_shot": per_shot,
        "grants_no_authority": (
            "Descriptive only (CLAUDE.md 6.5). Does not wire any SMC feature into "
            "a decision path; F-076's UNUSED conclusion is unchanged."
        ),
    }
    out_path = OUT_DIR / "smc_visual_verification.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"\nMECHANICAL: {len(checks) - len(failed) - len(skipped)}/"
          f"{len(checks) - len(skipped)} evaluated checks passed "
          f"({len(skipped)} skipped by construction: {skip_kinds})")
    for c in failed[:15]:
        print(f"  FAIL [{c.kind}] {c.feature} @ {c.timestamp}: {c.detail}")
    print(f"VISUAL: {len(rendered)} annotated PNG(s) — pending human adjudication")
    print(f"wrote {out_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
