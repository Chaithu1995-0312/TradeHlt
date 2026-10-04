"""Idempotent: append Unreferenced_spine paths to owning topic Code covered blocks."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "docs" / "topics"
MARKER = "Spine inventory (2026-09-03 citation pass"

# Owning topic → exact .py paths (Unreferenced_spine 2026-09-03 after GCMC restore).
ASSIGN: dict[str, list[str]] = {
    "feature-schema.md": [
        "src/core/feature_store.py",
        "src/data_ingestion/__init__.py",
        "src/data_ingestion/clock_detector.py",
        "src/data_ingestion/clock_registry.py",
        "src/data_ingestion/session_autoderive.py",
        "src/data_ingestion/xauusd_phase1_candidate.py",
        "src/features/__init__.py",
        "src/features/broker_clock.py",
        "src/features/calendar_periods.py",
        "src/features/dataset_builder.py",
        "src/features/feature_builder.py",
        "src/features/feature_identity.py",
        "src/features/fm_resolve.py",
        "src/features/gaussian_schema_contract.py",
        "src/features/magnitude_states.py",
        "src/features/market_context.py",
        "src/features/market_reality_contract.py",
        "src/features/market_shape.py",
        "src/features/model_evidence.py",
        "src/features/parent_candle.py",
        "src/features/registry/__init__.py",
        "src/features/registry/_loader.py",
        "src/features/registry/composition_registry.py",
        "src/features/registry/derived_registry.py",
        "src/features/registry/predicate_registry.py",
        "src/features/registry/primitive_registry.py",
        "src/features/schema_validator.py",
    ],
    "crt-spine.md": [
        "src/config_layer/crt_config_completeness.py",
        "src/config_layer/crt_config_provenance.py",
        "src/config_layer/crt_identity_schema.py",
        "src/config_layer/crt_sweep_taxonomy.py",
        "src/config_layer/state_contract.py",
        "src/config_layer/state_contract_loader.py",
        "src/config_layer/_crt_state_generated.py",
        "src/features/smc/__init__.py",
        "src/features/smc/_geometry.py",
        "src/features/smc/breaker.py",
        "src/features/smc/choch.py",
        "src/features/smc/fvg.py",
        "src/features/smc/levels.py",
        "src/features/smc/mitigation.py",
        "src/features/smc/order_block.py",
        "src/structure/__init__.py",
        "src/structure/predicates.py",
        "src/runtime/bar_structure_snapshot.py",
        "src/runtime/crt_baseline_trace.py",
        "src/runtime/crt_construction_trace.py",
        "src/runtime/crt_fail_reason_counters.py",
    ],
    "scoring-engines.md": [
        "src/engines/__init__.py",
        "src/engines/gaussian_engine.py",
        "src/engines/tradenet_meta_engine.py",
        "src/engines/zone_cluster_score.py",
    ],
    "fusion-decision.md": [
        "src/core/__init__.py",
        "src/core/backtest_port.py",
        "src/core/dynamic_threshold.py",
        "src/core/governance_mode.py",
        "src/core/hierarchical_meta_fusion.py",
        "src/core/signal_belief_tracker.py",
        "src/core/types.py",
        "src/runtime/analyze_fusion_shadow.py",
    ],
    "execution-planning.md": [
        "src/execution/__init__.py",
        "src/execution/execution_intent_v1_0.py",
    ],
    "ultron-risk-gate.md": [
        "src/core/ultron_live_adapter.py",
    ],
    "live-execution.md": [
        "src/live/__init__.py",
        "src/live/order_manager.py",
        "src/inout/live_rail/__init__.py",
        "src/inout/live_rail/bar_builder.py",
        "src/inout/live_rail/binance_ws_adapter.py",
        "src/inout/live_rail/config.py",
        "src/inout/live_rail/factory.py",
        "src/inout/live_rail/longport_adapter.py",
        "src/inout/live_rail/ohlcv_replay_port.py",
        "src/inout/live_rail/resilience.py",
        "src/inout/live_rail/tickdb_adapter.py",
        "src/inout/live_rail/types.py",
        "src/runtime/live_rail_feeder.py",
        "src/runtime/live_rail_orchestrator.py",
        "src/runtime/__init__.py",
    ],
    "portfolio-allocation.md": [
        "src/portfolio/__init__.py",
    ],
    "regime-classifier.md": [
        "src/regime/__init__.py",
    ],
    "config-validation.md": [
        "src/config_layer/__init__.py",
        "src/config_layer/stack_version.py",
        "src/utils/config_dumper.py",
        "src/utils/isolated_config_root.py",
        "src/utils/registry_refresh.py",
    ],
    "research-measurement-contract.md": [
        "src/identity/__init__.py",
        "src/identity/certify.py",
        "src/identity/check.py",
        "src/identity/hashes.py",
        "src/identity/outcome.py",
        "src/identity/query.py",
        "src/identity/store.py",
        "src/identity/tokens.py",
    ],
    "metrics-layer.md": [
        "src/journal/__init__.py",
        "src/journal/schema.py",
        "src/journal/trade_execution_link_v1_0.py",
        "src/journal/trade_identity_v1_0.py",
        "src/journal/trade_provenance_v1_0.py",
    ],
    "training-calibration.md": [
        "src/config_layer/rr/__init__.py",
        "src/config_layer/rr/rr_dataset_builder.py",
    ],
}

# Utils left on the spine with no NEEDED topic — INFRA.md names them.
INFRA_UTILS = [
    "src/utils/console_safe.py",
    "src/utils/jsonl_writer.py",
    "src/utils/log_identity.py",
    "src/utils/log_index_writer.py",
    "src/utils/logging_config.py",
    "src/utils/parquet_store.py",
    "src/utils/pattern_hasher.py",
    "src/utils/zone_schema_migrator.py",
]

NOTE = (
    "path existence on the GCMC spine join; not a behavior claim, not G001, "
    "not a file:line citation. Source still wins."
)


def _block(files: list[str]) -> str:
    lines = [
        f"- **{MARKER} — {NOTE}:**",
    ]
    for f in files:
        lines.append(f"- [`{f}`](../../{f})")
    return "\n".join(lines) + "\n"


def _stamp_updated(text: str) -> str:
    def repl(m: re.Match) -> str:
        return m.group(1) + "2026-09-03"
    return re.sub(r"(Updated:\s*)\d{4}-\d{2}-\d{2}", repl, text, count=1)


def patch_topic(name: str, files: list[str]) -> None:
    path = TOPICS / name
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"skip (already cited): {name}")
        return
    if "## Ins / Outs" not in text:
        raise SystemExit(f"{name}: no ## Ins / Outs")
    block = _block(files)
    text = text.replace("## Ins / Outs", block + "\n## Ins / Outs", 1)
    text = _stamp_updated(text)
    disc = (
        f"- **2026-09-03 — spine citation pass:** named {len(files)} previously "
        f"unreferenced spine paths under Code covered ({NOTE})."
    )
    if "## Discussion" in text:
        # append at end
        text = text.rstrip() + "\n" + disc + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"cited {len(files):3} -> docs/topics/{name}")


def patch_infra() -> None:
    path = ROOT / ".grok" / "INFRA.md"
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print("skip INFRA utils block")
        return
    rows = "\n".join(f"| `{f}` | `data_clock_identity` support |" for f in INFRA_UTILS)
    section = f"""
### {MARKER}

The 108 Unreferenced_spine rows after GCMC restore were named in owning
`docs/topics/*.md` Code covered blocks (existence only). Utils with no NEEDED
topic are named here so the join column `Cited in INFRA` is YES:

| File | Room |
|---|---|
{rows}

"""
    text = text.rstrip() + "\n" + section
    path.write_text(text, encoding="utf-8")
    print(f"cited {len(INFRA_UTILS)} utils -> INFRA.md")


def main() -> None:
    assigned = []
    for name, files in ASSIGN.items():
        assigned.extend(files)
        patch_topic(name, files)
    patch_infra()
    assigned.extend(INFRA_UTILS)
    print(f"total paths named: {len(assigned)} unique={len(set(assigned))}")


if __name__ == "__main__":
    main()
