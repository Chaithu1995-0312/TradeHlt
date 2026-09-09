#!/usr/bin/env python3
"""
visual_state_sample.py
======================
Read-only SAMPLER + RENDERER for the visual CRT state-fidelity test.

Pre-registration: docs/research/preregistration-visual-crt-state-fidelity.md
(read that first — the four questions, two arms, sample, and interpretation
rule are FROZEN there; this script implements the frozen design).

Emits, under --out-dir:

  * arm1/<item_id>.png + arm1/label.html   — bare 48-bar crops
  * arm2/<item_id>.png + arm2/label.html   — same crops + unlabelled h/l lines
  * manifest.json                          — the answer key. Never referenced
    by either HTML or by the labeler brief.

Joins engine events to the survey trace on timestamp (never candle_index).
Fails closed if the two artifacts disagree on state at any shared timestamp.

The real item set is refused until the prereg records a 64-hex SHA-256 of
the sealed user-prediction file (--allow-unsealed is test-only).

Usage:
    python scripts/research/visual_state_sample.py --seed 20260818 \\
        --out-dir results/visual_crt_state_fidelity
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "tv_forensic"))

from scripts.research.visual_state_questions import (  # noqa: E402
    BANNED_SURFACE_TOKENS,
    CONTEXT_BARS,
    DEFAULT_SEED,
    MIN_PX_PER_CANDLE,
    QUESTIONS,
    engine_to_visual,
)

PREREG = ROOT / "docs" / "research" / "preregistration-visual-crt-state-fidelity.md"
SEALED = ROOT / "docs" / "research" / "visual-crt-user-predictions.SEALED.md"
DEFAULT_EVENTS = (
    ROOT / "results" / "htfcrt_1month_parent_wired"
    / "run_20260816_011239_XAUUSD" / "XAUUSD_events.jsonl"
)
DEFAULT_TRACE = ROOT / "results" / "crt_survey_trace" / "20260815T062829Z" / "trace.jsonl"
DEFAULT_CSV = ROOT / "data" / "XAUUSD_M15.csv"
DEFAULT_SHOTS = ROOT / "tools" / "tv_forensic" / "shots"
SHA_SLOT_RE = re.compile(
    r"SHA-256 at seal time:\s*`?(?P<digest>[0-9a-fA-F]{64}|<[^`\n]+>)`?"
)
NEUTRAL_LINE = (168, 168, 168, 220)
TICK_FILL = (200, 200, 200, 255)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_ts(ts: object) -> str:
    if ts is None:
        raise ValueError("timestamp is required (join is never by candle_index)")
    s = str(ts).replace("T", " ").replace("Z", "")
    if "." in s:
        s = s.split(".", 1)[0]
    return s[:19]


def recorded_seal_digest(prereg_path: Path | None = None) -> str | None:
    text = (prereg_path or PREREG).read_text(encoding="utf-8")
    m = SHA_SLOT_RE.search(text)
    if not m:
        return None
    val = m.group("digest")
    if val.startswith("<"):
        return None
    return val.lower()


def assert_user_predictions_sealed(
    prereg_path: Path | None = None,
    sealed_path: Path | None = None,
) -> str:
    prereg_path = prereg_path or PREREG
    sealed_path = sealed_path or SEALED
    digest = recorded_seal_digest(prereg_path)
    if digest is None:
        raise SystemExit(
            "prereg SHA-256 slot is empty — will not emit the real item set "
            "until the user seals docs/research/visual-crt-user-predictions.SEALED.md "
            "and the digest is recorded. Tests may pass --allow-unsealed."
        )
    if not sealed_path.is_file():
        raise SystemExit(f"sealed prediction file missing: {sealed_path}")
    actual = _sha256_file(sealed_path)
    if actual != digest:
        raise SystemExit(
            f"sealed file SHA-256 {actual} != recorded {digest} — "
            "predictions moved after seal, or the recorded digest is wrong"
        )
    return digest


def load_events(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_ts"] = _norm_ts(rec["timestamp"])
            out.append(rec)
    return out


def load_trace_by_ts(path: Path) -> dict[str, dict]:
    by_ts: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_ts[_norm_ts(rec["timestamp"])] = rec
    return by_ts


def verify_config_consistency(events: list[dict], trace: dict[str, dict]) -> dict:
    """Fail closed if events and trace disagree on state at any shared timestamp.

    The known 85-vs-84 sweep delta is a warmup-only SWEEP_DETECTED in the
    trace (no matching STATE_TRANSITION). That is recorded, not a mismatch.
    """
    disagreements: list[dict] = []
    shared = 0
    warmup_only_sweeps = 0
    for ev in events:
        if ev.get("event") != "STATE_TRANSITION":
            continue
        tr = trace.get(ev["_ts"])
        if tr is None:
            disagreements.append({
                "timestamp": ev["_ts"],
                "reason": "transition timestamp missing from trace",
                "event_state": ev.get("state_to"),
            })
            continue
        shared += 1
        sa = (tr.get("crt") or {}).get("state_after")
        if sa != ev.get("state_to"):
            disagreements.append({
                "timestamp": ev["_ts"],
                "event_state": ev.get("state_to"),
                "trace_state": sa,
            })
    trans_ts = {ev["_ts"] for ev in events if ev.get("event") == "STATE_TRANSITION"}
    for ts, tr in trace.items():
        crt = tr.get("crt") or {}
        if crt.get("action") == "SWEEP_DETECTED" and ts not in trans_ts:
            warmup_only_sweeps += 1
            if crt.get("warmup_complete") not in (False, None) and (tr.get("bar_index") or 0) >= 78:
                disagreements.append({
                    "timestamp": ts,
                    "reason": "trace SWEEP_DETECTED outside warmup with no matching event",
                    "bar_index": tr.get("bar_index"),
                })
    if disagreements:
        raise SystemExit(
            "config-consistency FAIL: events and trace disagree "
            f"({len(disagreements)}). Re-run "
            "scripts/analysis/xauusd_excel_feature_state_trace.py "
            "--csv data/XAUUSD_M15.csv against the active config; "
            f"do not reconcile by hand. sample={disagreements[:5]}"
        )
    return {
        "shared_transition_timestamps": shared,
        "warmup_only_trace_sweeps": warmup_only_sweeps,
        "disagreements": 0,
    }


def load_csv_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for i, rec in enumerate(csv.DictReader(fh)):
            rec = {k.lower(): v for k, v in rec.items()}
            rec["_ts"] = _norm_ts(rec.get("timestamp") or rec.get("time"))
            rec["_i"] = i
            rec["_range"] = float(rec["high"]) - float(rec["low"])
            rows.append(rec)
    return rows


def _range_percentile(values: list[float], x: float) -> float:
    if not values:
        return 0.0
    below = sum(1 for v in values if v <= x)
    return below / len(values)


def _make_item_id(rng: random.Random) -> str:
    return "item_" + "".join(f"{rng.randint(0, 255):02x}" for _ in range(3))


def select_items(
    events: list[dict],
    trace: dict[str, dict],
    rows: list[dict],
    rng: random.Random,
) -> tuple[list[dict], dict]:
    by_ts = {r["_ts"]: r for r in rows}
    ranges = [r["_range"] for r in rows]
    transitions = [ev for ev in events if ev.get("event") == "STATE_TRANSITION"]
    positive_ts = {ev["_ts"] for ev in transitions}

    positives: list[dict] = []
    skipped_no_direction = 0
    skipped_no_context = 0
    for ev in transitions:
        row = by_ts.get(ev["_ts"])
        if row is None:
            raise SystemExit(
                f"ground-truth join FAIL: transition {ev['_ts']} has no CSV row "
                "(timestamp join, never candle_index)"
            )
        if row["_i"] < CONTEXT_BARS - 1:
            skipped_no_context += 1
            continue
        tr = trace.get(ev["_ts"]) or {}
        direction = ev.get("direction") or (tr.get("crt") or {}).get("direction")
        if ev.get("state_to") in ("SWEEP", "DISPLACEMENT") and (
            not direction or str(direction).upper() in ("NONE", "NULL")
        ):
            skipped_no_direction += 1
            continue
        session = (tr.get("features") or {}).get("session")
        rng_pct = _range_percentile(ranges, row["_range"])
        answers = engine_to_visual(ev.get("state_to"), direction)
        ar = (tr.get("crt_inputs") or {}).get("active_range") or {}
        positives.append({
            "role": "positive",
            "timestamp": ev["_ts"],
            "csv_index": row["_i"],
            "engine_state": ev.get("state_to"),
            "engine_from": ev.get("state_from"),
            "direction": None if direction is None else str(direction).upper(),
            "session": session,
            "range_percentile": rng_pct,
            "candle_range": row["_range"],
            "h_ref": ar.get("h_ref"),
            "l_ref": ar.get("l_ref"),
            "answers": answers,
        })

    # Controls: action == NONE, matched on session + range percentile.
    candidates: list[dict] = []
    for ts, tr in trace.items():
        crt = tr.get("crt") or {}
        if crt.get("action") != "NONE":
            continue
        if ts in positive_ts:
            continue
        row = by_ts.get(ts)
        if row is None or row["_i"] < CONTEXT_BARS - 1:
            continue
        session = (tr.get("features") or {}).get("session")
        rng_pct = _range_percentile(ranges, row["_range"])
        ar = (tr.get("crt_inputs") or {}).get("active_range") or {}
        candidates.append({
            "role": "control",
            "timestamp": ts,
            "csv_index": row["_i"],
            "engine_state": crt.get("state_after") or "RANGE",
            "engine_from": crt.get("state_before"),
            "direction": None,
            "session": session,
            "range_percentile": rng_pct,
            "candle_range": row["_range"],
            "h_ref": ar.get("h_ref"),
            "l_ref": ar.get("l_ref"),
            "answers": engine_to_visual(None, None),
        })

    controls: list[dict] = []
    unused = list(candidates)
    rng.shuffle(unused)
    for pos in positives:
        best_i = None
        best_d = 1e9
        for i, c in enumerate(unused):
            if c["session"] != pos["session"]:
                continue
            d = abs(c["range_percentile"] - pos["range_percentile"])
            if d < best_d:
                best_d = d
                best_i = i
        if best_i is None:
            continue
        pick = unused.pop(best_i)
        pick["matched_to"] = pos["timestamp"]
        pick["match_range_delta"] = best_d
        controls.append(pick)

    items = positives + controls
    for it in items:
        it["item_id"] = _make_item_id(rng)
        it["context_start_index"] = int(it["csv_index"] - CONTEXT_BARS + 1)
        it["context_end_index"] = int(it["csv_index"])

    # overlaps_prior_item: another selected item's 48-bar window overlaps this one.
    windows = [(it["context_start_index"], it["context_end_index"], it["item_id"]) for it in items]
    for it in items:
        a0, a1 = it["context_start_index"], it["context_end_index"]
        it["overlaps_prior_item"] = any(
            oid != it["item_id"] and not (a1 < b0 or b1 < a0)
            for b0, b1, oid in windows
        )

    rng.shuffle(items)
    for i, it in enumerate(items, start=1):
        it["display_position"] = i

    pos_pct = [it["range_percentile"] for it in positives]
    ctl_pct = [it["range_percentile"] for it in controls]
    balance = {
        "n_positives": len(positives),
        "n_controls": len(controls),
        "n_control_candidates": len(candidates),
        "skipped_no_context": skipped_no_context,
        "skipped_no_direction": skipped_no_direction,
        "positive_range_pct_mean": (sum(pos_pct) / len(pos_pct)) if pos_pct else None,
        "control_range_pct_mean": (sum(ctl_pct) / len(ctl_pct)) if ctl_pct else None,
        "positive_sessions": _count_key(positives, "session"),
        "control_sessions": _count_key(controls, "session"),
    }
    return items, balance


def _count_key(items: list[dict], key: str) -> dict:
    out: dict[str, int] = {}
    for it in items:
        k = str(it.get(key))
        out[k] = out.get(k, 0) + 1
    return out


def load_sidecars(shots_dir: Path) -> list[dict]:
    sidecars: list[dict] = []
    for path in sorted(shots_dir.glob("*_m15_legible_*.json")):
        if "ANNOTATED" in path.name or "PRE_" in path.name:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("shot", {}).get("interval") not in ("15", 15, "m15"):
            continue
        png = shots_dir / doc.get("saved", path.with_suffix(".png").name)
        doc["_sidecar_path"] = str(path)
        doc["_png_path"] = str(png)
        sidecars.append(doc)
    if not sidecars:
        # Tests / dry runs may drop synthetic sidecars with any name.
        for path in sorted(shots_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            if "bars" not in doc or "plot" not in doc:
                continue
            png = shots_dir / doc.get("saved", path.with_suffix(".png").name)
            doc["_sidecar_path"] = str(path)
            doc["_png_path"] = str(png)
            sidecars.append(doc)
    return sidecars


def _bar_epoch_to_broker(bar_t: int, offset_hours: int) -> str:
    utc = datetime.fromtimestamp(int(bar_t), tz=timezone.utc)
    broker = utc + timedelta(hours=int(offset_hours))
    return broker.strftime("%Y-%m-%d %H:%M:%S")


def _sidecar_ts_index(doc: dict) -> dict[str, dict]:
    offset = int(((doc.get("clock") or {}).get("offset_hours")) or 0)
    out: dict[str, dict] = {}
    for bar in doc.get("bars") or []:
        out[_bar_epoch_to_broker(bar["t"], offset)] = bar
    return out


def assign_shot(item: dict, sidecars: list[dict]) -> dict:
    """Pick a sidecar that contains the full 48-bar context. Fail closed if none."""
    target_ts = item["timestamp"]
    candidates: list[tuple[float, dict, dict]] = []
    for doc in sidecars:
        idx = _sidecar_ts_index(doc)
        if target_ts not in idx:
            continue
        bars = doc["bars"]
        # Require 47 bars to the left of the target in sidecar order.
        pos = next(i for i, b in enumerate(bars) if _bar_epoch_to_broker(
            b["t"], int((doc.get("clock") or {}).get("offset_hours") or 0)
        ) == target_ts)
        if pos < CONTEXT_BARS - 1:
            continue
        window = bars[pos - CONTEXT_BARS + 1: pos + 1]
        if len(window) != CONTEXT_BARS:
            continue
        xs = [b["x"] for b in window]
        if any(xs[i] >= xs[i + 1] for i in range(len(xs) - 1)):
            continue
        px = (xs[-1] - xs[0]) / (CONTEXT_BARS - 1)
        if px < MIN_PX_PER_CANDLE:
            continue
        # Prefer the shot where the target is most centered.
        center = (len(bars) - 1) / 2.0
        candidates.append((abs(pos - center), doc, {"pos": pos, "window": window, "px": px}))
    if not candidates:
        raise SystemExit(
            f"no legible sidecar contains a full {CONTEXT_BARS}-bar context "
            f"for {target_ts} at >= {MIN_PX_PER_CANDLE} px/candle"
        )
    candidates.sort(key=lambda t: t[0])
    _, doc, meta = candidates[0]
    item["shot_name"] = (doc.get("shot") or {}).get("name")
    item["px_per_candle"] = float(meta["px"])
    item["_render"] = {"doc": doc, **meta}
    return item


def _try_import_pil():
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Pillow is required to render item crops. "
            "Install it or pass --skip-render for a manifest-only run."
        ) from exc
    return Image, ImageDraw


def render_item(item: dict, out_arm1: Path, out_arm2: Path) -> None:
    Image, ImageDraw = _try_import_pil()
    sys.path.insert(0, str(ROOT / "tools" / "tv_forensic"))
    import annotate as an  # local tool; Frame.y_of is the only mapping we use

    meta = item["_render"]
    doc = meta["doc"]
    window = meta["window"]
    png_path = Path(doc["_png_path"])
    if not png_path.is_file():
        raise SystemExit(f"shot PNG missing: {png_path}")
    img = Image.open(png_path).convert("RGBA")
    xs = [b["x"] for b in window]
    spacing = (xs[-1] - xs[0]) / (CONTEXT_BARS - 1)
    if spacing < MIN_PX_PER_CANDLE:
        raise SystemExit(
            f"legibility FAIL: {item['item_id']} is {spacing:.3f} px/candle "
            f"(floor {MIN_PX_PER_CANDLE})"
        )
    rect = doc["plot"]["rect"]
    pad = spacing * 0.6
    left = max(0, int(xs[0] - pad))
    right = min(img.width, int(xs[-1] + pad))
    top = max(0, int(rect["y"]) - 4)
    # Extra strip below the plot so the tick sits outside the candles.
    tick_band = 18
    bottom = min(img.height, int(rect["y"] + rect["h"] + tick_band))
    crop = img.crop((left, top, right, bottom))

    def _stamp_tick(target: "Image.Image") -> None:
        d = ImageDraw.Draw(target)
        tx = xs[-1] - left
        by = (rect["y"] + rect["h"]) - top + 2
        d.polygon([(tx - 5, by + 10), (tx + 5, by + 10), (tx, by + 2)], fill=TICK_FILL)

    arm1 = crop.copy()
    _stamp_tick(arm1)
    arm1_path = out_arm1 / f"{item['item_id']}.png"
    arm1.save(arm1_path)

    arm2 = crop.copy()
    fr = an.Frame(doc)
    d2 = ImageDraw.Draw(arm2)
    for price in (item.get("h_ref"), item.get("l_ref")):
        if price is None:
            continue
        try:
            y = fr.y_of(float(price)) - top
        except (TypeError, ValueError):
            continue
        if 0 <= y < arm2.height:
            d2.line([(0, y), (arm2.width, y)], fill=NEUTRAL_LINE, width=1)
    _stamp_tick(arm2)
    arm2_path = out_arm2 / f"{item['item_id']}.png"
    arm2.save(arm2_path)
    item["files"] = {
        "arm1": str(arm1_path.as_posix()),
        "arm2": str(arm2_path.as_posix()),
    }
    item.pop("_render", None)


def _render_html(items: list[dict], arm: str, image_rel: str) -> str:
    body = []
    for it in items:
        q_blocks = []
        for q in QUESTIONS:
            opts = "".join(
                f'<label><input type="radio" name="{q["id"]}__{it["item_id"]}" '
                f'value="{val}"> {label}</label>'
                for val, label in q["options"]
            )
            q_blocks.append(
                f'<div class="qblock"><p>{html.escape(q["text"])}</p>{opts}'
                f'<p>Confidence: '
                f'<label><input type="radio" name="{q["id"]}conf__{it["item_id"]}" value="HIGH"> HIGH</label>'
                f'<label><input type="radio" name="{q["id"]}conf__{it["item_id"]}" value="MEDIUM"> MEDIUM</label>'
                f'<label><input type="radio" name="{q["id"]}conf__{it["item_id"]}" value="LOW"> LOW</label>'
                f'</p></div>'
            )
        body.append(
            f'<section class="item" data-item="{it["item_id"]}" '
            f'data-pos="{it["display_position"]}">'
            f'<h3>Chart {it["display_position"]} of {len(items)}</h3>'
            f'<img src="{html.escape(it["item_id"])}.png" alt="chart">'
            f'{"".join(q_blocks)}'
            f'<label>Visible evidence<br>'
            f'<textarea name="evidence__{it["item_id"]}" rows="3"></textarea></label>'
            f'</section>'
        )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Marked-bar labeling</title>
<style>
body {{ background:#111; color:#eee; font-family:system-ui,sans-serif; max-width:900px;
       margin:0 auto; padding:16px; }}
.item {{ background:#1a1a1a; border-radius:8px; padding:12px; margin-bottom:20px; }}
img {{ width:100%; height:auto; background:#000; }}
.qblock {{ margin-top:10px; }}
.qblock label {{ display:inline-block; margin-right:16px; cursor:pointer; }}
textarea {{ width:100%; background:#000; color:#eee; border:1px solid #333; }}
#progress {{ position:sticky; top:0; background:#111; padding:8px 0; z-index:10; }}
button {{ background:#f5a623; color:#111; border:none; padding:8px 16px; border-radius:4px;
         font-weight:bold; cursor:pointer; }}
</style></head><body>
<div id="progress">Answered: <span id="count">0</span> / {len(items)}
&nbsp; <button id="dl">Download JSONL</button></div>
{"".join(body)}
<script>
const STORE_KEY = "visual_state_{arm}_v1";
function loadState() {{ try {{ return JSON.parse(localStorage.getItem(STORE_KEY)) || {{}}; }}
                        catch(e) {{ return {{}}; }} }}
function saveState(s) {{ localStorage.setItem(STORE_KEY, JSON.stringify(s)); }}
let state = loadState();
function restore() {{
  document.querySelectorAll('input[type=radio]').forEach(inp => {{
    const [q, itemId] = inp.name.split('__');
    if (state[itemId] && state[itemId][q] === inp.value) inp.checked = true;
  }});
  document.querySelectorAll('textarea').forEach(t => {{
    const itemId = t.name.split('__')[1];
    if (state[itemId] && state[itemId].evidence) t.value = state[itemId].evidence;
  }});
  updateCount();
}}
function updateCount() {{
  let answered = 0;
  document.querySelectorAll('.item').forEach(sec => {{
    const id = sec.getAttribute('data-item');
    if (state[id] && state[id].v1) answered += 1;
  }});
  document.getElementById('count').textContent = answered;
}}
document.addEventListener('change', ev => {{
  const t = ev.target;
  if (!t.name || !t.name.includes('__')) return;
  const [q, itemId] = t.name.split('__');
  state[itemId] = state[itemId] || {{item_id: itemId}};
  if (t.name.startsWith('evidence')) state[itemId].evidence = t.value;
  else state[itemId][q] = t.value;
  saveState(state); updateCount();
}});
document.addEventListener('input', ev => {{
  const t = ev.target;
  if (t.tagName === 'TEXTAREA' && t.name && t.name.includes('__')) {{
    const itemId = t.name.split('__')[1];
    state[itemId] = state[itemId] || {{item_id: itemId}};
    state[itemId].evidence = t.value;
    saveState(state);
  }}
}});
document.getElementById('dl').onclick = () => {{
  const lines = Object.values(state).map(o => JSON.stringify(o));
  const blob = new Blob([lines.join('\\n')], {{type: 'application/jsonl'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '{arm}_labels.jsonl';
  a.click();
}};
restore();
</script></body></html>
"""


