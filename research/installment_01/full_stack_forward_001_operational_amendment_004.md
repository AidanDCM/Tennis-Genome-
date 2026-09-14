# FULL-STACK-FORWARD-001 — Operational Amendment 004

Date: 2026-09-14

Status: **REGISTERED PRE-RESULT / N=0**

This amendment applies only to `FULL-STACK-FORWARD-001`. PATTERN-CONFIRM-001 remains N=0 under its
separate frozen protocol.

## Purpose

Operational Amendment 003 retained the exact Sportradar daily-summary payload and required every due
main-tour ATP/WTA singles event in that retained provider batch to reconcile into the prospective event
census. That closed skip-after-batch-capture, but two narrower threats remained:

1. the local batch observation time and hash chain were still controlled by the operator's filesystem;
2. no frozen rule yet required every provider capture window to occur.

Amendment 004 therefore adds an externally timestamped GitHub Actions anchor and a fixed UTC provider
capture cadence.

## Scientific non-change

This is an evidence-integrity and denominator-completeness amendment only. It does **not** change:

- TGE-Independent-v1 or any production-bundle/model parameter;
- ATP/WTA prediction architecture;
- frozen ATP/WTA provider population scope from Amendment 003;
- the first-1,000-primary-eligible-completed-matches-per-tour target;
- prediction-commit ordering;
- formal primary-eligibility criteria;
- strict-Core comparator;
- Brier score or log-loss definitions;
- paired-bootstrap procedure, seed, confidence level or incremental-value gate;
- no-peeking restrictions;
- market separation;
- any betting, staking or PASS rule.

FULL-STACK-FORWARD-001 remains N=0 at registration of this amendment.

## External provider-batch anchor

The frozen workflow is `.github/workflows/provider_batch_anchor.yml`.

For every provider batch used for formal cadence/denominator coverage, the workflow receipt must bind:

- exact provider-batch record SHA-256;
- claimed immediate provider-batch chain-head SHA-256;
- queried schedule date;
- local `observed_at`;
- exact raw Sportradar payload SHA-256;
- deterministic provider-batch manifest SHA-256;
- GitHub repository, workflow source SHA and workflow run ID.

The exact receipt artifact and complete GitHub workflow-run metadata JSON must be retained locally.

The trusted external time is GitHub's server `created_at` field from the workflow-run metadata. The
runner-created receipt timestamp is provenance only.

A valid anchor requires:

- repository `AidanDCM/Tennis-Genome-`;
- event `workflow_dispatch`;
- completed/successful run;
- workflow path `.github/workflows/provider_batch_anchor.yml`;
- `head_branch=main`;
- workflow source SHA agreement between run metadata and receipt;
- exact agreement between all receipt batch fields and the retained provider-batch record;
- GitHub server `created_at` no more than one hour after the local batch observation time, with a
  five-minute tolerance for local/server clock skew.

Each provider-batch record may have at most one accepted anchor attestation.

## Frozen provider capture cadence

Formal collection uses the following UTC slots every calendar day:

- 00:00 UTC;
- 06:00 UTC;
- 12:00 UTC;
- 18:00 UTC.

Each slot has a one-hour capture/anchor window `[slot, slot + 1 hour]`.

For every due slot, exactly two schedule dates are required for coverage:

1. the slot's UTC calendar date `D`;
2. the following UTC calendar date `D+1`.

A required `slot x schedule-date` pair is covered when at least one retained provider batch for that
schedule date has both:

- local `observed_at` within the slot's one-hour window; and
- a verified GitHub server anchor time within the same one-hour window.

Extra provider batches are permitted but cannot substitute for a missing required pair unless they
satisfy that exact slot/date requirement.

A slot becomes due only after its one-hour window has closed. Formal completeness may therefore be read
only through a cutoff for which all preceding due slot/date pairs have been checked.

## Coverage start

The cadence structure and windows are frozen now at N=0. The concrete `coverage_start` is not assigned
retrospectively in this amendment because the genuine supervised end-to-end production dry run has not
yet occurred.

Before formal prospective accrual begins, the operator must register `coverage_start` as the first exact
00:00/06:00/12:00/18:00 UTC slot after the genuine supervised dry run has succeeded. Once registered,
`coverage_start` cannot be moved forward to erase a missed slot or unfavorable event.

Data before that registered start is diagnostic only and cannot retroactively establish cadence
coverage.

## Event-level external pre-start requirement

For every due event classified `CENSUS_REQUIRED` under Amendment 003, at least one retained batch
containing that event must have a valid GitHub server anchor timestamp **strictly before the event's
scheduled start**.

Consequences:

- a locally backdated batch anchored only after scheduled start cannot satisfy formal denominator
  evidence;
- an unanchored extra batch cannot rescue an event;
- if the same event appears in multiple batches, one valid externally anchored pre-start occurrence is
  sufficient, subject to all Amendment-003 cross-batch identity/schedule consistency checks;
- a late post-start recapture does not poison an earlier valid anchored pre-start capture.

## Combined formal-read gate

Before outcome-conditioned registered metrics are read, the operator must run the combined anchored
reconciliation gate. It requires all of:

1. provider-batch ledger verification;
2. provider-batch external-anchor ledger verification;
3. fixed-slot D/D+1 cadence completeness through the analysis cutoff;
4. Amendment-003 provider-batch/census reconciliation;
5. externally timestamped pre-start support for every due `CENSUS_REQUIRED` event;
6. all previously registered census/pilot/prospective eligibility checks.

Failure of any required capture slot, anchor, batch/census reconciliation, or event-level external
pre-start test blocks the formal read. It is not converted into a favorable exclusion.

## Short-notice provider changes

The six-hour cadence plus D/D+1 overlap is an operational integrity rule, not a claim that Sportradar
can never add or reschedule an event inside six hours. An otherwise in-scope event first retained only
at/after scheduled start remains a `DENOMINATOR_FAILURE` under Amendment 003 and blocks the formal read.
This is intentionally conservative.

## Threat boundary

This amendment provides an external GitHub timestamp and mechanically detectable cadence. It still
does not turn local GitHub metadata files into cryptographically signed statements. The durable GitHub
run ID/URL remains an external audit reference and should be confirmed directly against GitHub for a
formal audit.

The GitHub anchor workflow currently retains uploaded artifacts for 90 days. The exact receipt and run
metadata are retained locally as experiment evidence; long-term external archival can be hardened later
without changing the statistical experiment.

The current ChatGPT GitHub connector does not expose workflow dispatch, so code-level verification of
this workflow is not a genuine external-anchor dry run. A real manual dispatch remains mandatory in the
supervised end-to-end production dry run.

## Non-claims

This amendment establishes no evidence of predictive superiority, market mispricing, sportsbook edge,
profitability, autonomous wagering readiness or real-money readiness.
