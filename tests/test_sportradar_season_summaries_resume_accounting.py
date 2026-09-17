from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    SeasonSummariesCensusRow,
)
from tennis_genome.research_workbench.sportradar_season_summaries_resume import (
    CensusResumeCheckpoint,
)
from tennis_genome.research_workbench.sportradar_season_summaries_resume_accounting import (
    cumulative_retained_response_count,
)


def test_cumulative_retained_response_count_carries_prior_quota_pause() -> None:
    row = SeasonSummariesCensusRow(
        tour="ATP",
        competition_id="sr:competition:1",
        season_id="sr:season:1",
        disposition="SUMMARIES_CAPTURED",
        page_count=1,
        raw_summary_count=0,
        played_terminal_count=0,
        walkover_count=0,
        nonterminal_count=0,
        required_timeline_count=0,
        required_timeline_event_ids=(),
        season_summaries_sha256="a" * 64,
        access_failure_semantic_sha256=None,
    )
    source = CensusResumeCheckpoint(
        inventory_semantic_sha256="b" * 64,
        historical_candidate_count=2,
        completed_candidate_count=1,
        next_candidate_index=1,
        next_season_id="sr:season:2",
        retained_provider_response_count=2,
        reusable_provider_response_count=1,
        quota_exhausted=True,
        quota_failure_status=429,
        quota_failure_season_id="sr:season:2",
        rows=(row,),
    )
    assert (
        cumulative_retained_response_count(
            source_checkpoint=source,
            current_retained_response_count=2,
        )
        == 3
    )
