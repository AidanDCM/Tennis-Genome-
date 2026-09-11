from __future__ import annotations

from dataclasses import asdict

import pytest

from tennis_genome.experiments.pattern_confirm import (
    FrozenMarketCoreFit,
    build_prospective_record,
    prospective_record_as_dict,
)
from tennis_genome.experiments.pattern_confirm_ledger import append_prospective_rows


@pytest.fixture
def fit() -> FrozenMarketCoreFit:
    unsigned = {
        "experiment_id": "PATTERN-CONFIRM-001",
        "version": "pattern-confirm-v1",
        "source_bundle_sha256": "b" * 64,
        "source_claim": "synthetic",
        "training_rows_sha256": "c" * 64,
        "training_n": 100,
        "training_start_year": 2016,
        "training_end_year": 2025,
        "intercept": -0.04,
        "market_logit_slope": 1.03,
        "core_logit_slope": 0.01,
    }
    from tennis_genome.experiments.pattern_confirm import _self_hash

    return FrozenMarketCoreFit(**unsigned, artifact_sha256=_self_hash(unsigned))


def _raw(match_id: str, hour: int) -> dict[str, object]:
    return {
        "match_id": match_id,
        "tour": "ATP",
        "scheduled_start": f"2026-09-12T{hour:02d}:00:00-04:00",
        "observed_at": f"2026-09-12T{hour - 1:02d}:45:00-04:00",
        "market_source": "BOOKMAKER_CLOSE_V1",
        "market_probability_a": 0.58,
        "core_probability_a": 0.55,
        "profile_gap": -0.60,
    }


def test_append_verifies_and_orders_existing_and_new(fit: FrozenMarketCoreFit) -> None:
    existing = build_prospective_record(_raw("existing", 14), fit=fit)
    combined = append_prospective_rows(
        [prospective_record_as_dict(existing)],
        [_raw("new-earlier", 13), _raw("new-later", 15)],
        fit=fit,
    )
    assert [row.match_id for row in combined] == [
        "new-earlier",
        "existing",
        "new-later",
    ]


def test_append_rejects_cross_batch_duplicate(fit: FrozenMarketCoreFit) -> None:
    existing = build_prospective_record(_raw("duplicate", 14), fit=fit)
    with pytest.raises(ValueError, match="would duplicate match_id"):
        append_prospective_rows(
            [prospective_record_as_dict(existing)],
            [_raw("duplicate", 15)],
            fit=fit,
        )


def test_append_rejects_tampered_existing_row(fit: FrozenMarketCoreFit) -> None:
    existing = prospective_record_as_dict(
        build_prospective_record(_raw("existing", 14), fit=fit)
    )
    existing["profile_gap"] = -0.7
    with pytest.raises(ValueError, match="digest mismatch"):
        append_prospective_rows([existing], [_raw("new", 15)], fit=fit)


def test_append_rejects_mixed_fit_hash(fit: FrozenMarketCoreFit) -> None:
    existing = build_prospective_record(_raw("existing", 14), fit=fit)
    payload = prospective_record_as_dict(existing)
    unsigned_fit = asdict(fit)
    unsigned_fit.pop("artifact_sha256")
    unsigned_fit["intercept"] = -0.05
    from tennis_genome.experiments.pattern_confirm import _self_hash

    other_fit = FrozenMarketCoreFit(
        **unsigned_fit,
        artifact_sha256=_self_hash(unsigned_fit),
    )
    with pytest.raises(ValueError, match="different frozen fit"):
        append_prospective_rows([payload], [_raw("new", 15)], fit=other_fit)
