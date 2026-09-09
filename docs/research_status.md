# Research Status / Evidence Contract

This file prevents design ideas from quietly becoming factual claims.

## Status labels

### ESTABLISHED PROJECT REQUIREMENT
A design requirement we intentionally chose (for example: chronological validation, immutable predictions, separate market layer).

### SUPPORTED METHOD
A standard statistical/engineering method appropriate to the problem, still requiring correct implementation.

### TENNIS HYPOTHESIS
A tennis-specific claim that must be tested on historical/future data before acceptance.

### DEFERRED HYPOTHESIS
Potentially useful but outside the current installment.

### VERIFIED FINDING
Reserved for a result reproduced by our own pipeline under the project's validation rules.

No tennis-specific metric effect is a `VERIFIED FINDING` merely because it appeared in discussion or an external paper.

## Current established project requirements

- probabilities rather than only winner labels;
- Brier/log-loss/calibration as primary evaluation;
- T0 feature-availability semantics;
- chronological/walk-forward evaluation;
- immutable predictions;
- hypothesis registry;
- add-one and remove-one/ablation tests;
- multiple-testing safeguards;
- independent tennis model separated from sportsbook prices;
- explicit PASS/abstention behavior;
- model disagreement/data quality/historical density tested as uncertainty signals;
- betting profitability evaluated separately from predictive accuracy.

## Current tennis hypotheses, not yet verified by this repo

- Elo beats ranking as a probability baseline;
- surface Elo adds incremental value;
- opponent-adjusted serve/return adds value;
- recent underlying form adds value;
- fatigue/rest has conditional value;
- age modifies fatigue effects;
- H2H adds little after strong controls except possible matchup-specific cases;
- Player Profile Gap identifies improvement/decline before Elo catches up;
- historical-neighborhood/Tennis Genome similarity adds residual information;
- dense historical neighborhoods correspond to more reliable predictions;
- model disagreement predicts forecast error;
- selective prediction can isolate materially more predictable match subsets.

## Market hypotheses, not yet verified

- independent-model disagreements with no-vig market probabilities can identify mispricing;
- larger robust edges should produce better CLV/ROI after uncertainty filters;
- positive CLV may be a useful intermediate indicator of pricing information;
- any threshold/policy can be consistently profitable.

Profitability is explicitly **not established**.

## External evidence policy

Academic/public findings can motivate experiments and provide benchmark context, but production promotion requires our own reproducible test.

For every external claim eventually added to the repo, record:
- source citation
- publication/date
- dataset/tour/period
- target variable
- model/evaluation protocol
- whether random or chronological validation was used
- reported uncertainty
- limitations
- relevance to our implementation

## Proof-check sequence

Before coding a research finding into a production feature:
1. verify data source and licensing;
2. reproduce metric definition;
3. confirm T0 legality;
4. run data-quality audit;
5. pre-register experiment;
6. run add-one/ablation tests;
7. conduct adversarial review;
8. replicate in later windows;
9. test untouched holdout;
10. assign metric grade.

## Current state

The repository currently contains the **research architecture and starter implementation**, not a validated profitable model.
