from tennis_genome.experiments.family_lab import FAMILY_FEATURES
from tennis_genome.experiments.family_recent_diagnostic import (
    run_recent_family_diagnostic,
)
from tests.test_family_lab import _match


def test_recent_diagnostic_reports_exact_recent_year_block() -> None:
    matches = []
    for year in (2019, 2020, 2021, 2022, 2023, 2024):
        for index in range(12):
            matches.append(_match(index, year, a_won=(index + year) % 3 != 0))

    report = run_recent_family_diagnostic(
        matches,
        min_train_matches=10,
        recent_year_count=3,
    )

    assert report.recent_years == (2022, 2023, 2024)
    assert {item.family for item in report.families} == set(FAMILY_FEATURES)
    assert all(item.n > 0 for item in report.families)
    assert all(len(item.yearly) == 3 for item in report.families)
    assert all(
        tuple(year.year for year in item.yearly) == report.recent_years
        for item in report.families
    )
