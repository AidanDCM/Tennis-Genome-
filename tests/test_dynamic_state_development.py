from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.research_workbench.dynamic_state_development import (
    DynamicStateDevelopmentSpec,
    run_dynamic_state_development_comparison,
)


def _matches(*, tour: str = "ATP") -> list[HistoricalMatch]:
    players = ("P1", "P2", "P3", "P4")
    matches: list[HistoricalMatch] = []
    base = date(2022, 1, 3)
    sequence = 0
    for year_index, year in enumerate((2022, 2023, 2024)):
        year_start = date(year, 1, 3)
        for index in range(24):
            player_a = players[index % len(players)]
            player_b = players[(index + 1) % len(players)]
            match_id = f"{tour.lower()}-{year}-{index:03d}"
            event_date = year_start + timedelta(days=index * 7)
            a_won = (index + year_index) % 2 == 0
            service_points = 60
            shift = 5 if year == 2024 and player_a == "P1" else 0
            won_a = 38 + (2 if a_won else -2) + shift
            won_b = 37 + (-2 if a_won else 2)
            matches.append(
                HistoricalMatch(
                    pre_match=PreMatchState(
                        match_id=match_id,
                        tour=tour,  # type: ignore[arg-type]
                        event_date=event_date,
                        source_order=sequence,
                        tournament_id=f"event-{year}-{index:03d}",
                        tournament_name="Synthetic Development",
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
                        service_points_a=service_points,
                        service_points_b=service_points,
                        first_serve_points_won_a=won_a,
                        first_serve_points_won_b=won_b,
                        second_serve_points_won_a=0,
                        second_serve_points_won_b=0,
                    ),
                )
            )
            sequence += 1
    assert base < matches[-1].pre_match.event_date
    return matches


def _spec(**overrides: object) -> DynamicStateDevelopmentSpec:
    payload: dict[str, object] = {
        "tour": "ATP",
        "test_years": (2023, 2024),
        "min_train_rows": 10,
        "bootstrap_resamples": 200,
        "permutation_resamples": 200,
        "inference_seed": 11,
    }
    payload.update(overrides)
    return DynamicStateDevelopmentSpec(**payload)


def test_dynamic_state_development_comparison_is_deterministic_and_paired() -> None:
    spec = _spec()
    first = run_dynamic_state_development_comparison(_matches(), spec)
    second = run_dynamic_state_development_comparison(_matches(), spec)

    assert first.semantic_sha256 == second.semantic_sha256
    assert first.experiment_spec_sha256 == spec.semantic_sha256
    assert first.evidence_role == "DEVELOPMENT_ONLY"
    assert first.feature_names == ("elo_logit", "serve_return_edge")
    assert first.evaluated_years == (2023, 2024)
    assert first.n_predictions == 48
    assert len(first.predictions) == 48
    assert all(row.fixed_probability_a > 0.0 for row in first.predictions)
    assert all(row.dynamic_probability_a > 0.0 for row in first.predictions)
    assert first.brier_bootstrap["n_pairs"] == first.n_predictions
    assert first.log_loss_bootstrap["n_pairs"] == first.n_predictions


def test_dynamic_state_comparison_keeps_year_level_score_direction_explicit() -> None:
    report = run_dynamic_state_development_comparison(_matches(), _spec())

    assert len(report.year_scores) == 2
    for score in report.year_scores:
        assert score.brier_improvement == pytest.approx(
            score.fixed_brier - score.dynamic_brier
        )
        assert score.log_loss_improvement == pytest.approx(
            score.fixed_log_loss - score.dynamic_log_loss
        )


def test_dynamic_state_comparison_rejects_mixed_tours() -> None:
    matches = _matches()
    matches.extend(_matches(tour="WTA")[:2])

    with pytest.raises(ValueError, match="requires only ATP matches"):
        run_dynamic_state_development_comparison(matches, _spec())


def test_dynamic_state_comparison_fails_when_no_year_is_evaluable() -> None:
    with pytest.raises(ValueError, match="no development years"):
        run_dynamic_state_development_comparison(
            _matches(),
            _spec(test_years=(2021,), min_train_rows=10),
        )


def test_dynamic_state_development_spec_rejects_posthoc_search_shape() -> None:
    with pytest.raises(ValidationError, match="unique and sorted"):
        _spec(test_years=(2024, 2023, 2024))

    with pytest.raises(ValidationError, match="min_train_rows"):
        _spec(min_train_rows=0)

    with pytest.raises(ValidationError, match="resample"):
        _spec(bootstrap_resamples=0)
