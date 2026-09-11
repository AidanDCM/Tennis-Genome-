from __future__ import annotations

from dataclasses import asdict
from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.experiments.pattern_confirm_production import (
    core_probability_from_artifact,
    freeze_production_artifacts,
    profile_gap_from_artifact,
    verify_core_artifact,
    verify_profile_artifact,
)
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.models.profile_strength import ProfileStrengthModel
from tennis_genome.profiles.state import walk_forward_player_profiles


def _match(index: int, year: int) -> HistoricalMatch:
    match_id = f"m-{year}-{index}"
    a_won = (index + year) % 3 != 0
    return HistoricalMatch(
        pre_match=PreMatchState(
            match_id=match_id,
            tour="ATP",
            event_date=date(year, 1 + index % 10, 1 + index % 20),
            source_order=index,
            tournament_id=f"e-{year}-{index}",
            tournament_name="Synthetic",
            tournament_level="A",
            surface="Hard" if index % 2 else "Clay",
            round="R32",
            best_of=3,
            player_a_id=f"a{index % 7}",
            player_b_id=f"b{index % 7}",
            player_a_name=f"A {index % 7}",
            player_b_name=f"B {index % 7}",
            rank_a=10 + index,
            rank_b=40 + index,
            rank_points_a=1800 + index,
            rank_points_b=900 + index,
            hand_a="L" if index % 4 == 0 else "R",
            hand_b="R",
            height_cm_a=184 + index % 5,
            height_cm_b=180 + index % 6,
            age_years_a=22.0 + index % 12,
            age_years_b=24.0 + index % 10,
        ),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=60,
            first_serve_points_won_a=31 if a_won else 24,
            second_serve_points_won_a=12 if a_won else 9,
            first_serve_points_won_b=24 if a_won else 31,
            second_serve_points_won_b=9 if a_won else 12,
            duration_minutes=80 + index,
        ),
    )


def _matches() -> list[HistoricalMatch]:
    return [_match(i, y) for y in (2022, 2023, 2024, 2025) for i in range(20)]


def test_frozen_artifacts_reproduce_direct_predictions() -> None:
    matches = _matches()
    profile, core = freeze_production_artifacts(matches, canonical_manifest_sha256="a" * 64)
    assert verify_profile_artifact(asdict(profile)) == profile
    assert verify_core_artifact(asdict(core)) == core

    pairs = walk_forward_player_profiles(matches, exclude_retirements=False)
    snapshots = {
        row.match_id: row
        for row in walk_forward_foundational_features(matches, exclude_retirements=False)
    }
    outcome_by_id = {match.match_id: match.outcome.a_won for match in matches}
    outcomes = [outcome_by_id[pair.match_id] for pair in pairs]
    profile_model = ProfileStrengthModel("ATP").fit(pairs, outcomes)
    core_model = FeatureProbabilityModel(strict_a_features("ATP")).fit(
        [snapshots[pair.match_id] for pair in pairs], outcomes
    )
    pair = pairs[-1]
    assert profile_gap_from_artifact(pair, profile) == pytest.approx(
        profile_model.predict_pair(pair).profile_gap_match, abs=1e-12
    )
    assert core_probability_from_artifact(snapshots[pair.match_id], core) == pytest.approx(
        core_model.predict_probabilities([snapshots[pair.match_id]])[0], abs=1e-12
    )


def test_post_2025_training_is_rejected() -> None:
    with pytest.raises(ValueError, match="post-2025"):
        freeze_production_artifacts(
            _matches() + [_match(99, 2026)], canonical_manifest_sha256="b" * 64
        )
