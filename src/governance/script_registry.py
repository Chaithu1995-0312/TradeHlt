"""ScriptRegistry — inventory / debt visibility for scripts (SITS).

One JSONL line per script at ``data/script_registry.jsonl`` (GENERATED), seeded from hybrid
PRIMARY truth: committed stubs (``docs/governance/script_registry_stubs.jsonl``) + optional
Python overlays in ``scripts/governance/seed_script_registry.py``.

Sibling of ``governance.hypothesis_registry`` / ``governance.framework_registry``:
same persistence (``utils.jsonl_writer``), same closed-schema / pinned-authority discipline.

Authority (CLAUDE.md §6.5): every record's ``authority`` is the pinned literal
``"inventory"``. This registry grants **no** promote / economic / production authority.

Schema: ``docs/reference/schemas.md §9.8``. Design:
``docs/implementation_plan/script-implementation-traceability-sits-design.md``.
Enforced by ``tests/test_script_registry.py``. Query/CI:
``python scripts/governance/query_scripts.py --validate``.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from governance.framework_registry import ValidationError
from utils.jsonl_writer import append_jsonl, read_jsonl

# --------------------------------------------------------------------------- enums

CATEGORY_ENUM = frozenset({
    "PROBE",
    "DIAGNOSTIC",
    "RESEARCH_RUNNER",
    "CANONICAL_CLI",
    "TRAINING",
    "GOVERNANCE",
    "DATA",
    "MAINTENANCE",
    "ORPHAN",
})
LIFECYCLE_ENUM = frozenset({"ACTIVE", "EPHEMERAL", "SUPERSEDED", "DEAD", "ARCHIVED"})
TERMINAL_LIFECYCLES = frozenset({"SUPERSEDED", "DEAD", "ARCHIVED"})
IMPL_STATUS_ENUM = frozenset({
    "LOGIC_IN_SCRIPT",
    "EXTRACTED_TO_SRC",
    "WIRED",
    "REGISTERED",
    "TESTED",
    "CLOSED_EPHEMERAL",
    "N_A",
    "ACCEPTED_COLOCATED",
})
OWNER_KIND_ENUM = frozenset({"HUMAN", "AGENT", "MIXED", "UNKNOWN"})
AUTHORITY = "inventory"  # pinned — §6.5

_ID_RE = re.compile(r"^SCR-\d{3,}$")
_WONTFIX_RE = re.compile(r"wontfix:reason=.+", re.IGNORECASE)

_REQUIRED_FIELDS = (
    "id",
    "path",
    "category",
    "lifecycle",
    "implementation_status",
    "owner_kind",
    "owner_ref",
    "purpose",
    "task_refs",
    "dest_modules",
    "tests",
    "config_keys",
    "control_plane_id",
    "agent_tool_id",
    "has_main",
    "superseded_by",
    "created",
    "last_validated",
    "ttl_days",
    "logic_in_script",
    "notes",
    "authority",
)
_LIST_FIELDS = ("task_refs", "dest_modules", "tests", "config_keys")
_CLIMBING_STATUSES = frozenset({
    "EXTRACTED_TO_SRC", "WIRED", "REGISTERED", "TESTED",
})


def normalize_posix(path: str | Path) -> str:
    """Repo-relative POSIX path (forward slashes, no leading ./)."""
    s = str(path).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return s.lstrip("/")


def scr_num(script_id: str) -> int:
    """Numeric part of SCR-NNN; raises ValueError if malformed."""
    if not isinstance(script_id, str) or not _ID_RE.match(script_id):
        raise ValueError(f"id must match SCR-NNN, got {script_id!r}")
    return int(script_id.split("-", 1)[1])


def load_canonical_allowlist(path: "Path | str") -> set[str]:
    """Load script_canonical_allowlist.json → set of POSIX paths."""
    import json

    p = Path(path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    return {normalize_posix(x) for x in (data.get("paths") or [])}


def _load_core_command_specs():
    """Import core_command_specs under either PYTHONPATH=repo or PYTHONPATH=src."""
    try:
        from src.control_plane.registry import core_command_specs  # type: ignore

        return core_command_specs
    except ImportError:
        from control_plane.registry import core_command_specs  # type: ignore

        return core_command_specs


def command_specs_by_script(
    specs: "list | tuple | None" = None,
) -> dict[str, str]:
    """Reverse map CommandSpec.script → command id (unique scripts only).

    Only file-like script fields (scripts/**, src/**, root *.py) are included.
    Module modes (e.g. ``inout.runner``) are skipped — not SITS inventory paths.
    """
    if specs is None:
        specs = _load_core_command_specs()()
    out: dict[str, str] = {}
    for spec in specs:
        script = normalize_posix(getattr(spec, "script", "") or "")
        if not script:
            continue
        # Skip module mode / dotted package runners without a path segment
        if not (
            script.startswith("scripts/")
            or script.startswith("src/")
            or (script.endswith(".py") and "/" not in script)
        ):
            continue
        # Prefer first registration if duplicates ever appear
        out.setdefault(script, getattr(spec, "id"))
    return out


class ScriptRegistry:
    """In-memory view of the JSONL script inventory (latest line per id) + validators."""

    def __init__(self, path: "Path | str | None" = None) -> None:
        self.path: Optional[Path] = Path(path) if path else None
        self._records: dict[str, dict] = {}

    # ---------------------------------------------------------------- load / query

    def load(self, path: "Path | str | None" = None) -> int:
        if path is not None:
            self.path = Path(path)
        if self.path is None:
            raise ValueError("ScriptRegistry.load: no path given")
        self._records = {}
        for rec in read_jsonl(self.path):
            sid = rec.get("id")
            if sid:
                self._records[sid] = rec
        return len(self._records)

    @property
    def records(self) -> list[dict]:
        return list(self._records.values())

    def get(self, script_id: str) -> dict:
        if script_id not in self._records:
            raise KeyError(f"no script with id {script_id!r}")
        return self._records[script_id]

    def filter(
        self,
        *,
        category: Optional[str] = None,
        lifecycle: Optional[str] = None,
        implementation_status: Optional[str] = None,
        task: Optional[str] = None,
        path_substr: Optional[str] = None,
        owner_kind: Optional[str] = None,
    ) -> list[dict]:
        out = self.records
        if category is not None:
            out = [r for r in out if r.get("category") == category]
        if lifecycle is not None:
            out = [r for r in out if r.get("lifecycle") == lifecycle]
        if implementation_status is not None:
            out = [r for r in out if r.get("implementation_status") == implementation_status]
        if task is not None:
            out = [r for r in out if task in (r.get("task_refs") or [])]
        if path_substr is not None:
            needle = path_substr.replace("\\", "/")
            out = [r for r in out if needle in normalize_posix(r.get("path", ""))]
        if owner_kind is not None:
            out = [r for r in out if r.get("owner_kind") == owner_kind]
        return sorted(out, key=lambda r: r.get("id", ""))

    def summary(self) -> dict:
        def _tally(key: str) -> dict:
            out: dict = {}
            for r in self.records:
                out[r.get(key)] = out.get(r.get(key), 0) + 1
            return dict(sorted(out.items(), key=lambda kv: str(kv[0])))

        return {
            "total": len(self._records),
            "by_category": _tally("category"),
            "by_lifecycle": _tally("lifecycle"),
            "by_implementation_status": _tally("implementation_status"),
            "by_owner_kind": _tally("owner_kind"),
            "authority": AUTHORITY,
        }

    # ---------------------------------------------------------------- promotion / debt

    @staticmethod
    def is_valid_promotion_plan(rec: dict) -> bool:
        """True if notes non-empty AND (dest_modules non-empty OR wontfix:reason=…)."""
        notes = (rec.get("notes") or "").strip()
        if not notes:
            return False
        dest = rec.get("dest_modules") or []
        if isinstance(dest, list) and len(dest) >= 1:
            return True
        return bool(_WONTFIX_RE.search(notes))

    @staticmethod
    def parse_created(rec: dict) -> Optional[datetime]:
        """Parse record ``created`` ISO-8601 to aware UTC datetime; None if unparseable."""
        raw = rec.get("created")
        if not raw or not isinstance(raw, str):
            return None
        text = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def age_days(rec: dict, *, now: Optional[datetime] = None) -> Optional[float]:
        """Days since ``created`` (float); None if created missing/unparseable."""
        created = ScriptRegistry.parse_created(rec)
        if created is None:
            return None
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return (now - created).total_seconds() / 86400.0

    def promotion_debt(
        self,
        *,
        now: Optional[datetime] = None,
        now_days: Optional[int] = None,
    ) -> list[dict]:
        """LOGIC_IN_SCRIPT with ttl expired and invalid plan (Phase-4 debt gate).

        Excludes ``ACCEPTED_COLOCATED``, terminal lifecycles, and ``ttl_days is null``
        (grandfather/default: no debt until a curator sets TTL).

        Age resolution (first match wins):
        1. ``now_days`` — test injection (days since created, integer)
        2. calendar: ``now`` (default UTC now) vs parsed ``created``
        """
        if now is None and now_days is None:
            now = datetime.now(timezone.utc)

        debt: list[dict] = []
        for r in self.records:
            if r.get("lifecycle") in TERMINAL_LIFECYCLES:
                continue
            if r.get("implementation_status") == "ACCEPTED_COLOCATED":
                continue
            if r.get("implementation_status") != "LOGIC_IN_SCRIPT":
                continue
            if not r.get("logic_in_script", True):
                continue
            ttl = r.get("ttl_days")
            if ttl is None:
                continue
            ttl_i = int(ttl)

            if now_days is not None:
                age = float(now_days)
            else:
                age_opt = self.age_days(r, now=now)
                if age_opt is None:
                    continue
                age = age_opt

            if age <= ttl_i:
                continue
            if self.is_valid_promotion_plan(r):
                continue
            debt.append(r)
        return sorted(debt, key=lambda r: r.get("id", ""))

    def missing_impl(self) -> list[dict]:
        """logic_in_script with no valid promotion plan (visibility backlog; not a CI fail)."""
        out = [
            r for r in self.records
            if r.get("logic_in_script")
            and r.get("implementation_status") not in (
                "CLOSED_EPHEMERAL", "N_A", "ACCEPTED_COLOCATED",
            )
            and r.get("lifecycle") not in TERMINAL_LIFECYCLES
            and not self.is_valid_promotion_plan(r)
        ]
        return sorted(out, key=lambda r: r.get("id", ""))

    def missing_impl_queue_lines(self) -> list[dict]:
        """Machine lines for Orient / optional multi_llm build_queue helpers (no auto-mutate)."""
        lines: list[dict] = []
        for r in self.missing_impl():
            lines.append({
                "kind": "SITS_MISSING_IMPL",
                "script_id": r.get("id"),
                "path": r.get("path"),
                "category": r.get("category"),
                "implementation_status": r.get("implementation_status"),
                "purpose": r.get("purpose"),
                "task_refs": r.get("task_refs") or [],
                "ttl_days": r.get("ttl_days"),
                "authority": AUTHORITY,
                "suggested_action": (
                    "set dest_modules + notes (promotion plan) OR notes=wontfix:reason=… "
                    "OR reclassify CLOSED_EPHEMERAL; extract only via user-gated PR-6"
                ),
            })
        return lines

    def debt_report_markdown(
        self,
        *,
        now: Optional[datetime] = None,
    ) -> str:
        """Human report: TTL debt (CI-binding) + missing-impl counts (visibility)."""
        if now is None:
            now = datetime.now(timezone.utc)
        debt = self.promotion_debt(now=now)
        missing = self.missing_impl()
        with_ttl = [
            r for r in self.records
            if r.get("ttl_days") is not None
            and r.get("lifecycle") not in TERMINAL_LIFECYCLES
        ]
        lines = [
            "# Script promotion debt (SITS Phase 4)",
            "",
            f"Generated: {now.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            f"Authority: **inventory only** — no auto-extract; no promote power.",
            "",
            "## Summary",
            "",
            f"| Metric | Count |",
            f"|---|---|",
            f"| Total registry rows | {len(self.records)} |",
            f"| Rows with `ttl_days` set | {len(with_ttl)} |",
            f"| **TTL debt (CI-binding)** | **{len(debt)}** |",
            f"| Missing-impl (visibility) | {len(missing)} |",
            "",
            "### TTL debt (expired `ttl_days`, no valid promotion plan)",
            "",
            "CI fails when this list is non-empty (`tests/test_script_registry.py`).",
            "",
        ]
        if not debt:
            lines.append("_None — floor green._")
            lines.append("")
        else:
            lines.append("| ID | Path | ttl_days | Purpose |")
            lines.append("|---|---|---|---|")
            for r in debt:
                purpose = (r.get("purpose") or "").replace("|", "\\|")[:60]
                lines.append(
                    f"| `{r.get('id')}` | `{r.get('path')}` | {r.get('ttl_days')} | {purpose} |"
                )
            lines.append("")

        lines.extend([
            "### Missing-impl (top 30 by id — visibility only)",
            "",
            "Not a CI fail. Export: `query_scripts.py --missing-impl --jsonl`.",
            "",
        ])
        if not missing:
            lines.append("_None._")
            lines.append("")
        else:
            lines.append("| ID | Category | Path |")
            lines.append("|---|---|---|")
            for r in missing[:30]:
                lines.append(
                    f"| `{r.get('id')}` | {r.get('category')} | `{r.get('path')}` |"
                )
            if len(missing) > 30:
                lines.append(f"| … | … | *{len(missing) - 30} more* |")
            lines.append("")

        lines.extend([
            "### Curated TTL rows (tracked)",
            "",
            "| ID | Path | ttl_days | Plan OK |",
            "|---|---|---|---|",
        ])
        for r in sorted(with_ttl, key=lambda x: x.get("id", "")):
            plan = "yes" if self.is_valid_promotion_plan(r) else "NO"
            lines.append(
                f"| `{r.get('id')}` | `{r.get('path')}` | {r.get('ttl_days')} | {plan} |"
            )
        lines.append("")
        lines.append(
            "*Generator: `ScriptRegistry.debt_report_markdown` · "
            "schema §9.8 · design SITS PR-5*"
        )
        lines.append("")
        return "\n".join(lines)

    # ---------------------------------------------------------------- validation

    def validate_paths(self, repo_root: "Path | str") -> list[ValidationError]:
        """Non-terminal lifecycle ⇒ path must exist under repo_root; terminal ⇒ optional."""
        root = Path(repo_root)
        errors: list[ValidationError] = []
        for r in self.records:
            sid = r.get("id", "?")
            life = r.get("lifecycle")
            rel = normalize_posix(r.get("path", ""))
            if not rel:
                errors.append(ValidationError(sid, "path", "empty path"))
                continue
            exists = (root / rel).is_file()
            if life in TERMINAL_LIFECYCLES:
                continue
            if not exists:
                errors.append(
                    ValidationError(sid, "path", f"path not found for non-terminal lifecycle: {rel}")
                )
        return errors

    def validate_control_plane_parity(
        self,
        command_ids: set[str],
        allowlist: set[str],
    ) -> list[ValidationError]:
        """ACTIVE CANONICAL_CLI ⇒ control_plane_id in command_ids or path in allowlist."""
        errors: list[ValidationError] = []
        allow_norm = {normalize_posix(p) for p in allowlist}
        for r in self.records:
            if r.get("category") != "CANONICAL_CLI":
                continue
            if r.get("lifecycle") != "ACTIVE":
                continue
            sid = r.get("id", "?")
            cp = r.get("control_plane_id")
            path = normalize_posix(r.get("path", ""))
            if cp and cp in command_ids:
                continue
            if path in allow_norm:
                continue
            errors.append(
                ValidationError(
                    sid,
                    "control_plane",
                    f"ACTIVE CANONICAL_CLI lacks control_plane_id in catalog and path not allowlisted: {path}",
                )
            )
        return errors

    def coverage_against_disk(self, discovered_paths: set[str]) -> dict:
        """Compare discovered disk paths vs non-terminal registry paths."""
        disc = {normalize_posix(p) for p in discovered_paths}
        reg_non_terminal: set[str] = set()
        for r in self.records:
            if r.get("lifecycle") in TERMINAL_LIFECYCLES:
                continue
            reg_non_terminal.add(normalize_posix(r.get("path", "")))
        unregistered = sorted(disc - reg_non_terminal)
        missing_on_disk = sorted(reg_non_terminal - disc)
        return {
            "discovered": len(disc),
            "registered_non_terminal": len(reg_non_terminal),
            "unregistered": unregistered,
            "missing_on_disk": missing_on_disk,
            "ok": not unregistered,
        }

    def grandfather_ratchet(
        self,
        discovered_paths: set[str],
        grandfather_paths: set[str],
        *,
        stub_purpose: str = "GRANDFATHER_UNCLASSIFIED",
    ) -> dict:
        """Phase-2 ENFORCE_NEW: paths outside the grandfather pin must be classified.

        For each path in ``discovered - grandfather``:
        - must appear on a non-terminal registry row, and
        - ``purpose`` must not be the auto-stub sentinel (overlay required).

        Grandfathered paths may keep ``purpose=GRANDFATHER_UNCLASSIFIED``.
        """
        disc = {normalize_posix(p) for p in discovered_paths}
        gf = {normalize_posix(p) for p in grandfather_paths}
        new_paths = sorted(disc - gf)

        by_path: dict[str, dict] = {}
        for r in self.records:
            if r.get("lifecycle") in TERMINAL_LIFECYCLES:
                continue
            by_path[normalize_posix(r.get("path", ""))] = r

        unregistered: list[str] = []
        unclassified: list[str] = []
        for path in new_paths:
            rec = by_path.get(path)
            if rec is None:
                unregistered.append(path)
                continue
            purpose = (rec.get("purpose") or "").strip()
            if purpose == stub_purpose or purpose == "":
                unclassified.append(path)

        return {
            "new_path_count": len(new_paths),
            "new_paths": new_paths,
            "unregistered": unregistered,
            "unclassified": unclassified,
            "ok": not unregistered and not unclassified,
        }

    def validate_colocated(
        self,
        allowlist: set[str],
    ) -> list[ValidationError]:
        """R6: ACCEPTED_COLOCATED paths must appear on the colocated allowlist."""
        allow_norm = {normalize_posix(p) for p in allowlist}
        errors: list[ValidationError] = []
        for r in self.records:
            if r.get("implementation_status") != "ACCEPTED_COLOCATED":
                continue
            path = normalize_posix(r.get("path", ""))
            if path not in allow_norm:
                errors.append(
                    ValidationError(
                        r.get("id", "?"),
                        "colocated",
                        f"ACCEPTED_COLOCATED path not on allowlist: {path}",
                    )
                )
        return errors

    def validate_all(
        self,
        repo_root: "Path | str | None" = None,
        *,
        colocated_allowlist: Optional[set[str]] = None,
        command_ids: Optional[set[str]] = None,
        canonical_allowlist: Optional[set[str]] = None,
        check_control_plane: bool = False,
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []
        if repo_root is not None:
            errors.extend(self.validate_paths(repo_root))
        if colocated_allowlist is not None:
            errors.extend(self.validate_colocated(colocated_allowlist))
        if check_control_plane:
            errors.extend(
                self.validate_control_plane_parity(
                    command_ids or set(),
                    canonical_allowlist or set(),
                )
            )
        return errors

    # ---------------------------------------------------------------- mutation

    def append(self, record: dict) -> None:
        self.validate_record(record)
        if self.path is None:
            raise ValueError("ScriptRegistry.append: no path set (call load() or pass path=)")
        append_jsonl(self.path, record)
        self._records[record["id"]] = record

    # ---------------------------------------------------------------- schema / io

    @staticmethod
    def validate_record(
        record: dict,
        *,
        colocated_allowlist: Optional[set[str]] = None,
    ) -> None:
        """Raise ValueError on schema / enum / authority / rule violation.

        Unknown keys are REJECTED so authority-granting fields cannot enter the schema.
        """
        missing = [f for f in _REQUIRED_FIELDS if f not in record]
        if missing:
            raise ValueError(f"record {record.get('id')!r} missing fields: {missing}")
        unknown = [k for k in record if k not in _REQUIRED_FIELDS]
        if unknown:
            raise ValueError(
                f"{record.get('id')!r}: unknown keys {unknown} — the script schema is closed "
                "(§6.5: inventory authority only; no promote/threshold fields)"
            )

        sid = record["id"]
        if not isinstance(sid, str) or not _ID_RE.match(sid):
            raise ValueError(f"id must match SCR-NNN, got {sid!r}")

        path = record["path"]
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"{sid}: path must be a non-empty string")
        if "\\" in path:
            raise ValueError(f"{sid}: path must be POSIX (got backslash): {path!r}")

        cat = record["category"]
        if cat not in CATEGORY_ENUM:
            raise ValueError(f"{sid}: category {cat!r} not in {sorted(CATEGORY_ENUM)}")

        life = record["lifecycle"]
        if life not in LIFECYCLE_ENUM:
            raise ValueError(f"{sid}: lifecycle {life!r} not in {sorted(LIFECYCLE_ENUM)}")

        impl = record["implementation_status"]
        if impl not in IMPL_STATUS_ENUM:
            raise ValueError(
                f"{sid}: implementation_status {impl!r} not in {sorted(IMPL_STATUS_ENUM)}"
            )

        owner = record["owner_kind"]
        if owner not in OWNER_KIND_ENUM:
            raise ValueError(f"{sid}: owner_kind {owner!r} not in {sorted(OWNER_KIND_ENUM)}")

        if record["authority"] != AUTHORITY:
            raise ValueError(f"{sid}: authority must be the pinned literal {AUTHORITY!r} (§6.5)")

        for list_field in _LIST_FIELDS:
            if not isinstance(record[list_field], list):
                raise ValueError(f"{sid}: {list_field} must be a list")

        if not isinstance(record["has_main"], bool):
            raise ValueError(f"{sid}: has_main must be bool")
        if not isinstance(record["logic_in_script"], bool):
            raise ValueError(f"{sid}: logic_in_script must be bool")

        if record["ttl_days"] is not None and not isinstance(record["ttl_days"], int):
            raise ValueError(f"{sid}: ttl_days must be int or null")

        # agent_tool_id reserved for v1.1 — reject non-null in v1
        if record["agent_tool_id"] is not None:
            raise ValueError(
                f"{sid}: agent_tool_id must be null in v1 (reserved for v1.1 agent-tool parity)"
            )

        purpose = record["purpose"]
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError(f"{sid}: purpose must be a non-empty string")

        # R2: DEAD requires non-empty notes
        notes = record.get("notes")
        if not isinstance(notes, str):
            raise ValueError(f"{sid}: notes must be a string")
        if life == "DEAD" and not notes.strip():
            raise ValueError(f"{sid}: lifecycle=DEAD requires non-empty notes")

        # R3: SUPERSEDED requires superseded_by
        if life == "SUPERSEDED":
            sb = record.get("superseded_by")
            if not sb or not isinstance(sb, str):
                raise ValueError(f"{sid}: lifecycle=SUPERSEDED requires superseded_by SCR-id")
            if not _ID_RE.match(sb):
                raise ValueError(f"{sid}: superseded_by must match SCR-NNN, got {sb!r}")

        # R5: N_A cannot claim logic_in_script
        if impl == "N_A" and record["logic_in_script"] is True:
            raise ValueError(f"{sid}: implementation_status=N_A cannot have logic_in_script=true")

        # R6: ACCEPTED_COLOCATED path on allowlist when provided
        if impl == "ACCEPTED_COLOCATED" and colocated_allowlist is not None:
            p = normalize_posix(path)
            if p not in {normalize_posix(x) for x in colocated_allowlist}:
                raise ValueError(
                    f"{sid}: ACCEPTED_COLOCATED path {p!r} not on colocated allowlist"
                )

        # Soft consistency: climbing status on terminal without notes is allowed but
        # DEAD already forced notes. No extra hard rule for climbing+terminal.

    @staticmethod
    def dump(path: "Path | str", records: list[dict]) -> int:
        """Validate + write all records deterministically (overwrite, sorted by id)."""
        import json

        seen: set[str] = set()
        for rec in records:
            ScriptRegistry.validate_record(rec)
            if rec["id"] in seen:
                raise ValueError(f"duplicate id in seed set: {rec['id']}")
            seen.add(rec["id"])
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(records, key=lambda r: r["id"])
        with p.open("w", encoding="utf-8") as fh:
            for rec in ordered:
                fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return len(ordered)

    @staticmethod
    def new_stub_record(
        *,
        script_id: str,
        path: str,
        has_main: bool,
        category: str = "ORPHAN",
        lifecycle: str = "ACTIVE",
        timestamp: str = "2026-08-02T00:00:00Z",
    ) -> dict:
        """Grandfather defaults (K18): always LOGIC_IN_SCRIPT, never auto N_A."""
        return {
            "id": script_id,
            "path": normalize_posix(path),
            "category": category,
            "lifecycle": lifecycle,
            "implementation_status": "LOGIC_IN_SCRIPT",
            "owner_kind": "UNKNOWN",
            "owner_ref": "",
            "purpose": "GRANDFATHER_UNCLASSIFIED",
            "task_refs": [],
            "dest_modules": [],
            "tests": [],
            "config_keys": [],
            "control_plane_id": None,
            "agent_tool_id": None,
            "has_main": has_main,
            "superseded_by": None,
            "created": timestamp,
            "last_validated": timestamp,
            "ttl_days": None,
            "logic_in_script": True,
            "notes": "",
            "authority": AUTHORITY,
        }
