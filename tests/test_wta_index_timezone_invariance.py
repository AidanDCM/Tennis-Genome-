"""UTC observation invariance for non-production tournament discovery."""
from research.wta_index_discovery_prototype import discover


def test_equivalent_observation_instants_are_invariant():
    pages = [{"content": [{
        "tournamentGroup": {"id": 12}, "year": 2026,
        "endDate": "2026-11-17", "status": "future",
    }]}]
    timestamps = [
        "2026-11-17T23:30:00Z",
        "2026-11-18T01:30:00+02:00",
        "2026-11-17T18:30:00-05:00",
    ]
    results = [discover(pages, timestamp) for timestamp in timestamps]
    assert results[0] == results[1] == results[2]
    assert len(results[0]["candidates"]) == 1
    assert all(result["production_eligible"] is False for result in results)
