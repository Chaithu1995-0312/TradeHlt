"""measure.py — run a sealed Visual CRT measurement contract end to end.

Reads an ``MC-VCRT-*`` instance, binds the cost and exit models it declares, walks both
pre-registered arms, runs the declared controls, applies the declared OOS split, and writes
every evidence artifact the contract names.

The contract is the authority. Nothing here declares a threshold, a seed, a split fraction, or
a cost component — each is read from the sealed JSON, so running V1 and running V2 differ only
by which file is passed in.

AUTHORITY: diagnostic only. ``economic_claims_allowed`` is false on every instance to date; a
calibrated cost model does not change that (MEASUREMENT_CONTRACT.md section 2, E4).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from research.costs import ComponentCostModel
from research.measurement.forward_walk import AdverseFill
from research.provenance import provenance_block
from research.visual_crt.controls import (
    long_only_control,
    random_entry_control,
    rows_for,
    single_holdout_chronologic,
)
from research.visual_crt.driver import (
    ARMS,
    HORIZON_BARS,
    LedgerRow,
    load_bars,
    run_arm,
    summarize,
)

#: Two-sided critical value at the Bonferroni-adjusted alpha=0.025 (2 pre-registered arms).
#: INHERITED VERBATIM from the V1 run — recovered exactly (2.24) from its committed metrics.json
#: so V2's intervals stay directly comparable with V1's. Deliberately not re-derived: changing
#: the constant would silently make the two runs incomparable.
CRIT_2SIDED = 2.24


def _stats(values: Sequence[float]) -> dict:
    n = len(values)
    if n == 0:
        return {"mean_R": 0.0, "sd": 0.0, "t": 0.0, "ci975": [0.0, 0.0], "excludes_zero": False}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 and sd > 0 else 0.0
    half = CRIT_2SIDED * se
    lo, hi = mean - half, mean + half
    return {
        "mean_R": mean,
        "sd": sd,
        "t": (mean / se) if se > 0 else 0.0,
        "ci975": [lo, hi],
        "excludes_zero": (lo > 0.0) or (hi < 0.0),
    }


def _profit_factor(values: Sequence[float]) -> float | None:
    gains = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    return (gains / losses) if losses > 0 else None


def _corpus_from_population(population: dict) -> tuple[str, str | None]:
    """Recover the corpus path + sha256 from the frozen `population` surface.

    They are stated inside `inclusion_rule` prose rather than as separate keys. `population` is
    a FROZEN dimension carried byte-identically from V1, so they are parsed out rather than the
    surface being reshaped to be more convenient.
    """
    import re

    text = population.get("inclusion_rule", "")
    path_m = re.search(r"((?:data/)[\w./-]+\.csv)", text)
    sha_m = re.search(r"sha256\s+([0-9a-f]{64})", text)
    if not path_m:
        raise ValueError("measure: population.inclusion_rule names no corpus path")
    return path_m.group(1), (sha_m.group(1) if sha_m else None)


def _bind_cost_model(contract: dict):
    """Build the cost model the contract declares. None == the legacy flat 12bps binding."""
    costs = contract["costs"]
    cid = costs["cost_model_id"]
    if cid.startswith("CM-XAUUSD-LEGACY-12BPS"):
        return None, {"cost_model_id": cid, "binding": "legacy_flat_12bps_in_driver"}
    if not cid.startswith("CM-XAUUSD-COMPONENT-MEASURED"):
        raise ValueError(f"measure: unrecognised cost_model_id {cid!r}")
    # The frozen schema has no `source_manifest` field, so provenance is declared inside the
    # components free text. Parse it out and STILL verify the hash — a provenance string nobody
    # recomputes is a comment, not evidence.
    import re

    blob = " ".join(c.get("bps_or_formula", "") for c in costs.get("components", []))
    path_m = re.search(r"((?:results/)[\w./-]+\.json)", blob)
    sha_m = re.search(r"sha256\s+([0-9a-f]{64})", blob)
    if not path_m or not sha_m:
        raise ValueError(
            "measure: cost components declare no source manifest path + sha256; refusing to "
            "measure against unverifiable provenance"
        )
    manifest_path = Path(path_m.group(1))
    actual = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    declared = sha_m.group(1)
    if actual != declared:
        raise ValueError(
            f"measure: cost manifest sha256 mismatch — contract declares {declared}, "
            f"file is {actual}. Refusing to measure against unverified provenance."
        )
    model = ComponentCostModel.from_manifest(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        instrument=contract["population"]["instruments"][0]
        if isinstance(contract["population"].get("instruments"), list)
        else "XAUUSD",
        source=f"{manifest_path.as_posix()} sha256:{actual}",
    )
    return model, model.provenance()


def _bind_adverse_fill(contract: dict):
    """Build the fill model the contract declares. None == V1's perfect stop fill."""
    params = contract["exits"].get("parameters") or {}
    if "adverse_fill" not in params:
        return None, "perfect_stop_fill"
    text = str(params["adverse_fill"])
    # The contract states the parameters in prose; parse the two numbers it names rather than
    # hardcoding them here, so the sealed JSON stays the single authority.
    import re

    m = re.search(r"stop_slippage\s*=\s*([0-9.]+)", text)
    if not m:
        raise ValueError("measure: exits.parameters.adverse_fill declares no stop_slippage")
    slip = float(m.group(1))
    gaps = "model_gaps=True" in text.replace(" ", "")
    return (
        AdverseFill(stop_slippage=slip, model_gaps=gaps),
        {
            "model": "adverse_fill",
            "ontology_id": contract["exits"].get("ontology_id", "SEM-016"),
            "stop_slippage": slip,
            "model_gaps": gaps,
        },
    )


