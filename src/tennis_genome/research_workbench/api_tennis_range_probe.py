from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord

PROBE_ID = "API-TENNIS-RANGE-PROBE-001"
SOURCE_CONTRACT = "API_TENNIS_FIXTURES_RANGE_V1"
_BASE_URL = "https://api.api-tennis.com/tennis/"
_FORBIDDEN_RESPONSE_KEY_TOKENS = ("odd", "bookmaker", "sportsbook")
_ACTUAL_START_KEY_CANDIDATES = {
    "actual_start",
    "actual_start_time",
    "actual_started_at",
    "event_started_at",
    "match_started",
    "match_started_at",
    "start_timestamp",
    "started_at",
}

ProviderGet = Callable[[str], bytes]


class ApiTennisRangeProbeAudit(WorkbenchRecord):
    probe_id: Literal["API-TENNIS-RANGE-PROBE-001"] = PROBE_ID
    source_contract: Literal["API_TENNIS_FIXTURES_RANGE_V1"] = SOURCE_CONTRACT
    date_start: str
    date_stop: str
    span_days: int
    timezone: Literal["UTC"] = "UTC"
    provider_request_count: Literal[1] = 1
    raw_response_sha256: str
    response_bytes: int
    fixture_count: int
    atp_singles_count: int
    wta_singles_count: int
    finished_count: int
    pointbypoint_nonempty_count: int
    statistics_nonempty_count: int
    scores_nonempty_count: int
    event_dates: tuple[str, ...]
    separate_actual_start_field_paths: tuple[str, ...]
    historical_actual_start_admissible: Literal[False] = False

    @field_validator("raw_response_sha256")
    @classmethod
    def _hash(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("raw_response_sha256 must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _validate_range(self) -> Self:
        start = date.fromisoformat(self.date_start)
        stop = date.fromisoformat(self.date_stop)
        expected_span = (stop - start).days + 1
        if expected_span < 1:
            raise ValueError("date_stop must not precede date_start")
        if expected_span > 7:
            raise ValueError("range probe may span at most seven calendar days")
        if self.span_days != expected_span:
            raise ValueError("span_days does not match date range")
        if self.response_bytes < 1:
            raise ValueError("response_bytes must be positive")
        counts = (
            self.fixture_count,
            self.atp_singles_count,
            self.wta_singles_count,
            self.finished_count,
            self.pointbypoint_nonempty_count,
            self.statistics_nonempty_count,
            self.scores_nonempty_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("fixture counts must be non-negative")
        if self.atp_singles_count + self.wta_singles_count > self.fixture_count:
            raise ValueError("tour singles counts cannot exceed fixture count")
        for event_date in self.event_dates:
            parsed = date.fromisoformat(event_date)
            if parsed < start or parsed > stop:
                raise ValueError("event date falls outside requested range")
        return self


def _default_provider_get(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - frozen HTTPS host
            if int(response.status) != 200:
                raise RuntimeError(f"API-Tennis returned HTTP {response.status}")
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"API-Tennis returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("API-Tennis HTTPS transport failed") from exc


def _walk_paths(value: object, *, prefix: str = "$") -> tuple[tuple[str, object], ...]:
    rows: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            rows.append((path, child))
            rows.extend(_walk_paths(child, prefix=path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_walk_paths(child, prefix=f"{prefix}[{index}]"))
    return tuple(rows)


def inspect_range_payload(
    raw: bytes,
    *,
    date_start: str,
    date_stop: str,
) -> ApiTennisRangeProbeAudit:
    start = date.fromisoformat(date_start)
    stop = date.fromisoformat(date_stop)
    span_days = (stop - start).days + 1
    if span_days < 1 or span_days > 7:
        raise ValueError("range probe requires between one and seven calendar days")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("API-Tennis response must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("API-Tennis response must be a JSON object")
    if payload.get("success") not in {1, "1"}:
        raise ValueError("API-Tennis response did not report success")
    fixtures = payload.get("result")
    if not isinstance(fixtures, list):
        raise ValueError("API-Tennis fixtures result must be an array")
    if any(not isinstance(row, dict) for row in fixtures):
        raise ValueError("API-Tennis fixtures must contain only JSON objects")

    walked = _walk_paths(payload)
    forbidden = sorted(
        path
        for path, _ in walked
        if any(
            token in path.rsplit(".", 1)[-1].lower()
            for token in _FORBIDDEN_RESPONSE_KEY_TOKENS
        )
    )
    if forbidden:
        raise ValueError("fixture response unexpectedly contains downstream market fields")

    actual_start_paths = tuple(
        sorted(
            {
                path
                for path, _ in walked
                if path.rsplit(".", 1)[-1].lower() in _ACTUAL_START_KEY_CANDIDATES
            }
        )
    )

    fixture_rows = [row for row in fixtures if isinstance(row, dict)]
    event_dates = tuple(
        sorted(
            {
                str(row.get("event_date", ""))
                for row in fixture_rows
                if str(row.get("event_date", "")).strip()
            }
        )
    )
    for event_date in event_dates:
        parsed = date.fromisoformat(event_date)
        if parsed < start or parsed > stop:
            raise ValueError("provider returned fixture outside requested date range")

    def nonempty_list(row: dict[str, object], field: str) -> bool:
        value = row.get(field)
        return isinstance(value, list) and bool(value)

    return ApiTennisRangeProbeAudit(
        date_start=date_start,
        date_stop=date_stop,
        span_days=span_days,
        raw_response_sha256=hashlib.sha256(raw).hexdigest(),
        response_bytes=len(raw),
        fixture_count=len(fixture_rows),
        atp_singles_count=sum(
            str(row.get("event_type_type", "")).strip().lower() == "atp singles"
            for row in fixture_rows
        ),
        wta_singles_count=sum(
            str(row.get("event_type_type", "")).strip().lower() == "wta singles"
            for row in fixture_rows
        ),
        finished_count=sum(
            str(row.get("event_status", "")).strip().lower() == "finished"
            for row in fixture_rows
        ),
        pointbypoint_nonempty_count=sum(
            nonempty_list(row, "pointbypoint") for row in fixture_rows
        ),
        statistics_nonempty_count=sum(
            nonempty_list(row, "statistics") for row in fixture_rows
        ),
        scores_nonempty_count=sum(nonempty_list(row, "scores") for row in fixture_rows),
        event_dates=event_dates,
        separate_actual_start_field_paths=actual_start_paths,
    )


def capture_api_tennis_range_probe(
    *,
    date_start: str,
    date_stop: str,
    api_key: str,
    output_dir: Path,
    provider_get: ProviderGet = _default_provider_get,
) -> ApiTennisRangeProbeAudit:
    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    start = date.fromisoformat(date_start)
    stop = date.fromisoformat(date_stop)
    span_days = (stop - start).days + 1
    if span_days < 1 or span_days > 7:
        raise ValueError("range probe requires between one and seven calendar days")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("API-Tennis range probe output directory must begin empty")

    query = urlencode(
        {
            "method": "get_fixtures",
            "APIkey": api_key,
            "date_start": date_start,
            "date_stop": date_stop,
            "timezone": "UTC",
        }
    )
    raw = provider_get(f"{_BASE_URL}?{query}")
    audit = inspect_range_payload(raw, date_start=date_start, date_stop=date_stop)

    (output_dir / "raw-fixtures.json").write_bytes(raw)
    (output_dir / "audit.json").write_text(
        json.dumps(audit.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "audit_semantic_sha256": audit.semantic_sha256,
                "provider_request_count": 1,
                "raw_response_sha256": audit.raw_response_sha256,
                "response_bytes": audit.response_bytes,
                "span_days": audit.span_days,
                "historical_actual_start_admissible": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return audit
