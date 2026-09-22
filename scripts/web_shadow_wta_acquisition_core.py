from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

_API_ROOT = "https://api.wtatennis.com/tennis"
_MANIFEST_SCHEMA = "tennis-genome-web-shadow-wta-acquisition-v1"
_INDEX_PAGE_SIZE = 100
_MAX_INDEX_PAGES = 20
_MAX_RESPONSE_BYTES = 20 * 1024 * 1024
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Accept-Language": "en",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    ),
}
FetchBytes = Callable[[str], bytes]


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _parse_object(raw: bytes, *, label: str) -> dict[str, Any]:
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ValueError(f"{label} exceeds acquisition size limit")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tournament_url(group_id: int, year: int) -> str:
    return f"{_API_ROOT}/tournaments/{group_id}/{year}"


def matches_url(group_id: int, year: int) -> str:
    return f"{tournament_url(group_id, year)}/matches"


def tournament_index_url(year: int, *, page: int = 0) -> str:
    if page < 0:
        raise ValueError("page must be non-negative")
    query = urlencode(
        {
            "page": page,
            "pageSize": _INDEX_PAGE_SIZE,
            "excludeLevels": "ITF",
            "from": date(year, 1, 1).isoformat(),
            "to": date(year, 12, 31).isoformat(),
        }
    )
    return f"{_API_ROOT}/tournaments/?{query}"


def fetch_bytes(
    url: str,
    *,
    attempts: int = 4,
    timeout_seconds: float = 30.0,
) -> bytes:
    if attempts <= 0:
        raise ValueError("attempts must be positive")
    request = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise ValueError("WTA response exceeds acquisition size limit")
            return raw
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"failed to fetch official WTA JSON: {url}") from last_error


