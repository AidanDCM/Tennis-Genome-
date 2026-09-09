# Research Principles

## Prime directive

The project exists to discover repeatable predictive information, not to validate our own ideas.

A feature or model change is useful only if it improves future predictions, calibration, selective-prediction behavior, or later market-aware decisions after appropriate controls.

## T0 rule

For each match define `T0` as the prediction cutoff before first point.

A pre-match feature is legal only if its underlying information was genuinely available before T0.

Forbidden examples:
- closing information obtained after the chosen cutoff
- post-match injury explanations
- statistics from the match being predicted
- later ranking updates
- future player profile information
- retrospective labels derived from future events

Historical reconstruction must use `available_at`, not merely the date the underlying event occurred.

## Chronology first

Random train/test splitting is not sufficient for the core evaluation.

Preferred workflow:

```text
past -> train
next period -> validate/tune
future period -> test
roll window forward
```

Final claims require performance on untouched chronological holdouts.

## Hypothesis registry

Every research question receives an immutable hypothesis entry before final validation:

- hypothesis ID
- created date
- metric/family
- expected direction if any
- plausible mechanism
- alternative explanations/confounders
- datasets/periods used for discovery
- planned evaluation metrics
- planned interactions/subgroups
- multiple-testing family
- acceptance/rejection criteria
- result
- status

Rejected hypotheses remain stored.

## Metric usefulness hierarchy

A raw correlation is not sufficient.

For candidate metric `X`, test:

1. data availability and reliability
2. missingness pattern
3. raw association
4. relationship with existing features
5. confounder map
6. incremental add-one test
7. remove-one ablation from fuller model
8. unique/residual/orthogonal signal where appropriate
9. plausible interactions
10. chronological stability
11. calibration impact
12. uncertainty around the effect
13. subgroup robustness
14. untouched holdout

## Add-one and remove-one tests

Let `M0` be an accepted baseline model.

`M1 = M0 + X`

Evaluate on future data. Useful evidence includes lower log loss/Brier score and improved calibration without fragile subgroup behavior.

Then test the reverse:

`M_full` vs `M_full_without_X`.

If removing `X` causes no meaningful degradation, its apparent contribution may be redundant.

## Correlated features

Do not pretend highly collinear variables have clean individual causal attribution.

Examples may include:
- ranking
- Elo
- surface Elo
- win percentage
- point win percentage
- hold percentage
- serve ratings

When needed, test:
- family-level ablations
- residualization / orthogonalized components
- cross-fitted residual approaches
- permutation importance evaluated chronologically
- regularized models

The project cares first about **incremental predictive value**, not claiming causality.

## Confounder map

Before interpreting a metric, explicitly list variables that could generate the observed relationship.

Example: short rest may be confounded by previous-match duration, tournament scheduling, player quality, age, surface, weather, injuries, or round.

The adversarial review should ask whether the effect survives plausible controls.

## Interactions

A weak main effect does not imply a useless variable.

Potential forms:
- fatigue × age
- fatigue × heat
- fatigue × previous workload
- surface × serve style
- handedness × opponent return profile
- court pace × serve/return profile

Interaction search must be constrained, registered, and penalized for multiple testing.

## Multiple hypotheses

If hundreds or thousands of patterns are tested, some will appear significant by chance.

Required safeguards:
- explicit hypothesis families
- false-discovery-rate control where appropriate
- conservative family-wise checks for especially consequential claims
- minimum sample sizes
- shrinkage
- holdout replication
- effect-size thresholds
- stability requirements

A tiny p-value is not enough.

## Negative controls and placebos

The pipeline should intentionally test features that should not predict future tennis outcomes.

Examples:
- shuffled metric values within appropriate strata
- future-neutral random identifiers
- synthetic noise columns
- temporally impossible versions used only inside leakage tests

If the model extracts durable signal from nonsense, the evaluation pipeline is suspect.

## Effect representation

Avoid storing universal constants when effects are conditional.

Prefer:

`fatigue_effect = f(rest_hours, workload, age, heat, surface, player_profile)`

with:
- estimate
- uncertainty
- applicable population
- sample size
- validation periods
- stability score

## Metric grades

- **A — Core:** repeatable incremental signal, strong reliability, survives chronology and ablation.
- **B — Conditional:** useful in specific contexts/interactions with adequate validation.
- **C — Experimental:** promising but insufficiently stable, sparse, or uncertain.
- **D — Rejected/Noise:** fails incremental or out-of-sample tests.

Grades may change only through a documented new validation cycle.

## Model evaluation

Primary:
- log loss
- Brier score
- calibration / reliability

Secondary:
- accuracy
- discrimination/ranking metrics when useful
- subgroup performance

Selective prediction:
- performance vs coverage curve
- high-confidence bucket calibration
- abstention error analysis

Later market-aware:
- no-vig edge
- EV
- CLV
- realized ROI
- drawdown
- policy stability

## Profitability claims

No historical backtest alone proves future profitability.

A policy is not promoted as robust unless it survives:
- chronological out-of-sample testing
- separate seasons/periods
- multiple tournament/player subsets
- vig/price assumptions
- reasonable sensitivity tests
- sufficient sample size
- uncertainty analysis

The system must preserve the distinction between:
- good prediction
- good betting decision
- fortunate outcome
- sustainable edge
