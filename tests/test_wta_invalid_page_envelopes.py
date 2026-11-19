"""Metamorphic malformed-page isolation regression; research-only."""
from itertools import permutations

from research.wta_index_discovery_prototype import discover


def test_invalid_page_envelopes_do_not_change_valid_candidates():
    valid = {"content": [{"tournamentGroup": {"id": 81}, "year": 2026,
                          "startDate": "2026-11-19", "endDate": "2026-11-25",
                          "status": "future"}]}
    bad = [None, {}, [], {"content": None}, {"content": {}},
           {"content": "oops"}, {"content": [None]}]
    baseline = discover([valid], "2026-11-19T12:00:00Z")
    assert baseline["candidates"] == [
        {"group_id": 81, "year": 2026, "end_date": "2026-11-25"}
    ]
    assert baseline["production_eligible"] is False
    for malformed in bad:
        for pages in permutations([valid, malformed]):
            out = discover(pages, "2026-11-19T12:00:00Z")
            assert out["candidates"] == baseline["candidates"]
            assert out["production_eligible"] is False
            if isinstance(malformed, dict) and isinstance(malformed.get("content"), list):
                assert out["excluded"].get("invalid_identity_or_date") == 1
            else:
                assert out["excluded"].get("invalid_page_envelope") == 1