def _targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    tournaments = config.get("tournaments")
    if not isinstance(tournaments, list) or not tournaments:
        raise ValueError("intake config must define tournaments")
    targets: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for item in tournaments:
        if not isinstance(item, dict):
            raise ValueError("intake tournament entries must be objects")
        try:
            group_id = int(item["group_id"])
            year = int(item["year"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("intake tournament identity is invalid") from exc
        slug = item.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            raise ValueError("intake tournament slug is invalid")
        identity = group_id, year
        if identity in seen:
            raise ValueError("duplicate configured WTA tournament identity")
        seen.add(identity)
        targets.append(
            {
                "group_id": group_id,
                "year": year,
                "slug": slug.strip(),
            }
        )
    return targets


def _index_identities(
    payload: dict[str, Any],
    *,
    year: int,
    page: int,
) -> tuple[set[tuple[int, int]], int]:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ValueError(f"WTA tournament index {year} lacks content array")
    page_info = payload.get("pageInfo")
    if isinstance(page_info, dict) and "page" in page_info:
        try:
            observed_page = int(page_info["page"])
        except (TypeError, ValueError) as exc:
            raise ValueError("WTA tournament index page is invalid") from exc
        if observed_page != page:
            raise ValueError("WTA tournament index page identity mismatch")

    identities: set[tuple[int, int]] = set()
    for row in content:
        if not isinstance(row, dict):
            raise ValueError("WTA tournament index row must be an object")
        group = row.get("tournamentGroup")
        if not isinstance(group, dict):
            continue
        try:
            group_id = int(group.get("id"))
            row_year = int(row.get("year"))
        except (TypeError, ValueError):
            continue
        identities.add((group_id, row_year))
    return identities, len(content)


def _validate_tournament(
    payload: dict[str, Any],
    *,
    group_id: int,
    year: int,
) -> None:
    group = payload.get("tournamentGroup")
    if not isinstance(group, dict):
        raise ValueError("WTA tournament payload lacks tournamentGroup")
    try:
        observed_group = int(group.get("id"))
        observed_year = int(payload.get("year"))
    except (TypeError, ValueError) as exc:
        raise ValueError("WTA tournament identity is invalid") from exc
    if (observed_group, observed_year) != (group_id, year):
        raise ValueError("WTA tournament identity mismatch")


def _validate_matches(payload: dict[str, Any]) -> int:
    matches = payload.get("matches")
    if not isinstance(matches, list):
        raise ValueError("WTA matches payload lacks matches array")
    if not all(isinstance(row, dict) for row in matches):
        raise ValueError("WTA matches payload contains a non-object row")
    return len(matches)


def _write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def acquire_wta_sources(
    *,
    config_path: Path,
    source_root: Path,
    observed_at: str,
    fetcher: FetchBytes = fetch_bytes,
) -> dict[str, Any]:
    config = _load_object(config_path)
    targets = _targets(config)
    source_root.mkdir(parents=True, exist_ok=True)

    years = sorted({int(target["year"]) for target in targets})
    index_records: list[dict[str, Any]] = []
    for year in years:
        identities: set[tuple[int, int]] = set()
        for page in range(_MAX_INDEX_PAGES):
            url = tournament_index_url(year, page=page)
            raw = fetcher(url)
            payload = _parse_object(
                raw,
                label=f"WTA tournament index {year} page {page}",
            )
            page_identities, entry_count = _index_identities(
                payload,
                year=year,
                page=page,
            )
            identities.update(page_identities)
            filename = f"tournament-index-{year}-page-{page}.json"
            _write_bytes(source_root / filename, raw)
            index_records.append(
                {
                    "year": year,
                    "page": page,
                    "source_url": url,
                    "filename": filename,
                    "sha256": _sha256(raw),
                    "entry_count": entry_count,
                }
            )
            if entry_count < _INDEX_PAGE_SIZE:
                break
        else:
            raise ValueError(
                f"WTA tournament index {year} exceeded page safety limit"
            )

        configured_ids = {
            int(target["group_id"])
            for target in targets
            if int(target["year"]) == year
        }
        missing = sorted(
            group_id
            for group_id in configured_ids
            if (group_id, year) not in identities
        )
        if missing:
            raise ValueError(
                f"configured WTA tournaments absent from {year} index: "
                f"{missing}"
            )

    source_records: list[dict[str, Any]] = []
    for target in sorted(
        targets,
        key=lambda item: (
            int(item["year"]),
            int(item["group_id"]),
            str(item["slug"]),
        ),
    ):
        group_id = int(target["group_id"])
        year = int(target["year"])
        slug = str(target["slug"])
        detail_url = tournament_url(group_id, year)
        schedule_url = matches_url(group_id, year)
        detail_raw = fetcher(detail_url)
        matches_raw = fetcher(schedule_url)
        detail = _parse_object(
            detail_raw,
            label=f"WTA tournament {group_id}/{year}",
        )
        schedule = _parse_object(
            matches_raw,
            label=f"WTA matches {group_id}/{year}",
        )
        _validate_tournament(
            detail,
            group_id=group_id,
            year=year,
        )
        match_count = _validate_matches(schedule)

        detail_filename = f"{slug}-tournament.json"
        matches_filename = f"{slug}-matches.json"
        _write_bytes(source_root / detail_filename, detail_raw)
        _write_bytes(source_root / matches_filename, matches_raw)
        source_records.append(
            {
                "slug": slug,
                "group_id": group_id,
                "year": year,
                "tournament_source_url": detail_url,
                "matches_source_url": schedule_url,
                "tournament_filename": detail_filename,
                "matches_filename": matches_filename,
                "tournament_sha256": _sha256(detail_raw),
                "matches_sha256": _sha256(matches_raw),
                "raw_match_count": match_count,
            }
        )

    manifest = {
        "schema_version": _MANIFEST_SCHEMA,
        "production_eligible": False,
        "observed_at": observed_at,
        "source_policy": {
            "provider": "WTA",
            "api_root": _API_ROOT,
            "selection_authority": "web-shadow/intake-config.json",
            "index_role": "audit_and_discovery_only",
            "response_serialization": "provider_bytes_unmodified",
        },
        "index_records": index_records,
        "source_records": source_records,
    }
    return manifest
