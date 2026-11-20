"""Strict configured WTA identities must not coerce malformed values."""

import pytest

from scripts.web_shadow_wta_acquisition_core import _targets


@pytest.mark.parametrize("value", [0.5, False, 2026.9, True, "１２３", -1, " 123", None])
@pytest.mark.parametrize("field", ["group_id", "year"])
def test_targets_reject_malformed_identity(field, value):
    item = {"group_id": 123, "year": 2026, "slug": "example"}
    item[field] = value
    with pytest.raises(ValueError, match="intake tournament identity is invalid"):
        _targets({"tournaments": [item]})


@pytest.mark.parametrize("group_id,year", [(123, 2026), ("123", "2026"), ("00123", "02026")])
def test_targets_preserve_provider_compatible_identities(group_id, year):
    assert _targets({
        "tournaments": [{"group_id": group_id, "year": year, "slug": " example "}]
    }) == [{"group_id": 123, "year": 2026, "slug": "example"}]


def test_targets_reject_duplicate_normalized_identities():
    with pytest.raises(ValueError, match="duplicate configured WTA tournament identity"):
        _targets({"tournaments": [
            {"group_id": 123, "year": 2026, "slug": "first"},
            {"group_id": "00123", "year": "02026", "slug": "second"},
        ]})
