"""Config semantic-invariant floor: units, cross-section ordering, scale.

Parses docs/governance/config_unit_registry.json and checks the ACTIVE production config
(configs/production/ACTIVE_VERSION) against it:

  1. Completeness   every scalar whose key matches the registry's completeness_pattern
                    (`_pct` / `percent` / `_inr` / `capital` / `balance`) is registered,
                    and every registered path exists in the config.
  2. Unit range     percent in [0, 100], fraction in [0, 1], money >= 0, rate > 0.
  3. Ordering       declared cross-section orders (per-trade risk <= Ultron cap, gate >= goal, ...).
  4. Scale          INR loss/drawdown limits <= the declared capital reference.
  5. Agreement      LIVE keys of one concept agree after unit normalisation.

Known divergences are pinned in the registry's `known_divergences` by exact violation
fingerprint (values included, so drift INSIDE a known divergence is also caught). The
ratchet is two-sided: a new violation fails, and a pinned divergence that no longer
reproduces fails until its entry is removed. Both ratchet counts may only shrink.

Why: `_pct` meant percent in UltronRiskGate / ExecutionPlanner and a fraction in
backtest_v2 / portfolio_validation, with nothing recording which — an external review
(2026-10-01) surfaced it; this floor makes the unit a declared, checked fact.

Read-only. Does not mutate any config, model, or runtime behaviour.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config_layer.production_config import get_active_version  # noqa: E402

REGISTRY_PATH = ROOT / "docs" / "governance" / "config_unit_registry.json"
PROD_DIR = ROOT / "configs" / "production"

VALID_UNITS = {"percent", "fraction", "inr", "money_unspecified", "rate", "UNVERIFIED"}
VALID_STATUSES = {"LIVE", "SHADOW", "TOOLING", "DEAD"}
# §6.8 closing verdicts (CLAUDE.md) — a pinned divergence must carry exactly one.
VALID_VERDICTS = {
    "CONFIRMED DEFECT", "INTENTIONAL SEMANTIC SEPARATION", "STALE / LEGACY ARTIFACT",
    "COMPATIBILITY ARTIFACT", "DEFENSE-IN-DEPTH OPPORTUNITY", "TEST / CONTRACT GAP",
    "DOCUMENTATION GAP", "DORMANT BUT VALID", "INSUFFICIENT EVIDENCE",
    "USER AUTHORIZATION REQUIRED",
}

# Shrink-only ratchets (lower these when an entry is resolved; never raise).
MAX_KNOWN_DIVERGENCES = 2   # 4 -> 2 on 2026-10-01: RISK-01 + DD-01 resolved (F-111)
MAX_UNVERIFIED_UNITS = 9

_RATIO_UNITS = {"percent", "fraction"}
_MONEY_UNITS = {"inr", "money_unspecified"}
# INR limits that must not exceed the capital reference.
_SCALE_CONCEPTS = {"drawdown_limit", "daily_loss_limit", "weekly_loss_limit",
                   "risk_per_trade_cap_money"}
_FX_DEFAULT_PIP = 0.0001
_PIP_CONSUMERS = ("spread_pips", "slippage_pips", "min_sl_pips")


# ── pure helpers ──────────────────────────────────────────────────────────────


def _fmt(v: float) -> str:
    v = float(v)
    return str(int(v)) if v.is_integer() else f"{v:.10g}"


def _get(cfg: dict, path: str):
    node = cfg
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(path)
        node = node[part]
    return node


def _as_fraction(value: float, unit: str) -> float:
    return float(value) / 100.0 if unit == "percent" else float(value)


def _scalar_leaves(node, prefix: str = ""):
    if isinstance(node, dict):
        for k, v in node.items():
            if k.startswith("_"):
                continue
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                yield from _scalar_leaves(v, path)
            elif not isinstance(v, list):
                yield path, k, v


def evaluate(cfg: dict, reg: dict) -> tuple[set[str], list[str]]:
    """Return (violations, hard_errors).

    violations   — ratchetable fingerprints; must equal the pinned set exactly.
    hard_errors  — never ratchetable (registry rot, bad unit/range, armed landmine).
    """
    violations: set[str] = set()
    hard: list[str] = []
    rows = {r["path"]: r for r in reg["keys"]}

    # 1. completeness — both directions
    pat = re.compile(reg["completeness_pattern"])
    for path, leaf, _ in _scalar_leaves(cfg):
        if pat.search(leaf) and path not in rows:
            hard.append(f"UNREGISTERED:{path} (declare its unit in {REGISTRY_PATH.name})")
    values: dict[str, float] = {}
    for path, r in rows.items():
        try:
            v = _get(cfg, path)
        except KeyError:
            hard.append(f"REGISTRY_ROT:{path} not present in the active config")
            continue
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            hard.append(f"NON_NUMERIC:{path}={v!r}")
            continue
        values[path] = float(v)

    # 2. unit range
    for path, v in values.items():
        unit = rows[path]["unit"]
        ok = {
            "percent": 0.0 <= v <= 100.0,
            "fraction": 0.0 <= v <= 1.0,
            "inr": v >= 0.0,
            "money_unspecified": v >= 0.0,
            "rate": v > 0.0,
            "UNVERIFIED": True,
        }[unit]
        if not ok:
            hard.append(f"RANGE:{path}={_fmt(v)} outside declared unit '{unit}'")

    def frac(path: str) -> float | None:
        if path not in values or rows[path]["unit"] not in _RATIO_UNITS:
            return None
        return _as_fraction(values[path], rows[path]["unit"])

    # 3. ordering — (name, lhs, rhs) meaning lhs <= rhs, both as fractions
    cap = reg["capital_reference"]
    capital = values.get(cap)
    if capital is None or capital <= 0:
        hard.append(f"CAPITAL_REFERENCE:{cap} missing or non-positive")
        capital = None
    ultron_cap = frac("ultron_risk_gate.max_risk_per_trade_pct")
    orders: list[tuple[str, float | None, float | None]] = []
    for path, r in rows.items():
        if r["concept"] == "risk_per_trade" and r["status"] == "LIVE":
            orders.append((f"{path}<=ultron_risk_gate.max_risk_per_trade_pct",
                           frac(path), ultron_cap))
    orders += [
        ("ultron.max_risk_per_trade<=ultron.max_portfolio_risk",
         ultron_cap, frac("ultron_risk_gate.max_portfolio_risk_pct")),
        ("goal.max_drawdown<=config_validator.max_drawdown_gate",
         frac("goal.max_drawdown_pct.max"), frac("config_validator.max_drawdown_pct")),
    ]
    uat_daily = values.get("uat.kill_switch.daily_loss_limit_inr")
    if capital and uat_daily is not None:
        orders.append(("ultron.max_daily_loss<=uat.kill_switch.daily_loss/capital",
                       frac("ultron_risk_gate.max_daily_loss_pct"), uat_daily / capital))
    if uat_daily is not None and "uat.kill_switch.weekly_loss_limit_inr" in values:
        orders.append(("uat.daily_loss<=uat.weekly_loss",
                       uat_daily, values["uat.kill_switch.weekly_loss_limit_inr"]))
    for name, lhs, rhs in orders:
        if lhs is None or rhs is None:
            hard.append(f"ORDER_UNEVALUABLE:{name}")
        elif lhs > rhs + 1e-12:
            violations.add(f"ORDER:{name}:{_fmt(lhs)}>{_fmt(rhs)}")

    # 4. scale — INR limits within capital
    if capital:
        for path, r in rows.items():
            if (r["concept"] in _SCALE_CONCEPTS and r["unit"] == "inr"
                    and path in values and values[path] > capital):
                violations.add(f"SCALE:{path}:{_fmt(values[path])}>{_fmt(capital)}")

    # 5. agreement — LIVE keys per concept, after normalisation
    by_concept: dict[str, list[str]] = {}
    for path, r in rows.items():
        if r["status"] == "LIVE" and r["unit"] != "UNVERIFIED" and path in values:
            by_concept.setdefault(r["concept"], []).append(path)
    for concept, paths in sorted(by_concept.items()):
        if len(paths) < 2:
            continue
        units = {rows[p]["unit"] for p in paths}
        if units <= _RATIO_UNITS:
            norm = {round(frac(p), 12) for p in paths}
        elif units <= _MONEY_UNITS:
            norm = {round(values[p], 6) for p in paths}
        else:
            hard.append(f"MIXED_UNIT_CONCEPT:{concept} {sorted(units)}")
            continue
        if len(norm) > 1:
            violations.add(f"AGREE:{concept}:" + "|".join(_fmt(v) for v in sorted(norm)))

    # PIP — FX pip size on a non-FX instrument universe (ratchetable while dormant)
    urg = cfg.get("ultron_risk_gate", {})
    specs = [k for k in cfg.get("instrument_specs", {}) if not k.startswith("_")]
    if urg.get("pip_size") == _FX_DEFAULT_PIP and "XAUUSD" in specs:
        violations.add("PIP:fx_pip_size_on_non_fx_instruments")
        armed = [k for k in _PIP_CONSUMERS if float(urg.get(k, 0.0)) > 0.0]
        if armed:
            hard.append(f"PIP_ARMED: {armed} > 0 while pip_size={_FX_DEFAULT_PIP} on XAUUSD "
                        "(would price costs/min-SL 100x off)")

    return violations, hard


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def active_config() -> dict:
    version = get_active_version()
    return json.loads((PROD_DIR / f"{version}.json").read_text(encoding="utf-8"))


# ── registry shape ────────────────────────────────────────────────────────────


def test_registry_rows_are_well_formed(registry):
    paths = [r["path"] for r in registry["keys"]]
    assert len(paths) == len(set(paths)), "duplicate registry paths"
    for r in registry["keys"]:
        assert r["unit"] in VALID_UNITS, r
        assert r["status"] in VALID_STATUSES, r
        assert r.get("concept"), r
        assert r.get("consumer"), r
    assert registry["capital_reference"] in paths


def test_known_divergences_are_well_formed(registry):
    divs = registry["known_divergences"]
    ids = [d["id"] for d in divs]
    assert len(ids) == len(set(ids)), "duplicate divergence ids"
    for d in divs:
        assert d.get("violation") and d.get("reason"), d
        assert d.get("verdict") in VALID_VERDICTS, d


def test_ratchets_only_shrink(registry):
    n_div = len(registry["known_divergences"])
    n_unv = sum(1 for r in registry["keys"] if r["unit"] == "UNVERIFIED")
    assert n_div <= MAX_KNOWN_DIVERGENCES, (
        f"{n_div} known divergences > ratchet {MAX_KNOWN_DIVERGENCES}: fix the config "
        "instead of pinning a new divergence")
    assert n_unv <= MAX_UNVERIFIED_UNITS, (
        f"{n_unv} UNVERIFIED units > ratchet {MAX_UNVERIFIED_UNITS}: verify the new key's "
        "unit from its consumer")


# ── the floor ─────────────────────────────────────────────────────────────────


def test_active_config_has_no_hard_errors(active_config, registry):
    _, hard = evaluate(active_config, registry)
    assert not hard, "\n".join(hard)


def test_no_new_semantic_violations(active_config, registry):
    violations, _ = evaluate(active_config, registry)
    pinned = {d["violation"] for d in registry["known_divergences"]}
    new = violations - pinned
    assert not new, ("new config semantic violation(s) — fix the config, or (with user "
                     "approval) pin in config_unit_registry.json known_divergences:\n"
                     + "\n".join(sorted(new)))


def test_pinned_divergences_still_reproduce(active_config, registry):
    violations, _ = evaluate(active_config, registry)
    stale = [d["id"] for d in registry["known_divergences"]
             if d["violation"] not in violations]
    assert not stale, (f"divergence(s) {stale} no longer reproduce — remove them from "
                       "known_divergences and lower MAX_KNOWN_DIVERGENCES")


# ── self-tests: the floor can fail (E-001: a test that cannot fail is not enforcement) ──


def _mutate(cfg: dict, path: str, value) -> dict:
    out = copy.deepcopy(cfg)
    node = out
    *parents, leaf = path.split(".")
    for p in parents:
        node = node.setdefault(p, {})
    node[leaf] = value
    return out


def _new_violations(cfg, reg) -> set[str]:
    v, _ = evaluate(cfg, reg)
    return v - {d["violation"] for d in reg["known_divergences"]}


def test_selftest_planner_percent_written_as_fraction_is_caught(active_config, registry):
    # 0.5% mistakenly entered as 0.005 in a percent-unit key changes the AGREE fingerprint.
    mutated = _mutate(active_config, "execution_planner.risk_percent", 0.005)
    assert any(v.startswith("AGREE:risk_per_trade") for v in _new_violations(mutated, registry))


def test_selftest_fraction_key_written_as_percent_is_caught(active_config, registry):
    mutated = _mutate(active_config, "backtest.risk_pct_per_trade", 1.0 * 100)
    _, hard = evaluate(mutated, registry)
    assert any(h.startswith("RANGE:backtest.risk_pct_per_trade") for h in hard)


def test_selftest_unregistered_pct_key_is_caught(active_config, registry):
    mutated = _mutate(active_config, "backtest.foo_pct", 0.5)
    _, hard = evaluate(mutated, registry)
    assert "UNREGISTERED:backtest.foo_pct" in " ".join(hard)


def test_selftest_scale_regression_is_caught(active_config, registry):
    # Re-introduce the pre-F-111 75 M scale mistake: must fail as a NEW violation.
    mutated = _mutate(active_config, "multi_strategy_validator.max_portfolio_drawdown", 75_000_000.0)
    assert any(v.startswith("SCALE:multi_strategy_validator") for v in _new_violations(mutated, registry))


def test_selftest_fixed_divergence_becomes_stale(active_config, registry):
    mutated = _mutate(active_config, "execution_planner.default_account_balance", 100000.0)
    violations, _ = evaluate(mutated, registry)
    cap01 = next(d for d in registry["known_divergences"] if d["id"] == "CAP-01")
    assert cap01["violation"] not in violations


def test_resolved_divergences_do_not_recur(active_config, registry):
    violations, _ = evaluate(active_config, registry)
    recurred = [d["id"] for d in registry.get("resolved_divergences", []) if d["was"] in violations]
    assert not recurred, f"resolved divergence(s) {recurred} are back — see their finding"


def test_selftest_armed_pip_landmine_is_hard(active_config, registry):
    mutated = _mutate(active_config, "ultron_risk_gate.spread_pips", 2.0)
    _, hard = evaluate(mutated, registry)
    assert any(h.startswith("PIP_ARMED") for h in hard)


def test_selftest_ordering_breach_is_caught(active_config, registry):
    mutated = _mutate(active_config, "ultron_risk_gate.max_risk_per_trade_pct", 0.25)
    assert any(v.startswith("ORDER:") for v in _new_violations(mutated, registry))
