from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .contracts import WorkbenchRecord
from .sportradar_season_inventory import build_sportradar_season_inventory

CAPTURE_ID = "SPORTRADAR-HISTORICAL-SEASON-INVENTORY-CAPTURE-001"
_SPORTRADAR_HOST = "https://api.sportradar.com"
_LANGUAGE = "en"
_ALLOWED_ACCESS = frozenset({"trial", "production"})
_TRIAL_MIN_REQUEST_INTERVAL_SECONDS = 1.05
_MAX_HTTP_429_RETRIES = 4
_MAX_RETRY_DELAY_SECONDS = 16.0
_SAFE_FILE_RE = re.compile(r"[^A-Za-z0-9._-]+")


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
Sleeper = Callable[[float], None]
Now = Callable[[], datetime]


class InventoryRawEvidence(WorkbenchRecord):
    role: str
    binding_id: str
    endpoint_path: str
    http_status: int
    body_sha256: str
    headers_sha256: str
    provider_generated_at: str


class HistoricalInventoryCaptureReceipt(WorkbenchRecord):
    capture_id: str = CAPTURE_ID
    access_level: str
    inventory_semantic_sha256: str
    inventory_snapshot_at: str
    raw_request_count: int
    singles_competition_count: int
    raw_evidence: tuple[InventoryRawEvidence, ...]


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


def _aware_time(value: object, *, field: str) -> datetime:
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


def _json_object(content: bytes, *, label: str) -> dict[str, object]:
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _provider_generated_at(content: bytes, *, label: str) -> str:
    payload = _json_object(content, label=label)
    return _aware_time(payload.get("generated_at"), field=f"{label}.generated_at").isoformat()


def _rate_limit_retry_delay(exc: HTTPError, *, attempt: int) -> float:
    raw_retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
    if raw_retry_after is not None:
        try:
            retry_after = float(str(raw_retry_after).strip())
        except ValueError:
            retry_after = 0.0
        if retry_after > 0:
            return min(
                max(retry_after, _TRIAL_MIN_REQUEST_INTERVAL_SECONDS),
                _MAX_RETRY_DELAY_SECONDS,
            )
    return min(
        _TRIAL_MIN_REQUEST_INTERVAL_SECONDS * (2**attempt),
        _MAX_RETRY_DELAY_SECONDS,
    )


