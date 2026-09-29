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

from config_layer.strict_config import require, require_all, require_section

DEFAULT_CONFIG_PATH = Path("configs/research/research_config.json")

_CONSUMER = "ResearchConfig"
_QUAL_KEYS = (
    "min_samples",
    "expectancy_min",
    "pf_min",
    "oos_split",
    "oos_retention_min",
    "n_permutations",
    "significance_alpha",
)


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
    job_kind: str
    # Which cost model prices a trade. "flat_bps" is the historical flat
    # `round_trip_bps` haircut — one number for every instrument. "component_measured"
    # is the decomposed broker model (SEM-015: half-spread + commission + order-type
    # slippage + swap), usable only for an instrument with a MEASURED calibration.
    # Required. Once present it is part of `meaningful` (a declared cost model is a
    # different measured object). Files that omit it fail closed; they are not hashed.
    cost_model: str
    # Path to the `mt5_cost_calibration` manifest `cost_model="component_measured"` binds
    # to. Required together with cost_model=="component_measured" (validated in from_dict).
    # Absent key → None (not a substituted path). Enters `meaningful` only when declared.
    cost_model_manifest_path: str | None
    # Optional [start, end) sub-window of the instrument's full corpus, with symmetric
    # lead-in/tail buffers. Absent key → None (load the whole corpus). When the key is
    # present, start/end/lead_in_bars/tail_bars are all required.
    window: dict | None

    @classmethod
    def from_dict(cls, d: dict) -> "ResearchConfig":
        harness = require_section(d, "harness", consumer=_CONSUMER)
        fw = require_section(d, "forward_walk", consumer=_CONSUMER)
        sig = require_section(d, "signal", consumer=_CONSUMER)
        costs = require_section(d, "costs", consumer=_CONSUMER)
        q = require_section(d, "qualification", consumer=_CONSUMER)
        uni = require_section(d, "universe", consumer=_CONSUMER)
        h = require_all(
            harness, ["warmup", "window_size", "min_samples"],
            section_name="harness", consumer=_CONSUMER,
        )
        fwk = require_all(
            fw, ["max_forward", "trail_mult", "exit_model"],
            section_name="forward_walk", consumer=_CONSUMER,
        )
        sg = require_all(
            sig, ["apply_signal_defaults", "sl_atr_mult", "tp_atr_mult"],
            section_name="signal", consumer=_CONSUMER,
        )
        ck = require_all(
            costs, ["round_trip_bps", "cost_model"],
            section_name="costs", consumer=_CONSUMER,
        )
        qk = require_all(q, _QUAL_KEYS, section_name="qualification", consumer=_CONSUMER)
        uk = require_all(
            uni, ["data_dir", "pattern", "instruments"],
            section_name="universe", consumer=_CONSUMER,
        )
        job_kind = str(require(d, "job_kind", section_name="research", consumer=_CONSUMER))

        cost_model = str(ck["cost_model"])
        meaningful = {
            "harness": {
                "warmup": int(h["warmup"]),
                "window_size": int(h["window_size"]),
                "min_samples": int(h["min_samples"]),
            },
            "forward_walk": {
                "max_forward": int(fwk["max_forward"]),
                "trail_mult": float(fwk["trail_mult"]),
                "exit_model": str(fwk["exit_model"]),
            },
            "signal": {
                "apply_signal_defaults": bool(sg["apply_signal_defaults"]),
                "sl_atr_mult": float(sg["sl_atr_mult"]),
                "tp_atr_mult": float(sg["tp_atr_mult"]),
            },
            "costs": {
                "round_trip_bps": float(ck["round_trip_bps"]),
                "cost_model": cost_model,
            },
            "qualification": {
                "min_samples": int(qk["min_samples"]),
                "expectancy_min": float(qk["expectancy_min"]),
                "pf_min": float(qk["pf_min"]),
                "oos_split": float(qk["oos_split"]),
                "oos_retention_min": float(qk["oos_retention_min"]),
                "n_permutations": int(qk["n_permutations"]),
                "significance_alpha": float(qk["significance_alpha"]),
            },
            "universe": {
                "data_dir": str(uk["data_dir"]),
                "pattern": str(uk["pattern"]),
                "instruments": uk["instruments"],
            },
        }
        # `entry_ttl` enters the canonical dict only when the JSON carries it.
        # Absence is not a substituted integer (one-arg presence check).
        if "entry_ttl" in fw:
            meaningful["forward_walk"]["entry_ttl"] = int(fw["entry_ttl"])

        _valid_cost_models = {"flat_bps", "component_measured"}
        if cost_model not in _valid_cost_models:
            raise ValueError(
                f"ResearchConfig.cost_model={cost_model!r} is not one of "
                f"{sorted(_valid_cost_models)} (SEM-015: declare the cost model explicitly; "
                "an unrecognised value must never silently fall back to the flat haircut)."
            )

        if "cost_model_manifest_path" in costs:
            cost_model_manifest_path = costs["cost_model_manifest_path"]
        else:
            cost_model_manifest_path = None
        if cost_model == "component_measured" and not cost_model_manifest_path:
            raise ValueError(
                "ResearchConfig: cost_model='component_measured' requires "
                "costs.cost_model_manifest_path (the mt5_cost_calibration manifest to bind) "
                "— refusing to silently fall back to an unmeasured default."
            )
        if cost_model_manifest_path is not None:
            meaningful["costs"]["cost_model_manifest_path"] = str(cost_model_manifest_path)

        window: dict | None = None
        if "window" in d and d["window"] is not None:
            window_raw = require_section(d, "window", consumer=_CONSUMER)
            wk = require_all(
                window_raw, ["start", "end", "lead_in_bars", "tail_bars"],
                section_name="window", consumer=_CONSUMER,
            )
            window = {
                "start": str(wk["start"]),
                "end": str(wk["end"]),
                "lead_in_bars": int(wk["lead_in_bars"]),
                "tail_bars": int(wk["tail_bars"]),
            }
            meaningful["window"] = dict(window)

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
            cost_model=cost_model,
            cost_model_manifest_path=(
                str(cost_model_manifest_path) if cost_model_manifest_path is not None else None
            ),
            window=window,
        )

    @classmethod
    def from_file(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "ResearchConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def sha256(self) -> str:
        return hashlib.sha256(self._canonical.encode("utf-8")).hexdigest()
