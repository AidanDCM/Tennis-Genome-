from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections.abc import Callable
from datetime import datetime
from pathlib import Path


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def fetch_github_comment(*, repository: str, comment_id: int, token: str) -> dict[str, object]:
    url = f"https://api.github.com/repos/{repository}/issues/comments/{comment_id}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tennis-genome-shadow-verifier",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ValueError("GitHub comment response must be one JSON object")
    return value


def verify_live_shadow_anchors(
    *,
    shadow_root: Path,
    repository: str,
    output_dir: Path,
    fetch_comment: Callable[[str, int], dict[str, object]],
    expected_issue_number: int = 139,
) -> tuple[int, ...]:
    receipts = sorted((shadow_root / "anchors").glob("*.comment.json.receipt.json"))
    if not receipts:
        raise ValueError("shadow artifact contains no anchor receipts")
    output_dir.mkdir(parents=True, exist_ok=True)
    verified: list[int] = []
    for receipt_path in receipts:
        receipt = _load_object(receipt_path)
        comment_id = int(receipt["comment_id"])
        if comment_id <= 0:
            raise ValueError("shadow anchor comment ID must be positive")
        base = Path(str(receipt_path)[: -len(".comment.json.receipt.json")])
        retained_comment = _load_object(Path(f"{base}.comment.json"))
        retained_body = Path(f"{base}.comment.md").read_text(encoding="utf-8")
        live = fetch_comment(repository, comment_id)
        if int(live["id"]) != comment_id or int(retained_comment["id"]) != comment_id:
            raise ValueError("live/retained shadow anchor comment ID mismatch")
        user = live.get("user")
        if not isinstance(user, dict) or user.get("login") != "github-actions[bot]":
            raise ValueError("shadow anchor is not authored by github-actions[bot]")
        if live.get("created_at") != live.get("updated_at"):
            raise ValueError("shadow anchor has been edited")
        if live.get("body") != retained_body or retained_comment.get("body") != retained_body:
            raise ValueError("live/retained shadow anchor body mismatch")
        if not str(live.get("issue_url", "")).endswith(
            f"/issues/{expected_issue_number}"
        ):
            raise ValueError("shadow anchor is not on the canonical prediction ledger")
        created = datetime.fromisoformat(str(live["created_at"]).replace("Z", "+00:00"))
        scheduled = datetime.fromisoformat(
            str(receipt["scheduled_start"]).replace("Z", "+00:00")
        )
        if created >= scheduled:
            raise ValueError("shadow anchor is not pre-start")
        (output_dir / f"{comment_id}.json").write_text(
            json.dumps(live, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verified.append(comment_id)
    return tuple(sorted(verified))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Revalidate live GitHub shadow anchors")
    parser.add_argument("--shadow-root", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--issue-number", type=int, default=139)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN is required")

    def _fetch(repository: str, comment_id: int) -> dict[str, object]:
        return fetch_github_comment(
            repository=repository,
            comment_id=comment_id,
            token=token,
        )

    verified = verify_live_shadow_anchors(
        shadow_root=args.shadow_root,
        repository=args.repository,
        output_dir=args.output_dir,
        fetch_comment=_fetch,
        expected_issue_number=args.issue_number,
    )
    print(json.dumps({"verified_comment_ids": list(verified)}, sort_keys=True))


if __name__ == "__main__":
    main()