def _default_provider_get(url: str, headers: dict[str, str]) -> ProviderHttpResponse:
    for attempt in range(_MAX_HTTP_429_RETRIES + 1):
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
            if exc.code == 429 and attempt < _MAX_HTTP_429_RETRIES:
                time.sleep(_rate_limit_retry_delay(exc, attempt=attempt))
                continue
            raise RuntimeError(f"Sportradar request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError("Sportradar HTTPS transport failed") from exc
        return ProviderHttpResponse(
            status=status,
            body=body,
            headers=raw_headers,
            http_version=version,
        )
    raise AssertionError("Sportradar HTTP retry loop exhausted unexpectedly")


def _default_now() -> datetime:
    return datetime.now(UTC)


def _safe_filename(value: str) -> str:
    rendered = _SAFE_FILE_RE.sub("_", value).strip("._")
    if not rendered:
        raise ValueError("provider identity cannot be converted to a safe file name")
    return rendered


def _url(*, access_level: str, endpoint_path: str) -> str:
    parts = [quote(part, safe="") for part in endpoint_path.strip("/").split("/")]
    encoded_path = "/".join(parts)
    return (
        f"{_SPORTRADAR_HOST}/tennis/{access_level}/v3/{_LANGUAGE}/{encoded_path}"
    )


def _validate_response(response: ProviderHttpResponse, *, label: str) -> str:
    if response.status != 200:
        raise ValueError(f"{label} returned HTTP {response.status}")
    return _provider_generated_at(response.body, label=label)


def _retain_response(
    *,
    output_dir: Path,
    role: str,
    binding_id: str,
    endpoint_path: str,
    response: ProviderHttpResponse,
    provider_generated_at: str,
) -> tuple[Path, InventoryRawEvidence]:
    stem = _safe_filename(f"{role}-{binding_id}")
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    body_path = raw_dir / f"{stem}.json"
    headers_path = raw_dir / f"{stem}.headers"
    if body_path.exists() or headers_path.exists():
        raise ValueError(f"duplicate retained provider binding: {role}/{binding_id}")
    body_path.write_bytes(response.body)
    headers_bytes = response.headers_bytes()
    headers_path.write_bytes(headers_bytes)
    evidence = InventoryRawEvidence(
        role=role,
        binding_id=binding_id,
        endpoint_path=endpoint_path,
        http_status=response.status,
        body_sha256=_sha256_bytes(response.body),
        headers_sha256=_sha256_bytes(headers_bytes),
        provider_generated_at=provider_generated_at,
    )
    return body_path, evidence


def _singles_competition_ids(
    content: bytes,
    *,
    expected_category_id: str,
    expected_category_name: str,
) -> tuple[str, ...]:
    payload = _json_object(content, label=f"category {expected_category_id} competitions")
    competitions = payload.get("competitions")
    if not isinstance(competitions, list):
        raise ValueError("Competitions by Category competitions must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for raw in competitions:
        if not isinstance(raw, dict):
            raise ValueError("competition catalog row must be an object")
        competition_id = str(raw.get("id", "")).strip()
        if not competition_id:
            raise ValueError("competition.id must be non-empty")
        if competition_id in seen:
            raise ValueError("competition catalog contains a duplicate competition ID")
        seen.add(competition_id)
        category = raw.get("category")
        if not isinstance(category, dict):
            raise ValueError("competition.category must be an object")
        if str(category.get("id", "")).strip() != expected_category_id:
            raise ValueError("competition catalog category ID drifted")
        if str(category.get("name", "")).strip().upper() != expected_category_name:
            raise ValueError("competition catalog category name drifted")
        if str(raw.get("type", "")).strip().lower() == "singles":
            result.append(competition_id)
    return tuple(sorted(result))


def capture_historical_season_inventory(
    *,
    output_dir: Path,
    access_level: str,
    api_key: str,
    provider_get: ProviderGet = _default_provider_get,
    sleeper: Sleeper = time.sleep,
    now: Now = _default_now,
) -> HistoricalInventoryCaptureReceipt:
    """Capture the full frozen ATP/WTA competition-season denominator from Sportradar."""

    if access_level not in _ALLOWED_ACCESS:
        raise ValueError("Sportradar access level must be trial or production")
    if not api_key.strip():
        raise ValueError("SPORTRADAR_API_KEY must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("historical inventory capture output directory must begin empty")

    evidence: list[InventoryRawEvidence] = []
    category_paths: dict[str, Path] = {}
    all_singles: dict[str, str] = {}
    requests_made = 0

    category_specs = (
        ("ATP", "sr:category:3", "ATP"),
        ("WTA", "sr:category:6", "WTA"),
    )
    for index, (tour, category_id, category_name) in enumerate(category_specs):
        if index and access_level == "trial":
            sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
        endpoint = f"categories/{category_id}/competitions.json"
        response = provider_get(
            _url(access_level=access_level, endpoint_path=endpoint),
            {"x-api-key": api_key, "Accept": "application/json"},
        )
        requests_made += 1
        generated_at = _validate_response(
            response, label=f"{tour} Competitions by Category"
        )
        body_path, retained = _retain_response(
            output_dir=output_dir,
            role=f"{tour}_COMPETITIONS_BY_CATEGORY",
            binding_id=category_id,
            endpoint_path=endpoint,
            response=response,
            provider_generated_at=generated_at,
        )
        evidence.append(retained)
        category_paths[tour] = body_path
        for competition_id in _singles_competition_ids(
            response.body,
            expected_category_id=category_id,
            expected_category_name=category_name,
        ):
            if competition_id in all_singles:
                raise ValueError("competition ID appears in both ATP and WTA catalogs")
            all_singles[competition_id] = tour

    season_paths: dict[str, Path] = {}
    for competition_id in sorted(all_singles):
        if access_level == "trial":
            sleeper(_TRIAL_MIN_REQUEST_INTERVAL_SECONDS)
        endpoint = f"competitions/{competition_id}/seasons.json"
        response = provider_get(
            _url(access_level=access_level, endpoint_path=endpoint),
            {"x-api-key": api_key, "Accept": "application/json"},
        )
        requests_made += 1
        generated_at = _validate_response(
            response, label=f"Competition Seasons {competition_id}"
        )
        body_path, retained = _retain_response(
            output_dir=output_dir,
            role="COMPETITION_SEASONS",
            binding_id=competition_id,
            endpoint_path=endpoint,
            response=response,
            provider_generated_at=generated_at,
        )
        evidence.append(retained)
        season_paths[competition_id] = body_path

    captured_at = now()
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("capture clock must be timezone-aware")
    inventory = build_sportradar_season_inventory(
        atp_competitions_path=category_paths["ATP"],
        wta_competitions_path=category_paths["WTA"],
        season_response_paths=season_paths,
        snapshot_at=captured_at,
    )
    inventory_path = output_dir / "inventory.json"
    inventory_path.write_text(
        json.dumps(inventory.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    evidence_tuple = tuple(
        sorted(evidence, key=lambda row: (row.role, row.binding_id))
    )
    receipt = HistoricalInventoryCaptureReceipt(
        access_level=access_level,
        inventory_semantic_sha256=inventory.semantic_sha256,
        inventory_snapshot_at=inventory.snapshot_at,
        raw_request_count=requests_made,
        singles_competition_count=len(all_singles),
        raw_evidence=evidence_tuple,
    )
    receipt_path = output_dir / "capture-receipt.json"
    receipt_path.write_text(
        json.dumps(receipt.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "capture_receipt_sha256": receipt.semantic_sha256,
        "inventory_file_sha256": _sha256_bytes(inventory_path.read_bytes()),
        "inventory_semantic_sha256": inventory.semantic_sha256,
        "historical_candidate_count": inventory.historical_candidate_count,
        "not_yet_historical_count": inventory.not_yet_historical_count,
        "disabled_season_count": inventory.disabled_season_count,
        "season_count": inventory.season_count,
        "singles_competition_count": len(all_singles),
        "raw_request_count": requests_made,
    }
    (output_dir / "manifest.json").write_bytes(_canonical_json(manifest) + b"\n")
    return receipt
