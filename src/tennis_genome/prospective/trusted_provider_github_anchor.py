from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from datetime import UTC, datetime
from urllib.parse import quote

from tennis_genome.prospective.provider_batch_github_anchor import (
    ANCHOR_BOT_LOGIN,
    ANCHOR_COMMENT_MARKER,
    ANCHOR_LEDGER_ISSUE,
    ANCHOR_RECEIPT_SCHEMA,
    ANCHOR_REPOSITORY,
    GitHubGetBytes,
    LiveProviderBatchAnchorEvidence,
    verify_live_anchor_against_batch,
)
from tennis_genome.prospective.trusted_provider_capture import TRUSTED_CAPTURE_SCHEMA

TRUSTED_ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_provider_capture_anchor.yml"
TRUSTED_EVIDENCE_MODE = "TRUSTED_GITHUB_SPORTRADAR_CAPTURE_V1"
_GITHUB_API = "https://api.github.com"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Pre-result-approved Git blob identities for every capture-critical repository file.
TRUSTED_CAPTURE_SOURCE_BLOBS: dict[str, str] = {
    ".github/workflows/prospective_provider_capture_anchor.yml": (
        "41e24e3eb11deb01cc5bff8db0830a79f88b54b4"
    ),
    "src/tennis_genome/prospective/trusted_provider_capture.py": (
        "7f332d1a9d77b99fa862be776a928e55bf2e7fed"
    ),
    "src/tennis_genome/prospective/provider_batch_pagination.py": (
        "66d9b4f9ee788dbdddeefc1b806183ee8c273c40"
    ),
    "src/tennis_genome/prospective/provider_batch.py": (
        "44d4f0fce51e93641e00b99dafab263b08de52d9"
    ),
    "src/tennis_genome/prospective/provider_batch_operator.py": (
        "fc873374c3835dabcdfcb8186cd5950b487da686"
    ),
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


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


def _default_github_get_bytes(url: str) -> bytes:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tennis-genome-trusted-provider-anchor-verifier",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _parse_anchor_comment_body(body: object) -> dict[str, object]:
    text = str(body if body is not None else "")
    prefix = f"{ANCHOR_COMMENT_MARKER}\n```json\n"
    suffix = "\n```"
    if not text.startswith(prefix) or not text.endswith(suffix):
        raise ValueError("trusted anchor comment body does not match frozen ledger format")
    canonical = text[len(prefix) : -len(suffix)]
    try:
        receipt = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise ValueError("trusted anchor comment contains invalid receipt JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("trusted anchor receipt must be a JSON object")
    if canonical != _canonical_json(receipt):
        raise ValueError("trusted anchor receipt is not canonical JSON")
    return receipt


def _validate_trusted_receipt(receipt: dict[str, object]) -> None:
    if receipt.get("schema_version") != ANCHOR_RECEIPT_SCHEMA:
        raise ValueError("trusted anchor receipt schema is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("trusted anchor provider is not GitHub Actions")
    if receipt.get("repository") != ANCHOR_REPOSITORY:
        raise ValueError("trusted anchor repository differs from frozen repository")
    if receipt.get("trusted_capture_schema") != TRUSTED_CAPTURE_SCHEMA:
        raise ValueError("trusted anchor lacks frozen provider-capture schema")
    _require_sha256(
        receipt.get("trusted_capture_receipt_sha256"),
        field="receipt.trusted_capture_receipt_sha256",
    )
    access_level = _required_text(receipt, "sportradar_access_level")
    if access_level not in {"trial", "production"}:
        raise ValueError("trusted anchor Sportradar access level is not supported")
    for field in (
        "batch_record_sha256",
        "batch_chain_head_sha256",
        "raw_payload_sha256",
        "manifest_sha256",
    ):
        _require_sha256(receipt.get(field), field=f"receipt.{field}")
    source_sha = _required_text(receipt, "workflow_source_sha")
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("trusted anchor workflow_source_sha must be lowercase Git SHA-1")
    if int(receipt.get("workflow_run_id", -1)) <= 0:
        raise ValueError("trusted anchor workflow run ID must be positive")
    if int(receipt.get("workflow_run_attempt", -1)) <= 0:
        raise ValueError("trusted anchor workflow run attempt must be positive")
    _parse_time(receipt.get("observed_at"), field="receipt.observed_at")
    _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )


def _validate_comment(
    *,
    comment: dict[str, object],
    comment_id: int,
) -> tuple[dict[str, object], datetime]:
    if int(comment.get("id", -1)) != comment_id:
        raise ValueError("trusted anchor comment ID does not match requested comment")
    expected_issue_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/{ANCHOR_LEDGER_ISSUE}"
    )
    if comment.get("issue_url") != expected_issue_url:
        raise ValueError("trusted anchor comment is not on the frozen ledger issue")
    expected_comment_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    )
    if comment.get("url") != expected_comment_url:
        raise ValueError("trusted anchor comment API URL does not reproduce")
    actor = comment.get("user")
    if not isinstance(actor, dict):
        raise ValueError("trusted anchor comment lacks actor identity")
    if actor.get("login") != ANCHOR_BOT_LOGIN or actor.get("type") != "Bot":
        raise ValueError("trusted anchor comment was not created by github-actions[bot]")
    created_text = _required_text(comment, "created_at")
    if _required_text(comment, "updated_at") != created_text:
        raise ValueError("trusted anchor comment has been edited")
    receipt = _parse_anchor_comment_body(comment.get("body"))
    _validate_trusted_receipt(receipt)
    return receipt, _parse_time(created_text, field="trusted_anchor_comment.created_at")


