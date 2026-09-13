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


def _atp_payload() -> dict[str, object]:
    _, atp_input, _ = _calculator_and_inputs()
    payload = asdict(atp_input)
    payload["created_at"] = atp_input.created_at.isoformat()
    payload["prediction_cutoff_at"] = atp_input.prediction_cutoff_at.isoformat()
    payload["source_manifest_hashes"] = list(atp_input.source_manifest_hashes)
    payload["foundational"]["event_date"] = atp_input.foundational.event_date.isoformat()
    payload["profile_pair"]["event_date"] = atp_input.profile_pair.event_date.isoformat()
    for side in ("player_a", "player_b"):
        profile = payload["profile_pair"][side]
        profile["valid_from"] = profile["valid_from"].isoformat()
        if profile["valid_until"] is not None:
            profile["valid_until"] = profile["valid_until"].isoformat()
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


def test_provider_neutral_payload_rejects_invalid_manifest_hash() -> None:
    payload = _payload()
    payload["source_manifest_hashes"] = ["NOT-A-SHA256"]
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        matchup_input_from_dict(payload)


def test_provider_neutral_payload_rejects_undeclared_market_input() -> None:
    payload = _payload()
    payload["market_odds_a"] = 1.91
    with pytest.raises(ValueError, match="market/outcome fields are forbidden"):
        matchup_input_from_dict(payload)


def test_provider_neutral_payload_rejects_nested_market_input() -> None:
    payload = _atp_payload()
    payload["profile_pair"]["market_odds_a"] = 1.91
    with pytest.raises(ValueError, match="market/outcome fields are forbidden"):
        matchup_input_from_dict(payload)


def test_provider_neutral_payload_rejects_undeclared_profile_pair_field() -> None:
    payload = _atp_payload()
    payload["profile_pair"]["unexpected_context"] = "ignored-before-hardening"
    with pytest.raises(ValueError, match="undeclared profile_pair fields"):
        matchup_input_from_dict(payload)
