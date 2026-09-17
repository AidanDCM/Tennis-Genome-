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
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import model_validator

from .contracts import WorkbenchRecord
from .sportradar_season_summaries_census import (
    ProviderHttpResponse,
    SeasonSummariesCensus,
)
from .sportradar_start_time_admission import (
    admit_exact_time_audit_bytes,
    chronology_admission_failure_reasons,
    verify_exact_time_audit_integrity,
)
from .sportradar_start_time_audit import build_complete_season_summaries
from .sportradar_start_time_audit_v2 import audit_sportradar_start_time_coverage_v2
from .sportradar_timeline_audit_sample import TimelineAuditSamplePlan

CAPTURE_ID = "SPORTRADAR-TIMELINE-QUALITY-AUDIT-CAPTURE-001"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_LANGUAGE = "en"
_ALLOWED_ACCESS = frozenset({"trial", "production"})
_TRIAL_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_MAX_HTTP_429_RETRIES = 4
_MAX_RETRY_DELAY_SECONDS = 16.0

ProviderGet = Callable[[str, dict[str, str]], ProviderHttpResponse]
Sleeper = Callable[[float], None]


class TimelineSampleSeasonResult(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    competition_id: str
    season_id: str
    requested_timeline_count: int
    captured_timeline_count: int
    history_not_available_count: int
    audit_file_sha256: str
    audit_semantic_sha256: str
    admission_status: Literal["ADMITTED", "REJECTED"]
    admission_failure_reasons: tuple[str, ...]
    admission_receipt_semantic_sha256: str | None


class TimelineSampleCapture(WorkbenchRecord):
    capture_id: Literal["SPORTRADAR-TIMELINE-QUALITY-AUDIT-CAPTURE-001"] = CAPTURE_ID
    sample_plan_semantic_sha256: str
    census_semantic_sha256: str
    access_level: str
    provider_request_count: int
    selected_timeline_count: int
    captured_timeline_count: int
    history_not_available_count: int
    admitted_season_count: int
    rejected_season_count: int
    rows: tuple[TimelineSampleSeasonResult, ...]

    @model_validator(mode="after")
    def _reproduce_counts(self) -> TimelineSampleCapture:
        if self.provider_request_count != self.selected_timeline_count:
            raise ValueError("provider request count must equal the frozen selected timeline count")
        if self.selected_timeline_count != sum(
            row.requested_timeline_count for row in self.rows
        ):
            raise ValueError("selected timeline count does not reproduce from rows")
        if self.captured_timeline_count != sum(
            row.captured_timeline_count for row in self.rows
        ):
            raise ValueError("captured timeline count does not reproduce from rows")
        if self.history_not_available_count != sum(
            row.history_not_available_count for row in self.rows
        ):
            raise ValueError("unavailable timeline count does not reproduce from rows")
        if (
            self.captured_timeline_count + self.history_not_available_count
            != self.selected_timeline_count
        ):
            raise ValueError("timeline dispositions do not cover the frozen selected denominator")
        if self.admitted_season_count != sum(
            row.admission_status == "ADMITTED" for row in self.rows
        ):
            raise ValueError("admitted season count does not reproduce")
        if self.rejected_season_count != sum(
            row.admission_status == "REJECTED" for row in self.rows
        ):
            raise ValueError("rejected season count does not reproduce")
        return self


@dataclass(frozen=True)
class _RetainedTimeline:
    event_id: str
    path: Path | None
    status: int


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


def _header_bytes(response: ProviderHttpResponse) -> bytes:
    lines = [f"{response.http_version} {response.status}"]
    lines.extend(f"{name}: {value}" for name, value in response.headers)
    return ("\n".join(lines) + "\n").encode("iso-8859-1")


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
                    (str(key), str(value)) for key, value in response.headers.raw_items()
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
            raw_headers = (
                tuple((str(key), str(value)) for key, value in exc.headers.raw_items())
                if exc.headers is not None
                else ()
            )
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


def _timeline_url(*, access_level: str, event_id: str) -> str:
    encoded = quote(event_id, safe="")
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/{_LANGUAGE}/"
        f"sport_events/{encoded}/timeline.json"
    )


