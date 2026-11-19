"""Provider-shaped replay fixture derived from the 2026-11-17 retained index ledger.

These nine records are reconstructed, NOT byte-for-byte source snapshots.
See research/ledger/2026-11-17-wta-provider-index-replay.md.
"""
from research.wta_index_discovery_prototype import discover


def test_provider_shaped_candidate_and_stale_config_ids():
    candidates = [
        (2076, "2026-11-22", "inProgress"),
        (2052, "2026-11-29", "future"),
        (1118, "2026-12-06", "future"),
        (2056, "2026-12-06", "future"),
        (1072, "2026-12-20", "future"),
    ]
    ended = [
        (1023, "2026-11-01"),
        (1056, "2026-11-01"),
        (1074, "2026-11-08"),
        (1148, "2026-11-08"),
    ]
    rows = [
        {
            "tournamentGroup": {"id": group_id},
            "year": 2026,
            "endDate": end_date,
            "status": status,
        }
        for group_id, end_date, status in candidates
    ]
    rows += [
        {
            "tournamentGroup": {"id": group_id},
            "year": 2026,
            "endDate": end_date,
            "status": "past",
        }
        for group_id, end_date in ended
    ]
    result = discover(
        [{"content": rows[:6]}, {"content": rows[6:]}],
        "2026-11-17T08:01:39Z",
    )
    assert {row["group_id"] for row in result["candidates"]} == {
        2076, 2052, 1118, 2056, 1072,
    }
    assert result["excluded"] == {"non_active_status": 4}
    assert result["production_eligible"] is False
