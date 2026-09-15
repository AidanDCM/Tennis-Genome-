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

SETTLEMENT_CAPTURE_SCHEMA = "full-stack-pilot-trusted-settlement-capture-v1"
SETTLEMENT_CAPTURE_VERSION = "FULL-STACK-PILOT-001-settlement-capture-v1"
SETTLEMENT_COMMENT_MARKER = "<!-- FULL-STACK-PILOT-001-SETTLEMENT-CAPTURE-V1 -->"
SETTLEMENT_REPOSITORY = "AidanDCM/Tennis-Genome-"
SETTLEMENT_LEDGER_ISSUE = 122
SETTLEMENT_WORKFLOW_PATH = ".github/workflows/prospective_settlement_capture.yml"
SETTLEMENT_WORKFLOW_BLOB_SHA = "1de7ee9eea608d0c491feeb7c71ff2500cbb4a92"
SETTLEMENT_BOT_LOGIN = "github-actions[bot]"
SETTLEMENT_PROVIDER = "SPORTRADAR_TENNIS_V3"
_GITHUB_API = "https://api.github.com"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_EVENT_RE = re.compile(r"^sr:sport_event:[0-9]+$")
_MAX_PROVIDER_AGE = timedelta(minutes=10)
_MAX_COMMENT_AFTER_OBSERVATION = timedelta(minutes=10)

GitHubGetBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class LiveSettlementCaptureEvidence:
    comment_id: int
    workflow_run_id: int
    comment_created_at: datetime
    provider_generated_at: datetime
    observed_at: datetime
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


def build_settlement_comment_body(receipt: dict[str, object]) -> str:
    return f"{SETTLEMENT_COMMENT_MARKER}\n```json\n{_canonical_json(receipt)}\n```"


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
    prefix = f"{SETTLEMENT_COMMENT_MARKER}\n```json\n"
    suffix = "\n```"
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise ValueError("GitHub settlement comment does not match frozen format")
    canonical = text[len(prefix) : -len(suffix)]
    try:
        receipt = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub settlement comment contains invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("GitHub settlement receipt must be an object")
    if canonical != _canonical_json(receipt):
        raise ValueError("GitHub settlement receipt is not canonical JSON")
    if text != build_settlement_comment_body(receipt):
        raise ValueError("GitHub settlement comment body does not reproduce")
    return receipt


def _default_github_get_bytes(url: str) -> bytes:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tennis-genome-trusted-settlement-verifier",
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
    expected_identity_sha256: str | None,
    expected_event_id: str | None,
) -> tuple[datetime, datetime]:
    if receipt.get("schema_version") != SETTLEMENT_CAPTURE_SCHEMA:
        raise ValueError("settlement capture receipt schema is not supported")
    if receipt.get("settlement_capture_version") != SETTLEMENT_CAPTURE_VERSION:
        raise ValueError("settlement capture version is not supported")
    if receipt.get("provider") != SETTLEMENT_PROVIDER:
        raise ValueError("settlement capture provider is not frozen Sportradar Tennis v3")
    if receipt.get("repository") != SETTLEMENT_REPOSITORY:
        raise ValueError("settlement capture repository differs from frozen repository")
    if int(receipt.get("settlement_ledger_issue", -1)) != SETTLEMENT_LEDGER_ISSUE:
        raise ValueError("settlement capture ledger issue differs from frozen ledger")

    prediction_sha = _require_sha256(
        receipt.get("prediction_record_sha256"),
        field="receipt.prediction_record_sha256",
    )
    identity_sha = _require_sha256(
        receipt.get("identity_binding_sha256"),
        field="receipt.identity_binding_sha256",
    )
    _require_sha256(receipt.get("timeline_sha256"), field="receipt.timeline_sha256")
    _require_sha256(
        receipt.get("response_headers_sha256"),
        field="receipt.response_headers_sha256",
    )
    if expected_prediction_sha256 is not None and prediction_sha != expected_prediction_sha256:
        raise ValueError("settlement receipt prediction SHA differs from retained prediction")
    if expected_identity_sha256 is not None and identity_sha != expected_identity_sha256:
        raise ValueError("settlement receipt identity SHA differs from pre-match binding")

    event_id = _required_text(receipt, "sportradar_event_id")
    if not _EVENT_RE.fullmatch(event_id):
        raise ValueError("settlement receipt event ID has unsupported format")
    if expected_event_id is not None and event_id != expected_event_id:
        raise ValueError("settlement receipt event ID differs from pre-match binding")
    if receipt.get("sportradar_access_level") not in {"trial", "production"}:
        raise ValueError("settlement capture access level is not trial/production")
    if receipt.get("provider_status") not in {"ended", "closed"}:
        raise ValueError("settlement receipt provider status is not terminal")
    _required_text(receipt, "winner_sportradar_id")

    source_sha = _required_text(receipt, "workflow_source_sha")
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("receipt.workflow_source_sha must be lowercase Git SHA-1")
    run_id = int(receipt.get("workflow_run_id", -1))
    run_attempt = int(receipt.get("workflow_run_attempt", -1))
    if run_id <= 0 or run_attempt <= 0:
        raise ValueError("settlement workflow run identity must be positive")
    expected_url = f"https://github.com/{SETTLEMENT_REPOSITORY}/actions/runs/{run_id}"
    if receipt.get("workflow_run_url") != expected_url:
        raise ValueError("settlement workflow URL does not reproduce")

    provider_generated = _parse_time(
        receipt.get("provider_generated_at"),
        field="receipt.provider_generated_at",
    )
    observed_at = _parse_time(receipt.get("observed_at"), field="receipt.observed_at")
    if provider_generated > observed_at:
        raise ValueError("settlement provider generated_at is after runner observation")
    if observed_at - provider_generated > _MAX_PROVIDER_AGE:
        raise ValueError("settlement provider response is stale by more than 10 minutes")
    return provider_generated, observed_at


