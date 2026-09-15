from __future__ import annotations

import os
import urllib.request

from tennis_genome.prospective.provider_batch_github_anchor import (
    GitHubGetBytes,
    LiveProviderBatchAnchorEvidence,
    fetch_trusted_capture_anchor_evidence,
)
from tennis_genome.prospective.trusted_capture_provenance import (
    verify_trusted_capture_source,
)


def _default_github_get_bytes(url: str) -> bytes:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "tennis-genome-trusted-capture-verifier",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_authenticated_trusted_capture_evidence(
    *,
    comment_id: int,
    batch_record: dict[str, object] | None = None,
    get_bytes: GitHubGetBytes | None = None,
) -> LiveProviderBatchAnchorEvidence:
    """Authenticate ledger, workflow run, trusted-capture receipt, and frozen source blobs."""

    fetch = get_bytes or _default_github_get_bytes
    evidence = fetch_trusted_capture_anchor_evidence(
        comment_id=comment_id,
        batch_record=batch_record,
        get_bytes=fetch,
    )
    verify_trusted_capture_source(
        source_sha=str(evidence.receipt["workflow_source_sha"]),
        get_bytes=fetch,
    )
    return evidence
