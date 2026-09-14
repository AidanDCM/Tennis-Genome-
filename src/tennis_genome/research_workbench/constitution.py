from __future__ import annotations

from typing import Literal

from pydantic import field_validator, model_validator

from .contracts import WorkbenchRecord

REQUIRED_TENNIS_RESEARCH_INVARIANTS = (
    "T0_INFORMATION_ONLY",
    "INDEPENDENT_PROBABILITY_MARKET_BLIND",
    "PROPER_SCORES_PRIMARY",
    "PROTECTED_DATA_SINGLE_USE",
    "DESCENDANTS_INHERIT_EXPOSURE",
    "CANONICAL_EVIDENCE_BINDS_DATA_CODE_RUNTIME_AND_SPEC",
    "SEARCH_FAMILY_MUST_BE_DECLARED",
    "NEGATIVE_EVIDENCE_IS_PERMANENT",
    "FAILED_PROSPECTIVE_HYPOTHESES_STAY_FAILED",
    "V1_PRODUCTION_ISOLATED_FROM_V2_RESEARCH",
    "COMPLEXITY_COMPETES_WITH_SIMPLER_ALTERNATIVES",
    "PREDICTIVE_SUCCESS_IS_NOT_MARKET_EDGE",
    "MARKET_EDGE_IS_NOT_REALIZED_PROFITABILITY",
    "PROSPECTIVE_COHORT_REQUIRES_DENOMINATOR_ACCOUNTING",
)


class ResearchAuthority(WorkbenchRecord):
    """Capabilities that a research artifact must explicitly not possess."""

    modify_frozen_v1: Literal[False] = False
    bypass_t0_legality: Literal[False] = False
    bypass_protected_burn: Literal[False] = False
    omit_search_attempts: Literal[False] = False
    consume_market_data_in_independent_lane: Literal[False] = False
    claim_market_edge_from_predictive_evidence: Literal[False] = False
    activate_wagering: Literal[False] = False
    change_real_money_risk: Literal[False] = False


class ResearchConstitution(WorkbenchRecord):
    """Versioned non-negotiable rules bound into canonical Workbench evidence."""

    constitution_id: str
    version: int
    invariants: tuple[str, ...]
    authority: ResearchAuthority = ResearchAuthority()

    @field_validator("constitution_id")
    @classmethod
    def _identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("constitution_id must be nonblank")
        return value

    @field_validator("invariants")
    @classmethod
    def _unique_nonblank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("research constitution invariants must be unique")
        if any(not invariant.strip() for invariant in value):
            raise ValueError("research constitution invariants must be nonblank")
        return value

    @model_validator(mode="after")
    def _require_core_invariants(self) -> ResearchConstitution:
        if self.version < 1:
            raise ValueError("research constitution version must be positive")
        missing = sorted(set(REQUIRED_TENNIS_RESEARCH_INVARIANTS) - set(self.invariants))
        if missing:
            raise ValueError(
                "research constitution is missing required invariants: "
                + ", ".join(missing)
            )
        return self


DEFAULT_TENNIS_RESEARCH_CONSTITUTION = ResearchConstitution(
    constitution_id="TENNIS_GENOME_RESEARCH_CONSTITUTION",
    version=1,
    invariants=REQUIRED_TENNIS_RESEARCH_INVARIANTS,
)
