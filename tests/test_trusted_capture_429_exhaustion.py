"""Fail-closed regression for exhausted trusted-provider HTTP throttling."""

from __future__ import annotations

from datetime import date
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError

import pytest

import tennis_genome.prospective.trusted_provider_capture as capture


def test_repeated_http_429_never_publishes_trusted_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exhaust the actual transport retry loop without a live provider request."""
    calls: list[str] = []
    delays: list[float] = []
    headers = Message()
    headers["Retry-After"] = "0"
    monkeypatch.setattr(capture.time, "sleep", delays.append)

    def always_throttled(request: object, timeout: int) -> None:
        assert timeout == 30
        calls.append(str(request))
        raise HTTPError(
            "https://api.sportradar.com/tennis/trial/v3/en/test.json",
            429,
            "Too Many Requests",
            headers,
            None,
        )

    monkeypatch.setattr(capture, "urlopen", always_throttled)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        capture.capture_trusted_provider_batch(
            output_dir=tmp_path,
            schedule_date=date(2026, 11, 17),
            access_level="trial",
            api_key="test-only-secret",
        )

    assert len(calls) == capture._MAX_HTTP_429_RETRIES + 1
    assert delays == pytest.approx([1.05, 2.10, 4.20, 8.40])
    assert not (tmp_path / "trusted_capture_receipt.json").exists()
    assert not (tmp_path / "anchor_packet.json").exists()
    assert not list((tmp_path / "pages").glob("*"))
