from tennis_genome.experiments.core_holdout import run_core_holdout
from tests.test_family_lab import _match


def test_core_holdout_freezes_mapping_and_scores_future_year() -> None:
    matches = []
    for year in (2023, 2024, 2025, 2026):
        for index in range(12):
            matches.append(_match(index, year, a_won=(index + year) % 3 != 0))

    report = run_core_holdout(
        matches,
        benchmark_name="elo",
        benchmark_features=("elo_logit",),
        candidates={
            "elo_plus_form": (
                "elo_logit",
                "form_result_30_diff",
                "form_result_90_diff",
            )
        },
        train_end_year=2025,
        holdout_year=2026,
    )

    assert report.training_n == 36
    assert report.holdout_n == 12
    assert report.benchmark.n == 12
    assert report.sequential_state_updates is True
    assert report.frozen_predictive_mapping is True
    assert len(report.candidates) == 1
    assert report.candidates[0].score.n == 12


def test_core_holdout_rejects_non_future_holdout() -> None:
    matches = [_match(index, 2025, a_won=index % 2 == 0) for index in range(12)]

    try:
        run_core_holdout(
            matches,
            benchmark_name="elo",
            benchmark_features=("elo_logit",),
            candidates={"same": ("elo_logit",)},
            train_end_year=2025,
            holdout_year=2025,
        )
    except ValueError as exc:
        assert "holdout_year must be after" in str(exc)
    else:
        raise AssertionError("expected invalid holdout year to fail")
