from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench.sportradar_exact_time_panel import (
    ProviderAccessFailureEvidence,
    build_provider_access_failure_evidence,
)
from tennis_genome.research_workbench.sportradar_season_inventory import SeasonInventoryRow


def _season() -> SeasonInventoryRow:
    return SeasonInventoryRow(
        tour="WTA",
        category_id="sr:category:6",
        competition_id="sr:competition:2",
        competition_name="WTA Test",
        season_id="sr:season:access",
        season_name="WTA Test 2026",
        start_date="2026-03-01",
        end_date="2026-03-07",
        year="2026",
        disabled=False,
        seasons_payload_sha256="a" * 64,
        status="HISTORICAL_CANDIDATE",
    )


def _build(tmp_path: Path) -> ProviderAccessFailureEvidence:
    headers = tmp_path / "headers.txt"
    body = tmp_path / "body.json"
    headers.write_bytes(
        b"HTTP/1.1 200 Connection Established\r\n\r\n"
        b"HTTP/2 410 Gone\r\nContent-Type: application/json\r\n\r\n"
    )
    body.write_bytes(b'{"message":"season history unavailable"}\n')
    return build_provider_access_failure_evidence(
        season=_season(),
        endpoint_path="seasons/sr:season:access/summaries.json",
        attempted_at=datetime(2026, 9, 14, 19, 10, tzinfo=UTC),
        http_status=410,
        response_headers_path=headers,
        response_body_path=body,
    )


def test_access_failure_round_trip_rederives_retained_http_bytes(tmp_path: Path) -> None:
    evidence = _build(tmp_path)
    restored = ProviderAccessFailureEvidence.model_validate(evidence.canonical_payload())

    assert restored == evidence
    assert restored.http_status == 410
    assert restored.failure_class == "HISTORY_NOT_AVAILABLE"
    assert base64.b64decode(restored.response_body_b64) == (
        b'{"message":"season history unavailable"}\n'
    )


def test_access_failure_rejects_tampered_raw_headers(tmp_path: Path) -> None:
    payload = _build(tmp_path).canonical_payload()
    payload["response_headers_b64"] = base64.b64encode(
        b"HTTP/2 404 Not Found\r\n\r\n"
    ).decode("ascii")

    with pytest.raises(ValueError, match="header bytes do not match stored SHA-256"):
        ProviderAccessFailureEvidence.model_validate(payload)


def test_access_failure_rejects_status_that_disagrees_with_rehashed_headers(
    tmp_path: Path,
) -> None:
    payload = _build(tmp_path).canonical_payload()
    changed_headers = b"HTTP/2 404 Not Found\r\n\r\n"
    payload["response_headers_b64"] = base64.b64encode(changed_headers).decode("ascii")
    payload["response_headers_sha256"] = hashlib.sha256(changed_headers).hexdigest()

    with pytest.raises(ValueError, match="HTTP status does not match retained response headers"):
        ProviderAccessFailureEvidence.model_validate(payload)


def test_access_failure_rejects_tampered_body(tmp_path: Path) -> None:
    payload = _build(tmp_path).canonical_payload()
    payload["response_body_b64"] = base64.b64encode(b"different body").decode("ascii")

    with pytest.raises(ValueError, match="body bytes do not match stored SHA-256"):
        ProviderAccessFailureEvidence.model_validate(payload)


def test_access_failure_rejects_non_base64_payload(tmp_path: Path) -> None:
    payload = _build(tmp_path).canonical_payload()
    payload["response_headers_b64"] = "not@@base64"

    with pytest.raises(ValueError, match="canonical base64"):
        ProviderAccessFailureEvidence.model_validate(payload)


def test_access_failure_builder_rejects_declared_status_not_in_headers(
    tmp_path: Path,
) -> None:
    headers = tmp_path / "headers.txt"
    body = tmp_path / "body.txt"
    headers.write_bytes(b"HTTP/2 404 Not Found\r\n\r\n")
    body.write_bytes(b"not found")

    with pytest.raises(ValueError, match="HTTP status does not match retained response headers"):
        build_provider_access_failure_evidence(
            season=_season(),
            endpoint_path="seasons/sr:season:access/summaries.json",
            attempted_at=datetime(2026, 9, 14, 19, 10, tzinfo=UTC),
            http_status=410,
            response_headers_path=headers,
            response_body_path=body,
        )
