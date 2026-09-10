from dataclasses import replace
from datetime import date

import pytest

from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.models.feature_probability import FeatureProbabilityModel


def _snapshot(index: int) -> FoundationalSnapshot:
    return FoundationalSnapshot(
        match_id=f"m-{index}",
        event_date=date(2025, 1, 1),
        elo_logit=float(index - 3),
        serve_return_edge=0.01 * index,
        serve_rating_diff=0.02 * index,
        return_rating_diff=-0.01 * index,
        min_prior_points=100,
        form_result_30_diff=0.0,
        form_result_90_diff=0.0,
        form_point_30_diff=0.0,
        form_point_90_diff=0.0,
        event_gap_days_diff=None,
        minutes_7_diff=None,
        minutes_14_diff=None,
        minutes_28_diff=None,
        matches_14_diff=0.0,
        matches_28_diff=0.0,
        previous_event_minutes_diff=None,
        age_diff=None,
        age_curve_diff=None,
        young_diff=None,
        veteran_diff=None,
        height_diff=None,
        age_x_minutes_14_diff=None,
        age_x_short_gap_diff=None,
        h2h_edge=0.0,
        h2h_weighted_edge=0.0,
        h2h_count=0,
        left_hand_diff=0.0,
        opposite_hand_serve_edge=0.0,
        surface_hard_elo=0.0,
        surface_clay_elo=0.0,
        surface_grass_elo=0.0,
        surface_carpet_elo=0.0,
        surface_hard_serve=0.0,
        surface_clay_serve=0.0,
        surface_grass_serve=0.0,
        surface_carpet_serve=0.0,
        slam_elo=0.0,
        masters_elo=0.0,
        finals_elo=0.0,
        lower_tier_elo=0.0,
        late_round_elo=0.0,
        round_robin_elo=0.0,
        best_of_five_elo=0.0,
        qualifier_diff=0.0,
        wildcard_diff=0.0,
        lucky_loser_diff=0.0,
        protected_ranking_diff=0.0,
        seeded_diff=0.0,
        seed_strength_diff=0.0,
    )


def test_feature_probability_model_fits_and_freezes_mapping() -> None:
    snapshots = [_snapshot(index) for index in range(8)]
    outcomes = [False, False, False, False, True, True, True, True]
    model = FeatureProbabilityModel(("elo_logit", "serve_return_edge"))

    model.fit(snapshots, outcomes)
    before = model.predict_probabilities(snapshots)
    metadata = model.metadata
    after = model.predict_probabilities(
        [replace(snapshot, match_id=f"copy-{snapshot.match_id}") for snapshot in snapshots]
    )

    assert model.is_fitted
    assert metadata.training_rows == 8
    assert metadata.positive_rows == 4
    assert metadata.negative_rows == 4
    assert before == after
    assert before[0] < before[-1]


def test_feature_probability_model_rejects_invalid_training_contracts() -> None:
    with pytest.raises(ValueError, match="at least one feature"):
        FeatureProbabilityModel(())
    with pytest.raises(ValueError, match="unique"):
        FeatureProbabilityModel(("elo_logit", "elo_logit"))

    model = FeatureProbabilityModel(("elo_logit",))
    with pytest.raises(RuntimeError, match="not fitted"):
        model.predict_probabilities([_snapshot(0)])
    with pytest.raises(ValueError, match="both outcome classes"):
        model.fit([_snapshot(0), _snapshot(1)], [True, True])
