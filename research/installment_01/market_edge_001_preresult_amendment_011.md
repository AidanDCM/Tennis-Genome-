# MARKET-EDGE-001 — Pre-Result Amendment 011

Status: **FROZEN BEFORE POWER-MDE-001, STAGE A, AND ANY BOOKMAKER-VS-SIGNAL RESULT**

## Trigger

Amendment 009 hardened the Stage-A firewall by projecting accepted historical development reports into outcome-free signal ledgers containing only `match_id` and the frozen signal. During pre-result end-to-end wiring, a compatibility defect was identified: the already-preregistered `MARKET-EDGE-ADV-001` adversarial control requires the frozen Strict Core probability for the same match in addition to the frozen signal.

The accepted development reports already contain those pre-match Core probabilities, but Amendment 009's projection v1 removed them together with result-bearing fields. As a consequence, the primary two-arm test and POWER-MDE could consume projection v1, while the stronger Market + Core adversarial test could not consume the same sealed files.

No real bookmaker-vs-Profile-Gap, bookmaker-vs-Genome, `MARKET-EDGE-001`, or `MARKET-EDGE-ADV-001` result has been evaluated or inspected before this amendment.

## Correction

Projection version becomes `market-signal-projection-v2`.

Each projected row must contain only:

- canonical `match_id`;
- the already-frozen signal field;
- the already-frozen pre-match Strict Core probability field needed by `MARKET-EDGE-ADV-001`.

The Core probability is a pre-match model output and is not an outcome/result field. No winner label, score, correctness metric, realized residual, Brier/log-loss value, retirement/walkover flag, or other historical performance diagnostic may enter the projection.

## Frozen field mapping

### Profile Gap

- ATP and WTA signal: `profile_gap_match`;
- ATP and WTA Core probability: `strict_core_probability`.

### Genome adversarial artifacts

- ATP signal: `full_neighbor_residual`;
- WTA signal: `core_neighbor_residual`;
- ATP and WTA Core probability: `core_probability_a`.

These fields are copied byte-for-value through numeric JSON serialization from the exact accepted parent artifacts frozen in Amendment 008. No refitting or recomputation occurs in the projection step.

## Required checks

Projection v2 must:

1. verify the exact accepted parent SHA-256;
2. verify parent experiment ID and tour;
3. reject duplicate/empty match IDs;
4. require finite signal values;
5. require finite Core probabilities strictly inside `(0, 1)`;
6. sort rows deterministically by match ID;
7. self-hash the unsigned projection payload;
8. carry parent SHA-256 provenance;
9. contain no historical outcome/performance fields.

POWER-MDE-001, Stage A, `MARKET-EDGE-001`, and `MARKET-EDGE-ADV-001` must all consume these same four projection-v2 files.

## Amendment 009 relationship

Amendment 009 remains the governing outcome-firewall decision. Its phrase "read only canonical `match_id` and the already-frozen signal field" is superseded only to the minimum extent necessary to also carry the already-frozen pre-match Strict Core probability required by the preregistered adversarial control.

No outcome-bearing parent report may be passed directly into Stage A or Stage B.

## Unchanged

This correction changes no signal value, Core probability, source hierarchy, matched population, statistical model, significance threshold, multiplicity rule, chronology rule, market-coverage gate, or promotion criterion.
