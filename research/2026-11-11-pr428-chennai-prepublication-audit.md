# PR #428 Chennai result: pre-publication evidence audit (2026-11-11)

## Scope and immutable sources
Main scorecard: `web-shadow/scorecard.json` (blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`), 88 settlements, 85 scored, 16 pending, production_eligible=false.
Main active pointer: `web-shadow/active-results.json` (blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`).
PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f`; proposed result blob `8693ebd69e6acb4158721251809fedb046abba18`.
Prediction: `web-shadow/slates/2026-11-07-run-42418376306/predictions/chennai-2026-f-ls001-janice-tjen-magda-linette.json` (blob `799ce2152166bf238adca39271de8c102519348c`).
Match ID `web:wta:1148:2026:LS001`; players Magda Linette / Janice Tjen; predicted and reported winner Magda Linette.

## Preregistered falsifiable checks
H1: The proposed result points to the same immutable prediction hash, match ID, and one of its two players; fail on any mismatch.
H2: The prediction commitment predates the scheduled start, which predates result observation; fail on any nonpositive interval.
H3: Probability values are finite, in [0,1], and sum to 1; fail otherwise.
H4: This evidence suffices to independently verify the WTA provider's winner and raw-source hash. **Not established** by comparing repository JSON alone.

## Executed numerical reproduction
```python
from datetime import datetime
from math import log
commit=datetime.fromisoformat("2026-11-07T21:59:27.475055+00:00")
start=datetime.fromisoformat("2026-11-08T18:30:00+05:30")
observed=datetime.fromisoformat("2026-11-09T08:39:51+00:00")
p=.510573822024917
assert commit < start < observed
assert abs(p+.48942617797508303-1)<1e-12
print((start-commit).total_seconds()/3600, (observed-start).total_seconds()/3600)
print((1-p)**2,-log(p))
```
Observed: lead 15.009034706944444 hours; result observation delay 19.664166666666667 hours; probability sum 1.0; conditional single-match Brier 0.23953798368729765 and log loss 0.6722200445354388. These last two are diagnostic *only if* the result is independently verified and accepted, not a canonical settlement or sample increment.

Structural cross-file checks: prediction record SHA `42775ef387a985d5c68af2d4d349c7ce45e21d9c5304dccfd1886a381a44b929` equals result expected SHA; match ID matches; reported winner belongs to prediction participants. No contradiction found. Source authenticity, exact provider match-row identity, and SHA-256 of retained raw bytes were not independently recalculated. PR remains open; **do not merge automatically**.

## Research / contrary evidence
Ferro (2017), https://doi.org/10.1002/qj.3115 (peer-reviewed; observation-error correction, requires observation error model), warns that even proper scores can rank models incorrectly under noisy outcome labels. This is methodological, not a comparable tennis benchmark; no external code reused. Mitchell and Ferro (2017), https://doi.org/10.1002/qj.3029, develops interval forecast scoring; not applicable to point-probability records without an interval forecasting protocol. Neither licenses or validates an arbitrary settlement gate bypass.

## Negative findings and queue
1. **Highest:** independently inspect retained official WTA Chennai raw match row, its SHA-256, tournament edition, player IDs, winner and completion status against the PR provenance receipt. Reject if any mismatch; retain identity conflicts held out.
2. Run the existing settlement dry-run and verify the proposed result's source hash and frozen prediction; obtain exact-head CI before human review of PR #428.
3. Diagnose 13 legacy unresolved predictions with round and source-time constraints, without backfilling or relaxing identity gates.
4. Refresh the qualified production-forward aggregate and record N and eligibility reasons before any challenger comparison.
No champion or scorecard modifications. No inference of model improvement from one non-production outcome.
