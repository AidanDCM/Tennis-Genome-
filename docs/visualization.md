# Visualization Concept

Visualization is a human interface to validated mathematical structure. It must never define similarity merely because two pictures look alike.

## 1. Match Signature

Render ordered feature-family bands such as:

```text
STRENGTH | SERVE | RETURN | SURFACE | FORM | FATIGUE | MATCHUP | CONTEXT | QUALITY
```

Values can be normalized and rendered as a waveform/fingerprint. Visual emphasis should reflect validated scale/importance rather than equal pixel allocation.

## 2. Player Profile Overlay

Overlay Player A and B on validated dimensions:
- serve
- return
- surface strength
- movement/style where available
- recent form
- durability/workload

Useful for explanation, not model computation.

## 3. Difference Signature

Primary matchup visualization:

`D_i = feature_A_i - feature_B_i`

Positive values favor A on that dimension, negative values favor B, zero indicates similarity/equality.

## 4. Module similarity

Display historical similarity by family:
- strength
- serve-return
- surface/environment
- form
- fatigue
- style
- context

Example display fields:
- similarity score
- neighbor count/effective sample
- baseline residual in neighbors
- uncertainty

## 5. Historical neighborhood map

Exploratory 2D projection of historical Match Fingerprints with target match highlighted.

Possible uses:
- inspect dense vs sparse regions
- inspect where model errors occur
- inspect outcome/calibration patterns
- discover candidate motifs

Caution: PCA/UMAP/t-SNE visual clusters are not proof of predictive structure. Any discovered region must return to chronological quantitative testing.

## 6. Confidence panel

A final UI should expose why a match is or is not actionable:

```text
Model probability:        68.4%
Market no-vig:            60.1%
Estimated edge:           +8.3 pp
Probability uncertainty:  [64.9%, 71.8%]
Model disagreement:       low
Historical density:       high
Calibration support:      strong
Data quality:             A
Decision:                 BET / PASS
Reason codes:             ...
```

Values above are illustrative only.

## Genetics analogy

Borrow:
- fingerprints
- database alignment
- local/module matching
- motif discovery
- significance/uncertainty

Do not borrow literally:
- nucleotide ordering
- biological inheritance
- sequence-alignment scoring without validation

Tennis features have no natural DNA sequence. The underlying representation is a vector/embedding with time-aware feature families.
