"""Credit-bounded, resumable capture of the 2026 season-summary gap.

This is research evidence, not a prospective prediction or trusted T0 capture.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import sportradar_season_summaries_census as census
from .sportradar_exact_time_panel import (
    parse_season_inventory_bytes,
    verify_season_inventory_integrity,
)
from .sportradar_start_time_audit import (
    _load_season_page,
    build_complete_season_summaries,
)
from .sportradar_start_time_audit_v2 import derive_single_season_identity

_FIRST_MISSING_DATE = "2026-05-26"
_LAST_DATE = "2026-10-02"
_PAGE_NAME = re.compile(r"page-(\d{3})-offset-(\d{6})\.json")


def _one_request(url: str, headers: dict[str, str]) -> census.ProviderHttpResponse:
    """One HTTP attempt only; in particular, never retry a quota response."""
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:  # noqa: S310
            return census.ProviderHttpResponse(
                status=int(response.status),
                body=response.read(),
                headers=tuple((str(k), str(v)) for k, v in response.headers.raw_items()),
            )
    except HTTPError as exc:
        return census.ProviderHttpResponse(
            status=int(exc.code),
            body=exc.read(),
            headers=tuple((str(k), str(v)) for k, v in exc.headers.raw_items())
            if exc.headers
            else (),
        )
    except URLError as exc:
        raise RuntimeError("Sportradar HTTPS transport failed") from exc


def _pages(season_dir: Path) -> list[tuple[Path, Path]]:
    if not season_dir.exists():
        return []
    pairs = []
    for raw in sorted(season_dir.glob("page-*-offset-*.json")):
        if _PAGE_NAME.fullmatch(raw.name) is None:
            raise ValueError(f"unrecognized retained page name: {raw.name}")
        headers = raw.with_suffix(".headers")
        if not headers.is_file():
            raise ValueError(f"retained page has no headers: {raw}")
        pairs.append((raw, headers))
    for headers in season_dir.glob("page-*-offset-*.headers"):
        if not headers.with_suffix(".json").is_file():
            raise ValueError(f"retained headers have no page: {headers}")
    return pairs


def _state(
    pairs: list[tuple[Path, Path]], season_id: str, competition_id: str
) -> tuple[int, int, int | None]:
    """Return next page number, offset and total after verifying retained pages."""
    offset = 0
    total = None
    for index, (raw, headers) in enumerate(pairs):
        name = _PAGE_NAME.fullmatch(raw.name)
        if name is None or int(name[1]) != index or int(name[2]) != offset:
            raise ValueError("retained pages have a gap or noncanonical filename")
        page = _load_season_page(raw, headers)
        if page.offset != offset or (total is not None and page.max_results != total):
            raise ValueError("retained pagination disagrees on offset or total")
        total = page.max_results
        offset += page.result_count
        if offset > total or (offset < total and page.result_count == 0):
            raise ValueError("retained pagination does not advance")
    if total is not None and offset == total:
        aggregate = build_complete_season_summaries(pairs)
        if aggregate["summaries"]:
            identity = derive_single_season_identity(aggregate["summaries"])
            if identity.season_id != season_id or identity.competition_id != competition_id:
                raise ValueError("retained season identity differs from verified inventory")
    return len(pairs), offset, total


def _retain(
    season_dir: Path, page: int, offset: int, response: census.ProviderHttpResponse
) -> None:
    season_dir.mkdir(parents=True, exist_ok=True)
    stem = f"page-{page:03d}-offset-{offset:06d}"
    raw = season_dir / f"{stem}.json"
    headers = season_dir / f"{stem}.headers"
    if raw.exists() or headers.exists():
        raise ValueError("capture would overwrite retained evidence")
    raw.write_bytes(response.body)
    headers.write_bytes(response.headers_bytes())


def capture_targeted_2026(
    *,
    inventory_path: Path,
    output_dir: Path,
    source_dir: Path | None,
    access_level: str,
    api_key: str,
    max_requests: int,
    provider_get: census.ProviderGet = _one_request,
    sleeper: census.Sleeper = time.sleep,
) -> dict[str, object]:
    if access_level not in census._ALLOWED_ACCESS:
        raise ValueError("access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    if not 0 <= max_requests <= 50:
        raise ValueError("max_requests must be between 0 and 50")
    inventory = parse_season_inventory_bytes(inventory_path.read_bytes())
    verify_season_inventory_integrity(inventory)
    seasons = sorted(
        (
            row
            for row in inventory.season_rows
            if row.tour in {"ATP", "WTA"}
            and not row.disabled
            and _FIRST_MISSING_DATE <= row.start_date <= _LAST_DATE
        ),
        key=lambda row: (row.start_date, row.tour, row.season_id),
    )
    if not seasons:
        raise ValueError("verified inventory has no 2026 target seasons")
    output_dir.mkdir(parents=True, exist_ok=True)
    request_count = 0
    # Audit the full target set before any provider call. In particular, a zero
    # request dry run must report every reusable retained season.
    reusable: set[str] = set()
    for season in seasons:
        folder = season.season_id.replace(":", "_")
        source_pairs = _pages(source_dir / "seasons" / folder) if source_dir else []
        if source_pairs:
            _, source_offset, source_total = _state(
                source_pairs, season.season_id, season.competition_id
            )
            if source_total is None or source_offset != source_total:
                raise ValueError("source season is partial; resume it as the output directory")
            reusable.add(season.season_id)
    complete = len(reusable)
    blocked: str | None = None
    for season in seasons:
        folder = season.season_id.replace(":", "_")
        own_dir = output_dir / "seasons" / folder
        own_pairs = _pages(own_dir)
        if season.season_id in reusable:
            if own_pairs:
                raise ValueError("same season has source and output evidence")
            continue
        page, offset, total = _state(own_pairs, season.season_id, season.competition_id)
        if total is not None and offset == total:
            complete += 1
            continue
        while request_count < max_requests:
            if page >= census._MAX_PAGES:
                raise ValueError("season exceeds frozen page maximum")
            if request_count and access_level == "trial":
                sleeper(census._TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
            response = provider_get(
                census._url(access_level=access_level, season_id=season.season_id, start=offset),
                {"x-api-key": api_key, "Accept": "application/json"},
            )
            request_count += 1
            if response.status != 200:
                own_dir.mkdir(parents=True, exist_ok=True)
                failure_number = len(list(own_dir.glob("failed-request-*.json")))
                failure = own_dir / f"failed-request-{failure_number:03d}"
                failure.with_suffix(".body").write_bytes(response.body)
                failure.with_suffix(".headers").write_bytes(response.headers_bytes())
                failure.with_suffix(".json").write_text(
                    json.dumps(
                        {"status": response.status, "page": page, "offset": offset},
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                blocked = f"{season.season_id}: HTTP {response.status}"
                break
            _retain(own_dir, page, offset, response)
            next_total, returned_offset, count = census._validate_page(
                response, expected_start=offset, expected_total=total
            )
            total = next_total
            offset = returned_offset + count
            page += 1
            if offset == total:
                _state(_pages(own_dir), season.season_id, season.competition_id)
                complete += 1
                break
        if blocked or request_count >= max_requests:
            break
    report: dict[str, object] = {
        "schema": "sportradar-targeted-2026-capture-v1",
        "inventory_semantic_sha256": inventory.semantic_sha256,
        "target_seasons": len(seasons),
        "complete_seasons": complete,
        "requests_this_run": request_count,
        "request_limit": max_requests,
        "blocked": blocked,
        "historical_research_only": True,
    }
    (output_dir / "last-run.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
