from tennis_genome.models.core_v1_spec import (
    FAMILY_GRADES,
    HISTORICAL_BENCHMARK_FEATURES,
    a_plus_b_features,
    strict_a_features,
)


def test_atp_strict_core_contains_only_a_grade_families() -> None:
    features = strict_a_features("ATP")

    assert "elo_logit" in features
    assert "serve_return_edge" in features
    assert "form_result_30_diff" in features
    assert "minutes_14_diff" in features
    assert "age_diff" in features
    assert "surface_clay_elo" in features
    assert "age_x_minutes_14_diff" not in features
    assert "h2h_edge" not in features
    assert "left_hand_diff" not in features
    assert FAMILY_GRADES["ATP"]["age_fatigue_interaction"] == "B"


def test_wta_strict_core_excludes_non_a_grade_features() -> None:
    features = strict_a_features("WTA")
    diagnostic = a_plus_b_features("WTA")

    assert "elo_logit" in features
    assert "form_result_30_diff" in features
    assert "minutes_14_diff" in features
    assert "surface_clay_elo" in features
    assert "serve_return_edge" not in features
    assert "age_diff" not in features
    assert "h2h_edge" not in features
    assert "left_hand_diff" not in features
    assert "serve_return_edge" in diagnostic
    assert "age_x_minutes_14_diff" in diagnostic
    assert FAMILY_GRADES["WTA"]["age_career_physical"] == "C"


def test_holdout_benchmark_remains_family_lab_control() -> None:
    assert HISTORICAL_BENCHMARK_FEATURES == ("elo_logit", "serve_return_edge")
