from __future__ import annotations

import pytest

from tennis_genome.research_workbench.dynamic_state_search_family import (
    DynamicStateLessAggressiveFamilySpec,
    LessAggressiveDynamicCandidate,
    registered_less_aggressive_candidates,
)


def test_registered_family_is_exact_complete_2x2x2_grid() -> None:
    candidates = registered_less_aggressive_candidates()

    assert len(candidates) == 8
    assert {item.process_variance_per_day for item in candidates} == {0.00025, 0.00050}
    assert {item.mean_reversion_half_life_days for item in candidates} == {730.0, 1460.0}
    assert {item.max_variance for item in candidates} == {0.75, 1.00}
    assert len({item.candidate_id for item in candidates}) == 8


def test_all_registered_candidates_are_less_aggressive_than_failed_parent() -> None:
    for candidate in registered_less_aggressive_candidates():
        assert candidate.process_variance_per_day < 0.001
        assert candidate.mean_reversion_half_life_days > 365.0
        assert candidate.max_variance < 1.50
        config = candidate.dynamic_config()
        assert config.initial_variance == 0.50
        assert config.point_information_weight == 0.10
        assert config.min_variance == 0.02


def test_family_freezes_trial_and_primary_claim_counts() -> None:
    spec = DynamicStateLessAggressiveFamilySpec()
    search = spec.search_family()

    assert len(spec.candidates) == 8
    assert search.total_trials == 8
    assert search.frozen is True
    assert search.unregistered_variant_count == 0
    assert search.parameter_search_count == 0
    assert spec.primary_claim_count == 32
    assert spec.bonferroni_alpha == pytest.approx(0.0015625)


def test_development_spec_changes_only_registered_dynamic_axes() -> None:
    family = DynamicStateLessAggressiveFamilySpec()
    candidate = family.candidates[0]
    spec = family.development_spec(candidate=candidate, tour="ATP")

    assert spec.tour == "ATP"
    assert spec.dynamic_process_variance_per_day == candidate.process_variance_per_day
    assert (
        spec.dynamic_mean_reversion_half_life_days
        == candidate.mean_reversion_half_life_days
    )
    assert spec.dynamic_max_variance == candidate.max_variance
    assert spec.dynamic_initial_variance == 0.50
    assert spec.dynamic_point_information_weight == 0.10
    assert spec.dynamic_min_variance == 0.02
    assert spec.fixed_learning_rate == 0.50
    assert spec.fixed_reference_points == 60.0
    assert spec.test_years == tuple(range(2015, 2026))
    assert spec.min_train_rows == 5_000


def test_unregistered_candidate_cannot_enter_family_run() -> None:
    family = DynamicStateLessAggressiveFamilySpec()
    rogue = LessAggressiveDynamicCandidate(
        candidate_id="DYN-LA-PV00025-HL730-MV075",
        process_variance_per_day=0.00025,
        mean_reversion_half_life_days=730.0,
        max_variance=0.75,
    )
    # Same semantic candidate is allowed even if reconstructed independently.
    assert family.development_spec(candidate=rogue, tour="WTA").tour == "WTA"

    with pytest.raises(ValueError, match="candidate_id does not match|outside frozen family"):
        LessAggressiveDynamicCandidate(
            candidate_id="DYN-LA-PV00100-HL730-MV075",
            process_variance_per_day=0.001,
            mean_reversion_half_life_days=730.0,
            max_variance=0.75,
        )


def test_family_rejects_missing_candidate() -> None:
    candidates = registered_less_aggressive_candidates()
    with pytest.raises(ValueError, match="complete frozen 2x2x2 family"):
        DynamicStateLessAggressiveFamilySpec(candidates=candidates[:-1])
