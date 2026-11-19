"""Metamorphic regression for duplicate tournament status conflicts."""
from itertools import permutations

from research.wta_index_discovery_prototype import discover


def test_conflicting_duplicate_permutations_quarantined():
    rows = [
        {"tournamentGroup": {"id": 10}, "year": 2026, "endDate": "2026-11-22", "status": "past"},
        {"tournamentGroup": {"id": 10}, "year": 2026, "endDate": "2026-11-22", "status": "future"},
        {"tournamentGroup": {"id": 11}, "year": 2026, "endDate": "2026-11-22", "status": "future"},
        {"tournamentGroup": {"id": 12}, "year": 2026, "endDate": "2026-11-22", "status": "future"},
        {"tournamentGroup": {"id": 12}, "year": 2026, "endDate": "2026-11-22", "status": "future"},
    ]
    for perm in permutations(rows):
        out = discover([{"content": list(perm)}], "2026-11-17T12:00:00Z")
        assert [r["group_id"] for r in out["candidates"]] == [11, 12]
        assert out["excluded"] == {"conflicting_duplicate": 2, "duplicate": 1}
        assert out["production_eligible"] is False
