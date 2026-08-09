"""Live-Gaussian parameterization floor.

Machine-enforces the verified truth that `docs/governance/gaussian_lineage_audit.md` previously
mis-stated: the live Gaussian channel is an UNPARAMETERIZED kernel. Not "trained weights are
unused" (the audit's original `TRAINED_ARTIFACT = INERT` framing) but the stronger fact that **no
learned parameter reaches the scoring path at all**.

Mechanism: `HeuristicGaussianEngine.mu`/`.sigma` fall through to `GaussianRegistry`, whose
`_normalize_registry_entry` (heuristic_gaussian_engine.py:42-53) defaults `mu=0.0, sigma=1.0`.
No entry in `models/gaussian_registry.json` carries either key, so the defaults fire even on a
SUCCESSFUL registry load — making the live score exactly `exp(-x^2/2)`, byte-identical to the
no-registry-at-all path.

These tests are a two-sided guard, not a celebration of the status quo:
  * they fail if someone documents parameterization that isn't there, and
  * they fail LOUDLY the day a `mu`/`sigma` key is added to the registry — which would be a real
    live-behavior change requiring its own governance (§6.5: tunability is not authority).

Related: F-060 (docs/current-findings.md), `docs/governance/gaussian_lineage_audit.md`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "models" / "gaussian_registry.json"

# Instruments with an `__active__` pointer today — these are the cases where the registry
# resolves successfully, so they are the ones that prove "loaded but contributes nothing".
RESOLVING_INSTRUMENTS = ("BNBUSDT", "ETHUSDT")


def _registry_entries() -> dict:
    """Version entries only — skip meta keys (``__active__``, ``_schema_v4_note``, …)."""
    raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return {
        k: v for k, v in raw.items()
        if isinstance(v, dict) and not k.startswith("_")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Artifact-side: the registry carries no learned kernel parameters
# ─────────────────────────────────────────────────────────────────────────────

def test_no_registry_entry_carries_mu_or_sigma():
    """The artifact-level basis for the 'zero learned parameters' claim.

    If this goes red, the live Gaussian kernel just became parameterized by a trained artifact.
    That is a production-behavior change: update the audit + finding before making it green.
    """
    offenders = {
        name: [k for k in ("mu", "sigma") if k in entry]
        for name, entry in _registry_entries().items()
        if "mu" in entry or "sigma" in entry
    }
    assert offenders == {}, (
        f"gaussian_registry.json entries now carry kernel parameters: {offenders}. "
        "The live score is no longer exp(-x^2/2). See docs/governance/gaussian_lineage_audit.md."
    )


def test_registry_has_active_pointers_for_the_resolving_instruments():
    """Guards the premise of the test below: these loads must actually succeed, so that
    mu==0/sigma==1 demonstrates 'loaded and inert' rather than 'never loaded'."""
    active = json.loads(REGISTRY.read_text(encoding="utf-8")).get("__active__", {})
    for inst in RESOLVING_INSTRUMENTS:
        assert inst in active, f"{inst} lost its __active__ pointer; this floor's premise is stale"


# ─────────────────────────────────────────────────────────────────────────────
# Engine-side: a successful registry load still yields the defaults
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("instrument", RESOLVING_INSTRUMENTS)
def test_successful_registry_load_still_yields_default_kernel(instrument):
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine

    eng = HeuristicGaussianEngine({}, instrument=instrument, preload_registry=True)

    assert eng._registry is not None, (
        f"registry failed to load for {instrument} — this test must exercise the LOADED path"
    )
    assert eng.mu == 0.0
    assert eng.sigma == 1.0


def test_live_math_is_unparameterized_gaussian():
    """Pins the live scoring identity: score == exp(-x^2 / 2), x = (ema_diff + tanh(mom)) / 2."""
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    from features.feature_schema import CANONICAL_FEATURES

    feats = {k: 0.0 for k in CANONICAL_FEATURES}
    feats["ema_fast"] = 1.01
    feats["ema_slow"] = 1.00
    feats["momentum_score"] = 0.1

    eng = HeuristicGaussianEngine({}, instrument="BNBUSDT", preload_registry=True)
    result = eng.compute(feats)

    ema_diff = (1.01 - 1.00) / 1.00
    x = (ema_diff + math.tanh(0.1)) / 2.0
    expected = round(math.exp(-(x ** 2) / 2.0), 4)

    assert result["reason"] == "gaussian_computed"
    assert result["score"] == expected
    assert result["meta"]["mu"] == 0.0
    assert result["meta"]["sigma"] == 1.0


def test_kernel_is_symmetric_not_directional():
    """Consequence of mu=0: the score is a 'closeness to flat' measure, so a bullish and an
    equally-sized bearish state score IDENTICALLY — despite the channel entering fusion at
    `weight_gaussian` alongside directional channels. Documented in F-060; measured for
    pivotality by scripts/research/diagnose_gaussian_pivotality.py.
    """
    from engines.heuristic_gaussian_engine import HeuristicGaussianEngine
    from features.feature_schema import CANONICAL_FEATURES

    def _score(ema_fast, momentum):
        feats = {k: 0.0 for k in CANONICAL_FEATURES}
        feats["ema_fast"] = ema_fast
        feats["ema_slow"] = 1.00
        feats["momentum_score"] = momentum
        return HeuristicGaussianEngine(
            {}, instrument="BNBUSDT", preload_registry=True
        ).compute(feats)["score"]

    assert _score(1.02, 0.2) == _score(0.98, -0.2)