def _validate_run(
    *,
    run: dict[str, object],
    receipt: dict[str, object],
    anchor_created_at: datetime,
) -> str:
    run_id = int(receipt["workflow_run_id"])
    if int(run.get("id", -1)) != run_id:
        raise ValueError("trusted capture workflow run ID differs from receipt")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != ANCHOR_REPOSITORY:
        raise ValueError("trusted capture workflow repository differs from frozen repository")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("trusted provider capture was not workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("trusted provider capture workflow did not complete successfully")
    if run.get("path") != TRUSTED_ANCHOR_WORKFLOW_PATH:
        raise ValueError("provider evidence did not originate from trusted capture workflow")
    source_sha = str(receipt["workflow_source_sha"])
    if run.get("head_sha") != source_sha:
        raise ValueError("trusted provider capture source SHA differs from receipt")
    if int(run.get("run_attempt", -1)) != int(receipt["workflow_run_attempt"]):
        raise ValueError("trusted provider capture run attempt differs from receipt")
    expected_url = f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    if run.get("html_url") != expected_url or receipt.get("workflow_run_url") != expected_url:
        raise ValueError("trusted provider capture workflow URL does not reproduce")
    run_created_at = _parse_time(run.get("created_at"), field="trusted_run.created_at")
    if anchor_created_at < run_created_at:
        raise ValueError("trusted GitHub ledger anchor predates workflow-run creation")
    runner_created_at = _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )
    if runner_created_at < run_created_at:
        raise ValueError("trusted runner receipt predates workflow-run creation")
    if anchor_created_at < runner_created_at:
        raise ValueError("trusted GitHub ledger anchor predates runner receipt creation")
    return source_sha


def _verify_source_provenance(*, source_sha: str, get_bytes: GitHubGetBytes) -> None:
    for path, expected_blob_sha in TRUSTED_CAPTURE_SOURCE_BLOBS.items():
        encoded_path = quote(path, safe="/")
        url = (
            f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/contents/{encoded_path}"
            f"?ref={source_sha}"
        )
        payload = _strict_json_object(
            get_bytes(url),
            label=f"trusted source metadata for {path}",
        )
        if payload.get("type") != "file" or payload.get("path") != path:
            raise ValueError(f"trusted capture source path does not reproduce: {path}")
        if payload.get("sha") != expected_blob_sha:
            raise ValueError(f"trusted capture source blob differs from frozen code: {path}")


def fetch_trusted_live_anchor_evidence(
    *,
    comment_id: int,
    batch_record: dict[str, object] | None = None,
    get_bytes: GitHubGetBytes | None = None,
) -> LiveProviderBatchAnchorEvidence:
    """Authenticate one provider batch from GitHub-hosted provider transport to ledger."""

    if comment_id <= 0:
        raise ValueError("trusted GitHub anchor comment ID must be positive")
    fetch = get_bytes or _default_github_get_bytes
    comment_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    comment_bytes = fetch(comment_url)
    comment = _strict_json_object(comment_bytes, label="trusted GitHub anchor comment response")
    receipt, anchor_created_at = _validate_comment(comment=comment, comment_id=comment_id)

    run_id = int(receipt["workflow_run_id"])
    run_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    run_bytes = fetch(run_url)
    run = _strict_json_object(run_bytes, label="trusted GitHub workflow run response")
    source_sha = _validate_run(
        run=run,
        receipt=receipt,
        anchor_created_at=anchor_created_at,
    )
    _verify_source_provenance(source_sha=source_sha, get_bytes=fetch)

    evidence = LiveProviderBatchAnchorEvidence(
        comment_id=comment_id,
        workflow_run_id=run_id,
        anchor_created_at=anchor_created_at,
        receipt=receipt,
        comment_response_bytes=comment_bytes,
        workflow_run_response_bytes=run_bytes,
        comment_response_sha256=hashlib.sha256(comment_bytes).hexdigest(),
        workflow_run_response_sha256=hashlib.sha256(run_bytes).hexdigest(),
    )
    if batch_record is not None:
        verify_live_anchor_against_batch(batch_record=batch_record, evidence=evidence)
    return evidence
