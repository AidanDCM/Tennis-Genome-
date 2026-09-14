from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.research_workbench.dynamic_state_search_family import (
    DynamicStateLessAggressiveFamilySpec,
)
from tennis_genome.research_workbench.dynamic_state_search_runner import (
    _SEARCH_CODE_COMPONENTS,
    DynamicStateCandidateTourResult,
    _aggregate_candidates,
    run_dynamic_state_less_aggressive_search,
)


def _matches(tour: str) -> list[HistoricalMatch]:
    players = ("P1", "P2", "P3", "P4")
    rows: list[HistoricalMatch] = []
    sequence = 0
    for year_index, year in enumerate((2022, 2023, 2024)):
        start = date(year, 1, 3)
        for index in range(28):
            a = players[index % 4]
            b = players[(index + 1) % 4]
            match_id = f"{tour.lower()}-{year}-{index:03d}"
            a_won = (index + year_index) % 2 == 0
            won_a = 40 if a_won else 34
            won_b = 34 if a_won else 40
            rows.append(
                HistoricalMatch(
                    pre_match=PreMatchState(
                        match_id=match_id,
                        tour=tour,  # type: ignore[arg-type]
                        event_date=start + timedelta(days=index * 7),
                        source_order=sequence,
                        tournament_id=f"event-{year}-{index:03d}",
                        tournament_name="Search Runner Synthetic",
                        tournament_level="A",
                        surface="Hard",
                        round="R32",
                        best_of=3,
                        player_a_id=a,
                        player_b_id=b,
                        player_a_name=a,
                        player_b_name=b,
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
    return rows


def _repo_root(tmp_path: Path) -> Path:
    for relative in _SEARCH_CODE_COMPONENTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    return tmp_path


def _small_spec() -> DynamicStateLessAggressiveFamilySpec:
    return DynamicStateLessAggressiveFamilySpec(
        test_years=(2023, 2024),
        min_train_rows=10,
        bootstrap_resamples=50,
        permutation_resamples=50,
        inference_seed=17,
    )


def test_search_evaluates_every_registered_candidate_tour_cell(tmp_path: Path) -> None:
    evidence = run_dynamic_state_less_aggressive_search(
        atp_matches=_matches("ATP"),
        wta_matches=_matches("WTA"),
        atp_source_manifest_sha256="a" * 64,
        wta_source_manifest_sha256="b" * 64,
        atp_schema_version="canonical-v3",
        wta_schema_version="canonical-v3",
        repo_root=_repo_root(tmp_path),
        spec=_small_spec(),
    )

    report = evidence.report
    assert len(report.candidate_tour_results) == 16
    assert len(report.candidate_aggregates) == 8
    assert report.primary_claim_count == 32
    assert report.bonferroni_alpha == 0.0015625
    assert {row.tour for row in report.candidate_tour_results} == {"ATP", "WTA"}
    assert len({row.candidate_id for row in report.candidate_tour_results}) == 8
    assert evidence.atp_dataset_fingerprint.source_manifest_sha256 == "a" * 64
    assert evidence.wta_dataset_fingerprint.source_manifest_sha256 == "b" * 64
    assert len(evidence.search_code_fingerprint.components) == len(_SEARCH_CODE_COMPONENTS)


def _result(
    candidate_id: str,
    tour: str,
    *,
    brier: float,
    log_loss: float,
    n: int = 100,
) -> DynamicStateCandidateTourResult:
    return DynamicStateCandidateTourResult(
        candidate_id=candidate_id,
        tour=tour,  # type: ignore[arg-type]
        development_spec_sha256="a" * 64,
        development_report_sha256="b" * 64,
        n_predictions=n,
        fixed_brier=0.20,
        candidate_brier=0.20 - brier,
        brier_improvement=brier,
        brier_p_value=0.5,
        brier_familywise_supported=False,
        fixed_log_loss=0.60,
        candidate_log_loss=0.60 - log_loss,
        log_loss_improvement=log_loss,
        log_loss_p_value=0.5,
        log_loss_familywise_supported=False,
    )


def test_selection_returns_no_candidate_if_any_four_cell_sign_gate_fails() -> None:
    spec = DynamicStateLessAggressiveFamilySpec()
    rows: list[DynamicStateCandidateTourResult] = []
    for candidate in spec.candidates:
        rows.extend(
            [
                _result(candidate.candidate_id, "ATP", brier=0.001, log_loss=0.002),
                _result(candidate.candidate_id, "WTA", brier=0.001, log_loss=-0.0001),
            ]
        )

    aggregates, eligible, selected = _aggregate_candidates(
        spec=spec,
        results=tuple(rows),
    )

    assert len(aggregates) == 8
    assert eligible == ()
    assert selected is None


def test_selection_uses_pooled_log_loss_then_brier_then_id() -> None:
    spec = DynamicStateLessAggressiveFamilySpec()
    first = spec.candidates[0].candidate_id
    second = spec.candidates[1].candidate_id
    rows: list[DynamicStateCandidateTourResult] = []
    for candidate in spec.candidates:
        if candidate.candidate_id == first:
            atp = _result(first, "ATP", brier=0.001, log_loss=0.003, n=100)
            wta = _result(first, "WTA", brier=0.001, log_loss=0.003, n=100)
        elif candidate.candidate_id == second:
            atp = _result(second, "ATP", brier=0.004, log_loss=0.002, n=100)
            wta = _result(second, "WTA", brier=0.004, log_loss=0.002, n=100)
        else:
            atp = _result(
                candidate.candidate_id,
                "ATP",
                brier=-0.001,
                log_loss=-0.001,
            )
            wta = _result(
                candidate.candidate_id,
                "WTA",
                brier=-0.001,
                log_loss=-0.001,
            )
        rows.extend([atp, wta])

    _, eligible, selected = _aggregate_candidates(spec=spec, results=tuple(rows))

    assert eligible == tuple(sorted((first, second)))
    assert selected == first
