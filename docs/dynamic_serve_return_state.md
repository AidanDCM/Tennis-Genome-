# Dynamic serve/return state — research candidate

Status: **implemented challenger state representation; not promoted and not evaluated as
a superior forecasting procedure**

## Purpose

The current serve/return state uses a fixed learning-rate residual update. That is a useful
baseline but it does not represent uncertainty or allow uncertainty to grow when a player
has not been observed.

This candidate tests a simpler explanation for several residual phenomena before broader
pattern discovery: the current state estimator may simply adapt too slowly or treat sparse
and deep histories too similarly.

## State

Each player carries separate serve and return effects on the service-point logit scale:

- serve posterior mean and variance;
- return posterior mean and variance;
- prior serve-point count;
- prior return-point count;
- last update date.

For a server `i` facing returner `j`:

`logit(P(server wins point)) = base_logit + serve_i - return_j`

The snapshot exposes both the mean point probability and uncertainty of the corresponding
serve logit.

## Time dynamics

Before a new source date:

- latent means shrink toward the population mean according to a registered half-life;
- variances grow according to registered process variance;
- variance is capped rather than allowed to explode indefinitely.

This is a deliberately lightweight state-space approximation, not a claim of a fully
specified Bayesian posterior.

## Observation update

Completed-match service-point aggregates generate:

- a binomial score gradient;
- local Fisher information.

A configurable information discount prevents the aggregate point count from being treated
as perfectly independent information.

Serve and return parameters update against the opponent-adjusted expected point
probability.

## Same-day integrity

The current historical source does not preserve trusted intraday match chronology.

Therefore each UTC source date is atomic:

1. advance every participating player from prior-date state;
2. emit every target snapshot for the date;
3. calculate all observation gradients against that same frozen state;
4. aggregate by player and role;
5. commit one posterior update after the full date closes.

The update is therefore independent of arbitrary same-day CSV row or match-number order.

## Retirements

The first candidate keeps the existing conservative default of excluding retirement
matches from state learning. Partial-match retention is a separate registered experiment
because informative censoring and physical deterioration make retirement observations
scientifically different from ordinary complete matches.

## What must happen before promotion

This module is only a state representation. It does not establish forecast improvement.

A complete forecasting procedure using it must still be:

- registered in a `ProcedureSearchFamily`;
- bound to audited feature availability;
- fingerprinted for exact data/code/runtime;
- compared against the existing state estimator on identical chronological rows;
- evaluated with registered proper scores and dependence-aware inference;
- tested on protected evidence under the Research Constitution.

Trajectory should then be tested **after** this more responsive state estimator. If an
explicit trajectory term loses incremental value, the earlier trajectory signal was
likely estimator lag rather than a separate predictive mechanism.
