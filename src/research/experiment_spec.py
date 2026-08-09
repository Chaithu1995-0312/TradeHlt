"""
experiment_spec.py — the immutable execution specification for the research platform.

WHY THIS EXISTS (Research Runtime Step 1c, before Step 2).
Every one of the 194 existing drivers re-implements the same five things in Python:
which corpus, which instrument, which models, how to measure, where to write. That
duplication is what makes each new question a new script. `ExperimentSpec` names those
five things ONCE, as data, so implementation validation / benchmarking / explainability
/ comparison / ablation all consume the same contract instead of forking a driver.

DESIGN RULES (each one closes a specific failure this repo has already had):

  * **References, never redefines.** Measurement policy is a POINTER to a research
    config (`ResearchConfig`, already frozen + SHA-hashed); production behavior is a
    POINTER to a production config version. A spec that inlined engine params would
    become a second config system - the exact risk flagged in the architecture review.
  * **Corpus pins live in the spec, not in Python.** A SHA hardcoded in a driver forces
    a fork per instrument; that is the mechanism that produced the 194.
  * **Compared against the bundle, not the registry.** `model_selection.mode` resolves
    through `ProductionBundle` so "the selected model" means what production actually
    EXECUTES (Selected != Enabled; see production_bundle.py).
  * **Authority is frozen at NONE.** Construction rejects any other value. A research
    artifact that looks authoritative will eventually be cited as authoritative
    (CLAUDE.md §6.5).
  * **Deterministic identity.** `sha256()` over canonical JSON, so an experiment's
    provenance is a value, not a wall-clock artifact (mirrors `ResearchConfig.sha256`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

# How `model_selection.mode` resolves against the ProductionBundle.
MODE_EXECUTING = "executing"   # only families whose checkpoint demonstrably runs
MODE_SELECTED = "selected"     # registry-active versions (Selected, may not be Enabled)
MODE_ALL = "all"               # every registry version - the benchmarking surface
MODE_EXPLICIT = "explicit"     # exactly the versions named in `versions`
_MODES = frozenset({MODE_EXECUTING, MODE_SELECTED, MODE_ALL, MODE_EXPLICIT})

# What kind of question the experiment asks. Descriptive: reducers key off outputs,
# never off this label (mirrors the `family` discipline in research/contracts.py).
KINDS = frozenset(
    {
        "implementation_validation",
        "benchmark",
        "comparison",
        "explainability",
        "ablation",
        "promotion_readiness",
    }
)


class ExperimentSpecError(ValueError):
    """Fail-closed spec construction error."""


@dataclass(frozen=True)
class CorpusSpec:
    """One pinned dataset. The pin is DATA, so a new instrument is a new spec, not a fork."""

    path: str                        # repo-relative
    instrument: str
    sha256: Optional[str] = None     # None = deliberately unpinned (recorded as such)
    rows: Optional[int] = None

    def canonical(self) -> dict:
        return {
            "path": self.path.replace("\\", "/"),
            "instrument": self.instrument,
            "sha256": self.sha256,
            "rows": self.rows,
        }


@dataclass(frozen=True)
class ModelSelectionSpec:
    """Which executables enter the matrix."""

    mode: str = MODE_SELECTED
    families: tuple[str, ...] = ()                       # () = every family
    versions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # explicit mode
    include_missing_artifacts: bool = True               # dangling entries are RESULTS
    hypotheses: tuple[str, ...] = ()                     # the other Executable kind

    def canonical(self) -> dict:
        return {
            "mode": self.mode,
            "families": list(self.families),
            "versions": {k: list(v) for k, v in sorted(self.versions.items())},
            "include_missing_artifacts": self.include_missing_artifacts,
            "hypotheses": list(self.hypotheses),
        }


@dataclass(frozen=True)
class OutputSpec:
    """Where results land. Never a dated filename baked into code."""

    out_dir: str
    artifact_name: str
    write_latest: bool = True

    def canonical(self) -> dict:
        return {
            "out_dir": self.out_dir.replace("\\", "/"),
            "artifact_name": self.artifact_name,
            "write_latest": self.write_latest,
        }


@dataclass(frozen=True)
class ExperimentSpec:
    """Immutable, hashable description of one research execution."""

    experiment_id: str
    kind: str
    corpus: tuple[CorpusSpec, ...]
    model_selection: ModelSelectionSpec
    output: OutputSpec
    # POINTERS - never inlined parameter sets
    measurement_config: Optional[str] = None       # path to a research config JSON
    production_config_ref: Optional[str] = None    # production version (None = ACTIVE_VERSION)
    notes: str = ""
    authority: str = "NONE"

    def __post_init__(self) -> None:
        if self.authority != "NONE":
            raise ExperimentSpecError(
                f"authority is frozen at 'NONE' for research specs, got {self.authority!r}"
            )
        if self.kind not in KINDS:
            raise ExperimentSpecError(f"unknown kind {self.kind!r}; expected one of {sorted(KINDS)}")
        if self.model_selection.mode not in _MODES:
            raise ExperimentSpecError(
                f"unknown selection mode {self.model_selection.mode!r}; expected {sorted(_MODES)}"
            )
        if self.model_selection.mode == MODE_EXPLICIT and not self.model_selection.versions:
            raise ExperimentSpecError("mode='explicit' requires model_selection.versions")
        if not self.corpus:
            raise ExperimentSpecError("at least one CorpusSpec is required")
        if not self.experiment_id.strip():
            raise ExperimentSpecError("experiment_id must be non-empty")

    # ── deterministic identity ───────────────────────────────────────────────
    def canonical(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "kind": self.kind,
            "corpus": [c.canonical() for c in self.corpus],
            "model_selection": self.model_selection.canonical(),
            "output": self.output.canonical(),
            "measurement_config": (
                self.measurement_config.replace("\\", "/") if self.measurement_config else None
            ),
            "production_config_ref": self.production_config_ref,
            "authority": self.authority,
        }

    def sha256(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    # ── construction ─────────────────────────────────────────────────────────
    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> "ExperimentSpec":
        try:
            corpus = tuple(
                CorpusSpec(
                    path=str(c["path"]),
                    instrument=str(c["instrument"]),
                    sha256=(str(c["sha256"]) if c.get("sha256") else None),
                    rows=(int(c["rows"]) if c.get("rows") is not None else None),
                )
                for c in d["corpus"]
            )
        except (KeyError, TypeError) as exc:
            raise ExperimentSpecError(f"invalid corpus block: {exc}") from exc

        ms = d.get("model_selection") or {}
        selection = ModelSelectionSpec(
            mode=str(ms.get("mode", MODE_SELECTED)),
            families=tuple(ms.get("families") or ()),
            versions={k: tuple(v) for k, v in (ms.get("versions") or {}).items()},
            include_missing_artifacts=bool(ms.get("include_missing_artifacts", True)),
            hypotheses=tuple(ms.get("hypotheses") or ()),
        )

        out = d.get("output") or {}
        try:
            output = OutputSpec(
                out_dir=str(out["out_dir"]),
                artifact_name=str(out["artifact_name"]),
                write_latest=bool(out.get("write_latest", True)),
            )
        except KeyError as exc:
            raise ExperimentSpecError(f"output block requires out_dir + artifact_name: {exc}") from exc

        return cls(
            experiment_id=str(d["experiment_id"]),
            kind=str(d["kind"]),
            corpus=corpus,
            model_selection=selection,
            output=output,
            measurement_config=(str(d["measurement_config"]) if d.get("measurement_config") else None),
            production_config_ref=(
                str(d["production_config_ref"]) if d.get("production_config_ref") else None
            ),
            notes=str(d.get("notes", "")),
            authority=str(d.get("authority", "NONE")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "ExperimentSpec":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = [
    "CorpusSpec",
    "ModelSelectionSpec",
    "OutputSpec",
    "ExperimentSpec",
    "ExperimentSpecError",
    "KINDS",
    "MODE_ALL",
    "MODE_EXECUTING",
    "MODE_EXPLICIT",
    "MODE_SELECTED",
]
