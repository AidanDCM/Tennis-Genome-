from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import capture_api_tennis_trial_standings as standings


class _Response:
    status = 200

    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


def test_standings_capture_retains_both_raw_responses_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested: list[str] = []

    def provider(request: object, *, timeout: int) -> _Response:
        assert timeout == 90
        url = request.full_url  # type: ignore[attr-defined]
        requested.append(url)
        tour = "ATP" if "event_type=ATP" in url else "WTA"
        return _Response(
            json.dumps(
                {
                    "success": 1,
                    "result": [
                        {"player_key": "123", "place": "1", "league": tour, "points": "1000"}
                    ],
                }
            ).encode()
        )

    monkeypatch.setattr(standings, "urlopen", provider)
    output = tmp_path / "standings"
    manifest = standings.capture(api_key="test-secret", output_dir=output)
    assert len(requested) == 2
    assert "event_type=ATP" in requested[0]
    assert "event_type=WTA" in requested[1]
    assert manifest["provider_request_count"] == 2
    assert manifest["rank_as_of_assumed"] is False
    assert manifest["atp_count"] == manifest["wta_count"] == 1
    for tour in ("atp", "wta"):
        raw = (output / f"raw-{tour}-standings.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest[f"raw_{tour}_sha256"]
    assert "test-secret" not in (output / "manifest.json").read_text()
    with pytest.raises(ValueError, match="must begin empty"):
        standings.capture(api_key="test-secret", output_dir=output)
