# MARKET-VALIDATION-RUN-001 — staged real-market validation coordinator

Status: **PREREGISTERED BEFORE LICENSED MARKET OUTCOMES**

## Purpose

MARKET-VALIDATION-RUN-001 is an orchestration/integrity layer. It does **not** introduce a new predictive hypothesis, change MARKET-EDGE-001 or MARKET-EDGE-ADV-001, or create a new promotion rule.

Its purpose is to make the intended real-data execution order executable and auditable:

1. licensed Betfair source bundle is frozen and reconstructed;
2. MARKET-HIST-QA-001 is completed;
3. POWER-MDE-001 is completed without winner outcomes;
4. a deterministic outcome-unlock seal is created for the exact artifacts;
5. only then are canonical settled winners supplied to the official staged runner;
6. both frozen MARKET-EDGE-001 and MARKET-EDGE-ADV-001 are executed on the same immutable market/signal inputs.

The coordinator cannot prevent a human from manually opening an outcomes file outside the software. It provides the repository's official fail-closed execution path and makes deviations from the intended sequence explicit.

## Evidence boundary

No licensed Betfair market outcome/result has been supplied or inspected to define this protocol.

The 2026 holdout remains spent. All coordinated MARKET-EDGE development/evaluation is frozen through 2025.

## Stage A — outcome-locked seal

Stage A may read only:

- MARKET-HIST-QA-001 artifact;
- POWER-MDE-001 artifact;
- frozen Betfair source manifest;
- MARKET-HIST-001 records;
- canonical pre-match table;
- frozen ATP/WTA PROFILE-GAP-001 reports;
- frozen ATP/WTA GENOME-ADV-001 reports.

Stage A has no canonical-winner/outcome argument.

It must verify:

- MARKET-HIST-QA artifact self-digest is valid;
- MARKET-HIST-QA is not structurally blocked;
- ATP and WTA are both `ELIGIBLE_CONFIRMATORY` for the frozen four-claim confirmatory family;
- QA input hashes agree with the supplied source manifest, MARKET-HIST records and canonical pre-match table;
- POWER-MDE artifact self-digest is valid;
- POWER-MDE declares `outcome_blind=true`;
- POWER-MDE input hashes agree with the supplied MARKET-HIST, pre-match and four frozen signal reports;
- POWER-MDE contains exactly the four frozen claims:
  - ATP Profile Gap;
  - WTA Profile Gap;
  - ATP Genome;
  - WTA Genome;
- every claim has identifiable prospective power plans including 2021, 2022, 2023, 2024 and 2025;
- no supplied file hash changes between artifact generation and seal creation.

A high MDE or weak approximate power is **diagnostic only**. Stage A does not lower significance thresholds, delete a claim, or rescue/reject a signal based on power.

If integrity/coverage/power-artifact completeness fails, no unlock seal is produced.

## Stage A output

The deterministic seal records:

- experiment ID/version;
- stage=`OUTCOME_LOCKED_COMPLETE`;
- exact input SHA-256s;
- QA artifact SHA-256 and effective status;
- QA ATP/WTA statuses;
- POWER-MDE artifact SHA-256;
- the four claim labels and identifiable evaluation years;
- `winner_outcomes_permitted_for_stage_b=true`;
- a canonical SHA-256 digest over the unsigned seal payload.

No wall-clock timestamp is included in the digest so repeated execution on identical artifacts is byte/digest deterministic.

## Stage B — outcome-open execution

Stage B requires:

- the exact Stage A seal;
- the exact QA and POWER-MDE artifacts sealed in Stage A;
- the exact MARKET-HIST records, pre-match table and frozen signal reports sealed in Stage A;
- canonical settled outcomes supplied only at this stage.

Before reading/using winner outcomes for scoring, Stage B must re-verify:

- Stage A seal self-digest;
- all Stage A input file hashes;
- QA and POWER artifact self-digests;
- QA confirmatory ATP/WTA eligibility;
- POWER-MDE four-claim completeness/outcome-blind declaration.

Only after those checks succeed may Stage B execute:

1. frozen `MARKET-EDGE-001`;
2. frozen `MARKET-EDGE-ADV-001`.

The two experiments remain scientifically independent artifacts. Stage B does not combine their p-values, alter their Holm families, or promote a claim that either frozen experiment itself rejects.

## Stage B output

The deterministic result bundle records:

- Stage A seal SHA-256;
- canonical outcomes SHA-256;
- all sealed input hashes;
- complete MARKET-EDGE-001 artifact;
- complete MARKET-EDGE-ADV-001 artifact;
- SHA-256 of each embedded result artifact;
- deterministic bundle SHA-256.

The bundle is a transport/provenance object, not a new statistical experiment.

## Fail-closed requirements

The coordinator must reject at minimum:

- malformed or wrong experiment IDs;
- tampered artifact self-digests;
- hash disagreement between QA/POWER artifacts and supplied files;
- ATP or WTA not QA-confirmatory;
- missing/duplicate/unexpected POWER-MDE claims;
- missing or non-identifiable 2021–2025 power plans;
- changed files after Stage A seal creation;
- post-2025 canonical development rows as already enforced by downstream frozen experiments;
- a Stage B QA/POWER artifact different from the artifact sealed in Stage A.

## Non-claims

MARKET-VALIDATION-RUN-001 does not establish market edge, CLV, EV, ROI, profitability, execution quality, or new forward validation. It only makes the already-frozen research order executable and auditable.
