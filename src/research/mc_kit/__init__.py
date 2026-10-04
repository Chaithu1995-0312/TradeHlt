"""mc_kit — shared low-level primitives for sealed-contract (MC-*) research drivers.

Research-framework consolidation Phase 3 (2026-09-14). Every trade-contract driver
(`research.mother_range.driver`, `research.sujan_crt.driver`) and prior-contract driver
(`research.evidence.{mother_range_prior,magnitude_prior}`) independently re-implemented CSV
loading, the forward-walk call, exit-kind classification, and per-cell statistics. This package
names the pieces that are PROVABLY identical across drivers — verified by reading every target
file in full, not assumed from name similarity — and leaves everything that differs for a real
reason (candidate detection, `Signal` construction, split scheme, gate/verdict vocabulary) local
to its own driver.

SCOPE HONESTY (read before extending this package): the original design sketch imagined a full
`TradeContractSpec` template so a new contract could be "just a population function + a spec".
Reading every target driver in full showed that does not hold — `_signal` construction differs
per contract (different source dataclass, different zero-risk handling: `mother_range` raises,
`sujan_crt` guards to 1.0), and `verdict`/gate logic differs per contract by DESIGN (different
required checks, different vocabulary — trade contracts emit `DIAGNOSTIC_PASS_NOT_ECONOMIC`,
prior contracts emit `DIAGNOSTIC_PASS`/`DIAGNOSTIC_FAIL`). Forcing those into one template would
either silently drop a real distinction or require a Signal-construction DSL — both are new
behavior-risk for a shrink task that must never change behavior. So this kit stays at the level
that is actually proven safe: bars, the forward-walk step, exit classification, and per-cell
statistics. See `docs/implementation_plan` / the plan file's ROI table for the corrected estimate.

Every function here is pinned by tests/research/test_mc_kit.py against a VERBATIM copy of every
driver body it replaces, run on the same inputs — the same method Phase 1/2 used for exact
duplicates, extended to cover the "same computation, different statement order" cases found here
(e.g. `mother_range_prior._arm_cells` precomputes `ea`/`ed` inline; `magnitude_prior._arm_cells`
precomputes `pos_a`/`pos_d` as locals first — same result, different AST, so equivalence here is
proven by output comparison, not by AST identity).

Authority: research only. Adds no statistics beyond what every replaced copy already computed.
"""
