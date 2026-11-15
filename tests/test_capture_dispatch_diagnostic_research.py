"""Diagnostic-only reconciliation.

Does not establish prediction eligibility or dispatch workflows.
"""

from datetime import UTC, datetime, timedelta

CAPTURE = ".github/workflows/prospective_provider_capture_anchor.yml"
PRODUCER = ".github/workflows/wta_forward_004_auto_shadow_chain.yml"


def missing_dispatches(captures, producers, now, max_age=timedelta(days=1)):
    """Return fresh successful capture run IDs without recorded producer dispatches.

    Caller must supply complete, independently verified inventories. Missing run
    metadata is rejected; this is not an authorization or trust-gate substitute.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    eligible = set()
    for run in captures:
        run_id, created = run.get("id"), run.get("created_at")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
            continue
        if (
            not isinstance(created, datetime)
            or created.tzinfo is None
            or created.utcoffset() is None
        ):
            continue
        if (
            run.get("path"),
            run.get("event"),
            run.get("head_branch"),
            run.get("conclusion"),
        ) != (CAPTURE, "workflow_dispatch", "main", "success"):
            continue
        if timedelta(0) <= now - created <= max_age:
            eligible.add(run_id)
    dispatched = {
        run.get("provider_run_id")
        for run in producers
        if run.get("path") == PRODUCER
        and run.get("event") == "workflow_dispatch"
        and isinstance(run.get("provider_run_id"), int)
    }
    return sorted(eligible - dispatched)


def test_missing_dispatches_contract():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    base = dict(
        id=1, path=CAPTURE, event="workflow_dispatch", head_branch="main",
        conclusion="success", created_at=now - timedelta(hours=2),
    )
    assert missing_dispatches([base], [], now) == [1]
    assert missing_dispatches([base], [
        dict(path=PRODUCER, event="workflow_dispatch", provider_run_id=1)
    ], now) == []
    assert missing_dispatches([dict(base, conclusion="failure")], [], now) == []
    assert missing_dispatches([dict(base, head_branch="dev")], [], now) == []
    assert missing_dispatches([dict(base, created_at=now-timedelta(days=60))], [], now) == []
    assert missing_dispatches([dict(base, created_at=now+timedelta(minutes=1))], [], now) == []
    assert missing_dispatches([dict(base, created_at=now.replace(tzinfo=None))], [], now) == []
    assert missing_dispatches([base, base], [], now) == [1]
    try:
        missing_dispatches([], [], now.replace(tzinfo=None))
    except ValueError:
        pass
    else:
        raise AssertionError("naive observation time must be rejected")
