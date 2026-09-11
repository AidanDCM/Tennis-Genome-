# PATTERN-DISCOVERY-001 — Amendment 002

Status: **FROZEN BEFORE ANY REAL RESIDUAL PATTERN MINING**

## Trigger

During implementation review of `pattern-discovery-v1`, before the first real residual-pattern run, an edge case was identified in applying discovery-fitted numeric bins to the 2023-2025 validation block.

The first implementation used discovery-era minimum and maximum values as the outer numeric bin boundaries. If a validation observation fell below the discovery minimum or above the discovery maximum, it would be omitted from every numeric bin even though its feature value was finite. That would create avoidable validation attrition and make candidate coverage depend on whether future values happened to remain inside the historical range.

No real PATTERN-DISCOVERY-001 candidate statistic, p-value, survivor decision, or validation effect has been generated or inspected before this amendment.

## Frozen correction

Discovery-fitted internal cut points remain unchanged and are still learned from the discovery block only.

When those frozen cut points are applied to validation data:

- the first bin is open to negative infinity and contains every finite value below its upper cut point;
- interior bins remain `[lower, upper)`;
- the last bin is open to positive infinity and contains every finite value at or above its lower cut point;
- if duplicate discovery quantiles collapse the feature to a single remaining bin, that bin contains every finite value;
- missing and non-finite values remain excluded from numeric candidate cells and are still represented through the artifact's missingness accounting.

The same range-completion rule applies whenever the implementation reuses the frozen bin helper for discovery-fitted quintiles or tertiles.

## Unchanged methodology

This amendment does not change:

- the discovery cutoff (`<= 2022`);
- the untouched internal-validation years (`2023-2025`);
- any feature in the frozen search universe;
- any discovery-fitted internal quantile or tertile cut point;
- the fixed market-probability bands;
- the declared FDR families;
- the one-sample residual test;
- the Benjamini-Hochberg procedure or `q < 0.10` survivor threshold;
- minimum discovery or validation sample sizes;
- the 2,000-resample deterministic bootstrap;
- the annual-concentration gate;
- the correction diagnostic;
- the exploratory-only / no-production-promotion status.

This is a prospective range-completion correction made before any real pattern result exists.
