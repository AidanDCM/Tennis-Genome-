from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Literal, Self
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord

CAPTURE_ID = "API-TENNIS-FILTERED-RANGE-001"
SOURCE_CONTRACT = "API_TENNIS_FILTERED_FIXTURES_V1"
_BASE_URL = "https://api.api-tennis.com/tennis/"
_EVENT_TYPES = (("ATP", "265", "Atp Singles"), ("WTA", "266", "Wta Singles"))
_FORBIDDEN_RESPONSE_KEY_TOKENS = ("odd", "bookmaker", "sportsbook")
_MODEL_INPUT_FIELDS = (
    "event_key",
    "event_date",
    "event_type_type",
    "first_player_key",
    "second_player_key",
    "statistics",
)

ProviderGet = Callable[[str], bytes]


class ApiTennisFilteredRangeAudit(WorkbenchRecord):
    capture_id: Literal["API-TENNIS-FILTERED-RANGE-001"] = CAPTURE_ID
    source_contract: Literal["API_TENNIS_FILTERED_FIXTURES_V1"] = SOURCE_CONTRACT
    date_start: str
    date_stop: str
    span_days: int
    timezone: Literal["UTC"] = "UTC"
    provider_request_count: Literal[2] = 2
    atp_event_type_key: Literal["265"] = "265"
    wta_event_type_key: Literal["266"] = "266"
    atp_fixture_count: int
    wta_fixture_count: int
    finished_fixture_count: int
    statistics_nonempty_count: int
    pointbypoint_nonempty_count: int
    raw_atp_sha256: str
    raw_wta_sha256: str
    combined_raw_sha256: str
    serve_return_input_sha256: str
    response_bytes_total: int
    event_key_count: int
    event_dates: tuple[str, ...]
    historical_actual_start_admissible: Literal[False] = False

    @field_validator(
        "raw_atp_sha256",
        "raw_wta_sha256",
        "combined_raw_sha256",
        "serve_return_input_sha256",
    )
    @classmethod
    def _sha(cls, value: str) -> str:
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
            raise ValueError("hashes must be lowercase SHA-256")
        return value

    @model_validator(mode="after")
    def _validate(self) -> Self:
        start = date.fromisoformat(self.date_start)
        stop = date.fromisoformat(self.date_stop)
        expected_span = (stop - start).days + 1
        if expected_span < 1:
            raise ValueError("date_stop must not precede date_start")
        if expected_span > 31:
            raise ValueError("filtered capture may span at most 31 calendar days")
        if self.span_days != expected_span:
            raise ValueError("span_days does not match date range")
        counts = (
            self.atp_fixture_count,
            self.wta_fixture_count,
            self.finished_fixture_count,
            self.statistics_nonempty_count,
            self.pointbypoint_nonempty_count,
            self.response_bytes_total,
            self.event_key_count,
        )
        if any(value < 0 for value in counts):
            raise ValueError("counts must be non-negative")
        if self.event_key_count != self.atp_fixture_count + self.wta_fixture_count:
            raise ValueError("event_key_count must equal total fixture count")
        for value in self.event_dates:
            parsed = date.fromisoformat(value)
            if parsed < start or parsed > stop:
                raise ValueError("event date falls outside requested range")
        return self


def _default_provider_get(url: str) -> bytes:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310 - frozen HTTPS host
            if int(response.status) != 200:
                raise RuntimeError(f"API-Tennis returned HTTP {response.status}")
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"API-Tennis returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("API-Tennis HTTPS transport failed") from exc


