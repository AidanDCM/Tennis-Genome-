from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_BASE_URL = "https://api.api-tennis.com/tennis/"
_FORBIDDEN_KEY_TOKENS = ("odd", "bookmaker", "sportsbook", "market")
_ALLOWED_SINGLES_TYPES = {"atp singles", "wta singles"}

ProviderGet = Callable[[str], bytes]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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
                raise ValueError("API-Tennis inventory contains market-semantic fields")
            _ensure_market_blind(item)
    elif isinstance(value, list):
        for item in value:
            _ensure_market_blind(item)


def capture_api_tennis_daily_inventory(
    *,
    schedule_date: date,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
) -> tuple[bytes, bytes, dict[str, object]]:
    """Capture one complete provider fixture response for a single UTC calendar date."""

    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    query = urlencode(
        {
            "method": "get_fixtures",
            "APIkey": api_key,
            "date_start": schedule_date.isoformat(),
            "date_stop": schedule_date.isoformat(),
            "timezone": "UTC",
        }
    )
    raw = provider_get(f"{_BASE_URL}?{query}")
    rows = _payload_rows(raw)
    _ensure_market_blind(rows)

    event_keys: set[int] = set()
    filtered: list[dict[str, object]] = []
    type_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("event_date", "")) != schedule_date.isoformat():
            raise ValueError("API-Tennis inventory returned a fixture outside schedule_date")
        event_key = row.get("event_key")
        if isinstance(event_key, bool) or not isinstance(event_key, int) or event_key <= 0:
            raise ValueError("API-Tennis inventory event_key must be a positive integer")
        if event_key in event_keys:
            raise ValueError("API-Tennis inventory contains duplicate event_key")
        event_keys.add(event_key)

        event_type = str(row.get("event_type_type", "")).strip().casefold()
        status = str(row.get("event_status", "")).strip().casefold()
        type_counts[event_type or "unknown"] += 1
        status_counts[status or "unknown"] += 1
        if event_type in _ALLOWED_SINGLES_TYPES:
            filtered.append(row)

    filtered.sort(key=lambda row: int(row["event_key"]))
    filtered_payload = {"success": 1, "result": filtered}
    filtered_bytes = _canonical_json_bytes(filtered_payload)
    atp_count = sum(
        1
        for row in filtered
        if str(row.get("event_type_type", "")).strip().casefold() == "atp singles"
    )
    wta_count = sum(
        1
        for row in filtered
        if str(row.get("event_type_type", "")).strip().casefold() == "wta singles"
    )

    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-api-tennis-daily-inventory-v1",
        "schedule_date": schedule_date.isoformat(),
        "timezone": "UTC",
        "provider_request_count": 1,
        "query_method": "get_fixtures",
        "query_event_type_filter": None,
        "market_blind": True,
        "raw_fixture_count": len(rows),
        "atp_wta_singles_count": len(filtered),
        "atp_singles_count": atp_count,
        "wta_singles_count": wta_count,
        "event_type_counts": dict(sorted(type_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "atp_wta_singles_sha256": hashlib.sha256(filtered_bytes).hexdigest(),
    }
    return raw, filtered_bytes, manifest
