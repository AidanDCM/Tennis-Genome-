import pytest

from tennis_genome.data.provenance import (
    SourceMetadata,
    SourcePermissionError,
    assert_production_allowed,
    assert_research_allowed,
)


def test_production_source_passes_permission_gate():
    metadata = SourceMetadata(
        source_id="provider-v1",
        provider="Provider",
        allowed_use_status="production_allowed",
    )
    assert_production_allowed(metadata)
    assert_research_allowed(metadata)


def test_research_only_source_passes_research_but_fails_production_gate():
    metadata = SourceMetadata(
        source_id="research-source",
        provider="Research Provider",
        allowed_use_status="research_allowed",
    )
    assert_research_allowed(metadata)
    with pytest.raises(SourcePermissionError):
        assert_production_allowed(metadata)


def test_unknown_source_fails_closed_for_both_uses():
    metadata = SourceMetadata(source_id="unknown", provider="Unknown")
    with pytest.raises(SourcePermissionError):
        assert_research_allowed(metadata)
    with pytest.raises(SourcePermissionError):
        assert_production_allowed(metadata)


def test_permission_required_source_cannot_run_research_yet():
    metadata = SourceMetadata(
        source_id="permission-source",
        provider="Provider",
        allowed_use_status="permission_required",
    )
    with pytest.raises(SourcePermissionError):
        assert_research_allowed(metadata)


def test_manifest_preserves_license_metadata():
    metadata = SourceMetadata(
        source_id="source-v1",
        provider="Provider",
        source_version="abc123",
        license_name="Example License",
        license_url="https://example.com/license",
        allowed_use_status="permission_required",
    )
    manifest = metadata.to_manifest()
    assert manifest["source_version"] == "abc123"
    assert manifest["license_name"] == "Example License"
    assert manifest["allowed_use_status"] == "permission_required"
