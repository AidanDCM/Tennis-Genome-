# MARKET-VALIDATION-RUN-001 — Pre-Result Amendment 001

Status: **frozen before licensed Betfair winner-outcome evaluation**

## Why this amendment exists

The staged validation coordinator already separated an outcome-locked Stage A from the outcome-open Stage B. Before any licensed Betfair winner-outcome experiment was run, an integrity audit identified several coordinator-level gaps that could allow the execution environment to drift from the already-frozen MARKET-HIST-QA, POWER-MDE, MARKET-EDGE-001 and MARKET-EDGE-ADV-001 designs.

This amendment strengthens only orchestration and provenance. It does **not** alter any tennis signal, market-price transform, statistical model, multiplicity family, score metric, promotion threshold, or observed market result.

## Frozen hardenings

### 1. Source-manifest semantics

Stage A and Stage B must parse the Betfair historical source manifest through the repository's validated manifest loader. A file with a valid SHA-256 but invalid provider, sport, market type, data package, or research date interval is rejected.

### 2. QA consistency

The Stage-A seal requires:

- `effective_overall_status = ELIGIBLE_CONFIRMATORY`;
- `qa_report.overall_status = ELIGIBLE_CONFIRMATORY`;
- unique ATP and WTA rows;
- both tour rows marked `ELIGIBLE_CONFIRMATORY`;
- the exact frozen MARKET-HIST-QA coverage gate set; and
- every frozen gate equal to `true` for both tours.

A re-hashed but internally inconsistent QA artifact cannot unlock outcomes.

### 3. QA outcome-file binding

MARKET-HIST-QA already hashes the canonical outcomes table because it uses retirement/walkover metadata to define the eligible completed-match denominator. Stage A now copies that exact `input_sha256.outcomes` value into the outcome-unlock seal as `qa_outcomes_sha256`.

Stage B hashes the supplied outcomes file **before either market evaluator is called** and requires an exact match with `qa_outcomes_sha256`.

Therefore the outcome-bearing experiment cannot silently switch to a different settlement/outcome file after QA has been frozen.

### 4. POWER-MDE design binding

Stage A requires the frozen POWER-MDE family:

- four claims exactly: ATP Profile Gap, WTA Profile Gap, ATP Genome, WTA Genome;
- `family_size = 4`;
- `family_alpha = 0.05`;
- `conservative_planning_alpha = 0.0125`;
- `min_prior_rows = 1000` for every claim; and
- identifiable plans for every year 2021–2025 for all four claims.

POWER-MDE remains outcome-blind and remains a feasibility diagnostic, not a promotion test.

### 5. Confirmatory prior-row threshold

`MARKET-VALIDATION-RUN-001` Stage B is frozen at `min_prior_rows = 1000`.

The CLI may expose the parameter for explicit validation/backward compatibility, but any value other than 1000 is rejected before outcome scoring. Both frozen child evaluators receive 1000.

### 6. Stage-A input immutability

All non-outcome files sealed in Stage A continue to be SHA-256 checked again before Stage B. Any changed file blocks execution before winner outcomes are used by the evaluators.

## Synthetic validation scope

The dedicated staged-validation workflow is intentionally an orchestration gate. It verifies:

- valid Betfair manifest semantics;
- self-hashed QA and POWER-MDE artifacts;
- exact four-claim/frozen-threshold enforcement;
- deterministic Stage-A seals;
- no Stage-A outcome CLI argument;
- post-seal input mutation rejection;
- different-outcome-file rejection; and
- rejection of a non-1000 prior-row threshold.

The existing MARKET-EDGE-001 and MARKET-EDGE-ADV-001 workflows remain responsible for validating the child statistical experiments themselves.

## Interpretation

These changes make the confirmatory market run **harder to alter**, not easier to pass. No licensed Betfair winner-outcome result was inspected to motivate or tune them. They are frozen prospectively as provenance safeguards before real market evaluation.
