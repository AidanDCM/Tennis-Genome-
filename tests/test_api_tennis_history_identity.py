from __future__ import annotations

from scripts.audit_api_tennis_history_identity import (
    classify_identity,
    profile_identity_consistent,
)


def _registry():
    return {
        ("WTA", "ada example", "1999-01-02"): {"wta:id:101"},
        ("WTA", "ada example", "2000-02-03"): {"wta:id:202"},
    }


def test_profile_birthdate_resolves_ambiguous_name() -> None:
    status, candidate = classify_identity(
        tour="WTA",
        player_key=11,
        standing_name="Ada Example",
        profile={"player_full_name": "Ada Example", "player_bday": "02.01.1999"},
        registry=_registry(),
        name_index={("WTA", "ada example"): {"wta:id:101", "wta:id:202"}},
    )
    assert (status, candidate) == ("EXACT_NAME_BIRTHDATE", "wta:id:101")


def test_wrong_profile_birthdate_cannot_fall_back_to_standing_name() -> None:
    status, candidate = classify_identity(
        tour="WTA",
        player_key=11,
        standing_name="Ada Example",
        profile={"player_full_name": "Ada Example", "player_bday": "02.01.2001"},
        registry=_registry(),
        name_index={("WTA", "ada example"): {"wta:id:101"}},
    )
    assert (status, candidate) == ("PROFILE_NO_EXACT_MATCH", None)


def test_unique_standing_name_remains_name_only() -> None:
    status, candidate = classify_identity(
        tour="WTA",
        player_key=11,
        standing_name="Ada Example",
        profile=None,
        registry=_registry(),
        name_index={("WTA", "ada example"): {"wta:id:101"}},
    )
    assert (status, candidate) == ("NAME_ONLY_PROPOSAL", "wta:id:101")


def test_no_profile_or_standing_remains_unresolved() -> None:
    status, candidate = classify_identity(
        tour="WTA",
        player_key=11,
        standing_name=None,
        profile=None,
        registry=_registry(),
        name_index={},
    )
    assert (status, candidate) == ("NO_FULL_NAME", None)


def test_profile_comparison_ignores_mutable_stats_but_rejects_identity_change() -> None:
    original = {
        "player_full_name": "Ada Example",
        "player_bday": "02.01.1999",
        "stats": [{"season": "2026", "matches_won": 4}],
    }
    updated = {**original, "stats": [{"season": "2026", "matches_won": 7}]}
    conflicting = {**updated, "player_bday": "03.01.1999"}

    assert profile_identity_consistent(original, updated)
    assert not profile_identity_consistent(original, conflicting)
