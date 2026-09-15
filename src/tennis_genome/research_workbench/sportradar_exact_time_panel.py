from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord
from .sportradar_season_inventory import (
    INVENTORY_ID,
    SOURCE_CONTRACT as INVENTORY_SOURCE_CONTRACT,
    SeasonInventoryRow,
    SportradarSeasonInventory,
)
from .sportradar_start_time_admission import (
    DEFAULT_POLICY,
    ExactTimeChronologyAdmissionReceipt,
    admit_exact_time_audit_bytes,
    chronology_admission_failure_reasons,
    parse_exact_time_audit_bytes,
    verify_exact_time_audit_integrity,
)

PANEL_ID = "SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001"
ACCESS_FAILURE_ID = "SPORTRADAR-HISTORICAL-SEASON-ACCESS-FAILURE-001"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CATEGORY_SCOPE = {
    "ATP": ("sr:category:3", "ATP"),
    "WTA": ("sr:category:6", "WTA"),
}

PanelDisposition = Literal[
    "CHRONOLOGY_ADMITTED",
    "CHRONOLOGY_FAILED",
    "ACCESS_FAILURE",
    "NOT_YET_HISTORICAL",
    "DISABLED_PROVIDER_SEASON",
]


class ProviderAccessFailureEvidence(WorkbenchRecord):
    evidence_id: Literal["SPORTRADAR-HISTORICAL-SEASON-ACCESS-FAILURE-001"] = (
        ACCESS_FAILURE_ID
    )
    season_id: str
    competition_id: str
    tour: Literal["ATP", "WTA"]
    endpoint_path: str
    attempted_at: str
    http_status: int
    failure_class: Literal["ACCESS_DENIED", "HISTORY_NOT_AVAILABLE"]
    response_headers_sha256: str
    response_body_sha256: str


