# Dependence-aware paired inference

Status: **available for new Workbench/challenger research; frozen historical protocols unchanged**

Tennis matches are paired forecasting observations but are not plausibly independent draws.
Players recur, tournaments share conditions, and nearby matches share temporal regimes.

The existing observation-level paired bootstrap remains useful descriptive infrastructure and
is retained unchanged for already-frozen protocols. New challenger promotion should add a
dependence-aware view.

## Registered block inference

`paired_block_bootstrap_improvement` resamples entire caller-supplied blocks with
replacement. Every match in a sampled block travels together.

`paired_block_sign_flip_test` assigns one random sign to an entire block rather than one
sign per match.

The block definition is part of the research specification and must be frozen before the
protected outcome is opened. The inference code deliberately does not try multiple
clusterings and choose the most favorable result.

Reasonable primary candidates include:

- tournament-week;
- calendar-week;
- tournament/event.

No single grouping completely solves the two-player dependence structure. Serious
promotion should therefore combine a registered primary block definition with prespecified
sensitivity checks such as player-volume exclusions or alternate event grouping.

## Interpretation

Positive improvement means lower candidate loss than baseline.

Block-aware intervals may be wider than match-level intervals. That is expected rather
than a defect: repeated observations within a common tournament/time regime do not provide
the same amount of independent information as the same number of isolated matches.

This infrastructure does not retroactively change FULL-STACK-FORWARD-001,
PATTERN-CONFIRM-001, or other frozen experiments.
