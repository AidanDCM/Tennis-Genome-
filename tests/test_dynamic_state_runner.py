from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from tennis_genome.data.canonical import HistoricalMatch, MatchOutcome, MatchStats, PreMatchState
from tennis_genome.research_workbench import ChronologySemantics
from tennis_genome.research_workbench.dynamic_state_development import (
    DynamicStateDevelopmentSpec,
)
from tennis_genome.research_workbench.dynamic_state_runner import (
    _CODE_COMPONENTS,
    build_dynamic_state_development_evidence,
)


def _matches(*, tour: str = "ATP") -> list[HistoricalMatch]:
    players = ("P1", "P2", "P3", "P4")
    matches: list[HistoricalMatch] = []
    sequence = 0
    for year_index, year in enumerate((2022, 2023, 2024)):
        year_start = date(year, 1, 3)
        for index in range(24):
            player_a = players[index % len(players)]
            player_b = players[(index + 1) % len(players)]
            match_id = f"{tour.lower()}-{year}-{index:03d}"
            event_date = year_start + timedelta(days=index * 7)
            a_won = (index + year_index) % 2 == 0
            won_a = 40 if a_won else 34
            won_b = 34 if a_won else 40
            matches.append(
                HistoricalMatch(
                    pre_match=PreMatchState(
                        match_id=match_id,
                        tour=tour,  # type: ignore[arg-type]
                        event_date=event_date,
                        source_order=sequence,
                        tournament_id=f"event-{year}-{index:03d}",
                        tournament_name="Synthetic Runner",
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
    for relative in _CODE_COMPONENTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    return tmp_path


def _spec(**overrides: object) -> DynamicStateDevelopmentSpec:
    payload: dict[str, object] = {
        "tour": "ATP",
        "test_years": (2023, 2024),
        "min_train_rows": 10,
        "bootstrap_resamples": 100,
        "permutation_resamples": 100,
        "inference_seed": 19,
    }
    payload.update(overrides)
    return DynamicStateDevelopmentSpec(**payload)


def test_runner_binds_manifest_availability_population_code_and_report(tmp_path: Path) -> None:
    evidence = build_dynamic_state_development_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="a" * 64,
        schema_version="canonical-v3",
        repo_root=_repo_root(tmp_path),
    )

    assert evidence.source_manifest_sha256 == "a" * 64
    assert evidence.dataset_fingerprint.chronology_semantics == (
        ChronologySemantics.EVENT_DATE_MATCH_ID
    )
    assert evidence.dataset_fingerprint.source_manifest_sha256 == "a" * 64
    assert evidence.dataset_fingerprint.availability_contract_sha256 == (
        evidence.availability_registry_sha256
    )
    assert len(evidence.code_fingerprint.components) == len(_CODE_COMPONENTS)
    assert evidence.report.experiment_spec_sha256 == _spec().semantic_sha256
    assert evidence.report.evidence_role == "DEVELOPMENT_ONLY"


def test_runner_identity_changes_when_source_manifest_changes(tmp_path: Path) -> None:
    repo = _repo_root(tmp_path)
    first = build_dynamic_state_development_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="a" * 64,
        schema_version="canonical-v3",
        repo_root=repo,
    )
    second = build_dynamic_state_development_evidence(
        matches=_matches(),
        spec=_spec(),
        source_manifest_sha256="b" * 64,
        schema_version="canonical-v3",
        repo_root=repo,
    )

    assert first.availability_registry_sha256 != second.availability_registry_sha256
    assert first.dataset_fingerprint.sha256 != second.dataset_fingerprint.sha256
    assert first.semantic_sha256 != second.semantic_sha256


def test_runner_fails_closed_when_required_code_component_is_missing(tmp_path: Path) -> None:
    repo = _repo_root(tmp_path)
    (repo / _CODE_COMPONENTS[0]).unlink()

    with pytest.raises(ValueError, match="required code component is missing"):
        build_dynamic_state_development_evidence(
            matches=_matches(),
            spec=_spec(),
            source_manifest_sha256="a" * 64,
            schema_version="canonical-v3",
            repo_root=repo,
        )


def test_runner_rejects_mixed_tours_before_evidence_creation(tmp_path: Path) -> None:
    matches = _matches()
    matches.extend(_matches(tour="WTA")[:1])

    with pytest.raises(ValueError, match="requires only ATP matches"):
        build_dynamic_state_development_evidence(
            matches=matches,
            spec=_spec(),
            source_manifest_sha256="a" * 64,
            schema_version="canonical-v3",
            repo_root=_repo_root(tmp_path),
        )
