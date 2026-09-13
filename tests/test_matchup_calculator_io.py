from __future__ import annotations

from dataclasses import asdict

import pytest

from tennis_genome.calculator.io import matchup_input_from_dict
from tests.test_matchup_calculator import _calculator_and_inputs


def _payload() -> dict[str, object]:
    _, _, wta_input = _calculator_and_inputs()
    payload = asdict(wta_input)
    payload["created_at"] = wta_input.created_at.isoformat()
    payload["prediction_cutoff_at"] = wta_input.prediction_cutoff_at.isoformat()
    payload["source_manifest_hashes"] = list(wta_input.source_manifest_hashes)
    payload["foundational"]["event_date"] = wta_input.foundational.event_date.isoformat()
    payload["serve_return"]["event_date"] = wta_input.serve_return.event_date.isoformat()
    return payload


def test_provider_neutral_payload_round_trips_wta_state() -> None:
    original_calculator, _, original = _calculator_and_inputs()
    parsed = matchup_input_from_dict(_payload())

    assert parsed == original
    assert original_calculator.calculate(parsed).prediction.match_id == original.match_id


def test_provider_neutral_payload_rejects_naive_cutoff() -> None:
    payload = _payload()
    payload["prediction_cutoff_at"] = "2026-09-19T17:55:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        matchup_input_from_dict(payload)


def test_provider_neutral_payload_requires_manifest_hash_array() -> None:
    payload = _payload()
    payload["source_manifest_hashes"] = "a" * 64
    with pytest.raises(ValueError, match="must be an array"):
        matchup_input_from_dict(payload)
