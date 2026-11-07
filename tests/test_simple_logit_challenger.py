from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from datetime import date

import pytest

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.research_workbench.simple_logit_challenger import (
    BASE_FEATURES,
    ChallengerExample,
    SimpleLogitChallenger,
)


def _example(
    match_id: str,
    event_date: date,
    elo: float,
    outcome: bool | None,
) -> ChallengerExample:
    values = {field.name: 0.0 for field in fields(FoundationalSnapshot)}
    values.update(match_id=match_id, event_date=event_date, min_prior_points=20)
    values["elo_logit"] = elo
    values["form_result_30_diff"] = elo / 10
    snapshot = FoundationalSnapshot(**values)
    state = PreMatchState(
        match_id=match_id,
        tour="WTA",
        event_date=event_date,
        source_order=0,
        tournament_id="event",
        tournament_name="event",
        tournament_level="WTA",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id="a",
        player_b_id="b",
        player_a_name="A",
        player_b_name="B",
        rank_a=10,
        rank_b=40,
        rank_points_a=3000,
        rank_points_b=1000,
    )
    return ChallengerExample(snapshot=snapshot, state=state, outcome_a=outcome)


@pytest.mark.parametrize("include_rank", [False, True])
def test_training_is_chronological_and_player_symmetric(include_rank: bool) -> None:
    training = [
        _example("one", date(2024, 1, 1), 1.0, True),
        _example("two", date(2024, 1, 2), -1.0, False),
    ]
    model = SimpleLogitChallenger(include_rank=include_rank).fit(training)
    target = _example("future", date(2025, 1, 1), 0.7, None)
    probability = model.predict_probability_a(target)
    flipped_values = {name: -getattr(target.snapshot, name) for name in BASE_FEATURES}
    swapped = ChallengerExample(
        snapshot=replace(target.snapshot, **flipped_values),
        state=replace(
            target.state,
            player_a_id="b",
            player_b_id="a",
            rank_a=40,
            rank_b=10,
            rank_points_a=1000,
            rank_points_b=3000,
        ),
    )
    assert model.predict_probability_a(swapped) == pytest.approx(1 - probability)
    with pytest.raises(ValueError, match="after every training"):
        model.predict_probability_a(training[0])


def test_ranking_arm_refuses_missing_values_and_identity_mismatch() -> None:
    training = [_example("one", date(2024, 1, 1), 1.0, True)]
    with pytest.raises(ValueError, match="positive ranks"):
        SimpleLogitChallenger(include_rank=True).fit(
            [replace(training[0], state=replace(training[0].state, rank_a=None))]
        )
    with pytest.raises(ValueError, match="different matches"):
        SimpleLogitChallenger().fit(
            [replace(training[0], state=replace(training[0].state, match_id="other"))]
        )
    with pytest.raises(ValueError, match="positive ranks"):
        SimpleLogitChallenger(include_rank=True).fit(
            [replace(training[0], state=replace(training[0].state, rank_points_a=float("nan")))]
        )


def test_unfitted_and_unlabeled_training_are_rejected() -> None:
    target = _example("future", date(2025, 1, 1), 0.7, None)
    model = SimpleLogitChallenger()
    with pytest.raises(RuntimeError, match="fitted"):
        model.predict_probability_a(target)
    with pytest.raises(ValueError, match="labeled"):
        model.fit([target])


@pytest.mark.parametrize("include_rank", [False, True])
def test_frozen_artifact_round_trip_and_tamper_rejection(include_rank: bool) -> None:
    training = [
        _example("one", date(2024, 1, 1), 1.0, True),
        _example("two", date(2024, 1, 2), -1.0, False),
    ]
    fitted = SimpleLogitChallenger(include_rank=include_rank).fit(training)
    frozen = fitted.freeze(
        tour="WTA",
        training_population_sha256="a" * 64,
        source_manifest_sha256="b" * 64,
    )
    record = frozen.sealed_record()
    restored = type(frozen).from_sealed_record(record)
    target = _example("future", date(2025, 1, 1), 0.7, None)
    assert restored.predict_probability_a(target) == pytest.approx(
        fitted.predict_probability_a(target), abs=1e-12
    )
    tampered = deepcopy(record)
    tampered["payload"]["coefficients"][0] += 0.1
    with pytest.raises(ValueError, match="hash mismatch"):
        type(frozen).from_sealed_record(tampered)
    with pytest.raises(ValueError, match="after frozen training"):
        restored.predict_probability_a(training[0])
    with pytest.raises(ValueError, match="training tour"):
        fitted.freeze(
            tour="ATP",
            training_population_sha256="a" * 64,
            source_manifest_sha256="b" * 64,
        )
