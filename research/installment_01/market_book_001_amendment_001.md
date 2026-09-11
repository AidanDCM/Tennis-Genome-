# MARKET-BOOK-001 Amendment 001 — Row-Level Identity Quarantine

Status: **PREREGISTERED / PRE-RESULT**

Date: 2026-09-11

## Trigger

The first real-source, outcome-blind preflight discovered that the public Valuebetennis 2023 season file is otherwise structurally parseable but contains four raw rows whose two contestant fields both normalize to the same placeholder identity (`Unknown Player`).

The original adapter treated any such single-row identity failure as a file-level structural failure, which quarantined the entire season file. No Profile Gap, Genome, Strict Core, MARKET-EDGE, or MARKET-EDGE-ADV outcome result had been opened when this behavior was discovered.

## Clarification

A raw row that cannot form two distinct non-empty normalized contestant identities is ineligible for MARKET-BOOK construction and is skipped before a sanitized bookmaker quote is emitted.

This row-level quarantine applies only to contestant-identity failures such as:

- missing contestant name;
- empty contestant name;
- two contestant names that normalize to the same identity.

The exact raw source file remains bound by its SHA-256 in the source manifest, so skipped rows remain reproducibly part of the frozen source snapshot even though they do not produce sanitized market records.

## What remains fail-closed at file/source level

This amendment does **not** weaken structural validation for:

- missing required market columns;
- invalid or unparseable source dates;
- invalid tour values;
- Tennis-Data files whose embedded tour marker disagrees with the requested tour;
- post-2025 source rows in confirmatory construction;
- source-file size or SHA-256 mutations after manifest freeze.

Such failures continue to reject/quarantine the affected file or source construction as already specified.

## Methodology impact

None of the following changes:

- `BOOKMAKER_CLOSE_V1` source priority;
- Valuebetennis-over-Tennis-Data hierarchy;
- closing-price definitions;
- proportional no-vig transform;
- canonical identity window;
- ATP/WTA coverage thresholds;
- minimum prior-history requirement;
- four frozen confirmatory claims;
- multiplicity handling;
- MARKET-EDGE or adversarial statistical engines.

This amendment prevents a handful of unusable identity rows from deleting tens of thousands of unrelated, valid rows in the same season. It is an implementation-integrity correction made before confirmatory market-performance results are observed.
