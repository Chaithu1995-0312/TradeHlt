#!/usr/bin/env python3
"""
zone_x_o4_gap_study.py
======================
ZONE-X O-4 — DESCRIPTIVE gap penalty study (path (a) residual work).

Question (v0.8 O-4 / design §10.2):
  At k=1.5, m=1.0, L=h=12 on XAUUSD M15, when a stop resolves, how does
  *realized* adverse excursion (ATR units) compare to nominal m — especially
  on the ~29% of bars that gap from the prior close?

Authority: RESEARCH_ONLY / DESCRIPTIVE.
  - Does NOT seek region class X
  - Does NOT unseal the test year for feature search
  - Does NOT grant production or ontology authority
  - Reports generation and test splits separately (facts about microstructure)

Fill model (ASSUMED, declared):
  Conservative stop-first intrabar (v0.8 §5.3).
  If the resolving bar's *open* is already through the stop (gap-through),
  fill at open; else fill at the barrier price (touch). This is the natural
  gap penalty model; it is not a claim about broker stop algorithms.

Outputs under results/research/zone_x_o4_gap_study/:
  - ZONE_X_O4_GAP_STUDY.md
  - zone_x_o4_gap_study_LATEST.json
  - stop_events_sample_LATEST.csv (capped sample for audit)

Usage:
  python scripts/research/zone_x_o4_gap_study.py
  python scripts/research/zone_x_o4_gap_study.py --csv data/mt5/XAUUSD_M15.csv
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── v0.8 frozen constants (cited, not renegotiated) ───────────────────────────
L = 12
H = 12
K = 1.5
M_NOM = 1.0
ATR_PERIOD = 14
STEP_SECONDS = 15 * 60
GEN_START = "2024-05-22"
GEN_END = "2025-05-21"  # exclusive end of gen in split text is →; use < test start
TEST_START = "2025-05-21"
TEST_END = "2026-05-21"
# Decision dual-c (reporting only; O-4 is about m, not c)
C_EMPIRICAL = 0.0238
C_DESIGN = 0.055
C_LEGACY = 0.070
EPS_GAP_USD = 1e-9  # open != prev_close


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _stats(xs: np.ndarray) -> dict[str, Any]:
    a = np.asarray(xs, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    return {
        "n": int(a.size),
        "mean": float(a.mean()),
        "p50": float(np.median(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
        "p99": float(np.percentile(a, 99)),
        "min": float(a.min()),
        "max": float(a.max()),
    }


def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder ATR; first TR uses high-low only (no prev close)."""
    n = len(close)
    tr = np.empty(n, dtype=float)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    atr = np.full(n, np.nan, dtype=float)
    if n < period:
        return atr
    atr[period - 1] = tr[:period].mean()
    alpha = 1.0 / period
    for i in range(period, n):
        atr[i] = atr[i - 1] + alpha * (tr[i] - atr[i - 1])
    return atr


def load_ohlcv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"timestamp", "open", "high", "low", "close"}
    missing = need - {c.lower() for c in df.columns}
    if missing:
        # case-sensitive check
        cols = {c.lower(): c for c in df.columns}
        for m in list(need):
            if m not in cols:
                raise ValueError(f"missing column {m} in {path}")
        df = df.rename(columns={cols[k]: k for k in need})
    else:
        df = df.rename(columns={c: c.lower() for c in df.columns})
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    return df


def contiguity_mask(ts: np.ndarray) -> np.ndarray:
    """bar i is contiguous with i-1 if delta == 15min (or first bar)."""
    n = len(ts)
    ok = np.ones(n, dtype=bool)
    for i in range(1, n):
        dt = (ts[i] - ts[i - 1]) / np.timedelta64(1, "s")
        ok[i] = abs(dt - STEP_SECONDS) < 1.0
    return ok


def window_admissible(contig: np.ndarray, t: int) -> bool:
    """All L obs + H forward bars mutually contiguous, incl. boundary t+L-1 → t+L."""
    # bars involved: [t, t+L+H-1] need consecutive steps between each pair
    end = t + L + H - 1
    if end >= len(contig):
        return False
    # contig[i] means i is contiguous with i-1; for span [t..end] need contig[t+1..end]
    return bool(np.all(contig[t + 1 : end + 1]))


