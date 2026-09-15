from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

import tennis_genome.prospective.trusted_provider_capture as trusted_capture


def _summary(event_id: str, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:rate-limit-test",
                    "name": "Rate Limit Test",
                    "type": "singles",
                },
            },
        },
        "sport_event_status": {"status": "not_started"},
    }


def _response(
    *,
    generated_at: datetime,
    summaries: list[dict[str, object]],
    total: int,
    offset: int,
) -> trusted_capture.ProviderHttpResponse:
    return trusted_capture.ProviderHttpResponse(
        status=200,
        body=json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "summaries": summaries,
            },
            sort_keys=True,
        ).encode("utf-8"),
        headers=(
            ("Content-Type", "application/json"),
            ("X-Max-Results", str(total)),
            ("X-Offset", str(offset)),
            ("X-Result", str(len(summaries))),
        ),
    )


def test_trial_pagination_paces_between_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = datetime(2026, 9, 15, 16, tzinfo=UTC)
    starts: list[int] = []
    sleeps: list[float] = []
    monkeypatch.setattr(trusted_capture.time, "sleep", sleeps.append)

    def fake_get(url: str, headers: dict[str, str]) -> trusted_capture.ProviderHttpResponse:
        assert headers["x-api-key"] == "provider-secret"
        start = int(parse_qs(urlparse(url).query)["start"][0])
        starts.append(start)
        if start == 0:
            return _response(
                generated_at=generated,
                summaries=[
                    _summary(
                        "sr:sport_event:rate-limit-1",
                        start=generated + timedelta(hours=1),
                    )
                ],
                total=2,
                offset=0,
            )
        return _response(
            generated_at=generated + timedelta(seconds=1),
            summaries=[
                _summary(
                    "sr:sport_event:rate-limit-2",
                    start=generated + timedelta(hours=2),
                )
            ],
            total=2,
            offset=1,
        )

    pages = trusted_capture.fetch_daily_summary_pages(
        output_dir=tmp_path,
        schedule_date=date(2026, 9, 15),
        access_level="trial",
        api_key="provider-secret",
        provider_get=fake_get,
    )

    assert len(pages) == 2
    assert starts == [0, 1]
    assert sleeps == [pytest.approx(1.05)]


def test_default_transport_retries_429_using_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    calls = 0
    monkeypatch.setattr(trusted_capture.time, "sleep", sleeps.append)

    rate_headers = Message()
    rate_headers["Retry-After"] = "2"
    rate_error = HTTPError(
        "https://api.sportradar.com/tennis/trial/v3/en/test.json",
        429,
        "Too Many Requests",
        rate_headers,
        None,
    )

    response_headers = Message()
    response_headers["Content-Type"] = "application/json"

    class SuccessResponse:
        status = 200
        version = 11
        headers = response_headers

        def read(self) -> bytes:
            return b"{}"

        def __enter__(self) -> SuccessResponse:
            return self

        def __exit__(self, *args: object) -> None:
            del args

    def fake_urlopen(request: object, timeout: int) -> SuccessResponse:
        nonlocal calls
        del request
        assert timeout == 30
        calls += 1
        if calls == 1:
            raise rate_error
        return SuccessResponse()

    monkeypatch.setattr(trusted_capture, "urlopen", fake_urlopen)

    response = trusted_capture._default_provider_get(
        "https://api.sportradar.com/tennis/trial/v3/en/test.json",
        {"x-api-key": "provider-secret", "Accept": "application/json"},
    )

    assert calls == 2
    assert sleeps == [2.0]
    assert response.status == 200
    assert response.body == b"{}"
