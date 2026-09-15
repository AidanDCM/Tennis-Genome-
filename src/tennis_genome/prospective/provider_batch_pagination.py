from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tennis_genome.prospective.provider_batch import (
    BATCH_SCHEMA,
    BATCH_VERSION,
    ProviderBatchStore,
    build_batch_manifest,
)

PAGINATION_SCHEMA = "full-stack-forward-sportradar-pagination-v2"
_PROVIDER = "SPORTRADAR"
_REQUIRED_HEADERS = ("x-max-results", "x-offset", "x-result")
_MAX_PROVIDER_GENERATION_SPREAD = timedelta(minutes=10)
_MAX_OBSERVED_AFTER_PROVIDER_GENERATION = timedelta(minutes=10)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: object, *, field: str) -> datetime:
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


def _json_object_bytes(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("iso-8859-1")
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        if ":" not in raw_line:
            continue
        name, value = raw_line.split(":", 1)
        parsed[name.strip().lower()] = value.strip()
    missing = [name for name in _REQUIRED_HEADERS if not parsed.get(name)]
    if missing:
        raise ValueError(f"response headers missing required pagination fields: {missing}")
    return parsed


def _nonnegative_int(headers: dict[str, str], name: str) -> int:
    try:
        value = int(headers[name])
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _event_id(summary: object) -> str:
    if not isinstance(summary, dict):
        raise ValueError("Sportradar summary must be an object")
    event = summary.get("sport_event")
    if not isinstance(event, dict):
        raise ValueError("Sportradar summary sport_event must be an object")
    event_id = str(event.get("id", "")).strip()
    if not event_id:
        raise ValueError("Sportradar summary sport_event.id must be non-empty")
    return event_id


@dataclass(frozen=True)
class PageEvidence:
    offset: int
    result_count: int
    max_results: int
    provider_generated_at: str
    raw_payload_sha256: str
    response_headers_sha256: str
    summaries: tuple[object, ...]

    def metadata(self) -> dict[str, object]:
        return {
            "offset": self.offset,
            "result_count": self.result_count,
            "max_results": self.max_results,
            "provider_generated_at": self.provider_generated_at,
            "raw_payload_sha256": self.raw_payload_sha256,
            "response_headers_sha256": self.response_headers_sha256,
        }


def _load_page(raw_path: Path, headers_path: Path) -> PageEvidence:
    raw_bytes = raw_path.read_bytes()
    header_bytes = headers_path.read_bytes()
    raw = _json_object_bytes(raw_bytes, label="Sportradar page payload")
    generated_at = _parse_time(
        raw.get("generated_at"),
        field="Sportradar page generated_at",
    )
    summaries = raw.get("summaries")
    if not isinstance(summaries, list):
        raise ValueError("Sportradar page payload summaries must be an array")
    header_map = _headers(header_bytes)
    max_results = _nonnegative_int(header_map, "x-max-results")
    offset = _nonnegative_int(header_map, "x-offset")
    result_count = _nonnegative_int(header_map, "x-result")
    if len(summaries) != result_count:
        raise ValueError("Sportradar page summary count differs from X-Result")
    if result_count > 200:
        raise ValueError("Sportradar page X-Result exceeds documented 200-row maximum")
    return PageEvidence(
        offset=offset,
        result_count=result_count,
        max_results=max_results,
        provider_generated_at=generated_at.isoformat(),
        raw_payload_sha256=_sha256_bytes(raw_bytes),
        response_headers_sha256=_sha256_bytes(header_bytes),
        summaries=tuple(summaries),
    )


def _provider_generation_bounds(pages: Sequence[PageEvidence]) -> tuple[datetime, datetime]:
    generated = [
        _parse_time(page.provider_generated_at, field="page.provider_generated_at")
        for page in pages
    ]
    earliest = min(generated)
    latest = max(generated)
    if earliest.date() != latest.date():
        raise ValueError("Sportradar pages cross a UTC provider-generation date boundary")
    if latest - earliest > _MAX_PROVIDER_GENERATION_SPREAD:
        raise ValueError("Sportradar page generated_at spread exceeds frozen 10-minute bound")
    return earliest, latest


def _validate_capture_timing(
    *,
    aggregate: dict[str, object],
    schedule_date: date,
    observed_at: datetime,
) -> tuple[datetime, datetime, datetime]:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed = observed_at.astimezone(UTC)
    earliest = _parse_time(
        aggregate.get("provider_generated_at_min"),
        field="provider_generated_at_min",
    )
    latest = _parse_time(
        aggregate.get("provider_generated_at_max"),
        field="provider_generated_at_max",
    )
    if earliest > latest:
        raise ValueError("provider generation bounds are inverted")
    if earliest.date() != latest.date():
        raise ValueError("provider generation bounds cross a UTC date boundary")
    if schedule_date != latest.date():
        raise ValueError("schedule_date must equal provider generated_at UTC date")
    if observed.date() != schedule_date:
        raise ValueError("schedule_date must equal observed_at UTC date")
    if observed < latest:
        raise ValueError("observed_at cannot predate provider generated_at")
    if observed - latest > _MAX_OBSERVED_AFTER_PROVIDER_GENERATION:
        raise ValueError("observed_at exceeds frozen 10-minute provider-generation lag")
    return observed, earliest, latest


def build_complete_daily_payload(
    page_pairs: Sequence[tuple[Path, Path]],
) -> dict[str, object]:
    """Build one deterministic complete Daily Summaries payload from retained pages."""

    if not page_pairs:
        raise ValueError("at least one Sportradar page/header pair is required")
    pages = [_load_page(raw, headers) for raw, headers in page_pairs]
    pages.sort(key=lambda page: page.offset)

    totals = {page.max_results for page in pages}
    if len(totals) != 1:
        raise ValueError("Sportradar pages disagree on X-Max-Results")
    expected_total = totals.pop()
    if pages[0].offset != 0:
        raise ValueError("Sportradar pagination must begin at X-Offset 0")

    provider_generated_at_min, provider_generated_at_max = _provider_generation_bounds(pages)
    expected_offset = 0
    summaries: list[object] = []
    ids: set[str] = set()
    for page in pages:
        if page.offset != expected_offset:
            raise ValueError("Sportradar pagination has a gap or overlap")
        if expected_total > 0 and page.result_count == 0:
            raise ValueError("non-empty Sportradar pagination contains an empty page")
        for summary in page.summaries:
            event_id = _event_id(summary)
            if event_id in ids:
                raise ValueError("Sportradar pagination contains duplicate sport-event IDs")
            ids.add(event_id)
            summaries.append(summary)
        expected_offset += page.result_count

    if expected_offset != expected_total:
        raise ValueError("retained Sportradar pages do not cover X-Max-Results exactly")
    if expected_total == 0 and len(pages) != 1:
        raise ValueError("zero-result Sportradar capture must contain exactly one page")

    return {
        "pagination_schema": PAGINATION_SCHEMA,
        "provider": _PROVIDER,
        "x_max_results": expected_total,
        "page_count": len(pages),
        "provider_generated_at_min": provider_generated_at_min.isoformat(),
        "provider_generated_at_max": provider_generated_at_max.isoformat(),
        "provider_generated_at_spread_seconds": int(
            (provider_generated_at_max - provider_generated_at_min).total_seconds()
        ),
        "pages": [page.metadata() for page in pages],
        "summaries": summaries,
    }


def _verify_page_evidence(
    *,
    store: ProviderBatchStore,
    aggregate: dict[str, object],
) -> None:
    raw_pages = aggregate.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ValueError("paginated provider aggregate lacks page evidence metadata")
    page_pairs: list[tuple[Path, Path]] = []
    for raw_page in raw_pages:
        if not isinstance(raw_page, dict):
            raise ValueError("paginated provider page metadata must be an object")
        raw_sha = str(raw_page.get("raw_payload_sha256", ""))
        headers_sha = str(raw_page.get("response_headers_sha256", ""))
        for digest in (raw_sha, headers_sha):
            if len(digest) != 64:
                raise ValueError("paginated provider page evidence SHA-256 is invalid")
            evidence = store.evidence_dir / digest
            if not evidence.is_file():
                raise ValueError(f"missing paginated provider evidence {digest}")
            if _sha256_file(evidence) != digest:
                raise ValueError(f"paginated provider evidence digest mismatch: {digest}")
        page_pairs.append((store.evidence_dir / raw_sha, store.evidence_dir / headers_sha))

    rebuilt = build_complete_daily_payload(page_pairs)
    if _canonical_json(rebuilt) != _canonical_json(aggregate):
        raise ValueError("paginated provider aggregate does not reproduce from raw pages")


def verify_paginated_provider_batches(store: ProviderBatchStore) -> dict[str, object]:
    """Verify all pagination evidence referenced by provider-batch records."""

    store.verify()
    paginated = 0
    legacy = 0
    for record in store.records():
        raw_sha = str(record.get("raw_payload_sha256", ""))
        raw_path = store.evidence_dir / raw_sha
        if not raw_path.is_file():
            raise ValueError(f"missing provider aggregate evidence {raw_sha}")
        aggregate = _json_object_bytes(raw_path.read_bytes(), label="provider aggregate")
        if aggregate.get("pagination_schema") != PAGINATION_SCHEMA:
            legacy += 1
            continue
        _verify_page_evidence(store=store, aggregate=aggregate)
        if int(record.get("raw_summary_count", -1)) != int(aggregate["x_max_results"]):
            raise ValueError("provider record count differs from paginated X-Max-Results")
        observed_at = _parse_time(record.get("observed_at"), field="record.observed_at")
        try:
            schedule_date = date.fromisoformat(str(record.get("schedule_date", "")))
        except ValueError as exc:
            raise ValueError("record schedule_date must be YYYY-MM-DD") from exc
        _, provider_min, provider_max = _validate_capture_timing(
            aggregate=aggregate,
            schedule_date=schedule_date,
            observed_at=observed_at,
        )
        if record.get("provider_generated_at_min") != provider_min.isoformat():
            raise ValueError("provider record min generated_at does not reproduce")
        if record.get("provider_generated_at_max") != provider_max.isoformat():
            raise ValueError("provider record max generated_at does not reproduce")
        if int(record.get("provider_generated_at_spread_seconds", -1)) != int(
            aggregate["provider_generated_at_spread_seconds"]
        ):
            raise ValueError("provider record generated_at spread does not reproduce")
        paginated += 1
    return {
        "pagination_schema": PAGINATION_SCHEMA,
        "paginated_record_count": paginated,
        "legacy_record_count": legacy,
        "status": "VERIFIED",
    }


def capture_paginated_provider_batch(
    *,
    store: ProviderBatchStore,
    page_pairs: Sequence[tuple[Path, Path]],
    schedule_date: date,
    observed_at: datetime,
) -> dict[str, object]:
    """Capture one complete multi-page Daily Summaries response fail-closed."""

    aggregate = build_complete_daily_payload(page_pairs)
    normalized_observed_at, provider_min, provider_max = _validate_capture_timing(
        aggregate=aggregate,
        schedule_date=schedule_date,
        observed_at=observed_at,
    )
    with store.write_lock():
        store.verify()
        for raw_path, headers_path in page_pairs:
            store._store_evidence(raw_path.read_bytes())
            store._store_evidence(headers_path.read_bytes())
        aggregate_bytes = _pretty_json(aggregate)
        aggregate_sha = store._store_evidence(aggregate_bytes)
        manifest = build_batch_manifest(
            raw_payload=aggregate,
            schedule_date=schedule_date,
            observed_at=normalized_observed_at,
            raw_payload_sha256=aggregate_sha,
        )
        if manifest.get("schema_version") != BATCH_SCHEMA:
            raise AssertionError("provider-batch manifest schema drifted")
        manifest_sha = store._store_evidence(_pretty_json(manifest))
        record = store._append_record(
            {
                "record_type": "PROVIDER_BATCH",
                "provider": _PROVIDER,
                "schedule_date": manifest["schedule_date"],
                "observed_at": manifest["observed_at"],
                "provider_generated_at_min": provider_min.isoformat(),
                "provider_generated_at_max": provider_max.isoformat(),
                "provider_generated_at_spread_seconds": aggregate[
                    "provider_generated_at_spread_seconds"
                ],
                "raw_payload_sha256": aggregate_sha,
                "manifest_sha256": manifest_sha,
                "raw_summary_count": manifest["raw_summary_count"],
                "pagination_schema": PAGINATION_SCHEMA,
                "page_count": aggregate["page_count"],
                "page_evidence": aggregate["pages"],
                "evidence_sha256": [aggregate_sha, manifest_sha],
            }
        )
    verify_paginated_provider_batches(store)
    if record.get("batch_version") != BATCH_VERSION:
        raise AssertionError("provider-batch version drifted")
    return record


def write_complete_payload(
    *,
    page_pairs: Sequence[tuple[Path, Path]],
    output_path: Path,
) -> dict[str, object]:
    payload = build_complete_daily_payload(page_pairs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_pretty_json(payload))
    return payload