def assert_surface_blind(text: str, items: list[dict]) -> None:
    """Mechanical blinding: no timestamp, no engine field, no CRT noun."""
    low = text.lower()
    for tok in BANNED_SURFACE_TOKENS:
        if tok in low:
            raise AssertionError(f"labeling surface leaks banned token {tok!r}")
    for it in items:
        if it["timestamp"] in text:
            raise AssertionError(f"labeling surface leaks timestamp {it['timestamp']}")
        if it.get("engine_state") and str(it["engine_state"]).lower() in low:
            # engine_state is a CRT noun already banned; keep the explicit check
            raise AssertionError("labeling surface leaks engine_state")


def build_public_item(it: dict) -> dict:
    """Manifest record: answer key. Never copied into a labeling surface."""
    return {
        "item_id": it["item_id"],
        "display_position": it["display_position"],
        "role": it["role"],
        "timestamp": it["timestamp"],
        "csv_index": it["csv_index"],
        "context_start_index": it["context_start_index"],
        "context_end_index": it["context_end_index"],
        "engine_state": it["engine_state"],
        "engine_from": it.get("engine_from"),
        "direction": it.get("direction"),
        "session": it.get("session"),
        "range_percentile": it.get("range_percentile"),
        "candle_range": it.get("candle_range"),
        "h_ref": it.get("h_ref"),
        "l_ref": it.get("l_ref"),
        "answers": it["answers"],
        "overlaps_prior_item": it["overlaps_prior_item"],
        "shot_name": it.get("shot_name"),
        "px_per_candle": it.get("px_per_candle"),
        "matched_to": it.get("matched_to"),
        "files": it.get("files"),
    }


