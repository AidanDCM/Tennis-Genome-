from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .contracts import WorkbenchRecord
from .sportradar_season_summaries_census import (
    ProviderHttpResponse,
    SeasonSummariesCensus,
)
from .sportradar_start_time_audit import build_complete_season_summaries
from .sportradar_start_time_audit_v2 import (
    StartTimeCoverageAuditV2,
    audit_sportradar_start_time_coverage_v2,
)
from .sportradar_timeline_audit_sample import (
    TimelineAuditSamplePlan,
    classify_timeline_quality_pilot,
)

REPORT_ID = "SPORTRADAR-TIMELINE-QUALITY-PILOT-001"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_TRIAL_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_ALLOWED_ACCESS = frozenset({"trial", "production"})

ProviderGet = Callable[[str, dict[str, str]], ProviderHttpResponse]
Sleeper = Callable[[float], None]
PilotDisposition = Literal["PILOT_PROMISING", "PILOT_MIXED", "PILOT_POOR"]


class TimelineQualityStratum(WorkbenchRecord):
    stratum: str
    selected_season_count: int
    played_terminal_count: int
    exact_match_started_count: int
    missing_timeline_count: int
    missing_match_started_count: int
    conflicting_match_started_count: int
    invalid_match_started_time_count: int
    updated_match_started_count: int
    exact_coverage_rate: float


class TimelineQualityPilotReport(WorkbenchRecord):
    report_id: Literal["SPORTRADAR-TIMELINE-QUALITY-PILOT-001"] = REPORT_ID
    evidence_role: Literal["DESCRIPTIVE_ONLY_SOURCE_VALIDATION"] = (
        "DESCRIPTIVE_ONLY_SOURCE_VALIDATION"
    )
    sample_plan_semantic_sha256: str
    census_semantic_sha256: str
    access_level: str
    provider_request_count: int
    selected_timeline_count: int
    selected_season_count: int
    played_terminal_count: int
    exact_match_started_count: int
    missing_timeline_count: int
    missing_match_started_count: int
    conflicting_match_started_count: int
    invalid_match_started_time_count: int
    updated_match_started_count: int
    exact_coverage_rate: float
    schedule_drift_pair_count: int
    median_signed_schedule_drift_minutes: float | None
    median_absolute_schedule_drift_minutes: float | None
    p90_absolute_schedule_drift_minutes: float | None
    pilot_disposition: PilotDisposition
    strata: tuple[TimelineQualityStratum, ...]
    season_audit_sha256s: tuple[str, ...]


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


