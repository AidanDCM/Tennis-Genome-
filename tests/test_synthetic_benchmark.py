from __future__ import annotations

import pytest

from tennis_genome.research_workbench import (
    interaction_world,
    miscalibration_world,
    null_world,
    run_synthetic_benchmark,
)

_SOURCE_SHA = "27f936bebd52437173721feb65d007d931975097"


def _delta(candidate: float, baseline: float) -> float:
    return candidate - baseline


def test_null_world_does_not_manufacture_material_improvement() -> None:
    report = run_synthetic_benchmark(
        null_world(n=10_000, seed=20260913),
        source_code_sha=_SOURCE_SHA,
    )

    calibration_brier = _delta(report.calibration.brier, report.baseline.brier)
    calibration_logloss = _delta(report.calibration.log_loss, report.baseline.log_loss)
    interaction_brier = _delta(report.interaction.brier, report.baseline.brier)
    interaction_logloss = _delta(report.interaction.log_loss, report.baseline.log_loss)

    assert report.train_n == 6000
    assert report.protected_n == 4000
    assert calibration_brier > -0.0005
    assert calibration_logloss > -0.001
    assert interaction_brier > -0.0005
    assert interaction_logloss > -0.001


def test_miscalibration_world_is_repaired_by_simple_recalibration() -> None:
    report = run_synthetic_benchmark(
        miscalibration_world(n=10_000, seed=20260913),
        source_code_sha=_SOURCE_SHA,
    )

    assert _delta(report.calibration.brier, report.baseline.brier) < -0.002
    assert _delta(report.calibration.log_loss, report.baseline.log_loss) < -0.005

    extra_interaction_brier = _delta(report.interaction.brier, report.calibration.brier)
    extra_interaction_logloss = _delta(
        report.interaction.log_loss,
        report.calibration.log_loss,
    )
    assert abs(extra_interaction_brier) < 0.001
    assert abs(extra_interaction_logloss) < 0.002


def test_interaction_world_requires_interaction_capability() -> None:
    report = run_synthetic_benchmark(
        interaction_world(n=10_000, seed=20260913),
        source_code_sha=_SOURCE_SHA,
    )

    calibration_brier = _delta(report.calibration.brier, report.baseline.brier)
    calibration_logloss = _delta(report.calibration.log_loss, report.baseline.log_loss)
    assert calibration_brier > -0.002
    assert calibration_logloss > -0.003

    assert _delta(report.interaction.brier, report.calibration.brier) < -0.015
    assert _delta(report.interaction.log_loss, report.calibration.log_loss) < -0.03


def test_synthetic_benchmark_is_deterministic_and_hash_bound() -> None:
    world = interaction_world(n=4000, seed=7)
    first = run_synthetic_benchmark(world, source_code_sha=_SOURCE_SHA)
    second = run_synthetic_benchmark(world, source_code_sha=_SOURCE_SHA)

    assert first.semantic_sha256 == second.semantic_sha256
    assert len(first.protected_population_sha256) == 64
    assert first.baseline.evaluation_spec_sha256 == first.calibration.evaluation_spec_sha256
    assert first.baseline.evaluation_spec_sha256 == first.interaction.evaluation_spec_sha256
    assert first.baseline.procedure_spec_sha256 != first.calibration.procedure_spec_sha256
    assert first.calibration.procedure_spec_sha256 != first.interaction.procedure_spec_sha256


def test_synthetic_benchmark_rejects_tiny_or_invalid_partitions() -> None:
    with pytest.raises(ValueError, match="at least 200"):
        run_synthetic_benchmark(
            null_world(n=199, seed=7),
            source_code_sha=_SOURCE_SHA,
        )
    with pytest.raises(ValueError, match="train_fraction"):
        run_synthetic_benchmark(
            null_world(n=400, seed=7),
            source_code_sha=_SOURCE_SHA,
            train_fraction=0.9,
        )