def _validate_comment(
    comment: dict[str, object],
    *,
    comment_id: int,
    expected_prediction_sha256: str | None,
    expected_identity_sha256: str | None,
    expected_event_id: str | None,
) -> tuple[dict[str, object], datetime, datetime, datetime]:
    if int(comment.get("id", -1)) != comment_id:
        raise ValueError("settlement comment ID does not match requested comment")
    expected_issue_url = (
        f"{_GITHUB_API}/repos/{SETTLEMENT_REPOSITORY}/issues/{SETTLEMENT_LEDGER_ISSUE}"
    )
    if comment.get("issue_url") != expected_issue_url:
        raise ValueError("settlement comment is not on frozen ledger issue")
    expected_comment_url = (
        f"{_GITHUB_API}/repos/{SETTLEMENT_REPOSITORY}/issues/comments/{comment_id}"
    )
    if comment.get("url") != expected_comment_url:
        raise ValueError("settlement comment API URL does not reproduce")
    actor = comment.get("user")
    if not isinstance(actor, dict):
        raise ValueError("settlement comment lacks actor identity")
    if actor.get("login") != SETTLEMENT_BOT_LOGIN or actor.get("type") != "Bot":
        raise ValueError("settlement comment was not created by github-actions[bot]")
    created_text = _required_text(comment, "created_at")
    updated_text = _required_text(comment, "updated_at")
    if created_text != updated_text:
        raise ValueError("settlement comment has been edited")
    created_at = _parse_time(created_text, field="settlement_comment.created_at")
    receipt = _parse_comment_body(comment.get("body"))
    provider_generated, observed_at = _validate_receipt(
        receipt,
        expected_prediction_sha256=expected_prediction_sha256,
        expected_identity_sha256=expected_identity_sha256,
        expected_event_id=expected_event_id,
    )
    if created_at < observed_at:
        raise ValueError("settlement GitHub comment predates runner observation")
    if created_at - observed_at > _MAX_COMMENT_AFTER_OBSERVATION:
        raise ValueError("settlement GitHub commitment is too late after provider observation")
    return receipt, created_at, provider_generated, observed_at


