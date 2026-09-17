from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import model_validator

from .contracts import WorkbenchRecord

PROBE_ID = "API-TENNIS-SOURCE-ADMISSION-PROBE-001"
SOURCE_CONTRACT = "API_TENNIS_FIXTURES_V2_9_5_SCHEDULED_TIME_V1"
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


class ApiTennisSourceAudit(WorkbenchRecord):
    probe_id: Literal["API-TENNIS-SOURCE-ADMISSION-PROBE-001"] = PROBE_ID
    source_contract: Literal["API_TENNIS_FIXTURES_V2_9_5_SCHEDULED_TIME_V1"] = (
        SOURCE_CONTRACT
    )
    requested_date: str
    timezone: Literal["UTC"] = "UTC"
    provider_request_count: Literal[1] = 1
    raw_response_sha256: str
    fixture_count: int
    atp_singles_count: int
    wta_singles_count: int
    finished_count: int
    pointbypoint_nonempty_count: int
    statistics_nonempty_count: int
    scores_nonempty_count: int
    timestamp_like_paths: tuple[str, ...]
    separate_actual_start_field_paths: tuple[str, ...]
    historical_actual_start_admissible: Literal[False] = False
    supported_research_roles: tuple[str, ...]
    excluded_research_roles: tuple[str, ...]

    @model_validator(mode="after")
    def _reproduce(self) -> ApiTennisSourceAudit:
        if len(self.raw_response_sha256) != 64:
            raise ValueError("raw_response_sha256 must be a SHA-256 hex digest")
        if any(value < 0 for value in (
            self.fixture_count,
            self.atp_singles_count,
            self.wta_singles_count,
            self.finished_count,
            self.pointbypoint_nonempty_count,
            self.statistics_nonempty_count,
            self.scores_nonempty_count,
        )):
            raise ValueError("fixture counts must be non-negative")
        if self.atp_singles_count + self.wta_singles_count > self.fixture_count:
            raise ValueError("tour singles counts cannot exceed fixture count")
        for value in (
            self.finished_count,
            self.pointbypoint_nonempty_count,
            self.statistics_nonempty_count,
            self.scores_nonempty_count,
        ):
            if value > self.fixture_count:
                raise ValueError("fixture-derived counts cannot exceed fixture count")
        return self


def _default_provider_get(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - frozen HTTPS host
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


def inspect_fixture_payload(raw: bytes, *, requested_date: str) -> ApiTennisSourceAudit:
    try:
        parsed_date = date.fromisoformat(requested_date)
    except ValueError as exc:
        raise ValueError("requested_date must be YYYY-MM-DD") from exc
    if parsed_date.isoformat() != requested_date:
        raise ValueError("requested_date must use canonical YYYY-MM-DD form")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("API-Tennis response must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("API-Tennis response must be a JSON object")
    if payload.get("success") not in (1, "1"):
        raise ValueError("API-Tennis response did not report success")
    fixtures = payload.get("result")
    if not isinstance(fixtures, list):
        raise ValueError("API-Tennis fixtures result must be an array")

    walked = _walk_paths(payload)
    forbidden = sorted(
        path
        for path, _ in walked
        if any(token in path.rsplit(".", 1)[-1].lower() for token in _FORBIDDEN_RESPONSE_KEY_TOKENS)
    )
    if forbidden:
        raise ValueError("fixture response unexpectedly contains downstream market fields")

    timestamp_like_paths = tuple(
        sorted(
            {
                path
                for path, _ in walked
                if any(
                    token in path.rsplit(".", 1)[-1].lower()
                    for token in ("time", "date", "timestamp", "started", "updated", "upd")
                )
            }
        )
    )
    actual_start_paths = tuple(
        sorted(
            {
                path
                for path, _ in walked
                if path.rsplit(".", 1)[-1].lower() in _ACTUAL_START_KEY_CANDIDATES
            }
        )
    )

    def is_nonempty_list(row: dict[str, object], field: str) -> bool:
        value = row.get(field)
        return isinstance(value, list) and bool(value)

    fixture_rows = [row for row in fixtures if isinstance(row, dict)]
    if len(fixture_rows) != len(fixtures):
        raise ValueError("API-Tennis fixtures must contain only JSON objects")

    audit = ApiTennisSourceAudit(
        requested_date=requested_date,
        raw_response_sha256=hashlib.sha256(raw).hexdigest(),
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
            is_nonempty_list(row, "pointbypoint") for row in fixture_rows
        ),
        statistics_nonempty_count=sum(
            is_nonempty_list(row, "statistics") for row in fixture_rows
        ),
        scores_nonempty_count=sum(is_nonempty_list(row, "scores") for row in fixture_rows),
        timestamp_like_paths=timestamp_like_paths,
        separate_actual_start_field_paths=actual_start_paths,
        supported_research_roles=(
            "HISTORICAL_FIXTURE_IDENTITY",
            "HISTORICAL_MATCH_OUTCOME",
            "HISTORICAL_POINT_BY_POINT_WHEN_PRESENT",
            "HISTORICAL_SERVE_RETURN_STATISTICS_WHEN_PRESENT",
            "CURRENT_TOURNAMENT_STATE",
        ),
        excluded_research_roles=("HISTORICAL_ACTUAL_START_CHRONOLOGY",),
    )
    return audit


def capture_api_tennis_source_probe(
    *,
    requested_date: str,
    api_key: str,
    output_dir: Path,
    provider_get: ProviderGet = _default_provider_get,
) -> ApiTennisSourceAudit:
    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("API-Tennis probe output directory must begin empty")

    query = urlencode(
        {
            "method": "get_fixtures",
            "APIkey": api_key,
            "date_start": requested_date,
            "date_stop": requested_date,
            "timezone": "UTC",
        }
    )
    raw = provider_get(f"{_BASE_URL}?{query}")
    audit = inspect_fixture_payload(raw, requested_date=requested_date)

    (output_dir / "raw-fixtures.json").write_bytes(raw)
    (output_dir / "audit.json").write_text(
        json.dumps(audit.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "audit_semantic_sha256": audit.semantic_sha256,
                "provider_request_count": audit.provider_request_count,
                "raw_response_sha256": audit.raw_response_sha256,
                "historical_actual_start_admissible": audit.historical_actual_start_admissible,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return audit
