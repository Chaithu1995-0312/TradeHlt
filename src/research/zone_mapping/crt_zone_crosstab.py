"""
CRT State × Zone cross-tabulation — relevance of geometry to CRT structure.

Streams Phase-1 (or any) OHLCV through FeaturePipeline + CRTEngine + HistoricalZoneMapper
on the same bars, then builds:

  - count matrix:  state × zone
  - P(zone | state) and P(state | zone)
  - concentration / lift vs marginal zone occupancy
  - zone-entry events: CRT state distribution when best_zone_id changes into Z
  - CRT state-entry events: zone distribution when CRT state changes into S

Research-only. No admission authority.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTEngine, Candle
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES
from research.zone_mapping.collect_trade_opened_features import (
    _harden_crt_config,
)
from research.zone_mapping.historical_zone_mapper import (
    HistoricalZoneMapper,
    ZoneMapConfig,
)
from research.zone_mapping.zone_census import OUTSIDE, _zone_key
from runtime.backtest_v2 import HTFBuilder

CRT_STATE_ORDER = [
    "RANGE",
    "SHADOW_PENDING",
    "SWEEP",
    "DISPLACEMENT",
    "EXPANSION",
    "EXPIRED",
    "RETEST",
    "EXECUTION",
    "RESOLUTION",
]


@dataclass(frozen=True)
class BarJointLabel:
    timestamp: str
    candle_index: int
    crt_state: str
    zone_id: str
    cluster_score: float
    passed: bool
    crt_action: str
    # Geometry diagnostics (optional; filled by joint collector when available)
    best_zone_score: float = 0.0
    second_best_score: float = 0.0
    margin_best_second: float = 0.0


def collect_crt_zone_joint_labels(
    csv_path: str,
    *,
    instrument: str = "XAUUSD",
    warmup_candles: int = 50,
    htf_candles_per_range: int = 96,
    zone_config: Optional[ZoneMapConfig] = None,
    progress_every: int = 5000,
) -> list[BarJointLabel]:
    """
    Align CRT post-candle state with mapper best_zone_id on every post-init bar.
    """
    raw = pd.read_csv(csv_path)
    raw.columns = [c.strip().lower() for c in raw.columns]
    if "timestamp" not in raw.columns:
        if "date" in raw.columns and "time" in raw.columns:
            raw["timestamp"] = raw["date"].astype(str) + " " + raw["time"].astype(str)
        elif "date" in raw.columns:
            raw["timestamp"] = raw["date"]
        else:
            raise ValueError(f"No timestamp in {csv_path}")

    pipeline = FeaturePipeline(raw)
    enriched, vectors = pipeline.run()
    ts_series = pd.to_datetime(enriched["timestamp"])
    ts_to_idx = {
        ts_series.iloc[i].strftime("%Y-%m-%d %H:%M:%S"): i
        for i in range(len(ts_series))
    }

    candles: list[Candle] = []
    for _, row in raw.iterrows():
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.replace(tzinfo=None)
        if not isinstance(ts, datetime):
            ts = datetime.fromisoformat(str(ts))
        candles.append(
            Candle(
                timestamp=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if "volume" in row and pd.notna(row["volume"]) else 0.0,
            )
        )

    cfg = zone_config or ZoneMapConfig.from_prod_engine_runner()
    mapper = HistoricalZoneMapper(cfg)
    crt_cfg = _harden_crt_config(ConfigBuilder.build(instrument))
    engine = CRTEngine(crt_cfg)
    htf = HTFBuilder(htf_candles_per_range, instrument)

    labels: list[BarJointLabel] = []
    initialised = False
    candle_idx = 0
    prev_htf = ""
    htf_remaining = htf_candles_per_range
    n_candles = len(candles)

    for candle in candles:
        candle_idx += 1
        htf.push(candle)
        if htf.current_htf_id != prev_htf:
            prev_htf = htf.current_htf_id
            htf_remaining = htf_candles_per_range - 1
        else:
            htf_remaining = max(0, htf_remaining - 1)
        engine.state.htf_remaining_candles = htf_remaining

        if candle_idx < warmup_candles:
            continue
        if not initialised:
            seed = htf.seed_candles()
            if seed:
                engine.initialise_range(seed, htf.current_htf_id, "OFF_SESSION")
                initialised = True
            continue

        result = engine.process_candle(candle, htf.current_htf_id)
        action = str(result.get("action", "NONE"))
        state_name = engine.state.current_state.name

        ts_key = candle.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        fv_idx = ts_to_idx.get(ts_key, -1)
        if fv_idx < 0:
            continue

        vec = vectors[fv_idx]
        if hasattr(vec, "tolist"):
            vec = vec.tolist()
        feat = {name: float(vec[j]) for j, name in enumerate(CANONICAL_FEATURES)}
        for col in ("open", "high", "low", "close", "volume"):
            if col in enriched.columns:
                feat[col] = float(enriched.iloc[fv_idx][col])

        zrec = mapper.map_row(
            feat, timestamp=ts_key, bar_index=candle_idx, instrument=instrument
        )
        labels.append(
            BarJointLabel(
                timestamp=ts_key,
                candle_index=candle_idx,
                crt_state=str(state_name),
                zone_id=_zone_key(zrec.get("best_zone_id")),
                cluster_score=float(zrec.get("cluster_score", 0.0)),
                passed=bool(zrec.get("passed_cluster_threshold", False)),
                crt_action=action,
                best_zone_score=float(zrec.get("best_zone_score") or 0.0),
                second_best_score=float(zrec.get("second_best_score") or 0.0),
                margin_best_second=float(zrec.get("margin_best_second") or 0.0),
            )
        )
        if progress_every and candle_idx % progress_every == 0:
            print(f"  joint labels {len(labels)} (candle {candle_idx}/{n_candles})…", flush=True)

    return labels


def _ordered_union(preferred: list[str], seen: set[str]) -> list[str]:
    out = [s for s in preferred if s in seen]
    for s in sorted(seen):
        if s not in out:
            out.append(s)
    return out


def compute_crt_zone_crosstab(
    labels: list[BarJointLabel],
    *,
    registry_zone_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Build count matrices, conditionals, lift, and entry-event tables."""
    n = len(labels)
    states_seen = {lab.crt_state for lab in labels}
    zones_seen = {lab.zone_id for lab in labels}
    if registry_zone_ids:
        zones_seen |= set(registry_zone_ids)
    states = _ordered_union(CRT_STATE_ORDER, states_seen)
    zones = _ordered_union(list(registry_zone_ids or []), zones_seen)
    if OUTSIDE in zones_seen and OUTSIDE not in zones:
        zones.append(OUTSIDE)

    # Counts
    joint = Counter((lab.crt_state, lab.zone_id) for lab in labels)
    state_marg = Counter(lab.crt_state for lab in labels)
    zone_marg = Counter(lab.zone_id for lab in labels)

    count_matrix = [
        [int(joint.get((s, z), 0)) for z in zones] for s in states
    ]

    # P(zone | state)
    p_zone_given_state: dict[str, dict[str, float]] = {}
    for s in states:
        tot = state_marg.get(s, 0)
        p_zone_given_state[s] = {
            z: (float(joint.get((s, z), 0)) / tot if tot > 0 else 0.0) for z in zones
        }

    # P(state | zone)
    p_state_given_zone: dict[str, dict[str, float]] = {}
    for z in zones:
        tot = zone_marg.get(z, 0)
        p_state_given_zone[z] = {
            s: (float(joint.get((s, z), 0)) / tot if tot > 0 else 0.0) for s in states
        }

    # Lift: P(z|s) / P(z)  — concentration of state s in zone z
    zone_prior = {z: (zone_marg.get(z, 0) / n if n > 0 else 0.0) for z in zones}
    lift: dict[str, dict[str, float]] = {}
    for s in states:
        lift[s] = {}
        for z in zones:
            prior = zone_prior[z]
            pz_s = p_zone_given_state[s][z]
            lift[s][z] = (pz_s / prior) if prior > 0 else 0.0

    # Top concentration pairs (lift>=1.5 and count>=min_n)
    concentrations = []
    for s in states:
        for z in zones:
            c = int(joint.get((s, z), 0))
            if c < 30:
                continue
            L = lift[s][z]
            if L < 1.25:
                continue
            concentrations.append(
                {
                    "crt_state": s,
                    "zone_id": z,
                    "count": c,
                    "p_zone_given_state": p_zone_given_state[s][z],
                    "p_state_given_zone": p_state_given_zone[z][s],
                    "lift": L,
                    "zone_prior": zone_prior[z],
                }
            )
    concentrations.sort(key=lambda r: (-r["lift"], -r["count"]))

    # Zone-entry events: first bar of a new best_zone run
    zone_entry_state = Counter()  # (state, zone_entered)
    zone_entry_n = Counter()  # zone_entered
    prev_z = None
    for lab in labels:
        if prev_z is None or lab.zone_id != prev_z:
            zone_entry_state[(lab.crt_state, lab.zone_id)] += 1
            zone_entry_n[lab.zone_id] += 1
        prev_z = lab.zone_id

    zone_entry_p_state: dict[str, dict[str, float]] = {}
    for z in zones:
        tot = zone_entry_n.get(z, 0)
        zone_entry_p_state[z] = {
            s: (float(zone_entry_state.get((s, z), 0)) / tot if tot > 0 else 0.0)
            for s in states
        }

    # CRT state-entry events: first bar of a new CRT state run
    state_entry_zone = Counter()  # (state_entered, zone)
    state_entry_n = Counter()
    prev_s = None
    for lab in labels:
        if prev_s is None or lab.crt_state != prev_s:
            state_entry_zone[(lab.crt_state, lab.zone_id)] += 1
            state_entry_n[lab.crt_state] += 1
        prev_s = lab.crt_state

    state_entry_p_zone: dict[str, dict[str, float]] = {}
    for s in states:
        tot = state_entry_n.get(s, 0)
        state_entry_p_zone[s] = {
            z: (float(state_entry_zone.get((s, z), 0)) / tot if tot > 0 else 0.0)
            for z in zones
        }

    # TRADE_OPENED / EXECUTION focus slice
    open_actions = [
        lab for lab in labels if "TRADE_OPENED" in (lab.crt_action or "")
    ]
    exec_bars = [lab for lab in labels if lab.crt_state == "EXECUTION"]
    open_zone = Counter(lab.zone_id for lab in open_actions)
    exec_zone = Counter(lab.zone_id for lab in exec_bars)

    return {
        "schema_version": "crt_zone_crosstab_v1",
        "n_bars": n,
        "states": states,
        "zones": zones,
        "state_marginal": {s: int(state_marg.get(s, 0)) for s in states},
        "zone_marginal": {z: int(zone_marg.get(z, 0)) for z in zones},
        "count_matrix": {
            "rows": states,
            "cols": zones,
            "counts": count_matrix,
        },
        "p_zone_given_state": p_zone_given_state,
        "p_state_given_zone": p_state_given_zone,
        "lift_zone_given_state": lift,
        "concentrations": concentrations,
        "zone_entry": {
            "n_by_zone": {z: int(zone_entry_n.get(z, 0)) for z in zones},
            "p_crt_state_on_entry": zone_entry_p_state,
        },
        "crt_state_entry": {
            "n_by_state": {s: int(state_entry_n.get(s, 0)) for s in states},
            "p_zone_on_entry": state_entry_p_zone,
        },
        "trade_opened": {
            "n": len(open_actions),
            "zone_counts": dict(open_zone),
            "p_zone": {
                z: (open_zone.get(z, 0) / len(open_actions) if open_actions else 0.0)
                for z in zones
            },
        },
        "execution_state": {
            "n": len(exec_bars),
            "zone_counts": dict(exec_zone),
            "p_zone": {
                z: (exec_zone.get(z, 0) / len(exec_bars) if exec_bars else 0.0)
                for z in zones
            },
        },
    }