def run(args: argparse.Namespace) -> Path:
    if not args.allow_unsealed:
        assert_user_predictions_sealed(PREREG, SEALED)
    rng = random.Random(int(args.seed))
    events = load_events(Path(args.events))
    trace = load_trace_by_ts(Path(args.trace))
    consistency = verify_config_consistency(events, trace)
    rows = load_csv_rows(Path(args.csv))
    items, balance = select_items(events, trace, rows, rng)

    out = Path(args.out_dir)
    arm1 = out / "arm1"
    arm2 = out / "arm2"
    arm1.mkdir(parents=True, exist_ok=True)
    arm2.mkdir(parents=True, exist_ok=True)

    sidecars: list[dict] = []
    if not args.skip_render:
        sidecars = load_sidecars(Path(args.shots_dir))
        if not sidecars:
            raise SystemExit(f"no sidecars in {args.shots_dir}")
        for it in items:
            assign_shot(it, sidecars)
            render_item(it, arm1, arm2)
    else:
        for it in items:
            it["files"] = {
                "arm1": f"arm1/{it['item_id']}.png",
                "arm2": f"arm2/{it['item_id']}.png",
            }

    public = [build_public_item(it) for it in items]
    html1 = _render_html(items, "arm1", "arm1")
    html2 = _render_html(items, "arm2", "arm2")
    assert_surface_blind(html1, items)
    assert_surface_blind(html2, items)
    (arm1 / "label.html").write_text(html1, encoding="utf-8")
    (arm2 / "label.html").write_text(html2, encoding="utf-8")

    # Copy the brief next to each arm so a labeler does not need the repo tree.
    brief = (ROOT / "docs" / "research" / "visual-crt-labeler-brief.md").read_text(encoding="utf-8")
    assert_surface_blind(brief, items)
    (arm1 / "brief.md").write_text(brief, encoding="utf-8")
    (arm2 / "brief.md").write_text(brief, encoding="utf-8")

    manifest = {
        "seed": int(args.seed),
        "context_bars": CONTEXT_BARS,
        "min_px_per_candle": MIN_PX_PER_CANDLE,
        "events_path": str(Path(args.events)),
        "trace_path": str(Path(args.trace)),
        "csv_path": str(Path(args.csv)),
        "events_sha256": _sha256_file(Path(args.events)),
        "trace_sha256": _sha256_file(Path(args.trace)),
        "csv_sha256": _sha256_file(Path(args.csv)),
        "config_consistency": consistency,
        "control_balance": balance,
        "n_items": len(public),
        "join": "timestamp",
        "sealed_sha256": recorded_seal_digest() if not args.allow_unsealed else None,
        "allow_unsealed": bool(args.allow_unsealed),
        "skip_render": bool(args.skip_render),
        "arm1_labeler": None,
        "arm2_labeler": None,
        "arm_independence_rule": (
            "Arm 1 and Arm 2 must be labelled by different cold agents. "
            "Record agent ids here before scoring."
        ),
        "items": public,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Blinded visual CRT state-fidelity sampler")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--out-dir", default=str(ROOT / "results" / "visual_crt_state_fidelity"))
    p.add_argument("--events", default=str(DEFAULT_EVENTS))
    p.add_argument("--trace", default=str(DEFAULT_TRACE))
    p.add_argument("--csv", default=str(DEFAULT_CSV))
    p.add_argument("--shots-dir", default=str(DEFAULT_SHOTS))
    p.add_argument("--allow-unsealed", action="store_true",
                   help="TEST ONLY. Emit a sample before the user-prediction SHA is recorded.")
    p.add_argument("--skip-render", action="store_true",
                   help="Manifest + HTML only (used by floors that do not need pixels).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = run(args)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
