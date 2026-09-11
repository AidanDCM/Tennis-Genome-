# MARKET-EDGE-001 — Pre-Result Amendment 010

Status: **FROZEN BEFORE ANY BOOKMAKER-VS-SIGNAL RESULT**

## Trigger

A code-level adversarial review confirmed that the repository already contains two distinct frozen market tests:

1. `MARKET-EDGE-001`: chronological market recalibration control versus market + frozen signal;
2. `MARKET-EDGE-ADV-001`: chronological market-only, market + frozen Strict Core, and market + Strict Core + frozen signal.

The two experiment families currently emit independent pass decisions. Before opening any real bookmaker-vs-signal outcome, this amendment makes their relationship explicit and adds deterministic calibration diagnostics.

No real `BOOKMAKER_CLOSE_V1` Profile Gap or Genome edge result has been opened before this amendment.

## Load-bearing promotion rule

The four confirmatory claims remain:

1. ATP × Profile Gap;
2. WTA × Profile Gap;
3. ATP × Genome;
4. WTA × Genome.

For each claim:

- `market_incremental_pass` is the frozen `MARKET-EDGE-001` family decision;
- `market_core_incremental_pass` is the frozen `MARKET-EDGE-ADV-001` family decision;
- final `stack_promotion_pass` is fixed prospectively as:

```text
stack_promotion_pass = market_incremental_pass AND market_core_incremental_pass
```

A claim may be described as **market-incremental** if `MARKET-EDGE-001` passes. It may be promoted as incremental structure for the Tennis Genome stack only if `stack_promotion_pass` is true.

A failure of either constituent test cannot be rescued by the other test, a subgroup, a probability region, a later threshold, or a post-result rule change.

This rule is deliberately conservative and does not alter either underlying experiment, its Holm correction, or its proper-score promotion criteria.

## Reliability diagnostics

For every confirmatory claim, emit the repository's existing fixed-width ten-bin calibration table for every probability view already produced by the two frozen evaluators.

`MARKET-EDGE-001` views:

- raw market probability;
- chronological market recalibration control;
- market + signal challenger.

`MARKET-EDGE-ADV-001` primary expanding-window views:

- raw market probability;
- frozen Strict Core probability;
- market-only recalibration;
- market + Strict Core control;
- market + Strict Core + signal challenger.

Each bin records the existing `CalibrationBin` fields:

- lower probability bound;
- upper probability bound;
- sample count;
- mean forecast probability;
- observed outcome rate.

The fixed ten bins cover the entire `[0, 1]` interval. No individual bin, including the 40–60% region, is selected as a new confirmatory pass/fail threshold.

Reliability tables are **diagnostic only** for this already-frozen family. They may identify hypotheses for a later preregistered pattern-discovery phase, but they may not override or rescue the frozen proper-score / inference decisions.

## Combined decision artifact

After Stage B produces both frozen experiment artifacts, a deterministic postprocessor must:

1. verify both artifacts contain exactly the same frozen four-claim labels;
2. extract their machine-generated family decisions;
3. compute `stack_promotion_pass` only by the AND rule above;
4. compute all fixed ten-bin reliability tables from the already-emitted prediction rows;
5. self-hash the combined decision/diagnostic artifact.

The postprocessor may not refit a model, choose a subgroup, change a probability, alter an outcome, or modify either experiment's p-values or promotion decisions.

## Unchanged

This amendment does not change:

- `BOOKMAKER_CLOSE_V1` source hierarchy or no-vig transform;
- the exact market population or QA gates;
- Profile Gap or Genome signal values;
- Strict Core probabilities;
- chronological fitting;
- family size 4;
- alpha 0.05;
- conservative planning alpha 0.0125;
- Holm correction;
- `min_prior_rows = 1000`;
- annual/recent/concentration gates;
- the 2025 development cutoff;
- the non-claim of betting profitability.
