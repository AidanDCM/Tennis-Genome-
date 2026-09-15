from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from tennis_genome.prospective.provider_batch_pagination import PAGINATION_SCHEMA
from tennis_genome.prospective.trusted_provider_capture import (
    TRUSTED_CAPTURE_SCHEMA,
    TRUSTED_CAPTURE_WORKFLOW_PATH,
)

ANCHOR_RECEIPT_SCHEMA = "full-stack-forward-provider-batch-github-anchor-v1"
ANCHOR_COMMENT_MARKER = "<!-- FULL-STACK-FORWARD-001-PROVIDER-BATCH-ANCHOR-V1 -->"
ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"
ANCHOR_LEDGER_ISSUE = 111
ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_provider_batch_anchor.yml"
ANCHOR_BOT_LOGIN = "github-actions[bot]"
_GITHUB_API = "https://api.github.com"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_MAX_PROVIDER_OBSERVATION_LAG = timedelta(minutes=10)
_MAX_EXTERNAL_ANCHOR_LAG = timedelta(minutes=30)

GitHubGetBytes = Callable[[str], bytes]


@dataclass(frozen=True)
class LiveProviderBatchAnchorEvidence:
    comment_id: int
    workflow_run_id: int
    anchor_created_at: datetime
    receipt: dict[str, object]
    comment_response_bytes: bytes
    workflow_run_response_bytes: bytes
    comment_response_sha256: str
    workflow_run_response_sha256: str


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


