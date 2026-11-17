"""Synthetic tests only; index schema requires retained-artifact validation."""
import unittest

from research.wta_index_discovery_prototype import discover


class DiscoveryTests(unittest.TestCase):
    def test_rejects_ended_invalid_duplicate(self):
        rows = [
            {"tournamentGroup": {"id": 1}, "year": 2026, "endDate": "2026-11-01"},
            {"tournamentGroup": {"id": 2}, "year": 2026, "endDate": "2026-11-20"},
            {"tournamentGroup": {"id": 2}, "year": 2026, "endDate": "2026-11-20"},
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
            {"ended": 1, "duplicate": 1, "invalid_identity_or_date": 3},
        )
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
