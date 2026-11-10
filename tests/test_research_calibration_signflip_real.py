"""End-to-end regression tests against immutable non-production WTA paper evidence.

These tests do not estimate prospective performance or alter the champion.
Run: pytest -q tests/test_research_calibration_signflip_real.py
"""

import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def study():
    return importlib.import_module("scripts.research_calibration_signflip_real").evaluate(ROOT)


def test_reproduces_immutable_paper_population(study):
    assert study["research_only"] is True
    assert study["production_eligible"] is False
    assert study["source"] == "web-shadow/scorecard.json"
    assert study["evaluation_n"] == 55
    assert len(study["evaluation_ids"]) == 55
    assert len(set(study["evaluation_ids"])) == 55
    assert study["date_clusters"] == 15
    assert study["settlement_statuses"]["COMPLETED"] == 85
    assert sum(study["settlement_statuses"].values()) == 88


@pytest.mark.parametrize("candidate", ["adaptive", "fixed_half"])
@pytest.mark.parametrize("metric", ["brier", "log_loss"])
def test_exact_enumeration_is_bounded_and_reproducible(study, candidate, metric):
    result = study["results"][candidate][metric]
    assert result["n"] == 55
    assert result["cluster_count"] == 15
    assert result["configurations"] == 32768
    assert 0 <= result["exact_two_sided_sign_flip_fraction"] <= 1
    assert result["min_cluster_size"] >= 1
    assert result["max_cluster_size"] <= 55


def test_no_candidate_has_confirmatory_evidence(study):
    # Regression assertion for this *historical* paper dataset only.
    # Fractions are not valid confirmatory p-values after model selection.
    for candidate in ("adaptive", "fixed_half"):
        for metric in ("brier", "log_loss"):
            assert study["results"][candidate][metric]["exact_two_sided_sign_flip_fraction"] > 0.05


def test_fixed_half_brier_improvement_reproduced(study):
    assert study["results"]["fixed_half"]["brier"]["observed_mean_improvement"] == pytest.approx(
        0.01089, abs=0.00002
    )
