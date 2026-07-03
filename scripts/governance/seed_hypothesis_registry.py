"""Seed data/hypothesis_registry.jsonl from the curated research-hypothesis ledger.

Committed truth for the registry (the framework-registry precedent: ``data/`` is gitignored,
so THIS script is the hand-maintained artifact — to add or flip a hypothesis, edit here and
rerun). Deterministic: pinned timestamps + ``HypothesisRegistry.dump`` (sorted, sort_keys) make
reruns byte-identical.

Content is harvested from the falsification programs in ``docs/current-findings.md``
(F-019…F-043): one H-record per pre-registered falsifiable statement, status carrying the
program verdict. ``authority`` is always ``"research"`` (§6.5 — a `validated` hypothesis earns
research standing only; promotion runs exclusively through the M4 QualificationGate →
ConfigValidator → PromotionManager).

Run:  python scripts/governance/seed_hypothesis_registry.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from governance.hypothesis_registry import HypothesisRegistry  # noqa: E402

OUT = _ROOT / "data" / "hypothesis_registry.jsonl"
_TS = "2026-07-03T00:00:00Z"  # pinned for byte-stable reruns


def _rec(
    hid: str, statement: str, *, family: str | None = None, status: str,
    findings: list[str] | None = None, models: list[str] | None = None,
    code_hypotheses: list[str] | None = None, programs: list[str] | None = None,
    evidence: list[dict] | None = None, notes: str = "",
) -> dict:
    return {
        "id": hid, "statement": statement, "family": family, "status": status,
        "authority": "research",
        "findings": findings or [], "models": models or [],
        "code_hypotheses": code_hypotheses or [], "programs": programs or [],
        "evidence": evidence or [],
        "created": _TS, "last_validated": _TS, "notes": notes,
    }


def build_records() -> list[dict]:
    R: list[dict] = []

    R.append(_rec(
        "H-001",
        "CRT structural completion (sweep→displacement→retest) carries a standalone directional "
        "edge on crypto majors under honest exits + cost.",
        family="composite", status="falsified",
        findings=["F-019", "F-021", "F-026"], models=["crt", "engine_runner"],
        code_hypotheses=["spine", "expansion_breakout", "mean_reversion"],
        notes="Program 1/2: 0 PROMOTE at M4; RETEST selection = session filter only; "
              "completed funnel adds no forward asymmetry beyond sweep (underpowered).",
    ))
    R.append(_rec(
        "H-002",
        "Candle-conditional directional pockets (session × vol × momentum, h<=20) exist on "
        "crypto majors.",
        family="conditional", status="falsified",
        findings=["F-020"], models=["crt"],
        notes="Entropy 'significance' saturates at large N; 0 economic pockets.",
    ))
    R.append(_rec(
        "H-003",
        "Exit/SL-TP structure is an expectancy lever (some SL x TP cell clears E>0 with entries "
        "fixed).",
        family="exit", status="falsified",
        findings=["F-025"], models=["rr_model"],
        notes="42-cell grid: every E_oos<0; bottleneck is entry information (reality_gap +4.16R).",
    ))
    R.append(_rec(
        "H-004",
        "Coarser timeframes (H1/H4) rescue the directional edge that is null at M15.",
        family="htf", status="falsified",
        findings=["F-027"], models=["crt"],
        notes="Program 3A: 0 PROMOTE at H1/H4; H4 expansion_breakout only reaches cost-recovery.",
    ))
    R.append(_rec(
        "H-005",
        "A P&F (PNF-v1) double-top/bottom interpreter carries a standalone edge on crypto majors.",
        family="interpreter", status="frozen",
        findings=["F-028"],
        notes="Shadow-measured REJECT, worse than random controls; reopen only via a NEW ontology.",
    ))
    R.append(_rec(
        "H-006",
        "Contemporaneous volatility-regime LEVEL conditioning is economically consumable in the "
        "spot directional architecture.",
        family="regime", status="falsified",
        findings=["F-030"],
        programs=["docs/research-readiness/program-4-nondirectional-preregistration.md"],
        notes="Vol memory real (H_atr 0.885) but 0 exploitable cells; L1 information, not L2 value.",
    ))
    R.append(_rec(
        "H-007",
        "A forward Markov P^H regime-transition forecast adds exploitable information beyond the "
        "current vol level and persistence.",
        family="regime", status="falsified",
        findings=["F-043"],
        programs=["docs/research-readiness/program-4b-transition-preregistration.md"],
        notes="All 10 toy consumer x scope combos REGIME_REDUNDANT (within-tercile-shuffle control).",
    ))
    R.append(_rec(
        "H-008",
        "The MTF compression→expansion TRANSITION channel is directionally consumable "
        "(compression_breakout clears the M4 gate).",
        family="transition", status="falsified",
        findings=["F-040"], code_hypotheses=["compression_breakout"],
        programs=["docs/research/preregistration-program-4bcd.md"],
        notes="Stage-1 informative (p~0.0005, universal, persistent); Stage-2 economic 0 PROMOTE — "
              "binding constraint is the execution model, not predictability.",
    ))
    R.append(_rec(
        "H-009",
        "Cross-sectional dispersion (relative-value, market-neutral) on crypto majors is "
        "monetizable net of costs.",
        family="cross_sectional", status="falsified",
        findings=["F-032"],
        programs=["docs/research-readiness/program-5-cross-sectional-preregistration.md"],
        notes="0 PROMOTE, all 5 interpreters REJECT; lone positive cell is a long-leg/beta artifact.",
    ))
    R.append(_rec(
        "H-010",
        "Carry/basis is an informative SIGNAL for cross-sectional spot dispersion on crypto majors.",
        family="carry", status="falsified",
        findings=["F-033"],
        programs=["docs/research-readiness/program-6-carry-basis-preregistration.md"],
        notes="All 8 interpreters REJECT, below Authority-Level-1; scope = signal-on-dispersion only.",
    ))
    R.append(_rec(
        "H-011",
        "Carry HARVEST (hold perp to earn funding +/- basis convergence) clears costs on crypto "
        "majors.",
        family="carry", status="falsified",
        findings=["F-034"],
        programs=["docs/research-readiness/program-6b-carry-harvest-preregistration.md"],
        notes="Funding income real (+1..+6 bps/rebalance) but < ~24 bps turnover; all twins "
              "DIAGNOSTIC_NEGATIVE. Low-turnover cash-and-carry = separate untested construction.",
    ))
    R.append(_rec(
        "H-012",
        "The crypto entry-information null (F-019…F-028) GENERALIZES to FX majors under the "
        "verbatim M4 gate.",
        family="cross_asset", status="validated",
        findings=["F-035"], models=["crt"],
        notes="0 PROMOTE on 5 FX majors; toys well-powered decisively negative; PF<<1 keeps the "
              "direction null robust to the 12bps cost caveat.",
    ))
    R.append(_rec(
        "H-013",
        "The weekly liquidity-sweep ontology (ICT/CRT Mon+Tue accumulation → Wed-Fri sweep → "
        "reversal) clears the M4 gate on FX majors.",
        family="structural", status="falsified",
        findings=["F-042"], models=["crt"],
        code_hypotheses=["weekly_sweep_reversal"],
        notes="Program 8: 0 PROMOTE across 6 scopes; beats controls but absolute expectancy "
              "negative. Pre-reg: docs/research-readiness/program-8-weekly-crt-sweep-"
              "preregistration.md (untracked at seed time — cited here, not path-checked).",
    ))
    R.append(_rec(
        "H-014",
        "The feature-pipeline center=True swing lookahead and volatility_regime global-rank are "
        "FATAL training contamination that invalidates the model corpus.",
        family="pipeline", status="falsified",
        findings=["F-029"], models=["gaussian", "zone_gate"],
        notes="Byte-identical A/B across crypto majors — the leakage path does not exist for "
              "trade generation; the adversarial verdict was DOC_DRIFT.",
    ))
    R.append(_rec(
        "H-015",
        "ZoneGate feature-space neighborhood quality is a pivotal selection lever in gate-ON "
        "fusion.",
        family="zone", status="falsified",
        findings=["F-036", "F-041"], models=["zone_gate"],
        notes="dG001 == 0 across weight x threshold; zone non-pivotal (redundant/decision-"
              "dominated, not weak). Label quality question stays open under F-041 Phase-5 gate.",
    ))
    R.append(_rec(
        "H-016",
        "An M5-base multi-TF expansion with a non-directional OCO straddle consumer (Program 9: "
        "9a/9b/9c) carries incremental information beyond M15 and clears Gate A+B.",
        family="transition", status="open",
        code_hypotheses=["compression_box_straddle"],
        programs=["docs/research/preregistration-program-9.md"],
        notes="Pre-registered before any run; reopens Program 4 via both legal keys (new M5 "
              "corpus + new non-directional ontology). No findings yet.",
    ))
    return R


def main() -> int:
    n = HypothesisRegistry.dump(OUT, build_records())
    print(f"wrote {n} hypotheses -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