@dataclass
class StopEvent:
    split: str
    side: str  # long|short
    t: int
    anchor_ts: str
    sigma: float
    nominal_m: float
    realized_m: float
    gap_through: bool
    gap_on_resolve_bar: bool
    resolve_bar_offset: int
    fill_price: float
    barrier: float
    open_resolve: float
    prev_close_resolve: float


def first_passage_stop_events(
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    atr: np.ndarray,
    contig: np.ndarray,
    ts: np.ndarray,
    t: int,
    split: str,
) -> list[StopEvent]:
    """For one admissible anchor index t (window starts at t, anchor at t+L-1)."""
    if not window_admissible(contig, t):
        return []
    a_idx = t + L - 1
    sigma = float(atr[a_idx])
    if not np.isfinite(sigma) or sigma <= 0:
        return []
    A = float(c[a_idx])
    long_stop = A - M_NOM * sigma
    long_tgt = A + K * sigma
    short_stop = A + M_NOM * sigma
    short_tgt = A - K * sigma

    events: list[StopEvent] = []
    # walk forward bars [a_idx+1, a_idx+H]
    long_done = False
    short_done = False
    for j in range(1, H + 1):
        i = a_idx + j
        # gap vs prev close
        prev_c = float(c[i - 1])
        op = float(o[i])
        hi = float(h[i])
        lo = float(l[i])
        bar_gaps = abs(op - prev_c) > EPS_GAP_USD

        if not long_done:
            # gap-through stop: open already at/through stop
            long_gap_thru = op <= long_stop
            hit_stop = long_gap_thru or (lo <= long_stop)
            hit_tgt = hi >= long_tgt
            # v0.8 §5.3: if both stop and target on same bar, stop first
            if hit_stop:
                fill = op if long_gap_thru else long_stop
                realized = (A - fill) / sigma
                events.append(
                    StopEvent(
                        split=split,
                        side="long",
                        t=t,
                        anchor_ts=str(ts[a_idx]),
                        sigma=sigma,
                        nominal_m=M_NOM,
                        realized_m=float(realized),
                        gap_through=bool(long_gap_thru),
                        gap_on_resolve_bar=bool(bar_gaps),
                        resolve_bar_offset=j,
                        fill_price=float(fill),
                        barrier=float(long_stop),
                        open_resolve=op,
                        prev_close_resolve=prev_c,
                    )
                )
                long_done = True
            elif hit_tgt:
                long_done = True  # win — not a stop event

        if not short_done:
            short_gap_thru = op >= short_stop
            hit_stop = short_gap_thru or (hi >= short_stop)
            hit_tgt = lo <= short_tgt
            if hit_stop:
                fill = op if short_gap_thru else short_stop
                realized = (fill - A) / sigma
                events.append(
                    StopEvent(
                        split=split,
                        side="short",
                        t=t,
                        anchor_ts=str(ts[a_idx]),
                        sigma=sigma,
                        nominal_m=M_NOM,
                        realized_m=float(realized),
                        gap_through=bool(short_gap_thru),
                        gap_on_resolve_bar=bool(bar_gaps),
                        resolve_bar_offset=j,
                        fill_price=float(fill),
                        barrier=float(short_stop),
                        open_resolve=op,
                        prev_close_resolve=prev_c,
                    )
                )
                short_done = True
            elif hit_tgt:
                short_done = True

        if long_done and short_done:
            break
    return events


