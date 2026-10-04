#!/usr/bin/env python
"""phase1_shadow_create_economic_census.py — 69-row CREATE economics, not restore-loop.

Object: HTF_CHANGED_WHILE_DISPLACEMENT pending-memory CREATE (n=69).
Do not optimize SHADOW_PENDING→EXPANSION (6/6 restore). Leak is upstream.

For each create: identity + feature/state bundle + H20..H100 net R under
memory_dir / trendbias_dir / always_long, plus MFE/MAE.

DESCRIPTIVE ONLY. economic_claims_allowed=false. No TTL flip. No promotion.

Session bind: four-arm run_id run_20260909_202201 (measurement envelope).
Source dual-construction parquet run_id run_20260906_013609.
Probe that counted the 69: memory_subsystem.json / probe run_20260910_010142.

INDEX JOIN (2026-09-10): engine `candle_index` is NOT CSV/parquet `bar_index`
(offset +62 = warmup 78 − seed 16). On-disk census for run_20260909_202201 was
joined on engine index — funnel counts VALID; session/hour/HTF/parent/H20-context
DO NOT USE until a rebuild. This script now stores engine_candle_index and sets
created_idx from event timestamp → CSV row so a future rebuild is parquet-aligned.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.costs import ComponentCostModel, UnmeasuredCostError  # noqa: E402
from utils.duckdb_query import open_views  # noqa: E402

from research.probes.corpus import load_corpus  # noqa: E402
from research.probes.governance import assert_no_claim_keys  # noqa: E402
from research.probes.horizon import close_at_horizon  # noqa: E402

# excursion() still on p001 until forward_walk extraction.
from research.probes.excursion import excursion  # noqa: E402

HORIZONS = (20, 40, 60, 80, 100)
PF_CAP = 9999.0
MIN_N = 30
SESSION_BIND = "run_20260909_202201"
SOURCE_RUN = "run_20260906_013609"

_MS = _ROOT / "results/analysis/phase1_resolver_replay/event_census/memory_subsystem.json"
_CE = _ROOT / "results/analysis/phase1_resolver_replay/event_census/memory_create_expire.json"
_EVENTS = (
    _ROOT
    / "results/analysis/phase1_resolver_replay/memory_subsystem_probe_run"
    / "run_20260910_010142_XAUUSD"
    / "XAUUSD_events.jsonl"
)
_CSV = _ROOT / "data/mt5/XAUUSD_M15.csv"
_MANIFEST = (
    _ROOT / "results/research/xauusd_mt5_cost_calibration"
    / "xauusd_mt5_cost_calibration_manifest_LATEST.json"
)
_RUN_DIR = _ROOT / "logs/dual_construction_full_gapfix"
_OUT_DIR = (
    _ROOT / "results/analysis/phase1_resolver_replay" / SESSION_BIND / "create_economic_census"
)
_NOTE = _ROOT / "docs/research/phase1_shadow_create_economic_census_note.md"


from research.provenance import sha256_file as _sha256_file  # noqa: E402 — research-framework Phase 1 dedup


def _git() -> dict:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(_ROOT), text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=str(_ROOT), text=True
            ).strip()
        )
        return {"git_sha": sha, "tree_dirty": dirty}
    except Exception:
        return {"git_sha": None, "tree_dirty": None}


def _pf(xs: list[float]) -> float:
    gp = sum(x for x in xs if x > 0)
    gl = -sum(x for x in xs if x < 0)
    if gl <= 0:
        return PF_CAP if gp > 0 else 0.0
    return min(gp / gl, PF_CAP)


def _score(xs: list[float]) -> dict:
    n = len(xs)
    if n == 0:
        return {
            "n": 0, "expectancy": None, "PF": None, "win_rate": None, "power": "EMPTY"
        }
    wins = sum(1 for x in xs if x > 0)
    return {
        "n": n,
        "expectancy": round(st.mean(xs), 6),
        "PF": round(_pf(xs), 4),
        "win_rate": round(wins / n, 6),
        "power": "INSUFFICIENT" if n < MIN_N else "WEAK",
    }


def _tb_dir(tb: Any) -> Optional[str]:
    try:
        v = float(tb)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or v == 0:
        return None
    return "LONG" if v > 0 else "SHORT"


def _hour_bucket(hour: Any) -> str:
    try:
        h = int(hour)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if 0 <= h < 8:
        return "ASIA_0_8"
    if 8 <= h < 13:
        return "LONDON_8_13"
    if 13 <= h < 17:
        return "LONDON_NY_OVERLAP_13_17"
    if 17 <= h < 22:
        return "NY_17_22"
    return "OFFHOURS_22_24"


def _age_bucket(age: Any) -> str:
    try:
        a = int(age)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if a <= 0:
        return "UNKNOWN"
    if a >= 4:
        return "4+"
    return str(a)


def _parse_htf(reason: str) -> Optional[str]:
    # "HTF changed: XAUUSD-HTF-000070 → XAUUSD-HTF-000071"
    if "→" in reason:
        return reason.split("→")[-1].strip()
    if "->" in reason:
        return reason.split("->")[-1].strip()
    return None


def _load_create_events() -> list[dict]:
    if not _EVENTS.is_file():
        raise FileNotFoundError(f"probe events missing: {_EVENTS}")
    rows = []
    with _EVENTS.open(encoding="utf-8") as fh:
        for line in fh:
            o = json.loads(line)
            if o.get("event") != "RESET":
                continue
            if o.get("state_from") != "DISPLACEMENT":
                continue
            reason = str(o.get("reason") or "")
            if "HTF" not in reason:
                continue
            rows.append(
                {
                    "engine_candle_index": int(o["candle_index"]),
                    "event_timestamp": o.get("timestamp"),
                    "timestamp": o.get("timestamp"),
                    "reason": reason,
                    "source_htf": _parse_htf(reason),
                    "outcome": "UNKNOWN",
                }
            )
    return rows


def _csv_index_by_timestamp(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as fh:
        for i, r in enumerate(csv.DictReader(fh)):
            out[r["timestamp"]] = i
    return out


def assemble_creates(ms: dict, ce: dict) -> list[dict]:
    """Spine = 69 RESET DISP+HTF events. Overlay by engine candle_index.

    created_idx for parquet/H20 is the CSV row of event_timestamp, not engine index.
    age_at_reset stays an engine-domain delta (both ends engine-indexed).
    """
    spine = _load_create_events()
    by_idx: dict[int, dict] = {}
    for i, rec in enumerate(spine, start=1):
        rec["memory_id"] = i
        by_idx[int(rec["engine_candle_index"])] = rec

    def overlay(created_idx, **fields) -> None:
        rec = by_idx.get(int(created_idx))
        if rec is None:
            return
        for k, v in fields.items():
            if v is not None:
                rec[k] = v

    for c in ms.get("create_sample") or []:
        overlay(
            c["created_idx"],
            formed_idx=c.get("formed_idx"),
            pending_dir=c.get("direction"),
            source_htf=c.get("source_htf"),
            ttl_initial=c.get("ttl_initial"),
            sample_memory_id=c.get("memory_id"),
        )
    for e in (ce.get("q2_expire_45_distribution") or {}).get("expire_rows") or ms.get(
        "expire_sample"
    ) or []:
        overlay(
            e["created_idx"],
            formed_idx=e.get("formed_idx"),
            pending_dir=e.get("direction"),
            source_htf=e.get("source_htf"),
            outcome="EXPIRED_TTL",
            closed_idx=e.get("expire_idx"),
        )
    for r in ms.get("all_restores") or []:
        overlay(
            r["created_idx"],
            formed_idx=r.get("formed_idx"),
            pending_dir=r.get("direction"),
            source_htf=r.get("source_htf"),
            outcome="RESTORED_TO_EXPANSION",
            closed_idx=r.get("collapse_idx"),
        )
    ts_to_i = _csv_index_by_timestamp(_CSV)
    out = []
    for rec in sorted(by_idx.values(), key=lambda r: r["engine_candle_index"]):
        eng_created = rec.get("engine_candle_index")
        formed = rec.get("formed_idx")
        rec["age_at_reset"] = (
            int(eng_created) - int(formed)
            if eng_created is not None and formed is not None
            else None
        )
        rec["age_at_reset_bucket"] = _age_bucket(rec["age_at_reset"])
        ts = str(rec.get("event_timestamp") or "").replace("T", " ")[:19]
        csv_i = ts_to_i.get(ts)
        rec["created_idx"] = csv_i
        rec["created_idx_source"] = (
            "event_timestamp_to_csv" if csv_i is not None else "UNRESOLVED"
        )
        if rec.get("outcome") == "UNKNOWN":
            rec["outcome"] = "CLEARED_OR_OVERWRITTEN"
        out.append(rec)
    return out


def load_bar_features() -> dict[int, dict]:
    cglob = (
        str((_RUN_DIR / "XAUUSD_crt_construction.parquet").resolve()).replace("\\", "/")
        + "/**/*.parquet"
    )
    bglob = (
        str((_RUN_DIR / "XAUUSD_bar_structure.parquet").resolve()).replace("\\", "/")
        + "/**/*.parquet"
    )
    con = open_views({"crt": cglob, "bar": bglob})
    df = con.execute(
        """
        SELECT
          c.bar_index,
          c.ontology_state,
          c.engine_state_after,
          c."engine.live_context.live_atr" AS live_atr,
          c."resolver.feature_vector.trend_bias" AS trend_bias,
          c."resolver.feature_vector.ema_spread" AS ema_spread,
          c."resolver.feature_vector.momentum_score" AS momentum_score,
          c."resolver.feature_vector.body_ratio" AS body_ratio,
          c."resolver.feature_vector.body_size" AS body_size,
          c."resolver.feature_vector.candle_range" AS candle_range,
          c."resolver.feature_vector.hour_of_day" AS hour_of_day,
          c."resolver.feature_vector.session" AS session,
          c."resolver.feature_vector.atr" AS atr_rel,
          c."resolver.feature_vector.pdh_distance" AS pdh_distance,
          c."resolver.feature_vector.pdl_distance" AS pdl_distance,
          c."resolver.feature_vector.order_block_distance" AS order_block_distance,
          c."resolver.feature_vector.close" AS close,
          b.crt_direction,
          b.parent_crt_state,
          b.parent_bias,
          b.htf_state,
          b.crt_range_h_ref,
          b.crt_range_l_ref,
          b.crt_range_size,
          b.htf_candle_id
        FROM crt c
        LEFT JOIN bar b ON c.bar_index = b.bar_index
        WHERE c.phase = 'LIVE'
        """
    ).fetchdf()
    con.close()
    out: dict[int, dict] = {}
    for rec in df.to_dict("records"):
        out[int(rec["bar_index"])] = rec
    return out


def _finite(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def attach_features(row: dict, feat: Optional[dict]) -> None:
    if not feat:
        row["feature_status"] = "NO_PARQUET_ROW"
        return
    row["feature_status"] = "OK"
    row["t1_state"] = feat.get("ontology_state")  # resolver
    row["t3_state"] = feat.get("engine_state_after")  # engine
    t1, t3 = row["t1_state"], row["t3_state"]
    if t1 is None or t3 is None:
        row["t1_t3"] = "UNAVAILABLE"
    elif t1 == t3:
        row["t1_t3"] = "AGREE"
    else:
        row["t1_t3"] = "DISAGREE"
    row["parent_crt"] = feat.get("parent_crt_state") or "UNAVAILABLE"
    row["parent_bias"] = feat.get("parent_bias")
    row["htf_state"] = feat.get("htf_state")
    row["live_atr"] = _finite(feat.get("live_atr"))
    row["trend_bias"] = _finite(feat.get("trend_bias"))
    row["trendbias_dir"] = _tb_dir(row["trend_bias"])
    row["ema_spread"] = _finite(feat.get("ema_spread"))
    row["momentum_score"] = _finite(feat.get("momentum_score"))
    row["body_ratio"] = _finite(feat.get("body_ratio"))
    br = row["body_ratio"]
    row["wick_to_range"] = None if br is None else round(1.0 - br, 6)
    row["hour_of_day"] = _finite(feat.get("hour_of_day"))
    row["session_code"] = _finite(feat.get("session"))
    row["session_bucket"] = _hour_bucket(row["hour_of_day"])
    row["pdh_distance"] = _finite(feat.get("pdh_distance"))
    row["pdl_distance"] = _finite(feat.get("pdl_distance"))
    row["order_block_distance"] = _finite(feat.get("order_block_distance"))
    close = _finite(feat.get("close"))
    lo = _finite(feat.get("crt_range_l_ref"))
    sz = _finite(feat.get("crt_range_size"))
    if close is not None and lo is not None and sz and sz > 0:
        row["range_position"] = round((close - lo) / sz, 6)
    else:
        row["range_position"] = None
    row["atr_rel"] = _finite(feat.get("atr_rel"))


def _net(
    corpus: list[dict],
    bar_index: int,
    direction: Optional[str],
    atr: Optional[float],
    horizon: int,
    cost_model: ComponentCostModel,
) -> Optional[float]:
    if direction not in ("LONG", "SHORT") or not atr or atr <= 0:
        return None
    gross = close_at_horizon(corpus, bar_index, direction, atr, horizon)
    if gross is None:
        return None
    side = "long" if direction == "LONG" else "short"
    cost_r = cost_model.cost_price(exit_kind="TIMEOUT", direction=side, nights_held=0) / atr
    return gross - cost_r


def _mfe_mae(corpus: list[dict], bar_index: int, direction: Optional[str], atr: Optional[float], horizon: int):
    if direction not in ("LONG", "SHORT") or not atr or atr <= 0:
        return None, None
    ex = excursion(corpus, bar_index, atr, horizon)
    if ex is None:
        return None, None
    if direction == "LONG":
        return ex["up"], ex["down"]
    return ex["down"], ex["up"]


def bucket_table(rows: list[dict], key: str, dir_key: str, h: int = 20) -> list[dict]:
    groups: dict[str, list[float]] = defaultdict(list)
    al_groups: dict[str, list[float]] = defaultdict(list)
    net_key = f"{dir_key}_H{h}"
    al_key = f"always_long_H{h}"
    for r in rows:
        b = r.get(key)
        if b is None or b == "":
            b = "UNAVAILABLE"
        b = str(b)
        nv = r.get(net_key)
        av = r.get(al_key)
        if nv is not None:
            groups[b].append(nv)
        if av is not None:
            al_groups[b].append(av)
    out = []
    for b in sorted(groups, key=lambda x: (-len(groups[x]), x)):
        mem = _score(groups[b])
        al = _score(al_groups.get(b, []))
        lift = None
        if mem["expectancy"] is not None and al["expectancy"] is not None:
            lift = round(mem["expectancy"] - al["expectancy"], 6)
        out.append(
            {
                "feature": key,
                "bucket": b,
                "n": mem["n"],
                "E": mem["expectancy"],
                "PF": mem["PF"],
                "win_rate": mem["win_rate"],
                "E_always_long": al["expectancy"],
                "lift_vs_al": lift,
                "power": mem["power"],
            }
        )
    return out


def _md_table(rows: list[dict], title: str) -> list[str]:
    lines = [f"## {title}", "", "| Feature | Bucket | n | E | E_AL | lift | PF | WR | power |",
             "|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for r in rows:
        e = "n/a" if r["E"] is None else f"{r['E']:+.4f}"
        ea = "n/a" if r["E_always_long"] is None else f"{r['E_always_long']:+.4f}"
        lf = "n/a" if r["lift_vs_al"] is None else f"{r['lift_vs_al']:+.4f}"
        pf = "n/a" if r["PF"] is None else f"{r['PF']:.3f}"
        wr = "n/a" if r["win_rate"] is None else f"{r['win_rate']:.3f}"
        lines.append(
            f"| {r['feature']} | {r['bucket']} | {r['n']} | {e} | {ea} | {lf} | {pf} | {wr} | {r['power']} |"
        )
    lines.append("")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-run-id", default=SESSION_BIND)
    args = ap.parse_args()
    session_run = args.session_run_id

    if not _MS.is_file() or not _CSV.is_file() or not _MANIFEST.is_file():
        print("BLOCKER: missing memory_subsystem / csv / SEM-015 manifest")
        return 2
    try:
        cost_model = ComponentCostModel.from_manifest(
            json.loads(_MANIFEST.read_text(encoding="utf-8")),
            instrument="XAUUSD",
            source=_MANIFEST.name,
        )
    except UnmeasuredCostError as exc:
        print(f"BLOCKER: {exc}")
        return 2

    ms = json.loads(_MS.read_text(encoding="utf-8"))
    ce = json.loads(_CE.read_text(encoding="utf-8")) if _CE.is_file() else {}
    funnel = (ce.get("funnel_crosscheck") or ms.get("funnel") or {})
    creates = assemble_creates(ms, ce)
    print(f"assembled creates: {len(creates)} (funnel n={funnel.get('n_memories_created')})")
    oc = Counter(c.get("outcome") for c in creates)
    print("outcomes", dict(oc))
    if len(creates) != 69:
        print(f"BLOCKER: expected 69 creates, got {len(creates)} — refuse to score a partial funnel")
        return 2
    n_unresolved = sum(
        1 for c in creates if c.get("created_idx_source") != "event_timestamp_to_csv"
    )
    if n_unresolved:
        print(f"BLOCKER: {n_unresolved}/69 CREATE timestamps failed CSV join")
        return 2
    offsets = []
    for c in creates:
        try:
            offsets.append(int(c["created_idx"]) - int(c["engine_candle_index"]))
        except (TypeError, ValueError):
            print("BLOCKER: missing created_idx or engine_candle_index after timestamp join")
            return 2
    if not offsets or any(o != offsets[0] for o in offsets):
        print(f"BLOCKER: csv-minus-engine offset not constant: {Counter(offsets)}")
        return 2
    print(
        f"timestamp→CSV join: 69/69 resolved, offset_csv_minus_engine={offsets[0]} "
        f"(engine_candle_index kept; age_at_reset stays engine-domain)"
    )

    print("loading dual-construction features...")
    feats = load_bar_features()
    corpus = load_corpus(_CSV)

    atrs = []
    for c in creates:
        idx = int(c["created_idx"])
        attach_features(c, feats.get(idx))
        if c.get("pending_dir") not in ("LONG", "SHORT"):
            prev = feats.get(idx - 1) or {}
            d = prev.get("crt_direction")
            if d in ("LONG", "SHORT"):
                c["pending_dir"] = d
                c["pending_dir_source"] = "bar_structure.crt_direction_at_created_idx_minus_1"
        # formed_idx / age_at_reset stay engine-domain (overlay). Do not walk
        # parquet DISPLACEMENT occupancy with CSV created_idx — that mixes clocks.
        if c.get("live_atr"):
            atrs.append(c["live_atr"])
    atrs_sorted = sorted(atrs)
    def pct_rank(x):
        if not atrs_sorted or x is None:
            return None
        return round(100.0 * sum(1 for a in atrs_sorted if a <= x) / len(atrs_sorted), 2)
    for c in creates:
        c["atr_percentile_among_creates"] = pct_rank(c.get("live_atr"))
        apct = c["atr_percentile_among_creates"]
        if apct is None:
            c["atr_tercile"] = "UNAVAILABLE"
        elif apct <= 33.333:
            c["atr_tercile"] = "T1_LOW"
        elif apct <= 66.666:
            c["atr_tercile"] = "T2_MID"
        else:
            c["atr_tercile"] = "T3_HIGH"

    print("scoring H20..H100 ...")
    for c in creates:
        idx = int(c["created_idx"])
        atr = c.get("live_atr")
        md = c.get("pending_dir")
        td = c.get("trendbias_dir")
        for H in HORIZONS:
            c[f"memory_dir_H{H}"] = _net(corpus, idx, md, atr, H, cost_model)
            c[f"trendbias_dir_H{H}"] = _net(corpus, idx, td, atr, H, cost_model)
            c[f"always_long_H{H}"] = _net(corpus, idx, "LONG", atr, H, cost_model)
            mfe, mae = _mfe_mae(corpus, idx, md, atr, H)
            c[f"memory_mfe_H{H}"] = None if mfe is None else round(mfe, 6)
            c[f"memory_mae_H{H}"] = None if mae is None else round(mae, 6)

    # headline H20 arms on the 69
    def col(key):
        return [c[key] for c in creates if c.get(key) is not None]

    headline = {
        "memory_dir": _score(col("memory_dir_H20")),
        "trendbias_dir": _score(col("trendbias_dir_H20")),
        "always_long": _score(col("always_long_H20")),
    }

    tables = {
        "age_at_reset_bucket": bucket_table(creates, "age_at_reset_bucket", "memory_dir"),
        "pending_dir": bucket_table(creates, "pending_dir", "memory_dir"),
        "parent_crt": bucket_table(creates, "parent_crt", "memory_dir"),
        "session_bucket": bucket_table(creates, "session_bucket", "memory_dir"),
        "t1_t3": bucket_table(creates, "t1_t3", "memory_dir"),
        "outcome": bucket_table(creates, "outcome", "memory_dir"),
        "atr_tercile": bucket_table(creates, "atr_tercile", "memory_dir"),
    }
    ranked = []
    for rows in tables.values():
        ranked.extend(rows)
    ranked = [r for r in ranked if r["n"] >= 5 and r["lift_vs_al"] is not None]
    ranked.sort(key=lambda r: r["lift_vs_al"], reverse=True)

    out_dir = _ROOT / "results/analysis/phase1_resolver_replay" / session_run / "create_economic_census"
    out_dir.mkdir(parents=True, exist_ok=True)

    artifact = {
        "artifact": "phase1_shadow_create_economic_census",
        "session_run_id": session_run,
        "source_run_id": SOURCE_RUN,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_class": "DESCRIPTIVE_ONLY",
        "economic_claims_allowed": False,
        "authority": "none",
        "object": (
            "HTF_CHANGED_WHILE_DISPLACEMENT pending-memory CREATE. "
            "Unit=CREATE not RESTORE. n=69."
        ),
        "funnel": {
            "CREATE": 69,
            "EXPIRE_TTL": 45,
            "CLEAR_NON_HTF": 17,
            "RESTORE": 6,
            "OVERWRITE": 1,
            "assembled_outcomes": dict(oc),
        },
        "not_the_question": "find more restores / widen years / widen instruments",
        "headline_H20": headline,
        "bucket_tables_H20_memory_dir": tables,
        "ranked_lift_n_ge_5": ranked,
        "unavailable": {
            "atr_percentile": "no FM percentile on the vector; used rank among the 69 creates",
            "wick_ratio": "no FM wick_ratio; emitted wick_to_range = 1 - body_ratio (diagnostic)",
            "SEM_star": "SEM-* nodes are not per-bar on the dual-construction row",
            "FM_star_full": "full 48-dim vector is on the parquet; this census scores the named bundle",
        },
        "provenance": {
            **_git(),
            "csv_sha256": _sha256_file(_CSV),
            "cost": cost_model.provenance(),
            "memory_subsystem": str(_MS),
            "probe_funnel": funnel,
        },
        "rows": creates,
        "index_join": {
            "four_arm_path": "CSV_PARQUET_BAR_INDEX",
            "create_census_join": "EVENT_TIMESTAMP_TO_CSV",
            "same_defect_as_registry_has": "create_census_context_join was ENGINE_CANDLE_INDEX_PLUS_62 before this rebuild",
            "offset_csv_minus_engine": offsets[0],
            "n_creates_offset_checked": 69,
            "offset_constant": True,
            "funnel_counts": "VALID",
            "rebuild_completed": True,
            "created_idx_source": "event_timestamp_to_csv",
            "age_at_reset": "engine_domain_delta",
            "do_not_infer": [],
        },
    }
    assert_no_claim_keys(artifact)
    json_path = out_dir / "census.json"
    json_path.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

    md = [
        "# Phase-1 shadow CREATE economic census",
        "",
        f"**session_run_id:** `{session_run}`",
        f"**source_run_id:** `{SOURCE_RUN}`",
        "",
        "**Claim class:** DESCRIPTIVE_ONLY · `economic_claims_allowed: false` · no promotion",
        "",
        "**REBUILT 2026-09-10 — timestamp→CSV join.** `created_idx` is event timestamp → CSV/parquet `bar_index`. Funnel 69/45/18/6 unchanged. `engine_candle_index` kept; `age_at_reset` is engine-domain. Load first: `docs/research/phase1_run_20260909_202201_coding_llm_context.yaml`.",
        "",
        "Unit = **CREATE** of HTF-displacement pending memory (n=69), not SHADOW→EXP restore (n=6).",
        "Restore rate given SHADOW_PENDING is already 6/6. Do not optimize that branch.",
        "",
        "## Funnel",
        "",
        "```",
        "69 CREATE",
        "├─ 45 EXPIRE",
        "├─ 17 CLEAR",
        "└─ 6 RESTORE → EXPANSION",
        "```",
        "",
        f"Assembled outcomes: `{dict(oc)}`",
        "",
        "## Headline H20 on all 69 creates",
        "",
        "| Arm | n | E | PF | WR | power |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, s in headline.items():
        e = "n/a" if s["expectancy"] is None else f"{s['expectancy']:+.4f}"
        pf = "n/a" if s["PF"] is None else f"{s['PF']:.3f}"
        wr = "n/a" if s["win_rate"] is None else f"{s['win_rate']:.3f}"
        md.append(f"| {name} | {s['n']} | {e} | {pf} | {wr} | {s['power']} |")
    md += ["", "Lift is E(memory_dir | bucket) − E(always_long | same bars).", ""]
    for key, title in (
        ("age_at_reset_bucket", "age_at_reset"),
        ("pending_dir", "pending_dir"),
        ("parent_crt", "parent CRT"),
        ("session_bucket", "session"),
        ("t1_t3", "T1/T3 agree vs disagree"),
        ("outcome", "funnel outcome (diagnostic, not a selector)"),
        ("atr_tercile", "ATR tercile among creates"),
    ):
        md.extend(_md_table(tables[key], title))
    md += [
        "## Ranked lift (n≥5, H20, memory_dir vs always_long on the same creates)",
        "",
        "| Feature | Bucket | n | lift | E | E_AL |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in ranked[:20]:
        md.append(
            f"| {r['feature']} | {r['bucket']} | {r['n']} | "
            f"{r['lift_vs_al']:+.4f} | {r['E']:+.4f} | {r['E_always_long']:+.4f} |"
        )
    md += [
        "",
        "No bucket is a promotion. n=69 total; most cells are INSUFFICIENT.",
        "",
        f"JSON: `{json_path.relative_to(_ROOT).as_posix()}`",
        "",
    ]
    md_path = out_dir / "census.md"
    md_text = "\n".join(md)
    md_path.write_text(md_text, encoding="utf-8")
    _NOTE.write_text(md_text, encoding="utf-8")

    print("\n=== HEADLINE H20 (n=69 CREATE) ===")
    print(f"{'arm':16s} {'n':>4s} {'E':>10s} {'PF':>8s} {'WR':>8s}")
    for name, s in headline.items():
        e = f"{s['expectancy']:+.4f}" if s["expectancy"] is not None else "n/a"
        pf = f"{s['PF']:.3f}" if s["PF"] is not None else "n/a"
        wr = f"{100*s['win_rate']:.1f}%" if s["win_rate"] is not None else "n/a"
        print(f"{name:16s} {s['n']:4d} {e:>10s} {pf:>8s} {wr:>8s}")
    print("\n=== age_at_reset ===")
    for r in tables["age_at_reset_bucket"]:
        print(f"  {r['bucket']:>4s} n={r['n']:2d} E={r['E']} lift={r['lift_vs_al']}")
    print("=== pending_dir ===")
    for r in tables["pending_dir"]:
        print(f"  {r['bucket']:6s} n={r['n']:2d} E={r['E']} lift={r['lift_vs_al']}")
    print("=== parent_crt ===")
    for r in tables["parent_crt"]:
        print(f"  {r['bucket']:16s} n={r['n']:2d} E={r['E']} lift={r['lift_vs_al']}")
    print("=== session ===")
    for r in tables["session_bucket"]:
        print(f"  {r['bucket']:24s} n={r['n']:2d} E={r['E']} lift={r['lift_vs_al']}")
    print("=== T1/T3 ===")
    for r in tables["t1_t3"]:
        print(f"  {r['bucket']:12s} n={r['n']:2d} E={r['E']} lift={r['lift_vs_al']}")
    print(f"\nJSON {json_path}")
    print("DESCRIPTIVE ONLY — economic_claims_allowed=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
