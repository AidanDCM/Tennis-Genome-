from __future__ import annotations

from dataclasses import replace

import pytest

from tennis_genome.calculator.contract import (
    FROZEN_PRODUCTION_BUNDLE_SHA256,
    validate_frozen_bundle_contract,
)
from tennis_genome.independent.production import (
    ACCEPTED_CANONICAL_CONTENT,
    CANDIDATE_LIMIT,
    DEVELOPMENT_END_YEAR,
    PINNED_SOURCE_COMMIT,
    PINNED_SOURCE_REPO,
    PRIMARY_K,
    PRODUCTION_VERSION,
    canonical_content_sha256,
)
from tests.test_matchup_calculator import _calculator_and_inputs


def _valid_frozen_bundle():
    calculator, _, _ = _calculator_and_inputs()
    bundle = calculator.bundle
    atp = replace(
        bundle.atp,
        canonical_content_sha256=canonical_content_sha256(
            ACCEPTED_CANONICAL_CONTENT["ATP"]
        ),
    )
    wta = replace(
        bundle.wta,
        canonical_content_sha256=canonical_content_sha256(
            ACCEPTED_CANONICAL_CONTENT["WTA"]
        ),
    )
    return replace(
        bundle,
        artifact_sha256=FROZEN_PRODUCTION_BUNDLE_SHA256,
        production_version=PRODUCTION_VERSION,
        development_end_year=DEVELOPMENT_END_YEAR,
        source_repo=PINNED_SOURCE_REPO,
        source_commit=PINNED_SOURCE_COMMIT,
        atp=atp,
        wta=wta,
    )


def test_frozen_bundle_contract_accepts_expected_architecture() -> None:
    bundle = _valid_frozen_bundle()
    validate_frozen_bundle_contract(bundle)
    assert bundle.artifact_sha256 == FROZEN_PRODUCTION_BUNDLE_SHA256
    assert bundle.atp.neighbor_bank.k == PRIMARY_K
    assert bundle.wta.neighbor_bank.candidate_limit == CANDIDATE_LIMIT


def test_frozen_bundle_contract_rejects_different_bundle_digest() -> None:
    bundle = replace(_valid_frozen_bundle(), artifact_sha256="0" * 64)
    with pytest.raises(ValueError, match="bundle SHA-256 is not the sealed"):
        validate_frozen_bundle_contract(bundle)


def test_frozen_bundle_contract_rejects_source_commit_change() -> None:
    bundle = replace(_valid_frozen_bundle(), source_commit="0" * 40)
    with pytest.raises(ValueError, match="source commit is not frozen"):
        validate_frozen_bundle_contract(bundle)


def test_frozen_bundle_contract_rejects_development_cutoff_change() -> None:
    bundle = replace(_valid_frozen_bundle(), development_end_year=2026)
    with pytest.raises(ValueError, match="development cutoff"):
        validate_frozen_bundle_contract(bundle)


def test_frozen_bundle_contract_rejects_neighbor_k_change() -> None:
    bundle = _valid_frozen_bundle()
    changed_atp = replace(
        bundle.atp,
        neighbor_bank=replace(bundle.atp.neighbor_bank, k=PRIMARY_K + 1),
    )
    with pytest.raises(ValueError, match="neighbor-bank k is not frozen"):
        validate_frozen_bundle_contract(replace(bundle, atp=changed_atp))


def test_frozen_bundle_contract_rejects_wta_profile_aware_geometry() -> None:
    bundle = _valid_frozen_bundle()
    changed_wta = replace(
        bundle.wta,
        neighbor_bank=replace(
            bundle.wta.neighbor_bank,
            representation="full_genome",
        ),
    )
    with pytest.raises(ValueError, match="neighbor-bank representation is not frozen"):
        validate_frozen_bundle_contract(replace(bundle, wta=changed_wta))


def test_frozen_bundle_contract_rejects_missing_wta_pointsim_meta() -> None:
    bundle = _valid_frozen_bundle()
    changed_wta = replace(bundle.wta, wta_pointsim_meta=None)
    with pytest.raises(ValueError, match="lacks frozen PointSim"):
        validate_frozen_bundle_contract(replace(bundle, wta=changed_wta))


def test_frozen_bundle_contract_rejects_atp_canonical_source_change() -> None:
    bundle = _valid_frozen_bundle()
    changed_atp = replace(bundle.atp, canonical_content_sha256="0" * 64)
    with pytest.raises(ValueError, match="canonical content hash"):
        validate_frozen_bundle_contract(replace(bundle, atp=changed_atp))
