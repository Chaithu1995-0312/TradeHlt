#!/usr/bin/env python3
"""
blind_label_sample.py
======================
Read-only SAMPLER + RENDERER for the blind-labeling descriptive-fidelity test.

Pre-registration: docs/research/preregistration-blind-label-descriptive-fidelity.md
(read that first -- the sample design, the four questions, and the interpretation rule are
FROZEN there; this script implements the frozen design, it does not define it).

Runs the STANDARD production path -- FeaturePipeline.run() INCLUDING finalize() -- over the
full XAUUSD corpus, draws a seeded blinded sample (Arm A uniform / Arm B stratified / Arm C
repeats), and emits two artifacts:

  * results/blind_label/session_01.html   -- the labeling page. Contains ONLY raw OHLCV
    candlesticks per item. Zero feature values, zero timestamps, zero answer data.
  * results/blind_label/sample_manifest.json -- the answer key. Never referenced by the HTML.

tests/test_blind_label_harness.py enforces the blinding + determinism mechanically -- it does
not rely on this docstring being honoured.

Usage:
    PYTHONPATH=src python scripts/analysis/blind_label_sample.py --seed 20260801
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from features.feature_pipeline import FeaturePipeline, required_warmup_rows

CONTEXT_BARS = 48
MIN_SPACING_BARS = 60  # items must be this far apart so context windows don't overlap
N_ARM_A = 60
N_ARM_B_PER_STRATUM = 10  # x3 strata = 30
N_ARM_C = 10


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_frame(csv_path: Path) -> tuple[pd.DataFrame, str, str]:
    raw = pd.read_csv(csv_path)
    csv_sha = _sha256(csv_path)

    from config_layer.production_config import get_active_version, get_prod_section
    prod_version = get_active_version()
    fp_cfg = get_prod_section("feature_pipeline")

    pipe = FeaturePipeline(raw.copy(), cfg=fp_cfg)
    df, _vectors = pipe.run()
    df = df.copy().reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["ref_high"] = df["last_swing_high_price"].shift(1)
    df["ref_low"] = df["last_swing_low_price"].shift(1)
    return df, csv_sha, prod_version


def _strata_masks(df: pd.DataFrame) -> dict[str, np.ndarray]:
    candle_range = df["candle_range"]
    median_range = float(candle_range.median())
    top_decile = float(candle_range.quantile(0.9))

    nonzero_sweep = (df["liquidity_sweep"] != 0).to_numpy()

    bos = df["break_of_structure"]
    fresh_bos = ((bos != 0) & (bos != bos.shift(1))).to_numpy()

    # expansion-onset: this bar's range is top-decile AND each of the 3 prior bars was
    # below the population median range (a quiet run immediately preceding a big bar).
    below_median_prior = (candle_range < median_range)
    prior3_all_quiet = (
        below_median_prior.shift(1).fillna(False)
        & below_median_prior.shift(2).fillna(False)
        & below_median_prior.shift(3).fillna(False)
    )
    expansion_onset = ((candle_range > top_decile) & prior3_all_quiet).to_numpy()

    return {
        "nonzero_sweep": nonzero_sweep,
        "fresh_bos": fresh_bos,
        "expansion_onset": expansion_onset,
    }


def _greedy_spaced_sample(rng: np.random.Generator, pool: np.ndarray,
                           n: int, taken: list[int], min_spacing: int) -> list[int]:
    """Randomly order `pool`, accept indices at least `min_spacing` from every prior accept
    (both already-`taken` and accepted-this-call), stop at `n` or pool exhaustion."""
    order = rng.permutation(pool)
    accepted: list[int] = []
    all_taken = list(taken)
    for idx in order:
        idx = int(idx)
        if all(abs(idx - t) >= min_spacing for t in all_taken):
            accepted.append(idx)
            all_taken.append(idx)
            if len(accepted) >= n:
                break
    return accepted


def _make_item_id(rng: np.random.Generator) -> str:
    return "itm_" + "".join(f"{b:02x}" for b in rng.integers(0, 256, size=6, dtype=np.uint8))


def _ref_onscreen_flags(row: pd.Series, window: pd.DataFrame) -> dict:
    win_low = float(window["low"].min())
    win_high = float(window["high"].max())
    rh, rl = row.get("ref_high"), row.get("ref_low")
    rh_on = bool(pd.notna(rh) and win_low <= float(rh) <= win_high)
    rl_on = bool(pd.notna(rl) and win_low <= float(rl) <= win_high)
    bos = row["break_of_structure"]
    if bos == 1:
        primary_onscreen = rh_on
    elif bos == -1:
        primary_onscreen = rl_on
    else:
        primary_onscreen = None  # NoBreak -- no single relevant reference
    return {"ref_high_onscreen": rh_on, "ref_low_onscreen": rl_on,
            "primary_ref_onscreen": primary_onscreen}


def _build_items(df: pd.DataFrame, rng: np.random.Generator) -> list[dict]:
    n = len(df)
    eligible = np.arange(CONTEXT_BARS - 1, n)  # need a full window ending at each index

    strata = _strata_masks(df)

    taken: list[int] = []
    items: list[dict] = []

    # --- Arm A: uniform random ---------------------------------------------------------
    arm_a_idx = _greedy_spaced_sample(rng, eligible, N_ARM_A, taken, MIN_SPACING_BARS)
    taken.extend(arm_a_idx)
    arm_a_item_ids: list[str] = []
    for idx in arm_a_idx:
        item_id = _make_item_id(rng)
        arm_a_item_ids.append(item_id)
        items.append({"item_id": item_id, "arm": "A", "repeat_of": None, "strata": [],
                      "target_row_index": idx})

    # --- Arm B: stratified, ~10 per stratum, excluding indices already taken -----------
    for stratum_name, mask in strata.items():
        pool = eligible[mask[eligible]]
        pool = np.array([i for i in pool if i not in taken])
        picked = _greedy_spaced_sample(rng, pool, N_ARM_B_PER_STRATUM, taken, MIN_SPACING_BARS)
        taken.extend(picked)
        for idx in picked:
            item_id = _make_item_id(rng)
            items.append({"item_id": item_id, "arm": "B", "repeat_of": None,
                          "strata": [stratum_name], "target_row_index": idx})

    # --- Arm C: repeats of Arm-A items (same underlying bar, new item_id) --------------
    n_c = min(N_ARM_C, len(arm_a_item_ids))
    repeat_of_ids = rng.choice(arm_a_item_ids, size=n_c, replace=False)
    by_id = {it["item_id"]: it for it in items}
    for orig_id in repeat_of_ids:
        orig = by_id[orig_id]
        item_id = _make_item_id(rng)
        items.append({"item_id": item_id, "arm": "C", "repeat_of": orig_id, "strata": [],
                      "target_row_index": orig["target_row_index"]})

    # --- attach OHLCV window + answers + diagnostics ------------------------------------
    for it in items:
        idx = it["target_row_index"]
        window = df.iloc[idx - CONTEXT_BARS + 1: idx + 1]
        row = df.iloc[idx]
        it["target_timestamp"] = row["timestamp"].isoformat()
        it["context_start_index"] = int(idx - CONTEXT_BARS + 1)
        it["context_end_index"] = int(idx)
        it["ohlcv"] = [
            {"o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
             "c": float(r["close"]), "v": float(r["volume"])}
            for _, r in window.iterrows()
        ]
        it["answers"] = {
            "trend_bias": _native(row["trend_bias"]),
            "volatility_regime": _native(row["volatility_regime"]),
            "liquidity_sweep": _native(row["liquidity_sweep"]),
            "break_of_structure": _native(row["break_of_structure"]),
        }
        it.update(_ref_onscreen_flags(row, window))

    # --- shuffle display order -----------------------------------------------------------
    perm = rng.permutation(len(items))
    for display_pos, i in enumerate(perm, start=1):
        items[i]["display_position"] = int(display_pos)
    items.sort(key=lambda x: x["display_position"])

    return items


def _native(v):
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


# ── SVG rendering (stdlib only -- no matplotlib/mplfinance in this environment) ─────────────

_CHART_W = 720
_CHART_H = 220
_VOL_H = 50
_MARGIN = 4


def _render_candles_svg(ohlcv: list[dict], item_id: str) -> str:
    n = len(ohlcv)
    highs = [b["h"] for b in ohlcv]
    lows = [b["l"] for b in ohlcv]
    vols = [b["v"] for b in ohlcv]
    p_min, p_max = min(lows), max(highs)
    p_span = (p_max - p_min) or 1.0
    v_max = max(vols) or 1.0

    slot_w = (_CHART_W - 2 * _MARGIN) / n
    body_w = max(1.5, slot_w * 0.6)

    def y(price: float) -> float:
        return _MARGIN + (p_max - price) / p_span * (_CHART_H - 2 * _MARGIN)

    parts = [
        f'<svg class="candles" data-item="{html.escape(item_id)}" '
        f'viewBox="0 0 {_CHART_W} {_CHART_H + _VOL_H}" xmlns="http://www.w3.org/2000/svg">'
    ]
    for i, b in enumerate(ohlcv):
        cx = _MARGIN + slot_w * i + slot_w / 2
        is_last = (i == n - 1)
        up = b["c"] >= b["o"]
        color = "var(--up)" if up else "var(--down)"
        y_wick_top, y_wick_bot = y(b["h"]), y(b["l"])
        y_body_top, y_body_bot = y(max(b["o"], b["c"])), y(min(b["o"], b["c"]))
        body_h = max(1.0, y_body_bot - y_body_top)
        stroke = ' stroke="var(--mark)" stroke-width="2"' if is_last else ""
        parts.append(
            f'<line x1="{cx:.2f}" y1="{y_wick_top:.2f}" x2="{cx:.2f}" y2="{y_wick_bot:.2f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{cx - body_w/2:.2f}" y="{y_body_top:.2f}" width="{body_w:.2f}" '
            f'height="{body_h:.2f}" fill="{color}"{stroke}/>'
        )
        vh = (b["v"] / v_max) * (_VOL_H - 4)
        vy = _CHART_H + _VOL_H - vh
        parts.append(
            f'<rect x="{cx - body_w/2:.2f}" y="{vy:.2f}" width="{body_w:.2f}" '
            f'height="{vh:.2f}" fill="{color}" opacity="0.5"/>'
        )
    if n:
        cx_last = _MARGIN + slot_w * (n - 1) + slot_w / 2
        parts.append(
            f'<line x1="{cx_last:.2f}" y1="0" x2="{cx_last:.2f}" y2="{_CHART_H}" '
            f'stroke="var(--mark)" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


_QUESTIONS = [
    ("q1_trend", "Q1. At the marked bar (dashed line, rightmost candle), "
                 "is the market trending up, down, or neither?",
     [("up", "Up"), ("down", "Down"), ("neither", "Neither")]),
    ("q2_vol", "Q2. For recent conditions, is the marked bar's volatility "
               "Low, Normal, or High?",
     [("low", "Low"), ("normal", "Normal"), ("high", "High")]),
    ("q3_sweep", "Q3. Did the marked bar spike through a recent high or low "
                 "and then close back inside?",
     [("above", "Above (swept a high)"), ("below", "Below (swept a low)"),
      ("neither", "Neither")]),
    ("q4_bos", "Q4. Did the marked bar break market structure?",
     [("up", "Broke up"), ("down", "Broke down"), ("none", "No break")]),
]


def _render_html(items: list[dict], seed: int) -> str:
    body = []
    for it in items:
        svg = _render_candles_svg(it["ohlcv"], it["item_id"])
        q_blocks = []
        for qkey, qtext, options in _QUESTIONS:
            opts_html = "".join(
                f'<label><input type="radio" name="{qkey}__{it["item_id"]}" '
                f'value="{val}"> {label}</label>'
                for val, label in options
            )
            q_blocks.append(f'<div class="qblock"><p>{html.escape(qtext)}</p>{opts_html}</div>')
        body.append(
            f'<section class="item" data-item="{it["item_id"]}" '
            f'data-pos="{it["display_position"]}">'
            f'<h3>Chart {it["display_position"]} of {len(items)}</h3>'
            f'{svg}{"".join(q_blocks)}</section>'
        )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Blind Label Session</title>
<style>
:root {{ --up:#26a269; --down:#c01c28; --mark:#f5a623; --bg:#111; --fg:#eee; --card:#1a1a1a; }}
body {{ background:var(--bg); color:var(--fg); font-family:system-ui,sans-serif; max-width:800px;
       margin:0 auto; padding:16px; }}
.item {{ background:var(--card); border-radius:8px; padding:12px; margin-bottom:20px; }}
.candles {{ width:100%; height:auto; background:#000; border-radius:4px; }}
.qblock {{ margin-top:10px; }}
.qblock label {{ display:inline-block; margin-right:16px; cursor:pointer; }}
#progress {{ position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:10;
            border-bottom:1px solid #333; }}
button {{ background:var(--mark); color:#111; border:none; padding:8px 16px; border-radius:4px;
         font-weight:bold; cursor:pointer; }}
</style></head><body>
<div id="progress">Answered: <span id="count">0</span> / {len(items)}
&nbsp; <button id="dl">Download CSV</button></div>
{"".join(body)}
<script>
const SEED = {seed};
const STORE_KEY = "blind_label_answers_v1";
function loadState() {{ try {{ return JSON.parse(localStorage.getItem(STORE_KEY)) || {{}}; }}
                        catch(e) {{ return {{}}; }} }}
function saveState(s) {{ localStorage.setItem(STORE_KEY, JSON.stringify(s)); }}
let state = loadState();

function restore() {{
  document.querySelectorAll('input[type=radio]').forEach(inp => {{
    const [q, itemId] = inp.name.split('__');
    if (state[itemId] && state[itemId][q] === inp.value) inp.checked = true;
  }});
  updateCount();
}}

function updateCount() {{
  const total = document.querySelectorAll('.item').length;
  let answered = 0;
  document.querySelectorAll('.item').forEach(sec => {{
    const id = sec.dataset.item;
    const s = state[id];
    if (s && s.q1_trend && s.q2_vol && s.q3_sweep && s.q4_bos) answered++;
  }});
  document.getElementById('count').textContent = answered;
}}

document.addEventListener('change', (e) => {{
  if (e.target.type !== 'radio') return;
  const [q, itemId] = e.target.name.split('__');
  state[itemId] = state[itemId] || {{}};
  state[itemId][q] = e.target.value;
  saveState(state);
  updateCount();
}});

document.getElementById('dl').addEventListener('click', () => {{
  const rows = [['item_id','display_position','q1_trend','q2_vol','q3_sweep','q4_bos']];
  document.querySelectorAll('.item').forEach(sec => {{
    const id = sec.dataset.item, pos = sec.dataset.pos;
    const s = state[id] || {{}};
    rows.push([id, pos, s.q1_trend||'', s.q2_vol||'', s.q3_sweep||'', s.q4_bos||'']);
  }});
  const csv = rows.map(r => r.join(',')).join('\\n');
  const blob = new Blob([csv], {{type:'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'blind_label_answers.csv';
  a.click();
}});

restore();
</script>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default="data/mt5/XAUUSD_M15.csv")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--output-dir", default="results/blind_label")
    args = ap.parse_args()

    csv_path = Path(args.csv) if Path(args.csv).is_absolute() else ROOT / args.csv
    out_dir = Path(args.output_dir) if Path(args.output_dir).is_absolute() else ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    df, csv_sha, prod_version = _load_frame(csv_path)
    warmup = required_warmup_rows()

    rng = np.random.default_rng(args.seed)
    items = _build_items(df, rng)

    manifest = {
        "generator": "scripts/analysis/blind_label_sample.py",
        "preregistration": "docs/research/preregistration-blind-label-descriptive-fidelity.md",
        "seed": args.seed,
        "source_csv": str(csv_path), "source_csv_sha256": csv_sha,
        "prod_config_version": prod_version,
        "required_warmup_rows": int(warmup),
        "context_bars": CONTEXT_BARS,
        "min_spacing_bars": MIN_SPACING_BARS,
        "n_items": len(items),
        "arm_counts": {a: sum(1 for it in items if it["arm"] == a) for a in ("A", "B", "C")},
        "items": [{k: v for k, v in it.items() if k != "ohlcv"} | {"ohlcv_included": True}
                  for it in items],
    }
    manifest_path = out_dir / "sample_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    html_out = _render_html(items, args.seed)
    html_path = out_dir / "session_01.html"
    html_path.write_text(html_out, encoding="utf-8")

    print(f"Wrote {len(items)} items ({manifest['arm_counts']}) to {html_path}")
    print(f"Answer key (do not open before labeling): {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
