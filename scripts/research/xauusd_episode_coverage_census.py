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
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from research.episode_agreement import (  # noqa: E402
    attach_agreement,
    verdict_to_layer_status,
)
from research.episode_propositions import (  # noqa: E402
    attach_propositions,
    proposition_by_claim,
    relation_to_census_class,
)

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

    mag = ep.get("magnitude_states") or {}

    # O6 body commitment (Phase 2A FM-071)
    bc = mag.get("body_commitment")
    if bc and not str(bc).startswith("X_"):
        obs["O6_body_commitment"] = (
            "COVERED",
            f"body_commitment={bc} from body_ratio={body_ratio}",
        )
    elif body_ratio is not None:
        obs["O6_body_commitment"] = (
            "UNREPRESENTED",
            f"body_ratio={body_ratio:.3f} continuous only — no state band",
        )
    else:
        obs["O6_body_commitment"] = ("UNKNOWN", "body_ratio missing")

    # O7 ATR magnitude (Phase 2A FM-072)
    am = mag.get("atr_magnitude")
    if am and not str(am).startswith("X_"):
        obs["O7_atr_magnitude"] = (
            "COVERED",
            f"atr_magnitude={am} from atr={atr}",
        )
    elif atr is not None:
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

    # O11 / O12 — prefer Phase 2B typed propositions when present
    props = ep.get("propositions") or []
    p_o11 = proposition_by_claim(props, "DIRECTION_ALIGNMENT") if props else None
    p_o12 = proposition_by_claim(props, "CHAPTER_VS_STRUCTURE_SCORE") if props else None

    if isinstance(p_o11, dict) and p_o11.get("relation"):
        rel = p_o11["relation"]
        note = (p_o11.get("surfaces") or {}).get("adjudication_note") or rel
        obs["O11_crt_dir_vs_context_shape"] = (
            relation_to_census_class(rel, observation="O11_crt_dir_vs_context_shape"),
            f"proposition:{rel} — {note}",
        )
    else:
        # Fallback (pre-2B episodes)
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

    if isinstance(p_o12, dict) and p_o12.get("relation"):
        rel = p_o12["relation"]
        note = (p_o12.get("surfaces") or {}).get("adjudication_note") or rel
        pol = (p_o12.get("resolution") or {}).get("policy_id")
        obs["O12_crt_story_vs_structure_score"] = (
            relation_to_census_class(rel, observation="O12_crt_story_vs_structure_score"),
            f"proposition:{rel} policy={pol} — {note}",
        )
    else:
        # Fallback: pre-2B heuristic (score-threshold) — superseded by POL-O12 when props present
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

    # O14 typed Agreement object (Phase 2C) — COVERED when object present (verdict independent)
    ao = ep.get("agreement_object")
    if isinstance(ao, dict) and ao.get("verdict") and ao.get("policy_version"):
        obs["O14_cross_layer_agreement_object"] = (
            "COVERED",
            f"AGR-v0 verdict={ao.get('verdict')} "
            f"unresolved_conflicts={len(ao.get('unresolved_conflicts') or [])} "
            f"exit_claims={ao.get('exit_claims_present')}",
        )
    else:
        obs["O14_cross_layer_agreement_object"] = (
            "UNREPRESENTED",
            "agreement_object missing — run Phase 2C attach",
        )

    # O15 wick
    obs["O15_wick_absorption"] = (
        "UNREPRESENTED",
        "wick/price_position not first-class semantic states",
    )

    # O16 temporal causality — L4 temporal contract distinguishes observed vs causality
    temporal = (ctx or {}).get("temporal") or {}
    if temporal.get("causality") == "UNKNOWN" and (
        temporal.get("session_state") or sess or temporal.get("observed_time_context")
    ):
        obs["O16_temporal_episode_causality"] = (
            "COVERED",
            f"observed_time_context={temporal.get('observed_time_context') or sess}; "
            f"inferred_episode_causality=UNKNOWN "
            f"(session_owner={temporal.get('session_owner', 'session_classifier')}; "
            "not auto-cause)",
        )
    elif sess:
        obs["O16_temporal_episode_causality"] = (
            "PARTIAL",
            f"session={sess} labeled but temporal contract missing causality field",
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

    # O18 momentum magnitude bands (Phase 2A FM-073; F-061-safe percentile)
    mm = mag.get("momentum_magnitude")
    es, ms = cf.get("ema_spread"), cf.get("momentum_score")
    if mm and not str(mm).startswith("X_"):
        obs["O18_momentum_magnitude_bands"] = (
            "COVERED",
            f"momentum_magnitude={mm} from |momentum_score| series percentile "
            f"(ema_spread remains continuous; F-061)",
        )
    elif es is not None or ms is not None:
        obs["O18_momentum_magnitude_bands"] = (
            "UNREPRESENTED",
            f"ema_spread={es} momentum_score={ms} unbanded",
        )
    else:
        obs["O18_momentum_magnitude_bands"] = ("UNKNOWN", "missing momentum fields")

    # O19 model questions vs CRT validity — L7 separates CRT story from CRT testimony
    me_block = ep.get("model_evidence") or {}
    crt_story = me_block.get("crt_story")
    crt_testimony = me_block.get("crt_testimony")
    g_rel = (me.get("gaussian") or {}).get("relationship_to_story")
    crt_rel = (me.get("crt") or {}).get("relationship_to_story")
    if crt_testimony and (crt_story or crt_state):
        obs["O19_model_question_vs_crt_validity"] = (
            "COVERED",
            f"CRT_STORY state={ (crt_story or {}).get('state') or crt_state } "
            f"dir={(crt_story or {}).get('direction') or crt_dir}; "
            f"CRT_TESTIMONY score={(crt_testimony or {}).get('value')} "
            f"semantic={(crt_testimony or {}).get('semantic')} "
            f"rel={crt_rel}; gaussian_rel={g_rel} "
            f"(quality scores not market truth; relationship explicit)",
        )
    elif me:
        # Testimony present but pre-L7-closure shape (no crt_story/testimony split)
        if crt_state in ("EXPANSION", "RETEST", "EXECUTION") and crt_score is not None and crt_score < 0.05:
            g = (me.get("gaussian") or {}).get("value")
            obs["O19_model_question_vs_crt_validity"] = (
                "PARTIAL",
                f"models answer quality questions (gaussian={g}) while CRT chapter advanced with "
                f"crt_score={crt_score}; no joint validity object / no story-testimony split",
            )
        else:
            obs["O19_model_question_vs_crt_validity"] = (
                "PARTIAL",
                "model_evidence records testimony only — story/testimony split not emitted",
            )
    else:
        obs["O19_model_question_vs_crt_validity"] = (
            "UNREPRESENTED",
            "no model_evidence",
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

    # Phase 2B/2C: attach propositions + Agreement fold if missing (no full CRT rebuild)
    rewritten = False
    for i, ep in enumerate(episodes):
        props = ep.get("propositions")
        need_props = not props
        if props:
            kinds = {p.get("claim_kind") for p in props if isinstance(p, dict)}
            need_props = (
                "DIRECTION_ALIGNMENT" not in kinds
                or "CHAPTER_VS_STRUCTURE_SCORE" not in kinds
            )
        ao = ep.get("agreement_object")
        need_agr = not (
            isinstance(ao, dict) and ao.get("verdict") and ao.get("policy_version") == "AGR-v0"
        )
        if need_props or need_agr:
            if need_props and not need_agr:
                episodes[i] = attach_propositions(ep)
                episodes[i] = attach_agreement(episodes[i], ensure_propositions=False)
            else:
                episodes[i] = attach_agreement(ep, ensure_propositions=True)
            rewritten = True
    if rewritten:
        data["episodes"] = episodes
        data["phase_2b_propositions"] = True
        data["phase_2c_agreement"] = True
        EP_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        print(f"Attached Phase 2B/2C propositions+agreement → rewrote {EP_PATH}")

    rows = [classify_episode(ep) for ep in episodes]

    # Proposition relation aggregate (O11/O12 empirical product)
    prop_rel_counts: dict[str, Counter] = defaultdict(Counter)
    for ep in episodes:
        for p in ep.get("propositions") or []:
            if not isinstance(p, dict):
                continue
            prop_rel_counts[p.get("claim_kind", "?")][p.get("relation", "?")] += 1

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
            "Phase 2A closed continuous VALUE→STATE (O6/O7/O18). Phase 2B adds typed "
            "same-event propositions (O11/O12). AGREEMENT object (O14) remains UNREPRESENTED — "
            "correct until Phase 2C. This is not a missing-numerical-feature problem."
        ),
        "proposition_relation_counts": {
            k: dict(v) for k, v in sorted(prop_rel_counts.items())
        },
        "phase_2b": {
            "implemented": True,
            "policy_o12": "POL-O12-SCORE-NOT-CHAPTER",
        },
        "phase_2c": {
            "implemented": True,
            "o14_agreement_object": "IMPLEMENTED_SHADOW (AGR-v0)",
            "policy": "AGR-v0",
            "verdict_counts": dict(
                Counter(
                    (ep.get("agreement_object") or {}).get("verdict") or "MISSING"
                    for ep in episodes
                )
            ),
        },
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

    # Phase-2 chain coherence snapshot (same 10 episodes; AGREEMENT still Phase 2C)
    coherence = _phase2_chain_coherence(episodes, rows)
    coh_path = OUT_DIR / "phase2_chain_coherence.json"
    coh_path.write_text(json.dumps(coherence, indent=2), encoding="utf-8")
    print(f"Wrote {coh_path}")
    print(
        "phase2:",
        f"full={coherence['counts']['full_coherent']}",
        f"layerwise={coherence['counts']['layerwise_describable']}",
        f"AGREEMENT_BREAK={coherence['counts']['episodes_with_AGREEMENT_BREAK']}",
        f"STATE={coherence['layer_status_counts'].get('STATE')}",
    )
    return 0


def _phase2_chain_coherence(episodes: list[dict], rows: list[dict]) -> dict:
    """VALUE→…→AGREEMENT layer status after Phase 2A magnitude states.

    AGREEMENT remains BREAK until O14 (Phase 2C). STATE upgrades toward OK when
    O6+O7+O18 are COVERED on the episode.
    """
    by_id = {r["episode_id"]: r for r in rows}
    layer_counts: dict[str, Counter] = {
        k: Counter()
        for k in ("VALUE", "STATE", "CONTEXT", "SHAPE", "CRT", "TESTIMONY", "AGREEMENT")
    }
    episode_chains = []
    for ep in episodes:
        eid = ep["episode_id"]
        r = by_id[eid]
        obs = r["observations"]

        def _cls(oid: str) -> str:
            return (obs.get(oid) or {}).get("class", "UNKNOWN")

        o6, o7, o18 = _cls("O6_body_commitment"), _cls("O7_atr_magnitude"), _cls("O18_momentum_magnitude_bands")
        mag_covered = sum(1 for c in (o6, o7, o18) if c == "COVERED")
        if mag_covered == 3:
            state_st = "OK"
        elif mag_covered > 0:
            state_st = "PARTIAL"
        else:
            state_st = "PARTIAL"

        # CONTEXT: structured L4 contract + temporal (observed vs causality=UNKNOWN)
        # Requires O16 COVERED (session owner + explicit UNKNOWN causality).
        # Completeness/magnitude enrichment is represented in episode market_context fields.
        mc = ep.get("market_context") or {}
        has_ctx_contract = bool(mc.get("temporal") and mc.get("completeness") and mc.get("dimension_records"))
        if _cls("O16_temporal_episode_causality") == "COVERED" and has_ctx_contract:
            context_st = "OK"
        elif mc.get("dimensions") or _cls("O1_trend_direction") == "COVERED":
            context_st = "PARTIAL"
        else:
            context_st = "PARTIAL"
        shape_st = "OK" if _cls("O9_named_shape") == "COVERED" else "PARTIAL"
        crt_st = "OK" if _cls("O8_crt_chapter") == "COVERED" else "PARTIAL"
        # TESTIMONY L7: present producers + CRT story/testimony split (O19) + O12 policy
        me = ep.get("model_evidence") or {}
        has_testimony_contract = bool(
            me.get("crt_testimony") is not None
            and me.get("values")
            and all(
                isinstance(v, dict) and v.get("relationship_to_story") and v.get("question")
                for v in (me.get("values") or {}).values()
            )
        )
        if (
            _cls("O13_model_testimony_present") == "COVERED"
            and _cls("O19_model_question_vs_crt_validity") == "COVERED"
            and _cls("O12_crt_story_vs_structure_score") == "COVERED"
            and has_testimony_contract
        ):
            testimony_st = "OK"
        elif _cls("O13_model_testimony_present") == "COVERED":
            testimony_st = "PARTIAL"
        else:
            testimony_st = "PARTIAL"

        # Phase 2C: AGREEMENT layer from typed verdict (preserve BREAK on conflict)
        ao = ep.get("agreement_object") or {}
        verdict = ao.get("verdict")
        if verdict:
            agreement_st = verdict_to_layer_status(str(verdict))
        else:
            agreement_st = "BREAK"
        has_exit_props = False
        props = ep.get("propositions") or []
        if props:
            kinds = {p.get("claim_kind") for p in props if isinstance(p, dict)}
            has_exit_props = (
                "DIRECTION_ALIGNMENT" in kinds and "CHAPTER_VS_STRUCTURE_SCORE" in kinds
            )
        chain = {
            "VALUE": "OK",
            "STATE": state_st,
            "CONTEXT": context_st,
            "SHAPE": shape_st,
            "CRT": crt_st,
            "TESTIMONY": testimony_st,
            "AGREEMENT": agreement_st,
        }
        _ = has_exit_props
        for k, v in chain.items():
            layer_counts[k][v] += 1

        layerwise = all(v in ("OK", "PARTIAL") for k, v in chain.items() if k != "AGREEMENT") and agreement_st != "BREAK"
        # historical def: every layer OK or PARTIAL and no BREAK — AGREEMENT=BREAK fails layerwise
        # BREAK on AGREEMENT fails layerwise; PARTIAL/OK pass layerwise definition
        layerwise_describable = all(v in ("OK", "PARTIAL") for v in chain.values())
        integrated = layerwise_describable and agreement_st == "OK"
        full = all(v == "OK" for v in chain.values())
        episode_chains.append(
            {
                "episode_id": eid,
                "kind": ep.get("kind"),
                "chain": chain,
                "full_coherent": full,
                "layerwise_describable": layerwise_describable,
                "integrated_coherent": integrated,
                "blocking_layers": [k for k, v in chain.items() if v == "BREAK"],
                "partial_layers": [k for k, v in chain.items() if v == "PARTIAL"],
                "magnitude_states": ep.get("magnitude_states"),
                "propositions_present": has_exit_props,
                "proposition_relations": {
                    p.get("claim_kind"): p.get("relation")
                    for p in (ep.get("propositions") or [])
                    if isinstance(p, dict)
                },
            }
        )

    n = len(episode_chains)
    return {
        "question": (
            "After Phase 2A magnitude states, can the same 10 episodes be described coherently "
            "across VALUE→…→AGREEMENT without a new measurement?"
        ),
        "phase2_definition": {
            "intended": (
                "state bands for continuous features + cross-layer AGREEMENT object + "
                "resolution of CRT/score and CRT/shape alignment"
            ),
            "phase_2a_implemented": True,
            "phase_2b_implemented": True,
            "phase_2c_implemented": True,
            "phase_2a_work_items": {
                "O6_body_commitment": "IMPLEMENTED_SHADOW (FM-071)",
                "O7_atr_magnitude": "IMPLEMENTED_SHADOW (FM-072)",
                "O18_momentum_magnitude_bands": "IMPLEMENTED_SHADOW (FM-073 abs series percentile)",
            },
            "phase_2b_work_items": {
                "O11_direction_alignment": "IMPLEMENTED_SHADOW (DIRECTION_ALIGNMENT propositions)",
                "O12_chapter_vs_structure_score": (
                    "IMPLEMENTED_SHADOW (CHAPTER_VS_STRUCTURE_SCORE + POL-O12-SCORE-NOT-CHAPTER)"
                ),
            },
            "phase_2c_work_items": {
                "O14_cross_layer_agreement_object": "IMPLEMENTED_SHADOW (AGR-v0 fold)",
            },
            "implemented_in_repo": "Phase 2A+2B+2C complete (research shadow)",
        },
        "coherence_definitions": {
            "layerwise_describable": (
                "each of VALUE/STATE/CONTEXT/SHAPE/CRT/TESTIMONY is OK or PARTIAL; no BREAK "
                "(AGREEMENT BREAK still fails this under the frozen Phase-2 definition)"
            ),
            "integrated_coherent": "layerwise_describable AND AGREEMENT==OK",
            "full_coherent": "every layer OK including AGREEMENT",
        },
        "counts": {
            "n_episodes": n,
            "full_coherent": sum(1 for e in episode_chains if e["full_coherent"]),
            "layerwise_describable": sum(1 for e in episode_chains if e["layerwise_describable"]),
            "integrated_coherent": sum(1 for e in episode_chains if e["integrated_coherent"]),
            "episodes_with_AGREEMENT_BREAK": sum(
                1 for e in episode_chains if e["chain"]["AGREEMENT"] == "BREAK"
            ),
            "episodes_with_AGREEMENT_OK": sum(
                1 for e in episode_chains if e["chain"]["AGREEMENT"] == "OK"
            ),
            "episodes_with_AGREEMENT_PARTIAL": sum(
                1 for e in episode_chains if e["chain"]["AGREEMENT"] == "PARTIAL"
            ),
            "episodes_with_STATE_OK": sum(1 for e in episode_chains if e["chain"]["STATE"] == "OK"),
        },
        "layer_status_counts": {k: dict(v) for k, v in layer_counts.items()},
        "episodes": episode_chains,
        "production_behavior_changed": False,
    }


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