def _safe_id(value: str) -> str:
    return value.replace(":", "_").replace("/", "_")


def _retain_timeline_response(
    *,
    season_dir: Path,
    event_id: str,
    response: ProviderHttpResponse,
) -> _RetainedTimeline:
    event_name = _safe_id(event_id)
    if response.status == 200:
        target_dir = season_dir / "timelines"
        suffix = ".json"
    else:
        target_dir = season_dir / "timeline-failures"
        suffix = ".body"
    target_dir.mkdir(parents=True, exist_ok=True)
    body_path = target_dir / f"{event_name}{suffix}"
    headers_path = target_dir / f"{event_name}.headers"
    if body_path.exists() or headers_path.exists():
        raise ValueError(f"timeline evidence would overwrite retained bytes for {event_id}")
    body_path.write_bytes(response.body)
    headers_path.write_bytes(_header_bytes(response))

    if response.status in {401, 403}:
        raise RuntimeError(
            f"Sport Event Timeline authentication/authorization failed with HTTP {response.status}"
        )
    if response.status in {404, 410}:
        return _RetainedTimeline(event_id=event_id, path=None, status=response.status)
    if response.status != 200:
        raise RuntimeError(
            f"Sport Event Timeline returned non-admissible transient HTTP {response.status}"
        )

    payload = _json_object(response.body, label="Sportradar Sport Event Timeline response")
    _aware_time(payload.get("generated_at"), field="Sport Event Timeline generated_at")
    event = payload.get("sport_event")
    if not isinstance(event, dict):
        raise ValueError("Sport Event Timeline sport_event must be an object")
    observed_event_id = str(event.get("id", "")).strip()
    if observed_event_id != event_id:
        raise ValueError("Sport Event Timeline event identity differs from requested event")
    timeline = payload.get("timeline")
    if timeline is not None and not isinstance(timeline, list):
        raise ValueError("Sport Event Timeline timeline must be an array when present")
    return _RetainedTimeline(event_id=event_id, path=body_path, status=response.status)


def _season_page_pairs(census_root: Path, season_id: str) -> tuple[tuple[Path, Path], ...]:
    season_dir = census_root / "seasons" / _safe_id(season_id)
    raw_paths = tuple(sorted(season_dir.glob("page-*.json")))
    if not raw_paths:
        raise ValueError(f"retained Season Summaries pages missing for {season_id}")
    pairs: list[tuple[Path, Path]] = []
    for raw in raw_paths:
        headers = raw.with_suffix(".headers")
        if not headers.is_file():
            raise ValueError(f"retained Season Summaries headers missing for {raw.name}")
        pairs.append((raw, headers))
    return tuple(pairs)


