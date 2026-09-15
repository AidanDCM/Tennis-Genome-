from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective import settlement_capture_live as live
from tennis_genome.prospective.settlement_capture_github import (
    LiveSettlementCaptureEvidence,
)
from tennis_genome.prospective.settlement_identity import SettlementIdentityBinding


class _FakePilotStore:
    def __init__(self, root: Path) -> None:
        self.evidence_dir = root / "evidence"
        self.evidence_dir.mkdir(parents=True)
        self.prediction = {
            "record_type": "PREDICTION_COMMIT",
            "record_sha256": "a" * 64,
            "prediction_id": "prediction-001",
            "match_id": "match-001",
            "tour": "ATP",
            "player_a_id": "atp:id:1",
            "player_b_id": "atp:id:2",
            "scheduled_start": "2026-09-15T16:00:00+00:00",
            "source_manifest_hashes": ["b" * 64],
        }
        self._records: list[dict[str, object]] = [self.prediction]

    def verify(self) -> dict[str, object]:
        return {
            "status": "VERIFIED",
            "chain_head_sha256": str(self._records[-1]["record_sha256"]),
        }

    def records(self) -> list[dict[str, object]]:
        return [dict(record) for record in self._records]

    def find_record(self, sha: str) -> dict[str, object]:
        matches = [record for record in self._records if record.get("record_sha256") == sha]
        if len(matches) != 1:
            raise ValueError("expected exactly one")
        return dict(matches[0])


class _FakeVerifier:
    def verify(self, **kwargs):
        return {"status": "VERIFIED"}


def _binding() -> SettlementIdentityBinding:
    return SettlementIdentityBinding(
        schema_version="full-stack-pilot-sportradar-identity-v1",
        identity_version="FULL-STACK-PILOT-001-sportradar-identity-v1",
        provider="SPORTRADAR_TENNIS_V3",
        match_id="match-001",
        tour="ATP",
        sportradar_event_id="sr:sport_event:123456",
        player_a_canonical_id="atp:id:1",
        player_b_canonical_id="atp:id:2",
        player_a_sportradar_id="sr:competitor:11",
        player_b_sportradar_id="sr:competitor:22",
        player_a_sportradar_name="Alpha Player",
        player_b_sportradar_name="Beta Player",
        scheduled_start="2026-09-15T16:00:00+00:00",
        provider_batch_record_sha256="1" * 64,
        provider_batch_raw_sha256="2" * 64,
        provider_anchor_comment_id=111222333,
        provider_observed_at="2026-09-15T14:00:00+00:00",
        mapping_method="PREMATCH_PROVIDER_EVENT_EXPLICIT_A_B",
        artifact_sha256="3" * 64,
    )


def _timeline(*, winner: str = "sr:competitor:11") -> bytes:
    payload = {
        "generated_at": "2026-09-15T18:00:00Z",
        "sport_event": {"id": "sr:sport_event:123456"},
        "sport_event_status": {
            "status": "ended",
            "winner_id": winner,
        },
    }
    return json.dumps(payload, sort_keys=True).encode("utf-8")


def _evidence(timeline_bytes: bytes, headers_bytes: bytes) -> LiveSettlementCaptureEvidence:
    receipt = {
        "prediction_record_sha256": "a" * 64,
        "identity_binding_sha256": "b" * 64,
        "sportradar_event_id": "sr:sport_event:123456",
        "provider_status": "ended",
        "winner_sportradar_id": "sr:competitor:11",
        "timeline_sha256": hashlib.sha256(timeline_bytes).hexdigest(),
        "response_headers_sha256": hashlib.sha256(headers_bytes).hexdigest(),
    }
    return LiveSettlementCaptureEvidence(
        comment_id=975318642,
        workflow_run_id=246813579,
        comment_created_at=datetime(2026, 9, 15, 18, 0, 31, tzinfo=UTC),
        provider_generated_at=datetime(2026, 9, 15, 18, 0, tzinfo=UTC),
        observed_at=datetime(2026, 9, 15, 18, 0, 30, tzinfo=UTC),
        receipt=receipt,
        comment_response_bytes=b"comment-response",
        workflow_run_response_bytes=b"run-response",
        comment_response_sha256=hashlib.sha256(b"comment-response").hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(b"run-response").hexdigest(),
        workflow_source_sha="d" * 40,
    )


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    pilot: _FakePilotStore,
    evidence: LiveSettlementCaptureEvidence,
) -> None:
    binding = _binding()
    identity_payload = {"schema_version": binding.schema_version}

    monkeypatch.setattr(
        live,
        "find_prediction_identity_binding",
        lambda **kwargs: (binding, "b" * 64, identity_payload),
    )
    monkeypatch.setattr(live, "authenticate_identity_binding", lambda **kwargs: binding)
    monkeypatch.setattr(
        live,
        "fetch_authenticated_settlement_capture_evidence",
        lambda **kwargs: evidence,
    )
    monkeypatch.setattr(
        live,
        "validate_retained_settlement_capture_evidence",
        lambda **kwargs: evidence,
    )

    def fake_settle_prediction(**kwargs):
        wrapper_bytes = kwargs["settlement_evidence_path"].read_bytes()
        wrapper_sha = hashlib.sha256(wrapper_bytes).hexdigest()
        (pilot.evidence_dir / wrapper_sha).write_bytes(wrapper_bytes)
        record = {
            "record_type": "SETTLEMENT",
            "record_sha256": "c" * 64,
            "prediction_record_sha256": "a" * 64,
            "settlement_evidence_sha256": wrapper_sha,
            "primary_evaluation_eligible": True,
        }
        pilot._records.append(record)
        return dict(record)

    monkeypatch.setattr(live, "settle_prediction", fake_settle_prediction)


