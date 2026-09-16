from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.verify_live_shadow_anchors import verify_live_shadow_anchors

START = datetime(2026, 9, 16, 19, 0, tzinfo=UTC)


def _write_anchor_fixture(root: Path) -> tuple[int, str]:
    anchors = root / "anchors"
    anchors.mkdir(parents=True)
    comment_id = 5702468464
    body = "<!-- TENNIS-GENOME-CHALLENGER-SHADOW-ANCHOR-V1 -->\n{}"
    retained = {
        "id": comment_id,
        "body": body,
        "user": {"login": "github-actions[bot]"},
        "created_at": "2026-09-16T18:24:42Z",
        "updated_at": "2026-09-16T18:24:42Z",
        "issue_url": "https://api.github.com/repos/AidanDCM/Tennis-Genome-/issues/139",
    }
    (anchors / "request-01.comment.json").write_text(
        json.dumps(retained), encoding="utf-8"
    )
    (anchors / "request-01.comment.md").write_text(body, encoding="utf-8")
    (anchors / "request-01.comment.json.receipt.json").write_text(
        json.dumps(
            {
                "comment_id": comment_id,
                "scheduled_start": START.isoformat().replace("+00:00", "Z"),
            }
        ),
        encoding="utf-8",
    )
    return comment_id, body


def _live(comment_id: int, body: str) -> dict[str, object]:
    return {
        "id": comment_id,
        "body": body,
        "user": {"login": "github-actions[bot]"},
        "created_at": "2026-09-16T18:24:42Z",
        "updated_at": "2026-09-16T18:24:42Z",
        "issue_url": "https://api.github.com/repos/AidanDCM/Tennis-Genome-/issues/139",
    }


def test_live_shadow_anchor_revalidation_accepts_exact_unedited_bot_comment(
    tmp_path: Path,
) -> None:
    comment_id, body = _write_anchor_fixture(tmp_path)

    result = verify_live_shadow_anchors(
        shadow_root=tmp_path,
        repository="AidanDCM/Tennis-Genome-",
        output_dir=tmp_path / "verified",
        fetch_comment=lambda _repo, _comment_id: _live(comment_id, body),
    )

    assert result == (comment_id,)
    assert (tmp_path / "verified" / f"{comment_id}.json").is_file()


def test_live_shadow_anchor_revalidation_rejects_edited_or_wrong_author(
    tmp_path: Path,
) -> None:
    comment_id, body = _write_anchor_fixture(tmp_path)
    edited = _live(comment_id, body)
    edited["updated_at"] = "2026-09-16T18:25:00Z"
    with pytest.raises(ValueError, match="has been edited"):
        verify_live_shadow_anchors(
            shadow_root=tmp_path,
            repository="AidanDCM/Tennis-Genome-",
            output_dir=tmp_path / "edited",
            fetch_comment=lambda _repo, _comment_id: edited,
        )

    wrong_author = _live(comment_id, body)
    wrong_author["user"] = {"login": "AidanDCM"}
    with pytest.raises(ValueError, match="not authored by github-actions"):
        verify_live_shadow_anchors(
            shadow_root=tmp_path,
            repository="AidanDCM/Tennis-Genome-",
            output_dir=tmp_path / "wrong-author",
            fetch_comment=lambda _repo, _comment_id: wrong_author,
        )


def test_live_shadow_anchor_revalidation_rejects_late_wrong_ledger_or_body(
    tmp_path: Path,
) -> None:
    comment_id, body = _write_anchor_fixture(tmp_path)

    late = _live(comment_id, body)
    late["created_at"] = "2026-09-16T19:00:00Z"
    late["updated_at"] = "2026-09-16T19:00:00Z"
    with pytest.raises(ValueError, match="not pre-start"):
        verify_live_shadow_anchors(
            shadow_root=tmp_path,
            repository="AidanDCM/Tennis-Genome-",
            output_dir=tmp_path / "late",
            fetch_comment=lambda _repo, _comment_id: late,
        )

    wrong_ledger = _live(comment_id, body)
    wrong_ledger["issue_url"] = (
        "https://api.github.com/repos/AidanDCM/Tennis-Genome-/issues/999"
    )
    with pytest.raises(ValueError, match="canonical prediction ledger"):
        verify_live_shadow_anchors(
            shadow_root=tmp_path,
            repository="AidanDCM/Tennis-Genome-",
            output_dir=tmp_path / "wrong-ledger",
            fetch_comment=lambda _repo, _comment_id: wrong_ledger,
        )

    changed_body = _live(comment_id, body + "\nchanged")
    with pytest.raises(ValueError, match="body mismatch"):
        verify_live_shadow_anchors(
            shadow_root=tmp_path,
            repository="AidanDCM/Tennis-Genome-",
            output_dir=tmp_path / "changed-body",
            fetch_comment=lambda _repo, _comment_id: changed_body,
        )
