from __future__ import annotations

from .sportradar_season_summaries_resume import CensusResumeCheckpoint


def cumulative_retained_response_count(
    *,
    source_checkpoint: CensusResumeCheckpoint,
    current_retained_response_count: int,
) -> int:
    """Carry prior non-reusable quota responses into later checkpoint accounting.

    Reusable 200/404/410 evidence is physically copied into the resumed artifact and is
    therefore already included in ``current_retained_response_count``. Prior quota-stop
    responses are provenance-only and intentionally are not copied, so add exactly that
    historical delta back to the cumulative count.
    """

    if current_retained_response_count < 0:
        raise ValueError("current retained response count must be non-negative")
    prior_nonreusable = (
        source_checkpoint.retained_provider_response_count
        - source_checkpoint.reusable_provider_response_count
    )
    if prior_nonreusable < 0:
        raise ValueError("source checkpoint retained/reusable accounting is invalid")
    return current_retained_response_count + prior_nonreusable
