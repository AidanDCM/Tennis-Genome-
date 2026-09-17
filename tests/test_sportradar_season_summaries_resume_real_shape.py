import pytest

from tennis_genome.research_workbench.sportradar_season_summaries_resume import (
    CensusResumeCheckpoint,
)


def test_checkpoint_rejects_count_without_matching_rows() -> None:
    with pytest.raises(ValueError, match="completed candidate count"):
        CensusResumeCheckpoint(
            inventory_semantic_sha256="a" * 64,
            historical_candidate_count=559,
            completed_candidate_count=79,
            next_candidate_index=79,
            next_season_id="sr:season:133607",
            retained_provider_response_count=91,
            reusable_provider_response_count=90,
            quota_exhausted=True,
            quota_failure_status=429,
            quota_failure_season_id="sr:season:133607",
            rows=(),
        )
