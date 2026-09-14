from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.research_workbench.dynamic_state_development import (
    DynamicStateDevelopmentSpec,
)
from tennis_genome.research_workbench.dynamic_state_diagnostic import (
    DynamicStateFailureDiagnosticSpec,
)
from tennis_genome.research_workbench.dynamic_state_diagnostic_runner import (
    _DIAGNOSTIC_CODE_COMPONENTS,
    build_dynamic_state_failure_diagnostic_evidence,
)


def _matches() -> list[HistoricalMatch]:
    players = ("P1", "P2", "P3", "P4")
    matches: list[HistoricalMatch] = []
    sequence = 0
    for year_index, year in enumerate((2022, 2023, 2024)):
        start = date(year, 1, 3)
        for index in range(24):
            player_a = players[index % 4]
            player_b = players[(index + 1) % 4]
            match_id = f"m-{year}-{index:03d}"
            a_won = (index + year_index) % 2 == 0
            won_a = 40 if a_won else 34
            won_b = 34 if a_won else 40
            matches.append(
                HistoricalMatch(
                    pre_match=PreMatchState(
                        match_id=match_id,
                        tour="ATP",
                        event_date=start + timedelta(days=index * 7),
                        source_order=sequence,
                        tournament_id=f"event-{year}-{index:03d}",
                        tournament_name="Diagnostic Runner Synthetic",
                        tournament_level="A",
                        surface="Hard",
                        round="R32",
                        best_of=3,
                        player_a_id=player_a,
                        player_b_id=player_b,
                        player_a_name=player_a,
                        player_b_name=player_b,
                        rank_a=None,
                        rank_b=None,
                        rank_points_a=None,
                        rank_points_b=None,
                    ),
                    outcome=MatchOutcome(
                        match_id=match_id,
                        a_won=a_won,
                        score="synthetic",
                        retirement=False,
                        walkover=False,
                    ),
                    stats=MatchStats(
                        match_id=match_id,
                        service_points_a=60,
                        service_points_b=60,
                        first_serve_points_won_a=won_a,
                        first_serve_points_won_b=won_b,
                        second_serve_points_won_a=0,
                        second_serve_points_won_b=0,
                    ),
                )
            )
            sequence += 1
    return matches


def _repo_root(tmp_path: Path) -> Path:
    for relative in _DIAGNOSTIC_CODE_COMPONENTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    return tmp_path


def _spec() -> DynamicStateFailureDiagnosticSpec:
    development = DynamicStateDevelopmentSpec(
        tour="ATP",
        test_years=(2023, 2024),
        min_train_rows=10,
        bootstrap_resamples=100,
        permutation_resamples=100,
        inference_seed=23,
    )
    return DynamicStateFailureDiagnosticSpec(development_spec=development)


def test_diagnostic_evidence_binds_exact_parent_report_and_code(tmp_path: Path) -> None:
    evidence = build_dynamic_state_failure_diagnostic_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="a" * 64,
        schema_version="canonical-v3",
        repo_root=_repo_root(tmp_path),
    )

    assert evidence.report.development_report_sha256 == (
        evidence.parent_evidence.report.semantic_sha256
    )
    assert evidence.parent_evidence.source_manifest_sha256 == "a" * 64
    assert len(evidence.diagnostic_code_fingerprint.components) == len(
        _DIAGNOSTIC_CODE_COMPONENTS
    )
    assert evidence.report.interpretation_boundary == (
        "DESCRIPTIVE_ONLY_NO_PARAMETER_SELECTION"
    )


def test_diagnostic_evidence_is_deterministic(tmp_path: Path) -> None:
    repo = _repo_root(tmp_path)
    first = build_dynamic_state_failure_diagnostic_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="a" * 64,
        schema_version="canonical-v3",
        repo_root=repo,
    )
    second = build_dynamic_state_failure_diagnostic_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="a" * 64,
        schema_version="canonical-v3",
        repo_root=repo,
    )

    assert first.semantic_sha256 == second.semantic_sha256


def test_diagnostic_evidence_fails_if_code_component_is_missing(tmp_path: Path) -> None:
    repo = _repo_root(tmp_path)
    (repo / _DIAGNOSTIC_CODE_COMPONENTS[0]).unlink()

    with pytest.raises(ValueError, match="required diagnostic code component is missing"):
        build_dynamic_state_failure_diagnostic_evidence(
            matches=_matches(),
            spec=_spec(),
            source_manifest_sha256="a" * 64,
            schema_version="canonical-v3",
            repo_root=repo,
        )
