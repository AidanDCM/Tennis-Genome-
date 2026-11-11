"""Regression tests for fail-closed WTA legacy round matching.

Synthetic rows only: no historical settlement or provider semantics inferred.
"""

from __future__ import annotations

import pytest

from scripts.web_shadow_wta_result_core import _match_row


def _pending(*, source_match_id: str | None, round_name: str = "R32") -> dict:
    return {
        "source_match_id": source_match_id,
        "tournament": {"group_id": 1024, "year": 2026},
        "player_pair": ("alphaone", "betatwo"),
        "round": round_name,
    }


def _row(*, match_id: str = "LS001", round_id: str = "5",
         first_a: str = "Alpha", last_a: str = "One") -> dict:
    return {
        "DrawMatchType": "S",
        "DrawLevelType": "M",
        "EventID": "1024",
        "EventYear": 2026,
        "MatchID": match_id,
        "RoundID": round_id,
        "PlayerNameFirstA": first_a,
        "PlayerNameLastA": last_a,
        "PlayerNameFirstB": "Beta",
        "PlayerNameLastB": "Two",
    }


@pytest.mark.parametrize("round_id", ["1", "2", "3", "4", "6", "7", "Q", "S", "F"])
def test_legacy_rejects_wrong_or_uninterpretable_round(round_id: str) -> None:
    assert _match_row(_pending(source_match_id=None), [_row(round_id=round_id)]) is None


def test_legacy_accepts_unique_matching_round_and_full_names() -> None:
    assert _match_row(_pending(source_match_id=None), [_row()])["source_match_id"] == "LS001"


def test_legacy_rejects_same_round_wrong_full_player_identity() -> None:
    assert _match_row(
        _pending(source_match_id=None),
        [_row(first_a="Gamma", last_a="Three")],
    ) is None


def test_legacy_rejects_ambiguous_same_round_pair() -> None:
    with pytest.raises(ValueError, match="ambiguous"):
        _match_row(
            _pending(source_match_id=None),
            [_row(match_id="LS001"), _row(match_id="LS002")],
        )


def test_exact_match_id_can_retain_round_discrepancy_but_not_player_discrepancy() -> None:
    pending = _pending(source_match_id="LS001")
    assert _match_row(pending, [_row(round_id="2")])["round"] == "SF"
    with pytest.raises(ValueError, match="player identity mismatch"):
        _match_row(
            pending,
            [_row(round_id="2", first_a="Gamma", last_a="Three")],
        )


def test_exact_match_id_rejects_duplicate_provider_ids() -> None:
    with pytest.raises(ValueError, match="not unique"):
        _match_row(
            _pending(source_match_id="LS001"),
            [_row(), _row()],
        )
