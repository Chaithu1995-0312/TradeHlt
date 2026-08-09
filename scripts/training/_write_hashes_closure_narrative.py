#!/usr/bin/env python3
"""One-shot: embed conversation walkthrough into HASHES_AND_CLOSURE.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
p = ROOT / "results" / "gaussian_xauusd_train" / "HASHES_AND_CLOSURE.json"
payload = json.loads(p.read_text(encoding="utf-8"))
payload["recorded_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

a = payload["both_model_hashes"]["run_A_20260722T193342Z"]
b = payload["both_model_hashes"]["run_B_20260722T194904Z_PRIMARY"]

payload["user_intent_to_closure"] = {
    "north_star": (
        "User wanted trained/scored models on XAUUSD trailing ~2 months, recorded "
        "outputs, then a native XAUUSD Gaussian NB with production-aligned labels, "
        "inspectable bar-level semantics for later LLM explanation, and finally "
        "registry Promoted: Yes."
    ),
    "phases": [
        {
            "phase": 1,
            "user_intent": (
                "Run Gaussian trained model on XAUUSD 2 months data; record output"
            ),
            "what_we_did": (
                "Scored cross-instrument trained NB (BNB/ETH/EUR) + live heuristic on "
                "trailing 2m of Phase-1 frozen corpus (3949 bars). No XAUUSD checkpoint "
                "existed yet."
            ),
            "artifacts": [
                "results/gaussian_xauusd_2m/gaussian_xauusd_2m_LATEST.json",
                "results/gaussian_xauusd_2m/gaussian_scores_xauusd_2m_*.csv",
            ],
            "closure": (
                "Observation recorded; dual Gaussian paths (ML + heuristic) confirmed."
            ),
        },
        {
            "phase": 2,
            "user_intent": "Run ZoneGate trained model on same window; record",
            "what_we_did": (
                "Production v4 zone_registry via score_zone_cluster; thr=0.25; "
                "100% pass on window; non-constant scores mean 0.756."
            ),
            "artifacts": [
                "results/zonegate_xauusd_2m/zonegate_xauusd_2m_LATEST.json",
                "results/zonegate_xauusd_2m/zonegate_scores_xauusd_2m_*.csv",
            ],
            "closure": "ZoneGate output recorded; paired with Gaussian window.",
        },
        {
            "phase": 3,
            "user_intent": (
                "Confirm ZoneGate recorded; confirm both Gaussian ML + heuristic recorded"
            ),
            "what_we_did": (
                "Verified both Gaussian paths in same CSV; wrote "
                "results/xauusd_2m_model_runs_INDEX.json."
            ),
            "closure": "INDEX answers both=yes.",
        },
        {
            "phase": 4,
            "user_intent": "Run RR trained model on same; record",
            "what_we_did": (
                "NanoInference 38-dim name-mapped + live polarity; 100% F-044 bypass "
                "on gated path; raw expected_rr diagnostic columns kept."
            ),
            "artifacts": [
                "results/rr_xauusd_2m/rr_xauusd_2m_LATEST.json",
                "results/rr_xauusd_2m/rr_scores_xauusd_2m_*.csv",
            ],
            "closure": "RR dual path recorded (trained + polarity).",
        },
        {
            "phase": 5,
            "user_intent": (
                "Train Gaussian NB on frozen XAUUSD corpus with canonical schema + "
                "production labels; save XAUUSD artifact; eval trailing 2m; record "
                "manifests and per-bar scores"
            ),
            "what_we_did": (
                "Spine TRADE_OPENED N~1 starved; used CRT SWEEP + "
                "forward_walk(intrabar_fixed)+12bps labels; train on pre-holdout; "
                "live feature dim=39 (v4; 38 was pre-v4 wording). Run A trained 2980 "
                "units corr=0.2267 then failed eval path.relative_to; eval completed offline."
            ),
            "hashes_run_A": {
                "model_sha256": a["model_sha256"],
                "dataset_sha256": a["dataset_sha256"],
            },
            "closure_partial": "Model A exists; no full bar_semantic journal on A.",
        },
        {
            "phase": 6,
            "user_intent": (
                "Careful bar-by-bar semantic tracking for progress and later LLM explanations"
            ),
            "what_we_did": (
                "Shipped src/training/bar_semantic_tracker.py (bar_semantic.v1): closed "
                "Kind/ReasonCode, template narratives, interesting-only + heartbeats every "
                "500 bars, append-only JSONL. Wired into train_gaussian_xauusd.py; "
                "restarted as Run B."
            ),
            "semantic_jsonl": {
                "path": (
                    "results/gaussian_xauusd_train/"
                    "gaussian_xauusd_train_20260722T194904Z/bar_semantic_journal.jsonl"
                ),
                "sha256": b["bar_semantic_journal_sha256"],
                "schema": "bar_semantic.v1",
                "n_lines": 13577,
                "kind_counts": {
                    "STATE_TRANSITION": 6968,
                    "SWEEP_CANDIDATE": 3252,
                    "LABEL_ACCEPTED": 2980,
                    "HOLDOUT": 267,
                    "PROGRESS": 94,
                    "LABEL_SKIPPED": 5,
                    "PHASE_START": 5,
                    "PHASE_END": 4,
                    "NOTE": 1,
                    "WARMUP": 1,
                },
                "llm_contract": (
                    "reason_code is authoritative; narrative is deterministic template "
                    "render; explainer must not invent causes absent from reason_code + payload."
                ),
            },
            "hashes_run_B": {
                "model_sha256": b["model_sha256"],
                "dataset_sha256": b["dataset_sha256"],
                "journal_sha256": b["bar_semantic_journal_sha256"],
            },
            "closure": (
                "Semantic journal complete end-to-end through label_build "
                "(streamed=47275, units=2980). Train metrics match A (corr=0.2267); "
                "models not byte-identical (trained_at / bundle meta differ). Eval "
                "completed offline after same path bug; path fix landed in train script."
            ),
        },
        {
            "phase": 7,
            "user_intent": "Promoted: No → make Promoted: Yes via script reading registry/jsonl",
            "what_we_did": (
                "promote_gaussian(xauusd_nb_20260722T194904Z, instrument=XAUUSD) — "
                "first XAUUSD deploy. show_xauusd_gaussian_promotion.py prints "
                "Promoted: Yes. LATEST/INDEX updated."
            ),
            "closure": (
                "Registry __active__[XAUUSD]=xauusd_nb_20260722T194904Z; "
                "entry.active=true. Live gaussian_impl still heuristic unless config "
                "changed separately."
            ),
        },
    ],
    "terminal_closure": {
        "status": "CLOSED through semantic JSONL + promotion + both hashes recorded",
        "primary_version": "xauusd_nb_20260722T194904Z",
        "both_model_sha256": {
            "A_20260722T193342Z": a["model_sha256"],
            "B_primary_20260722T194904Z": b["model_sha256"],
        },
        "semantic_jsonl_sha256": b["bar_semantic_journal_sha256"],
        "corpus_sha256": payload["corpus_pin"]["sha256"],
        "promoted": True,
        "show_script": "python scripts/training/show_xauusd_gaussian_promotion.py",
        "hashes_file": "results/gaussian_xauusd_train/HASHES_AND_CLOSURE.json",
    },
}

p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print("updated", p)
print("A", a["model_sha256"])
print("B", b["model_sha256"])
print("journal", b["bar_semantic_journal_sha256"])
