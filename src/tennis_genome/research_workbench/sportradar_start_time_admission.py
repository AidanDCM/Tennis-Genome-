from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord
from .sportradar_start_time_audit_v2 import (
    AUDIT_ID,
    SOURCE_CONTRACT,
    StartTimeCoverageAuditV2,
)

POLICY_ID = "SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001"
ADMISSION_STATUS = "ADMITTED_EXACT_START_CHRONOLOGY_ONLY"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAIN_TOURS = {
    "sr:category:3": ("ATP", "ATP"),
    "sr:category:6": ("WTA", "WTA"),
}
_FAILURE_DISPOSITIONS = {
    "MISSING_TIMELINE",
    "MISSING_MATCH_STARTED",
    "CONFLICTING_MATCH_STARTED",
    "INVALID_MATCH_STARTED_TIME",
}
_PLAYED_DISPOSITIONS = _FAILURE_DISPOSITIONS | {"EXACT_MATCH_STARTED"}


class ExactTimeChronologyAdmissionPolicy(WorkbenchRecord):
    """Pre-result structural gate for one provider season's chronology evidence."""

    policy_id: Literal["SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001"] = POLICY_ID
    required_audit_id: Literal["SPORTRADAR-HISTORICAL-START-TIME-AUDIT-002"] = AUDIT_ID
    required_source_contract: Literal[
        "SPORTRADAR_TENNIS_V3_SEASON_SUMMARIES_PLUS_TIMELINE_V2"
    ] = SOURCE_CONTRACT
    require_single_main_tour_singles_season: Literal[True] = True
    require_completed_season: Literal[True] = True
    require_exact_start_for_every_played_terminal: Literal[True] = True
    allow_walkover_without_start: Literal[True] = True
    allow_updated_start_when_update_time_retained: Literal[True] = True
    scheduled_start_is_diagnostic_only: Literal[True] = True
    percentage_thresholds_forbidden: Literal[True] = True


DEFAULT_POLICY = ExactTimeChronologyAdmissionPolicy()


class ExactTimeChronologyAdmissionReceipt(WorkbenchRecord):
    receipt_id: Literal["SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001-RECEIPT"] = (
        "SPORTRADAR-HISTORICAL-EXACT-TIME-ADMISSION-001-RECEIPT"
    )
    policy_sha256: str
    audit_file_sha256: str
    audit_semantic_sha256: str
    base_audit_semantic_sha256: str
    source_contract: str
    tour: Literal["ATP", "WTA"]
    season_id: str
    season_start_date: str
    competition_id: str
    competition_name: str
    season_summaries_sha256: str
    timeline_bundle_sha256: str
    raw_summary_count: int
    played_terminal_count: int
    exact_match_started_count: int
    walkover_count: int
    updated_match_started_count: int
    base_audit_code_sha256: str
    audit_v2_code_sha256: str
    admission_code_sha256: str
    admission_status: Literal["ADMITTED_EXACT_START_CHRONOLOGY_ONLY"] = ADMISSION_STATUS


def _parse_audit_bytes(content: bytes) -> StartTimeCoverageAuditV2:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("exact-time audit must be UTF-8 JSON") from exc

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise ValueError("exact-time audit is not valid JSON") from exc
    return StartTimeCoverageAuditV2.model_validate(payload)


