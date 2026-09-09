from datetime import datetime, timedelta, timezone

import pytest

from tennis_genome.validation.temporal import (
    TemporalLeakageError,
    assert_available_before_t0,
    assert_history_strictly_before_t0,
    assert_neighbor_is_historical,
)


UTC = timezone.utc


def test_available_before_t0_passes():
    t0 = datetime(2026, 1, 10, 12, tzinfo=UTC)
    assert_available_before_t0(available_at=t0 - timedelta(hours=1), prediction_cutoff_at=t0)


def test_future_source_record_fails():
    t0 = datetime(2026, 1, 10, 12, tzinfo=UTC)
    with pytest.raises(TemporalLeakageError):
        assert_available_before_t0(available_at=t0 + timedelta(seconds=1), prediction_cutoff_at=t0)


def test_target_time_cannot_enter_history():
    t0 = datetime(2026, 1, 10, 12, tzinfo=UTC)
    with pytest.raises(TemporalLeakageError):
        assert_history_strictly_before_t0(
            history_times=[t0 - timedelta(days=1), t0], prediction_cutoff_at=t0
        )


def test_future_neighbor_fails():
    target = datetime(2026, 1, 10, 12, tzinfo=UTC)
    with pytest.raises(TemporalLeakageError):
        assert_neighbor_is_historical(
            neighbor_t0=target + timedelta(days=1), target_t0=target, neighbor_match_id="future"
        )
