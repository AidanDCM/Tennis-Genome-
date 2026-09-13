from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from urllib.request import Request, urlopen

_HOST = "https://api.sportradar.com"
_LANGUAGE = "en"
_ALLOWED_ACCESS = {"trial", "production"}
_SEASON_PAGE_SIZE = 200
_MAX_SEASON_PAGES = 20


def _validate(access_level: str, api_key: str) -> None:
    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("Sportradar API key must be non-empty")


def _http_json(url: str, *, headers: dict[str, str]) -> object:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - frozen HTTPS host
            raw = response.read()
    except Exception as exc:
        raise RuntimeError(f"Sportradar request failed: {url.split('?', 1)[0]}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Sportradar returned non-JSON response") from exc


def _get(
    path: str,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object],
) -> object:
    _validate(access_level, api_key)
    url = f"{_HOST}/tennis/{access_level}/v3/{_LANGUAGE}/{path.lstrip('/')}"
    return get_json(url, headers={"x-api-key": api_key})


def _object_payload(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def _object_array(payload: dict[str, object], name: str) -> list[dict[str, object]]:
    raw = payload.get(name)
    if not isinstance(raw, list):
        raise ValueError(f"Sportradar {name} must be an array")
    if any(not isinstance(item, dict) for item in raw):
        raise ValueError(f"Sportradar {name} contains a non-object row")
    return list(raw)


def fetch_competitions_catalog(
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> dict[str, object]:
    payload = _object_payload(
        _get(
            "competitions.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Competitions response",
    )
    _object_array(payload, "competitions")
    return payload


def fetch_seasons_catalog(
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> dict[str, object]:
    payload = _object_payload(
        _get(
            "seasons.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Seasons response",
    )
    _object_array(payload, "seasons")
    return payload


def fetch_season_summary_pages(
    season_id: str,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> list[tuple[int, dict[str, object]]]:
    season_id = str(season_id).strip()
    if not season_id:
        raise ValueError("season_id must be non-empty")
    pages: list[tuple[int, dict[str, object]]] = []
    start = 0
    for _ in range(_MAX_SEASON_PAGES):
        payload = _object_payload(
            _get(
                f"seasons/{season_id}/summaries.json?start={start}&limit={_SEASON_PAGE_SIZE}",
                api_key=api_key,
                access_level=access_level,
                get_json=get_json,
            ),
            field="Sportradar Season Summaries response",
        )
        summaries = _object_array(payload, "summaries")
        pages.append((start, payload))
        if len(summaries) < _SEASON_PAGE_SIZE:
            return pages
        start += _SEASON_PAGE_SIZE
    raise ValueError("Season Summaries pagination exceeded frozen maximum")


def fetch_sport_event_summary(
    sport_event_id: str,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> dict[str, object]:
    return _object_payload(
        _get(
            f"sport_events/{sport_event_id}/summary.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Sport Event Summary",
    )


def fetch_season_info(
    season_id: str,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> dict[str, object]:
    return _object_payload(
        _get(
            f"seasons/{season_id}/info.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Season Info",
    )


def fetch_competitor_profile(
    competitor_id: str,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> dict[str, object]:
    return _object_payload(
        _get(
            f"competitors/{competitor_id}/profile.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Competitor Profile",
    )


def fetch_daily_summaries(
    day: date,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> list[dict[str, object]]:
    payload = _object_payload(
        _get(
            f"schedules/{day.isoformat()}/summaries.json",
            api_key=api_key,
            access_level=access_level,
            get_json=get_json,
        ),
        field="Sportradar Daily Summaries response",
    )
    return _object_array(payload, "summaries")


def fetch_daily_summary_range(
    start_date: date,
    end_date_exclusive: date,
    *,
    api_key: str,
    access_level: str,
    get_json: Callable[..., object] = _http_json,
) -> list[dict[str, object]]:
    if end_date_exclusive <= start_date:
        raise ValueError("daily-summary range end must be after start")
    rows: list[dict[str, object]] = []
    current = start_date
    while current < end_date_exclusive:
        rows.extend(
            fetch_daily_summaries(
                current,
                api_key=api_key,
                access_level=access_level,
                get_json=get_json,
            )
        )
        current += timedelta(days=1)
    return rows
