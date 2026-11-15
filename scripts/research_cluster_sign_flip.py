"""Research-only exact cluster sign-flip sensitivity for paired forecast losses.

Sharp-null diagnostic conditional on cluster-level sign exchangeability.
Not a valid model-selection p-value on reused exploratory observations.
"""
from __future__ import annotations

import itertools
import math
from collections import defaultdict


def sign_flip_sensitivity(differences: list[float], clusters: list[str]) -> dict:
    if len(differences) != len(clusters) or not differences:
        raise ValueError("nonempty aligned losses and cluster keys required")
    if not all(math.isfinite(d) for d in differences):
        raise ValueError("nonfinite loss difference")
    grouped: dict[str, list[float]] = defaultdict(list)
    for difference, key in zip(differences, clusters, strict=True):
        if not key:
            raise ValueError("empty cluster key")
        grouped[key].append(difference)
    count = len(grouped)
    if not 2 <= count <= 18:
        raise ValueError("requires 2 to 18 clusters for exact enumeration")
    sums = [sum(values) for values in grouped.values()]
    n = len(differences)
    observed = sum(sums) / n
    threshold = abs(sum(sums)) - 1e-12
    extreme = 0
    total = 1 << count
    for signs in itertools.product((-1, 1), repeat=count):
        if abs(sum(sign * value for sign, value in zip(signs, sums, strict=True))) >= threshold:
            extreme += 1
    return {
        "n": n,
        "cluster_count": count,
        "observed_mean_improvement": observed,
        "exact_two_sided_sign_flip_fraction": extreme / total,
        "configurations": total,
        "min_cluster_size": min(map(len, grouped.values())),
        "max_cluster_size": max(map(len, grouped.values())),
        "assumption": "cluster-level sign exchangeability under sharp null; unverified",
        "research_only": True,
    }
