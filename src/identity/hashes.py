"""Identity hashes. Algorithms are frozen in the identity contract, not imported from HEAD schema."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

# Content-fingerprinted memo. Bare id() is unsafe: CPython reuses ids after GC
# and previously mixed unrelated snapshot bytes (1-month IDENTITY_MISMATCH).
# A cache hit requires the same id AND a content probe (len + head/mid/tail).
_SHA_CACHE: dict[int, tuple[int, bytes, str]] = {}


def _content_probe(data: bytes) -> bytes:
    n = len(data)
    if n <= 192:
        return data
    mid = n // 2
    return data[:64] + data[mid:mid + 64] + data[-64:]


def sha256_bytes(data: bytes) -> str:
    ident = id(data)
    n = len(data)
    probe = _content_probe(data)
    hit = _SHA_CACHE.get(ident)
    if hit is not None and hit[0] == n and hit[1] == probe:
        return hit[2]
    digest = hashlib.sha256(data).hexdigest()
    _SHA_CACHE[ident] = (n, probe, digest)
    return digest


def feature_order_hash(names: Sequence[str]) -> str:
    """SHA-256[:16] of ordered names. Matches identity contract / feature_schema algorithm
    without importing CANONICAL_FEATURES (HEAD substitution is forbidden on load).
    """
    payload = json.dumps(list(names), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()[:16]


def canonical_json_hash(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def round_px(value: float) -> float:
    return float(f"{float(value):.8f}")