def _require_sha256(value: str, *, field: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256")


def _aware_time(value: str, *, field: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _iso_date(value: str, *, field: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _assert_close(label: str, observed: float, expected: float) -> None:
    if not math.isfinite(observed) or not math.isfinite(expected):
        raise ValueError(f"{label} must be finite")
    if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{label} does not reproduce")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    if not path.is_file():
        raise ValueError(f"required admission code file is missing: {relative_path}")
    return _file_sha256(path)


def verify_exact_time_audit_for_admission(
    audit: StartTimeCoverageAuditV2,
    *,
    policy: ExactTimeChronologyAdmissionPolicy = DEFAULT_POLICY,
) -> Literal["ATP", "WTA"]:
    """Independently rederive one season's chronology gate from the audit payload."""

    if audit.audit_id != policy.required_audit_id:
        raise ValueError("exact-time audit version does not match frozen admission policy")
    if audit.source_contract != policy.required_source_contract:
        raise ValueError("exact-time audit source contract does not match frozen policy")

    season = audit.season
    mapping = _MAIN_TOURS.get(season.category_id)
    if mapping is None:
        raise ValueError("season is not a frozen main-tour ATP/WTA category")
    expected_name, tour = mapping
    if season.category_name.upper() != expected_name:
        raise ValueError("Sportradar category ID/name semantics drifted")
    if season.competition_type != "singles":
        raise ValueError("exact-time admission requires a singles competition season")
    if not season.season_id.strip() or not season.competition_id.strip():
        raise ValueError("season and competition identities must be non-empty")
    if not season.competition_name.strip():
        raise ValueError("competition name must be non-empty")
    _iso_date(season.season_start_date, field="season_start_date")

    base = audit.base_audit
    _require_sha256(base.season_summaries_sha256, field="season_summaries_sha256")
    _require_sha256(base.timeline_bundle_sha256, field="timeline_bundle_sha256")
    if base.raw_summary_count != base.in_scope_count:
        raise ValueError(
            "admitted season may not silently drop provider summaries from the main-tour singles denominator"
        )
    if len(base.events) != base.in_scope_count:
        raise ValueError("event rows do not reproduce the in-scope denominator")
    if base.atp_count + base.wta_count != base.in_scope_count:
        raise ValueError("tour counts do not reproduce the in-scope denominator")
    if tour == "ATP":
        if base.atp_count != base.in_scope_count or base.wta_count != 0:
            raise ValueError("ATP season audit contains mixed-tour in-scope rows")
    else:
        if base.wta_count != base.in_scope_count or base.atp_count != 0:
            raise ValueError("WTA season audit contains mixed-tour in-scope rows")

    event_ids = [event.provider_event_id for event in base.events]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("exact-time audit contains duplicate provider event IDs")
    if any(event.tour != tour for event in base.events):
        raise ValueError("event tour does not match season category")

    counts = Counter(event.disposition for event in base.events)
    expected_played = sum(counts[disposition] for disposition in _PLAYED_DISPOSITIONS)
    if base.played_terminal_count != expected_played:
        raise ValueError("played-terminal count does not reproduce from event dispositions")
    if base.exact_match_started_count != counts["EXACT_MATCH_STARTED"]:
        raise ValueError("exact-start count does not reproduce from event dispositions")
    if base.walkover_count != counts["WALKOVER"]:
        raise ValueError("walkover count does not reproduce from event dispositions")
    if base.nonterminal_count != counts["NOT_TERMINAL"]:
        raise ValueError("nonterminal count does not reproduce from event dispositions")
    if base.missing_timeline_count != counts["MISSING_TIMELINE"]:
        raise ValueError("missing-timeline count does not reproduce")
    if base.missing_match_started_count != counts["MISSING_MATCH_STARTED"]:
        raise ValueError("missing-start count does not reproduce")
    if base.conflicting_match_started_count != counts["CONFLICTING_MATCH_STARTED"]:
        raise ValueError("conflicting-start count does not reproduce")
    if base.invalid_match_started_time_count != counts["INVALID_MATCH_STARTED_TIME"]:
        raise ValueError("invalid-start-time count does not reproduce")
    expected_updated = sum(event.match_started_updated for event in base.events)
    if base.updated_match_started_count != expected_updated:
        raise ValueError("updated-start count does not reproduce")

    expected_rate = (
        0.0
        if base.played_terminal_count == 0
        else base.exact_match_started_count / base.played_terminal_count
    )
    _assert_close("exact coverage rate", base.exact_coverage_rate, expected_rate)

    terminal_statuses = {"closed", "ended"}
    for event in base.events:
        if event.disposition == "EXACT_MATCH_STARTED":
            if event.provider_status not in terminal_statuses:
                raise ValueError("exact-start event is not terminal")
            if event.match_started_time is None or event.timeline_sha256 is None:
                raise ValueError("exact-start event lacks retained chronology evidence")
            _aware_time(event.match_started_time, field="match_started_time")
            _require_sha256(event.timeline_sha256, field="timeline_sha256")
            if event.match_started_updated:
                if event.match_started_updated_time is None:
                    raise ValueError(
                        "updated match_started event lacks retained updated_time"
                    )
                _aware_time(
                    event.match_started_updated_time,
                    field="match_started_updated_time",
                )
            elif event.match_started_updated_time is not None:
                raise ValueError("updated_time is present without updated=true")
        elif event.disposition == "WALKOVER":
            if event.provider_status not in terminal_statuses:
                raise ValueError("walkover event is not terminal")
            if event.winning_reason != "walkover":
                raise ValueError("walkover disposition lacks provider walkover reason")
            if event.match_started_time is not None:
                raise ValueError("walkover must not be treated as a played exact-start row")

    if base.in_scope_count <= 0:
        raise ValueError("exact-time admission requires a non-empty season")
    if base.played_terminal_count <= 0:
        raise ValueError("exact-time admission requires at least one played terminal match")
    if base.nonterminal_count != 0:
        raise ValueError("exact-time admission requires a completed season")
    if any(counts[disposition] for disposition in _FAILURE_DISPOSITIONS):
        raise ValueError("every played terminal match must have one valid match_started time")
    if base.exact_match_started_count != base.played_terminal_count:
        raise ValueError("exact-start coverage is not complete")
    _assert_close("admission exact coverage rate", base.exact_coverage_rate, 1.0)
    return tour


def admit_exact_time_audit_bytes(
    content: bytes,
    *,
    repo_root: Path,
    policy: ExactTimeChronologyAdmissionPolicy = DEFAULT_POLICY,
) -> ExactTimeChronologyAdmissionReceipt:
    audit = _parse_audit_bytes(content)
    tour = verify_exact_time_audit_for_admission(audit, policy=policy)
    base = audit.base_audit

    return ExactTimeChronologyAdmissionReceipt(
        policy_sha256=policy.semantic_sha256,
        audit_file_sha256=hashlib.sha256(content).hexdigest(),
        audit_semantic_sha256=audit.semantic_sha256,
        base_audit_semantic_sha256=base.semantic_sha256,
        source_contract=audit.source_contract,
        tour=tour,
        season_id=audit.season.season_id,
        season_start_date=audit.season.season_start_date,
        competition_id=audit.season.competition_id,
        competition_name=audit.season.competition_name,
        season_summaries_sha256=base.season_summaries_sha256,
        timeline_bundle_sha256=base.timeline_bundle_sha256,
        raw_summary_count=base.raw_summary_count,
        played_terminal_count=base.played_terminal_count,
        exact_match_started_count=base.exact_match_started_count,
        walkover_count=base.walkover_count,
        updated_match_started_count=base.updated_match_started_count,
        base_audit_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_start_time_audit.py",
        ),
        audit_v2_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_start_time_audit_v2.py",
        ),
        admission_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_start_time_admission.py",
        ),
    )


def admit_exact_time_audit_file(
    audit_path: Path,
    *,
    repo_root: Path,
) -> ExactTimeChronologyAdmissionReceipt:
    return admit_exact_time_audit_bytes(audit_path.read_bytes(), repo_root=repo_root)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and admit one complete Sportradar exact-start season audit"
    )
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    receipt = admit_exact_time_audit_file(args.audit, repo_root=args.repo_root)
    rendered = json.dumps(
        receipt.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
