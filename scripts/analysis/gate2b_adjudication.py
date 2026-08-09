"""
gate2b_adjudication.py — F-049 FULL GATE 2B semantic adjudication over the frozen Census-v3 surface.

Evidence-first records for EVERY governed Census-v3 record (110 = 108 derivation sites + 2 admitted
executor_dispatch). The adjudication TABLE below was composed from independent source reads (session
evidence; every row cites file:line); the census only supplies identity join keys. Closure is
machine-checked: adjudicated ids == frozen governed ids (tests/test_gate2b_closure.py).

Hybrid granularity: SEMANTIC_FAMILY (math/units/operands/timeframe) → IMPLEMENTATION_VARIANT
(zero-range policy/floors/guards/params) → DERIVATION_SITE (role, 6-dim reachability, consumers).

Outputs:
  docs/governance/geometry_semantic_adjudication.jsonl      (one line per governed record)
  docs/governance/geometry_family_registry.json             (FAMILY + VARIANT registries)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parents[2]
CENSUS = _ROOT / "docs/governance/geometry_census.jsonl"
OUT = _ROOT / "docs/governance/geometry_semantic_adjudication.jsonl"
FAMOUT = _ROOT / "docs/governance/geometry_family_registry.json"

# ── reachability profiles (six dims; YES/NO require evidence — cited per row) ─────────────
def RB(runtime, decision, research, training, artifact, test, ev):
    return {"runtime_reachable": runtime, "decision_reachable": decision,
            "research_reachable": research, "training_reachable": training,
            "artifact_reachable": artifact, "test_only": test, "reachability_evidence": ev}

CANON_REG = RB("YES", "YES", "YES", "YES", "YES",
               "NO", "candle_math/registry consumed by CRT Candle props + pipeline (F-046); G5-RESOLVED: "
                     "model artifacts embed pipeline CANONICAL_FEATURES (rr_model 49k rows F-044; zone_registry 38-dim F-041)")
PIPE = RB("YES", "YES", "YES", "YES", "YES",
          "NO", "FeaturePipeline.run() feeds backtest vectors + training datasets; G5-RESOLVED: artifacts "
                "embed canonical features (rr_model/zone_registry per F-044/F-041)")
PIPE_AUX = RB("YES", "NO", "YES", "NO", "NO",
              "NO", "G5-RESOLVED: intermediate column, NOT in CANONICAL_FEATURES, no downstream reader "
                    "found (grep) -> no training/artifact path")
CRT_SPINE = RB("YES", "YES", "YES", "NO", "YES",
               "NO", "CRT state machine gate/scoring (research spine F-037 + live); not a training feature; "
                     "G5-RESOLVED: opportunities.jsonl telemetry artifacts")
CRT_TELEM = RB("YES", "NO", "YES", "YES", "YES",
               "NO", "G5-RESOLVED (F-050 chain): cached_features(crt:1372) -> opportunities.jsonl(:1121-1127) "
                     "-> stage1_dataset_builder -> master_*_training.jsonl -> trainer.py:807 (BitNet chain; "
                     "F-004 inert on active config bounds economic exposure)")
LIVE_HOOK = RB("YES", "YES", "NO", "NO", "NO",
               "NO", "live-hook only (pipeline_mode:160); decision-reachable-in-code per F-047 (F-048 veto "
                     "ctx); G5-RESOLVED: backtests bypass -> runtime logs only, NO model-artifact path")
DEAD = RB("NO", "NO", "NO", "NO", "NO", "NO", "0 callers (grep) — dead code")
ORPHAN = RB("NO", "NO", "NO", "NO", "NO", "NO", "strategies S1-S10 orphaned (F-013, dormant fuse_strategy_results)")
RESEARCH = RB("NO", "NO", "YES", "NO", "YES", "NO", "research module (isolated); G5-RESOLVED: research report artifacts only (F-040/secondlow)")
TOOLING = RB("NO", "NO", "YES", "NO", "NO", "NO", "manual analysis script/tool; G5: reports only")
TESTF = RB("NO", "NO", "NO", "NO", "NO", "YES", "test/demo context only")
GATEI = RB("YES", "UNKNOWN", "NO", "NO", "NO", "NO",
           "2G-C4 CORRECTED: planner Step-2 reject_engine precedes Step-5 gate and F-048 makes execute "
           "unreachable -> gate NEVER evaluated in practice; decision contingent on F-048 remediation; "
           "G5-RESOLVED: no artifact path (gate scores not persisted)")
RRE = RB("YES", "YES", "NO", "NO", "YES", "NO",
         "RREngine.compute on EngineRunner.run():683 (gate-ON/live; F-037 gate-OFF research); F-048 ctx; "
         "G5-RESOLVED: engines_raw/fusion jsonl telemetry artifacts")

# ── adjudication table: (file_suffix, line, symbol) -> row ───────────────────────────────
# relation ∈ {CANONICAL_EQUIVALENT, MATHEMATICALLY_EQUIVALENT_VARIANT, DOMAIN_POLICY_VARIANT,
#             NON_EQUIVALENT_SAME_NAME, SAME_MATH_DIFFERENT_NAME, SUBEXPRESSION_OF_GOVERNED_QUANTITY,
#             INDEPENDENT_UNGOVERNED_QUANTITY, TEST_ORACLE, NO_GOVERNED_COUNTERPART, UNKNOWN}
def row(rel, fam, var, zero, reach, ev, hyp="HYPOTHESIS_CONFIRMED", contra="", g5=""):
    return {"relation": rel, "family": fam, "variant": var, "zero_range_policy": zero,
            "reach": reach, "evidence": ev, "hypothesis_comparison": hyp,
            "contradiction_status": contra, "gate5_followup": g5}

T = {
# ---- canonical registry / scalar impls -------------------------------------------------
("candle_math.py",27,"<return>"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-exact","n/a",CANON_REG,"F1 anchor abs(close-open); oracle test_candle_math"),
("candle_math.py",32,"<return>"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-exact","n/a",CANON_REG,"F2 anchor high-low"),
("candle_math.py",37,"<return>"): row("CANONICAL_EQUIVALENT","FAM-13-F3-UPPER","V-exact","n/a",CANON_REG,"F3 anchor (raw price units)"),
("candle_math.py",42,"<return>"): row("CANONICAL_EQUIVALENT","FAM-14-F4-LOWER","V-exact","n/a",CANON_REG,"F4 anchor"),
("candle_math.py",47,"<return>"): row("CANONICAL_EQUIVALENT","FAM-15-F5-TOTALW","V-exact","n/a",CANON_REG,"F5 anchor = F3+F4 (identity-tested)"),
("candle_math.py",60,"rng"):      row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","n/a",CANON_REG,"F2 operand inside canonical F6"),
("candle_math.py",61,"<return>"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-guard0","zero_0.0",CANON_REG,"F6 anchor body/range, rng>0 guard (F-046)"),
("candle_math.py",74,"<return>"): row("CANONICAL_EQUIVALENT","FAM-02-GD001-BODY-OVER-TOTALW","V-registered-impl-FM013","guard_1e-8",LIVE_HOOK,"FM-013 body_to_total_wick_ratio registered impl (Phase-1 GD-001 closure); sole consumer live_engine_hook body_ratio binding"),
("composition_registry.py",0,"val"): row("CANONICAL_EQUIVALENT","FAM-07-REGISTRY-EXEC","V-config-num-den","zero_0.0",CANON_REG,"executor_dispatch: ontology-selected num/den + bounds clamp; parity battery test_formula_registry"),
("derived_registry.py",0,"<dispatch>"): row("CANONICAL_EQUIVALENT","FAM-07-REGISTRY-EXEC","V-signature-dispatch","delegates",CANON_REG,"executor_dispatch: NO local math; dispatch to derived_math impls; parity test_derived_math","HYPOTHESIS_PARTIAL"),
("derived_math.py",41,"val"):     row("CANONICAL_EQUIVALENT","FAM-17-FM020-DISPSTR","V-clip0-3","nan_fallback",PIPE,"FM-020 impl body/(atr*close) clip[0,3]; parity-bound"),
("derived_math.py",123,"<return>"): row("CANONICAL_EQUIVALENT","FAM-18-FM024-VOLRATIO","V-fallback1","one_fallback",PIPE,"FM-024 impl (high-low)/(atr*close); 1.0 fallback mirrors pipeline"),
# CH-001/CH-002 (F-050): FM-027/FM-028 registered impls — canonical scalars for CRT emission
# CENSUS-INVISIBLE 2026-07-22 (disclosed recall residual, NOT a retirement): the FM-027
#   displacement_retrace rows below (formerly :118 disp_move / :121 val, now :155 / :158) no longer
#   appear in the census. The CODE is byte-identical to its authoring commit b48d4d9 — the census
#   changed, not the impl: census-v2's same-candle guard resolves price tokens via _PRICE_LOOKUP,
#   and the parameter names `disp_close`/`disp_open` are not price aliases, so abs(disp_close -
#   disp_open) no longer matches F1. Effect is RECALL-ONLY and confined to a REGISTERED canonical
#   impl living where math is supposed to live — it cannot hide an ungoverned re-derivation, which
#   is what the floor exists to catch. Kept here (unmatched keys are inert) so the adjudication is
#   not silently lost. Follow-up: FU-CENSUS-PARAM-ALIAS (extend _PRICE token aliasing to
#   `<prefix>_<price>` parameter names, then re-adjudicate these two sites).
# ("derived_math.py",155,"disp_move"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-20-CROSS-CANDLE-RETRACE","V-body-guard","zero_0.0",CANON_REG,"FM-027 operand |disp.close-disp.open|; F-050 CH-002"),
# ("derived_math.py",158,"val"): row("CANONICAL_EQUIVALENT","FAM-20-CROSS-CANDLE-RETRACE","V-registered-impl-FM027","zero_0.0",CANON_REG,"FM-027 displacement_retrace canonical scalar (F-050 CH-001/CH-002); CRT emission key"),
("derived_math.py",169,"<return>"): row("CANONICAL_EQUIVALENT","FAM-06-RANGE-ATR-MULTIPLE","V-registered-impl-FM028","guard_atr>0",CANON_REG,"FM-028 displacement_atr_ratio canonical scalar (F-050 CH-001/CH-002); CRT emission key"),
# ---- feature_pipeline (vectorized authority; parity-bound) ------------------------------
("feature_pipeline.py",342,"upper_wick"): row("CANONICAL_EQUIVALENT","FAM-13-F3-UPPER","V-vectorized","n/a",PIPE_AUX,"vectorized F3 raw (np.maximum); intermediate column"),
("feature_pipeline.py",343,"lower_wick"): row("CANONICAL_EQUIVALENT","FAM-14-F4-LOWER","V-vectorized","n/a",PIPE_AUX,"vectorized F4 raw"),
# Phase-1 T-003 volume identity split: proxy is an EXPLICIT column now; source volume never rewritten.
("feature_pipeline.py",368,"proxy"):      row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-vectorized","n/a",PIPE_AUX,"F2 as tick-activity proxy operand (Phase-1 T-003 fix: no longer overwrites the volume column; explicit identity FEAT-VOLUME_RANGE_PROXY)"),
("feature_pipeline.py",369,"volume_range_proxy"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-vectorized","n/a",PIPE_AUX,"explicit F2 proxy column (FEAT-VOLUME_RANGE_PROXY); not in CANONICAL_FEATURES, volume_ratio/volume_spike bind to source volume only"),
("feature_pipeline.py",388,"proxy_ma20"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-window-mean","n/a",PIPE_AUX,"rolling-20 mean of the F2 proxy (denominator of the explicit proxy ratio)"),
("feature_pipeline.py",389,"volume_range_proxy_ratio"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-11-RANGE-EXPANSION","V-proxy-ratio-fallback1","one_fallback",PIPE_AUX,"proxy/proxy_ma20 — range-expansion-style ratio under an explicit name (never volume_ratio)"),
("feature_pipeline.py",456,"tr1"):        row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",PIPE,"F2 as TR operand (ATR kernel)"),
("feature_pipeline.py",459,"true_range"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",PIPE,"Wilder TR = max(tr1,tr2,tr3); feeds atr_14"),
("feature_pipeline.py",717,"body_size"):  row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-vectorized-methodabs","n/a",PIPE,"(close-open).abs() — Series.abs METHOD (census UNKNOWN_FORM label; math is exact F1); parity-bound test_candle_math"),
("feature_pipeline.py",718,"wick_size"):  row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-vectorized","n/a",PIPE,"F2 under the legacy wick_size column name (F-046 documented)"),
("feature_pipeline.py",720,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-guard0-vectorized","zero_0.0",PIPE,"body_size/wick_size where wick_size column==F2 ⇒ canonical F6 (census NC label resolved by column semantics); np.where guard","HYPOTHESIS_PARTIAL"),
("feature_pipeline.py",726,"price_position"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-19-PRICE-POSITION","V-guard05","half_fallback",PIPE,"(close-low)/range — position-in-range [0,1], 0.5 fallback; distinct quantity consuming F2"),
("feature_pipeline.py",753,"volatility_ratio"): row("CANONICAL_EQUIVALENT","FAM-18-FM024-VOLRATIO","V-vectorized-fallback1","one_fallback",PIPE,"FM-024 vectorized; parity-bound test_derived_math"),
("feature_pipeline.py",882,"disp_strength"): row("CANONICAL_EQUIVALENT","FAM-17-FM020-DISPSTR","V-vectorized-clip","nan_fallback",PIPE,"FM-020 vectorized; parity-bound"),
# ---- live hook (GD-001/2/3 RETIRED 2026-07-10: math routed through candle_math; the
#      name-collision semantics are preserved by explicit identity binding, FU-WICK-SIZE-NAME) ----
("live_engine_hook.py",469,"body_size"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-routed-call","n/a",LIVE_HOOK,"GD-003 retired: routed candle_math.body_size call (census UNKNOWN_FORM = registry call)"),
("live_engine_hook.py",471,"wick_size"): row("NON_EQUIVALENT_SAME_NAME","FAM-15-F5-TOTALW","V-routed-call","clip0",LIVE_HOOK,"GD-002 retired: routed candle_math.total_wick call; F5 semantic under the F2 wick_size name persists as explicit binding (FU-WICK-SIZE-NAME)","HYPOTHESIS_CONFIRMED","GD-002 name collision preserved by binding","G5-1: aux dict -> FeatureStore -> logs"),
# ---- crt_engine_v2 -----------------------------------------------------------------------
("crt_engine_v2.py",870,"tr"):   row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder-scalar","n/a",CRT_SPINE,"TR kernel in RangeDetector.compute_atr"),
("crt_engine_v2.py",904,"full_range"): row("DOMAIN_POLICY_VARIANT","FAM-12-F2-RANGE","V-floor0.001-table3","eps_floor_0.001",CRT_TELEM,"F2 with Table-3 doc floor; diagnostic-only consumer (GD-006 ctx)"),
("crt_engine_v2.py",910,"sweep_uw_frac"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",CRT_TELEM,"NORMALIZED F7-like ratio, floored denom. GD-006 RETIRED 2026-07-20 (T-15) by behaviour-neutral rename upper_wick -> sweep_uw_frac: math byte-identical, the raw-F3 NAME collision is gone but the non-canonical SEMANTIC persists (relation unchanged)"),
("crt_engine_v2.py",911,"sweep_lw_frac"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",CRT_TELEM,"GD-007 twin; RETIRED 2026-07-20 (T-15): lower_wick -> sweep_lw_frac, byte-identical rename"),
("crt_engine_v2.py",1095,"move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",CRT_SPINE,"F1 as displacement magnitude vs atr_min_displacement*atr — HARD state-machine gate (decision)"),
# ("crt_engine_v2.py",1360,"_disp_strength") RETIRED 2026-07-11 (GD-005 closure): [PATCH 7] gate
#   now routed through derived_math.displacement_atr_ratio (FM-028) — no longer a census derivation.
("crt_engine_v2.py",1793,"atr_multiple"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-plain","guard_atr>0",CRT_SPINE,"score_breakout: Candle.wick_size(F2)/atr"),
("crt_engine_v2.py",1794,"atr_component"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-div3-cap1","n/a",CRT_SPINE,"min(atr_multiple/3,1) score component"),
("crt_engine_v2.py",1892,"f_body"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-09-SOFTCONF-SCORES","V-norm-body-min","n/a",CRT_SPINE,"min(1, body_ratio/confirmation_body_min) — parameterized score consuming FM-010"),
("crt_engine_v2.py",1912,"disp_move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","guard_disp",CRT_SPINE,"F1 of displacement candle for f_disp"),
("crt_engine_v2.py",1913,"f_disp"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-10-BODY-ATR-MULTIPLE","V-1.5atr-cap1","guard_atr>0",CRT_SPINE,"min(1, disp_move/(1.5*atr)) — body-ATR multiple score (kin of scoring_engine move/atr)"),
("crt_engine_v2.py",2358,"move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","guard_>0",CRT_SPINE,"F1 base for reset retrace |price-disp.close|/move >= retrace_reset_pct (decision: reset)"),
("crt_engine_v2.py",2886,"_body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",CRT_TELEM,"routed _cm.body_ratio call (F-047 refactor); would_trade telemetry"),
# ---- crt_sweep_taxonomy (dead twin) ------------------------------------------------------
("crt_sweep_taxonomy.py",122,"full_range"): row("DOMAIN_POLICY_VARIANT","FAM-12-F2-RANGE","V-floor0.001-table3","eps_floor_0.001",DEAD,"Table-3 floor; candle_geometry 0 callers (GD-008)"),
("crt_sweep_taxonomy.py",123,"body"):       row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",DEAD,"F1 in dead helper"),
("crt_sweep_taxonomy.py",128,"sweep_uw_frac"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",DEAD,"GD-008 dead twin; RETIRED 2026-07-20 (T-15): local upper_wick -> sweep_uw_frac, return-dict KEY 'upper_wick' retained for tools/btcusdt_crt_v3_replay API stability"),
("crt_sweep_taxonomy.py",129,"sweep_lw_frac"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",DEAD,"GD-009 dead twin; RETIRED 2026-07-20 (T-15): lower_wick -> sweep_lw_frac, dict KEY retained"),
("crt_sweep_taxonomy.py",130,"body_ratio"): row("DOMAIN_POLICY_VARIANT","FAM-16-F6-BODY-RATIO","V-floored-denom","eps_floor_0.001",DEAD,"F6 with floored denominator (dead) — floored body_ratio variant"),
# ---- gaussian scorer (F-050 CH-002: emits FM-027/028 keys via derived_math) --------------
("crt_gaussian_scorer.py",196,"disp_move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","skip_none",CRT_TELEM,"F1 of disp candle as body-zero guard before FM-027/028 emission (F-050 CH-002)"),
# ---- gate intelligence / rr engine -------------------------------------------------------
("gate_intelligence.py",223,"score"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-09-SOFTCONF-SCORES","V-breakout-blend","n/a",GATEI,"0.5*clip(body_ratio-read)+0.5*disp/3 — gate score consuming features"),
("gate_intelligence.py",256,"r"):     row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-plain","guard_both>0",GATEI,"bar_range(F2 via reads)/atr"),
("gate_intelligence.py",257,"score"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-tent","n/a",GATEI,"tent function of r"),
("rr_engine.py",59,"candle_range"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-exact","eps_reject_1e-9",RRE,"GD-010: byte-identical F2; doji rejected below _EPS"),
("rr_engine.py",69,"upper_body"):   row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-21-POLARITY-FRACTIONS","V-plain","eps_reject",RRE,"(high-close)/range — close-position fraction (NOT F7: numerator is h-c, not h-max(o,c)); F-048 polarity"),
("rr_engine.py",70,"lower_body"):   row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-21-POLARITY-FRACTIONS","V-plain","eps_reject",RRE,"(close-low)/range twin"),
# ---- research: encoder + secondlow + candle_state ---------------------------------------
("encoder.py",100,"rng"):   row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","zero_0.0_triple",RESEARCH,"F2 with rng<=0 -> (0,0,0) guard (F-040 encoder)"),
("encoder.py",104,"body"):  row("SAME_MATH_DIFFERENT_NAME","FAM-16-F6-BODY-RATIO","V-guard0-research","zero_0.0",RESEARCH,"research F6 duplicate; zero policy matches canon"),
("encoder.py",105,"upper"): row("SAME_MATH_DIFFERENT_NAME","FAM-22-F7-UPPER-RATIO","V-guard0-research","zero_0.0",RESEARCH,"F7 ratio (research; FM-011 registered-inactive counterpart)"),
("encoder.py",106,"lower"): row("SAME_MATH_DIFFERENT_NAME","FAM-23-F8-LOWER-RATIO","V-guard0-research","zero_0.0",RESEARCH,"F8 ratio"),
("encoder.py",169,"cur"):   row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","n/a",RESEARCH,"F2 current bar"),
("encoder.py",170,"prior"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","filtered>0",RESEARCH,"F2 list comprehension (prior bars)"),
("encoder.py",177,"<return>"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-11-RANGE-EXPANSION","V-mean-prior","fallback_1.0",RESEARCH,"cur/mean(prior) range-expansion ratio (F-040 core)"),
("encoder.py",190,"cur_tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","n/a",RESEARCH,"F2 for vol norm"),
("encoder.py",191,"atr_ratio"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-research","guard",RESEARCH,"cur_tr/atr research"),
("secondlow_v1/detector.py",64,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",RESEARCH,"TR kernel (tracked secondlow)"),
# ---- H-SECONDLOW sole-copy package (research) --------------------------------------------
("secondlow_r5_pre_weakness_volatility_mechanics.py",110,"pre_range"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-window-mean","n/a",RESEARCH,"mean range pre-window"),
("secondlow_r5_pre_weakness_volatility_mechanics.py",111,"post_range"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-window-mean","n/a",RESEARCH,"mean range post-window"),
("xauusd_second_low_forensic_casebook.py",31,"atr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",RESEARCH,"TR->ATR"),
("xauusd_second_low_mechanism_report.py",22,"atr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",RESEARCH,"TR->ATR"),
("xauusd_second_low_v1_controlled.py",69,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",RESEARCH,"TR kernel"),
# ---- scripts/tools -----------------------------------------------------------------------
("p3b_gate_expired_counterfactual_rr.py",54,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"TR kernel"),
("purge_delay_scan.py",83,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"TR kernel"),
("gaussian_rr_scatter.py",88,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"TR kernel"),
("momentum_continuation_bnbusdt.py",177,"body_pct"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-24-BODY-PCT-OF-PRICE","V-x100","eps_1e-10",TOOLING,"body/close*100 — percent-of-PRICE, NOT body_ratio (despite _pct name)"),
("live_path_replay.py",137,"body_ratio"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",TOOLING,"_pref(row, cached_body_ratio, body_ratio) = column-preference READ (transport; census UNKNOWN_FORM from unlisted helper)","HYPOTHESIS_PARTIAL"),
("manual_backtest.py",108,"total"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","guard_<=0->0",TOOLING,"F2 inside script body_ratio helper"),
("manual_backtest.py",109,"<return>"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-16-F6-BODY-RATIO","V-guard0-script","zero_0.0",TOOLING,"script F6 duplicate"),
("manual_backtest.py",112,"<return>"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-12-F2-RANGE","V-exact","n/a",TOOLING,"script wick_size()=F2 duplicate"),
("manual_backtest.py",141,"f_body"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-09-SOFTCONF-SCORES","V-norm-body-min","n/a",TOOLING,"script replica of engine:1658 soft-conf f_body"),
("manual_backtest.py",429,"br"):  row("SAME_MATH_DIFFERENT_NAME","FAM-16-F6-BODY-RATIO","V-guard0-script","zero_0.0",TOOLING,"helper call"),
("manual_backtest.py",430,"ws"):  row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-exact","n/a",TOOLING,"helper call"),
("manual_backtest.py",431,"move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",TOOLING,"F1 displacement magnitude (script)"),
("manual_backtest.py",475,"body_ratio"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-16-F6-BODY-RATIO","V-guard0-script","zero_0.0",TOOLING,"cached_feat write via helper"),
("btcusdt_crt_v3_replay.py",199,"avg_body"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-01-F1-BODY","V-window-mean","n/a",TOOLING,"mean of F1 over window"),
("btcusdt_crt_v3_replay.py",202,"rel_range"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-11-RANGE-EXPANSION","V-avg-range","guard",TOOLING,"range/avg_range (tool twin of encoder:177)"),
("btcusdt_crt_v3_replay.py",203,"body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",TOOLING,"F1"),
("btcusdt_crt_v3_replay.py",258,"rel_range"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-11-RANGE-EXPANSION","V-avg-range","guard",TOOLING,"twin of :202"),
# ---- probes (intentional replicas) -------------------------------------------------------
("feature_math_decision_flip_probe.py",75,"body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-probe-replica","n/a",TOOLING,"GD-001 A/B probe replica"),
("feature_math_decision_flip_probe.py",76,"tw"):   row("SAME_MATH_DIFFERENT_NAME","FAM-15-F5-TOTALW","V-probe-replica-clip0","clip0",TOOLING,"replica of live :361"),
("feature_math_decision_flip_probe.py",77,"br"):   row("SAME_MATH_DIFFERENT_NAME","FAM-02-GD001-BODY-OVER-TOTALW","V-probe-replica","guard_1e-8",TOOLING,"replica of live :362 (docstring-declared)"),
("feature_math_decision_flip_probe.py",164,"canon_ws"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-probe","n/a",TOOLING,"canonical B-branch range"),
("feature_math_drift_probe.py",54,"body_size"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-01-F1-BODY","V-probe-replica","n/a",TOOLING,"replica"),
("feature_math_drift_probe.py",55,"wick_size"): row("NON_EQUIVALENT_SAME_NAME","FAM-15-F5-TOTALW","V-probe-replica-clip0","clip0",TOOLING,"replica"),
("feature_math_drift_probe.py",56,"body_ratio"): row("NON_EQUIVALENT_SAME_NAME","FAM-02-GD001-BODY-OVER-TOTALW","V-probe-replica","guard_1e-8",TOOLING,"replica"),
("feature_math_drift_probe.py",104,"canonical_ws"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-probe","n/a",TOOLING,"canonical range"),
("feature_semantic_adjudication_pass_a.py",403,"body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-probe-replica","n/a",TOOLING,"Phase-1 semantic-adjudication probe replica (F1)"),
("feature_semantic_adjudication_pass_a.py",464,"rng"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-probe-replica","n/a",TOOLING,"Phase-1 semantic-adjudication probe replica (F2)"),
# GD-004 identity-closure probe (2026-07-11): recomputes TR/ATR independently to verify the
# pipeline atr column's unit, and the FM-028 comparator for the identity adjudication.
("gd004_disp_rescale_probe.py",86,"tr1"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"TR operand for independent atr_14_raw recomputation (ATR-unit check)"),
("gd004_disp_rescale_probe.py",89,"atr_raw_recomputed"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder-mean","n/a",TOOLING,"rolling-14 TR mean == atr_14_raw replica (feature_pipeline.py:271-275)"),
("gd004_disp_rescale_probe.py",107,"fm028"): row("SAME_MATH_DIFFERENT_NAME","FAM-06-RANGE-ATR-MULTIPLE","V-probe","guard_atr>0",TOOLING,"FM-028 comparator (high-low)/atr_abs for the GD-004 identity adjudication (equals-FM-028 rate 0.00%)"),
# CRT XAUUSD runtime trace (observational, behavior-neutral wrapper; telemetry replicas)
("crt_xauusd_runtime_trace.py",96,"body_size"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-probe-replica","n/a",TOOLING,"F1 replica for per-candle IN/OUT trace record (JSONL telemetry only)"),
("crt_xauusd_runtime_trace.py",97,"candle_range"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-probe-replica","n/a",TOOLING,"F2 replica for trace record"),
("crt_xauusd_runtime_trace.py",98,"body_ratio"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-16-F6-BODY-RATIO","V-probe-replica-guard0","zero_0.0",TOOLING,"canonical F6 replica (body/range, range>0 guard) for trace record"),
# ---- dead / orphan / transport / demo / tests --------------------------------------------
("crt_feature_builder.py",131,"body_size"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-routed-call","zero_0.0",DEAD,"routed candle_math call (F-046 corrected builder; 0 callers)"),
("crt_feature_builder.py",132,"wick_size"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-routed-call","n/a",DEAD,"routed call, dead"),
("crt_feature_builder.py",133,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",DEAD,"routed call, dead"),
("strategy_backtest.py",285,"body_size"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","strategy_backtest tooling (governance sandbox); _f row-read helper"),"_f(row) READ helper (transport; census UNKNOWN_FORM from unlisted helper)","HYPOTHESIS_PARTIAL"),
("strategy_backtest.py",285,"wick_size"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","same"),"row-read transport","HYPOTHESIS_PARTIAL"),
("strategy_backtest.py",285,"body_ratio"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","same"),"row-read transport","HYPOTHESIS_PARTIAL"),
# ("feature_monitor.py",301,"body_ratio") RETIRED 2026-07-11 (lint hardening): demo now binds
#   fixture noise to intermediates (transport) — no longer a census derivation.
("s09_pattern_recog.py",204,"prev_body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","n/a",ORPHAN,"engulfing pattern F1 (prev candle)"),
("s09_pattern_recog.py",205,"curr_body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","n/a",ORPHAN,"engulfing F1 (curr)"),
("s09_pattern_recog.py",242,"body"):      row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","skip_none",ORPHAN,"single-candle F1"),
("s09_pattern_recog.py",243,"upper_wick"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-13-F3-UPPER","V-orphan","skip_none",ORPHAN,"raw F3"),
("s09_pattern_recog.py",244,"lower_wick"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-14-F4-LOWER","V-orphan","skip_none",ORPHAN,"raw F4"),
("s09_pattern_recog.py",245,"total_range"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-orphan","skip_none",ORPHAN,"F2"),
("s09_pattern_recog.py",250,"body_pct"): row("SAME_MATH_DIFFERENT_NAME","FAM-08-F6-EQUIV-SKIPPOLICY","V-skip-none","skip_none",ORPHAN,"F6 formula with SKIP-CANDLE zero policy (CS-2: policy splits family from FAM-16)"),
("test_derived_math.py",45,"atr_14_raw"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"F2.clip(0.5) as positive-ATR proxy in parity test setup"),
("test_feature_pipeline.py",582,"body_ratio"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"extreme-drift test fixture"),
("test_phase1_duplicate_formula_identity_closure.py",131,"t003_math"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"T-003 proxy-formula oracle (high-low) asserting no same-name volume substitution"),

# ═════════════════════════════════════════════════════════════════════════════════════════
# 2026-07-22 ADJUDICATION PASS — 21 census-fresh derivations admitted since the last freeze.
# SCOPE DECISION (explicit): NO scripts/ or tests/ census-scope exemption was granted. The
#   census universe is unchanged. Rationale: (a) ~20 scripts/tools sites are ALREADY adjudicated
#   here as TOOLING — an exemption would retroactively un-govern them; (b) tests/
#   test_feature_math_lint.py::test_universe_reconciliation_with_census exists precisely to close
#   the lint's outside-src/ scope gap via census closure — exempting scripts/ would punch a hole
#   where that floor was built; (c) adjudication costs one row and leaves an auditable record,
#   whereas an exemption is invisible. ZERO new FM ids were minted: every row below resolves to an
#   EXISTING family (TR kernels -> FAM-05, routed registry calls -> canonical families, RR polarity
#   -> FAM-21) or is a test oracle. No new SEMANTIC quantity appeared.
# ── analysis / certification scripts: independent-recompute TR kernels (TOOLING) ──────────
("b2a_feature_candidate_certification.py",150,"tr_abs"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"F2 as Wilder-TR operand in the B2A candidate-certification independent recompute (np.maximum triple)"),
("crt_local_math_authority_probe.py",45,"tr1"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"F2 TR operand for the pipeline atr_14_raw replica (CRT local-math authority probe)"),
("crt_local_math_authority_probe.py",48,"true_range"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"Wilder TR = max(tr1,tr2,tr3) — deliberate replica of feature_pipeline.py:459 for the ATR-unit authority check"),
("feature_dag_rolling_certification.py",75,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"F2 TR operand in the L1 rolling-indicator independent recompute (FM-040..046 certification)"),
("feature_dag_structural_certification.py",91,"tr"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",TOOLING,"F2 TR operand reconstructing promoted FM-041 atr for liquidity_distance certification"),
("volatility_regime_certification.py",48,"tr1"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder-scalar","nan_bar0",TOOLING,"F2 TR operand in the scalar-loop TR oracle (bar-0 NaN semantics deliberately mirrored)"),
# ── crt_state_transition_audit_4m: ROUTED candle_math calls (census UNKNOWN_FORM = registry call,
#    same class as crt_feature_builder.py:131-133) ─────────────────────────────────────────
("crt_state_transition_audit_4m.py",61,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",TOOLING,"routed candle_math.body_ratio call in the _bar audit record — no local math"),
("crt_state_transition_audit_4m.py",61,"body_size"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-routed-call","n/a",TOOLING,"routed candle_math.body_size call"),
("crt_state_transition_audit_4m.py",61,"candle_range"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-routed-call","n/a",TOOLING,"routed candle_math.candle_range call"),
("crt_state_transition_audit_4m.py",61,"wick_size"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-routed-call","n/a",TOOLING,"routed candle_math.candle_range under the legacy wick_size key — F2 semantic, matching feature_pipeline.py:718 (F-046), NOT the live_engine_hook total_wick semantic"),
# ── research: ERP synthetic trace + path ambiguity + story builder (RESEARCH) ─────────────
("erp_synth_4h_trace.py",266,"rng"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-21-POLARITY-FRACTIONS","V-exact","eps_reject_1e-9",RESEARCH,"F2 denominator of the RREngine polarity replica (twin of rr_engine.py:59 with the same 1e-9 doji reject)"),
("erp_synth_4h_trace.py",514,"rng"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","zero_0.0",RESEARCH,"F2 operand of the deliberate manual-vs-canonical body_ratio A/B on the entry bar"),
("erp_synth_4h_trace.py",515,"body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",RESEARCH,"F1 operand of the same A/B"),
("erp_synth_4h_trace.py",516,"br_manual"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-16-F6-BODY-RATIO","V-guard0-research","zero_0.0",RESEARCH,"INTENTIONAL manual F6 replica emitted alongside cm_body_ratio(:517) in one record — the replica IS the measurement (manual-vs-registry divergence probe), not stray math"),
("ambiguity_census.py",132,"bar_range"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","zero_0.0_no_exit_bar",RESEARCH,"F2 of the SL/TP collision exit bar; 0.0 when the exit bar is out of range (P1 ambiguity census)"),
("story_builder.py",92,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",RESEARCH,"routed cm_body_ratio call in synthetic story design features (census UNKNOWN_FORM = registry call)"),
("story_builder.py",116,"rng"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-21-POLARITY-FRACTIONS","V-exact","eps_reject",RESEARCH,"F2 denominator of the RR polarity replica (twin of erp_synth_4h_trace.py:266)"),
# ── live hook: T-11 strict-accessor READ misread as UNKNOWN_FORM (LIVE_HOOK) ──────────────
("live_engine_hook.py",417,"body_ratio"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",LIVE_HOOK,"_require_feature_value(trade_data,'body_ratio') in _build_engine_input = T-11 strict READ accessor. TRANSPORT, not mathematics: the census labels it UNKNOWN_FORM only because the strict accessor is an unlisted helper (identical class to live_path_replay.py:137 and strategy_backtest.py:285). Adjudicated rather than added to census _COERCION_LEAVES — that allowlist is for numeric coercion (float/int), and widening it for domain accessors would blind the floor repo-wide","HYPOTHESIS_PARTIAL"),
# ── tests: oracles / fixtures (TESTF) ─────────────────────────────────────────────────────
("test_b0b1_feature_semantic_migration.py",70,"tr1"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"F2 TR operand in the _true_range oracle for the B0/B1 FM-030/031 semantic-migration A/B"),
("test_b0b1_feature_semantic_migration.py",154,"hl"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"high-low oracle asserting F5 wick_size == candle_range (not wick magnitude)"),
("test_bitnet_composition.py",44,"body_ratio"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"seeded legacy-feature fixture literal (0.55 + seed); census UNKNOWN_FORM from fixture arithmetic at a governed sink"),
}

def main() -> int:
    cen = [json.loads(l) for l in CENSUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    gov = [r for r in cen if r["derivation_id_or_null"]]
    out, missing = [], []
    used = set()
    for r in sorted(gov, key=lambda r: (r["file"], r["line_span"][0], r["occurrence_id"])):
        key = None
        for (fs, ln, sym), t in T.items():
            if r["file"].endswith(fs) and r["line_span"][0] == ln and r["target_symbol"] == sym:
                key = (fs, ln, sym)
                break
        if key is None:
            missing.append(f'{r["file"]}:{r["line_span"][0]}::{r["target_symbol"]}')
            continue
        t = T[key]
        used.add(key)
        out.append({
            "derivation_id": r["derivation_id_or_null"],
            "occurrence_id": r["occurrence_id"],
            "file": r["file"], "line": r["line_span"][0],
            "enclosing_qualname": r["enclosing_qualname"],
            "target_symbol": r["target_symbol"],
            "census_form": r["feature_candidate"], "census_flags": r.get("flags", []),
            "semantic_relation": t["relation"],
            "semantic_family_id": t["family"],
            "implementation_variant": t["variant"],
            "zero_range_policy": t["zero_range_policy"],
            **t["reach"],
            "evidence": t["evidence"],
            "hypothesis_comparison": t["hypothesis_comparison"],
            "contradiction_status": t["contradiction_status"],
            "gate5_followup": t["gate5_followup"],
        })
    with OUT.open("w", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    fams: dict = {}
    for rec in out:
        f = rec["semantic_family_id"]
        if f == "-":
            continue
        d = fams.setdefault(f, {"family_id": f, "member_site_ids": [], "variants": {}})
        d["member_site_ids"].append(rec["derivation_id"])
        d["variants"].setdefault(rec["implementation_variant"], []).append(rec["derivation_id"])
    FAMOUT.write_text(json.dumps({
        "_doc": "F-049 Gate-2B FAMILY + IMPLEMENTATION_VARIANT registries (derived from the adjudication artifact).",
        "family_count": len(fams),
        "variant_count": sum(len(d["variants"]) for d in fams.values()),
        "families": fams}, indent=1), encoding="utf-8")

    from collections import Counter
    print("governed:", len(gov), "| adjudicated:", len(out), "| missing:", len(missing))
    for m in missing:
        print("  MISSING:", m)
    print("relations:", dict(Counter(r["semantic_relation"] for r in out)))
    print("families:", len(fams), "| variants:", sum(len(d["variants"]) for d in fams.values()))
    print("hypothesis:", dict(Counter(r["hypothesis_comparison"] for r in out)))
    unk = Counter()
    for rec in out:
        for dim in ("runtime_reachable","decision_reachable","research_reachable","training_reachable","artifact_reachable"):
            if rec[dim] == "UNKNOWN":
                unk[dim] += 1
    print("UNKNOWN reachability by dim:", dict(unk))
    print("gate5 followups:", sum(1 for r in out if r["gate5_followup"]))
    return 0 if not missing else 1

if __name__ == "__main__":
    raise SystemExit(main())
