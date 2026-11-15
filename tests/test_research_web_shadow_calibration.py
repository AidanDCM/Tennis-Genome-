"""Research-only checks for paired uncertainty and chronology controls."""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/research_web_shadow_calibration.py"
_spec = importlib.util.spec_from_file_location("research_web_shadow_calibration", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


def test_paired_interval_zero_difference() -> None:
    result = _module.paired_interval([0.0, 0.0, 0.0])
    assert result["n"] == 3
    assert result["ci95_normal"] == [0.0, 0.0]


def test_paired_interval_rejects_insufficient_or_nonfinite() -> None:
    with pytest.raises(ValueError):
        _module.paired_interval([0.1])
    with pytest.raises(ValueError):
        _module.paired_interval([0.1, float("nan")])


def test_paired_control_preserves_direction_and_zero_identity() -> None:
    rows = [{"p": 0.8, "correct": False}, {"p": 0.8, "correct": False}]
    same = _module.paired_improvements(rows, [1.0, 1.0])
    assert same["brier"]["mean"] == 0
    assert same["log_loss"]["mean"] == 0
    shrink = _module.paired_improvements(rows, [0.5, 0.5])
    assert shrink["brier"]["mean"] > 0
    assert shrink["log_loss"]["mean"] > 0


def test_experiment_never_uses_unobserved_results() -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        {"id": str(i), "start": t + timedelta(days=i),
         "observed": t + timedelta(days=i + 100),
         "p": 0.6, "correct": bool(i % 2)}
        for i in range(6)
    ]
    with pytest.raises(ValueError, match="no causally eligible"):
        _module.experiment(rows, min_train=2)


def test_cluster_interval_zero_differences() -> None:
    result = _module.cluster_paired_interval(
        [0.0, 0.0, 0.0, 0.0], ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-03"]
    )
    assert result["cluster_count"] == 3
    assert result["ci95_cluster_normal"] == [0.0, 0.0]


def test_cluster_interval_rejects_insufficient_clusters() -> None:
    with pytest.raises(ValueError, match="three independent"):
        _module.cluster_paired_interval([0.1, -0.1], ["a", "b"])
    with pytest.raises(ValueError, match="align"):
        _module.cluster_paired_interval([0.1, 0.2, 0.3], ["a"])


def test_cluster_interval_unequal_clusters_mean_and_finite() -> None:
    result = _module.cluster_paired_interval(
        [1.0, 1.0, -1.0, 0.0], ["a", "a", "b", "c"]
    )
    assert result["n"] == 4
    assert result["cluster_count"] == 3
    assert result["mean"] == pytest.approx(0.25)
    assert result["ci95_cluster_normal"][0] < 0.25
    assert result["ci95_cluster_normal"][1] > 0.25


def test_cluster_paired_improvements_identity() -> None:
    t = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        {"start": t + timedelta(days=i), "p": 0.65, "correct": bool(i % 2)}
        for i in range(3)
    ]
    result = _module.cluster_paired_improvements(rows, [1.0] * 3)
    assert result["brier"]["ci95_cluster_normal"] == [0.0, 0.0]
    assert result["log_loss"]["ci95_cluster_normal"] == [0.0, 0.0]
