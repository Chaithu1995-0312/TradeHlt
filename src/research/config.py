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
    # Which cost model prices a trade. "flat_bps" (default) is the historical flat
    # `round_trip_bps` haircut — one number for every instrument. "component_measured"
    # is the decomposed broker model (SEM-015: half-spread + commission + order-type
    # slippage + swap), usable only for an instrument with a MEASURED calibration.
    # Like `entry_ttl` above, this enters `meaningful` ONLY when the JSON declares it,
    # so every pre-existing config keeps its published config_sha256 byte-identical.
    cost_model: str = "flat_bps"
    # Path to the `mt5_cost_calibration` manifest `cost_model="component_measured"` binds
    # to. Required together with cost_model=="component_measured" (validated in from_dict);
    # ignored/absent otherwise. Same sha-parity precedent as `cost_model` itself — enters
    # `meaningful` only when declared, and only ever declared alongside a non-default
    # cost_model, so no pre-existing flat-bps config's hash moves.
    cost_model_manifest_path: str | None = None
    # Optional [start, end) sub-window of the instrument's full corpus, with symmetric
    # lead-in/tail buffers so bars just inside the window still get a full detect window
    # behind them and a full forward-walk future ahead of them (never right- or
    # left-censored by the slice boundary). None (default) = load the whole corpus,
    # byte-identical to every config written before this field existed — same sha-parity
    # precedent as `entry_ttl`/`cost_model`. Consumed by `HypothesisRunner._load_candles`
    # via `data_ingestion.corpus_store.read`; the plain `CandleLoader` path is untouched
    # when this is absent.
    window: dict | None = None

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

        # sha-parity (load-bearing, same precedent as `entry_ttl` directly above):
        # `cost_model` enters the canonical dict ONLY when the JSON carries it. All 23
        # pre-existing ResearchConfig files omit it and keep their published
        # config_sha256 byte-identical. A config that DOES declare it is measuring a
        # different object and correctly gets a different hash.
        if "cost_model" in costs:
            meaningful["costs"]["cost_model"] = str(costs["cost_model"])

        cost_model = str(costs.get("cost_model", "flat_bps"))
        _valid_cost_models = {"flat_bps", "component_measured"}
        if cost_model not in _valid_cost_models:
            raise ValueError(
                f"ResearchConfig.cost_model={cost_model!r} is not one of "
                f"{sorted(_valid_cost_models)} (SEM-015: declare the cost model explicitly; "
                "an unrecognised value must never silently fall back to the flat haircut)."
            )

        cost_model_manifest_path = costs.get("cost_model_manifest_path")
        if cost_model == "component_measured" and not cost_model_manifest_path:
            raise ValueError(
                "ResearchConfig: cost_model='component_measured' requires "
                "costs.cost_model_manifest_path (the mt5_cost_calibration manifest to bind) "
                "— refusing to silently fall back to an unmeasured default."
            )
        if cost_model_manifest_path is not None:
            meaningful["costs"]["cost_model_manifest_path"] = str(cost_model_manifest_path)

        window_raw = d.get("window")
        window: dict | None = None
        if window_raw is not None:
            missing = [k for k in ("start", "end") if k not in window_raw]
            if missing:
                raise ValueError(
                    f"ResearchConfig.window is missing required key(s) {missing} "
                    "(a window needs both a start and an end — an open-ended window "
                    "is not supported, it would silently read to the corpus's own edge)."
                )
            window = {
                "start": str(window_raw["start"]),
                "end": str(window_raw["end"]),
                "lead_in_bars": int(window_raw.get("lead_in_bars", 120)),
                "tail_bars": int(window_raw.get("tail_bars", 60)),
            }
            meaningful["window"] = dict(window)

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
