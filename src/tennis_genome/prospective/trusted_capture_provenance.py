from __future__ import annotations

import json
import re
from collections.abc import Callable
from urllib.parse import quote

TRUSTED_CAPTURE_SOURCE_VERSION = "FULL-STACK-FORWARD-001-trusted-capture-source-v1"
TRUSTED_CAPTURE_FROZEN_BLOBS: dict[str, str] = {
    ".github/workflows/prospective_provider_capture_anchor.yml": (
        "f6b3033b613a6426ffa0e23b093083994d141887"
    ),
    "src/tennis_genome/__init__.py": (
        "ea1fd2f9c22377f0fa0cdbb3cc8062bcb4d3712a"
    ),
    "src/tennis_genome/prospective/__init__.py": (
        "a5651fdea9ba5adb693156f3ce2ffe1503397ccd"
    ),
    "src/tennis_genome/prospective/trusted_provider_capture.py": (
        "9dcc1dd69591d013472ec5e2138397fb8916cb14"
    ),
    "src/tennis_genome/prospective/provider_batch.py": (
        "44d4f0fce51e93641e00b99dafab263b08de52d9"
    ),
    "src/tennis_genome/prospective/provider_batch_pagination.py": (
        "66d9b4f9ee788dbdddeefc1b806183ee8c273c40"
    ),
    "src/tennis_genome/prospective/provider_batch_operator.py": (
        "fc873374c3835dabcdfcb8186cd5950b487da686"
    ),
    "src/tennis_genome/prospective/census.py": (
        "5623ae8c3703ad5befd34bc4e033aa9a77faadc6"
    ),
}

_REPOSITORY = "AidanDCM/Tennis-Genome-"
_GITHUB_API = "https://api.github.com"
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GitHubGetBytes = Callable[[str], bytes]


def _json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def trusted_capture_contents_url(*, path: str, source_sha: str) -> str:
    encoded = quote(path, safe="/")
    return f"{_GITHUB_API}/repos/{_REPOSITORY}/contents/{encoded}?ref={source_sha}"


def verify_trusted_capture_source(
    *,
    source_sha: str,
    get_bytes: GitHubGetBytes,
) -> dict[str, object]:
    """Require every capture-critical file at a run SHA to equal its frozen Git blob."""

    if not _GIT_SHA_RE.fullmatch(source_sha):
        raise ValueError("trusted capture workflow source must be lowercase Git SHA-1")
    verified: dict[str, str] = {}
    for path, expected_blob in TRUSTED_CAPTURE_FROZEN_BLOBS.items():
        url = trusted_capture_contents_url(path=path, source_sha=source_sha)
        metadata = _json_object(
            get_bytes(url),
            label=f"GitHub contents response for {path}",
        )
        if metadata.get("type") != "file":
            raise ValueError(f"trusted capture source path is not a file: {path}")
        if metadata.get("path") != path:
            raise ValueError(f"trusted capture source path does not reproduce: {path}")
        observed_blob = str(metadata.get("sha", "")).strip()
        if observed_blob != expected_blob:
            raise ValueError(
                f"trusted capture source blob differs from frozen identity: {path}"
            )
        verified[path] = observed_blob
    return {
        "source_version": TRUSTED_CAPTURE_SOURCE_VERSION,
        "workflow_source_sha": source_sha,
        "verified_file_count": len(verified),
        "verified_blobs": verified,
        "status": "SOURCE_VERIFIED",
    }
