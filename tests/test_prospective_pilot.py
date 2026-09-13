from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from tennis_genome.prospective import pilot


class _FakeCalculation:
    production_bundle_sha256 = "7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1"
    assessment_status = "DIAGNOSTIC_ONLY_NO_HARD_PASS"

    def __init__(self) -> None:
        self.prediction = SimpleNamespace(
            p_player_a=0.61,
            p_player_b=0.39,
            component_probabilities={"strict_core_v1": 0.59},
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "prediction": {
                "p_player_a": 0.61,
                "p_player_b": 0.39,
                "component_probabilities": {"strict_core_v1": 0.59},
            },
            "production_bundle_sha256": self.production_bundle_sha256,
            "assessment_status": self.assessment_status,
        }


class _FakeCalculator:
    def __init__(self) -> None:
        self.bundle = SimpleNamespace(
            atp=SimpleNamespace(neighbor_bank=SimpleNamespace(sha256="a" * 64)),
            wta=SimpleNamespace(neighbor_bank=SimpleNamespace(sha256="b" * 64)),
        )

    def calculate(self, matchup: object) -> _FakeCalculation:
        del matchup
        return _FakeCalculation()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _patch_calculation_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source_sha: str,
) -> None:
    matchup = SimpleNamespace(
        prediction_id="pilot-pred-1",
        match_id="pilot-match-1",
        tour="ATP",
        player_a_id="canonical-a",
        player_b_id="canonical-b",
        created_at=datetime(2026, 9, 13, 15, 59, tzinfo=UTC),
        prediction_cutoff_at=datetime(2026, 9, 13, 15, 58, tzinfo=UTC),
        source_manifest_hashes=(source_sha,),
    )
    monkeypatch.setattr(pilot, "load_validated_matchup_calculator", lambda path: _FakeCalculator())
    monkeypatch.setattr(pilot, "load_matchup_input", lambda path: matchup)
    monkeypatch.setattr(
        pilot,
        "runtime_manifest",
        lambda: {
            "python_implementation": "CPython",
            "python_version": "3.11.16",
            "packages": {"numpy": "2.4.6"},
            "source_tree_sha256": "c" * 64,
        },
    )


def _commit_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[pilot.ProspectivePilotStore, dict[str, object]]:
    input_path = tmp_path / "input.json"
    input_path.write_text("{}\n")
    source_path = tmp_path / "source.json"
    source_path.write_text('{"captured":"pre-match"}\n')
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text('{"scheduled_start":"2026-09-13T17:00:00+00:00"}\n')
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text('{"sealed":"production"}\n')
    _patch_calculation_path(monkeypatch, source_sha=_sha(source_path))
    store = pilot.ProspectivePilotStore(tmp_path / "store")
    record = pilot.commit_prediction(
        store=store,
        bundle_path=bundle_path,
        input_path=input_path,
        scheduled_start="2026-09-13T17:00:00+00:00",
        source_evidence_paths=[source_path],
        schedule_evidence_path=schedule_path,
        now=lambda: datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
    )
    return store, record


def _anchor_files(
    tmp_path: Path,
    prediction: dict[str, object],
    *,
    created_at: str = "2026-09-13T16:05:00+00:00",
) -> tuple[Path, Path]:
    run_id = 123456789
    receipt = {
        "schema_version": "full-stack-pilot-github-anchor-v1",
        "provider": "GITHUB_ACTIONS",
        "repository": "AidanDCM/Tennis-Genome-",
        "workflow_source_sha": "d" * 40,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/AidanDCM/Tennis-Genome-/actions/runs/{run_id}",
        "prediction_record_sha256": prediction["record_sha256"],
        "chain_head_sha256": prediction["record_sha256"],
        "runner_receipt_created_at_utc": created_at,
    }
    run = {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/prospective_evidence_anchor.yml",
        "head_sha": "d" * 40,
        "created_at": created_at,
        "repository": {"full_name": "AidanDCM/Tennis-Genome-"},
    }
    receipt_path = tmp_path / "anchor.json"
    run_path = tmp_path / "run.json"
    receipt_path.write_text(json.dumps(receipt) + "\n")
    run_path.write_text(json.dumps(run) + "\n")
    return receipt_path, run_path