def _validate_run(
    run: dict[str, object],
    *,
    receipt: dict[str, object],
    comment_created_at: datetime,
) -> None:
    run_id = int(receipt["workflow_run_id"])
    if int(run.get("id", -1)) != run_id:
        raise ValueError("settlement workflow run ID differs from receipt")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != SETTLEMENT_REPOSITORY:
        raise ValueError("settlement workflow repository differs from frozen repository")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("settlement workflow was not workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("settlement workflow did not complete successfully")
    if run.get("path") != SETTLEMENT_WORKFLOW_PATH:
        raise ValueError("settlement used the wrong workflow path")
    if run.get("head_branch") != "main":
        raise ValueError("trusted settlement capture was not dispatched from main")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("settlement workflow source SHA differs from receipt")
    if int(run.get("run_attempt", -1)) != int(receipt["workflow_run_attempt"]):
        raise ValueError("settlement workflow attempt differs from receipt")
    expected_url = f"https://github.com/{SETTLEMENT_REPOSITORY}/actions/runs/{run_id}"
    if run.get("html_url") != expected_url:
        raise ValueError("settlement workflow URL does not reproduce")
    run_created_at = _parse_time(run.get("created_at"), field="workflow_run.created_at")
    observed_at = _parse_time(receipt.get("observed_at"), field="receipt.observed_at")
    if observed_at < run_created_at:
        raise ValueError("settlement provider observation predates workflow run")
    if comment_created_at < run_created_at:
        raise ValueError("settlement GitHub comment predates workflow run")


def _verify_workflow_source(*, source_sha: str, get_bytes: GitHubGetBytes) -> None:
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("settlement source SHA must be lowercase Git SHA-1")
    encoded = quote(SETTLEMENT_WORKFLOW_PATH, safe="/")
    url = f"{_GITHUB_API}/repos/{SETTLEMENT_REPOSITORY}/contents/{encoded}?ref={source_sha}"
    metadata = _strict_json_object(
        get_bytes(url),
        label="settlement workflow contents response",
    )
    if metadata.get("type") != "file":
        raise ValueError("settlement workflow source path is not a file")
    if metadata.get("path") != SETTLEMENT_WORKFLOW_PATH:
        raise ValueError("settlement workflow source path does not reproduce")
    if metadata.get("sha") != SETTLEMENT_WORKFLOW_BLOB_SHA:
        raise ValueError("settlement workflow source differs from frozen blob")


def validate_retained_settlement_capture_evidence(
    *,
    comment_response_bytes: bytes,
    workflow_run_response_bytes: bytes,
    expected_prediction_sha256: str | None = None,
    expected_identity_sha256: str | None = None,
    expected_event_id: str | None = None,
) -> LiveSettlementCaptureEvidence:
    comment = _strict_json_object(
        comment_response_bytes,
        label="retained GitHub settlement comment response",
    )
    comment_id = int(comment.get("id", -1))
    if comment_id <= 0:
        raise ValueError("retained settlement comment ID must be positive")
    receipt, created_at, provider_generated, observed_at = _validate_comment(
        comment,
        comment_id=comment_id,
        expected_prediction_sha256=expected_prediction_sha256,
        expected_identity_sha256=expected_identity_sha256,
        expected_event_id=expected_event_id,
    )
    run = _strict_json_object(
        workflow_run_response_bytes,
        label="retained GitHub settlement workflow response",
    )
    _validate_run(run, receipt=receipt, comment_created_at=created_at)
    return LiveSettlementCaptureEvidence(
        comment_id=comment_id,
        workflow_run_id=int(receipt["workflow_run_id"]),
        comment_created_at=created_at,
        provider_generated_at=provider_generated,
        observed_at=observed_at,
        receipt=receipt,
        comment_response_bytes=comment_response_bytes,
        workflow_run_response_bytes=workflow_run_response_bytes,
        comment_response_sha256=hashlib.sha256(comment_response_bytes).hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(workflow_run_response_bytes).hexdigest(),
        workflow_source_sha=str(receipt["workflow_source_sha"]),
    )


def fetch_authenticated_settlement_capture_evidence(
    *,
    comment_id: int,
    expected_prediction_sha256: str | None = None,
    expected_identity_sha256: str | None = None,
    expected_event_id: str | None = None,
    get_bytes: GitHubGetBytes | None = None,
) -> LiveSettlementCaptureEvidence:
    if comment_id <= 0:
        raise ValueError("settlement comment ID must be positive")
    fetch = get_bytes or _default_github_get_bytes
    comment_url = (
        f"{_GITHUB_API}/repos/{SETTLEMENT_REPOSITORY}/issues/comments/{comment_id}"
    )
    comment_bytes = fetch(comment_url)
    comment = _strict_json_object(comment_bytes, label="GitHub settlement comment response")
    receipt, created_at, provider_generated, observed_at = _validate_comment(
        comment,
        comment_id=comment_id,
        expected_prediction_sha256=expected_prediction_sha256,
        expected_identity_sha256=expected_identity_sha256,
        expected_event_id=expected_event_id,
    )

    run_id = int(receipt["workflow_run_id"])
    run_url = f"{_GITHUB_API}/repos/{SETTLEMENT_REPOSITORY}/actions/runs/{run_id}"
    run_bytes = fetch(run_url)
    run = _strict_json_object(run_bytes, label="GitHub settlement workflow response")
    _validate_run(run, receipt=receipt, comment_created_at=created_at)
    source_sha = str(receipt["workflow_source_sha"])
    _verify_workflow_source(source_sha=source_sha, get_bytes=fetch)

    return LiveSettlementCaptureEvidence(
        comment_id=comment_id,
        workflow_run_id=run_id,
        comment_created_at=created_at,
        provider_generated_at=provider_generated,
        observed_at=observed_at,
        receipt=receipt,
        comment_response_bytes=comment_bytes,
        workflow_run_response_bytes=run_bytes,
        comment_response_sha256=hashlib.sha256(comment_bytes).hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(run_bytes).hexdigest(),
        workflow_source_sha=source_sha,
    )