def _canonical_sha(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _parse_filtered_payload(
    raw: bytes,
    *,
    expected_event_type_key: str,
    expected_event_type_name: str,
    date_start: str,
    date_stop: str,
) -> list[dict[str, object]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("API-Tennis response must be UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") not in {1, "1"}:
        raise ValueError("API-Tennis response did not report success")
    rows = payload.get("result")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("API-Tennis result must be an array of objects")

    start = date.fromisoformat(date_start)
    stop = date.fromisoformat(date_stop)
    output: list[dict[str, object]] = []
    for raw_row in rows:
        row = dict(raw_row)
        for key in row:
            lowered = str(key).lower()
            if any(token in lowered for token in _FORBIDDEN_RESPONSE_KEY_TOKENS):
                raise ValueError("filtered fixture response contains market fields")
        if str(row.get("event_type_type", "")).strip().lower() != expected_event_type_name.lower():
            raise ValueError("provider returned wrong event type for filtered request")
        key_value = row.get("event_type_key")
        if key_value is not None and str(key_value) != expected_event_type_key:
            raise ValueError("provider returned wrong event_type_key for filtered request")
        event_date = date.fromisoformat(str(row.get("event_date", "")))
        if event_date < start or event_date > stop:
            raise ValueError("provider returned fixture outside requested range")
        output.append(row)
    return output


def serve_return_fixture_input_sha256(row: dict[str, object]) -> str:
    """Hash only fields consumed by the dynamic serve/return research state.

    Scores, scheduled clock time, point-by-point formatting, and other source
    presentation fields are deliberately excluded, so harmless provider display
    revisions do not masquerade as model-input changes.
    """

    projected = {field: row.get(field) for field in _MODEL_INPUT_FIELDS}
    return _canonical_sha(projected)


def capture_api_tennis_filtered_range(
    *,
    date_start: str,
    date_stop: str,
    api_key: str,
    output_dir: Path,
    provider_get: ProviderGet = _default_provider_get,
) -> ApiTennisFilteredRangeAudit:
    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    start = date.fromisoformat(date_start)
    stop = date.fromisoformat(date_stop)
    span_days = (stop - start).days + 1
    if span_days < 1 or span_days > 31:
        raise ValueError("filtered capture requires between one and 31 calendar days")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("filtered capture output directory must begin empty")

    retained: dict[str, bytes] = {}
    rows_by_tour: dict[str, list[dict[str, object]]] = {}
    for tour, event_type_key, event_type_name in _EVENT_TYPES:
        query = urlencode(
            {
                "method": "get_fixtures",
                "APIkey": api_key,
                "date_start": date_start,
                "date_stop": date_stop,
                "event_type_key": event_type_key,
                "timezone": "UTC",
            }
        )
        raw = provider_get(f"{_BASE_URL}?{query}")
        rows = _parse_filtered_payload(
            raw,
            expected_event_type_key=event_type_key,
            expected_event_type_name=event_type_name,
            date_start=date_start,
            date_stop=date_stop,
        )
        retained[tour] = raw
        rows_by_tour[tour] = rows

    all_rows = rows_by_tour["ATP"] + rows_by_tour["WTA"]
    event_keys = [str(row.get("event_key", "")) for row in all_rows]
    if any(not key for key in event_keys):
        raise ValueError("filtered fixture is missing event_key")
    if len(set(event_keys)) != len(event_keys):
        raise ValueError("duplicate event_key across ATP/WTA filtered responses")

    model_hash_rows = sorted(
        (key, serve_return_fixture_input_sha256(row))
        for key, row in zip(event_keys, all_rows, strict=True)
    )
    raw_hashes = {
        "ATP": hashlib.sha256(retained["ATP"]).hexdigest(),
        "WTA": hashlib.sha256(retained["WTA"]).hexdigest(),
    }
    event_dates = tuple(
        sorted({str(row["event_date"]) for row in all_rows})
    )

    def nonempty_list(row: dict[str, object], field: str) -> bool:
        value = row.get(field)
        return isinstance(value, list) and bool(value)

    audit = ApiTennisFilteredRangeAudit(
        date_start=date_start,
        date_stop=date_stop,
        span_days=span_days,
        atp_fixture_count=len(rows_by_tour["ATP"]),
        wta_fixture_count=len(rows_by_tour["WTA"]),
        finished_fixture_count=sum(
            str(row.get("event_status", "")).strip().lower() == "finished"
            for row in all_rows
        ),
        statistics_nonempty_count=sum(nonempty_list(row, "statistics") for row in all_rows),
        pointbypoint_nonempty_count=sum(
            nonempty_list(row, "pointbypoint") for row in all_rows
        ),
        raw_atp_sha256=raw_hashes["ATP"],
        raw_wta_sha256=raw_hashes["WTA"],
        combined_raw_sha256=_canonical_sha(raw_hashes),
        serve_return_input_sha256=_canonical_sha(model_hash_rows),
        response_bytes_total=len(retained["ATP"]) + len(retained["WTA"]),
        event_key_count=len(event_keys),
        event_dates=event_dates,
    )

    (output_dir / "raw-atp-fixtures.json").write_bytes(retained["ATP"])
    (output_dir / "raw-wta-fixtures.json").write_bytes(retained["WTA"])
    (output_dir / "audit.json").write_text(
        json.dumps(audit.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "audit_semantic_sha256": audit.semantic_sha256,
                "provider_request_count": 2,
                "raw_atp_sha256": audit.raw_atp_sha256,
                "raw_wta_sha256": audit.raw_wta_sha256,
                "combined_raw_sha256": audit.combined_raw_sha256,
                "serve_return_input_sha256": audit.serve_return_input_sha256,
                "fixture_count": audit.event_key_count,
                "response_bytes_total": audit.response_bytes_total,
                "historical_actual_start_admissible": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return audit
