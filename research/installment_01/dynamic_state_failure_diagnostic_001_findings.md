# DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001 — findings

Status: **descriptive diagnostic complete; no parameter or subgroup selection**

Run date: 2026-09-14

## Reproducible execution

The preregistered diagnostic completed successfully in GitHub Actions:

- workflow run: `34861688391`
- workflow head: `e89934c889ade319703164b85b3534c8fe0c8223`
- workflow: `.github/workflows/dynamic_state_failure_diagnostic_real.yml`
- artifact ID: `10355012936`
- artifact SHA-256: `1fb1faee7ab09645ccd527ec7f768adc07dc9d08ac7edfbd5cf705dc1cf44ff4`
- pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- historical source coverage: 2000–2025
- scored parent test years: 2015–2025
- interpretation boundary: **DESCRIPTIVE_ONLY_NO_PARAMETER_SELECTION**

Before the diagnostic ran, the workflow rebuilt both canonical datasets and reproduced the archived row counts plus source-bundle, pre-match, outcome and stats SHA-256s exactly.

## Parent binding and diagnostic provenance

### ATP

- prediction rows: `29,587`
- parent development report SHA-256: `3e49e858b5a79b0ec259e133e3e997131ffb6be36d705f84fb26ebe37040a3a4`
- parent dataset fingerprint: `df3822aa1129ba825de9300cf74f5b948171309e02bbaa3e6fabf8d813fe58cf`
- parent source identity: `742283031b9a89f703ae852511ef207e16dde7b70f961d02db102e785aa060a8`

### WTA

- prediction rows: `27,664`
- parent development report SHA-256: `c41ba6d22dd121e0ebaa3acebb83797756bbdd7791030c10c1a07401f307097c`
- parent dataset fingerprint: `b97a5d9fef5916e836d3ef4722d26c5c43c829d24c17d5d0d701106d150bd2ea`
- parent source identity: `9d43d556933947879d61c51a83865a8ee48a885df45b141e588136dd5c6d42d2`

Shared diagnostic code fingerprint:

`8b9ce63b85ae84f30f6f7e2a47ae8530f7793a91c558b99761739f343b11a23d`

Positive deltas below mean lower loss for the already-frozen dynamic candidate. These are descriptive bucket means, not bucket-specific model-selection tests.

## ATP decomposition

### Pair maximum layoff

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| DEBUT_OR_NO_PRIOR | 968 | **-0.00509238** | **-0.01166309** |
| 0_7 | 6,044 | -0.00168475 | -0.00374243 |
| 8_30 | 13,332 | -0.00079678 | -0.00176664 |
| 31_90 | 4,752 | -0.00081729 | -0.00205365 |
| 91_180 | 2,111 | -0.00277102 | -0.00621858 |
| 181_PLUS | 2,380 | **-0.00366114** | **-0.00766658** |

### Pair minimum prior point depth

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| 0 | 1,332 | **-0.00367657** | **-0.00847545** |
| 1_499 | 1,316 | **-0.00342342** | **-0.00757884** |
| 500_1999 | 2,738 | -0.00161443 | -0.00316542 |
| 2000_4999 | 3,626 | -0.00101246 | -0.00209034 |
| 5000_PLUS | 20,575 | -0.00129710 | -0.00296891 |

### Pair maximum dynamic serve-logit uncertainty

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| LE_0_35 | 3,274 | -0.00076175 | -0.00194018 |
| GT_0_35_LE_0_50 | 18,376 | -0.00116100 | -0.00261634 |
| GT_0_50_LE_0_75 | 4,888 | -0.00160343 | -0.00345581 |
| GT_0_75 | 3,049 | **-0.00410478** | **-0.00894485** |

## ATP interpretation

The parent ATP rejection is reinforced rather than explained away by one narrow subgroup.

The largest descriptive damage occurs where the dynamic estimator has the least stable information environment:

- debut / no-prior rows;
- layoffs above 90 days, especially 181+ days;
- zero or very shallow prior point history;
- the highest registered uncertainty bucket.

However, the important result is that **every preregistered ATP stratum is negative on both proper scores**. The dynamic state still loses in:

- ordinary 8–90 day layoff rows;
- deep-history rows with 5,000+ prior points on the weaker side;
- the lowest uncertainty bucket.

Therefore the ATP failure cannot honestly be reduced to sparse history, long layoffs, or high uncertainty alone. Those states amplify the degradation, but a broader mismatch remains. Plausible mechanisms include excessive dynamic aggressiveness, process variance, or mean-reversion behavior relative to real ATP evolution, but this diagnostic is descriptive and does not establish a causal explanation.

## WTA decomposition

### Pair maximum layoff

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| DEBUT_OR_NO_PRIOR | 1,015 | **-0.00294760** | **-0.00647270** |
| 0_7 | 4,654 | **+0.00108581** | **+0.00241376** |
| 8_30 | 12,653 | +0.00022013 | +0.00054670 |
| 31_90 | 5,123 | +0.00043379 | +0.00103754 |
| 91_180 | 1,993 | +0.00038530 | +0.00111794 |
| 181_PLUS | 2,226 | **-0.00182154** | **-0.00369364** |

### Pair minimum prior point depth

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| 0 | 1,312 | **-0.00255445** | **-0.00561228** |
| 1_499 | 1,586 | +0.00061592 | +0.00151024 |
| 500_1999 | 3,086 | +0.00027261 | +0.00077763 |
| 2000_4999 | 3,811 | +0.00041274 | +0.00107712 |
| 5000_PLUS | 17,869 | +0.00020945 | +0.00052414 |

### Pair maximum dynamic serve-logit uncertainty

| Bucket | N | Δ Brier | Δ log loss |
|---|---:|---:|---:|
| LE_0_35 | 1,353 | -0.00001293 | -0.00003626 |
| GT_0_35_LE_0_50 | 16,805 | +0.00020308 | +0.00050686 |
| GT_0_50_LE_0_75 | 6,284 | **+0.00092380** | **+0.00221819** |
| GT_0_75 | 3,222 | **-0.00168162** | **-0.00357088** |

## WTA interpretation

The WTA aggregate result was small and mixed because two regimes offset one another descriptively.

The frozen dynamic candidate tends to improve in common-state rows with:

- layoffs from 0 through 180 days;
- at least some prior point history;
- moderate rather than extreme dynamic uncertainty.

It tends to worsen in:

- debut / no-prior rows;
- zero prior point-depth rows;
- 181+ day layoffs;
- the highest uncertainty bucket.

This pattern is consistent with the aggregate WTA result: small favorable effects across many ordinary-state rows are partially cancelled by larger losses in sparse/extreme-state rows. It is still not grounds for a WTA subgroup model or a production change.

## Decision

1. The default dynamic-state candidate remains **not promoted** for either tour.
2. ATP remains negative evidence against this exact parameterization.
3. WTA remains hypothesis-generating only; no favorable bucket may be selected as a deployment population from this exposed diagnostic.
4. Do not remove debut, sparse-history, long-layoff, or high-uncertainty rows merely because they are unfavorable here.
5. Do not tune process variance, mean-reversion, variance caps or information weights on these exposed results without first registering the complete bounded candidate family and multiplicity treatment.
6. Do not open protected evidence, infer market edge, or alter prospective N from this diagnostic.
7. A legitimate next experiment may test a preregistered bounded family of **less aggressive** dynamic-state parameterizations, because the diagnostic suggests instability is amplified by sparse/extreme states while ATP also retains a broad baseline penalty. That search must be frozen before any candidate outcome is inspected.

No production, protected-data, market-validation, or prospective protocol changed in this diagnostic.
