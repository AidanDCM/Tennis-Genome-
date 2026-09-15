from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tennis_genome.prospective.provider_batch import ProviderBatchStore
from tennis_genome.prospective.provider_batch_operator import build_anchor_dispatch_packet
from tennis_genome.prospective.provider_batch_pagination import (
    PAGINATION_SCHEMA,
    capture_paginated_provider_batch,
    verify_paginated_provider_batches,
)

TRUSTED_CAPTURE_SCHEMA = "full-stack-forward-trusted-sportradar-capture-v1"
TRUSTED_CAPTURE_VERSION = "FULL-STACK-FORWARD-001-trusted-provider-capture-v1"
TRUSTED_CAPTURE_WORKFLOW_PATH = ".github/workflows/prospective_provider_capture_anchor.yml"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_LANGUAGE = "en"
_PAGE_LIMIT = 200
_MAX_PAGES = 100
_ALLOWED_ACCESS = {"trial", "production"}


@dataclass(frozen=True)
class ProviderHttpResponse:
    status: int
    body: bytes
    headers: tuple[tuple[str, str], ...]
    http_version: str = "HTTP/1.1"

    def headers_bytes(self) -> bytes:
        lines = [f"{self.http_version} {self.status}"]
        lines.extend(f"{name}: {value}" for name, value in self.headers)
        return ("\n".join(lines) + "\n").encode("iso-8859-1")


ProviderGet = Callable[[str, dict[str, str]], ProviderHttpResponse]
Now = Callable[[], datetime]


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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _self_hash(payload: dict[str, object], *, field: str) -> str:
    unsigned = dict(payload)
    unsigned.pop(field, None)
    return _sha256_bytes(_canonical_json(unsigned))


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


