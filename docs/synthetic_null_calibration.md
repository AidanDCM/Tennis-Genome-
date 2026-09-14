# Synthetic null calibration gate

Status: **bounded research-machine health check; not evidence about tennis prediction**

A single null-world example can show that the Workbench is capable of returning no
improvement. It cannot estimate how often the full benchmark would falsely promote a
challenger under repeated null data.

`NullCalibrationSpec` freezes:

- the full seed family;
- rows per world;
- source-code identity;
- the minimum Brier improvement called materially positive;
- the minimum log-loss improvement called materially positive;
- the maximum tolerable false-promotion rate;
- the confidence level used for the rate bound.

Each registered seed generates a world where the baseline probability is the true
conditional probability. The real synthetic benchmark then fits the calibration and
interaction challengers on development data and evaluates them on protected rows.

A challenger is a false promotion only if it clears **both** frozen proper-score material
thresholds in the same null world.

## Health rule

The campaign reports:

- observed number of false promotions;
- observed false-promotion rate;
- a one-sided Wilson upper confidence bound;
- `HEALTHY` or `FAILED`.

The gate compares the **upper confidence bound**, not merely the observed rate, against
the registered ceiling. A five-seed campaign with zero false promotions therefore cannot
claim that the true false-promotion rate is below an aggressive small threshold.

## What this does not establish

This first campaign calibrates only the current bounded baseline/calibration/interaction
benchmark. It does not yet simulate:

- hundreds of correlated candidate procedures;
- threshold shopping;
- outcome-adaptive candidate invention;
- leakage;
- schema drift;
- missingness artifacts;
- player/tournament dependence;
- rare-signal search;
- trajectory caused by a stale state estimator.

Those remain separate synthetic-world expansions.

If the null gate fails, new pattern/procedure promotion should stop until the research
machinery is understood. Passing this gate is necessary for broader search, not sufficient.
