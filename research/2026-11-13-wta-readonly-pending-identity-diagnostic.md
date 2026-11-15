# Tennis Genome — WTA read-only pending identity diagnostic

Date: 2026-11-13. Status: DRAFT RESEARCH; NO SETTLEMENT AUTHORITY.

## Pinned repository and source evidence

- Main source SHA: 40bb697ec786527b7ed1a4c67d6d0a92aea17782.
- WTA compiler blob SHA: e4785a6d0b9b07c4fd4a52d2b44927211e5f7172.
- WTA non-production scorecard blob SHA: c9636ac9d86c256ccf241e652b9456034c451fc3.
- Historical source root: web-shadow/result-evidence/wta-results-20261109t083951z/sources.
- Acquisition manifest blob SHA: f0a5a8b98029ece856a2bfffc0b88b5b7ad92c42; observation timestamp: 2026-11-09T08:39:51+00:00.
- Frozen independent production bundle SHA-256 as recorded by docs/independent_v1_production_freeze.md: 7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1. Not rebuilt, changed or promoted in this iteration.
- Prior independently qualified FULL-STACK-FORWARD-001 N=1 is recorded as of 2026-09-16 in research/installment_01/full_stack_forward_001_status_001.md; current cumulative qualified N not revalidated. Formal aggregate performance remains embargoed under its protocol.

## Falsifiable hypothesis, baseline and acceptance

Hypothesis: a read-only classifier, compared with the unchanged strict result compiler, separates all 15 pending records into exactly 12 unique same-event main-singles player-pair candidates with round discrepancies, one missing legacy player pair, and two exact MatchID conflicts. It must refuse ambiguous/incorrect-event/qualifying matches, return no winner, and have no write path. This is a result-acquisition diagnostic, NOT a new forecasting model or a performance comparison.

Acceptance: run the adversarial regression suite and SHA-verified historical integration test, require exactly 12 / 1 / 2; preserve all frozen predictions and strict production/settlement gates. A negative or ambiguous candidate never becomes qualified by this test.

## Work actually executed

