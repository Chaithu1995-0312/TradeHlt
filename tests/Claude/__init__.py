"""Independent semantic-auditor suite (Claude, families J-M).

Sibling of tests/Grok (families A-I), same house style and same nodeid-grain
intent workbook. This package opens the four contracts the Grok suite left
without a family, named in
docs/implementation_plan/topic-ladder-and-grok-test-intent-excel.md
(Open Question 3 + the ladder's L3 / L6 "no Grok family" rows):

  J  directional displacement            F-074, ladder layer 3
  K  SMC primitives are features         F-076, ladder layer 6
  L  schema / model-artifact staleness   F-076, ladder layers 1 and 7
  M  reachability is not certification   F-073 / F-075, layers 4, 8, 9

These tests encode *meaning* contracts (journeys, provenance, units,
name collisions, fail-open vs fail-closed policy). They deliberately do not
retread the domain floors — tests/test_directional_displacement.py pins
displacement SHAPES, tests/test_smc_primitives.py pins DETECTORS. Production
code is not modified by this package, and nothing here grants authority
(no ACTIVE_VERSION change, no G001, no CRT CLOSED stamp, no gate flip).
"""
