"""Synthetic tests only; index schema requires retained-artifact validation."""
import unittest

from research.wta_index_discovery_prototype import discover


class DiscoveryTests(unittest.TestCase):
    def test_rejects_ended_invalid_duplicate(self):
        rows = [
            {"tournamentGroup": {"id": 1}, "year": 2026,
             "endDate": "2026-11-01", "status": "past"},
            {"tournamentGroup": {"id": 2}, "year": 2026,
             "endDate": "2026-11-20", "status": "future"},
            {"tournamentGroup": {"id": 2}, "year": 2026,
             "endDate": "2026-11-20", "status": "future"},
            {"tournamentGroup": {"id": "3"}, "year": 2026, "endDate": "2026-11-20"},
            {"tournamentGroup": {"id": 4}, "year": 2026, "endDate": "2025-11-20"},
            {"tournamentGroup": {"id": 5}, "year": 2026, "endDate": "n/a"},
        ]
        out = discover([{"content": rows}], "2026-11-17T12:00:00Z")
        self.assertEqual(
            out["candidates"],
            [{"group_id": 2, "year": 2026, "end_date": "2026-11-20"}],
        )
        self.assertEqual(
            out["excluded"],
            {"non_active_status": 1, "duplicate": 1, "invalid_identity_or_date": 3},
        )
        self.assertIs(out["production_eligible"], False)

    def test_malformed_status_is_excluded_without_crashing(self):
        rows = [
            {"tournamentGroup": {"id": 20}, "year": 2026,
             "endDate": "2026-11-22", "status": {"value": "future"}},
            {"tournamentGroup": {"id": 21}, "year": 2026,
             "endDate": "2026-11-22", "status": ["future"]},
            {"tournamentGroup": {"id": 22}, "year": 2026,
             "endDate": "2026-11-22", "status": "future"},
        ]
        for ordered in (rows, list(reversed(rows))):
            out = discover([{"content": ordered}], "2026-11-18T12:00:00Z")
            self.assertEqual(
                [row["group_id"] for row in out["candidates"]], [22],
            )
            self.assertEqual(out["excluded"], {"invalid_status": 2})
            self.assertIs(out["production_eligible"], False)

    def test_malformed_duplicate_cannot_authorize_valid_identity(self):
        rows = [
            {"tournamentGroup": {"id": 30}, "year": 2026,
             "endDate": "2026-11-22", "status": {"value": "future"}},
            {"tournamentGroup": {"id": 30}, "year": 2026,
             "endDate": "2026-11-22", "status": "future"},
        ]
        out = discover([{"content": rows}], "2026-11-18T12:00:00Z")
        self.assertEqual(
            out["excluded"],
            {"invalid_status": 1, "malformed_status_conflict": 1},
        )
        self.assertEqual(out["candidates"], [])
        self.assertIs(out["production_eligible"], False)

    def test_rejects_naive_observation(self):
        with self.assertRaises(ValueError):
            discover([], "2026-11-17T12:00:00")

    def test_rejects_non_object_group(self):
        out = discover(
            [{"content": [{"tournamentGroup": None, "year": 2026, "endDate": "2026-11-20"}]}],
            "2026-11-17T12:00:00+00:00",
        )
        self.assertEqual(out["candidates"], [])

    def test_explicit_provider_status_vetoes_contradictory_dates(self):
        rows = [
            {"tournamentGroup": {"id": 10}, "year": 2026,
             "endDate": "2026-11-22", "status": "past"},
            {"tournamentGroup": {"id": 11}, "year": 2026,
             "endDate": "2026-11-17", "status": "past"},
            {"tournamentGroup": {"id": 12}, "year": 2026,
             "endDate": "2026-11-22", "status": "unknown"},
            {"tournamentGroup": {"id": 13}, "year": 2026,
             "endDate": "2026-11-22", "status": "inProgress"},
            {"tournamentGroup": {"id": 14}, "year": 2026,
             "endDate": "2026-11-01", "status": "future"},
        ]
        out = discover([{"content": rows}], "2026-11-17T22:00:00Z")
        self.assertEqual(
            [row["group_id"] for row in out["candidates"]], [13],
        )
        self.assertEqual(
            out["excluded"], {"non_active_status": 3, "ended": 1},
        )
        self.assertIs(out["production_eligible"], False)

    def test_rejects_inconsistent_provider_date_ranges(self):
        rows = [
            {"tournamentGroup": {"id": 91}, "year": 2026,
             "startDate": "2026-12-10", "endDate": "2026-11-22", "status": "future"},
            {"tournamentGroup": {"id": 92}, "year": 2026,
             "startDate": "not-a-date", "endDate": "2026-11-22", "status": "future"},
            {"tournamentGroup": {"id": 93}, "year": 2026,
             "startDate": "2026-11-20", "endDate": "2026-11-22", "status": "future"},
        ]
        for ordered in (rows, list(reversed(rows))):
            out = discover([{"content": ordered}], "2026-11-18T14:00:00Z")
            self.assertEqual([x["group_id"] for x in out["candidates"]], [93])
            self.assertEqual(out["excluded"], {"invalid_identity_or_date": 2})
            self.assertIs(out["production_eligible"], False)

    def test_missing_status_is_quarantined_in_any_order(self):
        rows = [
            {"tournamentGroup": {"id": 41}, "year": 2026,
             "endDate": "2026-11-22"},
            {"tournamentGroup": {"id": 42}, "year": 2026,
             "endDate": "2026-11-22", "status": "future"},
            {"tournamentGroup": {"id": 43}, "year": 2026,
             "endDate": "2026-11-22", "status": None},
        ]
        for ordered in (rows, list(reversed(rows))):
            out = discover([{"content": ordered}], "2026-11-18T12:00:00Z")
            self.assertEqual([x["group_id"] for x in out["candidates"]], [42])
            self.assertEqual(out["excluded"], {"missing_status": 2})
            self.assertIs(out["production_eligible"], False)
