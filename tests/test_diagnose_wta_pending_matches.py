"""Adversarial, read-only WTA diagnostic tests.

No test calls the result writer or assigns a winner.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.diagnose_wta_pending_matches import diagnose_match, diagnose_pending


def _pending(*, exact: bool = False) -> dict:
    return {
        "match_id": "web:wta:1024:2026:LS017" if exact else "legacy:match",
        "prediction_path": "unchanged/prediction.json",
        "prediction_sha256": "a" * 64,
        "player_a": "Alpha One",
        "player_b": "Beta Two",
        "round": "R32",
        "scheduled_start": datetime(2026, 9, 22, 10, tzinfo=UTC),
        "source_match_id": "LS017" if exact else None,
        "tournament": {"group_id": 1024, "year": 2026},
    }


def _row(**changes: object) -> dict:
    row = {
        "EventID": "1024",
        "EventYear": 2026,
        "DrawMatchType": "S",
        "DrawLevelType": "M",
        "MatchID": "LS017",
        "RoundID": "1",
        "MatchState": "F",
        "PlayerNameFirstA": "Alpha",
        "PlayerNameLastA": "One",
        "PlayerNameFirstB": "Beta",
        "PlayerNameLastB": "Two",
    }
    return {**row, **changes}


def test_legacy_round_discrepancy_does_not_relabel_source() -> None:
    out = diagnose_match(_pending(), [_row()])
    assert out["reason"] == "legacy_round_discrepancy"
    assert out["source_round_id_raw"] == "1"
    assert out["legacy_compiler_round_interpretation"] == "F"
    assert out["prediction_round"] == "R32"
    assert out["candidate_count"] == 1
    assert out["diagnostic_only"] is True
    assert out["production_eligible"] is False
    assert "winner" not in out


def test_strict_round_candidate_is_still_not_settlement() -> None:
    out = diagnose_match(_pending(), [_row(RoundID="5")])
    assert out["reason"] == "legacy_strict_round_candidate_only"
    assert "winner" not in out


def test_legacy_pair_absent_and_qualifying_excluded() -> None:
    assert diagnose_match(_pending(), [])["reason"] == "legacy_pair_absent"
    assert diagnose_match(_pending(), [_row(DrawLevelType="Q")])[
        "reason"
    ] == "legacy_pair_absent"


def test_legacy_multiple_candidates_are_ambiguous() -> None:
    out = diagnose_match(_pending(), [_row(), _row(MatchID="LS099")])
    assert out["reason"] == "legacy_pair_ambiguous"
    assert out["candidate_count"] == 2


@pytest.mark.parametrize("token", ["+1024", "1025", "1024.0", "1e3"])
def test_legacy_other_tournament_is_never_a_candidate(token: str) -> None:
    out = diagnose_match(_pending(), [_row(EventID=token)])
    assert out["reason"] == "legacy_pair_absent"


def test_exact_player_conflict_never_falls_back_to_pair_match() -> None:
    wrong = _row(PlayerNameFirstA="Gamma")
    right_pair = _row(MatchID="LS090")
    out = diagnose_match(_pending(exact=True), [wrong, right_pair])
    assert out["reason"] == "exact_id_player_conflict"
    assert out["source_match_id"] == "LS017"
    assert out["candidate_count"] == 1


def test_exact_duplicate_and_missing_ids_fail_closed() -> None:
    assert diagnose_match(_pending(exact=True), [])[
        "reason"
    ] == "exact_id_absent"
    assert diagnose_match(_pending(exact=True), [_row(), _row()])[
        "reason"
    ] == "exact_id_ambiguous"


def test_exact_wrong_event_or_draw_fails_closed() -> None:
    assert diagnose_match(_pending(exact=True), [_row(EventID="1025")])[
        "reason"
    ] == "exact_id_event_conflict"
    assert diagnose_match(_pending(exact=True), [_row(DrawLevelType="Q")])[
        "reason"
    ] == "exact_id_draw_conflict"


def test_exact_matching_players_only_identifies_candidate() -> None:
    out = diagnose_match(_pending(exact=True), [_row()])
    assert out["reason"] == "exact_id_identity_candidate_only"
    assert out["source_round_id_raw"] == "1"
    assert "winner" not in out


def test_textual_round_does_not_get_invented_numeric_meaning() -> None:
    out = diagnose_match(_pending(), [_row(RoundID="Q")])
    assert out["reason"] == "legacy_round_discrepancy"
    assert out["legacy_compiler_round_interpretation"] is None


def test_retained_main_snapshot_pending_crosswalk_is_diagnostic_only() -> None:
    root = Path(__file__).resolve().parents[1]
    snapshot = (
        root / "web-shadow/result-evidence/wta-results-20261109t083951z/sources"
    )
    report = diagnose_pending(
        config_path=root / "web-shadow/result-config.json",
        scorecard_path=root / "web-shadow/scorecard.json",
        acquisition_manifest_path=snapshot / "acquisition-manifest.json",
        source_root=snapshot,
        repo_root=root,
        observed_at="2026-11-09T08:39:51+00:00",
    )
    assert report["production_eligible"] is False
    assert report["pending_prediction_count"] == 15
    assert report["verified_tournament_source_count"] == 10
    assert report["reason_counts"] == {
        "exact_id_player_conflict": 2,
        "legacy_pair_absent": 1,
        "legacy_round_discrepancy": 12,
    }
    assert len({x["match_id"] for x in report["diagnostics"]}) == 15
    assert all("winner" not in row for row in report["diagnostics"])
