from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord
from .sportradar_season_summaries_census import ProviderHttpResponse
from .sportradar_timeline_candidate_queue import TimelineCandidateQueue

PROBE_ID = "SPORTRADAR-TIMELINE-COST-PROBE-001"
_PAGE_LIMIT = 200
_TRIAL_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_SPORTRADAR_HOST = "https://api.sportradar.com"
_ALLOWED_ACCESS = frozenset({"trial", "production"})

ProviderGet = Callable[[str, dict[str, str]], ProviderHttpResponse]
Sleeper = Callable[[float], None]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _header_map(headers: tuple[tuple[str, str], ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers:
        lowered = key.strip().lower()
        if lowered in result:
            raise ValueError(f"duplicate provider response header: {lowered}")
        result[lowered] = value.strip()
    return result


def _required_nonnegative_int(headers: dict[str, str], key: str) -> int:
    if key not in headers:
        raise ValueError(f"provider response missing {key}")
    try:
        value = int(headers[key])
    except ValueError as exc:
        raise ValueError(f"provider response {key} is not an integer") from exc
    if value < 0:
        raise ValueError(f"provider response {key} must be non-negative")
    return value


def _aware_generated_at(payload: dict[str, object]) -> None:
    text = str(payload.get("generated_at", "")).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("cost-probe generated_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("cost-probe generated_at must be timezone-aware")
    parsed.astimezone(UTC)


def _url(*, access_level: str, season_id: str) -> str:
    query = urlencode({"start": 0, "limit": _PAGE_LIMIT})
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/en/"
        f"seasons/{season_id}/summaries.json?{query}"
    )


def _default_provider_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - frozen HTTPS host
            return ProviderHttpResponse(
                status=int(response.status),
                body=response.read(),
                headers=tuple((str(k), str(v)) for k, v in response.headers.raw_items()),
                http_version={10: "HTTP/1.0", 11: "HTTP/1.1"}.get(
                    getattr(response, "version", 11), "HTTP/1.1"
                ),
            )
    except HTTPError as exc:
        return ProviderHttpResponse(
            status=int(exc.code),
            body=exc.read(),
            headers=(
                tuple((str(k), str(v)) for k, v in exc.headers.raw_items())
                if exc.headers is not None
                else ()
            ),
            http_version="HTTP/1.1",
        )
    except URLError as exc:
        raise RuntimeError("Sportradar cost-probe HTTPS transport failed") from exc


class TimelineCostProbeRow(WorkbenchRecord):
    queue_position: int
    tour: str
    era: str
    level_family: str
    competition_id: str
    season_id: str
    disposition: str
    http_status: int
    total_event_upper_bound: int
    first_page_result_count: int
    additional_summary_page_upper_bound: int
    response_body_sha256: str
    response_headers_sha256: str

    @field_validator(
        "queue_position",
        "http_status",
        "total_event_upper_bound",
        "first_page_result_count",
        "additional_summary_page_upper_bound",
    )
    @classmethod
    def _nonnegative_counts(cls, value: int) -> int:
        if value < 0:
            raise ValueError("probe counts must be non-negative")
        return value


class TimelineCostProbe(WorkbenchRecord):
    probe_id: str = PROBE_ID
    queue_semantic_sha256: str
    access_level: str
    request_budget_cap: int
    provider_request_count: int
    probed_candidate_count: int
    unavailable_candidate_count: int
    rows: tuple[TimelineCostProbeRow, ...]

    @model_validator(mode="after")
    def _reproduce(self) -> "TimelineCostProbe":
        if self.access_level not in _ALLOWED_ACCESS:
            raise ValueError("unsupported Sportradar access level")
        if self.request_budget_cap <= 0:
            raise ValueError("request_budget_cap must be positive")
        if self.provider_request_count > self.request_budget_cap:
            raise ValueError("provider request count exceeds hard budget cap")
        if self.provider_request_count != len(self.rows):
            raise ValueError("one provider request is required per retained probe row")
        if self.probed_candidate_count != sum(
            row.disposition == "PROBED" for row in self.rows
        ):
            raise ValueError("probed candidate count does not reproduce")
        if self.unavailable_candidate_count != sum(
            row.disposition == "HISTORY_NOT_AVAILABLE" for row in self.rows
        ):
            raise ValueError("unavailable candidate count does not reproduce")
        return self


def _retain(
    *,
    output_dir: Path,
    queue_position: int,
    season_id: str,
    response: ProviderHttpResponse,
) -> tuple[Path, Path]:
    stem = f"{queue_position:03d}-{season_id.replace(':', '_')}"
    body = output_dir / "responses" / f"{stem}.json"
    headers = output_dir / "responses" / f"{stem}.headers"
    body.parent.mkdir(parents=True, exist_ok=True)
    if body.exists() or headers.exists():
        raise ValueError("cost probe would overwrite retained provider bytes")
    body.write_bytes(response.body)
    headers.write_bytes(response.headers_bytes())
    return body, headers


def _parse_success(response: ProviderHttpResponse) -> tuple[int, int]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cost probe response must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("cost probe response must be a JSON object")
    _aware_generated_at(payload)
    summaries = payload.get("summaries")
    if not isinstance(summaries, list):
        raise ValueError("cost probe summaries must be an array")
    headers = _header_map(response.headers)
    total = _required_nonnegative_int(headers, "x-max-results")
    offset = _required_nonnegative_int(headers, "x-offset")
    result_count = _required_nonnegative_int(headers, "x-result")
    if offset != 0:
        raise ValueError("first-page cost probe must report X-Offset 0")
    if result_count != len(summaries):
        raise ValueError("cost probe X-Result differs from JSON row count")
    if result_count > _PAGE_LIMIT or result_count > total:
        raise ValueError("cost probe pagination counts are inconsistent")
    if total == 0 and result_count != 0:
        raise ValueError("zero-total cost probe returned rows")
    return total, result_count


def capture_timeline_cost_probe(
    *,
    queue_path: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    request_budget_cap: int,
    provider_get: ProviderGet = _default_provider_get,
    sleeper: Sleeper = time.sleep,
) -> TimelineCostProbe:
    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    if request_budget_cap <= 0:
        raise ValueError("request_budget_cap must be positive")
    queue = TimelineCandidateQueue.model_validate_json(
        queue_path.read_text(encoding="utf-8")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("cost-probe output directory must begin empty")
    rows: list[TimelineCostProbeRow] = []
    for candidate in queue.rows:
        if len(rows) >= request_budget_cap:
            break
        if rows and access_level == "trial":
            sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
        response = provider_get(
            _url(access_level=access_level, season_id=candidate.season_id),
            {"x-api-key": api_key, "Accept": "application/json"},
        )
        body_path, headers_path = _retain(
            output_dir=output_dir,
            queue_position=candidate.queue_position,
            season_id=candidate.season_id,
            response=response,
        )
        if response.status in {404, 410}:
            rows.append(
                TimelineCostProbeRow(
                    queue_position=candidate.queue_position,
                    tour=candidate.tour,
                    era=candidate.era,
                    level_family=candidate.level_family,
                    competition_id=candidate.competition_id,
                    season_id=candidate.season_id,
                    disposition="HISTORY_NOT_AVAILABLE",
                    http_status=response.status,
                    total_event_upper_bound=0,
                    first_page_result_count=0,
                    additional_summary_page_upper_bound=0,
                    response_body_sha256=_sha256(body_path.read_bytes()),
                    response_headers_sha256=_sha256(headers_path.read_bytes()),
                )
            )
            continue
        if response.status in {401, 403}:
            raise RuntimeError(
                f"cost probe authentication/authorization failed with HTTP {response.status}"
            )
        if response.status == 429:
            raise RuntimeError("cost probe provider returned HTTP 429; stopped without retry")
        if response.status != 200:
            raise RuntimeError(f"cost probe provider returned unexpected HTTP {response.status}")
        total, first_page = _parse_success(response)
        remaining = max(0, total - first_page)
        rows.append(
            TimelineCostProbeRow(
                queue_position=candidate.queue_position,
                tour=candidate.tour,
                era=candidate.era,
                level_family=candidate.level_family,
                competition_id=candidate.competition_id,
                season_id=candidate.season_id,
                disposition="PROBED",
                http_status=200,
                total_event_upper_bound=total,
                first_page_result_count=first_page,
                additional_summary_page_upper_bound=math.ceil(remaining / _PAGE_LIMIT),
                response_body_sha256=_sha256(body_path.read_bytes()),
                response_headers_sha256=_sha256(headers_path.read_bytes()),
            )
        )

    probe = TimelineCostProbe(
        queue_semantic_sha256=queue.semantic_sha256,
        access_level=access_level,
        request_budget_cap=request_budget_cap,
        provider_request_count=len(rows),
        probed_candidate_count=sum(row.disposition == "PROBED" for row in rows),
        unavailable_candidate_count=sum(
            row.disposition == "HISTORY_NOT_AVAILABLE" for row in rows
        ),
        rows=tuple(rows),
    )
    (output_dir / "cost-probe.json").write_text(
        json.dumps(probe.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "probe_semantic_sha256": probe.semantic_sha256,
                "queue_semantic_sha256": queue.semantic_sha256,
                "provider_request_count": probe.provider_request_count,
                "probed_candidate_count": probe.probed_candidate_count,
                "unavailable_candidate_count": probe.unavailable_candidate_count,
                "total_event_upper_bound_sum": sum(
                    row.total_event_upper_bound for row in probe.rows
                ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return probe
