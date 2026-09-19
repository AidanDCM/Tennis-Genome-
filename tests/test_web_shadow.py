from __future__ import annotations

from dataclasses import replace

import pytest

from tennis_genome.prospective.web_shadow import (
    WebShadowFixture,
    WebShadowPrediction,
    settle_web_shadow,
)


def fixture() -> WebShadowFixture:
    return WebShadowFixture(
        match_id="wta:guadalajara:2026:LS001",
        tour="WTA",
        tournament="Guadalajara Open",
        round="Final",
        surface="Hard",
        scheduled_start="2026-09-19T17:00:00-06:00",
        player_a="Iva Jovic",
        player_b="Peyton Stearns",
        source_url="https://www.wtatennis.com/example",
        source_observed_at="2026-09-19T10:00:00-06:00",
    )


def prediction() -> dict[str, object]:
    return WebShadowPrediction(
        fixture=fixture(),
        committed_at="2026-09-19T10:05:00-06:00",
        p_player_a=0.61,
        p_player_b=0.39,
        model_source_sha="a" * 40,
        input_manifest_sha256="b" * 64,
    ).record()


def test_prediction_is_prestart_hashed_and_never_production_eligible() -> None:
    record = prediction()
    assert record["selected_player"] == "Iva Jovic"
    assert record["production_eligible"] is False
    assert len(record["record_sha256"]) == 64


def test_prediction_rejects_post_start_commit() -> None:
    with pytest.raises(ValueError, match="before scheduled start"):
        WebShadowPrediction(
            fixture=fixture(),
            committed_at="2026-09-19T17:00:00-06:00",
            p_player_a=0.5,
            p_player_b=0.5,
            model_source_sha="a" * 40,
            input_manifest_sha256="b" * 64,
        ).record()


def test_fixture_rejects_source_observed_after_start() -> None:
    bad = replace(fixture(), source_observed_at="2026-09-19T18:00:00-06:00")
    with pytest.raises(ValueError, match="observed before scheduled start"):
        bad.validate()


def test_settlement_verifies_frozen_prediction_and_scores_selection() -> None:
    result = settle_web_shadow(
        prediction(),
        winner="Iva Jovic",
        status="completed",
        result_source_url="https://www.wtatennis.com/example",
        result_observed_at="2026-09-19T20:00:00-06:00",
    )
    assert result["prediction_correct"] is True
    assert result["production_eligible"] is False
    assert len(result["record_sha256"]) == 64


def test_settlement_rejects_tampered_prediction() -> None:
    record = prediction()
    record["p_player_a"] = 0.99
    with pytest.raises(ValueError, match="digest mismatch"):
        settle_web_shadow(
            record,
            winner="Iva Jovic",
            status="COMPLETED",
            result_source_url="https://www.wtatennis.com/example",
            result_observed_at="2026-09-19T20:00:00-06:00",
        )