def capture_timeline_audit_sample(
    *,
    sample_plan_path: Path,
    census_path: Path,
    census_root: Path,
    output_dir: Path,
    repo_root: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
    sleeper: Sleeper = time.sleep,
) -> TimelineSampleCapture:
    """Capture only the preregistered whole-season Timeline sample and apply Audit 002."""

    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("timeline sample output directory must begin empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    plan = TimelineAuditSamplePlan.model_validate_json(
        sample_plan_path.read_text(encoding="utf-8")
    )
    census = SeasonSummariesCensus.model_validate_json(
        census_path.read_text(encoding="utf-8")
    )
    if plan.census_semantic_sha256 != census.semantic_sha256:
        raise ValueError("sample plan is detached from the supplied census")
    if census.access_level != access_level:
        raise ValueError("timeline capture access level differs from frozen census")
    if plan.selected_timeline_count > plan.request_budget_cap:
        raise ValueError("sample plan exceeds its frozen request budget")

    census_by_season = {row.season_id: row for row in census.rows}
    request_count = 0
    results: list[TimelineSampleSeasonResult] = []

    for selected in plan.selected_rows:
        census_row = census_by_season.get(selected.season_id)
        if census_row is None:
            raise ValueError("sampled season is absent from the census")
        if census_row.disposition != "SUMMARIES_CAPTURED":
            raise ValueError("sampled season lacks retained Season Summaries evidence")
        if census_row.competition_id != selected.competition_id:
            raise ValueError("sample/census competition identity mismatch")
        if census_row.required_timeline_count != selected.required_timeline_count:
            raise ValueError("sample/census timeline denominator mismatch")
        if census_row.season_summaries_sha256 != selected.season_summaries_sha256:
            raise ValueError("sample/census Season Summaries hash mismatch")

        page_pairs = _season_page_pairs(census_root, selected.season_id)
        aggregate = build_complete_season_summaries(page_pairs)
        aggregate_sha = _sha256_bytes(_canonical_json(aggregate))
        if aggregate_sha != selected.season_summaries_sha256:
            raise ValueError("retained Season Summaries bytes differ from frozen sample plan")

        season_dir = output_dir / "seasons" / _safe_id(selected.season_id)
        successful_paths: list[Path] = []
        unavailable = 0
        for event_id in census_row.required_timeline_event_ids:
            if request_count and access_level == "trial":
                sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
            response = provider_get(
                _timeline_url(access_level=access_level, event_id=event_id),
                {"x-api-key": api_key, "Accept": "application/json"},
            )
            request_count += 1
            retained = _retain_timeline_response(
                season_dir=season_dir,
                event_id=event_id,
                response=response,
            )
            if retained.path is None:
                unavailable += 1
            else:
                successful_paths.append(retained.path)

        audit = audit_sportradar_start_time_coverage_v2(
            page_pairs=page_pairs,
            timeline_paths=tuple(successful_paths),
        )
        verify_exact_time_audit_integrity(audit)
        audit_bytes = (
            json.dumps(audit.canonical_payload(), indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        season_dir.mkdir(parents=True, exist_ok=True)
        audit_path = season_dir / "start-time-audit-v2.json"
        audit_path.write_bytes(audit_bytes)
        failures = chronology_admission_failure_reasons(audit)
        receipt_sha: str | None = None
        if failures:
            status: Literal["ADMITTED", "REJECTED"] = "REJECTED"
            (season_dir / "admission-failure-reasons.json").write_text(
                json.dumps({"failure_reasons": list(failures)}, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        else:
            status = "ADMITTED"
            receipt = admit_exact_time_audit_bytes(audit_bytes, repo_root=repo_root)
            receipt_sha = receipt.semantic_sha256
            (season_dir / "admission-receipt.json").write_text(
                json.dumps(receipt.canonical_payload(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        results.append(
            TimelineSampleSeasonResult(
                tour=selected.tour,
                competition_id=selected.competition_id,
                season_id=selected.season_id,
                requested_timeline_count=selected.required_timeline_count,
                captured_timeline_count=len(successful_paths),
                history_not_available_count=unavailable,
                audit_file_sha256=_sha256_bytes(audit_bytes),
                audit_semantic_sha256=audit.semantic_sha256,
                admission_status=status,
                admission_failure_reasons=failures,
                admission_receipt_semantic_sha256=receipt_sha,
            )
        )

    if request_count != plan.selected_timeline_count:
        raise AssertionError("provider calls differ from frozen selected timeline denominator")

    capture = TimelineSampleCapture(
        sample_plan_semantic_sha256=plan.semantic_sha256,
        census_semantic_sha256=census.semantic_sha256,
        access_level=access_level,
        provider_request_count=request_count,
        selected_timeline_count=plan.selected_timeline_count,
        captured_timeline_count=sum(row.captured_timeline_count for row in results),
        history_not_available_count=sum(row.history_not_available_count for row in results),
        admitted_season_count=sum(row.admission_status == "ADMITTED" for row in results),
        rejected_season_count=sum(row.admission_status == "REJECTED" for row in results),
        rows=tuple(results),
    )
    (output_dir / "capture.json").write_text(
        json.dumps(capture.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_bytes(
        _canonical_json(
            {
                "capture_semantic_sha256": capture.semantic_sha256,
                "sample_plan_semantic_sha256": capture.sample_plan_semantic_sha256,
                "provider_request_count": capture.provider_request_count,
                "selected_timeline_count": capture.selected_timeline_count,
                "captured_timeline_count": capture.captured_timeline_count,
                "history_not_available_count": capture.history_not_available_count,
                "admitted_season_count": capture.admitted_season_count,
                "rejected_season_count": capture.rejected_season_count,
            }
        )
        + b"\n"
    )
    return capture