from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tennis_genome.experiments.pattern_confirm import (
    HYPOTHESES,
    FrozenMarketCoreFit,
    ProspectiveRecord,
    SettledOutcome,
    build_prospective_record,
    evaluate_hypothesis,
    freeze_market_core_fit,
    log_prospective_rows,
    matching_hypotheses,
    prospective_record_as_dict,
    verify_fit_payload,
    verify_prospective_record,
)


def _synthetic_results(*, post_2025: bool = False, duplicate: bool = False) -> dict[str, object]:
    predictions: list[dict[str, object]] = []
    for index in range(240):
        year = 2016 + (index % 10)
        if post_2025 and index == 0:
            year = 2026
        predictions.append(
            {
                "match_id": f"m-{index}",
                "year": year,
                "market_probability_a": 0.15 + 0.70 * ((index % 17) / 16.0),
                "core_probability_a": 0.20 + 0.60 * (((index * 7) % 19) / 18.0),
                "outcome_a": ((index * 11) % 23) < 12,
            }
        )
    if duplicate:
        predictions[-1]["match_id"] = predictions[0]["match_id"]
    return {
        "bundle_sha256": "b" * 64,
        "market_edge_adv_001": {
            "family_report": {
                "claims": [
                    {
                        "tour": "ATP",
                        "signal_name": "profile_gap",
                        "primary": {"predictions": predictions},
                    }
                ]
            }
        },
    }


@pytest.fixture(scope="module")
def frozen_fit() -> FrozenMarketCoreFit:
    return freeze_market_core_fit(_synthetic_results())


def _raw_row(
    *,
    match_id: str = "future-1",
    profile_gap: float = -0.60,
    scheduled_start: str = "2026-09-12T12:00:00-04:00",
    observed_at: str = "2026-09-12T11:30:00-04:00",
) -> dict[str, object]:
    return {
        "match_id": match_id,
        "tour": "ATP",
        "scheduled_start": scheduled_start,
        "observed_at": observed_at,
        "market_source": "BOOKMAKER_CLOSE_V1",
        "market_probability_a": 0.58,
        "core_probability_a": 0.55,
        "profile_gap": profile_gap,
    }


def _prospective_record(
    index: int,
    *,
    hypothesis_id: str,
    probability: float = 0.60,
) -> ProspectiveRecord:
    start = datetime(2026, 9, 12, 12, tzinfo=UTC) + timedelta(minutes=index)
    return ProspectiveRecord(
        experiment_id="PATTERN-CONFIRM-001",
        version="pattern-confirm-v1",
        match_id=f"p-{index}",
        tour="ATP",
        scheduled_start=start.isoformat(),
        observed_at=(start - timedelta(minutes=30)).isoformat(),
        market_source="BOOKMAKER_CLOSE_V1",
        market_probability_a=0.60,
        core_probability_a=0.55,
        profile_gap=-0.60,
        market_core_probability_a=probability,
        market_core_fit_sha256="f" * 64,
        matched_hypotheses=(hypothesis_id,),
        source_row_sha256=f"{index:064x}"[-64:],
        record_sha256=f"{index + 1:064x}"[-64:],
    )


def test_frozen_family_and_look_schedule() -> None:
    assert [item.hypothesis_id for item in HYPOTHESES] == [
        "PC-ATP-PG-LOW",
        "PC-ATP-PG-ABS-HIGH",
    ]
    assert HYPOTHESES[0].look_ns == (524, 1047, 1570, 2094)
    assert HYPOTHESES[1].look_ns == (936, 1872, 2808, 3744)
    assert HYPOTHESES[0].z_boundaries == HYPOTHESES[1].z_boundaries
    assert HYPOTHESES[0].z_boundaries == (
        4.0486417304805205,
        2.862822022035254,
        2.337484394530551,
        2.0243208652402602,
    )


def test_freeze_fit_is_deterministic_and_historical_only() -> None:
    first = freeze_market_core_fit(_synthetic_results())
    second = freeze_market_core_fit(_synthetic_results())
    assert first == second
    assert first.training_end_year == 2025
    assert first.training_n == 240
    assert len(first.artifact_sha256) == 64

    with pytest.raises(ValueError, match="future outcomes are forbidden"):
        freeze_market_core_fit(_synthetic_results(post_2025=True))
    with pytest.raises(ValueError, match="unique match_id"):
        freeze_market_core_fit(_synthetic_results(duplicate=True))


def test_frozen_fit_self_hash_rejects_tampering(frozen_fit: FrozenMarketCoreFit) -> None:
    from dataclasses import asdict

    payload = asdict(frozen_fit)
    assert verify_fit_payload(payload) == frozen_fit
    payload["intercept"] = float(payload["intercept"]) + 0.01
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_fit_payload(payload)


