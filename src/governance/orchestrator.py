"""
governance/orchestrator.py
════════════════════════════════════════════════════════════════════════════
GovernanceOrchestrator — full 4-step governance loop.

Replaces the pseudocode outline in the deleted exectue_governance_scripts.py.

Pipeline
────────
  Step 1  ReflectionBuffer.load_and_merge()
            Joins collector.jsonl (decisions) with trades CSV (outcomes).
  Step 2  ReflectionBuffer.generate_prompt_payload()
            Analyses feature divergence between wins/losses → meta_prompt.txt
  Step 3  MetaGovernorExecutor.run_inference()
            Runs BitNet LLM on the prompt → raw config patch JSON.
            MetaGovernorExecutor.extract_and_validate_config()
            Parses and validates the patch (requires fusion_min_score key).
            MetaGovernorExecutor.log_governance_event()
            Appends event to governance_audit.jsonl.
  Step 4  ShadowPromotionGate.stage_candidate()
            Writes candidate.json from the patch + active config.
            ShadowPromotionGate.execute_shadow_test()
            Runs shadow backtest → (shadow_pnl, n_trades).
            ShadowPromotionGate.promote_if_superior()
            Promotes candidate if sample-size gate and PnL gate both pass.

CLI
───
  python src/governance/orchestrator.py \\
      --collector-log logs/collector.jsonl \\
      --trades-csv    results/AUDUSD_trades.csv \\
      --baseline-pnl  5.23

  Optional overrides:
      --active-config   configs/production/v1_multi_2026_03.json
      --bitnet-bin      ./bitnet/bin/main
      --model-path      ./models/bitnet_b1_58_70b.gguf
      --audit-log       logs/governance_audit.jsonl
      --prompt-path     logs/meta_prompt.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from governance.meta_governor_executor import MetaGovernorExecutor
from governance.reflection_buffer_advanced import ReflectionBuffer
from governance.shadow_promotion_gate import ShadowPromotionGate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
log = logging.getLogger("GovernanceOrchestrator")


class GovernanceOrchestrator:
    """
    Runs the full 4-step governance loop.

    Parameters
    ----------
    active_config_path : path to the active production config JSON.
    bitnet_bin         : path to the BitNet inference binary.
    model_path         : path to the BitNet model weights.
    audit_log_path     : path for governance_audit.jsonl.
    prompt_path        : path where meta_prompt.txt is written/read.
    """

    def __init__(
        self,
        active_config_path: str = "configs/production/v1_multi_2026_03.json",
        bitnet_bin: str = "./bitnet/bin/main",
        model_path: str = "./models/bitnet_b1_58_70b.gguf",
        audit_log_path: str = "logs/governance_audit.jsonl",
        prompt_path: str = "logs/meta_prompt.txt",
    ) -> None:
        self.prompt_path = prompt_path
        self.executor = MetaGovernorExecutor(
            bitnet_bin=bitnet_bin,
            model_path=model_path,
            audit_log_path=audit_log_path,
        )
        self.shadow_gate = ShadowPromotionGate(
            active_config_path=active_config_path,
        )

    def run(
        self,
        collector_log: str,
        trades_csv: str,
        baseline_pnl: float,
    ) -> dict:
        """
        Execute the full 4-step governance loop.

        Parameters
        ----------
        collector_log : path to Collector JSONL output (decisions).
        trades_csv    : path to backtest trades CSV (outcomes with pnl_rr_net).
        baseline_pnl  : PnL of the current active config on the same data,
                        used as the promotion threshold.

        Returns
        -------
        dict with keys:
            patch     : validated config patch from MetaGovernor (or None if
                        reflection failed).
            promoted  : bool — whether the candidate was promoted.
            reason    : human-readable outcome explanation.
        """
        # ── Step 1+2: Reflection ──────────────────────────────────────────────
        log.info("Step 1/4  Loading and merging decisions + trade outcomes …")
        reflection = ReflectionBuffer(
            logs_path=collector_log,
            trades_path=trades_csv,
        )
        try:
            df = reflection.load_and_merge()
        except Exception as exc:
            log.error("ReflectionBuffer.load_and_merge failed: %s", exc)
            return {"patch": None, "promoted": False, "reason": str(exc)}

        log.info("Step 2/4  Generating prompt payload …")
        prompt = reflection.generate_prompt_payload(df, output_path=self.prompt_path)
        if prompt is None:
            reason = (
                "Insufficient win/loss data for divergence analysis. "
                "Run more backtests before governance."
            )
            log.warning(reason)
            return {"patch": None, "promoted": False, "reason": reason}

        # ── Step 3: MetaGovernor inference ────────────────────────────────────
        log.info("Step 3/4  Running MetaGovernor inference …")
        try:
            raw_output = self.executor.run_inference(prompt_path=self.prompt_path)
            patch = self.executor.extract_and_validate_config(raw_output)
        except (ValueError, KeyError) as exc:
            log.error("MetaGovernor output invalid: %s", exc)
            self.executor.log_governance_event(
                event_type="INFERENCE_FAILED",
                engine_id="meta_governor",
                metrics_snapshot={"error": str(exc)},
                decision={"action": "abort"},
            )
            return {"patch": None, "promoted": False, "reason": str(exc)}

        log.info("Patch extracted: %s", json.dumps(patch))
        self.executor.log_governance_event(
            event_type="PATCH_EXTRACTED",
            engine_id="meta_governor",
            metrics_snapshot={"baseline_pnl": baseline_pnl},
            decision=patch,
        )

        # ── Step 4: Shadow promotion ──────────────────────────────────────────
        log.info("Step 4/4  Staging candidate and running shadow backtest …")
        self.shadow_gate.stage_candidate(patch)

        try:
            shadow_pnl, n_trades = self.shadow_gate.execute_shadow_test()
        except Exception as exc:
            log.error("Shadow backtest failed: %s", exc)
            self.executor.log_governance_event(
                event_type="SHADOW_BACKTEST_FAILED",
                engine_id="shadow_gate",
                metrics_snapshot={"error": str(exc)},
                decision={"action": "abort"},
            )
            return {"patch": patch, "promoted": False, "reason": str(exc)}

        result = self.shadow_gate.promote_if_superior(
            baseline_pnl=baseline_pnl,
            shadow_pnl=shadow_pnl,
            n_shadow_trades=n_trades,
        )

        self.executor.log_governance_event(
            event_type="PROMOTION_DECISION",
            engine_id="shadow_gate",
            metrics_snapshot={
                "baseline_pnl": baseline_pnl,
                "shadow_pnl": shadow_pnl,
                "n_trades": n_trades,
            },
            decision=result,
        )

        log.info("Governance complete. promoted=%s  reason=%s", result["promoted"], result["reason"])
        return {"patch": patch, "promoted": result["promoted"], "reason": result["reason"]}


# ── CLI entry point ───────────────────────────────────────────────────────────

def _parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Run the full CRT governance loop: "
                    "Reflection → MetaGovernor → ShadowGate → Promotion",
    )
    p.add_argument("--collector-log",  required=True,
                   help="Path to Collector JSONL output (logs/collector.jsonl)")
    p.add_argument("--trades-csv",     required=True,
                   help="Path to backtest trades CSV with pnl_rr_net column")
    p.add_argument("--baseline-pnl",   required=True, type=float,
                   help="PnL of active production config (promotion threshold)")
    p.add_argument("--active-config",
                   default="configs/production/v1_multi_2026_03.json",
                   help="Active production config JSON path")
    p.add_argument("--bitnet-bin",     default="./bitnet/bin/main",
                   help="BitNet inference binary path")
    p.add_argument("--model-path",     default="./models/bitnet_b1_58_70b.gguf",
                   help="BitNet model weights path")
    p.add_argument("--audit-log",      default="logs/governance_audit.jsonl",
                   help="Governance audit log path")
    p.add_argument("--prompt-path",    default="logs/meta_prompt.txt",
                   help="Path where meta_prompt.txt is written/read")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    orchestrator = GovernanceOrchestrator(
        active_config_path=args.active_config,
        bitnet_bin=args.bitnet_bin,
        model_path=args.model_path,
        audit_log_path=args.audit_log,
        prompt_path=args.prompt_path,
    )
    result = orchestrator.run(
        collector_log=args.collector_log,
        trades_csv=args.trades_csv,
        baseline_pnl=args.baseline_pnl,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["promoted"] else 1)


if __name__ == "__main__":
    main()
