from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord

AUDIT_ID = "SPORTRADAR-HISTORICAL-START-TIME-AUDIT-001"
EVIDENCE_ROLE = "DESCRIPTIVE_ONLY_SOURCE_VALIDATION"
_REQUIRED_HEADERS = ("x-max-results", "x-offset", "x-result")
_IN_SCOPE_CATEGORIES = {
    "sr:category:3": "ATP",
    "sr:category:6": "WTA",
}
_TERMINAL_STATUSES = {"closed", "ended"}

Disposition = Literal[
    "EXACT_MATCH_STARTED",
    "MISSING_TIMELINE",
    "MISSING_MATCH_STARTED",
    "CONFLICTING_MATCH_STARTED",
    "INVALID_MATCH_STARTED_TIME",
    "WALKOVER",
    "NOT_TERMINAL",
]


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


def _json_object_bytes(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _required_text(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        raise ValueError(f"{field} must be non-empty")
    return text


def _parse_time(value: object, *, field: str) -> datetime:
    text = _required_text(value, field=field)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _parse_headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("iso-8859-1")
    headers: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        name, value = raw_line.split(":", 1)
        headers[name.strip().lower()] = value.strip()
    missing = [name for name in _REQUIRED_HEADERS if not headers.get(name)]
    if missing:
        raise ValueError(f"response headers missing required pagination fields: {missing}")
    return headers


def _nonnegative_int(headers: dict[str, str], field: str) -> int:
    try:
        value = int(headers[field])
    except ValueError as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _event_id(summary: object) -> str:
    root = _as_dict(summary, field="summary")
    event = _as_dict(root.get("sport_event"), field="summary.sport_event")
    return _required_text(event.get("id"), field="summary.sport_event.id")


@dataclass(frozen=True)
class SeasonPageEvidence:
    offset: int
    result_count: int
    max_results: int
    raw_payload_sha256: str
    response_headers_sha256: str
    summaries: tuple[object, ...]

    def metadata(self) -> dict[str, object]:
        return {
            "offset": self.offset,
            "result_count": self.result_count,
            "max_results": self.max_results,
            "raw_payload_sha256": self.raw_payload_sha256,
            "response_headers_sha256": self.response_headers_sha256,
        }


def _load_season_page(raw_path: Path, headers_path: Path) -> SeasonPageEvidence:
    raw_bytes = raw_path.read_bytes()
    header_bytes = headers_path.read_bytes()
    payload = _json_object_bytes(raw_bytes, label="Sportradar Season Summaries page")
    summaries = _as_list(payload.get("summaries"), field="summaries")
    headers = _parse_headers(header_bytes)
    max_results = _nonnegative_int(headers, "x-max-results")
    offset = _nonnegative_int(headers, "x-offset")
    result_count = _nonnegative_int(headers, "x-result")
    if len(summaries) != result_count:
        raise ValueError("Sportradar Season Summaries count differs from X-Result")
    if result_count > 200:
        raise ValueError("Sportradar page X-Result exceeds documented 200-row maximum")
    return SeasonPageEvidence(
        offset=offset,
        result_count=result_count,
        max_results=max_results,
        raw_payload_sha256=_sha256_bytes(raw_bytes),
        response_headers_sha256=_sha256_bytes(header_bytes),
        summaries=tuple(summaries),
    )


def build_complete_season_summaries(
    page_pairs: Sequence[tuple[Path, Path]],
) -> dict[str, object]:
    """Rebuild a complete Season Summaries response from retained page evidence."""

    if not page_pairs:
        raise ValueError("at least one Season Summaries page/header pair is required")
    pages = [_load_season_page(raw, headers) for raw, headers in page_pairs]
    pages.sort(key=lambda page: page.offset)
    totals = {page.max_results for page in pages}
    if len(totals) != 1:
        raise ValueError("Season Summaries pages disagree on X-Max-Results")
    expected_total = totals.pop()
    if pages[0].offset != 0:
        raise ValueError("Season Summaries pagination must begin at X-Offset 0")

    expected_offset = 0
    summaries: list[object] = []
    ids: set[str] = set()
    for page in pages:
        if page.offset != expected_offset:
            raise ValueError("Season Summaries pagination has a gap or overlap")
        if expected_total > 0 and page.result_count == 0:
            raise ValueError("non-empty Season Summaries pagination contains an empty page")
        for summary in page.summaries:
            event_id = _event_id(summary)
            if event_id in ids:
                raise ValueError("Season Summaries contains duplicate sport-event IDs")
            ids.add(event_id)
            summaries.append(summary)
        expected_offset += page.result_count

    if expected_offset != expected_total:
        raise ValueError("retained Season Summaries pages do not cover X-Max-Results exactly")
    if expected_total == 0 and len(pages) != 1:
        raise ValueError("zero-result Season Summaries capture must contain exactly one page")

    return {
        "schema": "sportradar-historical-season-summaries-evidence-v1",
        "x_max_results": expected_total,
        "page_count": len(pages),
        "pages": [page.metadata() for page in pages],
        "summaries": summaries,
    }


class StartTimeEventAudit(WorkbenchRecord):
    provider_event_id: str
    tour: Literal["ATP", "WTA"]
    provider_status: str
    winning_reason: str | None
    scheduled_start: str | None
    start_time_confirmed: bool | None
    estimated: bool | None
    timeline_sha256: str | None
    match_started_time: str | None
    match_started_updated: bool
    match_started_updated_time: str | None
    disposition: Disposition


class StartTimeCoverageAudit(WorkbenchRecord):
    audit_id: Literal["SPORTRADAR-HISTORICAL-START-TIME-AUDIT-001"] = AUDIT_ID
    evidence_role: Literal["DESCRIPTIVE_ONLY_SOURCE_VALIDATION"] = EVIDENCE_ROLE
    season_summaries_sha256: str
    timeline_bundle_sha256: str
    raw_summary_count: int
    in_scope_count: int
    atp_count: int
    wta_count: int
    played_terminal_count: int
    exact_match_started_count: int
    walkover_count: int
    nonterminal_count: int
    missing_timeline_count: int
    missing_match_started_count: int
    conflicting_match_started_count: int
    invalid_match_started_time_count: int
    updated_match_started_count: int
    exact_coverage_rate: float
    events: tuple[StartTimeEventAudit, ...]


def _summary_scope(summary: object) -> tuple[str, Literal["ATP", "WTA"]] | None:
    root = _as_dict(summary, field="summary")
    event = _as_dict(root.get("sport_event"), field="summary.sport_event")
    event_id = _required_text(event.get("id"), field="summary.sport_event.id")
    context = _as_dict(event.get("sport_event_context"), field="sport_event_context")
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    competition = _as_dict(context.get("competition"), field="sport_event_context.competition")
    category_id = _required_text(category.get("id"), field="category.id")
    tour = _IN_SCOPE_CATEGORIES.get(category_id)
    if tour is None:
        return None
    expected_name = tour
    actual_name = _required_text(category.get("name"), field="category.name").upper()
    if actual_name != expected_name:
        raise ValueError(f"Sportradar category semantic drift for {category_id}: {actual_name!r}")
    competition_type = _required_text(competition.get("type"), field="competition.type").lower()
    if competition_type != "singles":
        return None
    return event_id, tour


def _timeline_index(timeline_paths: Sequence[Path]) -> dict[str, tuple[dict[str, object], str]]:
    index: dict[str, tuple[dict[str, object], str]] = {}
    for path in sorted(timeline_paths, key=lambda item: str(item)):
        raw = path.read_bytes()
        payload = _json_object_bytes(raw, label=f"timeline {path}")
        event = _as_dict(payload.get("sport_event"), field="timeline.sport_event")
        event_id = _required_text(event.get("id"), field="timeline.sport_event.id")
        if event_id in index:
            raise ValueError(f"duplicate retained timeline for {event_id}")
        index[event_id] = (payload, _sha256_bytes(raw))
    return index


def _timeline_bundle_sha256(index: dict[str, tuple[dict[str, object], str]]) -> str:
    identities = [
        {"provider_event_id": event_id, "timeline_sha256": index[event_id][1]}
        for event_id in sorted(index)
    ]
    return _sha256_bytes(_canonical_json(identities))


def _optional_schedule_time(event: dict[str, object]) -> str | None:
    raw = event.get("start_time")
    if raw is None or not str(raw).strip():
        return None
    try:
        return _parse_time(raw, field="sport_event.start_time").isoformat()
    except ValueError:
        return None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _match_started(
    payload: dict[str, object],
) -> tuple[Disposition, str | None, bool, str | None]:
    timeline = _as_list(payload.get("timeline", []), field="timeline")
    starts: list[dict[str, object]] = []
    for raw_event in timeline:
        event = _as_dict(raw_event, field="timeline event")
        if str(event.get("type", "")).strip().lower() == "match_started":
            starts.append(event)
    if not starts:
        return "MISSING_MATCH_STARTED", None, False, None
    if len(starts) != 1:
        return "CONFLICTING_MATCH_STARTED", None, False, None

    event = starts[0]
    try:
        started = _parse_time(event.get("time"), field="match_started.time")
    except ValueError:
        return "INVALID_MATCH_STARTED_TIME", None, False, None

    updated = event.get("updated") is True
    updated_time: str | None = None
    if event.get("updated_time") is not None:
        try:
            updated_time = _parse_time(
                event.get("updated_time"), field="match_started.updated_time"
            ).isoformat()
        except ValueError:
            return "INVALID_MATCH_STARTED_TIME", None, updated, None
    return "EXACT_MATCH_STARTED", started.isoformat(), updated, updated_time


def _audit_event(
    summary: object,
    *,
    tour: Literal["ATP", "WTA"],
    timelines: dict[str, tuple[dict[str, object], str]],
) -> StartTimeEventAudit:
    root = _as_dict(summary, field="summary")
    event = _as_dict(root.get("sport_event"), field="summary.sport_event")
    event_id = _required_text(event.get("id"), field="summary.sport_event.id")
    status = _as_dict(root.get("sport_event_status", {}), field="sport_event_status")
    provider_status = str(status.get("status", "")).strip().lower()
    winning_reason_raw = str(status.get("winning_reason", "")).strip().lower()
    winning_reason = winning_reason_raw or None
    scheduled_start = _optional_schedule_time(event)
    confirmed = _optional_bool(event.get("start_time_confirmed"))
    estimated = _optional_bool(event.get("estimated"))

    if provider_status not in _TERMINAL_STATUSES:
        return StartTimeEventAudit(
            provider_event_id=event_id,
            tour=tour,
            provider_status=provider_status,
            winning_reason=winning_reason,
            scheduled_start=scheduled_start,
            start_time_confirmed=confirmed,
            estimated=estimated,
            timeline_sha256=None,
            match_started_time=None,
            match_started_updated=False,
            match_started_updated_time=None,
            disposition="NOT_TERMINAL",
        )
    if winning_reason == "walkover":
        timeline = timelines.get(event_id)
        return StartTimeEventAudit(
            provider_event_id=event_id,
            tour=tour,
            provider_status=provider_status,
            winning_reason=winning_reason,
            scheduled_start=scheduled_start,
            start_time_confirmed=confirmed,
            estimated=estimated,
            timeline_sha256=None if timeline is None else timeline[1],
            match_started_time=None,
            match_started_updated=False,
            match_started_updated_time=None,
            disposition="WALKOVER",
        )

    retained = timelines.get(event_id)
    if retained is None:
        return StartTimeEventAudit(
            provider_event_id=event_id,
            tour=tour,
            provider_status=provider_status,
            winning_reason=winning_reason,
            scheduled_start=scheduled_start,
            start_time_confirmed=confirmed,
            estimated=estimated,
            timeline_sha256=None,
            match_started_time=None,
            match_started_updated=False,
            match_started_updated_time=None,
            disposition="MISSING_TIMELINE",
        )

    payload, timeline_sha256 = retained
    timeline_event = _as_dict(payload.get("sport_event"), field="timeline.sport_event")
    timeline_id = _required_text(timeline_event.get("id"), field="timeline.sport_event.id")
    if timeline_id != event_id:
        raise ValueError(f"timeline sport-event ID mismatch for {event_id}")
    disposition, started, updated, updated_time = _match_started(payload)
    return StartTimeEventAudit(
        provider_event_id=event_id,
        tour=tour,
        provider_status=provider_status,
        winning_reason=winning_reason,
        scheduled_start=scheduled_start,
        start_time_confirmed=confirmed,
        estimated=estimated,
        timeline_sha256=timeline_sha256,
        match_started_time=started,
        match_started_updated=updated,
        match_started_updated_time=updated_time,
        disposition=disposition,
    )


def audit_sportradar_start_time_coverage(
    *,
    page_pairs: Sequence[tuple[Path, Path]],
    timeline_paths: Sequence[Path],
) -> StartTimeCoverageAudit:
    aggregate = build_complete_season_summaries(page_pairs)
    timelines = _timeline_index(timeline_paths)
    summaries = _as_list(aggregate["summaries"], field="summaries")

    events: list[StartTimeEventAudit] = []
    for summary in summaries:
        scoped = _summary_scope(summary)
        if scoped is None:
            continue
        _, tour = scoped
        events.append(_audit_event(summary, tour=tour, timelines=timelines))
    events.sort(key=lambda item: item.provider_event_id)

    played = [
        event
        for event in events
        if event.provider_status in _TERMINAL_STATUSES and event.disposition != "WALKOVER"
    ]
    exact = sum(event.disposition == "EXACT_MATCH_STARTED" for event in played)
    denominator = len(played)
    return StartTimeCoverageAudit(
        season_summaries_sha256=_sha256_bytes(_canonical_json(aggregate)),
        timeline_bundle_sha256=_timeline_bundle_sha256(timelines),
        raw_summary_count=len(summaries),
        in_scope_count=len(events),
        atp_count=sum(event.tour == "ATP" for event in events),
        wta_count=sum(event.tour == "WTA" for event in events),
        played_terminal_count=denominator,
        exact_match_started_count=exact,
        walkover_count=sum(event.disposition == "WALKOVER" for event in events),
        nonterminal_count=sum(event.disposition == "NOT_TERMINAL" for event in events),
        missing_timeline_count=sum(event.disposition == "MISSING_TIMELINE" for event in events),
        missing_match_started_count=sum(
            event.disposition == "MISSING_MATCH_STARTED" for event in events
        ),
        conflicting_match_started_count=sum(
            event.disposition == "CONFLICTING_MATCH_STARTED" for event in events
        ),
        invalid_match_started_time_count=sum(
            event.disposition == "INVALID_MATCH_STARTED_TIME" for event in events
        ),
        updated_match_started_count=sum(event.match_started_updated for event in events),
        exact_coverage_rate=0.0 if denominator == 0 else exact / denominator,
        events=tuple(events),
    )


def _parse_page_pair(value: str) -> tuple[Path, Path]:
    parts = value.split("::", 1)
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise argparse.ArgumentTypeError("--page must be RAW_PATH::HEADERS_PATH")
    return Path(parts[0]), Path(parts[1])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit retained Sportradar timelines for exact match-start coverage"
    )
    parser.add_argument("--page", action="append", required=True, type=_parse_page_pair)
    parser.add_argument("--timeline-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    timeline_paths = tuple(sorted(args.timeline_dir.glob("*.json")))
    report = audit_sportradar_start_time_coverage(
        page_pairs=tuple(args.page),
        timeline_paths=timeline_paths,
    )
    rendered = json.dumps(
        report.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
