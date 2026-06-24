# Domain Contract: Governance

## Purpose
Ensure that no config change reaches production without validation, hashing, audit, and rollback capability. The config is the single source of truth for every tunable parameter — the governance path is the only way to change it.

## Why does this exist?
The user thought: *"Don't repeat mistakes."* A bad config reaching production is a process failure, not a code failure. Governance infrastructure exists to make the right thing the easy thing and the wrong thing impossible.

**Evidence:** intelligence-compounding.md:127; goal.md:19-20; governance.md:1-5 — Confidence: Certain

## Authority
- **Owns:** The promotion path (tuner → ConfigValidator → PromotionManager → registry + promotion_log).
- **Decides:** Which config versions are active (ACTIVE_VERSION pointer).
- **Must NOT:** Allow any code path outside PromotionManager to write to configs/production/.
- **Must NOT:** Allow a config to be promoted without an APPROVED ValidationReport.

**Evidence:** governance.md:390 (write-authority matrix) — Confidence: Certain

## Must (Required Behaviors)
1. Every promotion must produce a ValidationReport with decision == "APPROVE" before entering PromotionManager.
2. Every promotion must SHA-256 hash the params and record the hash in promotion_log.jsonl.
3. Every promotion must archive the existing active config before writing the new one.
4. Every promotion must append to promotion_log.jsonl (PROMOTED or PROMOTION_FAILED).
5. ACTIVE_VERSION must point to a version that exists in promotion_log.jsonl with a PROMOTED event.
6. ConfigValidator must enforce hard gates (min_trades, max_drawdown, min_fitness) and soft gates (win_rate, expectancy, cross-instrument consistency).

## Must Never (Forbidden Behaviors)
1. Must NEVER skip ConfigValidator for normal promotions (promote_direct is marked and reserved for hotfixes).
2. Must NEVER allow a config version with unrecognized top-level keys to load (ConfigBuilder._validate_override_keys).
3. Must NEVER silently resolve a version conflict between ACTIVE_VERSION and promotion_log — surface it.
4. Must NEVER edit or truncate promotion_log.jsonl.
5. Must NEVER hot-swap a config — consumers load at import time; restart required.

## Examples
- **Correct:** tuner produces checkpoint → ConfigValidator.validate() returns APPROVE → PromotionManager promotes → promotion_log has PROMOTED entry → ACTIVE_VERSION points to it.
- **Correct:** ConfigValidator returns REJECT (hard_failures=['min_trades']) → promotion_log has PROMOTION_FAILED → system continues with existing config.
- **Anti-example:** A direct edit to configs/production/v2_multi_2026_04.json bypassing PromotionManager.
- **Anti-example:** ACTIVE_VERSION = "v2_multi_2026_04 - deepdeektry" (suffix differs from promotion_log "v2_multi_2026_04") — this is what happened (F-016).

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| ACTIVE_VERSION not in promotion_log | config_integrity.active_version_is_governed (but it's ORPHANED) | HIGH |
| Config section expected by code absent from active config | RuntimeError at get_prod_section() | HIGH (was happening pre-R1 fix) |
| Hash mismatch after edit | ConfigBuilder._validate_override_keys | HIGH |
| Direct promotion not marked | Manual audit of promotion_log | MEDIUM |
| Rollback without ROLLBACK log entry | No automated detection | MEDIUM |

## Economic Meaning
Governance is the #1 binding constraint (F-001). A single ungoverned config change that destroys value costs more than the entire governance infrastructure. The cost of a false promotion (bad config reaches live) exceeds the cost of a false rejection (good config delayed).

**Evidence:** F-001 — Confidence: Certain

## Unknowns
- Whether the deepdeektry suffix was a deliberate experiment or an accidental divergence.
- Whether the config_integrity orphan represents an abandoned feature or a future intention.

## Evidence
- governance.md:1-5 (promotion flow) — Confidence: Certain  
- F-006 (config_integrity orphaned) — Confidence: Certain  
- F-016 (branch-scoped v4/v2 split-brain) — Confidence: Certain  
- F-018 (config → code split-brain) — Confidence: Certain  
- CLAUDE.md §4.0 (Active Version Resolution) — Confidence: Certain