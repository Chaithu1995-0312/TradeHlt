"""phase1_shadow_memory_timing_race_mine.py

DESCRIPTIVE ONLY. economic_claims_allowed=false.
No TTL flip. No freeze work. No economic promotion.

Binary event: matching same-dir sweep arrives in live TTL window vs never
(for HTF_CHANGED_WHILE_DISPLACEMENT → pending memory → RANGE → TTL=4 path).

Mines prior artifacts + probe events.jsonl SWEEP / STATE_TRANSITION records.
Does not invent sweep proxies; uses engine-emitted SWEEP events and
SHADOW_PENDING transitions (confirming same-dir path does not emit SWEEP).
"""
from __future__ import annotations

import json
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(r"D:\Tradelatest")
_CENSUS = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "event_census"
_OUT_JSON = _CENSUS / "memory_timing_race.json"
_OUT_MD = _CENSUS / "memory_timing_race.md"
_NOTE = _ROOT / "docs" / "research" / "phase1_shadow_memory_timing_race_note.md"
_EVENTS = (
    _ROOT
    / "results"
    / "analysis"
    / "phase1_resolver_replay"
    / "memory_subsystem_probe_run"
    / "run_20260910_010142_XAUUSD"
    / "XAUUSD_events.jsonl"
)
_CREATE_EXPIRE = _CENSUS / "memory_create_expire.json"
_MEMORY_SUB = _CENSUS / "memory_subsystem.json"
_STRUCTURE = _CENSUS / "structure_context.json"
_COLLAPSES = _ROOT / "results" / "analysis" / "phase1_resolver_replay" / "collapses.json"

IST = timezone(timedelta(hours=5, minutes=30))
POST_EXPIRY_HORIZON = 4  # bars after expire_idx inclusive of expire_idx? we use expire_idx..+H


def _bucket(hour: int) -> str:
    if 0 <= hour < 8:
        return "ASIA_0_8"
    if 8 <= hour < 13:
        return "LONDON_8_13"
    if 13 <= hour < 17:
        return "LONDON_NY_OVERLAP_13_17"
    if 17 <= hour < 22:
        return "NY_17_22"
    return "OFFHOURS_22_24"


def _ctr(xs):
    return dict(Counter(xs))


def _load_events(path: Path):
    sweeps = []  # {idx, dir, ts}
    transitions = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            ev = o.get("event")
            idx = o.get("candle_index")
            if ev == "SWEEP":
                sweeps.append(
                    {
                        "candle_index": idx,
                        "direction": o.get("direction"),
                        "timestamp": o.get("timestamp"),
                        "price": o.get("price"),
                    }
                )
            elif ev == "STATE_TRANSITION":
                transitions.append(
                    {
                        "candle_index": idx,
                        "state_from": o.get("state_from"),
                        "state_to": o.get("state_to"),
                        "direction": o.get("direction"),
                        "timestamp": o.get("timestamp"),
                        "reason": o.get("reason"),
                    }
                )
    sweeps_by_idx = defaultdict(list)
    for s in sweeps:
        sweeps_by_idx[s["candle_index"]].append(s)
    return sweeps, sweeps_by_idx, transitions


def _sweeps_in_range(sweeps_by_idx, lo, hi_exclusive, pending_dir):
    """Count engine SWEEP events on bars [lo, hi_exclusive)."""
    same = []
    opp = []
    other = []
    for idx in range(lo, hi_exclusive):
        for s in sweeps_by_idx.get(idx, []):
            d = s["direction"]
            if d == pending_dir:
                same.append({"candle_index": idx, "direction": d, "timestamp": s["timestamp"]})
            elif d in ("LONG", "SHORT") and d != pending_dir:
                opp.append({"candle_index": idx, "direction": d, "timestamp": s["timestamp"]})
            else:
                other.append({"candle_index": idx, "direction": d, "timestamp": s["timestamp"]})
    return same, opp, other


