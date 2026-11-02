from datetime import date

from scripts.audit_api_tennis_pinned_overlap import (
    _candidate_rows,
    _tournament_equivalent,
)


def test_only_reviewed_tournament_aliases_match() -> None:
    assert _tournament_equivalent("French Open", "Roland Garros")
    assert _tournament_equivalent("Rome", "Rome Masters")
    assert not _tournament_equivalent("Rome", "Linz")


def test_unique_candidate_requires_pair_winner_tournament_and_chronology() -> None:
    rows = [
        {
            "winner_id": "1",
            "loser_id": "2",
            "tourney_name": "Roland Garros",
            "tourney_date": "20260525",
        },
        {
            "winner_id": "1",
            "loser_id": "2",
            "tourney_name": "Linz",
            "tourney_date": "20260525",
        },
    ]
    args = {
        "tournament_name": "French Open",
        "first_id": "1",
        "second_id": "2",
        "winner_id": "1",
        "archive_rows": rows,
    }
    assert _candidate_rows(event_date=date(2026, 5, 27), **args) == rows[:1]
    assert _candidate_rows(event_date=date(2026, 5, 24), **args) == []
    assert _candidate_rows(event_date=date(2026, 6, 23), **args) == []
    assert _candidate_rows(event_date=date(2026, 5, 27), **{**args, "winner_id": "2"}) == []