def test_hypothesis_membership_boundaries_and_overlap() -> None:
    low = HYPOTHESES[0]
    high_abs = HYPOTHESES[1]

    assert low.hypothesis_id not in matching_hypotheses(low.threshold)
    assert low.hypothesis_id in matching_hypotheses(low.threshold - 1e-12)
    assert high_abs.hypothesis_id in matching_hypotheses(high_abs.threshold)
    assert high_abs.hypothesis_id in matching_hypotheses(-high_abs.threshold)
    assert set(matching_hypotheses(-0.60)) == {
        low.hypothesis_id,
        high_abs.hypothesis_id,
    }


def test_logger_enforces_outcome_firewall_and_cutoff(
    frozen_fit: FrozenMarketCoreFit,
) -> None:
    clean = build_prospective_record(_raw_row(), fit=frozen_fit)
    assert clean.matched_hypotheses == (
        "PC-ATP-PG-LOW",
        "PC-ATP-PG-ABS-HIGH",
    )
    assert clean.market_core_fit_sha256 == frozen_fit.artifact_sha256

    with pytest.raises(ValueError, match="forbidden result field"):
        build_prospective_record({**_raw_row(), "winner": "A"}, fit=frozen_fit)
    with pytest.raises(ValueError, match="precedes prospective confirmation cutoff"):
        build_prospective_record(
            _raw_row(scheduled_start="2026-09-11T23:59:59-04:00"),
            fit=frozen_fit,
        )
    with pytest.raises(ValueError, match="observation must occur before"):
        build_prospective_record(
            _raw_row(observed_at="2026-09-12T12:00:00-04:00"),
            fit=frozen_fit,
        )


def test_logger_rejects_duplicate_match_ids(frozen_fit: FrozenMarketCoreFit) -> None:
    with pytest.raises(ValueError, match="duplicate match_id"):
        log_prospective_rows(
            [_raw_row(match_id="dup"), _raw_row(match_id="dup")],
            fit=frozen_fit,
        )


def test_prospective_record_digest_rejects_tampering(
    frozen_fit: FrozenMarketCoreFit,
) -> None:
    record = build_prospective_record(_raw_row(), fit=frozen_fit)
    payload = prospective_record_as_dict(record)
    assert verify_prospective_record(payload) == record
    payload["profile_gap"] = -0.7
    with pytest.raises(ValueError, match="digest mismatch"):
        verify_prospective_record(payload)


def test_strong_negative_residual_confirms_at_first_look() -> None:
    hypothesis = HYPOTHESES[0]
    n = hypothesis.look_ns[0]
    records = [
        _prospective_record(
            index,
            hypothesis_id=hypothesis.hypothesis_id,
            probability=0.60,
        )
        for index in range(n)
    ]
    true_count = 235
    outcomes = {
        row.match_id: SettledOutcome(
            match_id=row.match_id,
            outcome_a=index < true_count,
            retirement=False,
            walkover=False,
        )
        for index, row in enumerate(records)
    }
    report = evaluate_hypothesis(records, outcomes, hypothesis)
    assert report.status == "CONFIRMED"
    assert report.confirmed_look == 1
    assert len(report.completed_looks) == 1
    look = report.completed_looks[0]
    assert look.z >= look.boundary
    assert look.mean_residual < 0.0
    assert look.brier_improvement > 0.0
    assert look.log_loss_improvement > 0.0


def test_null_final_sample_fails_to_confirm() -> None:
    hypothesis = HYPOTHESES[0]
    n = hypothesis.max_n
    records = [
        _prospective_record(
            index,
            hypothesis_id=hypothesis.hypothesis_id,
            probability=0.50,
        )
        for index in range(n)
    ]
    true_count = n // 2
    outcomes = {
        row.match_id: SettledOutcome(
            match_id=row.match_id,
            outcome_a=index < true_count,
            retirement=False,
            walkover=False,
        )
        for index, row in enumerate(records)
    }
    report = evaluate_hypothesis(records, outcomes, hypothesis)
    assert report.status == "FAILED_TO_CONFIRM"
    assert report.confirmed_look is None
    assert len(report.completed_looks) == 4
    assert all(not look.confirmed_at_look for look in report.completed_looks)


def test_retirements_and_walkovers_are_auditable_exclusions() -> None:
    hypothesis = HYPOTHESES[0]
    records = [
        _prospective_record(
            index,
            hypothesis_id=hypothesis.hypothesis_id,
            probability=0.50,
        )
        for index in range(3)
    ]
    outcomes = {
        records[0].match_id: SettledOutcome(
            match_id=records[0].match_id,
            outcome_a=True,
            retirement=False,
            walkover=False,
        ),
        records[1].match_id: SettledOutcome(
            match_id=records[1].match_id,
            outcome_a=None,
            retirement=True,
            walkover=False,
        ),
        records[2].match_id: SettledOutcome(
            match_id=records[2].match_id,
            outcome_a=None,
            retirement=False,
            walkover=True,
        ),
    }
    report = evaluate_hypothesis(records, outcomes, hypothesis)
    assert report.available_qualifying_n == 1
    assert report.excluded_retirement_n == 1
    assert report.excluded_walkover_n == 1
    assert report.status == "ACCUMULATING"
    assert report.completed_looks == ()
