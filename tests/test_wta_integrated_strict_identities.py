"""Integration regression for page, row and configured WTA identities.

Synthetic data only; no production prediction or settlement evidence.
"""

import pytest

from scripts.web_shadow_wta_acquisition_core import _index_identities, _targets


@pytest.mark.parametrize("page_id", [0, "0", "00"])
def test_integrated_valid_page_identity(page_id):
    payload = {
        "pageInfo": {"page": page_id},
        "content": [{"tournamentGroup": {"id": "123"}, "year": "2026"}],
    }
    assert _index_identities(payload, year=2026, page=0) == ({(123, 2026)}, 1)


@pytest.mark.parametrize("page_id", [0.5, False, 1.5, "0.5", -1, " 0", "٠"])
def test_integrated_invalid_page_identity(page_id):
    payload = {"pageInfo": {"page": page_id}, "content": []}
    with pytest.raises(ValueError, match="page"):
        _index_identities(payload, year=2026, page=0)


def test_integrated_config_and_index_identity_agree():
    target = _targets({
        "tournaments": [{"group_id": "00123", "year": "02026", "slug": "example"}]
    })[0]
    payload = {
        "pageInfo": {"page": "0"},
        "content": [{"tournamentGroup": {"id": "123"}, "year": 2026}],
    }
    identities, count = _index_identities(payload, year=2026, page=0)
    assert count == 1
    assert (target["group_id"], target["year"]) in identities


@pytest.mark.parametrize(
    "metadata",
    [None, "unexpected", {}, {"pageSize": 100}],
)
def test_integrated_missing_page_metadata_rejected(metadata):
    payload = {"content": [], "pageInfo": metadata}
    with pytest.raises(ValueError, match="page metadata is missing"):
        _index_identities(payload, year=2026, page=0)


def test_integrated_absent_page_info_rejected():
    with pytest.raises(ValueError, match="page metadata is missing"):
        _index_identities({"content": []}, year=2026, page=0)


@pytest.mark.parametrize("page_id", [0, 1])
def test_integrated_archived_page_metadata_shape(page_id):
    # Provider archive 2026-10-14: both pages contain this metadata shape.
    payload = {
        "pageInfo": {
            "page": page_id,
            "numPages": 0,
            "pageSize": 100,
            "numEntries": 124,
        },
        "content": [],
    }
    assert _index_identities(payload, year=2026, page=page_id) == (set(), 0)
