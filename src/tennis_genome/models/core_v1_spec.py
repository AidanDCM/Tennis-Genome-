from __future__ import annotations

from typing import Literal

from tennis_genome.experiments.family_lab import FAMILY_FEATURES

Tour = Literal["ATP", "WTA"]
Grade = Literal["A", "B", "C", "D"]

ELO_FEATURES = ("elo_logit",)
SERVE_RETURN_FEATURES = ("serve_return_edge",)

FAMILY_GRADES: dict[Tour, dict[str, Grade]] = {
    "ATP": {
        "overall_elo": "A",
        "serve_return": "A",
        "recent_form": "A",
        "workload_rest_proxy": "A",
        "age_career_physical": "A",
        "age_fatigue_interaction": "B",
        "head_to_head": "B",
        "handedness_matchup": "D",
        "surface_tournament_context": "A",
        "pure_surface_elo": "D",
    },
    "WTA": {
        "overall_elo": "A",
        "serve_return": "B",
        "recent_form": "A",
        "workload_rest_proxy": "A",
        "age_career_physical": "C",
        "age_fatigue_interaction": "B",
        "head_to_head": "C",
        "handedness_matchup": "D",
        "surface_tournament_context": "A",
        "pure_surface_elo": "D",
    },
}

ATP_A_FAMILIES = (
    "recent_form",
    "workload_rest_proxy",
    "age_career_physical",
    "surface_tournament_context",
)
ATP_B_FAMILIES = (
    "age_fatigue_interaction",
    "head_to_head",
)
WTA_A_FAMILIES = (
    "recent_form",
    "workload_rest_proxy",
    "surface_tournament_context",
)
WTA_B_FAMILIES = ("age_fatigue_interaction",)

# The family laboratory used Elo + serve/return as its common control on both
# tours. Keep that unchanged as the sealed-holdout benchmark even though WTA
# serve/return itself retains a B grade.
HISTORICAL_BENCHMARK_FEATURES = ELO_FEATURES + SERVE_RETURN_FEATURES


def _family_features(families: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(feature for family in families for feature in FAMILY_FEATURES[family])


def strict_a_features(tour: Tour) -> tuple[str, ...]:
    if tour == "ATP":
        return (
            ELO_FEATURES
            + SERVE_RETURN_FEATURES
            + _family_features(ATP_A_FAMILIES)
        )
    if tour == "WTA":
        return ELO_FEATURES + _family_features(WTA_A_FAMILIES)
    raise ValueError(f"unsupported tour: {tour}")


def a_plus_b_features(tour: Tour) -> tuple[str, ...]:
    if tour == "ATP":
        return strict_a_features(tour) + _family_features(ATP_B_FAMILIES)
    if tour == "WTA":
        return (
            strict_a_features(tour)
            + SERVE_RETURN_FEATURES
            + _family_features(WTA_B_FAMILIES)
        )
    raise ValueError(f"unsupported tour: {tour}")
