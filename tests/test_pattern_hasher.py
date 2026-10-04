"""
test_pattern_hasher.py
================================================================================
Tests for Phase D — pattern_hasher utilities.

Coverage:
  - _CRT_PATH_CODES completeness (all 7 canonical states present)
  - _CRT_PATH_DECODE is exact inverse
  - encode_crt_path: maps to_state → compact code, unknown → first char
  - decode_crt_path: maps compact code → full state name, unknown → pass-through
  - encode then decode round-trips for all canonical states
  - compute_pattern_hash: returns 16-char hex string
  - compute_pattern_hash: same inputs → same hash (deterministic)
  - compute_pattern_hash: different regime → different hash
  - compute_pattern_hash: sweep_type kwarg overrides features["sweep_type"]
  - compute_pattern_hash: missing keys use defaults (backward compatible)
  - compute_pattern_hash: floating-point rounding does NOT produce hash churn
    (values within the rounding tolerance hash identically)
================================================================================
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import pytest

from utils.pattern_hasher import (
    _CRT_PATH_CODES,
    _CRT_PATH_DECODE,
    compute_pattern_hash,
    decode_crt_path,
    encode_crt_path,
)


# ─── Minimal CRTTransitionEvent stub (no real import needed) ──────────────────

@dataclass
class _FakeTransition:
    to_state: str
    from_state: str = ""
    sweep_type: Optional[str] = None
    disp_strength: Optional[float] = None


# ─── Canonical state codes ────────────────────────────────────────────────────

CANONICAL_STATES = [
    "RANGE", "SWEEP", "DISPLACEMENT", "EXPANSION",
    "RETEST", "EXECUTION", "RESOLUTION",
]


class TestCRTPathCodes:
    def test_all_canonical_states_present(self):
        for s in CANONICAL_STATES:
            assert s in _CRT_PATH_CODES, f"Missing code for state: {s}"

    def test_all_codes_are_single_chars(self):
        for state, code in _CRT_PATH_CODES.items():
            assert len(code) == 1, f"Code for {state} is not single char: {code!r}"

    def test_codes_are_unique(self):
        codes = list(_CRT_PATH_CODES.values())
        assert len(codes) == len(set(codes)), "Duplicate codes found"

    def test_decode_is_exact_inverse(self):
        for state, code in _CRT_PATH_CODES.items():
            assert _CRT_PATH_DECODE[code] == state


# ─── encode_crt_path ──────────────────────────────────────────────────────────

class TestEncodeCrtPath:
    def test_empty_path_returns_empty(self):
        assert encode_crt_path([]) == []

    def test_canonical_states_encode_correctly(self):
        path = [_FakeTransition(to_state=s) for s in CANONICAL_STATES]
        codes = encode_crt_path(path)
        assert codes == [_CRT_PATH_CODES[s] for s in CANONICAL_STATES]

    def test_unknown_state_uses_first_char(self):
        path = [_FakeTransition(to_state="FOOBAR")]
        codes = encode_crt_path(path)
        assert codes == ["F"]

    def test_empty_to_state_returns_question_mark(self):
        path = [_FakeTransition(to_state="")]
        codes = encode_crt_path(path)
        assert codes == ["?"]

    def test_typical_sequence(self):
        path = [
            _FakeTransition("SWEEP"),
            _FakeTransition("DISPLACEMENT"),
            _FakeTransition("RETEST"),
            _FakeTransition("EXECUTION"),
        ]
        assert encode_crt_path(path) == ["S", "D", "T", "X"]


# ─── decode_crt_path ──────────────────────────────────────────────────────────

class TestDecodeCrtPath:
    def test_empty_codes_returns_empty(self):
        assert decode_crt_path([]) == []

    def test_canonical_codes_decode_correctly(self):
        codes = list(_CRT_PATH_CODES.values())
        names = decode_crt_path(codes)
        assert names == list(_CRT_PATH_CODES.keys())

    def test_unknown_code_returned_unchanged(self):
        assert decode_crt_path(["Q"]) == ["Q"]

    def test_typical_sequence(self):
        assert decode_crt_path(["S", "D", "T", "X"]) == [
            "SWEEP", "DISPLACEMENT", "RETEST", "EXECUTION"
        ]


# ─── Round-trip ───────────────────────────────────────────────────────────────

class TestRoundTrip:
    @pytest.mark.parametrize("state", CANONICAL_STATES)
    def test_encode_then_decode(self, state):
        path = [_FakeTransition(to_state=state)]
        codes = encode_crt_path(path)
        names = decode_crt_path(codes)
        assert names == [state]


# ─── compute_pattern_hash ─────────────────────────────────────────────────────

_BASE_FEATURES = {
    "body_ratio":    0.75,
    "retest_depth":  0.18,
    "disp_strength": 1.80,
    "session":       "london",
    "sweep_type":    "TYPE-B",
    "double_sweep":  False,
    "_regime":       "TRENDING",
}


class TestComputePatternHash:
    def test_returns_16_char_hex_string(self):
        h = compute_pattern_hash(_BASE_FEATURES)
        assert isinstance(h, str)
        assert len(h) == 16
        assert re.fullmatch(r"[0-9a-f]+", h), f"Not hex: {h!r}"

    def test_deterministic_same_inputs(self):
        h1 = compute_pattern_hash(dict(_BASE_FEATURES))
        h2 = compute_pattern_hash(dict(_BASE_FEATURES))
        assert h1 == h2

    def test_different_regime_different_hash(self):
        feat_trending = dict(_BASE_FEATURES, _regime="TRENDING")
        feat_ranging  = dict(_BASE_FEATURES, _regime="RANGING")
        assert compute_pattern_hash(feat_trending) != compute_pattern_hash(feat_ranging)

    def test_sweep_type_kwarg_overrides_features(self):
        feat = dict(_BASE_FEATURES, sweep_type="TYPE-A")
        h_via_feat = compute_pattern_hash(feat)
        h_via_kwarg = compute_pattern_hash(feat, sweep_type="TYPE-B")
        assert h_via_feat != h_via_kwarg

    def test_sweep_type_kwarg_none_falls_back_to_features(self):
        feat = dict(_BASE_FEATURES, sweep_type="TYPE-B")
        h_kwarg_none    = compute_pattern_hash(feat, sweep_type=None)
        h_from_features = compute_pattern_hash(feat)
        assert h_kwarg_none == h_from_features

    def test_missing_keys_use_defaults_no_error(self):
        """Empty features dict must not raise — backward compatible."""
        h = compute_pattern_hash({})
        assert len(h) == 16

    def test_rounding_prevents_hash_churn_body_ratio(self):
        """Values within the 2-decimal rounding tolerance hash identically."""
        feat_a = dict(_BASE_FEATURES, body_ratio=0.750001)
        feat_b = dict(_BASE_FEATURES, body_ratio=0.749999)
        # Both round to 0.75
        assert compute_pattern_hash(feat_a) == compute_pattern_hash(feat_b)

    def test_rounding_prevents_hash_churn_disp_strength(self):
        """disp_strength rounds to 1 decimal — 1.80 and 1.84 both → 1.8."""
        feat_a = dict(_BASE_FEATURES, disp_strength=1.80)
        feat_b = dict(_BASE_FEATURES, disp_strength=1.84)
        assert compute_pattern_hash(feat_a) == compute_pattern_hash(feat_b)

    def test_different_session_different_hash(self):
        feat_london   = dict(_BASE_FEATURES, session="london")
        feat_new_york = dict(_BASE_FEATURES, session="new_york")
        assert compute_pattern_hash(feat_london) != compute_pattern_hash(feat_new_york)

    def test_double_sweep_affects_hash(self):
        feat_no  = dict(_BASE_FEATURES, double_sweep=False)
        feat_yes = dict(_BASE_FEATURES, double_sweep=True)
        assert compute_pattern_hash(feat_no) != compute_pattern_hash(feat_yes)
