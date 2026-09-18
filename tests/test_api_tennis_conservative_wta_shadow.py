from __future__ import annotations

import pytest

from tennis_genome.research_workbench.api_tennis_conservative_wta_shadow import (
    CHALLENGER_ID,
    build_conservative_wta_shadow_output,
    is_conservative_wta_eligible,
    shrink_probability_to_neutral,
)
from tennis_genome.research_workbench.api_tennis_dynamic_shadow import (
    ApiTennisDynamicShadowRecord,
)
from tennis_genome.research_workbench.challenger import ShadowModelOutput


def _record(
    *,
    tour: str = "WTA",
    probability: float = 0.80,
    serve_a: int = 100,
    return_a: int = 100,
    serve_b: int = 100,
    return_b: int = 100,
) -> ApiTennisDynamicShadowRecord:
    return ApiTennisDynamicShadowRecord(
        match_id="api-tennis:123",
        event_key=123,
        event_date="2026-09-18",
        tour=tour,
        player_a_key=1,
        player_b_key=2,
        player_a_name="A",
        player_b_name="B",
        probability_a_serve_point=0.65,
        probability_b_serve_point=0.58,
        probability_a_match=probability,
        prior_serve_points_a=serve_a,
        prior_serve_points_b=serve_b,
        prior_return_points_a=return_a,
        prior_return_points_b=return_b,
        source_raw_match_sha256="a" * 64,
    )


def test_conservative_wta_gate_is_wta_only_and_uses_combined_history() -> None:
    assert is_conservative_wta_eligible(_record())
    assert not is_conservative_wta_eligible(_record(tour="ATP"))
    assert not is_conservative_wta_eligible(_record(serve_a=99))
    assert is_conservative_wta_eligible(_record(serve_a=120, return_a=80))


def test_conservative_wta_shrinkage_retains_twenty_percent_of_raw_edge() -> None:
    assert shrink_probability_to_neutral(0.80) == pytest.approx(0.56)
    assert shrink_probability_to_neutral(0.20) == pytest.approx(0.44)
    assert shrink_probability_to_neutral(0.50) == pytest.approx(0.50)

    with pytest.raises(ValueError, match="probability"):
        shrink_probability_to_neutral(1.01)


def test_conservative_wta_output_is_shadow_lane_compatible_and_abstains() -> None:
    output = build_conservative_wta_shadow_output(_record(probability=0.80))
    assert isinstance(output, ShadowModelOutput)
    assert output.challenger_id == CHALLENGER_ID
    assert output.p_player_a == pytest.approx(0.56)
    assert output.p_player_b == pytest.approx(0.44)
    assert output.diagnostics["history_threshold"] == 200
    assert output.diagnostics["shrinkage_to_neutral"] == pytest.approx(0.80)

    assert build_conservative_wta_shadow_output(_record(tour="ATP")) is None
    assert build_conservative_wta_shadow_output(_record(return_b=99)) is None
