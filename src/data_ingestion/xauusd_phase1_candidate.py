"""XAUUSD M15 Phase-1 frozen candidate — fail-closed identity verification.

Scope freeze only (FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION).
Not AUTHORITATIVE / not VALIDATED / not ECONOMICALLY_ADMISSIBLE.

Binding source of truth:
  docs/governance/xauusd_m15_phase1_frozen_candidate.json

Any Phase-1 OHLCV validation path for XAUUSD must call
``require_phase1_frozen_candidate`` (or ``verify_phase1_frozen_candidate``)
before treating bytes as the candidate corpus. Drift of path, hash, row count,
or time range is a hard failure.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from data_ingestion.ohlcv_schema import parse_ohlcv_timestamp

_REPO_ROOT = Path(__file__).resolve().parents[2]
BINDING_PATH = (
    _REPO_ROOT / "docs" / "governance" / "xauusd_m15_phase1_frozen_candidate.json"
)

# Hard-coded mirror of the binding (load-bearing constants for static import sites).
# Must match the JSON binding; tests enforce parity.
PHASE1_STATUS = "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
PHASE1_PHYSICAL_PATH = Path("data/mt5/XAUUSD_M15.csv")
PHASE1_SHA256 = "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56"
PHASE1_ROWS = 47275
PHASE1_START = datetime(2024, 5, 22, 1, 0, 0)
PHASE1_END = datetime(2026, 5, 21, 23, 45, 0)


class Phase1CandidateError(RuntimeError):
    """Fail-closed identity / range failure for the XAUUSD Phase-1 candidate."""


@dataclass(frozen=True)
class Phase1CandidateBinding:
    binding_id: str
    status: str
    physical_path: Path
    content_hash_sha256: str
    rows: int
    start: datetime
    end: datetime
    explicitly_not: tuple[str, ...]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_binding(path: Optional[Path] = None) -> Phase1CandidateBinding:
    p = path or BINDING_PATH
    if not p.is_file():
        raise Phase1CandidateError(f"Phase-1 binding missing: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if raw.get("status") != PHASE1_STATUS:
        raise Phase1CandidateError(
            f"binding status {raw.get('status')!r} != {PHASE1_STATUS!r}"
        )
    tr = raw["allowed_time_range"]
    return Phase1CandidateBinding(
        binding_id=str(raw["binding_id"]),
        status=str(raw["status"]),
        physical_path=Path(raw["physical_path"]),
        content_hash_sha256=str(raw["content_hash_sha256"]),
        rows=int(raw["rows"]),
        start=datetime.fromisoformat(tr["start"]),
        end=datetime.fromisoformat(tr["end"]),
        explicitly_not=tuple(raw.get("explicitly_not") or ()),
    )


def verify_phase1_frozen_candidate(
    *,
    repo_root: Optional[Path] = None,
    binding: Optional[Phase1CandidateBinding] = None,
) -> dict:
    """Verify on-disk bytes match the frozen candidate binding.

    Returns a report dict on success. Raises Phase1CandidateError on any mismatch.
    """
    root = repo_root or _REPO_ROOT
    b = binding or load_binding()
    if b.status != PHASE1_STATUS:
        raise Phase1CandidateError(f"illegal status for Phase-1 use: {b.status}")
    required_bans = {"AUTHORITATIVE", "VALIDATED", "ECONOMICALLY_ADMISSIBLE", "APPROVED"}
    missing_bans = required_bans - set(b.explicitly_not)
    if missing_bans:
        raise Phase1CandidateError(
            f"binding must explicitly ban authority labels; missing {sorted(missing_bans)}"
        )
    # constants parity
    if b.content_hash_sha256 != PHASE1_SHA256:
        raise Phase1CandidateError(
            f"binding hash {b.content_hash_sha256[:16]}.. != module constant"
        )
    if b.rows != PHASE1_ROWS or b.start != PHASE1_START or b.end != PHASE1_END:
        raise Phase1CandidateError("binding range/rows disagree with module constants")
    if b.physical_path != PHASE1_PHYSICAL_PATH:
        raise Phase1CandidateError(
            f"binding path {b.physical_path} != {PHASE1_PHYSICAL_PATH}"
        )

    path = root / b.physical_path
    if not path.is_file():
        raise Phase1CandidateError(f"candidate file missing: {path}")

    digest = _sha256_file(path)
    if digest != b.content_hash_sha256:
        raise Phase1CandidateError(
            f"content hash drift on {b.physical_path}: "
            f"expected {b.content_hash_sha256[:16]}.. got {digest[:16]}.. "
            "(another file/extension silently entered — fail closed)"
        )

    n = 0
    first: Optional[datetime] = None
    last: Optional[datetime] = None
    after_end = 0
    before_start = 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        header = f.readline()
        if not header:
            raise Phase1CandidateError("empty candidate file")
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            ts = parse_ohlcv_timestamp(line.split(",")[0])
            if first is None:
                first = ts
            last = ts
            if ts > b.end:
                after_end += 1
            if ts < b.start:
                before_start += 1

    if n != b.rows:
        raise Phase1CandidateError(f"row count {n} != bound {b.rows}")
    if first != b.start:
        raise Phase1CandidateError(f"first ts {first} != bound start {b.start}")
    if last != b.end:
        raise Phase1CandidateError(f"last ts {last} != bound end {b.end}")
    if after_end:
        raise Phase1CandidateError(
            f"{after_end} timestamps after policy end {b.end.isoformat()} — fail closed"
        )
    if before_start:
        raise Phase1CandidateError(
            f"{before_start} timestamps before policy start {b.start.isoformat()}"
        )

    return {
        "ok": True,
        "status": b.status,
        "physical_path": str(b.physical_path).replace("\\", "/"),
        "content_hash_sha256": digest,
        "rows": n,
        "first_timestamp": first.isoformat(sep="T") if first else None,
        "last_timestamp": last.isoformat(sep="T") if last else None,
        "authority_labels_forbidden": list(b.explicitly_not),
    }


def require_phase1_frozen_candidate(
    *,
    repo_root: Optional[Path] = None,
) -> Phase1CandidateBinding:
    """Load + verify; return binding. Fail closed on any drift."""
    b = load_binding()
    verify_phase1_frozen_candidate(repo_root=repo_root, binding=b)
    return b


def is_phase1_candidate_path(path: Path | str) -> bool:
    """True iff path normalizes to the frozen candidate relative path."""
    p = Path(path)
    try:
        rel = p.as_posix().replace("\\", "/")
    except Exception:
        rel = str(path).replace("\\", "/")
    target = PHASE1_PHYSICAL_PATH.as_posix()
    return rel == target or rel.endswith("/" + target)


def is_xauusd_m15_request(filepath: str | Path, instrument: str = "") -> bool:
    """True when the load request is for XAUUSD M15 OHLCV (any physical path)."""
    name = Path(filepath).name.upper()
    inst = (instrument or "").upper().replace("/", "").replace("_", "")
    if name.startswith("XAUUSD_M15") or name == "XAUUSD_M15.CSV":
        return True
    # instrument XAUUSD + M15 in filename (or GOLD broker alias + M15)
    if inst in ("XAUUSD", "XAUUSDM15", "GOLD", "XAUUSD.M15") and "M15" in name:
        return True
    if inst == "XAUUSD" and name.endswith(".CSV"):
        # Reject non-M15 XAUUSD files here only when clearly another TF
        if any(tf in name for tf in ("_M5", "_H1", "_H4", "_M1", "_D1")):
            return False
        if "M15" in name:
            return True
    return False


def resolve_xauusd_m15_csv(
    filepath: str | Path = "",
    *,
    instrument: str = "",
    repo_root: Optional[Path] = None,
    verify: bool = True,
) -> Path:
    """Return the only allowed XAUUSD M15 path after fail-closed verification.

    If *filepath* / *instrument* is not an XAUUSD M15 request, raises
    ``Phase1CandidateError`` when called for forced resolve; use
    ``guard_xauusd_csv_path`` for pass-through of non-XAUUSD loads.

    Does **not** grant AUTHORITATIVE / VALIDATED / APPROVED / ECONOMICALLY_ADMISSIBLE.
    """
    root = repo_root or _REPO_ROOT
    if filepath and not is_xauusd_m15_request(filepath, instrument):
        # allow explicit call with empty path + instrument=XAUUSD
        if not (instrument or "").upper().startswith("XAU"):
            raise Phase1CandidateError(
                f"resolve_xauusd_m15_csv called for non-XAUUSD-M15 request: "
                f"path={filepath!r} instrument={instrument!r}"
            )
    if verify:
        require_phase1_frozen_candidate(repo_root=root)
    return (root / PHASE1_PHYSICAL_PATH).resolve()


def guard_xauusd_csv_path(
    filepath: str | Path,
    instrument: str = "",
    *,
    repo_root: Optional[Path] = None,
) -> str:
    """For XAUUSD M15 loads: rewrite to frozen candidate + verify hash/range.

    For all other loads: return *filepath* unchanged.
    Fail closed if XAUUSD M15 is requested but the frozen candidate drifts.
    """
    if not is_xauusd_m15_request(filepath, instrument):
        return str(filepath)
    resolved = resolve_xauusd_m15_csv(
        filepath, instrument=instrument or "XAUUSD", repo_root=repo_root, verify=True
    )
    return str(resolved)


def authority_status_note() -> str:
    """Machine/human note: frozen candidate is not production-authoritative."""
    return (
        f"status={PHASE1_STATUS}; "
        f"NOT AUTHORITATIVE / NOT VALIDATED / NOT APPROVED / NOT ECONOMICALLY_ADMISSIBLE; "
        f"path={PHASE1_PHYSICAL_PATH.as_posix()}; "
        f"sha256={PHASE1_SHA256}; "
        f"range={PHASE1_START.isoformat()}..{PHASE1_END.isoformat()}"
    )
