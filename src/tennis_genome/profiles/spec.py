from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tennis_genome.data.canonical import Tour

ProfileFieldRole = Literal["core", "conditional", "descriptive", "excluded"]


@dataclass(frozen=True)
class ProfileFieldPermission:
    field_name: str
    atp_role: ProfileFieldRole
    wta_role: ProfileFieldRole
    rationale: str


PROFILE_FIELD_PERMISSIONS: tuple[ProfileFieldPermission, ...] = (
    ProfileFieldPermission(
        "elo_rating",
        "core",
        "core",
        "Overall Elo passed chronological and forward validation on both tours.",
    ),
    ProfileFieldPermission(
        "serve_rating",
        "core",
        "conditional",
        "Opponent-adjusted serve/return is A/Core ATP and B/Conditional WTA.",
    ),
    ProfileFieldPermission(
        "return_rating",
        "core",
        "conditional",
        "Opponent-adjusted serve/return is A/Core ATP and B/Conditional WTA.",
    ),
    ProfileFieldPermission(
        "form_result_30",
        "core",
        "core",
        "Recent form survived the foundational family lab on both tours.",
    ),
    ProfileFieldPermission(
        "form_result_90",
        "core",
        "core",
        "Recent form survived the foundational family lab on both tours.",
    ),
    ProfileFieldPermission(
        "form_point_30",
        "core",
        "core",
        "Recent point residual form survived as part of the form family.",
    ),
    ProfileFieldPermission(
        "form_point_90",
        "core",
        "core",
        "Recent point residual form survived as part of the form family.",
    ),
    ProfileFieldPermission(
        "event_gap_days",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "minutes_7",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "minutes_14",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "minutes_28",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "matches_14",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "matches_28",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "previous_event_minutes",
        "core",
        "core",
        "The source-date workload/rest proxy survived both tour family labs.",
    ),
    ProfileFieldPermission(
        "age_years",
        "core",
        "descriptive",
        "ATP age/career/physical is A/Core; WTA age was demoted to C after modern-regime failure.",
    ),
    ProfileFieldPermission(
        "height_cm",
        "core",
        "descriptive",
        "Stored with the ATP validated physical family; WTA physical family is not promoted.",
    ),
    ProfileFieldPermission(
        "ranking",
        "descriptive",
        "descriptive",
        "Ranking is retained for context/UI but Elo is the validated strength baseline.",
    ),
    ProfileFieldPermission(
        "ranking_points",
        "descriptive",
        "descriptive",
        "Ranking points are source context, not a promoted Profile Strength input.",
    ),
    ProfileFieldPermission(
        "hand",
        "descriptive",
        "descriptive",
        "Handedness/basic matchup was rejected under the current representation.",
    ),
    ProfileFieldPermission(
        "ioc",
        "descriptive",
        "descriptive",
        "Country is identity/context only and has no validated predictive permission.",
    ),
    ProfileFieldPermission(
        "prior_matches",
        "descriptive",
        "descriptive",
        "Data depth informs uncertainty but is not automatically predictive strength.",
    ),
    ProfileFieldPermission(
        "prior_serve_points",
        "descriptive",
        "descriptive",
        "Data depth informs uncertainty but is not automatically predictive strength.",
    ),
    ProfileFieldPermission(
        "prior_return_points",
        "descriptive",
        "descriptive",
        "Data depth informs uncertainty but is not automatically predictive strength.",
    ),
)


def field_role(field_name: str, tour: Tour) -> ProfileFieldRole:
    for permission in PROFILE_FIELD_PERMISSIONS:
        if permission.field_name == field_name:
            return permission.atp_role if tour == "ATP" else permission.wta_role
    raise KeyError(f"unknown Player Profile v1 field: {field_name}")


def core_profile_fields(tour: Tour) -> tuple[str, ...]:
    """Return only fields currently allowed into a strict profile-derived model."""
    return tuple(
        permission.field_name
        for permission in PROFILE_FIELD_PERMISSIONS
        if (permission.atp_role if tour == "ATP" else permission.wta_role) == "core"
    )


def conditional_profile_fields(tour: Tour) -> tuple[str, ...]:
    return tuple(
        permission.field_name
        for permission in PROFILE_FIELD_PERMISSIONS
        if (permission.atp_role if tour == "ATP" else permission.wta_role)
        == "conditional"
    )
