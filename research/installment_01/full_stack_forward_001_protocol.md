# FULL-STACK-FORWARD-001 protocol

Status: **REGISTERED PRE-RESULT / N=0**. This protocol is separate from PATTERN-CONFIRM-001. No record collected under the prospective pilot existed when this protocol was written.

## Question

Does the frozen final TGE-Independent-v1 probability stack retain useful probabilistic performance on a genuinely untouched prospective cohort, and does the full stack add reproducible predictive value over its frozen strict-Core component?

This protocol tests probability quality. It does **not** test sportsbook edge, execution, staking, profitability or a betting/PASS policy.

## Frozen model and execution boundary

All predictions must use the sealed TGE-Independent-v1 production bundle through the supported JSON/file-loading path. Production neighbor banks must pass their frozen byte hashes. Inputs must pass the calculator's canonical-order, finite-value, development-cutoff, Profile-validity and chronology gates. The runtime is CPython 3.11.16 with `requirements/runtime.lock`.

The prediction, exact input/source evidence, runtime/code fingerprint and later settlement must be retained by `FULL-STACK-PILOT-001-ledger-v1`. The local ledger is application-level append-only/tamper-evident, not a trusted external timestamp by itself. Each formal-cohort prediction must also be anchored before start by the registered `Prospective Evidence Anchor` GitHub Actions workflow. A calculation not durably committed and independently anchored before start is not repaired or reconstructed afterward.

## Prospective cohort

ATP and WTA are evaluated separately.

The formal cohort for each tour is the **first 1,000 eligible completed singles matches in prediction-commit order** after this protocol and the pilot implementation are merged to `main`.

A match is primary-eligible only when all of the following are true:

- exactly one official prediction was committed for that match;
- the sealed production bundle and historical banks were verified at calculation time;
- the exact input and declared source-manifest evidence were retained;
- the prediction record passes the ledger/hash-chain verifier;
- a `Prospective Evidence Anchor` workflow run was dispatched for that prediction record and chain head, the run still resolves at audit time, and its server-side GitHub Actions `created_at` precedes verified actual start;
- the anchor receipt's prediction SHA and chain-head SHA match the retained local ledger, and the run's workflow source SHA contains the registered anchor workflow version;
- the local commitment time is strictly before independently retained actual-start evidence;
- the match finished normally with `finish_status=COMPLETED`;
- the settlement winner is one of the two canonical competitors and the settlement record/evidence passes verification.

Retirements, walkovers, defaults, missing/late anchors, actual-start-unverified rows, late commitments, corrupt/incomplete records and duplicate predictions remain in the operational evidence trail but do not enter the primary scoring cohort. They must not be silently deleted.

No result-dependent filtering is allowed. Eligibility is determined solely by the frozen operational rules above.

## No-peeking rule

Operational settlement, ledger verification and anchor verification may occur continuously. Aggregate predictive outcome metrics for this registered experiment must not be calculated or inspected for a tour before that tour reaches 1,000 primary-eligible matches.

Operational counts, failure reasons, data completeness, latency, anchor success and ledger integrity may be monitored because they do not use winner-conditioned model performance. If a defect threatens scientific validity after prospective records have begun, the affected cohort is not retroactively patched to obtain a favorable result; the issue is documented and, when necessary, a new versioned prospective protocol is registered.

## Primary probability metrics

For each tour and each eligible match, let `p` be the final frozen Player A probability and `y` be 1 when canonical Player A won and 0 otherwise.

Primary full-stack metrics:

- Brier score: mean `(p - y)^2`;
- log loss: mean `-[y log(p) + (1-y) log(1-p)]`.

The frozen `strict_core_v1` component probability recorded at prediction time is the paired comparator on the same matches. Report paired match-level differences:

- `delta_brier = Brier_final - Brier_core`;
- `delta_logloss = LogLoss_final - LogLoss_core`.

Negative deltas favor the complete final stack.

## Registered incremental-value gate

Incremental forward value over strict Core is considered **confirmed for a tour** only if, at N=1,000:

1. mean `delta_brier < 0`;
2. mean `delta_logloss < 0`;
3. the upper endpoint of a two-sided 95% paired bootstrap confidence interval is below zero for **both** deltas.

Use 10,000 paired bootstrap resamples of the 1,000 match indices with replacement and fixed RNG seed `20260913`. The same resampled indices are used for final and Core losses within each replicate.

If this gate fails, retain the result. Do not tune Genome/PointSim/alignment components on this spent cohort and do not relabel a partial pass as confirmation.

This gate concerns the **incremental late stack over strict Core**. It is deliberately stronger than showing that the final probabilities are numerically reproducible.

## Calibration and descriptive diagnostics

At the same single formal read, report without additional promotion thresholds:

- calibration intercept and slope from a logistic calibration regression of outcome on final logit probability;
- expected calibration error using 10 fixed equal-width probability bins on `[0,1]`;
- mean predicted probability and observed Player A win rate;
- accuracy at the mechanical 0.5 threshold;
- probability distribution and sample count by calendar month;
- operational exclusions by reason.

These diagnostics are descriptive. No hard PASS/abstention threshold may be invented from this cohort.

## Tour conclusions

ATP and WTA receive separate conclusions. Success on one tour does not promote the other. A pooled all-tour metric may be displayed only as a descriptive supplement and cannot override a tour-specific failure.

## Market separation

Sportsbook odds, no-vig probabilities, quoted edge, EV, CLV, stake size and realized betting P/L are outside this protocol and must not enter eligibility, model inference, or the primary probability metrics.

Any future claim of sportsbook advantage requires a separately registered market/execution protocol with its own quote-age, availability, latency, selection-identity, transaction-cost and decision-policy rules. Quote freshness is therefore an operational execution concern, not a hidden scientific PASS threshold in FULL-STACK-FORWARD-001.

## Relationship to prior evidence

The partial-2026 Core holdout and the historical/adversarial Genome work remain prior evidence. This cohort is specifically intended to provide untouched forward evidence for the **complete frozen final architecture**. It does not reopen or erase prior null market hypotheses.

PATTERN-CONFIRM-001 remains scientifically and operationally separate and stays at its reported N=0 unless its own frozen provider-connected gates are satisfied.

## Outcome interpretation

A passed incremental-value gate supports the limited statement that the frozen complete stack improved both registered probabilistic losses over frozen strict Core on this prospective cohort for that tour. It still does not establish a betting advantage.

A failed gate means incremental full-stack value is not prospectively confirmed on this cohort. The result must remain visible and the cohort is spent.