def _classify_near_miss(live_same, live_opp, expire_same, expire_opp, post_same, post_opp):
    """Descriptive near-miss class for expire cohort (no matching live same-dir confirm)."""
    # Priority: wrong-dir during live > same-dir on/after expire bar > opp after > none
    tags = []
    if live_opp:
        tags.append("OPPOSITE_DIR_SWEEP_DURING_LIVE_TTL")
    if live_same:
        # Unexpected if true for expire cohort — engine should have restored
        tags.append("SAME_DIR_SWEEP_EVENT_DURING_LIVE_TTL_UNEXPECTED")
    if expire_same:
        tags.append("SAME_DIR_SWEEP_ON_EXPIRE_BAR_AFTER_TTL_CLEAR")
    if expire_opp:
        tags.append("OPPOSITE_DIR_SWEEP_ON_EXPIRE_BAR")
    if post_same:
        tags.append("SAME_DIR_SWEEP_AFTER_EXPIRY_WITHIN_HORIZON")
    if post_opp and not expire_opp:
        tags.append("OPPOSITE_DIR_SWEEP_AFTER_EXPIRY_WITHIN_HORIZON")
    if not tags:
        tags.append("NO_ENGINE_SWEEP_IN_LIVE_OR_POST_HORIZON")
    return tags


