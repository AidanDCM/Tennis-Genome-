from __future__ import annotations

import copy

import pytest

from tennis_genome.prospective.pilot_anchor_packet import (
    INPUT_FIELDS,
    WORKFLOW_PATH,
    build_prediction_anchor_packet,
)


class _FakeStore:
    def __init__(self, records: list[dict[str, object]], chain_head: str) -> None:
        self._records = records
        self._chain_head = chain_head

    def verify(self) -> dict[str, object]:
        return {
            "status": "VERIFIED",
            "record_count": len(self._records),
            "chain_head_sha256": self._chain_head,
        }

    def records(self) -> list[dict[str, object]]:
        return copy.deepcopy(self._records)


def _prediction(sha: str = "a" * 64) -> dict[str, object]:
    return {
        "record_type": "PREDICTION_COMMIT",
        "record_sha256": sha,
        "sequence": 1,
        "prediction_id": "prediction-001",
        "match_id": "match-001",
        "tour": "ATP",
    }


def test_packet_matches_exact_installed_workflow_input_contract() -> None:
    record = _prediction()
    store = _FakeStore([record], str(record["record_sha256"]))

    packet = build_prediction_anchor_packet(store=store)  # type: ignore[arg-type]

    assert packet["workflow_path"] == WORKFLOW_PATH
    assert tuple(packet["inputs"]) == INPUT_FIELDS
    assert packet["inputs"] == {
        "prediction_record_sha256": "a" * 64,
        "chain_head_sha256": "a" * 64,
    }
    assert len(str(packet["packet_sha256"])) == 64


def test_packet_is_deterministic_for_same_verified_head() -> None:
    record = _prediction()
    store = _FakeStore([record], str(record["record_sha256"]))

    first = build_prediction_anchor_packet(store=store)  # type: ignore[arg-type]
    second = build_prediction_anchor_packet(store=store)  # type: ignore[arg-type]

    assert first == second


def test_packet_rejects_prediction_that_is_no_longer_chain_head() -> None:
    record = _prediction()
    later = {
        "record_type": "ANCHOR_ATTESTATION",
        "record_sha256": "b" * 64,
        "sequence": 2,
    }
    store = _FakeStore([record, later], "b" * 64)

    with pytest.raises(ValueError, match="current ledger-head prediction"):
        build_prediction_anchor_packet(  # type: ignore[arg-type]
            store=store,
            prediction_record_sha256="a" * 64,
        )


def test_packet_rejects_non_prediction_current_head() -> None:
    record = {
        "record_type": "SETTLEMENT",
        "record_sha256": "b" * 64,
        "sequence": 1,
    }
    store = _FakeStore([record], "b" * 64)

    with pytest.raises(ValueError, match="PREDICTION_COMMIT"):
        build_prediction_anchor_packet(store=store)  # type: ignore[arg-type]


def test_packet_rejects_malformed_sha_and_missing_store() -> None:
    record = _prediction("not-a-sha")
    store = _FakeStore([record], "not-a-sha")
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        build_prediction_anchor_packet(store=store)  # type: ignore[arg-type]

    empty = _FakeStore([], "0" * 64)
    with pytest.raises(ValueError, match="no retained records"):
        build_prediction_anchor_packet(store=empty)  # type: ignore[arg-type]


def test_requested_sha_must_resolve_exactly_once() -> None:
    record = _prediction()
    store = _FakeStore([record], "a" * 64)

    with pytest.raises(ValueError, match="not found exactly once"):
        build_prediction_anchor_packet(  # type: ignore[arg-type]
            store=store,
            prediction_record_sha256="c" * 64,
        )
