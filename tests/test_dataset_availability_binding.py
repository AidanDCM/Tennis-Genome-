from __future__ import annotations

import pytest

from tennis_genome.research_workbench import (
    fingerprint_match_population,
)


_ROWS = (
    {
        "match_id": "m1",
        "event_time": "2026-01-01T12:00:00+00:00",
        "player_a_id": "a",
        "player_b_id": "b",
        "tour": "ATP",
    },
    {
        "match_id": "m2",
        "event_time": "2026-01-01T15:00:00+00:00",
        "player_a_id": "c",
        "player_b_id": "d",
        "tour": "ATP",
    },
)


def _fingerprint(availability_sha: str):
    return fingerprint_match_population(
        dataset_id="availability-binding-test",
        ordered_rows=_ROWS,
        source_manifest_sha256="1" * 64,
        availability_contract_sha256=availability_sha,
        schema_version="canonical-v4",
    )


def test_dataset_identity_changes_when_availability_registry_changes() -> None:
    first = _fingerprint("2" * 64)
    changed = _fingerprint("3" * 64)

    assert first.row_identity_sha256 == changed.row_identity_sha256
    assert first.availability_contract_sha256 != changed.availability_contract_sha256
    assert first.sha256 != changed.sha256


@pytest.mark.parametrize(
    "invalid",
    ("", "2" * 63, "G" * 64, "sha256:" + "2" * 64),
)
def test_dataset_fingerprint_rejects_invalid_availability_registry_hash(
    invalid: str,
) -> None:
    with pytest.raises(ValueError, match="availability_contract_sha256"):
        _fingerprint(invalid)
