# Dynamic state known-truth benchmark

Status: **synthetic estimator diagnostic; not tennis match-probability evidence**

The first dynamic serve/return candidate should demonstrate the behavior it was built for
before it is allowed to consume real historical research attention.

This benchmark creates a focal player with:

- a sequence of high-service matches;
- a registered layoff;
- a planted change in true service-point ability after the layoff;
- previously unseen neutral opponents so opponent history does not hide the state question.

Both the existing fixed-learning-rate serve/return estimator and the new dynamic estimator
receive the same noisy service-point observations.

The benchmark scores their **pre-match service-point probabilities** against the planted
true probability in the post-layoff phase using:

- mean squared probability error;
- expected Bernoulli log loss under the known true probability.

These are state-estimator diagnostics. They are not the project's primary match-win Brier
and log-loss evaluation and cannot promote a forecasting procedure.

## Why a persistent-skill control is included

A state model can appear responsive simply by shrinking every player after inactivity.

The benchmark therefore also supports a world where pre- and post-layoff ability are
identical. Tests require that the dynamic estimator not create a material instability cost
in that control world.

## Interpretation

Success in the shift world demonstrates only that the mechanism can recover a type of
planted nonstationarity more effectively than the older fixed updater.

It does not establish:

- that real tennis states move this way;
- that the registered dynamic hyperparameters are optimal;
- that match-win probabilities improve;
- that historical trajectory features become unnecessary;
- that the model has market edge.

The real scientific sequence remains:

1. known-truth behavior;
2. registered historical development comparison;
3. protected complete-procedure evaluation;
4. fresh prospective testing if promoted.
