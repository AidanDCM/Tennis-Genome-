from __future__ import annotations

from datetime import date, timedelta

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.research_workbench.dynamic_state_development import (
    DynamicStateDevelopmentSpec,
)
from tennis_genome.research_workbench.dynamic_state_diagnostic import (
    LAYOFF_BUCKETS,
    PRIOR_POINT_BUCKETS,
    UNCERTAINTY_BUCKETS,
    DynamicStateFailureDiagnosticSpec,
    run_dynamic_state_failure_diagnostic,
)


def _matches() -> list[HistoricalMatch]:
    players = ("P1", "P2", "P3", "P4")
    matches: list[HistoricalMatch] = []
    sequence = 0
    for year_index, year in enumerate((2022, 2023, 2024)):
        event_date = date(year, 1, 3)
        for index in range(30):
            if year == 2024 and index == 15:
                event_date += timedelta(days=120)
            player_a = players[index % 4]
            player_b = players[(index + 1) % 4]
            match_id = f"m-{year}-{index:03d}"
            a_won = (index + year_index) % 2 == 0
            won_a = 41 if a_won else 34
            won_b = 34 if a_won else 41
            matches.append(
                HistoricalMatch(
                    pre_match=PreMatchState(
                        match_id=match_id,
                        tour="ATP",
                        event_date=event_date,
                        source_order=sequence,
                        tournament_id=f"t-{year}-{index:03d}",
                        tournament_name="Diagnostic Synthetic",
                        tournament_level="A",
                        surface="Hard",
                        round="R32",
                        best_of=3,
                        player_a_id=player_a,
                        player_b_id=player_b,
                        player_a_name=player_a,
                        player_b_name=player_b,
                        rank_a=None,
                        rank_b=None,
                        rank_points_a=None,
                        rank_points_b=None,
                    ),
                    outcome=MatchOutcome(
                        match_id=match_id,
                        a_won=a_won,
                        score="synthetic",
                        retirement=False,
                        walkover=False,
                    ),
                    stats=MatchStats(
                        match_id=match_id,
                        service_points_a=60,
                        service_points_b=60,
                        first_serve_points_won_a=won_a,
                        first_serve_points_won_b=won_b,
                        second_serve_points_won_a=0,
                        second_serve_points_won_b=0,
                    ),
                )
            )
            sequence += 1
            event_date += timedelta(days=7)
    return matches


def _spec() -> DynamicStateFailureDiagnosticSpec:
    development = DynamicStateDevelopmentSpec(
        tour="ATP",
        test_years=(2023, 2024),
        min_train_rows=10,
        bootstrap_resamples=100,
        permutation_resamples=100,
        inference_seed=31,
    )
    return DynamicStateFailureDiagnosticSpec(development_spec=development)


def test_failure_diagnostic_is_deterministic_and_descriptive_only() -> None:
    first = run_dynamic_state_failure_diagnostic(_matches(), _spec())
    second = run_dynamic_state_failure_diagnostic(_matches(), _spec())

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.diagnostic_spec_sha256 == _spec().semantic_sha256
    assert first.interpretation_boundary == "DESCRIPTIVE_ONLY_NO_PARAMETER_SELECTION"
    assert first.n_predictions == 60


def test_each_diagnostic_dimension_partitions_all_prediction_rows() -> None:
    report = run_dynamic_state_failure_diagnostic(_matches(), _spec())

    for dimension in (
        "PAIR_MAX_LAYOFF_DAYS",
        "PAIR_MIN_PRIOR_POINT_DEPTH",
        "PAIR_MAX_SERVE_LOGIT_SD",
    ):
        assert sum(
            row.n for row in report.strata if row.dimension == dimension
        ) == report.n_predictions


def test_registered_bucket_definitions_are_preserved_in_report() -> None:
    report = run_dynamic_state_failure_diagnostic(_matches(), _spec())

    assert report.layoff_buckets == LAYOFF_BUCKETS
    assert report.prior_point_buckets == PRIOR_POINT_BUCKETS
    assert report.uncertainty_buckets == UNCERTAINTY_BUCKETS


def test_diagnostic_keeps_debut_and_long_layoff_rows_visible() -> None:
    report = run_dynamic_state_failure_diagnostic(_matches(), _spec())

    layoff = {
        row.bucket: row
        for row in report.strata
        if row.dimension == "PAIR_MAX_LAYOFF_DAYS"
    }
    assert "181_PLUS" in layoff or "91_180" in layoff
    assert all(row.n > 0 for row in layoff.values())


def test_stratum_improvements_are_exact_loss_differences() -> None:
    report = run_dynamic_state_failure_diagnostic(_matches(), _spec())

    for row in report.strata:
        assert row.brier_improvement == row.fixed_brier - row.dynamic_brier
        assert row.log_loss_improvement == row.fixed_log_loss - row.dynamic_log_loss
