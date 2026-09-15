from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.prospective import prediction_anchor_live as live
from tennis_genome.prospective.prediction_anchor_github import (
    ANCHOR_LEDGER_ISSUE,
    ANCHOR_REPOSITORY,
    ANCHOR_SCHEMA,
    ANCHOR_WORKFLOW_BLOB_SHA,
    ANCHOR_WORKFLOW_PATH,
    TRUSTED_ANCHOR_SCHEMA,
    TRUSTED_ANCHOR_VERSION,
    build_anchor_comment_body,
)


class _FakePilotStore:
    def __init__(self) -> None:
        self.prediction = {
            "record_type": "PREDICTION_COMMIT",
            "record_sha256": "a" * 64,
            "prediction_id": "prediction-001",
            "match_id": "match-001",
            "tour": "ATP",
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


def _receipt() -> dict[str, object]:
    run_id = 123456789
    return {
        "schema_version": ANCHOR_SCHEMA,
        "trusted_prediction_anchor_schema": TRUSTED_ANCHOR_SCHEMA,
        "provider": "GITHUB_ACTIONS",
        "repository": ANCHOR_REPOSITORY,
        "prediction_anchor_ledger_issue": ANCHOR_LEDGER_ISSUE,
        "prediction_anchor_workflow_version": TRUSTED_ANCHOR_VERSION,
        "workflow_source_sha": "d" * 40,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": (
            f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
        ),
        "prediction_record_sha256": "a" * 64,
        "chain_head_sha256": "a" * 64,
        "runner_receipt_created_at_utc": "2026-09-15T14:00:30+00:00",
    }


def _comment() -> dict[str, object]:
    comment_id = 987654321
    return {
        "id": comment_id,
        "url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/comments/"
            f"{comment_id}"
        ),
        "issue_url": (
            f"https://api.github.com/repos/{ANCHOR_REPOSITORY}/issues/"
            f"{ANCHOR_LEDGER_ISSUE}"
        ),
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "created_at": "2026-09-15T14:00:31Z",
        "updated_at": "2026-09-15T14:00:31Z",
        "body": build_anchor_comment_body(_receipt()),
    }


def _run() -> dict[str, object]:
    receipt = _receipt()
    run_id = int(receipt["workflow_run_id"])
    return {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ANCHOR_WORKFLOW_PATH,
        "head_branch": "main",
        "head_sha": receipt["workflow_source_sha"],
        "run_attempt": 1,
        "created_at": "2026-09-15T14:00:00Z",
        "html_url": f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}",
        "repository": {"full_name": ANCHOR_REPOSITORY},
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True).encode("utf-8")


def _get_bytes(*, source_blob: str = ANCHOR_WORKFLOW_BLOB_SHA):
    def get_bytes(url: str) -> bytes:
        if "/issues/comments/" in url:
            return _json_bytes(_comment())
        if "/actions/runs/" in url:
            return _json_bytes(_run())
        if "/contents/" in url:
            return _json_bytes(
                {
                    "type": "file",
                    "path": ANCHOR_WORKFLOW_PATH,
                    "sha": source_blob,
                }
            )
        raise AssertionError(f"unexpected URL: {url}")

    return get_bytes


def _patch_attest(monkeypatch: pytest.MonkeyPatch, pilot: _FakePilotStore) -> None:
    def fake_attest_anchor(**kwargs):
        assert kwargs["prediction_record_sha256"] == "a" * 64
        record = {
            "record_type": "ANCHOR_ATTESTATION",
            "record_sha256": "b" * 64,
            "prediction_record_sha256": "a" * 64,
            "workflow_run_id": 123456789,
            "anchor_created_at": "2026-09-15T14:00:31+00:00",
        }
        pilot._records.append(record)
        return dict(record)

    monkeypatch.setattr(live, "attest_anchor", fake_attest_anchor)


def test_live_attestation_retains_server_evidence_and_revalidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore()
    _patch_attest(monkeypatch, pilot)
    store = live.LivePredictionAnchorStore(tmp_path / "live")

    record = live.attest_live_prediction_anchor(
        pilot_store=pilot,  # type: ignore[arg-type]
        live_store=store,
        prediction_record_sha256="a" * 64,
        github_comment_id=987654321,
        github_get_bytes=_get_bytes(),
    )

    assert record["anchor_evidence_mode"] == live.LIVE_PREDICTION_ANCHOR_MODE
    assert record["github_comment_id"] == 987654321
    report = store.verify(
        pilot_store=pilot,  # type: ignore[arg-type]
        github_get_bytes=_get_bytes(),
    )
    assert report["status"] == "LIVE_VERIFIED"
    assert report["trusted_prediction_count"] == 1
    assert report["promotion_eligible_settlement_count"] == 0


def test_retained_replay_requires_no_live_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore()
    _patch_attest(monkeypatch, pilot)
    store = live.LivePredictionAnchorStore(tmp_path / "live")
    live.attest_live_prediction_anchor(
        pilot_store=pilot,  # type: ignore[arg-type]
        live_store=store,
        prediction_record_sha256="a" * 64,
        github_comment_id=987654321,
        github_get_bytes=_get_bytes(),
    )

    report = store.verify(
        pilot_store=pilot,  # type: ignore[arg-type]
        revalidate_live=False,
    )
    assert report["status"] == "RETAINED_VERIFIED"


def test_later_workflow_source_drift_fails_live_reverification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pilot = _FakePilotStore()
    _patch_attest(monkeypatch, pilot)
    store = live.LivePredictionAnchorStore(tmp_path / "live")
    live.attest_live_prediction_anchor(
        pilot_store=pilot,  # type: ignore[arg-type]
        live_store=store,
        prediction_record_sha256="a" * 64,
        github_comment_id=987654321,
        github_get_bytes=_get_bytes(),
    )

    with pytest.raises(ValueError, match="frozen blob"):
        store.verify(
            pilot_store=pilot,  # type: ignore[arg-type]
            github_get_bytes=_get_bytes(source_blob="f" * 40),
        )


def test_primary_settlement_without_live_anchor_is_not_promotion_capable(
    tmp_path: Path,
) -> None:
    pilot = _FakePilotStore()
    pilot._records.extend(
        [
            {
                "record_type": "ANCHOR_ATTESTATION",
                "record_sha256": "b" * 64,
                "prediction_record_sha256": "a" * 64,
                "workflow_run_id": 123456789,
                "anchor_created_at": "2026-09-15T14:00:31+00:00",
            },
            {
                "record_type": "SETTLEMENT",
                "record_sha256": "c" * 64,
                "prediction_record_sha256": "a" * 64,
                "primary_evaluation_eligible": True,
            },
        ]
    )
    store = live.LivePredictionAnchorStore(tmp_path / "live")

    with pytest.raises(ValueError, match="lacks trusted live prediction anchor"):
        store.verify(
            pilot_store=pilot,  # type: ignore[arg-type]
            revalidate_live=False,
        )
