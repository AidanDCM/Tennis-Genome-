import pytest

from tennis_genome.features.fingerprint import build_core_fingerprint, delta


def test_delta_preserves_missingness():
    assert delta(None, 1.0) is None
    assert delta(1.0, None) is None


def test_core_fingerprint_has_expected_differences():
    fp = build_core_fingerprint(
        match_id="m1",
        feature_version="v1",
        elo_a=1600,
        elo_b=1500,
        surface_elo_a=1550,
        surface_elo_b=1525,
        serve_a=0.66,
        serve_b=0.62,
        return_a=0.40,
        return_b=0.37,
    )
    assert fp.features["delta_elo"] == pytest.approx(100.0)
    assert fp.features["delta_surface_elo"] == pytest.approx(25.0)
    assert fp.features["a_serve_minus_b_return"] == pytest.approx(0.29)
    assert len(fp.digest()) == 64


def test_digest_is_deterministic():
    kwargs = dict(
        match_id="m1",
        feature_version="v1",
        elo_a=1600,
        elo_b=1500,
        surface_elo_a=1550,
        surface_elo_b=1525,
    )
    first = build_core_fingerprint(**kwargs).digest()
    second = build_core_fingerprint(**kwargs).digest()
    assert first == second
