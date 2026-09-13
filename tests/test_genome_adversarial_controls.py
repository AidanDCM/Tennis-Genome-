from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.experiments.genome_adversarial_controls import (
    _core_genome,
    _full_genome,
    _probability_genome,
    run_genome_adversarial_controls,
)
from tennis_genome.experiments.genome_neighborhood import _build_core_ledger
from tennis_genome.features.genome import GENOME_VERSION


def _synthetic_match(year: int, index: int) -> HistoricalMatch:
    surface = ("Hard", "Clay", "Grass")[index % 3]
    level = ("A", "G", "M")[index % 3]
    round_name = ("R32", "QF", "SF", "F")[index % 4]
    player_a = f"a-{year}-{index:03d}"
    player_b = f"b-{year}-{index:03d}"
    state = PreMatchState(
        match_id=f"m-{year}-{index:03d}",
        tour="ATP",
        event_date=date(year, 1 + (index % 12), 1),
        source_order=index,
        tournament_id=f"event-{year}-{index // 32}",
        tournament_name="Synthetic Event",
        tournament_level=level,
        surface=surface,
        round=round_name,
        best_of=5 if index % 11 == 0 else 3,
        player_a_id=player_a,
        player_b_id=player_b,
        player_a_name=player_a,
        player_b_name=player_b,
        rank_a=1 + (index % 100),
        rank_b=1 + ((index * 7) % 100),
        rank_points_a=5000 - (index % 1000),
        rank_points_b=4500 - ((index * 3) % 1000),
        seed_a=(1 + index % 16) if index % 4 == 0 else None,
        seed_b=(1 + (index * 3) % 16) if index % 5 == 0 else None,
        entry_a="Q" if index % 17 == 0 else None,
        entry_b="WC" if index % 19 == 0 else None,
        hand_a="R",
        hand_b="L" if index % 5 == 0 else "R",
        height_cm_a=178 + (index % 15),
        height_cm_b=176 + ((index * 2) % 15),
        age_years_a=20.0 + (index % 15),
        age_years_b=21.0 + ((index * 3) % 15),
        ioc_a="USA",
        ioc_b="ESP",
    )
    return HistoricalMatch(
        pre_match=state,
        outcome=MatchOutcome(
            match_id=state.match_id,
            a_won=(index % 2 == 0),
            score="6-4 6-4",
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )


def _history() -> list[HistoricalMatch]:
    return [_synthetic_match(year, index) for year in range(2010, 2016) for index in range(120)]


def test_three_registered_representations_are_distinct_and_full_is_frozen() -> None:
    ledger = _build_core_ledger(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
    )
    row = ledger[0]

    probability = _probability_genome(row)
    core = _core_genome(row)
    full = _full_genome(row)

    assert probability.feature_names == ("core_probability_logit",)
    assert len(probability.values) == 1
    assert core.feature_names
    assert all(name.startswith("core::") for name in core.feature_names)
    assert full.feature_version == GENOME_VERSION
    assert len(full.feature_names) > len(core.feature_names) > 1
    assert any(name.startswith("profile_mean::") for name in full.feature_names)


def test_genome_adversarial_controls_use_one_matched_future_population() -> None:
    report = run_genome_adversarial_controls(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=250,
        min_meta_train_rows=50,
    )

    assert report.primary_k == 100
    assert report.candidate_limit == 1000
    assert report.meta_population_n == report.comparison.n
    assert report.predictions
    assert min(row.year for row in report.predictions) >= 2015

    n = report.comparison.n
    assert report.comparison.calibration_control.n == n
    assert report.comparison.probability_neighborhood.n == n
    assert report.comparison.core_neighborhood.n == n
    assert report.comparison.full_genome.n == n

    match_ids = [row.match_id for row in report.predictions]
    assert len(match_ids) == len(set(match_ids))


def test_all_registered_neighbor_signals_exist_for_every_meta_prediction() -> None:
    report = run_genome_adversarial_controls(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=250,
        min_meta_train_rows=50,
    )

    for row in report.predictions:
        assert row.probability_neighbor_residual == pytest.approx(
            float(row.probability_neighbor_residual)
        )
        assert row.core_neighbor_residual == pytest.approx(float(row.core_neighbor_residual))
        assert row.full_neighbor_residual == pytest.approx(float(row.full_neighbor_residual))


def test_genome_adversarial_controls_reject_spent_post_2025_data() -> None:
    matches = _history()
    matches.append(_synthetic_match(2026, 0))

    with pytest.raises(ValueError, match="post-2025"):
        run_genome_adversarial_controls(
            matches,
            tour="ATP",
            min_core_train_matches=100,
            min_neighbor_pool=250,
            min_meta_train_rows=50,
        )


def test_gate_class_is_one_of_registered_interpretations() -> None:
    report = run_genome_adversarial_controls(
        _history(),
        tour="ATP",
        min_core_train_matches=100,
        min_neighbor_pool=250,
        min_meta_train_rows=50,
    )

    assert report.promotion_diagnostics.interpretation_class in {
        "local_core_probability_residual_correction_not_isolated_from_calibration",
        "core_geometry_local_residual_correction",
        "structured_matchup_historical_alignment_beyond_local_core_correction",
    }
