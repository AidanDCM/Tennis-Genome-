from __future__ import annotations

import pytest

from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_as_dict,
    crosswalk_mapping,
    seal_crosswalk,
    verify_crosswalk,
)


def test_crosswalk_is_deterministic_and_roundtrips() -> None:
    first = seal_crosswalk(
        {
            "sr:competitor:22": "canonical-b",
            "sr:competitor:11": "canonical-a",
        }
    )
    second = seal_crosswalk(
        {
            "sr:competitor:11": "canonical-a",
            "sr:competitor:22": "canonical-b",
        }
    )
    assert first.artifact_sha256 == second.artifact_sha256
    verified = verify_crosswalk(crosswalk_as_dict(first))
    assert verified.artifact_sha256 == first.artifact_sha256
    assert crosswalk_mapping(verified) == {
        "sr:competitor:11": "canonical-a",
        "sr:competitor:22": "canonical-b",
    }


def test_crosswalk_tampering_fails_digest() -> None:
    payload = crosswalk_as_dict(
        seal_crosswalk(
            {
                "sr:competitor:11": "canonical-a",
                "sr:competitor:22": "canonical-b",
            }
        )
    )
    payload["entries"][0]["canonical_player_id"] = "canonical-x"
    with pytest.raises(ValueError, match="digest"):
        verify_crosswalk(payload)


def test_crosswalk_requires_one_to_one_canonical_ids() -> None:
    with pytest.raises(ValueError, match="one-to-one"):
        seal_crosswalk(
            {
                "sr:competitor:11": "canonical-a",
                "sr:competitor:22": "canonical-a",
            }
        )


def test_crosswalk_rejects_blank_and_empty_inputs() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        seal_crosswalk({})
    with pytest.raises(ValueError, match="non-empty"):
        seal_crosswalk({"sr:competitor:11": ""})
