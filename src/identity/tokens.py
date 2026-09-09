"""Closed vocabularies copied from the identity contract. Not imported from HEAD engines."""

from __future__ import annotations

STATUS_PRESERVED = "PRESERVED"
STATUS_UNIDENTIFIED = "UNIDENTIFIED"
STATUS_IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
STATUS_IDENTITY_INCOMPLETE = "IDENTITY_INCOMPLETE"
STATUS_UNJOINABLE = "UNJOINABLE"

LAYERS = frozenset({
    "L0", "L1", "L2", "L3_OCCUPANCY", "L3_EVENT", "L4", "L5",
})

TIMEFRAMES = frozenset({"M15", "H1", "H4", "D1", "W1", "MN1"})
SCHEMA_VERSIONS = frozenset({"2.0", "3.0", "4.0", "5.0"})
PRODUCER_IDS = frozenset({"engine", "resolver"})
TRACK_IDS = frozenset({"execution_tf", "parent_tf"})
EVENT_KINDS = frozenset({"STATE_TRANSITION", "RESET"})
DIRECTIONS = frozenset({"long", "short"})
GEOMETRY_KINDS = frozenset({
    "engine_trade", "planner_v1_2", "oracle_every_bar",
    "episode_entry", "visual_crt_sem012", "detection_stream",
})
GEOMETRY_SCHEMAS = frozenset({"single_tp", "dual_tp_partial", "structural_no_tp"})
WALK_KERNELS = frozenset({
    "forward_walk_intrabar_fixed", "multi_tp_walk", "backtest_ledger", "detection_stream",
})
COST_MODEL_IDS = frozenset({"flat_12bps", "sem015_component_xauusd", "none_gross"})
FILL_MODEL_IDS = frozenset({"touch_exact", "sem016_adverse", "engine_intrabar"})
SNAPSHOT_KINDS = frozenset({"corpus", "feature_order", "states", "topology"})

EXECUTION_TF_STATES = frozenset({
    "RANGE", "SHADOW_PENDING", "SWEEP", "DISPLACEMENT", "EXPANSION",
    "EXPIRED", "RETEST", "EXECUTION", "RESOLUTION",
})
PARENT_TF_STATES = frozenset({"RANGE_C1", "MANIPULATION_C2", "DISTRIBUTION_C3"})

SCHEMA_DIM = {"2.0": 35, "3.0": 38, "4.0": 39, "5.0": 48}

L0_PK = ("instrument", "timeframe", "bar_open_ts", "corpus_sha256")
L0_PAYLOAD = ("open", "high", "low", "close", "volume")
L1_EXTRA = ("schema_version", "FEATURE_ORDER_HASH", "feature_dim", "values", "feature_names")
L2_EXTRA = ("fm_id", "ontology_states_hash", "state")
L3_OCC_EXTRA = ("producer_id", "topology_id", "track_id", "state")
L3_EVT_EXTRA = ("producer_id", "topology_id", "track_id", "state_from", "state_to", "event_kind")
L4_EXTRA = ("direction", "entry_px", "sl_px", "geometry_kind", "geometry_schema")
L5_BASIS = ("walk_kernel", "cost_model_id", "fill_model_id")
# Payload extensions (identity contract §9.4). Do not change L5 equality.
L5_PAYLOAD = ("y_R_gross", "mfe", "mae", "duration_bars", "exit_reason")
# Named engine-close basis. Bound on the record; never inferred on load.
ENGINE_CLOSE_WALK = "backtest_ledger"
ENGINE_CLOSE_COST = "none_gross"
ENGINE_CLOSE_FILL = "engine_intrabar"
L5_CLOSE_EVENTS = frozenset({
    "TRADE_STOPPED", "TRADE_TP2", "TRADE_STOPPED_STRUCTURAL", "TRADE_ABORTED",
})
