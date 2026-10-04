"""RC-003 — are the directional-contract-violation bars a distinct object at all?

Frozen pre-registration: ``docs/research/preregistration-rc003-distinct-object.md``
(whole-file sha256 0102f9dc... at freeze; frozen-prefix sha256 731ccbcf... verified at run,
2026-09-04 BEFORE this package existed).

Diagnostic only. PL-0, ``economic_claims_allowed: false``. No ontology, config,
predicate, or F-074 authority at any outcome.
"""

from .driver import (  # noqa: F401
    PREREG_FREEZE_SHA256,
    PREREG_SHA256,
    frozen_prefix_sha256,
    build_populations,
    run_rc003,
)
