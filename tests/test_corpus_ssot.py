"""CH-corpus-ssot (2026-10-08): enforcement of the corpus Single Source of Truth.

Architectural rule under test: NO COMPETING CORPUS AUTHORITY. One SSOT
(`data_ingestion.corpus_store.load`) owns every identified corpus — registered datasets
(dataset_id) and unregistered files (content address `sha256:<hex>`). An execution selects ONE
corpus; every consumer gets the same object, and artifacts take identity from it.

NOT under test (deliberately): "only one canonical corpus file may exist". Several identified
corpora coexist; each resolves to its own identity, never silently to another.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import sys
import traceback
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from data_ingestion import corpus_store as cs  # noqa: E402

CANON = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
WINDOW = ROOT / "data" / "mt5" / "XAUUSD_W2026-07-06-to-2026-08-07.csv"   # registered, small
ALIAS = ROOT / "data" / "XAUUSD_M15.csv"                                  # declared alias of CANON
NEWER_NAME = "XAUUSD_M15_2026-04-20_to_2026-10-06.csv"   # unregistered, different

CH_CLOCK = ("CH-corpus-clock-contract-v1: a real unreviewed fetch has no declared clock and is "
            "refused; the 'own identity' behaviour is exercised on a CONSTRUCTED file instead")


def _newer(tmp_path):
    p = tmp_path / NEWER_NAME
    p.write_text("\n".join(["timestamp,open,high,low,close,volume",
                            "2026-04-20 01:00:00,1.0,2.0,0.5,1.5,10",
                            "2026-04-20 01:15:00,1.5,2.5,1.0,2.0,11"]) + "\n", encoding="utf-8")
    return p


needs = pytest.mark.skipif(not (CANON.exists() and WINDOW.exists()), reason="XAUUSD corpora absent")


# ── runtime open-tracer: which code opens data/mt5/*.csv ───────────────────────────────────────
_AUTHORITY_DIR = (ROOT / "src" / "data_ingestion").resolve()
_TRACE = {"on": False, "opens": []}


def _hook(event, args):
    if not _TRACE["on"] or event != "open" or not args or not isinstance(args[0], (str, Path)):
        return
    p = str(args[0]).replace("\\", "/")
    if "/data/mt5/" not in p and not p.startswith("data/mt5/"):
        return
    if not p.lower().endswith(".csv"):
        return
    frames = [Path(f.filename).resolve() for f in traceback.extract_stack()[:-1]]
    by_authority = any(_AUTHORITY_DIR in f.parents for f in frames)
    _TRACE["opens"].append((p, by_authority, [str(f) for f in frames[-6:]]))


sys.addaudithook(_hook)


def _traced(fn):
    cs._SSOT_CACHE.clear()
    _TRACE["opens"].clear()
    _TRACE["on"] = True
    try:
        return fn()
    finally:
        _TRACE["on"] = False


def _foreign_opens():
    return [(p, tail) for p, auth, tail in _TRACE["opens"] if not auth]


# ── Test A — one corpus authority: consumers' corpus bytes come only from the SSOT ────────────
CONSUMERS = {
    "mc_kit.load_bars": lambda: __import__("research.mc_kit.bars", fromlist=["x"]).load_bars(
        WINDOW, __import__("research.mother_range.geometry", fromlist=["Bar"]).Bar),
    "probes.load_corpus": lambda: __import__("research.probes.corpus", fromlist=["x"]).load_corpus(WINDOW),
    "visual_crt.load_bars": lambda: __import__("research.visual_crt.driver", fromlist=["x"]).load_bars(WINDOW),
    "sujan_manipulation.load_bars": lambda: __import__(
        "research.sujan_manipulation.driver", fromlist=["x"]).load_bars(WINDOW),
    "secondlow.load_ohlcv": lambda: __import__("research.secondlow_v1.detector", fromlist=["x"]).load_ohlcv(WINDOW),
    "goal_alignment.corpus_span_months": lambda: __import__(
        "research.goal_alignment", fromlist=["x"]).corpus_span_months(str(WINDOW)),
    "select_window.read_timestamps": lambda: __import__(
        "semantics.integration.select_window", fromlist=["x"]).read_timestamps(WINDOW),
    "CandleLoader.stream": lambda: list(__import__("runtime.backtest_v2", fromlist=["x"]).CandleLoader(
        str(WINDOW), "XAUUSD").stream()),
}


@needs
@pytest.mark.parametrize("name", sorted(CONSUMERS))
def test_A_consumer_reads_corpus_only_through_ssot(name):
    out = _traced(CONSUMERS[name])
    assert out is not None and len(out) if not isinstance(out, float) else True
    assert _TRACE["opens"], f"{name}: expected the SSOT to open the corpus at least once"
    foreign = _foreign_opens()
    assert not foreign, f"{name} opened the corpus outside data_ingestion (competing reader): {foreign}"


@needs
def test_A_tracer_catches_a_direct_reader():
    # a raw byte read of the corpus, outside data_ingestion, must register as a competing reader
    _traced(lambda: Path(WINDOW).read_bytes())
    assert _foreign_opens(), "negative control: a direct corpus read must register as a competing reader"


# ── Test B — one corpus identity per execution ─────────────────────────────────────────────────
@needs
def test_B_identity_originates_in_the_ssot():
    cs._SSOT_CACHE.clear()
    a = cs.load(WINDOW, "XAUUSD")
    b = cs.load(str(WINDOW), "XAUUSD", sequence_check=False)
    assert a.data is b.data and a.sha256 == b.sha256            # same corpus object/bytes
    assert a.sha256 == hashlib.sha256(WINDOW.read_bytes()).hexdigest()
    from data_ingestion.dataset_registry import load_bound_datasets
    rec = load_bound_datasets()[a.dataset_id]
    assert rec["canonical_artifact"]["sha256"] == a.sha256
    assert a.identity == a.dataset_id
    assert a.n_rows == rec["canonical_artifact"]["rows"]


# ── Test C — one corpus content: every representation is a parse of the SSOT bytes ─────────────
@needs
def test_C_representations_share_the_ssot_bytes():
    c = cs.load(WINDOW, "XAUUSD")
    recs = c.records()
    df = c.frame()
    assert len(recs) == len(df) == c.n_rows
    # CH-corpus-clock-contract-v1: consumers receive canonical UTC; the source cell is kept
    assert recs[0]["timestamp"] == c.start and recs[-1]["timestamp"] == c.end
    assert recs[0]["source_timestamp"] == c.source_start and recs[-1]["source_timestamp"] == c.source_end
    assert c.source_text == c.data.decode("utf-8-sig")        # identity is the SOURCE bytes
    assert c.sha256 == hashlib.sha256(c.data).hexdigest()
    assert c.text != c.source_text and c.text.splitlines()[0].endswith("source_timestamp")
    assert c.clock_state == "canonical_utc" and df.attrs["timestamp_clock"] == "UTC"


# ── Test D — provenance propagation: artifacts take identity from the corpus consumed ──────────
@needs
def test_D_mother_range_report_identity_is_the_consumed_corpus():
    from research.mother_range import driver as mr

    cs._SSOT_CACHE.clear()
    rep = mr.run(WINDOW)
    c = cs.load(WINDOW, "XAUUSD")
    assert rep["corpus_sha256"] == c.sha256
    assert rep["dataset_id"] == c.dataset_id
    assert rep["corpus_provenance"]["corpus_identity"] == c.identity


@needs
def test_D_evidence_fingerprint_hashes_the_corpus_identity():
    from research.evidence import asymmetry_contract as ac

    real = cs.load(CANON, "XAUUSD", sequence_check=False)
    other = cs.load(WINDOW, "XAUUSD", sequence_check=False)
    rows = [{"instrument": "XAUUSD", "decision_ts": "2026-01-01 00:00:00", "delta_mfe": 0.5}]
    f1, f2 = ac.fingerprint(rows, real), ac.fingerprint(rows, other)
    assert f1["sha256"] != f2["sha256"], "fingerprint must change when the corpus changes"
    assert f1["corpus_sha256"] == real.sha256 and f1["dataset_id"] == real.dataset_id
    assert {"dataset_id", "corpus_sha256"} <= set(f1["population_hash_inputs"])


# ── Test E — no hidden readers: static scan of src/ for raw corpus reads outside the SSOT ──────
_CORPUS_NAMES = {"csv", "csv_path", "corpus", "corpus_path", "data_path", "ohlcv", "ohlcv_path",
                 "admitted_path", "CORPUS", "CSV", "CSV_PATH", "SRC_CSV", "filepath", "csv_file"}
_READERS = {"read_csv", "DictReader", "reader", "read_bytes", "read_text", "open", "loadtxt",
            "read_table", "read_parquet"}
# Reads that are NOT a competing corpus authority, each with its reason.
_ALLOWED = {
    "src/data_ingestion/": "the corpus authority itself (gate, registry, integrity, clock, store)",
    "src/governance/run_identity.py": "generic byte-hash formula, no corpus consumer calls it (grep)",
    "src/research/ohlcv_open_close_label.py": "verifies the admitted file's pin (no measurement)",
    "src/research/ohlcv_probe_report.py": "verifies the admitted file's pin (no measurement)",
    "src/validation_access/ladder.py": "verifies the admitted file's pin (no measurement)",
    "src/control_plane/dashboard_api.py": "reads trade ledgers, not OHLCV",
    "src/llm_research/pattern_extractor.py": "reads trade ledgers, not OHLCV",
}


def _scan_src():
    hits, unparseable = [], []
    for p in sorted((ROOT / "src").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(k) for k in _ALLOWED):
            continue
        try:
            tree = ast.parse(p.read_bytes().decode("utf-8-sig"), filename=rel)
        except SyntaxError as exc:
            unparseable.append((rel, str(exc)))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name not in _READERS:
                continue
            exprs = list(node.args[:1])
            if isinstance(fn, ast.Attribute) and name in ("open", "read_bytes", "read_text"):
                exprs.append(fn.value)
            names = {n.id for e in exprs for n in ast.walk(e) if isinstance(n, ast.Name)}
            names |= {n.attr for e in exprs for n in ast.walk(e) if isinstance(n, ast.Attribute)}
            if names & _CORPUS_NAMES:
                hits.append(f"{rel}:{node.lineno}: {ast.unparse(node)[:90]}")
    return hits, unparseable


def test_E_no_raw_corpus_reader_in_src_outside_the_ssot():
    hits, unparseable = _scan_src()
    assert not unparseable, f"source could not be analysed (never a clean result): {unparseable}"
    assert not hits, "raw corpus reads outside data_ingestion (route through corpus_store.load):\n" + "\n".join(hits)


# Script/tooling readers that are NOT a competing MT5 corpus authority (each with its reason).
# Separate scope, not exemptions from the rule: crypto/FX corpora await their own identity +
# clock contract (other corpus-identity work); acquisition writes/merges raw fetches BEFORE
# admission; the rest read trade ledgers or logs.
_SCRIPT_ALLOWED = {
    "scripts/data/": "acquisition/preparation of raw fetches, upstream of admission",
    "scripts/analysis/bnbusdt_trade_anatomy.py": "BNBUSDT corpus: other corpus identity (out of XAUUSD scope)",
    "tools/btcusdt_crt_v3_replay.py": "BTCUSDT corpus: other corpus identity (out of XAUUSD scope)",
    "scripts/analysis/set2_consumer_scale_probe.py": "concurrent session's uncommitted WIP (owner converts)",
    "scripts/analysis/schema_audit.py": "reads trade ledgers, not OHLCV",
    "analyze_crt_pipeline.py": "reads decision logs, not OHLCV",
    "scripts/training/phase5_calibration.py": "reads trade ledgers, not OHLCV",
    "scripts/research/candle_state_report.py": "writes a report CSV (mode 'w'), not a read",
}


def test_E_no_raw_corpus_reader_in_scripts_outside_the_ssot():
    files = [*ROOT.glob("scripts/**/*.py"), *ROOT.glob("tools/**/*.py"), *ROOT.glob("*.py")]
    hits, unparseable = [], []
    for p in sorted(files):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(k) for k in _SCRIPT_ALLOWED):
            continue
        try:
            tree = ast.parse(p.read_bytes().decode("utf-8-sig"), filename=rel)
        except SyntaxError as exc:
            unparseable.append((rel, str(exc)[:80]))
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if name not in _READERS:
                continue
            exprs = list(node.args[:1])
            if isinstance(fn, ast.Attribute) and name in ("open", "read_bytes", "read_text"):
                exprs.append(fn.value)
            names = {n.id for e in exprs for n in ast.walk(e) if isinstance(n, ast.Name)}
            names |= {n.attr for e in exprs for n in ast.walk(e) if isinstance(n, ast.Attribute)}
            if names & _CORPUS_NAMES:
                hits.append(f"{rel}:{node.lineno}: {ast.unparse(node)[:90]}")
    # Three files are genuinely invalid Python (not BOM): reported, never read as clean.
    assert {u[0] for u in unparseable} <= {"audit.py", "count_audit_tmp.py",
                                          "scripts/governance/crt_config_construction_census.py"}, unparseable
    assert not hits, "raw corpus reads outside the SSOT:\n" + "\n".join(hits)


def test_E_scanner_detects_a_planted_reader(tmp_path):
    # the rule must be able to fail: a planted direct read is found by the same matcher
    tree = ast.parse("import pandas as pd\ndef f(csv_path):\n    return pd.read_csv(csv_path)\n")
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "attr", "") == "read_csv"]
    assert calls and {a.id for a in calls[0].args if isinstance(a, ast.Name)} & _CORPUS_NAMES


# ── Test F — scanner completeness: BOM / unparseable sources never read as clean ───────────────
def _census():
    spec = importlib.util.spec_from_file_location(
        "corpus_read_census", ROOT / "scripts" / "analysis" / "corpus_read_census.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_F_bom_and_unparseable_files_are_not_clean():
    mod = _census()
    d = ROOT / "tests" / "_tmp_corpus_ssot_scan"
    d.mkdir(exist_ok=True)
    bom, broken = d / "bom_reader.py", d / "broken_reader.py"
    try:
        bom.write_bytes(b"\xef\xbb\xbfimport pandas as pd\n"
                        b"df = pd.read_csv('data/mt5/XAUUSD_M15.csv')\n")
        broken.write_text("def f(:\n    pd.read_csv('data/mt5/XAUUSD_M15.csv')\n", encoding="utf-8")
        found = mod.scan_file(bom)
        assert found, "a BOM-prefixed corpus read must be detected, not skipped"
        bad = mod.scan_file(broken)
        assert bad and bad[0]["call"] == "<syntax-error>", "an unparseable file must surface, not vanish"
    finally:
        for f in (bom, broken):
            if f.exists():
                f.unlink()
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


# ── Test G — no competing fallback authority; several identified corpora coexist ──────────────
@needs
def test_G_declared_alias_resolves_to_its_dataset():
    if not ALIAS.exists():
        pytest.skip("alias file absent")
    c = cs.load(ALIAS, "XAUUSD", sequence_check=False)
    canon = cs.load(CANON, "XAUUSD", sequence_check=False)
    assert c.rewritten and c.dataset_id == canon.dataset_id and c.sha256 == canon.sha256


@needs
def test_G_other_corpus_keeps_its_own_identity(tmp_path):
    NEWER = _newer(tmp_path)
    n = cs.load(NEWER, "XAUUSD", sequence_check=False)
    canon = cs.load(CANON, "XAUUSD", sequence_check=False)
    assert Path(n.path).resolve() == NEWER.resolve(), "must NOT be silently rewritten to the old corpus"
    assert not n.rewritten and n.dataset_id is None and n.identity == f"sha256:{n.sha256}"
    assert n.sha256 != canon.sha256


@needs
def test_G_program_candidates_must_be_one_corpus(monkeypatch, tmp_path):
    from research.ic002_entry_evolution import io_util

    c = io_util.resolve_ohlcv(["data/mt5/XAUUSD_M15.csv", "data/XAUUSD_M15.csv"])  # alias -> same
    assert c.dataset_id == "XAUUSD_MT5_PHASE1_20260521"
    NEWER = _newer(tmp_path)
    with pytest.raises(ValueError, match="different corpora"):
        io_util.resolve_ohlcv(["data/mt5/XAUUSD_M15.csv", str(NEWER)])
