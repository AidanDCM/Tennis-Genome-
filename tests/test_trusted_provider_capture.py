from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.trusted_provider_capture import (
    TRUSTED_CAPTURE_SCHEMA,
    TRUSTED_CAPTURE_VERSION,
    ProviderHttpResponse,
    capture_trusted_provider_batch,
    fetch_daily_summary_pages,
)


def _summary(event_id: str, *, start: datetime) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start.isoformat(),
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:trusted-capture-test",
                    "name": "Trusted Capture Test",
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
    status: int = 200,
) -> ProviderHttpResponse:
    body = json.dumps(
        {
            "generated_at": generated_at.isoformat(),
            "summaries": summaries,
        },
        sort_keys=True,
    ).encode("utf-8")
    return ProviderHttpResponse(
        status=status,
        body=body,
        headers=(
            ("Content-Type", "application/json"),
            ("X-Max-Results", str(total)),
            ("X-Offset", str(offset)),
            ("X-Result", str(len(summaries))),
            ("Cache-Control", "public, max-age=300"),
        ),
    )


def test_trusted_capture_fetches_complete_pages_and_derives_batch(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 12, tzinfo=UTC)
    observed = generated + timedelta(minutes=2)
    starts: list[int] = []
    seen_headers: list[dict[str, str]] = []

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        start = int(query["start"][0])
        starts.append(start)
        seen_headers.append(headers)
        assert parsed.scheme == "https"
        assert parsed.netloc == "api.sportradar.com"
        assert parsed.path == "/tennis/production/v3/en/schedules/2026-09-15/summaries.json"
        assert query["limit"] == ["200"]
        if start == 0:
            return _response(
                generated_at=generated,
                summaries=[
                    _summary(
                        "sr:sport_event:trusted-1",
                        start=observed + timedelta(hours=2),
                    )
                ],
                total=2,
                offset=0,
            )
        if start == 1:
            return _response(
                generated_at=generated + timedelta(seconds=20),
                summaries=[
                    _summary(
                        "sr:sport_event:trusted-2",
                        start=observed + timedelta(hours=3),
                    )
                ],
                total=2,
                offset=1,
            )
        raise AssertionError(f"unexpected pagination start {start}")

    result = capture_trusted_provider_batch(
        output_dir=tmp_path / "capture",
        schedule_date=date(2026, 9, 15),
        access_level="production",
        api_key="provider-secret",
        provider_get=fake_get,
        now=lambda: observed,
    )

    assert starts == [0, 1]
    assert all(headers["x-api-key"] == "provider-secret" for headers in seen_headers)
    record = result["record"]
    assert record["page_count"] == 2
    assert record["raw_summary_count"] == 2
    assert record["provider_generated_at_min"] == generated.isoformat()
    assert record["provider_generated_at_max"] == (generated + timedelta(seconds=20)).isoformat()
    assert record["observed_at"] == observed.isoformat()
    assert result["anchor_packet"]["inputs"]["batch_record_sha256"] == record["record_sha256"]

    receipt = result["trusted_capture_receipt"]
    assert receipt["schema_version"] == TRUSTED_CAPTURE_SCHEMA
    assert receipt["capture_version"] == TRUSTED_CAPTURE_VERSION
    assert receipt["transport"] == "GITHUB_ACTIONS_HTTPS_X_API_KEY"
    assert receipt["batch_record_sha256"] == record["record_sha256"]
    assert len(str(receipt["receipt_sha256"])) == 64

    store = ProviderBatchStore(tmp_path / "capture" / "provider-batch-store")
    assert store.verify()["record_count"] == 1
    assert (tmp_path / "capture" / "trusted_capture_receipt.json").is_file()
    assert (tmp_path / "capture" / "anchor_packet.json").is_file()
    assert len(list((tmp_path / "capture" / "pages").glob("*.json"))) == 2
    assert len(list((tmp_path / "capture" / "pages").glob("*.headers"))) == 2


def test_missing_api_key_fails_before_provider_request(tmp_path: Path) -> None:
    called = False

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        nonlocal called
        called = True
        raise AssertionError((url, headers))

    with pytest.raises(ValueError, match="SPORTRADAR_API_KEY"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="",
            provider_get=fake_get,
        )
    assert called is False


