from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tennis_genome.prospective import settlement_identity as identity
from tennis_genome.prospective.provider_batch import ProviderBatchStore, capture_provider_batch


def _raw_payload() -> dict[str, object]:
    return {
        "generated_at": "2026-09-15T14:00:00Z",
        "summaries": [
            {
                "sport_event": {
                    "id": "sr:sport_event:123456",
                    "start_time": "2026-09-15T16:00:00Z",
                    "sport_event_context": {
                        "category": {"id": "sr:category:3", "name": "ATP"},
                        "competition": {"id": "sr:competition:1", "type": "singles"},
                    },
                    "competitors": [
                        {
                            "id": "sr:competitor:11",
                            "name": "Alpha Player",
                            "virtual": False,
                        },
                        {
                            "id": "sr:competitor:22",
                            "name": "Beta Player",
                            "virtual": False,
                        },
                    ],
                },
                "sport_event_status": {"status": "not_started"},
            }
        ],
    }


def _provider_store(tmp_path: Path, *, observed_hour: int = 14):
    store = ProviderBatchStore(tmp_path / f"provider-{observed_hour}")
    raw = tmp_path / f"daily-{observed_hour}.json"
    raw.write_text(json.dumps(_raw_payload()), encoding="utf-8")
    record = capture_provider_batch(
        store=store,
        raw_payload_path=raw,
        schedule_date=date(2026, 9, 15),
        observed_at=datetime(2026, 9, 15, observed_hour, tzinfo=UTC),
    )
    return store, record


def _mock_trusted_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(**kwargs):
        assert kwargs["comment_id"] == 111222333
        assert kwargs["batch_record"]["record_type"] == "PROVIDER_BATCH"
        return object()

    monkeypatch.setattr(identity, "fetch_authenticated_trusted_capture_evidence", fake_fetch)


def _build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[identity.SettlementIdentityBinding, ProviderBatchStore]:
    store, record = _provider_store(tmp_path)
    _mock_trusted_anchor(monkeypatch)
    binding = identity.build_identity_binding(
        batch_store=store,
        batch_record_sha256=str(record["record_sha256"]),
        provider_anchor_comment_id=111222333,
        match_id="match-001",
        player_a_canonical_id="atp:id:1",
        player_b_canonical_id="atp:id:2",
        sportradar_event_id="sr:sport_event:123456",
        player_a_sportradar_id="sr:competitor:11",
        player_b_sportradar_id="sr:competitor:22",
    )
    return binding, store


def test_identity_binding_reproduces_from_trusted_prematch_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding, store = _build(tmp_path, monkeypatch)
    payload = identity.identity_as_dict(binding)

    verified = identity.authenticate_identity_binding(
        payload=payload,
        batch_store=store,
    )

    assert verified.sportradar_event_id == "sr:sport_event:123456"
    assert verified.player_a_sportradar_id == "sr:competitor:11"
    assert verified.player_b_sportradar_id == "sr:competitor:22"
    assert verified.provider_observed_at == "2026-09-15T14:00:00+00:00"


def test_identity_rejects_swapped_canonical_orientation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, record = _provider_store(tmp_path)
    _mock_trusted_anchor(monkeypatch)
    with pytest.raises(ValueError, match="ascending frozen orientation"):
        identity.build_identity_binding(
            batch_store=store,
            batch_record_sha256=str(record["record_sha256"]),
            provider_anchor_comment_id=111222333,
            match_id="match-001",
            player_a_canonical_id="atp:id:2",
            player_b_canonical_id="atp:id:1",
            sportradar_event_id="sr:sport_event:123456",
            player_a_sportradar_id="sr:competitor:22",
            player_b_sportradar_id="sr:competitor:11",
        )


def test_identity_rejects_competitor_set_not_equal_to_provider_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, record = _provider_store(tmp_path)
    _mock_trusted_anchor(monkeypatch)
    with pytest.raises(ValueError, match="do not equal provider event competitors"):
        identity.build_identity_binding(
            batch_store=store,
            batch_record_sha256=str(record["record_sha256"]),
            provider_anchor_comment_id=111222333,
            match_id="match-001",
            player_a_canonical_id="atp:id:1",
            player_b_canonical_id="atp:id:2",
            sportradar_event_id="sr:sport_event:123456",
            player_a_sportradar_id="sr:competitor:11",
            player_b_sportradar_id="sr:competitor:999",
        )


def test_identity_rejects_post_start_provider_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, record = _provider_store(tmp_path, observed_hour=17)
    _mock_trusted_anchor(monkeypatch)
    with pytest.raises(ValueError, match="pre-match provider batch"):
        identity.build_identity_binding(
            batch_store=store,
            batch_record_sha256=str(record["record_sha256"]),
            provider_anchor_comment_id=111222333,
            match_id="match-001",
            player_a_canonical_id="atp:id:1",
            player_b_canonical_id="atp:id:2",
            sportradar_event_id="sr:sport_event:123456",
            player_a_sportradar_id="sr:competitor:11",
            player_b_sportradar_id="sr:competitor:22",
        )


def test_forged_self_hashed_identity_does_not_reproduce_from_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding, store = _build(tmp_path, monkeypatch)
    payload = identity.identity_as_dict(binding)
    payload["player_a_sportradar_name"] = "Forged Name"
    unsigned = dict(payload)
    unsigned.pop("artifact_sha256")
    canonical = json.dumps(
        unsigned,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()

    identity.verify_identity_binding(payload)
    with pytest.raises(ValueError, match="does not reproduce"):
        identity.authenticate_identity_binding(
            payload=payload,
            batch_store=store,
        )


def test_prediction_identity_must_be_retained_as_source_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding, _ = _build(tmp_path, monkeypatch)
    evidence_dir = tmp_path / "pilot-evidence"
    evidence_dir.mkdir()
    payload = identity.identity_as_dict(binding)
    payload_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload_bytes).hexdigest()
    (evidence_dir / digest).write_bytes(payload_bytes)

    class FakePilot:
        pass

    pilot = FakePilot()
    pilot.evidence_dir = evidence_dir
    prediction = {
        "match_id": "match-001",
        "tour": "ATP",
        "player_a_id": "atp:id:1",
        "player_b_id": "atp:id:2",
        "scheduled_start": "2026-09-15T16:00:00+00:00",
        "source_manifest_hashes": [digest],
    }
    found, source_sha, _ = identity.find_prediction_identity_binding(
        pilot_store=pilot,
        prediction=prediction,
    )
    assert found.artifact_sha256 == binding.artifact_sha256
    assert source_sha == digest

    prediction["source_manifest_hashes"] = []
    with pytest.raises(ValueError, match="exactly one matching"):
        identity.find_prediction_identity_binding(
            pilot_store=pilot,
            prediction=prediction,
        )
