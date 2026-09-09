"""
CRT state-registry invariants — guards active_models.yaml against crt_engine_v2 code.

The original drift (`states: 10` in the registry vs 9 in code) was a YAML↔code
*synchronization* failure, not an algorithm bug. This test pins both directions so
that adding/removing a CRTState without updating the registry (or vice-versa) fails
CI. It also encodes historical drift points as institutional memory.

conftest.py puts `src/` on sys.path, so the engine imports without a `src.` prefix.
The YAML must be opened as UTF-8 (it contains box-drawing / math glyphs).

SEMANTICS CHANGED 2026-08-31 (CH-crt-state-generation-v1) -- READ BEFORE TRUSTING THIS FILE.
`CRTState` / `VALID_TRANSITIONS` are now GENERATED from this same active_models.yaml by
scripts/maintenance/gen_crt_state_identity.py. So assertions 1 and 2 below no longer compare
two INDEPENDENTLY-maintained records; both sides derive from one file. They are now a
FRESHNESS check (is the committed generated artifact current with the YAML?) rather than a
drift detector. That is a real reduction in what this file proves, recorded rather than glossed.

Independence now lives elsewhere, deliberately:
  * tests/test_crt_state_generated_parity.py pins the generated output against values
    transcribed by hand from the PRE-generation state_identity.py.
  * tests/test_crt_states_yaml_transition_parity.py (SK-0) and
    tests/test_crt_states_yaml_state_names.py compare against
    configs/formulas/market_crt_states.yaml -- a DIFFERENT file, not the generation source,
    so those remain fully non-vacuous cross-file guards.
Assertions 3 and 4 (historical-drift memory, RESOLUTION lifecycle) are unaffected: they encode
facts, not cross-record agreement.
"""
from pathlib import Path

import yaml

from config_layer.state_identity import CRTState, VALID_TRANSITIONS

_ROOT = Path(__file__).resolve().parents[1]


def _crt_runtime() -> dict:
    with open(_ROOT / "active_models.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["crt"]["runtime"]


def test_crt_state_invariants():
    crt = _crt_runtime()
    code_states = {s.name for s in CRTState}
    code_trans = {s.name: {t.name for t in ts} for s, ts in VALID_TRANSITIONS.items()}

    # 1. YAML internal consistency — count + set
    assert crt["states"] == len(crt["state_list"]) == len(crt["valid_transitions"])
    assert set(crt["state_list"]) == set(crt["valid_transitions"].keys())

    # 2. YAML <-> code — the real drift guard: state names + per-state transition targets
    assert set(crt["state_list"]) == code_states
    assert {k: set(v) for k, v in crt["valid_transitions"].items()} == code_trans

    # 3. Historical-regression memory — past drift points
    assert "CANCELLED" not in crt["state_list"]        # never existed
    assert "RESOLVED" not in crt["state_list"]         # the state is RESOLUTION
    assert {"RESOLUTION", "EXPIRED"} <= set(crt["state_list"])

    # 4. Lifecycle semantics — RESOLUTION is a cycle-reset to RANGE, NOT a dead-end
    assert code_trans["RESOLUTION"] == {"RANGE"}
