from __future__ import annotations

from tennis_genome.research_workbench.api_tennis_dynamic_shadow import (
    ApiTennisDynamicShadowRecord,
)
from tennis_genome.research_workbench.challenger import ShadowModelOutput

CHALLENGER_ID = "TGE-CHALLENGER-WTA-DYNAMIC-SR-SHRUNK-V1"
MIN_PRIOR_POINTS_PER_PLAYER = 200
SHRINKAGE_TO_NEUTRAL = 0.80
RETAINED_RAW_WEIGHT = 1.0 - SHRINKAGE_TO_NEUTRAL


def combined_prior_points(
    record: ApiTennisDynamicShadowRecord,
) -> tuple[int, int]:
    """Return each player's pre-match serve+return point history."""

    return (
        record.prior_serve_points_a + record.prior_return_points_a,
        record.prior_serve_points_b + record.prior_return_points_b,
    )


def is_conservative_wta_eligible(record: ApiTennisDynamicShadowRecord) -> bool:
    """Apply the frozen WTA-only development-derived eligibility gate."""

    history_a, history_b = combined_prior_points(record)
    return (
        record.tour == "WTA"
        and history_a >= MIN_PRIOR_POINTS_PER_PLAYER
        and history_b >= MIN_PRIOR_POINTS_PER_PLAYER
    )


def shrink_probability_to_neutral(probability: float) -> float:
    """Shrink a raw probability 80% of the distance back to 0.50."""

    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    return 0.5 + RETAINED_RAW_WEIGHT * (probability - 0.5)


def build_conservative_wta_shadow_output(
    record: ApiTennisDynamicShadowRecord,
) -> ShadowModelOutput | None:
    """Build a prospective-shadow-compatible output for eligible WTA matches.

    Ineligible matches abstain by returning None rather than emitting a neutral
    pseudo-prediction. The rule is frozen from development evidence and must not be
    retuned from prospective outcomes.
    """

    if not is_conservative_wta_eligible(record):
        return None

    history_a, history_b = combined_prior_points(record)
    raw_probability = record.probability_a_match
    probability_a = shrink_probability_to_neutral(raw_probability)
    return ShadowModelOutput(
        challenger_id=CHALLENGER_ID,
        p_player_a=probability_a,
        p_player_b=1.0 - probability_a,
        component_probabilities={
            "dynamic_serve_return_raw": raw_probability,
            "neutral_reference": 0.5,
        },
        diagnostics={
            "history_points_a": history_a,
            "history_points_b": history_b,
            "history_threshold": MIN_PRIOR_POINTS_PER_PLAYER,
            "shrinkage_to_neutral": SHRINKAGE_TO_NEUTRAL,
            "retained_raw_weight": RETAINED_RAW_WEIGHT,
            "development_derived_rule": True,
        },
    )
