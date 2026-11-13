"""Read-only identity regression. Never changes settlements or eligibility."""

import unittest

from scripts import web_shadow_wta_result_core as core

TOURNAMENT = {"group_id": 123, "year": 2026}

def row(match_id="LS001", round_id=1, first="Alice", event="123"):
    return {"DrawMatchType": "S", "DrawLevelType": "M", "EventID": event,
            "EventYear": 2026, "MatchID": match_id, "RoundID": round_id,
            "PlayerNameFirstA": first, "PlayerNameLastA": "Smith",
            "PlayerNameFirstB": "Bob", "PlayerNameLastB": "Jones",
            "MatchState": "F"}

def pending(source_id=None, round_name="R32"):
    return {"source_match_id": source_id, "tournament": TOURNAMENT,
            "player_pair": ("alicesmith", "bobjones"), "round": round_name}

class TestRoundIdentityDiagnostic(unittest.TestCase):
    def test_legacy_numeric_round_mismatch_unresolved(self):
        self.assertIsNone(core._match_row(pending(), [row(round_id=1)]))

    def test_legacy_matching_numeric_round(self):
        self.assertEqual(core._match_row(pending(), [row(round_id=5)])["source_match_id"], "LS001")

    def test_exact_id_retains_round_discrepancy(self):
        self.assertEqual(core._match_row(pending("LS001"), [row(round_id=1)])["round"], "F")

    def test_exact_id_wrong_player_fails_closed(self):
        with self.assertRaises(core.WtaPlayerIdentityConflict):
            core._match_row(pending("LS001"), [row(first="Carol")])

    def test_exact_id_missing_does_not_fallback(self):
        self.assertIsNone(core._match_row(pending("LS002"), [row()]))

    def test_legacy_duplicate_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            core._match_row(pending(), [row("LS001", 5), row("LS002", 5)])

    def test_legacy_textual_round_excluded(self):
        self.assertIsNone(core._match_row(pending(round_name="QF"), [row(round_id="Q")]))

    def test_exact_textual_round_supported(self):
        self.assertEqual(core._match_row(pending("LS001", "QF"), [row(round_id="Q")])["round"], "QF")

    def test_event_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "tournament identity mismatch"):
            core._match_row(pending("LS001"), [row(event="999")])
