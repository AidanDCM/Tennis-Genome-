from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from math import log
from pathlib import Path

import pytest

from tennis_genome.models.profile_strength import ProfileStrengthModel
from tennis_genome.profiles.features import profile_strength_feature_names
from tennis_genome.profiles.serialization import profile_record
from tennis_genome.profiles.state import MatchProfilePair, PlayerProfileSnapshot


def _profile(
    player_id: str,
    *,
    tour: str = "ATP",
    elo_rating: float = 1500.0,
    serve_rating: float = 0.0,
    return_rating: float = 0.0,
    form: float = 0.0,
    minutes_14: float | None = 0.0,
    age: float | None = 27.0,
    height: int | None = 185,
) -> PlayerProfileSnapshot:
    return PlayerProfileSnapshot(
        player_id=player_id,
        player_name=player_id,
        tour=tour,  # type: ignore[arg-type]
        valid_from=date(2025, 1, 1),
        valid_until=None,
        profile_version="player-profile-v1",
        ranking=None,
        ranking_points=None,
        age_years=age,
        height_cm=height,
        hand=None,
        ioc=None,
        elo_rating=elo_rating,
        prior_matches=20,
        serve_rating=serve_rating,
        return_rating=return_rating,
        prior_serve_points=2000,
        prior_return_points=2000,
        form_result_30=form,
        form_result_90=form / 2.0,
        form_point_30=form / 3.0,
        form_point_90=form / 4.0,
        event_gap_days=5.0,
        minutes_7=minutes_14,
        minutes_14=minutes_14,
        minutes_28=minutes_14,
        matches_14=2,
        matches_28=4,
        previous_event_minutes=75,
        has_point_history=True,
        has_complete_14d_duration=minutes_14 is not None,
    )


def _pair(match_id: str, a: PlayerProfileSnapshot, b: PlayerProfileSnapshot) -> MatchProfilePair:
    return MatchProfilePair(
        match_id=match_id,
        event_date=date(2025, 1, 1),
        player_a=a,
        player_b=b,
    )


def _training_pairs() -> tuple[list[MatchProfilePair], list[bool]]:
    strong = _profile(
        "strong",
        elo_rating=1650.0,
        serve_rating=0.10,
        return_rating=0.08,
        form=0.12,
        minutes_14=80.0,
        age=26.0,
        height=190,
    )
    medium = _profile(
        "medium",
        elo_rating=1530.0,
        serve_rating=0.02,
        return_rating=0.01,
        form=0.02,
        minutes_14=140.0,
        age=28.0,
        height=185,
    )
    weak = _profile(
        "weak",
        elo_rating=1390.0,
        serve_rating=-0.08,
        return_rating=-0.07,
        form=-0.10,
        minutes_14=240.0,
        age=34.0,
        height=178,
    )
    pairs = [
        _pair("s-w", strong, weak),
        _pair("w-s", weak, strong),
        _pair("s-m", strong, medium),
        _pair("m-s", medium, strong),
        _pair("m-w", medium, weak),
        _pair("w-m", weak, medium),
    ]
    return pairs, [True, False, True, False, True, False]


def test_profile_strength_is_player_order_symmetric():
    pairs, outcomes = _training_pairs()
    model = ProfileStrengthModel("ATP").fit(pairs, outcomes)
    target = pairs[0]
    swapped = _pair("swapped", target.player_b, target.player_a)

    forward = model.predict_pair(target)
    reverse = model.predict_pair(swapped)

    assert forward.probability_a + reverse.probability_a == pytest.approx(1.0)
    assert forward.profile_score_a == pytest.approx(reverse.profile_score_b)
    assert forward.profile_score_b == pytest.approx(reverse.profile_score_a)
    assert forward.profile_gap_match == pytest.approx(-reverse.profile_gap_match)


def test_profile_strength_logit_and_gap_identities_hold():
    pairs, outcomes = _training_pairs()
    model = ProfileStrengthModel("ATP").fit(pairs, outcomes)
    prediction = model.predict_pair(pairs[0])

    profile_logit = log(prediction.probability_a / (1.0 - prediction.probability_a))
    elo_logit = log(
        prediction.elo_probability_a / (1.0 - prediction.elo_probability_a)
    )

    assert profile_logit == pytest.approx(
        prediction.profile_score_a - prediction.profile_score_b
    )
    assert elo_logit == pytest.approx(prediction.elo_score_a - prediction.elo_score_b)
    assert prediction.profile_gap_match == pytest.approx(profile_logit - elo_logit)


def test_wta_strict_and_conditional_feature_sets_preserve_frozen_grades():
    strict = profile_strength_feature_names("WTA")
    conditional = profile_strength_feature_names("WTA", include_conditional=True)

    assert "serve_rating" not in strict
    assert "return_rating" not in strict
    assert "age_years" not in strict
    assert "height_cm" not in strict
    assert "serve_rating" in conditional
    assert "return_rating" in conditional
    assert "age_years" not in conditional


def test_schema_facing_profile_record_is_complete_and_deterministic():
    snapshot = _profile("schema")
    record = profile_record(snapshot)
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "player_snapshot.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(record)
    assert set(record) == set(schema["properties"])
    assert record["profile_hash"] == snapshot.profile_hash
    assert record["valid_from"] == "2025-01-01"
    assert record["data_cutoff"] == "2025-01-01"
    assert profile_record(replace(snapshot, ranking=10))["profile_hash"] != record["profile_hash"]
