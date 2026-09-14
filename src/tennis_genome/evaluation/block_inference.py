from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from itertools import product

from .paired_inference import _paired_differences, _percentile


@dataclass(frozen=True)
class PairedBlockBootstrapResult:
    improvement: float
    lower: float
    upper: float
    confidence_level: float
    n_pairs: int
    n_blocks: int
    n_resamples: int


@dataclass(frozen=True)
class PairedBlockPermutationResult:
    improvement: float
    p_value: float
    n_pairs: int
    n_blocks: int
    n_resamples: int | None
    exact: bool


def _block_differences(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
    block_ids: Iterable[Hashable],
) -> tuple[list[float], list[Hashable], dict[Hashable, list[float]]]:
    differences = _paired_differences(baseline_losses, candidate_losses)
    blocks = list(block_ids)
    if len(blocks) != len(differences):
        raise ValueError("block_ids must have the same length as paired losses")
    if any(block is None for block in blocks):
        raise ValueError("block_ids must not contain None")

    grouped: dict[Hashable, list[float]] = defaultdict(list)
    for block, difference in zip(blocks, differences, strict=True):
        try:
            hash(block)
        except TypeError as exc:
            raise ValueError("block_ids must be hashable") from exc
        grouped[block].append(difference)

    ordered_blocks = list(dict.fromkeys(blocks))
    if len(ordered_blocks) < 2:
        raise ValueError("dependence-aware inference requires at least two blocks")
    return differences, ordered_blocks, dict(grouped)


def paired_block_bootstrap_improvement(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
    block_ids: Iterable[Hashable],
    *,
    confidence_level: float = 0.95,
    n_resamples: int = 10_000,
    seed: int = 0,
) -> PairedBlockBootstrapResult:
    """Cluster/block bootstrap for paired proper-score loss differences.

    Entire predeclared blocks are resampled with replacement. Every observation within a
    selected block travels together, preserving arbitrary within-block dependence. The
    caller owns the scientific choice of block definition (for example tournament-week
    or calendar-week); this function does not search for a favorable clustering scheme.

    Positive improvement means lower candidate loss.
    """

    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    differences, blocks, grouped = _block_differences(
        baseline_losses,
        candidate_losses,
        block_ids,
    )
    observed = sum(differences) / len(differences)
    rng = random.Random(seed)

    draws: list[float] = []
    n_blocks = len(blocks)
    for _ in range(n_resamples):
        total = 0.0
        count = 0
        for _ in range(n_blocks):
            sampled_block = blocks[rng.randrange(n_blocks)]
            values = grouped[sampled_block]
            total += sum(values)
            count += len(values)
        if count == 0:
            raise AssertionError("sampled block bootstrap produced an empty draw")
        draws.append(total / count)

    draws.sort()
    alpha = 1.0 - confidence_level
    return PairedBlockBootstrapResult(
        improvement=observed,
        lower=_percentile(draws, alpha / 2.0),
        upper=_percentile(draws, 1.0 - alpha / 2.0),
        confidence_level=confidence_level,
        n_pairs=len(differences),
        n_blocks=n_blocks,
        n_resamples=n_resamples,
    )


def paired_block_sign_flip_test(
    baseline_losses: Iterable[float],
    candidate_losses: Iterable[float],
    block_ids: Iterable[Hashable],
    *,
    exact_max_blocks: int = 18,
    n_resamples: int = 20_000,
    seed: int = 0,
) -> PairedBlockPermutationResult:
    """Two-sided sign-flip test that preserves dependence within registered blocks.

    One sign is assigned to each block, then applied to every paired loss difference in
    that block. This is intentionally coarser than observation-level sign flipping.
    """

    if exact_max_blocks < 0:
        raise ValueError("exact_max_blocks must be non-negative")
    if n_resamples <= 0:
        raise ValueError("n_resamples must be positive")

    differences, blocks, grouped = _block_differences(
        baseline_losses,
        candidate_losses,
        block_ids,
    )
    n_pairs = len(differences)
    n_blocks = len(blocks)
    observed = sum(differences) / n_pairs
    threshold = abs(observed) - 1e-15

    block_sums = [sum(grouped[block]) for block in blocks]

    if n_blocks <= exact_max_blocks:
        extreme = 0
        total = 0
        for signs in product((-1.0, 1.0), repeat=n_blocks):
            statistic = (
                sum(
                    sign * block_sum
                    for sign, block_sum in zip(signs, block_sums, strict=True)
                )
                / n_pairs
            )
            total += 1
            if abs(statistic) >= threshold:
                extreme += 1
        return PairedBlockPermutationResult(
            improvement=observed,
            p_value=extreme / total,
            n_pairs=n_pairs,
            n_blocks=n_blocks,
            n_resamples=None,
            exact=True,
        )

    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_resamples):
        statistic = (
            sum(
                block_sum if rng.random() < 0.5 else -block_sum
                for block_sum in block_sums
            )
            / n_pairs
        )
        if abs(statistic) >= threshold:
            extreme += 1

    return PairedBlockPermutationResult(
        improvement=observed,
        p_value=(extreme + 1) / (n_resamples + 1),
        n_pairs=n_pairs,
        n_blocks=n_blocks,
        n_resamples=n_resamples,
        exact=False,
    )
