from __future__ import annotations

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench import (
    DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    REQUIRED_TENNIS_RESEARCH_INVARIANTS,
    ResearchAuthority,
    ResearchConstitution,
)


def test_default_constitution_contains_every_required_invariant() -> None:
    constitution = DEFAULT_TENNIS_RESEARCH_CONSTITUTION

    assert constitution.version == 1
    assert set(REQUIRED_TENNIS_RESEARCH_INVARIANTS).issubset(
        constitution.invariants
    )
    assert len(constitution.semantic_sha256) == 64


def test_constitution_cannot_drop_required_research_rule() -> None:
    reduced = REQUIRED_TENNIS_RESEARCH_INVARIANTS[:-1]

    with pytest.raises(ValidationError, match="missing required invariants"):
        ResearchConstitution(
            constitution_id="invalid",
            version=2,
            invariants=reduced,
        )


def test_constitution_version_or_extra_rule_changes_identity() -> None:
    original = DEFAULT_TENNIS_RESEARCH_CONSTITUTION
    changed = ResearchConstitution(
        constitution_id=original.constitution_id,
        version=2,
        invariants=original.invariants + ("NEW_REGISTERED_GOVERNANCE_RULE",),
    )

    assert original.semantic_sha256 != changed.semantic_sha256


def test_research_authority_cannot_grant_production_or_wagering_power() -> None:
    with pytest.raises(ValidationError):
        ResearchAuthority(modify_frozen_v1=True)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        ResearchAuthority(activate_wagering=True)  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        ResearchAuthority(consume_market_data_in_independent_lane=True)  # type: ignore[arg-type]


def test_constitution_is_frozen() -> None:
    constitution = DEFAULT_TENNIS_RESEARCH_CONSTITUTION

    with pytest.raises(ValidationError):
        constitution.version = 99  # type: ignore[misc]
