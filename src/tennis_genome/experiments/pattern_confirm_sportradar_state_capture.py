from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time

from tennis_genome.experiments.pattern_confirm_sportradar_client import (
    fetch_competitions_catalog,
    fetch_season_summary_pages,
    fetch_seasons_catalog,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_mapping,
    verify_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_state import (
    build_state_bundle,
    state_bundle_as_dict,
    verify_state_bundle,
)

_VERSION = "pattern-confirm-season-state-capture-v1"
_SOURCE_CONTRACT = "SPORTRADAR_TENNIS_V3_STATE_V1"
_ATP_CATEGORY_ID = "sr:category:3"
_STATE_START = date(2026, 1, 1)
_PAGE_SIZE = 200
_ALLOWED_LEVELS = {
    "grand_slam",
    "atp_1000",
    "atp_500",
    "atp_250",
    "atp_world_tour_finals",
    "atp_next_generation",
}


@dataclass(frozen=True)
class SelectedSeason:
    season_id: str
    competition_id: str
    start_date: str


@dataclass(frozen=True)
class SeasonPageAudit:
    season_id: str
    start: int
    summary_count: int
    payload_sha256: str


@dataclass(frozen=True)
class CutoffExclusion:
    sport_event_id: str
    reason: str
    start_time: str | None


@dataclass(frozen=True)
class SeasonStateCapture:
    version: str
    source_contract: str
    target_state_cutoff_date: str
    crosswalk_sha256: str
    competitions_sha256: str
    seasons_sha256: str
    selected_seasons: tuple[SelectedSeason, ...]
    page_audit: tuple[SeasonPageAudit, ...]
    selected_season_count: int
    fetched_page_count: int
    fetched_summary_count: int
    cutoff_eligible_summary_count: int
    cutoff_excluded_summary_count: int
    cutoff_exclusions: tuple[CutoffExclusion, ...]
    state_bundle_sha256: str
    state_bundle: dict[str, object]
    artifact_sha256: str


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


def _self_hash(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256", None)
    return _sha256(_canonical_json(unsigned))


def _as_dict(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _as_list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    return value


def _required_text(raw: dict[str, object], name: str) -> str:
    value = str(raw.get(name, "")).strip()
    if not value:
        raise ValueError(f"{name} must be non-empty")
    return value


def _catalog_array(payload: dict[str, object], name: str) -> list[dict[str, object]]:
    return [
        _as_dict(item, field=f"{name} item")
        for item in _as_list(payload.get(name), field=name)
    ]


def select_state_seasons(
    competitions_payload: dict[str, object],
    seasons_payload: dict[str, object],
    *,
    target_cutoff_date: date,
) -> tuple[SelectedSeason, ...]:
    if target_cutoff_date < _STATE_START:
        raise ValueError("state cutoff predates 2026 source window")
    competitions: dict[str, dict[str, object]] = {}
    eligible_competitions: set[str] = set()
    for competition in _catalog_array(competitions_payload, "competitions"):
        competition_id = _required_text(competition, "id")
        if competition_id in competitions:
            raise ValueError("Competitions catalog contains duplicate competition ID")
        competitions[competition_id] = competition
        category = _as_dict(competition.get("category"), field="competition category")
        if _required_text(category, "id") != _ATP_CATEGORY_ID:
            continue
        competition_type = _required_text(competition, "type").lower()
        level = _required_text(competition, "level").lower()
        if competition_type == "singles" and level in _ALLOWED_LEVELS:
            eligible_competitions.add(competition_id)

    selected: list[SelectedSeason] = []
    seen_seasons: set[str] = set()
    for season in _catalog_array(seasons_payload, "seasons"):
        season_id = _required_text(season, "id")
        if season_id in seen_seasons:
            raise ValueError("Seasons catalog contains duplicate season ID")
        seen_seasons.add(season_id)
        competition_id = _required_text(season, "competition_id")
        if competition_id not in eligible_competitions:
            continue
        if season.get("disabled") is True:
            continue
        start_date = date.fromisoformat(_required_text(season, "start_date"))
        if _STATE_START <= start_date < target_cutoff_date:
            selected.append(
                SelectedSeason(
                    season_id=season_id,
                    competition_id=competition_id,
                    start_date=start_date.isoformat(),
                )
            )
    selected.sort(key=lambda item: (item.start_date, item.season_id))
    return tuple(selected)


def _summary_event_id(summary: dict[str, object]) -> str:
    sport_event = _as_dict(summary.get("sport_event"), field="sport_event")
    return _required_text(sport_event, "id")


def _summary_season_id(summary: dict[str, object]) -> str:
    sport_event = _as_dict(summary.get("sport_event"), field="sport_event")
    context = _as_dict(sport_event.get("sport_event_context"), field="sport_event_context")
    season = _as_dict(context.get("season"), field="sport_event_context season")
    return _required_text(season, "id")


def _summary_start(summary: dict[str, object]) -> datetime:
    sport_event = _as_dict(summary.get("sport_event"), field="sport_event")
    raw = _required_text(sport_event, "start_time")
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("sport_event.start_time must be timezone-aware")
    return parsed


def build_season_state_capture(
    *,
    competitions_payload: dict[str, object],
    seasons_payload: dict[str, object],
    season_pages: dict[str, list[tuple[int, dict[str, object]]]],
    target_cutoff_date: date,
    crosswalk_payload: dict[str, object],
) -> SeasonStateCapture:
    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    crosswalk = crosswalk_mapping(sealed_crosswalk)
    selected = select_state_seasons(
        competitions_payload,
        seasons_payload,
        target_cutoff_date=target_cutoff_date,
    )
    selected_ids = {item.season_id for item in selected}
    if set(season_pages) != selected_ids:
        raise ValueError("Season Summaries page set does not exactly match selected seasons")

    cutoff = datetime.combine(target_cutoff_date, time.min, tzinfo=UTC)
    eligible_summaries: list[dict[str, object]] = []
    exclusions: list[CutoffExclusion] = []
    page_audit: list[SeasonPageAudit] = []
    fetched_summary_count = 0
    seen_events: set[str] = set()

    for season in selected:
        pages = season_pages[season.season_id]
        if not pages:
            raise ValueError("selected season is missing Season Summaries page zero")
        expected_start = 0
        for page_index, (start, payload) in enumerate(pages):
            if start != expected_start:
                raise ValueError("Season Summaries pagination contains a gap or wrong offset")
            summaries = [
                _as_dict(item, field="Season Summaries row")
                for item in _as_list(payload.get("summaries"), field="summaries")
            ]
            count = len(summaries)
            page_audit.append(
                SeasonPageAudit(
                    season_id=season.season_id,
                    start=start,
                    summary_count=count,
                    payload_sha256=_sha256(_canonical_json(payload)),
                )
            )
            fetched_summary_count += count
            for summary in summaries:
                if _summary_season_id(summary) != season.season_id:
                    raise ValueError("Season Summaries row belongs to a different season")
                event_id = _summary_event_id(summary)
                if event_id in seen_events:
                    raise ValueError("Season Summaries capture contains duplicate sport-event ID")
                seen_events.add(event_id)
                try:
                    event_start = _summary_start(summary)
                except (TypeError, ValueError):
                    exclusions.append(
                        CutoffExclusion(
                            sport_event_id=event_id,
                            reason="CUTOFF_START_UNVERIFIED",
                            start_time=None,
                        )
                    )
                    continue
                if event_start >= cutoff:
                    exclusions.append(
                        CutoffExclusion(
                            sport_event_id=event_id,
                            reason="AFTER_TARGET_STATE_CUTOFF",
                            start_time=event_start.isoformat(),
                        )
                    )
                    continue
                eligible_summaries.append(summary)
            if count == _PAGE_SIZE:
                if page_index == len(pages) - 1:
                    raise ValueError("Season Summaries capture is missing a required next page")
                expected_start += _PAGE_SIZE
                continue
            if page_index != len(pages) - 1:
                raise ValueError("Season Summaries capture contains pages after terminal page")
            expected_start += _PAGE_SIZE

    bundle = build_state_bundle(summaries=eligible_summaries, crosswalk=crosswalk)
    bundle_payload = state_bundle_as_dict(bundle)
    exclusions.sort(key=lambda item: (item.sport_event_id, item.reason))
    page_audit.sort(key=lambda item: (item.season_id, item.start))
    unsigned: dict[str, object] = {
        "version": _VERSION,
        "source_contract": _SOURCE_CONTRACT,
        "target_state_cutoff_date": target_cutoff_date.isoformat(),
        "crosswalk_sha256": sealed_crosswalk.artifact_sha256,
        "competitions_sha256": _sha256(_canonical_json(competitions_payload)),
        "seasons_sha256": _sha256(_canonical_json(seasons_payload)),
        "selected_seasons": [asdict(item) for item in selected],
        "page_audit": [asdict(item) for item in page_audit],
        "selected_season_count": len(selected),
        "fetched_page_count": len(page_audit),
        "fetched_summary_count": fetched_summary_count,
        "cutoff_eligible_summary_count": len(eligible_summaries),
        "cutoff_excluded_summary_count": len(exclusions),
        "cutoff_exclusions": [asdict(item) for item in exclusions],
        "state_bundle_sha256": bundle.artifact_sha256,
        "state_bundle": bundle_payload,
    }
    return SeasonStateCapture(
        version=_VERSION,
        source_contract=_SOURCE_CONTRACT,
        target_state_cutoff_date=target_cutoff_date.isoformat(),
        crosswalk_sha256=sealed_crosswalk.artifact_sha256,
        competitions_sha256=unsigned["competitions_sha256"],
        seasons_sha256=unsigned["seasons_sha256"],
        selected_seasons=selected,
        page_audit=tuple(page_audit),
        selected_season_count=len(selected),
        fetched_page_count=len(page_audit),
        fetched_summary_count=fetched_summary_count,
        cutoff_eligible_summary_count=len(eligible_summaries),
        cutoff_excluded_summary_count=len(exclusions),
        cutoff_exclusions=tuple(exclusions),
        state_bundle_sha256=bundle.artifact_sha256,
        state_bundle=bundle_payload,
        artifact_sha256=_self_hash(unsigned),
    )


def state_capture_as_dict(capture: SeasonStateCapture) -> dict[str, object]:
    return asdict(capture)


def verify_state_capture(
    payload: dict[str, object], *, crosswalk_payload: dict[str, object]
) -> SeasonStateCapture:
    if str(payload.get("artifact_sha256", "")) != _self_hash(payload):
        raise ValueError("season state capture digest mismatch")
    normalized = dict(payload)
    raw_selected = payload.get("selected_seasons")
    raw_pages = payload.get("page_audit")
    raw_exclusions = payload.get("cutoff_exclusions")
    if not isinstance(raw_selected, (list, tuple)):
        raise ValueError("selected_seasons must be an array")
    if not isinstance(raw_pages, (list, tuple)):
        raise ValueError("page_audit must be an array")
    if not isinstance(raw_exclusions, (list, tuple)):
        raise ValueError("cutoff_exclusions must be an array")
    normalized["selected_seasons"] = tuple(
        SelectedSeason(**_as_dict(item, field="selected season")) for item in raw_selected
    )
    normalized["page_audit"] = tuple(
        SeasonPageAudit(**_as_dict(item, field="page audit")) for item in raw_pages
    )
    normalized["cutoff_exclusions"] = tuple(
        CutoffExclusion(**_as_dict(item, field="cutoff exclusion"))
        for item in raw_exclusions
    )
    capture = SeasonStateCapture(**normalized)
    if capture.version != _VERSION or capture.source_contract != _SOURCE_CONTRACT:
        raise ValueError("unexpected season state capture contract")
    sealed_crosswalk = verify_crosswalk(crosswalk_payload)
    if capture.crosswalk_sha256 != sealed_crosswalk.artifact_sha256:
        raise ValueError("season state capture crosswalk mismatch")
    if capture.selected_season_count != len(capture.selected_seasons):
        raise ValueError("selected season count mismatch")
    if capture.fetched_page_count != len(capture.page_audit):
        raise ValueError("fetched page count mismatch")
    if capture.cutoff_excluded_summary_count != len(capture.cutoff_exclusions):
        raise ValueError("cutoff exclusion count mismatch")
    if (
        capture.fetched_summary_count
        != capture.cutoff_eligible_summary_count + capture.cutoff_excluded_summary_count
    ):
        raise ValueError("state capture summary accounting mismatch")
    crosswalk = crosswalk_mapping(sealed_crosswalk)
    bundle = verify_state_bundle(capture.state_bundle, crosswalk=crosswalk)
    if capture.state_bundle_sha256 != bundle.artifact_sha256:
        raise ValueError("season state capture nested bundle mismatch")
    if bundle.source_count != capture.cutoff_eligible_summary_count:
        raise ValueError("season state capture eligible count does not match bundle")
    date.fromisoformat(capture.target_state_cutoff_date)
    return capture


def capture_season_state(
    *,
    target_cutoff_date: date,
    crosswalk_payload: dict[str, object],
    api_key: str,
    access_level: str,
    get_json: Callable[..., object],
) -> SeasonStateCapture:
    competitions = fetch_competitions_catalog(
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    seasons = fetch_seasons_catalog(
        api_key=api_key,
        access_level=access_level,
        get_json=get_json,
    )
    selected = select_state_seasons(
        competitions,
        seasons,
        target_cutoff_date=target_cutoff_date,
    )
    pages = {
        item.season_id: fetch_season_summary_pages(
            item.season_id,
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        )
        for item in selected
    }
    return build_season_state_capture(
        competitions_payload=competitions,
        seasons_payload=seasons,
        season_pages=pages,
        target_cutoff_date=target_cutoff_date,
        crosswalk_payload=crosswalk_payload,
    )
