# Consumer Binding Manifest FC-0.5

## FeaturePipeline

- active: True
- verdict: `FORMULA_CHANGE`
- migration: `SHADOW_REPLAY_REQUIRED`
- retrain_required: False
- binding: LEGACY_FEATURE_SEMANTICS_V1 / default env
- unknowns: []

## BacktestRunner

- active: True
- verdict: `MULTIPLE_CHANGES`
- migration: `SHADOW_REPLAY_REQUIRED`
- retrain_required: False
- binding: FeaturePipeline dual pd.read_csv
- unknowns: []

## CRTEngine

- active: True
- verdict: `VALUE_COMPATIBLE_IDENTITY_RENAME`
- migration: `METADATA_BINDING_ONLY`
- retrain_required: False
- binding: FM-027/028 + candle_math; CH-002 emission
- unknowns: ['BitNet alias map if use_bitnet true']

## BitNet

- active: False
- verdict: `ARTIFACT_BINDING_UNKNOWN`
- migration: `RETRAIN_REQUIRED`
- retrain_required: True
- binding: ARTIFACT_BINDING_UNKNOWN for train-time; CRT maps FM-027/028 to retest_depth/disp_strength names at execute
- unknowns: ['exact training corpus/code for each bitnet artifact']

## Gaussian_live_heuristic

- active: True
- verdict: `EXACT_COMPATIBLE`
- migration: `NONE`
- retrain_required: False
- binding: 3-feature momentum vote; not 38-dim
- unknowns: []

## Gaussian_v4_mirrored_38dim

- active: False
- verdict: `ARTIFACT_BINDING_UNKNOWN`
- migration: `RETRAIN_REQUIRED`
- retrain_required: True
- binding: ARTIFACT_BINDING_UNKNOWN
- unknowns: ['train script/version/corpus']

## ZoneGate

- active: True
- verdict: `NOT_APPLICABLE`
- migration: `NONE`
- retrain_required: False
- binding: zone_registry.json membership
- unknowns: ['whether any zone path uses swing features']

## RR_Engine

- active: True
- verdict: `NOT_APPLICABLE`
- migration: `NONE`
- retrain_required: False
- binding: RREngine.compute local
- unknowns: []

## rr_fusion

- active: False
- verdict: `ARTIFACT_BINDING_UNKNOWN`
- migration: `REMAIN_UNWIRED`
- retrain_required: True
- binding: ARTIFACT_BINDING_UNKNOWN + F-044/F-045
- unknowns: ['label provenance F-022']

## TradeNet

- active: False
- verdict: `ARTIFACT_BINDING_UNKNOWN`
- migration: `REMAIN_UNWIRED`
- retrain_required: True
- binding: ARTIFACT_BINDING_UNKNOWN
- unknowns: ['training lineage']

## secondlow

- active: True
- verdict: `NOT_APPLICABLE`
- migration: `NONE`
- retrain_required: False
- binding: N/A FeaturePipeline
- unknowns: []

## HypothesisRunner

- active: True
- verdict: `MULTIPLE_CHANGES`
- migration: `SHADOW_REPLAY_REQUIRED`
- retrain_required: False
- binding: None
- unknowns: ['per-hypothesis feature use']

## live_engine_hook

- active: True
- verdict: `MULTIPLE_CHANGES`
- migration: `BLOCKED_PENDING_EVIDENCE`
- retrain_required: False
- binding: must align with FeaturePipeline if used; CRT/BitNet paths separate
- unknowns: ['exact live feature builder path parity vs batch']
