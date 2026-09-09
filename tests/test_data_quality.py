from datetime import date

import pytest

from tennis_genome.data.quality import audit_historical_matches, raise_for_quality_errors
from tests.factories import make_match


def test_duplicate_match_ids_are_fatal():
    first = make_match(
        match_id="duplicate",
        event_date=date(2026, 1, 1),
        player_a_id="a",
        player_b_id="b",
        a_won=True,
    )
    second = make_match(
        match_id="duplicate",
        event_date=date(2026, 1, 2),
        player_a_id="c",
        player_b_id="d",
        a_won=False,
    )

    issues = audit_historical_matches([first, second])
    assert any(issue.code == "duplicate_match_id" for issue in issues)
    with pytest.raises(ValueError):
        raise_for_quality_errors(issues)


def test_clean_matches_pass_quality_gate():
    match = make_match(
        match_id="clean",
        event_date=date(2026, 1, 1),
        player_a_id="a",
        player_b_id="b",
        a_won=True,
        rank_a=10,
        rank_b=20,
    )
    issues = audit_historical_matches([match])
    raise_for_quality_errors(issues)
    assert not [issue for issue in issues if issue.severity == "error"]
