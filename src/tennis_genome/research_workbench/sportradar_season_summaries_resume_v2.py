from __future__ import annotations

from pathlib import Path

from . import sportradar_season_summaries_resume as v1
from .sportradar_season_summaries_census import ProviderGet, SeasonSummariesCensus
from .sportradar_season_summaries_resume_accounting import (
    cumulative_retained_response_count,
)


def resume_season_summaries_census(
    *,
    inventory_path: Path,
    partial_census_root: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = v1.v1._default_provider_get,
    sleeper: v1.v1.Sleeper = v1.v1.time.sleep,
    now: v1.v1.Now = v1.v1._default_now,
) -> tuple[SeasonSummariesCensus | None, v1.CensusResumeCheckpoint]:
    """Resume a census while preserving cumulative quota-stop response accounting."""

    source_checkpoint = v1.reconstruct_resume_checkpoint(
        inventory_path=inventory_path,
        partial_census_root=partial_census_root,
    )
    census, checkpoint = v1.resume_season_summaries_census(
        inventory_path=inventory_path,
        partial_census_root=partial_census_root,
        output_dir=output_dir,
        access_level=access_level,
        api_key=api_key,
        provider_get=provider_get,
        sleeper=sleeper,
        now=now,
    )
    corrected_retained = cumulative_retained_response_count(
        source_checkpoint=source_checkpoint,
        current_retained_response_count=checkpoint.retained_provider_response_count,
    )
    if corrected_retained == checkpoint.retained_provider_response_count:
        return census, checkpoint

    corrected = checkpoint.model_copy(
        update={"retained_provider_response_count": corrected_retained}
    )
    (output_dir / "checkpoint.json").write_text(
        v1.json.dumps(corrected.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return census, corrected
