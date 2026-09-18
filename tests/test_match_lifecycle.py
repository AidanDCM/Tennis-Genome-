from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.prospective.match_lifecycle import MatchLifecycleLedger

BASE = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


class _Clock:
    def __init__(self) -> None:
        self.value = BASE

    def __call__(self) -> datetime:
        current = self.value
        self.value += timedelta(seconds=1)
        return current


def _ledger(tmp_path: Path) -> MatchLifecycleLedger:
    return MatchLifecycleLedger(tmp_path / "match-lifecycle", now=_Clock())


def test_match_lifecycle_supports_interleaved_full_slate_progression(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    ledger.discover(
        lifecycle_id="match-1",
        match_id="canonical:1",
        provider_event_id="sr:sport_event:1",
        evidence_sha256=(SHA_A,),
    )
    ledger.discover(
        lifecycle_id="match-2",
        match_id="canonical:2",
        provider_event_id="sr:sport_event:2",
        evidence_sha256=(SHA_B,),
    )
    ledger.advance(
        lifecycle_id="match-2",
        state="SNAPSHOT_CAPTURED",
        evidence_sha256=(SHA_C,),
    )
    ledger.advance(
        lifecycle_id="match-1",
        state="SNAPSHOT_CAPTURED",
        evidence_sha256=(SHA_B,),
    )

    report = ledger.verify()
    assert report.status == "PASS"
    assert report.lifecycle_count == 2
    assert report.event_count == 4
    assert report.lifecycle_states == {
        "match-1": "SNAPSHOT_CAPTURED",
        "match-2": "SNAPSHOT_CAPTURED",
    }


def test_match_lifecycle_requires_exact_next_state(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.discover(
        lifecycle_id="match-1",
        match_id="canonical:1",
        provider_event_id="sr:sport_event:1",
        evidence_sha256=(SHA_A,),
    )

    with pytest.raises(ValueError, match="illegal match lifecycle transition"):
        ledger.advance(
            lifecycle_id="match-1",
            state="CHAMPION_PREDICTED",
            evidence_sha256=(SHA_B,),
        )

    report = ledger.verify()
    assert report.event_count == 1
    assert report.lifecycle_states["match-1"] == "DISCOVERED"


def test_match_lifecycle_rejects_duplicate_match_or_provider_identity(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.discover(
        lifecycle_id="match-1",
        match_id="canonical:1",
        provider_event_id="sr:sport_event:1",
        evidence_sha256=(SHA_A,),
    )

    with pytest.raises(ValueError, match="match_id is already bound"):
        ledger.discover(
            lifecycle_id="match-2",
            match_id="canonical:1",
            provider_event_id="sr:sport_event:2",
            evidence_sha256=(SHA_B,),
        )

    with pytest.raises(ValueError, match="provider_event_id is already bound"):
        ledger.discover(
            lifecycle_id="match-3",
            match_id="canonical:3",
            provider_event_id="sr:sport_event:1",
            evidence_sha256=(SHA_C,),
        )


def test_match_lifecycle_detects_retained_event_tampering(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.discover(
        lifecycle_id="match-1",
        match_id="canonical:1",
        provider_event_id="sr:sport_event:1",
        evidence_sha256=(SHA_A,),
    )

    path = next((tmp_path / "match-lifecycle" / "events").glob("*.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["event"]["match_id"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="match lifecycle digest mismatch"):
        ledger.verify()


def test_match_lifecycle_requires_lowercase_sha256_evidence(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        ledger.discover(
            lifecycle_id="match-1",
            match_id="canonical:1",
            provider_event_id="sr:sport_event:1",
            evidence_sha256=("A" * 64,),
        )

    assert ledger.verify().status == "EMPTY"


def test_match_lifecycle_can_reach_validated_terminal_state(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.discover(
        lifecycle_id="match-1",
        match_id="canonical:1",
        provider_event_id="sr:sport_event:1",
        evidence_sha256=(SHA_A,),
    )

    states = (
        "SNAPSHOT_CAPTURED",
        "CHAMPION_PREDICTED",
        "CHAMPION_ANCHORED",
        "CHALLENGERS_PREDICTED",
        "CHALLENGERS_ANCHORED",
        "RESULT_CAPTURED",
        "SETTLED",
        "SCORED",
        "VALIDATED",
    )
    for state in states:
        ledger.advance(
            lifecycle_id="match-1",
            state=state,
            evidence_sha256=(SHA_B,),
        )

    report = ledger.verify()
    assert report.validated_count == 1
    assert report.lifecycle_states["match-1"] == "VALIDATED"

    with pytest.raises(ValueError, match="validated match lifecycle cannot advance"):
        ledger.advance(
            lifecycle_id="match-1",
            state="VALIDATED",
            evidence_sha256=(SHA_C,),
        )
