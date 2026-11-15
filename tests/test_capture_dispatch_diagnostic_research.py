"""Diagnostic-only reconciliation.

Does not establish prediction eligibility or dispatch workflows.
"""

from datetime import UTC, datetime, timedelta

CAPTURE = ".github/workflows/prospective_provider_capture_anchor.yml"
PRODUCER = ".github/workflows/wta_forward_004_auto_shadow_chain.yml"


def missing_dispatches(
    captures, producers, now, max_age=timedelta(days=1),
    *, capture_inventory_complete=False, producer_inputs_verified=False,
    routing_mode="LEGACY_SINGLE_TARGET",
):
    """Return fresh successful capture run IDs without recorded producer dispatches.

    Caller must supply complete, independently verified inventories. Missing run
    metadata is rejected; this is not an authorization or trust-gate substitute.
    """
    if routing_mode != "LEGACY_SINGLE_TARGET":
        raise ValueError("unsupported producer routing mode; reconciliation inconclusive")
    if capture_inventory_complete is not True or producer_inputs_verified is not True:
        raise ValueError("complete captures and verified producer inputs required")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware datetime")
    if not isinstance(max_age, timedelta) or max_age < timedelta(0):
        raise ValueError("max_age must be a nonnegative timedelta")
    if any(
        run.get("path") == PRODUCER
        and run.get("event") == "workflow_dispatch"
        and (not isinstance(run.get("provider_run_id"), int)
             or isinstance(run.get("provider_run_id"), bool)
             or run.get("provider_run_id") <= 0)
        for run in producers
    ):
        raise ValueError("producer dispatch input provenance unavailable")
    if any(
        run.get("path") == PRODUCER
        and run.get("event") == "workflow_dispatch"
        and (not isinstance(run.get("id"), int)
             or isinstance(run.get("id"), bool)
             or run.get("id") <= 0)
        for run in producers
    ):
        raise ValueError("producer run identity provenance unavailable")
    producer_seen = {}
    for run in producers:
        run_id = run.get("id")
        if isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0:
            if run_id in producer_seen and producer_seen[run_id] != run:
                raise ValueError("conflicting producer records for same run ID")
            producer_seen[run_id] = run
    seen = {}
    for run in captures:
        run_id = run.get("id")
        if isinstance(run_id, int) and not isinstance(run_id, bool) and run_id > 0:
            if run_id in seen and seen[run_id] != run:
                raise ValueError("conflicting capture records for same run ID")
            seen[run_id] = run
    if any(
        run.get("path") == CAPTURE
        and run.get("event") == "workflow_dispatch"
        and (not isinstance(run.get("id"), int)
             or isinstance(run.get("id"), bool)
             or run.get("id") <= 0)
        for run in captures
    ):
        raise ValueError("capture run identity provenance unavailable")
    if any(
        run.get("path") == CAPTURE
        and run.get("event") == "workflow_dispatch"
        and run.get("conclusion") == "success"
        and (
            not isinstance(run.get("created_at"), datetime)
            or run["created_at"].tzinfo is None
            or run["created_at"].utcoffset() is None
        )
        for run in captures
    ):
        raise ValueError("successful capture timestamp provenance unavailable")
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
    def checked(captures, producers, at=now):
        return missing_dispatches(
            captures, producers, at, capture_inventory_complete=True,
            producer_inputs_verified=True,
        )

    assert checked([base], []) == [1]
    assert checked([base], [
        dict(id=10, path=PRODUCER, event="workflow_dispatch", provider_run_id=1)
    ], now) == []
    assert checked([dict(base, conclusion="failure")], []) == []
    assert checked([dict(base, head_branch="dev")], []) == []
    assert checked([dict(base, created_at=now-timedelta(days=60))], []) == []
    assert checked([dict(base, created_at=now+timedelta(minutes=1))], []) == []
    for bad_time in (None, "2026-11-15T00:00:00Z", now.replace(tzinfo=None)):
        try:
            checked([dict(base, created_at=bad_time)], [])
        except ValueError:
            pass
        else:
            raise AssertionError("invalid successful capture timestamp accepted")
    assert checked([dict(base, conclusion="failure", created_at=None)], []) == []
    assert checked([base, base], []) == [1]
    try:
        checked([], [], now.replace(tzinfo=None))
    except ValueError:
        pass
    else:
        raise AssertionError("naive observation time must be rejected")


