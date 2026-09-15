from __future__ import annotations

import json

import pytest

from tennis_genome.prospective.trusted_capture_provenance import (
    TRUSTED_CAPTURE_FROZEN_BLOBS,
    TRUSTED_CAPTURE_SOURCE_VERSION,
    trusted_capture_contents_url,
    verify_trusted_capture_source,
)

_SOURCE_SHA = "d" * 40


def _responses(*, drift_path: str | None = None, wrong_type_path: str | None = None):
    by_url: dict[str, bytes] = {}
    for path, blob_sha in TRUSTED_CAPTURE_FROZEN_BLOBS.items():
        observed = "e" * 40 if path == drift_path else blob_sha
        payload = {
            "type": "dir" if path == wrong_type_path else "file",
            "path": path,
            "sha": observed,
            "size": 1,
        }
        by_url[
            trusted_capture_contents_url(path=path, source_sha=_SOURCE_SHA)
        ] = json.dumps(payload, sort_keys=True).encode("utf-8")

    def get_bytes(url: str) -> bytes:
        if url not in by_url:
            raise AssertionError(f"unexpected provenance URL: {url}")
        return by_url[url]

    return get_bytes


def test_frozen_capture_source_blobs_all_verify_at_run_sha() -> None:
    report = verify_trusted_capture_source(
        source_sha=_SOURCE_SHA,
        get_bytes=_responses(),
    )
    assert report["status"] == "SOURCE_VERIFIED"
    assert report["source_version"] == TRUSTED_CAPTURE_SOURCE_VERSION
    assert report["workflow_source_sha"] == _SOURCE_SHA
    assert report["verified_file_count"] == len(TRUSTED_CAPTURE_FROZEN_BLOBS)
    assert report["verified_blobs"] == TRUSTED_CAPTURE_FROZEN_BLOBS


def test_one_changed_capture_dependency_fails_closed() -> None:
    path = "src/tennis_genome/prospective/provider_batch_pagination.py"
    with pytest.raises(ValueError, match="blob differs from frozen identity"):
        verify_trusted_capture_source(
            source_sha=_SOURCE_SHA,
            get_bytes=_responses(drift_path=path),
        )


def test_capture_source_path_must_still_be_file() -> None:
    path = ".github/workflows/prospective_provider_capture_anchor.yml"
    with pytest.raises(ValueError, match="source path is not a file"):
        verify_trusted_capture_source(
            source_sha=_SOURCE_SHA,
            get_bytes=_responses(wrong_type_path=path),
        )


@pytest.mark.parametrize("source_sha", ["", "ABC", "f" * 39, "g" * 40])
def test_invalid_workflow_source_sha_fails_before_github_fetch(source_sha: str) -> None:
    called = False

    def get_bytes(url: str) -> bytes:
        nonlocal called
        called = True
        raise AssertionError(url)

    with pytest.raises(ValueError, match="lowercase Git SHA-1"):
        verify_trusted_capture_source(source_sha=source_sha, get_bytes=get_bytes)
    assert called is False
