"""Strict index page identity regression; synthetic non-production data."""

import pytest

from scripts.web_shadow_wta_acquisition_core import _index_identities


@pytest.mark.parametrize("page_id", [0, "0", "00"])
def test_valid_page_identity(page_id):
    identities, count = _index_identities(
        {"content": [], "pageInfo": {"page": page_id}}, year=2026, page=0
    )
    assert identities == set()
    assert count == 0


@pytest.mark.parametrize("page_id", [0.5, False, 1.5, "0.5", -1, " 0", "٠"])
def test_invalid_page_identity(page_id):
    with pytest.raises(ValueError):
        _index_identities(
            {"content": [], "pageInfo": {"page": page_id}}, year=2026, page=0
        )


def test_page_mismatch_rejected():
    with pytest.raises(ValueError, match="mismatch"):
        _index_identities(
            {"content": [], "pageInfo": {"page": "1"}}, year=2026, page=0
        )
