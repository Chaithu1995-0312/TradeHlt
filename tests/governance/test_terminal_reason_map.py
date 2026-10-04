"""V-12: every reset_to_range reason literal matches the terminal map."""

from __future__ import annotations

import copy

from semantics.registry import (
    ROOT,
    load_terminal_reason_map,
    reset_reason_literals,
    validate_all,
    validate_terminal_reasons,
)

# Leading literals the scanner must actually find. A tracer that drops calls stays red.
_REQUIRED = (
    "Sweep expired",
    "HTF changed:",
    "Session gap detected:",
    "trade_build_rejected:",
    "50% retrace hit",
    "1.618 extension hit",
    "stop_breached",
    "SHADOW_LEAK:",
    "Against parent-timeframe bias",
    "Against parent-timeframe objective",
    "resolver_founding",
    "resolver_founding_inputs_missing",
    "expansion_ttl_exceeded",
    "Not in discount zone",
    "Not in premium zone",
    "off_session_filter",
    "shadow_advisory_only",
    "Soft confirmation timeout",
    "Post-resolution reset",
)


def test_shipped_map_covers_the_engine_sources():
    assert validate_terminal_reasons(load_terminal_reason_map()) == []


def test_scanner_finds_the_known_reason_literals():
    found: list[str] = []
    unresolved: list[str] = []
    for rel in ("src/config_layer/crt_engine_v2.py", "src/runtime/backtest_v2.py"):
        literals, missing = reset_reason_literals(ROOT / rel)
        found.extend(literals)
        unresolved.extend(missing)
    assert unresolved == []
    for token in _REQUIRED:
        assert any(text == token or text.startswith(token) or token.startswith(text) for text in found), (
            token, found,
        )


def test_deleting_an_entry_fails_coverage():
    doc = copy.deepcopy(load_terminal_reason_map())
    doc["entries"] = [entry for entry in doc["entries"] if entry.get("reason") != "Sweep expired"]
    problems = validate_terminal_reasons(doc)
    assert any("Sweep expired" in item for item in problems), problems


def test_declared_class_vocabulary_must_match_the_code():
    doc = copy.deepcopy(load_terminal_reason_map())
    doc["classes"] = [c for c in doc["classes"] if c != "SPENT"]
    problems = validate_terminal_reasons(doc)
    assert any("`classes`" in item for item in problems), problems


def _engine_sources(tmp_path, engine_body: str):
    (tmp_path / "src" / "config_layer").mkdir(parents=True)
    (tmp_path / "src" / "runtime").mkdir(parents=True)
    (tmp_path / "src" / "config_layer" / "crt_engine_v2.py").write_text(engine_body, encoding="utf-8")
    (tmp_path / "src" / "runtime" / "backtest_v2.py").write_text("", encoding="utf-8")
    return tmp_path


def test_plain_literal_that_only_starts_a_map_entry_fails(tmp_path):
    # "HTF" is the whole runtime reason, and no entry matches it; that it is the start of
    # the "HTF changed:" prefix entry must not count as coverage.
    root = _engine_sources(tmp_path, "def f(s):\n    s.reset_to_range(s, 'HTF')\n")
    problems = validate_terminal_reasons(load_terminal_reason_map(), root=root)
    assert any("'HTF'" in item for item in problems), problems


def test_plain_literal_longer_than_an_exact_entry_fails(tmp_path):
    root = _engine_sources(tmp_path, "def f(s):\n    s.reset_to_range(s, 'Sweep expired early')\n")
    problems = validate_terminal_reasons(load_terminal_reason_map(), root=root)
    assert any("Sweep expired early" in item for item in problems), problems


def test_fstring_fragment_is_covered_by_a_prefix_entry(tmp_path):
    root = _engine_sources(tmp_path, "def f(s, x):\n    s.reset_to_range(s, f'HTF changed: {x}')\n")
    assert validate_terminal_reasons(load_terminal_reason_map(), root=root) == []


def test_validate_all_is_clean():
    assert validate_all() == []
