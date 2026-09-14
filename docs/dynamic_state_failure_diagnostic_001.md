# DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001

Status: **preregistered descriptive diagnostic**

Parent: `DYNAMIC-STATE-DEVELOPMENT-001`

## Purpose

Describe where the already-observed fixed-versus-dynamic paired loss difference occurs.
This diagnostic does not fit or select a new parameterization.

## Frozen dimensions

All bins are fixed before the real diagnostic result.

### Pair maximum layoff days

If either player has no prior eligible source date: `DEBUT_OR_NO_PRIOR`.

Otherwise use the larger player layoff:

- `0_7`
- `8_30`
- `31_90`
- `91_180`
- `181_PLUS`

Same-day matches do not update one another.

### Pair minimum prior point depth

For each player:

`prior_serve_points + prior_return_points`

Use the smaller player total:

- `0`
- `1_499`
- `500_1999`
- `2000_4999`
- `5000_PLUS`

### Pair maximum serve-logit standard deviation

Use the larger dynamic service-logit standard deviation:

- `LE_0_35`
- `GT_0_35_LE_0_50`
- `GT_0_50_LE_0_75`
- `GT_0_75`

## Outputs

For every non-empty bucket report N, fixed and dynamic Brier, fixed-minus-dynamic Brier,
fixed and dynamic log loss, and fixed-minus-dynamic log loss.

Bucket summaries are descriptive only. They are not used to select rows, parameters, or a
new model. The parent experiment retains the formal dependence-aware inference.

Any later parameter search must be registered separately before its historical results
are inspected.

This diagnostic does not alter frozen production or prospective evidence.
