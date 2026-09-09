import pytest

from tennis_genome.ratings.elo import EloConfig, expected_score, update_pair


def test_equal_ratings_are_even():
    assert expected_score(1500, 1500) == pytest.approx(0.5)


def test_probability_is_symmetric():
    p_ab = expected_score(1620, 1480)
    p_ba = expected_score(1480, 1620)
    assert p_ab + p_ba == pytest.approx(1.0)


def test_winner_gains_and_loser_loses():
    config = EloConfig(initial_rating=1500, k_factor=32, scale=400)
    new_a, new_b = update_pair(1500, 1500, a_won=True, config=config)
    assert new_a > 1500
    assert new_b < 1500
    assert new_a + new_b == pytest.approx(3000)


def test_invalid_scale_fails():
    with pytest.raises(ValueError):
        expected_score(1500, 1500, scale=0)


def test_elo_config_rejects_non_positive_k_factor():
    with pytest.raises(ValueError, match="k_factor"):
        EloConfig(k_factor=0)


def test_elo_config_rejects_non_positive_scale():
    with pytest.raises(ValueError, match="scale"):
        EloConfig(scale=-1)
