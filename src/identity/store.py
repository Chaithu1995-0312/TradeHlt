"""File-backed identity store: Class A snapshots, Class B records, Class C bindings.

Append-only. Writer will not emit a Class B record without the Class A snapshot
the Identity Check requires. Reader returns PRESERVED records only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from identity.check import CheckResult, identity_check, identity_check_event_series
from identity.hashes import feature_order_hash, round_px, sha256_bytes
from identity.tokens import L5_BASIS, LAYERS, STATUS_PRESERVED, STATUS_UNIDENTIFIED


def _pk_tuple(layer: str, record: Mapping[str, Any]) -> tuple:
    base = (
        record.get("instrument"),
        record.get("timeframe"),
        record.get("bar_open_ts"),
        record.get("corpus_sha256"),
    )
    if layer == "L0":
        return base
    if layer == "L1":
        return base + (record.get("schema_version"), record.get("FEATURE_ORDER_HASH"))
    if layer == "L2":
        return base + (record.get("fm_id"), record.get("ontology_states_hash"))
    if layer == "L3_OCCUPANCY":
        return base + (record.get("producer_id"), record.get("topology_id"), record.get("track_id"))
    if layer == "L3_EVENT":
        return base + (
            record.get("producer_id"), record.get("topology_id"), record.get("track_id"),
            record.get("state_from"), record.get("state_to"), record.get("event_kind"),
        )
    if layer == "L4":
        return base + (
            record.get("direction"), record.get("entry_px"), record.get("sl_px"),
            record.get("geometry_kind"), record.get("geometry_schema"),
        )
    if layer == "L5":
        return base + (
            record.get("direction"), record.get("entry_px"), record.get("sl_px"),
            record.get("geometry_kind"), record.get("geometry_schema"),
            record.get("walk_kernel"), record.get("cost_model_id"), record.get("fill_model_id"),
        )
    return base


class IdentityStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.objects = self.root / "objects"
        self.records_dir = self.root / "records"
        self.bindings_path = self.root / "bindings" / "bindings.jsonl"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.bindings_path.parent.mkdir(parents=True, exist_ok=True)
        self._pk_seen: set[tuple] = set()
        self._bindings_index: dict[tuple, dict[str, str]] = {}
        self._record_fhs: dict[str, Any] = {}
        self._bindings_fh: Any = None
        self._snap_cache: dict[str, bytes] = {}
        self._verified_digests: set[str] = set()
        self._load_pk_index()
        self._load_bindings_index()

    def _load_pk_index(self) -> None:
        for layer in LAYERS:
            path = self._layer_path(layer)
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                self._pk_seen.add((layer, _pk_tuple(layer, rec)))

    def _load_bindings_index(self) -> None:
        if not self.bindings_path.is_file():
            return
        for line in self.bindings_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            pk = tuple(row.get("pk") or [])
            self._bindings_index[(row.get("layer"), pk)] = dict(row.get("snapshots") or {})

    def _layer_path(self, layer: str) -> Path:
        return self.records_dir / f"{layer}.jsonl"

    def put_snapshot(self, kind: str, data: bytes) -> str:
        digest = sha256_bytes(data)
        dest = self.objects / digest
        if dest.exists():
            if digest not in self._verified_digests:
                if dest.read_bytes() != data:
                    dest.write_bytes(data)
                self._verified_digests.add(digest)
        else:
            dest.write_bytes(data)
            self._verified_digests.add(digest)
        self._snap_cache[digest] = data
        return digest

    def get_snapshot(self, digest: str) -> bytes | None:
        cached = self._snap_cache.get(digest)
        if cached is not None:
            return cached
        p = self.objects / digest
        if not p.is_file():
            return None
        blob = p.read_bytes()
        self._snap_cache[digest] = blob
        return blob

    def bind(self, layer: str, record: Mapping[str, Any], snapshot_digests: Mapping[str, str]) -> None:
        line = json.dumps({
            "layer": layer,
            "pk": list(_pk_tuple(layer, record)),
            "snapshots": dict(snapshot_digests),
        }, sort_keys=True)
        if self._bindings_fh is None:
            self._bindings_fh = self.bindings_path.open("a", encoding="utf-8")
        self._bindings_fh.write(line + "\n")
        self._bindings_index[(layer, tuple(_pk_tuple(layer, record)))] = dict(snapshot_digests)

    def write(self, layer: str, record: dict[str, Any], snapshots: Mapping[str, bytes]) -> CheckResult:
        """Persist Class A then Class B then Class C. Refuses PK reuse. Does not infer fields."""
        rec = dict(record)
        for key in ("entry_px", "sl_px"):
            if key in rec and rec[key] is not None:
                rec[key] = round_px(rec[key])
        if layer == "L1" and "feature_names" in rec and "FEATURE_ORDER_HASH" not in rec:
            rec["FEATURE_ORDER_HASH"] = feature_order_hash([str(n) for n in rec["feature_names"]])
        probe = identity_check(layer, rec, snapshots=snapshots)
        if not probe.preserved:
            return probe
        key = (layer, _pk_tuple(layer, rec))
        if key in self._pk_seen:
            return CheckResult(
                status=STATUS_UNIDENTIFIED,
                layer=layer,
                reasons=("PK reuse forbidden",),
                record=None,
            )
        digests: dict[str, str] = {}
        for kind, blob in snapshots.items():
            digests[kind] = self.put_snapshot(kind, blob)
        fh = self._record_fhs.get(layer)
        if fh is None:
            fh = self._layer_path(layer).open("a", encoding="utf-8")
            self._record_fhs[layer] = fh
        fh.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        if len(self._pk_seen) % 2000 == 0:
            fh.flush()
            if self._bindings_fh is not None:
                self._bindings_fh.flush()
        self.bind(layer, rec, digests)
        self._pk_seen.add(key)
        return CheckResult(status=STATUS_PRESERVED, layer=layer, record=rec)

    def write_l5_outcome(
        self,
        record: dict[str, Any],
        snapshots: Mapping[str, bytes] | None = None,
    ) -> CheckResult:
        """Write an L5 Class B record. Missing walk/cost/fill is UNIDENTIFIED, not defaulted."""
        rec = dict(record)
        for key in L5_BASIS:
            if rec.get(key) in (None, ""):
                return CheckResult(
                    status=STATUS_UNIDENTIFIED,
                    layer="L5",
                    reasons=(f"{key} missing; HEAD default is illegal",),
                    record=None,
                )
        return self.write("L5", rec, snapshots or {})

    def _binding_for(self, layer: str, record: Mapping[str, Any]) -> dict[str, str]:
        return dict(self._bindings_index.get((layer, _pk_tuple(layer, record))) or {})

    def read(self, layer: str, record: Mapping[str, Any]) -> CheckResult:
        """Load only through Identity Check. Missing snapshots ⇒ UNIDENTIFIED, never HEAD fill."""
        bound = self._binding_for(layer, record)
        snaps: dict[str, bytes] = {}
        for kind, digest in bound.items():
            blob = self.get_snapshot(digest)
            if blob is None:
                return CheckResult(
                    status=STATUS_UNIDENTIFIED,
                    layer=layer,
                    reasons=(f"bound snapshot {kind} hash {digest} not on disk",),
                    record=None,
                )
            snaps[kind] = blob
        return identity_check(layer, record, snapshots=snaps)

    def read_event_series(self, events: list[Mapping[str, Any]]) -> CheckResult:
        """Series completeness. Does not fold into occupancy."""
        return identity_check_event_series(events)

    def close(self) -> None:
        for fh in self._record_fhs.values():
            fh.close()
        self._record_fhs.clear()
        if self._bindings_fh is not None:
            self._bindings_fh.close()
            self._bindings_fh = None

    def scan(self, layer: str) -> list[CheckResult]:
        """Every stored record, each passed through Identity Check. Failures are not omitted silently;
        they remain UNIDENTIFIED / MISMATCH / INCOMPLETE and carry no payload as identified.
        """
        fh = self._record_fhs.get(layer)
        if fh is not None:
            fh.flush()
        if self._bindings_fh is not None:
            self._bindings_fh.flush()
        path = self._layer_path(layer)
        if not path.is_file():
            return []
        out: list[CheckResult] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                out.append(self.read(layer, rec))
        return out
