from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tennis_genome.prospective.budgeted_sportradar import (
    BudgetedSportradarStore,
    RequestBudgetExceeded,
)


def test_cached_replay_and_shared_budget_survive_new_store(tmp_path) -> None:
    moment = datetime(2026, 10, 2, 12, tzinfo=UTC)
    calls: list[str] = []

    def fetch(url, headers):
        assert headers["x-api-key"] == "private-test-value"
        calls.append(url)
        return 200, b'{"summaries":[]}'

    first = BudgetedSportradarStore(
        tmp_path, daily_limit=1, weekly_limit=1, transport=fetch, now=lambda: moment
    )
    response = first.capture("schedules/2026-10-02/summaries.json", api_key="private-test-value")
    assert not response.from_cache
    second = BudgetedSportradarStore(
        tmp_path, daily_limit=1, weekly_limit=1, transport=fetch, now=lambda: moment
    )
    assert second.capture(
        "schedules/2026-10-02/summaries.json",
        api_key="",
        offline=True,
    ).body == response.body
    assert second.capture(
        "schedules/2026-10-02/summaries.json",
        api_key="private-test-value",
        max_age=timedelta(hours=1),
    ).from_cache
    with pytest.raises(RequestBudgetExceeded):
        second.capture("competitions.json", api_key="private-test-value")
    assert len(calls) == 1
    assert second.usage() == {
        "attempts_today": 1,
        "attempts_rolling_seven_days": 1,
        "retained_responses": 1,
    }


def test_failed_attempt_is_charged_and_secret_is_not_retained(tmp_path) -> None:
    def fail(_url, _headers):
        raise RuntimeError("provider unavailable")

    store = BudgetedSportradarStore(
        tmp_path, daily_limit=1, weekly_limit=1, transport=fail
    )
    with pytest.raises(RuntimeError, match="provider unavailable"):
        store.capture("competitions.json", api_key="private-test-value")
    with pytest.raises(RequestBudgetExceeded):
        store.capture("seasons.json", api_key="private-test-value")
    assert store.usage()["attempts_today"] == 1
    assert b"private-test-value" not in (tmp_path / "requests.sqlite3").read_bytes()


def test_inflight_same_endpoint_is_not_sent_twice(tmp_path) -> None:
    attempts = 0

    def fetch(_url, _headers):
        nonlocal attempts
        attempts += 1
        with pytest.raises(RuntimeError, match="unresolved request"):
            store.capture("competitions.json", api_key="private-test-value")
        return 200, b"{}"

    store = BudgetedSportradarStore(
        tmp_path, daily_limit=2, weekly_limit=2, transport=fetch
    )
    store.capture("competitions.json", api_key="private-test-value")
    assert attempts == 1
    assert store.usage()["attempts_today"] == 1


def test_rejects_unsafe_paths_without_charge(tmp_path) -> None:
    store = BudgetedSportradarStore(tmp_path, daily_limit=1, weekly_limit=1)
    with pytest.raises(ValueError, match="canonical path"):
        store.capture("../other.json", api_key="private-test-value")
    assert store.usage()["attempts_today"] == 0