def crosstab_to_markdown(xt: Mapping[str, Any], *, title: str = "CRT State × Zone Cross-Tab") -> str:
    states = xt.get("states") or []
    zones = xt.get("zones") or []
    counts = (xt.get("count_matrix") or {}).get("counts") or []
    lines = [
        f"# {title}",
        "",
        f"**Bars (joint):** {xt.get('n_bars')}",
        "",
        "## Count matrix (rows = CRT state, cols = zone)",
        "",
    ]
    header = "| CRT \\ Zone | " + " | ".join(zones) + " | total |"
    sep = "|---|" + "|".join(["---:" for _ in zones]) + "|---:|"
    lines.extend([header, sep])
    sm = xt.get("state_marginal") or {}
    for i, s in enumerate(states):
        row = counts[i] if i < len(counts) else [0] * len(zones)
        cells = " | ".join(str(int(c)) for c in row)
        lines.append(f"| {s} | {cells} | {sm.get(s, 0)} |")
    zm = xt.get("zone_marginal") or {}
    tot_cells = " | ".join(str(int(zm.get(z, 0))) for z in zones)
    lines.append(f"| **total** | {tot_cells} | {xt.get('n_bars')} |")

    lines.extend(["", "## P(zone | CRT state) — concentration of structure in geometry", ""])
    pzs = xt.get("p_zone_given_state") or {}
    lines.append("| CRT \\ Zone | " + " | ".join(zones) + " |")
    lines.append("|---|" + "|".join(["---:" for _ in zones]) + "|")
    for s in states:
        row = pzs.get(s) or {}
        cells = " | ".join(f"{float(row.get(z, 0)):.3f}" for z in zones)
        lines.append(f"| {s} | {cells} |")

    lines.extend(["", "## Lift P(z|s)/P(z) — values ≫ 1 mean state is concentrated in zone", ""])
    lift = xt.get("lift_zone_given_state") or {}
    lines.append("| CRT \\ Zone | " + " | ".join(zones) + " |")
    lines.append("|---|" + "|".join(["---:" for _ in zones]) + "|")
    for s in states:
        row = lift.get(s) or {}
        cells = " | ".join(f"{float(row.get(z, 0)):.2f}" for z in zones)
        lines.append(f"| {s} | {cells} |")

    lines.extend(["", "## Top concentrations (lift ≥ 1.25, n ≥ 30)", ""])
    lines.append("| CRT state | Zone | n | P(z\\|s) | P(s\\|z) | lift |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for r in (xt.get("concentrations") or [])[:25]:
        lines.append(
            f"| {r['crt_state']} | {r['zone_id']} | {r['count']} | "
            f"{r['p_zone_given_state']:.3f} | {r['p_state_given_zone']:.3f} | {r['lift']:.2f} |"
        )

    lines.extend(["", "## Zone entry — P(CRT state | first bar of zone run)", ""])
    ze = (xt.get("zone_entry") or {}).get("p_crt_state_on_entry") or {}
    lines.append("| Zone entered \\ CRT | " + " | ".join(states) + " | n_entries |")
    lines.append("|---|" + "|".join(["---:" for _ in states]) + "|---:|")
    n_ze = (xt.get("zone_entry") or {}).get("n_by_zone") or {}
    for z in zones:
        row = ze.get(z) or {}
        cells = " | ".join(f"{float(row.get(s, 0)):.3f}" for s in states)
        lines.append(f"| {z} | {cells} | {n_ze.get(z, 0)} |")

    lines.extend(["", "## CRT state entry — P(zone | first bar of CRT state run)", ""])
    se = (xt.get("crt_state_entry") or {}).get("p_zone_on_entry") or {}
    lines.append("| CRT entered \\ Zone | " + " | ".join(zones) + " | n_entries |")
    lines.append("|---|" + "|".join(["---:" for _ in zones]) + "|---:|")
    n_se = (xt.get("crt_state_entry") or {}).get("n_by_state") or {}
    for s in states:
        row = se.get(s) or {}
        cells = " | ".join(f"{float(row.get(z, 0)):.3f}" for z in zones)
        lines.append(f"| {s} | {cells} | {n_se.get(s, 0)} |")

    to = xt.get("trade_opened") or {}
    lines.extend(
        [
            "",
            f"## TRADE_OPENED zone distribution (n={to.get('n', 0)})",
            "",
            "| Zone | count | P |",
            "|---|---:|---:|",
        ]
    )
    for z in zones:
        c = (to.get("zone_counts") or {}).get(z, 0)
        p = (to.get("p_zone") or {}).get(z, 0.0)
        if c or p:
            lines.append(f"| {z} | {c} | {float(p):.3f} |")

    ex = xt.get("execution_state") or {}
    lines.extend(
        [
            "",
            f"## EXECUTION-state bars zone distribution (n={ex.get('n', 0)})",
            "",
            "| Zone | count | P |",
            "|---|---:|---:|",
        ]
    )
    for z in zones:
        c = (ex.get("zone_counts") or {}).get(z, 0)
        p = (ex.get("p_zone") or {}).get(z, 0.0)
        if c or p:
            lines.append(f"| {z} | {c} | {float(p):.3f} |")

    lines.append("")
    return "\n".join(lines)
