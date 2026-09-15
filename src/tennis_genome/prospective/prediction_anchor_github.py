from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

ANCHOR_SCHEMA = "full-stack-pilot-github-anchor-v1"
TRUSTED_ANCHOR_SCHEMA = "full-stack-pilot-trusted-github-anchor-v1"
TRUSTED_ANCHOR_VERSION = "FULL-STACK-PILOT-001-live-anchor-v1"
ANCHOR_COMMENT_MARKER = "<!-- FULL-STACK-PILOT-001-PREDICTION-ANCHOR-V1 -->"
ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"
ANCHOR_LEDGER_ISSUE = 119
ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_evidence_anchor.yml"
ANCHOR_WORKFLOW_BLOB_SHA = "fd2663eaaf6240ef0584df08498683b6f21970e2"
ANCHOR_BOT_LOGIN = "github-actions[bot]"
_GITHUB_API = "https://api.github.com"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_COMMENT_AFTER_RECEIPT = timedelta(minutes=10)

GitHubGetBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class LivePredictionAnchorEvidence:
    comment_id: int
    workflow_run_id: int
    anchor_created_at: datetime
    receipt: dict[str, object]
    comment_response_bytes: bytes
    workflow_run_response_bytes: bytes
    comment_response_sha256: str
    workflow_run_response_sha256: str
    workflow_source_sha: str


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def build_anchor_comment_body(receipt: dict[str, object]) -> str:
    return f"{ANCHOR_COMMENT_MARKER}\n```json\n{_canonical_json(receipt)}\n```"


def _strict_json_object(content: bytes, *, label: str) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _parse_time(value: object, *, field: str) -> datetime:
    text = str(value if value is not None else "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(UTC)


def _require_sha256(value: object, *, field: str) -> str:
    text = str(value if value is not None else "").strip()
    if not _SHA256_RE.fullmatch(text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _parse_comment_body(body: object) -> dict[str, object]:
    text = str(body if body is not None else "")
    prefix = f"{ANCHOR_COMMENT_MARKER}\n```json\n"
    suffix = "\n```"
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise ValueError("GitHub prediction anchor comment does not match frozen format")
    canonical = text[len(prefix) : -len(suffix)]
    try:
        receipt = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub prediction anchor comment contains invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("GitHub prediction anchor receipt must be an object")
    if canonical != _canonical_json(receipt):
        raise ValueError("GitHub prediction anchor receipt is not canonical JSON")
    if text != build_anchor_comment_body(receipt):
        raise ValueError("GitHub prediction anchor comment body does not reproduce")
    return receipt


def _default_github_get_bytes(url: str) -> bytes:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tennis-genome-prediction-anchor-verifier",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _validate_receipt(
    receipt: dict[str, object],
    *,
    expected_prediction_sha256: str | None,
) -> None:
    if receipt.get("schema_version") != ANCHOR_SCHEMA:
        raise ValueError("prediction anchor receipt schema is not supported")
    if receipt.get("trusted_prediction_anchor_schema") != TRUSTED_ANCHOR_SCHEMA:
        raise ValueError("prediction anchor is not trusted live GitHub evidence")
    if receipt.get("prediction_anchor_workflow_version") != TRUSTED_ANCHOR_VERSION:
        raise ValueError("prediction anchor workflow version is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("prediction anchor provider is not GitHub Actions")
    if receipt.get("repository") != ANCHOR_REPOSITORY:
        raise ValueError("prediction anchor repository differs from frozen repository")
    if int(receipt.get("prediction_anchor_ledger_issue", -1)) != ANCHOR_LEDGER_ISSUE:
        raise ValueError("prediction anchor ledger issue differs from frozen ledger")

    prediction_sha = _require_sha256(
        receipt.get("prediction_record_sha256"),
        field="receipt.prediction_record_sha256",
    )
    chain_head = _require_sha256(
        receipt.get("chain_head_sha256"),
        field="receipt.chain_head_sha256",
    )
    if prediction_sha != chain_head:
        raise ValueError("prediction anchor does not attest prediction as immediate chain head")
    if expected_prediction_sha256 is not None and prediction_sha != expected_prediction_sha256:
        raise ValueError("live prediction anchor SHA differs from retained prediction")

    source_sha = _required_text(receipt, "workflow_source_sha")
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("receipt.workflow_source_sha must be lowercase Git SHA-1")
    run_id = int(receipt.get("workflow_run_id", -1))
    run_attempt = int(receipt.get("workflow_run_attempt", -1))
    if run_id <= 0 or run_attempt <= 0:
        raise ValueError("prediction anchor run identity must be positive")
    expected_url = f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    if receipt.get("workflow_run_url") != expected_url:
        raise ValueError("prediction anchor workflow URL does not reproduce")
    _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )


def _validate_comment(
    comment: dict[str, object],
    *,
    comment_id: int,
    expected_prediction_sha256: str | None,
) -> tuple[dict[str, object], datetime]:
    if int(comment.get("id", -1)) != comment_id:
        raise ValueError("prediction anchor comment ID does not match requested comment")
    expected_issue_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/{ANCHOR_LEDGER_ISSUE}"
    )
    if comment.get("issue_url") != expected_issue_url:
        raise ValueError("prediction anchor comment is not on frozen ledger issue")
    expected_comment_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    )
    if comment.get("url") != expected_comment_url:
        raise ValueError("prediction anchor comment API URL does not reproduce")
    actor = comment.get("user")
    if not isinstance(actor, dict):
        raise ValueError("prediction anchor comment lacks actor identity")
    if actor.get("login") != ANCHOR_BOT_LOGIN or actor.get("type") != "Bot":
        raise ValueError("prediction anchor comment was not created by github-actions[bot]")
    created_text = _required_text(comment, "created_at")
    updated_text = _required_text(comment, "updated_at")
    if created_text != updated_text:
        raise ValueError("prediction anchor comment has been edited")
    created_at = _parse_time(created_text, field="prediction_anchor_comment.created_at")
    receipt = _parse_comment_body(comment.get("body"))
    _validate_receipt(
        receipt,
        expected_prediction_sha256=expected_prediction_sha256,
    )
    return receipt, created_at