def test_trusted_settlement_admission_retains_transport_and_settles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore(tmp_path / "pilot")
    timeline_bytes = _timeline()
    headers_bytes = b"[]\n"
    evidence = _evidence(timeline_bytes, headers_bytes)
    _patch_dependencies(monkeypatch, pilot, evidence)
    timeline_path = tmp_path / "timeline.json"
    headers_path = tmp_path / "headers.json"
    timeline_path.write_bytes(timeline_bytes)
    headers_path.write_bytes(headers_bytes)
    store = live.TrustedSettlementStore(tmp_path / "trusted")

    record = live.admit_trusted_settlement(
        pilot_store=pilot,  # type: ignore[arg-type]
        prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
        provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
        trusted_store=store,
        prediction_record_sha256="a" * 64,
        github_comment_id=975318642,
        timeline_path=timeline_path,
        response_headers_path=headers_path,
    )

    assert record["settlement_evidence_mode"] == live.TRUSTED_SETTLEMENT_MODE
    assert record["github_comment_id"] == 975318642
    report = store.verify(
        pilot_store=pilot,  # type: ignore[arg-type]
        prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
        provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
    )
    assert report["status"] == "LIVE_VERIFIED"
    assert report["trusted_settlement_count"] == 1
    assert report["primary_evaluation_eligible_count"] == 1


def test_retained_only_settlement_replay_does_not_reauthenticate_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore(tmp_path / "pilot")
    timeline_bytes = _timeline()
    headers_bytes = b"[]\n"
    evidence = _evidence(timeline_bytes, headers_bytes)
    _patch_dependencies(monkeypatch, pilot, evidence)
    timeline_path = tmp_path / "timeline.json"
    headers_path = tmp_path / "headers.json"
    timeline_path.write_bytes(timeline_bytes)
    headers_path.write_bytes(headers_bytes)
    store = live.TrustedSettlementStore(tmp_path / "trusted")
    live.admit_trusted_settlement(
        pilot_store=pilot,  # type: ignore[arg-type]
        prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
        provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
        trusted_store=store,
        prediction_record_sha256="a" * 64,
        github_comment_id=975318642,
        timeline_path=timeline_path,
        response_headers_path=headers_path,
    )

    monkeypatch.setattr(
        live,
        "fetch_authenticated_settlement_capture_evidence",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("network fetch")),
    )
    monkeypatch.setattr(
        live,
        "authenticate_identity_binding",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("identity live fetch")),
    )
    report = store.verify(
        pilot_store=pilot,  # type: ignore[arg-type]
        prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
        provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
        revalidate_live=False,
    )
    assert report["status"] == "RETAINED_VERIFIED"


def test_timeline_digest_mismatch_fails_before_settlement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore(tmp_path / "pilot")
    authentic = _timeline()
    headers = b"[]\n"
    evidence = _evidence(authentic, headers)
    _patch_dependencies(monkeypatch, pilot, evidence)
    timeline_path = tmp_path / "timeline.json"
    headers_path = tmp_path / "headers.json"
    timeline_path.write_bytes(_timeline(winner="sr:competitor:22"))
    headers_path.write_bytes(headers)

    with pytest.raises(ValueError, match="does not match trusted settlement receipt"):
        live.admit_trusted_settlement(
            pilot_store=pilot,  # type: ignore[arg-type]
            prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
            provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
            trusted_store=live.TrustedSettlementStore(tmp_path / "trusted"),
            prediction_record_sha256="a" * 64,
            github_comment_id=975318642,
            timeline_path=timeline_path,
            response_headers_path=headers_path,
        )


def test_provider_winner_must_be_one_of_precommitted_competitors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore(tmp_path / "pilot")
    timeline_bytes = _timeline(winner="sr:competitor:999")
    headers = b"[]\n"
    evidence = _evidence(timeline_bytes, headers)
    evidence.receipt["winner_sportradar_id"] = "sr:competitor:999"
    _patch_dependencies(monkeypatch, pilot, evidence)
    timeline_path = tmp_path / "timeline.json"
    headers_path = tmp_path / "headers.json"
    timeline_path.write_bytes(timeline_bytes)
    headers_path.write_bytes(headers)

    with pytest.raises(ValueError, match="not a pre-match competitor"):
        live.admit_trusted_settlement(
            pilot_store=pilot,  # type: ignore[arg-type]
            prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
            provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
            trusted_store=live.TrustedSettlementStore(tmp_path / "trusted"),
            prediction_record_sha256="a" * 64,
            github_comment_id=975318642,
            timeline_path=timeline_path,
            response_headers_path=headers_path,
        )


def test_any_pilot_settlement_without_trusted_transport_fails_promotion(
    tmp_path: Path,
) -> None:
    pilot = _FakePilotStore(tmp_path / "pilot")
    pilot._records.append(
        {
            "record_type": "SETTLEMENT",
            "record_sha256": "c" * 64,
            "prediction_record_sha256": "a" * 64,
            "settlement_evidence_sha256": "d" * 64,
            "primary_evaluation_eligible": False,
        }
    )
    store = live.TrustedSettlementStore(tmp_path / "trusted")

    with pytest.raises(ValueError, match="lack trusted Sportradar transport"):
        store.verify(
            pilot_store=pilot,  # type: ignore[arg-type]
            prediction_anchor_store=_FakeVerifier(),  # type: ignore[arg-type]
            provider_batch_store=_FakeVerifier(),  # type: ignore[arg-type]
            revalidate_live=False,
        )
