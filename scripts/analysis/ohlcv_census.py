"""ohlcv_census.py — PHASE 1 (OHLCV Truth Closure) PASS-A census generator.

READ-ONLY, deterministic, stdlib-only. Scans every physical market-data artifact
under ``data/`` (plus ``btc_daily.csv`` at repo root), computes per-file identity
+ integrity statistics, applies the declared corpus-identity rules (physical file
!= logical corpus), and emits:

  * docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json  (machine)
  * docs/governance/ohlcv-census-2026-07-10.md                         (human)

Determinism contract: output bytes are a pure function of the scanned files, the
repo commit/branch, and the ``--timestamp`` argument (no wall-clock reads). Two
runs over unchanged data must be byte-identical — this is the PASS-A determinism
gate.

Census semantics are bound to runtime truth where possible: timestamp formats and
header aliases are IMPORTED from ``data_ingestion.ohlcv_schema`` (the single
source of truth the real loaders use), never re-declared.

This script never modifies, moves, or deletes anything outside its two output
artifacts. It COUNTS violations (duplicate/out-of-order timestamps, OHLC
inconsistencies) that the runtime ``CandleLoader`` would RAISE on — census is
recon, not enforcement.

Usage:
    venv/Scripts/python.exe scripts/analysis/ohlcv_census.py
    venv/Scripts/python.exe scripts/analysis/ohlcv_census.py --check   # no write; exit 1 on diff
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from data_ingestion.ohlcv_schema import (  # noqa: E402
    OHLCV_DATE_FORMATS,
    OHLCV_HEADER_ALIASES,
)

SCRIPT_VERSION = "1.0.0"
DEFAULT_TIMESTAMP = "2026-07-10T13:09:06Z"
OUT_JSON = _ROOT / "docs" / "governance" / "ohlcv-corpus-fingerprint-manifest-2026-07-10.json"
OUT_MD = _ROOT / "docs" / "governance" / "ohlcv-census-2026-07-10.md"

_TF_TOKENS = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
_DERIVED_SUFFIX_MARKERS = (
    "_setups", "_purge_scan", "_continuation", "_reversion", "_second_low",
    "_secondlow", "_part_", "_isolated",
)

# Corpus-identity / authority rules (C2). Rule ids are cited per-file in
# `authority_evidence`; the full rule text is reproduced in the census markdown.
AUTHORITY_RULES = {
    "RULE-QUARANTINE": (
        "path contains a `_rejected` segment -> QUARANTINED (integrity-gate "
        "quarantine convention: fetch_and_verify_mt5.py --quarantine "
        "data/mt5/_rejected, fetch_and_verify_binance.py --quarantine "
        "data/binance/_rejected). Confidence HIGH."
    ),
    "RULE-ARCHIVE": (
        "path contains an `_archive` segment -> ARCHIVED (frozen snapshot "
        "convention, e.g. data/_archive_5wk/). Confidence HIGH."
    ),
    "RULE-NON-OHLCV": (
        "header does not resolve the six OHLCV columns via "
        "ohlcv_schema.OHLCV_HEADER_ALIASES -> EXCLUDED (non-OHLCV artifact, "
        "e.g. data/perp/ funding/basis series). Confidence HIGH."
    ),
    "RULE-DERIVED-SUFFIX": (
        "filename stem carries a derived-artifact marker "
        f"({', '.join(_DERIVED_SUFFIX_MARKERS)}) -> DERIVED. Parent = the "
        "canonical `{SYMBOL}_{TF}` artifact in the same directory when present. "
        "Confidence MEDIUM (marker convention; per-file generator not "
        "individually traced)."
    ),
    "RULE-RESAMPLED": (
        "under data/resampled/ -> DERIVED from data/{SYMBOL}_M15.csv via "
        "scripts/research/build_resampled_data.py (reads --data-dir data, "
        "writes --out data/resampled; research.resample causality-invariant "
        "aggregator). Confidence HIGH for the pathway, MEDIUM per file (no "
        "stored generation log ties each output hash to an input hash)."
    ),
    "RULE-PROVIDER-MT5": (
        "data/mt5/{SYMBOL}_{TF}.csv canonical-pattern -> AUTHORITATIVE_RAW "
        "(provider-differentiated corpus written by "
        "scripts/data/fetch_and_verify_mt5.py DEFAULT_OUT='data/mt5' via "
        "inout.mt5_candle_fetcher.MT5CandleFetcher, strict-gate verified). "
        "Confidence MEDIUM (write path proven statically; per-file acquisition "
        "session not individually logged)."
    ),
    "RULE-PROVIDER-BINANCE": (
        "data/binance/{SYMBOL}_{TF}.csv canonical-pattern -> AUTHORITATIVE_RAW "
        "(provider-differentiated corpus written by "
        "scripts/data/fetch_and_verify_binance.py DEFAULT_OUT='data/binance', "
        "strict-gate verified). Confidence MEDIUM (same caveat as MT5)."
    ),
    "RULE-PROVIDER-YFINANCE": (
        "data/yfinance/*.csv -> AUTHORITATIVE_RAW candidate (provider dir; "
        "scripts/data/fetch_forex_yfinance.py exists) but NO verify-gate "
        "wrapper found. Confidence LOW."
    ),
    "RULE-ROOT-CANONICAL": (
        "data/{SYMBOL}_{TF}.csv at the data root, canonical pattern -> "
        "AUTHORITATIVE_CANONICAL role (the active config's "
        "dataset_integrity.canonical_data_roots=['data'] and the historical "
        "backtest corpus live here; fetch_and_verify_binance.py:9 calls this "
        "the 'legacy data/{SYMBOL}_M15.csv' corpus). SOURCE provenance is NOT "
        "established per file -> provenance UNKNOWN, confidence LOW."
    ),
    "RULE-UNMATCHED": (
        "no rule matched -> authority_class UNKNOWN, confidence UNKNOWN. "
        "Census never infers unknown provenance (Prompt-2 STEP 2)."
    ),
}


# ── timestamp parsing (fast path + runtime-truth fallback) ─────────────────────
def _fast_ts(raw: str):
    """Parse 'YYYY-MM-DD HH:MM:SS' / 'YYYY-MM-DD HH:MM' without strptime."""
    try:
        if len(raw) == 19:
            return datetime(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]),
                            int(raw[11:13]), int(raw[14:16]), int(raw[17:19]))
        if len(raw) == 16:
            return datetime(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]),
                            int(raw[11:13]), int(raw[14:16]))
        if len(raw) == 10:
            return datetime(int(raw[0:4]), int(raw[5:7]), int(raw[8:10]))
    except ValueError:
        return None
    return None


def _parse_ts(raw: str):
    """Return (datetime|None, format_label). Mirrors ohlcv_schema formats."""
    raw = raw.strip()
    dt = _fast_ts(raw)
    if dt is not None:
        return dt, "canonical"
    for fmt in OHLCV_DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt), fmt
        except ValueError:
            continue
    return None, "UNPARSEABLE"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=_ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _rel(p: Path) -> str:
    return str(p.relative_to(_ROOT)).replace("\\", "/")


# ── header resolution (bound to runtime aliases) ───────────────────────────────
def _resolve_headers(headers: list[str]) -> dict:
    lower = {h.strip().lower(): i for i, h in enumerate(headers)}
    resolved: dict = {}
    for canonical, aliases in OHLCV_HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                resolved[canonical] = lower[alias]
                break
    # split date+time satisfies "timestamp" (CandleLoader convention)
    if "timestamp" not in resolved and "date" in lower and "time" in lower:
        resolved["timestamp"] = -1  # sentinel: split columns
        resolved["_date_col"] = lower["date"]
        resolved["_time_col"] = lower["time"]
    return resolved


# ── per-file scan ──────────────────────────────────────────────────────────────
def _scan_csv(p: Path) -> dict:
    rec: dict = {"schema_class": None, "header": None}
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            headers = [h.strip() for h in next(reader)]
        except StopIteration:
            rec["schema_class"] = "EMPTY_FILE"
            rec["rows"] = 0
            return rec
        rec["header"] = headers
        res = _resolve_headers(headers)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if not required.issubset(res.keys()):
            rec["schema_class"] = "NON_OHLCV"
            rec["rows"] = sum(1 for _ in reader)
            rec["missing_columns"] = sorted(required - set(res.keys()))
            return rec
        rec["schema_class"] = ("OHLCV_PLUS_EXTRA" if len(headers) > 6 else "OHLCV")

        ts_i = res["timestamp"]
        split = ts_i == -1
        o_i, h_i, l_i, c_i, v_i = (res["open"], res["high"], res["low"],
                                   res["close"], res["volume"])
        n = dup = ooo = 0
        zero_vol = neg_vol = nonfinite = ohlc_viol = unparse_num = unparse_ts = 0
        first_ts = last_ts = prev = None
        fmts: Counter = Counter()
        deltas: Counter = Counter()
        max_gap_s = 0
        gaps = 0
        seen: set = set()
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            n += 1
            raw_ts = (row[res["_date_col"]].strip() + " " + row[res["_time_col"]].strip()
                      if split else row[ts_i].strip())
            ts, fmt = _parse_ts(raw_ts)
            fmts[fmt] += 1
            if ts is None:
                unparse_ts += 1
                prev = None
                continue
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            if ts in seen:
                dup += 1
            seen.add(ts)
            if prev is not None:
                if ts < prev:
                    ooo += 1
                else:
                    d = int((ts - prev).total_seconds())
                    if d > 0:
                        deltas[d] += 1
            prev = ts
            try:
                o, hi, lo, cl, v = (float(row[o_i]), float(row[h_i]),
                                    float(row[l_i]), float(row[c_i]),
                                    float(row[v_i]))
            except (ValueError, IndexError):
                unparse_num += 1
                continue
            for val in (o, hi, lo, cl, v):
                if math.isnan(val) or math.isinf(val):
                    nonfinite += 1
                    break
            if v == 0:
                zero_vol += 1
            elif v < 0:
                neg_vol += 1
            if hi < lo or hi < o or hi < cl or lo > o or lo > cl:
                ohlc_viol += 1
        modal = None
        if deltas:
            modal = deltas.most_common(1)[0][0]
            # ties: pick smallest for determinism
            top = deltas.most_common(1)[0][1]
            modal = min(d for d, c in deltas.items() if c == top)
            for d, c in sorted(deltas.items()):
                if d > modal:
                    gaps += c
                    max_gap_s = max(max_gap_s, d)
        rec.update({
            "rows": n,
            "first_timestamp": first_ts.isoformat(sep=" ") if first_ts else None,
            "last_timestamp": last_ts.isoformat(sep=" ") if last_ts else None,
            "timestamp_formats": dict(sorted(fmts.items())),
            "timezone": "NAIVE (no offset in data; UTC is an ASSUMPTION — see temporal report)",
            "duplicate_timestamps": dup,
            "out_of_order_timestamps": ooo,
            "unparseable_timestamps": unparse_ts,
            "unparseable_numeric_rows": unparse_num,
            "modal_delta_seconds": modal,
            "gap_events_gt_modal": gaps,
            "largest_gap_seconds": max_gap_s,
            "zero_volume_rows": zero_vol,
            "zero_volume_rate": round(zero_vol / n, 6) if n else None,
            "volume_all_zero": bool(n and zero_vol == n),
            "negative_volume_rows": neg_vol,
            "nonfinite_rows": nonfinite,
            "ohlc_violations": ohlc_viol,
        })
        return rec


# ── identity / authority assignment ────────────────────────────────────────────
def _split_stem(stem: str):
    """Return (symbol, tf, derived_marker) from a filename stem."""
    low = stem.lower()
    marker = next((m for m in _DERIVED_SUFFIX_MARKERS if m in low), None)
    parts = stem.split("_")
    for i, tok in enumerate(parts):
        if tok.upper() in _TF_TOKENS:
            return "_".join(parts[:i]).upper(), tok.upper(), marker
    return None, None, marker


def _classify(rel: str, stem: str, schema_class: str) -> tuple[str, str, str, str]:
    """Return (authority_class, rule_id, confidence, excluded_reason)."""
    low = rel.lower()
    if "_rejected" in low:
        return "QUARANTINED", "RULE-QUARANTINE", "HIGH", ""
    if "_archive" in low:
        return "ARCHIVED", "RULE-ARCHIVE", "HIGH", ""
    if schema_class in ("NON_OHLCV", "EMPTY_FILE", "PARQUET_UNREAD"):
        return "EXCLUDED", "RULE-NON-OHLCV", "HIGH", schema_class
    sym, tf, marker = _split_stem(stem)
    if marker:
        return "DERIVED", "RULE-DERIVED-SUFFIX", "MEDIUM", ""
    if low.startswith("data/resampled/"):
        return "DERIVED", "RULE-RESAMPLED", "MEDIUM", ""
    canonical_pattern = sym is not None and tf is not None
    if low.startswith("data/mt5/") and canonical_pattern:
        return "AUTHORITATIVE_RAW", "RULE-PROVIDER-MT5", "MEDIUM", ""
    if low.startswith("data/binance/") and canonical_pattern:
        return "AUTHORITATIVE_RAW", "RULE-PROVIDER-BINANCE", "MEDIUM", ""
    if low.startswith("data/yfinance/"):
        return ("AUTHORITATIVE_RAW", "RULE-PROVIDER-YFINANCE", "LOW", "") \
            if canonical_pattern else ("UNKNOWN", "RULE-UNMATCHED", "UNKNOWN", "")
    if canonical_pattern and low.count("/") == 1 and low.startswith("data/"):
        return "AUTHORITATIVE_CANONICAL", "RULE-ROOT-CANONICAL", "LOW", ""
    return "UNKNOWN", "RULE-UNMATCHED", "UNKNOWN", ""


def build_records() -> list[dict]:
    files = sorted(_ROOT.glob("data/**/*.csv")) + sorted(_ROOT.glob("data/**/*.parquet"))
    extra = _ROOT / "btc_daily.csv"
    if extra.is_file():
        files.append(extra)
    files = sorted(set(files), key=lambda p: _rel(p))

    records = []
    for p in files:
        rel = _rel(p)
        stem = p.stem
        if p.suffix == ".parquet":
            scan = {"schema_class": "PARQUET_UNREAD", "rows": None,
                    "note": "stdlib census cannot read parquet; stats UNKNOWN"}
        else:
            try:
                scan = _scan_csv(p)
            except Exception as exc:  # recon never crashes on one bad file
                scan = {"schema_class": "SCAN_ERROR", "rows": None,
                        "scan_error": f"{type(exc).__name__}: {exc}"}
        auth, rule, conf, excl = _classify(rel, stem, scan["schema_class"])
        sym, tf, marker = _split_stem(stem)
        family = rel.split("/")[1] if rel.startswith("data/") and rel.count("/") >= 2 \
            else ("data_root" if rel.startswith("data/") else "repo_root")
        logical = f"{sym}_{tf}" if sym and tf and not marker else stem.upper()
        parents: list[str] = []
        if rule == "RULE-RESAMPLED" and sym:
            parents = [f"data/{sym}_M15.csv"]
        elif rule == "RULE-DERIVED-SUFFIX" and sym and tf:
            cand = p.parent / f"{sym}_{tf}.csv"
            if cand.is_file():
                parents = [_rel(cand)]
        rec = {
            "physical_artifact_id": "PA-" + hashlib.sha256(rel.lower().encode()).hexdigest()[:12],
            "physical_path": rel,
            "size_bytes": p.stat().st_size,
            "sha256": _sha256(p),
            "corpus_family_id": family,
            "logical_corpus_id": logical,
            "instrument": sym or "UNKNOWN",
            "timeframe": tf or "UNKNOWN",
            "authority_class": auth,
            "authority_rule": rule,
            "authority_evidence": AUTHORITY_RULES[rule],
            "authority_confidence": conf,
            "excluded_reason": excl,
            "derivation_parent_ids": parents,
            "source_provenance": (
                "mt5_broker_ipc" if rule == "RULE-PROVIDER-MT5" else
                "binance_rest" if rule == "RULE-PROVIDER-BINANCE" else
                "resample_of_root_m15" if rule == "RULE-RESAMPLED" else
                "UNKNOWN"),
        }
        rec.update(scan)
        records.append(rec)

    # duplicate content groups
    by_hash: dict[str, list[dict]] = {}
    for r in records:
        by_hash.setdefault(r["sha256"], []).append(r)
    gid = 0
    for h in sorted(by_hash):
        group = by_hash[h]
        if len(group) > 1:
            gid += 1
            for r in group:
                r["duplicate_content_group"] = f"DUP-{gid:03d}"
        else:
            group[0]["duplicate_content_group"] = None
    return records


def logical_rollup(records: list[dict]) -> list[dict]:
    """One row per logical corpus id over ACTIVE claimants (non-quarantined,
    non-archived, non-derived, OHLCV-schema, canonical name)."""
    active = [r for r in records
              if r["authority_class"] in ("AUTHORITATIVE_RAW", "AUTHORITATIVE_CANONICAL")
              and r["instrument"] != "UNKNOWN"]
    by_logical: dict[str, list[dict]] = {}
    for r in active:
        by_logical.setdefault(r["logical_corpus_id"], []).append(r)
    out = []
    for lid in sorted(by_logical):
        claims = by_logical[lid]
        hashes = sorted({c["sha256"] for c in claims})
        out.append({
            "logical_corpus_id": lid,
            "n_claimants": len(claims),
            "claimant_paths": sorted(c["physical_path"] for c in claims),
            "claimant_families": sorted({c["corpus_family_id"] for c in claims}),
            "distinct_hashes": len(hashes),
            "authority_ambiguous": len(claims) > 1,
            "same_logical_different_bytes": len(claims) > 1 and len(hashes) > 1,
        })
    return out


# ── markdown rendering ─────────────────────────────────────────────────────────
def render_md(records, rollup, meta) -> str:
    def row(cells):
        return "| " + " | ".join(str(c) for c in cells) + " |"

    lines = [
        "# OHLCV Corpus Census — PHASE 1 (OHLCV Truth Closure) PASS A",
        "",
        "| Field | Value |",
        "|---|---|",
        "| Program | Layer-by-layer repository audit (bottom-up) |",
        "| Phase | 1 of 16 — OHLCV Truth |",
        "| Pass | A (Evidence Freeze) |",
        f"| Generated (UTC) | {meta['generated_at_utc']} |",
        f"| Pinned commit | `{meta['repository_commit']}` (worktree DIRTY — hashes pin on-disk bytes) |",
        f"| Branch | `{meta['branch']}` |",
        "| Machine-readable twin | `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json` |",
        f"| Generator | `scripts/analysis/ohlcv_census.py` v{SCRIPT_VERSION} (deterministic; stdlib) |",
        "| Verdict | (none — PASS A emits evidence only; closure adjudication is PASS B) |",
        "",
        "**Scope note.** This census inventories PHYSICAL artifacts and applies the",
        "declared identity rules. Inventorying N files is NOT a claim that logical",
        "corpus authority is closed (C2). Timestamps in every scanned file are",
        "tz-NAIVE; 'UTC' is an assumption to be proven per acquisition path in the",
        "temporal-semantics report, not a census finding. Gap statistics here are",
        "session-BLIND raw inter-bar deltas (the session-aware interpretation is",
        "`dataset_integrity._analyze_gaps`'s job) — a weekend close appears as a",
        "'gap' below and that is expected, not a defect.",
        "",
        "## Identity / authority rules applied",
        "",
        "| Rule | Effect |",
        "|---|---|",
    ]
    for rid in sorted(AUTHORITY_RULES):
        lines.append(row([f"`{rid}`", AUTHORITY_RULES[rid]]))

    lines += [
        "",
        "## Family summary",
        "",
        "| corpus_family_id | files | OHLCV-schema | rows (sum, scanned) | authority classes |",
        "|---|---|---|---|---|",
    ]
    fams: dict[str, list[dict]] = {}
    for r in records:
        fams.setdefault(r["corpus_family_id"], []).append(r)
    for fam in sorted(fams):
        rs = fams[fam]
        n_ohlcv = sum(1 for r in rs if r["schema_class"] in ("OHLCV", "OHLCV_PLUS_EXTRA"))
        rows_sum = sum(r["rows"] or 0 for r in rs)
        classes = sorted({r["authority_class"] for r in rs})
        lines.append(row([f"`{fam}`", len(rs), n_ohlcv, rows_sum, ", ".join(classes)]))

    lines += [
        "",
        "## Logical-corpus rollup (ACTIVE claimants only)",
        "",
        "A logical corpus is AMBIGUOUS when more than one active (non-quarantined,",
        "non-archived, non-derived) physical file claims the same `{SYMBOL}_{TF}`",
        "identity. `same_logical_different_bytes` is the stronger flag: identical",
        "logical name resolving to different data.",
        "",
        "| logical_corpus_id | claimants | families | distinct hashes | AMBIGUOUS | different bytes |",
        "|---|---|---|---|---|---|",
    ]
    for lr in rollup:
        lines.append(row([
            f"`{lr['logical_corpus_id']}`", lr["n_claimants"],
            ", ".join(f"`{f}`" for f in lr["claimant_families"]),
            lr["distinct_hashes"],
            "**YES**" if lr["authority_ambiguous"] else "no",
            "**YES**" if lr["same_logical_different_bytes"] else "no",
        ]))
    n_amb = sum(1 for lr in rollup if lr["authority_ambiguous"])
    n_diff = sum(1 for lr in rollup if lr["same_logical_different_bytes"])
    lines += [
        "",
        f"**{len(rollup)} logical corpora; {n_amb} AMBIGUOUS; "
        f"{n_diff} with same-logical-different-bytes.**",
        "",
        "## Physical artifact census",
        "",
        "Full per-artifact detail (all fields incl. per-format timestamp counts and",
        "authority evidence text) lives in the machine twin. `dupTS`/`oOo` = duplicate /",
        "out-of-order timestamp COUNTS (the runtime loader raises on the first; census",
        "counts all). `gaps` = inter-bar deltas > modal (session-blind).",
        "",
        "| id | path | class | conf | schema | rows | first ts | last ts | modal(s) | gaps | dupTS | oOo | zeroVol | negV | OHLCviol | dupGrp |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        lines.append(row([
            r["physical_artifact_id"], f"`{r['physical_path']}`",
            r["authority_class"], r["authority_confidence"], r["schema_class"],
            r.get("rows", ""), r.get("first_timestamp") or "", r.get("last_timestamp") or "",
            r.get("modal_delta_seconds", ""), r.get("gap_events_gt_modal", ""),
            r.get("duplicate_timestamps", ""), r.get("out_of_order_timestamps", ""),
            r.get("zero_volume_rows", ""), r.get("negative_volume_rows", ""),
            r.get("ohlc_violations", ""), r.get("duplicate_content_group") or "",
        ]))

    all_zero = [r for r in records if r.get("volume_all_zero")]
    lines += [
        "",
        "## Latent volume-substitution exposure",
        "",
        "`FeaturePipeline.compute_volume_features` (src/features/feature_pipeline.py:202-233)",
        "substitutes `high-low` into `volume` when a frame's volume column is ALL-zero.",
        f"Artifacts whose ENTIRE volume column is zero (would activate the proxy): "
        f"**{len(all_zero)}**",
    ]
    for r in all_zero:
        lines.append(f"- `{r['physical_path']}` ({r['authority_class']})")
    lines += [
        "",
        "## What this census did NOT do",
        "",
        "- No closure verdict, no BLOCKER adjudication (PASS B).",
        "- No session-aware gap gating (that is `dataset_integrity.validate_dataset`).",
        "- No remediation, no file moves, no quarantining.",
        "- No economic claim of any kind.",
        "- Parquet artifacts hashed but not parsed (stdlib constraint) — stats UNKNOWN.",
        "",
        "```text",
        f"OHLCV_CENSUS_FILES = {len(records)}",
        f"OHLCV_CENSUS_LOGICAL = {len(rollup)}",
        f"OHLCV_CENSUS_AMBIGUOUS_LOGICAL = {n_amb}",
        f"OHLCV_CENSUS_SAME_LOGICAL_DIFFERENT_BYTES = {n_diff}",
        f"OHLCV_CENSUS_ALL_ZERO_VOLUME_FILES = {len(all_zero)}",
        "OHLCV_CENSUS_STATUS = EVIDENCE_FROZEN",
        "NEXT = PASS-A lineage / temporal / contradiction artifacts; closure = PASS B",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--timestamp", default=DEFAULT_TIMESTAMP,
                    help="pinned generated_at_utc (determinism: no wall-clock)")
    ap.add_argument("--check", action="store_true",
                    help="compare against existing outputs; exit 1 on diff; write nothing")
    args = ap.parse_args()

    records = build_records()
    rollup = logical_rollup(records)
    meta = {
        "_doc": (
            "PHASE 1 (OHLCV Truth Closure) PASS-A corpus fingerprint manifest. "
            "GENERATED deterministically by scripts/analysis/ohlcv_census.py — "
            "regenerate, never hand-edit. Physical-artifact identity + integrity "
            "statistics + declared authority rules. Census is evidence, not a "
            "closure verdict."
        ),
        "schema_version": "1.0.0",
        "generator": f"scripts/analysis/ohlcv_census.py v{SCRIPT_VERSION}",
        "generated_at_utc": args.timestamp,
        "repository_commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "authority_rules": AUTHORITY_RULES,
    }
    manifest = {**meta,
                "n_physical_artifacts": len(records),
                "n_logical_corpora": len(rollup),
                "logical_rollup": rollup,
                "artifacts": records}
    js = json.dumps(manifest, indent=2) + "\n"
    md = render_md(records, rollup, meta)

    if args.check:
        ok = (OUT_JSON.read_text(encoding="utf-8") == js
              and OUT_MD.read_text(encoding="utf-8") == md)
        print("DETERMINISM_CHECK =", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    OUT_JSON.write_text(js, encoding="utf-8")
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON.name}: {len(records)} artifacts, {len(rollup)} logical corpora")
    print(f"wrote {OUT_MD.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
