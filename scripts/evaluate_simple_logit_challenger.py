"""Exploratory, same-fixture historical comparison; never a sealed validation."""

import argparse
import hashlib
import json
from math import log
from pathlib import Path

from tennis_genome.data.sackmann import load_sackmann_csvs
from tennis_genome.features.foundational import walk_forward_foundational_features
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.models.feature_probability import FeatureProbabilityModel
from tennis_genome.research_workbench.simple_logit_challenger import (
    ChallengerExample,
    SimpleLogitChallenger,
)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--data-dir", type=Path, required=True)
parser.add_argument("--tour", choices=("ATP", "WTA"), required=True)
args = parser.parse_args()
tour = args.tour
paths = [args.data_dir / f"{tour.lower()}_matches_{y}.csv" for y in range(2010, 2026)]
source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
raw = load_sackmann_csvs(paths, tour=tour)
matches = [
    m for m in raw if m.outcome.score and not m.outcome.retirement and not m.outcome.walkover
]
states = {m.match_id: m.pre_match for m in matches}
outcomes = {m.match_id: m.outcome.a_won for m in matches}
snaps = walk_forward_foundational_features(matches)
train = [s for s in snaps if s.event_date.year <= 2020]
test = [s for s in snaps if 2023 <= s.event_date.year <= 2025]
def examples(rows):
    return [ChallengerExample(s, states[s.match_id], outcomes[s.match_id]) for s in rows]


def rank_ok(snapshot):
    state = states[snapshot.match_id]
    return all(
        value is not None and value > 0
        for value in (
            state.rank_a,
            state.rank_b,
            state.rank_points_a,
            state.rank_points_b,
        )
    )


core = FeatureProbabilityModel(strict_a_features(tour)).fit(
    train, [outcomes[s.match_id] for s in train]
)
base = SimpleLogitChallenger().fit(examples(train))
rank = SimpleLogitChallenger(include_rank=True).fit(examples([s for s in train if rank_ok(s)]))
core_p = core.predict_probabilities(test)
base_p = [base.predict_probability_a(e) for e in examples(test)]
rank_p = {
    s.match_id: rank.predict_probability_a(ChallengerExample(s, states[s.match_id]))
    for s in test
    if rank_ok(s)
}


def score(rows):
    n = len(rows)
    return {
        "n": n,
        "accuracy": sum((p > 0.5) == y for y, p in rows) / n,
        "brier": sum((p - y) ** 2 for y, p in rows) / n,
        "log_loss": sum(-log(max(p, 1e-15)) if y else -log(max(1 - p, 1e-15)) for y, p in rows) / n,
    }


all_res = {}
for label, subset in [("all", False), ("rank_complete", True)]:
    ids = [i for i, s in enumerate(test) if not subset or s.match_id in rank_p]
    result = {}
    for name, probs in [("refit_strict_core", core_p), ("simple_base", base_p)]:
        result[name] = score([(outcomes[test[i].match_id], probs[i]) for i in ids])
    if subset:
        result["simple_rank"] = score(
            [(outcomes[test[i].match_id], rank_p[test[i].match_id]) for i in ids]
        )
    all_res[label] = result
print(
    json.dumps(
        {
            "tour": tour,
            "historical_research_only": True,
            "ranking_t0_unverified": True,
            "training_end": 2020,
            "evaluation_years": "2023-2025",
            "source_sha256": source_hashes,
            "results": all_res,
        },
        indent=2,
    )
)