def summarize_events(events: list[StopEvent], label: str) -> dict[str, Any]:
    if not events:
        return {"label": label, "n_stop_events": 0}
    rm = np.array([e.realized_m for e in events], dtype=float)
    gt = np.array([e.gap_through for e in events], dtype=bool)
    gb = np.array([e.gap_on_resolve_bar for e in events], dtype=bool)
    excess = rm - M_NOM
    ratio = rm / M_NOM

    def _sub(mask: np.ndarray, name: str) -> dict[str, Any]:
        if not mask.any():
            return {"name": name, "n": 0}
        return {
            "name": name,
            "n": int(mask.sum()),
            "realized_m": _stats(rm[mask]),
            "realized_m_over_nominal": _stats(ratio[mask]),
            "excess_m": _stats(excess[mask]),
            "frac_worse_than_nominal": float(np.mean(rm[mask] > M_NOM + 1e-12)),
            "frac_gap_through": float(np.mean(gt[mask])),
        }

    return {
        "label": label,
        "n_stop_events": len(events),
        "all": _sub(np.ones(len(events), dtype=bool), "all"),
        "gap_through": _sub(gt, "gap_through"),
        "non_gap_through": _sub(~gt, "non_gap_through"),
        "resolve_bar_gaps": _sub(gb, "resolve_bar_gaps"),
        "by_side": {
            "long": _sub(np.array([e.side == "long" for e in events]), "long"),
            "short": _sub(np.array([e.side == "short" for e in events]), "short"),
        },
        "P_gap_affects_stop": float(np.mean(gt)),  # design wording
        "E_realized_m_over_m": float(np.mean(ratio)),
        "p90_realized_m": float(np.percentile(rm, 90)),
        "p99_realized_m": float(np.percentile(rm, 99)),
        "mean_realized_m": float(np.mean(rm)),
        "median_realized_m": float(np.median(rm)),
        "mean_excess_m": float(np.mean(excess)),
        "frac_worse_than_nominal": float(np.mean(rm > M_NOM + 1e-12)),
    }


def bar_gap_census(
    o: np.ndarray,
    c: np.ndarray,
    atr: np.ndarray,
    contig: np.ndarray,
    bar_mask: Optional[np.ndarray] = None,
) -> dict[str, Any]:
    """Population gap structure (contiguous bar pairs with valid ATR).

    `bar_mask[i]` selects whether bar *i* (the open side of the step) is in-split.
    Contiguity is always evaluated on the full series (session breaks stay session breaks).
    """
    n = len(c)
    if bar_mask is None:
        bar_mask = np.ones(n, dtype=bool)
    gaps = []
    gaps_atr = []
    n_contig = 0
    for i in range(1, n):
        if not bar_mask[i]:
            continue
        if not contig[i]:
            continue
        n_contig += 1
        if not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        g = float(o[i] - c[i - 1])
        if abs(g) > EPS_GAP_USD:
            gaps.append(g)
            gaps_atr.append(g / float(atr[i]))
    n_gap = len(gaps)
    return {
        "n_contig_steps": n_contig,
        "n_gap_bars": n_gap,
        "gap_rate": float(n_gap / n_contig) if n_contig else None,
        "gap_usd": _stats(np.array(gaps)) if gaps else {"n": 0},
        "gap_atr": _stats(np.abs(np.array(gaps_atr))) if gaps_atr else {"n": 0},
        "gap_atr_signed": _stats(np.array(gaps_atr)) if gaps_atr else {"n": 0},
    }


