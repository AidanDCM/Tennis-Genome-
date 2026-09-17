from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_summaries_resume import (
    CensusResumeCheckpoint,
)


def test_checkpoint_model_accepts_expected_real_partial_shape() -> None:
    checkpoint = CensusResumeCheckpoint(
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
    # The real artifact has 79 reconstructed rows; this synthetic construction is
    # intentionally rejected because the count must reproduce from actual rows.
    assert checkpoint.completed_candidate_count == len(checkpoint.rows)
