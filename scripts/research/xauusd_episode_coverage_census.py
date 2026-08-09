#!/usr/bin/env python3
"""
Coverage census over reconstructed XAUUSD semantic episodes.

Input: results/research/xauusd_episode_semantic_reconstruction/episodes.json
Output: coverage_census.json + coverage_census.md

Classifies episode observations as:
  COVERED | PARTIAL | UNREPRESENTED | CONTRADICTORY | UNKNOWN

Only *recurring* gaps become ontology candidates.
No ontology mutation, no new indicators, no CPR.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EP_PATH = ROOT / "results/research/xauusd_episode_semantic_reconstruction/episodes.json"
OUT_DIR = ROOT / "results/research/xauusd_episode_semantic_reconstruction"


def _dir_sign(d):
    if d == "LONG":
        return 1
    if d == "SHORT":
        return -1
    return 0


def _shape_dir(name):
    if not name:
        return None
    n = name.lower()
    if "bear" in n or "sell" in n:
        return -1
    if "bull" in n or "buy" in n:
        return 1
    return 0


def _trend_from_ctx(ctx):
    dims = (ctx or {}).get("dimensions") or {}
    tr = dims.get("Trend") or {}
    for _, v in tr.items():
        if "Bear" in str(v):
            return -1
        if "Bull" in str(v):
            return 1
    return 0


def classify_episode(ep: dict) -> dict:
    cf = (ep.get("canonical_features") or {}).get("continuous_snapshot") or {}
    fs = ep.get("feature_states") or {}
    ctx = ep.get("market_context") or {}
    shape = ep.get("market_shape") or {}
    crt = ep.get("crt") or {}
    me = (ep.get("model_evidence") or {}).get("values") or {}
    mpath = (ep.get("market") or {}).get("local_path") or {}
    ohlc = (ep.get("market") or {}).get("ohlc") or {}

    body_ratio = cf.get("body_ratio")
    atr = cf.get("atr")
    vol_spike = fs.get("volume_spike")
    trend_bias = fs.get("trend_bias")
    sess = fs.get("session")
    crt_state = crt.get("state")
    crt_dir = (crt.get("event") or {}).get("direction")
    shape_name = shape.get("name")
    shape_matched = shape.get("matched")
    crt_score = (me.get("crt") or {}).get("value")
    net = mpath.get("net_move")
    body = abs((ohlc.get("c") or 0) - (ohlc.get("o") or 0))
    rng = abs((ohlc.get("h") or 0) - (ohlc.get("l") or 0)) + 1e-12
    body_commit = body / rng
    expansion_morph = (
        body_commit >= 0.55
        or abs(net or 0) > 20
        or ep.get("kind") == "large_body_expansion"
    )

    obs: dict[str, tuple[str, str]] = {}

    # O1 trend
    if trend_bias in ("Bullish", "Bearish"):
        obs["O1_trend_direction"] = ("COVERED", f"trend_bias={trend_bias}")
    elif trend_bias:
        obs["O1_trend_direction"] = ("PARTIAL", f"trend_bias={trend_bias}")
    else:
        obs["O1_trend_direction"] = ("UNREPRESENTED", "no trend_bias state")

    # O2 volatility regime
    vr = fs.get("volatility_regime")
    if vr and not str(vr).startswith("X_"):
        obs["O2_volatility_regime"] = ("COVERED", f"volatility_regime={vr}")
    else:
        obs["O2_volatility_regime"] = ("PARTIAL" if vr else "UNREPRESENTED", str(vr))

    # O3 structure
    bos = fs.get("break_of_structure")
    if bos:
        obs["O3_structure_break"] = ("COVERED", f"BOS={bos}")
    else:
        obs["O3_structure_break"] = ("UNREPRESENTED", "no BOS state")

    # O4 liquidity flags
    if fs.get("sweep_detected") is not None or fs.get("liquidity_sweep") is not None:
        obs["O4_liquidity_sweep_flags"] = (
            "COVERED",
            f"sweep={fs.get('sweep_detected')} liq={fs.get('liquidity_sweep')}",
        )
    else:
        obs["O4_liquidity_sweep_flags"] = ("UNREPRESENTED", "missing")

    # O5 participation
    if vol_spike == "VolumeSpike":
        obs["O5_participation_intensity"] = ("COVERED", "volume_spike=VolumeSpike")
    elif vol_spike == "NoSpike":
        if expansion_morph:
            obs["O5_participation_intensity"] = (
                "PARTIAL",
                "NoSpike during expansion-scale morphology",
            )
        else:
            obs["O5_participation_intensity"] = ("COVERED", "NoSpike on non-expansion bar")
    else:
        obs["O5_participation_intensity"] = ("UNREPRESENTED", str(vol_spike))

    # O6 body commitment
    if body_ratio is not None:
        obs["O6_body_commitment"] = (
            "UNREPRESENTED",
            f"body_ratio={body_ratio:.3f} continuous only — no state band",
        )
    else:
        obs["O6_body_commitment"] = ("UNKNOWN", "body_ratio missing")

    # O7 ATR magnitude
    if atr is not None:
        obs["O7_atr_magnitude"] = (
            "UNREPRESENTED",
            f"atr={atr:.6g} continuous only — no intensity band",
        )
    else:
        obs["O7_atr_magnitude"] = ("UNKNOWN", "atr missing")

    # O8 CRT chapter
    if crt_state and crt_state not in ("WARMUP", "UNKNOWN"):
        obs["O8_crt_chapter"] = ("COVERED", f"CRT={crt_state} dir={crt_dir}")
    else:
        obs["O8_crt_chapter"] = ("PARTIAL", f"CRT={crt_state}")

    # O9 named shape
    if shape_matched and shape_name:
        obs["O9_named_shape"] = ("COVERED", shape_name)
    elif shape.get("shape_id"):
        obs["O9_named_shape"] = ("PARTIAL", f"UNNAMED {shape.get('shape_id')}")
    else:
        obs["O9_named_shape"] = ("UNREPRESENTED", "no shape")

    # O10 CRT vs expansion morphology
    if expansion_morph:
        if crt_state in ("EXPANSION", "DISPLACEMENT", "RETEST", "EXECUTION"):
            obs["O10_crt_vs_expansion_morphology"] = (
                "COVERED",
                f"expansion-like path with CRT={crt_state}",
            )
        elif crt_state in ("SWEEP", "RANGE"):
            obs["O10_crt_vs_expansion_morphology"] = (
                "CONTRADICTORY",
                f"expansion-scale morphology with CRT={crt_state}",
            )
        else:
            obs["O10_crt_vs_expansion_morphology"] = (
                "PARTIAL",
                f"expansion morph CRT={crt_state}",
            )
    else:
        obs["O10_crt_vs_expansion_morphology"] = (
            "COVERED",
            f"non-expansion morph CRT={crt_state}",
        )

    # O11 CRT dir vs context/shape
    cdir = _dir_sign(crt_dir)
    tdir = _trend_from_ctx(ctx)
    sdir = _shape_dir(shape_name)
    if cdir != 0 and (tdir != 0 or sdir not in (None, 0)):
        conflicts = []
        if tdir != 0 and cdir != tdir:
            conflicts.append(f"CRT_dir={crt_dir} vs trend_bias={trend_bias}")
        if sdir not in (None, 0) and cdir != sdir:
            conflicts.append(f"CRT_dir={crt_dir} vs shape={shape_name}")
        if conflicts:
            obs["O11_crt_dir_vs_context_shape"] = ("CONTRADICTORY", "; ".join(conflicts))
        else:
            obs["O11_crt_dir_vs_context_shape"] = (
                "COVERED",
                f"CRT_dir={crt_dir} aligns with trend/shape",
            )
    elif cdir == 0:
        obs["O11_crt_dir_vs_context_shape"] = ("PARTIAL", "no CRT direction on anchor")
    else:
        obs["O11_crt_dir_vs_context_shape"] = ("PARTIAL", "shape/trend direction neutral")

    # O12 CRT story vs structure score
    if crt_state in ("EXPANSION", "RETEST", "DISPLACEMENT", "EXECUTION") and crt_score is not None:
        if crt_score < 0.05:
            obs["O12_crt_story_vs_structure_score"] = (
                "CONTRADICTORY",
                f"CRT={crt_state} but structure_rule_score={crt_score}",
            )
        else:
            obs["O12_crt_story_vs_structure_score"] = (
                "COVERED",
                f"CRT={crt_state} score={crt_score}",
            )
    else:
        obs["O12_crt_story_vs_structure_score"] = (
            "PARTIAL",
            f"CRT={crt_state} score={crt_score}",
        )

    # O13 model testimony
    active = [k for k, v in me.items() if v.get("value") is not None]
    absent = (ep.get("model_evidence") or {}).get("absent") or []
    if len(active) >= 3:
        obs["O13_model_testimony_present"] = (
            "COVERED",
            f"active={active}; absent={list(absent)}",
        )
    elif active:
        obs["O13_model_testimony_present"] = ("PARTIAL", f"active={active}")
    else:
        obs["O13_model_testimony_present"] = ("UNREPRESENTED", "no model values")

    # O14 cross-layer agreement object (always infrastructure gap)
    tensions = (ep.get("agreement") or {}).get("tension") or []
    conflict_here = any(
        obs[k][0] == "CONTRADICTORY"
        for k in (
            "O10_crt_vs_expansion_morphology",
            "O11_crt_dir_vs_context_shape",
            "O12_crt_story_vs_structure_score",
        )
        if k in obs
    )
    if conflict_here or tensions:
        obs["O14_cross_layer_agreement_object"] = (
            "UNREPRESENTED",
            f"conflicts present; no agreement object (tensions={tensions})",
        )
    else:
        obs["O14_cross_layer_agreement_object"] = (
            "UNREPRESENTED",
            "no conflicts this bar — still no declared agreement object",
        )

    # O15 wick
    obs["O15_wick_absorption"] = (
        "UNREPRESENTED",
        "wick/price_position not first-class semantic states",
    )

    # O16 temporal causality
    if sess:
        obs["O16_temporal_episode_causality"] = (
            "PARTIAL",
            f"session={sess} labeled but not causal episode object",
        )
    else:
        obs["O16_temporal_episode_causality"] = ("UNREPRESENTED", "no session")

    # O17 filter reason
    ev = crt.get("event") or {}
    if ev.get("action") == "FILTER_REJECTED":
        if ev.get("reason"):
            obs["O17_filter_reject_reason"] = ("COVERED", f"reason={ev.get('reason')}")
        else:
            obs["O17_filter_reject_reason"] = (
                "PARTIAL",
                "FILTER_REJECTED without reason in reconstruction event",
            )
    else:
        obs["O17_filter_reject_reason"] = ("COVERED", "n/a (not filter-reject episode)")

    # O18 momentum magnitude bands
    es, ms = cf.get("ema_spread"), cf.get("momentum_score")
    if es is not None or ms is not None:
        obs["O18_momentum_magnitude_bands"] = (
            "UNREPRESENTED",
            f"ema_spread={es} momentum_score={ms} unbanded",
        )
    else:
        obs["O18_momentum_magnitude_bands"] = ("UNKNOWN", "missing momentum fields")

    # O19 model questions vs CRT validity (testimony not story-aligned by design)
    if crt_state in ("EXPANSION", "RETEST", "EXECUTION") and crt_score is not None and crt_score < 0.05:
        g = (me.get("gaussian") or {}).get("value")
        obs["O19_model_question_vs_crt_validity"] = (
            "PARTIAL",
            f"models answer quality questions (gaussian={g}) while CRT chapter advanced with crt_score={crt_score}; "
            "no joint validity object",
        )
    else:
        obs["O19_model_question_vs_crt_validity"] = (
            "PARTIAL",
            "model_evidence records testimony only — never claims market truth (by design)",
        )

    return {
        "episode_id": ep["episode_id"],
        "kind": ep["kind"],
        "crt_state": crt_state,
        "crt_dir": crt_dir,
        "shape": shape_name or shape.get("label"),
        "expansion_morphology": expansion_morph,
        "observations": {k: {"class": v[0], "note": v[1]} for k, v in obs.items()},
    }


def main() -> int:
    data = json.loads(EP_PATH.read_text(encoding="utf-8"))
    episodes = data["episodes"]
    rows = [classify_episode(ep) for ep in episodes]

    obs_ids = sorted(rows[0]["observations"])
    agg = {}
    for oid in obs_ids:
        counts = Counter(r["observations"][oid]["class"] for r in rows)
        by_class: dict[str, list[str]] = defaultdict(list)
        notes: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            cl = r["observations"][oid]["class"]
            by_class[cl].append(r["episode_id"])
            notes[cl].append(r["observations"][oid]["note"])
        covered = counts.get("COVERED", 0)
        gap_n = counts.get("UNREPRESENTED", 0) + counts.get("CONTRADICTORY", 0)
        partial_n = counts.get("PARTIAL", 0)
        # Recurring gap: gap in >=3 episodes, or gap+partial in >=5, and not mostly covered
        recurring = (gap_n >= 3 or (gap_n + partial_n) >= 5) and covered < 7
        agg[oid] = {
            "counts": dict(counts),
            "n_episodes": len(rows),
            "recurring_gap": recurring,
            "episodes_by_class": dict(by_class),
            "example_notes": {k: v[:3] for k, v in notes.items()},
        }

    candidates = []
    for oid, a in agg.items():
        if not a["recurring_gap"]:
            continue
        c = a["counts"]
        priority = (
            c.get("CONTRADICTORY", 0) * 3
            + c.get("UNREPRESENTED", 0) * 2
            + c.get("PARTIAL", 0)
        )
        candidates.append(
            {
                "observation": oid,
                "counts": c,
                "priority": priority,
                "ontology_action": "REGISTER_AS_UNKNOWN_OR_STATE_BAND_CANDIDATE",
                "rationale": "recurring across episodes; not majority COVERED",
                "example_episodes": (
                    a["episodes_by_class"].get("CONTRADICTORY", [])
                    + a["episodes_by_class"].get("UNREPRESENTED", [])
                    + a["episodes_by_class"].get("PARTIAL", [])
                )[:5],
            }
        )
    candidates.sort(key=lambda x: -x["priority"])

    # Summary matrix episode x observation
    matrix = []
    for r in rows:
        matrix.append(
            {
                "episode_id": r["episode_id"],
                "classes": {oid: r["observations"][oid]["class"] for oid in obs_ids},
            }
        )

    out = {
        "source": str(EP_PATH.as_posix()),
        "n_episodes": len(rows),
        "classification_vocab": [
            "COVERED",
            "PARTIAL",
            "UNREPRESENTED",
            "CONTRADICTORY",
            "UNKNOWN",
        ],
        "recurrence_rule": {
            "recurring_gap_if": "(UNREPRESENTED+CONTRADICTORY)>=3 OR (those+PARTIAL)>=5",
            "and": "COVERED < 7 of 10",
            "principle": "Only repeated gaps become ontology candidates; single-episode quirks do not.",
        },
        "episode_census": rows,
        "aggregate": agg,
        "matrix": matrix,
        "ontology_candidates_recurring_only": candidates,
        "not_candidates_this_pass": [
            oid for oid, a in agg.items() if not a["recurring_gap"]
        ],
        "bottom_line": (
            "The MT5 corpus reveals a semantic integration problem: many market properties "
            "are measured, but episode-level meaning is not consistently shared across "
            "feature states, context, shape, CRT, and model testimony. This is not primarily "
            "a missing-numerical-feature problem."
        ),
        "production_behavior_changed": False,
        "cpr_reopened": False,
        "ontology_mutated": False,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "coverage_census.json"
    md_path = OUT_DIR / "coverage_census.md"
    json_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    md_path.write_text(_render_md(out), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print("candidates:", [c["observation"] for c in candidates])
    return 0


def _render_md(out: dict) -> str:
    lines = [
        "# XAUUSD episode semantic coverage census",
        "",
        f"**Source episodes:** `{out['source']}`",
        f"**n episodes:** {out['n_episodes']}",
        f"**Ontology mutated:** `{out['ontology_mutated']}`",
        f"**CPR reopened:** `{out['cpr_reopened']}`",
        "",
        "## Bottom line",
        "",
        out["bottom_line"],
        "",
        "## Recurrence rule",
        "",
        f"- {out['recurrence_rule']['recurring_gap_if']}",
        f"- and {out['recurrence_rule']['and']}",
        f"- {out['recurrence_rule']['principle']}",
        "",
        "## Aggregate by observation",
        "",
        "| Observation | COVERED | PARTIAL | UNREPRESENTED | CONTRADICTORY | UNKNOWN | Recurring gap? |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for oid, a in sorted(out["aggregate"].items()):
        c = a["counts"]
        lines.append(
            f"| `{oid}` | {c.get('COVERED',0)} | {c.get('PARTIAL',0)} | "
            f"{c.get('UNREPRESENTED',0)} | {c.get('CONTRADICTORY',0)} | {c.get('UNKNOWN',0)} | "
            f"{'**YES**' if a['recurring_gap'] else 'no'} |"
        )

    lines += ["", "## Ontology candidates (recurring only)", ""]
    if not out["ontology_candidates_recurring_only"]:
        lines.append("_None._")
    for cand in out["ontology_candidates_recurring_only"]:
        lines += [
            f"### {cand['observation']} (priority {cand['priority']})",
            "",
            f"- Counts: `{cand['counts']}`",
            f"- Action: `{cand['ontology_action']}`",
            f"- Examples: {', '.join(cand['example_episodes'])}",
            f"- Rationale: {cand['rationale']}",
            "",
        ]

    lines += [
        "## Not candidates this pass",
        "",
        ", ".join(f"`{x}`" for x in out["not_candidates_this_pass"]),
        "",
        "## Per-episode matrix (class only)",
        "",
    ]
    obs_ids = sorted(out["matrix"][0]["classes"]) if out["matrix"] else []
    # compact table: episode vs high-signal observations
    focus = [
        "O5_participation_intensity",
        "O6_body_commitment",
        "O9_named_shape",
        "O10_crt_vs_expansion_morphology",
        "O11_crt_dir_vs_context_shape",
        "O12_crt_story_vs_structure_score",
        "O14_cross_layer_agreement_object",
        "O15_wick_absorption",
        "O16_temporal_episode_causality",
        "O18_momentum_magnitude_bands",
    ]
    focus = [f for f in focus if f in obs_ids]
    header = "| Episode | " + " | ".join(f.replace("O", "").split("_", 1)[0] + "…" + f.split("_")[-1][:6] for f in focus) + " |"
    # simpler header
    header = "| Episode | " + " | ".join(f"`{f}`" for f in focus) + " |"
    lines.append(header)
    lines.append("|---|" + "|".join(["---"] * len(focus)) + "|")
    for row in out["matrix"]:
        cells = [row["classes"].get(f, "") for f in focus]
        # short codes
        code = {
            "COVERED": "C",
            "PARTIAL": "P",
            "UNREPRESENTED": "U",
            "CONTRADICTORY": "X",
            "UNKNOWN": "?",
        }
        lines.append(
            "| "
            + row["episode_id"][:40]
            + " | "
            + " | ".join(code.get(c, c) for c in cells)
            + " |"
        )
    lines += [
        "",
        "Legend: C=COVERED P=PARTIAL U=UNREPRESENTED X=CONTRADICTORY ?=UNKNOWN",
        "",
        "## Priority for next ontology work (not measurement)",
        "",
        "1. Continuous → state bands where episodes need meaning (body commitment, ATR intensity, momentum magnitude).",
        "2. Cross-layer AGREEMENT/CONFLICT object (CRT × Shape × Context × Model testimony).",
        "3. CRT chapter vs price morphology co-description (not force-merge).",
        "4. Named shape coverage for recurring UNNAMED contexts.",
        "5. Wick/absorption only if still recurring after (1)–(4).",
        "6. Only then consider a new measurement surface.",
        "",
        "`PRODUCTION_BEHAVIOR_CHANGED=NO`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