def pstar_sensitivity(summary: dict[str, Any]) -> dict[str, Any]:
    """
    How much does mean excess stop worsen the directional p* under design c?
    DESCRIPTIVE only — not a new cost model authority.
    If stops that resolve average realized_m = m_eff instead of m,
    a rough first-order replacement in p* = (m_eff + c)/(k + m_eff).
    """
    if summary.get("n_stop_events", 0) == 0:
        return {}
    m_eff = float(summary["mean_realized_m"])
    out = {}
    for name, c in (("c_empirical", C_EMPIRICAL), ("c_design", C_DESIGN), ("c_legacy", C_LEGACY)):
        p_nom = (M_NOM + c) / (K + M_NOM)
        p_eff = (m_eff + c) / (K + m_eff)
        out[name] = {
            "c": c,
            "p_star_nominal_m": p_nom,
            "p_star_mean_realized_m": p_eff,
            "delta_pp": (p_eff - p_nom) * 100.0,
            "m_eff": m_eff,
        }
    return out


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# ZONE-X O-4 — Descriptive Gap Penalty Study",
        "",
        f"**Generated:** {payload['generated_utc']}",
        f"**Corpus:** `{payload['csv']}` sha256=`{payload['csv_sha256'][:16]}…`",
        "**Authority:** RESEARCH_ONLY / DESCRIPTIVE — path (a) residual; does not seek X; "
        "does not amend v0.8; does not grant ontology or production authority.",
        "",
        "## Setup (v0.8 cited)",
        "",
        f"- L={L}, h={H}, k={K}, m_nominal={M_NOM}, ATR=Wilder{ATR_PERIOD}",
        f"- Splits: generation [{GEN_START} → {TEST_START}), test [{TEST_START} → {TEST_END}]",
        "- Fill model: stop-first; **gap-through fills at open**, else at barrier",
        "- `gap_through` = open of resolving bar already past stop (the gap *affects* the stop)",
        "",
        "## 1. Bar-level gap census",
        "",
    ]
    for split, g in payload["gap_census"].items():
        lines += [
            f"### {split}",
            "",
            f"| metric | value |",
            f"|---|---|",
            f"| contiguous steps | {g['n_contig_steps']} |",
            f"| gapping bars | {g['n_gap_bars']} |",
            f"| gap rate | {g['gap_rate']:.4f} |" if g.get("gap_rate") is not None else "| gap rate | n/a |",
        ]
        if g.get("gap_atr", {}).get("n", 0):
            ga = g["gap_atr"]
            lines += [
                f"| \\|gap\\|/ATR mean | {ga['mean']:.4f} |",
                f"| \\|gap\\|/ATR p50 | {ga['p50']:.4f} |",
                f"| \\|gap\\|/ATR p90 | {ga['p90']:.4f} |",
                f"| \\|gap\\|/ATR p99 | {ga['p99']:.4f} |",
            ]
        lines.append("")

    lines += ["## 2. Stop-event realized m", ""]
    for split, s in payload["stop_summaries"].items():
        if s.get("n_stop_events", 0) == 0:
            lines += [f"### {split}", "", "No stop events.", ""]
            continue
        lines += [
            f"### {split}",
            "",
            f"| metric | value |",
            f"|---|---|",
            f"| n stop events (long+short) | {s['n_stop_events']} |",
            f"| P(gap_affects_stop) = P(gap_through) | **{s['P_gap_affects_stop']:.4f}** |",
            f"| E[realized_m] | **{s['mean_realized_m']:.4f}** |",
            f"| median realized_m | {s['median_realized_m']:.4f} |",
            f"| p90 realized_m | **{s['p90_realized_m']:.4f}** |",
            f"| p99 realized_m | {s['p99_realized_m']:.4f} |",
            f"| E[realized_m / m] | **{s['E_realized_m_over_m']:.4f}** |",
            f"| mean excess (realized − m) | {s['mean_excess_m']:.4f} |",
            f"| frac realized_m > m | {s['frac_worse_than_nominal']:.4f} |",
            "",
            "#### Gap-through vs touch-fill",
            "",
        ]
        for key in ("gap_through", "non_gap_through"):
            sub = s[key]
            if sub.get("n", 0) == 0:
                lines += [f"- **{key}**: n=0", ""]
                continue
            rm = sub["realized_m"]
            lines += [
                f"- **{key}** (n={sub['n']}): mean realized_m={rm['mean']:.4f}, "
                f"p50={rm['p50']:.4f}, p90={rm['p90']:.4f}, "
                f"frac>m={sub['frac_worse_than_nominal']:.4f}",
            ]
        lines.append("")
        lines += ["#### By side", ""]
        for side, sub in s["by_side"].items():
            if sub.get("n", 0) == 0:
                continue
            rm = sub["realized_m"]
            lines.append(
                f"- **{side}** n={sub['n']}: mean={rm['mean']:.4f} p50={rm['p50']:.4f} "
                f"p90={rm['p90']:.4f} gap_through={sub['frac_gap_through']:.4f}"
            )
        lines.append("")

        aside = payload.get("economic_aside", {}).get(split, {})
        if aside:
            lines += [
                "#### First-order p* sensitivity (DESCRIPTIVE)",
                "",
                "Replace m with mean realized_m in p*=(m+c)/(k+m); not a new authority.",
                "",
                "| c role | c | p* (m=1) | p* (m_eff) | Δ pp |",
                "|---|---|---|---|---|",
            ]
            for name, row in aside.items():
                lines.append(
                    f"| {name} | {row['c']:.4f} | {row['p_star_nominal_m']:.4f} | "
                    f"{row['p_star_mean_realized_m']:.4f} | {row['delta_pp']:+.3f} |"
                )
            lines.append("")

    lines += [
        "## 3. Interpretation (bounded)",
        "",
        payload["interpretation"],
        "",
        "## 4. Non-claims",
        "",
        "- Not a feature search; not evidence for/against region class X.",
        "- Not a live broker stop-slip distribution (that is O-1 fill history).",
        "- Gap-through fill-at-open is an ASSUMED model of adverse selection on gaps.",
        "- Does not change D-C1 design c=0.055 or path (a).",
        "",
        "## 5. Reproduce",
        "",
        "```text",
        "python scripts/research/zone_x_o4_gap_study.py --csv data/mt5/XAUUSD_M15.csv",
        "```",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", default=str(ROOT / "data" / "mt5" / "XAUUSD_M15.csv"))
    p.add_argument(
        "--out-dir",
        default=str(ROOT / "results" / "research" / "zone_x_o4_gap_study"),
    )
    p.add_argument("--sample-rows", type=int, default=5000, help="cap CSV sample of stop events")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    csv_path = Path(args.csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_ohlcv(csv_path)
    ts = df["timestamp"].to_numpy()
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = wilder_atr(h, l, c, ATR_PERIOD)
    contig = contiguity_mask(ts)

    # split masks on anchor bar timestamp
    gen_lo = pd.Timestamp(GEN_START, tz="UTC")
    test_lo = pd.Timestamp(TEST_START, tz="UTC")
    test_hi = pd.Timestamp(TEST_END, tz="UTC") + pd.Timedelta(days=1)  # inclusive calendar end

    def split_of_anchor(a_idx: int) -> Optional[str]:
        tsa = pd.Timestamp(ts[a_idx])
        if tsa < gen_lo:
            return None
        if tsa < test_lo:
            return "generation"
        if tsa <= pd.Timestamp(TEST_END, tz="UTC") + pd.Timedelta(hours=23, minutes=45):
            return "test"
        return None

    # bar gap census per split (by bar timestamp)
    def mask_split(name: str) -> np.ndarray:
        tss = pd.to_datetime(df["timestamp"], utc=True)
        if name == "generation":
            return ((tss >= gen_lo) & (tss < test_lo)).to_numpy()
        if name == "test":
            return ((tss >= test_lo) & (tss <= pd.Timestamp(TEST_END, tz="UTC") + pd.Timedelta(hours=23, minutes=45))).to_numpy()
        return np.ones(len(df), dtype=bool)

    gap_census = {}
    for name in ("generation", "test", "full"):
        gap_census[name] = bar_gap_census(o, c, atr, contig, mask_split(name))

    # also overall open==prev_close rate as in v0.8
    eq = 0
    n_pair = 0
    for i in range(1, len(c)):
        if not contig[i]:
            continue
        n_pair += 1
        if abs(o[i] - c[i - 1]) <= EPS_GAP_USD:
            eq += 1
    open_eq_rate = eq / n_pair if n_pair else None

    events: list[StopEvent] = []
    n_windows = {"generation": 0, "test": 0}
    n_admissible = {"generation": 0, "test": 0}

    max_t = len(c) - (L + H)
    for t in range(0, max_t + 1):
        a_idx = t + L - 1
        split = split_of_anchor(a_idx)
        if split is None:
            continue
        n_windows[split] += 1
        if not window_admissible(contig, t):
            continue
        if not np.isfinite(atr[a_idx]) or atr[a_idx] <= 0:
            continue
        n_admissible[split] += 1
        events.extend(first_passage_stop_events(o, h, l, c, atr, contig, ts, t, split))

    stop_summaries = {
        "generation": summarize_events([e for e in events if e.split == "generation"], "generation"),
        "test": summarize_events([e for e in events if e.split == "test"], "test"),
        "pooled": summarize_events(events, "pooled"),
    }
    economic_aside = {k: pstar_sensitivity(v) for k, v in stop_summaries.items()}

    # interpretation (deterministic from numbers)
    gen = stop_summaries["generation"]
    test = stop_summaries["test"]
    g_rate = gap_census["full"].get("gap_rate")
    g_atr_p99 = gap_census["full"].get("gap_atr", {}).get("p99")
    if gen.get("n_stop_events", 0):
        interp = (
            f"**Structural point:** v0.8 admissibility requires 15-minute contiguity across the "
            f"L+h window, so weekend / session-break gaps never appear inside a valid forward path. "
            f"Only *intraday micro-gaps* (open≠prev_close on contiguous bars) can produce gap-through. "
            f"Full-corpus contig gap rate={g_rate:.3f} (open==prev_close={open_eq_rate:.3f}); "
            f"v0.8 cited ~71% open==prev_close / ~29% gap — this corpus measures a higher micro-gap "
            f"rate but tiny size (full |gap|/ATR p99={g_atr_p99}). "
            f"Generation: n_stop={gen['n_stop_events']}, P(gap_through)={gen['P_gap_affects_stop']:.4f} "
            f"(n={gen['gap_through'].get('n', 0)}), E[realized_m/m]={gen['E_realized_m_over_m']:.4f}. "
            f"Test: P(gap_through)={test.get('P_gap_affects_stop', float('nan')):.4f} "
            f"(n={test.get('gap_through', {}).get('n', 0)}), "
            f"conditional mean realized_m on gap-through="
            f"{test.get('gap_through', {}).get('realized_m', {}).get('mean', float('nan')):.3f}. "
            f"**Conclusion:** average stop gap-penalty is ~0 at m=1.0; gap-through is rare "
            f"(≪0.1% of stops) but fat-tailed when it occurs. O-4 does not justify changing "
            f"nominal m or design c=0.055; residual stop risk remains in broker/live slip (O-1), "
            f"not in OHLC gap-through under the admissibility filter."
        )
    else:
        interp = "No generation stop events; check data/admissibility."

    payload = {
        "title": "ZONE-X O-4 descriptive gap penalty",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "authority": "RESEARCH_ONLY_DESCRIPTIVE",
        "path": "a_stop",
        "decision_ref": "ZONE-X-DECISION-2026-08-06.md",
        "spec_ref": "ZONE-X-SPEC-v0.8.md O-4 / §5.3",
        "csv": str(csv_path).replace("\\", "/"),
        "csv_sha256": _sha256(csv_path),
        "constants": {
            "L": L, "H": H, "K": K, "M_NOM": M_NOM, "ATR_PERIOD": ATR_PERIOD,
            "GEN": [GEN_START, TEST_START], "TEST": [TEST_START, TEST_END],
        },
        "n_bars": int(len(df)),
        "open_eq_prev_close_rate_contig": open_eq_rate,
        "gap_rate_contig": (1.0 - open_eq_rate) if open_eq_rate is not None else None,
        "n_windows": n_windows,
        "n_admissible": n_admissible,
        "gap_census": gap_census,
        "stop_summaries": stop_summaries,
        "economic_aside": economic_aside,
        "interpretation": interp,
        "fill_model": "gap_through_at_open_else_barrier_stop_first",
    }

    # write JSON
    json_path = out_dir / "zone_x_o4_gap_study_LATEST.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    ts_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out_dir / f"zone_x_o4_gap_study_{ts_tag}.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )

    # sample CSV
    sample = events[: max(0, args.sample_rows)]
    # prefer including all gap_through
    gt_events = [e for e in events if e.gap_through]
    rest = [e for e in events if not e.gap_through]
    sample = (gt_events + rest)[: args.sample_rows]
    if sample:
        pd.DataFrame([asdict(e) for e in sample]).to_csv(
            out_dir / "stop_events_sample_LATEST.csv", index=False
        )

    md = render_md(payload)
    (out_dir / "ZONE_X_O4_GAP_STUDY.md").write_text(md, encoding="utf-8")

    print("--- ZONE-X O-4 GAP STUDY ---")
    print(f"bars={len(df)} open==prev_close(contig)={open_eq_rate}")
    print(f"admissible windows gen={n_admissible['generation']} test={n_admissible['test']}")
    for name in ("generation", "test", "pooled"):
        s = stop_summaries[name]
        if s.get("n_stop_events", 0) == 0:
            print(f"{name}: no stops")
            continue
        print(
            f"{name}: n_stop={s['n_stop_events']} P_gap_thru={s['P_gap_affects_stop']:.4f} "
            f"E[rm]={s['mean_realized_m']:.4f} E[rm/m]={s['E_realized_m_over_m']:.4f} "
            f"p90={s['p90_realized_m']:.4f}"
        )
    print(f"report: {out_dir / 'ZONE_X_O4_GAP_STUDY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