@pytest.mark.parametrize("access_level", ["", "advanced", "prod"])
def test_unfrozen_access_level_is_rejected(tmp_path: Path, access_level: str) -> None:
    with pytest.raises(ValueError, match="trial or production"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level=access_level,
            api_key="provider-secret",
        )


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_non_200_provider_response_fails_closed(tmp_path: Path, status: int) -> None:
    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return ProviderHttpResponse(
            status=status,
            body=b"{}",
            headers=(("X-Max-Results", "0"), ("X-Offset", "0"), ("X-Result", "0")),
        )

    with pytest.raises(ValueError, match=f"HTTP {status}"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
        )


def test_non_json_provider_response_fails_closed(tmp_path: Path) -> None:
    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return ProviderHttpResponse(
            status=200,
            body=b"<html>not json</html>",
            headers=(("X-Max-Results", "0"), ("X-Offset", "0"), ("X-Result", "0")),
        )

    with pytest.raises(ValueError, match="UTF-8 JSON"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
        )


def test_missing_provider_generated_at_fails_closed(tmp_path: Path) -> None:
    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return ProviderHttpResponse(
            status=200,
            body=b'{"summaries":[]}',
            headers=(("X-Max-Results", "0"), ("X-Offset", "0"), ("X-Result", "0")),
        )

    with pytest.raises(ValueError, match="generated_at"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
        )


def test_pagination_total_drift_fails_closed(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 12, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del headers
        start = int(parse_qs(urlparse(url).query)["start"][0])
        if start == 0:
            return _response(
                generated_at=generated,
                summaries=[
                    _summary(
                        "sr:sport_event:drift-1",
                        start=generated + timedelta(hours=2),
                    )
                ],
                total=2,
                offset=0,
            )
        return _response(
            generated_at=generated,
            summaries=[
                _summary(
                    "sr:sport_event:drift-2",
                    start=generated + timedelta(hours=3),
                )
            ],
            total=3,
            offset=1,
        )

    with pytest.raises(ValueError, match="disagree on X-Max-Results"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
        )


def test_pagination_offset_mismatch_fails_closed(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 12, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return _response(
            generated_at=generated,
            summaries=[_summary("sr:sport_event:offset", start=generated + timedelta(hours=2))],
            total=1,
            offset=1,
        )

    with pytest.raises(ValueError, match="X-Offset differs"):
        fetch_daily_summary_pages(
            output_dir=tmp_path,
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
        )


def test_zero_result_day_is_one_complete_provider_page(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 0, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return _response(
            generated_at=generated,
            summaries=[],
            total=0,
            offset=0,
        )

    pages = fetch_daily_summary_pages(
        output_dir=tmp_path,
        schedule_date=date(2026, 9, 15),
        access_level="trial",
        api_key="provider-secret",
        provider_get=fake_get,
    )
    assert len(pages) == 1


def test_observation_time_is_runner_derived_and_provider_bounded(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 12, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return _response(generated_at=generated, summaries=[], total=0, offset=0)

    with pytest.raises(ValueError, match="provider-generation lag"):
        capture_trusted_provider_batch(
            output_dir=tmp_path / "late",
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
            now=lambda: generated + timedelta(minutes=11),
        )


def test_provider_generation_after_runner_clock_fails_closed(tmp_path: Path) -> None:
    generated = datetime(2026, 9, 15, 12, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del url, headers
        return _response(generated_at=generated, summaries=[], total=0, offset=0)

    with pytest.raises(ValueError, match="cannot predate provider generated_at"):
        capture_trusted_provider_batch(
            output_dir=tmp_path / "clock-skew",
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
            now=lambda: generated - timedelta(seconds=1),
        )


def test_page_generation_spread_rule_is_preserved(tmp_path: Path) -> None:
    first = datetime(2026, 9, 15, 12, tzinfo=UTC)

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        del headers
        start = int(parse_qs(urlparse(url).query)["start"][0])
        if start == 0:
            return _response(
                generated_at=first,
                summaries=[_summary("sr:sport_event:spread-1", start=first + timedelta(hours=2))],
                total=2,
                offset=0,
            )
        return _response(
            generated_at=first + timedelta(minutes=11),
            summaries=[_summary("sr:sport_event:spread-2", start=first + timedelta(hours=3))],
            total=2,
            offset=1,
        )

    with pytest.raises(ValueError, match="spread exceeds frozen 10-minute"):
        capture_trusted_provider_batch(
            output_dir=tmp_path / "spread",
            schedule_date=date(2026, 9, 15),
            access_level="production",
            api_key="provider-secret",
            provider_get=fake_get,
            now=lambda: first + timedelta(minutes=11),
        )