def _validate_run(
    run: dict[str, object],
    *,
    receipt: dict[str, object],
    anchor_created_at: datetime,
) -> None:
    run_id = int(receipt["workflow_run_id"])
    if int(run.get("id", -1)) != run_id:
        raise ValueError("prediction anchor workflow run ID differs from receipt")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != ANCHOR_REPOSITORY:
        raise ValueError("prediction anchor workflow repository differs from frozen repository")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("prediction anchor workflow was not workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("prediction anchor workflow did not complete successfully")
    if run.get("path") != ANCHOR_WORKFLOW_PATH:
        raise ValueError("prediction anchor used the wrong workflow path")
    if run.get("head_branch") != "main":
        raise ValueError("trusted prediction anchor was not dispatched from main")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("prediction anchor workflow source SHA differs from receipt")
    if int(run.get("run_attempt", -1)) != int(receipt["workflow_run_attempt"]):
        raise ValueError("prediction anchor workflow attempt differs from receipt")
    expected_url = f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    if run.get("html_url") != expected_url:
        raise ValueError("prediction anchor workflow URL does not reproduce")

    run_created_at = _parse_time(run.get("created_at"), field="workflow_run.created_at")
    runner_created_at = _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )
    if runner_created_at < run_created_at:
        raise ValueError("prediction anchor runner receipt predates workflow run")
    if anchor_created_at < runner_created_at:
        raise ValueError("prediction anchor comment predates runner receipt")
    if anchor_created_at - runner_created_at > _MAX_COMMENT_AFTER_RECEIPT:
        raise ValueError("prediction anchor comment is too late after runner receipt")


def _verify_workflow_source(*, source_sha: str, get_bytes: GitHubGetBytes) -> None:
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("prediction anchor source SHA must be lowercase Git SHA-1")
    encoded = quote(ANCHOR_WORKFLOW_PATH, safe="/")
    url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/contents/{encoded}?ref={source_sha}"
    metadata = _strict_json_object(
        get_bytes(url),
        label="prediction anchor workflow contents response",
    )
    if metadata.get("type") != "file":
        raise ValueError("prediction anchor workflow source path is not a file")
    if metadata.get("path") != ANCHOR_WORKFLOW_PATH:
        raise ValueError("prediction anchor workflow source path does not reproduce")
    if metadata.get("sha") != ANCHOR_WORKFLOW_BLOB_SHA:
        raise ValueError("prediction anchor workflow source differs from frozen blob")


def validate_retained_prediction_anchor_evidence(
    *,
    comment_response_bytes: bytes,
    workflow_run_response_bytes: bytes,
    expected_prediction_sha256: str | None = None,
) -> LivePredictionAnchorEvidence:
    comment = _strict_json_object(
        comment_response_bytes,
        label="retained GitHub prediction anchor comment response",
    )
    comment_id = int(comment.get("id", -1))
    if comment_id <= 0:
        raise ValueError("retained prediction anchor comment ID must be positive")
    receipt, anchor_created_at = _validate_comment(
        comment,
        comment_id=comment_id,
        expected_prediction_sha256=expected_prediction_sha256,
    )
    run = _strict_json_object(
        workflow_run_response_bytes,
        label="retained GitHub prediction anchor workflow response",
    )
    _validate_run(run, receipt=receipt, anchor_created_at=anchor_created_at)
    return LivePredictionAnchorEvidence(
        comment_id=comment_id,
        workflow_run_id=int(receipt["workflow_run_id"]),
        anchor_created_at=anchor_created_at,
        receipt=receipt,
        comment_response_bytes=comment_response_bytes,
        workflow_run_response_bytes=workflow_run_response_bytes,
        comment_response_sha256=hashlib.sha256(comment_response_bytes).hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(workflow_run_response_bytes).hexdigest(),
        workflow_source_sha=str(receipt["workflow_source_sha"]),
    )


def fetch_authenticated_prediction_anchor_evidence(
    *,
    comment_id: int,
    expected_prediction_sha256: str | None = None,
    get_bytes: GitHubGetBytes | None = None,
) -> LivePredictionAnchorEvidence:
    if comment_id <= 0:
        raise ValueError("prediction anchor comment ID must be positive")
    fetch = get_bytes or _default_github_get_bytes
    comment_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    comment_bytes = fetch(comment_url)
    comment = _strict_json_object(comment_bytes, label="GitHub prediction anchor comment response")
    receipt, anchor_created_at = _validate_comment(
        comment,
        comment_id=comment_id,
        expected_prediction_sha256=expected_prediction_sha256,
    )

    run_id = int(receipt["workflow_run_id"])
    run_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    run_bytes = fetch(run_url)
    run = _strict_json_object(run_bytes, label="GitHub prediction anchor workflow response")
    _validate_run(run, receipt=receipt, anchor_created_at=anchor_created_at)
    source_sha = str(receipt["workflow_source_sha"])
    _verify_workflow_source(source_sha=source_sha, get_bytes=fetch)

    return LivePredictionAnchorEvidence(
        comment_id=comment_id,
        workflow_run_id=run_id,
        anchor_created_at=anchor_created_at,
        receipt=receipt,
        comment_response_bytes=comment_bytes,
        workflow_run_response_bytes=run_bytes,
        comment_response_sha256=hashlib.sha256(comment_bytes).hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(run_bytes).hexdigest(),
        workflow_source_sha=source_sha,
    )
