"""Synthetic regression for strict WTA tournament identity parsing."""

import pytest

from scripts.web_shadow_wta_acquisition_core import (
    _index_identities,
    _strict_identity_int,
    _validate_tournament,
)


@pytest.mark.parametrize("value", [0, 123, "0", "123", "00123"])
def test_strict_identity_valid(value):
    assert _strict_identity_int(value) == int(value)


@pytest.mark.parametrize("value", [0.5, False, 2026.9, True, "１２３", -1, " 123", None])
def test_strict_identity_invalid(value):
    with pytest.raises(ValueError):
        _strict_identity_int(value)


@pytest.mark.parametrize("value", [0.5, False, "１２３", -1])
def test_index_skips_invalid_group_id(value):
    payload = {"content": [
        {"tournamentGroup": {"id": value}, "year": 2026},
        {"tournamentGroup": {"id": "123"}, "year": "2026"},
    ]}
    assert _index_identities(payload, year=2026, page=0) == ({(123, 2026)}, 2)


@pytest.mark.parametrize("value", [2026.9, True, "２０２６", -1])
def test_index_skips_invalid_year(value):
    payload = {"content": [
        {"tournamentGroup": {"id": 123}, "year": value},
        {"tournamentGroup": {"id": 123}, "year": 2026},
    ]}
    assert _index_identities(payload, year=2026, page=0) == ({(123, 2026)}, 2)


@pytest.mark.parametrize("value", [0.5, False, "１２３", -1])
def test_detail_rejects_invalid_group_id(value):
    with pytest.raises(ValueError, match="invalid"):
        _validate_tournament(
            {"tournamentGroup": {"id": value}, "year": 2026},
            group_id=123,
            year=2026,
        )


def test_detail_accepts_ascii_numeric_strings():
    _validate_tournament(
        {"tournamentGroup": {"id": "123"}, "year": "2026"},
        group_id=123,
        year=2026,
    )
