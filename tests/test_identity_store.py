"""Phase 4 floor: Identity Check without recompute paths.

CANONICAL_LAYER_IDENTITY_CONTRACT.md v1.0.0
STORAGE_PRESERVATION_CONTRACT.md v1.0.0
PHYSICAL_STORAGE_ARCHITECTURE.md v1.0.0
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from identity.check import identity_check, identity_check_event_series
from identity.hashes import canonical_json_hash, feature_order_hash, sha256_bytes
from identity.outcome import L5WriteError, build_l5_record, engine_close_basis
from identity.query import IdentityQuery
from identity.store import IdentityStore
from identity.tokens import (
    STATUS_IDENTITY_INCOMPLETE,
    STATUS_IDENTITY_MISMATCH,
    STATUS_PRESERVED,
    STATUS_UNIDENTIFIED,
)

_REPO = Path(__file__).resolve().parents[1]
_PKG = _REPO / "src" / "identity"

FORBIDDEN_RUNTIME_MODULES = (
    "features.feature_pipeline",
    "features.feature_states",
    "features.feature_schema",
    "features.crt_state_resolver",
    "config_layer.crt_engine_v2",
    "config_layer.state_identity",
    "config_layer.state_topology",
    "TradeLib",
    "trade_lib",
    "runtime.backtest_v2",
)

L0 = {
    "instrument": "XAUUSD",
    "timeframe": "M15",
    "bar_open_ts": "2025-01-01T10:00:00",
    "open": 2600.0, "high": 2601.0, "low": 2599.0, "close": 2600.5, "volume": 10.0,
}
NAMES = ["open", "high", "low", "close"] + [f"f{i}" for i in range(44)]  # 48 names
assert len(NAMES) == 48
STATES = [{"value": 0, "name": "NoSpike"}, {"value": 1, "name": "VolumeSpike"}]
TOPOLOGY = {"RANGE": ["SWEEP", "SHADOW_PENDING"], "SWEEP": ["DISPLACEMENT"]}


def _corpus() -> bytes:
    return b"timestamp,open,high,low,close,volume\n2025-01-01T10:00:00,2600,2601,2599,2600.5,10\n"


def _l0() -> tuple[dict, dict[str, bytes]]:
    blob = _corpus()
    rec = {**L0, "corpus_sha256": sha256_bytes(blob)}
    return rec, {"corpus": blob}


def _runtime_imports(tree: ast.Module):
    type_only: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        guarded = (
            (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        )
        if guarded:
            for inner in node.body:
                type_only.add(id(inner))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in type_only:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def _l5_payload(**overrides):
    body = {
        "y_R_gross": -1.0,
        "mfe": 0.2,
        "mae": 1.0,
        "duration_bars": 3,
        "exit_reason": "TRADE_STOPPED",
    }
    body.update(overrides)
    return body


@pytest.mark.parametrize("rel", ["check.py", "store.py", "query.py", "outcome.py"])
def test_no_recompute_producer_imports(rel: str):
    src = (_PKG / rel).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = _runtime_imports(tree)
    hits = [m for m in FORBIDDEN_RUNTIME_MODULES if any(
        imp == m or imp.startswith(m + ".") for imp in imported
    )]
    assert hits == [], f"{rel} imports recompute producers: {hits}"


def test_l0_roundtrip_preserved(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    w = store.write("L0", rec, snaps)
    assert w.status == STATUS_PRESERVED
    r = store.read("L0", rec)
    assert r.status == STATUS_PRESERVED
    assert r.record["corpus_sha256"] == rec["corpus_sha256"]


def test_l0_missing_corpus_snapshot_unidentified():
    rec, _ = _l0()
    r = identity_check("L0", rec, snapshots={})
    assert r.status == STATUS_UNIDENTIFIED
    assert r.record is None


def test_l0_hash_mismatch():
    rec, snaps = _l0()
    r = identity_check("L0", rec, snapshots={"corpus": b"other-bytes"})
    assert r.status == STATUS_IDENTITY_MISMATCH
    assert r.record is None


def test_l0_same_ts_different_corpus_are_different(tmp_path: Path):
    rec_a, snaps_a = _l0()
    blob_b = _corpus() + b"#b"
    rec_b = {**L0, "corpus_sha256": sha256_bytes(blob_b)}
    store = IdentityStore(tmp_path)
    assert store.write("L0", rec_a, snaps_a).preserved
    assert store.write("L0", rec_b, {"corpus": blob_b}).preserved
    assert rec_a["corpus_sha256"] != rec_b["corpus_sha256"]


def test_l1_48_values_without_hash_unidentified():
    rec, snaps = _l0()
    rec = {**rec, "schema_version": "5.0", "feature_dim": 48, "values": [0.0] * 48}
    r = identity_check("L1", rec, snapshots=snaps)
    assert r.status == STATUS_UNIDENTIFIED


def test_l1_order_hash_must_match_stored_names():
    rec, snaps = _l0()
    names = list(NAMES)
    rec = {
        **rec,
        "schema_version": "5.0",
        "feature_dim": 48,
        "values": [0.0] * 48,
        "feature_names": names,
        "FEATURE_ORDER_HASH": feature_order_hash(names),
    }
    order_bytes = json.dumps(names, sort_keys=False).encode()
    r = identity_check("L1", rec, snapshots={**snaps, "feature_order": order_bytes})
    assert r.status == STATUS_PRESERVED
    rec_bad = {**rec, "FEATURE_ORDER_HASH": "deadbeefdeadbeef"}
    r2 = identity_check("L1", rec_bad, snapshots={**snaps, "feature_order": order_bytes})
    assert r2.status == STATUS_IDENTITY_MISMATCH


def test_l2_states_hash_mismatch():
    rec, snaps = _l0()
    block = json.dumps(STATES, sort_keys=True, separators=(",", ":")).encode()
    rec = {
        **rec,
        "fm_id": "FM-063",
        "ontology_states_hash": sha256_bytes(block),
        "state": "VolumeSpike",
    }
    assert identity_check("L2", rec, snapshots={**snaps, "states": block}).preserved
    assert identity_check("L2", rec, snapshots={**snaps, "states": b"[]"}).status == STATUS_IDENTITY_MISMATCH


def test_l3_occupancy_not_folded_from_events(tmp_path: Path):
    rec, snaps = _l0()
    topo = json.dumps(TOPOLOGY, sort_keys=True, separators=(",", ":")).encode()
    occ = {
        **rec,
        "producer_id": "engine",
        "topology_id": sha256_bytes(topo),
        "track_id": "execution_tf",
        "state": "SWEEP",
    }
    store = IdentityStore(tmp_path)
    assert store.write("L3_OCCUPANCY", occ, {**snaps, "topology": topo}).preserved
    events = [
        {**occ, "state_from": "RANGE", "state_to": "SWEEP", "event_kind": "STATE_TRANSITION"},
    ]
    series = store.read_event_series(events)
    assert series.status == STATUS_IDENTITY_INCOMPLETE
    loaded = store.read("L3_OCCUPANCY", occ)
    assert loaded.status == STATUS_PRESERVED
    assert loaded.record["state"] == "SWEEP"


def test_l3_reset_required_in_event_series():
    rec, _ = _l0()
    rec = {
        **rec,
        "producer_id": "engine",
        "topology_id": "abc",
        "track_id": "execution_tf",
        "state_from": "RANGE",
        "state_to": "SWEEP",
        "event_kind": "STATE_TRANSITION",
    }
    r = identity_check_event_series([rec])
    assert r.status == STATUS_IDENTITY_INCOMPLETE
    reset = {**rec, "state_from": "SWEEP", "state_to": "RANGE", "event_kind": "RESET"}
    r2 = identity_check_event_series([rec, reset])
    assert r2.status == STATUS_PRESERVED


def test_l3_engine_and_resolver_are_distinct(tmp_path: Path):
    rec, snaps = _l0()
    topo = json.dumps(TOPOLOGY, sort_keys=True, separators=(",", ":")).encode()
    store = IdentityStore(tmp_path)
    a = {**rec, "producer_id": "engine", "topology_id": sha256_bytes(topo), "track_id": "execution_tf", "state": "RANGE"}
    b = {**a, "producer_id": "resolver"}
    assert store.write("L3_OCCUPANCY", a, {**snaps, "topology": topo}).preserved
    assert store.write("L3_OCCUPANCY", b, {**snaps, "topology": topo}).preserved


def test_l4_single_tp_not_dual(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    geo = {
        **rec,
        "direction": "long",
        "entry_px": 2600.0,
        "sl_px": 2590.0,
        "geometry_kind": "engine_trade",
        "geometry_schema": "single_tp",
        "tp_px": 2620.0,
    }
    dual = {**geo, "geometry_schema": "dual_tp_partial", "tp1_px": 2610.0, "tp2_px": 2620.0}
    assert store.write("L4", geo, snaps).preserved
    assert store.write("L4", dual, snaps).preserved


def test_l5_fill_model_splits_outcome(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    base = {
        **rec,
        "direction": "long",
        "entry_px": 2600.0,
        "sl_px": 2590.0,
        "geometry_kind": "engine_trade",
        "geometry_schema": "single_tp",
        "walk_kernel": "forward_walk_intrabar_fixed",
        "cost_model_id": "none_gross",
        "fill_model_id": "touch_exact",
        **_l5_payload(),
    }
    other = {**base, "fill_model_id": "sem016_adverse"}
    assert store.write("L5", base, snaps).preserved
    assert store.write("L5", other, snaps).preserved


def test_pk_reuse_forbidden(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    assert store.write("L0", rec, snaps).preserved
    again = store.write("L0", rec, snaps)
    assert again.status == STATUS_UNIDENTIFIED
    assert "PK reuse" in again.reasons[0]


def test_reader_does_not_emit_unidentified_payload():
    rec, _ = _l0()
    r = identity_check("L0", rec, snapshots={})
    assert r.record is None
    assert r.status == STATUS_UNIDENTIFIED


def test_writer_does_not_fill_missing_hash_from_head(tmp_path: Path):
    rec, snaps = _l0()
    rec = {**rec, "schema_version": "5.0", "feature_dim": 48, "values": [0.0] * 48}
    store = IdentityStore(tmp_path)
    w = store.write("L1", rec, snaps)
    assert w.status == STATUS_UNIDENTIFIED
    assert w.record is None


def test_query_omits_unidentified_and_does_not_recompute(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    store.write("L0", rec, snaps)
    (tmp_path / "records" / "L1.jsonl").write_text(
        json.dumps({**rec, "schema_version": "5.0", "feature_dim": 48, "values": [0.0] * 48}) + "\n",
        encoding="utf-8",
    )
    q = IdentityQuery(store)
    assert q.preserved("L1") == []
    checked = q.scan_checked("L1")
    assert checked[0].status == STATUS_UNIDENTIFIED
    assert checked[0].record is None


def test_replay_occupancy_not_folded_from_incomplete_events(tmp_path: Path):
    rec, snaps = _l0()
    topo = json.dumps(TOPOLOGY, sort_keys=True, separators=(",", ":")).encode()
    store = IdentityStore(tmp_path)
    store.write("L0", rec, snaps)
    occ = {
        **rec, "producer_id": "engine", "topology_id": sha256_bytes(topo),
        "track_id": "execution_tf", "state": "SWEEP",
    }
    ev = {
        **occ, "state_from": "RANGE", "state_to": "SWEEP", "event_kind": "STATE_TRANSITION",
    }
    store.write("L3_OCCUPANCY", occ, {**snaps, "topology": topo})
    store.write("L3_EVENT", ev, {**snaps, "topology": topo})
    replay = IdentityQuery(store).at_l0(rec)
    assert replay.recovered
    assert replay.l3_occupancy[0]["state"] == "SWEEP"
    assert replay.l3_event_series is not None
    assert replay.l3_event_series.status == STATUS_IDENTITY_INCOMPLETE


def test_replay_does_not_join_different_corpus(tmp_path: Path):
    rec_a, snaps_a = _l0()
    blob_b = _corpus() + b"#other"
    rec_b = {**L0, "corpus_sha256": sha256_bytes(blob_b)}
    store = IdentityStore(tmp_path)
    store.write("L0", rec_a, snaps_a)
    store.write("L0", rec_b, {"corpus": blob_b})
    names = list(NAMES)
    order = json.dumps(names, sort_keys=False).encode()
    l1_b = {
        **rec_b, "schema_version": "5.0", "feature_dim": 48, "values": [0.0] * 48,
        "feature_names": names, "FEATURE_ORDER_HASH": feature_order_hash(names),
    }
    store.write("L1", l1_b, {"corpus": blob_b, "feature_order": order})
    replay_a = IdentityQuery(store).at_l0(rec_a)
    assert replay_a.l1 == []
    replay_b = IdentityQuery(store).at_l0(rec_b)
    assert len(replay_b.l1) == 1


def test_outcomes_join_copied_l4_pk_only(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    geo = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "single_tp",
    }
    other = {**geo, "geometry_schema": "dual_tp_partial"}
    store.write("L4", geo, snaps)
    store.write("L4", other, snaps)
    out = {
        **geo, "walk_kernel": "forward_walk_intrabar_fixed",
        "cost_model_id": "none_gross", "fill_model_id": "touch_exact",
        **_l5_payload(y_R_gross=0.0),
    }
    store.write("L5", out, snaps)
    q = IdentityQuery(store)
    assert len(q.outcomes_for_geometry(geo)) == 1
    assert q.outcomes_for_geometry(other) == []


def test_replay_unidentified_l0_is_not_a_recovered_bar(tmp_path: Path):
    rec, _ = _l0()
    store = IdentityStore(tmp_path)
    replay = IdentityQuery(store).at_l0(rec)
    assert not replay.recovered
    assert replay.join == STATUS_UNIDENTIFIED


def test_sha256_cache_does_not_mix_equal_length_blobs():
    import hashlib
    a = b"A" * 500
    b = b"B" * 500
    assert sha256_bytes(a) == hashlib.sha256(a).hexdigest()
    assert sha256_bytes(b) == hashlib.sha256(b).hexdigest()
    assert sha256_bytes(a) != sha256_bytes(b)
    assert sha256_bytes(a) == sha256_bytes(a)


def test_put_snapshot_overwrites_corrupt_digest_file(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    digest = sha256_bytes(snaps["corpus"])
    dest = store.objects / digest
    dest.write_bytes(b"CORRUPT")
    w = store.write("L0", rec, snaps)
    assert w.status == STATUS_PRESERVED
    assert dest.read_bytes() == snaps["corpus"]
    r = store.read("L0", rec)
    assert r.status == STATUS_PRESERVED


def test_l5_missing_cost_is_unidentified_not_defaulted():
    rec, snaps = _l0()
    l5 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "single_tp",
        "walk_kernel": "backtest_ledger", "fill_model_id": "engine_intrabar",
        **_l5_payload(),
    }
    r = identity_check("L5", l5, snapshots=snaps)
    assert r.status == STATUS_UNIDENTIFIED
    assert r.record is None
    assert "cost_model_id" in r.reasons[0]


def test_l5_missing_fill_is_unidentified_not_defaulted():
    rec, snaps = _l0()
    l5 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "single_tp",
        "walk_kernel": "backtest_ledger", "cost_model_id": "none_gross",
        **_l5_payload(),
    }
    r = identity_check("L5", l5, snapshots=snaps)
    assert r.status == STATUS_UNIDENTIFIED
    assert "fill_model_id" in r.reasons[0]


def test_l5_empty_walk_is_unidentified():
    rec, snaps = _l0()
    l5 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "single_tp",
        "walk_kernel": "", "cost_model_id": "none_gross",
        "fill_model_id": "engine_intrabar", **_l5_payload(),
    }
    r = identity_check("L5", l5, snapshots=snaps)
    assert r.status == STATUS_UNIDENTIFIED


def test_l5_missing_path_stats_unidentified():
    rec, snaps = _l0()
    l5 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "single_tp",
        "walk_kernel": "backtest_ledger", "cost_model_id": "none_gross",
        "fill_model_id": "engine_intrabar", "y_R_gross": -1.0,
    }
    r = identity_check("L5", l5, snapshots=snaps)
    assert r.status == STATUS_UNIDENTIFIED


def test_write_l5_outcome_refuses_missing_cost(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    l5 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "dual_tp_partial",
        "walk_kernel": "backtest_ledger", "fill_model_id": "engine_intrabar",
        **_l5_payload(),
    }
    r = store.write_l5_outcome(l5, snaps)
    assert r.status == STATUS_UNIDENTIFIED
    assert r.record is None


def test_build_l5_record_refuses_inferred_cost():
    rec, _ = _l0()
    l4 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "dual_tp_partial",
    }
    with pytest.raises(L5WriteError):
        build_l5_record(l4, walk_kernel="backtest_ledger", cost_model_id="",
                        fill_model_id="engine_intrabar", **_l5_payload())


def test_l5_engine_close_roundtrip(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    l4 = {
        **rec, "direction": "long", "entry_px": 2600.0, "sl_px": 2590.0,
        "geometry_kind": "engine_trade", "geometry_schema": "dual_tp_partial",
    }
    store.write("L4", l4, snaps)
    l5 = build_l5_record(l4, **engine_close_basis(), **_l5_payload(y_R_gross=-1.0))
    w = store.write_l5_outcome(l5, snaps)
    assert w.status == STATUS_PRESERVED
    r = store.read("L5", l5)
    assert r.status == STATUS_PRESERVED
    assert r.record["walk_kernel"] == "backtest_ledger"
    assert r.record["cost_model_id"] == "none_gross"
    assert r.record["fill_model_id"] == "engine_intrabar"
    assert r.record["exit_reason"] == "TRADE_STOPPED"
    assert IdentityQuery(store).outcomes_for_geometry(l4)[0]["y_R_gross"] == -1.0


def test_l1_roundtrip_without_corpus_snapshot(tmp_path: Path):
    rec, snaps = _l0()
    store = IdentityStore(tmp_path)
    store.write("L0", rec, snaps)
    names = list(NAMES)
    order = json.dumps(names, sort_keys=False).encode()
    l1 = {
        **rec, "schema_version": "5.0", "feature_dim": 48, "values": [0.0] * 48,
        "feature_names": names, "FEATURE_ORDER_HASH": feature_order_hash(names),
    }
    w = store.write("L1", l1, {"feature_order": order})
    assert w.status == STATUS_PRESERVED
    r = store.read("L1", l1)
    assert r.status == STATUS_PRESERVED
