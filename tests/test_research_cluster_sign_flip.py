"""Unit tests for research-only exact cluster sign-flip sensitivity."""
import pytest

from scripts.research_cluster_sign_flip import sign_flip_sensitivity


def test_zero_differences():
    result = sign_flip_sensitivity([0, 0, 0], ["a", "b", "c"])
    assert result["exact_two_sided_sign_flip_fraction"] == 1
    assert result["configurations"] == 8


def test_equal_positive_cluster_differences():
    result = sign_flip_sensitivity([1, 1, 1], ["a", "b", "c"])
    assert result["exact_two_sided_sign_flip_fraction"] == 0.25


def test_unequal_cluster_sizes():
    result = sign_flip_sensitivity([1, 1, -1], ["a", "a", "b"])
    assert result["n"] == 3
    assert result["max_cluster_size"] == 2
    assert result["exact_two_sided_sign_flip_fraction"] == 1


@pytest.mark.parametrize(
    ("differences", "clusters"),
    [
        ([1], ["a"]),
        ([float("nan"), 1], ["a", "b"]),
        ([1, 2], ["a"]),
        ([1, 2], ["a", ""]),
    ],
)
def test_invalid_inputs(differences, clusters):
    with pytest.raises(ValueError):
        sign_flip_sensitivity(differences, clusters)