- Read raw main scorecard, compiler, 15 immutable pending prediction fixtures, and retained Seoul/Singapore/Hong Kong match-source rows. Recomputed the candidate crosswalk without changing any outcomes.
- The read-only crosswalk found 12 unique player pairs (11 source RoundID=1 and one RoundID=2), one legacy pair absent, and two exact-MatchID wrong-player conflicts. The compiler maps numeric 1 to F, numeric 2 to SF, while the frozen legacy rounds are R32/R16. These are incompatible conventions; source numeric codes are retained without inventing authoritative round labels.
- Added scripts/diagnose_wta_pending_matches.py with a read-only JSON-only CLI. It invokes existing SHA-256 acquisition verification and frozen prediction-digest checks before any classification; outputs raw source fields and candidate reasons. It never produces or writes results.
- Added tests/test_diagnose_wta_pending_matches.py with adversarial source-identity tests and an integration regression against the ten-tournament pinned manifest.
- Local execution: python -m pytest -q tests/test_diagnose_wta_pending_matches.py -k 'not retained_main' returned **13 passed, 1 deselected**. Local python -m compileall -q scripts tests completed successfully. Local Ruff executable was not installed.
- First exact-code-head CI for SHA f376c7592df96afa951143e1e0d87b6b239627c5: [GitHub Actions 43462413440](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43462413440), job success; Ruff success and full pytest success. Logs confirmed both steps and complete job conclusion, but pytest output was redirected to a diagnostic artifact and the full-suite N was not extracted. Artifact 14057346531.
- [Draft PR #490](https://github.com/AidanDCM/Tennis-Genome-/pull/490); no merge, no changes to the settlement compiler. The documentation commit following this ledger will need its own exact-head CI observation.

## Sample IDs, categories and negative controls

The nine Seoul legacy round-discrepant prediction IDs:
- web:wta:seoul:2026:r32:sakatsume-preston
- web:wta:seoul:2026:r32:ruse-lys
- web:wta:seoul:2026:r32:montgomery-park
- web:wta:seoul:2026:r32:zarazua-bondar
- web:wta:seoul:2026:r32:ma-jones
- web:wta:seoul:2026:r32:ku-ibragimova
- web:wta:seoul:2026:r32:birrell-zidansek
- web:wta:seoul:2026:r32:zakharova-ostapenko
- web:wta:seoul:2026:r32:kenin-charaeva

Three Singapore legacy round-discrepant IDs:
- web:wta:singapore:2026:r32:oliynykova-wolff
- web:wta:singapore:2026:r32:parks-yamaguchi
- web:wta:singapore:2026:r16:sasnovich-andreeva

Absent legacy pair: web:wta:singapore:2026:r16:anisimova-gibson.

Exact-ID wrong-player conflicts:
- web:wta:1074:2026:LS031, frozen Parks/Eala versus source Emerson Jones/Eala.
- web:wta:1074:2026:LS020, frozen Kenin/Fernandez versus source Mika Stojsavljevic/Kenin.

Tested negative cases include duplicate exact IDs; absent IDs; conflicting exact players even with an alternative same-player row; different event IDs; malformed event numbers; qualifying rows; duplicate legacy pairs; textual RoundID with no numeric interpretation. A unique same-player match is ONLY a candidate; no pre-start schedule authority or round proof is inferred from it.

## Reproduction on a full repository checkout

Run from the repository root, after installing pinned CI requirements:

    python -m scripts.diagnose_wta_pending_matches --config web-shadow/result-config.json --scorecard web-shadow/scorecard.json --acquisition-manifest web-shadow/result-evidence/wta-results-20261109t083951z/sources/acquisition-manifest.json --source-root web-shadow/result-evidence/wta-results-20261109t083951z/sources --repo-root . --observed-at 2026-11-09T08:39:51+00:00

    python -m pytest -q tests/test_diagnose_wta_pending_matches.py
    ruff check scripts/diagnose_wta_pending_matches.py tests/test_diagnose_wta_pending_matches.py

## External research and contrary method

- Astappiev et al. (July 2026), [SMBench](https://doi.org/10.1016/j.is.2026.102711), Information Systems 139, 102711, separately benchmarks candidate filtering and verification with three filters and seven verifiers on nine datasets. Paper CC BY 4.0; linked external software license not verified and no code imported. Adapted principle: do not promote candidate retrieval into identity certification.
- Moslemi et al. (July 2026), [Heterogeneity in entity matching](https://doi.org/10.1016/j.datak.2026.102575), Data & Knowledge Engineering 164, finds test-time semantic heterogeneity degrades matching; motivates preserving raw RoundID and explicit negative cases.
- Poudel et al. (July 2026), [unified ATP benchmark](https://doi.org/10.3390/analytics5030022), aligned temporal experiments, contrary to assumed large gains from complex forecasting models. It is a different ATP population and cannot be compared with the present WTA selection diagnostics. No implementation or data was imported.

## Performance and ordered next actions

The NON-PRODUCTION WTA Web Shadow scorecard remains 47/86 correct (54.65%), Brier 0.251322, log loss 0.696621, with 15 pending. A fixed 0.5 probability yields better proper scores (Brier 0.250000, log loss about 0.693147). No new qualified forward N, accuracy improvement, or challenger lift is claimed.

1. Independently verify official pre-start event/draw/round, timestamps and source provenance for the 12 unique player-pair candidates; do not backfill or settle based solely on this report.
2. Preserve both Hong Kong identity vetoes and the absent Singapore pair. Examine identity migrations and round meaning with independent official evidence; if a future-only compiler change is justified, require new dedicated fail-closed tests and human review.
3. Fix current-player-state coverage and pre-start source qualification for NEW predictions. Refresh the prospective forward denominator, maintain frozen champion and holdout, and score matched chronological champion/challenger pairs only once independently qualified.