class PanelSeasonDisposition(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    competition_id: str
    competition_name: str
    season_id: str
    season_start_date: str
    season_end_date: str
    inventory_status: str
    disposition: PanelDisposition
    selected_for_exact_time_panel: bool
    evidence_file_sha256: str | None
    evidence_semantic_sha256: str | None
    chronology_season_summaries_sha256: str | None
    chronology_timeline_bundle_sha256: str | None
    failure_reasons: tuple[str, ...]


class SportradarExactTimePanelManifest(WorkbenchRecord):
    panel_id: Literal["SPORTRADAR-HISTORICAL-EXACT-TIME-PANEL-001"] = PANEL_ID
    inventory_id: Literal["SPORTRADAR-HISTORICAL-SEASON-INVENTORY-001"] = INVENTORY_ID
    inventory_source_contract: Literal[
        "SPORTRADAR_TENNIS_V3_CATEGORY_COMPETITION_SEASONS_V1"
    ] = INVENTORY_SOURCE_CONTRACT
    admission_policy_sha256: str
    inventory_file_sha256: str
    inventory_semantic_sha256: str
    rows: tuple[PanelSeasonDisposition, ...]
    historical_candidate_count: int
    chronology_admitted_count: int
    chronology_failed_count: int
    access_failure_count: int
    not_yet_historical_count: int
    disabled_season_count: int
    selected_season_ids: tuple[str, ...]
    admitted_receipt_sha256s: tuple[str, ...]
    inventory_code_sha256: str
    admission_code_sha256: str
    panel_code_sha256: str


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_sha256(repo_root: Path, relative_path: str) -> str:
    path = repo_root / relative_path
    if not path.is_file():
        raise ValueError(f"required panel code file is missing: {relative_path}")
    return _file_sha256(path)


def _require_sha256(value: str, *, field: str) -> None:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256")


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


def _iso_date(value: str, *, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _strict_json_bytes(content: bytes, *, label: str) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def parse_season_inventory_bytes(content: bytes) -> SportradarSeasonInventory:
    payload = _strict_json_bytes(content, label="season inventory")
    return SportradarSeasonInventory.model_validate(payload)


def verify_season_inventory_integrity(inventory: SportradarSeasonInventory) -> None:
    """Independently verify inventory arithmetic and structural classifications."""

    if inventory.inventory_id != INVENTORY_ID:
        raise ValueError("unexpected season inventory version")
    if inventory.source_contract != INVENTORY_SOURCE_CONTRACT:
        raise ValueError("unexpected season inventory source contract")
    snapshot_date = _aware_time(inventory.snapshot_at, field="snapshot_at").date()
    _require_sha256(inventory.atp_competitions_sha256, field="atp_competitions_sha256")
    _require_sha256(inventory.wta_competitions_sha256, field="wta_competitions_sha256")

    competition_ids = [row.competition_id for row in inventory.competition_rows]
    if len(competition_ids) != len(set(competition_ids)):
        raise ValueError("season inventory contains duplicate competition IDs")
    if inventory.competition_count != len(inventory.competition_rows):
        raise ValueError("competition count does not reproduce")

    competitions = {row.competition_id: row for row in inventory.competition_rows}
    required: set[str] = set()
    non_singles = 0
    for row in inventory.competition_rows:
        category_id, category_name = _CATEGORY_SCOPE[row.tour]
        if row.category_id != category_id or row.category_name.upper() != category_name:
            raise ValueError("competition row category does not match frozen tour semantics")
        expected_catalog_sha = (
            inventory.atp_competitions_sha256
            if row.tour == "ATP"
            else inventory.wta_competitions_sha256
        )
        if row.catalog_sha256 != expected_catalog_sha:
            raise ValueError("competition row detached from retained category catalog")
        if row.competition_type == "singles":
            if row.scope != "SEASON_INVENTORY_REQUIRED":
                raise ValueError("singles competition is not inventory-required")
            required.add(row.competition_id)
        else:
            if row.scope != "NON_SINGLES_STRUCTURAL_EXCLUSION":
                raise ValueError("non-singles competition is not structurally excluded")
            non_singles += 1

    if inventory.required_singles_competition_count != len(required):
        raise ValueError("required singles competition count does not reproduce")
    if inventory.non_singles_competition_count != non_singles:
        raise ValueError("non-singles competition count does not reproduce")

    catalog_ids = [row.competition_id for row in inventory.season_catalogs]
    if len(catalog_ids) != len(set(catalog_ids)):
        raise ValueError("season inventory contains duplicate season-catalog evidence")
    if set(catalog_ids) != required:
        raise ValueError("season-catalog evidence does not exactly cover required competitions")
    catalog_by_competition = {
        row.competition_id: row for row in inventory.season_catalogs
    }
    for row in inventory.season_catalogs:
        competition = competitions[row.competition_id]
        if row.tour != competition.tour:
            raise ValueError("season-catalog tour does not match competition")
        _require_sha256(row.payload_sha256, field="season catalog payload_sha256")
        if row.provider_generated_at is not None:
            _aware_time(row.provider_generated_at, field="provider_generated_at")

    season_ids = [row.season_id for row in inventory.season_rows]
    if len(season_ids) != len(set(season_ids)):
        raise ValueError("season inventory contains duplicate season IDs")
    if inventory.season_count != len(inventory.season_rows):
        raise ValueError("season count does not reproduce")

    per_competition: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for row in inventory.season_rows:
        competition = competitions.get(row.competition_id)
        if competition is None or competition.competition_id not in required:
            raise ValueError("season row references a non-required competition")
        if row.tour != competition.tour:
            raise ValueError("season row tour does not match competition")
        if row.category_id != competition.category_id:
            raise ValueError("season row category does not match competition")
        if row.competition_name != competition.competition_name:
            raise ValueError("season row competition name does not match catalog")
        catalog = catalog_by_competition[row.competition_id]
        if row.seasons_payload_sha256 != catalog.payload_sha256:
            raise ValueError("season row detached from retained Competition Seasons payload")
        start = _iso_date(row.start_date, field="season.start_date")
        end = _iso_date(row.end_date, field="season.end_date")
        if end < start:
            raise ValueError("season end_date precedes start_date")
        expected_status: str
        if row.disabled:
            expected_status = "DISABLED_PROVIDER_SEASON"
        elif end < snapshot_date:
            expected_status = "HISTORICAL_CANDIDATE"
        else:
            expected_status = "NOT_YET_HISTORICAL"
        if row.status != expected_status:
            raise ValueError("season structural status does not reproduce")
        per_competition[row.competition_id] += 1
        statuses[row.status] += 1

    for competition_id, catalog in catalog_by_competition.items():
        if catalog.returned_season_count != per_competition[competition_id]:
            raise ValueError("returned season count does not reproduce from season rows")
    if inventory.historical_candidate_count != statuses["HISTORICAL_CANDIDATE"]:
        raise ValueError("historical-candidate count does not reproduce")
    if inventory.not_yet_historical_count != statuses["NOT_YET_HISTORICAL"]:
        raise ValueError("not-yet-historical count does not reproduce")
    if inventory.disabled_season_count != statuses["DISABLED_PROVIDER_SEASON"]:
        raise ValueError("disabled-season count does not reproduce")


def build_provider_access_failure_evidence(
    *,
    season: SeasonInventoryRow,
    endpoint_path: str,
    attempted_at: datetime,
    http_status: int,
    response_headers_path: Path,
    response_body_path: Path,
) -> ProviderAccessFailureEvidence:
    if attempted_at.tzinfo is None or attempted_at.utcoffset() is None:
        raise ValueError("attempted_at must be timezone-aware")
    endpoint = endpoint_path.split("?", 1)[0].lstrip("/")
    expected = f"seasons/{season.season_id}/summaries.json"
    if endpoint != expected:
        raise ValueError("ACCESS_FAILURE may only bind the inventory season's summaries endpoint")
    if http_status in {401, 403}:
        failure_class: Literal["ACCESS_DENIED", "HISTORY_NOT_AVAILABLE"] = "ACCESS_DENIED"
    elif http_status in {404, 410}:
        failure_class = "HISTORY_NOT_AVAILABLE"
    else:
        raise ValueError("only retained 401/403/404/410 responses finalize ACCESS_FAILURE")
    return ProviderAccessFailureEvidence(
        season_id=season.season_id,
        competition_id=season.competition_id,
        tour=season.tour,
        endpoint_path=endpoint,
        attempted_at=attempted_at.astimezone(UTC).isoformat(),
        http_status=http_status,
        failure_class=failure_class,
        response_headers_sha256=_file_sha256(response_headers_path),
        response_body_sha256=_file_sha256(response_body_path),
    )


def _verify_audit_matches_inventory(
    audit_season: object,
    inventory_row: SeasonInventoryRow,
) -> None:
    season_id = getattr(audit_season, "season_id")
    competition_id = getattr(audit_season, "competition_id")
    competition_name = getattr(audit_season, "competition_name")
    season_start_date = getattr(audit_season, "season_start_date")
    category_id = getattr(audit_season, "category_id")
    if season_id != inventory_row.season_id:
        raise ValueError("chronology audit season ID does not match inventory")
    if competition_id != inventory_row.competition_id:
        raise ValueError("chronology audit competition ID does not match inventory")
    if competition_name != inventory_row.competition_name:
        raise ValueError("chronology audit competition name does not match inventory")
    if season_start_date != inventory_row.start_date:
        raise ValueError("chronology audit season start does not match inventory")
    if category_id != inventory_row.category_id:
        raise ValueError("chronology audit category does not match inventory")


def build_exact_time_panel_manifest(
    *,
    inventory_content: bytes,
    admitted_audits: dict[str, bytes],
    failed_audits: dict[str, bytes],
    access_failures: dict[str, ProviderAccessFailureEvidence],
    repo_root: Path,
) -> SportradarExactTimePanelManifest:
    inventory = parse_season_inventory_bytes(inventory_content)
    verify_season_inventory_integrity(inventory)
    rows_by_id = {row.season_id: row for row in inventory.season_rows}
    historical_ids = {
        row.season_id
        for row in inventory.season_rows
        if row.status == "HISTORICAL_CANDIDATE"
    }

    evidence_sets = [set(admitted_audits), set(failed_audits), set(access_failures)]
    combined: set[str] = set()
    for evidence_set in evidence_sets:
        overlap = combined & evidence_set
        if overlap:
            raise ValueError(f"season has multiple chronology dispositions: {sorted(overlap)}")
        combined |= evidence_set
    missing = sorted(historical_ids - combined)
    extra = sorted(combined - historical_ids)
    if missing or extra:
        raise ValueError(
            f"historical season disposition set mismatch; missing={missing}, extra={extra}"
        )

    disposition_rows: list[PanelSeasonDisposition] = []
    receipt_hashes: list[str] = []
    for inventory_row in inventory.season_rows:
        season_id = inventory_row.season_id
        if inventory_row.status == "NOT_YET_HISTORICAL":
            disposition_rows.append(
                PanelSeasonDisposition(
                    tour=inventory_row.tour,
                    competition_id=inventory_row.competition_id,
                    competition_name=inventory_row.competition_name,
                    season_id=season_id,
                    season_start_date=inventory_row.start_date,
                    season_end_date=inventory_row.end_date,
                    inventory_status=inventory_row.status,
                    disposition="NOT_YET_HISTORICAL",
                    selected_for_exact_time_panel=False,
                    evidence_file_sha256=None,
                    evidence_semantic_sha256=None,
                    chronology_season_summaries_sha256=None,
                    chronology_timeline_bundle_sha256=None,
                    failure_reasons=(),
                )
            )
            continue
        if inventory_row.status == "DISABLED_PROVIDER_SEASON":
            disposition_rows.append(
                PanelSeasonDisposition(
                    tour=inventory_row.tour,
                    competition_id=inventory_row.competition_id,
                    competition_name=inventory_row.competition_name,
                    season_id=season_id,
                    season_start_date=inventory_row.start_date,
                    season_end_date=inventory_row.end_date,
                    inventory_status=inventory_row.status,
                    disposition="DISABLED_PROVIDER_SEASON",
                    selected_for_exact_time_panel=False,
                    evidence_file_sha256=None,
                    evidence_semantic_sha256=None,
                    chronology_season_summaries_sha256=None,
                    chronology_timeline_bundle_sha256=None,
                    failure_reasons=(),
                )
            )
            continue

        if season_id in admitted_audits:
            content = admitted_audits[season_id]
            audit = parse_exact_time_audit_bytes(content)
            _verify_audit_matches_inventory(audit.season, inventory_row)
            receipt: ExactTimeChronologyAdmissionReceipt = admit_exact_time_audit_bytes(
                content, repo_root=repo_root
            )
            receipt_hashes.append(receipt.semantic_sha256)
            disposition_rows.append(
                PanelSeasonDisposition(
                    tour=inventory_row.tour,
                    competition_id=inventory_row.competition_id,
                    competition_name=inventory_row.competition_name,
                    season_id=season_id,
                    season_start_date=inventory_row.start_date,
                    season_end_date=inventory_row.end_date,
                    inventory_status=inventory_row.status,
                    disposition="CHRONOLOGY_ADMITTED",
                    selected_for_exact_time_panel=True,
                    evidence_file_sha256=hashlib.sha256(content).hexdigest(),
                    evidence_semantic_sha256=audit.semantic_sha256,
                    chronology_season_summaries_sha256=(
                        audit.base_audit.season_summaries_sha256
                    ),
                    chronology_timeline_bundle_sha256=audit.base_audit.timeline_bundle_sha256,
                    failure_reasons=(),
                )
            )
            continue

        if season_id in failed_audits:
            content = failed_audits[season_id]
            audit = parse_exact_time_audit_bytes(content)
            _verify_audit_matches_inventory(audit.season, inventory_row)
            verify_exact_time_audit_integrity(audit)
            reasons = chronology_admission_failure_reasons(audit)
            if not reasons:
                raise ValueError("CHRONOLOGY_FAILED audit actually passes frozen admission gate")
            disposition_rows.append(
                PanelSeasonDisposition(
                    tour=inventory_row.tour,
                    competition_id=inventory_row.competition_id,
                    competition_name=inventory_row.competition_name,
                    season_id=season_id,
                    season_start_date=inventory_row.start_date,
                    season_end_date=inventory_row.end_date,
                    inventory_status=inventory_row.status,
                    disposition="CHRONOLOGY_FAILED",
                    selected_for_exact_time_panel=False,
                    evidence_file_sha256=hashlib.sha256(content).hexdigest(),
                    evidence_semantic_sha256=audit.semantic_sha256,
                    chronology_season_summaries_sha256=(
                        audit.base_audit.season_summaries_sha256
                    ),
                    chronology_timeline_bundle_sha256=audit.base_audit.timeline_bundle_sha256,
                    failure_reasons=reasons,
                )
            )
            continue

        access = access_failures[season_id]
        if access.season_id != inventory_row.season_id:
            raise ValueError("access failure season ID does not match inventory")
        if access.competition_id != inventory_row.competition_id:
            raise ValueError("access failure competition does not match inventory")
        if access.tour != inventory_row.tour:
            raise ValueError("access failure tour does not match inventory")
        _aware_time(access.attempted_at, field="access failure attempted_at")
        _require_sha256(access.response_headers_sha256, field="response_headers_sha256")
        _require_sha256(access.response_body_sha256, field="response_body_sha256")
        expected_endpoint = f"seasons/{season_id}/summaries.json"
        if access.endpoint_path != expected_endpoint:
            raise ValueError("access failure endpoint does not match inventory season")
        if access.http_status in {401, 403}:
            if access.failure_class != "ACCESS_DENIED":
                raise ValueError("access failure class does not match HTTP status")
        elif access.http_status in {404, 410}:
            if access.failure_class != "HISTORY_NOT_AVAILABLE":
                raise ValueError("access failure class does not match HTTP status")
        else:
            raise ValueError("ACCESS_FAILURE uses a non-finalizable HTTP status")
        disposition_rows.append(
            PanelSeasonDisposition(
                tour=inventory_row.tour,
                competition_id=inventory_row.competition_id,
                competition_name=inventory_row.competition_name,
                season_id=season_id,
                season_start_date=inventory_row.start_date,
                season_end_date=inventory_row.end_date,
                inventory_status=inventory_row.status,
                disposition="ACCESS_FAILURE",
                selected_for_exact_time_panel=False,
                evidence_file_sha256=None,
                evidence_semantic_sha256=access.semantic_sha256,
                chronology_season_summaries_sha256=None,
                chronology_timeline_bundle_sha256=None,
                failure_reasons=(access.failure_class,),
            )
        )

    disposition_rows.sort(
        key=lambda row: (row.tour, row.competition_id, row.season_start_date, row.season_id)
    )
    counts = Counter(row.disposition for row in disposition_rows)
    selected = tuple(
        sorted(row.season_id for row in disposition_rows if row.selected_for_exact_time_panel)
    )
    receipt_hashes.sort()

    return SportradarExactTimePanelManifest(
        admission_policy_sha256=DEFAULT_POLICY.semantic_sha256,
        inventory_file_sha256=hashlib.sha256(inventory_content).hexdigest(),
        inventory_semantic_sha256=inventory.semantic_sha256,
        rows=tuple(disposition_rows),
        historical_candidate_count=inventory.historical_candidate_count,
        chronology_admitted_count=counts["CHRONOLOGY_ADMITTED"],
        chronology_failed_count=counts["CHRONOLOGY_FAILED"],
        access_failure_count=counts["ACCESS_FAILURE"],
        not_yet_historical_count=counts["NOT_YET_HISTORICAL"],
        disabled_season_count=counts["DISABLED_PROVIDER_SEASON"],
        selected_season_ids=selected,
        admitted_receipt_sha256s=tuple(receipt_hashes),
        inventory_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_season_inventory.py",
        ),
        admission_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_start_time_admission.py",
        ),
        panel_code_sha256=_code_sha256(
            repo_root,
            "src/tennis_genome/research_workbench/sportradar_exact_time_panel.py",
        ),
    )


