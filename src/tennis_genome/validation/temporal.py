from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime


class TemporalLeakageError(ValueError):
    """Raised when information unavailable at prediction time is used."""


def assert_available_before_t0(
    *,
    available_at: datetime,
    prediction_cutoff_at: datetime,
) -> None:
    """Assert a source record was available no later than prediction cutoff."""
    if available_at > prediction_cutoff_at:
        raise TemporalLeakageError(
            f"record available_at={available_at.isoformat()} exceeds "
            f"prediction_cutoff_at={prediction_cutoff_at.isoformat()}"
        )


def assert_history_strictly_before_t0(
    *,
    history_times: Iterable[datetime],
    prediction_cutoff_at: datetime,
) -> None:
    """Assert all rolling-history observations are strictly before T0."""
    illegal = [ts for ts in history_times if ts >= prediction_cutoff_at]
    if illegal:
        first = min(illegal)
        raise TemporalLeakageError(
            f"historical observation {first.isoformat()} is not strictly before "
            f"prediction cutoff {prediction_cutoff_at.isoformat()}"
        )


def assert_neighbor_is_historical(
    *,
    neighbor_t0: datetime,
    target_t0: datetime,
    neighbor_match_id: str | None = None,
) -> None:
    """Prevent future/self-period neighbors in Tennis Genome retrieval."""
    if neighbor_t0 >= target_t0:
        label = neighbor_match_id or "<unknown>"
        raise TemporalLeakageError(
            f"neighbor {label} has t0={neighbor_t0.isoformat()} which is not before "
            f"target_t0={target_t0.isoformat()}"
        )
