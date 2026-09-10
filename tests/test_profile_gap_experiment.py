from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from tennis_genome.experiments.profile_gap import run_profile_gap
from tests.factories import make_match


def _history():
    rows = []
    specs = [
        ("2020-1", date(2020, 1, 1), "a", "b", True),
        ("2020-2", date(2020, 2, 1), "c", "d", False),
        ("2020-3", date(2020, 3, 1), "a", "c", True),
        ("2020-4", date(2020, 4, 1), "b", "d", False),
        ("2020-5", date(2020, 5, 1), "a", "d", True),
        ("2020-6", date(2020, 6, 1), "b", "c", False),
        ("2021-1", date(2021, 1, 1), "a", "b", True),
        ("2021-2", date(2021, 2, 1), "c", "d", False),
        ("2021-3", date(2021, 3, 1), "a", "c", False),
        ("2022-1", date(2022, 1, 1), "a", "d", True),
        ("2022-2", date(2022, 2, 1), "b", "c", True),
        ("2022-3", date(2022, 3, 1), "d", "a", False),
    ]
    for match_id, event_date, player_a, player_b, a_won in specs:
        rows.append(
            make_match(
                match_id=match_id,
                event_date=event_date,
                player_a_id=player_a,
                player_b_id=player_b,
                a_won=a_won,
                rank_a=10,
                rank_b=20,
            )
        )
    return rows


def test_profile_gap_uses_expanding_prior_year_training_and_keeps_ledger():
    report = run_profile_gap(
        _history(),
        tour="ATP",
        min_train_matches=4,
    )

    assert report.population_n == 6
    assert report.comparison.n == report.population_n
    assert [item.year for item in report.yearly] == [2021, 2022]
    assert len(report.predictions) == report.population_n
    assert {row.year for row in report.predictions} == {2021, 2022}
    assert all(row.match_id.startswith(("2021-", "2022-")) for row in report.predictions)
    assert report.representation == "strict"


def test_profile_gap_rejects_post_2025_data():
    future = make_match(
        match_id="spent-2026",
        event_date=date(2026, 1, 1),
        player_a_id="a",
        player_b_id="b",
        a_won=True,
    )

    with pytest.raises(ValueError, match="post-2025"):
        run_profile_gap(
            [*_history(), future],
            tour="ATP",
            min_train_matches=4,
        )


def test_profile_gap_conditional_representation_is_wta_only():
    with pytest.raises(ValueError, match="only for WTA"):
        run_profile_gap(
            _history(),
            tour="ATP",
            include_conditional=True,
            min_train_matches=4,
        )


def test_wta_conditional_profile_gap_runs_without_promoting_age_fields():
    wta_history = [
        replace(match, pre_match=replace(match.pre_match, tour="WTA"))
        for match in _history()
    ]
    report = run_profile_gap(
        wta_history,
        tour="WTA",
        include_conditional=True,
        min_train_matches=4,
    )

    assert report.representation == "conditional"
    assert "serve_rating" in report.feature_names
    assert "return_rating" in report.feature_names
    assert "age_years" not in report.feature_names
