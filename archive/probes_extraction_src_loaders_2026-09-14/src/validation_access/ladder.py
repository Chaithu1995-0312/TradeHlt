"""VA-XAUUSD-M15 sequential validation ladder: S → I → F → E.

Design freeze: docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md

Authority: access/packaging only — no runtime, fusion, sizing, or promotion.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

DESIGN_ID = "VA-XAUUSD-M15"
INSTRUMENT = "XAUUSD"
TIMEFRAME = "M15"
RUNG_ORDER = ("S", "I", "F", "E")

STORY_ONTOLOGY_REL = "configs/research/market_story_ontology.yaml"
STORY_INDEX_REL = "data/synthetic/stories/INDEX.json"
IMPL_FREEZE_REL = "results/implementation_validation/IMPLEMENTATION_VALIDATION_V1.json"
IMPL_LATEST_REL = "results/implementation_validation/xauusd_model_validation_LATEST.json"
MC_PROFILES_REL = "configs/research/measurement_contracts"
MC_CHARTER_REL = "docs/governance/MEASUREMENT_CONTRACT.md"
OHLC_REL = "data/mt5/XAUUSD_M15.csv"


@dataclass
class RungResult:
    code: str
    name: str
    status: str  # PASS | FAIL | BLOCKED_BY_* | OPEN | PARTIAL | ERROR | SKIP
    summary: str
    details: dict[str, Any] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)


@dataclass
class LadderResult:
    design_id: str
    instrument: str
    timeframe: str
    run_id: str
    started_utc: str
    finished_utc: str
    active_version: Optional[str]
    rungs: dict[str, RungResult]
    overall_status: str
    authority_note: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _active_version(root: Path) -> Optional[str]:
    p = root / "configs" / "production" / "ACTIVE_VERSION"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _blocked(code: str, name: str, by: str, reason: str) -> RungResult:
    return RungResult(
        code=code,
        name=name,
        status=f"BLOCKED_BY_{by}",
        summary=reason,
        blockers=[by],
    )


# ── S: Story six-layer ───────────────────────────────────────────────────────

def _run_s(root: Path, *, live_story: bool) -> RungResult:
    name = "story_six_layer_semantic"
    ontology = root / STORY_ONTOLOGY_REL
    index_path = root / STORY_INDEX_REL
    evidence = [STORY_ONTOLOGY_REL]

    if not ontology.is_file():
        return RungResult(
            code="S", name=name, status="FAIL",
            summary=f"missing story ontology: {STORY_ONTOLOGY_REL}",
            blockers=["missing_ontology"],
        )

    if live_story:
        try:
            from research.synthetic.ontology import StoryOntology
            from research.synthetic.story_builder import build_story
            from research.synthetic.story_registry import all_stories
        except Exception as e:
            return RungResult(
                code="S", name=name, status="ERROR",
                summary=f"story imports failed: {type(e).__name__}: {e}",
                blockers=["import_error"],
                details={"error": str(e)},
            )
        onto = StoryOntology()
        stories: list[dict[str, Any]] = []
        all_pass = True
        layer_fails: dict[str, int] = {}
        for spec in all_stories():
            r = build_story(spec, onto)
            binding = r.get("ontology_binding") or {}
            layers = (binding.get("layers") or {})
            story_ok = bool(r.get("all_critical_pass") and binding.get("all_pass"))
            all_pass = all_pass and story_ok
            for lk, lv in layers.items():
                if isinstance(lv, dict) and not lv.get("pass", True):
                    layer_fails[lk] = layer_fails.get(lk, 0) + 1
            stories.append({
                "id": r.get("id"),
                "family": r.get("family"),
                "all_critical_pass": bool(r.get("all_critical_pass")),
                "ontology_binding_all_pass": bool(binding.get("all_pass")),
                "outcome": (r.get("outcome") or {}).get("outcome"),
            })
        evidence.append("live:build_story")
        status = "PASS" if all_pass and stories else "FAIL"
        return RungResult(
            code="S", name=name, status=status,
            summary=(
                f"live story library n={len(stories)} all_pass={all_pass}"
            ),
            details={
                "mode": "live",
                "n_stories": len(stories),
                "all_pass": all_pass,
                "stories": stories,
                "layer_fail_counts": layer_fails,
                "ontology_path": STORY_ONTOLOGY_REL,
            },
            blockers=[] if status == "PASS" else ["story_binding_or_critical_fail"],
            evidence_paths=evidence,
        )

    # Cached INDEX path (default — fast)
    if not index_path.is_file():
        return RungResult(
            code="S", name=name, status="FAIL",
            summary=(
                f"missing {STORY_INDEX_REL}; run story_library_build.py "
                "or pass --live-story"
            ),
            blockers=["missing_story_index"],
            evidence_paths=evidence,
        )
    try:
        idx = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as e:
        return RungResult(
            code="S", name=name, status="ERROR",
            summary=f"INDEX.json unreadable: {e}",
            blockers=["index_read_error"],
            evidence_paths=evidence + [STORY_INDEX_REL],
        )
    stories = list(idx.get("stories") or [])
    all_pass = bool(idx.get("all_pass"))
    # Re-derive from rows if flag missing
    if stories and "all_pass" not in idx:
        all_pass = all(
            bool(s.get("all_critical_pass") and s.get("ontology_binding_all_pass"))
            for s in stories
        )
    evidence.append(STORY_INDEX_REL)
    status = "PASS" if all_pass and stories else "FAIL"
    return RungResult(
        code="S", name=name, status=status,
        summary=f"cached INDEX n={len(stories)} all_pass={all_pass}",
        details={
            "mode": "cached_index",
            "n_stories": len(stories),
            "all_pass": all_pass,
            "stories": stories,
            "ontology_path": STORY_ONTOLOGY_REL,
            "index_sha256": _sha256_file(index_path),
        },
        blockers=[] if status == "PASS" else ["story_index_not_all_pass"],
        evidence_paths=evidence,
    )


# ── I: Implementation harness ────────────────────────────────────────────────

def _rel_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _parse_impl_artifact(data: dict[str, Any], path: Path, root: Path) -> RungResult:
    name = "implementation_model_harness"
    meta = data.get("meta") or {}
    acceptance = meta.get("acceptance_checks") or {}
    fail_open = acceptance.get("fail_open_count")
    if fail_open is None:
        fms = acceptance.get("failure_mode_summary") or data.get("failure_mode_summary") or {}
        fail_open = sum(1 for v in fms.values() if v == "FAIL_OPEN")
        if not fms:
            matrix = data.get("execution_matrix") or []
            fail_open = sum(
                1 for row in matrix
                if isinstance(row, dict) and row.get("failure_mode") == "FAIL_OPEN"
            )
    fail_open = int(fail_open or 0)
    fms = (
        acceptance.get("failure_mode_summary")
        or data.get("failure_mode_summary")
        or {}
    )
    status = "PASS" if fail_open == 0 else "FAIL"
    rel_s = _rel_to_root(path, root)
    corpus_pin = acceptance.get("corpus_pin_match")
    if corpus_pin is None:
        corpus_pin = (data.get("corpus") or {}).get("pin_match")
    return RungResult(
        code="I", name=name, status=status,
        summary=f"fail_open_count={fail_open}; modes={fms}",
        details={
            "fail_open_count": fail_open,
            "failure_mode_summary": fms,
            "acceptance": meta.get("acceptance"),
            "active_version": meta.get("active_version"),
            "corpus_pin_match": corpus_pin,
            "milestone": meta.get("milestone"),
            "artifact_sha256": _sha256_file(path),
            "source": rel_s,
        },
        blockers=[] if status == "PASS" else ["fail_open_detected"],
        evidence_paths=[rel_s],
    )


def _run_i(root: Path, *, live_impl: bool) -> RungResult:
    name = "implementation_model_harness"
    if live_impl:
        try:
            # Import harness module by path to avoid package pollution
            import importlib.util
            mod_path = root / "scripts" / "analysis" / "implementation_model_validation_xauusd.py"
            spec = importlib.util.spec_from_file_location(
                "implementation_model_validation_xauusd", mod_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"cannot load {mod_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rc = int(mod.main())
            latest = root / IMPL_LATEST_REL
            if latest.is_file():
                data = json.loads(latest.read_text(encoding="utf-8"))
                r = _parse_impl_artifact(data, latest, root)
                r.details["mode"] = "live_harness"
                r.details["harness_exit"] = rc
                return r
            return RungResult(
                code="I", name=name, status="ERROR",
                summary=f"live harness exit={rc} but LATEST artifact missing",
                blockers=["missing_latest_after_live"],
                details={"mode": "live_harness", "harness_exit": rc},
            )
        except Exception as e:
            return RungResult(
                code="I", name=name, status="ERROR",
                summary=f"live impl harness failed: {type(e).__name__}: {e}",
                blockers=["live_impl_error"],
                details={"error": str(e), "mode": "live_harness"},
            )

    for rel in (IMPL_FREEZE_REL, IMPL_LATEST_REL):
        path = root / rel
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                return RungResult(
                    code="I", name=name, status="ERROR",
                    summary=f"impl artifact unreadable: {e}",
                    blockers=["impl_read_error"],
                    evidence_paths=[rel],
                )
            r = _parse_impl_artifact(data, path, root)
            r.details["mode"] = "freeze_or_latest"
            return r

    return RungResult(
        code="I", name=name, status="FAIL",
        summary="no implementation validation artifact found; run harness or --live-impl",
        blockers=["missing_impl_artifact"],
    )


# ── F: Feature-cert / ontology surface ───────────────────────────────────────

def _run_f(root: Path) -> RungResult:
    name = "feature_cert_ontology_surface"
    try:
        # feature_surface_query is a script module — import via governance dir on sys.path
        gov_dir = str(root / "scripts" / "governance")
        if gov_dir not in sys.path:
            sys.path.insert(0, gov_dir)
        # Drop stale broken module if a prior importlib load left a shell
        if "feature_surface_query" in sys.modules:
            mod = sys.modules["feature_surface_query"]
            if not hasattr(mod, "FeatureSurfaceIndex"):
                del sys.modules["feature_surface_query"]
        import feature_surface_query as fsq  # type: ignore

        idx = fsq.FeatureSurfaceIndex.load(root)
        summary = idx.summary()
    except Exception as e:
        return RungResult(
            code="F", name=name, status="ERROR",
            summary=f"feature surface query failed: {type(e).__name__}: {e}",
            blockers=["feature_surface_error"],
            details={"error": str(e)},
        )

    meta = summary.get("meta") or {}
    closure = summary.get("closure_histogram") or {}
    n_vector = int(summary.get("n_vector") or 0)
    closed = int(closure.get("CLOSED") or 0)
    none_n = int(closure.get("None") or closure.get("none") or 0)
    # also count non-closed
    non_closed = sum(int(v) for k, v in closure.items() if str(k).upper() != "CLOSED")
    surface_status = meta.get("surface_status") or meta.get("closure_verdict")
    if n_vector > 0 and closed == n_vector and non_closed == 0:
        status = "PASS"
        summary_s = f"surface CLOSED {closed}/{n_vector}"
    elif closed > 0 and non_closed > 0:
        status = "PARTIAL"
        summary_s = f"surface PARTIAL closed={closed} other={non_closed} vector={n_vector}"
    else:
        status = "FAIL"
        summary_s = f"surface not closed: {closure} vector={n_vector} status={surface_status}"

    return RungResult(
        code="F", name=name, status=status,
        summary=summary_s,
        details={
            "n_vector": n_vector,
            "closure_histogram": closure,
            "pit_histogram": summary.get("pit_histogram"),
            "surface_status": surface_status,
            "closure_verdict": meta.get("closure_verdict"),
            "active_version": meta.get("active_version"),
            "stale_artifacts": meta.get("stale_artifacts"),
            "artifact_warnings": meta.get("artifact_warnings"),
        },
        blockers=[] if status == "PASS" else ["feature_surface_not_fully_closed"],
        evidence_paths=["scripts/governance/feature_surface_query.py --summary"],
    )


# ── E: Economic / measurement contract ───────────────────────────────────────

def _run_e(root: Path) -> RungResult:
    name = "economic_measurement_contract"
    profiles_dir = root / MC_PROFILES_REL
    charter = root / MC_CHARTER_REL
    profiles: list[dict[str, Any]] = []
    if profiles_dir.is_dir():
        for p in sorted(profiles_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                profiles.append({"path": str(p.name), "error": "unreadable"})
                continue
            profiles.append({
                "path": p.name,
                "profile_id": data.get("profile_id"),
                "lifecycle": data.get("lifecycle"),
                "version": data.get("version"),
                "asset_class": (data.get("profile") or {}).get("asset_class"),
            })

    # Sealed MC-* instances: look under docs/governance and configs for MC-*.json
    sealed: list[str] = []
    draft_mc: list[str] = []
    for base in (root / "docs" / "governance", root / "configs" / "research"):
        if not base.is_dir():
            continue
        for p in base.rglob("MC-*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            life = str(data.get("lifecycle") or data.get("trust_status") or "").upper()
            rel = str(p.relative_to(root)).replace("\\", "/")
            if "SEAL" in life or life == "SEALED":
                sealed.append(rel)
            else:
                draft_mc.append(rel)

    n_sealed = len(sealed)
    # Status is OPEN until any sealed MC exists (honest economic access)
    if n_sealed > 0:
        status = "PASS"
        summary_s = f"sealed_MC_count={n_sealed}"
    else:
        status = "OPEN"
        summary_s = (
            f"MEASUREMENT_LAYER OPEN; sealed_MC_count=0; "
            f"profiles={len(profiles)} (DRAFT defaults only)"
        )

    metals = next(
        (p for p in profiles if p.get("profile_id") == "MP-METALS-MT5"
         or "metals" in str(p.get("path", "")).lower()),
        None,
    )
    return RungResult(
        code="E", name=name, status=status,
        summary=summary_s,
        details={
            "sealed_mc_count": n_sealed,
            "sealed_paths": sealed,
            "draft_mc_paths": draft_mc[:20],
            "profiles": profiles,
            "metals_profile": metals,
            "charter_present": charter.is_file(),
            "charter": MC_CHARTER_REL,
            "note": (
                "Profiles are NOT sealed contracts. OPEN means no economic claim "
                "is admissible under Measurement Contract yet."
            ),
        },
        blockers=[] if status == "PASS" else ["no_sealed_measurement_contract"],
        evidence_paths=[MC_CHARTER_REL, MC_PROFILES_REL],
    )


# ── Orchestrator ─────────────────────────────────────────────────────────────

def _overall_status(rungs: dict[str, RungResult]) -> str:
    """Overall access status. E=OPEN and F=PARTIAL are terminal-but-honest, not hard fail."""
    for code in RUNG_ORDER:
        st = rungs[code].status
        if st.startswith("BLOCKED"):
            return st
        if st in ("FAIL", "ERROR"):
            # F FAIL still allowed E to run; report F_FAIL if E already present
            if code == "F" and "E" in rungs:
                if rungs["E"].status == "OPEN":
                    return "LADDER_COMPLETE_F_FAIL_E_OPEN"
                return f"F_{st}"
            return f"{code}_{st}"
    f_st = rungs["F"].status
    e_st = rungs["E"].status
    if e_st == "OPEN" and f_st == "PARTIAL":
        return "LADDER_COMPLETE_F_PARTIAL_E_OPEN"
    if e_st == "OPEN":
        return "LADDER_COMPLETE_E_OPEN"
    if f_st == "PARTIAL":
        return "LADDER_COMPLETE_F_PARTIAL"
    if e_st == "PASS" and f_st == "PASS":
        return "LADDER_COMPLETE_ALL_PASS"
    return "LADDER_COMPLETE"


def run_ladder(
    root: Path | None = None,
    *,
    live_story: bool = False,
    live_impl: bool = False,
    run_id: str | None = None,
    s_fn: Optional[Callable[..., RungResult]] = None,
    i_fn: Optional[Callable[..., RungResult]] = None,
    f_fn: Optional[Callable[..., RungResult]] = None,
    e_fn: Optional[Callable[..., RungResult]] = None,
) -> LadderResult:
    """Run S→I→F→E with gating. Optional *_fn hooks for tests."""
    root = Path(root) if root is not None else _ROOT
    started = _utc_now()
    rid = run_id or _run_id()
    av = _active_version(root)
    rungs: dict[str, RungResult] = {}

    s_runner = s_fn if s_fn is not None else _run_s
    i_runner = i_fn if i_fn is not None else _run_i
    f_runner = f_fn if f_fn is not None else _run_f
    e_runner = e_fn if e_fn is not None else _run_e

    rungs["S"] = s_runner(root, live_story=live_story)

    if rungs["S"].status != "PASS":
        rungs["I"] = _blocked("I", "implementation_model_harness", "S", "blocked: S not PASS")
        rungs["F"] = _blocked("F", "feature_cert_ontology_surface", "S", "blocked: S not PASS")
        rungs["E"] = _blocked("E", "economic_measurement_contract", "S", "blocked: S not PASS")
    else:
        rungs["I"] = i_runner(root, live_impl=live_impl)
        if rungs["I"].status != "PASS":
            rungs["F"] = _blocked(
                "F", "feature_cert_ontology_surface", "I", "blocked: I not PASS"
            )
            rungs["E"] = _blocked(
                "E", "economic_measurement_contract", "I", "blocked: I not PASS"
            )
        else:
            rungs["F"] = f_runner(root)
            # E always after F (status-only even if F PARTIAL/FAIL)
            rungs["E"] = e_runner(root)

    finished = _utc_now()
    overall = _overall_status(rungs)

    return LadderResult(
        design_id=DESIGN_ID,
        instrument=INSTRUMENT,
        timeframe=TIMEFRAME,
        run_id=rid,
        started_utc=started,
        finished_utc=finished,
        active_version=av,
        rungs=rungs,
        overall_status=overall,
        authority_note=(
            "Access/packaging only. No runtime, fusion, sizing, or promotion authority. "
            "Semantic story layer remains descriptive (§6.5)."
        ),
        options={
            "live_story": live_story,
            "live_impl": live_impl,
            "ohlc": OHLC_REL,
            "ohlc_present": (root / OHLC_REL).is_file(),
            "ohlc_sha256": _sha256_file(root / OHLC_REL),
        },
    )
