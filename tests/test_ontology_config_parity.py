"""Ontology <-> production-config parity floor (T-4, 2026-07-19).

WHY THIS EXISTS
---------------
The 2026-07-18/19 migration made 36 `feature_pipeline` constants config-driven. That left the
ontology holding DUPLICATE copies of those values in two places:

  * `lookback:` — a numeric mirror of a config period (9 entries), and
  * `formula:`  — prose that historically embedded the literal inline.

Nothing asserted either copy agreed with the config, so a single config edit could silently
falsify multiple ontology entries — the exact documented-vs-actual drift the feature-governance
programme exists to eliminate, re-created inside the WHAT layer itself.

This module is the guard. It does NOT check that the maths is right (parity batteries do that);
it checks that the ontology cannot LIE about where a value comes from or what it currently is.

CONVENTION ENFORCED
-------------------
An entry that declares `config_key` / `config_keys` states "this value is config-driven". Its
`formula:` must then reference the key with a `<feature_pipeline.KEY>` token rather than inline a
literal, e.g.

    formula: "close.ewm(span=<feature_pipeline.ema_fast_span>, adjust=False).mean()  # default 9"

Rule E below makes that structural, so a future entry cannot claim config-driven while hardcoding
the number (which is precisely how six entries had already gone stale before this test existed).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.registry import load_ontology  # noqa: E402

# Sections whose entries may declare config bindings.
_SECTIONS = (
    "primitives",
    "feature_compositions",
    "derived_metrics",
    "rolling_indicators",
    "temporal_context",
)

_CFG_SECTION = "feature_pipeline"
_TOKEN_RE = re.compile(r"<feature_pipeline\.([a-z_0-9]+)>")


@pytest.fixture(scope="module")
def ont() -> dict:
    return load_ontology()


@pytest.fixture(scope="module")
def fp_cfg() -> dict:
    """The live `feature_pipeline` config section (the thing the ontology must agree with)."""
    from config_layer.production_config import get_prod_section

    return get_prod_section(_CFG_SECTION)


def _entries(ont: dict):
    for section in _SECTIONS:
        for name, spec in (ont.get(section) or {}).items():
            yield section, name, spec


def _declared_keys(spec: dict) -> list[str]:
    """Every config key this entry claims to bind to (singular + plural + lookback pointer)."""
    keys: list[str] = []
    if spec.get("config_key"):
        keys.append(str(spec["config_key"]))
    for k in spec.get("config_keys") or []:
        keys.append(str(k))
    if spec.get("lookback_config_key"):
        keys.append(str(spec["lookback_config_key"]))
    return keys


def _strip_prefix(dotted: str) -> str:
    """`feature_pipeline.rsi_period` -> `rsi_period`."""
    return dotted.split(".", 1)[1] if "." in dotted else dotted


# ── A ── every declared binding names a config key that actually exists ───────────────────
def test_declared_config_keys_resolve(ont, fp_cfg):
    missing: list[str] = []
    for section, name, spec in _entries(ont):
        for dotted in _declared_keys(spec):
            if not dotted.startswith(f"{_CFG_SECTION}."):
                missing.append(f"{section}.{name}: {dotted!r} is not a {_CFG_SECTION}.* key")
                continue
            if _strip_prefix(dotted) not in fp_cfg:
                missing.append(f"{section}.{name}: {dotted!r} not present in config")
    assert not missing, "ontology references config keys that do not exist:\n  " + "\n  ".join(missing)


# ── B ── singular config_key + lookback must AGREE with the live config value ─────────────
def test_lookback_matches_singular_config_key(ont, fp_cfg):
    drift: list[str] = []
    for _section, name, spec in _entries(ont):
        lb = spec.get("lookback")
        ck = spec.get("config_key")
        if lb is None or not ck or spec.get("config_keys"):
            continue  # plural handled by rule C
        live = fp_cfg.get(_strip_prefix(str(ck)))
        if live != lb:
            drift.append(f"{name}: lookback={lb!r} but {ck}={live!r}")
    assert not drift, (
        "ontology `lookback` disagrees with the live config value it mirrors "
        "(update the lookback, or the config, so they agree):\n  " + "\n  ".join(drift)
    )


# ── C ── plural config_keys + lookback MUST disambiguate, and then agree ──────────────────
def test_plural_config_keys_declare_and_match_lookback(ont, fp_cfg):
    problems: list[str] = []
    for _section, name, spec in _entries(ont):
        lb = spec.get("lookback")
        if lb is None or not spec.get("config_keys"):
            continue
        pointer = spec.get("lookback_config_key")
        if not pointer:
            problems.append(
                f"{name}: has lookback={lb!r} and plural config_keys but no `lookback_config_key` "
                "— cannot tell which key the lookback mirrors"
            )
            continue
        if pointer not in [str(k) for k in spec["config_keys"]]:
            problems.append(f"{name}: lookback_config_key {pointer!r} is not among its config_keys")
            continue
        live = fp_cfg.get(_strip_prefix(pointer))
        if live != lb:
            problems.append(f"{name}: lookback={lb!r} but {pointer}={live!r}")
    assert not problems, "plural-config_keys lookback problems:\n  " + "\n  ".join(problems)


# ── D ── every <feature_pipeline.X> token in any formula resolves ─────────────────────────
def test_formula_tokens_resolve(ont, fp_cfg):
    unresolved: list[str] = []
    for _section, name, spec in _entries(ont):
        for field in ("formula", "note"):
            text = str(spec.get(field, ""))
            for key in _TOKEN_RE.findall(text):
                if key not in fp_cfg:
                    unresolved.append(f"{name}.{field}: <{_CFG_SECTION}.{key}> not in config")
    assert not unresolved, (
        "formula/note references a config key that does not exist "
        "(a renamed key orphaned it):\n  " + "\n  ".join(unresolved)
    )


# ── E ── THE REGRESSION GUARD: claiming config-driven obliges you to say where ────────────
def test_config_bound_entries_use_tokens_in_formula(ont):
    """An entry declaring config_key(s) must reference at least one token in its formula.

    Without this, an entry can declare `config_key: feature_pipeline.rsi_period` while its formula
    still hardcodes `SMA(14)` — true today, a lie the moment the config changes. Six entries had
    drifted this way before this rule existed (atr, rsi_14, ema_fast, ema_slow, macd_line,
    macd_signal), all fixed in the same commit that introduced this test.
    """
    offenders: list[str] = []
    for _section, name, spec in _entries(ont):
        if not (spec.get("config_key") or spec.get("config_keys")):
            continue
        formula = str(spec.get("formula", ""))
        if not _TOKEN_RE.search(formula):
            offenders.append(
                f"{name}: declares config binding but formula inlines the literal "
                f"(use <{_CFG_SECTION}.KEY>): {formula[:80]!r}"
            )
    assert not offenders, (
        "entries claim config-driven values but their formula hardcodes them:\n  "
        + "\n  ".join(offenders)
    )


# ── F ── a note may not NEGATE a binding the entry declares ───────────────────────────────
# The exact class that let FM-052 drift: the entry declared
#   config_keys: [feature_pipeline.session_asia_end_hour, ...]
# while its note said "Hour cutoffs remain hardcoded ... so no config_key." Rule D only checks
# that tokens RESOLVE and Rule E only inspects the FORMULA, so a self-contradicting NOTE slipped
# through both. This makes the contradiction structural.
_NO_CONFIG_KEY_RE = re.compile(r"no\s+config[_ ]key", re.IGNORECASE)


def test_note_does_not_deny_a_declared_config_binding(ont):
    """If an entry declares config_key(s), its note must not claim there is 'no config_key'."""
    offenders: list[str] = []
    for _section, name, spec in _entries(ont):
        if not (spec.get("config_key") or spec.get("config_keys")):
            continue
        note = str(spec.get("note", ""))
        if _NO_CONFIG_KEY_RE.search(note):
            offenders.append(
                f"{name}: declares a config binding but its note says 'no config_key' "
                f"— a self-contradicting documented-vs-actual claim (§6.2)"
            )
    assert not offenders, (
        "ontology note contradicts the entry's own declared config binding:\n  "
        + "\n  ".join(offenders)
    )


# ── sanity: the fixture set is non-trivial, so a silent no-op cannot pass ─────────────────
def test_guard_covers_a_meaningful_population(ont):
    """A test that asserts over an empty set is not enforcement."""
    bound = [n for _s, n, spec in _entries(ont) if spec.get("config_key") or spec.get("config_keys")]
    with_lookback = [
        n for _s, n, spec in _entries(ont)
        if spec.get("lookback") is not None and (spec.get("config_key") or spec.get("config_keys"))
    ]
    assert len(bound) >= 12, f"expected >=12 config-bound entries, found {len(bound)}: {bound}"
    assert len(with_lookback) >= 8, (
        f"expected >=8 entries with both lookback and a config binding, found {len(with_lookback)}"
    )
