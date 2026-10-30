from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.probe_api_tennis_tournament_metadata import capture


def test_metadata_probe_retains_one_bounded_market_blind_response(tmp_path: Path) -> None:
    urls: list[str] = []
    raw = json.dumps(
        {"success": 1, "result": [{"player_key": "7", "player_bday": "01.01.2000"}]}
    ).encode()

    def provider(url: str) -> bytes:
        urls.append(url)
        return raw

    output = tmp_path / "profile"
    manifest = capture(
        api_key="test-secret",
        method="get_players",
        tournament_key=3076,
        season=2026,
        output_dir=output,
        provider_get=provider,
    )
    assert len(urls) == 1
    assert "method=get_players" in urls[0]
    assert "tournament_key=3076" in urls[0]
    assert manifest["result_count"] == 1
    assert manifest["sample_keys"] == ["player_bday", "player_key"]
    assert manifest["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert "test-secret" not in (output / "manifest.json").read_text()
    with pytest.raises(ValueError, match="must begin empty"):
        capture(
            api_key="test-secret",
            method="get_players",
            tournament_key=3076,
            season=2026,
            output_dir=output,
            provider_get=provider,
        )
    assert len(urls) == 1


def test_metadata_probe_rejects_market_fields(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="market fields"):
        capture(
            api_key="test-secret",
            method="get_draw",
            tournament_key=3076,
            season=2026,
            output_dir=tmp_path / "draw",
            provider_get=lambda _url: b'{"success":1,"result":{"odds":{"a":2}}}',
        )
