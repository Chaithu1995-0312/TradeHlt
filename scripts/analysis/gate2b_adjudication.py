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
("candle_math.py",57,"rng"):      row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-12-F2-RANGE","V-exact","n/a",CANON_REG,"F2 operand inside canonical F6"),
("candle_math.py",58,"<return>"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-guard0","zero_0.0",CANON_REG,"F6 anchor body/range, rng>0 guard (F-046)"),
("composition_registry.py",0,"val"): row("CANONICAL_EQUIVALENT","FAM-07-REGISTRY-EXEC","V-config-num-den","zero_0.0",CANON_REG,"executor_dispatch: ontology-selected num/den + bounds clamp; parity battery test_formula_registry"),
("derived_registry.py",0,"<dispatch>"): row("CANONICAL_EQUIVALENT","FAM-07-REGISTRY-EXEC","V-signature-dispatch","delegates",CANON_REG,"executor_dispatch: NO local math; dispatch to derived_math impls; parity test_derived_math","HYPOTHESIS_PARTIAL"),
("derived_math.py",40,"val"):     row("CANONICAL_EQUIVALENT","FAM-17-FM020-DISPSTR","V-clip0-3","nan_fallback",PIPE,"FM-020 impl body/(atr*close) clip[0,3]; parity-bound"),
("derived_math.py",84,"<return>"): row("CANONICAL_EQUIVALENT","FAM-18-FM024-VOLRATIO","V-fallback1","one_fallback",PIPE,"FM-024 impl (high-low)/(atr*close); 1.0 fallback mirrors pipeline"),
# CH-001/CH-002 (F-050): FM-027/FM-028 registered impls — canonical scalars for CRT emission
("derived_math.py",117,"disp_move"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-20-CROSS-CANDLE-RETRACE","V-body-guard","zero_0.0",CANON_REG,"FM-027 operand |disp.close-disp.open|; F-050 CH-002"),
("derived_math.py",120,"val"): row("CANONICAL_EQUIVALENT","FAM-20-CROSS-CANDLE-RETRACE","V-registered-impl-FM027","zero_0.0",CANON_REG,"FM-027 displacement_retrace canonical scalar (F-050 CH-001/CH-002); CRT emission key"),
("derived_math.py",130,"<return>"): row("CANONICAL_EQUIVALENT","FAM-06-RANGE-ATR-MULTIPLE","V-registered-impl-FM028","guard_atr>0",CANON_REG,"FM-028 displacement_atr_ratio canonical scalar (F-050 CH-001/CH-002); CRT emission key"),
# ---- feature_pipeline (vectorized authority; parity-bound) ------------------------------
("feature_pipeline.py",186,"upper_wick"): row("CANONICAL_EQUIVALENT","FAM-13-F3-UPPER","V-vectorized","n/a",PIPE_AUX,"vectorized F3 raw (np.maximum); intermediate column"),
("feature_pipeline.py",187,"lower_wick"): row("CANONICAL_EQUIVALENT","FAM-14-F4-LOWER","V-vectorized","n/a",PIPE_AUX,"vectorized F4 raw"),
("feature_pipeline.py",214,"proxy"):      row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-vectorized","n/a",RB("YES","NO","YES","NO","NO","NO","G5-RESOLVED: LATENT path — zero corpora in data/*_M15.csv are majority-zero-volume, proxy never fired; conditional on future zero-volume corpora"),"F2 written into the VOLUME column as tick-activity proxy for all-zero-volume corpora (FX!) — F2 masquerading as volume","HYPOTHESIS_PARTIAL","CS-3: F2-as-volume proxy — volume_ratio/volume_spike on FX derive from RANGE math","G5-3: which datasets/models consumed proxy-volume?"),
("feature_pipeline.py",263,"tr1"):        row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",PIPE,"F2 as TR operand (ATR kernel)"),
("feature_pipeline.py",266,"true_range"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder","n/a",PIPE,"Wilder TR = max(tr1,tr2,tr3); feeds atr_14"),
("feature_pipeline.py",449,"body_size"):  row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-vectorized-methodabs","n/a",PIPE,"(close-open).abs() — Series.abs METHOD (census UNKNOWN_FORM label; math is exact F1); parity-bound test_candle_math"),
("feature_pipeline.py",450,"wick_size"):  row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-vectorized","n/a",PIPE,"F2 under the legacy wick_size column name (F-046 documented)"),
("feature_pipeline.py",452,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-guard0-vectorized","zero_0.0",PIPE,"body_size/wick_size where wick_size column==F2 ⇒ canonical F6 (census NC label resolved by column semantics); np.where guard","HYPOTHESIS_PARTIAL"),
("feature_pipeline.py",458,"price_position"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-19-PRICE-POSITION","V-guard05","half_fallback",PIPE,"(close-low)/range — position-in-range [0,1], 0.5 fallback; distinct quantity consuming F2"),
("feature_pipeline.py",482,"volatility_ratio"): row("CANONICAL_EQUIVALENT","FAM-18-FM024-VOLRATIO","V-vectorized-fallback1","one_fallback",PIPE,"FM-024 vectorized; parity-bound test_derived_math"),
("feature_pipeline.py",565,"disp_strength"): row("CANONICAL_EQUIVALENT","FAM-17-FM020-DISPSTR","V-vectorized-clip","nan_fallback",PIPE,"FM-020 vectorized; parity-bound"),
# ---- live hook (GD-001/2/3) --------------------------------------------------------------
("live_engine_hook.py",360,"body_size"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-exact","n/a",LIVE_HOOK,"GD-003: byte-identical F1 inline (re-derivation debt, math correct)"),
("live_engine_hook.py",361,"wick_size"): row("NON_EQUIVALENT_SAME_NAME","FAM-15-F5-TOTALW","V-clip0","clip0",LIVE_HOOK,"GD-002: F5 total_wick under the F2 wick_size name (canonical column meaning = F2)","HYPOTHESIS_CONFIRMED","GD-002 preserved","G5-1: aux dict -> FeatureStore -> logs"),
("live_engine_hook.py",362,"body_ratio"): row("NON_EQUIVALENT_SAME_NAME","FAM-02-GD001-BODY-OVER-TOTALW","V-guard1e8","guard_1e-8_to_0.0",LIVE_HOOK,"GD-001: body/total_wick vs canonical body/range; 97% value drift measured","HYPOTHESIS_CONFIRMED","GD-001 preserved","G5-1"),
# ---- crt_engine_v2 -----------------------------------------------------------------------
("crt_engine_v2.py",1011,"tr"):   row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-05-TRUE-RANGE","V-wilder-scalar","n/a",CRT_SPINE,"TR kernel in RangeDetector.compute_atr"),
("crt_engine_v2.py",1045,"full_range"): row("DOMAIN_POLICY_VARIANT","FAM-12-F2-RANGE","V-floor0.001-table3","eps_floor_0.001",CRT_TELEM,"F2 with Table-3 doc floor; diagnostic-only consumer (GD-006 ctx)"),
("crt_engine_v2.py",1046,"upper_wick"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",CRT_TELEM,"NORMALIZED F7-like ratio under the RAW F3 name (GD-006); floored denom"),
("crt_engine_v2.py",1047,"lower_wick"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",CRT_TELEM,"GD-007 twin of upper_wick floored ratio"),
("crt_engine_v2.py",1216,"move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",CRT_SPINE,"F1 as displacement magnitude vs atr_min_displacement*atr — HARD state-machine gate (decision)"),
("crt_engine_v2.py",1360,"_disp_strength"): row("CANONICAL_EQUIVALENT","FAM-06-RANGE-ATR-MULTIPLE","V-plain","guard_atr>0",CRT_SPINE,"FM-028 local gate wick_size/atr vs max_displacement_strength (F-050 CH-002; cache emits displacement_atr_ratio)"),
("crt_engine_v2.py",1566,"atr_multiple"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-plain","guard_atr>0",CRT_SPINE,"score_breakout: Candle.wick_size(F2)/atr"),
("crt_engine_v2.py",1567,"atr_component"): row("SUBEXPRESSION_OF_GOVERNED_QUANTITY","FAM-06-RANGE-ATR-MULTIPLE","V-div3-cap1","n/a",CRT_SPINE,"min(atr_multiple/3,1) score component"),
("crt_engine_v2.py",1664,"f_body"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-09-SOFTCONF-SCORES","V-norm-body-min","n/a",CRT_SPINE,"min(1, body_ratio/confirmation_body_min) — parameterized score consuming FM-010"),
("crt_engine_v2.py",1684,"disp_move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","guard_disp",CRT_SPINE,"F1 of displacement candle for f_disp"),
("crt_engine_v2.py",1685,"f_disp"): row("INDEPENDENT_UNGOVERNED_QUANTITY","FAM-10-BODY-ATR-MULTIPLE","V-1.5atr-cap1","guard_atr>0",CRT_SPINE,"min(1, disp_move/(1.5*atr)) — body-ATR multiple score (kin of scoring_engine move/atr)"),
("crt_engine_v2.py",2130,"move"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","guard_>0",CRT_SPINE,"F1 base for reset retrace |price-disp.close|/move >= retrace_reset_pct (decision: reset)"),
("crt_engine_v2.py",2566,"_body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",CRT_TELEM,"routed _cm.body_ratio call (F-047 refactor); would_trade telemetry"),
# ---- crt_sweep_taxonomy (dead twin) ------------------------------------------------------
("crt_sweep_taxonomy.py",122,"full_range"): row("DOMAIN_POLICY_VARIANT","FAM-12-F2-RANGE","V-floor0.001-table3","eps_floor_0.001",DEAD,"Table-3 floor; candle_geometry 0 callers (GD-008)"),
("crt_sweep_taxonomy.py",123,"body"):       row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-exact","n/a",DEAD,"F1 in dead helper"),
("crt_sweep_taxonomy.py",124,"upper_wick"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",DEAD,"GD-008 dead twin of crt floored upper_wick"),
("crt_sweep_taxonomy.py",125,"lower_wick"): row("NON_EQUIVALENT_SAME_NAME","FAM-04-TABLE3-FLOORED-WICK","V-floored-ratio","eps_floor_0.001",DEAD,"GD-009 dead twin"),
("crt_sweep_taxonomy.py",126,"body_ratio"): row("DOMAIN_POLICY_VARIANT","FAM-16-F6-BODY-RATIO","V-floored-denom","eps_floor_0.001",DEAD,"F6 with floored denominator (dead) — floored body_ratio variant"),
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
# ---- dead / orphan / transport / demo / tests --------------------------------------------
("crt_feature_builder.py",123,"body_size"): row("CANONICAL_EQUIVALENT","FAM-01-F1-BODY","V-routed-call","zero_0.0",DEAD,"routed candle_math call (F-046 corrected builder; 0 callers)"),
("crt_feature_builder.py",124,"wick_size"): row("CANONICAL_EQUIVALENT","FAM-12-F2-RANGE","V-routed-call","n/a",DEAD,"routed call, dead"),
("crt_feature_builder.py",125,"body_ratio"): row("CANONICAL_EQUIVALENT","FAM-16-F6-BODY-RATIO","V-routed-call","zero_0.0",DEAD,"routed call, dead"),
("strategy_backtest.py",285,"body_size"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","strategy_backtest tooling (governance sandbox); _f row-read helper"),"_f(row) READ helper (transport; census UNKNOWN_FORM from unlisted helper)","HYPOTHESIS_PARTIAL"),
("strategy_backtest.py",285,"wick_size"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","same"),"row-read transport","HYPOTHESIS_PARTIAL"),
("strategy_backtest.py",285,"body_ratio"): row("NO_GOVERNED_COUNTERPART","-","V-transport","n/a",RB("NO","NO","NO","NO","NO","NO","same"),"row-read transport","HYPOTHESIS_PARTIAL"),
("feature_monitor.py",301,"body_ratio"): row("TEST_ORACLE","-","V-demo-random","n/a",TESTF,"__main__ demo feeding random.uniform values (module demo block)"),
("s09_pattern_recog.py",204,"prev_body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","n/a",ORPHAN,"engulfing pattern F1 (prev candle)"),
("s09_pattern_recog.py",205,"curr_body"): row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","n/a",ORPHAN,"engulfing F1 (curr)"),
("s09_pattern_recog.py",242,"body"):      row("SAME_MATH_DIFFERENT_NAME","FAM-01-F1-BODY","V-orphan","skip_none",ORPHAN,"single-candle F1"),
("s09_pattern_recog.py",243,"upper_wick"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-13-F3-UPPER","V-orphan","skip_none",ORPHAN,"raw F3"),
("s09_pattern_recog.py",244,"lower_wick"): row("MATHEMATICALLY_EQUIVALENT_VARIANT","FAM-14-F4-LOWER","V-orphan","skip_none",ORPHAN,"raw F4"),
("s09_pattern_recog.py",245,"total_range"): row("SAME_MATH_DIFFERENT_NAME","FAM-12-F2-RANGE","V-orphan","skip_none",ORPHAN,"F2"),
("s09_pattern_recog.py",250,"body_pct"): row("SAME_MATH_DIFFERENT_NAME","FAM-08-F6-EQUIV-SKIPPOLICY","V-skip-none","skip_none",ORPHAN,"F6 formula with SKIP-CANDLE zero policy (CS-2: policy splits family from FAM-16)"),
("test_derived_math.py",45,"atr_14_raw"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"F2.clip(0.5) as positive-ATR proxy in parity test setup"),
("test_feature_pipeline.py",571,"body_ratio"): row("TEST_ORACLE","-","V-test-fixture","n/a",TESTF,"extreme-drift test fixture"),
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