def _json_object(content: bytes, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


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


def _event_filename(event_id: str) -> str:
    safe = event_id.replace(":", "_").replace("/", "_")
    if not safe or safe in {".", ".."}:
        raise ValueError("provider event ID cannot be converted to a safe filename")
    return safe


def _timeline_url(*, access_level: str, event_id: str) -> str:
    encoded = quote(event_id, safe=":")
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/en/"
        f"sport_events/{encoded}/timeline.json"
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
        raise RuntimeError("Sportradar timeline HTTPS transport failed") from exc


def _validate_timeline_payload(content: bytes, *, expected_event_id: str) -> None:
    payload = _json_object(content, label="Sportradar timeline response")
    if payload.get("generated_at") is not None:
        _aware_time(payload.get("generated_at"), field="timeline.generated_at")
    event = payload.get("sport_event")
    if not isinstance(event, dict):
        raise ValueError("timeline response lacks sport_event object")
    observed = str(event.get("id", "")).strip()
    if observed != expected_event_id:
        raise ValueError("timeline sport_event.id differs from requested event")
    timeline = payload.get("timeline")
    if timeline is not None and not isinstance(timeline, list):
        raise ValueError("timeline field must be an array when present")


def _page_pairs(season_dir: Path) -> tuple[tuple[Path, Path], ...]:
    raws = sorted(season_dir.glob("page-*.json"))
    if not raws:
        raise ValueError(f"census season directory contains no retained pages: {season_dir}")
    pairs: list[tuple[Path, Path]] = []
    for raw in raws:
        headers = raw.with_suffix(".headers")
        if not headers.is_file():
            raise ValueError(f"census page lacks retained headers: {raw.name}")
        pairs.append((raw, headers))
    return tuple(pairs)


def _nearest_rank_p90(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(0.90 * len(ordered)) - 1)
    return ordered[index]


def _drift_values(audits: tuple[StartTimeCoverageAuditV2, ...]) -> tuple[list[float], list[float]]:
    signed: list[float] = []
    absolute: list[float] = []
    for audit in audits:
        for event in audit.base_audit.events:
            if event.disposition != "EXACT_MATCH_STARTED":
                continue
            if event.scheduled_start is None or event.match_started_time is None:
                continue
            scheduled = _aware_time(event.scheduled_start, field="scheduled_start")
            actual = _aware_time(event.match_started_time, field="match_started_time")
            delta_minutes = (actual - scheduled).total_seconds() / 60.0
            signed.append(delta_minutes)
            absolute.append(abs(delta_minutes))
    return signed, absolute


def _strata(
    *,
    plan: TimelineAuditSamplePlan,
    audits_by_season: dict[str, StartTimeCoverageAuditV2],
) -> tuple[TimelineQualityStratum, ...]:
    grouped: dict[str, list[StartTimeCoverageAuditV2]] = defaultdict(list)
    for row in plan.selected_rows:
        grouped[f"{row.tour}:{row.era}"].append(audits_by_season[row.season_id])
    results: list[TimelineQualityStratum] = []
    for key in sorted(grouped):
        audits = grouped[key]
        played = sum(item.base_audit.played_terminal_count for item in audits)
        exact = sum(item.base_audit.exact_match_started_count for item in audits)
        results.append(
            TimelineQualityStratum(
                stratum=key,
                selected_season_count=len(audits),
                played_terminal_count=played,
                exact_match_started_count=exact,
                missing_timeline_count=sum(
                    item.base_audit.missing_timeline_count for item in audits
                ),
                missing_match_started_count=sum(
                    item.base_audit.missing_match_started_count for item in audits
                ),
                conflicting_match_started_count=sum(
                    item.base_audit.conflicting_match_started_count for item in audits
                ),
                invalid_match_started_time_count=sum(
                    item.base_audit.invalid_match_started_time_count for item in audits
                ),
                updated_match_started_count=sum(
                    item.base_audit.updated_match_started_count for item in audits
                ),
                exact_coverage_rate=0.0 if played == 0 else exact / played,
            )
        )
    return tuple(results)


def capture_timeline_quality_pilot(
    *,
    sample_plan_path: Path,
    census_path: Path,
    census_root: Path,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
    sleeper: Sleeper = time.sleep,
) -> TimelineQualityPilotReport:
    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("timeline audit output directory must begin empty")

    plan = TimelineAuditSamplePlan.model_validate_json(
        sample_plan_path.read_text(encoding="utf-8")
    )
    census = SeasonSummariesCensus.model_validate_json(
        census_path.read_text(encoding="utf-8")
    )
    if plan.census_semantic_sha256 != census.semantic_sha256:
        raise ValueError("timeline sample plan is detached from supplied census")

    census_by_season = {row.season_id: row for row in census.rows}
    if len(census_by_season) != len(census.rows):
        raise ValueError("census contains duplicate season IDs")

    request_count = 0
    audits: list[StartTimeCoverageAuditV2] = []
    audits_by_season: dict[str, StartTimeCoverageAuditV2] = {}
    for plan_row in plan.selected_rows:
        census_row = census_by_season.get(plan_row.season_id)
        if census_row is None:
            raise ValueError("sampled season is missing from census")
        if census_row.disposition != "SUMMARIES_CAPTURED":
            raise ValueError("sampled season was not successfully captured in census")
        if census_row.required_timeline_count != plan_row.required_timeline_count:
            raise ValueError("sample plan timeline cost differs from census")
        if census_row.season_summaries_sha256 != plan_row.season_summaries_sha256:
            raise ValueError("sample plan summaries hash differs from census")
        if len(census_row.required_timeline_event_ids) != plan_row.required_timeline_count:
            raise ValueError("census timeline event list does not reproduce required count")

        source_season_dir = census_root / "seasons" / plan_row.season_id.replace(":", "_")
        page_pairs = _page_pairs(source_season_dir)
        aggregate = build_complete_season_summaries(page_pairs)
        aggregate_sha = _sha256_bytes(_canonical_json(aggregate))
        if aggregate_sha != plan_row.season_summaries_sha256:
            raise ValueError("retained census pages do not reproduce sampled summaries hash")

        season_out = output_dir / "seasons" / plan_row.season_id.replace(":", "_")
        timeline_dir = season_out / "timelines"
        failure_dir = season_out / "timeline-failures"
        timeline_dir.mkdir(parents=True, exist_ok=True)
        failure_dir.mkdir(parents=True, exist_ok=True)
        valid_timeline_paths: list[Path] = []

        for event_id in census_row.required_timeline_event_ids:
            if request_count and access_level == "trial":
                sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
            response = provider_get(
                _timeline_url(access_level=access_level, event_id=event_id),
                {"x-api-key": api_key, "Accept": "application/json"},
            )
            request_count += 1
            stem = _event_filename(event_id)
            if response.status == 200:
                _validate_timeline_payload(response.body, expected_event_id=event_id)
                raw_path = timeline_dir / f"{stem}.json"
                headers_path = timeline_dir / f"{stem}.headers"
                raw_path.write_bytes(response.body)
                headers_path.write_bytes(response.headers_bytes())
                valid_timeline_paths.append(raw_path)
                continue

            body_path = failure_dir / f"{stem}.body"
            headers_path = failure_dir / f"{stem}.headers"
            body_path.write_bytes(response.body)
            headers_path.write_bytes(response.headers_bytes())
            failure_record = {
                "provider_event_id": event_id,
                "http_status": response.status,
                "response_body_sha256": _sha256_bytes(response.body),
                "response_headers_sha256": _sha256_bytes(response.headers_bytes()),
            }
            (failure_dir / f"{stem}.json").write_text(
                json.dumps(failure_record, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if response.status in {404, 410}:
                continue
            if response.status in {401, 403}:
                raise RuntimeError(
                    f"timeline authentication/authorization failed with HTTP {response.status}"
                )
            if response.status == 429:
                raise RuntimeError("timeline provider returned HTTP 429; audit stopped without retry")
            raise RuntimeError(f"timeline provider returned unexpected HTTP {response.status}")

        audit = audit_sportradar_start_time_coverage_v2(
            page_pairs=page_pairs,
            timeline_paths=tuple(valid_timeline_paths),
        )
        if audit.season.season_id != plan_row.season_id:
            raise ValueError("timeline audit season differs from frozen sample plan")
        audit_path = season_out / "start-time-audit.json"
        audit_path.write_text(
            json.dumps(audit.canonical_payload(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        audits.append(audit)
        audits_by_season[plan_row.season_id] = audit

    if request_count != plan.selected_timeline_count:
        raise ValueError("actual timeline request count differs from frozen sample plan")

    audits_tuple = tuple(audits)
    played = sum(item.base_audit.played_terminal_count for item in audits_tuple)
    exact = sum(item.base_audit.exact_match_started_count for item in audits_tuple)
    missing_timeline = sum(item.base_audit.missing_timeline_count for item in audits_tuple)
    missing_started = sum(
        item.base_audit.missing_match_started_count for item in audits_tuple
    )
    conflicting = sum(
        item.base_audit.conflicting_match_started_count for item in audits_tuple
    )
    invalid = sum(
        item.base_audit.invalid_match_started_time_count for item in audits_tuple
    )
    updated = sum(item.base_audit.updated_match_started_count for item in audits_tuple)
    signed_drift, absolute_drift = _drift_values(audits_tuple)
    report = TimelineQualityPilotReport(
        sample_plan_semantic_sha256=plan.semantic_sha256,
        census_semantic_sha256=census.semantic_sha256,
        access_level=access_level,
        provider_request_count=request_count,
        selected_timeline_count=plan.selected_timeline_count,
        selected_season_count=plan.selected_season_count,
        played_terminal_count=played,
        exact_match_started_count=exact,
        missing_timeline_count=missing_timeline,
        missing_match_started_count=missing_started,
        conflicting_match_started_count=conflicting,
        invalid_match_started_time_count=invalid,
        updated_match_started_count=updated,
        exact_coverage_rate=0.0 if played == 0 else exact / played,
        schedule_drift_pair_count=len(signed_drift),
        median_signed_schedule_drift_minutes=(
            None if not signed_drift else float(median(signed_drift))
        ),
        median_absolute_schedule_drift_minutes=(
            None if not absolute_drift else float(median(absolute_drift))
        ),
        p90_absolute_schedule_drift_minutes=_nearest_rank_p90(absolute_drift),
        pilot_disposition=classify_timeline_quality_pilot(
            exact_match_started_count=exact,
            played_terminal_count=played,
            conflicting_match_started_count=conflicting,
            invalid_match_started_time_count=invalid,
        ),
        strata=_strata(plan=plan, audits_by_season=audits_by_season),
        season_audit_sha256s=tuple(sorted(item.semantic_sha256 for item in audits_tuple)),
    )
    (output_dir / "timeline-quality-pilot-report.json").write_text(
        json.dumps(report.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "report_semantic_sha256": report.semantic_sha256,
                "provider_request_count": report.provider_request_count,
                "played_terminal_count": report.played_terminal_count,
                "exact_match_started_count": report.exact_match_started_count,
                "exact_coverage_rate": report.exact_coverage_rate,
                "pilot_disposition": report.pilot_disposition,
                "season_audit_sha256s": list(report.season_audit_sha256s),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return report
