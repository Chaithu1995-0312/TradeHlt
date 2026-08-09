"""One-shot: prepare PRE/POST worktrees for Phase-1 certification parity."""
from __future__ import annotations

import shutil
from pathlib import Path

import yaml

PRE = Path(r"D:\Tradelatest-pre-p1-cert")
POST = Path(r"D:\Tradelatest-post-p1-cert")
MAIN = Path(r"D:\Tradelatest")

GAUSS_OLD = '''class CRTGaussianScorer:
    """Default no-op scorer. Replaced by CRTCalibratedScorer after phase5 --integrate."""
    def compute(self, features: dict, candle_idx: int):
        return None'''

GAUSS_NEW = '''class CRTGaussianScorer:
    """Default no-op scorer. Replaced by CRTCalibratedScorer after phase5 --integrate.

    Signature matches CRTCalibratedScorer / HeuristicGaussianEngine duck-type:
    ``compute(features, candle_idx, direction=...)`` so the Phase-5 call site
    (``direction=_p5_dir``) never TypeErrors. direction is intentionally ignored —
    this scorer always returns None (no gate).
    """
    def compute(self, features: dict, candle_idx: int, direction: str = "long"):
        return None'''


def apply_gauss(root: Path) -> None:
    p = root / "src" / "runtime" / "backtest_v2.py"
    t = p.read_text(encoding="utf-8")
    if GAUSS_OLD not in t:
        if 'direction: str = "long"' in t and "class CRTGaussianScorer" in t:
            print(f"{root.name}: gauss already fixed")
            return
        raise SystemExit(f"gauss_old not found in {root}")
    p.write_text(t.replace(GAUSS_OLD, GAUSS_NEW), encoding="utf-8")
    print(f"{root.name}: gauss fix applied")


def patch_crt_engine(root: Path) -> None:
    ce = root / "src" / "config_layer" / "crt_engine_v2.py"
    t = ce.read_text(encoding="utf-8")
    if "load_and_validate_state_contracts" in t:
        print(f"{root.name}: crt already has contracts")
        return
    needle = """        self.detector  = RangeDetector(self.config)
        self.telemetry = TelemetryCollector()"""
    insert = """        # Phase-1 state contracts: load + validate once at construction (WHO declarations).
        # Non-mutating — does NOT change gates, formulas, transitions, or model dispatch.
        from config_layer.state_contract_loader import load_and_validate_state_contracts
        self.state_contracts = load_and_validate_state_contracts()
        self.detector  = RangeDetector(self.config)
        self.telemetry = TelemetryCollector()"""
    if needle not in t:
        raise SystemExit("crt inject point missing")
    t = t.replace(needle, insert, 1)
    needle2 = """    # ── Public API ────────────────────────────────────────────

    @staticmethod
    def _intrabar_trigger_price(trade: Trade, candle: Candle) -> float:"""
    insert2 = """    # ── Public API ────────────────────────────────────────────

    def get_state_contract(self, state_id: Optional[str] = None):
        \"\"\"Return the Phase-1 StateContract for ``state_id`` or the current SM state.

        Inspection only — does not resolve features or dispatch models.
        \"\"\"
        sid = state_id or self.state.current_state.name
        return self.state_contracts.get(sid)

    @staticmethod
    def _intrabar_trigger_price(trade: Trade, candle: Candle) -> float:"""
    if needle2 not in t:
        raise SystemExit("crt public api inject missing")
    t = t.replace(needle2, insert2, 1)
    ce.write_text(t, encoding="utf-8")
    print(f"{root.name}: crt_engine_v2 patched")


def inject_active_models(root: Path) -> None:
    main_am = yaml.safe_load((MAIN / "active_models.yaml").read_text(encoding="utf-8"))
    post_am_path = root / "active_models.yaml"
    post_am = yaml.safe_load(post_am_path.read_text(encoding="utf-8"))
    rt = post_am["crt"]["runtime"]
    mrt = main_am["crt"]["runtime"]
    rt["state_contract_schema_version"] = mrt["state_contract_schema_version"]
    rt["state_contracts"] = mrt["state_contracts"]
    if "cached_features_at_retest" in mrt:
        rt["cached_features_at_retest"] = mrt["cached_features_at_retest"]
    post_am_path.write_text(
        yaml.dump(post_am, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"{root.name}: active_models state_contracts injected")


def main() -> None:
    apply_gauss(PRE)
    apply_gauss(POST)
    for rel in [
        "src/config_layer/state_contract.py",
        "src/config_layer/state_contract_loader.py",
        "tests/test_state_contracts.py",
        "tests/test_crt_gaussian_scorer_direction_compat.py",
    ]:
        src = MAIN / rel
        dst = POST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("copied", rel)
    patch_crt_engine(POST)
    inject_active_models(POST)
    print("done")


if __name__ == "__main__":
    main()