def _attest_anchor(
    tmp_path: Path,
    store: pilot.ProspectivePilotStore,
    prediction: dict[str, object],
    *,
    created_at: str = "2026-09-13T16:05:00+00:00",
) -> dict[str, object]:
    receipt_path, run_path = _anchor_files(tmp_path, prediction, created_at=created_at)
    return pilot.attest_anchor(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        anchor_receipt_path=receipt_path,
        github_run_metadata_path=run_path,
    )


def _settlement_file(
    tmp_path: Path,
    prediction: dict[str, object],
    *,
    winner: str = "a",
    reason: str | None = None,
    actual_start: str = "2026-09-13T17:01:00+00:00",
    asserted: dict[str, object] | None = None,
) -> Path:
    winner_id = "sr:competitor:a" if winner == "a" else "sr:competitor:b"
    status: dict[str, object] = {"status": "ended", "winner_id": winner_id}
    if reason is not None:
        status["winning_reason"] = reason
    raw: dict[str, object] = {
        "schema_version": "full-stack-pilot-sportradar-settlement-v1",
        "match_id": prediction["match_id"],
        "sportradar_event_id": "sr:sport_event:pilot-1",
        "player_a_canonical_id": prediction["player_a_id"],
        "player_b_canonical_id": prediction["player_b_id"],
        "player_a_sportradar_id": "sr:competitor:a",
        "player_b_sportradar_id": "sr:competitor:b",
        "observed_at": "2026-09-13T18:00:00+00:00",
        "sportradar_timeline": {
            "sport_event": {"id": "sr:sport_event:pilot-1"},
            "sport_event_status": status,
            "timeline": [{"id": 1, "type": "match_started", "time": actual_start}],
        },
    }
    if asserted:
        raw.update(asserted)
    target = tmp_path / f"settlement-{winner}-{reason or 'completed'}.json"
    target.write_text(json.dumps(raw) + "\n")
    return target


def test_prediction_commit_is_hash_chained_and_retains_exact_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, record = _commit_fixture(tmp_path, monkeypatch)

    report = store.verify()
    assert report["status"] == "VERIFIED"
    assert report["prediction_count"] == 1
    assert report["settlement_count"] == 0
    assert report["chain_head_sha256"] == record["record_sha256"]
    assert record["previous_record_sha256"] == "0" * 64
    assert record["final_probability_a"] == pytest.approx(0.61)
    assert record["strict_core_probability_a"] == pytest.approx(0.59)
    for evidence_sha in record["evidence_sha256"]:
        assert (store.evidence_dir / evidence_sha).is_file()


def test_pilot_rejects_duplicate_official_prediction_for_same_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = _commit_fixture(tmp_path, monkeypatch)
    input_path = tmp_path / "input.json"
    source_path = tmp_path / "source.json"
    schedule_path = tmp_path / "schedule.json"
    bundle_path = tmp_path / "bundle.json"

    with pytest.raises(ValueError, match="only one committed prediction"):
        pilot.commit_prediction(
            store=store,
            bundle_path=bundle_path,
            input_path=input_path,
            scheduled_start="2026-09-13T17:00:00+00:00",
            source_evidence_paths=[source_path],
            schedule_evidence_path=schedule_path,
            now=lambda: datetime(2026, 9, 13, 16, 1, tzinfo=UTC),
        )


