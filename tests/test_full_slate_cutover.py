from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.prospective import full_slate_cutover as cutover
from tennis_genome.prospective.match_lifecycle import MatchLifecycleLedger

SOURCE_SHA = "f" * 64
PREDICTION_SHA = "d" * 64


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class _FakePilotStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def verify(self) -> dict[str, object]:
        return {
            "status": "VERIFIED",
            "prediction_count": 1,
            "chain_head_sha256": PREDICTION_SHA,
        }


def _valid_dry_run(tmp_path: Path) -> Path:
    root = tmp_path / "artifact"
    work = root / "forward-004-slate-work"
    execution_root = work / "execution"
    event_id = "sr:sport_event:1"
    stem = "sr-sport_event-1"

    _write(
        root / "forward-004-full-slate-run-mode.json",
        {
            "schema_version": "wta-forward-004-full-slate-run-mode-v1",
            "workflow_run_id": 123,
            "workflow_run_attempt": 1,
            "workflow_source_sha": SOURCE_SHA,
            "provider_run_id": 456,
            "publish_prospective_evidence": False,
        },
    )
    _write(
        work / "forward-004-slate-resolution.json",
        {
            "schema_version": "wta-forward-004-slate-resolution-v1",
            "eligible_target_count": 1,
            "targets": [
                {
                    "event_id": event_id,
                    "scheduled_start": "2026-09-19T18:00:00+00:00",
                }
            ],
        },
    )

    ledger = MatchLifecycleLedger(execution_root / "match-lifecycle-ledger")
    lifecycle_id = f"FULL-STACK-FORWARD-004-{event_id}"
    ledger.discover(
        lifecycle_id=lifecycle_id,
        match_id=event_id,
        provider_event_id=event_id,
        evidence_sha256=("a" * 64,),
    )
    ledger.advance(
        lifecycle_id=lifecycle_id,
        state="SNAPSHOT_CAPTURED",
        evidence_sha256=("b" * 64,),
    )
    ledger.advance(
        lifecycle_id=lifecycle_id,
        state="CHAMPION_PREDICTED",
        evidence_sha256=("c" * 64,),
    )
    audit = ledger.verify()

    _write(
        execution_root / "slate-execution-manifest.json",
        {
            "schema_version": "wta-forward-004-slate-execution-v1",
            "eligible_target_count": 1,
            "target_count": 1,
            "skipped_target_count": 0,
            "provider_unique_request_count": 3,
            "provider_cached_path_count": 3,
            "lifecycle_event_count": audit.event_count,
            "lifecycle_chain_head_sha256": audit.chain_head_sha256,
            "results": [
                {
                    "event_id": event_id,
                    "artifact_stem": stem,
                    "prediction_record_sha256": PREDICTION_SHA,
                    "chain_head_sha256": PREDICTION_SHA,
                }
            ],
            "skipped_targets": [],
        },
    )

    match_root = execution_root / "matches" / stem
    prediction_root = match_root / "prediction-work"
    _write(
        match_root / "forward-004-target-resolution.json",
        {"event_id": event_id},
    )
    _write(
        prediction_root / "prediction-dossier.json",
        {"target": {"event_id": event_id}},
    )
    _write(prediction_root / "matchup-input.json", {"match_id": event_id})
    _write(
        prediction_root / "calculation.json",
        {"prediction": {"p_player_a": 0.61, "p_player_b": 0.39}},
    )
    (prediction_root / "prospective-pilot-store").mkdir(parents=True, exist_ok=True)
    return root


def test_cutover_validator_accepts_complete_nonpublishing_dry_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _valid_dry_run(tmp_path)
    monkeypatch.setattr(cutover, "ProspectivePilotStore", _FakePilotStore)

    result = cutover.assess_full_slate_cutover(
        root,
        expected_source_sha=SOURCE_SHA,
    )

    assert result.status == "PASS"
    assert result.eligible_target_count == 1
    assert result.predicted_target_count == 1
    assert result.skipped_target_count == 0
    assert result.prediction_record_sha256 == (PREDICTION_SHA,)
    assert result.workflow_source_sha == SOURCE_SHA


def test_cutover_validator_rejects_publishing_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _valid_dry_run(tmp_path)
    monkeypatch.setattr(cutover, "ProspectivePilotStore", _FakePilotStore)
    receipt = json.loads(
        (root / "forward-004-full-slate-run-mode.json").read_text(encoding="utf-8")
    )
    receipt["publish_prospective_evidence"] = True
    _write(root / "forward-004-full-slate-run-mode.json", receipt)

    with pytest.raises(ValueError, match="nonpublishing dry run"):
        cutover.assess_full_slate_cutover(root, expected_source_sha=SOURCE_SHA)


def test_cutover_validator_rejects_stale_candidate_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _valid_dry_run(tmp_path)
    monkeypatch.setattr(cutover, "ProspectivePilotStore", _FakePilotStore)

    with pytest.raises(ValueError, match="candidate SHA"):
        cutover.assess_full_slate_cutover(
            root,
            expected_source_sha="e" * 64,
        )


def test_cutover_validator_rejects_broken_denominator_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _valid_dry_run(tmp_path)
    monkeypatch.setattr(cutover, "ProspectivePilotStore", _FakePilotStore)
    execution_path = (
        root
        / "forward-004-slate-work"
        / "execution"
        / "slate-execution-manifest.json"
    )
    execution = json.loads(execution_path.read_text(encoding="utf-8"))
    execution["skipped_target_count"] = 1
    execution["skipped_targets"] = [
        {
            "event_id": "sr:sport_event:2",
            "skip_reason": "SCHEDULED_START_REACHED",
        }
    ]
    _write(execution_path, execution)

    with pytest.raises(ValueError, match="predicted \+ skipped"):
        cutover.assess_full_slate_cutover(root, expected_source_sha=SOURCE_SHA)
