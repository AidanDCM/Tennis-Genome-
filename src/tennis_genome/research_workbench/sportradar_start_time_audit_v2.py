from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal

from . import sportradar_start_time_audit as audit_v1
from .contracts import WorkbenchRecord

AUDIT_ID = "SPORTRADAR-HISTORICAL-START-TIME-AUDIT-002"
SOURCE_CONTRACT = "SPORTRADAR_TENNIS_V3_SEASON_SUMMARIES_PLUS_TIMELINE_V2"
EVIDENCE_ROLE = audit_v1.EVIDENCE_ROLE


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


def _iso_date(value: object, *, field: str) -> str:
    try:
        return date.fromisoformat(_required_text(value, field=field)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _json_object_bytes(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


class SportradarSeasonIdentity(WorkbenchRecord):
    category_id: str
    category_name: str
    competition_id: str
    competition_name: str
    competition_type: str
    season_id: str
    season_start_date: str


class StartTimeCoverageAuditV2(WorkbenchRecord):
    audit_id: Literal["SPORTRADAR-HISTORICAL-START-TIME-AUDIT-002"] = AUDIT_ID
    evidence_role: Literal["DESCRIPTIVE_ONLY_SOURCE_VALIDATION"] = EVIDENCE_ROLE
    source_contract: Literal[
        "SPORTRADAR_TENNIS_V3_SEASON_SUMMARIES_PLUS_TIMELINE_V2"
    ] = SOURCE_CONTRACT
    season: SportradarSeasonIdentity
    base_audit: audit_v1.StartTimeCoverageAudit


def _season_identity(summary: object) -> SportradarSeasonIdentity:
    root = _as_dict(summary, field="summary")
    sport_event = _as_dict(root.get("sport_event"), field="summary.sport_event")
    context = _as_dict(
        sport_event.get("sport_event_context"), field="sport_event_context"
    )
    category = _as_dict(context.get("category"), field="sport_event_context.category")
    competition = _as_dict(
        context.get("competition"), field="sport_event_context.competition"
    )
    season = _as_dict(context.get("season"), field="sport_event_context.season")

    competition_id = _required_text(competition.get("id"), field="competition.id")
    season_competition_id = _required_text(
        season.get("competition_id"), field="season.competition_id"
    )
    if season_competition_id != competition_id:
        raise ValueError("Sportradar season competition_id does not match competition")

    return SportradarSeasonIdentity(
        category_id=_required_text(category.get("id"), field="category.id"),
        category_name=_required_text(category.get("name"), field="category.name"),
        competition_id=competition_id,
        competition_name=_required_text(competition.get("name"), field="competition.name"),
        competition_type=_required_text(
            competition.get("type"), field="competition.type"
        ).lower(),
        season_id=_required_text(season.get("id"), field="season.id"),
        season_start_date=_iso_date(season.get("start_date"), field="season.start_date"),
    )


def derive_single_season_identity(summaries: Sequence[object]) -> SportradarSeasonIdentity:
    """Require every retained Season Summaries row to identify the same provider season."""

    if not summaries:
        raise ValueError("historical start-time audit requires a non-empty provider season")
    expected = _season_identity(summaries[0])
    expected_payload = expected.canonical_payload()
    for summary in summaries[1:]:
        observed = _season_identity(summary)
        if observed.canonical_payload() != expected_payload:
            raise ValueError("Season Summaries evidence mixes provider season identities")
    return expected


def _event_id(summary: object) -> str:
    root = _as_dict(summary, field="summary")
    event = _as_dict(root.get("sport_event"), field="summary.sport_event")
    return _required_text(event.get("id"), field="summary.sport_event.id")


def _timeline_event_id(path: Path) -> str:
    payload = _json_object_bytes(path.read_bytes(), label=f"timeline {path}")
    event = _as_dict(payload.get("sport_event"), field="timeline.sport_event")
    return _required_text(event.get("id"), field="timeline.sport_event.id")


def audit_sportradar_start_time_coverage_v2(
    *,
    page_pairs: Sequence[tuple[Path, Path]],
    timeline_paths: Sequence[Path],
) -> StartTimeCoverageAuditV2:
    """Bind the v1 chronology audit to one exact Sportradar season identity."""

    aggregate = audit_v1.build_complete_season_summaries(page_pairs)
    summaries = _as_list(aggregate.get("summaries"), field="summaries")
    season = derive_single_season_identity(summaries)

    summary_ids = {_event_id(summary) for summary in summaries}
    timeline_ids: set[str] = set()
    for path in timeline_paths:
        event_id = _timeline_event_id(path)
        if event_id in timeline_ids:
            raise ValueError(f"duplicate retained timeline for {event_id}")
        timeline_ids.add(event_id)
    extras = sorted(timeline_ids - summary_ids)
    if extras:
        raise ValueError(
            "retained timeline evidence contains events outside the Season Summaries denominator: "
            + ", ".join(extras)
        )

    base = audit_v1.audit_sportradar_start_time_coverage(
        page_pairs=page_pairs,
        timeline_paths=timeline_paths,
    )
    if base.audit_id != audit_v1.AUDIT_ID:
        raise ValueError("unexpected base start-time audit version")
    expected_aggregate_sha = _sha256_bytes(_canonical_json(aggregate))
    if base.season_summaries_sha256 != expected_aggregate_sha:
        raise ValueError("base audit detached from retained Season Summaries evidence")

    return StartTimeCoverageAuditV2(season=season, base_audit=base)


def _parse_page_pair(value: str) -> tuple[Path, Path]:
    raw, separator, headers = value.partition("::")
    if not separator or not raw.strip() or not headers.strip():
        raise argparse.ArgumentTypeError("--page must be RAW_JSON::HEADERS_FILE")
    return Path(raw), Path(headers)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit one retained Sportradar season for exact historical start times"
    )
    parser.add_argument(
        "--page",
        action="append",
        required=True,
        type=_parse_page_pair,
        help="retained Season Summaries RAW_JSON::HEADERS_FILE; repeat for pagination",
    )
    parser.add_argument("--timeline-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    timeline_paths = tuple(sorted(args.timeline_dir.glob("*.json")))
    report = audit_sportradar_start_time_coverage_v2(
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
