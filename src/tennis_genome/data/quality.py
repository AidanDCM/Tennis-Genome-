from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tennis_genome.data.canonical import HistoricalMatch

Severity = Literal["warning", "error"]


@dataclass(frozen=True)
class QualityIssue:
    code: str
    severity: Severity
    message: str
    match_id: str | None = None


def audit_historical_matches(matches: list[HistoricalMatch]) -> list[QualityIssue]:
    """Run source-agnostic integrity checks before modeling."""
    issues: list[QualityIssue] = []
    seen_ids: set[str] = set()

    for match in matches:
        state = match.pre_match
        outcome = match.outcome

        if match.match_id in seen_ids:
            issues.append(
                QualityIssue(
                    code="duplicate_match_id",
                    severity="error",
                    message="match_id appears more than once",
                    match_id=match.match_id,
                )
            )
        seen_ids.add(match.match_id)

        for label, rank in (("rank_a", state.rank_a), ("rank_b", state.rank_b)):
            if rank is not None and rank <= 0:
                issues.append(
                    QualityIssue(
                        code="invalid_rank",
                        severity="error",
                        message=f"{label} must be positive when present",
                        match_id=match.match_id,
                    )
                )

        for label, points in (
            ("rank_points_a", state.rank_points_a),
            ("rank_points_b", state.rank_points_b),
        ):
            if points is not None and points < 0:
                issues.append(
                    QualityIssue(
                        code="invalid_rank_points",
                        severity="error",
                        message=f"{label} cannot be negative",
                        match_id=match.match_id,
                    )
                )

        if outcome.retirement and outcome.walkover:
            issues.append(
                QualityIssue(
                    code="retirement_walkover_conflict",
                    severity="error",
                    message="a match cannot be both a retirement and a walkover",
                    match_id=match.match_id,
                )
            )

        if state.surface == "Unknown":
            issues.append(
                QualityIssue(
                    code="unknown_surface",
                    severity="warning",
                    message="surface is missing or not recognized",
                    match_id=match.match_id,
                )
            )

        if ":name:" in state.player_a_id or ":name:" in state.player_b_id:
            issues.append(
                QualityIssue(
                    code="fallback_player_identity",
                    severity="warning",
                    message="at least one player uses a name-hash fallback identity",
                    match_id=match.match_id,
                )
            )

    return issues


def raise_for_quality_errors(issues: list[QualityIssue]) -> None:
    errors = [issue for issue in issues if issue.severity == "error"]
    if not errors:
        return
    preview = "; ".join(f"{issue.code}:{issue.match_id or '-'}" for issue in errors[:10])
    suffix = "" if len(errors) <= 10 else f" (+{len(errors) - 10} more)"
    raise ValueError(f"canonical dataset failed quality checks: {preview}{suffix}")