def test_missing_dispatches_fail_closed_on_unverified_inputs():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    try:
        missing_dispatches([], [], now)
    except ValueError:
        pass
    else:
        raise AssertionError("unverified inventories must fail closed")
    try:
        missing_dispatches(
            [], [dict(path=PRODUCER, event="workflow_dispatch")], now,
            capture_inventory_complete=True, producer_inputs_verified=True,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("missing producer dispatch inputs must fail closed")


def test_conflicting_capture_identity_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    capture = dict(
        id=77, path=CAPTURE, event="workflow_dispatch", head_branch="main",
        conclusion="success", created_at=now - timedelta(hours=1),
    )
    try:
        missing_dispatches(
            [capture, dict(capture, conclusion="failure")], [], now,
            capture_inventory_complete=True, producer_inputs_verified=True,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting same-ID captures must fail closed")


def test_conflicting_producer_identity_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    producer = dict(
        id=99, path=PRODUCER, event="workflow_dispatch",
        provider_run_id=1,
    )
    kwargs = dict(
        capture_inventory_complete=True, producer_inputs_verified=True,
    )
    try:
        missing_dispatches(
            [], [producer, dict(producer, provider_run_id=2)], now,
            **kwargs,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("conflicting same-ID producers must fail closed")
    assert missing_dispatches([], [producer, producer], now, **kwargs) == []


def test_missing_producer_run_identity_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    kwargs = dict(
        capture_inventory_complete=True, producer_inputs_verified=True,
    )
    for bad_id in (None, 0, True, "99"):
        producer = dict(
            path=PRODUCER, event="workflow_dispatch",
            provider_run_id=1, id=bad_id,
        )
        try:
            missing_dispatches([], [producer], now, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid producer run identity accepted")
    valid = dict(
        path=PRODUCER, event="workflow_dispatch",
        provider_run_id=1, id=99,
    )
    assert missing_dispatches([], [valid], now, **kwargs) == []


def test_invalid_capture_run_identity_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    kwargs = dict(
        capture_inventory_complete=True, producer_inputs_verified=True,
    )
    for bad_id in (None, 0, True, "77"):
        capture = dict(
            id=bad_id, path=CAPTURE, event="workflow_dispatch",
            head_branch="main", conclusion="success",
            created_at=now - timedelta(hours=1),
        )
        try:
            missing_dispatches([capture], [], now, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid capture run identity accepted")


def test_unsupported_routing_mode_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    kwargs = dict(
        capture_inventory_complete=True, producer_inputs_verified=True,
    )
    for mode in ("FULL_SLATE_V1", "UNKNOWN", None):
        try:
            missing_dispatches([], [], now, routing_mode=mode, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("unsupported routing mode accepted")
    assert missing_dispatches(
        [], [], now, routing_mode="LEGACY_SINGLE_TARGET", **kwargs,
    ) == []


def test_invalid_observation_window_fails_closed():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    kwargs = dict(
        capture_inventory_complete=True, producer_inputs_verified=True,
    )
    for bad_now in (None, "2026-11-15T00:00:00Z", 0):
        try:
            missing_dispatches([], [], bad_now, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid observation time accepted")
    for bad_age in (None, -1, timedelta(seconds=-1)):
        try:
            missing_dispatches([], [], now, max_age=bad_age, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid age window accepted")
    assert missing_dispatches([], [], now, max_age=timedelta(0), **kwargs) == []


def test_inventory_attestations_require_literal_true():
    now = datetime(2026, 11, 15, tzinfo=UTC)
    for capture_ok, producer_ok in (("yes", True), (True, "yes"), (1, True), (True, 1)):
        try:
            missing_dispatches(
                [], [], now, capture_inventory_complete=capture_ok,
                producer_inputs_verified=producer_ok,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("non-boolean inventory attestation accepted")
    assert missing_dispatches(
        [], [], now, capture_inventory_complete=True,
        producer_inputs_verified=True,
    ) == []
