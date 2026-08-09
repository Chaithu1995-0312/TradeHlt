"""Interpreter Contract Layer (Level 4) — behavior-agnostic event/feature producers.

An Interpreter OBSERVES a window and emits events + confidence/strength; it does NOT
emit trades. To be MEASURED it is bridged to the frozen research `Hypothesis` via
`adapter.InterpreterHypothesis`, then flows through the existing `forward_walk` +
`QualificationGate` (the reused oracle) — there is deliberately NO InterpreterOracle.

Public surface:
- `contract` — `Interpreter` Protocol, `BaseInterpreter`, `InterpreterReading`,
  `InterpreterEvent`, `EventKind`, `SCHEMA_VERSION`.
- `adapter` — `InterpreterHypothesis` (identity-blind bridge to research).
- `reference` — `ConstantDirectionInterpreter`, `NullInterpreter` (contract proof only).
"""