def test_settlement_is_separate_and_derives_primary_timing_eligibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(tmp_path, store, prediction)
    settlement_source = _settlement_file(tmp_path, prediction, winner="a")

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=settlement_source,
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["winner_player_id"] == "canonical-a"
    assert settlement["finish_status"] == "COMPLETED"
    assert settlement["timing_status"] == "PRE_START_VERIFIED"
    assert settlement["anchor_status"] == "PRE_START_ANCHORED"
    assert settlement["primary_evaluation_eligible"] is True
    report = store.verify()
    assert report["record_count"] == 3
    assert report["anchor_count"] == 1
    assert report["settlement_count"] == 1


def test_late_commit_is_preserved_but_not_primary_evaluation_eligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    settlement_source = _settlement_file(
        tmp_path,
        prediction,
        winner="b",
        actual_start="2026-09-13T15:59:30+00:00",
    )

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=settlement_source,
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["timing_status"] == "COMMIT_NOT_PRE_START"
    assert settlement["anchor_status"] == "ANCHOR_MISSING"
    assert settlement["primary_evaluation_eligible"] is False
    assert store.verify()["status"] == "VERIFIED"


def test_store_detects_record_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = _commit_fixture(tmp_path, monkeypatch)
    record_path = next(store.records_dir.glob("*.json"))
    payload = json.loads(record_path.read_text())
    payload["final_probability_a"] = 0.90
    record_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="record digest mismatch"):
        store.verify()


def test_recovery_removes_only_interrupted_temp_and_lock_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    (store.records_dir / "orphan.tmp").write_text("partial")
    store.lock_path.write_text("stale\n")

    report = store.recover()

    assert report["status"] == "VERIFIED"
    assert report["chain_head_sha256"] == prediction["record_sha256"]
    assert "records/orphan.tmp" in report["recovery_removed"]
    assert ".write.lock" in report["recovery_removed"]


def test_missing_anchor_excludes_otherwise_valid_completed_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(tmp_path, prediction),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["timing_status"] == "PRE_START_VERIFIED"
    assert settlement["anchor_status"] == "ANCHOR_MISSING"
    assert settlement["primary_evaluation_eligible"] is False


def test_late_anchor_is_retained_but_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(
        tmp_path,
        store,
        prediction,
        created_at="2026-09-13T17:02:00+00:00",
    )
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(tmp_path, prediction),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["anchor_status"] == "ANCHOR_NOT_PRE_START"
    assert settlement["primary_evaluation_eligible"] is False


def test_anchor_receipt_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    receipt_path, run_path = _anchor_files(tmp_path, prediction)
    receipt = json.loads(receipt_path.read_text())
    receipt["prediction_record_sha256"] = "f" * 64
    receipt_path.write_text(json.dumps(receipt) + "\n")
    with pytest.raises(ValueError, match="prediction SHA"):
        pilot.attest_anchor(
            store=store,
            prediction_record_sha256=str(prediction["record_sha256"]),
            anchor_receipt_path=receipt_path,
            github_run_metadata_path=run_path,
        )


def test_settlement_rejects_operator_asserted_outcome_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(tmp_path, store, prediction)
    evidence = _settlement_file(
        tmp_path,
        prediction,
        asserted={"winner_player_id": "canonical-b", "finish_status": "COMPLETED"},
    )
    with pytest.raises(ValueError, match="provider evidence"):
        pilot.settle_prediction(
            store=store,
            prediction_record_sha256=str(prediction["record_sha256"]),
            settlement_evidence_path=evidence,
            now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
        )


def test_provider_retirement_is_derived_from_retained_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(tmp_path, store, prediction)
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(
            tmp_path, prediction, winner="b", reason="retirement"
        ),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["winner_player_id"] == "canonical-b"
    assert settlement["finish_status"] == "RETIREMENT"
    assert settlement["primary_evaluation_eligible"] is False


def test_recovery_paths_are_posix_portable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, _ = _commit_fixture(tmp_path, monkeypatch)
    (store.records_dir / "orphan.tmp").write_text("partial")
    report = store.recover()
    assert all("\\" not in item for item in report["recovery_removed"])
