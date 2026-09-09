# Tennis Genome

A research-first tennis probability and betting-decision engine.

## Mission

Build a leakage-resistant, calibrated pre-match tennis probability engine that can:

1. estimate fair win probabilities using only information available before first point;
2. quantify uncertainty and model disagreement;
3. identify when the system should abstain because the match is not understood well enough;
4. compare independent model probabilities with market-implied/no-vig probabilities in a separate market-aware layer;
5. identify positive-expected-value opportunities only when estimated edge survives uncertainty and historical validation;
6. evaluate whether any betting policy is consistently profitable through chronological out-of-sample testing rather than assumption.

The system is **not** designed to prove a predetermined betting theory. Its job is to discover which ideas survive real data.

## Governing principles

- Prediction is probability estimation, not winner picking.
- Win rate alone is insufficient for betting.
- Market prices remain separate from the independent tennis model.
- Every metric must prove incremental out-of-sample value.
- Every pre-match feature must be known at prediction time (`T0`).
- Chronological/walk-forward validation is mandatory.
- The system must be allowed to say `PASS`.
- Research hypotheses, accepted findings, rejected patterns, and model versions are retained.
- The component proposing an improvement must not be the only judge of whether it worked.

## Core architecture

```text
Historical / current tennis data
        |
        v
Ingestion -> cleaning -> provenance / T0 checks
        |
        v
Player snapshots + pre-match state
        |
        v
Feature families / Match Fingerprint ("Tennis Genome")
        |
        +--------------------+
        |                    |
        v                    v
Baseline models       Historical-similarity engine
        |                    |
        +----------+---------+
                   v
          calibrated ensemble
                   |
                   v
       probability + uncertainty
                   |
          +--------+---------+
          |                  |
          v                  v
       PASS logic       market-aware layer
                              |
                              v
                  edge / EV / policy decision
                              |
                              v
                    immutable prediction log
                              |
                              v
                 post-match evaluation / CLV
```

## Initial model ladder

Complexity is earned in this order:

1. Ranking baseline
2. Overall Elo
3. Surface Elo
4. Opponent-adjusted serve/return strength
5. Recent underlying form
6. Player Profile v1
7. Workload/rest/fatigue
8. Matchup interactions
9. Tennis Genome historical-neighborhood similarity
10. Calibrated ensemble + selective prediction
11. Later: richer injury/news/environment/travel/current-event layers

Each step is evaluated with add-one, remove-one/ablation, calibration, and chronological holdout tests.

## Primary evaluation metrics

Prediction quality:
- log loss
- Brier score
- calibration / reliability curves
- accuracy (secondary, never sufficient alone)
- selective-prediction accuracy by coverage/confidence

Market-aware evaluation:
- model probability vs no-vig market probability
- estimated edge
- expected value
- closing-line value (CLV)
- realized ROI
- drawdown
- edge-bucket and confidence-bucket performance
- sample size and uncertainty

## Installment 01 goal

A successful first installment can take an arbitrary historical professional singles match, reconstruct only the pre-match knowledge available at that time, build time-aware player snapshots and a Match Fingerprint, generate baseline probabilities, and walk-forward test them against later matches while measuring calibration, log loss, Brier score, and incremental feature value.

Installment 01 is complete only when we know which initial features improve unseen predictions, which do not, and where uncertainty remains.

Start with:
- `docs/architecture.md`
- `docs/research_principles.md`
- `docs/metric_testing_lab.md`
- `docs/metric_registry.md`
- `docs/tennis_genome.md`
- `research/installment_01/README.md`