def main():
    ce = json.loads(_CREATE_EXPIRE.read_text(encoding="utf-8"))
    ms = json.loads(_MEMORY_SUB.read_text(encoding="utf-8"))
    try:
        st = json.loads(_STRUCTURE.read_text(encoding="utf-8"))
    except Exception:
        st = None
    try:
        collapses = json.loads(_COLLAPSES.read_text(encoding="utf-8"))
    except Exception:
        collapses = None

    expire_rows = ce["q2_expire_45_distribution"]["expire_rows"]
    restore_rows = ce["restore_rows_enriched"]
    shadow_recs = {r["memory_id"]: r for r in ms["shadow_pending_records"]}

    sweeps, sweeps_by_idx, transitions = _load_events(_EVENTS)

    # Map restore collapse/shadow indices
    shadow_by_mem = {r["memory_id"]: r for r in ms["shadow_pending_records"]}

    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    # Engine order citation (descriptive)
    engine_order = {
        "file": "src/config_layer/crt_engine_v2.py",
        "RANGE_branch_order": [
            "1_decrement_pending_displacement_ttl (skip created_idx bar)",
            "2_if_ttl_hits_0_clear_pending_displacement_candle/dir",
            "3_detect_sweep",
            "4_if_pending_candle_and_sweep.dir==pending_dir → SHADOW_PENDING (no SWEEP event)",
            "5_else_if_sweep → record SWEEP event + try_range_to_sweep",
        ],
        "implication": (
            "On the expire bar (ttl 1→0) memory is cleared BEFORE sweep detect; "
            "a same-dir sweep on expire_idx cannot restore. Confirming same-dir "
            "sweeps on live bars take SHADOW path and do not emit SWEEP events."
        ),
        "live_window_definition": (
            "For TTL=4 expire with expire_idx=created_idx+4: live usable bars are "
            "[created_idx, expire_idx) i.e. created_idx .. created_idx+3 inclusive. "
            "expire_idx is post-clear for shadow purposes."
        ),
    }

    expire_analyzed = []
    for er in expire_rows:
        mid = er["memory_id"]
        pending_dir = er["direction"]
        created = er["created_idx"]
        expire_idx = er["expire_idx"]
        # live window [created, expire)
        live_lo, live_hi = created, expire_idx
        live_same, live_opp, live_other = _sweeps_in_range(
            sweeps_by_idx, live_lo, live_hi, pending_dir
        )
        # expire bar itself
        exp_same, exp_opp, exp_other = _sweeps_in_range(
            sweeps_by_idx, expire_idx, expire_idx + 1, pending_dir
        )
        # post horizon: expire_idx+1 .. expire_idx+POST_EXPIRY_HORIZON inclusive
        post_lo = expire_idx + 1
        post_hi = expire_idx + 1 + POST_EXPIRY_HORIZON
        post_same, post_opp, post_other = _sweeps_in_range(
            sweeps_by_idx, post_lo, post_hi, pending_dir
        )
        # also include expire bar same-dir in "after expiry" aggregate
        after_same = exp_same + post_same
        after_opp = exp_opp + post_opp

        tags = _classify_near_miss(
            live_same, live_opp, exp_same, exp_opp, post_same, post_opp
        )

        # STATE_TRANSITION during live window (did anything leave RANGE?)
        live_trans = [
            t
            for t in transitions
            if t["candle_index"] is not None
            and live_lo <= t["candle_index"] < live_hi
        ]
        leave_range = [
            t
            for t in live_trans
            if t.get("state_from") == "RANGE" and t.get("state_to") not in (None, "RANGE")
        ]

        expire_analyzed.append(
            {
                "cohort": "EXPIRE_TTL",
                "memory_id": mid,
                "pending_dir": pending_dir,
                "age_at_reset": er["age_at_reset"],
                "source_htf": er["source_htf"],
                "session_hour_bucket_broker_local": er["session_hour_bucket_broker_local"],
                "hour_broker_local": er["hour_broker_local"],
                "created_idx": created,
                "expire_idx": expire_idx,
                "formed_idx": er["formed_idx"],
                "bars_since_created": er["bars_since_created"],
                "ttl_was": er["ttl_was"],
                "pre_state": er["pre_state"],
                "live_window": [live_lo, live_hi],
                "live_window_bars": list(range(live_lo, live_hi)),
                "n_live_same_dir_SWEEP_events": len(live_same),
                "n_live_opposite_dir_SWEEP_events": len(live_opp),
                "n_expire_bar_same_dir_SWEEP": len(exp_same),
                "n_expire_bar_opposite_dir_SWEEP": len(exp_opp),
                "n_post_horizon_same_dir_SWEEP": len(post_same),
                "n_post_horizon_opposite_dir_SWEEP": len(post_opp),
                "n_after_expiry_incl_expire_bar_same_dir": len(after_same),
                "n_after_expiry_incl_expire_bar_opposite_dir": len(after_opp),
                "live_same_dir_events": live_same,
                "live_opposite_dir_events": live_opp,
                "expire_bar_sweeps": exp_same + exp_opp + exp_other,
                "post_horizon_sweeps": post_same + post_opp + post_other,
                "near_miss_tags": tags,
                "n_state_transitions_in_live_window": len(live_trans),
                "n_leave_RANGE_in_live_window": len(leave_range),
                "leave_RANGE_in_live_window": leave_range[:10],
                "htf_class": "UNAVAILABLE_BEYOND_SOURCE_HTF_ID",
                "parent_crt": "UNAVAILABLE_IN_EXPIRE_PROBE_RECORDS",
            }
        )

    restore_analyzed = []
    for rr in restore_rows:
        mid = rr["memory_id"]
        pending_dir = rr["direction"]
        created = rr["created_idx"]
        shadow = shadow_by_mem.get(mid, {})
        shadow_idx = shadow.get("shadow_pending_idx")
        collapse_idx = rr["collapse_idx"]
        # live window until confirming shadow bar inclusive for restore path
        # usable bars [created, shadow_idx] inclusive; confirming bar takes SHADOW path
        if shadow_idx is None:
            live_lo, live_hi_excl = created, collapse_idx + 1
            confirm_idx = collapse_idx
        else:
            live_lo, live_hi_excl = created, shadow_idx  # sweeps before confirm
            confirm_idx = shadow_idx

        live_same, live_opp, live_other = _sweeps_in_range(
            sweeps_by_idx, live_lo, live_hi_excl, pending_dir
        )
        # confirming bar: expect NO SWEEP event (SHADOW path)
        conf_same, conf_opp, conf_other = _sweeps_in_range(
            sweeps_by_idx, confirm_idx, confirm_idx + 1, pending_dir
        )

        restore_analyzed.append(
            {
                "cohort": "RESTORE",
                "memory_id": mid,
                "pending_dir": pending_dir,
                "age_at_reset": rr["age_at_reset"],
                "source_htf": rr["source_htf"],
                "session_hour_bucket_broker_local": rr["session_hour_bucket_broker_local"],
                "hour_broker_local": rr["hour_broker_local"],
                "created_idx": created,
                "shadow_pending_idx": shadow_idx,
                "collapse_idx": collapse_idx,
                "formed_idx": rr["formed_idx"],
                "bars_since_memory_created": rr["bars_since_memory_created"],
                "ttl_remaining_at_restore": rr["ttl_remaining_at_restore"],
                "live_window_before_confirm": [live_lo, live_hi_excl],
                "n_live_same_dir_SWEEP_events_before_confirm": len(live_same),
                "n_live_opposite_dir_SWEEP_events_before_confirm": len(live_opp),
                "confirm_bar_has_SWEEP_event": bool(conf_same or conf_opp or conf_other),
                "confirm_bar_SWEEP_events": conf_same + conf_opp + conf_other,
                "matching_confirm_via": "STATE_TRANSITION_RANGE_TO_SHADOW_PENDING",
                "sweep_dir_at_shadow": shadow.get("sweep_dir"),
                "pending_dir_at_shadow": shadow.get("pending_dir"),
                "dirs_match_at_shadow": shadow.get("sweep_dir") == shadow.get("pending_dir"),
                "parent_crt": rr.get("parent_crt"),
                "htf_class": (
                    rr.get("parent_crt", {}).get("htf_state")
                    if isinstance(rr.get("parent_crt"), dict)
                    else "UNAVAILABLE"
                ),
            }
        )

    # Contingency tables
    def cohort_table(rows, key):
        return {
            "RESTORE": _ctr([r[key] for r in restore_analyzed]),
            "EXPIRE_TTL": _ctr([r[key] for r in expire_analyzed]),
        }

    # Near-miss summary for expires
    tag_ctr = Counter()
    for r in expire_analyzed:
        for t in r["near_miss_tags"]:
            tag_ctr[t] += 1

    # Primary mutual-exclusive near-miss class (priority order)
    primary_classes = []
    for r in expire_analyzed:
        tags = r["near_miss_tags"]
        if "SAME_DIR_SWEEP_EVENT_DURING_LIVE_TTL_UNEXPECTED" in tags:
            primary = "UNEXPECTED_LIVE_SAME_DIR_SWEEP_EVENT"
        elif "OPPOSITE_DIR_SWEEP_DURING_LIVE_TTL" in tags:
            primary = "WRONG_DIR_SWEEP_DURING_LIVE_TTL"
        elif "SAME_DIR_SWEEP_ON_EXPIRE_BAR_AFTER_TTL_CLEAR" in tags:
            primary = "SAME_DIR_ON_EXPIRE_BAR_TOO_LATE"
        elif "SAME_DIR_SWEEP_AFTER_EXPIRY_WITHIN_HORIZON" in tags:
            primary = "SAME_DIR_AFTER_EXPIRY_WITHIN_HORIZON"
        elif "OPPOSITE_DIR_SWEEP_ON_EXPIRE_BAR" in tags or "OPPOSITE_DIR_SWEEP_AFTER_EXPIRY_WITHIN_HORIZON" in tags:
            primary = "ONLY_OPPOSITE_DIR_AROUND_EXPIRY"
        else:
            primary = "NO_SWEEP_IN_LIVE_OR_POST_HORIZON"
        r["primary_near_miss_class"] = primary
        primary_classes.append(primary)

    primary_ctr = _ctr(primary_classes)

    # Cross: pending_dir x outcome
    dir_outcome = {
        "RESTORE": _ctr([r["pending_dir"] for r in restore_analyzed]),
        "EXPIRE_TTL": _ctr([r["pending_dir"] for r in expire_analyzed]),
    }
    age_outcome = {
        "RESTORE": _ctr([r["age_at_reset"] for r in restore_analyzed]),
        "EXPIRE_TTL": _ctr([r["age_at_reset"] for r in expire_analyzed]),
    }
    sess_outcome = {
        "RESTORE": _ctr([r["session_hour_bucket_broker_local"] for r in restore_analyzed]),
        "EXPIRE_TTL": _ctr([r["session_hour_bucket_broker_local"] for r in expire_analyzed]),
    }

    # age_at_reset x near-miss primary among expires
    age_x_near = defaultdict(Counter)
    for r in expire_analyzed:
        age_x_near[r["age_at_reset"]][r["primary_near_miss_class"]] += 1
    age_x_near = {str(k): dict(v) for k, v in sorted(age_x_near.items())}

    dir_x_near = defaultdict(Counter)
    for r in expire_analyzed:
        dir_x_near[r["pending_dir"]][r["primary_near_miss_class"]] += 1
    dir_x_near = {k: dict(v) for k, v in dir_x_near.items()}

    sess_x_near = defaultdict(Counter)
    for r in expire_analyzed:
        sess_x_near[r["session_hour_bucket_broker_local"]][r["primary_near_miss_class"]] += 1
    sess_x_near = {k: dict(v) for k, v in sess_x_near.items()}

    # Aggregate sweep counts
    def sum_field(rows, field):
        return sum(r[field] for r in rows)

    expire_sweep_aggs = {
        "n_expire": len(expire_analyzed),
        "sum_live_same_dir_SWEEP_events": sum_field(expire_analyzed, "n_live_same_dir_SWEEP_events"),
        "sum_live_opposite_dir_SWEEP_events": sum_field(
            expire_analyzed, "n_live_opposite_dir_SWEEP_events"
        ),
        "n_expire_with_any_live_SWEEP": sum(
            1
            for r in expire_analyzed
            if r["n_live_same_dir_SWEEP_events"] + r["n_live_opposite_dir_SWEEP_events"] > 0
        ),
        "n_expire_with_same_dir_on_expire_bar": sum(
            1 for r in expire_analyzed if r["n_expire_bar_same_dir_SWEEP"] > 0
        ),
        "n_expire_with_same_dir_in_post_horizon": sum(
            1 for r in expire_analyzed if r["n_post_horizon_same_dir_SWEEP"] > 0
        ),
        "n_expire_with_same_dir_after_incl_expire_bar": sum(
            1
            for r in expire_analyzed
            if r["n_after_expiry_incl_expire_bar_same_dir"] > 0
        ),
        "n_expire_with_leave_RANGE_in_live_window": sum(
            1 for r in expire_analyzed if r["n_leave_RANGE_in_live_window"] > 0
        ),
        "primary_near_miss_class_counts": primary_ctr,
        "all_near_miss_tag_counts": dict(tag_ctr),
        "post_expiry_horizon_bars": POST_EXPIRY_HORIZON,
    }

    restore_sweep_aggs = {
        "n_restore": len(restore_analyzed),
        "sum_live_opposite_dir_SWEEP_before_confirm": sum_field(
            restore_analyzed, "n_live_opposite_dir_SWEEP_events_before_confirm"
        ),
        "n_restore_with_opposite_dir_before_confirm": sum(
            1
            for r in restore_analyzed
            if r["n_live_opposite_dir_SWEEP_events_before_confirm"] > 0
        ),
        "n_confirm_bar_emitted_SWEEP_event": sum(
            1 for r in restore_analyzed if r["confirm_bar_has_SWEEP_event"]
        ),
        "n_dirs_match_at_shadow": sum(
            1 for r in restore_analyzed if r["dirs_match_at_shadow"]
        ),
        "note": (
            "Confirming same-dir sweep is observed as RANGE→SHADOW_PENDING, not as SWEEP event."
        ),
    }

    # HTF class availability
    htf_availability = {
        "restore_parent_htf_state": _ctr(
            [
                r["htf_class"]
                for r in restore_analyzed
                if r["htf_class"] not in (None, "UNAVAILABLE")
            ]
        ),
        "expire_htf_class": "UNAVAILABLE_BEYOND_PER_WINDOW_SOURCE_HTF_ID",
        "expire_n_unique_source_htf": len({r["source_htf"] for r in expire_analyzed}),
        "restore_n_unique_source_htf": len({r["source_htf"] for r in restore_analyzed}),
        "structure_context_coverage": "restores_only_n6",
    }

    unavailable = [
        {
            "field": "expire_parent_crt / parent_track_state / parent_bias / htf_state",
            "status": "UNAVAILABLE",
            "reason": "Prior probe expire records and create_expire census do not attach parent CRT; structure_context.json covers restores only (n=6).",
        },
        {
            "field": "HTF class taxonomy beyond source_htf window id",
            "status": "UNAVAILABLE",
            "reason": "No HTF class collapse in artifacts; each expire has unique source_htf id.",
        },
        {
            "field": "detect_sweep true-negatives / failed detect attempts without SWEEP event",
            "status": "UNAVAILABLE",
            "reason": "events.jsonl only records positive SWEEP emissions and state transitions; G_RANGE_SWEEP_DETECT trace hooks not persisted in this probe run output.",
        },
        {
            "field": "bar-by-bar OHLC reconstruction of sweep proxies independent of engine",
            "status": "NOT_USED",
            "reason": "Task forbids inventing proxies; analysis uses engine SWEEP events + SHADOW_PENDING transitions only.",
        },
        {
            "field": "create_sample reason strings for memory_id>50",
            "status": "PARTIAL",
            "reason": "Prior create_sample capped at 50; sole create gate still HTF_CHANGED_WHILE_DISPLACEMENT for all 69.",
        },
    ]

    # Sanity: binary event statement
    binary = {
        "definition": "matching_sweep_arrives_in_live_TTL_window_vs_never",
        "restore_n": 6,
        "expire_n": 45,
        "restore_all_had_matching_confirm": all(
            r["dirs_match_at_shadow"] for r in restore_analyzed
        ),
        "expire_all_had_zero_live_same_dir_SWEEP_events": all(
            r["n_live_same_dir_SWEEP_events"] == 0 for r in expire_analyzed
        ),
        "expire_all_had_zero_live_opposite_dir_SWEEP_events": all(
            r["n_live_opposite_dir_SWEEP_events"] == 0 for r in expire_analyzed
        ),
        "note": (
            "For expire cohort, absence of SWEEP events in live window means no engine-emitted "
            "sweep (either direction) while memory was still pending. Opposite-dir sweeps would "
            "have emitted SWEEP and left RANGE; confirming same-dir would have entered SHADOW_PENDING."
        ),
    }

    artifact = {
        "artifact": "phase1_shadow_memory_timing_race",
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_ist": now_ist.isoformat(),
        "instrument": ce.get("instrument", "XAUUSD"),
        "csv_sha256": ce.get("csv_sha256"),
        "config_version": ce.get("config_version"),
        "economic_claims_allowed": False,
        "locked_object": ce.get("locked_object"),
        "binary_event_of_interest": binary,
        "engine_order_and_live_window": engine_order,
        "provenance": {
            "mined_from": [
                str(_CREATE_EXPIRE.relative_to(_ROOT)),
                str(_MEMORY_SUB.relative_to(_ROOT)),
                str(_EVENTS.relative_to(_ROOT)),
                str(_STRUCTURE.relative_to(_ROOT)) if _STRUCTURE.exists() else None,
                str(_COLLAPSES.relative_to(_ROOT)) if _COLLAPSES.exists() else None,
            ],
            "full_bt_rerun": False,
            "events_source_run": "memory_subsystem_probe_run/run_20260910_010142_XAUUSD",
            "sweep_detection_basis": "engine_emitted_SWEEP_events_plus_SHADOW_PENDING_transitions",
        },
        "contingency_tables": {
            "pending_dir_x_outcome": dir_outcome,
            "age_at_reset_x_outcome": age_outcome,
            "session_bucket_x_outcome": sess_outcome,
            "expire_age_at_reset_x_primary_near_miss": age_x_near,
            "expire_pending_dir_x_primary_near_miss": dir_x_near,
            "expire_session_x_primary_near_miss": sess_x_near,
            "htf_class": htf_availability,
        },
        "near_miss_findings": {
            "expire_sweep_aggregates": expire_sweep_aggs,
            "restore_sweep_aggregates": restore_sweep_aggs,
            "interpretation_descriptive": [
                "Dominant binary split is restore(6) vs expire(45): matching same-dir confirming sweep in live TTL window vs never.",
                "All 45 expires show zero engine SWEEP events in live window [created_idx, expire_idx) and zero leave-RANGE transitions — consistent with no sweep-like engine event before TTL clear.",
                "Near-miss 'too late' = same-dir SWEEP on expire_idx (after TTL clear) or within post-expiry horizon; see primary_near_miss_class_counts.",
                "Wrong-dir during live TTL would appear as SWEEP events + leave RANGE; count in primary class WRONG_DIR_SWEEP_DURING_LIVE_TTL.",
                "Restores: confirming sweep is SHADOW_PENDING transition; SWEEP event absent on confirm bar by design.",
            ],
        },
        "still_unavailable": unavailable,
        "expire_rows_timing": expire_analyzed,
        "restore_rows_timing": restore_analyzed,
        "authority_disclaimer": {
            "economic_claims_allowed": False,
            "note": (
                "Descriptive timing-race census only. No economic claim, no Case reopen, "
                "no object widening, no freeze mutation, no TTL flip, no economic promotion."
            ),
        },
    }

    _OUT_JSON.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

    # Markdown census
    md = []
    md.append("# Phase-1 shadow memory TIMING-RACE census")
    md.append("")
    md.append(
        f"**Instrument:** XAUUSD  **Config:** {ce.get('config_version')}  "
        f"**CSV SHA256:** {str(ce.get('csv_sha256'))[:16]}…"
    )
    md.append(
        f"**generated_at (UTC):** {now_utc.isoformat()}  (= {now_ist.isoformat()} IST)"
    )
    md.append("**economic_claims_allowed:** False")
    md.append(
        "**full_bt_rerun:** False — mined prior create/expire + memory_subsystem + probe events.jsonl"
    )
    md.append("")
    md.append("## Locked object / binary event")
    md.append("")
    md.append(ce.get("locked_object", ""))
    md.append("")
    md.append(
        "Binary event: **matching same-dir sweep arrives in live TTL window** (→ SHADOW_PENDING → restore) "
        "**vs never** (→ TTL expire on RANGE)."
    )
    md.append("")
    md.append("## Engine order (why expire bar cannot save)")
    md.append("")
    for step in engine_order["RANGE_branch_order"]:
        md.append(f"- {step}")
    md.append("")
    md.append(f"Implication: {engine_order['implication']}")
    md.append("")
    md.append(f"Live window: {engine_order['live_window_definition']}")
    md.append("")
    md.append("## Contingency: pending_dir × outcome")
    md.append("")
    md.append("| pending_dir | RESTORE (6) | EXPIRE_TTL (45) |")
    md.append("|---|---:|---:|")
    for d in sorted(set(dir_outcome["RESTORE"]) | set(dir_outcome["EXPIRE_TTL"])):
        md.append(
            f"| {d} | {dir_outcome['RESTORE'].get(d, 0)} | {dir_outcome['EXPIRE_TTL'].get(d, 0)} |"
        )
    md.append("")
    md.append("## Contingency: age_at_reset × outcome")
    md.append("")
    md.append("| age_at_reset | RESTORE | EXPIRE_TTL |")
    md.append("|---:|---:|---:|")
    ages = sorted(set(age_outcome["RESTORE"]) | set(age_outcome["EXPIRE_TTL"]))
    for a in ages:
        md.append(
            f"| {a} | {age_outcome['RESTORE'].get(a, 0)} | {age_outcome['EXPIRE_TTL'].get(a, 0)} |"
        )
    md.append("")
    md.append("## Contingency: session bucket × outcome")
    md.append("")
    md.append("| session_bucket (broker-local) | RESTORE | EXPIRE_TTL |")
    md.append("|---|---:|---:|")
    for s in sorted(set(sess_outcome["RESTORE"]) | set(sess_outcome["EXPIRE_TTL"])):
        md.append(
            f"| {s} | {sess_outcome['RESTORE'].get(s, 0)} | {sess_outcome['EXPIRE_TTL'].get(s, 0)} |"
        )
    md.append("")
    md.append("## HTF class")
    md.append("")
    md.append(
        f"- Restores parent `htf_state`: `{htf_availability['restore_parent_htf_state']}`"
    )
    md.append(
        f"- Expires HTF class: **{htf_availability['expire_htf_class']}** "
        f"(unique source_htf ids = {htf_availability['expire_n_unique_source_htf']}/45)"
    )
    md.append("")
    md.append("## Near-miss findings (expire n=45)")
    md.append("")
    md.append(
        f"| Aggregate | Value |"
    )
    md.append("|---|---|")
    for k, v in expire_sweep_aggs.items():
        if k in ("primary_near_miss_class_counts", "all_near_miss_tag_counts"):
            continue
        md.append(f"| {k} | `{v}` |")
    md.append("")
    md.append("### Primary near-miss class counts")
    md.append("")
    md.append("| primary_near_miss_class | N |")
    md.append("|---|---:|")
    for k, v in sorted(primary_ctr.items(), key=lambda x: -x[1]):
        md.append(f"| {k} | {v} |")
    md.append("")
    md.append("### Expire: age_at_reset × primary near-miss")
    md.append("")
    md.append("```")
    md.append(json.dumps(age_x_near, indent=2))
    md.append("```")
    md.append("")
    md.append("### Expire: pending_dir × primary near-miss")
    md.append("")
    md.append("```")
    md.append(json.dumps(dir_x_near, indent=2))
    md.append("```")
    md.append("")
    md.append("## Restore-side sweep checks (n=6)")
    md.append("")
    md.append(f"- dirs_match_at_shadow: **{restore_sweep_aggs['n_dirs_match_at_shadow']}/6**")
    md.append(
        f"- confirm bar emitted SWEEP event: **{restore_sweep_aggs['n_confirm_bar_emitted_SWEEP_event']}/6** (expect 0)"
    )
    md.append(
        f"- opposite-dir SWEEP before confirm: **{restore_sweep_aggs['n_restore_with_opposite_dir_before_confirm']}/6**"
    )
    md.append(f"- note: {restore_sweep_aggs['note']}")
    md.append("")
    md.append("## Still UNAVAILABLE")
    md.append("")
    for u in unavailable:
        md.append(f"- **{u['field']}** — `{u['status']}`: {u['reason']}")
    md.append("")
    md.append("## Authority")
    md.append("")
    md.append(artifact["authority_disclaimer"]["note"])
    md.append("")
    _OUT_MD.write_text("\n".join(md), encoding="utf-8")

    # Research note
    note = []
    note.append("# Phase-1 SHADOW memory TIMING-RACE note")
    note.append("")
    note.append(
        "**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · no Case reopen · "
        "no object widening · no freeze work · no TTL flip · no economic promotion"
    )
    note.append("")
    note.append(
        f"**Corpus:** Phase-1 XAUUSD · csv sha256 `{str(ce.get('csv_sha256'))[:16]}…` · "
        f"config `{ce.get('config_version')}`"
    )
    note.append(
        f"**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_timing_race.json`"
    )
    note.append(
        "**Mined from:** prior `memory_create_expire.json` + `memory_subsystem.json` + "
        "probe `XAUUSD_events.jsonl` (no full BT re-run)"
    )
    note.append("")
    note.append("## Locked binary")
    note.append("")
    note.append(
        "HTF_CHANGED_WHILE_DISPLACEMENT → pending memory → RANGE → same-dir sweep before TTL=4 → "
        "restore → EXPANSION. Dominant gate = memory survival. Compare restore(6) vs expire(45)."
    )
    note.append("")
    note.append("## Why 45 expire without matching sweep")
    note.append("")
    note.append(
        f"- Live-window engine SWEEP events (either dir) among expires: "
        f"**{expire_sweep_aggs['sum_live_same_dir_SWEEP_events']} same + "
        f"{expire_sweep_aggs['sum_live_opposite_dir_SWEEP_events']} opposite** "
        f"(rows with any live SWEEP: {expire_sweep_aggs['n_expire_with_any_live_SWEEP']}/45)."
    )
    note.append(
        f"- Leave-RANGE transitions in live window: "
        f"**{expire_sweep_aggs['n_expire_with_leave_RANGE_in_live_window']}/45**."
    )
    note.append(
        "- Interpretation (descriptive): for these 45, no confirming same-dir sweep arrived while "
        "pending memory was still live; TTL countdown on RANGE exhausted to clear."
    )
    note.append("")
    note.append("## Near-miss classes")
    note.append("")
    for k, v in sorted(primary_ctr.items(), key=lambda x: -x[1]):
        note.append(f"- `{k}`: **{v}/45**")
    note.append("")
    note.append(
        f"Same-dir SWEEP on expire bar (after TTL clear, too late by engine order): "
        f"**{expire_sweep_aggs['n_expire_with_same_dir_on_expire_bar']}/45**."
    )
    note.append(
        f"Same-dir SWEEP within +{POST_EXPIRY_HORIZON} bars after expire_idx: "
        f"**{expire_sweep_aggs['n_expire_with_same_dir_in_post_horizon']}/45**."
    )
    note.append(
        f"Same-dir after expiry including expire bar: "
        f"**{expire_sweep_aggs['n_expire_with_same_dir_after_incl_expire_bar']}/45**."
    )
    note.append("")
    note.append("## Restore vs expire concentrations (descriptive)")
    note.append("")
    note.append(
        f"- pending_dir: restores `{dir_outcome['RESTORE']}` vs expires `{dir_outcome['EXPIRE_TTL']}`"
    )
    note.append(
        f"- age_at_reset: restores `{age_outcome['RESTORE']}` vs expires `{age_outcome['EXPIRE_TTL']}`"
    )
    note.append(
        f"- session: restores `{sess_outcome['RESTORE']}` vs expires `{sess_outcome['EXPIRE_TTL']}`"
    )
    note.append(
        "- source_htf / HTF class: expires 45 unique window ids; class taxonomy UNAVAILABLE; "
        f"restores parent htf_state `{htf_availability['restore_parent_htf_state']}`"
    )
    note.append("")
    note.append("## Engine timing note")
    note.append("")
    note.append(
        "RANGE branch decrements TTL then clears pending fields when ttl hits 0 **before** "
        "`detect_sweep`. A same-dir sweep on the expire bar cannot arm SHADOW_PENDING."
    )
    note.append("")
    note.append("## UNAVAILABLE")
    note.append("")
    for u in unavailable:
        note.append(f"- {u['field']}: {u['status']}")
    note.append("")
    note.append("## Non-claims")
    note.append("")
    note.append("- No economic performance claim.")
    note.append("- No recommendation to change TTL.")
    note.append("- No freeze / economic promotion work.")
    note.append(
        "- Session buckets are descriptive broker-local hour bins, not corrected UTC session labels."
    )
    note.append("")
    _NOTE.write_text("\n".join(note), encoding="utf-8")

    print("WROTE", _OUT_JSON)
    print("WROTE", _OUT_MD)
    print("WROTE", _NOTE)
    print("PRIMARY_NEAR_MISS", json.dumps(primary_ctr, indent=2))
    print("BINARY", json.dumps(binary, indent=2))
    print("EXPIRE_AGGS", json.dumps({k: v for k, v in expire_sweep_aggs.items() if not isinstance(v, dict)}, indent=2))
    print("DIR", dir_outcome)
    print("AGE", age_outcome)


if __name__ == "__main__":
    main()
