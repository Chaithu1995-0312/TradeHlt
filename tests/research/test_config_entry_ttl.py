"""Program 9 — ResearchConfig `entry_ttl`: parsed when present, sha-NEUTRAL when absent.

The load-bearing invariant: `entry_ttl` enters the canonical (hashed) JSON ONLY when the
config file carries it, so every pre-existing config keeps its published config_sha256
byte-identical (the sha is stamped into every published edge_report / qualification
artifact). Enforced here over ALL configs/research/*.json on disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.config import ResearchConfig                               # noqa: E402

_CFG = {
    "harness": {"warmup": 20, "window_size": 64, "min_samples": 10},
    "forward_walk": {"max_forward": 20, "trail_mult": 0.5},
    "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
    "costs": {"round_trip_bps": 12.0},
    "universe": {"data_dir": "data", "pattern": "*_M15.csv", "instruments": "ALL"},
}


def test_absent_entry_ttl_is_none_and_not_canonicalized():
    cfg = ResearchConfig.from_dict(_CFG)
    assert cfg.entry_ttl is None
    assert "entry_ttl" not in cfg._canonical


def test_present_entry_ttl_is_parsed_and_hashed():
    d = {k: dict(v) for k, v in _CFG.items()}
    d["forward_walk"]["entry_ttl"] = 12
    cfg = ResearchConfig.from_dict(d)
    assert cfg.entry_ttl == 12
    assert '"entry_ttl":12' in cfg._canonical
    # presence changes the hash BY DESIGN (it is a meaningful knob when declared)
    assert cfg.sha256() != ResearchConfig.from_dict(_CFG).sha256()


def test_every_existing_research_config_stays_sha_stable():
    """No config predating Program 9 carries entry_ttl -> none may canonicalize it."""
    cfg_dir = _ROOT / "configs" / "research"
    paths = sorted(cfg_dir.glob("*.json"))
    assert paths, f"no research configs found under {cfg_dir}"
    checked = 0
    for p in paths:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if "harness" not in raw:
            continue                      # driver-specific config, not a ResearchConfig
        checked += 1
        cfg = ResearchConfig.from_file(p)
        if "entry_ttl" in raw.get("forward_walk", {}):
            assert cfg.entry_ttl == int(raw["forward_walk"]["entry_ttl"]), p.name
        else:
            assert cfg.entry_ttl is None, p.name
            assert "entry_ttl" not in cfg._canonical, (
                f"{p.name}: entry_ttl leaked into the canonical hash of a config that "
                f"does not declare it — this silently changes its published config_sha256")
    assert checked > 0, "no ResearchConfig-format files were checked"


def test_entry_ttl_absent_reproduces_legacy_canonical_bytes():
    """The canonical JSON without entry_ttl must be EXACTLY the pre-Program-9 shape
    (regression pin: rebuilding the dict by hand yields the same canonical string)."""
    cfg = ResearchConfig.from_dict(_CFG)
    legacy = {
        "costs": {"round_trip_bps": 12.0},
        "forward_walk": {"exit_model": "intrabar_fixed", "max_forward": 20, "trail_mult": 0.5},
        "harness": {"min_samples": 10, "warmup": 20, "window_size": 64},
        "qualification": {"expectancy_min": 0.0, "min_samples": 30, "n_permutations": 2000,
                          "oos_retention_min": 0.5, "oos_split": 0.3,
                          "pf_min": 1.0, "significance_alpha": 0.05},
        "signal": {"apply_signal_defaults": True, "sl_atr_mult": 1.0, "tp_atr_mult": 2.0},
        "universe": {"data_dir": "data", "instruments": "ALL", "pattern": "*_M15.csv"},
    }
    assert cfg._canonical == json.dumps(legacy, sort_keys=True, separators=(",", ":"))
