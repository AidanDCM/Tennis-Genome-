from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from tennis_genome.prospective.trusted_provider_capture import (
    ProviderHttpResponse,
    fetch_daily_summary_pages,
)


def test_provider_api_key_is_header_only(tmp_path: Path) -> None:
    secret = "provider-secret-must-not-enter-url"
    seen_url = ""
    seen_headers: dict[str, str] = {}

    def fake_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
        nonlocal seen_url, seen_headers
        seen_url = url
        seen_headers = dict(headers)
        body = json.dumps(
            {
                "generated_at": datetime(2026, 9, 15, tzinfo=UTC).isoformat(),
                "summaries": [],
            },
            sort_keys=True,
        ).encode("utf-8")
        return ProviderHttpResponse(
            status=200,
            body=body,
            headers=(
                ("X-Max-Results", "0"),
                ("X-Offset", "0"),
                ("X-Result", "0"),
            ),
        )

    fetch_daily_summary_pages(
        output_dir=tmp_path,
        schedule_date=date(2026, 9, 15),
        access_level="production",
        api_key=secret,
        provider_get=fake_get,
    )

    assert seen_url.startswith("https://api.sportradar.com/tennis/production/v3/en/")
    assert secret not in seen_url
    assert "api_key=" not in seen_url.lower()
    assert seen_headers["x-api-key"] == secret
