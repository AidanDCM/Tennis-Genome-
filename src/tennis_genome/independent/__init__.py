"""Frozen market-blind Tennis Genome independent prediction contracts."""

from tennis_genome.independent.prediction import IndependentPrediction
from tennis_genome.independent.spec import (
    TGE_INDEPENDENT_V1,
    architecture_hash,
    tour_spec,
)

__all__ = [
    "IndependentPrediction",
    "TGE_INDEPENDENT_V1",
    "architecture_hash",
    "tour_spec",
]