def _json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _header_map(headers: Sequence[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers:
        key = str(name).strip().lower()
        if key:
            result[key] = str(value).strip()
    return result


def _required_nonnegative_int(headers: dict[str, str], field: str) -> int:
    raw = headers.get(field, "")
    if not raw:
        raise ValueError(f"Sportradar response missing required {field} header")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"Sportradar {field} header must be an integer") from exc
    if value < 0:
        raise ValueError(f"Sportradar {field} header must be non-negative")
    return value


def _default_now() -> datetime:
    return datetime.now(UTC)


def _default_provider_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310 - frozen HTTPS host
            body = response.read()
            status = int(response.status)
            raw_headers = tuple((str(k), str(v)) for k, v in response.headers.raw_items())
            version = {10: "HTTP/1.0", 11: "HTTP/1.1"}.get(
                getattr(response, "version", 11),
                "HTTP/1.1",
            )
    except HTTPError as exc:
        raise RuntimeError(f"Sportradar request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError("Sportradar HTTPS transport failed") from exc
    return ProviderHttpResponse(
        status=status,
        body=body,
        headers=raw_headers,
        http_version=version,
    )


def _validate_routing(*, schedule_date: date, access_level: str, api_key: str) -> None:
    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    if schedule_date.year < 2000:
        raise ValueError("schedule_date is outside the supported prospective range")


def _daily_summaries_url(
    *,
    schedule_date: date,
    access_level: str,
    start: int,
) -> str:
    query = urlencode({"start": start, "limit": _PAGE_LIMIT})
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/{_LANGUAGE}/"
        f"schedules/{schedule_date.isoformat()}/summaries.json?{query}"
    )


def _validate_page_response(
    *,
    response: ProviderHttpResponse,
    expected_start: int,
    expected_total: int | None,
) -> tuple[int, int, int]:
    if response.status != 200:
        raise ValueError(f"Sportradar Daily Summaries returned HTTP {response.status}")
    payload = _json_object(response.body, label="Sportradar Daily Summaries response")
    _parse_time(payload.get("generated_at"), field="Sportradar generated_at")
    summaries = payload.get("summaries")
    if not isinstance(summaries, list):
        raise ValueError("Sportradar Daily Summaries summaries must be an array")

    headers = _header_map(response.headers)
    total = _required_nonnegative_int(headers, "x-max-results")
    offset = _required_nonnegative_int(headers, "x-offset")
    result_count = _required_nonnegative_int(headers, "x-result")
    if offset != expected_start:
        raise ValueError("Sportradar X-Offset differs from requested pagination start")
    if expected_total is not None and total != expected_total:
        raise ValueError("Sportradar pages disagree on X-Max-Results")
    if result_count != len(summaries):
        raise ValueError("Sportradar X-Result differs from JSON summary count")
    if result_count > _PAGE_LIMIT:
        raise ValueError("Sportradar X-Result exceeds frozen 200-row page maximum")
    if total == 0:
        if offset != 0 or result_count != 0:
            raise ValueError("zero-result Sportradar response has inconsistent pagination")
    elif result_count == 0:
        raise ValueError("non-empty Sportradar pagination returned an empty page")
    if offset + result_count > total:
        raise ValueError("Sportradar page extends beyond X-Max-Results")
    return total, offset, result_count


def fetch_daily_summary_pages(
    *,
    output_dir: Path,
    schedule_date: date,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
) -> list[tuple[Path, Path]]:
    """Fetch and retain a complete Daily Summaries page set directly over HTTPS."""

    _validate_routing(
        schedule_date=schedule_date,
        access_level=access_level,
        api_key=api_key,
    )
    pages_dir = output_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    if any(pages_dir.iterdir()):
        raise ValueError("trusted capture pages directory must be empty")

    page_pairs: list[tuple[Path, Path]] = []
    expected_total: int | None = None
    start = 0
    for page_number in range(_MAX_PAGES):
        url = _daily_summaries_url(
            schedule_date=schedule_date,
            access_level=access_level,
            start=start,
        )
        response = provider_get(url, {"x-api-key": api_key, "Accept": "application/json"})
        total, offset, result_count = _validate_page_response(
            response=response,
            expected_start=start,
            expected_total=expected_total,
        )
        if expected_total is None:
            expected_total = total

        raw_path = pages_dir / f"page-{page_number:04d}-offset-{offset:06d}.json"
        headers_path = pages_dir / f"page-{page_number:04d}-offset-{offset:06d}.headers"
        raw_path.write_bytes(response.body)
        headers_path.write_bytes(response.headers_bytes())
        page_pairs.append((raw_path, headers_path))

        next_start = offset + result_count
        if next_start == total:
            return page_pairs
        if next_start <= start:
            raise ValueError("Sportradar pagination did not advance")
        start = next_start

    raise ValueError("Sportradar Daily Summaries pagination exceeded frozen page maximum")


def capture_trusted_provider_batch(
    *,
    output_dir: Path,
    schedule_date: date,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
    now: Now = _default_now,
) -> dict[str, object]:
    """Fetch, retain, and ledger one provider batch without operator-supplied evidence."""

    output_dir.mkdir(parents=True, exist_ok=True)
    store = ProviderBatchStore(output_dir / "provider-batch-store")
    if store.records():
        raise ValueError("trusted capture provider-batch store must begin empty")

    page_pairs = fetch_daily_summary_pages(
        output_dir=output_dir,
        schedule_date=schedule_date,
        access_level=access_level,
        api_key=api_key,
        provider_get=provider_get,
    )
    observed_at = now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("trusted runner clock must be timezone-aware")
    observed_at = observed_at.astimezone(UTC)

    record = capture_paginated_provider_batch(
        store=store,
        page_pairs=page_pairs,
        schedule_date=schedule_date,
        observed_at=observed_at,
    )
    pagination_report = verify_paginated_provider_batches(store)
    if pagination_report.get("paginated_record_count") != 1:
        raise AssertionError("trusted capture did not produce exactly one paginated batch")
    if pagination_report.get("legacy_record_count") != 0:
        raise AssertionError("trusted capture unexpectedly produced legacy provider evidence")

    anchor_packet = build_anchor_dispatch_packet(
        store=store,
        record_sha256=str(record["record_sha256"]),
    )
    receipt: dict[str, object] = {
        "schema_version": TRUSTED_CAPTURE_SCHEMA,
        "capture_version": TRUSTED_CAPTURE_VERSION,
        "workflow_path": TRUSTED_CAPTURE_WORKFLOW_PATH,
        "provider": "SPORTRADAR",
        "transport": "GITHUB_ACTIONS_HTTPS_X_API_KEY",
        "api_version": "v3",
        "language_code": _LANGUAGE,
        "access_level": access_level,
        "schedule_date": record["schedule_date"],
        "observed_at": record["observed_at"],
        "pagination_schema": PAGINATION_SCHEMA,
        "page_count": record["page_count"],
        "raw_summary_count": record["raw_summary_count"],
        "provider_generated_at_min": record["provider_generated_at_min"],
        "provider_generated_at_max": record["provider_generated_at_max"],
        "provider_generated_at_spread_seconds": record[
            "provider_generated_at_spread_seconds"
        ],
        "batch_record_sha256": record["record_sha256"],
        "batch_chain_head_sha256": record["record_sha256"],
        "raw_payload_sha256": record["raw_payload_sha256"],
        "manifest_sha256": record["manifest_sha256"],
        "page_evidence": record["page_evidence"],
        "anchor_packet_sha256": anchor_packet["packet_sha256"],
    }
    receipt["receipt_sha256"] = _self_hash(receipt, field="receipt_sha256")

    (output_dir / "trusted_capture_receipt.json").write_bytes(_pretty_json(receipt))
    (output_dir / "anchor_packet.json").write_bytes(_pretty_json(anchor_packet))
    return {
        "record": record,
        "anchor_packet": anchor_packet,
        "trusted_capture_receipt": receipt,
        "pagination_report": pagination_report,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trusted GitHub-runner Sportradar Daily Summaries capture"
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--schedule-date", required=True)
    parser.add_argument(
        "--access-level",
        required=True,
        choices=sorted(_ALLOWED_ACCESS),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    api_key = os.environ.get("SPORTRADAR_API_KEY", "")
    capture_trusted_provider_batch(
        output_dir=args.output_dir,
        schedule_date=date.fromisoformat(args.schedule_date),
        access_level=args.access_level,
        api_key=api_key,
    )


if __name__ == "__main__":
    main()
