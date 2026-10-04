"""Probe artifact governance helpers."""
from __future__ import annotations

from typing import Any

FORBIDDEN_KEYS = ("p_value", "pvalue", "ci", "conf_int", "verdict", "significant", "decision")


def assert_no_claim_keys(obj: Any, path: str = "") -> None:
    """A number that does not exist cannot be quoted. Enforce that mechanically."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in FORBIDDEN_KEYS:
                raise AssertionError(f"forbidden claim key '{k}' at {path}")
            assert_no_claim_keys(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for j, v in enumerate(obj):
            assert_no_claim_keys(v, f"{path}[{j}]")
