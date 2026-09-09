from __future__ import annotations

from dataclasses import dataclass
from math import pow


@dataclass(frozen=True)
class EloConfig:
    """Configuration for a basic two-player Elo model.

    Values are intentionally configurable because scale/K choices must be
    validated chronologically rather than treated as universal constants.
    """

    initial_rating: float = 1500.0
    k_factor: float = 32.0
    scale: float = 400.0

    def __post_init__(self) -> None:
        if self.k_factor <= 0:
            raise ValueError("k_factor must be positive")
        if self.scale <= 0:
            raise ValueError("scale must be positive")


def expected_score(rating_a: float, rating_b: float, *, scale: float = 400.0) -> float:
    """Return pre-match probability that A defeats B under the Elo model."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    return 1.0 / (1.0 + pow(10.0, (rating_b - rating_a) / scale))


def update_rating(
    rating: float,
    expected: float,
    actual: float,
    *,
    k_factor: float = 32.0,
) -> float:
    """Update one player's rating after an observed match outcome."""
    if not 0.0 <= expected <= 1.0:
        raise ValueError("expected must be in [0, 1]")
    if not 0.0 <= actual <= 1.0:
        raise ValueError("actual must be in [0, 1]")
    if k_factor <= 0:
        raise ValueError("k_factor must be positive")
    return rating + k_factor * (actual - expected)


def update_pair(
    rating_a: float,
    rating_b: float,
    *,
    a_won: bool,
    config: EloConfig | None = None,
) -> tuple[float, float]:
    """Update both players after a completed binary-outcome match.

    IMPORTANT: callers must capture the pre-match ratings/probability before
    calling this function. Ratings updated from the target match are not legal
    pre-match features for that same match.
    """
    config = config or EloConfig()
    p_a = expected_score(rating_a, rating_b, scale=config.scale)
    p_b = 1.0 - p_a
    y_a = 1.0 if a_won else 0.0
    y_b = 1.0 - y_a
    return (
        update_rating(rating_a, p_a, y_a, k_factor=config.k_factor),
        update_rating(rating_b, p_b, y_b, k_factor=config.k_factor),
    )
