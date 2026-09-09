"""mt00.py — the E-MT-00 clean-path runner (MEASUREMENT_CONTRACT.md §2, E0–E2).

Closes the placeholder gap found 2026-08-26: every `src/research/evidence/*.py` module wrote
`{"status": "UNRUN"}` into the very file its contract declares as `mt00_report_path`. The artifact
existed and proved nothing — a sealed contract could name an mt00 report, the report could be on
disk and git-tracked, and *no run had happened*. That is the F-056 / F-079 / F-083 / F-085 silent-gap
class: a skipped measurement indistinguishable from an absent one.

This module makes the report a MEASUREMENT. It loads a sealed `MC-*` instance and evaluates the
clean-path probes the frozen schema and charter actually require, emitting a per-probe verdict with
a witness — the literal field or path that justified it.

**What a PASS is and is not.** `mt00 == PASS` is one of four clauses in the charter's E4 seal:

    economic_claims_allowed
      ⇔ mt00 == PASS ∧ mt01_matrix_coverage == COMPLETE
        ∧ contract validates schema v1.0.0 ∧ no BLOCKING open probe failures

E-MT-01 matrix coverage is a separate program (0/27 probes repo-wide). This runner therefore can
NEVER grant economic admissibility on its own, and `economic_claims_allowed` is left untouched by
construction — `seal_verdict` refuses to return an admissible seal while mt01 is anything but
COMPLETE. Authority: research only (CLAUDE.md §6.5). A PASS proves the declared path is intact,
never that the result is real, replicable, or economic.

**Honest verdicts.** A probe that cannot be decided mechanically returns `INCONCLUSIVE`, and any
INCONCLUSIVE downgrades the run to `PARTIAL`. Nothing here defaults to green: an unreadable
artifact, a missing module, or an absent declared file is a FAIL, not a skip.

Schema: `docs/governance/measurement_contract.schema.json` (v1.0.0, FROZEN).
Result binding: `src/governance/measurement_result_log.py` (the executed-run record).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

_ROOT = Path(__file__).resolve().parents[3]

SCHEMA_PATH = _ROOT / "docs" / "governance" / "measurement_contract.schema.json"

#: Probe outcomes. `INCONCLUSIVE` is first-class — it is what a probe returns when the question is
#: real but not mechanically decidable here, and it must never be rendered as a pass.
PASS, FAIL, INCONCLUSIVE = "PASS", "FAIL", "INCONCLUSIVE"

#: Run verdicts, mirroring `measurement_result_log.MT00_VALUES` exactly.
V_PASS, V_FAIL, V_PARTIAL, V_UNRUN = "PASS", "FAIL", "PARTIAL", "UNRUN"

#: The seven declared surfaces (charter §2 E0.4).
SURFACES: tuple[str, ...] = (
    "population", "features", "labels", "costs", "exits", "splits", "metrics",
)


class Mt00Error(RuntimeError):
    """The runner could not be constructed — a contract is unreadable or the schema is missing."""


@dataclass(frozen=True)
class Probe:
    """One clean-path probe outcome. `witness` is the byte that justified the verdict."""

    probe_id: str
    stage: str          # E0 | E1 | E2
    outcome: str        # PASS | FAIL | INCONCLUSIVE
    detail: str
    witness: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "probe_id": self.probe_id, "stage": self.stage, "outcome": self.outcome,
            "detail": self.detail, "witness": self.witness,
        }


@dataclass
class Mt00Report:
    contract_id: str
    verdict: str
    probes: list[Probe] = field(default_factory=list)

    @property
    def failing(self) -> list[str]:
        return [p.probe_id for p in self.probes if p.outcome == FAIL]

    @property
    def inconclusive(self) -> list[str]:
        return [p.probe_id for p in self.probes if p.outcome == INCONCLUSIVE]

    def as_dict(self) -> dict[str, Any]:
        counts = {k: sum(1 for p in self.probes if p.outcome == k)
                  for k in (PASS, FAIL, INCONCLUSIVE)}
        return {
            "schema": "mt00_report/1",
            "status": self.verdict,
            "contract_id": self.contract_id,
            "authority": "research",
            "economic_claims_allowed": False,
            "note": (
                "E-MT-00 clean-path only. mt00 PASS is ONE of four E4 clauses; E-MT-01 matrix "
                "coverage is a separate program and economic admissibility is not granted here."
            ),
            "counts": counts,
            "failing_probes": self.failing,
            "inconclusive_probes": self.inconclusive,
            "probes": [p.as_dict() for p in self.probes],
        }


def _verdict(probes: list[Probe]) -> str:
    """FAIL beats INCONCLUSIVE beats PASS. An empty probe set is never a pass."""
    if not probes:
        return V_FAIL
    if any(p.outcome == FAIL for p in probes):
        return V_FAIL
    if any(p.outcome == INCONCLUSIVE for p in probes):
        return V_PARTIAL
    return V_PASS


def load_contract(path: Path | str) -> dict:
    p = Path(path)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Mt00Error(f"unreadable contract instance {p}: {exc}") from exc


def _schema() -> dict:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Mt00Error(f"frozen schema unreadable at {SCHEMA_PATH}: {exc}") from exc


# --- E0: the sealed contract ---------------------------------------------------------------


def _probes_e0(doc: Mapping[str, Any], schema: Mapping[str, Any], path: Path) -> list[Probe]:
    out: list[Probe] = []
    props = schema.get("properties", {})

    const = (props.get("schema_version") or {}).get("const")
    actual = doc.get("schema_version")
    out.append(Probe(
        "E0-01-SCHEMA-VERSION", "E0", PASS if actual == const else FAIL,
        f"instance schema_version {actual!r} vs frozen const {const!r}", str(actual),
    ))

    missing = [k for k in schema.get("required", []) if k not in doc]
    out.append(Probe(
        "E0-02-TOP-LEVEL-REQUIRED", "E0", PASS if not missing else FAIL,
        "all top-level required keys present" if not missing else f"missing: {missing}",
        ",".join(missing),
    ))

    surface_gaps: list[str] = []
    for surface in SURFACES:
        body = doc.get(surface)
        if not isinstance(body, Mapping):
            surface_gaps.append(f"{surface}: absent or not an object")
            continue
        for key in (props.get(surface) or {}).get("required", []):
            if key not in body:
                surface_gaps.append(f"{surface}.{key}")
    out.append(Probe(
        "E0-03-SEVEN-SURFACES-POPULATED", "E0", PASS if not surface_gaps else FAIL,
        "all seven surfaces carry their required fields" if not surface_gaps
        else f"gaps: {surface_gaps}",
        ",".join(surface_gaps),
    ))

    admissible = (doc.get("authority") or {}).get("economic_admissible")
    # Charter E0.3: economic_admissible stays false until E-MT-00 PASS. A contract that seals
    # itself admissible BEFORE its run is the defect this clause exists to catch.
    out.append(Probe(
        "E0-04-NOT-PRE-SEALED-ADMISSIBLE", "E0", PASS if admissible is False else FAIL,
        f"authority.economic_admissible={admissible!r} (must be false on a sealed, unrun contract)",
        repr(admissible),
    ))

    subs = doc.get("prohibited_substitutions") or []
    covered = {s.get("surface") for s in subs if isinstance(s, Mapping)}
    unclassed = [s.get("surface") for s in subs
                 if isinstance(s, Mapping)
                 and not str(s.get("historical_class", "")).startswith("FC-")]
    if not subs:
        out.append(Probe("E0-05-PROHIBITED-SUBSTITUTIONS", "E0", FAIL,
                         "no prohibited_substitutions declared (charter E0.6)"))
    elif unclassed:
        out.append(Probe("E0-05-PROHIBITED-SUBSTITUTIONS", "E0", FAIL,
                         f"substitution(s) without an FC-* historical_class: {unclassed}",
                         ",".join(str(u) for u in unclassed)))
    else:
        uncovered = sorted(set(SURFACES) - covered)
        out.append(Probe(
            "E0-05-PROHIBITED-SUBSTITUTIONS", "E0",
            PASS if not uncovered else INCONCLUSIVE,
            f"{len(subs)} substitutions covering {sorted(covered)}"
            + ("" if not uncovered else
               f"; no forbid declared for {uncovered} — the charter requires one per surface the "
               f"experiment USES, which this runner cannot determine mechanically"),
            ",".join(uncovered),
        ))

    stem_ok = doc.get("contract_id") == path.stem
    out.append(Probe(
        "E0-06-CONTRACT-ID-BINDS-FILE", "E0", PASS if stem_ok else FAIL,
        f"contract_id {doc.get('contract_id')!r} vs filename stem {path.stem!r}",
        str(doc.get("contract_id")),
    ))
    return out


# --- E1: fingerprints (identity of the measured object) -------------------------------------


def _probes_e1(doc: Mapping[str, Any], path: Path, root: Path) -> list[Probe]:
    out: list[Probe] = []
    arts = doc.get("evidence_artifacts") or {}

    declared_self = arts.get("contract_path")
    self_rel = str(path.relative_to(root)).replace("\\", "/") if _under(path, root) else None
    out.append(Probe(
        "E1-01-CONTRACT-SELF-REFERENCE", "E1",
        PASS if declared_self and declared_self == self_rel else FAIL,
        f"evidence_artifacts.contract_path={declared_self!r} vs actual {self_rel!r}",
        str(declared_self),
    ))

    # Every declared (non-null) artifact must exist and parse. A null path is an honest
    # "not produced for this experiment" and is reported, never counted as a pass.
    missing: list[str] = []
    unreadable: list[str] = []
    nulls: list[str] = []
    present: list[str] = []
    skipped: list[str] = []
    for key, rel in sorted(arts.items()):
        # `mt00_report_path` is this run's OWN output and `mt01_...` belongs to a separate
        # programme — neither is an input this run can require. Demanding them here made a first
        # run of a contract fail for not having already produced its own report. Their status is
        # reported by E1-06 instead of being folded into an input-resolution pass.
        if key in ("contract_path", "code_commit",
                   "mt00_report_path", "mt01_mutation_coverage_path"):
            continue
        if rel in (None, "", [], {}):
            nulls.append(key)
            continue
        # Not every evidence_artifacts value is a path. `data_snapshot_ids` carries a LIST of
        # `sha256:` content ids — a content address, not a file — and treating it as a missing
        # file would manufacture a failure. Skipped and reported, never silently passed.
        if not isinstance(rel, str) or rel.startswith("sha256:"):
            skipped.append(f"{key} (not a path)")
            continue
        # Some instances record absolute paths; honour them rather than re-rooting.
        target = Path(rel) if Path(rel).is_absolute() else root / rel
        if not target.is_file():
            missing.append(f"{key}={rel}")
            continue
        if target.suffix == ".json":
            try:
                json.loads(target.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                unreadable.append(f"{key}={rel}")
                continue
        present.append(key)

    if missing or unreadable:
        out.append(Probe(
            "E1-02-DECLARED-ARTIFACTS-RESOLVE", "E1", FAIL,
            f"declared but absent: {missing}; declared but unparseable: {unreadable}",
            ",".join(missing + unreadable),
        ))
    else:
        out.append(Probe(
            "E1-02-DECLARED-ARTIFACTS-RESOLVE", "E1", PASS,
            f"{len(present)} declared artifacts resolve and parse; {len(nulls)} declared null "
            f"({nulls}); {len(skipped)} non-path ({skipped})", ",".join(present),
        ))

    fp_rel = arts.get("population_fingerprint_path")
    fp_probe = _fingerprint_probe(root, fp_rel, doc)
    out.append(fp_probe)

    # Whether the digest actually MIXED every key it names is a property of the producer, not of
    # the artifact — the fingerprint records a list and a hash, and the two cannot be reconciled
    # without re-deriving the population. Kept as its own probe so the limit is stated, never
    # absorbed into E1-03's pass. (Observed while building this runner: at least one producer
    # declares 7 inputs and mixes 4 of them — the three constant-per-run identifiers are named but
    # not hashed, so two different corpora could collide. Recorded, not adjudicated here.)
    out.append(Probe(
        "E1-05-FINGERPRINT-DIGEST-COMPOSITION", "E1", INCONCLUSIVE,
        "the fingerprint's key LIST is checked against the contract (E1-03); whether the digest "
        "mixed each of those keys is not verifiable from the artifact and needs re-derivation",
        str(fp_probe.witness),
    ))

    # Report the two trust-report paths explicitly rather than letting their absence vanish.
    trust = doc.get("trust_status") or {}
    mt01_rel = arts.get("mt01_mutation_coverage_path")
    mt01_here = bool(mt01_rel) and (root / str(mt01_rel)).is_file()
    mt01_claim = trust.get("mt01_matrix_coverage")
    if mt01_claim == "UNRUN":
        # Honest: nothing claims coverage, so a missing report is consistent, not a gap.
        out.append(Probe(
            "E1-06-TRUST-REPORTS", "E1", PASS,
            f"mt01_matrix_coverage={mt01_claim!r} and the coverage report is "
            f"{'present' if mt01_here else 'absent'} — consistent either way while UNRUN",
            str(mt01_rel),
        ))
    else:
        out.append(Probe(
            "E1-06-TRUST-REPORTS", "E1", PASS if mt01_here else FAIL,
            f"mt01_matrix_coverage={mt01_claim!r} claims coverage; its report is "
            f"{'present' if mt01_here else 'ABSENT — declared-but-unexecuted (F-083)'}",
            str(mt01_rel),
        ))

    split_rel = arts.get("split_manifest_path")
    out.append(_split_probe(root, split_rel, doc))
    return out


def _dotted_module(rel_path: str) -> str:
    """`src/research/mother_range/driver.py` -> `research.mother_range.driver`.

    Returns "" for anything that is not a single importable module under `src/`.
    """
    p = rel_path.strip()
    if not p.endswith(".py"):
        return ""
    parts = Path(p).with_suffix("").parts
    if parts and parts[0] == "src":
        parts = parts[1:]
    return ".".join(parts) if parts else ""


def _strip_type_checking(src: str) -> str:
    """Drop `if TYPE_CHECKING:` blocks — their imports never execute at runtime.

    Indentation-based, matching how the repo actually writes them. A file that does not use the
    guard is returned unchanged.
    """
    if "TYPE_CHECKING" not in src:
        return src
    kept: list[str] = []
    skipping_indent: Optional[int] = None
    for line in src.splitlines():
        stripped = line.strip()
        if skipping_indent is not None:
            indent = len(line) - len(line.lstrip())
            if stripped and indent <= skipping_indent:
                skipping_indent = None
            else:
                continue
        # Strip a trailing comment first — `if TYPE_CHECKING:  # avoid the heavy import` does not
        # end with ':' and was missed, which is exactly how research/contracts.py was misread.
        code = stripped.split("#", 1)[0].rstrip()
        if code.startswith("if TYPE_CHECKING") and code.endswith(":"):
            skipping_indent = len(line) - len(line.lstrip())
            continue
        kept.append(line)
    return "\n".join(kept)


def _under(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _fingerprint_probe(root: Path, rel: Optional[str], doc: Mapping[str, Any]) -> Probe:
    """The population fingerprint must exist and hash over the contract's DECLARED unit keys.

    Charter E1: it is what stops a detection stream silently replacing trade units
    (`FC-POP-DETECTION-AS-TRADE`).
    """
    if not rel:
        return Probe("E1-03-POPULATION-FINGERPRINT", "E1", FAIL,
                     "population_fingerprint_path is required by the frozen schema but is null")
    target = root / str(rel)
    if not target.is_file():
        return Probe("E1-03-POPULATION-FINGERPRINT", "E1", FAIL,
                     f"declared fingerprint absent: {rel}", str(rel))
    try:
        fp = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Probe("E1-03-POPULATION-FINGERPRINT", "E1", FAIL,
                     f"fingerprint unreadable: {exc}", str(rel))

    digest = fp.get("sha256") if isinstance(fp, Mapping) else None
    if not (isinstance(digest, str) and len(digest) == 64):
        return Probe("E1-03-POPULATION-FINGERPRINT", "E1", FAIL,
                     "fingerprint carries no sha256 digest over the unit keys", str(rel))

    declared_keys = list((doc.get("population") or {}).get("population_hash_inputs") or [])
    # The artifact names its key list with the schema's own field name; `keys`/`fields` are
    # tolerated aliases so a differently-shaped producer is compared rather than waved through.
    recorded_keys = list(
        fp.get("population_hash_inputs") or fp.get("keys") or fp.get("fields") or []
    )
    if not recorded_keys:
        return Probe(
            "E1-03-POPULATION-FINGERPRINT", "E1", INCONCLUSIVE,
            "fingerprint carries a digest but does not record WHICH keys it hashed, so it cannot "
            "be compared to population_hash_inputs", digest,
        )
    if sorted(recorded_keys) != sorted(declared_keys):
        return Probe(
            "E1-03-POPULATION-FINGERPRINT", "E1", FAIL,
            f"fingerprint declares {sorted(recorded_keys)} but the contract declares "
            f"{sorted(declared_keys)}", digest,
        )
    return Probe("E1-03-POPULATION-FINGERPRINT", "E1", PASS,
                 f"fingerprint key list matches the contract's population_hash_inputs "
                 f"{sorted(declared_keys)}", digest)


def _split_probe(root: Path, rel: Optional[str], doc: Mapping[str, Any]) -> Probe:
    """The split manifest must exist when a split is declared, and must not be empty."""
    splits = doc.get("splits") or {}
    scheme = splits.get("scheme")
    if not rel:
        return Probe(
            "E1-04-SPLIT-MANIFEST", "E1", FAIL,
            f"splits.scheme={scheme!r} is declared but split_manifest_path is null — an OOS split "
            f"that produces no manifest is the F-083 declared-but-unexecuted class",
            str(scheme),
        )
    target = root / str(rel)
    if not target.is_file():
        return Probe("E1-04-SPLIT-MANIFEST", "E1", FAIL,
                     f"declared split manifest absent: {rel}", str(rel))
    try:
        body = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Probe("E1-04-SPLIT-MANIFEST", "E1", FAIL,
                     f"split manifest unreadable: {exc}", str(rel))
    if not body:
        return Probe("E1-04-SPLIT-MANIFEST", "E1", FAIL,
                     "split manifest is empty", str(rel))
    return Probe("E1-04-SPLIT-MANIFEST", "E1", PASS,
                 f"scheme={scheme!r}, manifest carries {len(body)} field(s)", str(rel))


# --- E2: clean-path probes on the declared pipeline ------------------------------------------


def _probes_e2(doc: Mapping[str, Any], root: Path) -> list[Probe]:
    out: list[Probe] = []
    ident = doc.get("pipeline_identity") or {}

    in_path = [str(m) for m in ident.get("modules_in_path") or []]
    absent = [m for m in in_path if not (root / m).is_file()]
    out.append(Probe(
        "E2-01-DECLARED-MODULES-EXIST", "E2", PASS if in_path and not absent else FAIL,
        "every module_in_path is on disk" if in_path and not absent
        else (f"declared modules absent: {absent}" if in_path else "modules_in_path is empty"),
        ",".join(absent),
    ))

    # The out-of-path declaration is load-bearing: it is how a contract says "the spine did NOT run
    # here". But `out of path` is claimed in two different senses, and conflating them manufactures
    # defects (§6.8 `different != wrong`):
    #   * STRUCTURAL  - "src/execution/loop.py": the module is not reached at all. Grep-decidable.
    #   * BEHAVIOURAL - "src/config_layer/rr/rr_fusion.py (enabled false)": the module IS imported
    #                   and is inert by configuration. engine_runner.py:46 really does import it,
    #                   and that is not a violation of this declaration.
    # Only the structural form is adjudicated. A qualified or glob entry returns INCONCLUSIVE with
    # its reason rather than a FAIL this runner cannot justify.
    out_of_path = [str(m) for m in ident.get("modules_explicitly_out_of_path") or []]
    structural = [m for m in out_of_path if "(" not in m and "*" not in m]
    undecidable = [m for m in out_of_path if m not in structural]

    leaks: list[str] = []
    for module in in_path:
        f = root / module
        if not f.is_file():
            continue
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # A TYPE_CHECKING-guarded import is not a runtime path (research/contracts.py imports
        # crt_engine_v2 that way purely for a type annotation). Strip those blocks first.
        runtime_src = _strip_type_checking(src)
        for banned in structural:
            dotted = _dotted_module(banned)
            if not dotted:
                continue
            # Match the FULL dotted path, never the bare stem: `research/mother_range/driver.py`
            # and `research/evidence/driver.py` share the stem `driver`, and stem-matching reported
            # the second as a violation of a declaration about the first.
            if (f"import {dotted}" in runtime_src or f"from {dotted} import" in runtime_src):
                leaks.append(f"{module} imports {banned}")

    if leaks:
        outcome, detail = FAIL, f"declared-out-of-path modules reached at runtime: {leaks}"
    elif undecidable:
        outcome, detail = INCONCLUSIVE, (
            f"{len(structural)} structural out-of-path declarations hold; {len(undecidable)} are "
            f"qualified or glob-shaped and assert BEHAVIOURAL inertness, which an import scan "
            f"cannot decide: {undecidable}"
        )
    else:
        outcome, detail = PASS, "no module_in_path imports a module declared explicitly out of path"
    out.append(Probe("E2-02-OUT-OF-PATH-NOT-IMPORTED", "E2", outcome, detail, ";".join(leaks)))

    level = ident.get("dataset_integrity_level")
    out.append(Probe(
        "E2-03-DATASET-INTEGRITY-DECLARED", "E2",
        PASS if level else FAIL,
        f"pipeline_identity.dataset_integrity_level={level!r}", str(level),
    ))

    # The charter's §5 "not minimum evidence" list forbids passing on a narrative. Whether the
    # metric gate actually consumed only declared metrics is a property of the RUN, not of the
    # contract text, and this runner reads artifacts rather than re-executing the experiment.
    banned = list((doc.get("metrics") or {}).get("forbidden_metric_substitutions") or [])
    out.append(Probe(
        "E2-04-METRIC-GATE-TRACE", "E2", INCONCLUSIVE,
        f"{len(banned)} forbidden metric substitutions are declared; confirming the success gate "
        f"consumed only declared metrics requires re-executing the experiment under trace, which "
        f"this clean-path runner does not do",
        ",".join(str(b) for b in banned[:3]),
    ))
    return out


def run_mt00(contract_path: Path | str, root: Path = _ROOT) -> Mt00Report:
    """Evaluate E-MT-00 clean-path probes for one sealed instance. Never mutates the contract."""
    path = Path(contract_path).resolve()
    doc = load_contract(path)
    schema = _schema()
    probes = (_probes_e0(doc, schema, path)
              + _probes_e1(doc, path, root)
              + _probes_e2(doc, root))
    return Mt00Report(
        contract_id=str(doc.get("contract_id") or path.stem),
        verdict=_verdict(probes),
        probes=probes,
    )


def seal_verdict(mt00: str, mt01_matrix_coverage: str) -> bool:
    """The charter's E4 seal. Returns whether economic claims are admissible.

    Deliberately a pure function of both clauses: mt00 PASS alone can never open the gate, so no
    caller can reach admissibility by running this module. Repo-wide mt01 coverage is 0/27.
    """
    return mt00 == V_PASS and mt01_matrix_coverage == "COMPLETE"


def write_report(report: Mt00Report, out_path: Path | str) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="E-MT-00 clean-path runner for a sealed MC-* instance")
    ap.add_argument("contract", help="path to the sealed MC-*.json instance")
    ap.add_argument("--out", default=None, help="write the mt00 report here (default: the "
                                                "contract's declared mt00_report_path)")
    args = ap.parse_args(argv)

    report = run_mt00(args.contract)
    doc = load_contract(args.contract)
    out = args.out or (doc.get("evidence_artifacts") or {}).get("mt00_report_path")
    if out:
        write_report(report, _ROOT / out if not Path(out).is_absolute() else out)

    print(f"{report.contract_id}: mt00={report.verdict}")
    for p in report.probes:
        if p.outcome != PASS:
            print(f"  {p.outcome:12s} {p.probe_id}: {p.detail}")
    print(f"  economic_claims_allowed={seal_verdict(report.verdict, 'UNRUN')} "
          f"(mt01_matrix_coverage=UNRUN, 0/27 probes)")
    return 0 if report.verdict != V_FAIL else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
