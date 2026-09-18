from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.dispatch_due_forward_settlements import (
    SETTLEMENT_WORKFLOW,
    run_monitor,
    settlement_due,
)


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


class _FakeApi:
    repository = "AidanDCM/Tennis-Genome-"

    def __init__(self, *, now: datetime, include_verified: bool = False) -> None:
        self.prediction_sha = "a" * 64
        self.identity_bytes = (
            json.dumps(
                {
                    "schema_version": "full-stack-pilot-sportradar-identity-v1",
                    "provider_batch_record_sha256": "b" * 64,
                },
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        scheduled = now - timedelta(hours=5)
        self.prediction_zip = _zip_bytes(
            {
                "forward-004-target-resolution.json": (
                    json.dumps(
                        {
                            "event_id": "sr:sport_event:90001",
                            "scheduled_start": scheduled.isoformat(),
                        }
                    )
                    + "\n"
                ).encode("utf-8"),
                "prediction-work/prediction-record-sha256.txt": (
                    self.prediction_sha + "\n"
                ).encode("utf-8"),
                "prediction-work/sportradar-identity-binding.json": self.identity_bytes,
                "provider-run.json": b'{"id":555}\n',
            }
        )
        self.anchor_zip = _zip_bytes({"comment-id.txt": b"303\n"})
        self.dispatched: list[tuple[str, dict[str, str]]] = []
        self.include_verified = include_verified

    def list_artifacts(self):
        rows = [
            {
                "id": 101,
                "name": "wta-forward-004-999",
                "expired": False,
            },
            {
                "id": 202,
                "name": f"prospective-prediction-anchor-{self.prediction_sha}",
                "expired": False,
            },
        ]
        if self.include_verified:
            rows.append(
                {
                    "id": 505,
                    "name": "full-stack-forward-verified-settlement-101",
                    "expired": False,
                }
            )
        return rows

    def artifact_zip(self, artifact_id: int):
        if artifact_id == 101:
            return zipfile.ZipFile(io.BytesIO(self.prediction_zip))
        if artifact_id == 202:
            return zipfile.ZipFile(io.BytesIO(self.anchor_zip))
        raise AssertionError(f"unexpected artifact id {artifact_id}")

    def run_artifacts(self, run_id: int):
        assert run_id == 555
        return [
            {
                "id": 404,
                "name": "trusted-provider-capture-555",
                "expired": False,
            }
        ]

    def dispatch(self, workflow: str, inputs: dict[str, str]) -> None:
        self.dispatched.append((workflow, inputs))


def test_settlement_due_uses_four_hour_grace_and_thirty_hour_ceiling() -> None:
    start = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

    assert not settlement_due(
        scheduled_start=start,
        now=start + timedelta(hours=3, minutes=59),
    )
    assert settlement_due(scheduled_start=start, now=start + timedelta(hours=4))
    assert settlement_due(scheduled_start=start, now=start + timedelta(hours=30))
    assert not settlement_due(
        scheduled_start=start,
        now=start + timedelta(hours=30, seconds=1),
    )


def test_monitor_reconstructs_trusted_ids_and_dispatches_one_settlement() -> None:
    now = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    api = _FakeApi(now=now)

    report = run_monitor(api=api, now=now)

    assert report["dispatch_count"] == 1
    assert report["error_count"] == 0
    assert len(api.dispatched) == 1
    workflow, inputs = api.dispatched[0]
    assert workflow == SETTLEMENT_WORKFLOW
    assert inputs == {
        "prediction_record_sha256": "a" * 64,
        "prediction_artifact_id": "101",
        "provider_artifact_id": "404",
        "prediction_anchor_comment_id": "303",
        "identity_binding_sha256": hashlib.sha256(api.identity_bytes).hexdigest(),
        "sportradar_event_id": "sr:sport_event:90001",
        "sportradar_access_level": "trial",
    }


def test_monitor_skips_prediction_that_already_has_verified_settlement() -> None:
    now = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)
    api = _FakeApi(now=now, include_verified=True)

    report = run_monitor(api=api, now=now)

    assert report["dispatch_count"] == 0
    assert report["error_count"] == 0
    assert api.dispatched == []
    assert report["rows"][0]["status"] == "already_finalized"


def test_settlement_monitor_workflow_is_bounded_and_scheduled() -> None:
    text = Path(".github/workflows/forward_settlement_monitor.yml").read_text(
        encoding="utf-8"
    )

    assert 'cron: "37 */2 * * *"' in text
    assert "actions: write" in text
    assert "scripts/dispatch_due_forward_settlements.py" in text
    assert "forward-settlement-monitor-${{ github.run_id }}" in text
    assert "retention-days: 30" in text


def test_verified_settlement_finalizer_uses_prediction_bound_provider_sha() -> None:
    text = Path(".github/workflows/prospective_settlement_finalize.yml").read_text(
        encoding="utf-8"
    )

    old_sha = "5f23498164f45f03c2d79133e4e28d59d3ff51dd0ef105d70cd760bc3458ad10"
    assert old_sha not in text
    assert "sportradar-identity-binding.json" in text
    assert "provider_batch_record_sha256" in text
    assert 'name="full-stack-forward-verified-settlement-${PREDICTION_ARTIFACT_ID}"' in text
    assert (
        "name: full-stack-forward-verified-settlement-"
        "${{ inputs.prediction_artifact_id }}"
        in text
    )
    assert "challenger_shadow_settlement_finalize.yml/dispatches" in text


def test_trusted_dispatch_bridge_accepts_complete_settlement_capture_identity() -> None:
    text = Path(".github/workflows/trusted_dispatch_bridge.yml").read_text(
        encoding="utf-8"
    )

    contract = text.split("'prospective_settlement_capture.yml':", maxsplit=1)[1]
    contract = contract.split("},", maxsplit=1)[0]
    for field in (
        "prediction_record_sha256",
        "prediction_artifact_id",
        "provider_artifact_id",
        "prediction_anchor_comment_id",
        "identity_binding_sha256",
        "sportradar_event_id",
        "sportradar_access_level",
    ):
        assert f"'{field}'" in contract