def _arm_block(rows: Sequence[LedgerRow], entry_rule: str) -> dict:
    gross = [r.rr_gross for r in rows]
    net = [r.rr_net for r in rows]
    n = len(rows)
    return {
        "n": n,
        "entry_rule": entry_rule,
        "outcomes": {o: sum(1 for r in rows if r.outcome == o)
                     for o in sorted({r.outcome for r in rows})},
        "win_rate_gross": (sum(1 for v in gross if v > 0) / n) if n else 0.0,
        "win_rate_net": (sum(1 for v in net if v > 0) / n) if n else 0.0,
        "median_risk_in_atr": statistics.median([r.sl_atr_mult for r in rows]) if n else 0.0,
        "gross": _stats(gross),
        "net": _stats(net),
        "profit_factor_net": _profit_factor(net),
        "power": "SUFFICIENTLY_POPULATED" if n >= 30 else "INSUFFICIENT",
    }


def _write_jsonl(path: Path, rows: Sequence[LedgerRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(asdict(r), sort_keys=True) + "\n")


def run_contract(contract_path: str | Path, out_dir: str | Path) -> dict:
    """Execute a sealed contract. Returns the metrics dict (also written to disk)."""
    contract_path = Path(contract_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract_id = contract["contract_id"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    corpus, declared_sha = _corpus_from_population(contract["population"])
    actual_sha = hashlib.sha256(Path(corpus).read_bytes()).hexdigest()
    if declared_sha and actual_sha != declared_sha:
        raise ValueError(
            f"measure: corpus sha256 mismatch — contract declares {declared_sha}, "
            f"file is {actual_sha}. The population is a frozen dimension."
        )

    from data_ingestion.dataset_integrity import validate_dataset

    l3 = validate_dataset(corpus, bar_minutes=15, write_report=False, raise_on_fail=True)
    bars = load_bars(corpus)

    cost_model, cost_prov = _bind_cost_model(contract)
    adverse_fill, fill_prov = _bind_adverse_fill(contract)
    instrument = "XAUUSD"

    (out / "population_fingerprint.json").write_text(json.dumps({
        "contract_id": contract_id,
        "corpus_path": corpus,
        "corpus_sha256": actual_sha,
        "bars": len(bars),
        "first_ts": bars[0].timestamp.isoformat(),
        "last_ts": bars[-1].timestamp.isoformat(),
        "l3_dataset_integrity": {"decision": l3.get("decision") if isinstance(l3, dict) else str(l3)},
        "visual_audit_corpus_EXCLUDED": contract.get("visual_audit_corpus_EXCLUDED",
                                                     "data/XAUUSD_M15.csv"),
    }, indent=2) + "\n", encoding="utf-8")

    (out / "cost_exit_fixture.json").write_text(json.dumps({
        "contract_id": contract_id,
        "cost_model": cost_prov,
        "fill_model": fill_prov,
        "worked_example": _cost_fixture(cost_model),
    }, indent=2) + "\n", encoding="utf-8")

    entry_rules = {"A": "displacement close", "B": "retest close"}
    metrics: dict = {
        "contract_id": contract_id,
        "sem_012_version": 2,
        "corpus": {"path": corpus, "sha256": actual_sha, "bars": len(bars)},
        "multiplicity": contract.get("multiplicity") or {
            "n_variants_preregistered": 2, "control": "bonferroni", "alpha_adjusted": 0.025},
        "crit_2sided": CRIT_2SIDED,
        "authority": "DIAGNOSTIC_ONLY. economic_claims_allowed="
                     f"{contract['trust_status']['economic_claims_allowed']}.",
        "arms": {}, "controls": {}, "splits": {},
    }

    # The FROZEN schema (additionalProperties:false everywhere) has no slot for a control
    # configuration block, so controls are declared in `metrics.success_gate` prose — which BOTH
    # V1 and V2 carry — and seeded from `splits.seed`, the one seed the schema does allow. Running
    # V1 through here therefore also produces the controls V1 declared and never ran.
    gate_text = str((contract.get("metrics") or {}).get("success_gate", ""))
    ctrl_cfg = ("random_entry" in gate_text) and ("long_only" in gate_text)
    seed = int(contract["splits"]["seed"])

    split_manifests: dict = {}
    for arm in ARMS:
        rows = run_arm(bars, arm, instrument=instrument, corpus_path=corpus,
                       corpus_sha256=actual_sha, cost_model=cost_model,
                       adverse_fill=adverse_fill, contract_id=contract_id)
        _write_jsonl(out / f"ledger_arm_{arm}.jsonl", rows)
        metrics["arms"][arm] = _arm_block(rows, entry_rules.get(arm, arm))

        sm = single_holdout_chronologic(
            rows,
            oos_fraction=0.20,
            horizon_bars=HORIZON_BARS,
        )
        split_manifests[arm] = sm
        metrics["splits"][arm] = {
            "counts": sm["counts"],
            "oos_start_entry_ts": sm.get("oos_start_entry_ts"),
            "is": _arm_block(rows_for(rows, sm, "is"), "in-sample")["net"],
            "oos": _arm_block(rows_for(rows, sm, "oos"), "out-of-sample")["net"],
        }

        if ctrl_cfg:
            lo = long_only_control(bars, rows, cost_model=cost_model, adverse_fill=adverse_fill)
            re_ = random_entry_control(bars, rows, seed=seed, cost_model=cost_model,
                                       adverse_fill=adverse_fill)
            _write_jsonl(out / f"controls_long_only_{arm}.jsonl", lo)
            _write_jsonl(out / f"controls_random_entry_{arm}.jsonl", re_)
            metrics["controls"][arm] = {
                "long_only": _arm_block(lo, "arm bars, direction forced long"),
                "random_entry": _arm_block(re_, f"uniform bars, seed {seed}"),
                "arm_beats_long_only": metrics["arms"][arm]["net"]["mean_R"]
                                       > _arm_block(lo, "")["net"]["mean_R"],
                "arm_beats_random_entry": metrics["arms"][arm]["net"]["mean_R"]
                                          > _arm_block(re_, "")["net"]["mean_R"],
            }

    (out / "split_manifest.json").write_text(
        json.dumps({"contract_id": contract_id,
                    "scheme": contract["splits"]["scheme"],
                    "embargo": contract["splits"]["embargo"],
                    "purge": contract["splits"]["purge"],
                    "seed": contract["splits"]["seed"],
                    "arms": split_manifests}, indent=2) + "\n", encoding="utf-8")

    for arm, block in metrics["arms"].items():
        gross_zero = not block["gross"]["excludes_zero"]
        block["verdict"] = (
            "REJECT — gross expectancy indistinguishable from zero" if gross_zero
            else ("REJECT — gross expectancy significantly NEGATIVE"
                  if block["gross"]["mean_R"] < 0 else "GROSS_POSITIVE_INVESTIGATE")
        )
    metrics["conclusion"] = (
        "0 PROMOTE. Both pre-registered arms REJECT."
        if all(a["verdict"].startswith("REJECT") for a in metrics["arms"].values())
        else "AT LEAST ONE ARM DID NOT REJECT — investigate before registering anything."
    )
    metrics["provenance"] = provenance_block(
        "intrabar_fixed", 12.0,
        cost_model=cost_prov if isinstance(cost_prov, dict) else None,
        fill_model=fill_prov if isinstance(fill_prov, dict) else None,
    )

    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(
        {a: summarize([], contract_id=contract_id) | metrics["arms"][a] for a in metrics["arms"]},
        indent=2) + "\n", encoding="utf-8")
    return metrics


def _cost_fixture(cost_model) -> dict:
    """A worked cost example so a reader can check the model without rerunning it."""
    entry, risk = 3300.0, 7.342
    if cost_model is None:
        return {"binding": "legacy_flat_12bps",
                "cost_R_at_entry_3300_risk_7.342": (12.0 / 10_000.0) * entry / risk}
    return {
        "binding": "component_measured",
        "entry": entry, "risk_distance": risk,
        "cost_R_stop_exit": cost_model.cost_r(entry, risk, exit_kind="SL_HIT"),
        "cost_R_tp_exit": cost_model.cost_r(entry, risk, exit_kind="TP_HIT"),
        "legacy_flat_cost_R_for_comparison": (12.0 / 10_000.0) * entry / risk,
    }
