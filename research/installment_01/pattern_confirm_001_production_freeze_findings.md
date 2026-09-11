# PATTERN-CONFIRM-001 Upstream Production Freeze

Status: **FROZEN BEFORE PROSPECTIVE N > 0**

The future Profile Gap and Strict Core mappings for `PATTERN-CONFIRM-001` were fitted once from the exact pinned ATP 2000-2025 canonical source and sealed before any eligible post-cutoff outcome was used.

## Immutable execution

- workflow run: `34648450930`
- workflow head SHA: `492c068c463056a23dfe10f92f0111763adcd141`
- Actions artifact ID: `10283261404`
- Actions artifact ZIP SHA-256: `bed13296aa0ceb05ebc716a4c402eeddddd3cd07235289f68970be6487ebbf78`
- canonical manifest SHA-256: `1b670194a5ec821fd636c2af544f10c4094ac729a0249c0359966599d00b7e7c`
- eligible ATP training rows: `75,112`
- shared training-row SHA-256: `c2c5b4ddcd30f68d75b98a9b5e460ff71d4601b50115695bb1784c8f5f897d2c`
- training end year: `2025`
- state semantics: `strictly-earlier-date-state-v1`

## PROFILE-PRODUCTION-001

- representation: ATP strict Profile Strength
- include conditional features: false
- artifact SHA-256: `cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351`
- persisted artifact: `research/installment_01/profile_production_001.json`
- Elo configuration: initial `1500`, K `32`, scale `400`

The artifact contains the exact feature order, imputer statistics, scaler parameters and fitted logistic coefficients. These fitted mapping parameters are frozen for the lifetime of `PATTERN-CONFIRM-001`.

## CORE-PRODUCTION-001

- representation: ATP `strict_a_features("ATP")`
- artifact SHA-256: `5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7`
- persisted artifact: `research/installment_01/core_production_001.json`

The artifact contains the exact Strict Core feature order, imputer statistics and missingness indicators, scaler parameters, logistic coefficients and intercept. These fitted mapping parameters are frozen for the lifetime of `PATTERN-CONFIRM-001`.

## Future-state rule

Post-2025 completed matches may update only the legal dynamic player state used for later calendar dates. They may not refit either frozen production mapping during this experiment. The historical date-level chronology is retained: all matches on the same calendar date see state from strictly earlier dates.

A same-day-aware, rolling-refit or otherwise altered Profile/Core mapping belongs to a future challenger and cannot silently replace these champion inputs.

## Scientific status

This freeze uses historical data already available to the project and does not spend a prospective confirmation result. `PATTERN-CONFIRM-001` remains at N=0 for both hypotheses until the hardened live intake contract is connected to a real provider and passes its timing/identity gates.
