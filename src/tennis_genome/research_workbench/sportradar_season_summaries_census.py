from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .contracts import WorkbenchRecord
from .sportradar_exact_time_panel import (
    build_provider_access_failure_evidence,
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_season_inventory import SeasonInventoryRow
from .sportradar_start_time_audit import build_complete_season_summaries
from .sportradar_start_time_audit_v2 import derive_single_season_identity

CENSUS_ID = "SPORTRADAR-HISTORICAL-SEASON-SUMMARIES-CENSUS-001"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_LANGUAGE = "en"
_PAGE_LIMIT = 200
_MAX_PAGES = 20
_ALLOWED_ACCESS = frozenset({"trial", "production"})
_TRIAL_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_MAX_HTTP_429_RETRIES = 4
_MAX_RETRY_DELAY_SECONDS = 16.0
_TERMINAL_STATUSES = frozenset({"closed", "ended"})


@dataclass(frozen=True)
class ProviderHttpResponse:
    status: int
    body: bytes
    headers: tuple[tuple[str, str], ...]
    http_version: str = "HTTP/1.1"

    def headers_bytes(self) -> bytes:
        lines = [f"{self.http_version} {self.status}"]
        lines.extend(f"{name}: {value}" for name, value in self.headers)
        return ("\n".join(lines) + "\n").encode("iso-8859-1")


ProviderGet = Callable[[str, dict[str, str]], ProviderHttpResponse]
Sleeper = Callable[[float], None]
Now = Callable[[], datetime]
CensusDisposition = Literal["SUMMARIES_CAPTURED", "HISTORY_NOT_AVAILABLE"]


class SeasonSummariesCensusRow(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    competition_id: str
    season_id: str
    disposition: CensusDisposition
    page_count: int
    raw_summary_count: int
    played_terminal_count: int
    walkover_count: int
    nonterminal_count: int
    required_timeline_count: int
    required_timeline_event_ids: tuple[str, ...]
    season_summaries_sha256: str | None
    access_failure_semantic_sha256: str | None


class SeasonSummariesCensus(WorkbenchRecord):
    census_id: str = CENSUS_ID
    inventory_semantic_sha256: str
    inventory_snapshot_at: str
    access_level: str
    historical_candidate_count: int
    summaries_captured_count: int
    history_not_available_count: int
    provider_request_count: int
    total_raw_summary_count: int
    total_played_terminal_count: int
    total_walkover_count: int
    total_nonterminal_count: int
    total_required_timeline_count: int
    rows: tuple[SeasonSummariesCensusRow, ...]


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _aware_time(value: object, *, field: str) -> datetime:
    text = str(value if value is not None else "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _json_object(content: bytes, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _header_map(headers: tuple[tuple[str, str], ...]) -> dict[str, str]:
    return {str(name).strip().lower(): str(value).strip() for name, value in headers}


def _required_nonnegative_int(headers: dict[str, str], field: str) -> int:
    raw = headers.get(field, "")
    if not raw:
        raise ValueError(f"Sportradar response missing required {field} header")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Sportradar {field} header must be an integer") from exc
    if value < 0:
        raise ValueError(f"Sportradar {field} header must be non-negative")
    return value


def _rate_limit_retry_delay(exc: HTTPError, *, attempt: int) -> float:
    raw_retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
    if raw_retry_after is not None:
        try:
            retry_after = float(str(raw_retry_after).strip())
        except ValueError:
            retry_after = 0.0
        if retry_after > 0:
            return min(
                max(retry_after, _TRIAL_MIN_REQUEST_INTERVAL_SECONDS),
                _MAX_RETRY_DELAY_SECONDS,
            )
    return min(
        _TRIAL_MIN_REQUEST_INTERVAL_SECONDS * (2**attempt),
        _MAX_RETRY_DELAY_SECONDS,
    )


def _default_provider_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
    for attempt in range(_MAX_HTTP_429_RETRIES + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - frozen HTTPS host
                body = response.read()
                status = int(response.status)
                raw_headers = tuple(
                    (str(k), str(v)) for k, v in response.headers.raw_items()
                )
                version = {10: "HTTP/1.0", 11: "HTTP/1.1"}.get(
                    getattr(response, "version", 11),
                    "HTTP/1.1",
                )
        except HTTPError as exc:
            if exc.code == 429 and attempt < _MAX_HTTP_429_RETRIES:
                time.sleep(_rate_limit_retry_delay(exc, attempt=attempt))
                continue
            body = exc.read()
            raw_headers = tuple(
                (str(k), str(v)) for k, v in exc.headers.raw_items()
            ) if exc.headers is not None else ()
            return ProviderHttpResponse(
                status=int(exc.code),
                body=body,
                headers=raw_headers,
                http_version="HTTP/1.1",
            )
        except URLError as exc:
            raise RuntimeError("Sportradar HTTPS transport failed") from exc
        return ProviderHttpResponse(
            status=status,
            body=body,
            headers=raw_headers,
            http_version=version,
        )
    raise AssertionError("Sportradar HTTP retry loop exhausted unexpectedly")


def _default_now() -> datetime:
    return datetime.now(UTC)


def _url(*, access_level: str, season_id: str, start: int) -> str:
    encoded = quote(season_id, safe="")
    query = urlencode({"start": start, "limit": _PAGE_LIMIT})
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/{_LANGUAGE}/"
        f"seasons/{encoded}/summaries.json?{query}"
    )


def _retain_response(
    *,
    season_dir: Path,
    page_number: int,
    start: int,
    response: ProviderHttpResponse,
) -> tuple[Path, Path]:
    season_dir.mkdir(parents=True, exist_ok=True)
    raw_path = season_dir / f"page-{page_number:03d}-offset-{start:06d}.json"
    headers_path = season_dir / f"page-{page_number:03d}-offset-{start:06d}.headers"
    if raw_path.exists() or headers_path.exists():
        raise ValueError("Season Summaries page evidence would overwrite retained bytes")
    raw_path.write_bytes(response.body)
    headers_path.write_bytes(response.headers_bytes())
    return raw_path, headers_path


def _validate_page(
    response: ProviderHttpResponse,
    *,
    expected_start: int,
    expected_total: int | None,
) -> tuple[int, int, int]:
    if response.status != 200:
        raise ValueError(f"Season Summaries returned HTTP {response.status}")
    payload = _json_object(response.body, label="Sportradar Season Summaries response")
    _aware_time(payload.get("generated_at"), field="Season Summaries generated_at")
    summaries = payload.get("summaries")
    if not isinstance(summaries, list):
        raise ValueError("Season Summaries summaries must be an array")
    headers = _header_map(response.headers)
    total = _required_nonnegative_int(headers, "x-max-results")
    offset = _required_nonnegative_int(headers, "x-offset")
    result_count = _required_nonnegative_int(headers, "x-result")
    if offset != expected_start:
        raise ValueError("Season Summaries X-Offset differs from requested start")
    if expected_total is not None and total != expected_total:
        raise ValueError("Season Summaries pages disagree on X-Max-Results")
    if result_count != len(summaries):
        raise ValueError("Season Summaries X-Result differs from JSON row count")
    if result_count > _PAGE_LIMIT:
        raise ValueError("Season Summaries page exceeds frozen 200-row maximum")
    if total == 0:
        if offset != 0 or result_count != 0:
            raise ValueError("zero-result Season Summaries pagination is inconsistent")
    elif result_count == 0:
        raise ValueError("non-empty Season Summaries pagination returned empty page")
    if offset + result_count > total:
        raise ValueError("Season Summaries page extends beyond X-Max-Results")
    return total, offset, result_count


def _event_census(aggregate: dict[str, object]) -> tuple[int, int, int, tuple[str, ...]]:
    summaries = aggregate.get("summaries")
    if not isinstance(summaries, list):
        raise ValueError("aggregate summaries must be an array")
    played = 0
    walkovers = 0
    nonterminal = 0
    timeline_ids: list[str] = []
    for raw in summaries:
        if not isinstance(raw, dict):
            raise ValueError("summary row must be an object")
        event = raw.get("sport_event")
        status = raw.get("sport_event_status")
        if not isinstance(event, dict) or not isinstance(status, dict):
            raise ValueError("summary lacks sport_event or sport_event_status")
        event_id = str(event.get("id", "")).strip()
        if not event_id:
            raise ValueError("summary sport_event.id must be non-empty")
        provider_status = str(status.get("status", "")).strip().lower()
        winning_reason = str(status.get("winning_reason", "")).strip().lower()
        if provider_status not in _TERMINAL_STATUSES:
            nonterminal += 1
        elif winning_reason == "walkover":
            walkovers += 1
        else:
            played += 1
            timeline_ids.append(event_id)
    return played, walkovers, nonterminal, tuple(sorted(timeline_ids))


def _capture_one_season(
    *,
    season: SeasonInventoryRow,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet,
    sleeper: Sleeper,
    now: Now,
    request_counter: list[int],
) -> SeasonSummariesCensusRow:
    season_dir = output_dir / "seasons" / season.season_id.replace(":", "_")
    page_pairs: list[tuple[Path, Path]] = []
    expected_total: int | None = None
    start = 0
    for page_number in range(_MAX_PAGES):
        if request_counter[0] and access_level == "trial":
            sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
        response = provider_get(
            _url(access_level=access_level, season_id=season.season_id, start=start),
            {"x-api-key": api_key, "Accept": "application/json"},
        )
        request_counter[0] += 1
        raw_path, headers_path = _retain_response(
            season_dir=season_dir,
            page_number=page_number,
            start=start,
            response=response,
        )
        if response.status in {404, 410}:
            if page_number != 0 or start != 0:
                raise ValueError("Season Summaries became unavailable mid-pagination")
            attempted = now()
            if attempted.tzinfo is None or attempted.utcoffset() is None:
                raise ValueError("capture clock must be timezone-aware")
            evidence = build_provider_access_failure_evidence(
                season=season,
                endpoint_path=f"seasons/{season.season_id}/summaries.json",
                attempted_at=attempted,
                http_status=response.status,
                response_headers_path=headers_path,
                response_body_path=raw_path,
            )
            (season_dir / "access-failure.json").write_text(
                json.dumps(evidence.canonical_payload(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return SeasonSummariesCensusRow(
                tour=season.tour,
                competition_id=season.competition_id,
                season_id=season.season_id,
                disposition="HISTORY_NOT_AVAILABLE",
                page_count=0,
                raw_summary_count=0,
                played_terminal_count=0,
                walkover_count=0,
                nonterminal_count=0,
                required_timeline_count=0,
                required_timeline_event_ids=(),
                season_summaries_sha256=None,
                access_failure_semantic_sha256=evidence.semantic_sha256,
            )
        if response.status in {401, 403}:
            raise RuntimeError(
                f"Season Summaries authentication/authorization failed with HTTP {response.status}"
            )
        total, offset, result_count = _validate_page(
            response,
            expected_start=start,
            expected_total=expected_total,
        )
        if expected_total is None:
            expected_total = total
        page_pairs.append((raw_path, headers_path))
        next_start = offset + result_count
        if next_start == total:
            break
        if next_start <= start:
            raise ValueError("Season Summaries pagination did not advance")
        start = next_start
    else:
        raise ValueError("Season Summaries pagination exceeded frozen page maximum")

    aggregate = build_complete_season_summaries(page_pairs)
    summaries = aggregate.get("summaries")
    if not isinstance(summaries, list):
        raise AssertionError("complete Season Summaries aggregate lacks summaries")
    identity = derive_single_season_identity(summaries)
    if identity.season_id != season.season_id:
        raise ValueError("Season Summaries season identity differs from frozen inventory")
    if identity.competition_id != season.competition_id:
        raise ValueError("Season Summaries competition differs from frozen inventory")
    played, walkovers, nonterminal, timeline_ids = _event_census(aggregate)
    aggregate_sha = _sha256_bytes(_canonical_json(aggregate))
    return SeasonSummariesCensusRow(
        tour=season.tour,
        competition_id=season.competition_id,
        season_id=season.season_id,
        disposition="SUMMARIES_CAPTURED",
        page_count=len(page_pairs),
        raw_summary_count=len(summaries),
        played_terminal_count=played,
        walkover_count=walkovers,
        nonterminal_count=nonterminal,
        required_timeline_count=len(timeline_ids),
        required_timeline_event_ids=timeline_ids,
        season_summaries_sha256=aggregate_sha,
        access_failure_semantic_sha256=None,
    )


def capture_season_summaries_census(
    *,
    inventory_path: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
    sleeper: Sleeper = time.sleep,
    now: Now = _default_now,
) -> SeasonSummariesCensus:
    """Capture every historical candidate's Season Summaries before timeline selection."""

    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("Season Summaries census output directory must begin empty")

    inventory = parse_season_inventory_bytes(inventory_path.read_bytes())
    verify_season_inventory_integrity(inventory)
    candidates = tuple(
        sorted(
            (row for row in inventory.season_rows if row.status == "HISTORICAL_CANDIDATE"),
            key=lambda row: (row.tour, row.competition_id, row.start_date, row.season_id),
        )
    )
    if len(candidates) != inventory.historical_candidate_count:
        raise AssertionError("historical candidate count detached from frozen inventory")

    request_counter = [0]
    rows = tuple(
        _capture_one_season(
            season=season,
            output_dir=output_dir,
            access_level=access_level,
            api_key=api_key,
            provider_get=provider_get,
            sleeper=sleeper,
            now=now,
            request_counter=request_counter,
        )
        for season in candidates
    )
    if len(rows) != inventory.historical_candidate_count:
        raise AssertionError("not every historical candidate received a census disposition")

    captured = sum(row.disposition == "SUMMARIES_CAPTURED" for row in rows)
    unavailable = sum(row.disposition == "HISTORY_NOT_AVAILABLE" for row in rows)
    census = SeasonSummariesCensus(
        inventory_semantic_sha256=inventory.semantic_sha256,
        inventory_snapshot_at=inventory.snapshot_at,
        access_level=access_level,
        historical_candidate_count=inventory.historical_candidate_count,
        summaries_captured_count=captured,
        history_not_available_count=unavailable,
        provider_request_count=request_counter[0],
        total_raw_summary_count=sum(row.raw_summary_count for row in rows),
        total_played_terminal_count=sum(row.played_terminal_count for row in rows),
        total_walkover_count=sum(row.walkover_count for row in rows),
        total_nonterminal_count=sum(row.nonterminal_count for row in rows),
        total_required_timeline_count=sum(row.required_timeline_count for row in rows),
        rows=rows,
    )
    (output_dir / "census.json").write_text(
        json.dumps(census.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_bytes(
        _canonical_json(
            {
                "census_semantic_sha256": census.semantic_sha256,
                "historical_candidate_count": census.historical_candidate_count,
                "history_not_available_count": census.history_not_available_count,
                "provider_request_count": census.provider_request_count,
                "summaries_captured_count": census.summaries_captured_count,
                "total_required_timeline_count": census.total_required_timeline_count,
            }
        )
        + b"\n"
    )
    return census
