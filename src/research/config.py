"""config.py — ResearchConfig: the single source of truth for the research harness.

Loaded from configs/research/research_config.json. No tunable lives in Python. The
config's SHA-256 (over its canonical JSON) is stamped into every EdgeReport so any
result is reproducible and the M5 ledger can verify provenance trivially.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("configs/research/research_config.json")


@dataclass(frozen=True)
class ResearchConfig:
    # harness
    warmup: int
    window_size: int
    min_samples: int
    # forward-walk envelope
    max_forward: int
    trail_mult: float
    exit_model: str                  # "intrabar_fixed" (governing truth) | "trailing" (opt-in)
    entry_ttl: int | None            # OCO straddle fill window (bars); None = no oco support
    # signal geometry (config-authoritative when apply_signal_defaults)
    apply_signal_defaults: bool
    sl_atr_mult: float
    tp_atr_mult: float
    # costs
    round_trip_bps: float
    # M4 qualification gate
    q_min_samples: int
    q_expectancy_min: float
    q_pf_min: float
    q_oos_split: float
    q_oos_retention_min: float
    q_n_permutations: int
    q_significance_alpha: float
    # universe
    data_dir: str
    pattern: str
    instruments: object              # "ALL" | list[str]
    # provenance
    _canonical: str                  # canonical JSON of the meaningful keys (for hashing)
    # §13 item6 / §14.D — declares what KIND of research activity this config
    # drives: "threshold_search" (strategy/gate tuning) | "model_retrain"
    # (fitting a new model artifact) | "unspecified" (legacy configs; no claim).
    # A single string field, not two flags, so "declaring both" is structurally
    # impossible rather than something a validator has to catch. Process
    # metadata only — deliberately OUTSIDE `meaningful`/`_canonical` so adding
    # it never changes any existing config's config_sha256 (same precedent as
    # the conditional `entry_ttl` guard below).
    job_kind: str = "unspecified"

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchConfig":
        harness = d.get("harness", {})
        fw = d.get("forward_walk", {})
        sig = d.get("signal", {})
        costs = d.get("costs", {})
        q = d.get("qualification", {})
        uni = d.get("universe", {})

        meaningful = {
            "harness": {
                "warmup": int(harness["warmup"]),
                "window_size": int(harness["window_size"]),
                "min_samples": int(harness["min_samples"]),
            },
            "forward_walk": {
                "max_forward": int(fw["max_forward"]),
                "trail_mult": float(fw["trail_mult"]),
                "exit_model": str(fw.get("exit_model", "intrabar_fixed")),
            },
            "signal": {
                "apply_signal_defaults": bool(sig["apply_signal_defaults"]),
                "sl_atr_mult": float(sig["sl_atr_mult"]),
                "tp_atr_mult": float(sig["tp_atr_mult"]),
            },
            "costs": {"round_trip_bps": float(costs["round_trip_bps"])},
            "qualification": {
                "min_samples": int(q.get("min_samples", 30)),
                "expectancy_min": float(q.get("expectancy_min", 0.0)),
                "pf_min": float(q.get("pf_min", 1.0)),
                "oos_split": float(q.get("oos_split", 0.3)),
                "oos_retention_min": float(q.get("oos_retention_min", 0.5)),
                "n_permutations": int(q.get("n_permutations", 2000)),
                "significance_alpha": float(q.get("significance_alpha", 0.05)),
            },
            "universe": {
                "data_dir": str(uni["data_dir"]),
                "pattern": str(uni["pattern"]),
                "instruments": uni.get("instruments", "ALL"),
            },
        }
        # sha-parity (load-bearing): `entry_ttl` (Program-9 OCO straddle) enters the
        # canonical dict ONLY when the JSON carries it — every pre-existing config keeps
        # its published config_sha256 byte-identical.
        if "entry_ttl" in fw:
            meaningful["forward_walk"]["entry_ttl"] = int(fw["entry_ttl"])

        job_kind = str(d.get("job_kind", "unspecified"))
        _valid_job_kinds = {"threshold_search", "model_retrain", "unspecified"}
        if job_kind not in _valid_job_kinds:
            raise ValueError(
                f"ResearchConfig.job_kind={job_kind!r} is not one of {sorted(_valid_job_kinds)} "
                "(§5 rule 4: threshold search and model retrain are two separate research "
                "activities — declare exactly one)."
            )
        return cls(
            warmup=meaningful["harness"]["warmup"],
            window_size=meaningful["harness"]["window_size"],
            min_samples=meaningful["harness"]["min_samples"],
            max_forward=meaningful["forward_walk"]["max_forward"],
            trail_mult=meaningful["forward_walk"]["trail_mult"],
            exit_model=meaningful["forward_walk"]["exit_model"],
            entry_ttl=meaningful["forward_walk"].get("entry_ttl"),
            apply_signal_defaults=meaningful["signal"]["apply_signal_defaults"],
            sl_atr_mult=meaningful["signal"]["sl_atr_mult"],
            tp_atr_mult=meaningful["signal"]["tp_atr_mult"],
            round_trip_bps=meaningful["costs"]["round_trip_bps"],
            q_min_samples=meaningful["qualification"]["min_samples"],
            q_expectancy_min=meaningful["qualification"]["expectancy_min"],
            q_pf_min=meaningful["qualification"]["pf_min"],
            q_oos_split=meaningful["qualification"]["oos_split"],
            q_oos_retention_min=meaningful["qualification"]["oos_retention_min"],
            q_n_permutations=meaningful["qualification"]["n_permutations"],
            q_significance_alpha=meaningful["qualification"]["significance_alpha"],
            data_dir=meaningful["universe"]["data_dir"],
            pattern=meaningful["universe"]["pattern"],
            instruments=meaningful["universe"]["instruments"],
            _canonical=json.dumps(meaningful, sort_keys=True, separators=(",", ":")),
            job_kind=job_kind,
        )

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "ResearchConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def sha256(self) -> str:
        return hashlib.sha256(self._canonical.encode("utf-8")).hexdigest()
