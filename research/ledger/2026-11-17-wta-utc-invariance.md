# UTC-invariant WTA index discovery — 2026-11-17

Tier: non-production research only; no fixture authorization or champion changes.

## Prespecified hypothesis
Equivalent timezone-aware representations of one instant must produce identical candidate sets, exclusions and production_eligible=False. Baseline: date derived directly from timestamp's supplied timezone; challenger: normalize timestamp to UTC before extracting date. Failure if any of three outputs differ, or production_eligible becomes true.

## Source and code
- PR: https://github.com/AidanDCM/Tennis-Genome-/pull/518
- Baseline source head: 596c60af9db8ce6007233d5c669802c96d0a2a1c
- UTC fix commit: 477a09d004dfb60b39ffe604b9f4cb9f9c718581
- Regression commit: 325e036ce5e2de30028329397ddf77779f0c2bc0
- Source reference: https://doi.org/10.1198/016214506000001437 (proper probability scoring; not evidence of discovery gains)

## Execution
Local equivalent implementation: `cd /tmp/tg && python -m pytest -q && python -m compileall -q research tests` => **1 passed in 0.05s**, compile succeeded. The local test was run against a functionally equivalent copy; exact committed-head CI not yet verified.

Synthetic sample ID: UTC-INSTANT-20261117-2330, group 12/2026, endDate 2026-11-17, status future. Equivalent instants: 2026-11-17T23:30:00Z, 2026-11-18T01:30:00+02:00, 2026-11-17T18:30:00-05:00. After UTC normalization, all three retain the same one candidate; production_eligible=False.

## Negative findings and limitations
Original date-only timezone interpretation failed representation invariance. This patch fixes the representation defect but does not establish whether provider endDate means UTC or local tournament calendar day. No raw 124-record replay in this iteration; no new eligible match, settlement or probability performance result. Do not merge without exact-head CI and provider semantics review.

## Next executable queue
1. Inspect exact-head Ruff/Pytest CI and debug any failure.
2. Replay all 124 frozen provider records with UTC-normalized filter; compare against prior five candidates and check missing status prevalence.
3. Verify tournament-local endDate semantics and actual future fixture identity/start/provenance before shadow coverage claims.
4. Continue prospective matched champion/challenger scoring only after trusted pre-start observations exist.
