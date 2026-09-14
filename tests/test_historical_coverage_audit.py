from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.research_workbench.historical_coverage_audit import (
    audit_historical_coverage,
)


def _match(
    match_id: str,
    *,
    tour: str = "WTA",
    year: int,
    stats: MatchStats | None = None,
    retirement: bool = False,
    walkover: bool = False,
) -> HistoricalMatch:
    pre = PreMatchState(
        match_id=match_id,
        tour=tour,  # type: ignore[arg-type]
        event_date=date(year, 6, 1),
        source_order=1,
        tournament_id="event",
        tournament_name="Event",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=f"{match_id}-a",
        player_b_id=f"{match_id}-b",
        player_a_name="A",
        player_b_name="B",
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    outcome = MatchOutcome(
        match_id=match_id,
        a_won=True,
        score=None,
        retirement=retirement,
        walkover=walkover,
    )
    return HistoricalMatch(pre_match=pre, outcome=outcome, stats=stats)


def _stats(
    match_id: str,
    *,
    service_points_a: int | None = 60,
    service_points_b: int | None = 55,
    first_won_a: int | None = 25,
    first_won_b: int | None = 22,
    second_won_a: int | None = 12,
    second_won_b: int | None = 11,
    duration: int | None = 90,
) -> MatchStats:
    return MatchStats(
        match_id=match_id,
        service_points_a=service_points_a,
        service_points_b=service_points_b,
        first_serve_points_won_a=first_won_a,
        first_serve_points_won_b=first_won_b,
        second_serve_points_won_a=second_won_a,
        second_serve_points_won_b=second_won_b,
        duration_minutes=duration,
    )


def test_audit_uses_strict_eligible_denominator_and_exact_consumed_stats() -> None:
    matches = [
        _match("complete", year=2015, stats=_stats("complete")),
        _match("missing", year=2015, stats=None),
        _match("retired", year=2015, stats=_stats("retired"), retirement=True),
        _match("walkover", year=2015, stats=None, walkover=True),
        _match(
            "invalid-b",
            year=2016,
            stats=_stats(
                "invalid-b",
                service_points_b=20,
                first_won_b=15,
                second_won_b=10,
                duration=None,
            ),
        ),
    ]

    report = audit_historical_coverage(
        matches,
        tour="WTA",
        source_manifest_sha256="a" * 64,
    )

    first, second = report.rows
    assert first.year == 2015
    assert first.n_matches == 4
    assert first.n_strict_eligible == 2
    assert first.n_stats_present == 1
    assert first.n_service_observation_a == 1
    assert first.n_service_observation_b == 1
    assert first.n_service_observation_both == 1
    assert first.n_duration_present == 1
    assert first.stats_present_rate == pytest.approx(0.5)
    assert first.service_both_rate == pytest.approx(0.5)
    assert first.duration_present_rate == pytest.approx(0.5)

    assert second.year == 2016
    assert second.n_strict_eligible == 1
    assert second.n_stats_present == 1
    assert second.n_service_observation_a == 1
    assert second.n_service_observation_b == 0
    assert second.n_service_observation_both == 0
    assert second.n_duration_present == 0
    assert second.stats_present_rate == pytest.approx(1.0)
    assert second.service_both_rate == pytest.approx(0.0)
    assert second.duration_present_rate == pytest.approx(0.0)
    assert report.evidence_role == "DESCRIPTIVE_ONLY"


def test_audit_rates_are_zero_when_year_has_no_strict_eligible_matches() -> None:
    report = audit_historical_coverage(
        [
            _match("wo", year=2020, walkover=True),
            _match("ret", year=2020, retirement=True, stats=_stats("ret")),
        ],
        tour="WTA",
        source_manifest_sha256="b" * 64,
    )
    row = report.rows[0]
    assert row.n_matches == 2
    assert row.n_strict_eligible == 0
    assert row.stats_present_rate == 0.0
    assert row.service_both_rate == 0.0
    assert row.duration_present_rate == 0.0


def test_audit_rejects_mixed_or_wrong_tour_population() -> None:
    with pytest.raises(ValueError, match="requires only ATP matches"):
        audit_historical_coverage(
            [_match("wta", year=2020, tour="WTA")],
            tour="ATP",
            source_manifest_sha256="c" * 64,
        )


def test_service_observation_requires_positive_total_and_valid_wins() -> None:
    report = audit_historical_coverage(
        [
            _match(
                "zero-total",
                year=2021,
                stats=_stats("zero-total", service_points_a=0),
            ),
            _match(
                "wins-exceed-total",
                year=2021,
                stats=_stats(
                    "wins-exceed-total",
                    service_points_b=20,
                    first_won_b=15,
                    second_won_b=10,
                ),
            ),
        ],
        tour="WTA",
        source_manifest_sha256="d" * 64,
    )
    row = report.rows[0]
    assert row.n_service_observation_a == 1
    assert row.n_service_observation_b == 1
    assert row.n_service_observation_both == 0
