# PATTERN-CONFIRM-001 Pre-result Amendment 008 — Source-Package-to-Live Provenance Binding

Status: **frozen while prospective N = 0, before any credentialed provider dry run, and before any eligible post-cutoff outcome is inspected**

Amendments 003–006 removed externally injected Profile/Core numbers and froze the real Sportradar state/context path. During final pre-merge review, one remaining provenance boundary was identified: a standalone `ProspectiveStateArtifact` can reproduce its Profile/Core values correctly without, by itself, proving that it was generated from the exact complete-season `SportradarSourcePackage` required by Amendments 004–006.

No real provider credential has been used and no prospective row has been appended. This amendment closes that integration boundary before accumulation.

No selected hypothesis, correction, alpha, O'Brien-Fleming boundary, look N, market definition, identity rule, or state-selection rule changes.

## 1. Source package is the authoritative live state input

A `PATTERN-CONFIRM-001` live row may not accept an arbitrary standalone prospective-state artifact as authoritative scientific state.

The row must be built from a verified `pattern-confirm-sportradar-source-package-v2` companion artifact that has already passed:

- the exact identity mapping;
- the sealed Sportradar-to-canonical crosswalk;
- complete Season Summaries selection/pagination/cutoff verification;
- deterministic target-context verification;
- exact frozen Profile artifact verification; and
- exact frozen Core artifact verification.

The live ledger may store the extracted prospective state for local reproducibility, but it must also bind the source package's deterministic SHA-256.

## 2. Package internal provenance must be relational, not merely parallel

It is insufficient for a package to contain one valid state-capture artifact and one valid prospective-state artifact if those artifacts are unrelated.

The package verifier must recompute the same deterministic `history_source_sha256` contract used by the Sportradar prospective-state pipeline from:

- frozen 2000–2025 canonical manifest hash;
- frozen base training-row hash;
- exact state-capture SHA-256;
- exact nested state-bundle SHA-256;
- exact target-context SHA-256;
- exact crosswalk SHA-256; and
- frozen source-contract label/version.

The prospective state's stored `history_source_sha256` must equal that recomputed value. Its `history_source_id` must equal the frozen Sportradar-extended history-source identifier.

The package must also fail closed if prospective `history_n` is inconsistent with the frozen base population plus accepted post-2025 state rows.

## 3. Live row binding

Every prospective live row must store at minimum:

- `source_package_sha256`;
- `prospective_state_sha256`; and
- the extracted sealed prospective-state payload already needed to reproduce Profile/Core values.

At append/reverification time the system must require the companion source package and verify:

- row source-package hash equals the verified package hash;
- row prospective-state hash equals the package prospective-state hash;
- row state payload equals the package prospective-state payload;
- package match ID/event/season/players agree with the verified identity mapping; and
- the package was captured no later than `prediction_generated_at` and before the then-known scheduled start.

Missing/mismatched source package fails closed and contributes zero confirmatory N.

## 4. Companion retention

The source package may be stored as a separate immutable artifact/JSONL companion rather than duplicated inside every ledger row. A live ledger is not independently admissible without its required source-package companion, identity mapping, crosswalk and frozen model artifacts.

This keeps row size manageable while making provenance mandatory.

## 5. No outcome scope expansion

The source package remains strictly target-outcome blind. It may include only the previously frozen pre-match target context and completed prior-state data admitted by the season-start/cutoff rules. Target timeline, result, score, live point state, settlement and post-match statistics remain forbidden at prediction construction.

## 6. Scientific status

This is a provenance hardening change only. `PATTERN-CONFIRM-001` remains `ACCUMULATING, N=0` for both selected hypotheses. No post-cutoff confirmatory result has been opened or spent.
