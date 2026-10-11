# Consumer-branch status: before vs after

Baseline: results/consumer_graph (commit c3318fefac). After: results/consumer_graph_after/consumer_registry.json.

Counts before {'verified': 5, 'mismatched': 6, 'broken': 4, 'unverified': 10}; after {'verified': 7, 'mismatched': 7, 'broken': 4, 'unverified': 9}.

| ID | Tree | Before | After | Change |
|---|---|---|---|---|
| A1 | A | verified | verified | identity/evidence updated, status unchanged |
| A2 | A | verified | verified | unchanged |
| A3 | A | verified | verified | identity/evidence updated, status unchanged |
| A4 | A | unverified | unverified | identity/evidence updated, status unchanged |
| A5 | A | verified | verified | unchanged |
| B1 | B | mismatched | mismatched | identity/evidence updated, status unchanged |
| B2 | B | broken | broken | unchanged |
| B3 | B | broken | broken | unchanged |
| B4 | B | broken | broken | unchanged |
| B5 | B | unverified | unverified | unchanged |
| B6 | B | broken | broken | unchanged |
| B8 | B | unverified | unverified | unchanged |
| B7 | B | unverified | unverified | unchanged |
| C1 | C | unverified | unverified | unchanged |
| C2 | C | mismatched | mismatched | unchanged |
| C3 | C | mismatched | mismatched | identity/evidence updated, status unchanged |
| C3b | C | unverified | mismatched | STATUS CHANGED |
| C4 | C | mismatched | mismatched | identity/evidence updated, status unchanged |
| C5 | C | verified | verified | unchanged |
| D1 | D | mismatched | mismatched | identity/evidence updated, status unchanged |
| D2 | D | mismatched | mismatched | unchanged |
| D3 | D | unverified | unverified | unchanged |
| D4 | D | unverified | unverified | unchanged |
| D5 | D | unverified | unverified | unchanged |
| D6 | D | unverified | unverified | unchanged |
| S1 | S | - | verified | new branch |
| S2 | S | - | verified | new branch |

## Changed or new branches

### C3b (STATUS CHANGED: unverified -> mismatched)
- **Producer:** ARTIFACTS:gaussian_xau_m15_causal_n9_20261011
- **Transformation:** 35 ordered features; experimental 9-trade fit
- **Consumer:** src/training/trainer.py::load_gaussian_model
- **Dependency path:** [('ARTIFACTS:gaussian_xau_m15_causal_n9_20261011 -> src/training/trainer.py', True)]
- **Contract identity:** 35 ordered features, schema checksum ok, own feature_definition_hash (pre-contract scheme) but NO feature_contract_hash
- **Test/execution evidence:** default loader: rejected:ContractMismatchError; allow_legacy: loads:legacy_unverified
- **Required tests:** ['eligibility rule for experimental artifacts']

### S1 (new branch: - -> verified)
- **Producer:** src/features/feature_contract.py (contract_hash, verify_bundle_contract)
- **Transformation:** save stamps feature_contract_hash only when the artifact uses the canonical feature list; load rejects missing/wrong hash and wrong dimensions
- **Consumer:** src/training/trainer.py::load_gaussian_model / save_gaussian_model
- **Dependency path:** [('src/training/trainer.py -> src/features/feature_contract.py', True)]
- **Contract identity:** feature_contract_hash 8cf0dfe71ea4... (formal: ['body_size', 'wick_size', 'body_ratio'])
- **Test/execution evidence:** executed: good artifact load verified; repository artifacts: [('260405T155721.json', 'rejected:ValueError'), ('260405T155823.json', 'rejected:ValueError'), ('260405T175730.json', 'rejected:ValueError')]...; tests/test_model_contract_gate.py (10 tests)
- **Required tests:** ['tests/test_model_contract_gate.py', 'tests/test_gaussian_active_artifact.py']
- **Does not imply:** C4, B1, D2, D3: no consumer of the loader or of the contract is verified by this branch

### S2 (new branch: - -> verified)
- **Producer:** src/features/feature_contract.py
- **Transformation:** registry stores the artifact's contract hash; promotion requires entry and artifact hash == current, not bypassed by force
- **Consumer:** src/core/model_registry.py::GaussianModelRegistry.register_gaussian/promote_gaussian
- **Dependency path:** [('src/core/model_registry.py -> src/features/feature_contract.py', True)]
- **Contract identity:** feature_contract_hash 8cf0dfe71ea4... (formal: ['body_size', 'wick_size', 'body_ratio'])
- **Test/execution evidence:** executed in a temp dir: legacy promote(force=True) -> [False, 'Gaussian promotion BLOCKED (feature contract): legacy entry=None artifact=None current=8cf0dfe71ea4. Legacy or incompatible artifacts are ineligible; retrain against the current feature contract.']; contract artifact promote -> [True, 'First Gaussian deployment: good (corr=+0.0000)']; tests/test_model_contract_gate.py
- **Required tests:** ['tests/test_model_contract_gate.py', 'tests/test_model_registry.py']
- **Does not imply:** C5 (heuristic reader) and C4 are unchanged; existing entries in models/gaussian_registry.json were not modified
