# Independent Architecture Audit — 2026-06-02

> **Point-in-time audit, not a living doc.** Code-first ground truth (3 Explore agents + direct file
> verification) reconciled with the 56-plan corpus and the dated `assistant_project.md` SESSION LOG.
> Read-only: no code/config was changed. For current truth use `CLAUDE.md` + `docs/architecture/`.

## Central thesis

**There is no evidence that lack of *intelligence* is the binding constraint.** The strongest
evidence points to four others:

1. **Governance integrity** — the running config is ungoverned (bypassed promotion).
2. **Throughput policy** — the limiter is the SESSION filter (config), not detection capability.
3. **Measurement gaps** — *enablement ≠ consumption*: the system builds/measures far more than it consumes.
4. **Unvalidated assumptions** — gate thresholds are hardcoded; the validator is pessimistic/blind.

The highest-ROI move is **promoting the per-coin version that already has measured ROI** (BNBUSDT V3:
+4.91% → **+20.59%**), not building new models.

## Deliverables

| # | File | Phase | Answers |
|---|------|-------|---------|
| 1 | [architectural-evolution-report.md](architectural-evolution-report.md) | A | V1→V2→V3→Current; where intent diverged |
| 2 | [implemented-system-map.md](implemented-system-map.md) | B | Exists / Wired / Active / Tested / Used-in-prod |
| 3 | [profitability-dependency-graph.md](profitability-dependency-graph.md) | C | Revenue / Governance / Research / Dead |
| 4 | [intent-to-code-gap-report.md](intent-to-code-gap-report.md) | D | Planned vs implemented vs used |
| 5 | [governance-audit.md](governance-audit.md) | E-1 | What blocks promotion; evidence vs assumption |
| 6 | [validation-audit.md](validation-audit.md) | E-2 | What blocks production/throughput |
| 7 | [dead-dormant-inventory.md](dead-dormant-inventory.md) | – | Orphaned / dormant / sidecar |
| 8 | [top-10-roi-actions.md](top-10-roi-actions.md) | – | Ranked actions + the ordered five |

## Prior analyses cited (not re-derived)
- `../intelligence-artifact-evidence-map-2026-06-02.md` — Generated/Stored/Consumed/Ignored map
- `../feature-region-oos-persistence-multi-2026-06-02.md` — OOS persistence 4/4 instruments
- `../architectural-evolution-from-plans.md` — 56-plan state board
- `../roi-funnel-diagnosis-bnbusdt-2026-05-30.md` — RETEST→EXECUTION bottleneck
