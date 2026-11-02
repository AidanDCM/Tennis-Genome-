import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.capture_wta_official_fixed_sample import (
    _check_match,
    _reference,
    verify_official_capture,
)


def _case():
    provider = {
        "event_key": 99,
        "event_date": "2026-11-01",
        "event_winner": "First Player",
        "event_qualification": "True",
        "event_first_player": "A. Sasnovich",
        "event_second_player": "C. Y. Lee",
        "first_player_key": 1,
        "second_player_key": 2,
    }
    official = {
        "EventID": "1074",
        "MatchID": "RS004",
        "DrawMatchType": "S",
        "MatchState": "F",
        "MatchTimeStamp": "2026-11-01T01:44:51+00:00",
        "Winner": "2",
        "DrawLevelType": "Q",
        "PlayerNameFirstA": "Aliaksandra",
        "PlayerNameLastA": "Sasnovich",
        "PlayerNameFirstB": "Carol Young Suh",
        "PlayerNameLastB": "Lee",
    }
    entry = {"tournament_id": 1074, "match_id": "RS004", "slug": "hong-kong"}
    return provider, official, entry


def test_matches_multi_initials_and_parsed_qualification() -> None:
    provider, official, entry = _case()
    with (
        patch(
            "scripts.capture_wta_official_fixed_sample.parse_api_tennis_match_enrichment",
            return_value=SimpleNamespace(qualification=True),
        ),
        patch(
            "scripts.capture_wta_official_fixed_sample.api_tennis_point_count_issues",
            return_value=(),
        ),
    ):
        _check_match(provider, official, entry)
        stats = [
            {
                "setnum": 0,
                "eventid": "1074",
                "matchid": "RS004",
                "ptstotwonserva": 30,
                "totservplayeda": 50,
                "ptstotwonservb": 20,
                "totservplayedb": 40,
            }
        ]
        reference = _reference(provider, official, stats, entry)
        assert reference["players"][1]["official_service_points_total"] == 40
        official["Winner"] = "3"
        with pytest.raises(ValueError, match="winners disagree"):
            _check_match(provider, official, entry)


def test_offline_verification_rejects_changed_raw_bytes(tmp_path) -> None:
    raw = b"[]"
    (tmp_path / "wta-raw.json").write_bytes(raw)
    (tmp_path / "reference.json").write_bytes(raw)
    manifest = {
        "schema_version": "tennis-genome-wta-official-fixed-sample-capture-v1",
        "official_public_request_count": 1,
        "api_tennis_provider_request_count": 0,
        "requests": [
            {
                "filename": "wta-raw.json",
                "url": "https://api.wtatennis.com/tennis/match",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        ],
        "reference_sha256": hashlib.sha256(raw).hexdigest(),
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    verify_official_capture(tmp_path)
    (tmp_path / "wta-raw.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="raw file hash mismatch"):
        verify_official_capture(tmp_path)
