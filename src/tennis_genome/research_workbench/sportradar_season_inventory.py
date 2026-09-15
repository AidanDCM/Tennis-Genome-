from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord

INVENTORY_ID = "SPORTRADAR-HISTORICAL-SEASON-INVENTORY-001"
SOURCE_CONTRACT = "SPORTRADAR_TENNIS_V3_CATEGORY_COMPETITION_SEASONS_V1"
_CATEGORY_SCOPE = {
    "ATP": ("sr:category:3", "ATP"),
    "WTA": ("sr:category:6", "WTA"),
}

CompetitionScope = Literal[
    "SEASON_INVENTORY_REQUIRED",
    "NON_SINGLES_STRUCTURAL_EXCLUSION",
]
SeasonStatus = Literal[
    "HISTORICAL_CANDIDATE",
    "NOT_YET_HISTORICAL",
    "DISABLED_PROVIDER_SEASON",
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


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _iso_date(value: object, *, field: str) -> str:
    try:
        return date.fromisoformat(_required_text(value, field=field)).isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _aware_time(value: object, *, field: str) -> datetime:
    text = _required_text(value, field=field)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _required_generated_at(payload: dict[str, object], *, field: str) -> str:
    return _aware_time(payload.get("generated_at"), field=field).isoformat()


class CompetitionInventoryRow(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    category_id: str
    category_name: str
    competition_id: str
    competition_name: str
    competition_type: str
    level: str | None
    gender: str | None
    parent_id: str | None
    catalog_sha256: str
    scope: CompetitionScope


class CompetitionSeasonCatalogEvidence(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    competition_id: str
    payload_sha256: str
    provider_generated_at: str
    returned_season_count: int


class SeasonInventoryRow(WorkbenchRecord):
    tour: Literal["ATP", "WTA"]
    category_id: str
    competition_id: str
    competition_name: str
    season_id: str
    season_name: str
    start_date: str
    end_date: str
    year: str | None
    disabled: bool
    seasons_payload_sha256: str
    status: SeasonStatus


class SportradarSeasonInventory(WorkbenchRecord):
    inventory_id: Literal["SPORTRADAR-HISTORICAL-SEASON-INVENTORY-001"] = INVENTORY_ID
    source_contract: Literal[
        "SPORTRADAR_TENNIS_V3_CATEGORY_COMPETITION_SEASONS_V1"
    ] = SOURCE_CONTRACT
    snapshot_at: str
    atp_competitions_sha256: str
    wta_competitions_sha256: str
    atp_competitions_generated_at: str
    wta_competitions_generated_at: str
    competition_rows: tuple[CompetitionInventoryRow, ...]
    season_catalogs: tuple[CompetitionSeasonCatalogEvidence, ...]
    season_rows: tuple[SeasonInventoryRow, ...]
    competition_count: int
    required_singles_competition_count: int
    non_singles_competition_count: int
    season_count: int
    historical_candidate_count: int
    not_yet_historical_count: int
    disabled_season_count: int

    def model_post_init(self, __context: object) -> None:
        provider_times = [
            _aware_time(
                self.atp_competitions_generated_at,
                field="atp_competitions_generated_at",
            ),
            _aware_time(
                self.wta_competitions_generated_at,
                field="wta_competitions_generated_at",
            ),
            *(
                _aware_time(
                    row.provider_generated_at,
                    field=f"Competition Seasons {row.competition_id} provider_generated_at",
                )
                for row in self.season_catalogs
            ),
        ]
        provider_dates = {value.date() for value in provider_times}
        if len(provider_dates) != 1:
            raise ValueError("inventory provider generated_at evidence crosses UTC dates")
        expected_snapshot = max(provider_times)
        actual_snapshot = _aware_time(self.snapshot_at, field="snapshot_at")
        if actual_snapshot != expected_snapshot:
            raise ValueError("inventory snapshot_at does not equal latest provider generated_at")


def _parse_category_catalog(
    raw: bytes,
    *,
    tour: Literal["ATP", "WTA"],
) -> tuple[str, str, list[CompetitionInventoryRow], set[str]]:
    payload = _json_object_bytes(raw, label=f"{tour} Competitions by Category response")
    digest = _sha256_bytes(raw)
    generated_at = _required_generated_at(
        payload,
        field=f"{tour} Competitions by Category generated_at",
    )
    category_id, category_name = _CATEGORY_SCOPE[tour]
    rows: list[CompetitionInventoryRow] = []
    required: set[str] = set()
    seen: set[str] = set()

    for raw_competition in _as_list(payload.get("competitions"), field="competitions"):
        competition = _as_dict(raw_competition, field="competition")
        competition_id = _required_text(competition.get("id"), field="competition.id")
        if competition_id in seen:
            raise ValueError(f"{tour} competition catalog contains duplicate competition ID")
        seen.add(competition_id)
        category = _as_dict(competition.get("category"), field="competition.category")
        observed_category_id = _required_text(category.get("id"), field="category.id")
        observed_category_name = _required_text(category.get("name"), field="category.name")
        if (
            observed_category_id != category_id
            or observed_category_name.upper() != category_name
        ):
            raise ValueError(
                f"{tour} category catalog contains a competition from another category"
            )

        competition_type = _required_text(
            competition.get("type"), field="competition.type"
        ).lower()
        scope: CompetitionScope
        if competition_type == "singles":
            scope = "SEASON_INVENTORY_REQUIRED"
            required.add(competition_id)
        else:
            scope = "NON_SINGLES_STRUCTURAL_EXCLUSION"

        rows.append(
            CompetitionInventoryRow(
                tour=tour,
                category_id=category_id,
                category_name=category_name,
                competition_id=competition_id,
                competition_name=_required_text(
                    competition.get("name"), field="competition.name"
                ),
                competition_type=competition_type,
                level=_optional_text(competition.get("level")),
                gender=_optional_text(competition.get("gender")),
                parent_id=_optional_text(competition.get("parent_id")),
                catalog_sha256=digest,
                scope=scope,
            )
        )

    rows.sort(key=lambda row: (row.tour, row.competition_id))
    return digest, generated_at, rows, required


def _parse_season_catalog(
    raw: bytes,
    *,
    tour: Literal["ATP", "WTA"],
    competition: CompetitionInventoryRow,
    snapshot_date: date,
    seen_season_ids: set[str],
) -> tuple[CompetitionSeasonCatalogEvidence, list[SeasonInventoryRow]]:
    payload = _json_object_bytes(
        raw,
        label=f"Competition Seasons {competition.competition_id}",
    )
    digest = _sha256_bytes(raw)
    generated_at = _required_generated_at(
        payload,
        field=f"Competition Seasons {competition.competition_id} generated_at",
    )
    raw_seasons = _as_list(payload.get("seasons"), field="seasons")
    rows: list[SeasonInventoryRow] = []

    for raw_season in raw_seasons:
        season = _as_dict(raw_season, field="season")
        season_id = _required_text(season.get("id"), field="season.id")
        if season_id in seen_season_ids:
            raise ValueError(
                "provider season ID appears more than once across inventory responses"
            )
        seen_season_ids.add(season_id)
        competition_id = _required_text(
            season.get("competition_id"), field="season.competition_id"
        )
        if competition_id != competition.competition_id:
            raise ValueError(
                "Competition Seasons response contains a season for another competition"
            )
        start_date = _iso_date(season.get("start_date"), field="season.start_date")
        end_date = _iso_date(season.get("end_date"), field="season.end_date")
        if date.fromisoformat(end_date) < date.fromisoformat(start_date):
            raise ValueError("provider season end_date precedes start_date")
        disabled_raw = season.get("disabled", False)
        if not isinstance(disabled_raw, bool):
            raise ValueError("season.disabled must be boolean when present")

        if disabled_raw:
            status: SeasonStatus = "DISABLED_PROVIDER_SEASON"
        elif date.fromisoformat(end_date) < snapshot_date:
            status = "HISTORICAL_CANDIDATE"
        else:
            status = "NOT_YET_HISTORICAL"

        rows.append(
            SeasonInventoryRow(
                tour=tour,
                category_id=competition.category_id,
                competition_id=competition.competition_id,
                competition_name=competition.competition_name,
                season_id=season_id,
                season_name=_required_text(season.get("name"), field="season.name"),
                start_date=start_date,
                end_date=end_date,
                year=_optional_text(season.get("year")),
                disabled=disabled_raw,
                seasons_payload_sha256=digest,
                status=status,
            )
        )

    rows.sort(key=lambda row: (row.start_date, row.season_id))
    evidence = CompetitionSeasonCatalogEvidence(
        tour=tour,
        competition_id=competition.competition_id,
        payload_sha256=digest,
        provider_generated_at=generated_at,
        returned_season_count=len(rows),
    )
    return evidence, rows


def build_sportradar_season_inventory(
    *,
    atp_competitions_path: Path,
    wta_competitions_path: Path,
    season_response_paths: dict[str, Path],
    snapshot_at: datetime,
) -> SportradarSeasonInventory:
    if snapshot_at.tzinfo is None or snapshot_at.utcoffset() is None:
        raise ValueError("snapshot_at must be timezone-aware")
    asserted_snapshot = snapshot_at.astimezone(UTC)
    snapshot_date = asserted_snapshot.date()

    atp_sha, atp_generated_at, atp_rows, atp_required = _parse_category_catalog(
        atp_competitions_path.read_bytes(), tour="ATP"
    )
    wta_sha, wta_generated_at, wta_rows, wta_required = _parse_category_catalog(
        wta_competitions_path.read_bytes(), tour="WTA"
    )
    competition_rows = [*atp_rows, *wta_rows]
    competition_ids = [row.competition_id for row in competition_rows]
    if len(competition_ids) != len(set(competition_ids)):
        raise ValueError("competition ID appears in both ATP and WTA category catalogs")

    required = atp_required | wta_required
    supplied = set(season_response_paths)
    missing = sorted(required - supplied)
    extra = sorted(supplied - required)
    if missing or extra:
        raise ValueError(
            f"Competition Seasons evidence set mismatch; missing={missing}, extra={extra}"
        )

    by_competition = {row.competition_id: row for row in competition_rows}
    season_catalogs: list[CompetitionSeasonCatalogEvidence] = []
    season_rows: list[SeasonInventoryRow] = []
    seen_season_ids: set[str] = set()
    for competition_id in sorted(required):
        competition = by_competition[competition_id]
        evidence, rows = _parse_season_catalog(
            season_response_paths[competition_id].read_bytes(),
            tour=competition.tour,
            competition=competition,
            snapshot_date=snapshot_date,
            seen_season_ids=seen_season_ids,
        )
        season_catalogs.append(evidence)
        season_rows.extend(rows)

    provider_times = [
        _aware_time(atp_generated_at, field="ATP competitions generated_at"),
        _aware_time(wta_generated_at, field="WTA competitions generated_at"),
        *(
            _aware_time(
                row.provider_generated_at,
                field=f"Competition Seasons {row.competition_id} generated_at",
            )
            for row in season_catalogs
        ),
    ]
    provider_dates = {value.date() for value in provider_times}
    if len(provider_dates) != 1:
        raise ValueError("retained provider inventory catalogs cross UTC dates; recapture one UTC day")
    provider_snapshot = max(provider_times)
    provider_snapshot_date = provider_snapshot.date()
    if asserted_snapshot.date() != provider_snapshot_date:
        raise ValueError("snapshot_at UTC date must match retained provider generated_at date")

    competition_rows.sort(key=lambda row: (row.tour, row.competition_id))
    season_catalogs.sort(key=lambda row: (row.tour, row.competition_id))
    season_rows.sort(
        key=lambda row: (row.tour, row.competition_id, row.start_date, row.season_id)
    )
    historical = sum(row.status == "HISTORICAL_CANDIDATE" for row in season_rows)
    future = sum(row.status == "NOT_YET_HISTORICAL" for row in season_rows)
    disabled = sum(row.status == "DISABLED_PROVIDER_SEASON" for row in season_rows)

    return SportradarSeasonInventory(
        snapshot_at=provider_snapshot.isoformat(),
        atp_competitions_sha256=atp_sha,
        wta_competitions_sha256=wta_sha,
        atp_competitions_generated_at=atp_generated_at,
        wta_competitions_generated_at=wta_generated_at,
        competition_rows=tuple(competition_rows),
        season_catalogs=tuple(season_catalogs),
        season_rows=tuple(season_rows),
        competition_count=len(competition_rows),
        required_singles_competition_count=len(required),
        non_singles_competition_count=len(competition_rows) - len(required),
        season_count=len(season_rows),
        historical_candidate_count=historical,
        not_yet_historical_count=future,
        disabled_season_count=disabled,
    )


def _parse_time(value: str) -> datetime:
    return _aware_time(value, field="snapshot_at")


def _parse_binding(value: str) -> tuple[str, Path]:
    competition_id, separator, raw_path = value.partition("::")
    if not separator or not competition_id.strip() or not raw_path.strip():
        raise argparse.ArgumentTypeError("--seasons must be COMPETITION_ID::RAW_JSON")
    return competition_id.strip(), Path(raw_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the retained Sportradar ATP/WTA competition-season inventory"
    )
    parser.add_argument("--atp-competitions", required=True, type=Path)
    parser.add_argument("--wta-competitions", required=True, type=Path)
    parser.add_argument(
        "--seasons",
        action="append",
        required=True,
        type=_parse_binding,
        help="retained Competition Seasons binding COMPETITION_ID::RAW_JSON; repeat",
    )
    parser.add_argument(
        "--snapshot-at",
        required=True,
        help="operator capture-time assertion; UTC date must match provider generated_at evidence",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    bindings: dict[str, Path] = {}
    for competition_id, path in args.seasons:
        if competition_id in bindings:
            raise ValueError(f"duplicate --seasons binding for {competition_id}")
        bindings[competition_id] = path
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=args.atp_competitions,
        wta_competitions_path=args.wta_competitions,
        season_response_paths=bindings,
        snapshot_at=_parse_time(args.snapshot_at),
    )
    rendered = json.dumps(
        inventory.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
