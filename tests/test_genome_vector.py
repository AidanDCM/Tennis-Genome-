from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.features.genome import (
    build_genome_vector,
    canonical_orientation_sign,
    canonical_outcome,
    canonical_probability,
    original_probability,
)
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.profiles.state import MatchProfilePair, walk_forward_player_profiles


def _match() -> HistoricalMatch:
    state = PreMatchState(
        match_id="target",
        tour="ATP",
        event_date=date(2025, 1, 5),
        source_order=0,
        tournament_id="event",
        tournament_name="Event",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id="a",
        player_b_id="b",
        player_a_name="A",
        player_b_name="B",
        rank_a=10,
        rank_b=20,
        rank_points_a=3000,
        rank_points_b=2000,
        age_years_a=25.0,
        age_years_b=30.0,
        height_cm_a=188,
        height_cm_b=180,
        hand_a="R",
        hand_b="L",
        ioc_a="USA",
        ioc_b="ESP",
    )
    return HistoricalMatch(
        pre_match=state,
        outcome=MatchOutcome(
            match_id="target",
            a_won=True,
            score="6-4 6-4",
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )


def _state() -> tuple[MatchProfilePair, object]:
    match = _match()
    pair = walk_forward_player_profiles([match])[0]
    foundational = walk_forward_foundational_features([match])[0]
    return pair, foundational


def test_canonical_orientation_uses_ids_for_exact_elo_tie() -> None:
    assert canonical_orientation_sign(
        elo_logit=0.0,
        player_a_id="a",
        player_b_id="b",
    ) == 1
    assert canonical_orientation_sign(
        elo_logit=0.0,
        player_a_id="b",
        player_b_id="a",
    ) == -1


def test_probability_and_outcome_round_trip_through_canonical_orientation() -> None:
    for sign in (-1, 1):
        canonical = canonical_probability(0.72, orientation_sign=sign)
        assert original_probability(canonical, orientation_sign=sign) == pytest.approx(0.72)
        outcome = canonical_outcome(True, orientation_sign=sign)
        assert canonical_outcome(outcome, orientation_sign=sign) is True


def test_genome_contains_core_differences_and_absolute_profile_means() -> None:
    pair, foundational = _state()
    genome = build_genome_vector(pair, foundational)

    assert "core::elo_logit" in genome.feature_names
    assert "core::age_diff" in genome.feature_names
    assert "profile_mean::elo_rating" in genome.feature_names
    assert "profile_mean::age_years" in genome.feature_names
    assert len(genome.feature_names) == len(genome.values)

    mean_age_index = genome.feature_names.index("profile_mean::age_years")
    assert genome.values[mean_age_index] == pytest.approx(27.5)


def test_swapping_players_preserves_canonical_genome_vector() -> None:
    pair, foundational = _state()
    original = build_genome_vector(pair, foundational)

    swapped_pair = MatchProfilePair(
        match_id=pair.match_id,
        event_date=pair.event_date,
        player_a=pair.player_b,
        player_b=pair.player_a,
    )
    swapped_core = {
        name: (
            None
            if getattr(foundational, name) is None
            else -float(getattr(foundational, name))
        )
        for name in strict_a_features("ATP")
    }
    swapped_foundational = replace(foundational, **swapped_core)
    swapped = build_genome_vector(swapped_pair, swapped_foundational)

    assert swapped.orientation_sign == -original.orientation_sign
    assert swapped.feature_names == original.feature_names
    assert swapped.values == pytest.approx(original.values)


def test_genome_hash_is_deterministic_and_missingness_is_preserved() -> None:
    pair, foundational = _state()
    missing_foundational = replace(foundational, event_gap_days_diff=None)
    first = build_genome_vector(pair, missing_foundational)
    second = build_genome_vector(pair, missing_foundational)

    index = first.feature_names.index("core::event_gap_days_diff")
    assert first.values[index] is None
    assert first.missing_fraction > 0.0
    assert first.digest == second.digest


def test_future_append_does_not_change_existing_genome_vector() -> None:
    target = _match()
    future_state = replace(
        target.pre_match,
        match_id="future",
        event_date=date(2025, 2, 1),
        source_order=1,
        player_b_id="c",
        player_b_name="C",
        rank_b=30,
        rank_points_b=1500,
        age_years_b=27.0,
        height_cm_b=184,
        hand_b="R",
        ioc_b="FRA",
    )
    future = HistoricalMatch(
        pre_match=future_state,
        outcome=replace(
            target.outcome,
            match_id="future",
            a_won=False,
        ),
        stats=None,
    )

    def target_genome(matches: list[HistoricalMatch]):
        pairs = {
            pair.match_id: pair
            for pair in walk_forward_player_profiles(matches)
        }
        foundational = {
            snapshot.match_id: snapshot
            for snapshot in walk_forward_foundational_features(matches)
        }
        return build_genome_vector(pairs["target"], foundational["target"])

    before = target_genome([target])
    after = target_genome([target, future])

    assert after.feature_names == before.feature_names
    assert after.values == before.values
    assert after.digest == before.digest
