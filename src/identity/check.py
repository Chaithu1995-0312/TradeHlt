"""Identity Check — the only legal load path.

Does not import feature_pipeline, feature_states, feature_schema, crt_engine,
crt_state_resolver, state_identity, TradeLib, or any walk/cost/fill kernel.
Hash comparison uses caller-supplied Class A snapshot bytes, never HEAD
declarations. Missing cost_model_id / fill_model_id / walk_kernel is
UNIDENTIFIED — never a default.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from identity.hashes import feature_order_hash, sha256_bytes
from identity.tokens import (
    COST_MODEL_IDS,
    DIRECTIONS,
    EVENT_KINDS,
    EXECUTION_TF_STATES,
    FILL_MODEL_IDS,
    GEOMETRY_KINDS,
    GEOMETRY_SCHEMAS,
    L0_PAYLOAD,
    L0_PK,
    L5_PAYLOAD,
    PARENT_TF_STATES,
    PRODUCER_IDS,
    SCHEMA_DIM,
    SCHEMA_VERSIONS,
    STATUS_IDENTITY_INCOMPLETE,
    STATUS_IDENTITY_MISMATCH,
    STATUS_PRESERVED,
    STATUS_UNIDENTIFIED,
    TIMEFRAMES,
    TRACK_IDS,
    WALK_KERNELS,
)

_MISSING = object()


@dataclass(frozen=True)
class CheckResult:
    status: str
    layer: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    record: Mapping[str, Any] | None = None

    @property
    def preserved(self) -> bool:
        return self.status == STATUS_PRESERVED


def _fail(layer: str, status: str, *reasons: str) -> CheckResult:
    return CheckResult(status=status, layer=layer, reasons=reasons, record=None)


def _need(record: Mapping[str, Any], keys: Sequence[str], layer: str) -> CheckResult | None:
    missing = [k for k in keys if record.get(k, _MISSING) in (_MISSING, None, "")]
    if missing:
        return _fail(layer, STATUS_UNIDENTIFIED, f"missing PK/required fields: {missing}")
    return None


def _closed(value: Any, allowed: frozenset, name: str, layer: str) -> CheckResult | None:
    if value not in allowed:
        return _fail(layer, STATUS_UNIDENTIFIED, f"{name}={value!r} not in closed vocabulary")
    return None


def identity_check(
    layer: str,
    record: Mapping[str, Any],
    *,
    snapshots: Mapping[str, bytes] | None = None,
) -> CheckResult:
    """Store→Load→Identity Check. snapshots keyed by kind (corpus/feature_order/states/topology)."""
    snaps = snapshots or {}
    if layer == "L0":
        return _check_l0(record, snaps)
    if layer == "L1":
        return _check_l1(record, snaps)
    if layer == "L2":
        return _check_l2(record, snaps)
    if layer == "L3_OCCUPANCY":
        return _check_l3_occupancy(record, snaps)
    if layer == "L3_EVENT":
        return _check_l3_event(record, snaps)
    if layer == "L4":
        return _check_l4(record, snaps)
    if layer == "L5":
        return _check_l5(record, snaps)
    return _fail(layer, STATUS_UNIDENTIFIED, f"unknown layer {layer!r}")


def identity_check_event_series(events: Sequence[Mapping[str, Any]]) -> CheckResult:
    """Fold-completeness on a stored event series. Does not produce occupancy."""
    if not events:
        return _fail("L3_EVENT", STATUS_UNIDENTIFIED, "empty event series")
    kinds = {e.get("event_kind") for e in events}
    if "STATE_TRANSITION" in kinds and "RESET" not in kinds:
        return _fail(
            "L3_EVENT",
            STATUS_IDENTITY_INCOMPLETE,
            "STATE_TRANSITION present and RESET absent",
        )
    for ev in events:
        r = identity_check("L3_EVENT", ev, snapshots={})
        if not r.preserved:
            return r
    return CheckResult(status=STATUS_PRESERVED, layer="L3_EVENT", reasons=("series complete",), record=None)


def _check_l0(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    bad = _need(record, L0_PK, "L0")
    if bad:
        return bad
    bad = _closed(record["timeframe"], TIMEFRAMES, "timeframe", "L0")
    if bad:
        return bad
    for k in L0_PAYLOAD:
        if k not in record:
            return _fail("L0", STATUS_UNIDENTIFIED, f"missing payload {k}")
    corpus = snaps.get("corpus")
    if corpus is None:
        return _fail("L0", STATUS_UNIDENTIFIED, "corpus snapshot bytes absent; cannot validate corpus_sha256")
    digest = sha256_bytes(corpus)
    if digest != record["corpus_sha256"]:
        return _fail("L0", STATUS_IDENTITY_MISMATCH, "corpus_sha256 does not match snapshot bytes")
    return CheckResult(status=STATUS_PRESERVED, layer="L0", record=dict(record))


def _check_l1(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    bad = _need(record, L0_PK + ("schema_version", "FEATURE_ORDER_HASH", "feature_dim", "values"), "L1")
    if bad:
        return bad
    bad = _closed(record["schema_version"], SCHEMA_VERSIONS, "schema_version", "L1")
    if bad:
        return bad
    values = record["values"]
    if not isinstance(values, list):
        return _fail("L1", STATUS_UNIDENTIFIED, "values must be a list")
    dim = int(record["feature_dim"])
    if len(values) != dim:
        return _fail("L1", STATUS_IDENTITY_MISMATCH, f"len(values)={len(values)} != feature_dim={dim}")
    expected_dim = SCHEMA_DIM.get(record["schema_version"])
    if expected_dim is not None and dim != expected_dim:
        return _fail("L1", STATUS_IDENTITY_MISMATCH, f"feature_dim={dim} != family dim {expected_dim}")
    names = record.get("feature_names")
    order_bytes = snaps.get("feature_order")
    if order_bytes is None and not names:
        return _fail("L1", STATUS_UNIDENTIFIED, "feature_order snapshot absent; cannot validate FEATURE_ORDER_HASH")
    if names is None and order_bytes is not None:
        names = json.loads(order_bytes.decode())
    if not isinstance(names, list):
        return _fail("L1", STATUS_UNIDENTIFIED, "feature_names must be a list")
    computed = feature_order_hash([str(n) for n in names])
    if computed != record["FEATURE_ORDER_HASH"]:
        return _fail("L1", STATUS_IDENTITY_MISMATCH, "FEATURE_ORDER_HASH does not match stored name order")
    if len(names) != dim:
        return _fail("L1", STATUS_IDENTITY_MISMATCH, "feature_names length != feature_dim")
    return CheckResult(status=STATUS_PRESERVED, layer="L1", record=dict(record))


def _check_l2(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    bad = _need(record, L0_PK + ("fm_id", "ontology_states_hash", "state"), "L2")
    if bad:
        return bad
    block = snaps.get("states")
    if block is None:
        return _fail("L2", STATUS_UNIDENTIFIED, "states snapshot absent; cannot validate ontology_states_hash")
    digest = sha256_bytes(block)
    if digest != record["ontology_states_hash"]:
        return _fail("L2", STATUS_IDENTITY_MISMATCH, "ontology_states_hash does not match states snapshot")
    return CheckResult(status=STATUS_PRESERVED, layer="L2", record=dict(record))


def _l3_common(record: Mapping[str, Any], layer: str) -> CheckResult | None:
    bad = _need(record, L0_PK + ("producer_id", "topology_id", "track_id"), layer)
    if bad:
        return bad
    bad = _closed(record["producer_id"], PRODUCER_IDS, "producer_id", layer)
    if bad:
        return bad
    bad = _closed(record["track_id"], TRACK_IDS, "track_id", layer)
    if bad:
        return bad
    return None


def _check_l3_occupancy(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    bad = _l3_common(record, "L3_OCCUPANCY")
    if bad:
        return bad
    if not record.get("state"):
        return _fail("L3_OCCUPANCY", STATUS_UNIDENTIFIED, "missing occupancy state")
    legal = EXECUTION_TF_STATES if record["track_id"] == "execution_tf" else PARENT_TF_STATES
    bad = _closed(record["state"], legal, "state", "L3_OCCUPANCY")
    if bad:
        return bad
    topo = snaps.get("topology")
    if topo is None:
        return _fail("L3_OCCUPANCY", STATUS_UNIDENTIFIED, "topology snapshot absent; cannot validate topology_id")
    if sha256_bytes(topo) != record["topology_id"]:
        return _fail("L3_OCCUPANCY", STATUS_IDENTITY_MISMATCH, "topology_id does not match topology snapshot")
    return CheckResult(status=STATUS_PRESERVED, layer="L3_OCCUPANCY", record=dict(record))


def _check_l3_event(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    bad = _l3_common(record, "L3_EVENT")
    if bad:
        return bad
    bad = _need(record, ("state_from", "state_to", "event_kind"), "L3_EVENT")
    if bad:
        return bad
    bad = _closed(record["event_kind"], EVENT_KINDS, "event_kind", "L3_EVENT")
    if bad:
        return bad
    topo = snaps.get("topology")
    if topo is not None and sha256_bytes(topo) != record["topology_id"]:
        return _fail("L3_EVENT", STATUS_IDENTITY_MISMATCH, "topology_id does not match topology snapshot")
    return CheckResult(status=STATUS_PRESERVED, layer="L3_EVENT", record=dict(record))


def _check_l4(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    keys = L0_PK + ("direction", "entry_px", "sl_px", "geometry_kind", "geometry_schema")
    bad = _need(record, keys, "L4")
    if bad:
        return bad
    bad = _closed(record["direction"], DIRECTIONS, "direction", "L4")
    if bad:
        return bad
    bad = _closed(record["geometry_kind"], GEOMETRY_KINDS, "geometry_kind", "L4")
    if bad:
        return bad
    bad = _closed(record["geometry_schema"], GEOMETRY_SCHEMAS, "geometry_schema", "L4")
    if bad:
        return bad
    if record["geometry_kind"] == "detection_stream":
        # identifiable, but not loadable as engine_trade — still a valid L4 of that kind
        pass
    return CheckResult(status=STATUS_PRESERVED, layer="L4", record=dict(record))


def _check_l5(record: Mapping[str, Any], snaps: Mapping[str, bytes]) -> CheckResult:
    l4 = _check_l4(record, snaps)
    if not l4.preserved:
        return CheckResult(status=l4.status, layer="L5", reasons=("L4 parent " + "; ".join(l4.reasons),), record=None)
    bad = _need(record, ("walk_kernel", "cost_model_id", "fill_model_id") + L5_PAYLOAD, "L5")
    if bad:
        return bad
    bad = _closed(record["walk_kernel"], WALK_KERNELS, "walk_kernel", "L5")
    if bad:
        return bad
    bad = _closed(record["cost_model_id"], COST_MODEL_IDS, "cost_model_id", "L5")
    if bad:
        return bad
    bad = _closed(record["fill_model_id"], FILL_MODEL_IDS, "fill_model_id", "L5")
    if bad:
        return bad
    if record["geometry_kind"] == "detection_stream" and record["walk_kernel"] == "backtest_ledger":
        return _fail("L5", STATUS_UNIDENTIFIED, "CONTAMINATED: detection_stream cannot bind as backtest_ledger")
    return CheckResult(status=STATUS_PRESERVED, layer="L5", record=dict(record))
