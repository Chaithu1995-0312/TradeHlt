"""Mine prior memory_subsystem probe artifacts -> create/expire census.
Descriptive only. economic_claims_allowed=false. No BT re-run. No freeze/TTL flip.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] if "__file__" in dir() else Path(r"D:\Tradelatest")
# When run via -c / temp, pin ROOT:
ROOT = Path(r"D:\Tradelatest")
SRC = ROOT / "results/analysis/phase1_resolver_replay/event_census/memory_subsystem.json"
STRUCT = ROOT / "results/analysis/phase1_resolver_replay/event_census/structure_context.json"
OUT_JSON = ROOT / "results/analysis/phase1_resolver_replay/event_census/memory_create_expire.json"
OUT_MD = ROOT / "results/analysis/phase1_resolver_replay/event_census/memory_create_expire.md"
OUT_NOTE = ROOT / "docs/research/phase1_shadow_memory_create_expire_note.md"


def ctr(items):
    return dict(Counter(items))


def parse_ts(ts: str) -> datetime:
    ts = ts.replace("T", " ").split("+")[0].strip()
    return datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")


def hour_bucket(ts: str) -> str:
    """Descriptive broker-local hour bucket (corpus timestamps AS-IS; not UTC-corrected)."""
    h = parse_ts(ts).hour
    if 0 <= h < 8:
        return "ASIA_0_8"
    if 8 <= h < 13:
        return "LONDON_8_13"
    if 13 <= h < 17:
        return "LONDON_NY_OVERLAP_13_17"
    if 17 <= h < 22:
        return "NY_17_22"
    return "OFFHOURS_22_24"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    sc = json.loads(STRUCT.read_text(encoding="utf-8")) if STRUCT.exists() else {}

    creates = d["create_sample"]
    expires = d["expire_sample"]
    restores = d["all_restores"]
    funnel = d["funnel"]

    IST = timezone(timedelta(hours=5, minutes=30))
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc.astimezone(IST)

    reason_class = Counter()
    reason_prefix = Counter()
    for c in creates:
        r = c.get("reason") or ""
        if "HTF" in r and r.startswith("HTF changed"):
            reason_class["HTF_CHANGED_WHILE_DISPLACEMENT"] += 1
            reason_prefix["HTF changed: <old> -> <new>"] += 1
        elif "HTF" in r:
            reason_class["OTHER_HTF_IN_REASON"] += 1
            reason_prefix[r[:60]] += 1
        else:
            reason_class["NON_HTF"] += 1
            reason_prefix[r[:60]] += 1

    create_dirs = ctr(c["direction"] for c in creates)
    create_ttl = ctr(c["ttl_initial"] for c in creates)
    create_age = ctr(c["created_idx"] - c["formed_idx"] for c in creates)

    create_by_id = {c["memory_id"]: c for c in creates}
    expire_derived_creates = []
    for e in expires:
        mid = e["memory_id"]
        if mid not in create_by_id:
            expire_derived_creates.append(
                {
                    "memory_id": mid,
                    "created_idx": e["created_idx"],
                    "formed_idx": e["formed_idx"],
                    "direction": e["direction"],
                    "source_htf": e["source_htf"],
                    "ttl_initial": 4,
                    "reason": None,
                    "reason_status": "NOT_IN_CREATE_SAMPLE_RECONSTRUCTED_FROM_EXPIRE",
                    "age_at_reset": e["created_idx"] - e["formed_idx"],
                    "outcome": "EXPIRED_TTL",
                }
            )

    restore_ids = {r["memory_id"] for r in restores}
    expire_ids = {e["memory_id"] for e in expires}
    for c in creates:
        mid = c["memory_id"]
        if mid in restore_ids:
            c["outcome_joined"] = "RESTORED_TO_EXPANSION"
        elif mid in expire_ids:
            c["outcome_joined"] = "EXPIRED_TTL"
        else:
            c["outcome_joined"] = "OTHER_OR_UNKNOWN"

    expire_rows = []
    for e in expires:
        row = dict(e)
        row["session_hour_bucket_broker_local"] = hour_bucket(e["timestamp"])
        row["hour_broker_local"] = parse_ts(e["timestamp"]).hour
        row["age_at_reset"] = e["created_idx"] - e["formed_idx"]
        row["bars_formed_to_expire"] = e["expire_idx"] - e["formed_idx"]
        row["parent_crt_status"] = "UNAVAILABLE_IN_EXPIRE_PROBE_RECORDS"
        expire_rows.append(row)

    expire_dir = ctr(e["direction"] for e in expire_rows)
    expire_sess = ctr(e["session_hour_bucket_broker_local"] for e in expire_rows)
    expire_hour = ctr(e["hour_broker_local"] for e in expire_rows)
    expire_bars = ctr(e["bars_since_created"] for e in expire_rows)
    expire_ttl_was = ctr(e["ttl_was"] for e in expire_rows)
    expire_pre = ctr(e["pre_state"] for e in expire_rows)
    expire_age = ctr(e["age_at_reset"] for e in expire_rows)
    expire_fte = ctr(e["bars_formed_to_expire"] for e in expire_rows)
    expire_htf_unique = len({e["source_htf"] for e in expire_rows})

    parent_by_idx = {}
    for pe in sc.get("per_event") or []:
        parent_by_idx[pe.get("candle_index")] = pe.get("Parent_CRT")

    restore_rows = []
    for r in restores:
        row = dict(r)
        row["session_hour_bucket_broker_local"] = hour_bucket(r["timestamp"])
        row["hour_broker_local"] = parse_ts(r["timestamp"]).hour
        row["age_at_reset"] = r["created_idx"] - r["formed_idx"]
        row["parent_crt"] = parent_by_idx.get(r["collapse_idx"])
        restore_rows.append(row)

    restore_dir = ctr(r["direction"] for r in restore_rows)
    restore_sess = ctr(r["session_hour_bucket_broker_local"] for r in restore_rows)
    restore_age = ctr(r["age_at_reset"] for r in restore_rows)
    restore_bars = ctr(r["bars_since_memory_created"] for r in restore_rows)
    restore_parent_track = ctr(
        (r["parent_crt"] or {}).get("parent_track_state", "MISSING") for r in restore_rows
    )
    restore_parent_htf_state = ctr(
        (r["parent_crt"] or {}).get("htf_state", "MISSING") for r in restore_rows
    )
    restore_parent_bias = ctr(
        (r["parent_crt"] or {}).get("parent_bias", "MISSING") for r in restore_rows
    )

    concentrations = [
        "Expires: 45/45 bars_since_created==4 and ttl_was==1 and pre_state==RANGE (exact TTL exhaustion on countdown).",
        "Expires direction SHORT-heavy (30/45=0.667) vs restores LONG-heavy (4/6 approx 0.667).",
        "age_at_reset: restores concentrate at 3 (4/6); expires concentrate at 1 (20/45).",
        "Restores bars_since_created in {2,4} only (3 early / 3 near-TTL); expires all at 4.",
        "source_htf: 45 unique among expires; 6 unique among restores — no repeated HTF id concentration.",
        "Expire session buckets (broker-local): NY_17_22 leading (16/45); not a single-bucket monopoly.",
    ]

    contrast = {
        "note": (
            "Restores n=6 complete; expires n=45 complete. "
            "create_sample persists only first 50 memory_ids; "
            "15 expire memory_ids >50 lack create_sample reason strings but share sole create gate."
        ),
        "direction": {
            "restored": restore_dir,
            "expired": expire_dir,
            "create_sample_all": create_dirs,
        },
        "age_at_reset_formed_to_created": {
            "restored": {str(k): v for k, v in sorted(restore_age.items())},
            "expired": {str(k): v for k, v in sorted(expire_age.items())},
            "create_sample_all": {str(k): v for k, v in sorted(create_age.items())},
        },
        "bars_since_created_at_resolution": {
            "restored_bars_since_memory_created": {
                str(k): v for k, v in sorted(restore_bars.items())
            },
            "expired_bars_since_created": {
                str(k): v for k, v in sorted(expire_bars.items())
            },
        },
        "session_hour_bucket_broker_local": {
            "restored_at_collapse": restore_sess,
            "expired_at_expire": expire_sess,
        },
        "parent_crt_restores_only": {
            "parent_track_state": restore_parent_track,
            "htf_state": restore_parent_htf_state,
            "parent_bias": restore_parent_bias,
            "expires_parent_crt": "UNAVAILABLE_IN_EXPIRE_PROBE_RECORDS",
        },
        "obvious_concentrations_descriptive": concentrations,
    }

    oc = funnel["outcome_counts"]
    arith = (
        oc["EXPIRED_TTL"]
        + oc["CLEARED_NON_HTF_RESET"]
        + oc["RESTORED_TO_EXPANSION"]
        + oc["OVERWRITTEN_BY_NEW_MEMORY"]
    )

    artifact = {
        "artifact": "phase1_shadow_memory_create_expire_census",
        "generated_at_utc": now_utc.isoformat(),
        "generated_at_ist": now_ist.isoformat(),
        "instrument": d["instrument"],
        "csv_path": d["csv_path"],
        "csv_sha256": d["csv_sha256"],
        "config_version": d["config_version"],
        "provenance": {
            **d.get("provenance", {}),
            "mined_from": [
                "results/analysis/phase1_resolver_replay/event_census/memory_subsystem.json",
                "results/analysis/phase1_resolver_replay/event_census/structure_context.json",
                "scripts/analysis/phase1_shadow_memory_subsystem_probe.py",
                "src/config_layer/crt_engine_v2.py:1892-1915 (create gate)",
                "src/config_layer/crt_engine_v2.py:2961-2977 (TTL countdown)",
            ],
            "full_bt_rerun": False,
            "create_sample_cap_note": (
                "Prior probe persisted create_sample[:50] of 69; expire_sample and restores complete. "
                "Create-reason class for all 69 follows sole create gate (DISPLACEMENT intersect HTF-in-reason)."
            ),
        },
        "locked_object": d["locked_object"],
        "economic_claims_allowed": False,
        "funnel_crosscheck": {
            "n_memories_created": funnel["n_memories_created"],
            "n_expire_ttl": funnel["n_expire_ttl_before_confirming_sweep"],
            "n_cleared_non_htf_reset": funnel["n_cleared_non_htf_reset"],
            "n_restored": funnel["n_restore_try_shadow_pending_to_expansion_ok"],
            "outcome_counts": oc,
            "arithmetic_check_69": arith,
        },
        "q1_what_creates_each_of_69": {
            "code_path": {
                "file": "src/config_layer/crt_engine_v2.py",
                "lines": "1892-1915",
                "function": "StateMachine.reset_to_range (pending-memory create block)",
                "gate_all_required": [
                    "state.current_state == CRTState.DISPLACEMENT",
                    "state.displacement_candle is not None",
                    '"HTF" in reason',
                ],
                "assignment": (
                    "state.pending_displacement_ttl = "
                    "self.config.pending_displacement_ttl_candles  # line 1901"
                ),
                "probe_mirror": (
                    "scripts/analysis/phase1_shadow_memory_subsystem_probe.py patched_reset "
                    "uses identical create_shadow predicate before counting n_created"
                ),
                "interpretation": (
                    "BOTH: DISPLACEMENT state precondition AND HTF reset reason. "
                    "Neither alone creates memory. There is no separate DISPLACEMENT-only create path."
                ),
            },
            "measured_create_reason_breakdown": {
                "create_sample_n": len(creates),
                "create_sample_cap": 50,
                "funnel_n_created": 69,
                "reason_class_counts_in_sample": dict(reason_class),
                "reason_prefix_counts_in_sample": dict(reason_prefix),
                "ttl_initial_in_sample": create_ttl,
                "direction_in_sample": create_dirs,
                "age_at_reset_in_sample": {
                    str(k): v for k, v in sorted(create_age.items())
                },
                "inferred_for_all_69": {
                    "HTF_CHANGED_WHILE_DISPLACEMENT": 69,
                    "OTHER": 0,
                    "basis": (
                        "Sole create gate requires DISPLACEMENT intersect displacement_candle "
                        "intersect HTF-in-reason; sample 50/50 reasons are literally "
                        "'HTF changed: ... -> ...'; probe n_created increments only inside that gate."
                    ),
                },
            },
            "create_sample_rows": creates,
            "expire_derived_create_stubs_for_ids_gt_50": expire_derived_creates,
        },
        "q2_expire_45_distribution": {
            "n": 45,
            "by_direction": expire_dir,
            "by_session_hour_bucket_broker_local": expire_sess,
            "by_hour_broker_local": {
                str(k): v for k, v in sorted(expire_hour.items())
            },
            "session_label_caveat": (
                "Buckets use raw corpus timestamps (broker-server / broker_local basis). "
                "Not UTC-corrected session labels (see F-066 / broker_clock notes). Descriptive only."
            ),
            "parent_crt": {
                "status": "UNAVAILABLE_IN_EXPIRE_PROBE_RECORDS",
                "note": (
                    "Parent_CRT recovered only for the 6 restores via structure_context.per_event; "
                    "expire probe rows do not carry parent track/bias."
                ),
            },
            "source_htf_class": {
                "n_unique_source_htf": expire_htf_unique,
                "n_expire": 45,
                "repeated_source_htf": False,
                "note": (
                    "Each expire has a distinct source_htf id; "
                    "no class collapse beyond per-window id."
                ),
            },
            "bars_to_expire": {
                "bars_since_created": {
                    str(k): v for k, v in sorted(expire_bars.items())
                },
                "ttl_was_at_clear": {
                    str(k): v for k, v in sorted(expire_ttl_was.items())
                },
                "pre_state": expire_pre,
                "interpretation": (
                    "All 45 expire after exactly 4 RANGE bars past created_idx "
                    "(pending_displacement_ttl_candles=4; creating bar skipped in countdown)."
                ),
            },
            "formed_near_ttl": {
                "age_at_reset_formed_to_created": {
                    str(k): v for k, v in sorted(expire_age.items())
                },
                "bars_formed_to_expire": {
                    str(k): v for k, v in sorted(expire_fte.items())
                },
                "note": (
                    "Formed near TTL here = displacement age at HTF-reset create. "
                    "Modal age_at_reset=1 (20/45); formed->expire = age_at_reset + 4."
                ),
            },
            "expire_rows": expire_rows,
        },
        "q3_contrast_restores_vs_expires": contrast,
        "restore_rows_enriched": restore_rows,
        "authority_disclaimer": {
            "economic_claims_allowed": False,
            "note": (
                "Descriptive census only. No economic claim, no Case reopen, "
                "no object widening, no freeze mutation, no TTL flip."
            ),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_NOTE.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

    md = []
    md.append("# Phase-1 shadow memory create / expire census")
    md.append("")
    md.append(
        f"**Instrument:** {artifact['instrument']}  **Config:** {artifact['config_version']}  "
        f"**CSV SHA256:** {artifact['csv_sha256'][:16]}…"
    )
    md.append(
        f"**generated_at (UTC):** {artifact['generated_at_utc']}  "
        f"(= {artifact['generated_at_ist']} IST)"
    )
    md.append("**economic_claims_allowed:** False")
    md.append("**full_bt_rerun:** False — mined prior probe artifacts")
    md.append("")
    md.append("## Locked object")
    md.append("")
    md.append(artifact["locked_object"])
    md.append("")
    md.append("## Q1 — What creates each of the 69?")
    md.append("")
    md.append(
        "**Code path:** `src/config_layer/crt_engine_v2.py:1892-1915` "
        "(`reset_to_range` pending-memory create)."
    )
    md.append("")
    md.append(
        "Gate (ALL required — both DISPLACEMENT state **and** HTF reset reason):"
    )
    md.append("")
    md.append("1. `state.current_state == CRTState.DISPLACEMENT`")
    md.append("2. `state.displacement_candle is not None`")
    md.append('3. `"HTF" in reason`')
    md.append("")
    md.append(
        "Probe mirror: `phase1_shadow_memory_subsystem_probe.py` "
        "`patched_reset` uses the identical predicate."
    )
    md.append("")
    md.append("### Create-reason table (measured)")
    md.append("")
    md.append("| Reason class | N (sample) | N (inferred all 69) | Basis |")
    md.append("|---|---:|---:|---|")
    md.append(
        "| HTF_CHANGED_WHILE_DISPLACEMENT (`HTF changed: … → …` + DISPLACEMENT gate) "
        "| 50 | 69 | sample 50/50 + sole create gate |"
    )
    md.append("| OTHER / NON_HTF / DISPLACEMENT-only | 0 | 0 | no alternate create path |")
    md.append("")
    md.append(f"- create_sample persisted: **{len(creates)}/69** (prior probe `[:50]` cap)")
    md.append(f"- sample direction: `{create_dirs}`")
    md.append(f"- sample ttl_initial: `{create_ttl}`")
    md.append(
        f"- sample age_at_reset (formed→created): `{dict(sorted(create_age.items()))}`"
    )
    md.append("")
    md.append("## Q2 — Of the 45 TTL expirations")
    md.append("")
    md.append("| Axis | Distribution |")
    md.append("|---|---|")
    md.append(f"| direction | `{expire_dir}` |")
    md.append(f"| session hour-bucket (broker-local) | `{expire_sess}` |")
    md.append(
        "| parent CRT | UNAVAILABLE in expire probe rows "
        "(restores only via structure_context) |"
    )
    md.append(f"| source_htf | {expire_htf_unique} unique / 45 (no repeats) |")
    md.append(f"| bars_since_created | `{dict(sorted(expire_bars.items()))}` |")
    md.append(f"| ttl_was at clear | `{dict(sorted(expire_ttl_was.items()))}` |")
    md.append(f"| pre_state | `{expire_pre}` |")
    md.append(
        f"| age_at_reset (formed→created) | `{dict(sorted(expire_age.items()))}` |"
    )
    md.append(f"| bars formed→expire | `{dict(sorted(expire_fte.items()))}` |")
    md.append("")
    md.append(
        "**Formed near TTL:** modal age_at_reset=1 (20/45). "
        "All expires are exact TTL-end clears (bars_since_created=4)."
    )
    md.append("")
    md.append(artifact["q2_expire_45_distribution"]["session_label_caveat"])
    md.append("")
    md.append("## Q3 — Contrast restores (6) vs expires (45)")
    md.append("")
    md.append("| Feature | Restores (6) | Expires (45) |")
    md.append("|---|---|---|")
    md.append(f"| direction | `{restore_dir}` | `{expire_dir}` |")
    md.append(
        f"| age_at_reset | `{dict(sorted(restore_age.items()))}` | "
        f"`{dict(sorted(expire_age.items()))}` |"
    )
    md.append(
        f"| bars_since_created at resolution | `{dict(sorted(restore_bars.items()))}` | "
        f"`{dict(sorted(expire_bars.items()))}` |"
    )
    md.append(f"| session bucket @ event | `{restore_sess}` | `{expire_sess}` |")
    md.append(f"| parent_track_state | `{restore_parent_track}` | UNAVAILABLE |")
    md.append(f"| parent htf_state | `{restore_parent_htf_state}` | UNAVAILABLE |")
    md.append(f"| parent_bias | `{restore_parent_bias}` | UNAVAILABLE |")
    md.append("")
    md.append("### Obvious concentrations (descriptive only)")
    md.append("")
    for line in concentrations:
        md.append(f"- {line}")
    md.append("")
    md.append("## Funnel cross-check")
    md.append("")
    md.append(
        f"outcome_counts = `{oc}`  sum={arith} (expect 69)"
    )
    md.append("")
    md.append("## Authority")
    md.append("")
    md.append(artifact["authority_disclaimer"]["note"])
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    note = []
    note.append("# Phase-1 SHADOW memory create / expire note")
    note.append("")
    note.append(
        "**Status:** DESCRIPTIVE ONLY · `economic_claims_allowed=false` · "
        "no Case reopen · no object widening · no freeze work · no TTL flip"
    )
    note.append("")
    note.append(
        f"**Corpus:** Phase-1 XAUUSD · csv sha256 `{artifact['csv_sha256'][:16]}…` · "
        f"config `{artifact['config_version']}`"
    )
    note.append(
        "**Artifact:** `results/analysis/phase1_resolver_replay/event_census/memory_create_expire.json`"
    )
    note.append(
        "**Mined from:** prior `memory_subsystem.json` + `structure_context.json` "
        "(no full BT re-run)"
    )
    note.append("")
    note.append("## Locked object")
    note.append("")
    note.append(artifact["locked_object"])
    note.append("")
    note.append("## Q1 — Create reasons (69)")
    note.append("")
    note.append(
        "Sole path: `crt_engine_v2.py:1892-1915` — **both** DISPLACEMENT "
        "(with displacement_candle) **and** `\"HTF\" in reason`."
    )
    note.append("")
    note.append("| Reason class | Sample N | All-69 inferred |")
    note.append("|---|---:|---:|")
    note.append("| HTF_CHANGED_WHILE_DISPLACEMENT | 50 | 69 |")
    note.append("| Other | 0 | 0 |")
    note.append("")
    note.append(
        "Prior probe capped `create_sample` at 50; funnel still reports 69 creates. "
        "Reason class does not bifurcate — there is no DISPLACEMENT-only create channel."
    )
    note.append("")
    note.append("## Q2 — Expire concentration (45)")
    note.append("")
    note.append("- **Direction:** SHORT 30 / LONG 15")
    note.append(
        "- **Session (broker-local hour buckets):** NY_17_22=16, ASIA_0_8=11, "
        "LONDON_8_13=10, OVERLAP_13_17=5, OFFHOURS_22_24=3"
    )
    note.append(
        "- **Parent CRT:** not on expire rows; **source_htf:** 45 unique"
    )
    note.append(
        "- **Bars-to-expire:** 45/45 at bars_since_created=4 (ttl_was=1, pre_state=RANGE)"
    )
    note.append("- **Formed near TTL:** age_at_reset modal=1 (20/45)")
    note.append("")
    note.append("## Q3 — Restores vs expires")
    note.append("")
    note.append(
        "- Restores LONG-heavy (4/6) vs expires SHORT-heavy (30/45)"
    )
    note.append(
        "- Restores age_at_reset modal=3 (4/6) vs expires modal=1 (20/45)"
    )
    note.append(
        "- Restores resolve at bars_since_created ∈ {2,4}; expires always 4"
    )
    note.append(
        "- Parent CRT (restores only): track/htf_state from structure_context — "
        "see JSON for per-row"
    )
    note.append("")
    note.append("## Non-claims")
    note.append("")
    note.append("- No economic performance claim.")
    note.append("- No recommendation to change TTL.")
    note.append(
        "- Session buckets are descriptive broker-local hour bins, "
        "not corrected UTC session labels."
    )
    note.append("")
    OUT_NOTE.write_text("\n".join(note), encoding="utf-8")

    print("Wrote", OUT_JSON)
    print("Wrote", OUT_MD)
    print("Wrote", OUT_NOTE)
    print("funnel_sum", arith)
    print("expire_dir", expire_dir)
    print("reason_class", dict(reason_class))
    print("restore_parent_track", restore_parent_track)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
