"""run_close_out.py — the shared close-out every sealed-contract experiment runs.

Named `run_close_out`, NOT `provenance`: `research/provenance.py` already exists and stamps a
different thing (truth-standard / cost-model / production-config versions onto an edge_report).
Two `provenance` modules one package apart is the name-collision class this repo has been bitten
by before (F-063), so the ambiguity is avoided rather than documented.


Replaces the identical placeholder tail that all four `research/evidence/*` modules carried:

    (out_dir / "mt00.json").write_text(json.dumps({"status": "UNRUN", ...}))

That wrote the file the contract declares as `mt00_report_path` and put `UNRUN` inside it. The
artifact existed, was git-tracked, and proved nothing — a declared measurement was
indistinguishable from an executed one (F-056 / F-079 / F-083 / F-085 silent-gap class, found
2026-08-26 by the research-provenance audit).

`finalize_run` does three things instead:

1. **Executes E-MT-00** against the sealed instance and writes the REAL verdict, so `mt00.json`
   records a measurement rather than a literal.
2. **Writes `mt01.json` as an honest UNRUN** — E-MT-01 matrix coverage is a separate programme at
   0/27 repo-wide. This one IS genuinely unrun, and says so with its reason rather than by default.
3. **Writes a `run_manifest.json`** via `utils.run_manifest`, the same provenance record seven
   `scripts/research/*` producers already emit. These four modules wrote none, so the newest
   economic-claim producers in the repo were also the least traceable.

Authority: research only. Nothing here can make a claim admissible — `seal_verdict` needs mt01
COMPLETE, which no contract has.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from research.measurement.mt00 import run_mt00, seal_verdict, write_report
from research.provenance import production_config_block
from utils.run_manifest import build_manifest, write_run
from utils.validation_contract import require_manifest

_ROOT = Path(__file__).resolve().parents[3]
_INSTANCE_DIR = _ROOT / "configs" / "research" / "measurement_contracts" / "instances"

MT01_UNRUN = {
    "schema": "mt01_report/1",
    "status": "UNRUN",
    "coverage": "0/27",
    "authority": "research",
    "economic_claims_allowed": False,
    "note": (
        "E-MT-01 adversarial matrix coverage is a separate programme (MEASUREMENT_CONTRACT.md "
        "§2 E3): 27 failure classes, each needing a seeded mutant its probe catches. None are "
        "implemented repo-wide. This UNRUN is measured-absent, not a placeholder for a run that "
        "happened."
    ),
}


def contract_path(contract_id: str) -> Path:
    return _INSTANCE_DIR / f"{contract_id}.json"


def _corpus_from_inclusion_rule(rule: str) -> str:
    """Pull the declared corpus path out of the contract's inclusion_rule prose.

    The contracts name their corpus inline ("MEASUREMENT CORPUS = data/mt5/XAUUSD_M15.csv ONLY").
    Returns "unknown" when no path is stated — never a guessed default, since `data_source` is a
    required manifest field precisely so it cannot be assumed.
    """
    m = re.search(r"(data/[\w/\-]+\.csv)", rule or "")
    return m.group(1) if m else "unknown"


def finalize_run(contract_id: str, out_dir: Path, *,
                 extra: Optional[dict[str, Any]] = None,
                 root: Path = _ROOT) -> dict[str, Any]:
    """Write mt00 (measured), mt01 (honestly unrun), and a run manifest. Returns a summary.

    Ordered deliberately: the E-MT-00 probes READ the fingerprint / split / metrics artifacts, so
    this must run after the experiment has written them.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inst = contract_path(contract_id)
    report = run_mt00(inst, root=root)
    write_report(report, out_dir / "mt00.json")

    (out_dir / "mt01.json").write_text(
        json.dumps({**MT01_UNRUN, "contract_id": contract_id}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # Every caller-required manifest field is READ FROM THE SEALED CONTRACT, never invented here.
    # That is the point of the manifest: it records the path that actually ran, and the contract is
    # the only artifact entitled to say what that path was.
    doc = json.loads(inst.read_text(encoding="utf-8"))
    population = doc.get("population") or {}
    manifest = build_manifest(
        command=f"python -m research.evidence ({contract_id})",
        argv=list(sys.argv),
        validation_lens=(doc.get("pipeline_identity") or {}).get("engine_gate_mode", "unknown"),
        exit_model=(doc.get("exits") or {}).get("exit_model_id", "unknown"),
        cost_model_bps=(doc.get("costs") or {}).get("cost_model_id", "unknown"),
        label_source=(doc.get("labels") or {}).get("derivation_authority", "unknown"),
        instruments=list(population.get("instruments") or []),
        timeframe=population.get("timeframe", "unknown"),
        data_source=_corpus_from_inclusion_rule(population.get("inclusion_rule", "")),
        intended_work_item_id=doc.get("experiment_id", contract_id),
        network="none",
        dry_run=True,
        contract_id=contract_id,
        out_dir=str(out_dir).replace("\\", "/"),
        mt00=report.verdict,
        mt01_matrix_coverage="UNRUN",
        economic_claims_allowed=seal_verdict(report.verdict, "UNRUN"),
        # Reuse the existing stamp rather than re-deriving it: which spine truth (ACTIVE_VERSION +
        # config hash) and which canonical feature schema were live when this ran. Fail-open by
        # design there, so it never blocks a research run.
        spine_truth=production_config_block(),
        **(extra or {}),
    )
    write_run(out_dir, manifest, {
        "mt00_verdict": report.verdict,
        "mt00_failing_probes": report.failing,
        "mt00_inconclusive_probes": report.inconclusive,
    })

    # Consumer half of the anti-H1 contract: read back what was just written, so a producer that
    # silently failed to emit provenance cannot return a result as if it had.
    require_manifest(out_dir)

    return {
        "contract_id": contract_id,
        "mt00": report.verdict,
        "mt00_failing_probes": report.failing,
        "mt00_inconclusive_probes": report.inconclusive,
        "economic_claims_allowed": seal_verdict(report.verdict, "UNRUN"),
    }