def _parse_path_binding(value: str, *, option: str) -> tuple[str, Path]:
    season_id, separator, path = value.partition("::")
    if not separator or not season_id.strip() or not path.strip():
        raise argparse.ArgumentTypeError(f"{option} must be SEASON_ID::PATH")
    return season_id.strip(), Path(path)


def _load_bound_files(values: list[str], *, option: str) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for value in values:
        season_id, path = _parse_path_binding(value, option=option)
        if season_id in result:
            raise ValueError(f"duplicate {option} binding for {season_id}")
        result[season_id] = path.read_bytes()
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize an anti-cherry-picking Sportradar exact-time season panel"
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--admitted-audit", action="append", default=[])
    parser.add_argument("--failed-audit", action="append", default=[])
    parser.add_argument(
        "--access-failure",
        action="append",
        default=[],
        help="prebuilt ProviderAccessFailureEvidence JSON; repeat",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    admitted = _load_bound_files(args.admitted_audit, option="--admitted-audit")
    failed = _load_bound_files(args.failed_audit, option="--failed-audit")
    access: dict[str, ProviderAccessFailureEvidence] = {}
    for path_text in args.access_failure:
        path = Path(path_text)
        payload = _strict_json_bytes(path.read_bytes(), label="access failure evidence")
        evidence = ProviderAccessFailureEvidence.model_validate(payload)
        if evidence.season_id in access:
            raise ValueError(f"duplicate access-failure evidence for {evidence.season_id}")
        access[evidence.season_id] = evidence
    manifest = build_exact_time_panel_manifest(
        inventory_content=args.inventory.read_bytes(),
        admitted_audits=admitted,
        failed_audits=failed,
        access_failures=access,
        repo_root=args.repo_root,
    )
    rendered = json.dumps(
        manifest.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