def _parse_date(value: object, *, field: str) -> date:
    try:
        return date.fromisoformat(str(value if value is not None else "").strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc


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
        raise ValueError("GitHub anchor comment body does not match frozen ledger format")
    canonical = text[len(prefix) : -len(suffix)]
    try:
        receipt = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise ValueError("GitHub anchor comment contains invalid receipt JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("GitHub anchor comment receipt must be a JSON object")
    if canonical != _canonical_json(receipt):
        raise ValueError("GitHub anchor comment receipt is not canonical JSON")
    if text != build_anchor_comment_body(receipt):
        raise ValueError("GitHub anchor comment body does not reproduce")
    return receipt


def _default_github_get_bytes(url: str) -> bytes:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tennis-genome-live-anchor-verifier",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _validate_receipt_shape(receipt: dict[str, object]) -> None:
    if receipt.get("schema_version") != ANCHOR_RECEIPT_SCHEMA:
        raise ValueError("GitHub anchor receipt schema is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("GitHub anchor receipt provider is not GitHub Actions")
    if receipt.get("repository") != ANCHOR_REPOSITORY:
        raise ValueError("GitHub anchor receipt repository differs from frozen repository")

    for field in (
        "batch_record_sha256",
        "batch_chain_head_sha256",
        "raw_payload_sha256",
        "manifest_sha256",
    ):
        _require_sha256(receipt.get(field), field=f"receipt.{field}")
    source_sha = _required_text(receipt, "workflow_source_sha")
    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("receipt.workflow_source_sha must be lowercase Git SHA-1")
    run_id = int(receipt.get("workflow_run_id", -1))
    run_attempt = int(receipt.get("workflow_run_attempt", -1))
    if run_id <= 0 or run_attempt <= 0:
        raise ValueError("GitHub anchor receipt run identity must be positive")
    expected_run_url = f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    if receipt.get("workflow_run_url") != expected_run_url:
        raise ValueError("GitHub anchor receipt workflow URL does not reproduce")
    schedule_date = _parse_date(receipt.get("schedule_date"), field="receipt.schedule_date")
    observed_at = _parse_time(receipt.get("observed_at"), field="receipt.observed_at")
    if schedule_date != observed_at.date():
        raise ValueError("GitHub anchor receipt schedule date differs from observation UTC date")
    _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )


def _validate_trusted_capture_receipt(receipt: dict[str, object]) -> None:
    if receipt.get("trusted_capture_schema") != TRUSTED_CAPTURE_SCHEMA:
        raise ValueError("GitHub anchor receipt is not trusted provider-capture evidence")
    _require_sha256(
        receipt.get("trusted_capture_receipt_sha256"),
        field="receipt.trusted_capture_receipt_sha256",
    )
    if receipt.get("sportradar_access_level") not in {"trial", "production"}:
        raise ValueError("trusted provider-capture access level is not supported")


def _validate_comment(
    *,
    comment: dict[str, object],
    comment_id: int,
) -> tuple[dict[str, object], datetime]:
    if int(comment.get("id", -1)) != comment_id:
        raise ValueError("GitHub anchor comment ID does not match requested comment")
    expected_issue_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/{ANCHOR_LEDGER_ISSUE}"
    )
    if comment.get("issue_url") != expected_issue_url:
        raise ValueError("GitHub anchor comment is not on the frozen ledger issue")
    expected_comment_url = (
        f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    )
    if comment.get("url") != expected_comment_url:
        raise ValueError("GitHub anchor comment API URL does not reproduce")
    actor = comment.get("user")
    if not isinstance(actor, dict):
        raise ValueError("GitHub anchor comment lacks actor identity")
    if actor.get("login") != ANCHOR_BOT_LOGIN or actor.get("type") != "Bot":
        raise ValueError("GitHub anchor comment was not created by github-actions[bot]")
    created_text = _required_text(comment, "created_at")
    updated_text = _required_text(comment, "updated_at")
    if created_text != updated_text:
        raise ValueError("GitHub anchor comment has been edited")
    created_at = _parse_time(created_text, field="anchor_comment.created_at")
    receipt = _parse_comment_body(comment.get("body"))
    _validate_receipt_shape(receipt)
    return receipt, created_at


def _validate_workflow_run(
    *,
    run: dict[str, object],
    receipt: dict[str, object],
    anchor_created_at: datetime,
    expected_workflow_path: str,
    require_main_ref: bool,
) -> None:
    run_id = int(receipt["workflow_run_id"])
    if int(run.get("id", -1)) != run_id:
        raise ValueError("GitHub workflow run ID differs from anchor receipt")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != ANCHOR_REPOSITORY:
        raise ValueError("GitHub workflow run repository differs from frozen repository")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("GitHub provider anchor run was not workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("GitHub provider anchor run did not complete successfully")
    if run.get("path") != expected_workflow_path:
        raise ValueError("GitHub provider anchor run used the wrong workflow path")
    if require_main_ref and run.get("head_branch") != "main":
        raise ValueError("trusted provider capture was not dispatched from main")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("GitHub provider anchor run source SHA differs from receipt")
    if int(run.get("run_attempt", -1)) != int(receipt["workflow_run_attempt"]):
        raise ValueError("GitHub provider anchor run attempt differs from receipt")
    expected_html_url = f"https://github.com/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    if run.get("html_url") != expected_html_url:
        raise ValueError("GitHub provider anchor run URL does not reproduce")
    run_created_at = _parse_time(run.get("created_at"), field="workflow_run.created_at")
    if anchor_created_at < run_created_at:
        raise ValueError("GitHub ledger anchor predates workflow-run creation")
    runner_receipt_created_at = _parse_time(
        receipt.get("runner_receipt_created_at_utc"),
        field="receipt.runner_receipt_created_at_utc",
    )
    if runner_receipt_created_at < run_created_at:
        raise ValueError("runner receipt predates workflow-run creation")
    # GitHub issue/comment timestamps are exposed at whole-second precision, while
    # the runner receipt is recorded with microseconds. Compare at the provider's
    # observable timestamp precision so a later comment in the same second is not
    # falsely treated as predating the runner receipt. Distinct seconds still fail.
    if anchor_created_at.replace(microsecond=0) < runner_receipt_created_at.replace(
        microsecond=0
    ):
        raise ValueError("GitHub ledger anchor predates runner receipt creation")


def verify_live_anchor_against_batch(
    *,
    batch_record: dict[str, object],
    evidence: LiveProviderBatchAnchorEvidence,
) -> None:
    receipt = evidence.receipt
    if batch_record.get("record_type") != "PROVIDER_BATCH":
        raise ValueError("live anchor requires a PROVIDER_BATCH record")
    if batch_record.get("provider") != "SPORTRADAR":
        raise ValueError("live anchor requires a Sportradar provider batch")
    if batch_record.get("pagination_schema") != PAGINATION_SCHEMA:
        raise ValueError("live anchor requires complete Sportradar pagination-v2 evidence")

    batch_sha = _require_sha256(
        batch_record.get("record_sha256"),
        field="batch_record.record_sha256",
    )
    if receipt.get("batch_record_sha256") != batch_sha:
        raise ValueError("live GitHub anchor batch record SHA differs from retained batch")
    if receipt.get("batch_chain_head_sha256") != batch_sha:
        raise ValueError("live GitHub anchor does not attest batch as immediate chain head")
    for field in ("schedule_date", "raw_payload_sha256", "manifest_sha256", "observed_at"):
        if receipt.get(field) != batch_record.get(field):
            raise ValueError(f"live GitHub anchor {field} differs from retained batch")

    schedule_date = _parse_date(batch_record.get("schedule_date"), field="batch.schedule_date")
    observed_at = _parse_time(batch_record.get("observed_at"), field="batch.observed_at")
    provider_min = _parse_time(
        batch_record.get("provider_generated_at_min"),
        field="batch.provider_generated_at_min",
    )
    provider_max = _parse_time(
        batch_record.get("provider_generated_at_max"),
        field="batch.provider_generated_at_max",
    )
    if provider_min > provider_max:
        raise ValueError("provider generation bounds are inverted")
    if provider_max - provider_min > timedelta(minutes=10):
        raise ValueError("provider generation spread exceeds frozen 10-minute bound")
    if schedule_date != provider_min.date() or schedule_date != provider_max.date():
        raise ValueError("batch schedule date differs from provider generation UTC date")
    if schedule_date != observed_at.date():
        raise ValueError("batch schedule date differs from observation UTC date")
    if observed_at < provider_max:
        raise ValueError("batch observation predates newest provider generation")
    if observed_at - provider_max > _MAX_PROVIDER_OBSERVATION_LAG:
        raise ValueError("batch observation exceeds frozen provider-generation lag")

    anchor_created_at = evidence.anchor_created_at
    if anchor_created_at < provider_max:
        raise ValueError("live GitHub anchor predates newest provider generation")
    if anchor_created_at - provider_min > _MAX_EXTERNAL_ANCHOR_LAG:
        raise ValueError("live GitHub anchor is too late for retained provider page set")


def fetch_live_anchor_evidence(
    *,
    comment_id: int,
    batch_record: dict[str, object] | None = None,
    get_bytes: GitHubGetBytes | None = None,
    expected_workflow_path: str = ANCHOR_WORKFLOW_PATH,
    require_main_ref: bool = False,
    require_trusted_capture: bool = False,
) -> LiveProviderBatchAnchorEvidence:
    if comment_id <= 0:
        raise ValueError("GitHub anchor comment ID must be positive")
    fetch = get_bytes or _default_github_get_bytes
    comment_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/issues/comments/{comment_id}"
    comment_bytes = fetch(comment_url)
    comment = _strict_json_object(comment_bytes, label="GitHub anchor comment response")
    receipt, anchor_created_at = _validate_comment(comment=comment, comment_id=comment_id)
    if require_trusted_capture:
        _validate_trusted_capture_receipt(receipt)

    run_id = int(receipt["workflow_run_id"])
    run_url = f"{_GITHUB_API}/repos/{ANCHOR_REPOSITORY}/actions/runs/{run_id}"
    run_bytes = fetch(run_url)
    run = _strict_json_object(run_bytes, label="GitHub workflow run response")
    _validate_workflow_run(
        run=run,
        receipt=receipt,
        anchor_created_at=anchor_created_at,
        expected_workflow_path=expected_workflow_path,
        require_main_ref=require_main_ref,
    )

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


def fetch_trusted_capture_anchor_evidence(
    *,
    comment_id: int,
    batch_record: dict[str, object] | None = None,
    get_bytes: GitHubGetBytes | None = None,
) -> LiveProviderBatchAnchorEvidence:
    """Fetch promotion-capable evidence from the trusted capture+anchor workflow only."""

    return fetch_live_anchor_evidence(
        comment_id=comment_id,
        batch_record=batch_record,
        get_bytes=get_bytes,
        expected_workflow_path=TRUSTED_CAPTURE_WORKFLOW_PATH,
        require_main_ref=True,
        require_trusted_capture=True,
    )
