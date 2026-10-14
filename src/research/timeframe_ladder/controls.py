"""Pre-registered verdict, cluster bootstrap, and matched controls.

CONTINUE needs n_clusters >= 30. Below that the verdict is INSUFFICIENT and
these functions must not be asked to publish a gate. They exist so the rule
is tested on synthetic numbers before any corpus result is read.
"""

from __future__ import annotations

import random

N_CLUSTERS_MIN = 30
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 20261005
N_RANDOM_SEEDS = 100
RANDOM_SEED0 = 20261005


def verdict(
    *,
    n_clusters: int | None,
    ci_low_vs_drift: float | None = None,
    random_percentile: float | None = None,
    long_ci_low: float | None = None,
    short_ci_low: float | None = None,
) -> dict:
    """Return the pre-registered label. n_clusters < 30 ignores every other input."""
    if n_clusters is None or int(n_clusters) < N_CLUSTERS_MIN:
        return {
            "verdict": "INSUFFICIENT",
            "failing_condition": "n_clusters < 30",
            "expectancy_published": False,
        }
    fails: list[str] = []
    if ci_low_vs_drift is None or not (ci_low_vs_drift > 0):
        fails.append("ci_lower_vs_drift")
    if random_percentile is None or not (random_percentile > 95):
        fails.append("random_percentile")
    long_ok = long_ci_low is not None and long_ci_low > 0
    short_ok = short_ci_low is not None and short_ci_low > 0
    if not long_ok:
        fails.append("long_vs_drift")
    if not short_ok:
        fails.append("short_vs_drift")
    # One side clears its own drift and the other does not: a named directional
    # outcome. Both missing, or both failing, stay the plain side tokens.
    if long_ci_low is not None and short_ci_low is not None and long_ok != short_ok:
        fails.append("directional_gold_beta")
    if fails:
        return {
            "verdict": "STOP",
            "failing_condition": ",".join(fails),
            "expectancy_published": True,
        }
    return {"verdict": "CONTINUE", "failing_condition": None, "expectancy_published": True}


def passive_drift_r(entry: float, mark: float, risk: float, direction: str) -> float:
    """Close-to-close drift over the holding window, in the trade's R units.

    This is the beta control: same entry, same exit bar, same risk distance,
    no stop and no target. Direction is the passive book's direction.
    """
    if risk <= 0:
        raise ValueError(f"passive_drift_r: risk must be positive, got {risk}")
    side = str(direction).strip().lower()
    if side in ("long", "buy"):
        signed = float(mark) - float(entry)
    elif side in ("short", "sell"):
        signed = float(entry) - float(mark)
    else:
        raise ValueError(f"direction must be long or short, got {direction!r}")
    return signed / float(risk)


def percentile_rank(value: float, sample: list[float]) -> float:
    """Percent of the sample strictly below `value`. Above the 95th means > 95."""
    if not sample:
        raise ValueError("percentile_rank: empty sample")
    below = sum(1 for x in sample if x < value)
    return 100.0 * below / len(sample)


def cluster_bootstrap_mean_ci(
    groups: list[list[float]],
    *,
    seed: int = BOOTSTRAP_SEED,
    draws: int = BOOTSTRAP_DRAWS,
) -> dict:
    """Percentile 95% CI of the size-weighted mean. Resamples whole clusters."""
    if not groups or any(len(g) == 0 for g in groups):
        raise ValueError("cluster_bootstrap_mean_ci: every cluster needs at least one value")
    if draws < 2:
        raise ValueError("cluster_bootstrap_mean_ci: draws must be >= 2")
    flat = [x for g in groups for x in g]
    point = sum(flat) / len(flat)
    rng = random.Random(seed)
    k = len(groups)
    samples = []
    for _ in range(draws):
        picked = [groups[rng.randrange(k)] for _ in range(k)]
        pooled = [x for g in picked for x in g]
        samples.append(sum(pooled) / len(pooled))
    samples.sort()
    low = samples[int(0.025 * (draws - 1))]
    high = samples[int(0.975 * (draws - 1))]
    return {"mean": point, "low": low, "high": high, "draws": draws, "seed": seed}


def random_seeds() -> list[int]:
    return [RANDOM_SEED0 + i for i in range(N_RANDOM_SEEDS)]


def random_entry_means(
    closes: list[float],
    templates: list[dict],
    seeds: list[int],
) -> list[float]:
    """One mark-to-close mean per seed. Not a second BacktestRunner.

    Each template carries `direction`, `holding` (bars after the entry bar), and
    `risk`. A seed draws one start bar per template among bars that still have
    `holding` closes ahead, then averages `passive_drift_r` across the templates.
    """
    if not templates:
        raise ValueError("random_entry_means: no templates")
    if not seeds:
        raise ValueError("random_entry_means: no seeds")
    means: list[float] = []
    for seed in seeds:
        rng = random.Random(int(seed))
        sample: list[float] = []
        for spec in templates:
            holding = int(spec["holding"])
            if holding < 0:
                raise ValueError(f"random_entry_means: negative holding {holding}")
            last = len(closes) - 1 - holding
            if last < 0:
                raise ValueError(
                    f"random_entry_means: series length {len(closes)} cannot hold {holding} bars"
                )
            start = rng.randrange(0, last + 1)
            sample.append(
                passive_drift_r(
                    closes[start],
                    closes[start + holding],
                    float(spec["risk"]),
                    str(spec["direction"]),
                )
            )
        means.append(sum(sample) / len(sample))
    return means
