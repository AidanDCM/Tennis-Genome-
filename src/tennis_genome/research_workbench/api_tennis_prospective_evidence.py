from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import field_validator

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, PreMatchState
from tennis_genome.ratings.dynamic_serve_return import walk_forward_dynamic_serve_return
from tennis_genome.simulation.tennis import point_sim_match_probability

from .api_tennis_dynamic_shadow import (
    api_tennis_enrichment_to_historical_match,
)
from .api_tennis_filtered_replay import build_filtered_daily_enrichment_batches
from .api_tennis_prospective_shadow import (
    ApiTennisChampionCrosswalk,
    ApiTennisProspectiveStateEvidence,
)
from .contracts import WorkbenchRecord

_BASE_URL = "https://api.api-tennis.com/tennis/"
_WTA_EVENT_TYPE_KEY = "266"
_EMPTY_PROVIDER_PAYLOAD = b'{"success":1,"result":[]}'
_FORBIDDEN_KEY_TOKENS = ("odd", "bookmaker", "sportsbook", "market")
_PREMATCH_STATUSES = {"not started", "not_started", "scheduled"}
NAME_MAPPING_VERSION = "exact-normalized-name-prematch-v1"

ProviderGet = Callable[[str], bytes]


class ApiTennisProspectiveEvidenceBuild(WorkbenchRecord):
    schema_version: str = "tennis-genome-api-tennis-prospective-evidence-build-v1"
    champion_prediction_artifact_id: int
    history_artifact_id: int
    provider_request_count: int = 1
    query_date_start: date
    query_date_stop: date
    base_history_raw_sha256: str
    extension_raw_sha256: str
    state_source_sha256: str
    target_fixture_sha256: str
    target_event_key: int
    target_event_date: date
    target_player_a_key: int
    target_player_b_key: int
    orientation: str
    evidence_sha256: str
    crosswalk_sha256: str
    captured_at: datetime

    @field_validator(
        "base_history_raw_sha256",
        "extension_raw_sha256",
        "state_source_sha256",
        "target_fixture_sha256",
        "evidence_sha256",
        "crosswalk_sha256",
    )
    @classmethod
    def _hashes(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hashes must be lowercase SHA-256")
        return value

    @field_validator("champion_prediction_artifact_id", "history_artifact_id")
    @classmethod
    def _artifact_ids(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("artifact IDs must be positive")
        return value

    @field_validator("provider_request_count")
    @classmethod
    def _request_count(cls, value: int) -> int:
        if value != 1:
            raise ValueError("prospective evidence capture must spend exactly one request")
        return value



class ApiTennisSlateExtensionCapture(WorkbenchRecord):
    schema_version: str = "tennis-genome-api-tennis-slate-extension-capture-v1"
    history_artifact_id: int
    provider_request_count: int = 1
    query_date_start: date
    query_date_stop: date
    base_history_raw_sha256: str
    extension_raw_sha256: str
    captured_at: datetime
    target_event_ids: tuple[str, ...]
    prestart_target_event_ids: tuple[str, ...]
    late_target_event_ids: tuple[str, ...]
    market_blind: bool = True

    @field_validator("history_artifact_id")
    @classmethod
    def _history_artifact_id(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("history artifact ID must be positive")
        return value

    @field_validator("provider_request_count")
    @classmethod
    def _slate_request_count(cls, value: int) -> int:
        if value != 1:
            raise ValueError("slate extension capture must spend exactly one request")
        return value

    @field_validator("base_history_raw_sha256", "extension_raw_sha256")
    @classmethod
    def _slate_hashes(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hashes must be lowercase SHA-256")
        return value

    @field_validator("target_event_ids", "prestart_target_event_ids", "late_target_event_ids")
    @classmethod
    def _event_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("slate target event IDs must be unique")
        if any(not item.startswith("sr:sport_event:") for item in value):
            raise ValueError("slate target event IDs must be Sportradar sport-event IDs")
        return value


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _default_provider_get(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310
            if int(response.status) != 200:
                raise RuntimeError(f"API-Tennis returned HTTP {response.status}")
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"API-Tennis returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("API-Tennis HTTPS transport failed") from exc


def _payload_rows(raw: bytes) -> list[dict[str, object]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("API-Tennis payload must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") not in {1, "1"}:
        raise ValueError("API-Tennis response did not report success")
    rows = payload.get("result")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("API-Tennis result must be an array of objects")
    return [dict(row) for row in rows]


def _ensure_market_blind(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if any(token in lowered for token in _FORBIDDEN_KEY_TOKENS):
                raise ValueError("API-Tennis target payload contains market-semantic fields")
            _ensure_market_blind(item)
    elif isinstance(value, list):
        for item in value:
            _ensure_market_blind(item)


def _normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return "".join(ch for ch in ascii_text.casefold() if ch.isalnum())


def _require_int(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _champion_target(
    *,
    prediction_dossier: dict[str, object],
    target_resolution: dict[str, object],
) -> tuple[str, str, str, str, datetime]:
    calculation = prediction_dossier.get("calculation")
    target = prediction_dossier.get("target")
    if not isinstance(calculation, dict) or not isinstance(target, dict):
        raise ValueError("Champion dossier lacks calculation/target identity")

    prediction = calculation.get("prediction")
    player_a = target.get("player_a")
    player_b = target.get("player_b")
    if (
        not isinstance(prediction, dict)
        or not isinstance(player_a, dict)
        or not isinstance(player_b, dict)
    ):
        raise ValueError("Champion dossier target identity is incomplete")
    if str(prediction.get("tour")) != "WTA":
        raise ValueError("prospective API-Tennis evidence is WTA-only")

    match_id = str(prediction.get("match_id", ""))
    provider_event_id = str(target_resolution.get("event_id", ""))
    if not match_id or match_id != provider_event_id:
        raise ValueError("Champion prediction and target resolution event IDs disagree")

    player_a_id = str(calculation.get("player_a_id", ""))
    player_b_id = str(calculation.get("player_b_id", ""))
    player_a_name = str(player_a.get("name", ""))
    player_b_name = str(player_b.get("name", ""))
    if not all((player_a_id, player_b_id, player_a_name, player_b_name)):
        raise ValueError("Champion player identity is incomplete")
    if str(player_a.get("id", "")) != player_a_id:
        raise ValueError("Champion target player A ID mismatch")
    if str(player_b.get("id", "")) != player_b_id:
        raise ValueError("Champion target player B ID mismatch")

    scheduled_start = datetime.fromisoformat(str(target_resolution.get("scheduled_start", "")))
    if scheduled_start.tzinfo is None or scheduled_start.utcoffset() is None:
        raise ValueError("Champion scheduled_start must be timezone-aware")
    return player_a_id, player_b_id, player_a_name, player_b_name, scheduled_start


def _base_history_end(raw_wta: bytes) -> date:
    rows = _payload_rows(raw_wta)
    if not rows:
        raise ValueError("retained WTA history payload is empty")
    dates: list[date] = []
    for row in rows:
        if str(row.get("event_type_type", "")).casefold() != "wta singles":
            raise ValueError("retained WTA history contains a non-WTA-singles fixture")
        event_date = date.fromisoformat(str(row.get("event_date", "")))
        dates.append(event_date)
    return max(dates)


def fetch_api_tennis_wta_extension(
    *,
    date_start: date,
    date_stop: date,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
) -> bytes:
    """Spend exactly one WTA fixtures request covering missing history through target date."""

    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    span_days = (date_stop - date_start).days + 1
    if span_days < 1 or span_days > 31:
        raise ValueError("API-Tennis prospective range must span between one and 31 days")
    query = urlencode(
        {
            "method": "get_fixtures",
            "APIkey": api_key,
            "date_start": date_start.isoformat(),
            "date_stop": date_stop.isoformat(),
            "event_type_key": _WTA_EVENT_TYPE_KEY,
            "timezone": "UTC",
        }
    )
    raw = provider_get(f"{_BASE_URL}?{query}")
    rows = _payload_rows(raw)
    for row in rows:
        _ensure_market_blind(row)
        if str(row.get("event_type_type", "")).casefold() != "wta singles":
            raise ValueError("provider returned non-WTA-singles fixture")
        key = row.get("event_type_key")
        if key is not None and str(key) != _WTA_EVENT_TYPE_KEY:
            raise ValueError("provider returned wrong WTA event_type_key")
        event_date = date.fromisoformat(str(row.get("event_date", "")))
        if event_date < date_start or event_date > date_stop:
            raise ValueError("provider returned fixture outside requested range")
    return raw



def capture_api_tennis_slate_extension(
    *,
    history_raw_wta: bytes,
    history_artifact_id: int,
    target_resolutions: Sequence[dict[str, object]],
    api_key: str,
    captured_at: datetime,
    provider_get: ProviderGet = _default_provider_get,
) -> tuple[bytes, ApiTennisSlateExtensionCapture]:
    """Spend one bounded WTA request for the complete prospective slate."""

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    if history_artifact_id <= 0:
        raise ValueError("history_artifact_id must be positive")
    if not target_resolutions:
        raise ValueError("API-Tennis slate capture requires at least one target")

    targets: list[tuple[datetime, str]] = []
    seen: set[str] = set()
    for resolution in target_resolutions:
        event_id = str(resolution.get("event_id", "")).strip()
        if not event_id.startswith("sr:sport_event:"):
            raise ValueError("slate target event_id must be a Sportradar sport-event ID")
        if event_id in seen:
            raise ValueError("slate target event IDs must be unique")
        seen.add(event_id)
        try:
            scheduled = datetime.fromisoformat(str(resolution.get("scheduled_start", "")))
        except ValueError as exc:
            raise ValueError("slate scheduled_start must be ISO-8601") from exc
        if scheduled.tzinfo is None or scheduled.utcoffset() is None:
            raise ValueError("slate scheduled_start must be timezone-aware")
        targets.append((scheduled.astimezone(UTC), event_id))

    base_history_end = _base_history_end(history_raw_wta)
    query_start = base_history_end + timedelta(days=1)
    query_stop = max(scheduled.date() for scheduled, _ in targets)
    extension_raw = fetch_api_tennis_wta_extension(
        date_start=query_start,
        date_stop=query_stop,
        api_key=api_key,
        provider_get=provider_get,
    )

    ordered = sorted(targets, key=lambda item: (item[0], item[1]))
    prestart = tuple(
        event_id for scheduled, event_id in ordered if captured_at < scheduled
    )
    late = tuple(
        event_id for scheduled, event_id in ordered if captured_at >= scheduled
    )
    if not prestart:
        raise ValueError("API-Tennis slate capture has no remaining pre-start targets")

    capture = ApiTennisSlateExtensionCapture(
        history_artifact_id=history_artifact_id,
        query_date_start=query_start,
        query_date_stop=query_stop,
        base_history_raw_sha256=hashlib.sha256(history_raw_wta).hexdigest(),
        extension_raw_sha256=hashlib.sha256(extension_raw).hexdigest(),
        captured_at=captured_at,
        target_event_ids=tuple(event_id for _, event_id in ordered),
        prestart_target_event_ids=prestart,
        late_target_event_ids=late,
    )
    return extension_raw, capture


def _select_target_fixture(
    *,
    extension_raw_wta: bytes,
    target_date: date,
    champion_player_a_name: str,
    champion_player_b_name: str,
) -> tuple[dict[str, object], str]:
    champion_a = _normalize_name(champion_player_a_name)
    champion_b = _normalize_name(champion_player_b_name)
    if not champion_a or not champion_b or champion_a == champion_b:
        raise ValueError("Champion names cannot form a unique normalized pair")

    candidates: list[tuple[dict[str, object], str]] = []
    for row in _payload_rows(extension_raw_wta):
        if date.fromisoformat(str(row.get("event_date", ""))) != target_date:
            continue
        api_a_name = str(row.get("event_first_player", ""))
        api_b_name = str(row.get("event_second_player", ""))
        api_a = _normalize_name(api_a_name)
        api_b = _normalize_name(api_b_name)
        if api_a == champion_a and api_b == champion_b:
            orientation = "DIRECT"
        elif api_a == champion_b and api_b == champion_a:
            orientation = "REVERSED"
        else:
            continue

        status = str(row.get("event_status", "")).strip().casefold()
        if status not in _PREMATCH_STATUSES:
            raise ValueError("matched API-Tennis target is not pre-match")
        winner = row.get("event_winner")
        if winner not in {None, ""}:
            raise ValueError("matched API-Tennis target unexpectedly contains a winner")
        for field in ("statistics", "pointbypoint", "scores"):
            value = row.get(field)
            if value is not None and value != "" and value != []:
                raise ValueError(f"matched API-Tennis target unexpectedly contains {field}")
        candidates.append((row, orientation))

    if len(candidates) != 1:
        raise ValueError(
            "expected exactly one pre-match API-Tennis fixture matching Champion names, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _target_snapshot_from_history(
    *,
    history_matches: list[HistoricalMatch],
    target_row: dict[str, object],
    sentinel_a_won: bool = False,
):
    target_date = date.fromisoformat(str(target_row.get("event_date", "")))
    if any(match.pre_match.event_date >= target_date for match in history_matches):
        raise ValueError("target state history must contain only strictly prior dates")

    event_key = _require_int(target_row.get("event_key"), field="event_key")
    player_a_key = _require_int(target_row.get("first_player_key"), field="first_player_key")
    player_b_key = _require_int(target_row.get("second_player_key"), field="second_player_key")
    if player_a_key == player_b_key:
        raise ValueError("API-Tennis target player keys must differ")

    match_id = f"api-tennis:{event_key}"
    tournament_key = target_row.get("tournament_key")
    tournament_id = (
        f"api-tennis-tournament:{tournament_key}"
        if isinstance(tournament_key, int) and not isinstance(tournament_key, bool)
        else "api-tennis-tournament:unknown"
    )
    target_state = PreMatchState(
        match_id=match_id,
        tour="WTA",
        event_date=target_date,
        source_order=len(history_matches),
        tournament_id=tournament_id,
        tournament_name=str(target_row.get("tournament_name", "")),
        tournament_level=None,
        surface="Unknown",
        round=str(target_row.get("tournament_round", "")) or None,
        best_of=3,
        player_a_id=f"api-tennis-player:{player_a_key}",
        player_b_id=f"api-tennis-player:{player_b_key}",
        player_a_name=str(target_row.get("event_first_player", "")),
        player_b_name=str(target_row.get("event_second_player", "")),
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
    )
    sentinel = HistoricalMatch(
        pre_match=target_state,
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=sentinel_a_won,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=None,
    )
    snapshots = walk_forward_dynamic_serve_return(
        [*history_matches, sentinel],
        exclude_retirements=True,
    )
    matches = [snapshot for snapshot in snapshots if snapshot.match_id == match_id]
    if len(matches) != 1:
        raise ValueError("dynamic target snapshot was not uniquely produced")
    return matches[0]


def build_api_tennis_prospective_evidence(
    *,
    history_raw_wta: bytes,
    extension_raw_wta: bytes,
    champion_prediction_artifact_id: int,
    history_artifact_id: int,
    prediction_dossier: dict[str, object],
    target_resolution: dict[str, object],
    captured_at: datetime,
) -> tuple[
    ApiTennisProspectiveStateEvidence,
    ApiTennisChampionCrosswalk,
    ApiTennisProspectiveEvidenceBuild,
]:
    """Create target-outcome-free state and an explicit Champion identity crosswalk."""

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("captured_at must be timezone-aware")
    (
        champion_player_a_id,
        champion_player_b_id,
        champion_player_a_name,
        champion_player_b_name,
        scheduled_start,
    ) = _champion_target(
        prediction_dossier=prediction_dossier,
        target_resolution=target_resolution,
    )
    if captured_at >= scheduled_start:
        raise ValueError("API-Tennis prospective evidence must be captured before scheduled start")

    target_date = scheduled_start.astimezone(UTC).date()
    base_history_end = _base_history_end(history_raw_wta)
    if base_history_end >= target_date:
        raise ValueError("retained history must end before the prospective target date")
    query_start = base_history_end + timedelta(days=1)
    if (target_date - query_start).days + 1 > 31:
        raise ValueError("retained history is too stale for one bounded prospective request")

    target_row, orientation = _select_target_fixture(
        extension_raw_wta=extension_raw_wta,
        target_date=target_date,
        champion_player_a_name=champion_player_a_name,
        champion_player_b_name=champion_player_b_name,
    )
    _ensure_market_blind(target_row)

    base_rows = _payload_rows(history_raw_wta)
    extension_rows = _payload_rows(extension_raw_wta)
    history_rows = [
        row
        for row in [*base_rows, *extension_rows]
        if date.fromisoformat(str(row.get("event_date", ""))) < target_date
    ]
    combined_history_raw = _canonical_json_bytes(
        {"success": 1, "result": history_rows}
    )
    batches = build_filtered_daily_enrichment_batches(
        raw_atp=_EMPTY_PROVIDER_PAYLOAD,
        raw_wta=combined_history_raw,
    )
    history_records = [
        record
        for batch in batches
        for record in batch.admitted_records
        if record.tour == "WTA"
    ]
    historical_matches = [
        api_tennis_enrichment_to_historical_match(record, source_order=index)
        for index, record in enumerate(
            sorted(history_records, key=lambda item: (item.event_date, item.event_key))
        )
    ]

    snapshot = _target_snapshot_from_history(
        history_matches=historical_matches,
        target_row=target_row,
    )
    event_key = _require_int(target_row.get("event_key"), field="event_key")
    player_a_key = _require_int(target_row.get("first_player_key"), field="first_player_key")
    player_b_key = _require_int(target_row.get("second_player_key"), field="second_player_key")
    player_a_name = str(target_row.get("event_first_player", ""))
    player_b_name = str(target_row.get("event_second_player", ""))
    target_fixture_sha = _canonical_sha256(target_row)
    base_sha = hashlib.sha256(history_raw_wta).hexdigest()
    extension_sha = hashlib.sha256(extension_raw_wta).hexdigest()
    state_source_sha = _canonical_sha256(
        {
            "history_artifact_id": history_artifact_id,
            "base_history_raw_sha256": base_sha,
            "extension_raw_sha256": extension_sha,
            "history_through_date": (target_date - timedelta(days=1)).isoformat(),
            "admitted_history_semantic_sha256": [
                record.semantic_sha256
                for record in sorted(
                    history_records,
                    key=lambda item: (item.event_date, item.event_key),
                )
            ],
        }
    )

    evidence = ApiTennisProspectiveStateEvidence(
        source_artifact_id=history_artifact_id,
        state_source_sha256=state_source_sha,
        target_fixture_sha256=target_fixture_sha,
        captured_at=captured_at,
        history_through_date=target_date - timedelta(days=1),
        event_key=event_key,
        event_date=target_date,
        tour="WTA",
        player_a_key=player_a_key,
        player_b_key=player_b_key,
        player_a_name=player_a_name,
        player_b_name=player_b_name,
        probability_a_serve_point=snapshot.probability_a_serve_point,
        probability_b_serve_point=snapshot.probability_b_serve_point,
        probability_a_match=point_sim_match_probability(
            snapshot.probability_a_serve_point,
            snapshot.probability_b_serve_point,
            best_of=3,
        ),
        prior_serve_points_a=snapshot.prior_serve_points_a,
        prior_serve_points_b=snapshot.prior_serve_points_b,
        prior_return_points_a=snapshot.prior_return_points_a,
        prior_return_points_b=snapshot.prior_return_points_b,
    )

    mapping_evidence_sha = _canonical_sha256(
        {
            "mapping_version": NAME_MAPPING_VERSION,
            "champion_event_id": target_resolution["event_id"],
            "champion_player_a_id": champion_player_a_id,
            "champion_player_b_id": champion_player_b_id,
            "champion_player_a_name": champion_player_a_name,
            "champion_player_b_name": champion_player_b_name,
            "api_tennis_event_key": event_key,
            "api_tennis_player_a_key": player_a_key,
            "api_tennis_player_b_key": player_b_key,
            "api_tennis_player_a_name": player_a_name,
            "api_tennis_player_b_name": player_b_name,
            "orientation": orientation,
            "target_fixture_sha256": target_fixture_sha,
        }
    )
    crosswalk = ApiTennisChampionCrosswalk(
        champion_match_id=str(target_resolution["event_id"]),
        champion_provider_event_id=str(target_resolution["event_id"]),
        champion_player_a_id=champion_player_a_id,
        champion_player_b_id=champion_player_b_id,
        api_tennis_event_key=event_key,
        api_tennis_player_a_key=player_a_key,
        api_tennis_player_b_key=player_b_key,
        orientation=orientation,
        mapping_basis="EXACT_NORMALIZED_NAME_PREMATCH",
        mapping_evidence_sha256=mapping_evidence_sha,
        created_at=captured_at,
    )
    build = ApiTennisProspectiveEvidenceBuild(
        champion_prediction_artifact_id=champion_prediction_artifact_id,
        history_artifact_id=history_artifact_id,
        query_date_start=query_start,
        query_date_stop=target_date,
        base_history_raw_sha256=base_sha,
        extension_raw_sha256=extension_sha,
        state_source_sha256=state_source_sha,
        target_fixture_sha256=target_fixture_sha,
        target_event_key=event_key,
        target_event_date=target_date,
        target_player_a_key=player_a_key,
        target_player_b_key=player_b_key,
        orientation=orientation,
        evidence_sha256=evidence.semantic_sha256,
        crosswalk_sha256=crosswalk.semantic_sha256,
        captured_at=captured_at,
    )
    return evidence, crosswalk, build


def capture_api_tennis_prospective_evidence(
    *,
    history_raw_wta: bytes,
    champion_prediction_artifact_id: int,
    history_artifact_id: int,
    prediction_dossier: dict[str, object],
    target_resolution: dict[str, object],
    api_key: str,
    captured_at: datetime,
    provider_get: ProviderGet = _default_provider_get,
) -> tuple[
    bytes,
    ApiTennisProspectiveStateEvidence,
    ApiTennisChampionCrosswalk,
    ApiTennisProspectiveEvidenceBuild,
]:
    """Fetch one bounded WTA extension and build immutable prospective evidence."""

    _, _, _, _, scheduled_start = _champion_target(
        prediction_dossier=prediction_dossier,
        target_resolution=target_resolution,
    )
    target_date = scheduled_start.astimezone(UTC).date()
    base_history_end = _base_history_end(history_raw_wta)
    query_start = base_history_end + timedelta(days=1)
    extension_raw = fetch_api_tennis_wta_extension(
        date_start=query_start,
        date_stop=target_date,
        api_key=api_key,
        provider_get=provider_get,
    )
    evidence, crosswalk, build = build_api_tennis_prospective_evidence(
        history_raw_wta=history_raw_wta,
        extension_raw_wta=extension_raw,
        champion_prediction_artifact_id=champion_prediction_artifact_id,
        history_artifact_id=history_artifact_id,
        prediction_dossier=prediction_dossier,
        target_resolution=target_resolution,
        captured_at=captured_at,
    )
    return extension_raw, evidence, crosswalk, build
